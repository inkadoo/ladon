"""Onchain evidence about a single wallet, taken from its own transfers.

Only evidence can raise a score. Reports are handled separately in scoring and are never evidence.
"""

from collections.abc import Iterable

from .models import Evidence, Transfer

# A sweeper bot moves each payment out almost as soon as it lands. Real people rarely do this, and
# never for payments from many different senders.
SWEEP_WINDOW_SECONDS = 10
SWEEP_MIN_SHARE = 0.9
SWEEP_MIN_COUNT = 3
SWEEP_MIN_SENDERS = 3


def detect_sweeps(address: str, transfers: Iterable[Transfer], excluded: frozenset[str] = frozenset()) -> Evidence | None:
    incoming = sorted((t for t in transfers if t.destination == address and t.source not in excluded), key=lambda t: t.timestamp)
    # Forwarding to an exchange is what exchange deposit addresses do all day, so it is not a sweep.
    outgoing = sorted(
        (t for t in transfers if t.source == address and t.destination not in excluded),
        key=lambda t: t.timestamp,
    )
    used: set[int] = set()
    swept = 0
    senders: set[str] = set()
    for payment in incoming:
        for i, out in enumerate(outgoing):
            if i in used or out.asset != payment.asset:
                continue
            delay = out.timestamp - payment.timestamp
            if 0 <= delay <= SWEEP_WINDOW_SECONDS and out.amount >= payment.amount * SWEEP_MIN_SHARE:
                used.add(i)
                swept += 1
                senders.add(payment.source)
                break
    if swept < SWEEP_MIN_COUNT or len(senders) < SWEEP_MIN_SENDERS:
        return None
    return Evidence(
        code="sweeps_incoming",
        weight=min(0.55, 0.3 + 0.025 * swept),
        text=f"Moved {swept} incoming payments straight back out, each within {SWEEP_WINDOW_SECONDS} seconds of arriving.",
    )


def detect(address: str, transfers: Iterable[Transfer], excluded: frozenset[str] = frozenset()) -> list[Evidence]:
    transfers = list(transfers)
    found = [detect_sweeps(address, transfers, excluded)]
    return [e for e in found if e is not None]
