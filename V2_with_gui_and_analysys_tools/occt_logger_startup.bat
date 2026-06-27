@echo off
title OCCT historical logger
if not exist "D:\occt_history" mkdir "D:\occt_history"
"C:\Users\dongk\AppData\Local\Programs\Python\Python311\python.exe" "D:\occt_history\occt_logger.py" >> "D:\occt_history\logger.log" 2>&1
