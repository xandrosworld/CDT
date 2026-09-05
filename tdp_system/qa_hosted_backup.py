"""Download an authenticated, consistent pre-deploy backup without exposing secrets."""
import argparse
from contextlib import closing
import http.cookiejar
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base')
    parser.add_argument('credentials', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    credentials = json.loads(args.credentials.read_text(encoding='utf-8'))
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with opener.open(args.base + '/login', timeout=30) as response:
        csrf = re.search(r'name="csrf" value="([^"]+)"', response.read().decode()).group(1)
    payload = urlencode(dict(username=credentials['username'], password=credentials['password'], csrf=csrf)).encode()
    with opener.open(Request(args.base + '/login', data=payload, headers={'Origin': args.base}), timeout=60) as response:
        assert response.url.rstrip('/') == args.base.rstrip('/'), 'Login did not reach application'
    with opener.open(args.base + '/api/backup', timeout=120) as response:
        payload = response.read()
    assert payload.startswith(b'SQLite format 3'), 'Not a database backup'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as handle: handle.write(payload)
    with closing(sqlite3.connect(args.output.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        assert conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        tables = ['orders', 'msmi_invoices', 'outgoing_source_invoices', 'invoice_inventory_ledger', 'payments', 'products']
        counts = {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in tables}
    print(json.dumps({'ok': True, 'bytes': len(payload), 'counts': counts, 'output': str(args.output)}))


if __name__ == '__main__': main()
