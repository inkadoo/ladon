import asyncio
import logging
from typing import Any

import httpx

RPC_URL = "https://mainnet.helius-rpc.com/"
DEX_URL = "https://api.dexscreener.com/tokens/v1/solana/"
DEX_BATCH = 30
RATE_LIMIT_RETRIES = 1
RATE_LIMIT_BACKOFF_SECONDS = 0.6

logging.getLogger("httpx").setLevel(logging.WARNING)


class SourceError(Exception):
    pass


class HeliusRpc:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None, concurrency: int = 5):
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=8)
        self._gate = asyncio.Semaphore(concurrency)

    async def _call(self, method: str, params: list[Any]) -> Any:
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            async with self._gate:
                try:
                    response = await self._client.post(
                        RPC_URL,
                        params={"api-key": self._api_key},
                        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                    )
                except httpx.HTTPError as error:
                    raise SourceError(f"Helius did not respond ({type(error).__name__})") from None
            if response.status_code != 429 or attempt == RATE_LIMIT_RETRIES:
                break
            await asyncio.sleep(RATE_LIMIT_BACKOFF_SECONDS)
        if response.status_code == 429:
            raise SourceError("Helius rate limit reached")
        if response.status_code != 200:
            raise SourceError(f"Helius returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise SourceError("Helius sent an unreadable reply") from None
        if "error" in body:
            raise SourceError(f"Helius error: {body['error'].get('message', 'unknown')}")
        return body.get("result")

    async def history(self, address: str, oldest_first: bool, limit: int) -> list[dict[str, Any]]:
        result = await self._call(
            "getTransactionsForAddress",
            [
                address,
                {
                    "transactionDetails": "full",
                    "sortOrder": "asc" if oldest_first else "desc",
                    "limit": limit,
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 1,
                    "filters": {"status": "succeeded"},
                },
            ],
        )
        return (result or {}).get("data") or []

    async def mint(self, mint: str) -> dict[str, Any] | None:
        result = await self._call("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        value = (result or {}).get("value")
        if not value:
            return None
        parsed = (value.get("data") or {}).get("parsed") if isinstance(value.get("data"), dict) else None
        if not parsed or parsed.get("type") != "mint":
            return None
        return parsed.get("info") or {}

    async def close(self) -> None:
        await self._client.aclose()


class DexScreener:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(timeout=8)

    async def pairs(self, mints: list[str]) -> dict[str, list[dict[str, Any]]]:
        found: dict[str, list[dict[str, Any]]] = {m: [] for m in mints}
        batches = [mints[i:i + DEX_BATCH] for i in range(0, len(mints), DEX_BATCH)]
        for pairs in await asyncio.gather(*(self._batch(b) for b in batches)):
            for pair in pairs:
                base = (pair.get("baseToken") or {}).get("address")
                if base in found:
                    found[base].append(pair)
        return found

    async def _batch(self, mints: list[str]) -> list[dict[str, Any]]:
        try:
            response = await self._client.get(DEX_URL + ",".join(mints))
        except httpx.HTTPError as error:
            raise SourceError(f"DexScreener did not respond ({type(error).__name__})") from None
        if response.status_code == 429:
            raise SourceError("DexScreener rate limit reached")
        if response.status_code != 200:
            raise SourceError(f"DexScreener returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise SourceError("DexScreener sent an unreadable reply") from None
        return body if isinstance(body, list) else []

    async def close(self) -> None:
        await self._client.aclose()
