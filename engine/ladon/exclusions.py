"""Shared infrastructure that must never inherit risk through the graph.

A scammer cashing out through an exchange, swapping on a DEX or bridging away must not make that
exchange, DEX or bridge look like a scammer. Excluded addresses are neither scored through the graph
nor used as a path to reach other wallets.

Programs are listed here by their published program IDs. Exchange hot and deposit wallets are added
from `data/exchanges.txt` (one address per line) so the list can grow without code changes; wallets
the engine sees trading with an unusually large number of counterparties are also treated as
infrastructure (see graph.HUB_DEGREE).
"""

from pathlib import Path

from .addresses import is_valid_address

PROGRAMS = {
    "11111111111111111111111111111111",  # System Program
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL Token
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # SPL Token-2022
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # Associated Token Account
    "ComputeBudget111111111111111111111111111111",  # Compute Budget
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",  # Memo
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter aggregator v6
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM v4
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpools
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # Pump.fun
    "worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth",  # Wormhole core bridge
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_exclusions(data_dir: Path = DATA_DIR) -> frozenset[str]:
    addresses = set(PROGRAMS)
    exchanges = data_dir / "exchanges.txt"
    if exchanges.exists():
        for line in exchanges.read_text().splitlines():
            entry = line.split("#", 1)[0].strip()
            if entry and is_valid_address(entry):
                addresses.add(entry)
    return frozenset(addresses)
