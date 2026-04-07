@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-spygym.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo O inicializador encontrou um problema e foi encerrado com codigo %EXIT_CODE%.
  pause
)

exit /b %EXIT_CODE%
