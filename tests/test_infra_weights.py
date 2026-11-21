from engine.schema import Edge, Evidence, Feature, Item
from engine.similarity import Weights, compare
from engine.similarity.comparators import date_proximity
from engine.similarity.rules import link_basis
from engine.similarity.weights import FEATURES


def ev(feature, contribution):
    return Evidence(
        feature, feature.split(".")[0], 1.0, contribution, None, None, f"{feature}: test"
    )


def item(id_, **features):
    return Item(
        id=id_,
        case_id=id_,
        paths={},
        features={
            k.replace("__", "."): Feature(k.replace("__", "."), k.split("__")[0], v, 0.9, "test")
            for k, v in features.items()
        },
    )


def test_catalog_weights_present():
    for name in (
        "infra.tracker_ids",
        "infra.domain",
        "infra.favicon",
        "infra.created",
        "template.dom_simhash",
    ):
        assert name in FEATURES


def test_kit_overlap_alone_does_not_link():
    e = Edge("a", "b", 0.95, [ev("infra.favicon", 0.7), ev("infra.endpoints", 0.65)])
    basis = link_basis(e)
    assert not basis.ok
    assert basis.kit == ("infra.endpoints", "infra.favicon")
    assert "zestaw" in basis.reason
    assert link_basis(e, kit_as_campaign=True).ok


def test_kit_is_reported_next_to_real_evidence():
    e = Edge("a", "b", 0.95, [ev("infra.tracker_ids", 0.9), ev("infra.favicon", 0.7)])
    basis = link_basis(e)
    assert basis.ok and "zestaw" in basis.reason


def test_shared_tracker_links_through_compare():
    a = item("a", infra__tracker_ids=["fbpixel:123"], infra__favicon=["f1"])
    b = item("b", infra__tracker_ids=["fbpixel:123"], infra__favicon=["f1"])
    edge = compare(a, b)
    assert link_basis(edge).hard == ("infra.tracker_ids",)


def test_single_shared_html_comment_is_not_strong():
    a = item("a", template__html_comments=["c1", "c2", "c3", "c4"])
    b = item("b", template__html_comments=["c1", "c5", "c6"])
    edge = compare(a, b, None, Weights())
    assert not link_basis(edge).ok


def test_date_proximity():
    assert date_proximity("infra.created", "2026-01-01", "2026-01-03", None).score == 1.0
    assert date_proximity("infra.created", ["2026-01-01"], ["2026-03-01"], None).score == 0.0
    assert 0 < date_proximity("infra.created", "2026-01-01", "2026-01-15", None).score < 1
    assert date_proximity("infra.created", "?", "2026-01-15", None).score == 0.0
