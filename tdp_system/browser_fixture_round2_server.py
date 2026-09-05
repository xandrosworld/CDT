"""Disposable local fixture, no customer DB or remote invoice access."""
import os
import tempfile
from pathlib import Path


def main():
    from waitress import serve
    with tempfile.TemporaryDirectory(prefix='browser_', dir='D:/TDP_ROUND2') as root:
        os.environ['TDP_DATA_DIR'] = root
        os.environ['TDP_DB_PATH'] = str(Path(root) / 'fixture.sqlite3')
        os.environ['TDP_EXPORT_DIR'] = str(Path(root) / 'exports')
        from . import server
        from .test_physical_inventory import seed_round2
        server.MASTER_SOURCE = Path(root) / 'disabled.xlsx'
        server.init_database()
        with server.db() as conn:
            batch = seed_round2(conn)
            conn.execute("INSERT INTO suppliers(code,name) VALUES('S2','Nhà cung cấp 2')")
            conn.execute("INSERT INTO kitchens(code,name,contractor) VALUES('K2','Bếp thứ hai','C1')")
            lookup = server.product_lookup(conn)
            rows = []
            for i in range(65):
                row = server.resolve_order(conn, {
                    'kitchen':'K1' if i % 2 else 'K2','product_code':'P1' if i % 2 else 'P2',
                    'product_name':f'Hàng thử {i + 1}', 'supplier':'S1' if i < 40 else 'S2',
                    'qty':.855 if i == 0 else 1, 'actual_received':1,'actual_delivered':1,
                    'sell_price':1200,'buy_price':1000,'tax':'0',
                }, '2026-09-05', *lookup)
                row.update(errors=['Lỗi thử nghiệm cần sửa'] if i in (31,50) else [],
                           warnings=['Cảnh báo không chặn'] if i in (3,4) else [],
                           source_sheet='Dữ liệu thử',source_row=i + 2)
                rows.append(row)
            server.save_imported_orders(conn,batch,rows)
        @server.app.before_request
        def no_remote():
            from flask import request
            if '/sync' in request.path or '/minvoice/' in request.path:
                return {'ok':False,'error':'Remote connector disabled for fixture'},403
        print('ROUND2_READY',flush=True)
        serve(server.app,host='127.0.0.1',port=18803,threads=4)


if __name__ == '__main__':
    main()
