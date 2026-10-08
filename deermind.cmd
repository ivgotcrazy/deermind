@echo off
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deermind.ps1" %*
exit /b %errorlevel%
