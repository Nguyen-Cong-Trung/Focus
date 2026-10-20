@echo off
setlocal
cd /d "%~dp0"
if not exist ".runtime\Scripts\pythonw.exe" (
    echo Please run Setup.cmd first.
    pause
    exit /b 1
)
start "Focus" "%~dp0.runtime\Scripts\pythonw.exe" -B "%~dp0PythonProject\main.py"
