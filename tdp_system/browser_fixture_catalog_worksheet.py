"""1255 synthetic products, loopback only, no live connectors."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='tdp_catalog_worksheet_') as root:
    data = Path(root)
    os.environ.update(TDP_DATA_DIR=str(data), TDP_DB_PATH=str(data/'test.sqlite3'), TDP_EXPORT_DIR=str(data/'exports'), TDP_OFFLINE_TEST='1')
    from tdp_system import server
    from tdp_system.test_invoice_workbench_listing import seed_round1
    from waitress import serve
    server.connector_config_paths = lambda: []
    server.init_database(sync_master=False)
    with server.db() as conn:
        seed_round1(conn)
        conn.execute("UPDATE products SET tax='0.08'")
        count = conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        conn.executemany("INSERT INTO products(code,name,unit,tax) VALUES(?,?,'Kg','0.08')",
                         [(f'Z{i:04}', f'Hàng thử {i}') for i in range(1255-count)])
    @server.app.before_request
    def block_connectors():
        from flask import request
        if '/sync' in request.path or '/minvoice/' in request.path:
            return {'ok':False,'error':'Offline fixture'},403
    print('CATALOG_WORKSHEET_READY', flush=True)
    serve(server.app,host='127.0.0.1',port=18852,threads=4)
