import importlib.util
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from engine.features import media, ocr, person, text, visual
from engine.schema import Item

HAS_CV2 = importlib.util.find_spec("cv2") is not None
HAS_OCR = importlib.util.find_spec("rapidocr_onnxruntime") is not None


def _write_video(path: Path) -> None:
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5, (320, 240))
    for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        for _ in range(10):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            frame[:] = color
            cv2.rectangle(frame, (40, 40), (200, 160), (255, 255, 255), -1)
            cv2.circle(frame, (250, 180), 30 + color[0] // 20, (0, 0, 0), -1)
            writer.write(frame)
    writer.release()


def _text_image(path: Path, words: str) -> None:
    img = Image.new("RGB", (900, 200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("Arial.ttf", 48)
    except OSError:
        font = ImageFont.load_default(size=48)
    draw.text((20, 60), words, fill="black", font=font)
    img.save(path)


def test_missing_optional_dependencies_give_explicit_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "opencv_available", lambda: False)
    monkeypatch.setattr(ocr, "available", lambda: False)
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "film.mp4").write_bytes(b"\x00" * 64)
    Image.new("RGB", (200, 200), "white").save(tmp_path / "c" / "shot.png")
    item = Item("c", "c", {"video": ["c/film.mp4"], "screenshot": ["c/shot.png"]})
    feats = {**visual.extract(item, tmp_path), **text.extract(item, tmp_path)}
    assert not feats["visual.video"].available and "opencv" in feats["visual.video"].source
    assert not feats["text.ocr"].available and "ocr" in feats["text.ocr"].source
    assert not person.extract(item, tmp_path)["person.faces"].available


@pytest.mark.skipif(not HAS_CV2, reason="brak opencv")
def test_key_frames_from_synthetic_video(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_CACHE_DIR", str(tmp_path / "cache"))
    (tmp_path / "c").mkdir()
    _write_video(tmp_path / "c" / "film.mp4")
    item = Item("c", "c", {"video": ["c/film.mp4"]})
    frames = media.item_frames(item, tmp_path)
    assert 2 <= len(frames) <= media.MAX_FRAMES
    assert all(Path(f.path).exists() for f in frames)
    again = media.item_frames(item, tmp_path)
    assert [f.phash for f in again] == [f.phash for f in frames]
    feat = visual.extract(item, tmp_path)["visual.video"]
    assert feat.available and feat.value[0]["src"].startswith("c/film.mp4@")


@pytest.mark.skipif(not HAS_OCR, reason="brak rapidocr")
def test_ocr_text_feeds_narrative_for_image_only_item(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_CACHE_DIR", str(tmp_path / "cache"))
    (tmp_path / "ad").mkdir()
    _text_image(tmp_path / "ad" / "reklama.png", "Inwestuj teraz platforma zysk codziennie")
    item = Item("ad", "ad", {"screenshot": ["ad/reklama.png"]})
    feats = text.extract(item, tmp_path)
    assert feats["text.title"].available is False
    docs = text.load_docs(item, tmp_path)
    assert docs and docs[0].source.startswith("ocr:")
    assert "platforma" in text.tokens(docs[0].full)


def test_tokens_fold_diacritics():
    assert text.tokens("Pieniądze łatwo zarobić") == ["pieniadze", "latwo", "zarobic"]


def test_person_refs_file_is_used():
    names = {p["name"] for p in person.reference_persons()}
    assert len(names) >= 10
    assert person.REFS_FILE.exists()
