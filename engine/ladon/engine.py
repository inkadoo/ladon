import asyncio
from typing import TYPE_CHECKING

from .evidence import detect
from .graph import HOP_DECAY, MIN_LINK, ScamGraph
from .helius import Helius, parse_takeovers, parse_transfers
from .models import Confidence, Inheritance, Reason, Score
from .scoring import CONFIRM_THRESHOLD, FLAG_THRESHOLD, KNOWN_DRAINER_RISK, combine, score_wallet
from .store import MemoryStore
from .wallets.patterns import FLOW_CODES

if TYPE_CHECKING:
    from .db import Database
    from .wallets.checker import WalletChecker, WalletFindings

EXPAND_LIMIT = 10
ATTACKER_LIMIT = 3
MAX_ROUNDS = 5
FUNDER_CHECKS = 3


def unknown(address: str) -> Score:
    return Score(
        address=address,
        risk=0.0,
        confidence=Confidence.NONE,
        reasons=(Reason("no_data", "No reports or onchain evidence about this wallet yet."),),
    )


class Engine:
    def __init__(
        self,
        store: MemoryStore,
        excluded: frozenset[str] = frozenset(),
        known_drainers: frozenset[str] = frozenset(),
        helius: Helius | None = None,
        db: "Database | None" = None,
    ):
        self.store = store
        self.excluded = excluded
        self.known_drainers = known_drainers
        self.helius = helius
        self.db = db
        self._inherited: dict = {}

    def lookup(self, address: str) -> Score:
        if address in self.excluded:
            return Score(
                address=address,
                risk=0.0,
                confidence=Confidence.HIGH,
                reasons=(Reason("infrastructure", "A known exchange, protocol or program. It never inherits risk from the wallets that use it."),),
            )
        return self.store.score(address) or unknown(address)

    async def investigate(self, address: str, wallets: "WalletChecker") -> Score:
        if address in self.excluded:
            return self.lookup(address)
        findings = await wallets.check(address)
        stored = self.store.evidence.get(address, [])
        if findings.infrastructure:
            stored = [e for e in stored if e.code not in FLOW_CODES]
        live = list(findings.evidence)
        codes = {e.code for e in live}
        base = self.store.score(address)
        links = [self._inherited.get(address), await self._funder_link(address, findings, wallets)]
        return score_wallet(
            address,
            evidence=[*live, *(e for e in stored if e.code not in codes)],
            inherited=max((l for l in links if l), key=lambda l: l.risk, default=None),
            reports=self.store.report_count(address),
            known_drainer=address in self.known_drainers,
            cluster_size=base.cluster_size if base else 0,
            notes=findings.notes,
            checked=findings.checked,
        )

    async def _funder_link(self, address: str, findings: "WalletFindings", wallets: "WalletChecker") -> Inheritance | None:
        received: dict[str, float] = {}
        for t in findings.transfers:
            if t.destination == address and t.source not in (address, *self.excluded) and t.amount >= MIN_LINK[t.asset]:
                received[t.source] = received.get(t.source, 0.0) + t.amount
        funders = sorted(received, key=received.__getitem__, reverse=True)[:FUNDER_CHECKS]
        risks = await asyncio.gather(*(self._own_risk(f, wallets) for f in funders))
        links = [
            Inheritance(source=funder, hops=1, risk=round(risk * HOP_DECAY[0], 4))
            for funder, risk in zip(funders, risks)
            if risk >= FLAG_THRESHOLD
        ]
        return max(links, key=lambda l: l.risk, default=None)

    async def _own_risk(self, address: str, wallets: "WalletChecker") -> float:
        if address in self.known_drainers:
            return KNOWN_DRAINER_RISK
        findings = await wallets.check(address)
        if findings.infrastructure:
            return 0.0
        codes = {e.code for e in findings.evidence}
        stored = [e for e in self.store.evidence.get(address, []) if e.code not in codes]
        return combine(e.weight for e in [*findings.evidence, *stored])

    async def report(self, address: str, reporter: str, description: str, signature: str = "") -> bool:
        report = self.store.add_report(address, reporter, description, signature)
        if report and self.db:
            await self.db.save_report(report)
        await self._rescore_and_save()
        return report is not None

    async def check(self, address: str, signature: str = "") -> None:
        if self.helius is None or address in self.excluded:
            return
        if signature:
            takeovers = await self._record(await self.helius.transaction(signature))
            for attacker in list(dict.fromkeys(t.attacker for t in takeovers))[:ATTACKER_LIMIT]:
                if attacker not in self.store.checked and attacker not in self.excluded:
                    await self._ingest(attacker)
        await self._ingest(address)
        await self._rescore_and_save()
        if self._confirmed().get(address):
            graph = self._graph()
            for wallet in graph.recipients(address)[:EXPAND_LIMIT]:
                if wallet not in self.store.checked:
                    await self._ingest(wallet)
            await self._rescore_and_save()

    async def _ingest(self, address: str) -> None:
        assert self.helius is not None
        await self._record(await self.helius.transactions(address))
        self.store.mark_checked(address)
        if self.db:
            await self.db.mark_checked(address)

    async def _record(self, transactions: list[dict]) -> list:
        transfers = parse_transfers(transactions)
        takeovers = parse_takeovers(transactions)
        self.store.add_transfers(transfers)
        self.store.add_takeovers(takeovers)
        if self.db:
            await self.db.save_transfers(transfers)
            await self.db.save_takeovers(takeovers)
        return takeovers

    async def _rescore_and_save(self) -> None:
        self.rescore()
        if self.db:
            await self.db.save_derived(self.store.scores, self.store.evidence)

    def _gather_evidence(self) -> None:
        candidates = (self.store.checked | self.store.attackers() | self.store.reported_addresses()) - self.excluded
        evidence = {}
        for address in candidates:
            found = detect(address, self.store.transfers_of(address), self.excluded, self.store.takeovers_by(address))
            if found:
                evidence[address] = found
        self.store.evidence = evidence

    def _graph(self) -> ScamGraph:
        graph = ScamGraph(self.excluded)
        graph.add(self.store.transfers)
        return graph

    def _confirmed(self) -> dict[str, float]:
        return {a: s.risk for a, s in self.store.scores.items() if s.risk >= CONFIRM_THRESHOLD and self._has_own_evidence(a)}

    def _has_own_evidence(self, address: str) -> bool:
        return address in self.known_drainers or bool(self.store.evidence.get(address))

    def rescore(self) -> None:
        self._gather_evidence()
        graph = self._graph()
        seeds = {a: KNOWN_DRAINER_RISK for a in self.known_drainers}
        scores: dict[str, Score] = {}
        for _ in range(MAX_ROUNDS):
            inherited = graph.propagate(seeds)
            scores = self._score_all(inherited)
            confirmed = {
                a: s.risk
                for a, s in scores.items()
                if s.risk >= CONFIRM_THRESHOLD and self._has_own_evidence(a)
            }
            new_seeds = {**confirmed, **{a: KNOWN_DRAINER_RISK for a in self.known_drainers}}
            if new_seeds.keys() == seeds.keys():
                break
            seeds = new_seeds
        self._inherited = inherited
        self.store.set_scores(scores)

    def _score_all(self, inherited) -> dict[str, Score]:
        addresses = (
            set(self.store.evidence)
            | self.store.reported_addresses()
            | set(inherited)
            | set(self.known_drainers)
        ) - self.excluded
        clusters: dict[str, int] = {}
        for link in inherited.values():
            clusters[link.source] = clusters.get(link.source, 1) + 1
        scores = {}
        for address in addresses:
            link = inherited.get(address)
            scores[address] = score_wallet(
                address,
                evidence=self.store.evidence.get(address, []),
                inherited=link,
                reports=self.store.report_count(address),
                known_drainer=address in self.known_drainers,
                cluster_size=clusters.get(link.source if link else address, 0),
            )
        return scores
