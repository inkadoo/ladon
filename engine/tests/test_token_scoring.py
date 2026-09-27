from itertools import product

from ladon.tokens.scoring import HIGH_FROM, Level, TokenSignals, labels, score_token


def test_clean_token_scores_zero_and_still_explains_itself():
    risk = score_token(TokenSignals(deployer_rugs=0, linked_rugs=0, mint_authority=False, freeze_authority=False, deployer_age_hours=500))
    assert risk.score == 0
    assert risk.level is Level.LOW
    assert len(risk.reasons) == 8
    assert all(r.points == 0 for r in risk.reasons)


def test_every_point_has_a_reason():
    risk = score_token(TokenSignals(deployer_rugs=1, linked_rugs=0, mint_authority=True, freeze_authority=False, deployer_age_hours=2))
    assert risk.score == sum(r.points for r in risk.reasons) == 25 + 15 + 10
    assert all(r.label and r.explanation.endswith(".") for r in risk.reasons)


def test_weak_signals_alone_never_reach_high():
    for mint, freeze, fresh, held in product([True, False, None], [True, False, None], [True, False, None], [0.0, 0.25, 0.6]):
        risk = score_token(
            TokenSignals(
                deployer_rugs=0,
                linked_rugs=0,
                mint_authority=mint,
                freeze_authority=freeze,
                deployer_age_hours=1 if fresh else 100 if fresh is False else None,
                creator_sold_share=0.1,
                bundle_bought_share=max(held, 0.05),
                bundle_held_share=held,
            )
        )
        assert risk.score < HIGH_FROM
        assert risk.level is not Level.HIGH


def test_a_serial_rugger_is_high_risk_on_its_own_record():
    risk = score_token(TokenSignals(deployer_rugs=7, linked_rugs=0, mint_authority=False, freeze_authority=False, deployer_age_hours=500))
    assert risk.level is Level.HIGH
    assert risk.reasons[0].label == "Deployer dumped earlier tokens"
    assert "7 earlier tokens" in risk.reasons[0].explanation
    assert "sold off" in risk.reasons[0].explanation


def test_funding_link_to_rugs_raises_risk_for_a_fresh_wallet():
    risk = score_token(TokenSignals(deployer_rugs=0, linked_rugs=4, mint_authority=True, freeze_authority=True, deployer_age_hours=3))
    assert risk.score == 40 + 15 + 15 + 10
    assert risk.level is Level.HIGH
    assert risk.reasons[0].label == "Linked wallets dumped their tokens"


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


def clean(**changes) -> TokenSignals:
    base = dict(deployer_rugs=0, linked_rugs=0, mint_authority=False, freeze_authority=False, deployer_age_hours=500,
                creator_sold_share=0.0, bundle_bought_share=0.0, bundle_held_share=0.0)
    return TokenSignals(**{**base, **changes})


def test_a_creator_dumping_this_token_is_a_strong_signal():
    risk = score_token(clean(creator_sold_share=0.95, deployer_age_hours=2, mint_authority=True))
    assert risk.reasons[0].label == "Creator dumped this token"
    assert "95%" in risk.reasons[0].explanation
    assert risk.score == 35 + 10 + 15
    assert risk.level is Level.HIGH


def test_partial_creator_selling_counts_less():
    risk = score_token(clean(creator_sold_share=0.6))
    assert risk.reasons[0].label == "Creator sold most of their tokens"
    assert risk.score == 20


def test_a_creator_who_never_bought_is_not_accused():
    risk = score_token(clean(creator_sold_share=0.0, creator_held_any=False))
    assert "Creator bought none at launch" in {r.label for r in risk.reasons}
    assert risk.score == 0


def test_a_launch_bundle_that_already_sold_is_strong():
    risk = score_token(clean(bundle_bought_share=0.3, bundle_held_share=0.02, mint_authority=True, freeze_authority=True))
    assert risk.reasons[0].label == "Launch bundle already sold"
    assert risk.score == 30 + 15 + 15
    assert risk.level is Level.HIGH


def test_a_bundle_still_holding_warns_but_cannot_reach_high_alone():
    risk = score_token(clean(bundle_bought_share=0.5, bundle_held_share=0.45, mint_authority=True, freeze_authority=True, deployer_age_hours=1))
    assert risk.reasons[0].label == "Linked wallets hold a big share"
    assert risk.level is Level.MEDIUM


def test_small_bundles_are_ignored():
    risk = score_token(clean(bundle_bought_share=0.05, bundle_held_share=0.0))
    assert "No launch bundle found" in {r.label for r in risk.reasons}


def test_concentrated_holders_warn_but_never_reach_high_alone():
    risk = score_token(clean(top_holders_share=0.45, mint_authority=True, freeze_authority=True, deployer_age_hours=1))
    assert risk.reasons[0].label == "A few wallets hold a lot"
    assert "45%" in risk.reasons[0].explanation
    assert risk.level is Level.MEDIUM


def test_spread_out_supply_adds_nothing():
    risk = score_token(clean(top_holders_share=0.12))
    assert "Supply is spread out" in {r.label for r in risk.reasons}
    assert risk.score == 0


def test_labels_for_a_serial_rugger_with_a_bundle():
    signals = clean(deployer_rugs=5, creator_sold_share=0.9, bundle_bought_share=0.3, bundle_held_share=0.25, top_holders_share=0.4)
    kinds = {l.kind: l for l in labels(signals, score_token(signals))}
    assert set(kinds) == {"high_risk", "serial_rugger", "dev_dumped", "bundled", "top_holders"}
    assert kinds["serial_rugger"].text == "Dev rugged 5 coins"
    assert kinds["bundled"].text == "Bundled 25%"
    assert kinds["top_holders"].text == "Top 10 hold 40%"
    assert kinds["serial_rugger"].severity == "danger"


def test_one_past_rug_is_not_called_a_serial_rugger():
    signals = clean(deployer_rugs=1)
    assert labels(signals, score_token(signals)) == ()


def test_a_bundle_that_already_sold_is_labelled_as_sold():
    signals = clean(bundle_bought_share=0.3, bundle_held_share=0.01)
    assert [l.kind for l in labels(signals, score_token(signals))] == ["bundle_sold"]


def test_an_established_token_is_not_raised_by_its_settings_or_big_holders():
    risky_settings = dict(mint_authority=True, freeze_authority=True, deployer_age_hours=1, top_holders_share=0.7, deployer_rugs=0, linked_rugs=0)
    young = score_token(TokenSignals(**risky_settings, token_age_days=2, liquidity_usd=5_000_000))
    old = score_token(TokenSignals(**risky_settings, token_age_days=900, liquidity_usd=5_000_000))
    assert young.level is not Level.LOW
    assert old.level is Level.LOW and old.score == 0
    assert any(r.label == "Established token" for r in old.reasons)


def test_an_old_token_with_thin_liquidity_is_not_treated_as_established():
    risk = score_token(TokenSignals(mint_authority=True, freeze_authority=True, top_holders_share=0.7, token_age_days=900, liquidity_usd=20_000))
    assert risk.level is not Level.LOW


def test_rug_evidence_still_counts_on_an_established_token():
    risk = score_token(TokenSignals(creator_sold_share=0.95, deployer_rugs=3, token_age_days=400, liquidity_usd=1_000_000))
    assert risk.level is Level.HIGH


def test_a_long_lived_token_needs_less_liquidity_to_count_as_established():
    settings = dict(mint_authority=True, freeze_authority=True, top_holders_share=0.7)
    assert score_token(TokenSignals(**settings, token_age_days=400, liquidity_usd=60_000)).level is Level.LOW
    assert score_token(TokenSignals(**settings, token_age_days=60, liquidity_usd=60_000)).level is not Level.LOW
