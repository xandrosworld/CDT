import sqlite3
import unittest

from .test_invoice_input_sync import init_test_database
from .test_minvoice_portal import document
from .minvoice_portal import normalize_portal_document
from .invoice_output_sync import upsert_output_invoice
from .invoice_mapping import (save_mapping, apply_saved_mappings, validated_output_stock_snapshot,
                              _record_revision, InvoiceMappingError)
from .invoice_output_code_only import repair_output_code_only
from .invoice_inventory import post_output_invoice, reverse_output_invoice
from .invoice_product_identity import output_identity_warning

NOW = '2026-09-08T22:00:00'


class OutputCodeOnlyTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        init_test_database(self.conn)
        self.conn.execute("INSERT INTO products(code,name,unit) VALUES('A','Goods','Chai')")
        self.raw = document()
        self.raw['invoiceDetail'][0].update(unitCode='xách')
        self.iid = self.sync()
        self.item = self.conn.execute('SELECT id FROM outgoing_source_invoice_items').fetchone()[0]
        save_mapping(self.conn, direction='output', item_id=self.item, product_code='A', now_iso=lambda:NOW)

    def tearDown(self):
        self.conn.close()

    def sync(self):
        iid = upsert_output_invoice(self.conn, normalize_portal_document(self.raw), tenant='TDP', now=NOW,
                                    status_map={}, status_fields=(), reference_fields=())[0]
        apply_saved_mappings(self.conn, 'output', iid)
        self.item = self.conn.execute('SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=?', (iid,)).fetchone()[0]
        return iid

    def legacy(self, factor=None):
        qty = 2 * factor if factor else 0
        price = 100000 / qty if qty else 0
        self.conn.execute("UPDATE invoice_line_mappings SET mapping_status=?,conversion_factor=?",
                          ('confirmed' if factor else 'unit_review', factor))
        self.conn.execute("UPDATE outgoing_source_invoice_items SET mapping_status=?,conversion_factor=?,stock_qty=?,stock_unit_price=?",
                          ('mapped' if factor else 'unit_review', factor, qty, price))
        self.conn.execute("UPDATE outgoing_source_invoices SET stock_status='pending_mapping'")

    def test_migration_preserves_code_source_and_ledger_and_is_idempotent(self):
        for factor in (None, 12, 0.5):
            with self.subTest(factor=factor):
                self.legacy(factor)
                before = dict(self.conn.execute('SELECT * FROM outgoing_source_invoice_items').fetchone())
                result = repair_output_code_only(self.conn, timestamp=NOW)
                self.assertEqual(result['changed_lines'], 1)
                after = dict(self.conn.execute('SELECT * FROM outgoing_source_invoice_items').fetchone())
                for key in before:
                    if key not in {'mapping_status', 'conversion_factor', 'stock_qty', 'stock_unit_price'}:
                        self.assertEqual(after[key], before[key])
                self.assertEqual(validated_output_stock_snapshot(self.conn, self.item)['stock_qty'], 2)
                self.assertEqual(after['mapping_status'], 'mapped')
                self.assertEqual(after['stock_unit_price'], 50000)
                self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0], 0)
                saved = list(self.conn.iterdump())
                self.assertEqual(repair_output_code_only(self.conn, timestamp=NOW)['changed_lines'], 0)
                self.assertEqual(list(self.conn.iterdump()), saved)

    def test_resync_does_not_restore_a_legacy_multiplier(self):
        self.legacy(12)
        self.sync()
        snapshot = validated_output_stock_snapshot(self.conn, self.item)
        self.assertEqual(snapshot['stock_qty'], 2)
        self.assertEqual(snapshot['conversion_factor'], 1)

    def test_output_post_and_reverse_use_source_quantity_and_frozen_data_stays_unchanged(self):
        self.conn.execute("INSERT INTO inventory_transactions(txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,status,note,created_at,updated_at) "
                          "VALUES('2026-08-01','A',10,0,100,'OPENING','2026-08','1','posted','fixture',?,?)", (NOW,NOW))
        post_output_invoice(self.conn, self.iid, confirmed=True, now_iso=lambda:NOW)
        event = self.conn.execute("SELECT * FROM invoice_inventory_ledger WHERE direction='output'").fetchone()
        self.assertEqual(event['qty_delta'], -2)
        before = list(self.conn.iterdump())
        self.assertEqual(repair_output_code_only(self.conn, timestamp=NOW)['changed_lines'], 0)
        self.assertEqual(list(self.conn.iterdump()), before)
        self.conn.execute("UPDATE outgoing_source_invoices SET stock_status='reversal_required',source_status_class='cancelled' WHERE id=?", (self.iid,))
        reverse_output_invoice(self.conn, self.iid, confirmed=True, note='Fixture reversal', now_iso=lambda:NOW)
        self.assertEqual(self.conn.execute("SELECT SUM(qty_delta) FROM invoice_inventory_ledger WHERE direction='output'").fetchone()[0], 0)

    def test_migration_keeps_wrong_product_identity_blocked(self):
        self.raw['invoiceDetail'][0]['productName'] = 'Bánh đa đỏ ướt'
        self.sync()
        save_mapping(self.conn, direction='output', item_id=self.item, product_code='A', now_iso=lambda:NOW)
        self.legacy()
        before = output_identity_warning(self.conn, self.item)
        self.assertTrue(before)
        repair_output_code_only(self.conn, timestamp=NOW)
        self.assertEqual(output_identity_warning(self.conn, self.item), before)
        with self.assertRaises(InvoiceMappingError):
            validated_output_stock_snapshot(self.conn, self.item)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM audit_log WHERE event_type='invoice_mapping.identity_confirmed'").fetchone()[0], 0)

    def test_stale_multiplier_is_rejected_even_when_mapping_and_snapshot_agree(self):
        self.legacy(12)
        mapping = self.conn.execute('SELECT * FROM invoice_line_mappings').fetchone()
        _record_revision(self.conn, mapping, NOW)
        with self.assertRaises(InvoiceMappingError) as error:
            validated_output_stock_snapshot(self.conn, self.item)
        self.assertEqual(error.exception.code, 'stale_conversion_snapshot')
