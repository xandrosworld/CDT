import io
import unittest
import zipfile
from unittest.mock import patch
from openpyxl import load_workbook
from . import server
from .test_outgoing_readiness import OutgoingReadinessTests as Fixture
from .outgoing_readiness import canonical_available_stock, allocation_by_order


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
        self.assertEqual(r.headers['X-Invoice-Files'],'1')
        self.assertEqual(r.headers['X-Pending-Order-Lines'],'1')
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            self.assertEqual(len([n for n in z.namelist() if n.endswith('.xlsx')]),1)
            self.assertTrue(all('/' not in n for n in z.namelist()))
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
            self.assertEqual(c.execute("SELECT SUM(l.qty) FROM outgoing_invoice_lines l JOIN outgoing_invoice_drafts d ON d.id=l.draft_id WHERE d.status='draft'").fetchone()[0],7)

    def test_unapproved_day_blocks_entire_range(self):
        _,b=self.seed()
        with server.db() as c:c.execute("UPDATE batches SET status='draft' WHERE id=?",(b,))
        self.assertEqual(self.request().status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)

    def test_export_failure_rolls_back_new_reservations(self):
        self.seed()
        with patch('tdp_system.invoice_tax_export.build_invoice_workbook',side_effect=server.InvoiceTaxExportError('test invalid template')):
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
        with server.db() as c:self.assertEqual(c.execute("SELECT SUM(l.qty) FROM outgoing_invoice_lines l JOIN outgoing_invoice_drafts d ON d.id=l.draft_id WHERE d.status='draft'").fetchone()[0],10)

    def excel_rows(self,response):
        self.assertEqual(response.status_code,200,response.get_json(silent=True))
        result=[]
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            for name in z.namelist():
                if name.endswith('.xlsx'):
                    wb=load_workbook(io.BytesIO(z.read(name)),data_only=True)
                    result.extend(list(wb.active.values)[1:]);wb.close()
        return result

    def test_weighted_price_and_single_product_across_days(self):
        with server.db() as c:
            self.add_opening(c,10)
            a,ids_a=self.add_batch(c,'2026-09-01',[{'qty':2,'sell_price':20}])
            b,ids_b=self.add_batch(c,'2026-09-02',[{'qty':1,'sell_price':30}])
        rows=self.excel_rows(self.request())
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0][3],rows[0][8]),(3,70))
        self.assertAlmostEqual(rows[0][4],70/3,places=8)
        with server.db() as c:
            allocated=allocation_by_order(c,[a,b])
            self.assertEqual(allocated[ids_a[0]]['drafted_qty'],2)
            self.assertEqual(allocated[ids_b[0]]['drafted_qty'],1)
            did=c.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
        # One merged invoice is visible from either source day, with its lineage.
        for bid in (a,b):
            draft=next(r for r in self.client.get('/api/outgoing-invoices?batch_id='+str(bid)).get_json()['items'] if r['id']==did)
            self.assertEqual(set(draft['source_batch_ids']),{a,b})
        self.assertEqual(self.request(start='2026-09-02').status_code,409)

    def test_kg_floor_releases_fraction_and_recalculates_money(self):
        with server.db() as c:
            self.add_opening(c,1)
            bid,ids=self.add_batch(c,'2026-09-01',[{'qty':.432,'sell_price':20000}])
        response=self.request();rows=self.excel_rows(response)
        self.assertEqual((rows[0][3],rows[0][4],rows[0][8]),(.4,20000,8000))
        self.assertEqual(response.headers['X-Pending-Order-Lines'],'1')
        with server.db() as c:
            self.assertEqual(allocation_by_order(c,[bid])[ids[0]]['drafted_qty'],.4)
            self.assertAlmostEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],.6)

    def test_kg_round_only_after_adding_matching_codes(self):
        with server.db() as c:
            self.add_opening(c,1)
            self.add_batch(c,'2026-09-01',[{'qty':.04,'sell_price':10000}])
            self.add_batch(c,'2026-09-02',[{'qty':.06,'sell_price':10000}])
        rows=self.excel_rows(self.request())
        self.assertEqual(len(rows),1);self.assertEqual((rows[0][3],rows[0][8]),(.1,1000))

    def test_shrimp_example_and_tax_files_not_day_files(self):
        with server.db() as c:
            self.add_opening(c,20)
            self.add_batch(c,'2026-09-01',[{'qty':7,'sell_price':130000}])
            _,ids=self.add_batch(c,'2026-09-02',[{'qty':6.3,'sell_price':130000},{'qty':1,'sell_price':10000}])
            c.execute("UPDATE orders SET tax='8%' WHERE id=?",(ids[1],))
        response=self.request();rows=self.excel_rows(response)
        self.assertEqual(response.headers['X-Invoice-Files'],'2')
        shrimp=next(r for r in rows if r[9]==0)
        self.assertEqual((shrimp[3],shrimp[4],shrimp[8]),(13.3,130000,1729000))

    def test_cancelling_group_restores_all_source_days(self):
        a,b=self.seed()
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:
            did=c.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
        response=self.client.post(f'/api/outgoing-invoices/{did}/cancel',json={'confirmed':True})
        self.assertEqual(response.status_code,200,response.get_json())
        with server.db() as c:
            self.assertEqual(allocation_by_order(c,[a,b]),{})
            self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],7)

    def test_repeat_with_entire_day_rounded_out_keeps_same_price_and_draft(self):
        with server.db() as c:
            self.add_opening(c,3)
            self.add_batch(c,'2026-09-01',[{'qty':1,'sell_price':20000}])
            self.add_batch(c,'2026-09-02',[{'qty':.04,'sell_price':30000}])
        first=self.request();self.assertEqual(first.status_code,200)
        with server.db() as c:before=c.serialize()
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_one_issued_invoice_tracks_both_source_days(self):
        a,b=self.seed()
        self.assertEqual(self.request().status_code,200)
        self.client.put('/api/outgoing-buyers/NT-A',json={'legal_name':'Công ty thử','tax_code':'0100000001','address':'Địa chỉ thử'})
        with server.db() as c:
            did=c.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
        r=self.client.post(f'/api/outgoing-invoices/{did}/confirm-issued',json={'confirmed':True,'invoice_number':'1234','invoice_series':'C26TEST','invoice_date':'2026-09-03'})
        self.assertEqual(r.status_code,200,r.get_json())
        with server.db() as c:
            allocations=allocation_by_order(c,[a,b])
            self.assertEqual(sum(r['issued_qty'] for r in allocations.values()),7)
            self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)
            self.assertTrue(server.batch_mutation_blocker(c,a))
            self.assertTrue(server.batch_mutation_blocker(c,b))
        scope=self.client.get('/api/outgoing-invoices/payment-scope/NT-A?from=2026-09-01&to=2026-09-03')
        self.assertEqual(scope.status_code,200,scope.get_json())

    def test_zero_stock_taxable_does_not_create_empty_file(self):
        self.seed(stock=0)
        self.assertEqual(self.request().status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)

    def test_missing_contractor_and_invalid_range(self):
        self.seed()
        self.assertEqual(self.request('MISSING').status_code,409)
        self.assertEqual(self.request(start='2026-09-03',end='2026-09-01').status_code,409)


if __name__=='__main__':unittest.main()
