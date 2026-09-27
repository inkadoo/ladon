from dataclasses import dataclass, replace
from enum import Enum

DEPLOYER_RUG_POINTS = (0, 25, 45, 60)
LINKED_RUG_POINTS = (0, 20, 30, 40)
MINT_AUTHORITY_POINTS = 15
FREEZE_AUTHORITY_POINTS = 15
FRESH_DEPLOYER_POINTS = 10
FRESH_DEPLOYER_HOURS = 24
CREATOR_DUMP_POINTS = 35
CREATOR_SELLING_POINTS = 20
CREATOR_SELLING_SHARE = 0.5
CREATOR_DUMP_SHARE = 0.8
BUNDLE_MIN_SHARE = 0.1
BUNDLE_DUMP_MIN_SHARE = 0.15
BUNDLE_DUMP_KEPT = 0.25
BUNDLE_HOLDING_POINTS = (20, 30)
BUNDLE_HOLDING_SHARES = (0.2, 0.4)
BUNDLE_DUMP_POINTS = 30
TOP_HOLDERS_SHARES = (0.15, 0.3)
TOP_HOLDERS_POINTS = (15, 25)
SERIAL_RUGGER_RUGS = 2
ESTABLISHED = ((30, 250_000), (180, 50_000))
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
    funder_skipped: bool = False
    mint_authority: bool | None = None
    freeze_authority: bool | None = None
    deployer_age_hours: float | None = None
    creator_sold_share: float | None = None
    creator_held_any: bool = True
    bundle_bought_share: float | None = None
    bundle_held_share: float | None = None
    top_holders_share: float | None = None
    token_age_days: float | None = None
    liquidity_usd: float | None = None
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
        return Reason("No dumped tokens from this deployer", "We found no earlier token that this deployer sold off soon after launching.")
    points = DEPLOYER_RUG_POINTS[min(rugs, len(DEPLOYER_RUG_POINTS) - 1)]
    return Reason(
        "Deployer dumped earlier tokens",
        f"The wallet that created this token sold off {_plural(rugs, 'earlier token')} of its own within a day of launching them.",
        points,
    )


def _linked(rugs: int | None, funder_is_busy: bool, skipped: bool = False) -> Reason:
    if skipped:
        return Reason("Funding link traced in full checks", "Quick checks skip tracing who funded the deployer. The full check includes it.")
    if funder_is_busy:
        return Reason(
            "Funder not traced",
            "The deployer was funded by a very busy wallet, most likely an exchange, so its other customers were not treated as linked.",
        )
    if rugs is None:
        return Reason("Funding link not checked", "We could not trace who funded the deployer or what else they launched.")
    if rugs == 0:
        return Reason("No dumped tokens from linked wallets", "We traced who funded the deployer and found no tokens that the funder or its other wallets sold off after launch.")
    points = LINKED_RUG_POINTS[min(rugs, len(LINKED_RUG_POINTS) - 1)]
    return Reason(
        "Linked wallets dumped their tokens",
        f"The wallet that funded this deployer, or other wallets it funded, launched and then sold off {_plural(rugs, 'token')} within a day.",
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


def _pct(share: float) -> str:
    return f"{round(share * 100)}%"


def _creator_sold(share: float | None, held_any: bool) -> Reason:
    if share is None:
        return Reason("Creator's selling not checked", "We could not see whether the creator has sold this token.")
    if not held_any:
        return Reason("Creator bought none at launch", "The creator did not hold any of this token after launching it.")
    if share >= CREATOR_DUMP_SHARE:
        return Reason(
            "Creator dumped this token",
            f"The creator sold {_pct(share)} of their tokens within a day of launching, the classic sign of a rug pull.",
            CREATOR_DUMP_POINTS,
        )
    if share >= CREATOR_SELLING_SHARE:
        return Reason(
            "Creator sold most of their tokens",
            f"The creator sold {_pct(share)} of their tokens within a day of launching.",
            CREATOR_SELLING_POINTS,
        )
    return Reason("Creator has not dumped", f"The creator sold {_pct(share)} of their tokens in the first day, which is not a dump.")


def _bundle_dumped(bought: float | None, held: float | None) -> bool:
    return bought is not None and held is not None and bought >= BUNDLE_DUMP_MIN_SHARE and held <= bought * BUNDLE_DUMP_KEPT


def _bundle(bought: float | None, held: float | None) -> Reason:
    if bought is None or held is None:
        return Reason("Launch buyers not checked", "We could not see who bought this token when it launched.")
    if bought < BUNDLE_MIN_SHARE:
        return Reason("No launch bundle found", "We found no group of linked wallets buying a large share of the supply at launch.")
    if _bundle_dumped(bought, held):
        return Reason(
            "Launch bundle already sold",
            f"Linked wallets bought {_pct(bought)} of the supply at launch and have since sold almost all of it.",
            BUNDLE_DUMP_POINTS,
        )
    points = 0
    for threshold, value in zip(BUNDLE_HOLDING_SHARES, BUNDLE_HOLDING_POINTS):
        if held >= threshold:
            points = value
    if points:
        return Reason(
            "Linked wallets hold a big share",
            f"Linked wallets that bought at launch still hold {_pct(held)} of the supply and could sell together at any moment.",
            points,
        )
    return Reason("Launch bundle holds little", f"Linked wallets bought {_pct(bought)} at launch but now hold only {_pct(held)}.")


def _top_holders(share: float | None) -> Reason:
    if share is None:
        return Reason("Top holders not checked", "We could not see who holds the most of this token.")
    points = 0
    for threshold, value in zip(TOP_HOLDERS_SHARES, TOP_HOLDERS_POINTS):
        if share > threshold:
            points = value
    if points:
        return Reason(
            "A few wallets hold a lot",
            f"The 10 biggest wallets hold {_pct(share)} of the supply, not counting pools. If they sell together the price collapses.",
            points,
        )
    return Reason("Supply is spread out", f"The 10 biggest wallets hold {_pct(share)} of the supply, not counting pools.")


def established(signals: TokenSignals) -> bool:
    age, liquidity = signals.token_age_days, signals.liquidity_usd
    if age is None or liquidity is None:
        return False
    return any(age >= days and liquidity >= usd for days, usd in ESTABLISHED)


def _established(signals: TokenSignals) -> Reason:
    days = int(signals.token_age_days or 0)
    return Reason(
        "Established token",
        f"It has traded for {days} days with ${signals.liquidity_usd:,.0f} in liquidity, so its settings and biggest holders count for less than on a new launch.",
    )


@dataclass(frozen=True)
class Label:
    kind: str
    text: str
    severity: str


def labels(signals: TokenSignals, risk: TokenRisk) -> tuple[Label, ...]:
    found: list[Label] = []
    if risk.level is Level.HIGH:
        found.append(Label("high_risk", "High rug risk", "danger"))
    if signals.deployer_rugs and signals.deployer_rugs >= SERIAL_RUGGER_RUGS:
        found.append(Label("serial_rugger", f"Dev rugged {signals.deployer_rugs} coins", "danger"))
    if signals.linked_rugs and signals.linked_rugs >= SERIAL_RUGGER_RUGS:
        found.append(Label("linked_rugger", f"Dev's network rugged {signals.linked_rugs}", "danger"))
    if signals.creator_sold_share is not None and signals.creator_held_any and signals.creator_sold_share >= CREATOR_DUMP_SHARE:
        found.append(Label("dev_dumped", "Dev dumped", "danger"))
    bought, held = signals.bundle_bought_share, signals.bundle_held_share
    if _bundle_dumped(bought, held):
        found.append(Label("bundle_sold", "Bundle sold", "danger"))
    elif bought is not None and held is not None and bought >= BUNDLE_MIN_SHARE and held >= BUNDLE_HOLDING_SHARES[0] and not established(signals):
        found.append(Label("bundled", f"Bundled {_pct(held)}", "warning"))
    if signals.top_holders_share is not None and signals.top_holders_share > TOP_HOLDERS_SHARES[0] and not established(signals):
        found.append(Label("top_holders", f"Top 10 hold {_pct(signals.top_holders_share)}", "warning"))
    return tuple(found)


def score_token(signals: TokenSignals) -> TokenRisk:
    strong = [
        _deployer(signals.deployer_rugs),
        _linked(signals.linked_rugs, signals.funder_is_busy, signals.funder_skipped),
        _creator_sold(signals.creator_sold_share, signals.creator_held_any),
    ]
    bundle = _bundle(signals.bundle_bought_share, signals.bundle_held_share)
    if _bundle_dumped(signals.bundle_bought_share, signals.bundle_held_share):
        strong.append(bundle)
    weak = [
        _mint_authority(signals.mint_authority),
        _freeze_authority(signals.freeze_authority),
        _deployer_age(signals.deployer_age_hours),
        _top_holders(signals.top_holders_share),
        *([] if bundle in strong else [bundle]),
    ]
    if established(signals):
        weak = [replace(r, points=0) for r in weak] + [_established(signals)]
    reasons = [*strong, *weak, *(Reason("Not checked", note) for note in signals.unchecked)]
    score = min(100, sum(r.points for r in reasons))
    if not any(r.points for r in strong):
        score = min(score, HIGH_FROM - 1)
    level = Level.HIGH if score >= HIGH_FROM else Level.MEDIUM if score >= MEDIUM_FROM else Level.LOW
    ordered = sorted(reasons, key=lambda r: r.points, reverse=True)
    return TokenRisk(score=score, level=level, reasons=tuple(ordered))
