from typing import Any

from ..evidence import detect_sweeps
from ..graph import MIN_LINK
from ..models import Evidence, Transfer
from ..tokens.analysis import created_mints
from ..tokens.trading import creator_sale
from .parse import Pull

RELAY_WINDOW_SECONDS = 60
RELAY_SHARE = 0.9
RELAY_MIN_COUNT = 5
RELAY_WEIGHT = 0.35
DUMP_WEIGHTS = (0.5, 0.75, 0.9)
PULL_WEIGHTS = (0.6, 0.85, 0.95)
LAYERING_WEIGHT = 0.45


def _pick(weights: tuple[float, ...], count: int) -> float:
    return weights[min(count, len(weights)) - 1]


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def relays(address: str, transfers: list[Transfer], excluded: frozenset[str] = frozenset()) -> Evidence | None:
    incoming = sorted((t for t in transfers if t.destination == address and t.amount >= MIN_LINK[t.asset]), key=lambda t: t.timestamp)
    outgoing = sorted((t for t in transfers if t.source == address and t.destination not in excluded), key=lambda t: t.timestamp)
    used: set[int] = set()
    count = 0
    for payment in incoming:
        for i, out in enumerate(outgoing):
            if i in used or out.destination == payment.source:
                continue
            delay = out.timestamp - payment.timestamp
            if 0 <= delay <= RELAY_WINDOW_SECONDS and out.amount >= payment.amount * RELAY_SHARE:
                used.add(i)
                count += 1
                break
    if count < RELAY_MIN_COUNT:
        return None
    return Evidence(
        "relays_funds",
        RELAY_WEIGHT,
        f"Passed money straight through {count} times, sending it on to another wallet within a minute of receiving it.",
    )


def dumped_launches(address: str, txs: list[dict[str, Any]]) -> Evidence | None:
    launches = created_mints(txs, address)
    dumped = [m for m, at in launches.items() if creator_sale(txs, address, m, at).dumped]
    if not dumped:
        return None
    return Evidence(
        "dumped_own_tokens",
        _pick(DUMP_WEIGHTS, len(dumped)),
        f"Sold off its own supply within a day of launch on {len(dumped)} of the {_plural(len(launches), 'token', 'tokens')} it created, the pattern of a rug pull.",
    )


def drained_victims(pulls: list[Pull]) -> Evidence | None:
    victims = {p.victim for p in pulls}
    if not victims:
        return None
    return Evidence(
        "pulled_from_other_wallets",
        _pick(PULL_WEIGHTS, len(victims)),
        f"Moved tokens out of {_plural(len(victims), 'other wallet', 'other wallets')} using spending approvals, the way wallet drainers empty their victims.",
    )


def layering(hops: int, amount: float) -> Evidence | None:
    if hops < 2:
        return None
    return Evidence(
        "layered_through_wallets",
        LAYERING_WEIGHT,
        f"Sent {amount:,.2f} SOL through a chain of {hops} brand-new wallets, each passing it on within minutes, a common way to hide where money goes.",
    )


FLOW_CODES = {"sweeps_incoming", "relays_funds", "layered_through_wallets"}


def own_actions(address: str, txs: list[dict[str, Any]], pulls: list[Pull]) -> list[Evidence]:
    return [e for e in (drained_victims(pulls), dumped_launches(address, txs)) if e is not None]


def money_flow(address: str, transfers: list[Transfer], excluded: frozenset[str]) -> list[Evidence]:
    sweeps = detect_sweeps(address, transfers, excluded)
    return [sweeps] if sweeps else [e for e in (relays(address, transfers, excluded),) if e is not None]
