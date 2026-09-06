"""Run a read-only browser against the already verified isolated Phong copy."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    p=argparse.ArgumentParser(); p.add_argument('--copy',type=Path,required=True); args=p.parse_args()
    root=args.copy.resolve()
    assert json.loads((root/'summary.json').read_text())['ok']
    for port in (18830,19430):
        with socket.socket() as sock: assert sock.connect_ex(('127.0.0.1',port))!=0
    env=dict(os.environ,TDP_DATA_DIR=str(root),TDP_DB_PATH=str(root/'copy.sqlite3'),TDP_EXPORT_DIR=str(root/'exports'),
        MSMI_API_BASE_URL='http://127.0.0.1:9',MSMI_API_TOKEN='offline-test',MINVOICE_API_BASE_URL='http://127.0.0.1:9',MINVOICE_USERNAME='offline-test',MINVOICE_PASSWORD='offline-test')
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    code="from tdp_system import server; from waitress import serve; server.connector_config_paths=lambda:[]; serve(server.app,host='127.0.0.1',port=18830,threads=4)"
    processes=[]
    with (root/'browser-server.log').open('wb') as log:
        try:
            processes.append(subprocess.Popen([sys.executable,'-c',code],env=env,stdout=log,stderr=log,creationflags=flags))
            processes.append(subprocess.Popen(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run',
                '--remote-debugging-port=19430',f'--user-data-dir={root / "browser-profile"}','about:blank'],stdout=log,stderr=log,creationflags=flags))
            for endpoint in ('http://127.0.0.1:18830/health','http://127.0.0.1:19430/json/list'):
                end=time.monotonic()+60
                while True:
                    try:
                        with urlopen(endpoint,timeout=2) as response: response.read()
                        break
                    except OSError:
                        if time.monotonic()>end: raise RuntimeError('Fixture did not start')
                        time.sleep(.2)
            subprocess.run(['node',str(Path(__file__).with_name('browser_smoke_phong.cjs')),str(root)],check=True,timeout=180)
        finally:
            import psutil
            for process in processes:
                try:
                    children=psutil.Process(process.pid).children(recursive=True); process.terminate()
                    for child in children:
                        try: child.terminate()
                        except psutil.Error: pass
                    process.wait(timeout=10)
                except (psutil.Error,subprocess.TimeoutExpired): pass


if __name__=='__main__': main()
