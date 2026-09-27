from ladon.exchanges import Verdict, entry, profile
from ladon.exclusions import PROGRAMS, load_exclusions
from helpers import wallet
from token_fixtures import sol_transfer, tx

SOL = 10**9
HOT = wallet("hot")
COLD = wallet("cold")


def pay(source: str, destination: str, at: int, sol: float = 1.0) -> dict:
    return tx(source, at, top=[sol_transfer(source, destination, int(sol * SOL))])


def exchange_history(withdrawals: int, deposits: int, span_seconds: int) -> list[dict]:
    history = [pay(HOT, wallet(f"user{i}"), i * span_seconds // withdrawals) for i in range(withdrawals)]
    history += [pay(wallet(f"depositor{i}"), HOT, i * span_seconds // deposits) for i in range(deposits)]
    history.append(pay(COLD, HOT, span_seconds, sol=5000))
    return history


def test_a_busy_two_way_hot_wallet_is_a_strong_candidate():
    p = profile(HOT, exchange_history(400, 150, 3600))
    assert p.verdict is Verdict.STRONG
    assert p.recipients == 400 and p.senders == 151
    assert p.big_partners == (COLD,)


def test_a_wallet_that_only_pays_out_is_not_an_exchange():
    history = [pay(HOT, wallet(f"user{i}"), i) for i in range(500)]
    assert profile(HOT, history).verdict is Verdict.NO


def test_a_slow_wallet_with_many_partners_is_not_an_exchange():
    assert profile(HOT, exchange_history(150, 40, 30 * 24 * 3600)).verdict is Verdict.NO


def test_moderate_activity_is_only_likely():
    assert profile(HOT, exchange_history(150, 40, 3600)).verdict is Verdict.LIKELY


def test_dust_does_not_count_as_customers():
    history = [tx(HOT, i, top=[sol_transfer(HOT, wallet(f"u{i}"), 1000)]) for i in range(500)]
    assert profile(HOT, history).recipients == 0


def test_writes_clean_entries():
    assert entry(COLD, "Big  Exchange #2 hot wallet", "2026-09-27") == f"{COLD}  # Big Exchange 2 hot wallet (reviewed 2026-09-27)"


def test_every_exchange_file_is_loaded_and_junk_skipped(tmp_path):
    (tmp_path / "exchanges.txt").write_text(f"# header\n{HOT}  # Some exchange\nnot-an-address\n")
    (tmp_path / "exchanges_okx.txt").write_text(f"{COLD}\n")
    (tmp_path / "other.txt").write_text(f"{wallet('ignored')}\n")
    loaded = load_exclusions(tmp_path) - PROGRAMS
    assert loaded == {HOT, COLD}


def test_imports_only_signed_solana_rows_from_okx_reserves():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("okx", Path(__file__).resolve().parent.parent / "scripts" / "import_okx_reserves.py")
    okx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(okx)
    rows = [
        ["coin", "amount"],
        ["SOL", "7718468"],
        ["coin", "Type", "Network", "Snapshot Height", "address", "amount", "message"],
        ["SOL", "Non Staking", "SOL", "1", HOT, "4.3", "I am an OKX address"],
        ["USDT-SPL", "Non Staking", "SOL", "1", HOT, "9", "I am an OKX address"],
        ["BTC", "Non Staking", "BTC", "1", "13jTtHxBPFwZkaCdm6BwJMMJkqvTpBZccw", "1", "I am an OKX address"],
        ["SOL", "Non Staking", "SOL", "1", COLD, "1", "something else"],
        ["SOL", "Non Staking", "SOL", "1", "not-an-address", "1", "I am an OKX address"],
    ]
    assert okx.solana_addresses(rows) == {HOT}
