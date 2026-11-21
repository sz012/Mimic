# Źródła danych i modeli: treść, obraz, osoby

| Składnik | Źródło | Licencja | Ograniczenia |
|---|---|---|---|
| Dane organizatora | `data/raw/` (NASK, HackNation 2026) | do użytku w zadaniu, nie publikować | 10 przypadków, parsowane statycznie |
| MinHash | biblioteka `datasketch` | MIT | sygnatura przybliża Jaccarda (128 permutacji) |
| pHash, dHash | biblioteka `ImageHash` | BSD-2-Clause | wrażliwe na mocne kadrowanie i nakładki |
| Klatki wideo | `opencv-python-headless` (extra `video`) | Apache-2.0 | kodeki zależne od kompilacji OpenCV |
| OCR | `rapidocr-onnxruntime` (extra `ocr`), modele PP-OCR (PaddleOCR) w ONNX dołączone do pakietu | Apache-2.0 | model rozpoznawania chińsko-angielski: polskie znaki diakrytyczne bywają gubione, dlatego tekst jest porównywany bez diakrytyków |
| Środowisko ONNX | `onnxruntime` | MIT | CPU, ok. 0.5–2 s na obraz, wyniki w pamięci podręcznej |
| Baza osób publicznych | `data/refs/persons.json`, lista nazwisk przygotowana ręcznie na podstawie publicznych ostrzeżeń o oszustwach z wizerunkiem znanych osób | tylko nazwiska, bez obrazów i danych biometrycznych | lista niepełna; nowe osoby dopisuje się w pliku |
| Twarze | nie używane (InsightFace wymaga modelu ok. 300 MB i obrazów referencyjnych) | — | `person.faces` jest jawnym brakiem |
