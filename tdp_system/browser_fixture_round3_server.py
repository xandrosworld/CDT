"""Isolated synthetic fixture; never points at the customer's database."""
import tempfile
from pathlib import Path
from waitress import serve
from . import server
from .test_round3_documents import seed_round3


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='browser-round3-') as folder:
        server.DATA_DIR = Path(folder)
        server.DB_PATH = Path(folder) / 'fixture.sqlite3'
        golden = Path(__file__).resolve().parent.parent / 'Em Thành.xlsx'
        server.MASTER_SOURCE = Path(folder) / 'no-auto-import.xlsx'
        server.init_database()
        server.MASTER_SOURCE = golden
        with server.db() as conn:
            seed_round3(conn, 70)
        print('Round 3 synthetic fixture on 18805', flush=True)
        serve(server.app, host='127.0.0.1', port=18805, threads=4)
