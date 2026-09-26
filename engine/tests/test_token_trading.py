from ladon.tokens.trading import creator_sale, launch_bundle, token_deltas
from helpers import wallet
from token_fixtures import DAY, trade

MINT, DEV, SNIPER, B1, B2 = (wallet(n) for n in ["mint", "dev", "sniper", "b1", "b2"])
T0 = 1_700_000_000
SOL = 10**9


def test_reads_token_balance_changes_per_owner():
    tx = trade(MINT, T0, [(DEV, 500, -SOL), (B1, 200, -SOL)])
    assert token_deltas(tx, MINT) == {DEV: 500, B1: 200}
    assert token_deltas(tx, wallet("other-mint")) == {}


def test_creator_dumping_within_a_day():
    txs = [trade(MINT, T0, [(DEV, 1000, -2 * SOL)]), trade(MINT, T0 + 3600, [(DEV, -900, 5 * SOL)])]
    sale = creator_sale(txs, DEV, MINT, T0)
    assert sale.peak == 1000 and sale.sold == 900
    assert sale.dumped


def test_selling_after_the_first_day_is_not_a_dump():
    txs = [trade(MINT, T0, [(DEV, 1000, -2 * SOL)]), trade(MINT, T0 + 3 * DAY, [(DEV, -1000, 5 * SOL)])]
    assert not creator_sale(txs, DEV, MINT, T0).dumped


def test_moving_tokens_without_getting_paid_is_not_selling():
    txs = [trade(MINT, T0, [(DEV, 1000, -2 * SOL)]), trade(MINT, T0 + 60, [(DEV, -1000, -5000)])]
    sale = creator_sale(txs, DEV, MINT, T0)
    assert sale.sold == 0 and not sale.dumped


def test_bundle_is_wallets_buying_together_or_funded_by_the_creator():
    txs = [
        trade(MINT, T0, [(DEV, 100, -SOL)], slot=10),
        trade(MINT, T0, [(B1, 300, -SOL), (B2, 300, -SOL)], slot=10),
        trade(MINT, T0 + 1, [(SNIPER, 400, -SOL)], slot=10),
        trade(MINT, T0 + 5, [(wallet("funded"), 200, -SOL)], slot=12),
    ]
    bundle = launch_bundle(txs, MINT, DEV, {wallet("funded")}, holdings={B1: 300, wallet("funded"): 0}, supply=4000)
    assert bundle.wallets == {B1, B2, wallet("funded")}
    assert SNIPER not in bundle.wallets
    assert bundle.bought_share == 800 / 4000
    assert bundle.held_share == 300 / 4000


def test_accounts_that_did_not_sign_are_never_buyers():
    tx = trade(MINT, T0, [(B1, 300, -SOL), (B2, 300, -SOL)])
    tx["transaction"]["message"]["accountKeys"][1]["signer"] = False
    assert launch_bundle([tx], MINT, DEV, set(), {}, 1000).wallets == frozenset()
