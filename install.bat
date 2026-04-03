@echo off
chcp 65001 >nul
title Package Installer
cd /d "%~dp0"

echo ========================================
echo   AI Meeting Minutes - Package Install
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed.
    echo Install Python from https://www.python.org
    pause
    exit /b 1
)

echo Installing packages...
echo.
pip install -r requirements.txt

echo.
if errorlevel 1 (
    echo [ERROR] Package installation failed.
) else (
    echo ========================================
    echo   Done! Run run.bat to start.
    echo ========================================
)
echo.
pause
