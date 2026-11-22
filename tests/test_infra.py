import base64
import json
from pathlib import Path

from engine.features.harparse import load_har, main_entry, redirect_hosts
from engine.features.infra import NAMES, extract
from engine.features.trackers import is_identifier, trackers_in_text, trackers_in_url, url_params
from engine.features.urlnorm import is_common, normalize_path, registrable_domain
from engine.schema import Item


def har_entry(
    url,
    status=200,
    rtype="other",
    mime="text/html",
    method="GET",
    ip="93.184.216.34",
    headers=None,
    text=None,
    redirect="",
):
    content = {"mimeType": mime}
    if text is not None:
        content["text"] = text
    return {
        "request": {"url": url, "method": method},
        "response": {
            "status": status,
            "redirectURL": redirect,
            "headers": [{"name": k, "value": v} for k, v in (headers or {}).items()],
            "content": content,
        },
        "_resourceType": rtype,
        "serverIPAddress": ip,
    }


def write_har(path: Path, entries: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"log": {"creator": {"name": "t"}, "entries": entries}}))
    return path


def make_item(raw: Path, **paths) -> Item:
    return Item(id="1", case_id="1", paths={k: v for k, v in paths.items()})


def test_shared_cdn_ips_are_not_features(tmp_path):
    from engine.features.urlnorm import is_shared_ip

    assert is_shared_ip("188.114.98.40") and is_shared_ip("104.18.40.7")
    assert is_shared_ip("1.1.1.1") and is_shared_ip("127.0.0.1") and is_shared_ip("10.0.0.5")
    assert not is_shared_ip("93.184.216.34") and not is_shared_ip("nie-ip")
    write_har(
        tmp_path / "1" / "a.har",
        [har_entry("https://x.przyklad.test/", rtype="document", ip="104.18.40.7")],
    )
    feats = extract(make_item(tmp_path, har=["1/a.har"]), tmp_path)
    assert not feats["infra.ip"].available


def test_registrable_domain_and_common():
    assert registrable_domain("sklep.przyklad.test") == "przyklad.test"
    assert registrable_domain("a.b.co.uk") == "b.co.uk"
    assert registrable_domain("localhost") is None
    assert registrable_domain("203.0.113.5") is None
    assert is_common("fonts.googleapis.com")
    assert not is_common("sklep.przyklad.test")


def test_normalize_path_collapses_ids_and_drops_static():
    assert normalize_path("https://x.test/api/v1/lead/123456") == "/api/v1/lead/{id}"
    assert (
        normalize_path("https://x.test/api/0f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0/go")
        == "/api/{id}/go"
    )
    assert normalize_path("https://x.test/lander/order.php?x=1") == "/lander/order.php"
    assert normalize_path("https://x.test/") is None
    assert normalize_path("https://x.test/app.js") is None
    assert normalize_path("https://x.test/lead") is None


def test_trackers_from_text_and_urls():
    text = "fbq('init', '1234567890123'); gtag('config','AW-10293847561'); ym(12345678, 'init', {})"
    found = trackers_in_text(text)
    assert {"fbpixel:1234567890123", "gads:AW-10293847561", "ym:12345678"} <= found
    assert "ga4:G-ABCDEFGH" not in trackers_in_text("G-ABCDEFGH")
    assert "ga4:G-ABCD1234EF" in trackers_in_text("G-ABCD1234EF")
    assert "fbpixel:99999999999" in trackers_in_url(
        "https://www.facebook.com/tr/?id=99999999999&ev=PageView"
    )
    assert "gads:AW-10293847561" in trackers_in_url(
        "https://www.google.com/pagead/1p-conversion/10293847561/?rand=1"
    )


def test_url_params_filters_low_entropy_and_hashes_secrets():
    params, trackers = url_params(
        "https://x.test/?utm_id=Qx7TmZp2LkW9rB4nYc8D&utm_source=fb&utm_medium=Instagram_Feed"
        "&utm_campaign=5150&pxl=1029384756102938&access_token=SECRETVALUE123&fbclid=abc1234567"
    )
    assert "utm_id=Qx7TmZp2LkW9rB4nYc8D" in params
    assert not any(
        p.startswith(("utm_source", "utm_medium", "utm_campaign", "fbclid")) for p in params
    )
    assert any(p.startswith("access_token=sha1:") and "SECRET" not in p for p in params)
    assert "fbpixel:1029384756102938" in trackers


def test_is_identifier():
    assert is_identifier("kq3vz81mx0pt5ws2nd7e")
    assert is_identifier("QmZrTpWkVb")
    assert not is_identifier("FacebookAds")
    assert not is_identifier("vid_3")
    assert not is_identifier("{account.id}")


def test_extract_from_har(tmp_path):
    entries = [
        har_entry("https://static.cdn.test/a.js", rtype="script", mime="text/javascript"),
        har_entry(
            "https://sklep.przyklad.test/oferta/?utm_id=Qx7TmZp2LkW9rB4nYc8D",
            rtype="document",
            headers={"Server": "nginx"},
            text="<html>fbq('init','1234567890123')</html>",
        ),
        har_entry(
            "https://sklep.przyklad.test/api/v1/lead/99887766",
            rtype="xhr",
            method="POST",
            mime="application/json",
        ),
        har_entry("https://fonts.googleapis.com/css", mime="text/css", rtype="stylesheet"),
        har_entry("https://edge.partner.test/x.png", mime="image/png", rtype="image"),
    ]
    write_har(tmp_path / "1" / "ruch.har", entries)
    item = make_item(tmp_path, har=["1/ruch.har"])
    feats = extract(item, tmp_path)
    assert set(feats) == set(NAMES)
    assert feats["infra.domain"].value == ["przyklad.test"]
    assert feats["infra.tracker_ids"].value == ["fbpixel:1234567890123"]
    assert feats["infra.url_params"].value == ["utm_id=Qx7TmZp2LkW9rB4nYc8D"]
    assert feats["infra.endpoints"].value == ["/api/v1/lead/{id}"]
    assert feats["infra.server"].value == ["server:nginx"]
    assert feats["infra.ip"].value == ["93.184.216.34"]
    assert "fonts.googleapis.com" not in feats["infra.hosts"].value
    assert feats["infra.third_party_hosts"].value == ["edge.partner.test", "static.cdn.test"]
    assert feats["infra.domain"].confidence == 0.9


def test_missing_features_are_explicit_not_zero(tmp_path):
    item = make_item(tmp_path)
    feats = extract(item, tmp_path)
    assert set(feats) == set(NAMES)
    assert all(not f.available and f.value is None for f in feats.values())
    assert feats["infra.ip"].source == "brak pliku HAR"


def test_broken_and_empty_har_do_not_raise(tmp_path):
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "zly.har").write_text("to nie json")
    (tmp_path / "1" / "pusty.har").write_text(json.dumps({"log": {"entries": []}}))
    feats = extract(make_item(tmp_path, har=["1/zly.har", "1/pusty.har", "1/brak.har"]), tmp_path)
    assert all(not f.available for f in feats.values())


def test_html_only_uses_saved_from_url_and_forms(tmp_path):
    html = (
        "<!-- saved from url=(0070)https://landing.przyklad.test/oferta/?utm_id=Qx7TmZp2LkW9rB4nYc8D -->"
        "<html><head><link rel='icon' href='ikona.png'></head><body>"
        "<form action='https://landing.przyklad.test/lander/order.php'></form>"
        "<script>fbq('init','1234567890123')</script>"
        "<img src='https://img.partner.test/a.png'></body></html>"
    )
    page = tmp_path / "1" / "strona.html"
    page.parent.mkdir(parents=True)
    page.write_text(html)
    assets = tmp_path / "1" / "strona_files"
    assets.mkdir()
    (assets / "ikona.png").write_bytes(b"ikona")
    item = make_item(tmp_path, html=["1/strona.html"], assets=["1/strona_files"])
    feats = extract(item, tmp_path)
    assert feats["infra.domain"].value == ["przyklad.test"]
    assert feats["infra.tracker_ids"].value == ["fbpixel:1234567890123"]
    assert feats["infra.endpoints"].value == ["/lander/order.php"]
    assert feats["infra.favicon"].available
    assert feats["infra.third_party_hosts"].value == ["img.partner.test"]
    assert feats["infra.domain"].confidence == 0.7
    assert not feats["infra.ip"].available


def test_meta_and_url_sources(tmp_path):
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "manifest.json").write_text(
        json.dumps({"page_url": "https://sklep.przyklad.test/?pxl=1029384756102938"})
    )
    (tmp_path / "1" / "info.json").write_text(
        json.dumps({"extractor": "facebook:ads", "playlist_uploader": "Strona Testowa"})
    )
    (tmp_path / "1" / "input.url").write_text("https://inna.example.test/x\n")
    item = make_item(tmp_path, meta=["1/manifest.json", "1/info.json"], url=["1/input.url"])
    feats = extract(item, tmp_path)
    assert feats["infra.ad_account"].value == ["facebook:strona testowa"]
    assert "fbpixel:1029384756102938" in feats["infra.tracker_ids"].value
    assert sorted(feats["infra.domain"].value) == ["example.test", "przyklad.test"]


def test_main_entry_skips_common_hosts_and_redirect_chain(tmp_path):
    entries = [
        har_entry("https://www.googletagmanager.com/gtm.js", mime="text/html"),
        har_entry(
            "https://a.przyklad.test/",
            status=302,
            rtype="document",
            redirect="https://b.przyklad.test/x",
        ),
        har_entry("https://b.przyklad.test/x", rtype="document"),
    ]
    path = write_har(tmp_path / "r.har", entries)
    loaded = load_har(path)
    main = main_entry(loaded)
    assert main is not None and main.host == "a.przyklad.test"
    assert redirect_hosts(loaded, main) == ["a.przyklad.test", "b.przyklad.test"]


def test_har_body_base64(tmp_path):
    body = base64.b64encode(b"<html>fbq('init','1234567890123')</html>").decode()
    entry = har_entry("https://x.przyklad.test/", rtype="document")
    entry["response"]["content"].update({"text": body, "encoding": "base64"})
    write_har(tmp_path / "1" / "a.har", [entry])
    feats = extract(make_item(tmp_path, har=["1/a.har"]), tmp_path)
    assert feats["infra.tracker_ids"].value == ["fbpixel:1234567890123"]


def test_real_data_shared_signals():
    raw = Path("data/raw")
    if not (raw / "1").is_dir():
        import pytest

        pytest.skip("brak danych organizatora")
    from engine.ingest import discover_items

    items = {i.id: extract(i, raw) for i in discover_items(raw) if i.id in {"1", "2", "3"}}
    assert set(items["1"]["infra.tracker_ids"].value) & set(items["2"]["infra.tracker_ids"].value)
    assert set(items["2"]["infra.domain"].value) & set(items["3"]["infra.domain"].value)
