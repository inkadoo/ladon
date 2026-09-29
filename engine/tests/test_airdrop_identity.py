import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ladon.addresses import b58encode
from ladon.airdrop import Airdrop
from ladon.airdrop_auth import AirdropAuth, digest
from ladon.airdrop_social import SocialQuests, post_id, post_text, verify_post
from ladon.api import create_app
from ladon.config import Settings
from ladon.db import Database
from ladon.engine import Engine
from ladon.store import MemoryStore
from helpers import wallet

URL = os.environ.get("LADON_TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not URL, reason="set LADON_TEST_DATABASE_URL for database tests")


@asynccontextmanager
async def database():
    schema = f"ladon_identity_test_{secrets.token_hex(4)}"
    admin = await asyncpg.connect(URL, statement_cache_size=0)
    await admin.execute(f"create schema {schema}")
    db = None
    try:
        db = await Database.connect(URL, schema=schema)
        await db.migrate()
        yield db
    finally:
        if db:
            await db.close()
        await admin.execute(f"drop schema {schema} cascade")
        await admin.close()


def test_wallet_challenge_rejects_untrusted_origin_before_database():
    client = TestClient(create_app(Settings()))
    response = client.post("/v1/airdrop/auth/challenge", json={"wallet": wallet("a")}, headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403


@pytest.mark.parametrize("url", ["https://evil.example/a/status/123", "http://x.com/a/status/123", "https://x.com/a", "https://x.com/a/status/123/extra"])
def test_rejects_non_post_urls(url):
    with pytest.raises(HTTPException):
        post_id(url)


def test_post_verification_checks_author_text_and_age():
    expected = post_text("ABC123")
    now = datetime.now(UTC)
    post = {"author_id": "123", "created_at": now.isoformat(), "text": expected.replace("https://getladon.vercel.app/airdrop?ref=ABC123", "https://t.co/abc"), "entities": {"urls": [{"url": "https://t.co/abc", "expanded_url": "https://getladon.vercel.app/airdrop?ref=ABC123"}]}}
    verify_post(post, "123", expected, now - timedelta(seconds=1))
    assert post_id("https://x.com/user/status/123?s=20") == "123"
    for changed in [{"author_id": "456"}, {"text": "different message"}, {"created_at": (now - timedelta(days=1)).isoformat()}, {"referenced_tweets": [{"type": "retweeted"}]}]:
        with pytest.raises(HTTPException):
            verify_post({**post, **changed}, "123", expected, now - timedelta(seconds=1))


@needs_db
def test_wallet_signature_replay_expiry_and_session_isolation():
    async def run():
        async with database() as db:
            auth = AirdropAuth(db.pool)
            key = Ed25519PrivateKey.generate()
            address = b58encode(key.public_key().public_bytes_raw())
            challenge = await auth.challenge(address, "https://getladon.vercel.app")
            assert "does not authorize transactions" in challenge["message"]
            wrong = Ed25519PrivateKey.generate().sign(challenge["message"].encode())
            with pytest.raises(HTTPException):
                await auth.verify(address, challenge["nonce"], b58encode(wrong))
            signature = b58encode(key.sign(challenge["message"].encode()))
            session = await auth.verify(address, challenge["nonce"], signature)
            assert await auth.wallet(session["token"]) == address
            app = create_app(Settings(), engine=Engine(MemoryStore(), db=db))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/v1/airdrop/join", json={"wallet": address})
                assert response.status_code == 401
                headers = {"Authorization": "Bearer " + session["token"]}
                response = await client.post("/v1/airdrop/join", json={"wallet": wallet("different")}, headers=headers)
                assert response.status_code == 403
                response = await client.post("/v1/airdrop/join", json={"wallet": address}, headers=headers)
                assert response.status_code == 200
                assert response.json()["profile"]["points"] == 50
            with pytest.raises(HTTPException):
                await auth.verify(address, challenge["nonce"], signature)
            expired = await auth.challenge(address, "https://getladon.vercel.app")
            await db.pool.execute("update airdrop_challenges set expires_at = now() - interval '1 second' where nonce = $1", expired["nonce"])
            with pytest.raises(HTTPException):
                await auth.verify(address, expired["nonce"], b58encode(key.sign(expired["message"].encode())))
            await db.pool.execute("delete from airdrop_sessions where token_hash = $1", digest(session["token"]))
            with pytest.raises(HTTPException):
                await auth.wallet(session["token"])
    asyncio.run(run())


@needs_db
def test_social_oauth_binding_and_rewards_are_once(monkeypatch):
    async def run():
        async with database() as db:
            settings = Settings(x_client_id="client", x_client_secret="secret", airdrop_encryption_key=Fernet.generate_key().decode())
            service = SocialQuests(db.pool, settings)
            points = Airdrop(db.pool)
            owner, second = wallet("owner"), wallet("second")
            await points.join(owner)
            await points.join(second)
            profile = await points.profile(owner)
            expected = post_text(profile["referral_code"])
            follows = False
            def handler(request):
                if request.url.path == "/2/oauth2/token":
                    return httpx.Response(200, json={"access_token": "x-access", "expires_in": 7200})
                if request.url.path == "/2/users/me":
                    return httpx.Response(200, json={"data": {"id": "123", "username": "earlywatch"}})
                if request.url.path.endswith("/following"):
                    return httpx.Response(200, json={"data": [{"username": "ladon_sol"}] if follows else []})
                if request.url.path == "/2/tweets/987":
                    return httpx.Response(200, json={"data": {"id": "987", "author_id": "123", "text": expected, "created_at": datetime.now(UTC).isoformat()}})
                return httpx.Response(500)
            factory = httpx.AsyncClient
            with monkeypatch.context() as patch:
                patch.setattr(httpx, "AsyncClient", lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs))
                pending = await service.start(owner, "session-a")
                with pytest.raises(HTTPException):
                    await service.complete(owner, "session-b", pending["state"], "code")
                await service.complete(owner, "session-a", pending["state"], "code")
                assert (await points.profile(owner))["points"] == 75
                with pytest.raises(HTTPException):
                    await service.complete(owner, "session-a", pending["state"], "code")
                with pytest.raises(HTTPException):
                    await service.claim(owner, "x_follow")
                assert (await points.profile(owner))["points"] == 75
                follows = True
                assert await service.claim(owner, "x_follow")
                assert not await service.claim(owner, "x_follow")
                assert await service.claim(owner, "x_post", "https://x.com/earlywatch/status/987")
                assert not await service.claim(owner, "x_post", "https://x.com/earlywatch/status/987")
                assert (await points.profile(owner))["points"] == 275
                pending = await service.start(second, "session-c")
                with pytest.raises(HTTPException, match="already linked"):
                    await service.complete(second, "session-c", pending["state"], "code")
                assert (await points.profile(second))["points"] == 50
                await service.disconnect(owner)
                assert not (await service.status(owner))["connected"]
                assert len((await service.status(owner))["completed"]) == 3
    asyncio.run(run())
