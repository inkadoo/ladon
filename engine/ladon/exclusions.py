from pathlib import Path

from .addresses import is_valid_address

PROGRAMS = {
    "11111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "ComputeBudget111111111111111111111111111111",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    "worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth",
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
