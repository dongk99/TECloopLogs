# Registers a Scheduled Task that runs occt_snapshot_startup.bat at boot,
# as SYSTEM, with highest privileges. Fires BEFORE user logon so OCCT
# (which launches at logon via Startup folder) hasn't yet wiped State.
#
# One-time UAC prompt to register. After that, runs automatically every boot.

Start-Transcript -Path "C:\Users\dongk\.local\bin\register_occt_snapshot_task.log" -Force | Out-Null

$TaskName = "OCCT Session Snapshot"
$BatPath  = "C:\Users\dongk\.local\bin\occt_snapshot_startup.bat"

if (-not (Test-Path $BatPath)) {
    Write-Error "Snapshot bat not found at $BatPath"
    exit 1
}

# Remove any prior version of this task
schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

$action    = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatPath`""
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Snapshot OCCT State dir at boot before OCCT launches at logon and wipes it." | Out-Null

Write-Host "Registered task: $TaskName"
schtasks /Query /TN $TaskName /V /FO LIST | Select-String -Pattern "TaskName|Status|Next Run|Run As User|Schedule Type|Start Time"

Stop-Transcript | Out-Null
