"""Launch the new single-origin local UI; never reuse an unrelated listening service."""
import subprocess
import sys
import time
import urllib.request
import json
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8503'


def main():
    python=next((p for p in [ROOT/'.venv314/Scripts/python.exe',ROOT/'.venv/Scripts/python.exe',ROOT/'.venv/bin/python'] if p.exists()),Path(sys.executable))
    try:
        with urllib.request.urlopen(URL+'/health',timeout=1) as r:
            data=json.load(r)
        if data.get('service')=='vc-platform-backend':
            with urllib.request.urlopen(URL+'/api/v2/models',timeout=2):
                webbrowser.open(URL+'/app/')
                return
        raise RuntimeError('Port 8503 is already in use by another application.')
    except urllib.error.URLError:
        pass
    logs=ROOT/'data'/'logs';logs.mkdir(parents=True,exist_ok=True)
    with (logs/'web.log').open('a',encoding='utf-8') as log:
        proc=subprocess.Popen([str(python),'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8503'],cwd=ROOT,stdout=log,stderr=log)
        try:
            for _ in range(60):
                if proc.poll() is not None:
                    raise RuntimeError('Startup failed. See data/logs/web.log')
                try:
                    with urllib.request.urlopen(URL+'/health',timeout=1):
                        break
                except OSError:
                    time.sleep(.5)
            else:
                raise RuntimeError('Startup timed out. See data/logs/web.log')
            webbrowser.open(URL+'/app/')
            print('VC Intelligence: '+URL+'/app/ (Ctrl+C to stop)')
            proc.wait()
        except KeyboardInterrupt:
            pass
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill()


if __name__=='__main__':
    main()
