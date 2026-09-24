"""Regression for decoupling order approval from invoice-stock receipts."""
import unittest
from . import server, batch_bk_approval as approval
from . import test_batch_bk_approval as fixture


class OrderApprovalWithoutBKTests(unittest.TestCase):
    setUpClass=classmethod(fixture.BatchBKApprovalTests.setUpClass.__func__)
    tearDownClass=classmethod(fixture.BatchBKApprovalTests.tearDownClass.__func__)
    setUp=fixture.BatchBKApprovalTests.setUp
    add_line=fixture.BatchBKApprovalTests.add_line

    def stock(self):
        with server.db() as c:
            return {t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in
                    ('invoice_inventory_ledger','bk_import_documents','bk_import_lines','batch_bk_approvals')}

    def test_preview_and_approval_do_not_create_stock_even_for_old_browser(self):
        before=self.stock()
        p=self.client.get(f'/api/batches/{self.batch}/approval-preview').json
        self.assertEqual(p['inventoryMode'],'separate_supplement')
        self.assertFalse(p['writesInventory']);self.assertEqual(p['rowCount'],0)
        for body in ({}, {'confirm_bk':True,'source_hash':'old-browser','confirm_separate_purchases':True}):
            r=self.client.post(f'/api/batches/{self.batch}/approve',json=body)
            self.assertEqual(r.status_code,200,r.json)
            self.assertEqual(r.json['bk']['newInventoryLines'],0)
            self.assertEqual(before,self.stock())

    def test_missing_seller_no_longer_forces_bk_before_export_selection(self):
        with server.db() as c:c.execute('DELETE FROM people')
        before=self.stock()
        r=self.client.post(f'/api/batches/{self.batch}/approve',json={})
        self.assertEqual(r.status_code,200,r.json);self.assertEqual(before,self.stock())

    def test_order_errors_still_block(self):
        with server.db() as c:c.execute("UPDATE orders SET errors='[\"Thiếu mã hàng\"]' WHERE id=?",(self.order,))
        self.assertEqual(self.client.post(f'/api/batches/{self.batch}/approve',json={}).status_code,400)

    def test_approval_still_updates_purchase_sheet_payable(self):
        with server.db() as c:
            c.execute('''INSERT INTO purchase_workbook_lines(batch_id,row_key,order_id,
                source_row,product_code,work_date,product_name,unit,supplier,
                actual_qty,buy_price,amount,status,created_at,updated_at)
                VALUES(?, 'purchase', ?, 42, 'BK-P1', '2026-09-03', 'Hàng BK',
                'kg', 'BK-S1', 2, 111, 222, 'confirmed', 'now', 'now')''', (self.batch,self.order))
        before=self.stock()
        r=self.client.post(f'/api/batches/{self.batch}/approve',json={})
        self.assertEqual(r.status_code,200,r.json)
        with server.db() as c:
            amount=c.execute("SELECT SUM(amount) FROM payable_ledger_lines WHERE status!='reversed' AND batch_id=?", (self.batch,)).fetchone()[0]
        self.assertEqual(amount,222)
        self.assertEqual(before,self.stock())

    def test_historical_posted_document_preserved(self):
        with server.db() as c:
            p=approval.prepare(c,self.batch)
            approval.approve(c,self.batch,{'source_hash':p['sourceHash'],'confirm_bk':True},server.now_iso(),server.audit_event)
        before=self.stock()
        r=self.client.post(f'/api/batches/{self.batch}/approve',json={})
        self.assertEqual(r.status_code,200,r.json);self.assertEqual(before,self.stock())
        with server.db() as c:self.assertTrue(approval.mutation_blocker(c,self.batch))
        with server.db() as c:
            c.execute('UPDATE orders SET actual_received=9 WHERE id=?', (self.order,))
        r=self.client.post(f'/api/batches/{self.batch}/approve',json={})
        self.assertEqual(r.status_code,409,r.json)
        self.assertEqual(before,self.stock())
