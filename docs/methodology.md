# Metodyka

Cel: z pojedynczych materiałów (zapisane strony, logi HAR, zrzuty, nagrania) wydobyć wspólne ślady i połączyć je w kampanie tak, aby każde połączenie dało się wyjaśnić. Dokument opisuje przepływ od pliku do kampanii: pozyskiwanie cech, liczenie podobieństwa i grupowanie.

## 1. Przepływ

1. **Ingest.** Katalogi z plikami zamieniane są na materiały (`Item`). Wgrane pliki (także zip i mhtml) są zapisywane bezpiecznie w katalogu roboczym.
2. **Cechy.** Każdy moduł zwraca ustrukturyzowane wartości z pewnością i źródłem. Brak danych to jawny brak z powodem, a błąd modułu nie przerywa przetwarzania.
3. **Porównanie.** Dwa materiały porównywane są cecha po cesze, a wyniki łączone w jeden wynik z listą przesłanek.
4. **Grupowanie.** Krawędzie spełniające regułę uzasadnienia tworzą kampanie.
5. **Przypisanie nowego materiału.** Nowy materiał jest porównywany z członkami istniejących kampanii. Najlepsze uzasadnione dopasowanie daje kampanię, w przeciwnym razie wynik to "nowy wzorzec".

## 2. Materiały i ingest

Jeden materiał to jedna strona w katalogu. Identyfikator to ścieżka katalogu względem `data/raw/`, a katalog główny przypadku ma `id == case_id` (np. `61`, `61/strona_2`). Rodzaje plików: `html` (także mhtml), `har` (także plik o nazwie `.har`), `screenshot`, `video`, `meta` (np. `info.json`, `manifest.json`), `url` oraz `assets` (katalogi `*_files` i `resources`, niebędące osobnymi materiałami). Braki plików nie przerywają przetwarzania.

Wgrywane materiały mogą mieć dowolną kombinację rodzajów. Zip jest rozpakowywany z blokadą ścieżek spoza katalogu i limitem liczby oraz rozmiaru plików. Adres URL wpisany w interfejsie daje analizę samej domeny. Strona spod adresu jest pobierana tylko po `MIMIC_ALLOW_FETCH=1`, statycznie, bez wykonywania skryptów.

## 3. Cechy

Wszystkie cechy liczone są statycznie. Strony oszustów nie są otwierane, a ich JavaScript nie jest wykonywany. Pewność cechy zależy od źródła (HAR najwyższa, sam adres najniższa) i skaluje jej wagę.

### 3.1 Tekst
Źródła w kolejności: zapisany HTML, największa odpowiedź `text/html` z HAR, metadane wideo (tytuł, opis), a gdy brak strony, tekst z OCR obrazów i klatek. Tekst jest normalizowany: małe litery, bez polskich znaków diakrytycznych (odporność na OCR i kodowania), bez słów funkcyjnych.

| Cecha | Wartość |
|---|---|
| `text.narrative` | MinHash (128 permutacji) 3-gramów słów z akapitów, list i nagłówków |
| `text.exact` | SHA-1 znormalizowanej narracji (duplikaty) |
| `text.title`, `text.keywords` | słowa tytułu, 30 najczęstszych słów |
| `text.entities` | nazwy własne i produkty |
| `text.identifiers` | e-mail, telefon, uchwyty komunikatorów, IBAN |
| `text.prices` | kwoty z walutą |
| `text.topic` | temat ze słownika: inwestycje, zdrowie, hazard, zakupy, wiadomości |
| `text.ocr` | MinHash 5-gramów znaków tekstu z obrazów i klatek wideo (porównanie na znakach jest odporniejsze, bo OCR skleja polskie słowa) |

### 3.2 Obraz
- `visual.screenshot`: pHash i dHash zrzutu oraz pHash pierwszego ekranu.
- `visual.assets`: pHash obrazów z katalogów zasobów (bez ikon poniżej 80 px i obrazów jednolitych); gdy ich brak, obrazy zapisane w HAR.
- `visual.video`: klatki kluczowe wideo (próbkowanie co 1 s, zapis przy zmianie sceny albo co najmniej raz na 10 s, do 30 klatek), zapisywane w `data/cache/frames/`.
- `visual.exact`: SHA-1 plików zrzutów i wideo.

### 3.3 OCR
RapidOCR (modele PP-OCR w ONNX, bez binarek systemowych) czyta zrzuty, klatki kluczowe i do 6 największych obrazów strony. Linie o pewności poniżej 0,6 są odrzucane, a wyniki zapamiętywane w `data/cache/ocr/`. Tekst z OCR zasila narrację, słowa kluczowe i nazwy tylko wtedy, gdy materiał nie ma strony (sama reklama, samo wideo). Zawsze trafia do `text.ocr`.

### 3.4 Osoby
- `person.names`: osoby publiczne z małej bazy `data/refs/persons.json` (nazwa, aliasy) wykryte w tekście lub OCR, z obsługą odmiany nazwisk i wymogiem imienia przy krótkich nazwiskach.
- `person.faces`: jawny brak. Dopasowanie twarzy wymaga modelu i obrazów referencyjnych z jasną licencją i nie weszło do tej wersji.

### 3.5 Infrastruktura
- `domain`, `hosts`, `third_party_hosts`: domena rejestrowalna strony (lista sufiksów wbudowana, bez sieci) i hosty z HAR i HTML, bez powszechnej infrastruktury publicznej.
- `tracker_ids`: identyfikatory trackerów z HAR i HTML (piksel Meta, Google Ads, Analytics i Tag Manager, TikTok, Yandex, Clarity, Hotjar) oraz z parametrów adresu.
- `url_params`: identyfikatory kampanii z adresu strony (`utm_id`, `ad_id`, `clickid` i podobne). Wartości o niskiej entropii są pomijane, a wrażliwe (`key`, `token`, `access_token`) zapisywane jako skrót.
- `redirect_chain`, `endpoints`, `favicon`, `ip`, `server`: łańcuch przekierowań, ścieżki formularzy i wywołań (identyfikatory zamienione na `{id}`), skrót faviconu, adresy IP serwerów (bez pul CDN i adresów nieinformatywnych) i nagłówki serwera.
- `ad_account`: konto reklamodawcy z metadanych wideo reklamy.
- Wzbogacenie (opcjonalne, `MIMIC_ENRICH=1`): `created`, `registrar`, `nameservers`, `cert_sans` z RDAP, DNS i crt.sh. Wyniki są w `data/cache/enrich/`, a błąd sieci daje jawny brak z powodem i nie jest zapamiętywany.

Pewność: 0,9 z HAR, 0,8 z manifestu i wzbogacenia, 0,7 z zapisanego HTML, 0,5 z samego adresu.

### 3.6 Szablon
Odcisk niezależny od treści: simhash struktury DOM (trigramy znaczników), skróty skryptów inline po normalizacji identyfikatorów (bez fragmentów trackerów), nazwy skryptów, klasy CSS bez klas frameworków, nazwy zasobów obrazkowych (bez nazw będących skrótami), nazwy pól formularzy (tylko gdy pojawia się nietypowe pole), skróty komentarzy HTML i wybrane znaczniki meta.

### 3.7 Ślady platformy i ślady operatora
Wspólna favikona i ścieżki backendu konstruktora stron dowodzą wspólnej platformy, a nie jednej kampanii. Identyfikatory trackerów, domeny, identyfikatory kampanii i konta reklamodawców dowodzą tego samego operatora. Reguła łączenia (sekcja 5) rozróżnia te dwa poziomy.

### 3.8 Zależności opcjonalne
Wideo (OpenCV) i OCR (RapidOCR) są dodatkami (`uv sync --extra video --extra ocr`, w Dockerze `MIMIC_EXTRAS`), importowanymi leniwie. Bez nich aplikacja działa, a odpowiednie cechy są jawnym brakiem z nazwą brakującej zależności.

## 4. Podobieństwo

`compare(a, b)` porównuje każdą cechę dostępną po obu stronach komparatorem dobranym do typu wartości:

| Komparator | Dla cech | Zgodność |
|---|---|---|
| `shared_values` | identyfikatory, skróty plików i tekstu, trackery | 1, gdy jest choć jedna wspólna wartość, inaczej 0 |
| `set_overlap` | tytuł, nazwy własne, słowa kluczowe, osoby, hosty | średnia z Jaccarda i pokrycia mniejszego zbioru |
| `minhash` | narracja (3-gramy słów) | (Jaccard − 0,1) / 0,5, obcięte do 0..1 |
| `image_set` | obrazy zasobów, klatki wideo | 1 − 0,6^k, k = liczba par obrazów z odległością pHash ≤ 8 |
| `screenshot` | zrzuty ekranu (także względem obrazów drugiej strony) | 1 − d/16 dla najbliższej pary, 0 gdy d > 12 |
| `hash_distance` | odcisk struktury DOM | spada liniowo z odległością Hamminga |
| `date_proximity` | data rejestracji domeny | 1 przy różnicy ≤ 3 dni, liniowo do 0 przy 30 dniach |
| `generic` | cechy bez wpisu w wagach | wybór według typu wartości |

Wkład cechy = waga × (0,5 + 0,5 × pewność) × zgodność. Wynik krawędzi:

- tryb `features` (domyślny): `1 − Π(1 − wkład_i)` po cechach,
- tryb `groups`: najpierw maksimum wkładu w każdej grupie, potem `1 − Π(1 − max_g)` po grupach, żeby skorelowane cechy jednej grupy nie kumulowały się jak niezależne dowody.

Brak cechy po którejś stronie nie obniża wyniku i trafia do przesłanek jako jawny brak z powodem. Wartości obecne w ponad połowie materiałów (przy co najmniej sześciu) są pomijane jako pospolite. Nazwy osób publicznych wspólne dla obu stron są usuwane z porównania nazw własnych, żeby ta sama osoba nie liczyła się dwa razy.

Wagi startowe: dokładny duplikat tekstu i pliku 0,95; wspólny kontakt 0,9; ta sama narracja 0,8; wspólne obrazy 0,75; podobny zrzut 0,6; nazwy własne i tytuł 0,45–0,5; słowa kluczowe i kwoty 0,3; temat 0,1. Wagi infrastruktury i szablonu wynikają z kalibracji na etykietach (sekcja 8): identyfikatory trackerów i kampanii, domena i konto reklamodawcy są najsilniejsze, ślady platformy najsłabsze.

## 5. Kiedy krawędź jest połączeniem

Połączenie wymaga wyniku ≥ progu (domyślnie 0,6) i uzasadnienia:

1. twardej przesłanki (`text.exact`, `visual.exact`, `text.identifiers`, `infra.tracker_ids`, `infra.ad_account`, `infra.domain`, `infra.cert_sans`, `infra.url_params`) z wkładem ≥ 0,3, albo
2. co najmniej dwóch niezależnych grup dowodów, każda z wkładem ≥ 0,25; grupa `person` oraz cechy `text.topic`, `text.keywords`, `text.prices`, `infra.hosts`, `infra.server`, `infra.registrar` i `template.meta` nie liczą się jako niezależne, bo ta sama osoba, temat, kwota czy popularny host występują w różnych kampaniach, albo
3. jednej bardzo silnej przesłanki z wkładem ≥ 0,55 (np. narracja z Jaccardem ok. 0,45 lub co najmniej 3 wspólne obrazy).

Wspólny zestaw narzędzi (`infra.favicon`, `infra.endpoints`: ta sama ikona i te same ścieżki backendu na różnych domenach) nie wystarcza do połączenia. Jest pokazywany w uzasadnieniu jako "wspólny zestaw narzędzi", ale materiały trafiają do jednej kampanii dopiero przy dowodzie z treści, szablonu lub identyfikatorów. Ustawienie `Weights(kit_as_campaign=True)` przywraca traktowanie zestawu jak kampanii.

## 6. Grupowanie

Kampanie to składowe grafu połączeń (`components`) lub wynik średniego wiązania (`average`). Opcja `case_links` (domyślnie włączona) dokłada połączenia między materiałami z tego samego zgłoszenia (`case_id`, np. reklama i strony docelowe). Identyfikator kampanii jest stały: `K-<najmniejszy id członka>`, a pojedynczy materiał to `N-<id>`.

Przy więcej niż 40 materiałach porównywane są tylko pary kandydatów z indeksu odwrotnego: wspólne wartości cech o wadze ≥ 0,4, pasma MinHash LSH i segmenty pHash. Na mniejszych zbiorach porównywane są wszystkie pary. Test sprawdza, że na zbiorze 56 materiałów oba sposoby dają identyczne kampanie.

## 7. Przypisanie nowego materiału

1. Materiał bez żadnej dostępnej cechy dostaje status "za mało danych".
2. Dla każdej kampanii brane jest najlepsze porównanie z jej członkami. Wygrywa kampania z połączeniem spełniającym regułę z sekcji 5.
3. Brak takiej kampanii oznacza "nowy wzorzec" z powodem (wynik poniżej progu albo brak uzasadnienia).
4. Gdy druga kampania też spełnia regułę, a różnica wyników jest mniejsza niż 0,05, przypisanie zostaje, ale uzasadnienie ostrzega, że materiał może łączyć obie kampanie.
5. Kampania z jednym członkiem jest pełnoprawnym celem przypisania.

## 8. Interpretowalność

Każda krawędź ma: przesłanki z wkładem (cecha, grupa, waga, zgodność, wartości po obu stronach, opis po polsku), przesłanki przeciw (ważne cechy, które się nie zgadzają), braki danych z powodem, podstawę decyzji i kontrprzykład (jakie przesłanki trzeba by usunąć, żeby rozdzielić materiały, albo jakiego wkładu brakuje do połączenia). Interfejs pokazuje także wzór wyniku.

## 9. Niepełne dane

Martwa strona, sam plik HAR, sam zrzut lub samo wideo dają mniej cech, a nie błąd. Materiał bez żadnej cechy dostaje status "za mało danych" i nie jest łączony z niczym. Uszkodzone pliki są pomijane, a brakująca zależność opcjonalna daje jawny brak.

## 10. Ocena

`make eval` liczy na etykietach z `data/labels/`:
- metryki par (precyzja, pokrycie, F1, ARI) i listę fałszywych połączeń (test "nie łącz") dla czterech konfiguracji: `features` i `groups`, z łączeniem przypadków i bez,
- `eval/holdout.py`: symulację ukrytego zbioru metodą leave-one-case-out, czyli usuwa przypadek, grupuje resztę i przypisuje usunięte materiały (trafność, precyzja przypisań, poprawność "nowego wzorca"),
- `eval/variants.py`: warianty każdego materiału (duplikat, okrojenie, usunięcie grupy, tylko jedna grupa) i miarę odporności,
- `eval/synthetic.py`: korpus syntetyczny z "wabikami" (kampanie dzielące osobę publiczną i obraz stockowy), działający bez danych organizatora,
- ablację grup cech i test duplikatu (materiał z cechami musi połączyć się z własną kopią).

Raport zbiorczy: `data/cache/eval_report.json`.

### Wyniki

Dane organizatora: 14 materiałów, 10 przypadków, wstępne etykiety `data/labels/labels.json` (A = 1, 2, 3; B = 48, 61; pozostałe przypadki pojedyncze).

| Konfiguracja | Precyzja par | Pokrycie par | ARI | Holdout: trafność | Holdout: fałszywe |
|---|---|---|---|---|---|
| tylko treść (przed cechami infrastruktury i szablonu) | 1,00 | 0,21 | 0,32 | 0,71 | 0 |
| + infrastruktura i szablon, wagi domyślne grupy | 0,45 | 0,71 | 0,45 | 0,43 | 6 |
| + wagi per cecha, zestaw narzędzi nie łączy | 0,77 | 0,71 | 0,70 | 0,79 | 1 |
| + komentarze HTML jako nakładanie zbiorów | 1,00 | 0,71 | 0,81 | 0,86 | 0 |
| + łączenie materiałów z jednego przypadku (domyślne) | **1,00** | **1,00** | **1,00** | 0,86 | 0 |
| jak wyżej, ale zestaw narzędzi traktowany jak kampania | 0,48 | 1,00 | 0,56 | 0,50 | 5 |

Wynik jest stały dla progów 0,4–0,9, bo decyduje reguła uzasadnienia, a nie próg. Tryby `features` i `groups` dają ten sam wynik. Ablacja grup (precyzja 1,00, pokrycie 0,71): bez `infra` pokrycie spada do 0,21, a bez `text`, `visual`, `person` lub `template` wynik się nie zmienia. Na tym zbiorze kampanie wyznacza infrastruktura, a cechy treści potwierdzają połączenia i są potrzebne dla materiałów bez HAR.

Uwagi o rzetelności wyniku:
- Zbiór ma 10 przypadków, a etykiety są wstępne. Dwie zmiany wag wynikają z analizy konkretnych fałszywych połączeń na tych samych danych, więc wynik 1,00 jest optymistyczny. Wiarygodniejsze są holdout, korpus syntetyczny z wabikami (precyzja 1,00, pokrycie 0,92) i warianty (zero przypisań do obcej kampanii).
- Przy niepełnych danych (brak html w dwóch przypadkach) trafność holdoutu spada do 0,79, nadal bez fałszywych przypisań.
- Holdout nie trafia reklamy w przypadku 61 (sam obraz, krótki tekst z OCR ma za małe nakładanie z narracją strony), a poza regułą tego samego przypadku nie łączy się ona ze stroną docelową.

## 11. Biblioteki reklam i odświeżanie

Z biblioteki reklam Meta (wymaga tokenu) pobierane są wyłącznie metadane reklam: tekst, nazwa strony reklamodawcy i domena docelowa z podpisu. Każda reklama staje się materiałem z cechami tekstu i infrastruktury (konto reklamodawcy, domena), a skrypt odświeżania (`make refresh`, w trybie ciągłym usługa `refresher`) przypisuje nowe reklamy do kampanii albo oznacza je jako nowy wzorzec i zapisuje wynik w bazie. Bez tokenu funkcja jest jawnie niedostępna.
