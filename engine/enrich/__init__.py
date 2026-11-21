from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from engine.enrich.cache import Cache
from engine.enrich.http import HttpJson
from engine.enrich.sources import fetch_crtsh, fetch_rdap, resolve_dns
from engine.features.urlnorm import is_shared_ip


@dataclass
class DomainInfo:
    created: str | None = None
    registrar: str | None = None
    nameservers: list[str] = field(default_factory=list)
    a_records: list[str] = field(default_factory=list)
    cert_sans: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


OFFLINE_PAUSE_SECONDS = 60
_offline_until: dict[str, float] = {}


def enabled() -> bool:
    return os.environ.get("MIMIC_ENRICH") == "1"


def _default_resolver():
    import dns.resolver

    resolver = dns.resolver.Resolver()
    resolver.lifetime = 3.0
    resolver.timeout = 3.0
    return resolver


def _cached(cache: Cache, kind: str, domain: str, loader):
    hit = cache.get(kind, domain)
    if hit is not None:
        return hit, None
    if time.monotonic() < _offline_until.get(kind, 0.0):
        return None, "tryb offline: pominięto zapytanie"
    try:
        value = loader()
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        IndexError,
    ) as exc:
        if isinstance(exc, (OSError, RuntimeError)):
            _offline_until[kind] = time.monotonic() + OFFLINE_PAUSE_SECONDS
        return None, f"{type(exc).__name__}: {str(exc)[:80]}"
    cache.put(kind, domain, value)
    return value, None


def lookup_domain(domain: str, http=None, resolver=None, cache: Cache | None = None) -> DomainInfo:
    cache = cache or Cache()
    http = http or HttpJson()
    info = DomainInfo()
    rdap, err = _cached(cache, "rdap", domain, lambda: fetch_rdap(domain, http))
    if rdap:
        info.created = rdap.get("created")
        info.registrar = rdap.get("registrar")
        info.nameservers = list(rdap.get("nameservers") or [])
    elif err:
        info.errors["rdap"] = err
    dns_data, err = _cached(
        cache, "dns", domain, lambda: resolve_dns(domain, resolver or _default_resolver())
    )
    if dns_data:
        info.a_records = [a for a in dns_data.get("a") or [] if not is_shared_ip(a)]
        if not info.nameservers:
            info.nameservers = list(dns_data.get("ns") or [])
    elif err:
        info.errors["dns"] = err
    sans, err = _cached(cache, "crtsh", domain, lambda: fetch_crtsh(domain, http))
    if sans is not None:
        info.cert_sans = list(sans)
    elif err:
        info.errors["crtsh"] = err
    return info


__all__ = ["DomainInfo", "enabled", "lookup_domain"]
