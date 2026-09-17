import json
import unittest
from unittest.mock import patch

from . import server
from . import outgoing_amount_settlement as money
from .test_outgoing_readiness import OutgoingReadinessTests as Fixture
from .outgoing_unissued import unissued_payload, issued_allocations
from .outgoing_contractors import selected_orders
from .outgoing_readiness import validate_demand_orders, OutgoingReadinessError


class AmountSettlementTests(unittest.TestCase):
    setUpClass = classmethod(Fixture.setUpClass.__func__)
    tearDownClass = classmethod(Fixture.tearDownClass.__func__)

    def setUp(self):
        with server.db() as c:
            c.execute('DELETE FROM outgoing_amount_settlements')
        Fixture.setUp(self)
        with server.db() as c:
            self.batch, self.orders = Fixture.add_batch(c, '2026-09-01', [{'qty': 10}])
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Test','0101234567','Test',?)", (server.now_iso(),))
            self.invoice = Fixture.add_posted_source(c, source='minvoice', qty=3, invoice_date='2026-09-16', number='900')
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567',subtotal=200,total_amount=200 WHERE id=?", (self.invoice,))
        self.body = {'contractor': 'NT-A', 'from': '2026-09-01', 'to': '2026-09-15',
                     'invoice_ids': [self.invoice], 'actor': 'QA', 'reason': 'Đã xác nhận kỳ đơn theo tiền', 'confirmed': True}

    def settle(self, c):
        report = money.preview(c, self.body)
        self.assertTrue(report['can_confirm'], report)
        return money.confirm(c, {**self.body, 'token': report['token']}, server.now_iso())

    def test_full_money_closes_period_without_fabricating_quantities_or_changing_business_rows(self):
        with server.db() as c:
            before = {t: [tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in ('orders', 'batches', 'inventory_transactions', 'invoice_inventory_ledger', 'receivable_ledger_lines', 'payable_ledger_lines')}
            self.assertEqual(7, unissued_payload(c, '2026-09-15', 'NT-A')['rows'][0]['unissued_qty'])
            self.settle(c)
            self.assertEqual({}, issued_allocations(c)[0])  # No invented 10 kg issued allocation.
            report = unissued_payload(c, '2026-09-15', 'NT-A')
            self.assertEqual([], report['details'])
            self.assertEqual(200, report['amount_settlements'][0]['amount'])
            self.assertFalse(report['amount_settlements'][0]['needs_review'])
            self.assertEqual([], selected_orders(c, [dict(r) for r in c.execute('SELECT * FROM orders')]))
            with self.assertRaises(OutgoingReadinessError):
                validate_demand_orders(c, [dict(r) for r in c.execute('SELECT * FROM orders')])
            for table, rows in before.items():
                self.assertEqual(rows, [tuple(r) for r in c.execute('SELECT * FROM '+table)], table)

    def test_one_dong_difference_and_unsigned_invoice_never_close(self):
        with server.db() as c:
            for amount in (199, 201):
                c.execute('UPDATE outgoing_source_invoices SET total_amount=? WHERE id=?', (amount, self.invoice))
                r = money.preview(c, self.body)
                self.assertFalse(r['can_confirm'])
                with self.assertRaises(ValueError):
                    money.confirm(c, {**self.body, 'token': r['token']}, server.now_iso())
            c.execute("UPDATE outgoing_source_invoices SET source_status_class='draft' WHERE id=?", (self.invoice,))
            with self.assertRaises(ValueError): money.preview(c, self.body)
            self.assertFalse(money.records(c))

    def test_same_invoice_cannot_cover_two_periods_and_does_not_fifo_into_new_orders(self):
        with server.db() as c:
            self.settle(c)
            _, ids = Fixture.add_batch(c, '2026-09-16', [{'qty': 10}])
            self.assertNotIn(ids[0], issued_allocations(c)[0])
            r = money.preview(c, {**self.body, 'from': '2026-09-16', 'to': '2026-09-16'})
            self.assertFalse(r['can_confirm']); self.assertTrue(r['conflicts'])

    def test_source_cancel_or_price_change_reopens_review_and_blocks_next_issue(self):
        with server.db() as c:
            self.settle(c)
            c.execute('UPDATE orders SET sell_price=21 WHERE id=?', (self.orders[0],))
            orders, invoices, warnings = money.coverage(c)
            self.assertFalse(orders); self.assertFalse(invoices); self.assertTrue(warnings)
            self.assertTrue(money.history(c)[0]['needs_review'])
            with self.assertRaises(OutgoingReadinessError): validate_demand_orders(c, [dict(r) for r in c.execute('SELECT * FROM orders')])
            c.execute('UPDATE orders SET sell_price=20 WHERE id=?', (self.orders[0],))
            self.assertTrue(money.coverage(c)[0])
            c.execute("UPDATE outgoing_source_invoices SET source_status_class='cancelled' WHERE id=?", (self.invoice,))
            self.assertTrue(money.coverage(c)[2])
            self.assertTrue(unissued_payload(c, '2026-09-15', 'NT-A')['warnings'])

    def test_stale_preview_retry_and_revoke_keep_audit(self):
        with server.db() as c:
            report = money.preview(c, self.body)
            c.execute("UPDATE outgoing_source_invoices SET raw_json='{"+'"changed":true'+"}' WHERE id=?", (self.invoice,))
            with self.assertRaisesRegex(ValueError, 'vừa thay đổi'):
                money.confirm(c, {**self.body, 'token': report['token']}, server.now_iso())
            r = self.settle(c)
            self.assertTrue(money.confirm(c, self.body, server.now_iso())['unchanged'])
            self.assertEqual(1, len(money.records(c)))
            money.revoke(c, r['id'], {'actor': 'QA', 'reason': 'Đối chiếu lại'}, server.now_iso())
            self.assertFalse(money.coverage(c)[0])
            self.assertEqual(7, unissued_payload(c, '2026-09-15', 'NT-A')['rows'][0]['unissued_qty'])
            self.assertEqual(1, c.execute('SELECT COUNT(*) FROM outgoing_amount_settlements').fetchone()[0])

    def test_cross_period_quantity_allocation_must_be_reviewed(self):
        with server.db() as c:
            Fixture.add_batch(c, '2026-08-31', [{'qty': 1}])
            r = money.preview(c, self.body)
            self.assertFalse(r['can_confirm'])
            self.assertTrue(any('ngoài kỳ' in w for w in r['conflicts']))

    def test_new_order_in_closed_period_invalidates_completion(self):
        with server.db() as c:
            self.settle(c)
            Fixture.add_batch(c, '2026-09-02', [{'qty': 1}])
            self.assertTrue(money.coverage(c)[2])

    def test_protected_remote_draft_blocks_confirmation(self):
        with server.db() as c:
            did = Fixture.add_local_issued_draft(c, self.batch, self.orders[0], number='901', qty=2, invoice_date='2026-09-16')
            c.execute("UPDATE outgoing_invoice_drafts SET status='draft',minvoice_status='unknown' WHERE id=?", (did,))
            r = money.preview(c, self.body)
            self.assertFalse(r['can_confirm'])
            self.assertTrue(any('chưa rõ kết quả' in w for w in r['conflicts']))

    def test_editable_draft_released_and_never_recreated_for_closed_orders(self):
        with server.db() as c:
            Fixture.add_opening(c, 20)
            did = Fixture.add_local_issued_draft(c, self.batch, self.orders[0], number='901', qty=2, invoice_date='2026-09-16')
            c.execute("UPDATE outgoing_invoice_drafts SET status='draft',minvoice_status='not_sent' WHERE id=?", (did,))
            self.settle(c)
            self.assertEqual('cancelled', c.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?', (did,)).fetchone()[0])
            from .outgoing_waiting import refresh_waiting
            self.assertFalse(refresh_waiting(c, server.now_iso())['created'])

    def test_wrong_buyer_duplicate_selection_and_local_invoice_not_selected_rejected(self):
        with server.db() as c:
            for body in ({**self.body, 'contractor': 'NT-B'}, {**self.body, 'invoice_ids': [self.invoice, self.invoice]}):
                with self.assertRaises(ValueError): money.preview(c, body)
            Fixture.add_local_issued_draft(c, self.batch, self.orders[0], number='901', qty=1, invoice_date='2026-09-16')
            self.assertFalse(money.preview(c, self.body)['can_confirm'])

    def test_api_confirm_requires_fresh_source_and_failure_does_not_close(self):
        body = {**self.body, 'action': 'confirm'}
        with server.db() as c: body['token'] = money.preview(c, body)['token']
        with patch('tdp_system.outgoing_source_refresh.refresh_sources', side_effect=ValueError('Nguồn chưa đầy đủ')):
            response = self.client.post('/api/outgoing-invoices/amount-settlement', json=body)
        self.assertEqual(409, response.status_code)
        with server.db() as c: self.assertFalse(money.records(c))
        with patch('tdp_system.outgoing_source_refresh.refresh_sources', return_value={}):
            response = self.client.post('/api/outgoing-invoices/amount-settlement', json=body)
        self.assertEqual(200, response.status_code, response.json)

    def test_receivable_rounding_with_returns_and_tax_matches_to_the_dong(self):
        from .receivable_ledger import discover_receivable_sources
        with server.db() as c:
            c.execute("UPDATE orders SET actual_delivered=3.3,customer_return_qty=0.2,sell_price=25005,tax='8%' WHERE id=?", (self.orders[0],))
            projected = money.order_snapshot(c, 'NT-A', '2026-09-01', '2026-09-15')
            ledger = [r for r in discover_receivable_sources(c) if r['source_id'] == self.orders[0]][0]
            self.assertEqual(ledger['amount'], projected[0]['amount'])
            self.assertEqual(ledger['tax_amount'], projected[0]['tax_amount'])

    def test_different_product_can_settle_money_without_remapping_stock(self):
        with server.db() as c:
            c.execute("INSERT OR REPLACE INTO products(code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd) VALUES('HH-02','Khác','kg','0%','NCC-A',10,0,'','')")
            c.execute("UPDATE invoice_inventory_ledger SET product_code='HH-02' WHERE source_invoice_id=? AND source_invoice_table='outgoing_source_invoices'", (self.invoice,))
            before = [tuple(r) for r in c.execute('SELECT * FROM invoice_inventory_ledger')]
            self.settle(c)
            self.assertFalse(unissued_payload(c, '2026-09-15', 'NT-A')['details'])
            self.assertEqual(before, [tuple(r) for r in c.execute('SELECT * FROM invoice_inventory_ledger')])

    def test_held_signed_invoice_is_visible_but_cannot_be_selected_for_money(self):
        with server.db() as c:
            c.execute("UPDATE outgoing_source_invoices SET sync_status='review_required' WHERE id=?", (self.invoice,))
        response = self.client.get('/api/outgoing-invoices/amount-settlement?contractor=NT-A&from=2026-09-01&to=2026-09-15')
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json['invoices'])
        self.assertEqual(self.invoice, response.json['unavailable_invoices'][0]['id'])

    def test_export_retains_settlement_evidence_with_no_invoiceable_quantity(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from .outgoing_unissued import unissued_workbook
        with server.db() as c:
            self.settle(c)
            before = c.serialize()
            payload = unissued_payload(c, '2026-09-15', 'NT-A')
            book = load_workbook(unissued_workbook(payload), data_only=True)
            self.assertEqual(200, book['Da doi tru theo tien']['E2'].value)
            book.close()
            self.assertEqual(before, c.serialize())


if __name__ == '__main__': unittest.main()
