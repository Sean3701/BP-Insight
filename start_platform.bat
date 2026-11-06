@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python virtual environment not found.
  echo Expected .venv\Scripts\python.exe in this folder.
  pause
  exit /b 1
)
if not exist "launcher.py" (
  echo [ERROR] launcher.py is missing.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "launcher.py"
echo.
echo Launcher exited. Press any key to close.
pause >nul
