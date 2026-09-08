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
                ('AMB-1','Tên trùng','Kg'),('AMB-2','Tên trùng','Kg'),('ALIAS','Tên trong danh mục','Kg'),('G000007','Bánh đa đỏ ướt (sợi nhỏ)','Kg')])
            conn.execute("INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES('ALIAS','Tên trên hóa đơn',?)",(now_iso(),))
            for key,code,name in [('coded','R1-KG','Hàng kiểm thử kg'),('ambiguous','','Tên trùng'),('alias','','Tên trên hóa đơn'),('collision','R1-KG','Bánh đa đỏ ướt (sợi nhỏ)')]:
                row={k:v for k,v in original.items() if k!='id'}
                row.update(line_index=len(ids['output_name_lines'])+1,source_item_code=code,source_item_name=name)
                cur=conn.execute('INSERT INTO outgoing_source_invoice_items('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
                ids['output_name_lines'][key]=cur.lastrowid
                if key in {'coded','collision'}:save_mapping(conn,direction='output',item_id=cur.lastrowid,product_code='R1-KG',now_iso=now_iso)
            conn.execute('UPDATE outgoing_source_invoices SET subtotal=subtotal*5,tax_amount=tax_amount*5,total_amount=total_amount*5 WHERE id=?',(ids['output_id'],))
            # A blocked source must explain why a known code cannot be edited.
            parent=dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(ids['output_id'],)).fetchone())
            parent.pop('id')
            parent.update(identity_key='FIXTURE-BLOCKED-717',remote_id='FIXTURE-BLOCKED-717',invoice_number='717',sync_status='review_required',
                          stock_status='blocked',error_message='Tổng dòng 1.938.000 đ lệch tổng hóa đơn 2.058.000 đ')
            blocked=conn.execute('INSERT INTO outgoing_source_invoices('+','.join(parent)+') VALUES('+','.join('?' for _ in parent)+')',tuple(parent.values())).lastrowid
            row={k:v for k,v in original.items() if k!='id'}
            row.update(invoice_id=blocked,source_item_code='R1-KG',source_item_name='Hàng kiểm thử kg',line_index=1)
            ids['output_name_lines']['blocked']=conn.execute('INSERT INTO outgoing_source_invoice_items('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values())).lastrowid
            conn.execute("INSERT INTO products(code,name,unit) VALUES('M000246','Thạch rau câu Long Hải (100 cốc/ thùng)','Cốc')")
            row={k:v for k,v in original.items() if k!='id'}
            row.update(line_index=6,source_item_code='',source_item_name='Nước rau câu các vị (95gr/cốc x 100 cốc/thùng)',
                       source_unit='cái',qty=5500,unit_price=1300,amount=7150000)
            unit_line=conn.execute('INSERT INTO outgoing_source_invoice_items('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values())).lastrowid
            save_mapping(conn,direction='output',item_id=unit_line,product_code='M000246',now_iso=now_iso)
            ids['output_name_lines']['unit_review']=unit_line
            from tdp_system.test_minvoice_portal import document
            from tdp_system.minvoice_portal import normalize_portal_document
            from tdp_system.invoice_output_sync import upsert_output_invoice
            financial=document()
            financial.update(invoiceNumber=716,totalAmountWithoutVAT=120000,totalAmount=128000)
            financial['invoiceDetail'][0].update(productCode='R1-KG',productName='Hàng kiểm thử kg',
                                                quantity=1,amount=50000,amountWithoutVAT=50000,vatAmount=4000)
            conn.execute("INSERT INTO products(code,name,unit) VALUES('AUTO-REVIEW','Hàng tự khớp khi đối chiếu tiền','Kg')")
            financial['invoiceDetail'].append(dict(financial['invoiceDetail'][0],productCode='AUTO-REVIEW',
                                                  productName='Hàng tự khớp khi đối chiếu tiền'))
            financial_id=upsert_output_invoice(conn,normalize_portal_document(financial),tenant='TDP',now=now_iso(),status_map={},status_fields=(),reference_fields=())[0]
            ids['output_name_lines']['amount_review']=conn.execute('SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=?',(financial_id,)).fetchone()[0]
            ids['output_name_lines']['auto_amount_review']=conn.execute('SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=? AND source_item_code=?',
                                                                       (financial_id,'AUTO-REVIEW')).fetchone()[0]
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
