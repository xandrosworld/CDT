import copy
import json
import sqlite3
import unittest
from contextlib import contextmanager
from datetime import date

from flask import Flask
from .test_invoice_input_sync import init_test_database, now_iso
from .test_minvoice_portal import document
from .minvoice_portal import normalize_portal_document
from .invoice_output_sync import upsert_output_invoice
from .invoice_mapping import apply_saved_mappings
from .invoice_output_mapping import match_output_catalog_codes
from .invoice_output_bulk import preview_outputs, post_outputs, output_review
from .invoice_inventory import post_output_invoice, reverse_output_invoice, InvoiceInventoryError
from .invoice_valuation import moving_average_report
from .invoice_workbench import register_invoice_workbench_routes
from .invoice_workbench_listing import invoice_range_payload
from .inventory_period_close import init_inventory_period_close_schema, inventory_period_close_preview


class SourceQuantityPostingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        init_test_database(self.conn)
        self.conn.execute("INSERT INTO products(code,name,unit) VALUES('A','Goods','Chai')")
        self.counter = 0

    def tearDown(self):
        self.conn.close()

    def new(self, qty=2, mismatch=False, **changes):
        self.counter += 1
        raw = document()
        raw.update(id='quantity-post-' + str(self.counter), invoiceNumber=900+self.counter,
                   invoiceDate='2026-08-20T00:00:00', totalAmountWithoutVAT=qty*1000,
                   vatAmount=qty*80, totalAmount=qty*1080)
        raw['invoiceDetail'][0].update(quantity=qty, unitPrice=1000, amount=qty*1000,
                                      amountWithoutVAT=qty*1000, vatAmount=qty*80, unitCode='xách')
        if mismatch:
            raw.update(totalAmountWithoutVAT=qty*1000+120000, totalAmount=qty*1080+120000)
        raw.update(changes)
        iid = upsert_output_invoice(self.conn, normalize_portal_document(raw), tenant='TDP',
                                    now=now_iso(), status_map={}, status_fields=(), reference_fields=())[0]
        apply_saved_mappings(self.conn, 'output', iid)
        match_output_catalog_codes(self.conn, tenant='TDP', invoice_id=iid, now_iso=now_iso)
        self.conn.commit()
        return iid

    def sources(self):
        return ([tuple(r) for r in self.conn.execute('SELECT id,raw_json,subtotal,tax_amount,total_amount FROM outgoing_source_invoices ORDER BY id')],
                [tuple(r) for r in self.conn.execute('SELECT * FROM outgoing_source_invoice_items ORDER BY id')])

    def report(self):
        return moving_average_report(self.conn, date_from='2026-08-01', date_to='2026-08-31', include_events=True, include_zero=True)

    def test_no_stock_no_cost_no_bk_flag_still_posts_once_without_inventing_receipts(self):
        ids = [self.new(7), self.new(9)]
        before = list(self.conn.iterdump())
        preview = preview_outputs(self.conn, ids, 'TDP', now_iso)
        self.assertEqual(before, list(self.conn.iterdump()))
        self.assertEqual([], preview['blocked'])
        self.assertEqual([{'xách':7}, {'xách':9}], [r['qty_by_unit'] for r in preview['items']])
        sources = self.sources()
        posted = post_outputs(self.conn, preview['items'], 'TDP', now_iso, confirmed=True)
        self.assertEqual(2, posted['posted_count'])
        self.assertEqual(2, post_outputs(self.conn, preview['items'], 'TDP', now_iso, confirmed=True)['already_posted_count'])
        self.assertEqual(sources, self.sources())
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM inventory_transactions').fetchone()[0])
        self.assertEqual(0, self.conn.execute("SELECT COUNT(*) FROM invoice_inventory_ledger WHERE direction='input'").fetchone()[0])
        self.assertEqual(-16, self.conn.execute('SELECT SUM(qty_delta) FROM invoice_inventory_ledger').fetchone()[0])
        row = self.report()['items'][0]
        self.assertEqual((-16, 'pending_source_cost'), (row['closing_qty'], row['valuation_status']))
        init_inventory_period_close_schema(self.conn)
        self.assertFalse(inventory_period_close_preview(self.conn, '2026-08', today=date(2026,9,9))['can_close'])

    def test_amount_warning_remains_visible_after_quantity_post_and_source_is_unchanged(self):
        iid = self.new(mismatch=True)
        sources = self.sources()
        before = invoice_range_payload(self.conn, tenant='TDP', invoice_type='output', date_from='2026-08-01', date_to='2026-08-31')
        self.assertEqual('ready', before['items'][0]['workbench_status'])
        self.assertEqual(1, len(before['amount_reviews']))
        preview = preview_outputs(self.conn, [iid], 'TDP', now_iso)
        self.assertEqual(122000, preview['items'][0]['amount'])
        self.assertEqual(2000, preview['items'][0]['detail_amount'])
        post_outputs(self.conn, preview['items'], 'TDP', now_iso, confirmed=True)
        after = invoice_range_payload(self.conn, tenant='TDP', invoice_type='output', date_from='2026-08-01', date_to='2026-08-31')
        self.assertEqual('posted', after['items'][0]['workbench_status'])
        self.assertEqual(before['amount_reviews'], after['amount_reviews'])
        self.assertEqual(sources, self.sources())
        raw = json.loads(self.conn.execute('SELECT raw_json FROM outgoing_source_invoices WHERE id=?', (iid,)).fetchone()[0])
        upsert_output_invoice(self.conn, raw, tenant='TDP', now=now_iso(), status_map={}, status_fields=(), reference_fields=())
        refreshed = invoice_range_payload(self.conn, tenant='TDP', invoice_type='output', date_from='2026-08-01', date_to='2026-08-31')
        self.assertEqual('posted', refreshed['items'][0]['workbench_status'])
        self.assertEqual(before['amount_reviews'], refreshed['amount_reviews'])
        self.assertTrue(post_output_invoice(self.conn, iid, confirmed=True, now_iso=now_iso)['idempotent'])
        raw['details'][0]['quantity'] += 1
        upsert_output_invoice(self.conn, raw, tenant='TDP', now=now_iso(), status_map={}, status_fields=(), reference_fields=())
        self.assertEqual('reversal_required', self.conn.execute('SELECT stock_status FROM outgoing_source_invoices WHERE id=?', (iid,)).fetchone()[0])

    def test_invalid_mapping_or_changed_source_rolls_back_whole_group(self):
        ids = [self.new(), self.new()]
        preview = preview_outputs(self.conn, ids, 'TDP', now_iso)
        self.conn.execute("UPDATE outgoing_source_invoice_items SET product_code='' WHERE invoice_id=?", (ids[-1],))
        with self.assertRaises(InvoiceInventoryError):
            post_outputs(self.conn, preview['items'], 'TDP', now_iso, confirmed=True)
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])
        with self.assertRaises(InvoiceInventoryError):
            post_output_invoice(self.conn, ids[-1], confirmed=True, now_iso=now_iso)

    def test_unknown_source_state_and_unsafe_detail_are_still_rejected(self):
        for changes in ({'invoiceStatus':1}, {'sendTaxStatus':0}, {'invoiceDetail':[]}):
            with self.subTest(changes=changes):
                iid = self.new(**changes)
                with self.assertRaises(InvoiceInventoryError):
                    post_output_invoice(self.conn, iid, confirmed=True, now_iso=now_iso)
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])

    def test_negative_output_can_be_reversed_without_creating_a_receipt(self):
        iid = self.new()
        post_output_invoice(self.conn, iid, confirmed=True, now_iso=now_iso)
        self.conn.execute("UPDATE outgoing_source_invoices SET stock_status='reversal_required',source_status_class='cancelled' WHERE id=?", (iid,))
        reverse_output_invoice(self.conn, iid, confirmed=True, note='Cancelled source', now_iso=lambda:'2026-08-31T12:00:00')
        row = self.report()['items'][0]
        self.assertEqual((0, 0, 'ok'), (row['closing_qty'], row['closing_value'], row['valuation_status']))

    def test_http_review_and_confirm_keep_warning_instead_of_holding_issued_invoice(self):
        self.new(mismatch=True)
        @contextmanager
        def db():
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise
        app = Flask(__name__)
        register_invoice_workbench_routes(app, {'db':db, 'now_iso':now_iso, 'setting_get':lambda c,k,d:d})
        client = app.test_client()
        url = '/api/invoice-workbench/output-postings'
        before = list(self.conn.iterdump())
        review = client.get(url+'?from=2026-08-01&to=2026-08-31')
        self.assertEqual(200, review.status_code)
        self.assertEqual(before, list(self.conn.iterdump()))
        self.assertEqual(1, len(review.json['items']))
        self.assertEqual([], review.json['blocked'])
        self.assertEqual(400, client.post(url, json={'items':review.json['items']}).status_code)
        response = client.post(url, json={'confirmed':True, 'items':review.json['items']})
        self.assertEqual(200, response.status_code, response.json)
        self.assertEqual(1, response.json['posted_count'])
        self.assertEqual(1, client.post(url, json={'confirmed':True, 'items':review.json['items']}).json['already_posted_count'])
