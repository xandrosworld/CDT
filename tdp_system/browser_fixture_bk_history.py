import os
from tempfile import TemporaryDirectory
from pathlib import Path


def main():
    with TemporaryDirectory(prefix='tdp_bk_history_') as folder:
        os.environ['TDP_DATA_DIR']=str(Path(folder)/'data')
        os.environ['TDP_DB_PATH']=str(Path(folder)/'test.sqlite3')
        os.environ['TDP_EXPORT_DIR']=str(Path(folder)/'exports')
        from .test_bk_history import SavedHistoryTests
        from . import server
        from waitress import serve
        SavedHistoryTests.setUpClass()
        try:
            fixture=SavedHistoryTests();fixture.setUp()
            with server.db() as c:
                c.execute("INSERT INTO batches(work_date,source_name,status,created_at,approved_at) VALUES('2026-08-01','Fixture August.xlsx','approved','test','test')")
            serve(server.app,host='127.0.0.1',port=18807,threads=4)
        finally:SavedHistoryTests.tearDownClass()


if __name__=='__main__':main()
