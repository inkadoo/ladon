import hashlib

from ladon.addresses import b58encode
from ladon.models import Asset, Transfer


def wallet(name: str) -> str:
    return b58encode(hashlib.sha256(name.encode()).digest())


def sol(source: str, destination: str, amount: float = 1.0, at: int = 1_700_000_000, sig: str | None = None) -> Transfer:
    return Transfer(source, destination, amount, Asset.SOL, at, sig or f"{source[:6]}-{destination[:6]}-{at}")


def helius_tx(source: str, destination: str, lamports: int, at: int, sig: str) -> dict:
    return {
        "signature": sig,
        "timestamp": at,
        "nativeTransfers": [{"fromUserAccount": source, "toUserAccount": destination, "amount": lamports}],
        "tokenTransfers": [],
    }


class FakeHelius:
    def __init__(self, histories: dict[str, list[dict]]):
        self.histories = histories
        self.calls: list[str] = []

    async def transactions(self, address: str, limit: int = 100) -> list[dict]:
        self.calls.append(address)
        return self.histories.get(address, [])

    async def close(self) -> None:
        pass
