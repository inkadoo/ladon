import asyncio
import os
import secrets

import asyncpg
import pytest

from ladon.db import Database
from ladon.engine import Engine
from ladon.store import MemoryStore
from helpers import FakeHelius, helius_tx, signature, takeover_tx, wallet

URL = os.environ.get("LADON_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set LADON_TEST_DATABASE_URL to run database tests")

DRAINER, OPERATOR = wallet("drainer"), wallet("operator")


async def round_trip() -> None:
    schema = f"ladon_test_{secrets.token_hex(4)}"
    admin = await asyncpg.connect(URL, statement_cache_size=0)
    await admin.execute(f"create schema {schema}")
    try:
        db = await Database.connect(URL, schema=schema)
        await db.migrate()
        history = {OPERATOR: [helius_tx(DRAINER, OPERATOR, 11_000_000_000, 1_700_000_000, "d")]}
        drain = takeover_tx(wallet("victim"), OPERATOR, wallet("victim-usdc"), 1_700_000_100, signature("drain"))
        engine = Engine(MemoryStore(), known_drainers=frozenset({DRAINER}), helius=FakeHelius(history, [drain]), db=db)
        await engine.report(OPERATOR, "reporter-hash", "Took my SOL", signature("drain"))
        await engine.check(OPERATOR, signature("drain"))
        await db.close()

        db = await Database.connect(URL, schema=schema)
        restored = Engine(MemoryStore(), known_drainers=frozenset({DRAINER}), db=db)
        await db.load_into(restored.store)
        restored.rescore()
        assert restored.store.report_count(OPERATOR) == 1
        assert restored.store.reports[0].signature == signature("drain")
        assert len(restored.store.takeovers) == 1
        assert restored.lookup(OPERATOR) == engine.lookup(OPERATOR)
        assert restored.lookup(OPERATOR).flagged
        stored = await db.pool.fetchval("select count(*) from scores where flagged")
        assert stored >= 1
        await db.close()
    finally:
        await admin.execute(f"drop schema {schema} cascade")
        await admin.close()


def test_database_round_trip():
    asyncio.run(round_trip())
