"""Download an authenticated consistent snapshot; keep credentials and DB outside Git."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    base = 'https://tdp.up.railway.app'
    credentials = json.loads(args.credentials.read_text(encoding='utf-8'))
    session = requests.Session()
    page = session.get(base + '/login', timeout=30); page.raise_for_status()
    token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    response = session.post(base + '/login', data=dict(username=credentials['username'],
        password=credentials['password'], csrf=token), headers={'Origin': base}, timeout=40)
    response.raise_for_status()
    response = session.get(base + '/api/backup', timeout=180); response.raise_for_status()
    assert response.content.startswith(b'SQLite format 3'), 'Snapshot unavailable'
    database = args.output / 'snapshot.sqlite3'; database.write_bytes(response.content)
    tables = ('orders', 'batches', 'products', 'msmi_invoices', 'msmi_invoice_lines',
              'outgoing_source_invoices', 'invoice_inventory_ledger', 'invoice_line_mappings',
              'payable_payments', 'receivable_payments', 'purchase_workbook_lines')
    conn = sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)
    report = {'integrity': conn.execute('PRAGMA integrity_check').fetchone()[0], 'tables': {}}
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in tables:
        if table not in existing: continue
        rows = sorted(conn.execute('SELECT * FROM "'+table+'"').fetchall(), key=repr)
        report['tables'][table] = {'rows': len(rows), 'hash': hashlib.sha256(repr(rows).encode()).hexdigest()}
    conn.close()
    if args.compare:
        before = json.loads(args.compare.read_text(encoding='utf-8'))
        report['unchanged'] = before['tables'] == report['tables']
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'integrity': report['integrity'], 'tables': len(report['tables']), 'unchanged': report.get('unchanged')}))
    assert report['integrity']=='ok' and report.get('unchanged', True)


if __name__ == '__main__':
    main()
