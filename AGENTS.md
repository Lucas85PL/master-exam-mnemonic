# Master Exam Mnemonic 2.0

Aplikacja do nauki pytań testowych na egzaminy morskie (Flutter: Windows + Android) wraz z narzędziami do budowy
i kontroli jakości bazy pytań. **Priorytetem jest klucz odpowiedzi z oficjalnych arkuszy Urzędu Morskiego (PDF)** —
AI służy tylko do wskazywania podejrzanych miejsc, nigdy do automatycznej zmiany klucza.

> Stan na **2026-10-13** · wersja aplikacji **2.7.0 (build 11)** · baza **3249 wierszy** (w tym 207 pytań ze skanów/arkuszy egzaminów 2017–2026; liczbę unikalnych pytań przelicza start aplikacji, przed 2026-10-12: 2146 z 3042) · schemat bazy **v8** (FSRS, obrazki, dziennik odpowiedzi z serią, grupy powtórzeń `dup_group`, `dup_links`).
> Stara wersja projektu (folder roboczy sprzed porządków) istnieje jako backup:
> `C:\Users\Lukasz\Desktop\Dev\Master Exam Mnemonic` — jeśli czegoś brakuje tutaj, szukaj tam (patrz „Stary folder”).

---

## 1. Zakres i dane

| Kategoria w aplikacji | Pytań | Źródło (PDF Urzędu Morskiego) |
|---|---|---|
| **Master** (Kapitan żeglugi wielkiej) | 840 (w tym 129 autorskich pytań AI, `ai_authored`, i 207 pytań ze skanów egzaminów, `exam_scan`) | `sources/pdf_urzad/Master/` (6 plików, 2025) |
| **Pokład** (Dział pokładowy) | 1853 (w tym 65 z obrazkami) | `sources/pdf_urzad/Pokład_Dział/` — poziom operacyjny (Oficer wachtowy, 988) i zarządzania (Starszy oficer pokładowy, 804) |
| **Angielski** | 556 (w tym 54 z obrazkami) | `sources/pdf_urzad/Angielski/` (angielskie wersje arkuszy poziomu operacyjnego) |

Wszystkie pytania są testowe (A/B/C, czasem D), `review_status = 'ok'`. Pytania wymagające rysunku/zdjęcia były usunięte (105),
a od 2.1 wracają **z obrazkami** (patrz 4.4): Łączność morska (flagi MKS, 50) + wszystkie pozostałe arkusze (69: światła statków, rysunki konstrukcji, symbole meteo, wykresy stateczności…).
Szczegóły historii zmian: `docs/CHANGELOG.md`.

Pytania Anki (Chief Officer) **nie** są częścią tej wersji (są tylko w starym folderze).

---

## 2. Struktura projektu

```
Master Exam Mnemonic 2.0/
├─ AGENTS.md                  ← ten plik
├─ Start.bat / Start-rebuild.bat / Build-APK.bat    ← uruchom / przebuduj Windows / zbuduj APK
├─ .env.example               ← wzór pliku .env (klucz OpenRouter dla narzędzi AI; .env NIE jest w projekcie)
├─ app/                       ← aplikacja Flutter (pakiet `memonic_app`)
│   ├─ lib/ test/ android/ windows/ assets/db/memonic_app_seed.db assets/question_images/ (obrazki pytań, ~4 MB)
│   ├─ run.ps1  scripts/flutter_env.ps1  Start*.bat
├─ android/                   ← build-apk.ps1 + README.txt (instalacja na telefonie)
├─ dist/                      ← APK (nazwa pliku zawsze Master-Exam-Mnemonic-2.0.apk — wersję sprawdzaj w aplikacji) oraz wersja przenośna PC (folder + ZIP)
├─ data/                      ← snapshot bazy użytkownika (backup postępu) + README
├─ review/                    ← DO_PRZEGLADU.xlsx (pytania czekające na decyzję) + restore_questions.py
├─ sources/pdf_urzad/         ← oryginalne arkusze PDF (Master, Pokład_Dział, Angielski)
├─ tools/
│   ├─ ai_audit/              ← FINALNY workflow kontroli jakości pytań (L1→L2→L3), dup_swarm.py (powtórzenia), history/ (jednorazowe poprawki, logi, generatory pytań autorskich)
│   ├─ pdf_extraction/        ← niezależna ekstrakcja pytań z PDF, rysunki z PDF (figures.py), porównanie z bazą
│   ├─ build-portable.ps1 + make_clean_seed.py ← wersja przenośna PC (czysta baza, osobne ustawienia)
│   └─ legacy_pipeline/       ← pierwsza wersja pipeline'u (parsery PDF, Vision, konsensus, GUI/review) — archiwum
├─ docs/                      ← CHANGELOG.md
└─ .tools/flutter/            ← Flutter SDK (kopia; ~2,3 GB; w .gitignore)
```

`.cache/` (Gradle, pub dla APK) powstaje przy pierwszym `Build-APK.bat`. `app/build/` i `.dart_tool/` generuje Flutter.

---

## 3. Uruchamianie, testy, budowanie

**Wymagania (Windows 11):**
- *Tryb dewelopera* włączony (symlinki dla pluginów Flutter): Ustawienia → Dla deweloperów.
- Visual Studio **Build Tools z obciążeniem „Programowanie aplikacji klasycznych w C++”** (flutter doctor ma pokazać `[√] Visual Studio`).
  Po aktualizacji Visual Studio usuń `app\build\windows` (stary cache CMake z poprzednim generatorem blokuje build).
- Android SDK (dla APK) — domyślnie z Android Studio. Internet przy pierwszym budowaniu APK.

**Komendy (z katalogu głównego):**
- `Start.bat` — uruchamia aplikację (jeśli nie ma builda Release, buduje go).
- `Start-rebuild.bat` — zamyka aplikację, przebudowuje Windows Release i uruchamia (po każdej zmianie kodu).
- `Build-APK.bat` — APK do `dist\Master-Exam-Mnemonic-2.0.apk` (patrz `android/README.txt`).
- `tools\build-portable.ps1` — **wersja przenośna PC** (folder + ZIP w `dist\Master-Exam-Mnemonic-<wersja>-PC`, patrz 4.7).
- Testy: `powershell -File app\run.ps1 -Action test` (74 testy: FSRS, kolejka, plan nauki, TEST, import/eksport, ustawienia portable, prompt AI, kolory…).
- Analiza: `Q:\app> . .\scripts\flutter_env.ps1; Invoke-MemonicFlutter analyze --no-pub lib test` (zostają tylko 3 stare uwagi `deprecated_member_use`).

**Dysk `Q:` (subst):** ścieżka projektu ma spacje, a build natywny na nich się wywala. `app/scripts/flutter_env.ps1`
(`Mount-ProjectDrive`) mapuje projekt na `Q:` i przemapowuje, jeśli `Q:` wskazuje gdzie indziej. Stara wersja używa `M:` —
nie wchodzą sobie w drogę. **Nie używaj Flutter SDK spoza `.tools\flutter`.**

**Uwagi z doświadczenia:** w PowerShell 5.1 nie dopisuj `2>&1` do natywnych poleceń (ostrzeżenia Kotlina na stderr
przerywają skrypt); gdy Gradle zgłasza uszkodzone cache — zatrzymaj demony (Java z `.cache\gradle`) i usuń `.cache\gradle\caches\jars-9`
oraz `…\transforms`.

---

## 4. Aplikacja (app/)

**Stos:** Flutter 3.44 · Riverpod · go_router · sqflite (+ffi na Windows) · sqlite3 (import) · file_picker · SharedPreferences.

**Funkcje:**
- **Nauka** (`features/study`): kolejka FSRS, odpowiedź A/B/C(D) z podświetleniem (zielony/czerwony, dark mode), przycisk **„Nie wiem”**
  (pokazuje odpowiedź, liczy się jak błąd), **„Błąd”** (ukrywa pytanie — `study_hidden=1`), **„Wyjaśnij”** (AI), „Dalej”,
  etykieta „Powtórka: za 10 min / jutro…”.
- **Ekran główny:** kategoria (All/Master/Pokład/Angielski), statystyki: do powtórki teraz / zaplanowane 24 h / nowe, przyciski
  „Start nauki” i „Powtórz zaplanowane (24 h)”.
- **Baza Danych:** lista z filtrami (kategoria, „Tylko Błąd”), edycja pytania (treść, warianty, klucz), przywracanie z „Błąd”.
- **Ustawienia:** tryb ciemny · docelowa retencja FSRS (80–97%, domyślnie 90%) · wyjaśnienia AI (przełącznik, model, klucz API) ·
  **eksport/import bazy** · numer wersji.

### 4.9 Synchronizacja powtórzonych pytań (od 2.6; `data/duplicate_groups.dart`, schemat v8)
- To samo pytanie bywa w bazie w kilku wierszach (3035 wierszy puli = **2225 unikalnych** pytań; 448 grup, 1260 wierszy). Klucz grupy: znormalizowane pytanie + warianty A–D + obrazek
  (bez ID, poziomu, działu i rodzaju cudzysłowu); kolumna `questions.dup_group` (hash, NULL = brak powtórzeń). Inny obrazek = inne pytanie.
- **Synchronizacja:** `saveSrs` i `recordAnswer` kopiują stan karty (FSRS, termin, seria, „trudne”, błędy) do wszystkich wierszy grupy — odpowiedź, odłożenie klepsydrą lub błąd w TEŚCIE jednego wiersza
  ustawia ten sam harmonogram w kopiach, więc pytanie nie wraca tego samego dnia pod innym ID. Dziennik odpowiedzi (`review_log`) zapisuje tylko faktycznie udzieloną odpowiedź.
- **Statystyki liczą unikalne pytania** (`QuestionRepository._grouped`): pula, nowe, do powtórki, znane, „trudne”, brakująca praca i cel dzienny.
- **Przy każdym starcie** (`AppDatabase.open`): `refresh` (przeliczenie grup po imporcie/edycji/nowych pytaniach) i `align` (wyrównanie postępu kopii: harmonogram z najnowszej powtórki, seria = najwyższa w grupie,
  „trudne”/błędy = maks.). Edycja pytania w Bazie Danych przelicza grupy. Znacznik „Błąd” (ukrycie) pozostaje per wiersz — treść jednej kopii może być uszkodzona.
- Pierwsze wyrównanie na bazie użytkownika (2026-10-09): 3035 → 2225 unikalnych; nowych 1826 → 1144; brakująca praca 7249 → 4964 jedn. serii. Kopia przed zmianą: `Documents\memonic_app.db.bak_before_dupsync_*`.
- **Powtórzenia o nieidentycznym zapisie (od 2.7; `tools/ai_audit/dup_swarm.py`, `apply_dup_links.py`, tabela `dup_links`):** dokładne porównanie nie łapie kopii różniących się OCR-em, interpunkcją czy skrótem.
  `dup_swarm.py --db <KOPIA bazy>` buduje pary-kandydatów (trigramy treści i wariantów; ~350 par na 2108 unikalnych treści), każdą parę ocenia **dwóch niezależnych sędziów Claude Haiku 5.5**
  (kolejność pary zamieniona; wymagane „to samo pytanie” ORAZ „ta sama poprawna odpowiedź”), a przy rozbieżności trzeci sędzia z doprecyzowanym promptem rozstrzyga (2 z 3). Koszt ≈ 0,15 USD.
  Wynik: `runs/dups_<tag>.json` i `review/Duplikaty_swarm_<tag>.xlsx`. `apply_dup_links.py <baza> <json> --apply` zapisuje powiązania `question_id → canonical_id` w `dup_links`
  (kopia bazy przed zapisem; nic nie jest usuwane, skasowanie wiersza cofa powiązanie); `DuplicateGroups.refresh` łączy je z grupami dokładnych duplikatów (union-find), więc kopie dzielą harmonogram nauki,
  a TEST nie losuje dwóch pytań z jednej grupy. Przebieg 2026-10-09 (`run1`): 93 pary potwierdzone → 86 grup (254 ID), 7 par odrzuconych po rozstrzygnięciu (różnice znaczeniowe: „tylko”, „na statkach morskich”…);
  unikalnych pytań w puli 2225 → 2146.
- TEST (4.6) dalej odrzuca duplikaty po treści; kopie pytań w różnych działach (Master / Pokład) pozostają w swoich pulach.

### 4.8 Odłóż pytanie — klepsydra (od 2.4; `StudyScreen._showSnoozeMenu`, `FsrsScheduler.snooze`)
- Po udzieleniu odpowiedzi pod „Wyjaśnij” pojawia się kwadratowy przycisk w pastelowej zieleni z klepsydrą (także przy pytaniach z obrazkiem, gdzie „Wyjaśnij” jest ukryte).
  Aktywny dopiero po zapisie oceny karty. Menu: **Odłóż na 3 / 6 / 12 dni**.
- Wybór **nadpisuje harmonogram FSRS** dla tego pytania: stan „powtórka”, termin = wybrana liczba dni od 4:00 rano, stabilność nie niższa niż liczba dni (kolejna powtórka wypada w terminie),
  kroki powtórek po błędzie (1/10 min) są anulowane. Historia (liczba ocen, błędy, seria „znane”, dziennik) nie jest zmieniana; limit egzaminowy interwału nie jest stosowany (decyzja użytkownika ma pierwszeństwo).
  Cel: „odbijanie” pytań, na które użytkownik zna odpowiedź z doświadczenia.

### 4.7 Wersja przenośna PC (standalone; od 2.3.1; `data/app_paths.dart`, `data/portable_prefs.dart`, `tools/build-portable.ps1`)
- Flutter na Windows nie da się spakować do jednego pliku .exe — paczka to folder (exe + `flutter_windows.dll` + `data\`) i ZIP (~17 MB). Obok exe leży `portable.flag`.
- **Tryb przenośny** (jest `portable.flag`): baza w `user_data\memonic_app.db`, ustawienia w `user_data\settings.json` (własny magazyn `PortablePrefsStore` zamiast wspólnego
  `%APPDATA%\com.example\memonic_app\shared_preferences.json`) — nie dotyka `Documents\memonic_app.db` ani zwykłych ustawień, nie widzi klucza API zwykłej instalacji. Reset nauki = usunięcie `user_data`.
- **Czysta baza startowa:** na czas budowy skrypt podmienia seed na `tools/make_clean_seed.py` (treść pytań + znaczniki „Błąd” z bieżącej bazy użytkownika, ale karty SRS jako nowe,
  pusty `review_log`, `explanation_cache`, `import_meta`) i **zawsze przywraca oryginalny seed** w repo. Skrypt sprawdza też, że `Documents\memonic_app.db` nie zmienił się (hash).
- **Uwaga:** seed w repo (`app/assets/db`) zawiera stary postęp nauki (213 kart z wersji RC, 43 wyjaśnienia) — nowa instalacja APK startuje z tym postępem. Zwykłe buildy (APK, Start-rebuild) nadal używają tego seeda.
- Backup stanu nauki z 2026-10-09: `data/snapshot_bazy_uzytkownika_2026-10-09.db` oraz `Documents\MasterExam_backup_2026-10-09\` (baza + ustawienia z kluczem API — poza projektem).

### 4.6 TEST — symulacja egzaminu (od 2.3; `features/test/test_screen.dart`, `domain/test_plan.dart`)
- Przycisk **TEST** (pastelowy pomarańcz `#FFB877`) na ekranie głównym; domyślnie **105 pytań**, zaliczenie **70** poprawnych; pula: **50% Master / 20% Angielski / 30% Pokład**
  (metoda największych reszt: 53/21/31). Wszystko zmienia się w Ustawieniach → TEST (liczba pytań, próg, % Master i Angielski; Pokład = reszta).
  **Bez powtórzeń:** to samo pytanie bywa w bazie w kilku wierszach (inne ID/poziom/wersja OCR: np. Angielski 555 wierszy = 339 unikalnych, Pokład 1851 = 1243), więc `pickTestQuestions`
  odrzuca duplikaty po treści (klucz: pytanie+warianty+obrazek oraz pytanie+poprawna odpowiedź+obrazek), także między pulami; braki po odrzuceniu są dobierane z pozostałych pul.
  Losowane są pytania z puli nauki (bez ukrytych „Błąd”), w losowej kolejności, także te z obrazkami.
- Bez podpowiedzi w trakcie (jedna odpowiedź → „Dalej”, osobno „Nie wiem” = błąd). Wynik na końcu: zaliczony/niezaliczony, wynik wg pul, lista błędnych z poprawnymi odpowiedziami.
  Ostatni wynik widać pod przyciskiem (historia 30 testów w SharedPreferences `test_history`, poza bazą i jej eksportem).
- **Błędna odpowiedź w teście od razu trafia do powtórek w swoim dziale:** FSRS `Again` (powrót po 1 i 10 min, potem wg FSRS), wpis w `review_log` (zeruje serię, liczy się do flagi „trudne”).
  Poprawne odpowiedzi w teście NIE zmieniają harmonogramu FSRS ani serii (to sprawdzian, nie nauka). Przerwanie testu: wynik nie jest zapisywany, błędy do tej pory już są w powtórkach.

### 4.5 Plan nauki, „znane” i egzamin (od 2.2; `domain/study_plan.dart`, schemat v6)
- **Nowe pytania w sesji:** co `newCardGap` odpowiedzi wstawiane jest losowe, nigdy niewidziane pytanie (`fetchNextCard(preferNew: true)`);
  odstęp zależy od skuteczności w ostatnich ≤10 odpowiedziach sesji: ≥90% → co 3, ≥80% → 4, ≥70% → 5, ≥60% → 6, ≥50% → 7, niżej → 8 (brak danych: 5).
  Karty po błędzie (1/10 min) mają dalej pierwszeństwo; w trybie „Powtórz zaplanowane” nowych nie wstawiamy.
- **Seria i „znane”:** `srs_cards.streak_days` = kolejne DNI NAUKI (dzień od 4:00) z poprawną odpowiedzią (kilka odpowiedzi tego samego dnia = 1; błąd zeruje).
  Znane = seria ≥ 3. Migracja v6 jednorazowo szacuje serię istniejących kart: `min(3, powtórzenia − lapsy)` dla kart w powtórkach.
- **Dziennik:** tabela `review_log` (pytanie, czas, dzień nauki, poprawna?, ocena FSRS, sekundy) — źródło dla „dziś zrobiono” i flagi „trudne”.
- **Trudne:** `srs_cards.hard` = ≥3 błędy w ostatnich 10 odpowiedziach na to pytanie albo ≥3 lapsy bez serii. Etykieta „Trudne” w nauce, licznik na ekranie głównym,
  zaległe karty trudne są podawane przed zwykłymi, a ich odstęp FSRS jest ograniczony do 3 dni (`hardMaxIntervalDays`).
- **Egzamin i cel dzienny wg Twojego tempa (od 2.5; `DailyPlan.compute`, `QuestionRepository.paceStats`):** Ustawienia → termin egzaminu (SharedPreferences `exam_date`). Cel = materiał „znany” na `examBufferDays` = 3 dni przed egzaminem,
  liczony **osobno dla wybranego działu** (All / Master / Pokład / Angielski). Praca do wykonania = Σ(3 − seria) po pytaniach nieznanych (jednostki serii). Tempo z `review_log` (ostatnie 14 dni, od pierwszego wpisu;
  kolumny `streak_before/streak_after` od v7): odpowiedzi, przyrost serii netto, pytania opanowane. **Koszt jednostki** = (odpowiedzi + 10×1,4) / (przyrost netto + 10) — Twoje błędy i powtórki zwiększają koszt, założenie startowe 1,4
  zanika w miarę danych. **Cel na dziś** = ⌈koszt × (pozostała praca + dzisiejszy przyrost) / dni do terminu⌉ (stały w ciągu dnia). **Prognoza** = pozostała praca / dotychczasowy przyrost na dzień, nie mniej niż
  `minDaysForUnits` (seria rośnie najwyżej raz na dzień nauki, powtórki ≥ ~2 dni od siebie: seria 0 → min. 5 dni); porównanie z dniami do terminu (zielone / pomarańczowe z zaleceniem tempa).
  Przy ustawionym terminie interwał FSRS jest skracany (`capIntervalForExam`), żeby seria 3 dni zdążyła się zamknąć (domyślny FSRS dawałby 2 → 11 → 46 dni).
- **Ekran główny:** pasek „Opanowanie materiału” (znane/pula, %) + cel na dziś, Twoje tempo i prognoza opanowania. **Nauka:** nagłówek `X/Y/Z` (X białe = odpowiedzi w sesji, Y zielone = poprawne, Z czerwone = błędne).

### 4.4 Pytania z obrazkami (od 2.1; `image_path`, `widgets/question_image.dart`)
- Kolumna `questions.image_path` = nazwa pliku w `app/assets/question_images/` (PNG, oryginalny obraz wyjęty z PDF, ~3 KB; wchodzi do APK).
  Obrazek jest nad treścią pytania, na białym tle (też w trybie ciemnym), skaluje się (max 420 px szer., 30% wysokości ekranu), tap = powiększenie.
- Dla pytań z obrazkiem **„Wyjaśnij” (AI) jest wyłączone** (model nie widzi obrazka). `contentKey` importu uwzględnia obrazek (pytania „Flaga oznacza:” mają identyczny tekst).
- Narzędzia (`tools/pdf_extraction/`): `figures.py` (wykrywa wiersze z rastrem lub kształtami wektorowymi ≥4 pt w komórce treści; pomija żółte zakreślenia,
  szare cieniowanie i białe nakładki; zwykły raster zapisuje w oryginale, resztę renderuje 300 dpi z przycięciem tekstu pytania), `list_figures.py` (lista),
  `contact_sheets.py <katalog>` (arkusze podglądu do kontroli wzrokowej — **zawsze oglądać przed `--apply`**), `apply_figures.py` (podgląd / `--apply`: kopia obu baz,
  UPDATE istniejących bez obrazka, INSERT nowych z `ai_verified=pdf_urzad:z_obrazkiem:<data>`; metadane z ścieżki i nazwy PDF; `SKIP` = ręczne wyjątki).
  Klucz odpowiedzi brany z PDF. Log ostatniego przebiegu: `figures_apply_log.json` (nadpisywany; etap 1 = ID 2949–2997, etap 2 = 3 uzupełnione + 66 dodanych od 2998).
  `list_figures.py` pomija arkusze F1-P6 Łączność morska (już wdrożone) — przy ponownym uruchomieniu `apply_figures.py` zduplikowałoby je tylko, gdyby je włączyć.
- Kopie sprzed zmiany: `Documents\memonic_app.db.bak_figures_*`, `data\memonic_app_seed.db.bak_figures_*`.

### 4.1 Algorytm nauki — FSRS-6 (`lib/domain/fsrs.dart`)
- Wzory i 21 parametrów domyślnych z oficjalnego py-fsrs (open-spaced-repetition). Stany: new → relearning → review.
- **Ocena:** poprawna = Good; poprawna, ale po >25 s (zgadywanie?) = Hard; błędna / „Nie wiem” = Again.
- **Kroki po błędzie:** wraca po **1 min**, potem **10 min** (w tej samej sesji), po dwóch poprawnych dostaje interwał w dniach.
- **Karty „na dni”** są dostępne od **4:00** rano (rollover), nie co do godziny.
- **Kolejka** (`QuestionRepository.fetchNextCard`): (1) po błędzie, których czas minął → (2) zaległe na dni (losowo) → (3) nowe (losowo) →
  (4) najbliższa karta po błędzie (żeby sesja nie kończyła się pusto). Ta sama karta nie pojawia się dwa razy z rzędu.
  Tryb „Powtórz zaplanowane”: karty z terminem w ciągu 24 h; karta zaliczona w sesji nie wraca (`doneIds`), bo wczesna powtórka (<1 doby) nie zmienia terminu
  w FSRS i bez tego karty krążyłyby w nieskończoność (błąd naprawiony 2026-10-05, test regresji w `test/fsrs_test.dart`).
- **Zapis postępu:** natychmiast po każdej odpowiedzi (`saveSrs`), nie przy zamykaniu programu.
- Migracja z SM-2 (v3→v4) jest idempotentna (`AppDatabase.migrateSrsToFsrs`, `Sm2Migration`); stary kod SM-2 (`domain/sm2.dart`) zostaje tylko w testach.

### 4.2 „Wyjaśnij” — AI przez OpenRouter (`domain/explain_prompt.dart`, `data/explain_service.dart`)
- Modele (Ustawienia): Gemini 2.5 Flash (domyślny), Qwen3.6 Plus, DeepSeek V3.2/V4 Flash, Grok 4.3, **GPT 6.1 Sol (Medium)**,
  **Claude Sonnet 5.5 (Medium)** (dwa ostatnie z `reasoning.effort=medium`).
- Model dostaje pytanie i klucz z bazy, **sam sprawdza, czy klucz jest prawidłowy** (dane z OCR bywają uszkodzone) i zwraca JSON
  `{my_answer, agree, explanation}`. **Nagłówek ustala kod, nie model:** `agree=true` i ta sama litera → „Prawidłowa odpowiedź to X. …”,
  w przeciwnym razie `UWAGA - ODP. W BAZIE DANYCH MOŻE BYĆ BŁĘDNA` (czerwony tekst). Prompt wymusza oparcie na: Kodeks morski, STCW, COLREG,
  MARPOL, ISM Code, LSA Code, FFE Code, MLC, UNCLOS, ISPS Code, IMDG Code, SOLAS; zasada „najtrafniejszy wariant”, bez zgadywania „klucza egzaminacyjnego”.
- Cache: tabela `explanation_cache` (klucz: id pytania + hash treści + wersja promptu `explainPromptVersion`). **Zmieniając prompt, podbij wersję.**
- Klucz API trzyma tylko `SharedPreferences` na urządzeniu (nie w bazie, nie w APK, nie w eksporcie).

### 4.3 Eksport / import bazy (`data/db_transfer_service.dart`, `features/settings/db_transfer_actions.dart`)
- **Eksport:** cały plik bazy (pytania + statusy + postęp FSRS + cache) przez „Zapisz jako”.
- **Import** (wybór pliku → wybór trybu → potwierdzenie „Czy na pewno wykonać: A/B/C?”):
  **A** pełny import z nadpisaniem (kopia obecnej bazy `*.bak_before_import_*`; obce bazy są uzupełniane do schematu aplikacji),
  **B** tylko statusy (`review_status`, „Błąd”) pytań już obecnych, **C** dodanie pytań nieobecnych w bazie (z ich statusami).
  Dopasowanie w B/C po treści (poziom + pytanie + warianty), nie tylko po ID.
  **D (od 2026-10-15; `DbTransferService.updateKeepProgress`) — aktualizacja bazy z zachowaniem postępu, domyślny tryb:** łączenie po **numerze ID** (ID są stałe od przenumerowania); nowe pytania dodaje z ich ID, pytaniom
  obecnym nadpisuje treść, warianty, klucz, status, `ai_verified`, obrazek; **nie rusza** `srs_cards`, `review_log` ani lokalnego `study_hidden` („Błąd”); dołącza `explanation_cache` z pliku i (jeśli jest) `ai_disputed`;
  nic nie usuwa. Zabezpieczenie: gdy <80% wspólnych ID ma podobną treść (inna numeracja), import jest odrzucany. Typowy obieg: poprawki w bazie roboczej → Eksport/plik `.db` → na telefonie Import → D.
- Stary przycisk „Wczytaj questions.db” na ekranie głównym łączy po ID — **nie używać** (po przenumerowaniu ID daje duplikaty).

---

## 5. Baza danych (SQLite)

- **Baza użytkownika (Windows):** `%USERPROFILE%\Documents\memonic_app.db` — wspólna dla każdej zainstalowanej wersji aplikacji.
  Android: katalog dokumentów aplikacji. Seed `app/assets/db/memonic_app_seed.db` jest kopiowany tylko, gdy bazy użytkownika nie ma.
- **Schemat v8** (`lib/data/database.dart`, `onUpgrade` migruje v1→v8, wszystkie migracje idempotentne): `questions` (id, kategoria, podkategoria, poziom, tematyka, nr_pytania, typ_pytania, pytanie,
  odp_a..d, poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku, review_status, review_notes, study_hidden, **ai_verified**, **image_path**, **dup_group**),
  `srs_cards` (question_id, repetitions, interval_days, ease_factor←trudność, due_ms, lapses, state, step, stability, difficulty, last_review_ms, **streak_days, last_good_day, hard**),
  `review_log` (odpowiedzi: pytanie, czas, dzień nauki, poprawna?, ocena, sekundy, **streak_before, streak_after**), `dup_links` (powiązania powtórzeń: question_id → canonical_id),
  `explanation_cache`, `import_meta`. Ustawienia (termin egzaminu, ustawienia TESTU, historia testów, klucz API) są poza bazą, w SharedPreferences.
- **ID pytań** to 1…3424 z lukami (3193–3424: skany egzaminów; 25 ID usunięto jako duplikaty, patrz niżej) (usunięte pytania nie są renumerowane po raz drugi). Mapowanie starych ID (sprzed przenumerowania):
  `tools/ai_audit/history/logs/id_mapping_stare_nowe.csv`.
- **`ai_verified`** (ślad kontroli): `ok:gpt-6.1-sol+sonnet-5.5:…` (Master, 1. test dwoma drogimi modelami), `ai_cascade_v5:ok:…` (przeszło kaskadę),
  `ai_cascade_v5:tekst_poprawiony:…` (poprawiony tekst), `manual:…` (decyzja użytkownika, np. klucz z arkusza PDF), `pdf_urzad:bez_AI:…`
  (dodane z PDF bez AI), `…wiele_poprawnych_odp…` (zostawione z adnotacją), `exam_scan:ai_high_runda1_haiku|runda2_sonnet_sol:<data>` (207 pytań ze skanów egzaminów, ID 3193–3418 z lukami; zob. 6.2), `ai_authored:<data>` (autorskie pytania Master napisane przez AI na bazie dokumentów morskich — 129 szt., ID 3064–3192: zestaw 1 = 13 [pływy, GT/NT, GM, ECDIS, konosament…], zestaw 2 = 77 [FAL 1–7, laytime, akredytywa, IALA z rysunkami, COLREG, UNCLOS, MARPOL, sygnały mgłowe, znaki dzienne z rysunkami, OWS, obszary specjalne], zestaw 3 = 27 [planowanie podróży A.893, UKC/squat/Barrass, Letter of Protest, Polar Code, klasy IACS PC1–PC7], zestaw 4 = 12 [klasyfikacja akwenów manewrowych: nieograniczony / płytkowodzie / pogłębiony tor / kanał, PIANC H/T]; wspólny kod wstawiania: `tools/ai_audit/history/authored_lib.py`; przeszły kaskadę L1+L2 bez uwag; do przeglądu przez człowieka; źródła w `zrodlo_pliku`, wersje do czytania w `review/Nowe_pytania_Master_*.md`).
- **Kopie bezpieczeństwa:** każda zmiana bazy przez skrypty robi najpierw `*.bak_*` obok pliku. Backup postępu: `data/snapshot_*.db`.

---

## 6. Workflow kontroli jakości pytań (FINALNY — `tools/ai_audit/`)

**Zasady:** (1) klucz z arkusza Urzędu ma priorytet — AI nie zmienia klucza, tylko flaguje; (2) tekst pytania naprawiamy z PDF (warstwa tekstowa) lub
oczywistych literówek; (3) pytania z rysunkiem zostają z obrazkiem (4.4; wcześniej usuwano); (4) wątpliwe klucze **usuwamy z bazy do decyzji człowieka** (`review/DO_PRZEGLADU.xlsx`); (5) przed każdą zmianą — kopia bazy i log.

**Dlaczego kaskada:** drogie modele na całej bazie są zbyt kosztowne (Sol+Sonnet ≈ 12 USD / 2400 pytań), a tanie same mylą się na pytaniach merytorycznych
(zgodnie z literaturą: wykrywanie błędów etykiet przez LLM ma niski recall i trzeba filtrować po pewności).

| Warstwa | Model (OpenRouter) | Zadanie | Wchodzą |
|---|---|---|---|
| **L1** | `openai/gpt-6-luna` (reasoning low) | Zna klucz. Ocenia integralność tekstu (usterka? jaka?) i wiarygodność klucza (JSON). | wszystkie |
| **L2** | `deepseek/deepseek-v4.1-flash` (low) | NIE zna klucza. Lista kontrolna integralności + ślepa odpowiedź. | wszystkie |
| **L3** | `anthropic/claude-sonnet-5.5` (medium) | Finalny arbiter: `OK / DEFECT / KEY_SUSPECT` + uzasadnienie. | tylko sygnały `key` / `weak` (≈ 5–10%) |

**Routing (wf.py, wersja `v5`):**
- `integrity` — L1 i L2 niezależnie zgłaszają uszkodzenie tekstu → od razu na listę poprawek (bez L3).
- `figure` — któryś model zgłasza `needs_figure` → pytanie do usunięcia (bez L3).
- `key` — L2 ślepo wskazuje inny wariant z pewnością ≥ 90, albo L1 uznaje klucz za niewiarygodny (≥ 85) i L2 (≥ 80) wskazuje ten sam inny wariant → L3.
- `weak` — L1 widzi poważną usterkę, a L2 nie potwierdza (lub błąd API) → L3.

**Kalibracja** (`build_calibration.py`, 3 zestawy × 30 pytań, 15 czystych + 15 ze wstrzykniętą usterką): usterki tekstu wykryte **97%**,
usterki klucza **67%** (zamienione klucze, które tani model uznaje za wiarygodne, nadal się wymykają), czyste pytania w Excelu 3/45, do Sonneta 11%.
**Koszt ≈ 1–1,4 USD / 1000 pytań** (cała baza bez Master: 2438 pytań ≈ 2,3 USD).

**Uruchamianie** (potrzebny `.env` z `OPENROUTER_API_KEY`, baza domyślnie `Documents\memonic_app.db`, nadpisz `MEM_DB`):
```bash
cd tools/ai_audit
python wf.py --set calibration_set.json --tag test --pv v5 --l3          # sprawdzenie workflow na zestawie kalibracyjnym
python audit_db.py --limit 60 --tag probe                                # próba na losowych pytaniach
python audit_db.py --after-id 900 --limit 100000 --ordered --cap 8 --tag batchN   # przegląd partii (limit kosztu w USD)
python audit_db.py --categories Kap --marker ai_authored --cap 3 --tag authored      # kontrola pytań autorskich
python audit_db.py --only-images --cap 3 --tag figures                              # pytania z obrazkami (obraz idzie do modeli)
```
Wynik: `review/Przeglad_AI_<tag>.xlsx` (arkusze: usterka tekstu / wątpliwy klucz / wymaga rysunku) + `runs/audit_<tag>.json`.
Wywołania są cache'owane (`runs/cache_*.jsonl`, w .gitignore) — powtórka przebiegu kosztuje tylko brakujące wywołania.

**Procedura po przeglądzie** (tak zrobiono wszystkie partie; wzorce w `tools/ai_audit/history/apply_*_fixes.py`): kopia obu baz (aplikacji i seeda) →
poprawki tekstu (z PDF/literówki) → usunięcie pytań z rysunkiem → usunięcie wątpliwych kluczy (pełne wiersze do logu JSON) → znaczniki `ai_verified`.
Skryptów `history/apply_*` **nie uruchamiaj ponownie** (jednorazowe, ścieżki z poprzedniego układu).

**Oczekujące na człowieka:** `review/DO_PRZEGLADU.xlsx` — 41 pozycji (38 usuniętych kluczy wątpliwych + 2 pytania BHP z wieloma poprawnymi + 1 nieprzejrzane),
4 pytania z niezgodną literą względem PDF, 105 usuniętych (rysunek/puste — informacyjnie). W kolumnie „Twoja decyzja” wybierz PRZYWRÓĆ / ZMIEŃ KLUCZ / USUŃ / ZOSTAW, potem:
```bash
python review\restore_questions.py            # podgląd
python review\restore_questions.py --apply    # zastosuj do bazy aplikacji i seeda (najpierw kopia *.bak_review_*)
```

### 6.2 Pytania ze skanów egzaminów (2026-10-12; `tools/ai_audit/exam_verify*.py`, `deploy_exam_high.py`)
- **Źródło:** zdjęcia/skany testów z egzaminów kapitańskich 2017–2026 (foldery Desktop `Nowe pytania` i `Nowe nowe`; zaznaczenia na skanach to odpowiedzi zdających, NIE klucz).
  Przepis do JSON: `review/Egzamin_2026-03-30/` (partia 1, 60 pytań) i `review/Nowe_nowe/` (partia 2, 402 pytania ze 482 wystąpień); wspólny zbiór `review/Egzaminy_lokalna_baza.{xlsx,md,json}` (462).
  Pominięte/niedokończone: f15 „Budowa okrętu” (120 pytań), f01 „TESTY RÓŻNE LATA” (57 rozmytych zdjęć), zadania pisemne/obliczeniowe, nieczytelne fragmenty.
- **Weryfikacja** (`review/Weryfikacja_2026-10-12/`): etap A — duplikaty względem bazy (2 sędziów Haiku 5.5, 86 duplikatów); etap B — 3 sędziów Haiku 5.5 (reasoning medium, 2 ślepych z przetasowanymi wariantami + weryfikator,
  fragmenty Kodeksu morskiego/ustawy o pracy na morzu/PKBWM w prompcie) → 106 HIGH; runda 2 dla MEDIUM/NISKA: 2× Claude Sonnet 5.5 + GPT 6.1 Sol (`exam_verify2.py`) → +120 HIGH. Razem 226 HIGH, 22 MEDIUM, 58 NISKA, 61 odrzuconych.
  HIGH = zgodność sędziów z odpowiedzią wstępną (pewność ≥80/85, bez flagi niejednoznaczności), a nie dowód z tekstu przepisu (tylko 3 ustawy były dostarczane jako tekst).
- **Wdrożenie** (`deploy_exam_high.py`, log `wdrozenie_log.json`): kategoria Master, oryginalna kolejność wariantów (rozkład kluczy nierównomierny: B ≈ 50%), karty SRS nowe. Po wdrożeniu usunięto 25 wierszy jako duplikaty
  (sędzia dup był zbyt ostrożny: 19 = to samo co w bazie, 6 = powtórzone w partii) — **lekcja: po wdrożeniu zrób kontrolę trigramami względem bazy** (próg ≥0,72) i porównaj warianty ręcznie.
- **Klucz OpenRouter ma limit całkowity (5 USD, bez resetu):** po jego wyczerpaniu wszystkie wywołania zwracają 403 — sprawdź `GET /api/v1/key`; udane wywołania są w cache (`cache*.jsonl`).

- **PDF „Pytania super nowe” (2026-10-13; Studocu, UMG, egzamin dyplomowy KZW – Manewrowanie i administracja):** 24 pytania testowe (bez #7 z wzorami w obrazkach) przeszły przez 2× Sonnet 5.5 + GPT 6.1 Sol
  (`tools/ai_audit/super_nowe_verify.py`, wyniki `review/Super_nowe/wyniki.json`; PDF nie ma klucza). 14 HIGH: 8 już było w bazie (klucz potwierdzony), do bazy weszło **6** (#1, 4, 6, 15, 17, 22; ID 3419–3424,
  `deploy_super_nowe.py`, `ai_verified = exam_scan:ai_high_super_nowe_sonnet_sol:2026-10-13`, log `review/Super_nowe/wdrozenie_log.json`). Niewdrożone: #16, 18, 23 (flaga „incomplete”/pewność 70), #19, 20, 24 (rozbieżność), #11, 14 (uszkodzony tekst z PDF), zadania pisemne #26–30.
- **Analiza „najczęściej poprawna wartość”** (`review/Statystyka/`): reguła wyboru wartości liczbowej wg statystyki bazy trafia 43% vs 32% losowo (np. „5 lat” 37%); „szóstka/wielokrotność” = szum. Praktycznie bezużyteczna do zgadywania.

### 6.3 Wyjaśnienia AI z roju Haiku i oznaczenie pytań bez konsensusu (2026-10-14)
- 3 × Claude Haiku 5.5 (lokalne subagenty, nie OpenRouter) ocenił każde z 2491 unikalnych pytań (wiedza morska: Kodeks morski, SOLAS, STCW, UNCLOS, MARPOL, FAL…). Paczki w scratchpadzie sesji; wyniki zbiorcze: `review/Wyjasnij_AI/`.
- **Konsensus (2367 unikalnych, 3078 wierszy):** wszyscy 3 zgodni z kluczem → wyjaśnienie wpisane do `explanation_cache` w obu bazach (hash jak w aplikacji, wersja promptu v6; istniejące wpisy zachowane, m.in. ręczne dla ID 3444). Model w cache: `claude-haiku-5-5 x3 swarm`. Log: `review/Wyjasnij_AI/wdrozenie_log.json`; kopie `*.bak_before_ai_explain_*`.
- **Bez konsensusu (124 unikalne, 148 wierszy):** `review/Wyjasnij_AI/Pytania_bez_konsensusu_Haiku.xlsx` (zielony/pomarańczowy = zgodny/niezgodny agent). ID wierszy: `niezgodne_ids.json`.
- **TYMCZASOWO:** tabela `ai_disputed(question_id)` (`data/ai_disputed.dart`, ładowana przy starcie) — treść takich pytań w nauce i w TEŚCIE jest na pastelowo-pomarańczowym tle (#FFD8A8). Po weryfikacji: `DELETE FROM ai_disputed` (w obu bazach) i usunąć kod `aiDisputed`.

### 6.1 Narzędzia pomocnicze
- `tools/pdf_extraction/` — niezależny ekstraktor pytań z PDF (tabele `find_tables`, obsługa pytań rozciętych na stronach), parowanie z bazą
  (`pair_master.py`, `match_dzial.py`), raport brakujących/niezgodnych. Użyto go do znalezienia 141 brakujących pytań Master i 825 brakujących pytań Pokładu
  (parser pierwszej wersji gubił pytania przechodzące przez granicę strony).
- `tools/legacy_pipeline/` — pierwsza wersja budowy bazy z PDF (parsery `parser_pdf_format1/2`, Vision, konsensus 3 modeli, `gui.py`, `review.py`, `fix_pdf.py`);
  opis w `LEGACY_AGENTS.md`. Nie jest potrzebna do codziennej pracy.

---

## 7. Historia (skrót; pełna w `docs/CHANGELOG.md`)

1. v1 (maj 2026): pipeline PDF→SQLite, aplikacja Flutter (SM-2), AI „Wyjaśnij”.
2. RC1 (Android): APK z wbudowaną bazą.
3. 2026-10-05 (→ 2.0): Master zweryfikowany Sol+Sonnet (369 → 510 po dodaniu 141 brakujących z PDF; 66 pytań do decyzji → wdrożone wg arkusza PDF);
   dodano 825 brakujących pytań Pokładu z PDF; przenumerowanie ID; kaskadowy przegląd Pokładu i Angielskiego (3 partie: 300 + 600 + 1538 pytań);
   FSRS-6; eksport/import bazy; „Nie wiem”; nowe modele AI i weryfikacja klucza w „Wyjaśnij”.
4. 2026-10-06 (2.1–2.2): obrazki w pytaniach (119 pytań z rysunków PDF, kontrola AI z obrazami); wstrzykiwanie nowych pytań co 3–8 odpowiedzi, seria „znane”, termin egzaminu, „trudne”, 13 pytań autorskich Master.
5. 2026-10-07/08 (2.3): TEST 105 pytań (zaliczenie 70), 77+27+12 pytań autorskich Master (FAL, IALA, COLREG, MARPOL, Polar Code, akweny manewrowe…), naprawa urwanych treści pytań, deduplikacja kluczy.
6. 2026-10-09 (2.3.1–2.7): wersja przenośna PC; „odłóż pytanie” (klepsydra); cel dzienny wg tempa nauki; synchronizacja powtórzonych pytań; roj Haiku 5.5 do wykrywania powtórzeń (`dup_links`).
7. 2026-10-12: skany nowych egzaminów → 462 pytania lokalnie, weryfikacja rojem modeli, wdrożone 201 pytań (Master, `exam_scan`) + 2026-10-13 jeszcze 6 z PDF „Pytania super nowe” (ID 3419–3424); paczki „Baza Pytan Apka-2.4” (APK + ZIP PC, czysta baza, `tools/build-release-clean.ps1`).

---

## 8. Znane ograniczenia i pomysły

- Zamienione klucze, które tani model uznaje za wiarygodne, wymykają się kaskadzie (~1/3); zadania obliczeniowe są oceniane niepewnie.
- FSRS używa parametrów domyślnych (nie dostrojonych do użytkownika); próg „Hard” 25 s to założenie.
- Pytania z obrazkami nie przeszły kontroli AI (L1–L3 nie widzą rysunków); klucz pochodzi wprost z PDF. Pytania, których rysunek jest w innej formie niż raster/wektor w komórce tabeli, mogły zostać pominięte — gdyby brakowało jakiegoś, sprawdź `list_figures.py`.
- Nie wszystkie pytania Pokładu mają odpowiedniki angielskie; Angielski to osobna lista (556), a moduł F1-P8 „Język angielski” leży w Pokładzie.
- Seria „znane” działa od wdrożenia v6 (wcześniejsza historia odpowiedzi nie istniała — stąd szacunek startowy); FSRS dla pytań o serii < 3 przy dalekim egzaminie rozsuwa powtórki szeroko.
- **Seed w repo** (`app/assets/db/memonic_app_seed.db`) zawiera stary postęp nauki (213 kart z wersji RC, 43 wyjaśnienia) — świeża instalacja APK startuje z nim; wersja przenośna PC używa czystego seeda (patrz 4.7).
- **APK i wersja przenośna PC** nie są przebudowywane automatycznie: po zmianach w aplikacji trzeba uruchomić `Build-APK.bat` / `tools\build-portable.ps1` (ostatnie: paczki „Baza Pytan Apka-2.4” z 2026-10-12 zbudowane z aktualnym kodem 2.7.0 i czystą bazą 3243 pytań — `tools\build-release-clean.ps1 -Label <nazwa>` buduje APK + ZIP PC na pulpit; seed w repo nadal ma stary postęp).
- Cel dzienny i prognoza opierają się na dzienniku odpowiedzi od 2026-10-06 (14-dniowe okno) — przy kilku dniach danych są szacunkiem; powtórki po błędzie (1 i 10 min) mogą wracać pod innym ID tej samej grupy powtórzeń.
- Autorskie pytania AI (`ai_authored`) przeszły kaskadę L1+L2, ale nie były weryfikowane przez człowieka z uprawnieniami; wzór Barrassa i granica Arktyki w Polar Code mają źródła niejednoznaczne (patrz `review/Nowe_pytania_Master_*.md`).
- Skany `f15` (Budowa okrętu) i `f01` nie są przepisane; pytania MEDIUM (22) i NISKA (58) ze skanów czekają na ręczny przegląd (`review/Weryfikacja_2026-10-12/wyniki*.xlsx`); część pytań `exam_scan` jest poziomu operacyjnego (nawigacja, meteorologia) w kategorii Master.
- **Windows 8.1 / starsze bez `winsqlite3.dll`:** build Release musi mieć `sqlite3.dll` obok exe (od 2026-10-14 dołączana z `app/windows/third_party/sqlite3.dll` przez `CMakeLists.txt`); bez niej błąd „Failed to load dynamic library 'winsqlite3.dll': error code 126”. Paczki PC zbudowane wcześniej (np. „Baza Pytan Apka-2.4”) tego pliku nie mają.
- Pomysły: przechowywanie klucza API w `flutter_secure_storage` (Android), trenowanie parametrów FSRS, ponowny przegląd po aktualizacji arkuszy, wspólna baza postępu PC ↔ telefon.

---

## 9. Konwencje pracy (dla agentów i ludzi)

- Odpowiadaj po polsku. **Projekt ma lokalne repo git** (od 2026-10-15, gałąź `main`, bez zdalnego; `.gitignore` wyklucza bazy `*.db`, `data/`, `dist/`, `sources/`, PDF/Word/Excel, `*.bak*`). Nie commituj bez prośby. Nie zapisuj kluczy API w repozytorium (`.env` jest w `.gitignore`).
- **Przed każdą zmianą bazy** zrób kopię i zapisz log; zmieniaj **obie** bazy (Documents + `app/assets/db` seed), żeby APK miał ten sam stan.
- Zmieniając prompt „Wyjaśnij” — podbij `explainPromptVersion`; zmieniając schemat — podbij `version` w `database.dart` i napisz idempotentną migrację.
- Po zmianach w kodzie: `flutter analyze`, testy, `Start-rebuild.bat`. Przed APK — zamknij aplikację PC (blokuje pliki).
- Numer wersji: `app/pubspec.yaml` (`version:`) i `app/lib/app_info.dart` — zmieniaj razem.
- Nowe pytania autorskie dodawaj przez `tools/ai_audit/history/authored_lib.py` (kopie obu baz, rozkład kluczy, plik do przeglądu), a potem `audit_db.py --marker ai_authored` (kontrola kaskadą).
- Duplikaty wykrywaj na KOPII bazy (`dup_swarm.py`), gdy użytkownik uczy się w aplikacji; zapis do bazy użytkownika dopiero po zamknięciu aplikacji (kopia + log).
- Skany egzaminów: tylko odpowiedzi z klucza arkusza/przepisu, nie zaznaczenia zdających; weryfikuj rojem (Haiku → Sonnet+Sol), wdrażaj tylko HIGH i po wdrożeniu sprawdź duplikaty trigramami (6.2).
- Paczki dla użytkownika: `tools\build-release-clean.ps1` (czysta baza, bez klucza API); klucz OpenRouter ma limit całkowity.
- `.env` w katalogu głównym musi mieć postać `OPENROUTER_API_KEY=...` (Windows potrafi ukryć rozszerzenie i zapisać `.env.txt`).

## 10. Stary folder (backup)

`C:\Users\Lukasz\Desktop\Dev\Master Exam Mnemonic` zawiera poprzednią wersję i rzeczy **celowo niezabrane**: `Question Database\` z logami i cache pipeline'u
(`vision_cache`, `*.jsonl`, `DB backup`, `__pycache__`), `Android RC\` (APK RC1 + ~GB cache Gradle), stare Excele z przeglądów AI (`Przeglad_AI_*.xlsx`,
`Master_do_weryfikacji_v2.xlsx`, `Master_research_przepisow.xlsx`, `Dzial_do_sprawdzenia.xlsx`), plik Anki `cpt-AllInOne.colpkg`,
`questionsDB_final_25.05.2026.db`, `Pytania - scalone\`, `memonic_app\.git` (historia commitów starej aplikacji) oraz kopie `*.bak_*` baz.
Gdyby czegoś brakowało — to jest backup; po potwierdzeniu, że 2.0 działa, można go zarchiwizować.
