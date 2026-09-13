"""A stock-only change must not settle an unrelated sold product."""
import json
import unittest

from . import server
from . import test_outgoing_readiness as support
from .outgoing_unissued import issued_allocations


class RemapOrderReconciliationTests(unittest.TestCase):
    setUpClass = classmethod(support.OutgoingReadinessTests.setUpClass.__func__)
    tearDownClass = classmethod(support.OutgoingReadinessTests.tearDownClass.__func__)

    def setUp(self):
        with server.db() as conn:
            conn.execute('DELETE FROM output_stock_remap_parts')
            conn.execute('DELETE FROM output_stock_remaps')
        support.OutgoingReadinessTests.setUp(self)

    def seed(self, *, partial=False, event='inventory.output.remap', day='2026-09-02'):
        with server.db() as conn:
            conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax) VALUES('OTHER','Other goods','kg','0%')")
            conn.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Buyer','0101234567','Address','2026-09-01')")
            batch, orders = support.OutgoingReadinessTests.add_batch(conn, '2026-09-01', [
                {'qty':5}, {'qty':5,'product_code':'OTHER'},
            ])
            sid = support.OutgoingReadinessTests.add_posted_source(
                conn, source='minvoice', number='CHECK-1', invoice_date=day, qty=3)
            conn.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567' WHERE id=?", (sid,))
            ledger = conn.execute('SELECT id FROM invoice_inventory_ledger WHERE source_invoice_id=?', (sid,)).fetchone()[0]
            if partial:
                conn.executemany('INSERT INTO output_stock_remap_parts(ledger_id,product_code,qty,unit_cost) VALUES(?,?,?,10)',
                                 [(ledger,'HH-01',2),(ledger,'OTHER',1)])
            else:
                conn.execute("INSERT INTO output_stock_remaps(ledger_id,product_code,revision,updated_at,unit_cost) VALUES(?,'OTHER',1,'2026-09-03',10)", (ledger,))
            metadata = {'changes':[{'ledger_id':ledger, 'invoice_id':sid, 'old_code':'HH-01','new_code':'OTHER'}]}
            conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES(?,'excel','test','ok','',?,'2026-09-03')", (event,json.dumps(metadata)))
        return batch, orders, sid, ledger

    def test_full_stock_remap_cannot_settle_a_different_sold_product(self):
        _, orders, _, _ = self.seed()
        with server.db() as conn:
            before = conn.serialize()
            allocations, warnings = issued_allocations(conn)
            self.assertEqual(0, allocations.get(orders[1],0))
            self.assertEqual(0, allocations.get(orders[0],0))
            self.assertTrue(any(w.get('code')=='stock_remap_requires_order_review' for w in warnings))
            self.assertEqual(before,conn.serialize())

    def test_partial_stock_remap_does_not_split_invoice_settlement_across_products(self):
        _, orders, _, _ = self.seed(partial=True)
        with server.db() as conn:
            allocations,warnings=issued_allocations(conn)
            self.assertEqual([0,0],[allocations.get(i,0) for i in orders])
            self.assertTrue(any(w.get('code')=='stock_remap_requires_order_review' for w in warnings))

    def test_restoring_original_stock_identity_releases_review(self):
        _,orders,_,ledger=self.seed()
        with server.db() as conn:
            conn.execute('DELETE FROM output_stock_remaps WHERE ledger_id=?',(ledger,))
            allocations,warnings=issued_allocations(conn)
            self.assertEqual([3,0],[allocations.get(i,0) for i in orders])
            self.assertEqual([],warnings)

    def test_old_invoice_before_order_period_does_not_block_current_orders(self):
        self.seed(day='2026-08-20')
        with server.db() as conn:
            allocations,warnings=issued_allocations(conn)
            self.assertFalse(any(allocations.values()))
            self.assertEqual([],warnings)

    def test_audited_product_identity_correction_is_distinct_from_stock_only_remap(self):
        _,orders,_,_=self.seed(event='inventory.output.identity_correction')
        with server.db() as conn:
            allocations,warnings=issued_allocations(conn)
            self.assertEqual([0,3],[allocations.get(i,0) for i in orders])
            self.assertEqual([],warnings)

    def test_existing_explicit_order_link_is_preserved_but_review_is_visible(self):
        batch,orders,_,_=self.seed()
        with server.db() as conn:
            support.OutgoingReadinessTests.add_local_issued_draft(
                conn,batch,orders[0],number='CHECK-1',invoice_date='2026-09-02',qty=3)
            allocations,warnings=issued_allocations(conn)
            self.assertEqual([3,0],[allocations.get(i,0) for i in orders])
            self.assertTrue(any(w.get('code')=='stock_remap_requires_order_review' for w in warnings))

    def test_warning_is_limited_to_affected_contractor(self):
        self.seed()
        with server.db() as conn:
            _,orders=support.OutgoingReadinessTests.add_batch(conn,'2026-09-01',[{'qty':5,'contractor':'NT-B'}])
            conn.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-B','Buyer B','0109876543','Address','2026-09-01')")
            sid=support.OutgoingReadinessTests.add_posted_source(conn,source='minvoice',number='CHECK-2',invoice_date='2026-09-02',qty=2)
            conn.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0109876543' WHERE id=?",(sid,))
            allocations,warnings=issued_allocations(conn)
            self.assertEqual(2,allocations.get(orders[0],0))
            self.assertTrue(warnings)
            self.assertTrue(all(w['contractor']=='NT-A' for w in warnings))

    def test_remap_history_of_existing_part_resolves_original_ledger(self):
        _,orders,_,ledger=self.seed(partial=True)
        with server.db() as conn:
            part=conn.execute("SELECT id FROM output_stock_remap_parts WHERE ledger_id=? AND product_code='OTHER'",(ledger,)).fetchone()[0]
            conn.execute("UPDATE audit_log SET metadata_json=? WHERE event_type='inventory.output.remap'",
                         (json.dumps({'changes':[{'ledger_id':-2*part}]}),))
            allocations,warnings=issued_allocations(conn)
            self.assertEqual([0,0],[allocations.get(i,0) for i in orders])
            self.assertTrue(any(w.get('code')=='stock_remap_requires_order_review' for w in warnings))


if __name__=='__main__':
    unittest.main()
