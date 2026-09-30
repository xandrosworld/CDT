"""Isolated stock correction fixture; never opens the real database."""
import os
import tempfile
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory(prefix='tdp_stock_web_') as folder:
        os.environ['TDP_DATA_DIR'] = str(Path(folder) / 'data')
        os.environ['TDP_DB_PATH'] = str(Path(folder) / 'fixture.sqlite3')
        os.environ['TDP_EXPORT_DIR'] = str(Path(folder) / 'exports')
        from . import server
        from .test_output_stock_remap import OutputStockRemapTests
        from waitress import serve
        server.init_database()
        server.app.config['TESTING'] = True
        OutputStockRemapTests().setUp()
        serve(server.app, host='127.0.0.1', port=18803, threads=4)


if __name__ == '__main__':
    main()
