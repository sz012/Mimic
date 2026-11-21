import json
from pathlib import Path

import pytest

from engine import enrich
from engine.enrich import DomainInfo, lookup_domain
from engine.enrich.cache import TTL_SECONDS, Cache
from engine.enrich.sources import parse_crtsh, parse_rdap, resolve_dns
from engine.features.infra import ENRICH_OFF, extract
from engine.schema import Item

RDAP = {
    "events": [
        {"eventAction": "last changed", "eventDate": "2026-10-20T10:00:00Z"},
        {"eventAction": "registration", "eventDate": "2026-10-01T08:30:00Z"},
    ],
    "entities": [
        {
            "roles": ["registrar"],
            "vcardArray": [
                "vcard",
                [["version", {}, "text", "4.0"], ["fn", {}, "text", "Rejestrator Testowy"]],
            ],
        }
    ],
    "nameservers": [{"ldhName": "NS1.Przyklad-DNS.test."}, {"ldhName": "ns2.przyklad-dns.test"}],
}
CRT = [
    {"name_value": "sklep.przyklad.test\nsiostra.test\n*.siostra.test"},
    {"name_value": "\n".join(f"d{i}.hosting.test" for i in range(30))},
]


class FakeHttp:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def get(self, url):
        self.calls.append(url)
        if self.fail:
            raise OSError("brak sieci")
        return RDAP if "rdap" in url else CRT


class Answer:
    def __init__(self, text):
        self.text = text

    def to_text(self):
        return self.text


class FakeResolver:
    def resolve(self, domain, record):
        if record == "A":
            return [Answer("93.184.216.35"), Answer("104.21.82.70")]
        return [Answer("ns1.przyklad-dns.test.")]


@pytest.fixture(autouse=True)
def reset_offline(monkeypatch):
    monkeypatch.setattr(enrich, "_offline_until", {})


def test_parse_rdap_extracts_creation_registrar_nameservers():
    parsed = parse_rdap(RDAP)
    assert parsed["created"] == "2026-10-01"
    assert parsed["registrar"] == "rejestrator testowy"
    assert parsed["nameservers"] == ["ns1.przyklad-dns.test", "ns2.przyklad-dns.test"]
    assert parse_rdap({}) == {"created": None, "registrar": None, "nameservers": []}


def test_parse_crtsh_skips_own_domain_and_multi_tenant_certs():
    assert parse_crtsh("sklep.przyklad.test", CRT) == ["siostra.test"]
    assert parse_crtsh("x.test", "nie lista") == []


def test_resolve_dns_filters_shared_ips_and_flags_total_failure():
    out = resolve_dns("x.przyklad.test", FakeResolver())
    assert out == {"a": ["93.184.216.35"], "ns": ["ns1.przyklad-dns.test"]}

    class Down:
        def resolve(self, domain, record):
            raise OSError("brak sieci")

    with pytest.raises(RuntimeError):
        resolve_dns("x.przyklad.test", Down())


def test_lookup_collects_everything_and_uses_cache(tmp_path):
    http, cache = FakeHttp(), Cache(tmp_path)
    info = lookup_domain("sklep.przyklad.test", http, FakeResolver(), cache)
    assert info.created == "2026-10-01"
    assert info.cert_sans == ["siostra.test"]
    assert info.a_records == ["93.184.216.35"]
    assert info.errors == {}
    calls = len(http.calls)
    again = lookup_domain("sklep.przyklad.test", FakeHttp(fail=True), FakeResolver(), cache)
    assert again.created == "2026-10-01" and len(http.calls) == calls


def test_offline_gives_explicit_errors_and_pauses_requests(tmp_path):
    http = FakeHttp(fail=True)
    info = lookup_domain("a.przyklad.test", http, FakeResolver(), Cache(tmp_path))
    assert info.created is None and "rdap" in info.errors
    first_calls = len(http.calls)
    lookup_domain("b.przyklad.test", http, FakeResolver(), Cache(tmp_path))
    assert len(http.calls) == first_calls


def test_slow_source_does_not_pause_the_others(tmp_path):
    class SlowCrt(FakeHttp):
        def get(self, url):
            if "crt.sh" in url:
                raise TimeoutError("za wolno")
            return super().get(url)

    first = lookup_domain("a.przyklad.test", SlowCrt(), FakeResolver(), Cache(tmp_path))
    assert "crtsh" in first.errors and first.created == "2026-10-01"
    second = lookup_domain("b.przyklad.test", SlowCrt(), FakeResolver(), Cache(tmp_path))
    assert second.created == "2026-10-01"
    assert second.errors["crtsh"].startswith("tryb offline")


def test_failures_are_not_cached(tmp_path):
    cache = Cache(tmp_path)
    lookup_domain("a.przyklad.test", FakeHttp(fail=True), FakeResolver(), cache)
    assert cache.get("rdap", "a.przyklad.test") is None


def test_cache_ttl_and_corrupt_files(tmp_path):
    now = [1000.0]
    cache = Cache(tmp_path, clock=lambda: now[0])
    cache.put("rdap", "x.test", {"a": 1})
    assert cache.get("rdap", "x.test") == {"a": 1}
    now[0] += TTL_SECONDS + 1
    assert cache.get("rdap", "x.test") is None
    (tmp_path / "rdap" / "zly.json").write_text("{")
    assert cache.get("rdap", "zly") is None


def test_enrichment_disabled_by_default_is_explicit_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("MIMIC_ENRICH", raising=False)
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "input.url").write_text("https://sklep.przyklad.test/\n")
    item = Item("1", "1", paths={"url": ["1/input.url"]})
    feats = extract(item, tmp_path)
    for name in ("infra.created", "infra.registrar", "infra.nameservers", "infra.cert_sans"):
        assert not feats[name].available and feats[name].source == ENRICH_OFF


def test_enrichment_adds_features_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_ENRICH", "1")
    info = DomainInfo(
        created="2026-10-01",
        registrar="rejestrator testowy",
        nameservers=["ns1.przyklad-dns.test"],
        a_records=["93.184.216.35"],
        cert_sans=["siostra.test"],
    )
    monkeypatch.setattr("engine.features.infra.enrich.lookup_domain", lambda domain: info)
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "input.url").write_text("https://sklep.przyklad.test/\n")
    feats = extract(Item("1", "1", paths={"url": ["1/input.url"]}), tmp_path)
    assert feats["infra.created"].value == "2026-10-01"
    assert feats["infra.registrar"].value == ["rejestrator testowy"]
    assert feats["infra.nameservers"].value == ["ns1.przyklad-dns.test"]
    assert feats["infra.cert_sans"].value == ["siostra.test"]
    assert feats["infra.ip"].value == ["93.184.216.35"]
    assert feats["infra.created"].confidence == 0.8
    json.dumps({k: v.value for k, v in feats.items()})


def test_enrichment_errors_are_reported_per_feature(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_ENRICH", "1")
    info = DomainInfo(errors={"rdap": "OSError: brak sieci", "crtsh": "OSError: brak sieci"})
    monkeypatch.setattr("engine.features.infra.enrich.lookup_domain", lambda domain: info)
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "input.url").write_text("https://sklep.przyklad.test/\n")
    feats = extract(Item("1", "1", paths={"url": ["1/input.url"]}), tmp_path)
    assert feats["infra.created"].source.startswith("rdap: OSError")
    assert feats["infra.cert_sans"].source.startswith("crtsh: OSError")


def test_no_domain_means_missing_not_a_lookup(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIC_ENRICH", "1")
    called = []
    monkeypatch.setattr(
        "engine.features.infra.enrich.lookup_domain", lambda d: called.append(d) or DomainInfo()
    )
    feats = extract(Item("1", "1"), Path(tmp_path))
    assert called == []
    assert feats["infra.created"].source == "nieznana domena strony głównej"
