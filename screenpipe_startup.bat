@echo off
title screenpipe recorder
set /p SCREENPIPE_API_KEY=<"C:\Users\dongk\screenpipe_api_key.txt"
"C:\Program Files\nodejs\npx.cmd" -y screenpipe record --data-dir "D:\screenpipe_recording_data" --disable-audio
