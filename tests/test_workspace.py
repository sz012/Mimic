import copy
import io
import json
import zipfile

from app.demo_items import demo_items
from app.sources import discover_items, ingest_upload
from engine.cluster import Workspace
from engine.explain.report import to_csv, to_html, to_json
from engine.schema import Item


def _ws(tmp_path):
    return Workspace(demo_items(), tmp_path)


def test_workspace_builds_campaigns(tmp_path):
    ws = _ws(tmp_path)
    assert ws.stats() == {"insufficient": 0, "items": 5, "campaigns": 2, "singletons": 1}
    card = ws.card(ws.label["demo/A1"])
    assert card["links"] and card["links"][0]["edges"] >= 1
    assert card["formula"]


def test_analyze_known_item_and_new_pattern(tmp_path):
    ws = _ws(tmp_path)
    a = ws.analyze(ws.by_id["demo/A2"])
    assert a.assignment.campaign_id == ws.label["demo/A1"]
    assert a.similar[0]["item"] == "demo/A1"
    assert a.similar[0]["card"]["reasons"]
    stranger = Item(id="x", case_id="x", paths={}, features={})
    b = ws.analyze(stranger)
    assert b.is_new_pattern and not b.similar


def test_add_reclusters(tmp_path):
    ws = _ws(tmp_path)
    twin = copy.deepcopy(ws.by_id["demo/C1"])
    twin.id = "demo/C2"
    assignment = ws.add(twin)
    assert assignment.campaign_id == ws.label["demo/C1"]
    assert ws.label["demo/C2"] == ws.label["demo/C1"]
    assert ws.stats()["campaigns"] == 3


def test_recluster_threshold(tmp_path):
    ws = _ws(tmp_path)
    ws.recluster(0.99)
    assert ws.stats()["campaigns"] <= 2
    assert ws.threshold == 0.99


def test_exports(tmp_path):
    ws = _ws(tmp_path)
    cards = ws.campaign_cards()
    data = json.loads(to_json(cards, ws.stats()))
    assert len(data["campaigns"]) == 2
    assert to_csv(cards).splitlines()[0].startswith("kampania,")
    html = to_html(cards, ws.stats())
    assert "<script" not in html and "Kampania" in html


def test_graph_payload(tmp_path):
    ws = _ws(tmp_path)
    g = ws.graph(0.1)
    assert {n["id"] for n in g["nodes"]} == set(ws.by_id)
    assert all(link["card"]["summary"] for link in g["links"])


def test_upload_from_files_and_zip(raw, tmp_path):
    ws = Workspace.load(discover_items(raw), raw, tmp_path / "cache")
    html = (raw / "100" / "strona.html").read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../ucieczka.html", "<p>x</p>")
        zf.writestr("kopia/strona.html", html)
    item = ingest_upload(
        [("paczka.zip", buf.getvalue())], "https://przyklad.test/a", tmp_path / "up"
    )
    assert item.id.startswith("upload/") and item.case_id == "upload"
    assert not (tmp_path / "ucieczka.html").exists()
    assert "url" in item.kinds
    a = ws.analyze(item, tmp_path / "up")
    assert a.assignment.campaign_id == ws.label["100"]


def test_store_keeps_uploads_and_assignments_across_restart(raw, tmp_path):
    from engine.store import Store

    store = Store(tmp_path / "m.sqlite")
    ws = Workspace.load(discover_items(raw), raw, tmp_path / "cache", store=store)
    assert {i.id for i in store.items()} == set(ws.by_id)
    assert store.campaigns()
    html = (raw / "100" / "strona.html").read_bytes()
    item = ingest_upload([("kopia.html", html)], None, tmp_path / "up")
    assignment = ws.add(item, tmp_path / "up")
    assert assignment.campaign_id == ws.label["100"]
    again = Workspace.load(
        discover_items(raw), raw, tmp_path / "cache", store=Store(tmp_path / "m.sqlite")
    )
    assert item.id in again.by_id
    assert again.label[item.id] == again.label["100"]
    assert [a.item_id for a in again.history()] == [item.id]


class FakeAds:
    def __init__(self, ads):
        self.ads = ads

    def get(self, url, headers=None):
        return {"data": self.ads}


def test_search_ads_analyzes_and_adds(raw, tmp_path):
    ws = Workspace.load(discover_items(raw), raw, tmp_path / "cache")
    ads = [
        {
            "id": "11111111",
            "ad_creative_bodies": ["Kapsułki na stawy naturalny lekarz poleca kurację"],
            "page_name": "Strona A",
        },
        {
            "id": "22222222",
            "ad_creative_bodies": ["Kapsułki na stawy naturalny lekarz poleca kurację"],
            "page_name": "Strona B",
        },
    ]
    results, error = ws.search_ads(
        "stawy", ["PL"], tmp_path / "adlib", transport=FakeAds(ads), access_token="T"
    )
    assert error is None and [i.id for i, _ in results] == ["adlib/11111111", "adlib/22222222"]
    for item, _ in results:
        ws.add(item, tmp_path / "adlib")
    assert ws.label["adlib/11111111"] == ws.label["adlib/22222222"] != ws.label["100"]


def test_search_ads_without_token(raw, tmp_path, monkeypatch):
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    ws = Workspace.load(discover_items(raw), raw, tmp_path / "cache")
    results, error = ws.search_ads("x", ["PL"], tmp_path / "adlib")
    assert results == [] and "META_AD_LIBRARY_TOKEN" in error


def test_graph_shows_case_links(raw, tmp_path):
    from engine.schema import Feature, Item

    ad = Item(
        "200",
        "200",
        {"screenshot": ["200/ad.png"]},
        {"text.topic": Feature("text.topic", "text", ["news"], 0.5, "t")},
    )
    ws = Workspace.load([*discover_items(raw), ad], raw, tmp_path / "cache")
    case = [link for link in ws.graph(0.1)["links"] if link.get("case")]
    assert {frozenset((link["a"], link["b"])) for link in case} == {
        frozenset(("200", "200/strona_1"))
    }
    assert ws.label["200"] == ws.label["200/strona_1"]
