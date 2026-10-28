# Buduje APK (Android) i wersje PC (przenosna, ZIP) z CZYSTA baza nauki (bez postepu i bez klucza API; gotowe wyjasnienia AI zostaja) i kopiuje je na pulpit.
# Seed w repozytorium jest podmieniany tylko na czas budowy i zawsze przywracany; zwykla baza uzytkownika nie jest zmieniana (kontrola hasha).
# Uzycie: powershell -ExecutionPolicy Bypass -File tools\build-release-clean.ps1 -Label "2.4"
param([string]$Label = '2.4', [switch]$ApkOnly, [switch]$PcOnly, [switch]$KeepProgress, [string]$ApkName = '')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $repoRoot 'app\scripts\flutter_env.ps1')
Mount-ProjectDrive $repoRoot
$d = "$($script:ProjectDrive):"
if (-not $ApkOnly) { Get-Process -Name memonic_app, 'Master Exam Mnemonic' -ErrorAction SilentlyContinue | Stop-Process -Force }
$desktop = [Environment]::GetFolderPath('Desktop')

$userDb = Join-Path $env:USERPROFILE 'Documents\memonic_app.db'
$tmp = Join-Path $env:TEMP 'memonic_clean_seed.db'
if ($KeepProgress) {
    # wersja prywatna: baza ZE STANEM NAUKI (kopia przez sqlite backup API - dziala tez przy uruchomionej aplikacji), bez klucza API (ten jest poza baza)
    python -c "import sqlite3,sys; s=sqlite3.connect('file:'+sys.argv[1].replace(chr(92),'/')+'?mode=ro',uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $userDb $tmp
    if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie skopiowac bazy uzytkownika' }
} else {
    $hashBefore = (Get-FileHash $userDb -Algorithm MD5).Hash
    python (Join-Path $repoRoot 'tools\make_clean_seed.py') $userDb $tmp
    if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie utworzyc czystej bazy' }
}

$env:FLUTTER_ROOT = "$d\.tools\flutter"
$env:GRADLE_USER_HOME = "$d\.cache\gradle"
$env:PUB_CACHE = "$d\.cache\pub"
New-Item -ItemType Directory -Force -Path $env:GRADLE_USER_HOME, $env:PUB_CACHE | Out-Null
$flutter = "$d\.tools\flutter\bin\flutter.bat"
$withoutOld = ($env:PATH -split ';' | Where-Object { $_ -and $_ -notmatch '\\flutter\\flutter\\bin' })
$env:PATH = (@("$d\.tools\flutter\bin") + $withoutOld) -join ';'

$seed = Join-Path $repoRoot 'app\assets\db\memonic_app_seed.db'
$seedBak = Join-Path $env:TEMP 'memonic_seed_original_release.db'
Copy-Item $seed $seedBak -Force
try {
    Copy-Item $tmp $seed -Force
    Set-Location "$d\app"
    & $flutter pub get
    if ($LASTEXITCODE -ne 0) { throw 'pub get' }
    if (-not $PcOnly) {
        & $flutter build apk --release
        if ($LASTEXITCODE -ne 0) { throw 'flutter build apk nie powiodl sie' }
    }
    if (-not $ApkOnly) {
        & $flutter build windows --release
        if ($LASTEXITCODE -ne 0) { throw 'flutter build windows nie powiodl sie' }
    }
}
finally {
    Copy-Item $seedBak $seed -Force
    Set-Location $repoRoot
}

# APK -> pulpit
if (-not $ApkName) { $ApkName = "Baza Pytan Apka-$Label for Android.apk" }
$apkDest = Join-Path $desktop $ApkName
Copy-Item "$d\app\build\app\outputs\flutter-apk\app-release.apk" $apkDest -Force

if ($ApkOnly) {
    if (-not $KeepProgress) { $hashAfter = (Get-FileHash $userDb -Algorithm MD5).Hash }
    if (-not $KeepProgress -and $hashBefore -ne $hashAfter) { throw 'UWAGA: baza uzytkownika zmienila sie w trakcie budowy!' }
    Write-Host "Gotowe (tylko APK): $apkDest"
    return
}
# PC -> folder + ZIP na pulpicie
$folderName = "Baza Pytan Apka-$Label for PC"
$stage = Join-Path $env:TEMP $folderName
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item "$d\app\build\windows\x64\runner\Release\*" $stage -Recurse
Rename-Item (Join-Path $stage 'memonic_app.exe') 'Baza Pytan Apka.exe'
Set-Content -Path (Join-Path $stage 'portable.flag') -Value 'Tryb przenosny: baza i ustawienia w folderze user_data obok programu. Nie usuwaj tego pliku.' -Encoding UTF8
@"
Baza Pytan Apka $Label - wersja PC (Windows 64-bit), przenosna

URUCHOMIENIE
  Rozpakuj caly ZIP (np. na pulpit) i uruchom "Baza Pytan Apka.exe". Instalacja nie jest potrzebna.
  Nie przenos samego pliku .exe bez reszty folderu (potrzebuje plikow .dll i folderu data).
  Windows 8.1: w paczce jest wlasna biblioteka sqlite3.dll (system nie ma winsqlite3.dll). Wymagany jest 64-bitowy
  "Visual C++ Redistributable 2015-2022" (x64) i aktualizacja Universal C Runtime (KB2999226); to wersja nieoficjalnie wspierana.

DANE
  Postep nauki i ustawienia sa w folderze "user_data" obok programu (powstaje przy pierwszym uruchomieniu).
  Program startuje z czysta baza nauki (bez powtorek) i NIE uzywa bazy ani ustawien zwyklej instalacji.
  Kopia zapasowa postepu = skopiowanie folderu user_data. Reset nauki = usuniecie folderu user_data.

WYJASNIJ (AI)
  Gotowe wyjasnienia do wiekszosci pytan sa w programie - przycisk "Wyjasnij" dziala bez klucza API i bez internetu.
  Dla pytan bez gotowego wyjasnienia mozna wlaczyc AI: Ustawienia -> wlacz wyjasnienia AI i wpisz wlasny klucz OpenRouter
  (w programie nie ma zadnego klucza; wpisany zapisze sie tylko w user_data).
"@ | Set-Content -Path (Join-Path $stage 'CZYTAJ.txt') -Encoding UTF8
$zipDest = Join-Path $desktop "$folderName.zip"
if (Test-Path $zipDest) { Remove-Item $zipDest -Force }
Compress-Archive -Path $stage -DestinationPath $zipDest -CompressionLevel Optimal

$hashAfter = (Get-FileHash $userDb -Algorithm MD5).Hash
if ($hashBefore -ne $hashAfter) { throw 'UWAGA: zwykla baza uzytkownika zostala zmieniona!' }
Write-Host "Gotowe:`n  $apkDest`n  $zipDest"
