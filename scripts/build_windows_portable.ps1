[CmdletBinding()]
param(
  [string]$Version = "0.1.0",
  [string]$OutputRoot = "dist"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$desktop = Join-Path $repo "desktop"
$python = Join-Path $desktop ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
Push-Location $desktop
try {
  & npm --prefix web run build
  & $python -m pip install pyinstaller
  & $python -m PyInstaller --noconfirm --clean --onedir --name MarketListener `
    --paths src --collect-all market_monitor --add-data "src\market_monitor\web_dist;market_monitor\web_dist" `
    src\market_monitor\cli.py
  $release = Join-Path $repo "$OutputRoot\MarketListener-Windows-x64-$Version"
  Remove-Item -Recurse -Force $release -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Force $release | Out-Null
  Copy-Item -Recurse -Force "dist\MarketListener\*" $release
  @'
@echo off
setlocal
set "ROOT=%~dp0"
set "DATA_DIR=%LOCALAPPDATA%\MarketListener\data"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
start "MarketListener" /b "%ROOT%MarketListener.exe" serve --data-root "%DATA_DIR%" --host 127.0.0.1 --port 8765 --quiet
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8765/
'@ | Set-Content -Encoding ascii (Join-Path $release "启动网页.cmd")
  Get-FileHash (Join-Path $release "MarketListener.exe") -Algorithm SHA256 | ForEach-Object { "$($_.Hash)  MarketListener.exe" } | Set-Content -Encoding ascii (Join-Path $release "SHA256SUMS.txt")
  Compress-Archive -Path "$release\*" -DestinationPath "$release.zip" -Force
  Write-Output $release
} finally { Pop-Location }
