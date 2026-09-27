import argparse
import asyncio
import os
from pathlib import Path

from ladon.engine import Engine
from ladon.exclusions import load_exclusions
from ladon.store import MemoryStore
from ladon.tokens.analysis import TokenChecker
from ladon.tokens.sources import DexScreener, HeliusRpc, SourceError
from ladon.wallets.checker import WalletChecker

SAFE_TOKENS = {
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "wSOL": "So11111111111111111111111111111111111111112",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
    "mSOL": "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
}

HOLDER_SOURCES = ["USDC", "USDT", "BONK", "JUP"]


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


async def check_tokens(tokens: TokenChecker) -> list[tuple[str, str, int]]:
    rows = []
    for name, mint in SAFE_TOKENS.items():
        try:
            result = await tokens.check(mint)
            rows.append((name, result["level"], result["score"]))
        except SourceError as error:
            rows.append((name, f"error: {error}", -1))
    return rows


async def check_wallets(rpc: HeliusRpc, engine: Engine, wallets: WalletChecker, per_token: int) -> list[tuple[str, str, bool, float]]:
    seen: dict[str, str] = {}
    for name in HOLDER_SOURCES:
        try:
            holders = await rpc.largest_holders(SAFE_TOKENS[name])
        except SourceError:
            continue
        for owner in sorted(holders, key=holders.get, reverse=True)[:per_token]:
            seen.setdefault(owner, f"top {name} holder")
    rows = []
    for address, source in seen.items():
        try:
            score = await engine.investigate(address, wallets)
            rows.append((address, source, score.flagged, score.risk))
        except SourceError as error:
            rows.append((address, f"{source} (error: {error})", False, -1.0))
    return rows


async def main(per_token: int) -> None:
    load_env(Path(__file__).resolve().parent.parent / ".env")
    key = os.environ.get("HELIUS_API_KEY")
    if not key:
        raise SystemExit("Set HELIUS_API_KEY in engine/.env first.")
    rpc = HeliusRpc(key)
    dex = DexScreener()
    excluded = load_exclusions()
    tokens = TokenChecker(rpc, dex, excluded=excluded)
    wallets = WalletChecker(rpc, excluded=excluded)
    engine = Engine(MemoryStore(), excluded=excluded)
    try:
        token_rows = await check_tokens(tokens)
        wallet_rows = await check_wallets(rpc, engine, wallets, per_token)
    finally:
        await rpc.close()
        await dex.close()

    print("Well-known tokens (anything above low risk is a false positive)")
    for name, level, score in token_rows:
        mark = "OK " if level == "low" else "!! "
        print(f"  {mark}{name:<5} {level:<8} {score}")
    print("\nTop holders of well-known tokens (flagged is a false positive)")
    for address, source, flagged, risk in wallet_rows:
        print(f"  {'!! ' if flagged else 'OK '}{address}  {source:<18} risk {risk:.2f}")

    token_fp = sum(1 for _, level, _ in token_rows if level not in ("low",) and not level.startswith("error"))
    token_n = sum(1 for _, level, _ in token_rows if not level.startswith("error"))
    wallet_fp = sum(1 for row in wallet_rows if row[2])
    wallet_n = sum(1 for row in wallet_rows if row[3] >= 0)
    print(f"\nTokens: {token_fp}/{token_n} wrongly raised.  Wallets: {wallet_fp}/{wallet_n} wrongly flagged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure how often Ladon wrongly warns on well-known safe tokens and wallets.")
    parser.add_argument("--per-token", type=int, default=4, help="top holders to check per token")
    asyncio.run(main(parser.parse_args().per_token))
