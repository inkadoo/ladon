import json
from pathlib import Path

import asyncpg

from .models import Asset, Evidence, Score, Transfer
from .store import MemoryStore, Report

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


class Database:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @classmethod
    async def connect(cls, url: str, schema: str | None = None) -> "Database":
        settings = {"search_path": schema} if schema else None
        pool = await asyncpg.create_pool(url, min_size=1, max_size=5, statement_cache_size=0, server_settings=settings)
        return cls(pool)

    async def close(self) -> None:
        await self.pool.close()

    async def migrate(self) -> None:
        for path in sorted(MIGRATIONS.glob("*.sql")):
            await self.pool.execute(path.read_text())

    async def load_into(self, store: MemoryStore) -> None:
        async with self.pool.acquire() as conn:
            for row in await conn.fetch("select address, reporter, description, extract(epoch from created_at) as created from reports"):
                store.reports.append(Report(row["address"], row["reporter"], row["description"], float(row["created"])))
            for row in await conn.fetch("select signature, source, destination, asset, amount, ts from transfers"):
                store.transfers.add(Transfer(row["source"], row["destination"], row["amount"], Asset(row["asset"]), row["ts"], row["signature"]))
            for row in await conn.fetch("select address, items from evidence"):
                store.evidence[row["address"]] = [Evidence(**item) for item in json.loads(row["items"])]
            for row in await conn.fetch("select address from checked_wallets"):
                store.checked.add(row["address"])

    async def save_report(self, report: Report) -> None:
        await self.pool.execute(
            "insert into reports (address, reporter, description, created_at) values ($1, $2, $3, to_timestamp($4)) on conflict do nothing",
            report.address, report.reporter, report.description, report.created_at,
        )

    async def save_transfers(self, transfers: list[Transfer]) -> None:
        if not transfers:
            return
        await self.pool.executemany(
            "insert into transfers (signature, source, destination, asset, amount, ts) values ($1, $2, $3, $4, $5, $6) on conflict do nothing",
            [(t.signature, t.source, t.destination, t.asset.value, t.amount, t.timestamp) for t in transfers],
        )

    async def save_evidence(self, address: str, evidence: list[Evidence]) -> None:
        items = json.dumps([{"code": e.code, "weight": e.weight, "text": e.text} for e in evidence])
        await self.pool.execute(
            "insert into evidence (address, items) values ($1, $2::jsonb) on conflict (address) do update set items = excluded.items, updated_at = now()",
            address, items,
        )

    async def mark_checked(self, address: str) -> None:
        await self.pool.execute(
            "insert into checked_wallets (address) values ($1) on conflict (address) do update set checked_at = now()",
            address,
        )

    async def save_scores(self, scores: dict[str, Score]) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("delete from scores")
            if scores:
                await conn.executemany(
                    "insert into scores (address, risk, confidence, flagged, reasons, cluster_size, reports) values ($1, $2, $3, $4, $5::jsonb, $6, $7)",
                    [
                        (
                            s.address, s.risk, s.confidence.value, s.flagged,
                            json.dumps([{"code": r.code, "text": r.text} for r in s.reasons]),
                            s.cluster_size, s.reports,
                        )
                        for s in scores.values()
                    ],
                )
