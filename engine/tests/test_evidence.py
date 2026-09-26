from ladon.evidence import detect_sweeps
from ladon.helius import parse_transfers
from ladon.models import Asset
from helpers import helius_tx, sol, wallet

SWEEPER = wallet("sweeper")
COLLECTOR = wallet("collector")
EXCHANGE = wallet("exchange")


def sweeps(delay: int, senders: int = 4, destination: str = COLLECTOR):
    transfers = []
    for i in range(senders):
        at = 1_700_000_000 + i * 3600
        transfers.append(sol(wallet(f"victim-{i}"), SWEEPER, amount=2.0, at=at))
        transfers.append(sol(SWEEPER, destination, amount=1.99, at=at + delay))
    return transfers


def test_detects_a_sweeper_bot():
    evidence = detect_sweeps(SWEEPER, sweeps(delay=4))
    assert evidence is not None
    assert evidence.code == "sweeps_incoming"
    assert "4 incoming payments" in evidence.text


def test_ignores_people_who_move_money_on_later():
    assert detect_sweeps(SWEEPER, sweeps(delay=600)) is None


def test_needs_several_different_senders():
    assert detect_sweeps(SWEEPER, sweeps(delay=4, senders=2)) is None


def test_forwarding_to_an_exchange_is_not_sweeping():
    assert detect_sweeps(SWEEPER, sweeps(delay=4, destination=EXCHANGE), excluded=frozenset({EXCHANGE})) is None


def test_parses_helius_transactions_into_transfers():
    a, b = wallet("a"), wallet("b")
    tx = helius_tx(a, b, lamports=1_500_000_000, at=1_700_000_000, sig="sig1")
    tx["tokenTransfers"] = [
        {"fromUserAccount": b, "toUserAccount": a, "tokenAmount": 25.0, "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"},
        {"fromUserAccount": b, "toUserAccount": a, "tokenAmount": 1e9, "mint": wallet("random-memecoin")},
    ]
    transfers = parse_transfers([tx])
    assert [(t.amount, t.asset) for t in transfers] == [(1.5, Asset.SOL), (25.0, Asset.USDC)]


def test_parser_skips_self_transfers_and_empty_fields():
    a = wallet("a")
    tx = helius_tx(a, a, lamports=5, at=1, sig="s")
    tx["nativeTransfers"].append({"fromUserAccount": None, "toUserAccount": a, "amount": 10})
    assert parse_transfers([tx, {"signature": "empty"}]) == []
