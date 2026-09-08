"""Portable, synthetic fixture for browser_smoke_date_picker.cjs; no remote access."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory(prefix='tdp_date_picker_') as root:
    data = Path(root)
    os.environ.update(TDP_DATA_DIR=str(data), TDP_DB_PATH=str(data / 'test.sqlite3'), TDP_EXPORT_DIR=str(data / 'exports'))
    from tdp_system import server
    from tdp_system.test_invoice_workbench_listing import seed_round1
    from waitress import serve
    server.init_database(sync_master=False)
    with server.db() as conn:
        ids = seed_round1(conn)
        if os.environ.get('TDP_FIXTURE_OUTPUT_NAMES') == '1':
            from tdp_system.invoice_mapping import save_mapping
            from tdp_system.test_invoice_input_sync import now_iso
            conn.execute("UPDATE outgoing_source_invoice_items SET source_item_code='',source_item_name='Hàng kiểm thử kg',source_unit='Kg' WHERE id=?",(ids['output_line'],))
            original=dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(ids['output_line'],)).fetchone())
            ids['output_name_lines']={'blank':original['id']}
            conn.executemany('INSERT INTO products(code,name,unit) VALUES(?,?,?)',[
                ('AMB-1','Tên trùng','Kg'),('AMB-2','Tên trùng','Kg'),('ALIAS','Tên trong danh mục','Kg')])
            conn.execute("INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES('ALIAS','Tên trên hóa đơn',?)",(now_iso(),))
            for key,code,name in [('coded','R1-KG','Hàng kiểm thử kg'),('ambiguous','','Tên trùng'),('alias','','Tên trên hóa đơn')]:
                row={k:v for k,v in original.items() if k!='id'}
                row.update(line_index=len(ids['output_name_lines'])+1,source_item_code=code,source_item_name=name)
                cur=conn.execute('INSERT INTO outgoing_source_invoice_items('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
                ids['output_name_lines'][key]=cur.lastrowid
                if key=='coded':save_mapping(conn,direction='output',item_id=cur.lastrowid,product_code='R1-KG',now_iso=now_iso)
            conn.execute('UPDATE outgoing_source_invoices SET subtotal=subtotal*4,tax_amount=tax_amount*4,total_amount=total_amount*4 WHERE id=?',(ids['output_id'],))
        if os.environ.get('TDP_FIXTURE_OLD_PENDING') == '1':
            conn.execute("UPDATE msmi_invoices SET invoice_date='2022-07-31' WHERE id=?",(ids['input_ids']['3'],))
    @server.app.get('/fixture/ids')
    def fixture_ids():
        return ids
    @server.app.before_request
    def block_connectors():
        from flask import request
        if '/sync' in request.path or '/minvoice/' in request.path:
            return {'ok': False, 'error': 'Connectors disabled in local fixture'}, 403
    print('DATE_PICKER_FIXTURE_READY', flush=True)
    serve(server.app, host='127.0.0.1', port=18805, threads=4)
