import time
from dataclasses import dataclass, field

from collections import defaultdict

from .models import Evidence, Score, Takeover, Transfer


@dataclass(frozen=True)
class Report:
    address: str
    reporter: str
    description: str
    created_at: float
    signature: str = ""


@dataclass
class MemoryStore:
    reports: list[Report] = field(default_factory=list)
    transfers: set[Transfer] = field(default_factory=set)
    takeovers: set[Takeover] = field(default_factory=set)
    by_address: dict[str, set[Transfer]] = field(default_factory=lambda: defaultdict(set))
    evidence: dict[str, list[Evidence]] = field(default_factory=dict)
    scores: dict[str, Score] = field(default_factory=dict)
    checked: set[str] = field(default_factory=set)

    def add_report(self, address: str, reporter: str, description: str, signature: str = "") -> Report | None:
        if any(r.address == address and r.reporter == reporter for r in self.reports):
            return None
        report = Report(address, reporter, description, time.time(), signature)
        self.reports.append(report)
        return report

    def report_count(self, address: str) -> int:
        return len({r.reporter for r in self.reports if r.address == address})

    def reported_addresses(self) -> set[str]:
        return {r.address for r in self.reports}

    def add_transfers(self, transfers: list[Transfer]) -> None:
        for t in transfers:
            self.transfers.add(t)
            self.by_address[t.source].add(t)
            self.by_address[t.destination].add(t)

    def transfers_of(self, address: str) -> list[Transfer]:
        return list(self.by_address.get(address, ()))

    def add_takeovers(self, takeovers: list[Takeover]) -> None:
        self.takeovers.update(takeovers)

    def takeovers_by(self, attacker: str) -> list[Takeover]:
        return [t for t in self.takeovers if t.attacker == attacker]

    def attackers(self) -> set[str]:
        return {t.attacker for t in self.takeovers}

    def mark_checked(self, address: str) -> None:
        self.checked.add(address)

    def set_scores(self, scores: dict[str, Score]) -> None:
        self.scores = scores

    def score(self, address: str) -> Score | None:
        return self.scores.get(address)
