# data/

Dane organizatora są objęte zasadą: tylko na potrzeby zadania, nie publikować. Nie trafiają do gita.

| Ścieżka | W gicie | Zawartość |
|---|---|---|
| `data/raw/<id>/` | nie | przypadki organizatora (1, 2, 3, 5, 10, 14, 36, 47, 48, 61), jeden folder na przypadek, oryginalne nazwy i zawartość, tylko do odczytu |
| `data/cache/` | nie | cechy, baza SQLite, wyniki wzbogacenia; do odtworzenia z `data/raw/` |
| `data/refs/persons.json` | tak | nazwiska osób publicznych do wyszukiwania w tekście (bez obrazów) |
| `data/refs/images/<imię nazwisko>/` | nie | zdjęcia referencyjne do dopasowania twarzy, tylko lokalnie, na potrzeby demo; zalecany plik `ZRODLA.txt` ze źródłem i licencją zdjęć |
| `data/labels/labels.json` | tak | przypisanie przypadków do kampanii: tylko identyfikatory i etykiety |

## Pierwsze uruchomienie po `git clone`

Skopiuj foldery przypadków do `data/raw/`, tak aby powstały ścieżki `data/raw/1`, `data/raw/2` itd. Dane dostaje się od organizatorów, nie przez GitHub.

```bash
make ingest
```

Polecenie odkrywa materiały, liczy cechy i zapisuje je w `data/cache/mimic.sqlite`.

## Układ przypadku

Folder przypadku zawiera jedną lub kilka stron. Materiałem jest każdy katalog z plikami html, har, obrazami, wideo, plikami json lub adresem. Katalogi `*_files` i `resources` to zasoby strony i nie są osobnymi materiałami. Identyfikator materiału to ścieżka katalogu względem `data/raw/`, np. `61/strona_2`.

## Etykiety

`data/labels/labels.json` to słownik `identyfikator: etykieta kampanii`. Klucz może wskazywać cały przypadek (`"61": "B"`) albo pojedynczy materiał (`"61/strona_2": "B"`), a wpis dla materiału ma pierwszeństwo. Walidacja: `make labels-check`.

## Uwaga bezpieczeństwa

To strony oszustów. Nie otwieraj ich w zwykłej przeglądarce i nie wykonuj ich skryptów.
