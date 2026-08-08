param(
    [Parameter(Mandatory = $true)][string]$StatePath,
    [Parameter(Mandatory = $true)][string]$StepsPath,
    [string]$DataRoot = "",
    [switch]$Resume,
    [string]$JobId = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "desktop\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "venv python not found: $python"
    exit 2
}
$arguments = @("-m", "market_monitor.ops_cli", "nightly", "--state", $StatePath, "--steps", $StepsPath)
if ($DataRoot) { $arguments += @("--data-root", $DataRoot) }
if ($Resume) { $arguments += "--resume" }
if ($JobId) { $arguments += @("--job-id", $JobId) }
& $python $arguments
exit $LASTEXITCODE
