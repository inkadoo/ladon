from ladon.models import Confidence, Evidence, Inheritance
from ladon.scoring import FLAG_THRESHOLD, REPORT_CAP, combine, score_wallet
from helpers import wallet

A = wallet("subject")
SWEEPS = Evidence("sweeps_incoming", 0.5, "Moved 8 incoming payments straight back out.")


def test_reports_alone_never_flag_a_wallet():
    score = score_wallet(A, reports=1000)
    assert score.risk == REPORT_CAP
    assert score.risk < FLAG_THRESHOLD
    assert not score.flagged
    assert score.confidence is Confidence.LOW


def test_report_reason_says_reports_are_not_proof():
    score = score_wallet(A, reports=2)
    assert any("never treated as proof" in r.text for r in score.reasons)


def test_no_information_means_no_confidence():
    score = score_wallet(A)
    assert score.risk == 0
    assert score.confidence is Confidence.NONE
    assert not score.flagged


def test_onchain_evidence_can_flag_with_medium_confidence():
    score = score_wallet(A, evidence=[SWEEPS])
    assert score.flagged
    assert score.confidence is Confidence.MEDIUM
    assert score.reasons[0].code == "sweeps_incoming"


def test_two_independent_signals_give_high_confidence():
    score = score_wallet(A, evidence=[SWEEPS], inherited=Inheritance(wallet("drainer"), 1, 0.71))
    assert score.risk >= 0.8
    assert score.confidence is Confidence.HIGH
    assert {r.code for r in score.reasons} == {"sweeps_incoming", "linked_to_scam"}


def test_known_drainer_is_flagged_with_high_confidence():
    score = score_wallet(A, known_drainer=True)
    assert score.flagged
    assert score.confidence is Confidence.HIGH
    assert score.reasons[0].code == "known_drainer"


def test_every_score_has_a_reason_when_it_has_risk():
    for score in [score_wallet(A, reports=1), score_wallet(A, evidence=[SWEEPS]), score_wallet(A, known_drainer=True)]:
        assert score.risk > 0 and score.reasons


def test_combine_raises_risk_but_stays_below_one():
    assert combine([]) == 0
    assert combine([0.5]) == 0.5
    assert combine([0.5, 0.5]) == 0.75
    assert combine([0.99, 0.99, 0.99]) < 1
    assert combine([2, -1]) == 1  # out-of-range weights are clamped
