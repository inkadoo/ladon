import argparse
import csv
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ladon.addresses import is_valid_address
from ladon.exclusions import DATA_DIR

OUTPUT = DATA_DIR / "exchanges_okx.txt"
PROOF_PAGE = "https://www.okx.com/proof-of-reserves/download"


def solana_addresses(rows: list[list[str]]) -> set[str]:
    header_at = next((i for i, row in enumerate(rows) if row[:3] == ["coin", "Type", "Network"]), None)
    if header_at is None:
        raise SystemExit("This does not look like an OKX proof of reserves file.")
    header = rows[header_at]
    network, address, message = header.index("Network"), header.index("address"), header.index("message")
    found = set()
    for row in rows[header_at + 1:]:
        if len(row) > max(network, address, message) and row[network] == "SOL" and row[message] == "I am an OKX address":
            if is_valid_address(row[address].strip()):
                found.add(row[address].strip())
    return found


def read_rows(source: str) -> list[list[str]]:
    data = httpx.get(source, timeout=120).content if source.startswith("https://") else Path(source).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".csv"))
        return list(csv.reader(io.TextIOWrapper(archive.open(name), encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import OKX's Solana wallets from its signed proof of reserves file.")
    parser.add_argument("source", help=f"URL or path of the reserves .zip, from {PROOF_PAGE}")
    source = parser.parse_args().source
    addresses = sorted(solana_addresses(read_rows(source)))
    lines = [
        "# OKX's Solana wallets, from OKX's own signed proof of reserves file.",
        f"# Source: {source}",
        f"# Imported {date.today().isoformat()} with scripts/import_okx_reserves.py. {len(addresses)} addresses.",
        "# Each one is marked 'I am an OKX address' and signed by OKX. Most are customer deposit addresses.",
        "",
        *addresses,
    ]
    OUTPUT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(addresses)} OKX Solana addresses to {OUTPUT}")


if __name__ == "__main__":
    main()
