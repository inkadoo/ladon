import asyncio
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .scoring import TokenSignals, score_token
from .sources import DexScreener, HeliusRpc, SourceError
from .trading import creator_sale, launch_bundle

MINT_INSTRUCTIONS = {"initializeMint", "initializeMint2"}
SYSTEM_PROGRAM = "11111111111111111111111111111111"
DEPLOYER_HISTORY = 1000
FUNDER_HISTORY = 1000
LINKED_HISTORY = 300
LAUNCH_HISTORY = 200
LINKED_WALLETS = 8
BUSY_FUNDER_RECIPIENTS = 100
BUSY_FUNDER_SPAN_SECONDS = 24 * 3600
PAST_TOKEN_LIMIT = 60
LINKED_BUDGET_SECONDS = 4
HOLDERS_BUDGET_SECONDS = 4
ACTIVE_LIQUIDITY_USD = 10_000
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


def classify(pairs: list[dict[str, Any]], dumped: bool) -> str:
    if dumped:
        return "likely rug"
    liquidity = max((float((p.get("liquidity") or {}).get("usd") or 0) for p in pairs), default=0)
    return "active" if liquidity >= ACTIVE_LIQUIDITY_USD else "unknown"


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
        launch_task = asyncio.create_task(self.rpc.history(mint, oldest_first=True, limit=LAUNCH_HISTORY))
        holders_task = asyncio.create_task(self._holders(mint))
        try:
            info = await info_task
        except SourceError:
            info = {}
            unchecked.append("We could not read this token's settings from Helius.")
        if info is None:
            launch_task.cancel()
            holders_task.cancel()
            raise NotAToken(mint)
        try:
            launch = await launch_task
        except SourceError:
            launch = []

        deployer = fee_payer(launch[0]) if launch else None
        created_at = int(launch[0].get("blockTime") or now) if launch else int(now)
        if not deployer:
            unchecked.append("We could not find the transaction that created this token.")

        recent: list[dict[str, Any]] | None = None
        deployer_tokens: dict[str, int] | None = None
        funder: str | None = None
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

        linked: dict[str, tuple[int, str]] | None = None
        histories: dict[str, list[dict[str, Any]]] = {deployer: recent} if deployer and recent is not None else {}
        funder_is_busy = False
        if funder and funder not in self.excluded:
            try:
                linked, linked_histories, funder_is_busy = await asyncio.wait_for(
                    self._linked_tokens(funder, deployer or "", mint), LINKED_BUDGET_SECONDS
                )
                histories.update(linked_histories)
            except (SourceError, TimeoutError):
                unchecked.append("We ran out of time tracing the wallets linked to this deployer's funder.")
        elif funder:
            funder_is_busy = True

        past: dict[str, tuple[int, str, str]] = {m: (t, w, "linked wallet") for m, (t, w) in (linked or {}).items()}
        past.update({m: (t, deployer, "deployer") for m, t in (deployer_tokens or {}).items() if deployer})
        newest = sorted(past.items(), key=lambda kv: kv[1][0], reverse=True)[:PAST_TOKEN_LIMIT]
        dumped = {m: creator_sale(histories.get(w) or [], w, m, t).dumped for m, (t, w, _) in newest}
        try:
            pairs = await self.dex.pairs([m for m, _ in newest]) if newest else {}
        except SourceError:
            pairs = {}
            unchecked.append("We could not reach DexScreener to see which of the deployer's past tokens are still trading.")
        outcomes = {m: classify(pairs.get(m, []), dumped[m]) for m, _ in newest}

        def rugs(by: str) -> int:
            return sum(1 for m, (_, _, who) in newest if who == by and outcomes[m] == "likely rug")

        sale = creator_sale(recent, deployer, mint, created_at) if deployer and recent is not None else None
        bundle_bought: float | None = None
        bundle_held: float | None = None
        try:
            holdings, supply = await asyncio.wait_for(holders_task, HOLDERS_BUDGET_SECONDS)
            if launch and deployer and supply:
                funded = set(sol_recipients(recent or [], deployer))
                bundle = launch_bundle(launch, mint, deployer, funded, holdings, supply)
                bundle_bought, bundle_held = bundle.bought_share, bundle.held_share
        except (SourceError, TimeoutError):
            unchecked.append("We could not load this token's largest holders in time.")

        signals = TokenSignals(
            deployer_rugs=rugs("deployer") if deployer_tokens is not None else None,
            linked_rugs=rugs("linked wallet") if linked is not None else None,
            funder_is_busy=funder_is_busy,
            mint_authority=bool(info.get("mintAuthority")) if info else None,
            freeze_authority=bool(info.get("freezeAuthority")) if info else None,
            deployer_age_hours=deployer_age_hours,
            creator_sold_share=sale.share if sale else None,
            creator_held_any=bool(sale and sale.peak),
            bundle_bought_share=bundle_bought,
            bundle_held_share=bundle_held,
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
                {"mint": m, "created_at": _iso(t), "outcome": outcomes[m], "created_by": who}
                for m, (t, _, who) in newest
            ],
            "checked_at": _iso(now),
        }

    async def _holders(self, mint: str) -> tuple[dict[str, int], int]:
        holdings, supply = await asyncio.gather(self.rpc.largest_holders(mint), self.rpc.supply(mint))
        return holdings, supply

    async def _linked_tokens(self, funder: str, deployer: str, mint: str):
        history = await self.rpc.history(funder, oldest_first=False, limit=FUNDER_HISTORY)
        recipients = [w for w in sol_recipients(history, funder) if w != deployer and w not in self.excluded]
        if is_busy(history, recipients, FUNDER_HISTORY):
            return None, {}, True
        tokens = {m: (t, funder) for m, t in created_mints(history, funder).items() if m != mint}
        wallets = recipients[:LINKED_WALLETS]
        fetched = await asyncio.gather(*(self.rpc.history(w, oldest_first=False, limit=LINKED_HISTORY) for w in wallets))
        histories = {funder: history, **dict(zip(wallets, fetched))}
        for wallet, txs in zip(wallets, fetched):
            for m, t in created_mints(txs, wallet).items():
                if m != mint:
                    tokens.setdefault(m, (t, wallet))
        return tokens, histories, False
