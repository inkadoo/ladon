"""The scam graph: which wallets sent money to which, and how risk spreads from confirmed scams.

Risk only flows downstream, along money a confirmed scam wallet sent out: to the wallets it controls,
the wallets it cashes out through, and the fresh wallets it funds to launch new tokens. It never flows
back to the wallets that paid it, because those are mostly its victims.
"""

from collections.abc import Iterable

import networkx as nx

from .models import Asset, Inheritance, Transfer

# Share of a confirmed wallet's risk passed on at 1, 2 and 3 steps away. Nothing beyond 3 steps.
HOP_DECAY = (0.75, 0.4, 0.15)
# Dust is ignored so a scammer cannot tie strangers to themselves by spraying tiny amounts at them.
MIN_LINK = {Asset.SOL: 0.05, Asset.USDC: 5.0, Asset.USDT: 5.0}
# A wallet paying this many others is broadcasting (airdrops, dust spam, payroll); its payments pass on no risk.
FANOUT_LIMIT = 50
# A wallet dealing with this many counterparties is infrastructure we have not listed yet, not a person.
HUB_DEGREE = 1000


class ScamGraph:
    def __init__(self, excluded: frozenset[str] = frozenset()):
        self.graph = nx.DiGraph()
        self.excluded = excluded

    def add(self, transfers: Iterable[Transfer]) -> None:
        for t in transfers:
            if t.amount < MIN_LINK[t.asset]:
                continue
            if self.graph.has_edge(t.source, t.destination):
                self.graph[t.source][t.destination]["count"] += 1
            else:
                self.graph.add_edge(t.source, t.destination, count=1)

    def is_infrastructure(self, address: str) -> bool:
        if address in self.excluded:
            return True
        if address not in self.graph:
            return False
        counterparties = set(self.graph.predecessors(address)) | set(self.graph.successors(address))
        return len(counterparties) >= HUB_DEGREE

    def propagate(self, seeds: dict[str, float]) -> dict[str, Inheritance]:
        """Risk each wallet inherits from its nearest, strongest confirmed scam wallet."""
        best: dict[str, Inheritance] = {}
        for seed, risk in seeds.items():
            if seed not in self.graph or self.is_infrastructure(seed):
                continue
            frontier = [seed]
            seen = {seed}
            for hop, decay in enumerate(HOP_DECAY, start=1):
                next_frontier = []
                for node in frontier:
                    recipients = list(self.graph.successors(node))
                    if len(recipients) > FANOUT_LIMIT:
                        continue
                    for wallet in recipients:
                        if wallet in seen or self.is_infrastructure(wallet):
                            continue
                        seen.add(wallet)
                        next_frontier.append(wallet)
                        inherited = round(risk * decay, 4)
                        # Confirmed wallets record their links too, or their own score would drop once
                        # they start passing risk on, and they would flip in and out of being confirmed.
                        if wallet not in best or best[wallet].risk < inherited:
                            best[wallet] = Inheritance(source=seed, hops=hop, risk=inherited)
                frontier = next_frontier
        return best

    def recipients(self, address: str) -> list[str]:
        """Wallets this one paid, most frequent first, leaving out infrastructure."""
        if address not in self.graph:
            return []
        edges = sorted(self.graph.out_edges(address, data="count"), key=lambda e: e[2], reverse=True)
        return [dst for _, dst, _ in edges if not self.is_infrastructure(dst)]
