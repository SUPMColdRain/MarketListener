param(
    [Parameter(Mandatory = $true)][string]$ApkPath
)
$ErrorActionPreference = "Continue"
if (-not (Test-Path -LiteralPath $ApkPath)) {
    Write-Error "APK not found: $ApkPath"
    exit 2
}

# Locate zipalign from any installed Android SDK build-tools version.
$sdkRoot = $env:ANDROID_HOME
if (-not $sdkRoot) { $sdkRoot = $env:ANDROID_SDK_ROOT }
$zipalign = $null
if ($sdkRoot) {
    $candidates = Get-ChildItem -Path (Join-Path $sdkRoot "build-tools") -Recurse -Filter "zipalign.exe" -ErrorAction SilentlyContinue
    $zipalign = $candidates | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $zipalign) {
    Write-Error "zipalign not found under ANDROID_HOME/ANDROID_SDK_ROOT build-tools"
    exit 2
}

# -c checks alignment only (no rewrite); 4-byte ZIP alignment plus -P 16
# requests 16 KiB page alignment for uncompressed native libraries.
& $zipalign -c -P 16 4 $ApkPath
$exit = $LASTEXITCODE
if ($exit -eq 0) {
    Write-Output "16 KiB page alignment check PASSED: $ApkPath"
} else {
    Write-Error "16 KiB page alignment check FAILED: $ApkPath"
}
exit $exit
