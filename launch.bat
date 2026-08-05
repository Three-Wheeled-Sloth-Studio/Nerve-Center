@echo off
setlocal

set "REPO_ROOT=%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%launch.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Nerve Center exited with error code %EXIT_CODE%.
  pause
)

exit /b %EXIT_CODE%
