"""Replay the five existing acceptance scenarios in disposable browser profiles."""
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
    parser.add_argument('--round', type=int, choices=range(1, 6))
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    module_root = Path(__file__).resolve().parent
    chrome = Path(os.environ.get('TDP_BROWSER_PATH', 'C:/Program Files/Google/Chrome/Application/chrome.exe'))
    results = []
    for number in ([args.round] if args.round else range(1, 6)):
        fixture_name = 'invoice_round1' if number == 1 else f'round{number}'
        http_port = {1: 18801, 2: 18803, 3: 18805, 4: 18807, 5: 18808}[number]
        cdp_port = {1: 19311, 2: 19313, 3: 19315, 4: 19317, 5: 19318}[number]
        for port in (http_port, cdp_port):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', port)) == 0:
                    raise RuntimeError(f'Test port {port} already occupied')
        folder = output / f'round{number}'; folder.mkdir(exist_ok=True)
        (folder / 'downloads').mkdir(exist_ok=True)
        fixture = module_root / f'browser_fixture_{fixture_name}_server.py'
        code = fixture.read_text(encoding='utf-8').replace(f'D:/TDP_ROUND{number}', folder.as_posix())
        private_fixture = folder / 'fixture.py'; private_fixture.write_text(code, encoding='utf-8')
        script = module_root / f'browser_smoke_{fixture_name}.js'
        js = script.read_text(encoding='utf-8').replace(f'D:/TDP_ROUND{number}', folder.as_posix())
        js = js.replace('__dirname', json.dumps(module_root.as_posix()))
        js = js.replace(f'D:\\\\TDP_ROUND{number}\\\\downloads', (folder / 'downloads').as_posix())
        private_script = folder / 'smoke.cjs'; private_script.write_text(js, encoding='utf-8')
        env = dict(os.environ, TDP_DATA_DIR=str(folder / 'data'), TDP_DB_PATH=str(folder / 'default.sqlite3'),
                   TDP_EXPORT_DIR=str(folder / 'exports'), MSMI_API_BASE_URL='http://127.0.0.1:9',
                   MSMI_API_TOKEN='offline-test', MINVOICE_API_BASE_URL='http://127.0.0.1:9',
                   MINVOICE_USERNAME='offline-test', MINVOICE_PASSWORD='offline-test', PYTHONIOENCODING='utf-8')
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        launcher = ('from pathlib import Path; import sys; '
                    "exec(compile(Path(sys.argv[1]).read_text(encoding='utf-8'),sys.argv[2],'exec'),"
                    "{'__name__':'__main__','__package__':'tdp_system','__file__':sys.argv[2]})")
        with (folder / 'server.log').open('wb') as log:
            server = subprocess.Popen([sys.executable, '-c', launcher, str(private_fixture), str(fixture)],
                                      env=env, stdout=log, stderr=log, creationflags=flags)
            browser = subprocess.Popen([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                                        f'--remote-debugging-port={cdp_port}', f'--user-data-dir={folder / "profile"}',
                                        'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            try:
                for endpoint in (f'http://127.0.0.1:{http_port}/health', f'http://127.0.0.1:{cdp_port}/json/list'):
                    end = time.monotonic() + 60
                    while True:
                        try:
                            with urlopen(endpoint, timeout=2) as response: response.read()
                            break
                        except OSError:
                            if server.poll() is not None or time.monotonic() > end: raise RuntimeError('Fixture startup failed')
                            time.sleep(.2)
                with (folder / 'browser.log').open('wb') as browser_log:
                    run = subprocess.run(['node', str(private_script)], stdout=browser_log, stderr=browser_log, timeout=240)
                result = {'round': number, 'ok': run.returncode == 0, 'log': str(folder / 'browser.log')}
                results.append(result); print(json.dumps(result), flush=True)
            finally:
                # Terminate only the processes launched above and their own children.
                import psutil
                for parent in (server, browser):
                    try:
                        children = psutil.Process(parent.pid).children(recursive=True)
                        parent.terminate()
                        for child in children:
                            try: child.terminate()
                            except psutil.Error: pass
                        parent.wait(timeout=10)
                    except (psutil.Error, subprocess.TimeoutExpired): pass
    (output / 'result.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return 0 if all(r['ok'] for r in results) else 1


if __name__ == '__main__': raise SystemExit(main())
