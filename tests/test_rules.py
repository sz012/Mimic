from engine.schema import Edge, Evidence
from engine.similarity.rules import is_link, link_basis


def ev(feature, contribution):
    return Evidence(
        feature, feature.split(".")[0], 1.0, contribution, None, None, f"{feature}: test"
    )


def edge(*evidence, score=0.9):
    return Edge("a", "b", score, list(evidence))


def test_hard_evidence_links_alone():
    basis = link_basis(edge(ev("text.identifiers", 0.9)))
    assert basis.ok and basis.hard == ("text.identifiers",)


def test_two_independent_groups_link():
    assert link_basis(edge(ev("text.narrative", 0.4), ev("visual.assets", 0.3))).ok


def test_person_and_weak_features_are_not_independent():
    e = edge(
        ev("person.names", 0.45),
        ev("text.topic", 0.1),
        ev("text.keywords", 0.3),
        ev("text.title", 0.3),
    )
    basis = link_basis(e)
    assert not basis.ok
    assert basis.groups == ("text",)


def test_very_strong_single_group_links():
    assert link_basis(edge(ev("text.narrative", 0.7))).ok
    assert not link_basis(edge(ev("text.narrative", 0.4))).ok


def test_threshold_still_applies():
    assert not is_link(edge(ev("text.identifiers", 0.9), score=0.5), 0.6)
