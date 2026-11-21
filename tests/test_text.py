from engine.features.text import entities, extract, identifiers, prices
from engine.schema import Item


def _item(raw, rel, kind="html"):
    return Item(id=rel, case_id=rel.split("/")[0], paths={kind: [rel]})


def test_extract_from_html(raw):
    feats = extract(_item(raw, "100/strona.html"), raw)
    assert feats["text.narrative"].available
    assert len(feats["text.narrative"].value["minhash"]) == 128
    assert "phone:501502503" in feats["text.identifiers"].value
    assert "email:kontakt@przyklad.test" in feats["text.identifiers"].value
    assert "var" not in feats["text.keywords"].value
    assert feats["text.topic"].value == ["investment"]
    assert "strona.html" in feats["text.title"].source


def test_missing_text_is_explicit(raw):
    feats = extract(Item(id="x", case_id="x", paths={"screenshot": ["100/zrzut.png"]}), raw)
    assert feats and all(not f.available for f in feats.values())
    assert all(f.value is None for f in feats.values())


def test_meta_json_gives_title(raw):
    feats = extract(_item(raw, "400/film.info.json", "meta"), raw)
    assert feats["text.title"].available
    assert "reklama" in feats["text.title"].value


def test_helpers():
    assert identifiers("pisz na t.me/kanal_test", []) == ["handle:kanal_test"]
    assert prices("tylko 39,99 zł dziś") == ["39.99 zł"]
    assert prices("teraz 1 000 zł zamiast 2.500 PLN") == ["1000 zł", "2500 zł"]
    assert "jan kowalski" in entities("Jan Kowalski mówi. Potem Jan Kowalski dodał.")
