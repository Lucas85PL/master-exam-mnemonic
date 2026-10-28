# Buduje PATCH do wersji PC (przenosnej) 2.4/2.5: pliki programu do nadpisania (bez portable.flag i bez user_data) + czysta baza pytan do importu (tryb D).
# Seed w repozytorium jest podmieniany na czysta baze (bez postepu i klucza API) tylko na czas budowy i zawsze przywracany; baza uzytkownika nie jest zmieniana (kontrola hasha).
# Uzycie: powershell -ExecutionPolicy Bypass -File tools\build-pc-patch.ps1 -Label "2.6" -OutDir "C:\Users\...\Desktop\App patch to 2.6"
param([string]$Label = '2.6', [string]$OutDir = '')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
. (Join-Path $repoRoot 'app\scripts\flutter_env.ps1')
Mount-ProjectDrive $repoRoot
$d = "$($script:ProjectDrive):"
Get-Process -Name memonic_app, 'Master Exam Mnemonic', 'Baza Pytan Apka' -ErrorAction SilentlyContinue | Stop-Process -Force
if (-not $OutDir) { $OutDir = Join-Path ([Environment]::GetFolderPath('Desktop')) "App patch to $Label" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$userDb = Join-Path $env:USERPROFILE 'Documents\memonic_app.db'
$hashBefore = (Get-FileHash $userDb -Algorithm MD5).Hash
$tmp = Join-Path $env:TEMP 'memonic_patch_clean_seed.db'
python (Join-Path $repoRoot 'tools\make_clean_seed.py') $userDb $tmp
if ($LASTEXITCODE -ne 0) { throw 'Nie udalo sie utworzyc czystej bazy' }

$env:FLUTTER_ROOT = "$d\.tools\flutter"
$env:GRADLE_USER_HOME = "$d\.cache\gradle"
$env:PUB_CACHE = "$d\.cache\pub"
New-Item -ItemType Directory -Force -Path $env:GRADLE_USER_HOME, $env:PUB_CACHE | Out-Null
$flutter = "$d\.tools\flutter\bin\flutter.bat"
$withoutOld = ($env:PATH -split ';' | Where-Object { $_ -and $_ -notmatch '\\flutter\\flutter\\bin' })
$env:PATH = (@("$d\.tools\flutter\bin") + $withoutOld) -join ';'

$seed = Join-Path $repoRoot 'app\assets\db\memonic_app_seed.db'
$seedBak = Join-Path $env:TEMP 'memonic_seed_original_patch.db'
Copy-Item $seed $seedBak -Force
try {
    Copy-Item $tmp $seed -Force
    Set-Location "$d\app"
    & $flutter pub get
    if ($LASTEXITCODE -ne 0) { throw 'pub get' }
    & $flutter build windows --release
    if ($LASTEXITCODE -ne 0) { throw 'flutter build windows nie powiodl sie' }
}
finally {
    Copy-Item $seedBak $seed -Force
    Set-Location $repoRoot
}

# pliki programu (bez portable.flag i bez user_data - zostaja u uzytkownika)
$stage = Join-Path $env:TEMP "patch_stage_$Label"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
Copy-Item "$d\app\build\windows\x64\runner\Release\*" $stage -Recurse
Rename-Item (Join-Path $stage 'memonic_app.exe') 'Baza Pytan Apka.exe'
foreach ($bad in 'portable.flag', 'user_data') { $p = Join-Path $stage $bad; if (Test-Path $p) { Remove-Item $p -Recurse -Force } }
$zipDest = Join-Path $OutDir "1 - PATCH programu $Label (rozpakuj do folderu programu).zip"
if (Test-Path $zipDest) { Remove-Item $zipDest -Force }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipDest -CompressionLevel Optimal

# czysta baza do importu (tryb D)
Copy-Item $tmp (Join-Path $OutDir "2 - Baza pytan do importu ($Label).db") -Force

$hashAfter = (Get-FileHash $userDb -Algorithm MD5).Hash
if ($hashBefore -ne $hashAfter) { throw 'UWAGA: baza uzytkownika zmienila sie w trakcie budowy!' }
Write-Host "Gotowe: $OutDir"
