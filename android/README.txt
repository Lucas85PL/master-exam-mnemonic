Master Exam Mnemonic 2.0 - Android (APK, sideload, nie Play Store)
=====================================================================

Budowanie:   Build-APK.bat  (w katalogu glownym projektu)  ->  dist\Master-Exam-Mnemonic-2.0.apk
Skrypt:      android\build-apk.ps1

Instalacja na telefonie:
 1. Skopiuj plik .apk na telefon i zainstaluj (zezwol na instalacje z nieznanych zrodel).
 2. WAZNE: jesli na telefonie jest starsza wersja aplikacji (np. RC1), ODINSTALUJ ja najpierw.
    Baza wbudowana w APK jest kopiowana tylko przy pierwszym uruchomieniu, wiec instalacja "na wierzch"
    nie podmieni starej bazy. Odinstalowanie kasuje postep nauki i klucz API na telefonie.
 3. Wpisz klucz OpenRouter w Ustawieniach (klucz NIE jest w APK).

Baza w APK:  app\assets\db\memonic_app_seed.db  (stan z 2026-10-05: 2805 pytan, FSRS, postep z PC).
Aby zbudowac APK z nowszym stanem bazy: podmien ten plik (np. kopia z Dokumentow\memonic_app.db) i zbuduj ponownie.
Paczki dla uzytkownika z czysta baza (bez postepu i bez klucza API): tools\build-release-clean.ps1 -Label <nazwa> -> APK i ZIP wersji PC na pulpicie (seed w repo podmieniany tylko na czas budowy).
Eksport/import bazy miedzy PC a telefonem: Ustawienia -> Baza danych.

Pierwsze budowanie trwa dluzej (pobiera Gradle i zaleznosci do .cache\). Wymaga internetu i Android SDK.

Uwaga: plik w dist\ zawsze nazywa sie Master-Exam-Mnemonic-2.0.apk (nazwa nie zawiera wersji) - wersje sprawdzisz w aplikacji (menu / Ustawienia).
