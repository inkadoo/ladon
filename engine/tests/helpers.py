import hashlib

from ladon.addresses import b58decode, b58encode
from ladon.models import Asset, Transfer


def wallet(name: str) -> str:
    return b58encode(hashlib.sha256(name.encode()).digest())


def signature(name: str) -> str:
    return b58encode(hashlib.sha512(name.encode()).digest())


def sol(source: str, destination: str, amount: float = 1.0, at: int = 1_700_000_000, sig: str | None = None) -> Transfer:
    return Transfer(source, destination, amount, Asset.SOL, at, sig or f"{source[:6]}-{destination[:6]}-{at}")


def helius_tx(source: str, destination: str, lamports: int, at: int, sig: str) -> dict:
    return {
        "signature": sig,
        "timestamp": at,
        "nativeTransfers": [{"fromUserAccount": source, "toUserAccount": destination, "amount": lamports}],
        "tokenTransfers": [],
    }


def takeover_tx(victim: str, attacker: str, token_account: str, at: int, sig: str, program: str = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA") -> dict:
    data = b58encode(bytes([6, 2, 1]) + b58decode(attacker))
    return {
        "signature": sig,
        "timestamp": at,
        "nativeTransfers": [],
        "tokenTransfers": [],
        "instructions": [
            {"programId": "ComputeBudget111111111111111111111111111111", "accounts": [], "data": "3", "innerInstructions": []},
            {"programId": program, "accounts": [token_account, victim], "data": data, "innerInstructions": []},
        ],
    }


class FakeHelius:
    def __init__(self, histories: dict[str, list[dict]], transactions: list[dict] = ()):
        self.histories = histories
        self.calls: list[str] = []
        self.by_signature = {tx["signature"]: tx for txs in histories.values() for tx in txs}
        self.by_signature.update({tx["signature"]: tx for tx in transactions})

    async def transaction(self, signature: str) -> list[dict]:
        return [self.by_signature[signature]] if signature in self.by_signature else []

    async def transactions(self, address: str, limit: int = 100) -> list[dict]:
        self.calls.append(address)
        return self.histories.get(address, [])

    async def close(self) -> None:
        pass
