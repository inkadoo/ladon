import asyncio

from fastapi.testclient import TestClient

from ladon.api import create_app
from ladon.config import Settings
from ladon.engine import Engine
from ladon.store import MemoryStore
from ladon.tokens.analysis import TokenChecker, classify, created_mints, first_funder, is_busy, sol_recipients
from helpers import wallet
from token_fixtures import DAY, FakeDex, FakeRpc, launch, pair, sol_transfer, tx

NOW = 1_800_000_000
MINT, DEPLOYER, FUNDER, SIBLING, EXCHANGE = (wallet(n) for n in ["mint", "deployer", "funder", "sibling", "exchange"])
OLD = [wallet(f"old-{i}") for i in range(4)]
SIBLING_OLD = [wallet(f"sibling-old-{i}") for i in range(3)]


def world(deployer_age_days: float = 35, funder_extra: list | None = None) -> tuple[dict, dict, dict]:
    created = NOW - DAY
    histories = {
        MINT: [launch(DEPLOYER, MINT, created, via_program=True)],
        DEPLOYER: [
            tx(FUNDER, int(created - deployer_age_days * DAY), top=[sol_transfer(FUNDER, DEPLOYER)]),
            launch(DEPLOYER, OLD[0], NOW - 30 * DAY),
            launch(DEPLOYER, OLD[1], NOW - 20 * DAY, via_program=True),
            launch(DEPLOYER, OLD[2], NOW - 10 * DAY),
            launch(DEPLOYER, MINT, created, via_program=True),
        ],
        FUNDER: [
            tx(FUNDER, NOW - 40 * DAY, top=[sol_transfer(FUNDER, SIBLING)]),
            tx(FUNDER, int(created - deployer_age_days * DAY), top=[sol_transfer(FUNDER, DEPLOYER)]),
            *(funder_extra or []),
        ],
        SIBLING: [launch(SIBLING, m, NOW - (15 + i) * DAY) for i, m in enumerate(SIBLING_OLD)],
    }
    mints = {MINT: {"mintAuthority": None, "freezeAuthority": DEPLOYER}}
    pairs = {
        OLD[0]: [pair(OLD[0], 120)],
        OLD[1]: [pair(OLD[1], 40)],
        OLD[2]: [pair(OLD[2], 50_000)],
        SIBLING_OLD[0]: [pair(SIBLING_OLD[0], 10)],
        SIBLING_OLD[1]: [pair(SIBLING_OLD[1], 900)],
    }
    return mints, histories, pairs


def check(mints, histories, pairs, failing=frozenset(), dex_fails=False, excluded=frozenset()):
    checker = TokenChecker(FakeRpc(mints, histories, failing), FakeDex(pairs, dex_fails), excluded, clock=lambda: NOW)
    return asyncio.run(checker.check(MINT))


def test_finds_mints_created_directly_or_through_a_launchpad():
    txs = [launch(DEPLOYER, OLD[0], 1), launch(DEPLOYER, OLD[1], 2, via_program=True), launch(SIBLING, OLD[2], 3)]
    assert set(created_mints(txs, DEPLOYER)) == {OLD[0], OLD[1]}


def test_funder_is_the_first_wallet_to_send_sol():
    txs = [tx(FUNDER, 1, top=[sol_transfer(FUNDER, DEPLOYER)]), tx(SIBLING, 2, top=[sol_transfer(SIBLING, DEPLOYER)])]
    assert first_funder(txs, DEPLOYER) == FUNDER
    assert first_funder([tx(DEPLOYER, 1, top=[sol_transfer(DEPLOYER, FUNDER)])], DEPLOYER) is None


def test_recipients_are_ranked_by_how_often_they_were_paid():
    txs = [tx(FUNDER, i, top=[sol_transfer(FUNDER, SIBLING if i % 3 else DEPLOYER)]) for i in range(6)]
    assert sol_recipients(txs, FUNDER) == [SIBLING, DEPLOYER]


def test_outcomes():
    assert classify([pair(MINT, 50)], NOW - 3 * DAY, NOW) == "likely rug"
    assert classify([pair(MINT, 50)], NOW - 3600, NOW) == "unknown"
    assert classify([pair(MINT, 5_000)], NOW - 3 * DAY, NOW) == "unknown"
    assert classify([pair(MINT, 20_000), pair(MINT, 5)], NOW - 3 * DAY, NOW) == "active"
    assert classify([], NOW - 3 * DAY, NOW) == "unknown"


def test_busy_funders_look_like_exchanges():
    many = [wallet(f"customer-{i}") for i in range(100)]
    assert is_busy([], many, 1000)
    burst = [tx(EXCHANGE, NOW - i) for i in range(1000)]
    assert is_busy(burst, [], 1000)
    assert not is_busy(burst[:40], many[:10], 1000)


def test_full_check_links_the_fresh_deployer_to_its_funders_rugs():
    body = check(*world())
    assert body["deployer"] == DEPLOYER
    assert body["funder"] == FUNDER
    assert body["level"] == "high"
    labels = {r["label"]: r["points"] for r in body["reasons"]}
    assert labels["Deployer's past tokens collapsed"] == 45
    assert labels["Linked wallets have rugged"] == 30
    assert labels["Holders can be frozen"] == 15
    assert labels["Supply is fixed"] == 0
    assert labels["Established deployer wallet"] == 0
    outcomes = {p["mint"]: (p["outcome"], p["created_by"]) for p in body["past_tokens"]}
    assert outcomes[OLD[2]] == ("active", "deployer")
    assert outcomes[SIBLING_OLD[0]] == ("likely rug", "linked wallet")
    assert MINT not in outcomes


def test_a_throwaway_deployer_is_flagged_as_brand_new():
    created = NOW - DAY
    histories = {
        MINT: [launch(DEPLOYER, MINT, created, via_program=True)],
        DEPLOYER: [tx(FUNDER, created - 7200, top=[sol_transfer(FUNDER, DEPLOYER)]), launch(DEPLOYER, MINT, created, via_program=True)],
        FUNDER: [tx(FUNDER, created - 7200, top=[sol_transfer(FUNDER, DEPLOYER)])],
    }
    body = check({MINT: {"mintAuthority": None, "freezeAuthority": None}}, histories, {})
    assert {r["label"]: r["points"] for r in body["reasons"]}["Brand-new deployer wallet"] == 10
    assert body["score"] == 10
    assert body["level"] == "low"


def test_exchange_funding_is_never_used_as_a_link():
    mints, histories, pairs = world()
    histories[FUNDER] += [tx(FUNDER, NOW - 50 * DAY + i, top=[sol_transfer(FUNDER, wallet(f"customer-{i}"))]) for i in range(120)]
    body = check(mints, histories, pairs)
    labels = {r["label"] for r in body["reasons"]}
    assert "Funder not traced" in labels
    assert all(p["created_by"] == "deployer" for p in body["past_tokens"])


def test_listed_infrastructure_funders_are_skipped():
    body = check(*world(), excluded=frozenset({FUNDER}))
    assert "Funder not traced" in {r["label"] for r in body["reasons"]}


def test_helius_failure_returns_partial_results_not_an_error():
    body = check(*world(), failing={DEPLOYER})
    labels = {r["label"] for r in body["reasons"]}
    assert "Deployer history not checked" in labels
    assert any("deployer's history" in r["explanation"] for r in body["reasons"] if r["label"] == "Not checked")
    assert body["score"] == 15


def test_dexscreener_failure_returns_partial_results():
    body = check(*world(), dex_fails=True)
    assert "Deployer history not checked" in {r["label"] for r in body["reasons"]}
    assert all(p["outcome"] == "unknown" for p in body["past_tokens"])


def test_results_are_cached_for_ten_minutes():
    mints, histories, pairs = world()
    clock = {"now": NOW}
    rpc = FakeRpc(mints, histories)
    checker = TokenChecker(rpc, FakeDex(pairs), clock=lambda: clock["now"])
    asyncio.run(checker.check(MINT))
    calls = len(rpc.calls)
    clock["now"] += 9 * 60
    asyncio.run(checker.check(MINT))
    assert len(rpc.calls) == calls
    clock["now"] += 2 * 60
    asyncio.run(checker.check(MINT))
    assert len(rpc.calls) > calls


def client(checker: TokenChecker | None) -> TestClient:
    engine = Engine(MemoryStore())
    return TestClient(create_app(Settings(reporter_salt="test"), engine, tokens=checker))


def test_endpoint_rejects_invalid_mints_before_any_api_call():
    rpc = FakeRpc({}, {})
    c = client(TokenChecker(rpc, FakeDex({})))
    for bad in ["hello", "0" * 44, "<script>"]:
        assert c.get(f"/v1/token/{bad}/risk").status_code == 400
    assert rpc.calls == []


def test_endpoint_rejects_addresses_that_are_not_tokens():
    c = client(TokenChecker(FakeRpc({}, {}), FakeDex({})))
    response = c.get(f"/v1/token/{wallet('just-a-wallet')}/risk")
    assert response.status_code == 400
    assert "not a token" in response.json()["detail"]


def test_endpoint_returns_the_documented_shape():
    mints, histories, pairs = world()
    checker = TokenChecker(FakeRpc(mints, histories), FakeDex(pairs), clock=lambda: NOW)
    body = client(checker).get(f"/v1/token/{MINT}/risk").json()
    assert set(body) == {"mint", "deployer", "funder", "score", "level", "reasons", "past_tokens", "checked_at"}
    assert set(body["reasons"][0]) == {"label", "explanation", "points"}
    assert set(body["past_tokens"][0]) == {"mint", "created_at", "outcome", "created_by"}


def test_endpoint_without_a_helius_key_says_so():
    assert client(None).get(f"/v1/token/{MINT}/risk").status_code == 503
