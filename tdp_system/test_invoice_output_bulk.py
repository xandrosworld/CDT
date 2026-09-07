import unittest
from contextlib import contextmanager
from datetime import date

from flask import Flask
from . import test_invoice_inventory as fixture
now_iso = fixture.now_iso
from .invoice_output_bulk import preview_outputs, post_outputs, output_review, InvoiceInventoryError
from .invoice_inventory import invoice_stock_rows
from .invoice_workbench import register_invoice_workbench_routes
from .invoice_workbench_listing import invoice_range_payload
from .inventory_period_close import init_inventory_period_close_schema, inventory_period_close_preview, close_inventory_period
from .invoice_valuation import moving_average_report


class OutputGroupTests(unittest.TestCase):
    setUp = fixture.InvoiceInventoryLedgerTests.setUp
    tearDown = fixture.InvoiceInventoryLedgerTests.tearDown
    _input = fixture.InvoiceInventoryLedgerTests._input
    _output = fixture.InvoiceInventoryLedgerTests._output

    def preview(self, ids):
        self.conn.commit()
        return preview_outputs(self.conn, ids, 'TDP', now_iso)

    def post(self, items, confirmed=True):
        return post_outputs(self.conn, items, 'TDP', now_iso, confirmed=confirmed)

    def test_preview_consumes_shared_stock_only_on_copy_and_retry_is_idempotent(self):
        a = self._output(3, 7)[0]
        b = self._output(4, 7)[0]
        before = list(self.conn.iterdump())
        preview = self.preview([b, a])
        self.assertEqual([a], [r['id'] for r in preview['items']])
        self.assertEqual(b, preview['blocked'][0]['id'])
        self.assertIn('thiếu 4', preview['blocked'][0]['reason'])
        self.assertEqual(before, list(self.conn.iterdump()))
        self.assertEqual(1, self.post(preview['items'])['posted_count'])
        self.assertEqual(1, self.post(preview['items'])['already_posted_count'])
        self.assertEqual(3, invoice_stock_rows(self.conn, '2026-08-31')[0]['closing_qty'])

    def test_changed_invoice_rejects_entire_group(self):
        ids = [self._output(i, 3)[0] for i in (3,4)]
        rows = self.preview(ids)['items']
        self.conn.execute('UPDATE outgoing_source_invoice_items SET amount=999 WHERE invoice_id=?', (ids[-1],))
        with self.assertRaises(InvoiceInventoryError) as caught: self.post(rows)
        self.assertEqual('stale_review', caught.exception.code)
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])

    def test_stock_changed_after_preview_rolls_back_first_invoice_as_well(self):
        ids = [self._output(i, 4)[0] for i in (3,4)]
        rows = self.preview(ids)['items']
        self.conn.execute("UPDATE inventory_transactions SET qty_in=6 WHERE source_type='OPENING'")
        with self.assertRaises(InvoiceInventoryError) as caught: self.post(rows)
        self.assertEqual('negative_stock', caught.exception.code)
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_confirmations').fetchone()[0])

    def test_explicit_confirmation_and_valid_selection_required(self):
        rows = self.preview([self._output()[0]])['items']
        for invalid in (None, [], [1], [{'id':True,'token':'x'}], rows * 2):
            with self.assertRaises(InvoiceInventoryError): self.post(invalid)
        with self.assertRaises(InvoiceInventoryError): self.post(rows, False)
        with self.assertRaises(InvoiceInventoryError): output_review(self.conn, rows[0]['id'], 'OTHER')
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])

    def test_future_receipts_and_newer_opening_do_not_fund_old_output(self):
        self._input(qty=10)
        self.conn.execute("UPDATE invoice_inventory_ledger SET txn_date='2026-08-31'")
        self.conn.execute("UPDATE inventory_transactions SET qty_in=0")
        invoice_id = self._output()[0]
        self.conn.execute("UPDATE outgoing_source_invoices SET invoice_date='2026-08-20'")
        self.assertFalse(self.preview([invoice_id])['items'])
        self.conn.execute("UPDATE inventory_transactions SET txn_date='2026-09-01',source_id='2026-09',qty_in=20")
        self.assertIn('tồn đầu', self.preview([invoice_id])['blocked'][0]['reason'])

    def test_pending_output_keeps_previous_days_excludes_posted(self):
        a, b = [self._output(i, 2)[0] for i in (3,4)]
        self.post(self.preview([a])['items'])
        payload = invoice_range_payload(self.conn, tenant='TDP', invoice_type='output', date_from='2026-09-01', date_to='2026-09-02', scope='pending')
        self.assertEqual([b], [r['id'] for r in payload['items']])

    def test_input_output_report_carry_forward_and_repeat(self):
        self._input(qty=5)
        invoice_id = self._output(qty=4)[0]
        self.post(self.preview([invoice_id])['items'])
        init_inventory_period_close_schema(self.conn)
        preview = inventory_period_close_preview(self.conn, '2026-08', today=date(2026,9,8))
        self.assertTrue(preview['can_close'], preview['issues'])
        self.assertEqual(11, preview['total_qty'])
        args = dict(expected_source_hash=preview['source_hash'], expected_target_hash=preview['target_hash'], timestamp=now_iso(), today=date(2026,9,8), actor='QA')
        close_inventory_period(self.conn, '2026-08', **args)
        report = moving_average_report(self.conn, date_from='2026-09-01', date_to='2026-09-30')
        self.assertEqual(11, report['items'][0]['opening_qty'])
        self.assertEqual(1100, report['items'][0]['opening_value'])
        refreshed = inventory_period_close_preview(self.conn, '2026-08', today=date(2026,9,8))
        args['expected_target_hash'] = refreshed['target_hash']
        self.assertTrue(close_inventory_period(self.conn, '2026-08', **args)['idempotent'])

    def test_api_get_read_only_and_post_rejects_missing_confirmation(self):
        self._output()
        self.conn.commit()
        @contextmanager
        def db():
            try: yield self.conn; self.conn.commit()
            except Exception: self.conn.rollback(); raise
        app=Flask(__name__)
        register_invoice_workbench_routes(app, {'db':db,'now_iso':now_iso,'setting_get':lambda c,k,d:d})
        client=app.test_client()
        before=list(self.conn.iterdump())
        result=client.get('/api/invoice-workbench/output-postings?from=2026-08-01&to=2026-08-31')
        self.assertEqual(200,result.status_code,result.json)
        self.assertEqual(before,list(self.conn.iterdump()))
        rows=result.json['items']
        self.assertEqual(400,client.post('/api/invoice-workbench/output-postings',json={'items':rows}).status_code)
        self.assertEqual(200,client.post('/api/invoice-workbench/output-postings',json={'items':rows,'confirmed':True}).status_code)


if __name__ == '__main__': unittest.main()
