import unittest
import io
from openpyxl import load_workbook
from . import server, batch_bk_approval as approval
from .test_bk_import import BKImportTests, NOW
from .purchase_summary_export import collect_purchase_summary_rows


class BatchBKApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        BKImportTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        BKImportTests.tearDownClass.__func__(cls)

    def setUp(self):
        with server.db() as conn:
            conn.execute('DELETE FROM batch_bk_approvals')
        BKImportTests.setUp(self)
        with server.db() as conn:
            conn.execute("DELETE FROM people")
            conn.execute("INSERT INTO people(name,cccd,address) VALUES('Người bán BK','123456789','Địa chỉ thử nghiệm')")
            conn.execute("UPDATE products SET seller='Người bán BK',cccd='123456789'")
            self.batch = conn.execute("INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-09-03','test.xlsx','draft',?)", (NOW,)).lastrowid
            self.order = self.add_line(conn)

    def add_line(self, conn, code='BK-P1', qty=2):
        name, unit = ('Hàng BK', 'kg') if code == 'BK-P1' else ('Hàng BK 2','chai')
        return conn.execute('''INSERT INTO orders(batch_id,work_date,contractor,kitchen,product_code,
            product_name,qty,actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
            purchase_list,source_row,errors,warnings,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (self.batch,'2026-09-03','C1','K1',code,name,qty,qty,qty,unit,'BK-S1',111,200,'8%',1,27,'[]','[]',NOW)).lastrowid

    def preview(self):
        r=self.client.get(f'/api/batches/{self.batch}/approval-preview')
        self.assertEqual(r.status_code,200,r.get_json())
        return r.get_json()

    def post(self, **extra):
        p=self.preview()
        return self.client.post(f'/api/batches/{self.batch}/approve',json={
            'source_hash':p['sourceHash'],'confirm_bk':True,**extra})

    def assert_empty_draft(self):
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM invoice_inventory_ledger').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM bk_import_documents').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT status FROM batches WHERE id=?',(self.batch,)).fetchone()[0],'draft')

    def test_preview_readonly_and_repeat_approval_does_not_duplicate(self):
        p=self.preview();self.assertTrue(p['canApprove']);self.assertEqual(p['amount'],380)
        self.assert_empty_draft()
        first=self.post();self.assertEqual(first.status_code,200,first.get_json())
        second=self.post();self.assertEqual(second.status_code,200,second.get_json())
        self.assertEqual(first.get_json()['bk']['newInventoryLines'],1)
        self.assertEqual(second.get_json()['bk']['newInventoryLines'],0)
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT SUM(qty_delta) FROM invoice_inventory_ledger').fetchone()[0],2)
            self.assertTrue(server.batch_mutation_blocker(conn,self.batch))
            rows=collect_purchase_summary_rows(conn,dict(conn.execute('SELECT * FROM batches WHERE id=?',(self.batch,)).fetchone()),
                                               conn.execute('SELECT * FROM orders WHERE batch_id=?',(self.batch,)).fetchall())
            self.assertEqual((rows[0]['buy_price'],rows[0]['amount']),(190,380))

    def test_no_confirmation_cannot_post(self):
        r=self.client.post(f'/api/batches/{self.batch}/approve')
        self.assertEqual(r.status_code,409);self.assert_empty_draft()

    def test_stale_preview_cannot_post(self):
        p=self.preview()
        with server.db() as conn:conn.execute('UPDATE orders SET actual_received=3 WHERE id=?',(self.order,))
        r=self.client.post(f'/api/batches/{self.batch}/approve',json={'source_hash':p['sourceHash'],'confirm_bk':True})
        self.assertEqual(r.status_code,409);self.assert_empty_draft()

    def test_missing_price_reports_source_row_without_identity_number(self):
        with server.db() as conn:conn.execute('UPDATE orders SET sell_price=0 WHERE id=?',(self.order,))
        p=self.preview();self.assertFalse(p['canApprove']);self.assertEqual(p['issues'][0]['row'],27)
        self.assertNotIn('123456789',str(p))
        self.assertEqual(self.post().status_code,409);self.assert_empty_draft()

    def test_missing_identity_blocks(self):
        with server.db() as conn:conn.execute("UPDATE people SET address=''")
        self.assertFalse(self.preview()['canApprove'])
        self.assertEqual(self.post().status_code,409);self.assert_empty_draft()

    def test_wrong_product_name_and_unit_block(self):
        with server.db() as conn:conn.execute("UPDATE orders SET product_name='Khác mặt hàng',unit='thùng' WHERE id=?",(self.order,))
        self.assertFalse(self.preview()['canApprove']);self.assertEqual(self.post().status_code,409)
        self.assert_empty_draft()

    def test_receipt_less_returns_and_damage(self):
        with server.db() as conn:conn.execute('UPDATE orders SET damaged_qty=.25,supplier_return_qty=.5 WHERE id=?',(self.order,))
        self.assertEqual(self.post().status_code,200)
        with server.db() as conn:self.assertEqual(conn.execute('SELECT qty_delta FROM invoice_inventory_ledger').fetchone()[0],1.25)

    def test_failure_second_line_rolls_back_approval_and_all_movements(self):
        with server.db() as conn:
            self.add_line(conn,'BK-P2')
            conn.execute("""CREATE TRIGGER fail_bk_second_line BEFORE INSERT ON invoice_inventory_ledger
                WHEN NEW.product_code='BK-P2' BEGIN SELECT RAISE(ABORT,'injected failure'); END""")
        r=self.post();self.assertEqual(r.status_code,409,r.get_json());self.assert_empty_draft()

    def test_non_bk_and_warehouse_lines_do_not_create_receipts(self):
        with server.db() as conn:
            conn.execute('UPDATE orders SET purchase_list=0 WHERE id=?',(self.order,))
            second=self.add_line(conn,'BK-P2')
            conn.execute("UPDATE orders SET supplier='KHO' WHERE id=?",(second,))
        self.assertEqual(self.preview()['rowCount'],0)
        self.assertEqual(self.post().status_code,200)
        with server.db() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM invoice_inventory_ledger').fetchone()[0],0)

    def test_existing_source_from_excel_blocks_duplicate_receipt(self):
        with server.db() as conn:
            p=approval.prepare(conn,self.batch)
            approval.bk._post_pending(conn,p['_pending'],NOW,None)
        # Exact same validated content can be attached, without another inventory event.
        r=self.post();self.assertEqual(r.status_code,200,r.get_json())
        self.assertEqual(r.get_json()['bk']['newInventoryLines'],0)

    def test_changed_posted_order_is_detected_even_if_mutation_guard_bypassed(self):
        self.assertEqual(self.post().status_code,200)
        with server.db() as conn:conn.execute('UPDATE orders SET actual_received=9 WHERE id=?',(self.order,))
        r=self.client.post(f'/api/batches/{self.batch}/approve',json={'confirm_bk':True})
        self.assertEqual(r.status_code,409)
        with server.db() as conn:self.assertEqual(conn.execute('SELECT sum(qty_delta) FROM invoice_inventory_ledger').fetchone()[0],2)

    def test_download_after_approval_cannot_double_import(self):
        self.assertEqual(self.post().status_code,200)
        payload=self.client.get(f'/api/bk-import/template?batch_id={self.batch}').data
        with server.db() as conn:
            p=approval.bk.parse_bk_preview(conn,payload)
            self.assertTrue(p['canConfirm']);self.assertTrue(p['alreadyPosted'])

    def test_selected_input_export_uses_posted_cost_without_writing_stock(self):
        self.assertEqual(self.post().status_code, 200)
        with server.db() as conn:
            before = conn.serialize()
            conn.execute("UPDATE settings SET value='0.8' WHERE key='purchase_rate'")
        with server.db() as conn:
            before = conn.serialize()
        for _ in range(2):
            response = self.client.post('/api/bk-import/export-approved', json={'batch_ids':[self.batch, self.batch]})
            self.assertEqual(response.status_code, 200, response.get_json(silent=True))
            wb = load_workbook(io.BytesIO(response.data), data_only=True)
            try:
                self.assertEqual(wb.active['A1'].value, 'BẢNG KÊ ĐẦU VÀO ĐÃ GHI NHẬP KHO')
                self.assertEqual(wb.active.max_row, 4)
                self.assertEqual([wb.active.cell(4,c).value for c in (8,9,10)], [2,190,380])
            finally:
                wb.close()
        with server.db() as conn:
            self.assertEqual(before, conn.serialize(), 'Download must not write stock or business data')

    def test_selected_input_export_blocks_unapproved_or_unposted(self):
        response = self.client.post('/api/bk-import/export-approved', json={'batch_ids':[self.batch]})
        self.assertEqual(response.status_code, 409)
        with server.db() as conn:
            conn.execute("UPDATE batches SET status='approved' WHERE id=?", (self.batch,))
        response = self.client.post('/api/bk-import/export-approved', json={'batch_ids':[self.batch]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['code'], 'bk_not_posted')

    def test_selected_input_export_multiple_days_in_one_file(self):
        self.assertEqual(self.post().status_code, 200)
        first = self.batch
        with server.db() as conn:
            self.batch = conn.execute("INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-09-02','second.xlsx','draft',?)", (NOW,)).lastrowid
            second_order = self.add_line(conn, qty=3)
            conn.execute("UPDATE orders SET work_date='2026-09-02' WHERE id=?", (second_order,))
        self.assertEqual(self.post().status_code, 200)
        response = self.client.post('/api/bk-import/export-approved', json={'batch_ids':[first, self.batch]})
        self.assertEqual(response.status_code, 200, response.get_json(silent=True))
        wb = load_workbook(io.BytesIO(response.data), data_only=True)
        try:
            self.assertEqual(wb.active.max_row, 5)
            self.assertEqual([wb.active.cell(r, 1).value.day for r in (4,5)], [2,3])
            self.assertEqual(sum(wb.active.cell(r, 10).value for r in (4,5)), 950)
        finally:
            wb.close()

    def test_selected_input_export_validates_selection(self):
        for ids in ([], [True], [1.5], ['1'], [-1], list(range(1,102))):
            self.assertEqual(self.client.post('/api/bk-import/export-approved', json={'batch_ids':ids}).status_code, 400)
        with server.db() as conn:
            conn.execute('UPDATE orders SET purchase_list=0 WHERE id=?', (self.order,))
        self.assertEqual(self.post().status_code, 200)
        response = self.client.post('/api/bk-import/export-approved', json={'batch_ids':[self.batch]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['code'], 'no_posted_bk')

    def test_reversal_reopens_batch_and_reapproval_posts_only_corrected_quantity(self):
        posted=self.post().get_json()['bk']
        r=self.client.post(f"/api/bk-import/documents/{posted['documentId']}/reversal",json={
            'confirmed':True,'reversalDate':'2026-09-03','reason':'Sửa lượng thực nhận'})
        self.assertEqual(r.status_code,200,r.get_json())
        with server.db() as conn:
            self.assertFalse(server.batch_mutation_blocker(conn,self.batch))
            self.assertEqual(conn.execute('SELECT status FROM batches WHERE id=?',(self.batch,)).fetchone()[0],'draft')
            conn.execute('UPDATE orders SET actual_received=3 WHERE id=?',(self.order,))
        r=self.post();self.assertEqual(r.status_code,200,r.get_json())
        with server.db() as conn:self.assertEqual(conn.execute('SELECT sum(qty_delta) FROM invoice_inventory_ledger').fetchone()[0],3)

    def test_canonical_purchase_quantity_wins_and_unconfirmed_line_blocks_all(self):
        with server.db() as conn:
            conn.execute('''INSERT INTO purchase_workbook_lines(batch_id,row_key,order_id,source_row,
                product_code,work_date,product_name,unit,supplier,actual_qty,status,created_at,updated_at)
                VALUES(?,?,?,31,'BK-P1','2026-09-03','Hàng BK','kg','BK-S1',1,'draft',?,?)''',
                (self.batch,'r1',self.order,NOW,NOW))
        self.assertFalse(self.preview()['canApprove']);self.assertEqual(self.post().status_code,409)
        self.assert_empty_draft()
        with server.db() as conn:conn.execute("UPDATE purchase_workbook_lines SET status='confirmed'")
        self.assertEqual(self.post().status_code,200)
        with server.db() as conn:self.assertEqual(conn.execute('SELECT sum(qty_delta) FROM invoice_inventory_ledger').fetchone()[0],1)

    def test_catalog_change_invalidates_confirmation(self):
        p=self.preview()
        with server.db() as conn:conn.execute("UPDATE people SET address='Địa chỉ mới'")
        r=self.client.post(f'/api/batches/{self.batch}/approve',json={'source_hash':p['sourceHash'],'confirm_bk':True})
        self.assertEqual(r.status_code,409);self.assert_empty_draft()

    def test_catalog_change_after_post_does_not_duplicate_or_reprice_receipt(self):
        self.assertEqual(self.post().status_code,200)
        with server.db() as conn:
            conn.execute("UPDATE settings SET value='0.90' WHERE key='purchase_rate'")
            conn.execute("UPDATE people SET address='Địa chỉ mới'")
        r=self.post();self.assertEqual(r.status_code,200,r.get_json())
        with server.db() as conn:
            self.assertEqual(tuple(conn.execute('SELECT count(*),sum(qty_delta),max(unit_cost) FROM invoice_inventory_ledger').fetchone()),(1,2,190))

    def test_invoice_same_day_requires_separate_purchase_confirmation(self):
        with server.db() as conn:
            iid=conn.execute('''INSERT INTO msmi_invoices(remote_id,invoice_type,invoice_series,invoice_number,
                invoice_date,raw_json,synced_at,created_at,updated_at) VALUES('overlap','purchase','AA','11','2026-09-03','{}',?,?,?)''', (NOW,NOW,NOW)).lastrowid
            cid=conn.execute('''INSERT INTO invoice_inventory_confirmations(confirmation_key,direction,source_invoice_table,
                source_invoice_id,action,confirmed,created_at) VALUES('invoice-test','input','msmi_invoices',?,'post',1,?)''',(iid,NOW)).lastrowid
            conn.execute('''INSERT INTO invoice_inventory_ledger(event_key,direction,event_type,source_invoice_table,
                source_invoice_id,source_line_id,source_line_index,product_code,txn_date,qty_delta,unit_cost,status,confirmation_id,created_at)
                VALUES('overlap','input','POST','msmi_invoices',?,1,1,'BK-P1','2026-09-03',5,100,'posted',?,?)''',(iid,cid,NOW))
        self.assertEqual(len(self.preview()['overlaps']),1)
        r=self.post();self.assertEqual(r.status_code,409,r.get_json())
        with server.db() as conn:self.assertEqual(conn.execute('SELECT sum(qty_delta) FROM invoice_inventory_ledger').fetchone()[0],5)
        r=self.post(confirm_separate_purchases=True);self.assertEqual(r.status_code,200,r.get_json())
        with server.db() as conn:self.assertEqual(conn.execute('SELECT sum(qty_delta) FROM invoice_inventory_ledger').fetchone()[0],7)

    def test_historical_bk_requires_separate_purchase_and_invalidates_old_preview(self):
        before = self.preview()
        with server.db() as conn:
            prepared = approval.prepare(conn, self.batch)
            rows = prepared['rows']
            for row in rows:
                row['source_reference'] = 'HISTORICAL-PURCHASE'
            parsed = approval.bk.parse_bk_preview(conn, approval.bk.build_bk_import_template(rows))
            pending = dict(prepared['_pending'], rows=parsed['rows'], content_hash=parsed['contentHash'],
                           database_state_hash=approval.bk._database_state_hash(conn, parsed['rows']))
            approval.bk._post_pending(conn, pending, NOW, None)
        # An independent import is not proof the order is an additional purchase.
        preview = self.preview()
        self.assertEqual(preview['overlaps'][0]['kind'], 'bk')
        self.assertNotEqual(before['sourceHash'], preview['sourceHash'])
        response = self.client.post(f'/api/batches/{self.batch}/approve', json={
            'source_hash': before['sourceHash'], 'confirm_bk': True,
            'confirm_separate_purchases': True})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.post().status_code, 409)
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT SUM(qty_delta) FROM invoice_inventory_ledger').fetchone()[0], 2)
            self.assertEqual(conn.execute('SELECT status FROM batches WHERE id=?', (self.batch,)).fetchone()[0], 'draft')

    def test_purchase_workbook_import_cannot_replace_posted_bk_source(self):
        from .contract_modules import apply_purchase_order_preview, PurchaseOrderApplyError
        self.assertEqual(self.post().status_code,200)
        with server.db() as conn:
            with self.assertRaises(PurchaseOrderApplyError):
                apply_purchase_order_preview(conn,batch_id=self.batch,items=[],source_hash='other',source_name='new.xlsx',format_name='test',now_iso=server.now_iso)

    def test_two_simultaneous_approvals_create_only_one_receipt(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        p=self.preview();barrier=Barrier(2)
        def run():
            with server.app.test_client() as client:
                barrier.wait()
                r=client.post(f'/api/batches/{self.batch}/approve',json={'source_hash':p['sourceHash'],'confirm_bk':True})
                return r.status_code,r.get_json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:run(),range(2)))
        self.assertEqual([r[0] for r in results],[200,200])
        self.assertEqual(sum(r[1]['bk']['newInventoryLines'] for r in results),1)
        with server.db() as conn:self.assertEqual(conn.execute('SELECT SUM(qty_delta) FROM invoice_inventory_ledger').fetchone()[0],2)

    def test_returns_cannot_exceed_received_quantity(self):
        with server.db() as conn:conn.execute('UPDATE orders SET supplier_return_qty=3 WHERE id=?',(self.order,))
        self.assertFalse(self.preview()['canApprove']);self.assertEqual(self.post().status_code,409)
        self.assert_empty_draft()


if __name__ == '__main__': unittest.main()
