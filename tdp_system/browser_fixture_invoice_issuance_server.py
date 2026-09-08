"""Isolated invoice-file and local issued-number workflow; no connector writes."""
import os


def main():
    from flask import request
    from waitress import serve
    from . import server
    from .test_outgoing_readiness import OutgoingReadinessTests
    server.init_database()
    server.app.config['TESTING'] = True
    # Match the browser's fixed Vietnam-midnight clock on every future run.
    today = '2026-09-09'
    with server.db() as conn:
        conn.execute("INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) VALUES('NT-A','Khách kiểm thử','NT-A','group')")
        conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax) VALUES('HH-01','Hàng kiểm thử','kg','0%')")
        stock_cause = os.environ.get('TDP_FIXTURE_STOCK_CAUSE') == '1'
        OutgoingReadinessTests.add_opening(conn, -1.5 if stock_cause else 20)
        rows = [{'qty':4},{'qty':6}]
        if stock_cause:
            conn.execute("UPDATE products SET name='Quả me tươi' WHERE code='HH-01'")
            conn.execute("UPDATE inventory_transactions SET note='Tồn kiểm thử.xlsx; sheet Tồn đầu; dòng 168'")
            conn.execute("INSERT INTO products(code,name,unit,tax) VALUES('HH-02','Rau <kiểm tra>','kg','0%')")
            OutgoingReadinessTests.add_opening(conn, -2, product_code='HH-02')
            conn.execute("UPDATE inventory_transactions SET source_id='2026-08' WHERE source_type='OPENING'")
            rows.append({'qty':1,'product_code':'HH-02'})
        batch_id, ids = OutgoingReadinessTests.add_batch(conn, today, rows)
        conn.execute("UPDATE orders SET tax='KKKNT' WHERE id=?", (ids[0],))
        conn.execute("UPDATE orders SET tax='8%' WHERE id=?", (ids[1],))
        for key,value in {'company':'Công ty thử','company_tax_code':'0100000001','company_address':'Địa chỉ thử',
                          'payment_requester':'Người thử','payment_bank_name':'Ngân hàng thử','payment_bank_account':'123456'}.items():
            conn.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(key,value))
    @server.app.before_request
    def block_connectors():
        if '/sync' in request.path or request.path.startswith('/api/minvoice/'):
            return {'ok':False,'error':'Offline fixture'},403
    @server.app.get('/fixture/state')
    def fixture_state():
        with server.db() as conn:
            return {'batch_id':batch_id,'orders':[dict(r) for r in conn.execute('SELECT * FROM orders WHERE batch_id=?',(batch_id,))],
                    'drafts':[dict(r) for r in conn.execute('SELECT * FROM outgoing_invoice_drafts WHERE batch_id=?',(batch_id,))],
                    'ledger_count':conn.execute('SELECT count(*) FROM invoice_inventory_ledger').fetchone()[0],
                    'opening':[dict(r) for r in conn.execute("SELECT product_code,qty_in,qty_out,unit_cost,note FROM inventory_transactions WHERE source_type='OPENING' ORDER BY id")],
                    'holds':[dict(r) for r in conn.execute("SELECT source_id,status,SUM(qty_out) qty FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' GROUP BY source_id,status")]}
    serve(server.app,host='127.0.0.1',port=18854,threads=4)


if __name__ == '__main__':
    main()
