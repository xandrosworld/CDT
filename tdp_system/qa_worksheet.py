"""Run worksheet browser checks using a disposable database and browser profile."""
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for port in (18803, 19313):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError('Test port occupied: ' + str(port))
    root = Path(__file__).resolve().parent
    fixture = root / 'browser_fixture_round2_server.py'
    code = fixture.read_text(encoding='utf-8').replace('D:/TDP_ROUND2', output.as_posix())
    local_fixture = output / 'fixture.py'
    local_fixture.write_text(code, encoding='utf-8')
    launcher = "from pathlib import Path; import sys; exec(compile(Path(sys.argv[1]).read_text(encoding='utf-8'),sys.argv[2],'exec'),{'__name__':'__main__','__package__':'tdp_system','__file__':sys.argv[2]})"
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    env = dict(os.environ, PYTHONIOENCODING='utf-8', TDP_DATA_DIR=str(output / 'data'),
               TDP_DB_PATH=str(output / 'isolated.sqlite3'), TDP_EXPORT_DIR=str(output / 'exports'),
               MSMI_API_BASE_URL='http://127.0.0.1:9', MINVOICE_API_BASE_URL='http://127.0.0.1:9')
    with (output / 'server.log').open('wb') as log:
        server = subprocess.Popen([sys.executable, '-c', launcher, str(local_fixture), str(fixture)],
                                  env=env, stdout=log, stderr=log, creationflags=flags)
        browser = None
        try:
            browser = subprocess.Popen([os.environ.get('TDP_BROWSER_PATH', 'C:/Program Files/Google/Chrome/Application/chrome.exe'),
                '--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=19313',
                '--user-data-dir=' + str(output / 'profile'), 'about:blank'], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=flags)
            for endpoint in ('http://127.0.0.1:18803/health','http://127.0.0.1:19313/json/list'):
                until = time.monotonic() + 40
                while True:
                    try:
                        with urlopen(endpoint, timeout=2) as response: response.read()
                        break
                    except OSError:
                        if time.monotonic() > until: raise RuntimeError('Startup failed')
                        time.sleep(.2)
            result = subprocess.run(['node', str(root / 'browser_smoke_worksheet.cjs'), str(output)], timeout=180)
            return result.returncode
        finally:
            import psutil
            for process in (server, browser):
                if process is None: continue
                try:
                    children = psutil.Process(process.pid).children(recursive=True)
                    process.terminate()
                    for child in children:
                        try: child.terminate()
                        except psutil.Error: pass
                    process.wait(timeout=10)
                except (psutil.Error, subprocess.TimeoutExpired): pass


if __name__ == '__main__': raise SystemExit(main())
