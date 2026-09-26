import json
from pathlib import Path

import asyncpg

from .models import Asset, Evidence, Score, Takeover, Transfer
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
            for row in await conn.fetch("select address, reporter, description, extract(epoch from created_at) as created, tx_signature from reports"):
                store.reports.append(Report(row["address"], row["reporter"], row["description"], float(row["created"]), row["tx_signature"] or ""))
            rows = await conn.fetch("select signature, source, destination, asset, amount, ts from transfers")
            store.add_transfers([Transfer(r["source"], r["destination"], r["amount"], Asset(r["asset"]), r["ts"], r["signature"]) for r in rows])
            rows = await conn.fetch("select victim, attacker, token_account, ts, signature from takeovers")
            store.add_takeovers([Takeover(r["victim"], r["attacker"], r["token_account"], r["ts"], r["signature"]) for r in rows])
            for row in await conn.fetch("select address from checked_wallets"):
                store.checked.add(row["address"])

    async def save_report(self, report: Report) -> None:
        await self.pool.execute(
            "insert into reports (address, reporter, description, created_at, tx_signature) values ($1, $2, $3, to_timestamp($4), nullif($5, '')) on conflict do nothing",
            report.address, report.reporter, report.description, report.created_at, report.signature,
        )

    async def save_transfers(self, transfers: list[Transfer]) -> None:
        if not transfers:
            return
        await self.pool.executemany(
            "insert into transfers (signature, source, destination, asset, amount, ts) values ($1, $2, $3, $4, $5, $6) on conflict do nothing",
            [(t.signature, t.source, t.destination, t.asset.value, t.amount, t.timestamp) for t in transfers],
        )

    async def save_takeovers(self, takeovers: list[Takeover]) -> None:
        if not takeovers:
            return
        await self.pool.executemany(
            "insert into takeovers (signature, victim, attacker, token_account, ts) values ($1, $2, $3, $4, $5) on conflict do nothing",
            [(t.signature, t.victim, t.attacker, t.token_account, t.timestamp) for t in takeovers],
        )

    async def mark_checked(self, address: str) -> None:
        await self.pool.execute(
            "insert into checked_wallets (address) values ($1) on conflict (address) do update set checked_at = now()",
            address,
        )

    async def save_derived(self, scores: dict[str, Score], evidence: dict[str, list[Evidence]]) -> None:
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("delete from evidence")
            if evidence:
                await conn.executemany(
                    "insert into evidence (address, items) values ($1, $2::jsonb)",
                    [(a, json.dumps([{"code": e.code, "weight": e.weight, "text": e.text} for e in items])) for a, items in evidence.items()],
                )
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
