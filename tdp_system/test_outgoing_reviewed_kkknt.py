import unittest

from . import outgoing_amount_settlement as money
from . import test_outgoing_amount_settlement as fixtures
from . import server
from .outgoing_unissued import issued_allocations


class ReviewedKkkntTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.AmountSettlementTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AmountSettlementTests.tearDownClass.__func__)

    def setUp(self):
        fixtures.AmountSettlementTests.setUp(self)
        self.body['reviewed_kkknt'] = True
        with server.db() as c:
            c.execute("UPDATE orders SET tax='KKKNT'")
            c.execute("INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,tax_rate) VALUES(?,1,'-2')", (self.invoice,))
            c.execute('UPDATE outgoing_source_invoices SET subtotal=300,total_amount=300 WHERE id=?', (self.invoice,))

    def confirm(self, c):
        report = money.preview(c, self.body)
        self.assertTrue(report['can_confirm'], report)
        return money.confirm(c, {**self.body, 'token': report['token']}, server.now_iso())

    def test_excess_is_separate_vat_and_other_dates_stay_open(self):
        with server.db() as c:
            _, vat = fixtures.Fixture.add_batch(c, '2026-09-01', [{'qty': 2, 'tax': '8%'}])
            _, older = fixtures.Fixture.add_batch(c, '2026-08-31', [{'qty': 2, 'tax': 'KKKNT'}])
            _, later = fixtures.Fixture.add_batch(c, '2026-09-17', [{'qty': 2, 'tax': 'KKKNT'}])
            tables = ('orders', 'batches', 'invoice_inventory_ledger', 'outgoing_source_invoices', 'receivable_ledger_lines')
            before = {t: [tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in tables}
            self.confirm(c)
            covered, invoices, errors = money.coverage(c)
            self.assertEqual(covered, set(self.orders))
            self.assertFalse(covered.intersection(vat+older+later))
            self.assertEqual(invoices, {self.invoice})
            self.assertEqual(errors, [])
            self.assertEqual(money.history(c)[0]['excess_amount'], 100)
            self.assertEqual(issued_allocations(c)[0], {})
            for t in tables:
                self.assertEqual(before[t], [tuple(r) for r in c.execute('SELECT * FROM '+t)], t)

    def test_default_still_rejects_excess_and_taxable_invoice(self):
        with server.db() as c:
            self.assertFalse(money.preview(c, {**self.body, 'reviewed_kkknt': False})['can_confirm'])
            c.execute("UPDATE outgoing_source_invoice_items SET tax_rate='0'")
            with self.assertRaises(ValueError):
                money.preview(c, self.body)

    def test_confirmation_idempotent_and_changed_data_invalidates(self):
        with server.db() as c:
            report = money.preview(c, self.body)
            body = {**self.body, 'token': report['token']}
            first = money.confirm(c, body, server.now_iso())
            again = money.confirm(c, body, server.now_iso())
            self.assertEqual(first['id'], again['id'])
            self.assertTrue(again['unchanged'])
            c.execute('UPDATE orders SET sell_price=21 WHERE id=?', (self.orders[0],))
            self.assertFalse(money.coverage(c)[0])
            self.assertTrue(money.coverage(c)[2])

    def test_stale_preview_or_missing_confirmation_cannot_apply(self):
        with server.db() as c:
            report = money.preview(c, self.body)
            with self.assertRaises(ValueError):
                money.confirm(c, {**self.body, 'confirmed': False, 'token': report['token']}, server.now_iso())
            c.execute('UPDATE orders SET sell_price=21 WHERE id=?', (self.orders[0],))
            with self.assertRaises(ValueError):
                money.confirm(c, {**self.body, 'token': report['token']}, server.now_iso())

    def test_partial_note_remains_valid_without_closing_orders(self):
        with server.db() as c:
            c.execute('UPDATE outgoing_source_invoices SET subtotal=100,total_amount=100 WHERE id=?', (self.invoice,))
            report = money.preview(c, self.body)
            money.save_progress(c, {**self.body, 'token': report['token']}, server.now_iso())
            note = money.progress(c, self.body['contractor'], self.body['from'], self.body['to'])
            self.assertFalse(note['needs_review'])
            self.assertTrue(note['reviewed_kkknt'])
            self.assertEqual(money.coverage(c), (set(), set(), []))

    def test_other_invoice_covering_same_orders_still_blocks(self):
        with server.db() as c:
            other = fixtures.Fixture.add_posted_source(c, source='minvoice', qty=2, invoice_date='2026-09-10', number='899')
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567' WHERE id=?", (other,))
            report = money.preview(c, self.body)
            self.assertFalse(report['can_confirm'])
            self.assertTrue(report['conflicts'])
