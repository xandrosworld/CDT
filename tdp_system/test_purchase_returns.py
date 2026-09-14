import io
import unittest
from openpyxl import load_workbook
from . import server, contract_modules as cm, batch_bk_approval
from . import test_purchase_money_adjustments as fixtures
from .supplier_plan import parse_supplier_plan, save_supplier_plan
from .payable_ledger import sync_payable_ledger
from .purchase_returns import RETURN_KIND, RETURN_LABEL


class PurchaseReturnTests(unittest.TestCase):
    setUp = fixtures.PurchaseMoneyAdjustmentTests.setUp
    cleanup = fixtures.PurchaseMoneyAdjustmentTests.cleanup
    preview = fixtures.PurchaseMoneyAdjustmentTests.preview
    confirm = fixtures.PurchaseMoneyAdjustmentTests.confirm
    protected = fixtures.PurchaseMoneyAdjustmentTests.protected

    def book(self):
        with server.db() as conn:
            conn.execute("UPDATE batches SET work_date='2026-09-08' WHERE id=?", (self.batch,))
        w = fixtures.PurchaseMoneyAdjustmentTests.book()
        s = w.active
        s.delete_rows(3, s.max_row)
        s.append(['', 'J000024', 'SUPPY', '08.09.2026', 'Quả nhãn', -1,
                  'Kg', 'phong', '', 80000, 0, 0, 0, 0, -1, -80000])
        s.append(['', 'M000309', 'SUMI', '08.09.2026', 'Trả lại đông trùng', -1,
                  'kg', 'việt', '', 270000, 0, 0, 0, 0, -1, -270000])
        self.addCleanup(w.close)
        return w

    def test_confirmed_returns_reduce_payables_keep_signed_quantity_and_replay(self):
        w = self.book(); before = self.protected()
        p = self.preview(w)
        self.assertEqual(p['error_rows'], 0, p)
        self.confirm(p)
        self.assertEqual(self.protected(), before)
        with server.db() as conn:
            for code, name in [('J000024', 'Quả nhãn'), ('M000309', 'Trả lại đông trùng')]:
                conn.execute('INSERT OR REPLACE INTO products(code,name,unit,purchase_list) VALUES(?,?,?,1)', (code,name,'kg'))
            rows = [dict(r) for r in conn.execute('SELECT * FROM purchase_workbook_lines')]
            self.assertEqual([r['line_kind'] for r in rows], [RETURN_KIND, RETURN_KIND])
            self.assertTrue(all(r['order_id'] is None for r in rows))
            self.assertEqual(sum(r['actual_qty'] for r in rows), -2)
            ledger = list(conn.execute("SELECT actual_qty,amount FROM payable_ledger_lines WHERE status!='reversed'"))
            self.assertEqual(sum(r['amount'] for r in ledger), -350000)
            self.assertEqual(sum(r['actual_qty'] for r in ledger), -2)
            self.assertTrue(batch_bk_approval.prepare(conn, self.batch)['canApprove'])
            self.assertEqual(batch_bk_approval.prepare(conn, self.batch)['rows'], [])
            history = conn.execute('SELECT count(*) FROM payable_ledger_revisions').fetchone()[0]
        self.assertTrue(self.confirm(self.preview(w))['idempotent'])
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM payable_ledger_revisions').fetchone()[0], history)

    def test_purchase_plan_projection_and_export_roundtrip(self):
        w = self.book()
        with server.db() as conn:
            p = parse_supplier_plan(conn, w, self.batch)
            self.assertTrue(p['can_confirm'], p)
            save_supplier_plan(conn, batch_id=self.batch, preview=p, source_hash='TEST-RETURNS',
                               source_name='returns.xlsx', now_iso=server.now_iso)
            sync_payable_ledger(conn, timestamp=server.now_iso())
            self.assertEqual(conn.execute("SELECT sum(amount) FROM payable_ledger_lines WHERE status!='reversed'").fetchone()[0], -350000)
            batch = conn.execute('SELECT * FROM batches WHERE id=?', (self.batch,)).fetchone()
            output = server.export_supplier_orders(conn, batch, [])
            self.addCleanup(output.close)
            self.assertEqual(output.active['F3'].value, -1)
            self.assertEqual(output.active['R3'].value, RETURN_LABEL)
        p = self.preview(output)
        self.assertEqual(p['error_rows'], 0, p)
        self.assertEqual(p['total_amount'], -350000)

    def test_unconfirmed_negatives_and_invalid_returns_remain_blocked(self):
        for cell, value in [('J3', 81000), ('H3', 'khác'), ('D3', '09.09.2026')]:
            w = self.book(); w.active[cell] = value
            self.assertGreater(self.preview(w)['error_rows'], 0)
        for cell, value in [('F3', 1), ('K3', 1), ('J3', 0), ('G3', ''), ('H3', 'kho')]:
            w = self.book(); s = w.active
            s['R2'] = 'Loại dòng'; s['R3'] = RETURN_LABEL; s[cell] = value
            self.assertGreater(self.preview(w)['error_rows'], 0)

    def test_explicit_return_type_supports_other_dates_without_guessing(self):
        w = self.book(); s = w.active
        s['R2'] = 'Loại dòng'; s['R3'] = RETURN_LABEL
        s['H3'] = 'khác'; s['F3'] = -2; s['O3'] = -2; s['P3'] = -160000
        p = self.preview(w)
        self.assertEqual(p['error_rows'], 0, p)
        self.assertEqual(p['total_amount'], -430000)

    def test_duplicate_return_is_blocked_before_payable_write(self):
        w = self.book()
        w.active.append([c.value for c in w.active[3]])
        self.assertGreater(self.preview(w)['error_rows'], 0)
