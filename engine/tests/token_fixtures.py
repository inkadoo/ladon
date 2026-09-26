from ladon.tokens.sources import SourceError

SYSTEM = "11111111111111111111111111111111"
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
DAY = 24 * 3600


def tx(payer: str, at: int, top=(), inner=()) -> dict:
    return {
        "blockTime": at,
        "transaction": {"message": {"accountKeys": [{"pubkey": payer, "signer": True}], "instructions": list(top)}},
        "meta": {"err": None, "innerInstructions": [{"index": 0, "instructions": list(inner)}] if inner else []},
    }


def init_mint(mint: str, kind: str = "initializeMint2") -> dict:
    return {"program": "spl-token", "programId": TOKEN, "parsed": {"type": kind, "info": {"mint": mint, "decimals": 6}}}


def sol_transfer(source: str, destination: str, lamports: int = 1_000_000_000) -> dict:
    return {"program": "system", "programId": SYSTEM, "parsed": {"type": "transfer", "info": {"source": source, "destination": destination, "lamports": lamports}}}


def launch(payer: str, mint: str, at: int, via_program: bool = False) -> dict:
    if via_program:
        return tx(payer, at, top=[{"programId": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", "accounts": [], "data": ""}], inner=[init_mint(mint)])
    return tx(payer, at, top=[init_mint(mint, "initializeMint")])


def pair(mint: str, liquidity_usd: float) -> dict:
    return {"baseToken": {"address": mint}, "liquidity": {"usd": liquidity_usd}, "priceUsd": "0.0001"}


class FakeRpc:
    def __init__(self, mints: dict, histories: dict, failing: set[str] = frozenset()):
        self.mints = mints
        self.histories = histories
        self.failing = failing
        self.calls: list[tuple[str, bool, int]] = []

    async def mint(self, mint: str):
        if "mint" in self.failing:
            raise SourceError("Helius rate limit reached")
        return self.mints.get(mint)

    async def history(self, address: str, oldest_first: bool, limit: int):
        self.calls.append((address, oldest_first, limit))
        if address in self.failing:
            raise SourceError("Helius rate limit reached")
        txs = sorted(self.histories.get(address, []), key=lambda t: t["blockTime"], reverse=not oldest_first)
        return txs[:limit]

    async def close(self):
        pass


class FakeDex:
    def __init__(self, pairs: dict, fail: bool = False):
        self._pairs = pairs
        self.fail = fail

    async def pairs(self, mints):
        if self.fail:
            raise SourceError("DexScreener rate limit reached")
        return {m: self._pairs.get(m, []) for m in mints}

    async def close(self):
        pass
