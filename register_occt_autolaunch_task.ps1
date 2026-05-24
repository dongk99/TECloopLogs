Start-Transcript -Path "C:\Users\dongk\.local\bin\register_occt_autolaunch_task.log" -Force | Out-Null

$TaskName = "OCCT Auto-launch"
$OcctExe  = "C:\Users\dongk\Downloads\OCCT.exe"
$User     = "$env:USERDOMAIN\$env:USERNAME"

if (-not (Test-Path $OcctExe)) {
    Write-Error "OCCT.exe not found at $OcctExe"
    Stop-Transcript | Out-Null
    exit 1
}

# Note: when this script runs elevated via RunAs, $env:USERNAME is still the
# launching user, not SYSTEM, because Start-Process -Verb RunAs preserves the
# user identity. That's what we want — task should run as the desktop user
# (so the GUI displays) with elevation (so UAC manifest is satisfied).
Write-Host "Registering '$TaskName' for user: $User -> $OcctExe"

schtasks /Delete /TN $TaskName /F 2>$null | Out-Null

$action    = New-ScheduledTaskAction -Execute $OcctExe
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $User
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 0) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Launch OCCT.exe elevated at user logon. Replaces the deleted broken 'OCCT Auto-start Monitoring' task." | Out-Null

Write-Host "Registered: $TaskName"
schtasks /Query /TN $TaskName /V /FO LIST | Select-String -Pattern "TaskName|Status|Run As User|Schedule Type|Task To Run"

Stop-Transcript | Out-Null
