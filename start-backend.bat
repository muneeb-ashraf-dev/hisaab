@echo off
setlocal
title Hisaab Backend

set "PATH=%USERPROFILE%\.local\bin;%PATH%"
cd /d "%~dp0backend"

where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv was not found.
    echo Install it from https://docs.astral.sh/uv/ and try again.
    pause
    exit /b 1
)

if not exist ".env" (
    echo WARNING: backend\.env was not found.
    echo The built-in defaults will be used.
    echo.
)

echo Starting Hisaab API on http://127.0.0.1:8000 ...
echo Press Ctrl+C to stop.
echo.
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

echo.
echo Backend stopped.
pause
