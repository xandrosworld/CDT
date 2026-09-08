import json
import sqlite3
import unittest

from .contract_modules import normalize_invoice_item, upsert_msmi_invoice
from .invoice_input_integrity import receipt_cost_warning, repair_missing_unit_price_goods
from .invoice_input_sync import input_invoice_payload
from .invoice_expenses import expense_token, set_expenses
from .invoice_mapping import save_mapping
from .invoice_receipt import InvoiceReceiptError, create_input_receipt
from .invoice_receipt_bulk import preview_receipts
from .invoice_workbench_listing import invoice_state, line_issue
from .test_invoice_input_sync import init_test_database
from .test_msmi_sync import remote_invoice

NOW = '2026-09-08T19:00:00'


class InputIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        init_test_database(self.conn)
        self.conn.execute("INSERT INTO products(code,name,unit) VALUES('P1','Hàng kiểm thử','kg')")
        self.raw = remote_invoice(1)
        self.raw['hdhhdvu'][0].update(dgia=0, sluong=2, tchat=1)
        self.iid = upsert_msmi_invoice(self.conn, self.raw, 'INPUT_ELECTRONIC_INVOICE', 'TDP', NOW)[0]
        self.item = self.conn.execute('SELECT id FROM msmi_invoice_items').fetchone()[0]

    def tearDown(self):
        self.conn.close()

    def map(self):
        save_mapping(self.conn, direction='input', item_id=self.item, product_code='P1', now_iso=lambda: NOW)

    def test_missing_unit_price_goods_post_from_amount_without_changing_source(self):
        self.map()
        source = tuple(self.conn.execute('SELECT qty,unit_price,amount FROM msmi_invoice_items').fetchone())
        result = create_input_receipt(self.conn, self.iid, lambda: NOW)
        self.assertEqual(result['new_inventory_lines'], 1)
        self.assertEqual(tuple(self.conn.execute('SELECT qty_in,unit_cost FROM inventory_transactions').fetchone()), (2, 5000))
        self.assertEqual(source, (2, 0, 10000))
        self.assertEqual(tuple(self.conn.execute('SELECT qty,unit_price,amount FROM msmi_invoice_items').fetchone()), source)

    def test_financial_and_note_lines_never_become_stock_even_with_quantity(self):
        for nature in (3, 4):
            with self.subTest(nature=nature):
                row = normalize_invoice_item({'sluong': 1, 'dgia': 100, 'thtien': 100, 'tchat': nature}, 1)
                self.assertFalse(row['inventory_eligible'])

    def test_expense_roundtrip_retains_goods_with_missing_unit_price(self):
        for expense in (True, False):
            set_expenses(self.conn, tenant='TDP', invoice_id=self.iid, expense=expense,
                         item_ids=[self.item], expected=expense_token(self.conn, self.iid), now=NOW)
        self.assertEqual(self.conn.execute('SELECT inventory_eligible,mapping_status FROM msmi_invoice_items').fetchone()[:], (1, 'unmapped'))

    def discount(self, *, total=10300, subtotal=9500, tax=800):
        self.raw.update(ttcktmai=500, tgtcthue=subtotal, tgtthue=tax, tgtttbso=total)
        self.conn.execute('UPDATE msmi_invoices SET raw_json=?,subtotal=?,tax_amount=?,total_amount=?',
                          (json.dumps(self.raw), subtotal or 0, tax or 0, total or 0))

    def test_unallocated_discount_is_visible_and_blocks_single_and_bulk_without_writes(self):
        self.map()
        self.discount()
        self.conn.commit()
        before = list(self.conn.iterdump())
        invoice = input_invoice_payload(self.conn, invoice_ids=[self.iid])['items'][0]
        self.assertEqual(invoice_state(invoice, 'input'), 'error')
        self.assertIn('chiết khấu', line_issue(invoice['items'][0], invoice, 'error'))
        with self.assertRaises(InvoiceReceiptError) as error:
            create_input_receipt(self.conn, self.iid, lambda: NOW)
        self.assertEqual(error.exception.code, 'input_cost_review_required')
        self.assertEqual(len(preview_receipts(self.conn, [self.iid], 'TDP', lambda: NOW)['blocked']), 1)
        self.assertEqual(list(self.conn.iterdump()), before)

    def test_source_net_amount_already_allocated_is_not_subtracted_twice(self):
        self.map()
        self.discount()
        self.conn.execute('UPDATE msmi_invoice_items SET amount=9500')
        self.map()
        self.assertEqual(receipt_cost_warning(self.conn, self.iid), '')
        create_input_receipt(self.conn, self.iid, lambda: NOW)
        self.assertEqual(self.conn.execute('SELECT qty_in*unit_cost FROM inventory_transactions').fetchone()[0], 9500)

    def test_discount_subtracted_after_header_subtotal_is_also_blocked(self):
        self.discount(subtotal=10000)
        self.assertTrue(receipt_cost_warning(self.conn, self.iid))

    def test_missing_header_subtotal_without_discount_does_not_invent_a_difference(self):
        self.raw.update(tgtcthue=None, tgtthue=None, tgtttbso=10000)
        self.conn.execute('UPDATE msmi_invoices SET raw_json=?', (json.dumps(self.raw),))
        self.assertEqual(receipt_cost_warning(self.conn, self.iid), '')
        self.raw['ttcktmai'] = 500
        self.conn.execute('UPDATE msmi_invoices SET raw_json=?', (json.dumps(self.raw),))
        self.assertTrue(receipt_cost_warning(self.conn, self.iid))

    def legacy_exclusion(self):
        self.conn.execute("""UPDATE msmi_invoice_items SET inventory_eligible=0,mapping_status='not_inventory',
            validation_note='Không ghi kho: dòng nguồn không có số lượng/đơn giá dương; vẫn giữ nguyên để đối chiếu hóa đơn'""")
        self.conn.execute("UPDATE msmi_invoices SET receipt_status='not_inventory'")

    def test_repair_only_flags_once_and_preserves_source_financials(self):
        self.legacy_exclusion()
        before = self.conn.execute('SELECT raw_json,subtotal,tax_amount,total_amount FROM msmi_invoices').fetchone()[:]
        line = self.conn.execute('SELECT qty,unit_price,amount,source_item_name,source_nature FROM msmi_invoice_items').fetchone()[:]
        self.assertEqual(repair_missing_unit_price_goods(self.conn, NOW), [self.item])
        self.assertEqual(repair_missing_unit_price_goods(self.conn, NOW), [])
        self.assertEqual(self.conn.execute('SELECT receipt_status FROM msmi_invoices').fetchone()[0], 'pending_mapping')
        self.assertEqual(self.conn.execute('SELECT raw_json,subtotal,tax_amount,total_amount FROM msmi_invoices').fetchone()[:], before)
        self.assertEqual(self.conn.execute('SELECT qty,unit_price,amount,source_item_name,source_nature FROM msmi_invoice_items').fetchone()[:], line)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM inventory_transactions').fetchone()[0], 0)

    def test_repair_preserves_explicit_expense_and_posted_rows(self):
        self.legacy_exclusion()
        self.conn.execute("INSERT INTO invoice_input_expense_choices VALUES(?,1,'user-choice',?)", (self.iid, NOW))
        self.assertEqual(repair_missing_unit_price_goods(self.conn, NOW), [])
        self.conn.execute('DELETE FROM invoice_input_expense_choices')
        self.conn.execute("UPDATE msmi_invoices SET receipt_status='posted'")
        self.assertEqual(repair_missing_unit_price_goods(self.conn, NOW), [])

