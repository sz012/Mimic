# Decyzje projektowe

Format: decyzja, powód. Data wszystkich wpisów: 2026-11-21, o ile nie zapisano inaczej.

- **Python 3.12, uv, `uv.lock`.** Powtarzalne środowisko lokalnie i w Dockerze.
- **SQLite, graf w pamięci (NetworkX po stronie silnika, D3 w interfejsie).** Najmniej infrastruktury przy pełnym przepływie od początku do końca. Neo4j odłożone.
- **Materiał to jedna strona, nie cały folder.** Przypadek bywa kilkoma stronami (reklama i strony docelowe). Identyfikator to ścieżka katalogu i jest niezmienny, bo etykiety się do niego odwołują.
- **Parsowanie wyłącznie statyczne.** Nigdy nie wykonujemy skryptów stron oszustów i domyślnie ich nie pobieramy. Adres URL wpisany w interfejsie daje tylko analizę domeny, chyba że ustawiono `MIMIC_ALLOW_FETCH=1`.
- **Wzbogacenie metadanymi domen jest opcjonalne** (`MIMIC_ENRICH=1`). Demo ma działać bez sieci, a błąd sieci daje jawny brak cechy z powodem.
- **Brak danych to jawny brak, nie zero.** Brak cechy nie obniża wyniku, a w uzasadnieniu pojawia się jako "brak danych" z powodem.
- **Wynik łączenia: `1 - Π(1 - waga × zgodność)`.** Niezależne dowody wzmacniają się, a pojedyncza słaba cecha nie wystarcza do połączenia. Każda krawędź niesie listę przesłanek.
- **Precyzja przed pokryciem.** Ukryty zbiór sprawdza, czy nie łączymy rzeczy niepowiązanych, więc próg i wagi stroi się na etykietach tak, aby najpierw nie było fałszywych połączeń.
- **Ślady platformy a ślady operatora.** Wspólna favikona lub endpointy konstruktora stron dowodzą tej samej platformy, a nie tej samej kampanii. Identyfikatory trackerów, kampanii i domeny to ślady operatora i mają większą wagę.
- **Odfiltrowanie szumu infrastruktury.** Adresy IP z pul CDN, powszechne hosty publiczne i identyfikatory o niskiej entropii nie są cechami, bo łączyłyby niepowiązane strony.
- **Wrażliwe parametry (`key`, `token`, `access_token`) zapisujemy jako skrót.** Zachowują wartość porównawczą bez przechowywania sekretów.
- **Etykiety na poziomie przypadku z możliwością nadpisania dla materiału.** Prosty zapis, a wyjątki są możliwe.
- **Ciężkie zależności jako opcjonalne grupy** (`video`, `ocr`, `faces`), instalowane w obrazie przez `MIMIC_EXTRAS` (domyślnie `video,ocr`). Aplikacja uruchamia się bez nich.
- **Połączenie wymaga uzasadnienia, nie tylko progu.** Krawędź musi mieć twardą przesłankę (identyfikator, domena, dokładny duplikat), co najmniej dwie niezależne grupy dowodów albo jedną bardzo silną przesłankę. Wynik ≥ 0,6 sam nie wystarcza.
- **Wspólny zestaw narzędzi nie łączy kampanii.** Ta sama favikona i ścieżki backendu konstruktora stron są pokazywane w uzasadnieniu, ale materiały łączą się dopiero przy dowodzie z treści, szablonu lub identyfikatorów.
- **Materiały z jednego zgłoszenia (`case_id`) tworzą jedną kampanię.** Reklama i jej strony docelowe są jednym incydentem, więc `case_links` jest domyślnie włączone.
- **Identyfikator kampanii jest stały** (`K-<najmniejszy id członka>`), żeby nie zmieniał się po dodaniu materiałów.
- **Ocena symuluje ukryty zbiór** (holdout, warianty z brakami danych, korpus syntetyczny z wabikami), bo wynik na 10 przypadkach z wstępnymi etykietami jest optymistyczny.
- **Twarze porównujemy także między samymi materiałami.** `person.face_vectors` nie wymaga bazy referencyjnej, więc łączy materiały z tą samą osobą także wtedy, gdy nie wiemy, kim jest. Dzięki temu cecha działa na ukrytym zbiorze bez publikowania czyjegokolwiek wizerunku. Baza referencyjna (`person.faces`) służy tylko do nazwania osoby w demo.
- **Rozpoznawanie twarzy tylko lokalnie, na potrzeby demo.** Mentorzy dopuścili użycie wizerunków osób publicznych. Obrazy referencyjne i wektory zostają poza repozytorium (`data/refs/images/`, `data/cache/`), cecha jest opcjonalna (dodatek `faces`), a bez niej `person.faces` jest jawnym brakiem. Twarz jest dowodem pomocniczym: grupa `person` nie jest niezależnym źródłem przy łączeniu.
- **Główny interfejs to React z API (FastAPI), Streamlit zostaje zapasowy.** Zadanie nie ocenia estetyki, ale demo na kamerze wymaga czytelnej, szybkiej sceny. Silnik nie zależy od interfejsu, więc oba korzystają z tych samych modułów.
- **Biblioteka reklam ma tryb weryfikacji.** Token Meta jest wymagany do działania na żywo, a jury ma móc sprawdzić przepływ bez niego, więc `MIMIC_ADLIB_FIXTURE=1` używa wbudowanego, syntetycznego zestawu reklam w formacie odpowiedzi API.
