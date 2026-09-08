"""Run current browser workflows against fresh, isolated fixtures, one per case."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

CASES = {
    'invoice_issuance': ('invoice_issuance_server', 18854, 'ISSUANCE'),
    'output_names': ('date_picker_server', 18805, 'INVOICE'),
    'catalog_worksheet': ('catalog_worksheet', 18852, 'CATALOG'),
    'startup_layout': ('date_picker_server', 18805, 'INVOICE'),
    'mapping_real_large': ('date_picker_server', 18805, 'INVOICE'),
    'mapping_large': ('date_picker_server', 18805, 'INVOICE'),
    'receipt_period_scope': ('date_picker_server', 18805, 'INVOICE'),
    'inventory_tools': ('inventory_tools_server', 18853, 'TOOLS'),
    'invoice_factor': ('date_picker_server', 18805, 'INVOICE'),
    'expense_confirmation': ('date_picker_server', 18805, 'EXPENSE'),
    'pending_receipts': ('date_picker_server', 18805, 'INVOICE'),
    'invoice_review': ('invoice_review_server', 18806, 'REVIEW'),
    'inventory_reports': ('inventory_reports_server', 18807, 'INVENTORY'),
    'stock_workflows': ('stock_workflows', 18920, 'STOCK'),
    'compact_workspace': ('compact_workspace', 18809, 'COMPACT'),
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=CASES)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent
    results = []
    for name in ([args.case] if args.case else CASES):
        fixture, port, prefix = CASES[name]
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError(f'Fixture port {port} occupied; no existing process stopped')
        folder = output / name
        (folder / 'tmp').mkdir(parents=True)
        env = dict(os.environ, PYTHONIOENCODING='utf-8', TEMP=str(folder / 'tmp'), TMP=str(folder / 'tmp'),
                   MSMI_API_BASE_URL='http://127.0.0.1:9', MSMI_API_TOKEN='offline-test',
                   MINVOICE_API_BASE_URL='http://127.0.0.1:9', MINVOICE_USERNAME='offline-test', MINVOICE_PASSWORD='offline-test')
        env[f'TDP_{prefix}_TEST_URL'] = f'http://127.0.0.1:{port}'
        env['TDP_FIXTURE_OUTPUT'] = str(folder)
        if name == 'receipt_period_scope': env['TDP_FIXTURE_OLD_PENDING']='1'
        if name == 'output_names': env['TDP_FIXTURE_OUTPUT_NAMES']='1'
        for key in ('EXPENSE', 'PENDING', 'REVIEW', 'INVENTORY'):
            env[f'TDP_{key}_SCREENSHOT'] = str(folder / f'{key.lower()}.png')
        # Load the fixture as a module with connector-file lookup disabled first.
        launcher = ('import runpy; from tdp_system import server; '
                    'server.connector_config_paths=lambda:[]; '
                    f'runpy.run_module("tdp_system.browser_fixture_{fixture}",run_name="__main__")')
        # Most fixtures set their paths before importing server. The launcher
        # imports it first to disable connector lookup, so isolate paths here too.
        env.update(TDP_DATA_DIR=str(folder / 'data'), TDP_DB_PATH=str(folder / 'fixture.sqlite3'),
                   TDP_EXPORT_DIR=str(folder / 'exports'))
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        process = None
        started = time.monotonic()
        result = {'case': name, 'ok': False}
        try:
            with (folder / 'server.log').open('wb') as log:
                process = subprocess.Popen([sys.executable, '-c', launcher], cwd=root.parent, env=env,
                                           stdout=log, stderr=log, creationflags=flags)
            deadline = time.monotonic() + 60
            while True:
                try:
                    with urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as response:
                        if response.status == 200: break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Fixture startup failed; see server.log')
                    time.sleep(.2)
            with (folder / 'browser.log').open('wb') as log:
                run = subprocess.run(['node', str(root / f'browser_smoke_{name}.cjs')], cwd=folder,
                                     env=env, stdout=log, stderr=log, timeout=420, creationflags=flags)
            result.update(ok=run.returncode == 0, exit_code=run.returncode)
        except Exception as error:
            result['error'] = str(error)
        finally:
            if process is not None:
                import psutil
                try:
                    children = psutil.Process(process.pid).children(recursive=True)
                    process.terminate()
                    for child in children:
                        try: child.terminate()
                        except psutil.Error: pass
                    process.wait(timeout=10)
                except (psutil.Error, subprocess.TimeoutExpired): pass
        result['seconds'] = round(time.monotonic() - started, 1)
        results.append(result)
        (output / 'result.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
    return 0 if all(r['ok'] for r in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
