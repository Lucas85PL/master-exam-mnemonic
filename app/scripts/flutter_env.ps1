# Master Exam Mnemonic 2.0 - środowisko Flutter.
# Używaj TYLKO SDK z katalogu projektu (.tools\flutter). Stary C:\...\flutter\flutter bywał uszkodzony.
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$flutterRoot = Join-Path $repoRoot ".tools\flutter"

# Litera wirtualnego dysku (subst). Ścieżka projektu ma spacje, a build natywny (hooks/Gradle) na nich się wywala,
# więc budujemy z dysku bez spacji. Litera Q: jest inna niż w starej wersji (M:), żeby się nie mieszały.
$script:ProjectDrive = 'Q'

function Mount-ProjectDrive {
    param([string]$Root)
    $letter = $script:ProjectDrive
    $mapped = (subst) | Where-Object { $_ -like "${letter}:\*" }
    if ($mapped) {
        $target = ($mapped -split '=> ', 2)[1].Trim()
        if ($target.TrimEnd('\') -ne $Root.TrimEnd('\')) {
            subst "${letter}:" /D | Out-Null
            subst "${letter}:" $Root
        }
    } else {
        subst "${letter}:" $Root
    }
}

if (-not (Test-Path (Join-Path $flutterRoot "packages\flutter_tools\pubspec.yaml"))) {
    throw "Brak SDK w $flutterRoot. Skopiuj SDK z poprzedniej wersji albo: git clone -b stable --depth 1 https://github.com/flutter/flutter.git .tools/flutter"
}

$env:FLUTTER_ROOT = $flutterRoot
$withoutOldFlutter = ($env:PATH -split ';' | Where-Object {
    $_ -and ($_ -notmatch '\\flutter\\flutter\\bin' -and $_ -notmatch '\\flutter\\bin$')
})
$env:PATH = (@($flutterRoot + '\bin') + $withoutOldFlutter) -join ';'

function Invoke-MemonicFlutter {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & (Join-Path $flutterRoot 'bin\flutter.bat') @Args
}
