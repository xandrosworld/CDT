import unittest

from . import server
from . import test_output_stock_remap as fixtures
from .output_stock_web import review_shortages, preview_web
from .output_stock_remap import confirm_preview, RemapError


class OutputStockWebTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.OutputStockRemapTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.OutputStockRemapTests.tearDownClass.__func__)
    setUp = fixtures.OutputStockRemapTests.setUp

    def body(self, conn, **extra):
        view = review_shortages(conn, '2026-08-01', '2026-08-31')
        item = next(r for r in view['items'] if r['product_code'] == 'HH-01')
        return dict({'from':'2026-08-01', 'to':'2026-08-31', 'version':view['version'],
                     'product_code':'HH-01', 'ledger_id':item['sources'][0]['ledger_id'],
                     'new_code':'REMAP-B', 'qty':4}, **extra)

    def test_preview_partial_post_idempotent_and_source_immutable(self):
        with server.db() as conn:
            conn.execute("UPDATE inventory_transactions SET qty_in=30 WHERE product_code='HH-01' AND source_type='OPENING'")
            conn.execute("UPDATE inventory_transactions SET qty_in=100 WHERE product_code='REMAP-B' AND source_type='OPENING'")
            conn.execute('UPDATE invoice_inventory_ledger SET qty_delta=-52 WHERE source_invoice_id=?', (self.source_id,))
            conn.execute('UPDATE outgoing_source_invoice_items SET qty=52,stock_qty=52 WHERE id=?', (self.line_id,))
            raw = dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?', (self.line_id,)).fetchone())
            preview = preview_web(conn, self.body(conn, qty=22))
            self.assertTrue(preview['can_confirm'], preview)
            self.assertEqual(0, conn.execute('SELECT COUNT(*) FROM output_stock_remap_parts').fetchone()[0])
            self.assertEqual((0,78), (preview['changes'][0]['old_closing_after'],preview['changes'][0]['new_closing_after']))
            first = confirm_preview(conn, preview['token'], 'Kiểm thử', server.now_iso())
            again = confirm_preview(conn, preview['token'], 'Kiểm thử', server.now_iso())
            self.assertFalse(first['idempotent']); self.assertTrue(again['idempotent'])
            self.assertEqual(raw, dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone()))
            parts = {r['product_code']:r['qty'] for r in conn.execute('SELECT * FROM output_stock_remap_parts')}
            self.assertEqual({'HH-01':30,'REMAP-B':22}, parts)
            self.assertNotIn('HH-01', [r['product_code'] for r in review_shortages(conn,'2026-08-01','2026-08-31')['items']])
            audit = conn.execute("SELECT entity_type FROM audit_log WHERE entity_id=?", (preview['token'],)).fetchone()
            self.assertEqual('web', audit['entity_type'])

    def test_invalid_fields_have_actionable_targets_and_no_writes(self):
        with server.db() as conn:
            for patch, field in [({'new_code':'HH-01'},'new_code'),({'new_code':'MISSING'},'new_code'),
                                 ({'qty':'NaN'},'qty'),({'qty':float('inf')},'qty'),({'qty':5},'qty'),
                                 ({'qty':0},'qty'),({'ledger_id':0},'ledger_id')]:
                result = preview_web(conn,self.body(conn,**patch))
                self.assertFalse(result['can_confirm'],patch)
                self.assertIn(field,[i['field'] for i in result['issues']])
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])

    def test_unit_mismatch_rejected(self):
        with server.db() as conn:
            conn.execute("UPDATE products SET unit='Gói' WHERE code='REMAP-B'")
            result=preview_web(conn,self.body(conn))
            self.assertFalse(result['can_confirm'])
            self.assertIn('đơn vị',result['issues'][0]['message'])

    def test_insufficient_recipient_rejected_with_edit_button_target(self):
        with server.db() as conn:
            conn.execute("UPDATE inventory_transactions SET qty_in=1 WHERE product_code='REMAP-B'")
            result=preview_web(conn,self.body(conn))
            self.assertFalse(result['can_confirm'])
            self.assertEqual('new_code', result['issues'][0]['field'])
            self.assertNotIn('Excel',result['issues'][0]['message'])

    def test_stale_preview_and_confirmation(self):
        with server.db() as conn:
            body=self.body(conn)
            result=preview_web(conn,body)
            conn.execute("UPDATE inventory_transactions SET qty_in=9 WHERE product_code='REMAP-B'")
            stale=preview_web(conn,body)
            self.assertEqual('reload',stale['issues'][0]['field'])
            with self.assertRaisesRegex(RemapError,'Cập nhật số liệu'):
                confirm_preview(conn,result['token'],'Người thử',server.now_iso())
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])

    def test_closed_period_visible_but_not_editable(self):
        with server.db() as conn:
            # A later opening is also a protected carried period.
            conn.execute("UPDATE inventory_transactions SET txn_date='2026-09-01' WHERE product_code='REMAP-B'")
            view=review_shortages(conn,'2026-08-01','2026-08-31')
            self.assertIn('tồn đầu kỳ sau',view['blocked_reason'])
            result=preview_web(conn,self.body(conn))
            self.assertEqual('period',result['issues'][0]['field'])

    def test_confirm_route_requires_explicit_confirmation(self):
        with server.db() as conn:
            result=preview_web(conn,self.body(conn))
        response=self.client.post('/api/inventory/output-remap/confirm',json={'token':result['token'],'actor':'Test'})
        self.assertEqual(409,response.status_code)
        with server.db() as conn:
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])


if __name__ == '__main__':
    unittest.main()
