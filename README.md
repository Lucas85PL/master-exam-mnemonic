# Master Exam Mnemonic

Aplikacja do nauki pytań testowych na egzaminy morskie (Flutter: **Windows + Android**) razem z narzędziami do budowy
i kontroli jakości bazy pytań. Wersja **3.0**, baza pytań **3.0** (4900 pytań, kategorie: Master, Pokład, Angielski).

> Projekt hobbystyczny, nieoficjalny. Nie jest powiązany z Urzędem Morskim ani żadną instytucją egzaminacyjną.

## Co potrafi

- **Nauka** z algorytmem powtórek **FSRS-6** (odpowiedź A/B/C/D, „Nie wiem”, odkładanie pytań, pytania nowe wplatane w sesję).
- **TEST** — symulacja egzaminu (105 pytań, próg 70), tryb *Normalny* i *Trudny*, bez powtórzeń z dwóch ostatnich testów.
- **Powtórka trudnych**, **Statystyki** (trudność pytań, sesje, testy), **Slideshow** (szybkie przypomnienie błędnych, trudnych i najstarszych pytań).
- **Baza Pytań** z edycją pytań w aplikacji (treść, warianty, klucz, kategorie, status „Niepewne”).
- **Wyjaśnienia** pytań (gotowe, offline; opcjonalnie generowane przez AI z Twoim własnym kluczem OpenRouter).
- **Eksport / import bazy** (tryb „aktualizacja z zachowaniem postępu”), wersja przenośna na PC.

## Ważne o danych

- Postęp nauki jest **wyzerowany** — aplikacja startuje od zera z wbudowaną bazą pytań (`app/assets/db/memonic_app_seed.db`).
- W aplikacji i w repozytorium **nie ma żadnego klucza API**. Klucz OpenRouter (opcjonalny, tylko do „Wyjaśnij” dla pytań bez gotowego
  wyjaśnienia) wpisujesz sam w Ustawieniach; zapisuje się tylko na Twoim urządzeniu.
- Pytania pochodzą z oficjalnych arkuszy (PDF) oraz z dodatkowych źródeł; część klucza odpowiedzi była weryfikowana przez modele AI
  i **nie ma gwarancji poprawności**. Pytania oznaczone jako **Niepewne** (pomarańczowe tło) mają wątpliwy klucz — jeśli znasz
  odpowiedź, popraw pytanie w Bazie Pytań. Traktuj aplikację jako pomoc w nauce, a nie źródło prawdy.

## Uruchomienie i budowanie

Wymagania (Windows 11): tryb dewelopera, Visual Studio Build Tools z „Programowanie aplikacji klasycznych w C++”, Flutter 3.44
(skrypty używają kopii SDK w `.tools\flutter`), Android SDK dla APK.

```
Start.bat            # uruchom (zbuduje Windows Release, jeśli trzeba)
Start-rebuild.bat    # przebuduj i uruchom po zmianie kodu
Build-APK.bat        # APK do dist\
```

Testy: `powershell -File app\run.ps1 -Action test`.

Szczegółowy opis projektu, architektury i workflow kontroli jakości pytań: [`AGENTS.md`](AGENTS.md) (po polsku).

## Struktura

- `app/` — aplikacja Flutter (`lib/`, `test/`, `assets/`),
- `android/` — skrypt budowania APK,
- `tools/` — narzędzia do bazy pytań (ekstrakcja z PDF, kontrola jakości AI, wydania),
- `docs/` — historia zmian.

## Licencja

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) — można kopiować i przerabiać z podaniem autora, bez użycia komercyjnego (szczegóły w `LICENSE`).
