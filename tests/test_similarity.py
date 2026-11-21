import copy

from engine.schema import Feature, Item
from engine.similarity import build_context, combine, compare


def feat(name, value, conf=1.0):
    return Feature(name, name.split(".")[0], value, conf, "test")


def item(id_, **features):
    return Item(
        id=id_,
        case_id=id_,
        paths={},
        features={k.replace("__", "."): feat(k.replace("__", "."), v) for k, v in features.items()},
    )


def test_duplicate_is_linked_with_evidence():
    a = item("a", text__identifiers=["phone:111222333"], text__title=["sekret", "bankier"])
    b = copy.deepcopy(a)
    b.id = "b"
    edge = compare(a, b)
    assert edge.score >= 0.9
    assert edge.evidence[0].feature == "text.identifiers"
    assert "111222333" in edge.evidence[0].note


def test_unrelated_is_weak():
    a = item("a", text__title=["sekret", "bankier"], text__topic=["investment"])
    b = item("b", text__title=["kapsułki", "stawy"], text__topic=["health"])
    edge = compare(a, b)
    assert edge is None or edge.score < 0.3


def test_missing_data_does_not_lower_score():
    shared = ["phone:111222333"]
    a = item("a", text__identifiers=shared)
    b = item("b", text__identifiers=shared)
    full = item(
        "c",
        text__identifiers=shared,
        visual__assets=[{"src": "x.png", "phash": "ffffffff00000000"}],
    )
    assert compare(a, b).score == compare(a, full).score
    missing = [e for e in compare(a, full).evidence if e.weight == 0.0]
    assert missing and missing[0].feature == "visual.assets"
    assert "brak danych" in missing[0].note


def test_common_values_are_ignored_with_context():
    items = [item(str(i), text__entities=["facebook", f"produkt{i}"]) for i in range(8)]
    ctx = build_context(items)
    edge = compare(items[0], items[1], ctx)
    assert edge is None or edge.score == 0.0


def test_unknown_infra_feature_uses_generic_comparator():
    a = item("a", infra__trackers=["ga:UA-1", "px:42"])
    b = item("b", infra__trackers=["px:42"])
    edge = compare(a, b)
    assert edge.score > 0.5
    assert edge.evidence[0].group == "infra"


def test_combine_is_noisy_or():
    assert combine([]) == 0.0
    assert abs(combine([0.5, 0.5]) - 0.75) < 1e-9
