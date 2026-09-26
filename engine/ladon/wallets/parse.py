from dataclasses import dataclass
from typing import Any

from ..models import Asset, Transfer
from ..tokens.analysis import SYSTEM_PROGRAM, instructions

LAMPORTS_PER_SOL = 1_000_000_000
TOKEN_PROGRAMS = {"spl-token", "spl-token-2022"}


def signature_of(tx: dict[str, Any]) -> str:
    signatures = (tx.get("transaction") or {}).get("signatures") or []
    return signatures[0] if signatures else ""


def _parsed(ins: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    parsed = ins.get("parsed")
    if not isinstance(parsed, dict):
        return None, {}
    return parsed.get("type"), parsed.get("info") or {}


def sol_transfers(txs: list[dict[str, Any]]) -> list[Transfer]:
    transfers: list[Transfer] = []
    for tx in txs:
        at = int(tx.get("blockTime") or 0)
        signature = signature_of(tx)
        for ins in instructions(tx):
            if ins.get("programId") != SYSTEM_PROGRAM:
                continue
            kind, info = _parsed(ins)
            source, destination, lamports = info.get("source"), info.get("destination"), int(info.get("lamports") or 0)
            if kind == "transfer" and source and destination and source != destination and lamports > 0:
                transfers.append(Transfer(source, destination, lamports / LAMPORTS_PER_SOL, Asset.SOL, at, signature))
    return transfers


@dataclass(frozen=True)
class Pull:
    victim: str
    mint: str
    signature: str
    timestamp: int


def delegated_pulls(txs: list[dict[str, Any]], wallet: str) -> list[Pull]:
    pulls: list[Pull] = []
    for tx in txs:
        keys = [k.get("pubkey") if isinstance(k, dict) else k for k in ((tx.get("transaction") or {}).get("message") or {}).get("accountKeys") or []]
        owners: dict[int, tuple[str, str]] = {}
        for field in ("preTokenBalances", "postTokenBalances"):
            for balance in (tx.get("meta") or {}).get(field) or []:
                if balance.get("owner") is not None and balance.get("accountIndex") is not None:
                    owners[int(balance["accountIndex"])] = (balance["owner"], balance.get("mint") or "")
        for ins in instructions(tx):
            if ins.get("program") not in TOKEN_PROGRAMS:
                continue
            kind, info = _parsed(ins)
            if kind not in ("transfer", "transferChecked") or info.get("authority") != wallet or info.get("source") not in keys:
                continue
            owner, mint = owners.get(keys.index(info["source"]), (None, ""))
            if owner and owner != wallet:
                pulls.append(Pull(owner, info.get("mint") or mint, signature_of(tx), int(tx.get("blockTime") or 0)))
    return pulls
