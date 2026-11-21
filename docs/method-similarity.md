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

1. twardej przesłanki (`text.exact`, `visual.exact`, `text.identifiers`, `infra.tracker_ids`, `infra.domain`, `infra.cert_sans`, `infra.url_params`, `infra.favicon`) z wkładem ≥ 0.3, albo
2. co najmniej dwóch niezależnych grup dowodów, każda z wkładem ≥ 0.25; grupa `person` oraz cechy `text.topic`, `text.keywords`, `text.prices` nie liczą się jako niezależne, bo ta sama osoba, temat czy kwota występują w różnych kampaniach, albo
3. jednej bardzo silnej przesłanki z wkładem ≥ 0.55 (np. narracja z Jaccardem ok. 0.45 lub co najmniej 3 wspólne obrazy).

Każda krawędź ma: przesłanki z wkładem, przesłanki przeciw (cechy ważne, które się nie zgadzają), braki danych, podstawę decyzji i kontrprzykład: jakie przesłanki trzeba by usunąć, żeby rozdzielić materiały, albo jakiego wkładu brakuje do połączenia.

## Grupowanie
Kampanie to składowe grafu połączeń (`components`) lub wynik średniego wiązania (`average`). Opcja `case_links` dokłada połączenia między materiałami z tego samego zgłoszenia (`case_id`, np. reklama i strony docelowe). Identyfikator kampanii jest stały: `K-<najmniejszy id członka>`, a pojedynczy materiał to `N-<id>`.

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

## Wyniki (stan bez etykiet organizatora)
| Zbiór | Konfiguracja | Precyzja par | Pokrycie par | Holdout: fałszywe przypisania |
|---|---|---|---|---|
| syntetyczny z wabikami | features / groups | 1.00 | 0.92 | 0 |
| syntetyczny czysty | features / groups | 1.00 | 0.48 | 0 |

Przed wyłączeniem grupy `person` z liczenia niezależnych grup korpus z wabikami dawał przy progu 0.6 precyzję par 0.43 i 64 fałszywe połączenia. Spadek pokrycia na czystym korpusie to świadomy koszt: połączenia oparte tylko na tej samej osobie i podobnej narracji nie wystarczają.

Dane organizatora (14 materiałów, bez etykiet): kampanie przy progu 0.6 w trybie `features` to {1, 2}, {14, 14/ineptsolidoval_top/…}, {48, 61/strona_1}. Tryb `groups` rozdziela drugą parę (wynik 0.50). Wszystkie 14 materiałów łączy się z własnym duplikatem. Warianty nie dają ani jednego przypisania do obcej kampanii, a odporność wynosi 0.85–0.86 dla okrojeń i usunięcia grupy. Wybór trybu i progu nastąpi w kalibracji na etykietach (pakiet K2b).
