"""Synthetic stock posting, carry-forward and catalog regression server."""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='tdp_stock_workflows_') as root:
    os.environ.update(TDP_DATA_DIR=root, TDP_DB_PATH=str(Path(root)/'test.sqlite3'), TDP_EXPORT_DIR=str(Path(root)/'exports'))
    from tdp_system import server
    from tdp_system.test_invoice_workbench_listing import seed_round1, prepare
    from tdp_system.test_invoice_output_sync import output_invoice, OutputFixtureMsmi
    from tdp_system.invoice_output_sync import sync_output_batch
    from tdp_system.invoice_mapping import save_mapping
    from tdp_system.test_invoice_input_sync import now_iso
    from flask import request
    from waitress import serve
    server.init_database(sync_master=False)
    with server.db() as conn:
        ids=seed_round1(conn)
        conn.execute("""INSERT INTO inventory_transactions(txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,status,note,created_at,updated_at)
            VALUES('2026-08-01','R1-KG',9,0,100,'OPENING','2026-08','R1-KG','posted','fixture',?,?)""",(now_iso(),now_iso()))
        conn.executemany("INSERT INTO products(code,name,unit) VALUES(?,?,'Cái')", [(f'A{i:04}',f'Hàng kiểm thử {i}') for i in range(1253)])
        batch=prepare(conn,'output')
        for i in (90,91):
            remote=output_invoice(i)
            remote['tdlap']='2026-08-30T17:00:00Z'
            remote['hdhhdvu'][0].update(sluong=7,dgia=100,thtien=700)
            remote.update(tgtcthue=700,tgtttbso=700,tgtthue=0)
            sync_output_batch(conn,OutputFixtureMsmi([remote]),batch['id'],now_iso)
            item=conn.execute('SELECT li.id,li.invoice_id FROM outgoing_source_invoice_items li JOIN outgoing_source_invoices i ON i.id=li.invoice_id WHERE i.invoice_number=?',(str(i),)).fetchone()
            save_mapping(conn,direction='output',item_id=item['id'],product_code='R1-KG',now_iso=now_iso)
        conn.execute("INSERT INTO contractors(code,name,price_group,pricing_mode) VALUES('QA','Khách kiểm thử','QA','group')")
        conn.execute("INSERT INTO kitchens(code,contractor,name) VALUES('QA-K','QA','Bếp kiểm thử')")
        conn.execute("INSERT INTO suppliers(code,name) VALUES('QA-S','Nhà cung cấp kiểm thử')")
        order_batch=conn.execute("INSERT INTO batches(work_date,source_name,created_at) VALUES('2026-08-31','Đơn kiểm thử',?)",(now_iso(),)).lastrowid
        conn.execute("""INSERT INTO orders(batch_id,work_date,contractor,kitchen,product_code,product_name,qty,actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,updated_at)
          VALUES(?,'2026-08-31','QA','QA-K','R1-KG','Hàng kiểm thử',1,1,1,'kg','QA-S',100,200,'0.08',?)""",(order_batch,now_iso()))
    @server.app.get('/fixture/digest')
    def digest():
        with server.db() as conn:
            return {'sha256':hashlib.sha256('\n'.join(conn.iterdump()).encode()).hexdigest()}
    @server.app.before_request
    def block_connectors():
        if '/sync' in request.path or '/minvoice/' in request.path:
            return {'ok':False,'error':'Connectors disabled in fixture'},403
    print('STOCK_WORKFLOWS_FIXTURE_READY',flush=True)
    serve(server.app,host='127.0.0.1',port=18920,threads=4)
