@echo off
echo =======================================================
echo  Setting Windows Pagefile for 64GB/96GB Rig
echo =======================================================
echo Options:
echo 1. Set to 64GB Mode (96 GB Min / 192 GB Max)
echo 2. Set to 96GB Mode (144 GB Min / 288 GB Max)
echo 3. Set to Default (System Managed)
echo 4. Check Current Status
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"\"%~dp0manage_pagefile.ps1\"\" -Mode 64gb'"
)
if "%choice%"=="2" (
    powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"\"%~dp0manage_pagefile.ps1\"\" -Mode 96gb'"
)
if "%choice%"=="3" (
    powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"\"%~dp0manage_pagefile.ps1\"\" -Mode default'"
)
if "%choice%"=="4" (
    powershell -ExecutionPolicy Bypass -File "%~dp0manage_pagefile.ps1" -Mode status
    pause
)
