"""Synthetic inventory reports with opening stock and posted input/output."""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='tdp_inventory_reports_') as root:
    os.environ.update(TDP_DATA_DIR=root, TDP_DB_PATH=str(Path(root)/'test.sqlite3'), TDP_EXPORT_DIR=str(Path(root)/'exports'))
    from tdp_system import server
    from tdp_system.test_invoice_workbench_listing import seed_round1
    from tdp_system.invoice_mapping import save_mapping
    from tdp_system.invoice_inventory import post_output_invoice
    from tdp_system.test_invoice_input_sync import now_iso
    from tdp_system.test_invoice_receipt_summary import seed_promotion
    from tdp_system.invoice_line_groups import preview_group, create_group
    from tdp_system.invoice_receipt import create_input_receipt
    from flask import request
    from waitress import serve
    server.init_database(sync_master=False)
    with server.db() as conn:
        ids=seed_round1(conn)
        for code,qty in [('R1-KG',10),('R1-CAI',0.855)]:
            conn.execute("""INSERT INTO inventory_transactions(txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,status,note,created_at,updated_at)
                VALUES('2026-08-01',?,?,0,100,'OPENING','2026-08',?,'posted','fixture',?,?)""",(code,qty,code,now_iso(),now_iso()))
        save_mapping(conn,direction='output',item_id=ids['output_line'],product_code='R1-KG',now_iso=now_iso)
        post_output_invoice(conn,ids['output_id'],confirmed=True,now_iso=now_iso)
        promotion=seed_promotion(conn)
        for kind in ('OIL','CHILI'):
            members=[promotion['promotion_lines'][f'QA-{kind}-{suffix}'] for suffix in ('PAID','FREE')]
            preview=preview_group(conn,'TDP',members)
            create_group(conn,'TDP',members,preview['token'],now_iso())
        create_input_receipt(conn,promotion['promotion_invoice'],now_iso)
    @server.app.get('/fixture/digest')
    def digest():
        with server.db() as conn:
            return {'sha256':hashlib.sha256('\n'.join(conn.iterdump()).encode()).hexdigest()}
    @server.app.before_request
    def block_connectors():
        if '/sync' in request.path or '/minvoice/' in request.path:
            return {'ok':False,'error':'Connectors disabled in fixture'},403
    print('INVENTORY_REPORTS_FIXTURE_READY',flush=True)
    serve(server.app,host='127.0.0.1',port=18807,threads=4)
