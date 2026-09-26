import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..models import Evidence, Reason, Transfer
from ..tokens.sources import HeliusRpc, SourceError
from .parse import delegated_pulls, sol_transfers
from .patterns import layering, money_flow, own_actions

HISTORY = 1000
LAYER_START_SOL = 0.5
LAYER_BRANCHES = 3
LAYER_DEPTH = 3
LAYER_FRESH_SECONDS = 3600
LAYER_FORWARD_SECONDS = 600
LAYER_FORWARD_SHARE = 0.8
LAYER_BUDGET_SECONDS = 3
SERVICE_RECIPIENTS = 100
CACHE_SECONDS = 600
PARTIAL_CACHE_SECONDS = 60


@dataclass(frozen=True)
class WalletFindings:
    evidence: tuple[Evidence, ...] = ()
    notes: tuple[Reason, ...] = ()
    checked: bool = False
    infrastructure: bool = False
    transfers: tuple[Transfer, ...] = field(default=(), repr=False)


def _date(ts: int) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%-d %b %Y")


class WalletChecker:
    def __init__(self, rpc: HeliusRpc, excluded: frozenset[str] = frozenset(), clock=time.time):
        self.rpc = rpc
        self.excluded = excluded
        self.clock = clock
        self._cache: dict[str, tuple[float, WalletFindings]] = {}

    async def check(self, address: str) -> WalletFindings:
        cached = self._cache.get(address)
        if cached and cached[0] > self.clock():
            return cached[1]
        findings = await self._check(address)
        ttl = CACHE_SECONDS if findings.checked else PARTIAL_CACHE_SECONDS
        self._cache[address] = (self.clock() + ttl, findings)
        return findings

    async def _check(self, address: str) -> WalletFindings:
        try:
            recent = await self.rpc.history(address, oldest_first=False, limit=HISTORY)
        except SourceError:
            return WalletFindings(notes=(Reason("not_checked", "We could not load this wallet's history from Helius just now, so only Ladon's existing records were used."),))
        if not recent:
            return WalletFindings(checked=True, notes=(Reason("no_activity", "This wallet has no transactions on Solana yet."),))

        transfers = sol_transfers(recent)
        service = len({t.destination for t in transfers if t.source == address}) >= SERVICE_RECIPIENTS
        evidence = own_actions(address, recent, delegated_pulls(recent, address))
        notes: list[Reason] = []
        if service:
            notes.append(Reason("busy_wallet", "This wallet pays a very large number of other wallets, like an exchange or payment service, so fast-moving money is not treated as suspicious. What it does with its own tokens is still checked."))
        else:
            evidence.extend(money_flow(address, transfers, self.excluded))
            try:
                hops, amount = await asyncio.wait_for(self._longest_chain(address, transfers), LAYER_BUDGET_SECONDS)
                chain = layering(hops, amount)
                if chain:
                    evidence.append(chain)
            except (SourceError, TimeoutError):
                notes.append(Reason("not_checked", "We ran out of time following where this wallet's money went next."))

        times = [int(t["blockTime"]) for t in recent if t.get("blockTime")]
        span = f"back to {_date(min(times))}" if times else "in its history"
        if not evidence:
            notes.append(Reason("checked_clean", f"We checked this wallet's last {len(recent)} transactions, {span}, and found none of the scam patterns Ladon looks for."))
        else:
            notes.append(Reason("checked", f"Based on this wallet's last {len(recent)} transactions, {span}."))
        return WalletFindings(
            tuple(sorted(evidence, key=lambda e: e.weight, reverse=True)),
            tuple(notes),
            checked=True,
            infrastructure=service,
            transfers=tuple(transfers),
        )

    async def _longest_chain(self, address: str, transfers: list[Transfer]) -> tuple[int, float]:
        outflows = sorted(
            (t for t in transfers if t.source == address and t.amount >= LAYER_START_SOL and t.destination not in self.excluded),
            key=lambda t: t.amount,
            reverse=True,
        )
        starts: list[Transfer] = []
        for t in outflows:
            if t.destination not in {s.destination for s in starts}:
                starts.append(t)
            if len(starts) == LAYER_BRANCHES:
                break
        chains = await asyncio.gather(*(self._follow(t, 0) for t in starts))
        best = max(chains, default=(0, 0.0))
        return best

    async def _follow(self, hop: Transfer, depth: int) -> tuple[int, float]:
        if depth >= LAYER_DEPTH or hop.destination in self.excluded:
            return depth, hop.amount
        history = await self.rpc.history(hop.destination, oldest_first=True, limit=20)
        times = [int(t["blockTime"]) for t in history if t.get("blockTime")]
        if not times or min(times) < hop.timestamp - LAYER_FRESH_SECONDS:
            return depth, hop.amount
        onward = [
            t
            for t in sol_transfers(history)
            if t.source == hop.destination
            and 0 <= t.timestamp - hop.timestamp <= LAYER_FORWARD_SECONDS
            and t.amount >= hop.amount * LAYER_FORWARD_SHARE
        ]
        if not onward:
            return depth, hop.amount
        return await self._follow(onward[0], depth + 1)
