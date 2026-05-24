@echo off
title OCCT bin tail
if not exist "D:\occt_history" mkdir "D:\occt_history"
"C:\Users\dongk\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\dongk\.local\bin\occt_bin_tail.py" >> "D:\occt_history\occt_bin_tail.log" 2>&1
