import json
from pathlib import Path

from engine.features.template import NAMES, extract, simhash
from engine.schema import Item
from tests.test_ingest import build_mhtml


def page(body: str, head: str = "") -> str:
    return f"<html><head><title>t</title>{head}</head><body>{body}</body></html>"


LAYOUT = (
    "<div class='hero-box'><h1>{t}</h1><div class='lead-form'><form action='/lander/order.php'>"
    "<input name='fio'><input name='tel_number'><input type='hidden' name='subid'>"
    "<input name='pxl' type='hidden'></form></div></div>"
    "<div class='reviews'><ul><li><p>{p}</p></li><li><p>{p}</p></li><li><p>{p}</p></li></ul></div>"
    "<footer><a href='#'>x</a></footer>"
)
OTHER_LAYOUT = (
    "<table><tr><td><table><tr><td><span>{t}</span></td></tr></table></td></tr></table>"
    "<section><article><header><h2>{p}</h2></header><aside><nav><a>1</a><a>2</a></nav></aside></article></section>"
)


def write_item(root: Path, name: str, html: str, assets: dict[str, bytes] | None = None) -> Item:
    case = root / name
    case.mkdir(parents=True)
    (case / "strona.html").write_text(html)
    paths = {"html": [f"{name}/strona.html"]}
    if assets:
        directory = case / "strona_files"
        directory.mkdir()
        for filename, data in assets.items():
            (directory / filename).write_bytes(data)
        paths["assets"] = [f"{name}/strona_files"]
    return Item(id=name, case_id=name, paths=paths)


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()


def test_clones_with_different_text_have_close_simhash_and_other_layouts_far(tmp_path):
    a = write_item(tmp_path, "a", page(LAYOUT.format(t="Pierwszy tytul", p="Opinia jeden")))
    b = write_item(tmp_path, "b", page(LAYOUT.format(t="Zupelnie inny naglowek", p="Inna opinia")))
    c = write_item(tmp_path, "c", page(OTHER_LAYOUT.format(t="Tytul", p="Opinia")))
    fa, fb, fc = (extract(i, tmp_path)["template.dom_simhash"].value for i in (a, b, c))
    assert hamming(fa, fb) == 0
    assert hamming(fa, fc) > 12


def test_simhash_needs_enough_structure():
    assert simhash(["0div"]) is None
    assert len(simhash(["0div", "1p", "1p", "0div"])) == 16


def test_all_feature_names_present_and_missing_is_explicit(tmp_path):
    feats = extract(Item(id="x", case_id="x"), tmp_path)
    assert set(feats) == set(NAMES)
    assert all(not f.available and f.value is None for f in feats.values())
    assert "html" in feats["template.scripts"].source


def test_scripts_classes_fields_comments_meta(tmp_path):
    html = page(
        "<!-- notatka kitu wersja 7 -->"
        "<div class='container hero-box'><form><input name='fio'><input name='tel_number'>"
        "<input type='hidden' name='subid'></form></div>"
        "<script src='https://cdn.przyklad.test/js/kit-core.3f9a2b7c.js'></script>"
        "<script src='/js/jquery.min.js'></script>"
        "<script>window.kit = {'start': function() { return 1234567; }}; // inline kit code</script>"
        "<script>fbq('init','1234567890123'); /* piksel */ var padding = 'x'.repeat(10);</script>",
        head="<meta name='generator' content='KitBuilder 2.1'><meta name='viewport' content='w'>",
    )
    feats = extract(write_item(tmp_path, "1", html), tmp_path)
    assert feats["template.scripts"].value == ["kit-core.js"]
    assert "hero-box" in feats["template.css_classes"].value
    assert "container" not in feats["template.css_classes"].value
    assert feats["template.form_fields"].value == [
        "field:fio",
        "field:tel_number",
        "hidden:subid",
    ]
    assert feats["template.meta"].value == ["generator:kitbuilder 2.1"]
    assert len(feats["template.inline_scripts"].value) == 1
    assert len(feats["template.html_comments"].value) == 1


def test_inline_script_hash_ignores_ids_so_clones_match(tmp_path):
    body = (
        "<script>window.kit = {'start': function() { return CODE; }}; var padding = 'abc';</script>"
    )
    a = write_item(tmp_path, "a", page(body.replace("CODE", "1234567")))
    b = write_item(tmp_path, "b", page(body.replace("CODE", "7654321")))
    va = extract(a, tmp_path)["template.inline_scripts"].value
    vb = extract(b, tmp_path)["template.inline_scripts"].value
    assert va == vb


def test_generic_forms_are_not_emitted(tmp_path):
    html = page("<form><input name='name'><input name='phone'><input name='email'></form>")
    feats = extract(write_item(tmp_path, "1", html), tmp_path)
    assert not feats["template.form_fields"].available


def test_asset_names_skip_hashed_files(tmp_path):
    html = page("<img src='strona_files/obraz1.webp'><p>x</p><p>y</p><p>z</p>")
    assets = {
        "obraz1.webp": b"a",
        "04-baner-oferta.webp": b"b",
        "9a8b7c6d-1e2f-4a3b-8c4d-5e6f7a8b9c0d.png": b"c",
        "main.css": b"d",
    }
    feats = extract(write_item(tmp_path, "1", html, assets), tmp_path)
    assert feats["template.asset_names"].value == ["04-baner-oferta.webp", "obraz1.webp"]


def test_assets_without_html_still_give_names(tmp_path):
    case = tmp_path / "1" / "tytul_files"
    case.mkdir(parents=True)
    (case / "zdjecie7.webp").write_bytes(b"x")
    item = Item(id="1", case_id="1", paths={"assets": ["1/tytul_files"]})
    feats = extract(item, tmp_path)
    assert feats["template.asset_names"].value == ["zdjecie7.webp"]
    assert not feats["template.dom_simhash"].available


def test_mhtml_only_item_is_parsed(tmp_path):
    case = tmp_path / "1"
    case.mkdir()
    (case / "zapis.mhtml").write_bytes(
        build_mhtml(page(LAYOUT.format(t="a", p="b")).replace("<title>t</title>", ""))
    )
    item = Item(id="1", case_id="1", paths={"html": ["1/zapis.mhtml"]})
    assert extract(item, tmp_path)["template.dom_simhash"].available


def test_html_from_har_is_used_when_no_html_file(tmp_path):
    case = tmp_path / "1"
    case.mkdir()
    entry = {
        "request": {"url": "https://x.przyklad.test/", "method": "GET"},
        "response": {
            "status": 200,
            "headers": [],
            "content": {"mimeType": "text/html", "text": page(LAYOUT.format(t="a", p="b"))},
        },
        "_resourceType": "document",
    }
    (case / "r.har").write_text(json.dumps({"log": {"entries": [entry]}}))
    item = Item(id="1", case_id="1", paths={"har": ["1/r.har"]})
    feats = extract(item, tmp_path)
    assert feats["template.dom_simhash"].available
    assert feats["template.dom_simhash"].source.startswith("har:")


def test_real_data_clone_and_capture_pairs():
    raw = Path("data/raw")
    if not (raw / "1").is_dir():
        import pytest

        pytest.skip("brak danych organizatora")
    from engine.ingest import discover_items

    feats = {i.id: extract(i, raw) for i in discover_items(raw)}
    one, two = feats["1"], feats["2"]
    assert one["template.dom_simhash"].value == two["template.dom_simhash"].value
    cap = feats["14/ineptsolidoval_top/ineptsolidoval_top"]
    assert (
        hamming(feats["14"]["template.dom_simhash"].value, cap["template.dom_simhash"].value) < 12
    )
