@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup-local.ps1"
if errorlevel 1 (
    echo.
    echo Backup failed.
    pause
    exit /b 1
)

echo.
echo Backup complete.
