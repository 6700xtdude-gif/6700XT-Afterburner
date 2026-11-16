@echo off
title AfterBurner Control Center Launcher
cd /d "C:\Users\6700XT\6700XT-Afterburner"

netstat -ano | findstr "127.0.0.1:3333" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "AfterBurner Control Center" /min "C:\Program Files\nodejs\node.exe" "C:\Users\6700XT\.gemini\antigravity\scratch\dashboard\server.js"
    timeout /t 2 /nobreak >nul
)

start "" "http://127.0.0.1:3333"
