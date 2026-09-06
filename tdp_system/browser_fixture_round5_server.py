"""Synthetic fixture for menu, recurring backup and seller-exclusion acceptance."""
import tempfile
from pathlib import Path
from waitress import serve
from . import server
from .automatic_backup import automatic_backup, start_backup_worker
from .test_round3_documents import seed_round3
from .seller_identity_catalog import CATALOG_FILENAME, sync_catalog

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='browser-round5-') as folder:
        server.DATA_DIR = Path(folder)
        server.DB_PATH = Path(folder) / 'fixture.sqlite3'
        server.MASTER_SOURCE = Path(folder) / 'no-auto-import.xlsx'
        server.init_database()
        server.MASTER_SOURCE = Path(__file__).resolve().parent.parent / 'Em Thành.xlsx'
        with server.db() as conn:
            sync_catalog(conn, Path(__file__).resolve().parent / 'templates' / CATALOG_FILENAME)
            seed_round3(conn, 30)
            conn.execute("UPDATE orders SET kitchen='K2' WHERE id%3=0")
            conn.execute("INSERT OR REPLACE INTO people(name,cccd,issue_date,issue_place,address) VALUES('Người hợp lệ kiểm thử','012345670000','01/01/2020','Nơi cấp kiểm thử','Thái Bình')")
            conn.execute("UPDATE orders SET purchase_list=1,seller='Người hợp lệ kiểm thử',cccd='012345670000'")
            conn.execute("UPDATE orders SET seller='Nguyễn Văn Toại' WHERE id%3=0")
            conn.execute("UPDATE orders SET seller='Đoàn Văn Giang',cccd=(SELECT cccd FROM people WHERE name='Đoàn Văn Giang') WHERE id%3=2")
            conn.execute("UPDATE orders SET product_name='Chả cá loại ngon (90-100 miếng/kg)' WHERE id%3=1")
        automatic_backup(server.DB_PATH, server.DATA_DIR, force=True)
        stop, worker = start_backup_worker(server.auto_backup)
        print('Round 5 synthetic fixture on 18808', flush=True)
        try:
            serve(server.app, host='127.0.0.1', port=18808, threads=4)
        finally:
            stop.set(); worker.join(2)
