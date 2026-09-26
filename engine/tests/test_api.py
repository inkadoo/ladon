from fastapi.testclient import TestClient

from ladon.api import create_app
from ladon.config import Settings
from ladon.engine import Engine
from ladon.store import MemoryStore
from helpers import FakeHelius, helius_tx, signature, takeover_tx, wallet

DRAINER, OPERATOR, MULE, VICTIM, SWEEPER, CASHOUT = (
    wallet(n) for n in ["drainer", "operator", "mule", "victim", "sweeper", "cashout"]
)
SOL = 1_000_000_000


def client_for(histories: dict[str, list[dict]], known_drainers=frozenset({DRAINER}), transactions=()) -> TestClient:
    engine = Engine(MemoryStore(), known_drainers=known_drainers, helius=FakeHelius(histories, transactions))
    return TestClient(create_app(Settings(reporter_salt="test"), engine))


def drain_ring() -> dict[str, list[dict]]:
    victim_pays = helius_tx(VICTIM, DRAINER, 12 * SOL, 1_700_000_000, "v")
    to_operator = helius_tx(DRAINER, OPERATOR, 11 * SOL, 1_700_000_100, "d")
    to_mule = helius_tx(OPERATOR, MULE, 5 * SOL, 1_700_000_200, "o")
    return {
        DRAINER: [victim_pays, to_operator],
        OPERATOR: [to_operator, to_mule],
        MULE: [to_mule],
    }


def test_rejects_invalid_addresses():
    client = client_for({})
    assert client.get("/v1/address/not-an-address").status_code == 400
    assert client.post("/v1/reports", json={"address": "0OIl"}).status_code == 400


def test_unknown_wallet_has_no_risk_and_says_why():
    body = client_for({}).get(f"/v1/address/{wallet('stranger')}").json()
    assert body["risk"] == 0
    assert body["confidence"] == "none"
    assert body["reasons"][0]["code"] == "no_data"


def test_a_report_starts_a_check_and_the_ring_is_exposed():
    client = client_for(drain_ring())
    response = client.post("/v1/reports", json={"address": OPERATOR, "description": "Took my SOL"})
    assert response.status_code == 202

    operator = client.get(f"/v1/address/{OPERATOR}").json()
    assert operator["flagged"]
    assert operator["risk"] >= 0.7
    assert any(r["code"] == "linked_to_scam" for r in operator["reasons"])

    mule = client.get(f"/v1/address/{MULE}").json()
    assert 0.3 < mule["risk"] < operator["risk"]

    victim = client.get(f"/v1/address/{VICTIM}").json()
    assert victim["risk"] == 0
    assert not victim["flagged"]


def test_a_report_with_no_evidence_does_not_flag():
    client = client_for({})
    target = wallet("innocent")
    client.post("/v1/reports", json={"address": target, "description": "I think this is a scam"})
    body = client.get(f"/v1/address/{target}").json()
    assert not body["flagged"]
    assert body["confidence"] == "low"


def test_the_same_reporter_counts_once():
    client = client_for({})
    target = wallet("target")
    for _ in range(3):
        client.post("/v1/reports", json={"address": target})
    assert client.get(f"/v1/address/{target}").json()["reports"] == 1


def test_reports_are_rate_limited():
    client = client_for({})
    codes = [client.post("/v1/reports", json={"address": wallet(f"t{i}")}).status_code for i in range(7)]
    assert codes[:5] == [202] * 5
    assert codes[5:] == [429, 429]


def test_a_sweeper_funded_by_a_drainer_is_confirmed_and_passes_risk_on():
    histories = drain_ring()
    funded = helius_tx(DRAINER, SWEEPER, 3 * SOL, 1_700_001_000, "f")
    sweeps = []
    for i in range(4):
        at = 1_700_002_000 + i * 3600
        sweeps.append(helius_tx(wallet(f"v{i}"), SWEEPER, 2 * SOL, at, f"in{i}"))
        sweeps.append(helius_tx(SWEEPER, CASHOUT, 2 * SOL - 5000, at + 3, f"out{i}"))
    histories[SWEEPER] = [funded, *sweeps]
    histories[DRAINER].append(funded)
    client = client_for(histories)

    client.post("/v1/reports", json={"address": SWEEPER})
    sweeper = client.get(f"/v1/address/{SWEEPER}").json()
    assert sweeper["confidence"] == "high"
    assert {"sweeps_incoming", "linked_to_scam"} <= {r["code"] for r in sweeper["reasons"]}

    cashout = client.get(f"/v1/address/{CASHOUT}").json()
    assert cashout["flagged"]


ATTACKER = wallet("attacker")


def drained(victim: str) -> dict:
    return takeover_tx(victim, ATTACKER, wallet(f"{victim}-usdc"), 1_700_000_000, signature(f"drain-{victim}"))


def report_drain(client: TestClient, victim: str):
    return client.post("/v1/reports", json={"address": ATTACKER, "signature": signature(f"drain-{victim}")})


def test_one_victims_signature_flags_the_attacker_without_confirming_it():
    client = client_for({}, known_drainers=frozenset(), transactions=[drained(wallet("v1"))])
    assert report_drain(client, wallet("v1")).status_code == 202
    body = client.get(f"/v1/address/{ATTACKER}").json()
    assert body["flagged"]
    assert body["reasons"][0]["code"] == "took_token_accounts"
    assert body["risk"] < 0.8


def test_three_victims_confirm_a_drainer_and_expose_where_the_money_went():
    victims = [wallet(f"v{i}") for i in range(3)]
    cashout = helius_tx(ATTACKER, OPERATOR, 40 * SOL, 1_700_000_500, signature("cashout"))
    client = client_for({ATTACKER: [cashout]}, known_drainers=frozenset(), transactions=[drained(v) for v in victims])
    for victim in victims:
        report_drain(client, victim)

    attacker = client.get(f"/v1/address/{ATTACKER}").json()
    assert attacker["confidence"] == "high"
    assert "3 different wallets" in attacker["reasons"][0]["text"]

    operator = client.get(f"/v1/address/{OPERATOR}").json()
    assert operator["flagged"]
    assert operator["reasons"][0]["code"] == "linked_to_scam"

    for victim in victims:
        assert client.get(f"/v1/address/{victim}").json()["risk"] == 0


def test_rejects_malformed_signatures():
    client = client_for({})
    response = client.post("/v1/reports", json={"address": ATTACKER, "signature": "not-a-signature"})
    assert response.status_code == 400
