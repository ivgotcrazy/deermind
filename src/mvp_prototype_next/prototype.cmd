@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\prototype.ps1" %*
exit /b %errorlevel%
