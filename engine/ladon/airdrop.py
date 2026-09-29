"""Season 1 participation ledger. All awards happen in database transactions."""

import secrets
from datetime import UTC, datetime, timedelta

import asyncpg


class AirdropError(ValueError):
    pass


def utc_day(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).date().isoformat()


class Airdrop:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def join(self, wallet: str, referral_code: str | None = None) -> bool:
        async with self.pool.acquire() as conn, conn.transaction():
            inviter = None
            if referral_code:
                inviter = await conn.fetchval("select wallet from airdrop_profiles where referral_code = $1", referral_code.upper())
                if inviter is None:
                    raise AirdropError("That referral code was not found.")
                if inviter == wallet:
                    raise AirdropError("You cannot use your own referral code.")
            # A code collision is vanishingly unlikely, but the unique index remains the authority.
            for _ in range(3):
                code = secrets.token_hex(6).upper()
                try:
                    async with conn.transaction():
                        created = await conn.fetchval(
                            "insert into airdrop_profiles (wallet, referral_code) values ($1, $2) "
                            "on conflict (wallet) do nothing returning wallet", wallet, code,
                        )
                    break
                except asyncpg.UniqueViolationError:
                    continue
            else:
                raise AirdropError("Could not create a referral code. Please try again.")
            if not created:
                return False
            await conn.execute(
                "insert into airdrop_events (wallet, kind, points, reference) values ($1, 'join', 50, 'season-1')", wallet,
            )
            if inviter:
                await conn.execute("insert into airdrop_referrals (invitee, inviter) values ($1, $2)", wallet, inviter)
                await conn.execute(
                    "insert into airdrop_events (wallet, kind, points, reference) values ($1, 'referral_inviter', 100, $2)", inviter, wallet,
                )
                await conn.execute(
                    "insert into airdrop_events (wallet, kind, points, reference) values ($1, 'referral_invitee', 25, $2)", wallet, inviter,
                )
            return True

    async def checkin(self, wallet: str) -> bool:
        today = datetime.now(UTC).date()
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow("select streak, last_checkin from airdrop_profiles where wallet = $1 for update", wallet)
            if not row:
                raise AirdropError("Join Season 1 first.")
            if row["last_checkin"] == today:
                return False
            streak = row["streak"] + 1 if row["last_checkin"] == today - timedelta(days=1) else 1
            await conn.execute("update airdrop_profiles set streak = $2, last_checkin = $3 where wallet = $1", wallet, streak, today)
            await conn.execute(
                "insert into airdrop_events (wallet, kind, points, reference) values ($1, 'checkin', 10, $2)", wallet, today.isoformat(),
            )
            return True

    async def wallet_check(self, wallet: str, target: str) -> bool:
        today = utc_day()
        async with self.pool.acquire() as conn, conn.transaction():
            exists = await conn.fetchval("select wallet from airdrop_profiles where wallet = $1 for update", wallet)
            if not exists:
                raise AirdropError("Join Season 1 first.")
            count = await conn.fetchval(
                "select count(*) from airdrop_events where wallet = $1 and kind = 'wallet_check' and reference like $2",
                wallet, today + ':%',
            )
            if count >= 5:
                return False
            inserted = await conn.fetchval(
                "insert into airdrop_events (wallet, kind, points, reference) values ($1, 'wallet_check', 5, $2) "
                "on conflict (wallet, kind, reference) do nothing returning id", wallet, f"{today}:{target}",
            )
            return inserted is not None

    async def profile(self, wallet: str) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "select p.wallet, p.referral_code, p.streak, p.last_checkin, p.created_at, "
                "coalesce((select sum(points) from airdrop_events where wallet = p.wallet), 0) as points, "
                "(select count(*) from airdrop_referrals where inviter = p.wallet) as referral_count, "
                "(select count(*) from airdrop_events where wallet = p.wallet and kind = 'wallet_check' and reference like $2) as checks_today "
                "from airdrop_profiles p where p.wallet = $1", wallet, utc_day() + ':%',
            )
            if not row:
                return None
            points = int(row["points"])
            rank = await conn.fetchval(
                "select count(*) + 1 from (select wallet, sum(points) as total from airdrop_events group by wallet) scores "
                "where total > $1 or (total = $1 and wallet < $2)", points, wallet,
            )
            milestone = ((points // 100) + 1) * 100
            return {
                "wallet": wallet, "points": points, "streak": row["streak"],
                "last_checkin": row["last_checkin"].isoformat() if row["last_checkin"] else None,
                "checks_today": int(row["checks_today"]), "referral_code": row["referral_code"],
                "referral_count": int(row["referral_count"]), "rank": int(rank),
                "next_milestone": milestone, "season_status": "active",
            }

    async def leaderboard(self) -> list[dict]:
        rows = await self.pool.fetch(
            "select p.wallet, coalesce(sum(e.points), 0) as points from airdrop_profiles p "
            "left join airdrop_events e on e.wallet = p.wallet group by p.wallet "
            "order by points desc, p.wallet asc limit 20"
        )
        return [{"rank": i, "wallet": row["wallet"][:4] + '…' + row["wallet"][-4:], "points": int(row["points"])}
                for i, row in enumerate(rows, 1)]
