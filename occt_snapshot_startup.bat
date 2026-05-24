@echo off
title OCCT session snapshotter
if not exist "D:\occt_history\snapshots" mkdir "D:\occt_history\snapshots"
"C:\Users\dongk\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\dongk\.claude\skills\occt-sensors\occt_snapshot.py" >> "D:\occt_history\snapshot.log" 2>&1
