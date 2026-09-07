$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.13 -m venv .venv
}

$Python = ".\.venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -e ".[desktop]"
& $Python -m pip install --group dev --group packaging
& $Python -m pytest
& $Python -m PyInstaller --clean --noconfirm OsintEngine.spec

$Exe = Join-Path $Root "dist\OSINT_Engine.exe"
if (-not (Test-Path $Exe)) {
    throw "No se generó $Exe"
}
Get-FileHash $Exe -Algorithm SHA256
Write-Host "Build listo: $Exe"
