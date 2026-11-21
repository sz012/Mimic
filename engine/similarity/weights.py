from __future__ import annotations

from dataclasses import dataclass, field

from engine.similarity import comparators as cmp


@dataclass(frozen=True)
class Spec:
    weight: float
    comparator: cmp.Comparator
    label: str


FEATURES: dict[str, Spec] = {
    "text.exact": Spec(0.95, cmp.shared_values, "identyczny tekst (duplikat)"),
    "visual.exact": Spec(0.95, cmp.shared_values, "identyczny plik (duplikat)"),
    "text.identifiers": Spec(
        0.9, cmp.shared_values, "ten sam kontakt (e-mail/telefon/komunikator/IBAN)"
    ),
    "text.narrative": Spec(0.8, cmp.minhash, "ta sama narracja"),
    "text.ocr": Spec(0.6, cmp.minhash, "ten sam tekst na obrazach lub w wideo (OCR)"),
    "text.title": Spec(0.45, cmp.set_overlap, "podobny tytuł"),
    "text.entities": Spec(0.5, cmp.set_overlap, "te same nazwy własne/produkty"),
    "text.keywords": Spec(0.3, cmp.set_overlap, "te same słowa kluczowe"),
    "text.prices": Spec(0.3, cmp.set_overlap, "te same kwoty"),
    "text.topic": Spec(0.1, cmp.same_label, "ten sam temat"),
    "visual.assets": Spec(0.75, cmp.image_set, "te same obrazy na stronie"),
    "visual.screenshot": Spec(0.6, cmp.screenshot, "podobny wygląd (zrzut ekranu)"),
    "visual.video": Spec(0.6, cmp.image_set, "te same klatki wideo"),
    "person.names": Spec(0.45, cmp.set_overlap, "ta sama osoba publiczna"),
    "person.faces": Spec(0.6, cmp.generic, "ta sama twarz"),
    "infra.tracker_ids": Spec(0.95, cmp.shared_values, "ten sam identyfikator trackera/piksela"),
    "infra.ad_account": Spec(0.9, cmp.shared_values, "to samo konto reklamowe"),
    "infra.url_params": Spec(0.8, cmp.shared_values, "te same identyfikatory kampanii w adresie"),
    "infra.domain": Spec(0.9, cmp.shared_values, "ta sama domena"),
    "infra.hosts": Spec(0.3, cmp.set_overlap, "wspólne hosty"),
    "infra.third_party_hosts": Spec(0.5, cmp.set_overlap, "wspólne hosty zewnętrzne"),
    "infra.redirect_chain": Spec(0.6, cmp.set_overlap, "wspólny łańcuch przekierowań"),
    "infra.endpoints": Spec(0.7, cmp.set_overlap, "te same ścieżki formularzy i API"),
    "infra.favicon": Spec(0.7, cmp.shared_values, "ta sama favicona"),
    "infra.ip": Spec(0.5, cmp.shared_values, "ten sam adres IP serwera"),
    "infra.server": Spec(0.15, cmp.set_overlap, "ten sam serwer/oprogramowanie"),
    "infra.nameservers": Spec(0.5, cmp.shared_values, "te same serwery nazw"),
    "infra.cert_sans": Spec(0.9, cmp.shared_values, "domeny z tego samego certyfikatu"),
    "infra.registrar": Spec(0.1, cmp.shared_values, "ten sam rejestrator"),
    "infra.created": Spec(0.4, cmp.date_proximity, "bliskie daty rejestracji domen"),
    "template.dom_simhash": Spec(0.7, cmp.hash_distance, "podobna struktura strony (DOM)"),
    "template.inline_scripts": Spec(0.8, cmp.set_overlap, "te same skrypty wbudowane"),
    "template.scripts": Spec(0.6, cmp.set_overlap, "te same pliki skryptów"),
    "template.css_classes": Spec(0.6, cmp.set_overlap, "te same klasy CSS"),
    "template.asset_names": Spec(0.6, cmp.set_overlap, "te same nazwy plików zasobów"),
    "template.form_fields": Spec(0.5, cmp.set_overlap, "te same pola formularzy"),
    "template.html_comments": Spec(0.7, cmp.set_overlap, "te same komentarze HTML"),
    "template.meta": Spec(0.2, cmp.set_overlap, "te same metadane strony"),
}

GROUP_DEFAULT_WEIGHT = {"infra": 0.8, "template": 0.7, "text": 0.3, "visual": 0.5, "person": 0.4}


@dataclass
class Weights:
    features: dict[str, Spec] = field(default_factory=lambda: dict(FEATURES))
    group_default: dict[str, float] = field(default_factory=lambda: dict(GROUP_DEFAULT_WEIGHT))
    scale: dict[str, float] = field(default_factory=dict)
    combine: str = "features"
    kit_as_campaign: bool = False

    def spec(self, name: str, group: str) -> Spec:
        base = self.features.get(name)
        if base is None:
            base = Spec(self.group_default.get(group, 0.3), cmp.generic, name)
        factor = self.scale.get(name, self.scale.get(group, 1.0))
        if factor == 1.0:
            return base
        return Spec(min(0.99, base.weight * factor), base.comparator, base.label)


DEFAULT = Weights()
