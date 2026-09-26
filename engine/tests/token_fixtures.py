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


BASE = 10**15


def trade(mint: str, at: int, moves: list[tuple[str, int, int]], slot: int | None = None, payer: str | None = None) -> dict:
    wallets = [w for w, _, _ in moves]
    first = payer or wallets[0]
    keys = [{"pubkey": first, "signer": True}] + [{"pubkey": w, "signer": True} for w in wallets if w != first]
    pre = [{"accountIndex": i, "mint": mint, "owner": w, "uiTokenAmount": {"amount": str(BASE)}} for i, (w, _, _) in enumerate(moves)]
    post = [{"accountIndex": i, "mint": mint, "owner": w, "uiTokenAmount": {"amount": str(BASE + d)}} for i, (w, d, _) in enumerate(moves)]
    lamports = {w: l for w, _, l in moves}
    return {
        "blockTime": at,
        "slot": slot if slot is not None else at,
        "transactionIndex": 0,
        "transaction": {"message": {"accountKeys": keys, "instructions": []}},
        "meta": {
            "err": None,
            "innerInstructions": [],
            "preTokenBalances": pre,
            "postTokenBalances": post,
            "preBalances": [10**12 for _ in keys],
            "postBalances": [10**12 + lamports.get(k["pubkey"], 0) for k in keys],
        },
    }


def pair(mint: str, liquidity_usd: float) -> dict:
    return {"baseToken": {"address": mint}, "liquidity": {"usd": liquidity_usd}, "priceUsd": "0.0001"}


class FakeRpc:
    def __init__(self, mints: dict, histories: dict, failing: set[str] = frozenset(), holders: dict | None = None, supply: int = 10**15):
        self.mints = mints
        self.histories = histories
        self.failing = failing
        self.holders = holders or {}
        self.total = supply
        self.calls: list[tuple[str, bool, int]] = []

    async def supply(self, mint: str) -> int:
        if "holders" in self.failing:
            raise SourceError("Helius rate limit reached")
        return self.total

    async def largest_holders(self, mint: str) -> dict:
        if "holders" in self.failing:
            raise SourceError("Helius rate limit reached")
        return self.holders

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
