"""Synthetic documents only; separate database and output paths."""
import tempfile
from pathlib import Path
from waitress import serve
from . import server
from .test_round3_documents import seed_round3

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='browser-round4-') as folder:
        server.DATA_DIR=Path(folder); server.DB_PATH=Path(folder)/'fixture.sqlite3'
        server.MASTER_SOURCE=Path(folder)/'no-auto-import.xlsx'
        server.init_database()
        server.MASTER_SOURCE=Path(__file__).resolve().parent.parent/'Em Thành.xlsx'
        with server.db() as conn:
            batch=seed_round3(conn,30)
            conn.execute("UPDATE orders SET kitchen='K2' WHERE id%3=0")
            conn.execute("UPDATE orders SET product_name='Chả cá loại ngon (90-100 miếng/kg)' WHERE id%3=1")
        print('Round 4 synthetic fixture on 18807',flush=True)
        serve(server.app,host='127.0.0.1',port=18807,threads=4)
