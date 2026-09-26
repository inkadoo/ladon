import asyncio

from fastapi.testclient import TestClient

from ladon.api import create_app
from ladon.config import Settings
from ladon.engine import Engine
from ladon.store import MemoryStore
from ladon.wallets.checker import WalletChecker
from ladon.wallets.parse import delegated_pulls, sol_transfers
from ladon.wallets.patterns import drained_victims, dumped_launches, layering, relays
from helpers import wallet
from token_fixtures import TOKEN, FakeRpc, launch, sol_transfer, trade, tx

NOW = 1_800_000_000
SOL = 10**9
SUSPECT, OTHER = wallet("suspect"), wallet("other")
MINT = wallet("mint")


def pay(source: str, destination: str, at: int, sol: float = 1.0) -> dict:
    return tx(source, at, top=[sol_transfer(source, destination, int(sol * SOL))])


def pull(drainer: str, victim: str, at: int) -> dict:
    token_account = wallet(f"{victim}-token-account")
    return {
        "blockTime": at,
        "transaction": {
            "signatures": [f"pull-{victim[:6]}"],
            "message": {
                "accountKeys": [{"pubkey": drainer, "signer": True}, {"pubkey": token_account, "signer": False}],
                "instructions": [
                    {
                        "program": "spl-token",
                        "programId": TOKEN,
                        "parsed": {"type": "transferChecked", "info": {"authority": drainer, "source": token_account, "destination": wallet("stash"), "mint": MINT}},
                    }
                ],
            },
        },
        "meta": {"err": None, "innerInstructions": [], "preTokenBalances": [{"accountIndex": 1, "owner": victim, "mint": MINT, "uiTokenAmount": {"amount": "500"}}]},
    }


def checker(histories: dict, failing=frozenset()) -> WalletChecker:
    return WalletChecker(FakeRpc({}, histories, failing), clock=lambda: NOW)


def findings(histories: dict, address: str = SUSPECT, failing=frozenset()):
    return asyncio.run(checker(histories, failing).check(address))


def codes(result) -> set[str]:
    return {e.code for e in result.evidence}


def test_reads_plain_sol_transfers():
    [t] = sol_transfers([pay(SUSPECT, OTHER, NOW, sol=2.5)])
    assert (t.source, t.destination, t.amount) == (SUSPECT, OTHER, 2.5)


def test_spots_tokens_pulled_from_other_peoples_accounts():
    pulls = delegated_pulls([pull(SUSPECT, wallet(f"v{i}"), NOW + i) for i in range(3)], SUSPECT)
    assert {p.victim for p in pulls} == {wallet(f"v{i}") for i in range(3)}
    assert drained_victims(pulls).weight == 0.95


def test_moving_your_own_tokens_is_not_a_pull():
    own = pull(SUSPECT, SUSPECT, NOW)
    assert delegated_pulls([own], SUSPECT) == []


def test_relaying_money_straight_through_again_and_again():
    txs = []
    for i in range(5):
        at = NOW - i * 3600
        txs += [pay(wallet(f"in{i}"), SUSPECT, at), pay(SUSPECT, wallet(f"out{i}"), at + 20)]
    evidence = relays(SUSPECT, sol_transfers(txs))
    assert evidence and "5 times" in evidence.text


def test_occasional_quick_payments_are_not_relaying():
    txs = [pay(OTHER, SUSPECT, NOW), pay(SUSPECT, wallet("shop"), NOW + 30)]
    assert relays(SUSPECT, sol_transfers(txs)) is None


def test_launching_and_dumping_tokens():
    txs = [launch(SUSPECT, MINT, NOW), trade(MINT, NOW, [(SUSPECT, 1000, -SOL)]), trade(MINT, NOW + 900, [(SUSPECT, -1000, 3 * SOL)]), launch(SUSPECT, wallet("kept"), NOW)]
    evidence = dumped_launches(SUSPECT, txs)
    assert evidence.weight == 0.5
    assert "1 of the 2 tokens" in evidence.text


def test_one_hop_to_a_new_wallet_is_not_layering():
    assert layering(1, 5.0) is None
    assert layering(2, 5.0).code == "layered_through_wallets"


def test_follows_money_through_a_chain_of_fresh_wallets():
    hop1, hop2, hop3 = wallet("hop1"), wallet("hop2"), wallet("hop3")
    histories = {
        SUSPECT: [pay(OTHER, SUSPECT, NOW - 5 * 86400, sol=10), pay(SUSPECT, hop1, NOW, sol=9)],
        hop1: [pay(SUSPECT, hop1, NOW, sol=9), pay(hop1, hop2, NOW + 120, sol=8.9)],
        hop2: [pay(hop1, hop2, NOW + 120, sol=8.9), pay(hop2, hop3, NOW + 300, sol=8.8)],
        hop3: [pay(hop2, hop3, NOW + 300, sol=8.8)],
    }
    result = findings(histories)
    assert "layered_through_wallets" in codes(result)
    assert "chain of 2 brand-new wallets" in next(e.text for e in result.evidence if e.code == "layered_through_wallets")


def test_paying_an_established_wallet_is_not_layering():
    shop = wallet("shop")
    histories = {
        SUSPECT: [pay(SUSPECT, shop, NOW, sol=9)],
        shop: [pay(OTHER, shop, NOW - 90 * 86400), pay(SUSPECT, shop, NOW, sol=9), pay(shop, wallet("supplier"), NOW + 60, sol=8.9)],
    }
    assert "layered_through_wallets" not in codes(findings(histories))


def test_exchanges_are_not_judged_on_money_flow_but_still_on_their_own_actions():
    txs = [pay(SUSPECT, wallet(f"customer-{i}"), NOW - i) for i in range(100)]
    txs += [pay(wallet(f"deposit-{i}"), SUSPECT, NOW - 5000 - i * 60) for i in range(5)]
    txs += [pull(SUSPECT, wallet("victim"), NOW)]
    result = findings({SUSPECT: txs})
    assert result.infrastructure
    assert codes(result) == {"pulled_from_other_wallets"}
    assert any(n.code == "busy_wallet" for n in result.notes)


def test_a_clean_wallet_says_what_was_checked():
    result = findings({SUSPECT: [pay(OTHER, SUSPECT, NOW - 86400), pay(SUSPECT, wallet("shop"), NOW)]})
    assert result.checked and not result.evidence
    assert "found none of the scam patterns" in result.notes[-1].text


def test_helius_failure_falls_back_to_existing_records():
    result = findings({}, failing={SUSPECT})
    assert not result.checked
    assert result.notes[0].code == "not_checked"


def test_results_are_cached():
    rpc = FakeRpc({}, {SUSPECT: [pay(OTHER, SUSPECT, NOW)]})
    c = WalletChecker(rpc, clock=lambda: NOW)
    asyncio.run(c.check(SUSPECT))
    calls = len(rpc.calls)
    asyncio.run(c.check(SUSPECT))
    assert len(rpc.calls) == calls


def test_lookup_runs_the_deep_check_and_merges_reports():
    engine = Engine(MemoryStore())
    asyncio.run(engine.report(SUSPECT, "someone", "drained me"))
    histories = {SUSPECT: [pull(SUSPECT, wallet(f"v{i}"), NOW + i) for i in range(3)]}
    api = TestClient(create_app(Settings(reporter_salt="test"), engine, wallets=checker(histories)))
    body = api.get(f"/v1/address/{SUSPECT}").json()
    assert body["flagged"] and body["confidence"] == "high"
    got = [r["code"] for r in body["reasons"]]
    assert got[0] == "pulled_from_other_wallets"
    assert "reported" in got


def test_lookup_of_a_quiet_wallet_is_low_risk_not_unknown():
    api = TestClient(create_app(Settings(reporter_salt="test"), Engine(MemoryStore()), wallets=checker({SUSPECT: [pay(OTHER, SUSPECT, NOW)]})))
    body = api.get(f"/v1/address/{SUSPECT}").json()
    assert body["risk"] == 0 and not body["flagged"]
    assert body["confidence"] == "low"


def test_wallet_lookups_are_rate_limited():
    api = TestClient(create_app(Settings(reporter_salt="test"), Engine(MemoryStore()), wallets=checker({})))
    statuses = [api.get(f"/v1/address/{wallet(f'w{i}')}").status_code for i in range(22)]
    assert statuses[:20] == [200] * 20
    assert statuses[20:] == [429, 429]
