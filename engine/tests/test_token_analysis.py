import asyncio

from fastapi.testclient import TestClient

from ladon.api import create_app
from ladon.config import Settings
from ladon.engine import Engine
from ladon.store import MemoryStore
from ladon.tokens.analysis import TokenChecker, classify, created_mints, first_funder, is_busy, sol_recipients
from helpers import wallet
from token_fixtures import DAY, FakeDex, FakeRpc, launch, pair, sol_transfer, trade, tx

NOW = 1_800_000_000
SOL = 10**9
CREATED = NOW - DAY
MINT, DEPLOYER, FUNDER, SIBLING, EXCHANGE, B1, B2 = (wallet(n) for n in ["mint", "deployer", "funder", "sibling", "exchange", "b1", "b2"])
OLD = [wallet(f"old-{i}") for i in range(3)]
SIBLING_OLD = [wallet(f"sibling-old-{i}") for i in range(2)]


def dump(owner: str, mint: str, at: int) -> list[dict]:
    return [trade(mint, at, [(owner, 1000, -SOL)]), trade(mint, at + 600, [(owner, -950, 2 * SOL)])]


def world() -> tuple[dict, dict, dict]:
    histories = {
        MINT: [
            launch(DEPLOYER, MINT, CREATED, via_program=True),
            trade(MINT, CREATED, [(DEPLOYER, 5000, -SOL)], slot=CREATED),
            trade(MINT, CREATED + 1, [(B1, 2000, -SOL)], slot=CREATED + 1),
            trade(MINT, CREATED + 2, [(B2, 1000, -SOL)], slot=CREATED + 2),
            trade(MINT, CREATED + 3, [(wallet("sniper"), 1500, -SOL)], slot=CREATED + 1),
        ],
        DEPLOYER: [
            tx(FUNDER, NOW - 60 * DAY, top=[sol_transfer(FUNDER, DEPLOYER)]),
            launch(DEPLOYER, OLD[0], NOW - 30 * DAY),
            *dump(DEPLOYER, OLD[0], NOW - 30 * DAY),
            launch(DEPLOYER, OLD[1], NOW - 20 * DAY, via_program=True),
            *dump(DEPLOYER, OLD[1], NOW - 20 * DAY),
            launch(DEPLOYER, OLD[2], NOW - 10 * DAY),
            tx(DEPLOYER, CREATED - 60, top=[sol_transfer(DEPLOYER, B1), sol_transfer(DEPLOYER, B2)]),
            launch(DEPLOYER, MINT, CREATED, via_program=True),
            trade(MINT, CREATED, [(DEPLOYER, 5000, -SOL)], slot=CREATED),
            trade(MINT, CREATED + 3600, [(DEPLOYER, -4500, 3 * SOL)], slot=CREATED + 3600),
        ],
        FUNDER: [
            tx(FUNDER, NOW - 70 * DAY, top=[sol_transfer(FUNDER, SIBLING)]),
            tx(FUNDER, NOW - 60 * DAY, top=[sol_transfer(FUNDER, DEPLOYER)]),
        ],
        SIBLING: [
            launch(SIBLING, SIBLING_OLD[0], NOW - 15 * DAY),
            *dump(SIBLING, SIBLING_OLD[0], NOW - 15 * DAY),
            launch(SIBLING, SIBLING_OLD[1], NOW - 14 * DAY),
        ],
    }
    mints = {MINT: {"mintAuthority": None, "freezeAuthority": DEPLOYER}}
    pairs = {OLD[0]: [pair(OLD[0], 120)], OLD[2]: [pair(OLD[2], 50_000)], SIBLING_OLD[1]: [pair(SIBLING_OLD[1], 10)]}
    return mints, histories, pairs


def checker(mints, histories, pairs, failing=frozenset(), dex_fails=False, excluded=frozenset(), holders=None, clock=lambda: NOW):
    rpc = FakeRpc(mints, histories, failing, holders={B1: 200} if holders is None else holders, supply=10_000)
    return TokenChecker(rpc, FakeDex(pairs, dex_fails), excluded, clock=clock)


def check(*args, **kwargs):
    return asyncio.run(checker(*args, **kwargs).check(MINT))


def points(body) -> dict[str, int]:
    return {r["label"]: r["points"] for r in body["reasons"]}


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


def test_a_rug_needs_sell_evidence_not_just_a_dead_chart():
    assert classify([pair(MINT, 5)], dumped=False) == "unknown"
    assert classify([], dumped=True) == "likely rug"
    assert classify([pair(MINT, 20_000)], dumped=True) == "likely rug"
    assert classify([pair(MINT, 20_000)], dumped=False) == "active"


def test_busy_funders_look_like_exchanges():
    many = [wallet(f"customer-{i}") for i in range(100)]
    assert is_busy([], many, 1000)
    burst = [tx(EXCHANGE, NOW - i) for i in range(1000)]
    assert is_busy(burst, [], 1000)
    assert not is_busy(burst[:40], many[:10], 1000)


def test_full_check_catches_the_dump_the_bundle_and_the_funding_link():
    body = check(*world())
    assert body["deployer"] == DEPLOYER
    assert body["funder"] == FUNDER
    assert body["score"] == 100
    assert body["level"] == "high"
    got = points(body)
    assert got["Deployer dumped earlier tokens"] == 45
    assert got["Linked wallets dumped their tokens"] == 20
    assert got["Creator dumped this token"] == 35
    assert got["Launch bundle already sold"] == 30
    assert got["Holders can be frozen"] == 15
    outcomes = {p["mint"]: (p["outcome"], p["created_by"]) for p in body["past_tokens"]}
    assert outcomes[OLD[0]] == ("likely rug", "deployer")
    assert outcomes[OLD[2]] == ("active", "deployer")
    assert outcomes[SIBLING_OLD[0]] == ("likely rug", "linked wallet")
    assert outcomes[SIBLING_OLD[1]] == ("unknown", "linked wallet")
    assert MINT not in outcomes


def test_a_dead_token_without_selling_is_not_called_a_rug():
    mints, histories, pairs = world()
    histories[DEPLOYER] = [t for t in histories[DEPLOYER] if not (t.get("meta") or {}).get("postTokenBalances") or t["meta"]["postTokenBalances"][0]["mint"] == MINT]
    body = check(mints, histories, pairs)
    outcomes = {p["mint"]: p["outcome"] for p in body["past_tokens"] if p["created_by"] == "deployer"}
    assert outcomes[OLD[0]] == "unknown"
    assert "No dumped tokens from this deployer" in points(body)


def test_snipers_are_not_mistaken_for_the_creators_bundle():
    mints, histories, pairs = world()
    histories[DEPLOYER] = [t for t in histories[DEPLOYER] if not any(i.get("parsed", {}).get("info", {}).get("destination") in (B1, B2) for i in t["transaction"]["message"]["instructions"])]
    body = check(mints, histories, pairs, holders={})
    assert "No launch bundle found" in points(body)


def test_a_throwaway_deployer_is_flagged_as_brand_new():
    histories = {
        MINT: [launch(DEPLOYER, MINT, CREATED, via_program=True)],
        DEPLOYER: [tx(FUNDER, CREATED - 7200, top=[sol_transfer(FUNDER, DEPLOYER)]), launch(DEPLOYER, MINT, CREATED, via_program=True)],
        FUNDER: [tx(FUNDER, CREATED - 7200, top=[sol_transfer(FUNDER, DEPLOYER)])],
    }
    body = check({MINT: {"mintAuthority": None, "freezeAuthority": None}}, histories, {}, holders={})
    assert points(body)["Brand-new deployer wallet"] == 10
    assert body["score"] == 10
    assert body["level"] == "low"


def test_exchange_funding_is_never_used_as_a_link():
    mints, histories, pairs = world()
    histories[FUNDER] += [tx(FUNDER, NOW - 50 * DAY + i, top=[sol_transfer(FUNDER, wallet(f"customer-{i}"))]) for i in range(120)]
    body = check(mints, histories, pairs)
    assert "Funder not traced" in points(body)
    assert all(p["created_by"] == "deployer" for p in body["past_tokens"])


def test_listed_infrastructure_funders_are_skipped():
    assert "Funder not traced" in points(check(*world(), excluded=frozenset({FUNDER})))


def test_helius_failure_returns_partial_results_not_an_error():
    body = check(*world(), failing={DEPLOYER})
    got = points(body)
    assert "Deployer history not checked" in got
    assert "Creator's selling not checked" in got
    assert any("deployer's history" in r["explanation"] for r in body["reasons"] if r["label"] == "Not checked")


def test_holder_lookup_failure_returns_partial_results():
    body = check(*world(), failing={"holders"})
    assert "Launch buyers not checked" in points(body)
    assert body["level"] == "high"


def test_dexscreener_failure_still_uses_sell_evidence():
    body = check(*world(), dex_fails=True)
    outcomes = {p["mint"]: p["outcome"] for p in body["past_tokens"]}
    assert outcomes[OLD[0]] == "likely rug"
    assert outcomes[OLD[2]] == "unknown"


def test_results_are_cached_for_ten_minutes():
    mints, histories, pairs = world()
    clock = {"now": NOW}
    c = checker(mints, histories, pairs, clock=lambda: clock["now"])
    asyncio.run(c.check(MINT))
    calls = len(c.rpc.calls)
    clock["now"] += 9 * 60
    asyncio.run(c.check(MINT))
    assert len(c.rpc.calls) == calls
    clock["now"] += 2 * 60
    asyncio.run(c.check(MINT))
    assert len(c.rpc.calls) > calls


def client(tokens: TokenChecker | None) -> TestClient:
    return TestClient(create_app(Settings(reporter_salt="test"), Engine(MemoryStore()), tokens=tokens))


def test_endpoint_rejects_invalid_mints_before_any_api_call():
    c = checker({}, {}, {})
    api = client(c)
    for bad in ["hello", "0" * 44, "<script>"]:
        assert api.get(f"/v1/token/{bad}/risk").status_code == 400
    assert c.rpc.calls == []


def test_endpoint_rejects_addresses_that_are_not_tokens():
    response = client(checker({}, {}, {})).get(f"/v1/token/{wallet('just-a-wallet')}/risk")
    assert response.status_code == 400
    assert "not a token" in response.json()["detail"]


def test_endpoint_returns_the_documented_shape():
    body = client(checker(*world())).get(f"/v1/token/{MINT}/risk").json()
    assert set(body) == {"mint", "deployer", "funder", "score", "level", "reasons", "past_tokens", "checked_at"}
    assert set(body["reasons"][0]) == {"label", "explanation", "points"}
    assert set(body["past_tokens"][0]) == {"mint", "created_at", "outcome", "created_by"}


def test_endpoint_is_rate_limited_per_visitor():
    api = client(checker(*world()))
    codes = [api.get(f"/v1/token/{MINT}/risk").status_code for _ in range(22)]
    assert codes[:20] == [200] * 20
    assert codes[20:] == [429, 429]


def test_endpoint_without_a_helius_key_says_so():
    assert client(None).get(f"/v1/token/{MINT}/risk").status_code == 503
