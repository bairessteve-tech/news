$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\fetch_news.py"
$taskName = "NewsDailyFetch"

if (-not (Test-Path $python)) {
  throw "Python venv not found: $python"
}

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 8:00am
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "Created daily task: $taskName (every day 08:00)"
Get-ScheduledTaskInfo -TaskName $taskName | Format-List LastRunTime, NextRunTime, LastTaskResult
