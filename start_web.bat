@echo off
cd /d "%~dp0"
if exist .venv314\Scripts\python.exe (
  .venv314\Scripts\python.exe launcher_web.py
) else (
  .venv\Scripts\python.exe launcher_web.py
)
pause
