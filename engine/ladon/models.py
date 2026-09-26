from dataclasses import dataclass, field
from enum import Enum


class Asset(str, Enum):
    SOL = "SOL"
    USDC = "USDC"
    USDT = "USDT"


@dataclass(frozen=True)
class Transfer:
    """Money moving from one wallet to another, in whole units of the asset (SOL, not lamports)."""

    source: str
    destination: str
    amount: float
    asset: Asset
    timestamp: int
    signature: str


@dataclass(frozen=True)
class Evidence:
    """One onchain finding about a wallet. `weight` is how strongly it alone suggests a scam (0-1)."""

    code: str
    weight: float
    text: str


@dataclass(frozen=True)
class Inheritance:
    """Risk a wallet picks up from a confirmed scam wallet that sent it money."""

    source: str
    hops: int
    risk: float


class Confidence(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Reason:
    code: str
    text: str


@dataclass(frozen=True)
class Score:
    address: str
    risk: float
    confidence: Confidence
    reasons: tuple[Reason, ...] = field(default_factory=tuple)
    flagged: bool = False
    cluster_size: int = 0
    reports: int = 0
