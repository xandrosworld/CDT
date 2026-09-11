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

    def test_unit_mismatch_holds_only_affected_row_and_exports_both_parties(self):
        self.seed(stock=100)
        with server.db() as c:
            self.add_batch(c,'2026-09-01',[{'qty':5,'contractor':'NT-B'}])
            bid,_=self.add_batch(c,'2026-09-02',[{'qty':4,'contractor':'NT-B'}])
            c.execute("UPDATE orders SET unit='gói' WHERE batch_id=?",(bid,))
        self.assertEqual(self.request('NT-B',start='2026-09-01',end='2026-09-01').status_code,200)
        self.assertEqual(self.request('NT-B',start='2026-09-02',end='2026-09-02').status_code,409)
        before=None
        for _ in range(2):
            result=self.request(contractor='')
            self.assertEqual(result.status_code,200,result.get_json(silent=True))
            self.assertEqual(result.headers['X-Blocked-Contractors'],'0')
            self.assertEqual(result.headers['X-Held-Unit-Lines'],'1')
            with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
                excel=[n for n in archive.namelist() if n.endswith('.xlsx')]
                self.assertEqual(len(excel),2)
                guide=archive.read('HUONG_DAN_VA_PHAN_CHUA_XUAT.txt').decode('utf-8-sig')
                self.assertIn('NT-B',guide);self.assertIn('đơn ghi gói, kho dùng kg',guide)
            with server.db() as c:
                self.assertEqual(c.execute("SELECT COALESCE(SUM(qty_out),0) FROM inventory_transactions WHERE status='reserved'").fetchone()[0],15)
                if before is not None:self.assertEqual(c.serialize(),before)
                before=c.serialize()
        self.assertEqual(self.request('NT-B').status_code,200)

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

    def test_new_stock_fills_remainder_and_repeat_keeps_same_holds(self):
        self.seed();self.assertEqual(self.request().status_code,200)
        with server.db() as c:
            c.execute("UPDATE inventory_transactions SET qty_in=10 WHERE source_type='OPENING'")
        rows=self.excel_rows(self.request())
        self.assertEqual(rows[0][3],10)
        with server.db() as c:
            self.assertEqual(c.execute("SELECT SUM(qty_out) FROM inventory_transactions WHERE status='reserved'").fetchone()[0],10)
            before=c.serialize()
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_fractional_remainder_combines_with_later_day_at_same_sale_price(self):
        with server.db() as c:
            self.add_opening(c,3)
            self.add_batch(c,'2026-09-01',[{'qty':.46,'sell_price':20000}])
        self.assertEqual(self.excel_rows(self.request())[0][3],.4)
        with server.db() as c:before=c.serialize()
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:
            self.assertEqual(c.serialize(),before)
            self.add_batch(c,'2026-09-02',[{'qty':.46,'sell_price':20000}])
        rows=self.excel_rows(self.request())
        self.assertEqual((rows[0][3],rows[0][4]),(.9,20000))

    def test_float_residual_does_not_lose_tenth_or_change_redownload(self):
        with server.db() as c:
            self.add_opening(c,0)
            self.add_batch(c,'2026-09-01',[
                {'qty':.1+.7,'sell_price':40000},
                {'qty':.799999,'sell_price':50000},
            ])
            c.execute('UPDATE orders SET purchase_list=1')
        first=self.excel_rows(self.request())
        self.assertEqual([(r[3],r[4],r[8]) for r in first],[(.8,40000,32000),(.7,50000,35000)])
        with server.db() as c:before=c.serialize()
        for _ in range(2):
            self.assertEqual(self.excel_rows(self.request()),first)
            with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_piece_float_residual_is_not_treated_as_a_whole_piece_shortage(self):
        from decimal import Decimal
        from .outgoing_consolidation import export_quantity
        self.assertEqual(export_quantity(Decimal('26.999999999999996'),'Cái'),Decimal('27'))
        self.assertEqual(export_quantity(Decimal('26.999999'),'Cái'),Decimal('26'))
        self.assertEqual(export_quantity(Decimal('27.6'),'Cái'),Decimal('27'))

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

    def test_decreased_stock_caps_redownload(self):
        self.seed();self.assertEqual(self.request().status_code,200)
        with server.db() as c:c.execute("UPDATE inventory_transactions SET qty_in=1 WHERE source_type='OPENING'")
        self.assertEqual(sum(r[3] for r in self.excel_rows(self.request())),1)

    def test_only_bk_named_rows_export_without_stock(self):
        self.seed(stock=0)
        with server.db() as c:
            c.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
            c.execute("UPDATE orders SET tax='KKKNT'")
        self.assertEqual(self.request().status_code,409)
        with server.db() as c:c.execute("UPDATE orders SET product_name='Hàng thử BK'")
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

    def test_distinct_sale_prices_are_preserved_across_days(self):
        with server.db() as c:
            self.add_opening(c,10)
            a,ids_a=self.add_batch(c,'2026-09-01',[{'qty':2,'sell_price':20}])
            b,ids_b=self.add_batch(c,'2026-09-02',[{'qty':1,'sell_price':30}])
        rows=self.excel_rows(self.request())
        self.assertEqual(len(rows),2)
        self.assertEqual([(r[3],r[4],r[8]) for r in rows],[(2,20,40),(1,30,30)])
        with server.db() as c:
            allocated=allocation_by_order(c,[a,b])
            self.assertEqual(allocated[ids_a[0]]['drafted_qty'],2)
            self.assertEqual(allocated[ids_b[0]]['drafted_qty'],1)
            did=c.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
        # One merged invoice is visible from either source day, with its lineage.
        for bid in (a,b):
            draft=next(r for r in self.client.get('/api/outgoing-invoices?batch_id='+str(bid)).get_json()['items'] if r['id']==did)
            self.assertEqual(set(draft['source_batch_ids']),{a,b})
        selected=self.excel_rows(self.request(start='2026-09-02'))
        self.assertEqual([(r[3],r[4]) for r in selected],[(1,30)])

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

    def test_approved_order_prices_ignore_separate_quote_and_do_not_average(self):
        with server.db() as c:
            self.add_opening(c,300)
            a,_=self.add_batch(c,'2026-09-01',[{'qty':108.9,'sell_price':2700}])
            b,_=self.add_batch(c,'2026-09-03',[{'qty':108,'sell_price':2800}])
            c.execute("UPDATE orders SET unit='Quả'")
            c.execute("UPDATE products SET unit='Quả' WHERE code='HH-01'")
            c.execute("INSERT OR REPLACE INTO product_prices(product_code,price_group,price_text,price_value) VALUES('HH-01','NT-A','X',NULL)")
            before=[tuple(r) for r in c.execute('SELECT * FROM orders ORDER BY id')]
        try:
            rows=self.excel_rows(self.request())
            self.assertEqual([(r[3],r[4],r[8]) for r in rows],[(108,2700,291600),(108,2800,302400)])
            with server.db() as c:
                self.assertEqual(before,[tuple(r) for r in c.execute('SELECT * FROM orders ORDER BY id')])
                self.assertEqual(sum(r['drafted_qty'] for r in allocation_by_order(c,[a,b]).values()),216)
        finally:
            with server.db() as c:c.execute("DELETE FROM product_prices WHERE product_code='HH-01' AND price_group='NT-A'")

    def test_existing_averaged_draft_restores_source_price_and_is_repeatable(self):
        self.seed()
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:
            line=c.execute("SELECT l.* FROM outgoing_invoice_lines l JOIN outgoing_invoice_drafts d ON d.id=l.draft_id WHERE d.status='draft'").fetchone()
            c.execute('UPDATE outgoing_invoice_lines SET unit_price=20.5,amount=144 WHERE id=?',(line['id'],))
            reserved=c.execute("SELECT SUM(qty_out) FROM inventory_transactions WHERE status='reserved'").fetchone()[0]
            orders=[tuple(r) for r in c.execute('SELECT * FROM orders ORDER BY id')]
        rows=self.excel_rows(self.request())
        self.assertEqual((rows[0][3],rows[0][4],rows[0][8]),(7,20,140))
        with server.db() as c:
            self.assertEqual(reserved,c.execute("SELECT SUM(qty_out) FROM inventory_transactions WHERE status='reserved'").fetchone()[0])
            self.assertEqual(orders,[tuple(r) for r in c.execute('SELECT * FROM orders ORDER BY id')])
            self.assertEqual(c.execute("SELECT subtotal FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0],140)
            before=c.serialize()
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_select_one_day_after_range_preserves_other_days_and_rolls_back_failure(self):
        a,b=self.seed()
        self.assertEqual(self.request().status_code,200)
        with server.db() as c:before=c.serialize()
        with patch('tdp_system.invoice_tax_export.build_invoice_workbook',side_effect=server.InvoiceTaxExportError('bad template')):
            self.assertEqual(self.request(start='2026-09-02',end='2026-09-02').status_code,409)
        with server.db() as c:self.assertEqual(c.serialize(),before)
        rows=self.excel_rows(self.request(start='2026-09-02',end='2026-09-02'))
        self.assertEqual(rows[0][3],2)
        with server.db() as c:
            allocation=allocation_by_order(c,[a,b])
            self.assertEqual(sum(r['drafted_qty'] for r in allocation.values()),7)
            self.assertEqual(canonical_available_stock(c)['HH-01']['raw_available_qty'],0)
            before=c.serialize()
        self.assertEqual(self.request(start='2026-09-02',end='2026-09-02').status_code,200)
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_ten_rows_same_sale_price_keep_one_price(self):
        with server.db() as c:
            self.add_opening(c,30)
            self.add_batch(c,'2026-09-01',[{'qty':1,'sell_price':20000} for _ in range(10)])
        rows=self.excel_rows(self.request())
        self.assertEqual([(r[3],r[4],r[8]) for r in rows],[(10,20000,200000)])

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

    def cumulative(self, contractor='NT-A', **extra):
        return self.client.post('/api/export/order-invoices',json={'contractor':contractor,'scope':'unissued',**extra})

    def test_explicit_order_cutoff_excludes_later_orders_but_deducts_later_signed_invoice(self):
        with server.db() as c:
            self.add_opening(c,100)
            _,ids=self.add_batch(c,'2026-09-07',[{'qty':10}])
            self.add_batch(c,'2026-09-08',[{'qty':20}])
            Fixture.add_local_issued_draft(c,c.execute('SELECT batch_id FROM orders WHERE id=?',(ids[0],)).fetchone()[0],ids[0],number='790',invoice_date='2026-09-10',qty=3)
        response=self.cumulative(to='2026-09-07')
        self.assertEqual(sum(r[3] for r in self.excel_rows(response)),7)
        self.assertIn('2026-09-07',response.headers['Content-Disposition'])

    def test_signed_buns_are_deducted_and_fractional_piece_is_not_exported(self):
        with server.db() as c:
            self.add_opening(c,27.6)
            bid,ids=self.add_batch(c,'2026-09-02',[{'qty':83}])
            c.execute("UPDATE orders SET unit='Cái'")
            c.execute("UPDATE products SET unit='Cái' WHERE code='HH-01'")
            Fixture.add_local_issued_draft(c,bid,ids[0],number='790',invoice_date='2026-09-10',qty=27)
        self.assertEqual(self.cumulative(to='2026-09-07').status_code,409)
        with server.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0],0)

    def test_cumulative_includes_prior_month_ignores_stale_dates_and_excludes_drafts_future(self):
        with server.db() as c:
            self.add_opening(c,50)
            self.add_batch(c,'2026-08-31',[{'qty':2}])
            self.add_batch(c,'2026-09-03',[{'qty':3}])
            draft,_=self.add_batch(c,'2026-09-04',[{'qty':10}])
            c.execute("UPDATE batches SET status='draft' WHERE id=?",(draft,))
            self.add_batch(c,'2099-09-01',[{'qty':20}])
            before=[tuple(r) for r in c.execute('SELECT * FROM orders ORDER BY id')]
        r=self.cumulative(**{'from':'2026-09-03','to':'2026-09-03'})
        self.assertEqual(r.headers['X-Order-Scope'],'unissued')
        self.assertEqual(self.excel_rows(r)[0][3],5)
        with server.db() as c:
            self.assertEqual(before,[tuple(r) for r in c.execute('SELECT * FROM orders ORDER BY id')])
            self.assertEqual(c.execute('SELECT status FROM batches WHERE id=?',(draft,)).fetchone()[0],'draft')
            snapshot=c.serialize()
        self.assertEqual(self.cumulative().status_code,200)
        with server.db() as c:self.assertEqual(c.serialize(),snapshot)

    def test_cumulative_new_day_adds_to_old_download_and_issued_amount_disappears(self):
        with server.db() as c:
            self.add_opening(c,20)
            self.add_batch(c,'2026-09-01',[{'qty':3}])
        self.assertEqual(self.excel_rows(self.cumulative())[0][3],3)
        with server.db() as c:self.add_batch(c,'2026-09-04',[{'qty':2}])
        self.assertEqual(self.excel_rows(self.cumulative())[0][3],5)
        self.client.put('/api/outgoing-buyers/NT-A',json={'legal_name':'Công ty thử','tax_code':'0100000001','address':'Địa chỉ thử'})
        with server.db() as c:did=c.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
        issued=self.client.post(f'/api/outgoing-invoices/{did}/confirm-issued',json={'confirmed':True,'invoice_number':'5678','invoice_series':'C26TEST','invoice_date':'2026-09-05'})
        self.assertEqual(issued.status_code,200,issued.get_json())
        self.assertEqual(self.cumulative().status_code,409)
        with server.db() as c:self.add_batch(c,'2026-09-06',[{'qty':4}])
        self.assertEqual(self.excel_rows(self.cumulative())[0][3],4)

    def test_cumulative_has_no_100_batch_cutoff(self):
        with server.db() as c:
            self.add_opening(c,110)
            for _ in range(101):self.add_batch(c,'2026-09-01',[{'qty':1}])
        self.assertEqual(self.excel_rows(self.cumulative())[0][3],101)

    def test_no_dates_defaults_to_backlog_and_sync_uses_earliest_approved(self):
        self.seed()
        response=self.client.post('/api/export/order-invoices',json={'contractor':'NT-A'})
        self.assertEqual(self.excel_rows(response)[0][3],7)
        with patch('tdp_system.outgoing_source_refresh.refresh_sources',return_value={'to':'2026-09-11'}) as sync:
            r=self.client.post('/api/outgoing-invoices/sync-issued',json={'scope':'unissued','contractor':'NT-A'})
            self.assertEqual(r.status_code,200)
            self.assertEqual(sync.call_args.args[3],'2026-09-01')

    def test_cumulative_sync_failure_never_exports_stale_quantities(self):
        self.seed()
        with server.db() as c:c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('minvoice_active_connection','test')")
        try:
            with patch('tdp_system.outgoing_source_refresh.refresh_sources',side_effect=ValueError('test connection failed')):
                r=self.cumulative()
                self.assertEqual(r.status_code,409)
                self.assertEqual(r.get_json()['code'],'issued_sync_required')
            with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)
        finally:
            with server.db() as c:c.execute("DELETE FROM settings WHERE key='minvoice_active_connection'")


if __name__=='__main__':unittest.main()
