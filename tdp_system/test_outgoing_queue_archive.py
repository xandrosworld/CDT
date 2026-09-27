import json
import unittest
from . import server
from .test_outgoing_readiness import OutgoingReadinessTests as Fixture
from .outgoing_queue_archive import SCHEMA, archived_order_ids
from .outgoing_unissued import unissued_payload
from .outgoing_contractors import selected_orders, line_choices_payload
from .outgoing_readiness import validate_demand_orders, OutgoingReadinessError
from .outgoing_waiting import refresh_waiting

class QueueArchiveTests(unittest.TestCase):
    setUpClass=classmethod(Fixture.setUpClass.__func__)
    tearDownClass=classmethod(Fixture.tearDownClass.__func__)
    def setUp(self):
        Fixture.setUp(self)
        with server.db() as c:
            c.execute(SCHEMA);c.execute('DELETE FROM outgoing_queue_archives')
            self.batch,self.ids=Fixture.add_batch(c,'2026-09-01',[{'qty':10}])
            Fixture.add_opening(c,30)
        self.scope=dict(contractor='NT-A',**{'from':'2026-09-01','to':'2026-09-30'})
        self.url='/api/outgoing-invoices/queue-archive'

    def post(self,**body):
        return self.client.post(self.url,json={**self.scope,**body})
    def hide(self):
        p=self.post().json
        r=self.post(action='hide',token=p['token'],confirmed=True)
        self.assertEqual(200,r.status_code,r.json)
        return r.json

    def test_queue_download_and_invoice_inputs_exclude_archived_but_business_is_intact(self):
        with server.db() as c:
            tables=('orders','batches','receivable_ledger_lines','payable_ledger_lines','invoice_inventory_ledger')
            before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in tables}
        r=self.hide()
        download=self.client.get('/api/outgoing-invoices/unissued-template.zip',query_string=self.scope)
        self.assertEqual(400,download.status_code)
        self.assertIn('Phần cũ đã được bỏ',download.json['error'])
        with server.db() as c:
            self.assertEqual(set(self.ids),archived_order_ids(c))
            self.assertFalse(unissued_payload(c,'2026-09-30','NT-A',respect_export_choices=True)['details'])
            self.assertFalse(line_choices_payload(c,'2026-09-30','NT-A'))
            orders=[dict(r) for r in c.execute('SELECT * FROM orders')]
            self.assertFalse(selected_orders(c,orders))
            with self.assertRaises(OutgoingReadinessError):validate_demand_orders(c,orders)
            for t,rows in before.items():self.assertEqual(rows,[tuple(r) for r in c.execute('SELECT * FROM '+t)],t)
            _,new=Fixture.add_batch(c,'2026-09-02',[{'qty':2}])
            self.assertEqual(new,[r['id'] for r in selected_orders(c,[dict(r) for r in c.execute('SELECT * FROM orders')])])
        self.assertTrue(self.post(action='restore',id=r['id'],confirmed=True).json['ok'])
        self.assertEqual(2,self.post().json['rows'])

    def test_local_reservations_retire_remote_snapshots_stay_and_refresh_does_not_recreate(self):
        created=self.client.post(f'/api/outgoing-invoices/draft/{self.batch}')
        self.assertEqual(200,created.status_code,created.json)
        with server.db() as c:
            did=c.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
        self.hide()
        with server.db() as c:
            self.assertEqual('cancelled',c.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?',(did,)).fetchone()[0])
            self.assertFalse(c.execute("SELECT 1 FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND status='reserved'").fetchone())
            refresh_waiting(c,server.now_iso(),fill=True)
            self.assertFalse(c.execute("SELECT 1 FROM outgoing_invoice_drafts WHERE status='draft'").fetchone())

    def test_remote_draft_is_not_cancelled_or_released(self):
        self.client.post(f'/api/outgoing-invoices/draft/{self.batch}')
        with server.db() as c:
            c.execute("UPDATE outgoing_invoice_drafts SET minvoice_status='saved' WHERE status='draft'")
            before=[tuple(r) for r in c.execute('SELECT * FROM outgoing_invoice_drafts')]
            holds=[tuple(r) for r in c.execute('SELECT * FROM inventory_transactions')]
        result=self.hide();self.assertTrue(result['remote_drafts'])
        with server.db() as c:
            result=refresh_waiting(c,server.now_iso(),fill=True)
            self.assertFalse(result['warnings'],result)
            self.assertEqual(before,[tuple(r) for r in c.execute('SELECT * FROM outgoing_invoice_drafts')])
            self.assertEqual(holds,[tuple(r) for r in c.execute('SELECT * FROM inventory_transactions')])

    def test_confirmation_stale_review_and_changed_order_reappears(self):
        p=self.post().json
        self.assertEqual(409,self.post(action='hide',token=p['token']).status_code)
        with server.db() as c:c.execute('UPDATE orders SET sell_price=21 WHERE id=?',(self.ids[0],))
        self.assertEqual(409,self.post(action='hide',token=p['token'],confirmed=True).status_code)
        self.hide()
        with server.db() as c:
            c.execute('UPDATE orders SET actual_delivered=11 WHERE id=?',(self.ids[0],))
            self.assertFalse(archived_order_ids(c))
        self.assertEqual(1,self.post().json['rows'])

    def test_other_scope_and_restore_does_not_count_signed_quantity_twice(self):
        with server.db() as c:
            _,other=Fixture.add_batch(c,'2026-09-02',[{'qty':3,'contractor':'NT-B'}])
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Test','0101234567','Test',?)",(server.now_iso(),))
        r=self.hide()
        with server.db() as c:
            self.assertEqual(other,[o['id'] for o in selected_orders(c,[dict(r) for r in c.execute('SELECT * FROM orders')])])
            iid=Fixture.add_posted_source(c,source='minvoice',number='901',invoice_date='2026-09-03',qty=3)
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567' WHERE id=?",(iid,))
        self.post(action='restore',id=r['id'],confirmed=True)
        with server.db() as c:
            p=unissued_payload(c,'2026-09-30','NT-A')
            self.assertEqual(7,p['details'][0]['unissued_qty'])
            self.assertEqual(3,p['details'][0]['issued_qty'])

    def test_restore_also_restores_legacy_hidden_file_without_affecting_other_records(self):
        from .outgoing_download_archive import visible_payload
        endpoint='/api/outgoing-invoices/download-archive'
        p=self.client.post(endpoint,json=self.scope).json
        self.client.post(endpoint,json={**self.scope,'action':'hide','confirmed':True,'token':p['token']})
        # Queue preview includes rows previously hidden only from downloads.
        self.assertEqual(1,self.post().json['rows'])
        r=self.hide()
        self.post(action='restore',id=r['id'],confirmed=True)
        with server.db() as c:
            p=unissued_payload(c,'2026-09-30','NT-A',respect_export_choices=True)
            self.assertEqual(1,len(visible_payload(c,p)['details']))

if __name__=='__main__':unittest.main()
