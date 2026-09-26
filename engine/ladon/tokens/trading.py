from collections import defaultdict
from dataclasses import dataclass
from typing import Any

DUMP_WINDOW_SECONDS = 24 * 3600
DUMP_SHARE = 0.8


def _keys(tx: dict[str, Any]) -> list[dict[str, Any]]:
    keys = ((tx.get("transaction") or {}).get("message") or {}).get("accountKeys") or []
    return [k if isinstance(k, dict) else {"pubkey": k} for k in keys]


def signers(tx: dict[str, Any]) -> set[str]:
    return {k["pubkey"] for k in _keys(tx) if k.get("signer")}


def token_deltas(tx: dict[str, Any], mint: str) -> dict[str, int]:
    meta = tx.get("meta") or {}
    deltas: dict[str, int] = defaultdict(int)
    for sign, field in ((-1, "preTokenBalances"), (1, "postTokenBalances")):
        for balance in meta.get(field) or []:
            if balance.get("mint") == mint and balance.get("owner"):
                deltas[balance["owner"]] += sign * int((balance.get("uiTokenAmount") or {}).get("amount") or 0)
    return {owner: delta for owner, delta in deltas.items() if delta}


def lamport_delta(tx: dict[str, Any], wallet: str) -> int:
    meta = tx.get("meta") or {}
    pre, post = meta.get("preBalances") or [], meta.get("postBalances") or []
    for i, key in enumerate(_keys(tx)):
        if key["pubkey"] == wallet and i < len(pre) and i < len(post):
            return post[i] - pre[i]
    return 0


@dataclass(frozen=True)
class Sale:
    peak: int
    sold: int

    @property
    def share(self) -> float:
        return self.sold / self.peak if self.peak else 0.0

    @property
    def dumped(self) -> bool:
        return self.peak > 0 and self.share >= DUMP_SHARE


def creator_sale(txs: list[dict[str, Any]], wallet: str, mint: str, created_at: int, window: int = DUMP_WINDOW_SECONDS) -> Sale:
    holding = peak = sold = 0
    for tx in sorted(txs, key=lambda t: (t.get("slot") or 0, t.get("transactionIndex") or 0)):
        at = int(tx.get("blockTime") or 0)
        if at < created_at or at > created_at + window:
            continue
        delta = token_deltas(tx, mint).get(wallet, 0)
        if not delta:
            continue
        holding += delta
        peak = max(peak, holding)
        if delta < 0 and lamport_delta(tx, wallet) > 0:
            sold += -delta
    return Sale(peak=peak, sold=min(sold, peak))


@dataclass(frozen=True)
class Bundle:
    wallets: frozenset[str]
    bought: int
    held: int
    supply: int

    @property
    def bought_share(self) -> float:
        return self.bought / self.supply if self.supply else 0.0

    @property
    def held_share(self) -> float:
        return self.held / self.supply if self.supply else 0.0


def launch_bundle(
    mint_txs: list[dict[str, Any]],
    mint: str,
    deployer: str,
    funded_by_deployer: set[str],
    holdings: dict[str, int],
    supply: int,
) -> Bundle:
    bought: dict[str, int] = defaultdict(int)
    for tx in mint_txs:
        signed = signers(tx)
        buys = {o: d for o, d in token_deltas(tx, mint).items() if d > 0 and o in signed and o != deployer}
        together = len(buys) >= 2 or deployer in signed
        for owner, delta in buys.items():
            if together or owner in funded_by_deployer:
                bought[owner] += delta
    wallets = frozenset(bought)
    return Bundle(wallets, sum(bought.values()), sum(holdings.get(w, 0) for w in wallets), supply)
