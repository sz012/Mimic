import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import RateLimiter, create_app
from app.demo_items import demo_items
from engine.cluster import Workspace
from engine.schema import Feature, Item
from engine.similarity.weights import DEFAULT


def client(tmp_path):
    app = create_app(Workspace(demo_items(), tmp_path))
    app.state.upload_dir = tmp_path / "uploads"
    return TestClient(app)


def test_state_settings_and_items(tmp_path):
    api = client(tmp_path)
    state = api.get("/api/state").json()
    assert state["is_demo"] and state["stats"]["items"] == 5
    assert (
        api.post("/api/settings", json={"threshold": 0.8, "method": "average"}).json()["threshold"]
        == 0.8
    )
    assert api.post("/api/settings", json={"method": "bad"}).status_code == 422
    items = api.get("/api/items").json()
    assert len(items) == 5 and items[0]["available_features"] > 0
    assert api.get("/api/items/demo/A1").json()["features"]
    assert api.get("/api/items/unknown").status_code == 404


def test_campaigns_graph_compare_and_criteria(tmp_path):
    api = client(tmp_path)
    campaigns = api.get("/api/campaigns").json()
    assert campaigns and api.get(f"/api/campaigns/{campaigns[0]['id']}").json()["formula"]
    assert len(api.get("/api/graph").json()["nodes"]) == 5
    comparison = api.post("/api/compare", json={"a": "demo/A1", "b": "demo/A2"}).json()
    assert comparison["score"] > 0 and comparison["card"]["counterfactual"]
    criteria = api.get("/api/criteria").json()
    assert len(criteria["criteria"]) == 6 and len(criteria["membership"]) == 5


def test_analyze_add_and_media_safety(tmp_path):
    api = client(tmp_path)
    response = api.post(
        "/api/analyze",
        files={
            "files": (
                "sample.html",
                b"<html><title>syntetyczny przyklad</title></html>",
                "text/html",
            )
        },
    )
    assert response.status_code == 200
    upload_id = response.json()["item"]["id"]
    added = api.post("/api/items", json={"upload_id": upload_id})
    assert added.status_code == 200 and added.json()["state"]["stats"]["items"] == 6
    assert api.get("/api/media", params={"path": "../../etc/passwd"}).status_code == 404
    assert api.get("/api/media", params={"path": "sample.html"}).status_code == 404


def test_exports_and_adlib_without_token(tmp_path, monkeypatch):
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    api = client(tmp_path)
    assert api.get("/api/export/json").status_code == 200
    assert api.get("/api/export/csv").status_code == 200
    assert api.get("/api/export/html").status_code == 200
    result = api.post("/api/adlib/search", json={"terms": "syntetyczne"}).json()
    assert result["results"] == [] and result["notice"]


def test_face_vectors_are_not_sent_to_browser(tmp_path):
    items = demo_items()
    items[0].features["person.faces"] = Feature(
        "person.faces",
        "person",
        [{"name": "Osoba Publiczna 1", "score": 0.8, "embedding": [0.1] * 128}],
        0.8,
        "syntetyczne",
    )
    items[0].features["person.face_vectors"] = Feature(
        "person.face_vectors", "person", [[0.1] * 128], 0.8, "syntetyczne"
    )
    api = TestClient(create_app(Workspace(items, tmp_path)))
    response = api.get("/api/items/demo/A1")
    assert response.status_code == 200
    assert "embedding" not in response.text
    faces = next(row for row in response.json()["features"] if row["name"] == "person.faces")
    assert faces["value"] == [{"name": "Osoba Publiczna 1", "score": 0.8}]
    vectors = next(
        row for row in response.json()["features"] if row["name"] == "person.face_vectors"
    )
    assert vectors["value"] == {"count": 1}


def test_uploaded_image_is_served_as_source_material(tmp_path):
    api = client(tmp_path)
    image = Image.new("RGB", (16, 16), "#5546ff")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    response = api.post(
        "/api/analyze", files={"files": ("synthetic.png", buffer.getvalue(), "image/png")}
    )
    assert response.status_code == 200
    media = response.json()["item"]["media"]
    assert len(media) == 1
    preview = api.get("/api/media", params={"path": media[0]})
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["x-content-type-options"] == "nosniff"


def test_face_comparison_uses_vectors_only_on_server(tmp_path):
    if "person.face_vectors" not in DEFAULT.features:
        pytest.skip("Porównywanie twarzy zostanie dołączone z silnikiem")
    vector = [1.0] + [0.0] * 127
    items = [
        Item(
            "synthetic/A",
            "A",
            features={
                "person.face_vectors": Feature(
                    "person.face_vectors", "person", [vector], 0.8, "syntetyczne"
                )
            },
        ),
        Item(
            "synthetic/B",
            "B",
            features={
                "person.face_vectors": Feature(
                    "person.face_vectors", "person", [vector], 0.8, "syntetyczne"
                )
            },
        ),
    ]
    api = TestClient(create_app(Workspace(items, tmp_path)))
    response = api.post("/api/compare", json={"a": "synthetic/A", "b": "synthetic/B"})
    assert response.status_code == 200
    evidence = next(
        row for row in response.json()["evidence"] if row["feature"] == "person.face_vectors"
    )
    assert evidence["score"] > 0
    assert evidence["left"] == "1 twarzy"
    assert len(response.text) < 10000


def test_rate_limiter_is_per_client_and_action():
    limiter = RateLimiter()
    assert limiter.allow("one", "analyze", 1, 60)
    assert not limiter.allow("one", "analyze", 1, 60)
    assert limiter.allow("two", "analyze", 1, 60)
    assert limiter.allow("one", "criteria", 1, 60)


def test_analyze_existing_material_excludes_itself(tmp_path):
    api = client(tmp_path)
    known = api.post("/api/analyze", data={"existing_id": "demo/A2"}).json()
    assert known["existing"] is True and known["assignment"]["campaign_id"]
    assert all(row["item"] != "demo/A2" for row in known["similar"])
    assert api.post("/api/analyze", data={"existing_id": "brak"}).status_code == 404
    state = api.get("/api/state").json()
    assert state["adlib_enabled"] is False


def test_adlib_fixture_mode_returns_analysed_ads(tmp_path, monkeypatch):
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    monkeypatch.setenv("MIMIC_ADLIB_FIXTURE", "1")
    api = client(tmp_path)
    state = api.get("/api/state").json()
    assert state["adlib_enabled"] is True and state["adlib_mode"] == "fixture"
    found = api.post(
        "/api/adlib/search", json={"terms": "inwestycje", "countries": ["PL"], "max_pages": 1}
    ).json()
    assert found["results"] and found["results"][0]["card"]["verdict"]


def test_dataset_export_has_features_without_face_vectors(tmp_path):
    api = client(tmp_path)
    rows = api.get("/api/export/dataset-json").json()
    assert rows and {"material", "kampania", "cecha", "dostepna", "wartosc"} <= set(rows[0])
    assert all(row["cecha"] != "person.face_vectors" for row in rows)
    csv_text = api.get("/api/export/dataset-csv").text
    assert csv_text.splitlines()[0].startswith("material,przypadek,kampania")


def test_analysis_lists_extracted_features(tmp_path):
    api = client(tmp_path)
    result = api.post("/api/analyze", data={"existing_id": "demo/A1"}).json()
    assert result["features"] and {"name", "group", "available", "confidence", "source"} <= set(
        result["features"][0]
    )
