"""Synthetic seven-blocker database; never opens the operational database."""
import os
import tempfile
from pathlib import Path


def main():
    from waitress import serve
    with tempfile.TemporaryDirectory(prefix='tdp_documents_resolution_') as temp:
        os.environ['TDP_DATA_DIR'] = str(Path(temp) / 'data')
        os.environ['TDP_DB_PATH'] = str(Path(temp) / 'fixture.sqlite3')
        os.environ['TDP_EXPORT_DIR'] = str(Path(temp) / 'exports')
        from . import server
        from .test_outgoing_readiness import OutgoingReadinessTests as Seed
        server.init_database()
        server.app.config['TESTING'] = True
        with server.db() as conn:
            conn.execute("INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) VALUES('NT-A','Khách kiểm thử','NT-A','group')")
            rows=[]
            for i in range(1,8):
                code=f'TEST-{i}'
                unit='kg' if i<5 else 'chai'
                conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax,buy_price) VALUES(?,?,?,'0%',10)", (code,f'Hàng kiểm thử {i}',unit))
                Seed.add_opening(conn,-1,product_code=code)
                rows.append({'product_code':code,'qty':2})
            conn.execute("UPDATE inventory_transactions SET source_id='2026-08',note='Nguồn kiểm thử đã đối chiếu'")
            batch_id,_=Seed.add_batch(conn,'2026-09-04',rows)
            conn.execute("UPDATE orders SET unit='chai' WHERE product_code IN ('TEST-5','TEST-6','TEST-7')")
            conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?",(batch_id,))
            # TEST-1 also has a movement: editing its opening must remain usable.
            source_id=Seed.add_posted_source(conn,source='minvoice',number='FIXTURE-1',product_code='TEST-1',qty=1)
            tenant=conn.execute("SELECT value FROM settings WHERE key='tenant_code'").fetchone()
            conn.execute('UPDATE outgoing_source_invoices SET tenant=? WHERE id=?',((tenant[0] if tenant else 'TDP'),source_id))
            line_id=conn.execute("""INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,
                source_item_name,source_unit,qty,unit_price,amount,tax_rate,product_code,mapping_status,stock_qty)
                VALUES(?,1,'TEST-1','Hàng kiểm thử 1','kg',1,20,20,'0%','TEST-1','mapped',1)""",(source_id,)).lastrowid
            conn.execute("UPDATE invoice_inventory_ledger SET source_line_id=? WHERE source_invoice_id=?",(line_id,source_id))
            conn.execute("UPDATE inventory_transactions SET qty_in=0 WHERE product_code='TEST-1' AND source_type='OPENING'")
        print('SYNTHETIC_DOCUMENTS_READY',flush=True)
        serve(server.app,host='127.0.0.1',port=18801,threads=4)


if __name__=='__main__':
    main()
