import logging
from typing import Any

import httpx

from .addresses import InvalidAddress, b58decode, b58encode
from .models import Asset, Takeover, Transfer

BASE_URL = "https://api.helius.xyz/v0"

STABLECOINS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": Asset.USDC,
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": Asset.USDT,
}
LAMPORTS_PER_SOL = 1_000_000_000
TOKEN_PROGRAMS = {
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
}
SET_AUTHORITY = 6
ACCOUNT_OWNER = 2

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


def _instructions(tx: dict[str, Any]):
    for ins in tx.get("instructions") or []:
        yield ins
        yield from ins.get("innerInstructions") or []


def parse_takeovers(transactions: list[dict[str, Any]]) -> list[Takeover]:
    takeovers: list[Takeover] = []
    for tx in transactions:
        if tx.get("transactionError"):
            continue
        for ins in _instructions(tx):
            accounts = ins.get("accounts") or []
            if ins.get("programId") not in TOKEN_PROGRAMS or len(accounts) < 2:
                continue
            try:
                data = b58decode(ins.get("data") or "")
            except InvalidAddress:
                continue
            if len(data) != 35 or data[0] != SET_AUTHORITY or data[1] != ACCOUNT_OWNER or data[2] != 1:
                continue
            victim, attacker = accounts[1], b58encode(data[3:35])
            if victim != attacker:
                takeovers.append(Takeover(victim, attacker, accounts[0], int(tx.get("timestamp") or 0), tx.get("signature", "")))
    return takeovers


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

    async def transaction(self, signature: str) -> list[dict[str, Any]]:
        response = await self._client.post(
            f"{BASE_URL}/transactions",
            params={"api-key": self._api_key},
            json={"transactions": [signature]},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
