import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import server, contract_modules as cm
from . import test_customer_purchase_layout as layout_tests
from . import test_purchase_order_roundtrip as roundtrip_tests
from .purchase_money_adjustments import DEDUCTION_KIND, DEDUCTION_LABEL
from .payable_export import payable_export_data, payable_workbook


class PurchaseMoneyAdjustmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(server, 'DB_PATH', root / 'test.sqlite3'),
                        patch.object(server, 'DATA_DIR', root), patch.object(server, 'auto_backup')]
        for p in self.patches: p.start()
        self.addCleanup(self.cleanup)
        server.init_database(sync_master=False)
        self.client = server.app.test_client()
        with server.db() as conn:
            self.batch, self.order = roundtrip_tests.PurchaseOrderRoundtripTests._insert_approved_order(conn)
            conn.execute("UPDATE batches SET work_date='2026-09-03' WHERE id=?", (self.batch,))
            conn.execute("UPDATE orders SET work_date='2026-09-03',supplier='phong' WHERE id=?", (self.order,))

    def cleanup(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    @staticmethod
    def book():
        book = layout_tests.CustomerPurchaseLayoutTests.workbook()
        sheet = book.active
        sheet.cell(2, 16, 'Thành tiền')
        sheet.append(['', 'J000017', 'MNLINHTRANG2', '03.09.2026', 'quả dưa hấu', -1,
                      'Kg', 'phong', '', 117000, 0, 0, 0, 0, -1, -117000])
        sheet.append(['', None, 'MNLINHTRANG3', '03.09.2026', 'quả nhãn', -1,
                      'Kg', 'phong', '', 90000, 0, 0, 0, 0, -1, -90000])
        sheet.append(['', 'PO-P1', 'POT', '03.09.2026', 'Sườn non', 10,
                      'kg', 'phong', '', 50000, 0, 0, 0, 0, 10, 500000])
        return book

    def preview(self, book):
        stream = io.BytesIO(); book.save(stream); stream.seek(0)
        response = self.client.post('/api/purchase-orders/import/preview',
            data={'batch_id': str(self.batch), 'file': (stream, 'purchase.xlsx')},
            content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json

    def confirm(self, preview):
        response = self.client.post('/api/purchase-orders/import/confirm',
            json={'token': preview['token'], 'confirmed': True})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.json

    def protected(self):
        with server.db() as conn:
            return {table: [tuple(r) for r in conn.execute('SELECT * FROM ' + table + ' ORDER BY rowid')]
                    for table in ('orders', 'receivable_ledger_lines', 'invoice_inventory_ledger', 'inventory_transactions')}

    def test_approved_deductions_net_payable_only_and_repeat_is_noop(self):
        before = self.protected()
        book = self.book(); self.addCleanup(book.close)
        preview = self.preview(book)
        self.assertEqual(preview['error_rows'], 0, preview)
        self.confirm(preview)
        self.assertEqual(self.protected(), before)
        with server.db() as conn:
            money = [dict(r) for r in conn.execute('SELECT * FROM purchase_workbook_lines WHERE line_kind=?', (DEDUCTION_KIND,))]
            self.assertEqual(len(money), 2)
            self.assertEqual(sum(r['amount'] for r in money), -207000)
            for row in money:
                self.assertIsNone(row['order_id'])
                self.assertEqual(sum(row[f] for f in ('base_qty','actual_qty','buy_price','damaged_qty','added_qty','reduced_qty','missing_qty')), 0)
            ledger = [dict(r) for r in conn.execute("SELECT * FROM payable_ledger_lines WHERE supplier_code='phong' AND status!='reversed'")]
            self.assertEqual(sum(r['amount'] for r in ledger), 293000)
            self.assertEqual(sum(r['actual_qty'] for r in ledger), 10)
            self.assertEqual(sum(DEDUCTION_LABEL in r['product_name'] for r in ledger), 2)
            data = payable_export_data(conn, date_from='2026-09-03', date_to='2026-09-03',
                supplier='', canonical_party_code=server.canonical_party_code)
            workbook = payable_workbook(data)
            sheet = workbook['Công nợ phải trả']
            self.assertEqual(sheet.max_column, 14)
            # The complete sheet also includes the fixture's 14,040đ kho row.
            self.assertEqual(sheet.cell(sheet.max_row,14).value, 307040)
            deductions = [r for r in sheet.iter_rows(min_row=4) if str(r[3].value).startswith(DEDUCTION_LABEL)]
            self.assertEqual(sum(r[13].value for r in deductions), -207000)
            workbook.close()
            history = conn.execute('SELECT COUNT(*) FROM payable_ledger_revisions').fetchone()[0]
        self.assertTrue(self.confirm(self.preview(book))['idempotent'])
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM payable_ledger_revisions').fetchone()[0], history)
        self.assertEqual(self.protected(), before)

    def test_other_negative_or_changed_source_stays_blocked(self):
        for cell, value in [('H4', 'khác'), ('D4', '04.09.2026'), ('J4', 118000), ('P4', -118000)]:
            with self.subTest(cell=cell):
                book = self.book(); book.active[cell] = value
                try: self.assertGreater(self.preview(book)['error_rows'], 0)
                finally: book.close()
        book = self.book()
        book.active.append([c.value for c in book.active[4]])
        try: self.assertGreater(self.preview(book)['error_rows'], 0)
        finally: book.close()

    def test_export_reimport_preserves_money_and_sales(self):
        book = self.book(); self.addCleanup(book.close)
        self.confirm(self.preview(book))
        before = self.protected()
        with server.db() as conn:
            batch = conn.execute('SELECT * FROM batches WHERE id=?', (self.batch,)).fetchone()
            orders = conn.execute('SELECT * FROM orders WHERE batch_id=?', (self.batch,)).fetchall()
            exported = server.export_supplier_orders(conn, batch, orders)
        self.addCleanup(exported.close)
        money = [row for row in exported.active.iter_rows(min_row=3) if len(row)>17 and row[17].value == DEDUCTION_LABEL]
        self.assertEqual(len(money), 2)
        self.assertEqual(sum(row[15].value for row in money), -207000)
        preview = self.preview(exported)
        self.assertEqual(preview['error_rows'], 0, preview)
        self.confirm(preview)
        self.assertEqual(self.protected(), before)
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT SUM(amount) FROM purchase_workbook_lines WHERE line_kind=?', (DEDUCTION_KIND,)).fetchone()[0], -207000)

    def test_explicit_deduction_rejects_quantity_and_nonnegative_money(self):
        for qty, amount in [(1, -1000), (0, 1000), (0, 0)]:
            book = self.book(); sheet = book.active
            sheet.cell(2,18,'Loại dòng'); sheet.cell(4,18,DEDUCTION_LABEL)
            sheet.cell(4,6,qty); sheet.cell(4,10,0); sheet.cell(4,15,qty); sheet.cell(4,16,amount)
            try: self.assertGreater(self.preview(book)['error_rows'], 0)
            finally: book.close()

    def test_draft_is_not_active_debt_and_failure_rolls_back(self):
        with server.db() as conn:
            conn.execute("UPDATE batches SET status='draft' WHERE id=?", (self.batch,))
        book = self.book(); self.addCleanup(book.close)
        preview = self.preview(book)
        with patch.object(cm, 'audit', side_effect=RuntimeError('forced audit failure')):
            response = self.client.post('/api/purchase-orders/import/confirm',
                json={'token': preview['token'], 'confirmed': True})
        self.assertEqual(response.status_code, 500)
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM purchase_workbook_lines').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM purchase_workbook_line_revisions').fetchone()[0], 0)
        self.confirm(self.preview(book))
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM payable_ledger_lines WHERE status!='reversed'").fetchone()[0], 0)
