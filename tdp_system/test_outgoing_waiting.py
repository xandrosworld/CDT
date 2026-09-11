import unittest,io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from openpyxl import load_workbook
from . import server
from .test_outgoing_readiness import OutgoingReadinessTests as Fixture
from .test_order_invoice_range import OrderInvoiceRangeTests
from .outgoing_waiting import refresh_waiting
from .outgoing_readiness import canonical_available_stock


class WaitingTests(unittest.TestCase):
    setUpClass=classmethod(Fixture.setUpClass.__func__)
    tearDownClass=classmethod(Fixture.tearDownClass.__func__)
    setUp=Fixture.setUp
    add_batch=staticmethod(Fixture.add_batch)
    add_opening=staticmethod(Fixture.add_opening)
    request=OrderInvoiceRangeTests.request
    excel_rows=OrderInvoiceRangeTests.excel_rows

    def refresh(self,party='NT-A'):
        r=self.client.post('/api/outgoing-invoices/unissued/refresh?to=2026-09-30&contractor='+party)
        self.assertEqual(r.status_code,200,r.get_json());return r.get_json()

    def seed(self,qty=10,stock=7):
        with server.db() as c:
            self.add_opening(c,stock)
            a,ids=self.add_batch(c,'2026-09-01',[{'qty':qty}])
        return a,ids

    def test_approval_reserves_without_download_then_next_day_cannot_steal(self):
        a,_=self.seed()
        with server.db() as c:c.execute("UPDATE batches SET status='draft' WHERE id=?",(a,))
        response=self.client.post('/api/batches/'+str(a)+'/approve',json={})
        self.assertEqual(response.status_code,200,response.get_json())
        first=self.refresh()['rows'][0]
        self.assertEqual((first['ready_qty'],first['waiting_qty'],first['unissued_qty']),(7,3,10))
        with server.db() as c:
            self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)
            self.add_batch(c,'2026-09-02',[{'qty':4,'contractor':'NT-B'}])
        self.assertEqual(self.refresh('NT-B')['rows'][0]['ready_qty'],0)
        self.assertEqual(self.refresh()['rows'][0]['ready_qty'],7)

    def test_partial_external_issue_then_new_orders_and_stock_accumulate_once(self):
        a,ids=self.seed();self.refresh()
        with server.db() as c:
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','A','0101234567','A','2026-09-01')")
            sid=Fixture.add_posted_source(c,source='minvoice',qty=3,invoice_date='2026-09-02',number='201')
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567' WHERE id=?",(sid,))
        r=self.refresh()['rows'][0]
        self.assertEqual((r['issued_qty'],r['ready_qty'],r['waiting_qty'],r['unissued_qty']),(3,4,3,7))
        with server.db() as c:
            self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)
            before=c.serialize()
        self.refresh()
        with server.db() as c:
            self.assertEqual(c.serialize(),before)
            self.add_batch(c,'2026-09-03',[{'qty':5}])
            Fixture.add_canonical_event(c,4,'input','NEW-STOCK',work_date='2026-09-03')
        r=self.refresh()['rows'][0]
        self.assertEqual((r['approved_qty'],r['issued_qty'],r['ready_qty'],r['waiting_qty'],r['unissued_qty']),(15,3,8,4,12))
        self.assertEqual(sum(row[3] for row in self.excel_rows(self.request())),8)
        r=self.refresh()['rows'][0];self.assertEqual((r['issued_qty'],r['unissued_qty']),(3,12))
        with server.db() as c:self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)

    def test_partial_date_export_preserves_other_days_waiting(self):
        self.seed(stock=20)
        with server.db() as c:self.add_batch(c,'2026-09-02',[{'qty':5}])
        self.refresh();self.assertEqual(sum(r[3] for r in self.excel_rows(self.request(start='2026-09-02',end='2026-09-02'))),5)
        r=self.refresh()['rows'][0];self.assertEqual((r['ready_qty'],r['unissued_qty']),(15,15))
        self.assertEqual(sum(r[3] for r in self.excel_rows(self.request(start='2026-09-01',end='2026-09-01'))),10)

    def test_two_external_issues_consume_the_same_pool_incrementally(self):
        self.seed();self.refresh()
        with server.db() as c:
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','A','0101234567','A','2026-09-01')")
        for number,qty,expected in [('301',3,4),('302',2,2)]:
            with server.db() as c:
                sid=Fixture.add_posted_source(c,source='minvoice',qty=qty,invoice_date='2026-09-03',number=number)
                c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567' WHERE id=?",(sid,))
            self.assertEqual(self.refresh()['rows'][0]['ready_qty'],expected)
            self.assertEqual(self.refresh()['rows'][0]['ready_qty'],expected)

    def test_local_issue_then_matching_source_sync_never_deducts_twice(self):
        self.seed();self.refresh()
        with server.db() as c:
            did=c.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
            c.execute("UPDATE outgoing_invoice_drafts SET status='issued',issued_invoice_number='401',issued_invoice_series='1C26TDP',issued_invoice_date='2026-09-03' WHERE id=?",(did,))
            c.execute("UPDATE inventory_transactions SET status='posted' WHERE source_type='OUTGOING_DRAFT' AND source_id=?",(str(did),))
        self.assertEqual(self.refresh()['rows'][0]['unissued_qty'],3)
        with server.db() as c:
            self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)
            Fixture.add_posted_source(c,source='minvoice',qty=7,invoice_date='2026-09-03',number='401')
        r=self.refresh()['rows'][0]
        self.assertEqual((r['issued_qty'],r['ready_qty'],r['waiting_qty']),(7,0,3))
        with server.db() as c:self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)

    def test_bk_named_waiting_keeps_the_authorized_stock_exception(self):
        self.seed(stock=0)
        with server.db() as c:
            c.execute("UPDATE orders SET tax='KKKNT'")
            c.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
        r=self.refresh()['rows'][0];self.assertEqual((r['ready_qty'],r['waiting_qty']),(0,10))
        with server.db() as c:c.execute("UPDATE orders SET product_name='Hàng thử BK'")
        r=self.refresh()['rows'][0];self.assertEqual((r['ready_qty'],r['waiting_qty']),(10,0))

    def test_changed_stock_reduces_mutable_holds_to_available_stock(self):
        self.seed();self.refresh()
        with server.db() as c:c.execute("UPDATE inventory_transactions SET qty_in=2 WHERE source_type='OPENING'")
        r=self.refresh();self.assertEqual(r['warnings'],[]);self.assertEqual(r['rows'][0]['ready_qty'],2)
        self.assertEqual(sum(r[3] for r in self.excel_rows(self.request())),2)

    def test_old_kkknt_holds_are_removed_and_cannot_unlock_negative_stock(self):
        from unittest.mock import patch
        self.seed(stock=0)
        with server.db() as c:
            c.execute("UPDATE orders SET tax='KKKNT'")
            c.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
            with patch('tdp_system.outgoing_waiting.exempt_order_codes',return_value={'HH-01'}):
                refresh_waiting(c,server.now_iso())
            self.assertEqual(c.execute("SELECT SUM(qty_out) FROM inventory_transactions WHERE status='reserved'").fetchone()[0],10)
        report=self.refresh()
        self.assertEqual(report['rows'][0]['ready_qty'],0)
        self.assertEqual(report['rows'][0]['waiting_qty'],10)
        with server.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM inventory_transactions WHERE status='reserved'").fetchone()[0],0)
        self.assertEqual(self.request().status_code,409)

    def test_locked_remote_hold_is_not_rewritten_after_stock_decreases(self):
        self.seed();self.refresh()
        with server.db() as c:
            c.execute("UPDATE outgoing_invoice_drafts SET minvoice_status='saved' WHERE status='draft'")
            c.execute("UPDATE inventory_transactions SET qty_in=2 WHERE source_type='OPENING'")
            before=c.serialize()
            result=refresh_waiting(c,server.now_iso())
            self.assertTrue(result['warnings'])
            self.assertEqual(c.serialize(),before)

    def test_bk_exception_does_not_leak_to_unmarked_rows_of_same_code(self):
        self.seed(stock=0)
        with server.db() as c:
            c.execute("UPDATE orders SET product_name='Hàng BK'")
            self.add_batch(c,'2026-09-02',[{'qty':5}])
            result=refresh_waiting(c,server.now_iso())
            self.assertEqual(result['created'],[])

    def test_explicit_bk_column_survives_draft_roundtrip_without_renaming_goods(self):
        self.seed(stock=0)
        with server.db() as c:
            c.execute("UPDATE orders SET purchase_list=1,tax='KKKNT'")
            c.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
        self.assertEqual(self.refresh()['rows'][0]['ready_qty'],10)
        self.assertEqual(sum(r[3] for r in self.excel_rows(self.request())),10)
        with server.db() as c:before=c.serialize()
        self.assertEqual(self.refresh()['rows'][0]['ready_qty'],10)
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_old_unit_mismatch_hold_is_released_even_with_bk_marker(self):
        self.seed(stock=10);self.refresh()
        with server.db() as c:
            c.execute("UPDATE orders SET unit='gói',purchase_list=1")
        result=self.refresh()
        self.assertEqual(result['rows'][0]['ready_qty'],0)
        self.assertIn('đơn ghi gói, kho dùng kg',result['held_line_issues'][0]['message'])
        with server.db() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM inventory_transactions WHERE status='reserved'").fetchone()[0],0)

    def test_refresh_and_excel_are_idempotent_and_repeat_does_not_consume_stock(self):
        self.seed();self.refresh()
        with server.db() as c:before=c.serialize()
        self.refresh()
        r=self.client.get('/api/outgoing-invoices/unissued.xlsx?to=2026-09-30&contractor=NT-A')
        self.assertEqual(r.status_code,200)
        w=load_workbook(io.BytesIO(r.data),data_only=True)
        self.assertEqual((w.active['J2'].value,w.active['K2'].value,w.active['L2'].value),(10,7,3));w.close()
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_concurrent_refresh_holds_stock_only_once(self):
        self.seed();gate=Barrier(2)
        def work():
            with server.app.test_client() as client:
                gate.wait();return client.post('/api/outgoing-invoices/unissued/refresh?to=2026-09-30').status_code
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(list(pool.map(lambda _:work(),range(2))),[200,200])
        with server.db() as c:self.assertEqual(c.execute("SELECT SUM(qty_out) FROM inventory_transactions WHERE status='reserved'").fetchone()[0],7)

    def test_kg_remainders_pool_across_days_at_the_original_sale_price(self):
        self.seed(qty=.46,stock=3);self.refresh()
        with server.db() as c:self.add_batch(c,'2026-09-02',[{'qty':.46}])
        r=self.refresh()['rows'][0];self.assertAlmostEqual(r['ready_qty'],.9);self.assertAlmostEqual(r['waiting_qty'],.02)
        rows=self.excel_rows(self.request());self.assertEqual((rows[0][3],rows[0][4]),(.9,20))

if __name__=='__main__':unittest.main()
