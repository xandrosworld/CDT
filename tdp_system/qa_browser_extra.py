"""Replay quotation, price history and partial invoice allocation on isolated data."""
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
    parser.add_argument('--case', choices=['quote_ui', 'order_price', 'outgoing_readiness'])
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent
    results = []
    for name in ([args.case] if args.case else ['quote_ui', 'order_price', 'outgoing_readiness']):
        folder = output / name
        folder.mkdir()
        http_port, cdp_port = 18820, 19420
        for port in (http_port, cdp_port):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', port)) == 0:
                    raise RuntimeError(f'Test port {port} occupied')
        fixture = root / f'browser_fixture_{name}_server.py'
        code = fixture.read_text(encoding='utf-8').replace('port=18799', f'port={http_port}')
        local_fixture = folder / 'fixture.py'
        local_fixture.write_text(code, encoding='utf-8')
        script = (root / f'browser_smoke_{name}.js').read_text(encoding='utf-8')
        script = script.replace('127.0.0.1:18799', f'127.0.0.1:{http_port}')
        script = script.replace('127.0.0.1:19309', f'127.0.0.1:{cdp_port}')
        script = script.replace('D:/TDP_TEMP_OUTGOING', folder.as_posix())
        private_script = folder / 'smoke.cjs'
        private_script.write_text(script, encoding='utf-8')
        env = dict(os.environ, PYTHONIOENCODING='utf-8', TDP_DATA_DIR=str(folder / 'data'),
                   TDP_DB_PATH=str(folder / 'fixture.sqlite3'), TDP_EXPORT_DIR=str(folder / 'exports'),
                   MSMI_API_BASE_URL='http://127.0.0.1:9', MSMI_API_TOKEN='offline-test',
                   MINVOICE_API_BASE_URL='http://127.0.0.1:9', MINVOICE_USERNAME='offline-test',
                   MINVOICE_PASSWORD='offline-test')
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        launcher = ("from pathlib import Path; import sys; fixture=sys.argv.pop(1); origin=sys.argv.pop(1); "
                    "exec(compile(Path(fixture).read_text(encoding='utf-8'),origin,'exec'),"
                    "{'__name__':'__main__','__package__':'tdp_system','__file__':origin})")
        server = browser = None
        try:
            with (folder / 'server.log').open('wb') as log:
                server = subprocess.Popen([sys.executable, '-c', launcher, str(local_fixture), str(fixture),
                                           str(http_port), str(folder)], env=env, stdout=log, stderr=log,
                                          creationflags=flags)
            browser = subprocess.Popen([os.environ.get('TDP_BROWSER_PATH', 'C:/Program Files/Google/Chrome/Application/chrome.exe'),
                '--headless=new', '--disable-gpu', '--no-first-run', f'--remote-debugging-port={cdp_port}',
                '--user-data-dir=' + str(folder / 'profile'), 'about:blank'], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=flags)
            for endpoint in (f'http://127.0.0.1:{http_port}/health', f'http://127.0.0.1:{cdp_port}/json/list'):
                until = time.monotonic() + 60
                while True:
                    try:
                        with urlopen(endpoint, timeout=2) as response: response.read()
                        break
                    except OSError:
                        if server.poll() is not None or time.monotonic() > until:
                            raise RuntimeError('Fixture startup failed')
                        time.sleep(.2)
            command = ['node', str(private_script), f'http://127.0.0.1:{http_port}', f'http://127.0.0.1:{cdp_port}']
            if name == 'quote_ui':
                command.extend([str(folder / 'quote-conflict.xlsx'), str(folder / 'quote-clean.xlsx')])
            with (folder / 'browser.log').open('wb') as log:
                run = subprocess.run(command, stdout=log, stderr=log, timeout=240)
            result = {'case': name, 'ok': run.returncode == 0, 'log': str(folder / 'browser.log')}
            results.append(result)
            print(json.dumps(result), flush=True)
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
    (output / 'result.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return 0 if all(item['ok'] for item in results) else 1


if __name__ == '__main__': raise SystemExit(main())
