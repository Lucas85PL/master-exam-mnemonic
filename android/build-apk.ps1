# Budowa APK (release, sideload) - Master Exam Mnemonic 2.0.
# Wymaga: Flutter SDK w .tools\flutter, Android SDK (ANDROID_HOME lub domyslna lokalizacja Android Studio), internet
# przy pierwszym budowaniu (Gradle/pub pobiera zaleznosci do .cache\).
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent

. (Join-Path $repoRoot 'app\scripts\flutter_env.ps1')
Mount-ProjectDrive $repoRoot
$d = "$($script:ProjectDrive):"

# Caches (Gradle, pub) w katalogu projektu - bez spacji w sciezce (native assets / Gradle)
$env:FLUTTER_ROOT = "$d\.tools\flutter"
$env:GRADLE_USER_HOME = "$d\.cache\gradle"
$env:PUB_CACHE = "$d\.cache\pub"
New-Item -ItemType Directory -Force -Path $env:GRADLE_USER_HOME, $env:PUB_CACHE | Out-Null
$flutter = "$d\.tools\flutter\bin\flutter.bat"
$withoutOld = ($env:PATH -split ';' | Where-Object { $_ -and $_ -notmatch '\\flutter\\flutter\\bin' })
$env:PATH = (@("$d\.tools\flutter\bin") + $withoutOld) -join ';'

Set-Location "$d\app"
& $flutter pub get
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $flutter build apk --release
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$apk = "$d\app\build\app\outputs\flutter-apk\app-release.apk"
$dest = "$d\dist\Master-Exam-Mnemonic-2.0.apk"
New-Item -ItemType Directory -Force -Path "$d\dist" | Out-Null
Copy-Item $apk $dest -Force
Write-Host "APK: $dest"
