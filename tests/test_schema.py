import json
from dataclasses import asdict

from engine.schema import Assignment, Edge, Evidence, Feature, Item


def test_missing_feature_is_explicit_not_zero():
    f = Feature.missing("tracker_ids", "infra", "har")
    assert f.available is False
    assert f.value is None
    assert f.confidence == 0.0


def test_item_kinds_skip_empty():
    item = Item(id="61/strona_1", case_id="61", paths={"har": ["a.har"], "html": []})
    assert item.kinds == ["har"]


def test_assignment_new_pattern():
    assert Assignment("x", None, 0.0).is_new_pattern
    assert not Assignment("x", "c1", 0.9).is_new_pattern


def test_edge_roundtrips_to_json():
    ev = Evidence("tracker_ids", "infra", 0.4, 1.0, ["123"], ["123"], "ten sam piksel")
    edge = Edge("1", "2", 0.8, [ev])
    assert json.loads(json.dumps(asdict(edge)))["evidence"][0]["feature"] == "tracker_ids"
