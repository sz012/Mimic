from engine.features.visual import extract
from engine.schema import Item


def test_screenshot_and_assets(raw):
    item = Item(
        id="100",
        case_id="100",
        paths={"html": ["100/strona.html"], "screenshot": ["100/zrzut.png"]},
    )
    feats = extract(item, raw)
    assert feats["visual.screenshot"].available
    assert {"phash", "dhash", "top_phash", "src"} <= set(feats["visual.screenshot"].value[0])
    srcs = [a["src"] for a in feats["visual.assets"].value]
    assert any(s.endswith("foto.png") for s in srcs)
    assert not any(s.endswith("ikona.png") for s in srcs)
    assert feats["visual.exact"].available


def test_missing_visual_is_explicit(raw):
    feats = extract(
        Item(
            id="400",
            case_id="400",
            paths={"meta": ["400/film.info.json"], "video": ["400/film.mp4"]},
        ),
        raw,
    )
    assert not feats["visual.screenshot"].available
    assert not feats["visual.assets"].available
    assert not feats["visual.video"].available
    assert feats["visual.video"].source
