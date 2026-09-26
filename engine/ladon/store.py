"""Where reports, transfers, evidence and scores are kept.

MemoryStore is the engine's working copy. When a database is configured it is loaded from Postgres
on startup and every change is written through (see db.py).
"""

import time
from dataclasses import dataclass, field

from .models import Evidence, Score, Transfer


@dataclass(frozen=True)
class Report:
    address: str
    reporter: str
    description: str
    created_at: float


@dataclass
class MemoryStore:
    reports: list[Report] = field(default_factory=list)
    transfers: set[Transfer] = field(default_factory=set)
    evidence: dict[str, list[Evidence]] = field(default_factory=dict)
    scores: dict[str, Score] = field(default_factory=dict)
    checked: set[str] = field(default_factory=set)

    def add_report(self, address: str, reporter: str, description: str) -> Report | None:
        """Store a report. Returns None when this reporter already reported this address."""
        if any(r.address == address and r.reporter == reporter for r in self.reports):
            return None
        report = Report(address, reporter, description, time.time())
        self.reports.append(report)
        return report

    def report_count(self, address: str) -> int:
        return len({r.reporter for r in self.reports if r.address == address})

    def reported_addresses(self) -> set[str]:
        return {r.address for r in self.reports}

    def add_transfers(self, transfers: list[Transfer]) -> None:
        self.transfers.update(transfers)

    def transfers_of(self, address: str) -> list[Transfer]:
        return [t for t in self.transfers if address in (t.source, t.destination)]

    def set_evidence(self, address: str, evidence: list[Evidence]) -> None:
        self.evidence[address] = evidence

    def mark_checked(self, address: str) -> None:
        self.checked.add(address)

    def set_scores(self, scores: dict[str, Score]) -> None:
        self.scores = scores

    def score(self, address: str) -> Score | None:
        return self.scores.get(address)
