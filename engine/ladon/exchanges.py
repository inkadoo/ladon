from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .wallets.parse import sol_transfers

DUST_SOL = 0.001
LIKELY = {"per_hour": 20, "recipients": 100, "senders": 30}
STRONG = {"per_hour": 100, "recipients": 300, "senders": 100}
BIG_MOVE_SOL = 100


class Verdict(str, Enum):
    STRONG = "strong"
    LIKELY = "likely"
    NO = "no"


@dataclass(frozen=True)
class Profile:
    address: str
    transactions: int
    hours: float
    recipients: int
    senders: int
    big_partners: tuple[str, ...]

    @property
    def per_hour(self) -> float:
        return self.transactions / max(self.hours, 1 / 60)

    @property
    def verdict(self) -> Verdict:
        def meets(bar: dict[str, int]) -> bool:
            return self.per_hour >= bar["per_hour"] and self.recipients >= bar["recipients"] and self.senders >= bar["senders"]

        if meets(STRONG):
            return Verdict.STRONG
        if meets(LIKELY):
            return Verdict.LIKELY
        return Verdict.NO

    def summary(self) -> str:
        return (
            f"{self.transactions} txs over {self.hours:.1f}h ({self.per_hour:.0f}/h), "
            f"paid {self.recipients} wallets, paid by {self.senders}"
        )


def profile(address: str, history: list[dict[str, Any]]) -> Profile:
    times = [int(t["blockTime"]) for t in history if t.get("blockTime")]
    hours = (max(times) - min(times)) / 3600 if len(times) > 1 else 0.0
    transfers = [t for t in sol_transfers(history) if t.amount >= DUST_SOL]
    recipients = {t.destination for t in transfers if t.source == address}
    senders = {t.source for t in transfers if t.destination == address}
    big = Counter()
    for t in transfers:
        if t.amount >= BIG_MOVE_SOL:
            partner = t.destination if t.source == address else t.source if t.destination == address else None
            if partner:
                big[partner] += t.amount
    return Profile(
        address=address,
        transactions=len(history),
        hours=hours,
        recipients=len(recipients),
        senders=len(senders),
        big_partners=tuple(p for p, _ in big.most_common()),
    )


def entry(address: str, label: str, day: str) -> str:
    clean = " ".join(label.replace("#", "").split())[:80] or "exchange wallet"
    return f"{address}  # {clean} (reviewed {day})"
