import os
import tempfile
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory(prefix='tdp_customer_payment_') as folder:
        os.environ['TDP_DATA_DIR']=str(Path(folder)/'data')
        os.environ['TDP_DB_PATH']=str(Path(folder)/'fixture.sqlite3')
        os.environ['TDP_EXPORT_DIR']=str(Path(folder)/'exports')
        from . import server
        from .test_invoice_payment_scope import InvoicePaymentScopeTests
        from waitress import serve
        server.init_database();server.app.config['TESTING']=True
        fixture=InvoicePaymentScopeTests();fixture.setUp()
        with server.db() as conn:
            fixture.add_direct_source(conn,invoice_number='853')
            fixture.add_direct_source(conn,invoice_number='854')
            draft,_,_=fixture.add_invoice(conn,invoice_number='813')
            line=conn.execute('SELECT id FROM outgoing_invoice_lines WHERE draft_id=?',(draft,)).fetchone()[0]
            for n in range(25):
                _,_,order=fixture.add_invoice(conn,status='draft',invoice_number=f'DRAFT-{n}')
                conn.execute('INSERT INTO outgoing_line_allocations(line_id,order_id,qty,amount,source_unit_price) VALUES(?,?,.08,8,100)',(line,order))
        serve(server.app,host='127.0.0.1',port=18804,threads=4)


if __name__=='__main__':main()
