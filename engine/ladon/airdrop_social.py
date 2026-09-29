import base64
import hashlib
import html
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit

import asyncpg
import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from .airdrop_auth import digest
from .config import Settings

REWARDS = {"x_connect": 25, "x_follow": 50, "x_post": 150}


def post_text(referral_code: str) -> str:
    return (
        "I'm joining Ladon Season 1. @ladon_sol helps Solana users spot wallets linked to scams and rug pulls. "
        "Join the watch and earn participation points: "
        f"https://getladon.vercel.app/airdrop?ref={referral_code} #ad"
    )


def post_id(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        raise HTTPException(400, "Paste the HTTPS link to your post on X.")
    match = re.fullmatch(r"/(?:[A-Za-z0-9_]{1,15}|i/web)/status/([0-9]{1,25})/?", parsed.path)
    if not match:
        raise HTTPException(400, "That is not an X post link.")
    return match[1]


def verify_post(data: dict, user_id: str, expected: str, joined_at: datetime) -> None:
    if data.get("author_id") != user_id or data.get("referenced_tweets"):
        raise HTTPException(400, "Use an original post from your connected X account.")
    try:
        created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        if created < joined_at:
            raise ValueError("old post")
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, "Publish the prepared post after joining Season 1.") from None
    text = data.get("text", "")
    for entity in data.get("entities", {}).get("urls", []):
        if entity.get("url") and entity.get("expanded_url"):
            text = text.replace(entity["url"], entity["expanded_url"])
    if " ".join(html.unescape(text).split()) != " ".join(expected.split()):
        raise HTTPException(400, "The post must contain the prepared text and your referral link.")


class SocialQuests:
    def __init__(self, pool: asyncpg.Pool, settings: Settings):
        self.pool = pool
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.x_client_id and self.settings.x_client_secret and self.settings.airdrop_encryption_key)

    def cipher(self) -> Fernet:
        if not self.enabled:
            raise HTTPException(503, "X reward verification is not available yet. Your wallet points still work.")
        return Fernet(self.settings.airdrop_encryption_key.encode())

    async def status(self, wallet: str) -> dict:
        profile = await self.pool.fetchrow("select referral_code from airdrop_profiles where wallet = $1", wallet)
        if not profile:
            raise HTTPException(400, "Join Season 1 first.")
        account = await self.pool.fetchrow("select username, expires_at, access_token is not null as authorized from airdrop_x_accounts where wallet = $1", wallet)
        tasks = await self.pool.fetch("select task from airdrop_quests where wallet = $1", wallet)
        return {
            "enabled": self.enabled, "rewards": REWARDS,
            "username": account["username"] if account else None,
            "connected": bool(account and account["authorized"] and account["expires_at"] > datetime.now(UTC)),
            "completed": [row["task"] for row in tasks], "post_text": post_text(profile["referral_code"]),
        }

    async def start(self, wallet: str, session: str) -> dict:
        cipher = self.cipher()
        if not await self.pool.fetchval("select wallet from airdrop_profiles where wallet = $1", wallet):
            raise HTTPException(400, "Join Season 1 first.")
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        await self.pool.execute("delete from airdrop_x_pending where expires_at < now()")
        await self.pool.execute(
            "insert into airdrop_x_pending values ($1, $2, $3, $4, now() + interval '10 minutes')",
            digest(state), wallet, digest(session), cipher.encrypt(verifier.encode()).decode(),
        )
        params = {
            "response_type": "code", "client_id": self.settings.x_client_id,
            "redirect_uri": self.settings.x_redirect_uri, "scope": "tweet.read users.read follows.read",
            "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        }
        return {"state": state, "url": "https://x.com/i/oauth2/authorize?" + urlencode(params)}

    @staticmethod
    async def get(client: httpx.AsyncClient, path: str, token: str, params: dict | None = None) -> dict:
        try:
            response = await client.get("https://api.x.com/2/" + path, headers={"Authorization": "Bearer " + token}, params=params)
        except httpx.HTTPError:
            raise HTTPException(503, "X is unavailable right now. Please try again later.") from None
        if response.status_code == 401:
            raise HTTPException(409, "Reconnect X to renew your verification access.")
        if response.status_code == 404:
            raise HTTPException(400, "X could not find that public post or account.")
        if response.status_code != 200:
            raise HTTPException(503, "X could not verify this task right now. No points were awarded.")
        return response.json()

    async def complete(self, wallet: str, session: str, state: str, code: str) -> None:
        cipher = self.cipher()
        row = await self.pool.fetchrow(
            "delete from airdrop_x_pending where state_hash = $1 and wallet = $2 and session_hash = $3 and expires_at > now() returning verifier",
            digest(state), wallet, digest(session),
        )
        if not row:
            raise HTTPException(400, "This X connection request expired or was already used. Try connecting again.")
        try:
            verifier = cipher.decrypt(row["verifier"].encode()).decode()
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.x.com/2/oauth2/token", auth=(self.settings.x_client_id, self.settings.x_client_secret),
                    data={"grant_type": "authorization_code", "code": code, "redirect_uri": self.settings.x_redirect_uri, "code_verifier": verifier},
                )
                if response.status_code != 200:
                    raise HTTPException(400, "X could not finish connecting. Please try again.")
                credentials = response.json()
                token = credentials["access_token"]
                user = (await self.get(client, "users/me", token))["data"]
        except (httpx.HTTPError, InvalidToken, KeyError, ValueError):
            raise HTTPException(503, "X could not finish connecting. Please try again later.") from None
        try:
            async with self.pool.acquire() as conn, conn.transaction():
                await conn.fetchval("select wallet from airdrop_profiles where wallet = $1 for update", wallet)
                existing = await conn.fetchval("select user_id from airdrop_x_accounts where wallet = $1", wallet)
                if existing and existing != user["id"]:
                    raise HTTPException(409, "Use the X account already linked to this wallet for Season 1.")
                expires = datetime.now(UTC) + timedelta(seconds=min(int(credentials.get("expires_in", 7200)), 7200))
                await conn.execute(
                    "insert into airdrop_x_accounts values ($1, $2, $3, $4, $5) "
                    "on conflict (wallet) do update set username = excluded.username, access_token = excluded.access_token, expires_at = excluded.expires_at",
                    wallet, user["id"], user["username"], cipher.encrypt(token.encode()).decode(), expires,
                )
                await self.award(conn, wallet, "x_connect", user["id"])
        except asyncpg.UniqueViolationError:
            raise HTTPException(409, "That X account is already linked to another Season 1 wallet.") from None

    @staticmethod
    async def award(conn: asyncpg.Connection, wallet: str, task: str, proof: str) -> bool:
        inserted = await conn.fetchval(
            "insert into airdrop_quests (wallet, task, proof) values ($1, $2, $3) on conflict do nothing returning task",
            wallet, task, proof,
        )
        if not inserted:
            return False
        await conn.execute(
            "insert into airdrop_events (wallet, kind, points, reference) values ($1, 'social', $2, $3)", wallet, REWARDS[task], task,
        )
        return True

    async def claim(self, wallet: str, task: str, url: str = "") -> bool:
        cipher = self.cipher()
        if task not in {"x_follow", "x_post"}:
            raise HTTPException(400, "Unknown task.")
        if await self.pool.fetchval("select task from airdrop_quests where wallet = $1 and task = $2", wallet, task):
            return False
        row = await self.pool.fetchrow("select * from airdrop_x_accounts where wallet = $1", wallet)
        if not row or not row["access_token"] or row["expires_at"] <= datetime.now(UTC):
            raise HTTPException(409, "Connect X before verifying this task.")
        try:
            token = cipher.decrypt(row["access_token"].encode()).decode()
        except InvalidToken:
            raise HTTPException(409, "Reconnect X before verifying this task.") from None
        async with httpx.AsyncClient(timeout=15) as client:
            if task == "x_follow":
                cursor = None
                found = False
                for _ in range(10):
                    params = {"max_results": 1000}
                    if cursor:
                        params["pagination_token"] = cursor
                    page = await self.get(client, f"users/{row['user_id']}/following", token, params)
                    found = any(user.get("username", "").lower() == "ladon_sol" for user in page.get("data", []))
                    cursor = page.get("meta", {}).get("next_token")
                    if found or not cursor:
                        break
                if not found:
                    raise HTTPException(400, "We could not verify your follow yet. Follow @ladon_sol, then try again.")
                proof = row["user_id"]
            else:
                proof = post_id(url)
                result = await self.get(client, f"tweets/{proof}", token, {"tweet.fields": "author_id,created_at,entities,referenced_tweets"})
                profile = await self.pool.fetchrow("select referral_code, created_at from airdrop_profiles where wallet = $1", wallet)
                verify_post(result.get("data", {}), row["user_id"], post_text(profile["referral_code"]), profile["created_at"])
        async with self.pool.acquire() as conn, conn.transaction():
            return await self.award(conn, wallet, task, proof)

    async def disconnect(self, wallet: str) -> None:
        # Keep the account binding and completed quest proofs to prevent repeated rewards.
        await self.pool.execute("update airdrop_x_accounts set access_token = null, expires_at = null where wallet = $1", wallet)
