import unittest
from unittest.mock import patch
from copy import deepcopy
from . import test_invoice_receipt as fixture
from .invoice_receipt_bulk import preview_receipts, post_receipts, InvoiceReceiptError
from .invoice_input_sync import sync_input_batch
from .invoice_mapping import save_mapping


class BulkReceiptTests(unittest.TestCase):
    def setUp(self):
        fixture.ConvertedInputReceiptTests.setUp(self)
        fixture.ConvertedInputReceiptTests.confirm_conversion(self)
        remote = deepcopy(self.remote)
        remote.update(_id='SECOND', shdon='9', tdlap='2026-08-09')
        remote['hdhhdvu'] = [dict(remote['hdhhdvu'][0], ma='SECOND', ten='Other goods', dvtinh='kg')]
        sync_input_batch(self.conn, fixture.DateBoundedMsmi([remote]), self.batch['id'], fixture.now_iso)
        self.second = self.conn.execute("SELECT id FROM msmi_invoices WHERE remote_id='SECOND'").fetchone()[0]
        self.conn.execute("INSERT INTO products(code,name,unit) VALUES('P-KG','Other goods','kg')")
        item = self.conn.execute('SELECT id FROM msmi_invoice_items WHERE invoice_id=?',(self.second,)).fetchone()[0]
        save_mapping(self.conn,direction='input',item_id=item,product_code='P-KG',now_iso=fixture.now_iso)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def preview(self):
        return preview_receipts(self.conn,[self.invoice_id,self.second],'TDP',fixture.now_iso)

    def count(self):
        return self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0]

    def test_review_read_only_units_and_group_idempotency(self):
        before='\n'.join(self.conn.iterdump())
        rows=self.preview()['items']
        self.assertEqual(before,'\n'.join(self.conn.iterdump()))
        self.assertEqual({'gói':90},rows[0]['qty_by_unit'])
        self.assertEqual({'kg':2},rows[1]['qty_by_unit'])
        self.assertEqual(10000,rows[0]['amount'])
        result=post_receipts(self.conn,rows,'TDP',fixture.now_iso)
        self.assertEqual(2,result['posted_count']); self.assertEqual(3,self.count())
        again=post_receipts(self.conn,rows,'TDP',fixture.now_iso)
        self.assertEqual(2,again['already_posted_count']);self.assertEqual(3,self.count())

    def test_subset_only_and_duplicate_rejected(self):
        rows=self.preview()['items']
        with self.assertRaises(InvoiceReceiptError):post_receipts(self.conn,[rows[0],rows[0]],'TDP',fixture.now_iso)
        self.assertEqual(0,self.count())
        post_receipts(self.conn,[rows[1]],'TDP',fixture.now_iso)
        self.assertEqual(1,self.count())
        self.assertEqual('ready',self.conn.execute('SELECT receipt_status FROM msmi_invoices WHERE id=?',(self.invoice_id,)).fetchone()[0])

    def test_stale_amount_cancels_entire_group(self):
        rows=self.preview()['items']
        self.conn.execute('UPDATE msmi_invoice_items SET amount=amount+1 WHERE invoice_id=?',(self.second,))
        with self.assertRaisesRegex(InvoiceReceiptError,'đã thay đổi'):post_receipts(self.conn,rows,'TDP',fixture.now_iso)
        self.assertEqual(0,self.count())

    def test_mid_group_failure_rolls_back_first_invoice(self):
        rows=self.preview()['items']
        from .invoice_receipt import create_input_receipt
        def post(conn, invoice_id, now):
            if invoice_id==self.second:raise InvoiceReceiptError('Simulated audit failure')
            return create_input_receipt(conn,invoice_id,now)
        with patch('tdp_system.invoice_receipt_bulk.create_input_receipt',side_effect=post):
            with self.assertRaises(InvoiceReceiptError):post_receipts(self.conn,rows,'TDP',fixture.now_iso)
        self.assertEqual(0,self.count())
        self.assertEqual(0,self.conn.execute('SELECT COUNT(*) FROM inventory_transactions').fetchone()[0])
        self.assertEqual('ready',self.conn.execute('SELECT receipt_status FROM msmi_invoices WHERE id=?',(self.invoice_id,)).fetchone()[0])

    def test_preview_excludes_unsafe_and_tenant_rejected(self):
        self.conn.execute("UPDATE msmi_invoices SET sync_status='review_required' WHERE id=?",(self.second,));self.conn.commit()
        result=self.preview()
        self.assertEqual([self.invoice_id],[r['id'] for r in result['items']])
        self.assertEqual(self.second,result['blocked'][0]['id']);self.assertEqual(0,self.count())
        with self.assertRaises(InvoiceReceiptError):post_receipts(self.conn,result['items'],'OTHER',fixture.now_iso)

    def test_double_confirmation_serializes_without_duplicates(self):
        import tempfile,sqlite3
        from pathlib import Path
        from concurrent.futures import ThreadPoolExecutor
        from contextlib import closing
        rows=self.preview()['items']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db.sqlite3'
            with closing(sqlite3.connect(path)) as target:self.conn.backup(target)
            def submit(_):
                c=sqlite3.connect(path,timeout=20);c.row_factory=sqlite3.Row
                try:
                    with c:
                        c.execute('BEGIN IMMEDIATE')
                        return post_receipts(c,rows,'TDP',fixture.now_iso)
                finally:c.close()
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,range(2)))
            self.assertEqual([0,2],sorted(r['posted_count'] for r in results))
            with closing(sqlite3.connect(path)) as c:self.assertEqual(3,c.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])
