import unittest
from unittest.mock import patch

from . import server, test_output_stock_remap as fixtures
from .output_stock_hold_release import preview, confirm
from .output_stock_remap import RemapError
from .outgoing_consolidation import _write_draft, decimal
from .contract_modules import invoice_tax_percent


class HoldReleaseTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.OutputStockRemapTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.OutputStockRemapTests.tearDownClass.__func__)
    setUp = fixtures.OutputStockRemapTests.setUp

    def seed(self, conn, single=False):
        batch, ids = fixtures.Seed.add_batch(conn, '2026-08-20', [
            {'product_code':'REMAP-B', 'qty':224.8, 'sell_price':21000},
            *([] if single else [{'product_code':'HH-01', 'qty':7.3, 'sell_price':31001}])])
        rows = [dict(r) for r in conn.execute('SELECT * FROM orders WHERE batch_id=?', (batch,))]
        rows = [{**r, 'order_id':r['id'], '_source_price':decimal(r['sell_price'])} for r in rows]
        return _write_draft(conn, 'NT-A', rows, {batch}, invoice_tax_percent, server.now_iso(), floor_kg=False, kind='invoice_upload')

    def submit(self, conn, plan):
        return confirm(conn, dict(token=plan['token'], actor='Kiểm thử', confirmed=True), server.now_iso())

    def test_partial_release_preserves_evidence_other_lines_orders_and_stock(self):
        with server.db() as conn:
            did = self.seed(conn)
            tables = ['orders', 'batches', 'invoice_inventory_ledger', 'outgoing_source_invoice_items', 'outgoing_invoice_lines', 'outgoing_line_allocations']
            before = {t:[tuple(r) for r in conn.execute('SELECT * FROM '+t)] for t in tables}
            plan = preview(conn, did, 'REMAP-B')
            self.assertEqual(224.8, plan['removed'][0]['qty'])
            self.assertEqual(1, len(plan['kept']))
            self.assertEqual('draft', conn.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?', (did,)).fetchone()[0])
            result = self.submit(conn, plan)
            new_id = result['replacement_draft_id']
            line = dict(conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=?', (new_id,)).fetchone())
            self.assertEqual({k:v for k,v in plan['kept'][0].items() if k not in ('id','draft_id')}, {k:v for k,v in line.items() if k not in ('id','draft_id')})
            self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND product_code='REMAP-B' AND status='reserved'").fetchone()[0])
            self.assertEqual(7.3, conn.execute("SELECT SUM(qty_out) FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND status='reserved'").fetchone()[0])
            for t in tables:
                after = [tuple(r) for r in conn.execute('SELECT * FROM '+t)]
                self.assertEqual(before[t], after[:len(before[t])], t)
                if t not in ('outgoing_invoice_lines','outgoing_line_allocations'):
                    self.assertEqual(before[t], after, t)
            self.assertTrue(self.submit(conn, plan)['idempotent'])
            self.assertEqual(2, conn.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0])

    def test_stale_allocations_or_remote_status_block_confirmation(self):
        with server.db() as conn:
            did = self.seed(conn)
            plan = preview(conn, did, 'REMAP-B')
            conn.execute('UPDATE outgoing_line_allocations SET amount=amount+1')
            with self.assertRaisesRegex(RemapError, 'vừa thay đổi'):
                self.submit(conn, plan)
            for status in ('saved', 'saving', 'unknown', 'error'):
                conn.execute('UPDATE outgoing_invoice_drafts SET minvoice_status=? WHERE id=?', (status, did))
                with self.assertRaisesRegex(RemapError, 'M-Invoice'):
                    self.submit(conn, plan)
            self.assertEqual('draft', conn.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?', (did,)).fetchone()[0])

    def test_single_line_release_cancels_without_empty_replacement(self):
        with server.db() as conn:
            did = self.seed(conn, single=True)
            plan = preview(conn, did, 'REMAP-B')
            result = self.submit(conn, plan)
            self.assertIsNone(result['replacement_draft_id'])
            self.assertEqual('cancelled', conn.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?', (did,)).fetchone()[0])
            self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM outgoing_invoice_lines').fetchone()[0])

    def test_routes_require_consent_and_transaction_rolls_back_failure(self):
        with server.db() as conn:
            did = self.seed(conn)
        route = '/api/inventory/output-remap/release-product/'
        response = self.client.post(route+'preview', json={'draft_id':did,'product_code':'REMAP-B'})
        self.assertEqual(200, response.status_code, response.json)
        token = response.json['token']
        for body in ({'token':token}, {'token':token,'confirmed':True}, {'token':token,'actor':'A','confirmed':'true'}):
            self.assertEqual(409, self.client.post(route+'confirm', json=body).status_code)
        with patch('tdp_system.output_stock_hold_release._recompute_draft_totals', side_effect=ValueError('injected failure')):
            self.assertEqual(409, self.client.post(route+'confirm', json={'token':token,'actor':'A','confirmed':True}).status_code)
        with server.db() as conn:
            self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0])
            self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM inventory_transactions WHERE status='reserved'").fetchone()[0])
        response = self.client.post(route+'confirm', json={'token':token,'actor':'A','confirmed':True})
        self.assertEqual(200, response.status_code, response.json)

    def test_mismatched_reservation_blocks_without_mutation(self):
        with server.db() as conn:
            did = self.seed(conn)
            conn.execute("UPDATE inventory_transactions SET qty_out=qty_out+1 WHERE source_type='OUTGOING_DRAFT'")
            with self.assertRaisesRegex(RemapError, 'chưa khớp'):
                preview(conn, did, 'REMAP-B')
            self.assertEqual(1, conn.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0])

    def test_export_matching_signed_invoice_blocks_even_with_local_not_sent(self):
        from .outgoing_export_receipts import create
        with server.db() as conn:
            did = self.seed(conn)
            conn.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,address,tax_code,updated_at) VALUES('NT-A','Test','0101234567',?)", (server.now_iso(),))
            receipt = create(conn, [did], b'test', 'test.zip', '2026-08-20 00:00:00')
            conn.execute("UPDATE outgoing_export_receipts SET received_at='2026-08-20 00:00:00' WHERE token=?", (receipt,))
            plan = preview(conn, did, 'REMAP-B')
            invoice = fixtures.Seed.add_posted_source(conn, source='minvoice', number='SIGNED-EXPORTED')
            draft = conn.execute('SELECT * FROM outgoing_invoice_drafts WHERE id=?', (did,)).fetchone()
            conn.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567',subtotal=?,total_amount=?,created_at='2026-08-21 00:00:00' WHERE id=?", (draft['subtotal'], draft['total_amount'], invoice))
            for index, line in enumerate(conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=?', (did,)), 1):
                conn.execute('''INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,source_item_name,source_unit,qty,unit_price,amount,tax_rate,source_nature)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''', (invoice,index,line['product_code'],line['product_name'],line['unit'],line['qty'],line['unit_price'],line['amount'],line['tax'],line['invoice_nature']))
            with self.assertRaisesRegex(RemapError, 'đã khớp hóa đơn phát hành'):
                self.submit(conn, plan)
            self.assertEqual('draft', conn.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?', (did,)).fetchone()[0])
