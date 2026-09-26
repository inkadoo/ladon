from ladon.graph import FANOUT_LIMIT, HUB_DEGREE, ScamGraph
from helpers import sol, wallet

SEED, HOP1, HOP2, HOP3, HOP4 = (wallet(n) for n in ["seed", "hop1", "hop2", "hop3", "hop4"])
VICTIM = wallet("victim")
EXCHANGE = wallet("exchange")


def chain() -> ScamGraph:
    graph = ScamGraph()
    graph.add([sol(SEED, HOP1), sol(HOP1, HOP2), sol(HOP2, HOP3), sol(HOP3, HOP4)])
    return graph


def test_risk_fades_with_every_step_and_stops_after_three():
    inherited = chain().propagate({SEED: 0.94})
    assert inherited[HOP1].risk == 0.705
    assert inherited[HOP2].risk == 0.376
    assert inherited[HOP3].risk == 0.141
    assert HOP4 not in inherited
    assert [inherited[w].hops for w in (HOP1, HOP2, HOP3)] == [1, 2, 3]


def test_victims_who_paid_the_scammer_inherit_nothing():
    graph = chain()
    graph.add([sol(VICTIM, SEED, amount=12)])
    assert VICTIM not in graph.propagate({SEED: 0.94})


def test_exchanges_never_inherit_and_block_the_path_through_them():
    graph = ScamGraph(excluded=frozenset({EXCHANGE}))
    graph.add([sol(SEED, EXCHANGE), sol(EXCHANGE, HOP2)])
    inherited = graph.propagate({SEED: 0.94})
    assert EXCHANGE not in inherited
    assert HOP2 not in inherited


def test_dust_does_not_link_wallets():
    graph = ScamGraph()
    graph.add([sol(SEED, HOP1, amount=0.00001)])
    assert graph.propagate({SEED: 0.94}) == {}


def test_broadcasting_wallets_pass_on_no_risk():
    graph = ScamGraph()
    graph.add([sol(SEED, wallet(f"stranger-{i}")) for i in range(FANOUT_LIMIT + 1)])
    assert graph.propagate({SEED: 0.94}) == {}


def test_busy_unlisted_wallets_are_treated_as_infrastructure():
    hub = wallet("hub")
    graph = ScamGraph()
    graph.add([sol(wallet(f"user-{i}"), hub) for i in range(HUB_DEGREE)])
    graph.add([sol(SEED, hub)])
    assert graph.is_infrastructure(hub)
    assert hub not in graph.propagate({SEED: 0.94})


def test_the_strongest_link_wins():
    other_seed = wallet("other-seed")
    graph = chain()
    graph.add([sol(other_seed, HOP2)])
    inherited = graph.propagate({SEED: 0.94, other_seed: 0.94})
    assert inherited[HOP2].source == other_seed
    assert inherited[HOP2].hops == 1


def test_confirmed_wallets_keep_their_own_links():
    other_seed = wallet("other-seed")
    graph = ScamGraph()
    graph.add([sol(SEED, other_seed)])
    inherited = graph.propagate({SEED: 0.94, other_seed: 0.9})
    assert inherited[other_seed].source == SEED
    assert SEED not in inherited
