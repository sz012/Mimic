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
