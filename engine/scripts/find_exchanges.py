import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ladon.exchanges import Profile, Verdict, entry, profile
from ladon.exclusions import DATA_DIR, load_exclusions
from ladon.tokens.sources import HeliusRpc, SourceError

SEED_TOKENS = {
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
}
HISTORY = 1000
EXCHANGES = DATA_DIR / "exchanges.txt"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


async def seeds(rpc: HeliusRpc, per_token: int) -> dict[str, str]:
    found: dict[str, str] = {}
    for name, mint in SEED_TOKENS.items():
        try:
            holders = await rpc.largest_holders(mint)
        except SourceError as error:
            print(f"  could not load top {name} holders: {error}")
            continue
        for owner in sorted(holders, key=holders.get, reverse=True)[:per_token]:
            found.setdefault(owner, f"top {name} holder")
    return found


async def examine(rpc: HeliusRpc, address: str) -> Profile | None:
    try:
        return profile(address, await rpc.history(address, oldest_first=False, limit=HISTORY))
    except SourceError as error:
        print(f"  could not load {address}: {error}")
        return None


def show(p: Profile, source: str) -> None:
    mark = {Verdict.STRONG: "STRONG", Verdict.LIKELY: "likely", Verdict.NO: "no"}[p.verdict]
    print(f"  [{mark:>6}] {p.address}  ({source})")
    print(f"           {p.summary()}")
    if p.verdict is not Verdict.NO:
        print(f"           check: https://solscan.io/account/{p.address}")


def review(candidates: list[tuple[Profile, str]]) -> list[str]:
    added: list[str] = []
    today = date.today().isoformat()
    print("\nReview each candidate on Solscan before adding it. Only add wallets you can confirm belong to an exchange.")
    for p, source in candidates:
        print()
        show(p, source)
        if input("  Add to exchanges.txt? [y/N] ").strip().lower() != "y":
            continue
        label = input("  Label (e.g. 'Binance hot wallet'): ").strip()
        added.append(entry(p.address, label, today))
    return added


async def main(args: argparse.Namespace) -> None:
    load_env(Path(__file__).resolve().parent.parent / ".env")
    key = os.environ.get("HELIUS_API_KEY")
    if not key:
        raise SystemExit("Set HELIUS_API_KEY in engine/.env first.")
    known = load_exclusions()
    rpc = HeliusRpc(key)
    try:
        print("Finding seed wallets…")
        queue = {a: "given" for a in args.address}
        queue.update(await seeds(rpc, args.per_token))
        results: dict[str, tuple[Profile, str]] = {}
        for depth in range(args.hops + 1):
            todo = {a: s for a, s in queue.items() if a not in results and a not in known}
            profiles = await asyncio.gather(*(examine(rpc, a) for a in todo))
            queue = {}
            for (address, source), p in zip(todo.items(), profiles):
                if not p:
                    continue
                results[address] = (p, source)
                if p.verdict is Verdict.STRONG and depth < args.hops:
                    for partner in p.big_partners[: args.expand]:
                        queue.setdefault(partner, f"moves big sums with {address[:4]}…{address[-4:]}")
    finally:
        await rpc.close()

    ranked = sorted(results.values(), key=lambda r: (r[0].verdict is not Verdict.STRONG, r[0].verdict is Verdict.NO, -r[0].per_hour))
    print(f"\nChecked {len(ranked)} wallets ({len(known & set(results))} already listed were skipped):\n")
    for p, source in ranked:
        show(p, source)
    candidates = [r for r in ranked if r[0].verdict is not Verdict.NO]
    print(f"\n{len(candidates)} candidates. Nothing has been added.")
    if args.review and candidates:
        added = review(candidates)
        if added:
            with EXCHANGES.open("a") as out:
                out.writelines(line + "\n" for line in added)
            print(f"\nAdded {len(added)} to {EXCHANGES}. Restart the engine to use them.")
        else:
            print("\nNothing added.")
    elif candidates:
        print("Run again with --review to confirm and add them one by one.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find wallets that behave like exchange hot wallets, for you to confirm and add to data/exchanges.txt.")
    parser.add_argument("--address", action="append", default=[], help="also examine this wallet (repeatable)")
    parser.add_argument("--per-token", type=int, default=4, help="top holders of each seed token to start from")
    parser.add_argument("--hops", type=int, default=1, help="how many steps to follow large transfers from strong candidates")
    parser.add_argument("--expand", type=int, default=5, help="large-transfer partners to follow per strong candidate")
    parser.add_argument("--review", action="store_true", help="confirm candidates one by one and append them to exchanges.txt")
    asyncio.run(main(parser.parse_args()))
