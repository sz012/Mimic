# Podobieństwo, grupowanie i przypisanie

## Porównanie dwóch materiałów
`compare(a, b)` porównuje każdą cechę dostępną po obu stronach komparatorem dobranym do typu wartości:

| Komparator | Dla cech | Zgodność |
|---|---|---|
| `shared_values` | identyfikatory, skróty plików i tekstu, trackery | 1, gdy jest choć jedna wspólna wartość, inaczej 0 |
| `set_overlap` | tytuł, nazwy własne, słowa kluczowe, osoby, hosty | średnia z Jaccarda i pokrycia mniejszego zbioru |
| `minhash` | narracja (3-gramy słów) | (Jaccard − 0.1) / 0.5, obcięte do 0..1 |
| `image_set` | obrazy zasobów, klatki wideo | 1 − 0.6^k, k = liczba par obrazów z odległością pHash ≤ 8 |
| `screenshot` | zrzuty ekranu (także względem obrazów drugiej strony) | 1 − d/16 dla najbliższej pary, 0 gdy d > 12 |
| `generic` | cechy bez wpisu w wagach | wybór po typie wartości |

Wkład cechy = waga × (0.5 + 0.5 × pewność) × zgodność. Wynik krawędzi:

- tryb `features` (domyślny): `1 − Π(1 − wkład_i)` po cechach,
- tryb `groups`: najpierw maksimum wkładu w każdej grupie, potem `1 − Π(1 − max_g)` po grupach, żeby skorelowane cechy jednej grupy nie kumulowały się jak niezależne dowody.

Brak cechy po którejś stronie nie obniża wyniku. Trafia do przesłanek jako jawny brak z powodem. Wartości występujące w ponad połowie materiałów (przy co najmniej 6 materiałach) są pomijane jako pospolite. Nazwy osób publicznych wspólne dla obu stron są usuwane z porównania `text.entities`, żeby ta sama osoba nie liczyła się dwa razy.

## Kiedy krawędź jest połączeniem
Połączenie wymaga wyniku ≥ progu (domyślnie 0.6) i uzasadnienia:

1. twardej przesłanki (`text.exact`, `visual.exact`, `text.identifiers`, `infra.tracker_ids`, `infra.ad_account`, `infra.domain`, `infra.cert_sans`, `infra.url_params`) z wkładem ≥ 0.3, albo
2. co najmniej dwóch niezależnych grup dowodów, każda z wkładem ≥ 0.25; grupa `person` oraz cechy `text.topic`, `text.keywords`, `text.prices`, `infra.hosts`, `infra.server`, `infra.registrar`, `template.meta` nie liczą się jako niezależne, bo ta sama osoba, temat, kwota czy popularny host występują w różnych kampaniach, albo
3. jednej bardzo silnej przesłanki z wkładem ≥ 0.55 (np. narracja z Jaccardem ok. 0.45 lub co najmniej 3 wspólne obrazy).

Wspólny zestaw narzędzi oszustów (`infra.favicon`, `infra.endpoints`: ta sama ikona i te same ścieżki backendu na różnych domenach) nie wystarcza do połączenia. Jest pokazywany w uzasadnieniu jako „wspólny zestaw narzędzi”, ale dwa materiały trafiają do jednej kampanii dopiero przy dowodzie z treści, szablonu lub identyfikatorów. Ustawienie `Weights(kit_as_campaign=True)` przywraca traktowanie zestawu jak kampanii.

Każda krawędź ma: przesłanki z wkładem, przesłanki przeciw (cechy ważne, które się nie zgadzają), braki danych, podstawę decyzji i kontrprzykład: jakie przesłanki trzeba by usunąć, żeby rozdzielić materiały, albo jakiego wkładu brakuje do połączenia.

## Grupowanie
Kampanie to składowe grafu połączeń (`components`) lub wynik średniego wiązania (`average`). Opcja `case_links` (domyślnie włączona) dokłada połączenia między materiałami z tego samego zgłoszenia (`case_id`, np. reklama i strony docelowe). Identyfikator kampanii jest stały: `K-<najmniejszy id członka>`, a pojedynczy materiał to `N-<id>`.

Przy więcej niż 40 materiałach porównywane są tylko pary kandydatów z indeksu odwrotnego: wspólne wartości cech o wadze ≥ 0.4, pasma MinHash LSH (4 wiersze) oraz segmenty pHash (4 × 16 bitów). Na mniejszych zbiorach porównywane są wszystkie pary. Test sprawdza, że na zbiorze 56 materiałów oba sposoby dają identyczne kampanie.

## Przypisanie nowego materiału
1. Materiał bez żadnej dostępnej cechy dostaje status „za mało danych”.
2. Dla każdej kampanii brane jest najlepsze porównanie z jej członkami. Wygrywa kampania z połączeniem spełniającym regułę powyżej.
3. Brak takiej kampanii oznacza „nowy wzorzec” z powodem (wynik poniżej progu albo brak uzasadnienia).
4. Gdy druga kampania też spełnia regułę i różnica wyników jest mniejsza niż 0.05, przypisanie zostaje, ale uzasadnienie ostrzega, że materiał może łączyć obie kampanie.
5. Kampania z jednym członkiem jest pełnoprawnym celem przypisania.

## Ewaluacja (`make eval`)
- Metryki par (precyzja, pokrycie, F1, ARI) i lista fałszywych połączeń (test „nie łącz”) dla czterech konfiguracji: `features`/`groups` × z łączeniem przypadków i bez.
- `eval/holdout.py`: symulacja ukrytego zbioru metodą leave-one-case-out. Usuwa przypadek, grupuje resztę, przypisuje usunięte materiały. Mierzy trafność, precyzję przypisań, pokrycie znanych kampanii i poprawność „nowego wzorca”.
- `eval/variants.py`: warianty każdego materiału (duplikat, okrojenie tekstu i zbiorów, usunięcie grupy, tylko jedna grupa; poza duplikatem bez skrótów dokładnych) i miara odporności: odsetek wariantów przypisanych do kampanii oryginału oraz liczba przypisań do obcej kampanii.
- `eval/synthetic.py`: korpus syntetyczny z etykietami, także z „wabikami” (kampanie dzielące osobę publiczną i obraz stockowy), działający bez danych organizatora.
- Raport zbiorczy: `data/cache/eval_report.json`.

## Wagi cech infrastruktury i szablonu
Wagi startowe z katalogu cech (sekcja 4.3 briefu), z trzema zmianami wynikającymi z pomiaru:

| Zmiana | Powód (dane organizatora, etykiety tymczasowe) |
|---|---|
| `infra.favicon` i `infra.endpoints` jako „zestaw narzędzi”, nie twarda przesłanka | ta sama favicona i te same ścieżki `/api/v1/agent/…` serwowane z domen kampanii A i B; skleiły dwie kampanie o różnej narracji (precyzja par 0.45) |
| `template.html_comments`: `set_overlap` zamiast `shared_values` | jeden wspólny znacznik sekcji typu `===== FOOTER =====` dawał „bardzo silną przesłankę” i dołączał przypadek 36 do kampanii A (precyzja par 0.77) |
| `infra.ad_account` (spoza katalogu) jako twarda przesłanka, waga 0.9 | identyfikator konta reklamowego wskazuje operatora |

Komparator `date_proximity` dla `infra.created`: zgodność 1 przy różnicy ≤ 3 dni, liniowo do 0 przy 30 dniach.

## Wyniki
Dane organizatora: 14 materiałów, 10 przypadków, tymczasowe etykiety `data/labels/labels.json` (7 kampanii: A = 1, 2, 3; B = 48, 61; pozostałe pojedyncze).

| Konfiguracja | Precyzja par | Pokrycie par | ARI | Holdout: trafność | Holdout: fałszywe |
|---|---|---|---|---|---|
| tylko treść (przed cechami infra i szablonu) | 1.00 | 0.21 | 0.32 | 0.71 | 0 |
| + infra i szablon, wagi domyślne grupy | 0.45 | 0.71 | 0.45 | 0.43 | 6 |
| + wagi z katalogu, zestaw nie łączy | 0.77 | 0.71 | 0.70 | 0.79 | 1 |
| + komentarze HTML jako nakładanie zbiorów | 1.00 | 0.71 | 0.81 | 0.86 | 0 |
| + łączenie materiałów z jednego przypadku (domyślne) | **1.00** | **1.00** | **1.00** | 0.86 | 0 |
| jak wyżej, ale zestaw traktowany jak kampania | 0.48 | 1.00 | 0.56 | 0.50 | 5 |

Wynik jest stały dla progów 0.4–0.9: decyduje reguła uzasadnienia, nie próg. Tryby `features` i `groups` dają ten sam wynik. Domyślnie zostaje próg 0.6 i tryb `features`.

Ablacja grup (bez łączenia po przypadku, punkt odniesienia: precyzja 1.00, pokrycie 0.71): bez `infra` pokrycie spada do 0.21; bez `text`, `visual`, `person` lub `template` wynik się nie zmienia. Na tym zbiorze kampanie wyznacza infrastruktura, a cechy treści potwierdzają połączenia i są potrzebne dla materiałów bez HAR (zrzuty, wideo).

Holdout nie trafia dwóch materiałów: reklamy w przypadku 61 (sam obraz, bez tekstu) oraz `61/strona_3`, gdy cały przypadek 61 jest wyjęty ze zbioru. Pierwszy wymaga OCR (pakiet K1).

Ograniczenia: 10 przypadków i tymczasowe etykiety. Dwie zmiany wag wynikają z analizy konkretnych fałszywych połączeń na tym samym zbiorze, więc wynik 1.00 jest optymistyczny. Korpus syntetyczny z wabikami (precyzja 1.00, pokrycie 0.92) i warianty (zero przypisań do obcej kampanii) służą jako kontrola, że zmiany nie są dopasowane wyłącznie do tych 10 przypadków.
