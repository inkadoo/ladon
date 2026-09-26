from ladon.addresses import b58decode, b58encode
from ladon.evidence import detect_sweeps, detect_takeovers
from ladon.helius import parse_takeovers, parse_transfers
from ladon.models import Asset
from helpers import helius_tx, sol, takeover_tx, wallet

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


def test_dust_moving_through_quickly_is_not_sweeping():
    transfers = []
    for i in range(5):
        at = 1_700_000_000 + i * 60
        transfers.append(sol(wallet(f"rent-{i}"), SWEEPER, amount=0.0015, at=at))
        transfers.append(sol(SWEEPER, COLLECTOR, amount=0.0015, at=at + 1))
    assert detect_sweeps(SWEEPER, transfers) is None


def test_failed_transactions_move_no_money():
    a, b = wallet("a"), wallet("b")
    failed = helius_tx(a, b, lamports=3_000_000_000, at=1, sig="failed")
    failed["transactionError"] = {"InstructionError": [0, "Custom"]}
    assert parse_transfers([failed]) == []


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


ATTACKER = wallet("attacker")


def test_decodes_token_account_takeovers():
    tx = takeover_tx(wallet("victim"), ATTACKER, wallet("token-account"), 1_700_000_000, "t1")
    [takeover] = parse_takeovers([tx])
    assert takeover.victim == wallet("victim")
    assert takeover.attacker == ATTACKER
    assert takeover.token_account == wallet("token-account")


def test_finds_takeovers_hidden_in_inner_instructions_and_token_2022():
    tx = takeover_tx(wallet("victim"), ATTACKER, wallet("ta"), 1, "t", program="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
    tx["instructions"] = [{"programId": wallet("some-program"), "accounts": [], "data": "", "innerInstructions": tx["instructions"]}]
    assert len(parse_takeovers([tx])) == 1


def test_ignores_other_authority_changes_and_failed_transactions():
    tx = takeover_tx(wallet("victim"), ATTACKER, wallet("ta"), 1, "t")
    close_authority = b58encode(bytes([6, 3, 1]) + b58decode(ATTACKER))
    tx["instructions"][1]["data"] = close_authority
    failed = takeover_tx(wallet("victim"), ATTACKER, wallet("ta"), 1, "f")
    failed["transactionError"] = {"InstructionError": [1, "Custom"]}
    assert parse_takeovers([tx, failed]) == []


def test_moving_your_own_accounts_to_yourself_is_not_a_takeover():
    me = wallet("me")
    assert parse_takeovers([takeover_tx(me, me, wallet("ta"), 1, "s")]) == []


def test_takeover_evidence_grows_with_each_different_victim():
    def takeovers(victims):
        return parse_takeovers([takeover_tx(wallet(f"v{i}"), ATTACKER, wallet(f"ta{i}"), i, f"s{i}") for i in range(victims)])

    one, two, three = (detect_takeovers(ATTACKER, takeovers(n)) for n in (1, 2, 3))
    assert one.weight < 0.8 <= two.weight < three.weight
    assert "3 different wallets" in three.text
    assert detect_takeovers(wallet("bystander"), takeovers(3)) is None


def test_one_victim_signing_twice_counts_once():
    victim = wallet("victim")
    txs = [takeover_tx(victim, ATTACKER, wallet(f"ta{i}"), i, f"s{i}") for i in range(3)]
    assert detect_takeovers(ATTACKER, parse_takeovers(txs)).weight == 0.6
