# Cechy infrastruktury i szablonu

Wszystkie cechy powstają ze statycznych plików (HAR, zapisany HTML, manifesty, metadane wideo). Żaden skrypt strony nie jest wykonywany, a sama strona nie jest pobierana.

## Materiały i ingest
Jeden materiał (`Item`) to jedna strona w katalogu. Identyfikator to ścieżka katalogu względem `data/raw/`, a katalog główny przypadku ma `id == case_id`. Rodzaje plików: `html`, `har`, `screenshot`, `video`, `meta`, `url` oraz `assets` (katalogi `*_files` i `resources`). Braki plików nie przerywają przetwarzania.

## Infrastruktura (`infra.*`)
- `domain`, `hosts`, `third_party_hosts`: domena rejestrowalna strony (lista sufiksów wbudowana, bez sieci), hosty z HAR i HTML, bez powszechnej infrastruktury publicznej.
- `tracker_ids`: identyfikatory trackerów z HAR i HTML (piksel Meta, Google Ads/Analytics/Tag Manager, TikTok, Yandex, Clarity, Hotjar) oraz z parametrów adresu (`pxl`, `fbpx`).
- `url_params`: identyfikatory kampanii z adresu strony (`utm_id`, `ad_id`, `clickid` i podobne). Wartości o niskiej entropii są pomijane, a wrażliwe (`key`, `token`, `access_token`) zapisywane jako skrót.
- `redirect_chain`, `endpoints`, `favicon`, `ip`, `server`: łańcuch przekierowań, ścieżki formularzy i wywołań (z identyfikatorami zamienionymi na `{id}`), skrót faviconu, adresy IP serwerów (bez pul Cloudflare i adresów nieinformatywnych), nagłówki serwera.
- `ad_account`: konto reklamodawcy z metadanych materiału wideo reklamy.
- Wzbogacenie (opcjonalne, `MIMIC_ENRICH=1`): `created`, `registrar`, `nameservers`, `cert_sans` z RDAP, DNS i crt.sh. Wyniki są w `data/cache/enrich/`, błędy sieci dają jawny brak z powodem i nie są zapamiętywane.

Pewność cechy: 0.9 z HAR, 0.8 z manifestu i wzbogacenia, 0.7 z zapisanego HTML, 0.5 z samego adresu.

## Szablon (`template.*`)
Odcisk niezależny od treści: simhash struktury DOM (trigramy znaczników), skróty skryptów inline po normalizacji identyfikatorów (bez fragmentów trackerów), nazwy skryptów, klasy CSS bez klas frameworków, nazwy zasobów obrazkowych (bez nazw będących skrótami), nazwy pól formularzy (tylko gdy pojawia się nietypowe pole), skróty komentarzy HTML, wybrane znaczniki meta.

## Poziom platformy a poziom operatora
Część śladów (favikona, endpointy konstruktora stron, szablon) dowodzi wspólnej platformy, a nie jednego operatora. Identyfikatory trackerów, domeny, identyfikatory kampanii i konta reklamodawców są śladami operatora. Wagi i reguły łączenia powinny to rozróżniać.
