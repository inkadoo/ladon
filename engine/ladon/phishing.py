import asyncio
import re
import time
from pathlib import Path

import httpx

PHANTOM_BLOCKLIST = "https://raw.githubusercontent.com/phantom/blocklist/master/blocklist.yaml"
REFRESH_SECONDS = 6 * 60 * 60
RETRY_SECONDS = 5 * 60
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_ENTRY = re.compile(r"^\s*-\s*url:\s*['\"]?([^'\"\s#]+)")
_DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$")


def clean_domain(raw: str) -> str | None:
    value = raw.strip().lower()
    value = re.sub(r"^[a-z]+://", "", value)
    value = value.split("/", 1)[0].split("?", 1)[0].split(":", 1)[0].rstrip(".")
    value = value.removeprefix("*.").removeprefix("www.")
    return value if _DOMAIN.match(value) else None


def parse_blocklist(text: str) -> set[str]:
    domains = set()
    for line in text.splitlines():
        match = _ENTRY.match(line)
        if match and (domain := clean_domain(match.group(1))):
            domains.add(domain)
    return domains


def load_seed(data_dir: Path = DATA_DIR) -> set[str]:
    path = data_dir / "phishing_domains.txt"
    if not path.exists():
        return set()
    return {d for line in path.read_text().splitlines() if (d := clean_domain(line.split("#", 1)[0]))}


class PhishingList:
    def __init__(self, seed: set[str] | None = None, client: httpx.AsyncClient | None = None, clock=time.time):
        self.seed = set(seed if seed is not None else load_seed())
        self.remote: set[str] = set()
        self.updated_at = 0.0
        self._tried_at = float("-inf")
        self._client = client
        self._clock = clock
        self._lock = asyncio.Lock()

    @property
    def domains(self) -> list[str]:
        return sorted(self.seed | self.remote)

    async def refresh(self) -> None:
        async with self._lock:
            now = self._clock()
            if self.remote and now - self.updated_at < REFRESH_SECONDS:
                return
            if now - self._tried_at < RETRY_SECONDS:
                return
            self._tried_at = now
            client = self._client or httpx.AsyncClient(timeout=10)
            try:
                response = await client.get(PHANTOM_BLOCKLIST)
                if response.status_code == 200:
                    fetched = parse_blocklist(response.text)
                    if fetched:
                        self.remote = fetched
                        self.updated_at = self._clock()
            except httpx.HTTPError:
                pass
            finally:
                if self._client is None:
                    await client.aclose()
