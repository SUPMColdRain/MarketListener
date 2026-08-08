param(
    [string]$TaskName = "MarketMonitorNightly",
    [string]$Time = "18:30"
)
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $root "scripts\run-nightly.ps1"
$state = Join-Path $env:USERPROFILE ".market-monitor\nightly-state.sqlite"
$steps = Join-Path $root "scripts\nightly-steps.example.json"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $state) | Out-Null

$xmlPath = Join-Path $env:TEMP "market-monitor-nightly-task.xml"
$startBoundary = "2026-08-06T$Time`:00"
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -StatePath `"$state`" -StepsPath `"$steps`" -Resume"
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Market monitor nightly pipeline (health check + data jobs)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>$arguments</Arguments>
    </Exec>
  </Actions>
</Task>
"@
[System.IO.File]::WriteAllText($xmlPath, $xml, [System.Text.Encoding]::Unicode)

& schtasks.exe /Query /TN $TaskName 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    & schtasks.exe /Delete /TN $TaskName /F 2>&1 | Out-Null
}
& schtasks.exe /Create /TN $TaskName /XML $xmlPath /F 2>&1
$createExit = $LASTEXITCODE
if ($createExit -ne 0) {
    Write-Error "Failed to create scheduled task (elevation may be required)."
    exit 1
}
& schtasks.exe /Query /TN $TaskName /V /FO LIST
exit $LASTEXITCODE
