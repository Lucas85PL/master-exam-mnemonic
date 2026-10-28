# Wersja przenosna PC (standalone): folder + ZIP z programem, ktory
#  - trzyma baze i ustawienia w folderze user_data obok .exe (nie dotyka Documents\memonic_app.db ani zwyklych ustawien),
#  - startuje z CZYSTA baza nauki (tresc pytan + znaczniki "Blad" z biezacej bazy, ale bez postepu/powtorek),
#  - nie zawiera klucza API.
# Zwykla baza uzytkownika i seed w repozytorium NIE sa zmieniane (seed jest na czas budowy podmieniany i przywracany).
# Uzycie: powershell -ExecutionPolicy Bypass -File tools\build-portable.ps1
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $repoRoot 'app\scripts\flutter_env.ps1')
Mount-ProjectDrive $repoRoot

Get-Process -Name memonic_app, 'Master Exam Mnemonic' -ErrorAction SilentlyContinue | Stop-Process -Force
$userDb = Join-Path $env:USERPROFILE 'Documents\memonic_app.db'
$userDbHashBefore = (Get-FileHash $userDb -Algorithm MD5).Hash

# 1) czysta baza startowa (zrodlo tylko do odczytu)
$tmp = Join-Path $env:TEMP 'memonic_clean_seed.db'
python (Join-Path $repoRoot 'tools\make_clean_seed.py') $userDb $tmp
if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie utworzyc czystej bazy' }

# 2) budowa z podmienionym seedem (oryginal zawsze przywracany)
$seed = Join-Path $repoRoot 'app\assets\db\memonic_app_seed.db'
$seedBak = Join-Path $env:TEMP 'memonic_seed_original.db'
Copy-Item $seed $seedBak -Force
try {
    Copy-Item $tmp $seed -Force
    Set-Location "$($script:ProjectDrive):\app"
    Invoke-MemonicFlutter pub get
    Invoke-MemonicFlutter build windows --release
    if ($LASTEXITCODE -ne 0) { throw 'flutter build windows nie powiodl sie' }
}
finally {
    Copy-Item $seedBak $seed -Force
    Set-Location $repoRoot
}

# 3) skladanie paczki
$version = (Select-String -Path (Join-Path $repoRoot 'app\pubspec.yaml') -Pattern '^version:\s*(\S+)').Matches[0].Groups[1].Value -replace '\+.*', ''
$name = "Master-Exam-Mnemonic-$version-PC"
$out = Join-Path $repoRoot "dist\$name"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
Copy-Item "$($script:ProjectDrive):\app\build\windows\x64\runner\Release\*" $out -Recurse
Rename-Item (Join-Path $out 'memonic_app.exe') 'Master Exam Mnemonic.exe'
Set-Content -Path (Join-Path $out 'portable.flag') -Value 'Tryb przenosny: baza i ustawienia w folderze user_data obok programu. Nie usuwaj tego pliku.' -Encoding UTF8
@"
Master Exam Mnemonic $version - wersja przenosna (PC, Windows 10/11 64-bit)

URUCHOMIENIE
  Rozpakuj caly folder (np. na pulpit) i uruchom "Master Exam Mnemonic.exe". Instalacja nie jest potrzebna.
  Nie przenos samego pliku .exe bez reszty folderu (potrzebuje plikow .dll i folderu data).

DANE
  Postep nauki (baza) i ustawienia sa w folderze "user_data" obok programu - powstaje przy pierwszym uruchomieniu.
  Program startuje z czysta baza nauki (bez powtorek) i NIE uzywa bazy ani ustawien zwyklej instalacji na tym komputerze.
  Kopia zapasowa postepu = skopiowanie folderu user_data. Przeniesienie na inny komputer = skopiowanie calego folderu programu.
  Ustawienia -> Eksport/Import bazy dzialaja tak samo jak w zwyklej wersji.

WYJASNIJ (AI)
  Wyjasnienia AI sa domyslnie wylaczone i nie ma w programie zadnego klucza API.
  Aby z nich korzystac: Ustawienia -> wlacz wyjasnienia AI i wpisz wlasny klucz OpenRouter (zapisze sie tylko w user_data).

RESET NAUKI
  Zamknij program i usun folder "user_data" - przy nastepnym uruchomieniu postep bedzie zerowy.
"@ | Set-Content -Path (Join-Path $out 'CZYTAJ.txt') -Encoding UTF8

# 4) kontrola: zwykla baza uzytkownika niezmieniona
$userDbHashAfter = (Get-FileHash $userDb -Algorithm MD5).Hash
if ($userDbHashBefore -ne $userDbHashAfter) { throw 'UWAGA: zwykla baza uzytkownika zostala zmieniona!' }
Write-Host "Gotowe: $out"
