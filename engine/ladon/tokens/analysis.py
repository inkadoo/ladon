import asyncio
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .scoring import TokenSignals, score_token
from .sources import DexScreener, HeliusRpc, SourceError

MINT_INSTRUCTIONS = {"initializeMint", "initializeMint2"}
SYSTEM_PROGRAM = "11111111111111111111111111111111"
DEPLOYER_HISTORY = 1000
FUNDER_HISTORY = 1000
LINKED_HISTORY = 300
LINKED_WALLETS = 8
BUSY_FUNDER_RECIPIENTS = 100
BUSY_FUNDER_SPAN_SECONDS = 24 * 3600
PAST_TOKEN_LIMIT = 60
LINKED_BUDGET_SECONDS = 4
RUG_LIQUIDITY_USD = 1_000
ACTIVE_LIQUIDITY_USD = 10_000
RUG_MIN_AGE_SECONDS = 24 * 3600
CACHE_SECONDS = 600
PARTIAL_CACHE_SECONDS = 60


class NotAToken(Exception):
    pass


def fee_payer(tx: dict[str, Any]) -> str | None:
    keys = ((tx.get("transaction") or {}).get("message") or {}).get("accountKeys") or []
    if not keys:
        return None
    first = keys[0]
    return first.get("pubkey") if isinstance(first, dict) else first


def instructions(tx: dict[str, Any]):
    yield from ((tx.get("transaction") or {}).get("message") or {}).get("instructions") or []
    for group in (tx.get("meta") or {}).get("innerInstructions") or []:
        yield from group.get("instructions") or []


def _parsed(ins: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    parsed = ins.get("parsed")
    if not isinstance(parsed, dict):
        return None, {}
    return parsed.get("type"), parsed.get("info") or {}


def created_mints(txs: list[dict[str, Any]], wallet: str) -> dict[str, int]:
    mints: dict[str, int] = {}
    for tx in txs:
        if fee_payer(tx) != wallet:
            continue
        for ins in instructions(tx):
            kind, info = _parsed(ins)
            if kind in MINT_INSTRUCTIONS and info.get("mint"):
                mints.setdefault(info["mint"], int(tx.get("blockTime") or 0))
    return mints


def _system_transfers(txs: list[dict[str, Any]]):
    for tx in txs:
        for ins in instructions(tx):
            if ins.get("programId") != SYSTEM_PROGRAM:
                continue
            kind, info = _parsed(ins)
            if kind == "transfer" and info.get("source") and info.get("destination"):
                yield info["source"], info["destination"]
            elif kind == "createAccount" and info.get("source") and info.get("newAccount"):
                yield info["source"], info["newAccount"]


def first_funder(oldest_first: list[dict[str, Any]], wallet: str) -> str | None:
    for source, destination in _system_transfers(oldest_first):
        if destination == wallet and source != wallet:
            return source
    return None


def sol_recipients(txs: list[dict[str, Any]], wallet: str) -> list[str]:
    counts = Counter(d for s, d in _system_transfers(txs) if s == wallet and d != wallet)
    return [address for address, _ in counts.most_common()]


def is_busy(history: list[dict[str, Any]], recipients: list[str], page_size: int) -> bool:
    if len(recipients) >= BUSY_FUNDER_RECIPIENTS:
        return True
    times = [int(t["blockTime"]) for t in history if t.get("blockTime")]
    return len(history) >= page_size and bool(times) and max(times) - min(times) < BUSY_FUNDER_SPAN_SECONDS


def classify(pairs: list[dict[str, Any]], created_at: int, now: float) -> str:
    if not pairs:
        return "unknown"
    liquidity = max(float((p.get("liquidity") or {}).get("usd") or 0) for p in pairs)
    if liquidity >= ACTIVE_LIQUIDITY_USD:
        return "active"
    if liquidity < RUG_LIQUIDITY_USD and now - created_at >= RUG_MIN_AGE_SECONDS:
        return "likely rug"
    return "unknown"


def _iso(ts: int | float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


class TokenChecker:
    def __init__(self, rpc: HeliusRpc, dex: DexScreener, excluded: frozenset[str] = frozenset(), clock=time.time):
        self.rpc = rpc
        self.dex = dex
        self.excluded = excluded
        self.clock = clock
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def check(self, mint: str) -> dict[str, Any]:
        cached = self._cache.get(mint)
        if cached and cached[0] > self.clock():
            return cached[1]
        result = await self._check(mint)
        partial = any(r["label"] == "Not checked" or r["label"].endswith("not checked") for r in result["reasons"])
        self._cache[mint] = (self.clock() + (PARTIAL_CACHE_SECONDS if partial else CACHE_SECONDS), result)
        return result

    async def _check(self, mint: str) -> dict[str, Any]:
        now = self.clock()
        unchecked: list[str] = []

        info_task = asyncio.create_task(self.rpc.mint(mint))
        creation_task = asyncio.create_task(self.rpc.history(mint, oldest_first=True, limit=1))
        try:
            info = await info_task
        except SourceError:
            info = {}
            unchecked.append("We could not read this token's settings from Helius.")
        if info is None:
            creation_task.cancel()
            raise NotAToken(mint)
        try:
            creation = await creation_task
        except SourceError:
            creation = []

        deployer = fee_payer(creation[0]) if creation else None
        created_at = int(creation[0].get("blockTime") or now) if creation else int(now)
        if not deployer:
            unchecked.append("We could not find the transaction that created this token.")

        deployer_tokens: dict[str, int] | None = None
        linked_tokens: dict[str, int] | None = None
        funder: str | None = None
        funder_is_busy = False
        deployer_age_hours: float | None = None

        if deployer:
            try:
                oldest, recent = await asyncio.gather(
                    self.rpc.history(deployer, oldest_first=True, limit=20),
                    self.rpc.history(deployer, oldest_first=False, limit=DEPLOYER_HISTORY),
                )
                deployer_tokens = {m: t for m, t in created_mints(recent, deployer).items() if m != mint}
                funder = first_funder(oldest, deployer)
                if oldest and oldest[0].get("blockTime"):
                    deployer_age_hours = (created_at - int(oldest[0]["blockTime"])) / 3600
            except SourceError:
                unchecked.append("We could not load the deployer's history from Helius.")

        if funder and funder not in self.excluded:
            try:
                linked_tokens, funder_is_busy = await asyncio.wait_for(
                    self._linked_tokens(funder, deployer or "", mint), LINKED_BUDGET_SECONDS
                )
            except (SourceError, TimeoutError):
                unchecked.append("We ran out of time tracing the wallets linked to this deployer's funder.")
        elif funder:
            funder_is_busy = True

        past = {**{m: (t, "linked wallet") for m, t in (linked_tokens or {}).items()}, **{m: (t, "deployer") for m, t in (deployer_tokens or {}).items()}}
        newest = sorted(past.items(), key=lambda kv: kv[1][0], reverse=True)[:PAST_TOKEN_LIMIT]
        outcomes: dict[str, str] = {}
        if newest:
            try:
                pairs = await self.dex.pairs([m for m, _ in newest])
                outcomes = {m: classify(pairs.get(m, []), t, now) for m, (t, _) in newest}
            except SourceError:
                unchecked.append("We could not reach DexScreener to see how this deployer's past tokens are trading.")

        def rugs(by: str) -> int | None:
            theirs = [m for m, (_, who) in newest if who == by]
            if not theirs:
                return 0
            if not outcomes:
                return None
            return sum(1 for m in theirs if outcomes.get(m) == "likely rug")

        signals = TokenSignals(
            deployer_rugs=rugs("deployer") if deployer_tokens is not None else None,
            linked_rugs=rugs("linked wallet") if linked_tokens is not None else None,
            funder_is_busy=funder_is_busy,
            mint_authority=bool(info.get("mintAuthority")) if info else None,
            freeze_authority=bool(info.get("freezeAuthority")) if info else None,
            deployer_age_hours=deployer_age_hours,
            unchecked=tuple(unchecked),
        )
        risk = score_token(signals)
        return {
            "mint": mint,
            "deployer": deployer,
            "funder": funder,
            "score": risk.score,
            "level": risk.level.value,
            "reasons": [{"label": r.label, "explanation": r.explanation, "points": r.points} for r in risk.reasons],
            "past_tokens": [
                {"mint": m, "created_at": _iso(t), "outcome": outcomes.get(m, "unknown"), "created_by": who}
                for m, (t, who) in newest
            ],
            "checked_at": _iso(now),
        }

    async def _linked_tokens(self, funder: str, deployer: str, mint: str) -> tuple[dict[str, int] | None, bool]:
        history = await self.rpc.history(funder, oldest_first=False, limit=FUNDER_HISTORY)
        recipients = [w for w in sol_recipients(history, funder) if w != deployer and w not in self.excluded]
        if is_busy(history, recipients, FUNDER_HISTORY):
            return None, True
        tokens = {m: t for m, t in created_mints(history, funder).items() if m != mint}
        wallets = recipients[:LINKED_WALLETS]
        histories = await asyncio.gather(*(self.rpc.history(w, oldest_first=False, limit=LINKED_HISTORY) for w in wallets))
        for wallet, txs in zip(wallets, histories):
            for m, t in created_mints(txs, wallet).items():
                if m != mint:
                    tokens.setdefault(m, t)
        return tokens, False
