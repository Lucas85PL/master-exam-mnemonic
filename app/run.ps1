# Master Exam Mnemonic 2.0 - uruchamianie / budowanie aplikacji z lokalnym Flutter SDK (.tools\flutter w katalogu glownym).
# Sciezka projektu ma spacje - budujemy z wirtualnego dysku Q: (subst), inaczej build hooki sie wywalaja.
param(
    [ValidateSet('setup', 'pub-get', 'test', 'run-windows', 'build-windows', 'doctor')]
    [string]$Action = 'run-windows'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\flutter_env.ps1')

$repoRoot = Split-Path $PSScriptRoot -Parent
Mount-ProjectDrive $repoRoot
Set-Location "$($script:ProjectDrive):\app"

switch ($Action) {
    'doctor' { Invoke-MemonicFlutter doctor }
    'pub-get' { Invoke-MemonicFlutter pub get }
    'test' { Invoke-MemonicFlutter test }
    'setup' {
        if (-not (Test-Path 'windows\runner\main.cpp')) {
            Invoke-MemonicFlutter create . --platforms=windows,android
        }
        Invoke-MemonicFlutter pub get
        Invoke-MemonicFlutter test
    }
    'build-windows' {
        Get-Process -Name memonic_app -ErrorAction SilentlyContinue | Stop-Process -Force
        if (-not (Test-Path 'windows\runner\main.cpp')) {
            Invoke-MemonicFlutter create . --platforms=windows,android
        }
        Invoke-MemonicFlutter pub get
        Invoke-MemonicFlutter build windows --release
        Write-Host ''
        Write-Host 'Gotowe. Nastepnym razem uruchom Start.bat (szybki start bez konsoli Flutter).'
    }
    'run-windows' {
        $devMode = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\DeveloperSettings' -Name DeveloperModeEnabled -ErrorAction SilentlyContinue
        if ($devMode.DeveloperModeEnabled -ne 1) {
            Write-Host 'Wlacz Tryb deweloperski: Ustawienia -> Dla deweloperow -> Tryb deweloperski (ON).'
            Start-Process 'ms-settings:developers'
        }
        if (-not (Test-Path 'windows\runner\main.cpp')) {
            Invoke-MemonicFlutter create . --platforms=windows,android
        }
        Invoke-MemonicFlutter pub get
        Invoke-MemonicFlutter run -d windows
    }
}
