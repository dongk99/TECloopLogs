@echo off
title OCCT screenpipe extractor
if not exist "D:\occt_history" mkdir "D:\occt_history"
"C:\Users\dongk\AppData\Local\Programs\Python\Python311\python.exe" "C:\Users\dongk\.local\bin\occt_screenpipe_extract.py" >> "D:\occt_history\occt_screenpipe_extract.log" 2>&1
