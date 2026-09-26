import logging
from typing import Any

import httpx

from .models import Asset, Transfer

BASE_URL = "https://api.helius.xyz/v0"

STABLECOINS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": Asset.USDC,
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": Asset.USDT,
}
LAMPORTS_PER_SOL = 1_000_000_000

logging.getLogger("httpx").setLevel(logging.WARNING)


def parse_transfers(transactions: list[dict[str, Any]]) -> list[Transfer]:
    transfers: list[Transfer] = []
    for tx in transactions:
        if tx.get("transactionError"):
            continue
        signature = tx.get("signature", "")
        timestamp = int(tx.get("timestamp") or 0)
        for native in tx.get("nativeTransfers") or []:
            source, destination = native.get("fromUserAccount"), native.get("toUserAccount")
            lamports = native.get("amount") or 0
            if source and destination and source != destination and lamports > 0:
                transfers.append(Transfer(source, destination, lamports / LAMPORTS_PER_SOL, Asset.SOL, timestamp, signature))
        for token in tx.get("tokenTransfers") or []:
            asset = STABLECOINS.get(token.get("mint", ""))
            source, destination = token.get("fromUserAccount"), token.get("toUserAccount")
            amount = float(token.get("tokenAmount") or 0)
            if asset and source and destination and source != destination and amount > 0:
                transfers.append(Transfer(source, destination, amount, asset, timestamp, signature))
    return transfers


class Helius:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=20)

    async def transactions(self, address: str, limit: int = 100) -> list[dict[str, Any]]:
        response = await self._client.get(
            f"{BASE_URL}/addresses/{address}/transactions",
            params={"api-key": self._api_key, "limit": min(limit, 100)},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
