import numpy as np
import pytest
from PIL import Image

from engine.features import faces, person
from engine.schema import Item

COLORS = {"red": (255, 0, 0), "blue": (0, 0, 255)}


def _photo(path, color):
    rng = np.random.default_rng(7)
    arr = rng.integers(0, 255, (200, 200, 3), dtype=np.uint8)
    arr[:20, :20] = COLORS[color]
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)


def _fake_embedder(img):
    r, g, b = img.getpixel((0, 0))
    vec = np.array([r, g, b], dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    return [(vec / norm, 0.99)] if norm else []


@pytest.fixture
def env(tmp_path, monkeypatch):
    refs = tmp_path / "refs"
    monkeypatch.setenv("MIMIC_FACE_REFS", str(refs))
    monkeypatch.setenv("MIMIC_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(faces, "_galleries", {})
    monkeypatch.setattr(faces, "_embedder", (_fake_embedder, ""))
    return tmp_path


def _item(tmp_path, color):
    rel = f"case/{color}.png"
    _photo(tmp_path / "raw" / rel, color)
    return Item(id="case", case_id="case", paths={"screenshot": [rel]})


def test_missing_without_insightface(env, monkeypatch):
    monkeypatch.setattr(faces, "_embedder", (None, faces.INSTALL_HINT))
    feat = faces.extract(_item(env, "red"), env / "raw")["person.faces"]
    assert not feat.available and "insightface" in feat.source


def test_missing_without_reference_images(env):
    feat = faces.extract(_item(env, "red"), env / "raw")["person.faces"]
    assert not feat.available and "referencyjnych" in feat.source


def test_matches_reference_person(env):
    _photo(env / "refs" / "Jan Test" / "a.png", "red")
    _photo(env / "refs" / "Anna Test" / "a.png", "blue")
    feat = faces.extract(_item(env, "red"), env / "raw")["person.faces"]
    assert feat.available and feat.value == ["Jan Test"]
    assert feat.confidence >= 0.99


def test_unknown_face_is_explicit_missing(env):
    _photo(env / "refs" / "Jan Test" / "a.png", "red")
    feat = faces.extract(_item(env, "blue"), env / "raw")["person.faces"]
    assert not feat.available and "brak dopasowania" in feat.source


def test_gallery_cache_and_signature_change(env):
    before = faces.state()
    _photo(env / "refs" / "Jan Test" / "a.png", "red")
    assert faces.state() != before
    faces.extract(_item(env, "red"), env / "raw")
    assert list((env / "cache" / "faces").glob("gallery-*.json"))


def test_person_version_tracks_faces_state(env):
    before = person.VERSION
    _photo(env / "refs" / "Jan Test" / "a.png", "red")
    assert person.VERSION != before and person.VERSION.startswith("3.")


def test_face_vectors_feature_and_comparison(env):
    from engine.similarity import compare

    a = _item(env, "red")
    b = _item(env, "red")
    b.id = "other"
    c = _item(env, "blue")
    c.id = "third"
    raw = env / "raw"
    for it in (a, b, c):
        it.features.update(faces.extract(it, raw))
    assert a.features["person.face_vectors"].available
    assert not a.features["person.faces"].available
    edge = compare(a, b)
    ev = next(e for e in edge.evidence if e.feature == "person.face_vectors")
    assert ev.score >= 0.99 and "ta sama twarz" in ev.note
    assert compare(a, c) is None or all(
        e.score == 0 for e in compare(a, c).evidence if e.feature == "person.face_vectors"
    )


def test_face_vectors_alone_never_link(env):
    from engine.similarity import compare
    from engine.similarity.rules import link_basis

    a = _item(env, "red")
    b = _item(env, "red")
    b.id = "other"
    for it in (a, b):
        it.features.update(faces.extract(it, env / "raw"))
    assert not link_basis(compare(a, b)).ok


def test_face_vectors_missing_without_images(env):
    item = Item(id="x", case_id="x", paths={})
    feats = faces.extract(item, env / "raw")
    assert not feats["person.face_vectors"].available
