from dataclasses import dataclass, field
from enum import Enum


class Asset(str, Enum):
    SOL = "SOL"
    USDC = "USDC"
    USDT = "USDT"


@dataclass(frozen=True)
class Transfer:
    source: str
    destination: str
    amount: float
    asset: Asset
    timestamp: int
    signature: str


@dataclass(frozen=True)
class Evidence:
    code: str
    weight: float
    text: str


@dataclass(frozen=True)
class Inheritance:
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
