from app.demo_items import demo_items
from engine.cluster import assign, cluster, labels_of
from engine.cluster.pipeline import all_edges, extract_features
from engine.explain import assignment_card, campaign_card, edge_card
from engine.schema import Item
from engine.similarity import build_context


def _campaigns(items, method="components"):
    return cluster(items, all_edges(items), 0.6, method)


def test_demo_campaigns():
    for method in ("components", "average"):
        groups = sorted(sorted(c.item_ids) for c in _campaigns(demo_items(), method))
        assert groups == [["demo/A1", "demo/A2"], ["demo/B1", "demo/B2"], ["demo/C1"]]


def test_assign_known_and_new_pattern():
    items = demo_items()
    known = items[1]
    rest = [i for i in items if i.id != known.id]
    campaigns = _campaigns(rest)
    a = assign(known, campaigns, build_context(items))
    assert a.campaign_id == labels_of(campaigns)["demo/A1"]
    assert a.evidence
    stranger = Item(id="x", case_id="x", paths={}, features={})
    b = assign(stranger, campaigns)
    assert b.campaign_id is None
    assert "nowy wzorzec" in assignment_card(b)["verdict"]


def test_cards_explain_links():
    items = demo_items()
    campaigns = _campaigns(items)
    first = campaigns[0]
    card = campaign_card(first.id, first.items, first.edges)
    assert card["size"] == 2 and card["edges"]
    assert card["edges"][0]["summary"].startswith("połączone, bo:")
    assert edge_card(first.edges[0])["reasons"]


def test_pipeline_on_files(raw, tmp_path):
    from app.sources import discover_items

    items = [extract_features(i, raw, tmp_path / "cache") for i in discover_items(raw)]
    labels = labels_of(cluster(items, all_edges(items), 0.6))
    assert labels["100"] == labels["200/strona_1"]
    assert labels["300"] != labels["100"]
    assert labels["400"] != labels["100"]
    cached = [extract_features(i, raw, tmp_path / "cache") for i in discover_items(raw)]
    assert set(cached[0].features) == set(items[0].features)
