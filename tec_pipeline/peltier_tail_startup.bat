@echo off
title Peltier tailer
if not exist "D:\occt_history" mkdir "D:\occt_history"
"C:\Users\dongk\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\dongk\.local\bin\peltier_tail.py" >> "D:\occt_history\peltier_tail.log" 2>&1
