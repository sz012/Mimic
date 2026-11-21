from __future__ import annotations

from urllib.parse import quote

import dns.exception
import dns.resolver

from engine.features.urlnorm import is_shared_ip, registrable_domain

MAX_SANS_PER_CERT = 20
MAX_SANS = 60


def parse_rdap(data: dict) -> dict:
    created = None
    for event in data.get("events") or []:
        if str(event.get("eventAction", "")).lower() == "registration":
            created = str(event.get("eventDate", ""))[:10] or None
            break
    registrar = None
    for entity in data.get("entities") or []:
        if "registrar" in [str(r).lower() for r in entity.get("roles") or []]:
            for field in (entity.get("vcardArray") or [None, []])[1]:
                if field and field[0] == "fn":
                    registrar = str(field[3]).strip().lower()
                    break
    nameservers = sorted(
        {
            str(ns.get("ldhName", "")).lower().rstrip(".")
            for ns in data.get("nameservers") or []
            if ns.get("ldhName")
        }
    )
    return {"created": created, "registrar": registrar, "nameservers": nameservers}


def fetch_rdap(domain: str, http) -> dict:
    return parse_rdap(http.get(f"https://rdap.org/domain/{quote(domain)}"))


def parse_crtsh(domain: str, data: list) -> list[str]:
    own = registrable_domain(domain)
    related: set[str] = set()
    for cert in data if isinstance(data, list) else []:
        names = [
            n.strip().lower() for n in str(cert.get("name_value", "")).split("\n") if n.strip()
        ]
        if len(names) > MAX_SANS_PER_CERT:
            continue
        for name in names:
            base = registrable_domain(name.lstrip("*."))
            if base and base != own:
                related.add(base)
    return sorted(related)[:MAX_SANS]


def fetch_crtsh(domain: str, http) -> list[str]:
    return parse_crtsh(domain, http.get(f"https://crt.sh/?q={quote(domain)}&output=json"))


def resolve_dns(domain: str, resolver) -> dict:
    out: dict[str, list[str]] = {"a": [], "ns": []}
    failures = 0
    for record, key in (("A", "a"), ("NS", "ns")):
        try:
            answers = resolver.resolve(domain, record)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            continue
        except (dns.exception.DNSException, OSError):
            failures += 1
            continue
        values = [str(r.to_text()).lower().rstrip(".") for r in answers]
        out[key] = sorted(v for v in values if not (key == "a" and is_shared_ip(v)))
    if failures == 2:
        raise RuntimeError("DNS niedostępny")
    return out
