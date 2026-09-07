"""Offline data for the compact workspace and output code-only editor."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='tdp_compact_workspace_') as root:
    os.environ.update(TDP_DATA_DIR=root, TDP_DB_PATH=str(Path(root)/'test.sqlite3'), TDP_EXPORT_DIR=str(Path(root)/'exports'))
    from tdp_system import server
    from tdp_system.test_invoice_workbench_listing import seed_round1, prepare
    from tdp_system.test_invoice_output_sync import output_invoice, OutputFixtureMsmi
    from tdp_system.invoice_output_sync import sync_output_batch
    from tdp_system.invoice_mapping import save_mapping, save_conversion
    from tdp_system.invoice_inventory import post_output_invoice
    from tdp_system.test_invoice_input_sync import now_iso
    from flask import request
    from waitress import serve
    server.init_database(sync_master=False)
    with server.db() as conn:
        ids=seed_round1(conn,extra_lines=30)
        conn.execute("INSERT INTO contractors(code,name,price_group,pricing_mode) VALUES('QA','Nhà thầu kiểm thử','QA','group')")
        conn.execute("INSERT INTO kitchens(code,contractor,name) VALUES('QA-K','QA','Bếp kiểm thử')")
        conn.execute("INSERT INTO suppliers(code,name) VALUES('QA-S','Nhà cung cấp kiểm thử')")
        order_batch=conn.execute("INSERT INTO batches(work_date,source_name,created_at) VALUES('2026-08-31','Dữ liệu kiểm thử',?)",(now_iso(),)).lastrowid
        conn.executemany("""INSERT INTO orders(batch_id,work_date,contractor,kitchen,product_code,product_name,qty,actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,updated_at)
          VALUES(?,'2026-08-31','QA','QA-K','R1-KG',?,1,1,1,'kg','QA-S',10000,12000,'0.08',?)""",[(order_batch,'Hàng kiểm thử '+str(i),now_iso()) for i in range(30)])
        outputs=[]
        for i in range(10,45):
            item=output_invoice(i)
            item['tdlap']='2026-08-30T17:00:00Z'
            outputs.append(item)
        batch=prepare(conn,'output')
        sync_output_batch(conn,OutputFixtureMsmi(outputs),batch['id'],now_iso)
        for number,key in [('10','unsafe'),('11','posted'),('12','converted')]:
            row=conn.execute('SELECT li.id,li.invoice_id FROM outgoing_source_invoice_items li JOIN outgoing_source_invoices i ON i.id=li.invoice_id WHERE i.invoice_number=?',(number,)).fetchone()
            ids[key]=dict(row)
        conn.execute("UPDATE outgoing_source_invoices SET sync_status='review_required',stock_status='blocked',error_message='Tổng nguồn lệch' WHERE id=?",(ids['unsafe']['invoice_id'],))
        save_mapping(conn,direction='output',item_id=ids['posted']['id'],product_code='R1-KG',now_iso=now_iso)
        post_output_invoice(conn,ids['posted']['invoice_id'],confirmed=True,now_iso=now_iso)
        save_mapping(conn,direction='output',item_id=ids['converted']['id'],product_code='R1-CAI',now_iso=now_iso)
        save_conversion(conn,direction='output',item_id=ids['converted']['id'],conversion_factor=2.5,now_iso=now_iso)
    @server.app.get('/fixture/ids')
    def fixture_ids(): return ids
    @server.app.get('/fixture/snapshot')
    def snapshot():
        with server.db() as conn:
            rows={}
            for t in ['outgoing_source_invoices','invoice_inventory_ledger','inventory_transactions']:
                # Stock status legitimately changes after saving a mapping.
                fields='id,invoice_number,subtotal,tax_amount,total_amount,raw_json' if t=='outgoing_source_invoices' else '*'
                rows[t]=[tuple(r) for r in conn.execute(f'SELECT {fields} FROM {t} ORDER BY id')]
            rows['source_lines']=[tuple(r) for r in conn.execute('SELECT id,invoice_id,source_item_code,source_item_name,source_unit,qty,unit_price,amount FROM outgoing_source_invoice_items ORDER BY id')]
        return {'digest':hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
    @server.app.before_request
    def block_connectors():
        if '/sync' in request.path or '/minvoice/' in request.path:
            return {'ok':False,'error':'Connectors disabled in fixture'},403
    print('COMPACT_WORKSPACE_FIXTURE_READY',flush=True)
    serve(server.app,host='127.0.0.1',port=18809,threads=4)
