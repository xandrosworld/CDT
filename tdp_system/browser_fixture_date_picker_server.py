"""Portable, synthetic fixture for browser_smoke_date_picker.cjs; no remote access."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='tdp_date_picker_') as root:
    data = Path(root)
    os.environ.update(TDP_DATA_DIR=str(data), TDP_DB_PATH=str(data / 'test.sqlite3'), TDP_EXPORT_DIR=str(data / 'exports'))
    from tdp_system import server
    from tdp_system.test_invoice_workbench_listing import seed_round1
    from waitress import serve
    server.init_database(sync_master=False)
    with server.db() as conn:
        ids = seed_round1(conn)
        if os.environ.get('TDP_FIXTURE_OLD_PENDING') == '1':
            conn.execute("UPDATE msmi_invoices SET invoice_date='2022-07-31' WHERE id=?",(ids['input_ids']['3'],))
    @server.app.get('/fixture/ids')
    def fixture_ids():
        return ids
    @server.app.before_request
    def block_connectors():
        from flask import request
        if '/sync' in request.path or '/minvoice/' in request.path:
            return {'ok': False, 'error': 'Connectors disabled in local fixture'}, 403
    print('DATE_PICKER_FIXTURE_READY', flush=True)
    serve(server.app, host='127.0.0.1', port=18805, threads=4)
