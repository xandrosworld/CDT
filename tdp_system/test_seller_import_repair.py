import unittest

from . import server, batch_bk_approval as approval
from .seller_import_repair import repair_order_sellers, row_hash
from .test_batch_bk_approval import BatchBKApprovalTests
from .test_bk_import import NOW


class SellerImportRepairTests(unittest.TestCase):
    setUpClass = classmethod(BatchBKApprovalTests.setUpClass.__func__)
    tearDownClass = classmethod(BatchBKApprovalTests.tearDownClass.__func__)
    add_line = BatchBKApprovalTests.add_line

    def setUp(self):
        BatchBKApprovalTests.setUp(self)
        with server.db() as conn:
            conn.execute("INSERT INTO people(name,cccd,address) VALUES('Workbook seller','987654321','Verified address')")
            conn.execute("UPDATE orders SET seller='Người bán BK',cccd='987654321' WHERE id=?", (self.order,))
        # Recreate a historical, already-posted approval. New order approvals
        # deliberately no longer post a purchase schedule.
        with server.db() as conn:
            p = approval.prepare(conn, self.batch)
            approval.approve(conn, self.batch, {
                'source_hash': p['sourceHash'], 'confirm_bk': True}, NOW, server.audit_event)
        r = self.client.post(f'/api/batches/{self.batch}/approve', json={})
        self.assertEqual(r.status_code, 200, r.get_json())

    def item(self, conn):
        row = conn.execute('SELECT * FROM orders WHERE id=?', (self.order,)).fetchone()
        return {'id': self.order, 'seller': 'Workbook seller', 'source_cccd': row['cccd'],
                'file_hash': 'A' * 64, 'source_row': 27, 'expected_row_hash': row_hash(row)}

    def test_posted_correction_preserves_money_stock_and_approval(self):
        with server.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old = dict(conn.execute('SELECT * FROM orders WHERE id=?', (self.order,)).fetchone())
            stock = [tuple(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger')]
            doc = [tuple(r) for r in conn.execute('SELECT * FROM bk_import_documents')]
            result = repair_order_sellers(conn, [self.item(conn)], '2026-09-16 18:00:00', server.audit_event)
            new = dict(conn.execute('SELECT * FROM orders WHERE id=?', (self.order,)).fetchone())
            self.assertEqual({k for k in old if old[k] != new[k]}, {'seller', 'updated_at'})
            self.assertEqual(stock, [tuple(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger')])
            self.assertEqual(doc, [tuple(r) for r in conn.execute('SELECT * FROM bk_import_documents')])
            self.assertTrue(approval.prepare(conn, self.batch)['alreadyPosted'])
            self.assertEqual(conn.execute('SELECT status FROM batches WHERE id=?', (self.batch,)).fetchone()[0], 'approved')
            self.assertEqual(result['corrected_orders'], 1)

    def test_stale_financial_edit_cannot_be_hidden_by_seller_repair(self):
        with server.db() as conn:
            item = self.item(conn)
            conn.execute('UPDATE orders SET buy_price=999 WHERE id=?', (self.order,))
            with self.assertRaisesRegex(ValueError, 'changed since'):
                repair_order_sellers(conn, [item], 'now', server.audit_event)

    def test_does_not_replace_explicit_seller_or_change_exclusion(self):
        with server.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            item = self.item(conn)
            item['seller'] = 'Nguyễn Văn Toại'
            with self.assertRaisesRegex(ValueError, 'exclusion'):
                repair_order_sellers(conn, [item], 'now', server.audit_event)
            conn.execute("UPDATE orders SET seller='Explicit override' WHERE id=?", (self.order,))
            with self.assertRaisesRegex(ValueError, 'override'):
                repair_order_sellers(conn, [self.item(conn)], 'now', server.audit_event)

    def test_reference_cell_must_match_and_new_person_must_exist(self):
        with server.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            item = self.item(conn)
            item['source_cccd'] = '111111111'
            with self.assertRaisesRegex(ValueError, 'identity does not match'):
                repair_order_sellers(conn, [item], 'now', server.audit_event)
            item = self.item(conn)
            item['seller'] = 'Unknown'
            with self.assertRaisesRegex(ValueError, 'incomplete or ambiguous'):
                repair_order_sellers(conn, [item], 'now', server.audit_event)

    def test_failure_rolls_back_seller_and_approval_link_together(self):
        with server.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            item = self.item(conn)
            old_hash = approval.prepare(conn, self.batch)['_source_state_hash']
            def fail(*args, **kwargs):
                raise RuntimeError('forced audit failure')
            with self.assertRaisesRegex(RuntimeError, 'forced'):
                repair_order_sellers(conn, [item], 'now', fail)
            self.assertEqual(row_hash(conn.execute('SELECT * FROM orders WHERE id=?', (self.order,)).fetchone()), item['expected_row_hash'])
            self.assertEqual(approval.prepare(conn, self.batch)['_source_state_hash'], old_hash)
