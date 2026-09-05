"""Replay an actual historical DB upgrade on a private copy; persist evidence.

Never launches against the supplied source DB or contacts invoice providers.
Use --exe to exercise an isolated copy of a packaged candidate twice.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from urllib.request import urlopen

from openpyxl import load_workbook

try:
    from contract_modules import as_date, first_value
    from build_release_inputs import snapshot_database
except ImportError:
    from .contract_modules import as_date, first_value
    from .build_release_inputs import snapshot_database

PROTECTED = ("orders", "msmi_invoice_items", "invoice_inventory_ledger", "inventory_transactions",
             "invoice_line_mappings", "invoice_mapping_revisions", "inventory_period_closures",
             "outgoing_invoice_drafts", "outgoing_invoice_lines")
QUERY = "?invoice_type=input&from=2026-08-01&to=2026-08-31&status=all&line_filter=all"


def read_db(path):
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def digest(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def state(path, protected_columns=None):
    with closing(read_db(path)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = protected_columns or {table: [r[1] for r in conn.execute(f'PRAGMA table_info({table})')]
                                        for table in PROTECTED if table in tables}
        invoices = [dict(r) for r in conn.execute("SELECT * FROM msmi_invoices ORDER BY id")]
        selected = [r for r in invoices if r['invoice_type'] == 'INPUT_ELECTRONIC_INVOICE'
                    and '2026-08-01' <= r['invoice_date'] <= '2026-08-31']
        expected = []
        for r in invoices:
            if r['invoice_type'] != 'INPUT_ELECTRONIC_INVOICE':
                continue
            source = json.loads(r['raw_json'])
            day = as_date(first_value(source, 'tdlap', 'nlap', 'invoiceDate', 'signedDate'))
            if '2026-08-01' <= day <= '2026-08-31':
                expected.append(r)
        return {
            'invoice_count': len(selected), 'ids': [r['id'] for r in selected],
            'expected_count': len(expected), 'expected_ids': [r['id'] for r in expected],
            'expected_amount': sum(r['total_amount'] for r in expected),
            'invoice_amount': sum(r['total_amount'] for r in selected),
            'source_fingerprint': digest([{k: v for k, v in r.items() if k not in ('invoice_date','updated_at')}
                                          for r in invoices]),
            'protected_columns': columns,
            'protected': {table: digest([tuple(r) for r in conn.execute(
                'SELECT '+','.join('"'+name+'"' for name in names)+f' FROM {table} ORDER BY rowid')])
                          for table, names in columns.items()},
            'repair_history_count': conn.execute('SELECT COUNT(*) FROM invoice_date_repairs').fetchone()[0]
                                    if 'invoice_date_repairs' in tables else 0,
        }


def check_exports(get, expected, directory):
    payload = json.loads(get('/api/invoice-workbench/invoices' + QUERY))
    assert payload['ok'], payload
    assert payload['totals']['invoice_count'] == expected['expected_count'], payload['totals']
    assert sorted(r['id'] for r in payload['items']) == sorted(expected['expected_ids'])
    assert abs(payload['totals']['invoice_amount'] - expected['expected_amount']) < .01
    assert payload['date_repair']['blocked_count'] == 0
    blob = get('/api/invoice-workbench/invoices/export' + QUERY)
    (directory/'input_august.xlsx').write_bytes(blob)
    book = load_workbook(io.BytesIO(blob), data_only=True)
    lines = [r for r in book.active.values if isinstance(r[0], str) and r[0].startswith('2026-08-')]
    assert len(lines) == len(payload['lines'])
    assert abs(sum(float(r[7] or 0) for r in lines) - payload['totals']['line_amount']) < .01
    # The literal grand total in the exported workbook uses the same scope as the screen.
    assert abs(float(list(book.active.values)[-1][7]) - expected['expected_amount']) < .01
    book.close()
    (directory/'listing_summary.json').write_text(json.dumps({
        'totals': payload['totals'], 'counts': payload['counts'],
        'date_repair': payload['date_repair'], 'invoice_ids': sorted(r['id'] for r in payload['items'])
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload['totals']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = args.source.resolve()
    before = state(source)
    db_path = root/'data'/'tdp.sqlite3'
    db_path.parent.mkdir()
    with closing(read_db(source)) as src, closing(sqlite3.connect(db_path)) as dst:
        src.backup(dst)
    offline = {'MSMI_API_BASE_URL': 'http://127.0.0.1:9', 'MSMI_API_TOKEN': 'offline-test',
               'MINVOICE_API_BASE_URL': 'http://127.0.0.1:9', 'MINVOICE_USERNAME': 'offline-test',
               'MINVOICE_PASSWORD': 'offline-test'}
    env = {**os.environ, **offline, 'TDP_DATA_DIR': str(db_path.parent), 'TDP_DB_PATH': str(db_path),
           'TDP_EXPORT_DIR': str(root/'exports'), 'TDP_ALLOW_LAN': '0', 'TDP_SMOKE_INSTANCE_ID': 'date-upgrade'}
    (root/'.env').write_text('\n'.join(f'{k}={v}' for k,v in offline.items()), encoding='utf-8')
    snapshots = []
    if args.exe:
        # Smoke mode requires all runtime paths below the OS temporary root.
        if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ValueError('Packaged verification output must be within Windows Temp')
        runtime = root/'Thanh_Dat_Phat.exe'
        shutil.copy2(args.exe, runtime)
        import psutil
        for attempt in (1, 2):
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
            env['TDP_PORT'] = str(port)
            def get(path):
                with urlopen(f'http://127.0.0.1:{port}'+path, timeout=60) as response:
                    return response.read()
            with (root/f'run-{attempt}.log').open('wb') as log:
                process = subprocess.Popen([str(runtime), '--no-browser', '--smoke-test-instance'],
                                           cwd=root, env=env, stdout=log, stderr=log,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    deadline = time.monotonic() + 150
                    while True:
                        if process.poll() is not None:
                            raise RuntimeError('Candidate exited; inspect private runtime log')
                        try:
                            if json.loads(get('/health')).get('ok'): break
                        except OSError:
                            pass
                        if time.monotonic() > deadline: raise TimeoutError('Candidate startup timed out')
                        time.sleep(.3)
                    check_exports(get, before, root)
                    snapshots.append(state(db_path, before['protected_columns']))
                finally:
                    parent = psutil.Process(process.pid) if process.poll() is None else None
                    children = parent.children(recursive=True) if parent else []
                    for child in reversed(children):
                        try: child.terminate()
                        except psutil.Error: pass
                    if parent:
                        try: parent.terminate()
                        except psutil.Error: pass
                    process.wait(timeout=15)
                    psutil.wait_procs(children, timeout=10)
    else:
        os.environ.update(env)
        try:
            import server
        except ImportError:
            from . import server
        client = server.app.test_client()
        def get(path):
            response = client.get(path)
            assert response.status_code == 200, response.get_data(as_text=True)[:500]
            return response.data
        for _ in range(2):
            server.init_database()
            check_exports(get, before, root)
            snapshots.append(state(db_path, before['protected_columns']))
    for after in snapshots:
        assert after['ids'] == before['expected_ids']
        assert abs(after['invoice_amount'] - before['expected_amount']) < .01
        assert after['source_fingerprint'] == before['source_fingerprint']
        assert after['protected'] == before['protected']
    assert snapshots[0] == snapshots[1], 'Second startup changed the repaired data'
    backups = list((db_path.parent/'migration_backups').glob('*.sqlite3'))
    assert any(state(p)['ids'] == before['ids'] for p in backups), 'No pre-repair backup'
    snapshot_database(source, root/'verified_seed.sqlite3')
    seed = state(root/'verified_seed.sqlite3', before['protected_columns'])
    assert seed['ids'] == before['expected_ids'] and seed['protected'] == before['protected']
    assert state(source) == before, 'Operational source changed during test'
    result = {'ok': True, 'source_database': str(source), 'candidate_exe': str(args.exe) if args.exe else None,
              'before': before, 'after': snapshots[-1], 'seed': seed,
              'checks': ['real_source_timestamp_ids', 'screen_and_excel_counts_and_money',
                         'pre_upgrade_backup', 'two_startups_idempotent', 'protected_tables_unchanged',
                         'source_payloads_and_money_unchanged', 'release_seed_corrected', 'source_db_unchanged'],
              'connector_calls': False, 'output': str(root)}
    (root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok':True,'before':before['invoice_count'],'after':snapshots[-1]['invoice_count'],
                      'result':str(root/'result.json')},ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
