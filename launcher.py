"""Local one-click launcher for VC Intelligence Platform M01 (Windows)."""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / '.venv' / 'Scripts' / 'python.exe'
BACKEND = 'http://127.0.0.1:8000/health'
FRONTEND = 'http://127.0.0.1:8501'
LOGS = ROOT / 'data' / 'logs'


def get(url: str, timeout: float = 1.5) -> tuple[int, str] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read(4096).decode('utf-8', errors='replace')
    except (OSError, urllib.error.URLError):
        return None


def main() -> int:
    if not PYTHON.is_file():
        print('ERROR: Missing .venv\\Scripts\\python.exe')
        print('Run: py -3.11 -m venv .venv')
        return 1
    if not (ROOT / 'backend' / 'main.py').exists() or not (ROOT / 'frontend' / 'app.py').exists():
        print('ERROR: Run this file from the M01 project root. Missing backend/main.py or frontend/app.py.')
        return 1
    LOGS.mkdir(parents=True, exist_ok=True)
    processes = []
    handles = []
    try:
        backend = get(BACKEND)
        if backend and 'vc-platform-backend' in backend[1] and '"status":"ok"' in backend[1].replace(' ', ''):
            print('[OK] Backend already running on port 8000.')
        elif backend:
            print('[ERROR] Port 8000 is used by a different service. Stop it before using this launcher.')
            return 1
        else:
            handle = (LOGS / 'backend.log').open('a', encoding='utf-8')
            handles.append(handle)
            proc = subprocess.Popen([str(PYTHON), '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000'], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
            processes.append(proc)
            print('[START] Backend...')
        for _ in range(35):
            result = get(BACKEND)
            if result and 'vc-platform-backend' in result[1]:
                break
            if processes and processes[-1].poll() is not None:
                break
            time.sleep(.4)
        else:
            print('[ERROR] Backend did not become ready. See data\\logs\\backend.log')
            return 1
        if not get(BACKEND):
            print('[ERROR] Backend failed. See data\\logs\\backend.log')
            return 1

        if get(FRONTEND):
            print('[OK] Frontend already running on port 8501.')
        else:
            handle = (LOGS / 'frontend.log').open('a', encoding='utf-8')
            handles.append(handle)
            proc = subprocess.Popen([str(PYTHON), '-m', 'streamlit', 'run', 'frontend/app.py', '--server.address', '127.0.0.1', '--server.port', '8501', '--server.headless', 'true'], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
            processes.append(proc)
            print('[START] Frontend...')
        for _ in range(50):
            if get(FRONTEND):
                break
            if processes and processes[-1].poll() is not None:
                break
            time.sleep(.4)
        else:
            print('[ERROR] Frontend did not become ready. See data\\logs\\frontend.log')
            return 1
        if not get(FRONTEND):
            print('[ERROR] Frontend failed. See data\\logs\\frontend.log')
            return 1

        print('\n[READY] VC Intelligence Platform')
        print('Open only this page: ' + FRONTEND)
        print('Backend health (for troubleshooting): ' + BACKEND)
        print('Keep this window open; press Ctrl+C to stop services started here.')
        webbrowser.open(FRONTEND)
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    print('[ERROR] A service exited. Check data\\logs\\*.log')
                    return 1
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nStopping services started by this launcher...')
        return 0
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    sys.exit(main())
