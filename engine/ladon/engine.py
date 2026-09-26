"""The core loop: a report starts a check, the check gathers evidence, and scores are recomputed."""

from typing import TYPE_CHECKING

from .evidence import detect
from .graph import ScamGraph
from .helius import Helius, parse_transfers
from .models import Confidence, Reason, Score
from .scoring import CONFIRM_THRESHOLD, KNOWN_DRAINER_RISK, score_wallet
from .store import MemoryStore

if TYPE_CHECKING:
    from .db import Database

# After a wallet is confirmed, the histories of the wallets it paid most are fetched too, so the
# graph can reach two and three steps out. Bounded to stay inside the free Helius quota.
EXPAND_LIMIT = 10
# Confirmed wallets can confirm the wallets they fund (when those have evidence of their own), so
# scoring repeats until nothing changes, up to this many rounds.
MAX_ROUNDS = 5


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

    def lookup(self, address: str) -> Score:
        if address in self.excluded:
            return Score(
                address=address,
                risk=0.0,
                confidence=Confidence.HIGH,
                reasons=(Reason("infrastructure", "A known exchange, protocol or program. It never inherits risk from the wallets that use it."),),
            )
        return self.store.score(address) or unknown(address)

    async def report(self, address: str, reporter: str, description: str) -> bool:
        report = self.store.add_report(address, reporter, description)
        if report and self.db:
            await self.db.save_report(report)
        await self._rescore_and_save()
        return report is not None

    async def check(self, address: str) -> None:
        """Fetch a wallet's history, look for evidence, and rescore. Needs a Helius client."""
        if self.helius is None or address in self.excluded:
            return
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
        transfers = parse_transfers(await self.helius.transactions(address))
        evidence = detect(address, [*self.store.transfers_of(address), *transfers], self.excluded)
        self.store.add_transfers(transfers)
        self.store.set_evidence(address, evidence)
        self.store.mark_checked(address)
        if self.db:
            await self.db.save_transfers(transfers)
            await self.db.save_evidence(address, evidence)
            await self.db.mark_checked(address)

    async def _rescore_and_save(self) -> None:
        self.rescore()
        if self.db:
            await self.db.save_scores(self.store.scores)

    def _graph(self) -> ScamGraph:
        graph = ScamGraph(self.excluded)
        graph.add(self.store.transfers)
        return graph

    def _confirmed(self) -> dict[str, float]:
        return {a: s.risk for a, s in self.store.scores.items() if s.risk >= CONFIRM_THRESHOLD and self._has_own_evidence(a)}

    def _has_own_evidence(self, address: str) -> bool:
        return address in self.known_drainers or bool(self.store.evidence.get(address))

    def rescore(self) -> None:
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
