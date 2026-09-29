import asyncio
import os
import secrets

import asyncpg
import pytest
from fastapi.testclient import TestClient

from ladon.airdrop import Airdrop, AirdropError
from ladon.api import create_app
from ladon.config import Settings
from ladon.db import Database
from helpers import wallet


def test_airdrop_rejects_invalid_wallets():
    client = TestClient(create_app(Settings(reporter_salt="test")))
    assert client.post("/v1/airdrop/join", json={"wallet": "bad"}).status_code == 400
    assert client.post("/v1/airdrop/checkin", json={"wallet": "bad"}).status_code == 400
    assert client.post("/v1/airdrop/wallet-check", json={"wallet": wallet("owner"), "target": "bad"}).status_code == 400


@pytest.mark.skipif(not os.environ.get("LADON_TEST_DATABASE_URL"), reason="set LADON_TEST_DATABASE_URL to run database tests")
def test_airdrop_rewards_are_atomic_and_unique():
    async def run():
        url = os.environ["LADON_TEST_DATABASE_URL"]
        schema = f"ladon_test_{secrets.token_hex(4)}"
        admin = await asyncpg.connect(url, statement_cache_size=0)
        await admin.execute(f"create schema {schema}")
        try:
            db = await Database.connect(url, schema=schema)
            await db.migrate()
            service = Airdrop(db.pool)
            inviter, invitee, other = wallet("inviter"), wallet("invitee"), wallet("other")

            assert await service.join(inviter)
            assert not await service.join(inviter)
            code = (await service.profile(inviter))["referral_code"]
            with pytest.raises(AirdropError, match="own"):
                await service.join(inviter, code)

            assert await service.join(invitee, code)
            assert not await service.join(invitee, code)
            assert (await service.profile(inviter))["points"] == 150
            assert (await service.profile(invitee))["points"] == 75
            assert (await service.profile(inviter))["referral_count"] == 1
            assert await db.pool.fetchval("select count(*) from airdrop_referrals where invitee = $1", invitee) == 1

            assert await service.checkin(invitee)
            assert not await service.checkin(invitee)
            assert (await service.profile(invitee))["points"] == 85

            targets = [wallet(f"target-{i}") for i in range(6)]
            assert await service.wallet_check(invitee, targets[0])
            assert not await service.wallet_check(invitee, targets[0])
            for target in targets[1:5]:
                assert await service.wallet_check(invitee, target)
            assert not await service.wallet_check(invitee, targets[5])
            assert (await service.profile(invitee))["checks_today"] == 5
            assert (await service.profile(invitee))["points"] == 110

            assert await service.join(other)
            assert not await service.join(other, code)  # Existing wallets cannot gain referral attribution later.
            assert (await service.profile(other))["points"] == 50
            await db.close()
        finally:
            await admin.execute(f"drop schema {schema} cascade")
            await admin.close()

    asyncio.run(run())
