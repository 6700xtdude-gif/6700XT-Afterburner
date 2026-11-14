@echo off
echo =======================================================
echo  Setting Windows Pagefile to Default (System Managed)
echo =======================================================
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"\"%~dp0manage_pagefile.ps1\"\" -Mode default'"
