# Historia zmian

## 2026-10-15
- Import bazy: nowy tryb **D — aktualizacja z zachowaniem postępu nauki** (domyślny): nowe pytania, nadpisanie treści/klucza po ID, wyjaśnienia z pliku; postęp i „Błąd” bez zmian (testy + próba na kopii prawdziwej bazy). Aplikacja nie przebudowana.
- Weryfikacja użytkownika, część 2: klucze i wyjaśnienia 5 pytań, +4 nowe (ID 3554–3557), baza 3382 wierszy, 14 wierszy nadal bez rozstrzygnięcia (pomarańczowe). Losowa kolejność odpowiedzi (domyślnie wyłączona), skróty klawiszowe 1–9/spacja, „Wyjaśnij” z cache bez klucza API, repo git.

## 2026-10-14
- Wdrożono weryfikację użytkownika: klucze i wyjaśnienia 105 pytań, +19 nowych pytań (ID 3535–3553), zdjęto pomarańczowe oznaczenie ze 129 wierszy. Baza: 3378 wierszy.
- Naprawa startu na Windows 8.1 (błąd `winsqlite3.dll`, kod 126): `sqlite3.dll` dołączana do buildu Windows (`app/windows/third_party`, `CMakeLists.txt`).
- Wyjaśnienia AI (rój 3×Haiku 5.5) wpisane do `explanation_cache` dla 3078 wierszy z pełnym konsensusem; 148 wierszy (124 unikalne pytania) bez konsensusu oznaczonych tymczasowo pomarańczowym tłem treści (`ai_disputed`). Szczegóły: AGENTS.md 6.3.

## 2026-10-13 (bez zmiany wersji aplikacji, 2.7.0)
- **PDF „Pytania super nowe”** (Studocu, egzamin dyplomowy KZW – Manewrowanie): 24 pytania testowe zweryfikowane 2× Sonnet 5.5 + GPT 6.1 Sol (`tools/ai_audit/super_nowe_verify.py`); 8 HIGH już było w bazie, **dodano 6** (ID 3419–3424, Master, `exam_scan`). Baza: 3249 wierszy.
  Kopie: `Documents\memonic_app.db.bak_super_nowe_20261013_083015`, `data\memonic_app_seed.db.bak_super_nowe_20261013_083015`; log: `review/Super_nowe/wdrozenie_log.json`.
- Analiza statystyczna „najczęściej poprawnych wartości” (`review/Statystyka/`): przewaga nad losowym wyborem zbyt mała (43% vs 32%), bez zmian w aplikacji.
- Paczki „Baza Pytan Apka-2.4” na pulpicie NIE zawierają tych 6 pytań (przebudowa: `tools\build-release-clean.ps1`).

## 2026-10-12 (bez zmiany wersji aplikacji, 2.7.0)
- **Pytania ze skanów egzaminów:** 462 pytania z testów 2017–2026 (partia 1: 60, partia 2: 402) przepisane lokalnie, zweryfikowane rojem modeli (Haiku 5.5 → Sonnet 5.5 + GPT 6.1 Sol, `tools/ai_audit/exam_verify*.py`);
  wdrożono **201 pytań (HIGH)** do kategorii Master w bazie użytkownika i w seedzie (ID 3193–3418 z lukami, `ai_verified = exam_scan:…`); usunięto 25 wierszy jako duplikaty. Baza: 3243 wiersze.
  Kopie: `Documents\memonic_app.db.bak_exam_high_20261012_161129`, `data\memonic_app_seed.db.bak_exam_high_20261012_161129`; log: `review/Weryfikacja_2026-10-12/wdrozenie_log.json`.
- Paczki „Baza Pytan Apka-2.4” (APK + ZIP wersji przenośnej PC) z czystą bazą startową (0 kart, bez cache AI, bez klucza API): `tools/build-release-clean.ps1`.

## 2.7 (2026-10-09)
- Powiązania powtórzonych pytań o nieidentycznym zapisie (`dup_links`), wykrywane rojem modeli Haiku 5.5 na kopii bazy (`tools/ai_audit/dup_swarm.py`); grupy uwzględniane też w losowaniu TESTU. Wdrożono 168 powiązań (86 grup; unikalnych pytań 2225 → 2146) w bazie użytkownika i w seedzie.
- Naprawa błędu w angielskim arkuszu: pytanie o pozycję po przemieszczeniu o 480 NM (ID 1069, 1121, 1138, 1152, 1166, 1194, 1206) miało „southwards”, a polska wersja urzędowa (ID 11) i klucz C oznaczają „na północ” — tekst poprawiony na „northwards”, pytania przywrócone do nauki. Log: `tools/ai_audit/history/logs/fix_480nm_northwards_log.json`.

## 2.6 (2026-10-09)
- **Synchronizacja powtórzonych pytań:** pytania o tej samej treści (inne ID/dział) mają wspólny harmonogram nauki — nie wracają tego samego dnia pod innym numerem (np. „statek o ograniczonej zdolności manewrowej”: ID 1721, 1729, 2490);
  statystyki, cel dzienny i prognoza liczą unikalne pytania (3035 wierszy = 2225 pytań). Schemat v8 (`questions.dup_group`), wyrównanie postępu kopii przy starcie.

## 2.5 (2026-10-09)
- **Cel dzienny wg Twojego tempa:** „Cel na dziś” liczony z rzeczywistego tempa nauki w wybranym dziale (koszt opanowania w odpowiedziach z dziennika, a nie stały bufor 1,25)
  i terminu egzaminu − 3 dni; dodane: Twoje tempo (odpowiedzi i opanowane pytania dziennie), prognoza daty opanowania i ocena, czy zdążysz.
- Schemat v7: `review_log.streak_before/streak_after`; historia odpowiedzi z v6 uzupełniona wstecz (odtworzone serie zgodne z bazą 1156/1156 pytań).

## 2.4 (2026-10-09)
- **Odłóż pytanie** (zielony kwadratowy przycisk z klepsydrą pod „Wyjaśnij”): odłożenie na 3, 6 lub 12 dni nadpisuje harmonogram nauki dla pytań, które użytkownik zna na pewno.

## 2.3.1 (2026-10-09)
- **Wersja przenośna PC** (folder + ZIP, `tools/build-portable.ps1`): osobna baza i ustawienia w `user_data` obok exe (tryb włączany plikiem `portable.flag`), start z czystą bazą nauki,
  bez klucza API; zwykła instalacja i jej baza nie są zmieniane. Bez zmian w funkcjach nauki.

## 2.3 (2026-10-08)
- **12 pytań Master o klasyfikacji akwenów manewrowych** (akwen nieograniczony, płytkowodzie, pogłębiony tor wodny, kanał; podział PIANC H/T; efekt kanałowy; wpływ płytkowodzia na cyrkulację; 4 zadania „rozpoznaj akwen”). Kontrola AI: 129/129 autorskich bez uwag.
- **27 kolejnych pytań Master** (autorskich): 4 fazy planowania podróży (A.893), UKC, osiadanie i wzór Barrassa (z przykładami liczbowymi), Letter of Protest, Kodeks Polarny (obszar, data, kategorie A–C, Polar Ship Certificate), klasy IACS PC1–PC7. Kontrola AI: 117/117 autorskich bez uwag.
- **TEST bez powtórzeń:** pytania są wybierane po treści (duplikaty w bazie — inne ID/poziomy/wersje OCR — nie trafiają do jednego testu); test sprawdzony na 20 losowaniach.
- Baza: naprawiono urwane/pomieszane treści pytań z PDF (Master: ID 1622, 1626, 1631, 1655, 1693, 1717, 1742, 1664, 1705, 1768, 1802; Pokład: 733, 2078), usunięto duplikat ID 1794 („się na:”),
  przywrócono do nauki 5 pytań ukrytych tylko z powodu urwanego tekstu (1622, 1626, 1631, 1693, 1742). Log: `tools/ai_audit/history/logs/fix_truncated_stems_log.json`.
- **TEST** (pastelowy pomarańcz): 105 pytań (50% Master / 20% Angielski / 30% Pokład, do zmiany w Ustawieniach), zaliczenie 70; błędne odpowiedzi trafiają od razu do powtórek w swoim dziale;
  wynik z podziałem na pule i lista błędów; ostatni wynik na ekranie głównym.
- Ekran główny przewijany (przy dodanych elementach nie mieścił się na niskich ekranach telefonu).

## 2.2 (2026-10-06) + dodatki 2026-10-07/08
- Master: usunięto 3 wadliwe duplikaty: ID 1657 (pytanie 45 ECDIS z wariantami pytania 46 — właściwe jest ID 1987), ID 1673 i 1677 („AIS nie ma zastosowania” — ukryte, z pomieszanym tekstem; właściwe jest ID 1989). Klucze 1987 i 1989 zgodne z PDF. Log: `history/logs/dedup_ais_ecdis_log.json`.
- Usunięto 2 duplikaty pytania Master ID 1978 (ID 1969, 1970; w 1970 klucz wskazywał błędny wariant „do zawinięcia statku do pierwszego portu”). Poprawna odp. wg PDF: „…dogodnego dla armatora, jednak nie dłużej niż 6 tygodni”. Log: `tools/ai_audit/history/logs/dedup_1978_log.json`.
- **77 kolejnych pytań Master** (autorskich): FAL 1–7, laytime, akredytywa, dokumenty portowe, znaki IALA (6, z rysunkami), COLREG (22 prawidła/definicje), UNCLOS (EEZ, morze terytorialne, strefa przyległa), front zokludowany, żyrokompas, załączniki MARPOL I–VI, sygnały mgłowe (13), znaki dzienne (8, z rysunkami), OWS, obszary specjalne.
  Rysunki IALA i znaków dziennych generowane programowo (`tools/ai_audit/history/make_nav_images.py`). Kontrola AI (L1+L2 z obrazami): 90/90 bez uwag.
- **13 nowych pytań Master** (autorskich, na bazie dokumentów morskich: pływy, GT/NT, GM, ECDIS, konosament, indos, dyspasza, kwit sternika, manifest) — `review/Nowe_pytania_Master_2026-10-06.md`, `ai_verified=ai_authored:2026-10-06`.
- **Nowe pytania w sesji:** losowe, niewidziane pytanie co 3–8 odpowiedzi (dynamicznie wg skuteczności), także gdy powtórek jest dużo.
- **Termin egzaminu** (Ustawienia) + **pasek opanowania** na ekranie głównym (znane = poprawne odpowiedzi 3 dni nauki z rzędu) + **dzienny cel** (do egzaminu − 3 dni);
  przy ustawionym terminie interwały FSRS są skracane, by seria zdążyła się zamknąć.
- **„Trudne” pytania** (często błędne): etykieta, licznik, pierwszeństwo wśród zaległych, odstęp ≤ 3 dni.
- Nagłówek nauki `X/Y/Z` (sesja: wszystkie / poprawne / błędne).
- Schemat v6: `review_log`, `srs_cards.streak_days/last_good_day/hard` (migracja idempotentna; seria istniejących kart szacowana).

## 2.1 (2026-10-06)
- **Obrazki w pytaniach** (schemat v5, kolumna `image_path`, `assets/question_images/`): widget skalujący się na PC i telefon, powiększenie po dotknięciu;
  „Wyjaśnij” wyłączone dla pytań z obrazkiem; import (B/C) rozróżnia pytania o tej samej treści po obrazku.
- Pilotaż: **F1-P6 Łączność morska** (flagi Międzynarodowego Kodu Sygnałowego) — PL operacyjny 25 pytań + EN 25 pytań; baza 2853 pytań
  (49 dodanych, 1 uzupełnione, 1 usunięty błędny duplikat EN bez obrazka). Narzędzia: `tools/pdf_extraction/figures.py`, `apply_figures.py`.
- Etap 2: pozostałe arkusze PDF (Meteorologia, Ratownictwo, Bezpieczeństwo nawigacji — światła statków, Budowa i stateczność, Przewozy; PL operacyjny/zarządzania + EN):
  66 pytań dodanych, 3 istniejące uzupełnione obrazkiem; baza **2919 pytań**, obrazki 4,1 MB (89 plików).

## 2.0 (2026-10-05)
_Poprawka po pierwszym teście:_ tryb „Powtórz zaplanowane (24 h)” zapętlał się na 2 pytaniach (wczesna powtórka zostawiała kartę w oknie 24 h) — zaliczone karty nie wracają w sesji.

**Aplikacja**
- Algorytm nauki **FSRS-6** zamiast SM-2: błędne pytania wracają w tej samej sesji (1 min, 10 min), potem następnego dnia od 4:00;
  „Nie wiem”; etykieta „Powtórka: …”; statystyki „do powtórki teraz” / „zaplanowane 24 h”; tryb „Powtórz zaplanowane (24 h)”;
  suwak docelowej retencji. Migracja bazy v3→v4 zachowuje dotychczasowy postęp.
- „Wyjaśnij”: modele GPT 6.1 Sol (Medium) i Claude Sonnet 5.5 (Medium); weryfikacja klucza (nagłówek ustala kod, nie model);
  priorytet dokumentów morskich (Kodeks morski, STCW, COLREG, MARPOL, ISM, LSA, FFE, MLC, UNCLOS, ISPS, IMDG, SOLAS); poprawka „pierwsze kliknięcie nic nie robi”.
- Ustawienia → Baza danych: **eksport** i **import** (A pełny / B statusy / C brakujące pytania) z potwierdzeniem.
- Wersja 2.0 widoczna w menu i w Ustawieniach.

**Baza (2805 pytań)**
- Master: test Sol+Sonnet (369 pytań), dodanie 141 brakujących pytań z PDF, 66 pytań wdrożonych wg arkusza PDF.
- Pokład: dodano 825 brakujących pytań z PDF (parser v1 gubił pytania przechodzące przez granicę strony).
- Przenumerowanie ID (1…); kolumna `ai_verified` (ślad kontroli).
- Kaskadowy przegląd AI (Luna → DeepSeek V4.1 Flash → Sonnet 5.5) całego Pokładu i Angielskiego (2438 pytań, ≈ 2,2 USD):
  poprawiono 124 usterki tekstu, usunięto 104 pytania z rysunkiem, 38 pytań z wątpliwym kluczem czeka na decyzję (`review/DO_PRZEGLADU.xlsx`).

**Projekt**
- Nowy układ folderów (`app/`, `sources/`, `tools/`, `review/`, `data/`, `android/`, `docs/`), kompletny `AGENTS.md`.
- Własny Flutter SDK w `.tools/flutter`, build przez dysk `Q:`; skrypt APK `android/build-apk.ps1`.

## RC1 (maj 2026)
- Android: APK sideload z wbudowaną bazą (369 Master, Pokład, Angielski), SM-2, AI „Wyjaśnij” (OpenRouter).

## 1.0 (maj 2026)
- Pipeline PDF → SQLite (parsery, Vision, konsensus modeli), aplikacja Flutter na Windows (SM-2, burger menu, Baza Danych, dark mode).
