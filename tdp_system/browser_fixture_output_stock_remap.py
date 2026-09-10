"""Disposable fixture for Excel remapping, negative KKKNT and month closing."""
import os
import tempfile
from pathlib import Path


def main():
    from waitress import serve
    with tempfile.TemporaryDirectory(prefix='tdp_remap_browser_') as folder:
        os.environ['TDP_DATA_DIR'] = str(Path(folder)/'data')
        os.environ['TDP_DB_PATH'] = str(Path(folder)/'fixture.sqlite3')
        os.environ['TDP_EXPORT_DIR'] = str(Path(folder)/'exports')
        from . import server
        from .test_output_stock_remap import OutputStockRemapTests
        from .test_outgoing_readiness import OutgoingReadinessTests as Seed
        server.init_database(); server.app.config['TESTING'] = True
        fixture=OutputStockRemapTests(); fixture.setUp()
        with server.db() as conn:
            conn.execute("UPDATE products SET unit='Bịch' WHERE code='REMAP-B'")
            batch,_=Seed.add_batch(conn,'2026-08-20',[{'product_code':'REMAP-C','qty':100}])
            conn.execute("UPDATE orders SET tax='KKKNT' WHERE batch_id=?",(batch,))
        print('SYNTHETIC_REMAP_READY',flush=True)
        serve(server.app,host='127.0.0.1',port=18802,threads=4)


if __name__=='__main__': main()
