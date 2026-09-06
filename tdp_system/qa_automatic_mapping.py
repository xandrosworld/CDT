"""Exercise automatic mapping through HTTP on a separate production snapshot."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from flask import Flask
from .contract_modules import register_contract_routes
from .invoice_workbench_listing import invoice_range_payload, range_workbook


def fingerprint(conn):
    excluded = {'audit_log', 'invoice_line_mappings', 'invoice_mapping_revisions'}
    changed_columns = {
        'msmi_invoices': {'receipt_status'},
        'msmi_invoice_items': {'product_code','mapping_status','conversion_factor','stock_qty','stock_unit_price'},
        'invoice_sync_batches': {'status','needs_mapping_count','ready_count','posted_count','error_count','updated_at'},
    }
    result = {}
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        if table in excluded:
            continue
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")') if r[1] not in changed_columns.get(table, set())]
        query = ','.join('"'+c+'"' for c in cols)
        rows = sorted((tuple(r) for r in conn.execute(f'SELECT {query} FROM "{table}"')), key=repr)
        result[table] = hashlib.sha256(repr(rows).encode()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    original_hash = hashlib.sha256(args.snapshot.read_bytes()).hexdigest()
    conn = sqlite3.connect(args.output / 'copy.sqlite3')
    source = sqlite3.connect(args.snapshot.resolve().as_uri()+'?mode=ro', uri=True)
    source.backup(conn)
    source.close()
    conn.row_factory = sqlite3.Row
    before = fingerprint(conn)
    @contextmanager
    def db():
        with conn:
            yield conn
    app = Flask(__name__)
    register_contract_routes(app, dict(db=db, now_iso=lambda: datetime.now(timezone.utc).isoformat(),
        clean_text=lambda v: str(v or '').strip(), number_value=lambda v: float(v or 0),
        tax_factor=lambda v: 1, setting_get=lambda c,k,d='': (c.execute('SELECT value FROM settings WHERE key=?',(k,)).fetchone() or [d])[0],
        setting_set=lambda *a: None, root=Path.cwd(), data_dir=args.output))
    client = app.test_client()
    with args.legacy.open('rb') as file:
        response = client.post('/api/msmi/auto-mappings', data={'from':'2026-08-01','to':'2026-08-31', 'file':(file,args.legacy.name)})
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    conn.commit()
    after = fingerprint(conn)
    assert before == after, [k for k in before if before[k] != after[k]]
    dump = list(conn.iterdump())
    with args.legacy.open('rb') as file:
        repeat = client.post('/api/msmi/auto-mappings', data={'from':'2026-08-01','to':'2026-08-31', 'file':(file,args.legacy.name)})
    assert repeat.status_code == 200 and repeat.get_json()['applied_rules'] == 0, repeat.get_json()
    assert dump == list(conn.iterdump()), 'Repeat changed data'
    listing = invoice_range_payload(conn, tenant='TDP', invoice_type='input', date_from='2026-08-01',date_to='2026-08-31')
    ranks = [r['action_rank'] for r in listing['lines']]
    assert ranks == sorted(ranks)
    (args.output/'listing.json').write_text(json.dumps(listing, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output/'invoices.xlsx').write_bytes(range_workbook(listing).getvalue())
    assert original_hash == hashlib.sha256(args.snapshot.read_bytes()).hexdigest()
    result.update(protected_tables=len(before), protected_data_unchanged=True, repeat_no_changes=True,
                  counts=listing['counts'], totals=listing['totals'], integrity=conn.execute('PRAGMA integrity_check').fetchone()[0])
    assert result['integrity'] == 'ok'
    (args.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    conn.close()


if __name__ == '__main__':
    main()
