import io
import unittest
import zipfile
from unittest.mock import patch
from . import server
from .test_outgoing_readiness import OutgoingReadinessTests as Fixture
from .outgoing_readiness import canonical_available_stock


class OrderInvoiceRangeTests(unittest.TestCase):
    setUpClass = classmethod(Fixture.setUpClass.__func__)
    tearDownClass = classmethod(Fixture.tearDownClass.__func__)
    setUp = Fixture.setUp
    add_batch = staticmethod(Fixture.add_batch)
    add_opening = staticmethod(Fixture.add_opening)

    def request(self, contractor='NT-A', start='2026-09-01', end='2026-09-03'):
        return self.client.post('/api/export/order-invoices',json={'contractor':contractor,'from':start,'to':end})

    def seed(self, stock=7):
        with server.db() as c:
            self.add_opening(c,stock)
            a,_=self.add_batch(c,'2026-09-01',[{'qty':5}])
            b,_=self.add_batch(c,'2026-09-02',[{'qty':5}])
        return a,b

    def test_two_days_cap_stock_and_repeat_does_not_change_reservations(self):
        self.seed()
        r=self.request();self.assertEqual(r.status_code,200,r.get_json(silent=True))
        self.assertEqual(r.headers['X-Invoice-Files'],'2')
        self.assertEqual(r.headers['X-Pending-Order-Lines'],'1')
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            self.assertEqual(len([n for n in z.namelist() if n.endswith('.xlsx')]),2)
            self.assertIn('còn 3 kg',z.read('HUONG_DAN_VA_PHAN_CHUA_XUAT.txt').decode('utf-8-sig'))
        with server.db() as c:
            self.assertEqual(c.execute("SELECT SUM(qty_out) FROM inventory_transactions WHERE status='reserved'").fetchone()[0],7)
            self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)
            before=c.serialize()
        again=self.request();self.assertEqual(again.status_code,200)
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_contractor_filter_does_not_touch_other_drafts(self):
        with server.db() as c:
            self.add_opening(c,20)
            bid,_=self.add_batch(c,'2026-09-01',[{'qty':3,'contractor':'NT-A'},{'qty':4,'contractor':'NT-B'}])
        self.assertEqual(self.request('NT-B').status_code,200)
        with server.db() as c:
            before=[tuple(r) for r in c.execute("SELECT * FROM outgoing_invoice_drafts WHERE contractor='NT-B'")]
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:
            self.assertEqual(before,[tuple(r) for r in c.execute("SELECT * FROM outgoing_invoice_drafts WHERE contractor='NT-B'")])
            self.assertEqual(c.execute('SELECT SUM(qty) FROM outgoing_invoice_lines').fetchone()[0],7)

    def test_unapproved_day_blocks_entire_range(self):
        _,b=self.seed()
        with server.db() as c:c.execute("UPDATE batches SET status='draft' WHERE id=?",(b,))
        self.assertEqual(self.request().status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)

    def test_export_failure_rolls_back_new_reservations(self):
        self.seed()
        with patch.object(server,'export_invoices_zip',side_effect=server.InvoiceTaxExportError('test invalid template')):
            self.assertEqual(self.request().status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)

    def test_decreased_stock_blocks_redownload(self):
        self.seed();self.assertEqual(self.request().status_code,200)
        with server.db() as c:c.execute("UPDATE inventory_transactions SET qty_in=1 WHERE source_type='OPENING'")
        self.assertEqual(self.request().status_code,409)

    def test_kkknt_exception_still_exports_without_stock(self):
        self.seed(stock=0)
        with server.db() as c:
            c.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
            c.execute("UPDATE orders SET tax='KKKNT'")
        r=self.request();self.assertEqual(r.status_code,200,r.get_json(silent=True))
        self.assertEqual(r.headers['X-Pending-Order-Lines'],'0')
        with server.db() as c:self.assertEqual(c.execute('SELECT SUM(qty) FROM outgoing_invoice_lines').fetchone()[0],10)

    def test_zero_stock_taxable_does_not_create_empty_file(self):
        self.seed(stock=0)
        self.assertEqual(self.request().status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)

    def test_missing_contractor_and_invalid_range(self):
        self.seed()
        self.assertEqual(self.request('MISSING').status_code,409)
        self.assertEqual(self.request(start='2026-09-03',end='2026-09-01').status_code,409)


if __name__=='__main__':unittest.main()
