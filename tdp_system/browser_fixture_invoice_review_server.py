"""Isolated invoice editor fixture. All data is synthetic; connectors are blocked."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='tdp_invoice_review_') as root:
    data = Path(root)
    os.environ.update(TDP_DATA_DIR=str(data), TDP_DB_PATH=str(data / 'test.sqlite3'), TDP_EXPORT_DIR=str(data / 'exports'))
    from tdp_system import server
    from tdp_system.test_invoice_workbench_listing import seed_round1
    from tdp_system.test_invoice_receipt_summary import seed_promotion
    from waitress import serve
    from flask import request

    server.init_database(sync_master=False)
    with server.db() as conn:
        ids = seed_round1(conn)
        ids.update(seed_promotion(conn))
        conn.execute("UPDATE msmi_invoices SET sync_status='review_required', error_message='Nguồn cần đối chiếu tổng tiền' WHERE id=?", (ids['input_ids']['3'],))

    @server.app.get('/fixture/ids')
    def fixture_ids():
        return ids

    @server.app.get('/fixture/snapshot')
    def fixture_snapshot():
        with server.db() as conn:
            source = [tuple(r) for r in conn.execute('SELECT id,invoice_id,line_index,source_item_code,source_item_name,source_unit,qty,unit_price,amount FROM msmi_invoice_items ORDER BY id')]
            headers = [tuple(r) for r in conn.execute('SELECT id,invoice_number,invoice_series,invoice_date,total_amount,raw_json FROM msmi_invoices ORDER BY id')]
            ledger = [tuple(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger ORDER BY id')]
            stock = [tuple(r) for r in conn.execute('SELECT * FROM inventory_transactions ORDER BY id')]
        digest = lambda rows: hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        return {name: digest(rows) for name, rows in [('source',source),('headers',headers),('ledger',ledger),('stock',stock)]}

    @server.app.before_request
    def block_connectors():
        if '/sync' in request.path or '/minvoice/' in request.path:
            return {'ok': False, 'error': 'Connectors disabled in local fixture'}, 403

    print('INVOICE_REVIEW_FIXTURE_READY', flush=True)
    serve(server.app, host='127.0.0.1', port=18806, threads=4)
