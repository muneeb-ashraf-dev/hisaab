@echo off
setlocal
title Hisaab Frontend

cd /d "%~dp0frontend"

where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo ERROR: npm.cmd was not found.
    echo Install Node.js 20.9 or newer and try again.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo Installing frontend dependencies for the first run...
    call npm.cmd install
    if errorlevel 1 (
        echo.
        echo ERROR: npm install failed.
        pause
        exit /b 1
    )
)

echo Starting Hisaab web app on http://localhost:3000 ...
echo Press Ctrl+C to stop.
echo.
call npm.cmd run dev

echo.
echo Frontend stopped.
pause
