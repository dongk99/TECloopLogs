@echo off
title OCCT historical logger
if not exist "D:\occt_history" mkdir "D:\occt_history"
"C:\Users\dongk\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\dongk\.claude\skills\occt-sensors\occt_logger.py" >> "D:\occt_history\logger.log" 2>&1
