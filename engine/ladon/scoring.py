from collections.abc import Iterable

from .models import Confidence, Evidence, Inheritance, Reason, Score

REPORT_WEIGHT = 0.05
REPORT_CAP = 0.15
FLAG_THRESHOLD = 0.5
CONFIRM_THRESHOLD = 0.8
KNOWN_DRAINER_RISK = 0.95
CONCLUSIVE = 0.9


def combine(weights: Iterable[float]) -> float:
    remaining = 1.0
    for w in weights:
        remaining *= 1 - max(0.0, min(1.0, w))
    return 1 - remaining


def inheritance_text(link: Inheritance) -> str:
    if link.hops == 1:
        return "Received money directly from a wallet confirmed as a scam."
    return f"Linked to a wallet confirmed as a scam through {link.hops} transfers."


def score_wallet(
    address: str,
    evidence: Iterable[Evidence] = (),
    inherited: Inheritance | None = None,
    reports: int = 0,
    known_drainer: bool = False,
    cluster_size: int = 0,
) -> Score:
    evidence = sorted(evidence, key=lambda e: e.weight, reverse=True)
    onchain = [e.weight for e in evidence]
    reasons = [Reason(e.code, e.text) for e in evidence]
    if known_drainer:
        onchain.append(KNOWN_DRAINER_RISK)
        reasons.insert(0, Reason("known_drainer", "On Ladon's list of confirmed drainer wallets."))
    if inherited:
        onchain.append(inherited.risk)
        reasons.append(Reason("linked_to_scam", inheritance_text(inherited)))

    report_part = min(REPORT_CAP, reports * REPORT_WEIGHT)
    if reports:
        people = "person" if reports == 1 else "people"
        reasons.append(Reason("reported", f"Reported by {reports} {people}. Reports alone are never treated as proof."))

    risk = combine([*onchain, report_part]) if onchain else report_part
    signals = len(onchain)
    if signals == 0:
        confidence = Confidence.LOW if reports else Confidence.NONE
    elif known_drainer or any(w >= CONCLUSIVE for w in onchain) or (signals >= 2 and risk >= CONFIRM_THRESHOLD):
        confidence = Confidence.HIGH
    else:
        confidence = Confidence.MEDIUM

    return Score(
        address=address,
        risk=round(risk, 2),
        confidence=confidence,
        reasons=tuple(reasons),
        flagged=signals > 0 and risk >= FLAG_THRESHOLD,
        cluster_size=cluster_size,
        reports=reports,
    )
