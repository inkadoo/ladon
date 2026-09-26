from itertools import product

from ladon.tokens.scoring import HIGH_FROM, Level, TokenSignals, score_token


def test_clean_token_scores_zero_and_still_explains_itself():
    risk = score_token(TokenSignals(deployer_rugs=0, linked_rugs=0, mint_authority=False, freeze_authority=False, deployer_age_hours=500))
    assert risk.score == 0
    assert risk.level is Level.LOW
    assert len(risk.reasons) == 5
    assert all(r.points == 0 for r in risk.reasons)


def test_every_point_has_a_reason():
    risk = score_token(TokenSignals(deployer_rugs=1, linked_rugs=0, mint_authority=True, freeze_authority=False, deployer_age_hours=2))
    assert risk.score == sum(r.points for r in risk.reasons) == 25 + 15 + 10
    assert all(r.label and r.explanation.endswith(".") for r in risk.reasons)


def test_weak_signals_alone_never_reach_high():
    for mint, freeze, fresh in product([True, False, None], repeat=3):
        risk = score_token(
            TokenSignals(
                deployer_rugs=0,
                linked_rugs=0,
                mint_authority=mint,
                freeze_authority=freeze,
                deployer_age_hours=1 if fresh else 100 if fresh is False else None,
            )
        )
        assert risk.score < HIGH_FROM
        assert risk.level is not Level.HIGH


def test_a_serial_rugger_is_high_risk_on_its_own_record():
    risk = score_token(TokenSignals(deployer_rugs=7, linked_rugs=0, mint_authority=False, freeze_authority=False, deployer_age_hours=500))
    assert risk.level is Level.HIGH
    assert risk.reasons[0].label == "Deployer's past tokens collapsed"
    assert "7 earlier tokens" in risk.reasons[0].explanation


def test_funding_link_to_rugs_raises_risk_for_a_fresh_wallet():
    risk = score_token(TokenSignals(deployer_rugs=0, linked_rugs=4, mint_authority=True, freeze_authority=True, deployer_age_hours=3))
    assert risk.score == 40 + 15 + 15 + 10
    assert risk.level is Level.HIGH
    assert risk.reasons[0].label == "Linked wallets have rugged"


def test_one_past_rug_alone_is_not_high():
    risk = score_token(TokenSignals(deployer_rugs=1, linked_rugs=0, mint_authority=False, freeze_authority=False, deployer_age_hours=500))
    assert risk.level is Level.LOW


def test_score_is_capped_at_100():
    risk = score_token(TokenSignals(deployer_rugs=9, linked_rugs=9, mint_authority=True, freeze_authority=True, deployer_age_hours=1))
    assert risk.score == 100


def test_unchecked_signals_add_no_points_but_say_so():
    risk = score_token(TokenSignals(unchecked=("We could not load the deployer's history from Helius.",)))
    assert risk.score == 0
    labels = [r.label for r in risk.reasons]
    assert "Deployer history not checked" in labels
    assert "Not checked" in labels


def test_busy_funders_are_not_used_as_links():
    risk = score_token(TokenSignals(deployer_rugs=0, funder_is_busy=True, mint_authority=False, freeze_authority=False, deployer_age_hours=100))
    reason = next(r for r in risk.reasons if r.label == "Funder not traced")
    assert reason.points == 0
    assert "exchange" in reason.explanation
