@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m venv .runtime
if errorlevel 1 goto failed
".runtime\Scripts\python.exe" -m pip install --no-cache-dir --no-compile -r "PythonProject\requirements.txt"
if errorlevel 1 goto failed
echo Ready. Open Focus.cmd to start.
pause
exit /b 0
:failed
echo Setup failed. Install 64-bit Python 3.12 with Tk support, then retry.
pause
exit /b 1
