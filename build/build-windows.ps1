# build/build-windows.ps1
# Build the Windows x86-64 binary. Run from the project root in PowerShell:
#   .\build\build-windows.ps1
#
# Requires Python 3.12+ on PATH and uv installed (https://docs.astral.sh/uv/).

$ErrorActionPreference = "Stop"

if (-not (Test-Path "pyproject.toml")) {
    Write-Error "Run this script from the project root."
}

Write-Host "==> Ensuring pyinstaller is installed in the venv" -ForegroundColor Cyan
uv pip install pyinstaller --quiet

Write-Host "==> Running PyInstaller" -ForegroundColor Cyan
uv run pyinstaller build\glycerin_calculator.spec `
  --clean --noconfirm `
  --workpath "$env:TEMP\pyinstaller-glycerin"

Write-Host ""
Write-Host "Done. Binary directory: dist\glycerin-calculator\" -ForegroundColor Green
Write-Host "Run with:  .\dist\glycerin-calculator\glycerin-calculator.exe" -ForegroundColor Green
