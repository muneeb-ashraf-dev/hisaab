@echo off
setlocal
title Hisaab Launcher

echo Starting Hisaab...
start "Hisaab Backend" cmd /k ""%~dp0start-backend.bat""
timeout /t 3 /nobreak >nul
start "Hisaab Frontend" cmd /k ""%~dp0start-frontend.bat""
timeout /t 5 /nobreak >nul
start "" "http://localhost:3000"

endlocal
