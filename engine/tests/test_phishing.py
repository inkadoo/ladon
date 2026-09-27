import asyncio

import httpx
from fastapi.testclient import TestClient

from ladon.api import create_app
from ladon.config import Settings
from ladon.engine import Engine
from ladon.phishing import PhishingList, clean_domain, parse_blocklist
from ladon.store import MemoryStore

BLOCKLIST = """---
  - url: phantom-app.online
  - url: "*.solana-claim.xyz"
  - url: https://Raydlum.io/swap?x=1
  - url: not a domain
  - url: localhost
"""


def fake_client(status: int = 200, text: str = BLOCKLIST, calls: list | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url)
        return httpx.Response(status, text=text)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_cleans_domains_and_drops_junk():
    assert clean_domain("https://WWW.Phantom-App.online/path") == "phantom-app.online"
    assert clean_domain("*.solana-claim.xyz") == "solana-claim.xyz"
    assert clean_domain("not a domain") is None
    assert clean_domain("localhost") is None
    assert clean_domain("<script>.com") is None


def test_parses_phantom_blocklist_entries():
    assert parse_blocklist(BLOCKLIST) == {"phantom-app.online", "solana-claim.xyz", "raydlum.io"}


def test_refresh_merges_remote_with_seed_and_waits_before_refetching():
    calls: list = []
    now = [1000.0]
    phishing = PhishingList(seed={"fake-ladon.xyz"}, client=fake_client(calls=calls), clock=lambda: now[0])
    asyncio.run(phishing.refresh())
    asyncio.run(phishing.refresh())
    assert phishing.domains == ["fake-ladon.xyz", "phantom-app.online", "raydlum.io", "solana-claim.xyz"]
    assert len(calls) == 1
    now[0] += 7 * 60 * 60
    asyncio.run(phishing.refresh())
    assert len(calls) == 2


def test_a_failed_fetch_keeps_the_seed_and_backs_off():
    calls: list = []
    now = [1000.0]
    phishing = PhishingList(seed={"fake-ladon.xyz"}, client=fake_client(status=503, calls=calls), clock=lambda: now[0])
    asyncio.run(phishing.refresh())
    asyncio.run(phishing.refresh())
    assert phishing.domains == ["fake-ladon.xyz"]
    assert len(calls) == 1


def test_endpoint_serves_the_list():
    phishing = PhishingList(seed=set(), client=fake_client())
    api = TestClient(create_app(Settings(reporter_salt="test"), Engine(MemoryStore()), phishing=phishing))
    response = api.get("/v1/phishing/domains")
    assert response.status_code == 200
    assert "phantom-app.online" in response.json()["domains"]
    assert response.json()["updated_at"]
    assert "max-age" in response.headers["cache-control"]
