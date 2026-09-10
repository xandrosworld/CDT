import unittest,io
from openpyxl import load_workbook
from . import server
from .test_order_invoice_range import OrderInvoiceRangeTests
from .test_outgoing_readiness import OutgoingReadinessTests as Fixture
from .outgoing_unissued import issued_allocations

class UnissuedTests(unittest.TestCase):
    setUpClass=classmethod(Fixture.setUpClass.__func__)
    tearDownClass=classmethod(Fixture.tearDownClass.__func__)
    setUp=Fixture.setUp
    add_batch=staticmethod(Fixture.add_batch)
    add_opening=staticmethod(Fixture.add_opening)
    request=OrderInvoiceRangeTests.request
    seed=OrderInvoiceRangeTests.seed

    def report(self,to='2026-09-03'):
        r=self.client.get('/api/outgoing-invoices/unissued?to='+to+'&contractor=NT-A')
        self.assertEqual(r.status_code,200,r.get_json());return r.get_json()

    def test_cumulative_orders_and_downloads_never_reduce_unissued(self):
        self.seed()
        self.assertEqual(self.report('2026-09-01')['rows'][0]['unissued_qty'],5)
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],10)
        self.assertEqual(self.request().status_code,200)
        r=self.report()['rows'][0]
        self.assertEqual((r['approved_qty'],r['drafted_qty'],r['issued_qty'],r['unissued_qty']),(10,7,0,10))
        with server.db() as c:before=c.serialize()
        excel=self.client.get('/api/outgoing-invoices/unissued.xlsx?to=2026-09-03&contractor=NT-A')
        self.assertEqual(excel.status_code,200)
        w=load_workbook(io.BytesIO(excel.data),data_only=True);self.assertEqual(w.active['J2'].value,10);w.close()
        with server.db() as c:self.assertEqual(before,c.serialize())

    def test_later_issued_invoice_settles_earlier_order_dates(self):
        a,b=self.seed()
        with server.db() as c:
            oid=c.execute('SELECT id FROM orders WHERE batch_id=?',(a,)).fetchone()[0]
            Fixture.add_local_issued_draft(c,a,oid,number='101',invoice_date='2026-09-03',qty=3)
        self.assertEqual(self.report('2026-09-01')['rows'][0]['unissued_qty'],2)
        self.assertEqual(self.report('2026-09-02')['rows'][0]['unissued_qty'],7)
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],7)

    def test_synced_m_invoice_fifo_and_duplicate_local_confirmation_count_once(self):
        a,b=self.seed(stock=20)
        with server.db() as c:
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Test','0101234567','Test','2026-09-01')")
            sid=Fixture.add_posted_source(c,source='minvoice',qty=3,invoice_date='2026-09-03',number='101')
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567' WHERE id=?",(sid,))
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],7)
        with server.db() as c:
            oid=c.execute('SELECT id FROM orders WHERE batch_id=?',(a,)).fetchone()[0]
            Fixture.add_local_issued_draft(c,a,oid,number='101',invoice_date='2026-09-03',qty=3)
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],7)
        with server.db() as c:c.execute("UPDATE outgoing_source_invoices SET source_status_class='cancelled',stock_status='reversed' WHERE id=?",(sid,))
        report=self.report();self.assertEqual(report['rows'][0]['unissued_qty'],10);self.assertTrue(report['warnings'])

    def test_external_draft_never_counts_and_unapproved_orders_excluded(self):
        a,b=self.seed(stock=20)
        with server.db() as c:
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Test','0101234567','Test','2026-09-01')")
            sid=Fixture.add_posted_source(c,source='minvoice',qty=3,invoice_date='2026-09-03',number='102')
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567',source_status_class='draft' WHERE id=?",(sid,))
            c.execute("UPDATE batches SET status='draft' WHERE id=?",(b,))
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],5)

    def test_invalid_cutoff_is_rejected(self):
        self.assertEqual(self.client.get('/api/outgoing-invoices/unissued?to=bad').status_code,400)

    def test_unmapped_issued_invoice_is_flagged_and_blocks_duplicate_export(self):
        self.seed(stock=20)
        with server.db() as c:
            Fixture.add_posted_source(c,source='minvoice',qty=3,invoice_date='2026-09-03',number='103')
            before=c.serialize()
        report=self.report()
        self.assertFalse(report['reconciliation_complete'])
        response=self.request()
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.get_json()['code'],'issued_source_unresolved')
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_conflicting_confirmed_quantity_is_visible_and_not_counted_twice(self):
        a,b=self.seed(stock=20)
        with server.db() as c:
            sid=Fixture.add_posted_source(c,source='minvoice',qty=4,invoice_date='2026-09-03',number='104')
            oid=c.execute('SELECT id FROM orders WHERE batch_id=?',(a,)).fetchone()[0]
            Fixture.add_local_issued_draft(c,a,oid,number='104',invoice_date='2026-09-03',qty=3)
        report=self.report()
        self.assertFalse(report['reconciliation_complete'])
        self.assertEqual(report['rows'][0]['issued_qty'],3)
        self.assertEqual(self.request().status_code,409)

if __name__=='__main__':unittest.main()
