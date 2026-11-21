# Cechy treści, obrazu i osób

Wszystkie cechy liczone są statycznie z zapisanych plików (HTML, HAR, obrazy, wideo, metadane). Strony oszustów nie są otwierane ani pobierane, ich JavaScript nie jest wykonywany. Każda cecha ma wartość, pewność i źródło; brak danych to jawny brak (`Feature.missing`) z powodem.

## Tekst (`engine/features/text.py`)
Źródła w kolejności: zapisany HTML; gdy go nie ma, największa odpowiedź `text/html` z HAR; metadane wideo (`info.json`: tytuł, opis); gdy brak strony, tekst z OCR obrazów i klatek wideo. Tekst jest normalizowany: małe litery, usunięte polskie znaki diakrytyczne (odporność na OCR i różne kodowania), bez słów funkcyjnych.

| Cecha | Wartość |
|---|---|
| `text.narrative` | MinHash (128 permutacji) 3-gramów słów z akapitów `<p>`, `<li>`, nagłówków |
| `text.exact` | SHA-1 znormalizowanej narracji (duplikaty) |
| `text.title` | słowa tytułu |
| `text.keywords` | 30 najczęstszych słów |
| `text.entities` | nazwy własne i produkty (sekwencje wielkich liter, powtarzające się słowa) |
| `text.identifiers` | e-mail, telefon, uchwyty komunikatorów (t.me, wa.me), IBAN |
| `text.prices` | kwoty z walutą |
| `text.topic` | temat ze słownika: inwestycje, zdrowie, hazard, zakupy, wiadomości |
| `text.ocr` | MinHash 5-gramów znaków (bez spacji i diakrytyków) tekstu odczytanego z obrazów i klatek wideo; model OCR skleja polskie słowa, więc porównanie na znakach jest odporniejsze niż na słowach |

## Obraz (`engine/features/visual.py`, `media.py`)
- `visual.screenshot`: pHash i dHash zrzutu oraz pHash jego górnej części (pierwszy ekran).
- `visual.assets`: pHash obrazów z katalogów zasobów strony (`_files`, `resources`, rodzaj `assets`), z pominięciem ikon (< 80 px) i jednolitych obrazów; gdy ich brak, obrazy zapisane w HAR.
- `visual.video`: klatki kluczowe wideo (próbkowanie co 1 s; klatka jest zapisywana przy zmianie sceny, czyli odległości pHash ≥ 10, albo co najmniej raz na 10 s dla nagrań ekranu z powolnym przewijaniem; do 30 klatek), zapis w `data/cache/frames/`.
- `visual.exact`: SHA-1 plików zrzutów i wideo.

## OCR (`engine/features/ocr.py`)
RapidOCR (modele PP-OCR w ONNX, bez binarek systemowych) czyta zrzuty, klatki kluczowe i do 6 największych obrazów strony (bok ≥ 300 px). Linie z pewnością < 0.6 są odrzucane. Wyniki są w pamięci podręcznej `data/cache/ocr/` według skrótu pliku. Tekst z OCR zasila narrację, słowa kluczowe, nazwy i osoby tylko wtedy, gdy materiał nie ma strony (sama reklama, samo wideo); zawsze trafia do `text.ocr`.

## Osoby (`engine/features/person.py`)
- `person.names`: osoby publiczne z bazy `data/refs/persons.json` (nazwa, aliasy) wykryte w tekście lub OCR, z obsługą odmiany nazwisk (rdzeń nazwiska) i wymogiem imienia przy krótkich nazwiskach. Liczona, gdy osoba pada co najmniej 2 razy.
- `person.faces`: jawny brak. Dopasowanie twarzy wymaga modelu (InsightFace, ok. 300 MB) i obrazów referencyjnych z jasną licencją; nie weszło do tej wersji.

## Zależności opcjonalne
`video` (OpenCV) i `ocr` (RapidOCR) są dodatkami (`uv sync --extra video --extra ocr`), importowanymi leniwie. Bez nich aplikacja działa, a odpowiednie cechy są jawnym brakiem z nazwą brakującej zależności.

## Wynik na danych organizatora
Klatki kluczowe: 30 (przypadek 5), 30 (14), 17 (47). Tekst z OCR jest dostępny dla wszystkich materiałów z obrazami, w tym reklamy w przypadku 61. Przypadek 5 (samo wideo) ma narrację z metadanych i OCR. Na tymczasowych etykietach nowe cechy nie zmieniają wyniku grupowania (precyzja i pokrycie par 1.00); OCR dodatkowo potwierdza połączenie 1–2 (Jaccard 0.81). Reklama w przypadku 61 nadal nie łączy się ze stroną docelową poza regułą tego samego przypadku: krótki tekst reklamy (ok. 100 liter) ma za małe nakładanie z długą narracją strony.
