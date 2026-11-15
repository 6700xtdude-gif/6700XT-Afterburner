@echo off
title AfterBurner Control Center Launcher
cd /d "C:\Users\6700XT\Documents\Strata"

netstat -ano | findstr "127.0.0.1:8090" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "AfterBurner Control Center" /min python "C:\Users\6700XT\Documents\Strata\dashboard\server.py"
    timeout /t 2 /nobreak >nul
)

start "" "http://127.0.0.1:8090"
