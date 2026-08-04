# D0-001 unified test entry.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$python = Join-Path $root "desktop\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "Python venv missing at $python. Run: python -m venv desktop\.venv"
    exit 1
}

Write-Host "== Desktop pytest =="
& $python -m pytest (Join-Path $root "desktop\tests") -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "== Android JVM unit tests =="
$gradlew = Join-Path $root "android\gradlew.bat"
if (-not (Test-Path -LiteralPath $gradlew)) {
    Write-Error "Gradle wrapper missing at $gradlew."
    exit 1
}

if (-not $env:JAVA_HOME) {
    $javaPath = (Get-Command java -ErrorAction Stop).Source
    $env:JAVA_HOME = Split-Path -Parent (Split-Path -Parent $javaPath)
    Write-Host "JAVA_HOME not set; using $env:JAVA_HOME"
}

& $gradlew -p (Join-Path $root "android") testDebugUnitTest
exit $LASTEXITCODE
