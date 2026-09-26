from dataclasses import dataclass
from enum import Enum

DEPLOYER_RUG_POINTS = (0, 25, 45, 60)
LINKED_RUG_POINTS = (0, 20, 30, 40)
MINT_AUTHORITY_POINTS = 15
FREEZE_AUTHORITY_POINTS = 15
FRESH_DEPLOYER_POINTS = 10
FRESH_DEPLOYER_HOURS = 24
MEDIUM_FROM = 30
HIGH_FROM = 60


class Level(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Reason:
    label: str
    explanation: str
    points: int = 0


@dataclass(frozen=True)
class TokenSignals:
    deployer_rugs: int | None = None
    linked_rugs: int | None = None
    funder_is_busy: bool = False
    mint_authority: bool | None = None
    freeze_authority: bool | None = None
    deployer_age_hours: float | None = None
    unchecked: tuple[str, ...] = ()


@dataclass(frozen=True)
class TokenRisk:
    score: int
    level: Level
    reasons: tuple[Reason, ...]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _deployer(rugs: int | None) -> Reason:
    if rugs is None:
        return Reason("Deployer history not checked", "We could not look up the other tokens this deployer has made.")
    if rugs == 0:
        return Reason("No collapsed tokens from this deployer", "None of the deployer's earlier tokens that we found lost their liquidity.")
    points = DEPLOYER_RUG_POINTS[min(rugs, len(DEPLOYER_RUG_POINTS) - 1)]
    return Reason(
        "Deployer's past tokens collapsed",
        f"The wallet that created this token made {_plural(rugs, 'earlier token')} that lost almost all their liquidity.",
        points,
    )


def _linked(rugs: int | None, funder_is_busy: bool) -> Reason:
    if funder_is_busy:
        return Reason(
            "Funder not traced",
            "The deployer was funded by a very busy wallet, most likely an exchange, so its other customers were not treated as linked.",
        )
    if rugs is None:
        return Reason("Funding link not checked", "We could not trace who funded the deployer or what else they launched.")
    if rugs == 0:
        return Reason("No collapsed tokens from linked wallets", "We traced who funded the deployer and found no collapsed tokens from that funder or the other wallets it funded.")
    points = LINKED_RUG_POINTS[min(rugs, len(LINKED_RUG_POINTS) - 1)]
    return Reason(
        "Linked wallets have rugged",
        f"The wallet that funded this deployer, or other wallets it funded, made {_plural(rugs, 'token')} that lost almost all their liquidity.",
        points,
    )


def _mint_authority(enabled: bool | None) -> Reason:
    if enabled is None:
        return Reason("Mint authority not checked", "We could not read this token's settings.")
    if enabled:
        return Reason("Supply can still be increased", "The creator can still mint new tokens, which would dilute everyone holding it.", MINT_AUTHORITY_POINTS)
    return Reason("Supply is fixed", "No one can mint more of this token.")


def _freeze_authority(enabled: bool | None) -> Reason:
    if enabled is None:
        return Reason("Freeze authority not checked", "We could not read this token's settings.")
    if enabled:
        return Reason("Holders can be frozen", "The creator can still freeze holders' tokens so they cannot sell.", FREEZE_AUTHORITY_POINTS)
    return Reason("Holders cannot be frozen", "No one can freeze this token in your wallet.")


def _deployer_age(hours: float | None) -> Reason:
    if hours is None:
        return Reason("Deployer age not checked", "We could not see when the deployer's wallet was first used.")
    if hours < FRESH_DEPLOYER_HOURS:
        return Reason(
            "Brand-new deployer wallet",
            "The wallet that created this token was less than a day old at the time, a common pattern for throwaway launch wallets.",
            FRESH_DEPLOYER_POINTS,
        )
    return Reason("Established deployer wallet", "The deployer's wallet was in use for more than a day before it created this token.")


def score_token(signals: TokenSignals) -> TokenRisk:
    strong = [_deployer(signals.deployer_rugs), _linked(signals.linked_rugs, signals.funder_is_busy)]
    weak = [
        _mint_authority(signals.mint_authority),
        _freeze_authority(signals.freeze_authority),
        _deployer_age(signals.deployer_age_hours),
    ]
    reasons = [*strong, *weak, *(Reason("Not checked", note) for note in signals.unchecked)]
    score = min(100, sum(r.points for r in reasons))
    if not any(r.points for r in strong):
        score = min(score, HIGH_FROM - 1)
    level = Level.HIGH if score >= HIGH_FROM else Level.MEDIUM if score >= MEDIUM_FROM else Level.LOW
    ordered = sorted(reasons, key=lambda r: r.points, reverse=True)
    return TokenRisk(score=score, level=level, reasons=tuple(ordered))
