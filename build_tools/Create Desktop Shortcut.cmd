@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install Desktop Shortcut.ps1"
if errorlevel 1 (
    echo Shortcut could not be created.
) else (
    echo Focus shortcut is ready on your desktop.
)
pause
