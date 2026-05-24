@echo off
title screenpipe recorder (bottom monitor only)

REM Resolve bottom monitor's screenpipe ID. Falls back to 65539 (DISPLAY2)
REM if the .txt file is missing.
set MID=65539
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "if (Test-Path 'C:\Users\dongk\.local\bin\screenpipe_monitor_id.txt') { (Get-Content 'C:\Users\dongk\.local\bin\screenpipe_monitor_id.txt' -TotalCount 1).Trim() }"') do set MID=%%i

set /p SCREENPIPE_API_KEY=<"C:\Users\dongk\screenpipe_api_key.txt"

"C:\Program Files\nodejs\npx.cmd" -y screenpipe record ^
    --data-dir "D:\screenpipe_recording_data" ^
    --disable-audio ^
    --monitor-id %MID% ^
    --ignored-windows "foobar2000" ^
    --min-capture-interval-ms 1000 ^
    --idle-capture-interval-ms 2000
