@echo off
chcp 65001 >nul
title Meeting Minutes Writer
cd /d "%~dp0"

:: Find real Python path (exclude WindowsApps)
set "PYTHON="
for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        if not defined PYTHON set "PYTHON=%%i"
    )
)

if not defined PYTHON (
    echo [ERROR] Python not found.
    echo Install Python from https://www.python.org
    pause
    exit /b 1
)

"%PYTHON%" main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to run.
    echo Run install.bat first if packages are not installed.
    pause
)
