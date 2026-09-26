import unittest
from . import server
from .test_outgoing_amount_settlement import AmountSettlementTests
from .outgoing_download_archive import SCHEMA,preview,visible_payload
from .outgoing_unissued import unissued_payload

class DownloadArchiveTests(AmountSettlementTests):
    def setUp(self):
        super().setUp()
        with server.db() as c:
            c.execute(SCHEMA);c.execute('DELETE FROM outgoing_download_archives')

    def test_hide_restore_preserves_accounts_and_new_orders(self):
        scope={k:self.body[k] for k in ('contractor','from','to')}
        endpoint='/api/outgoing-invoices/download-archive'
        with server.db() as c:
            before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in ('orders','invoice_inventory_ledger','outgoing_invoice_drafts','receivable_ledger_lines')}
        p=self.client.post(endpoint,json=scope).json
        self.assertEqual(1,p['rows'])
        self.assertEqual(409,self.client.post(endpoint,json={**scope,'action':'hide','token':p['token']}).status_code)
        self.assertTrue(self.client.post(endpoint,json={**scope,'action':'hide','token':p['token'],'confirmed':True}).json['ok'])
        downloaded=self.client.get('/api/outgoing-invoices/unissued-template.zip',query_string=scope)
        self.assertEqual(400,downloaded.status_code)
        self.assertIn('đã ẩn phần cũ',downloaded.json['error'])
        self.assertTrue(self.client.get('/api/outgoing-invoices/unissued',query_string=scope).json['details'])
        with server.db() as c:
            raw=unissued_payload(c,scope['to'],scope['contractor'],start=scope['from'],respect_export_choices=True)
            self.assertTrue(raw['details'])
            self.assertFalse(visible_payload(c,raw)['details'])
            for t,rows in before.items():self.assertEqual(rows,[tuple(r) for r in c.execute('SELECT * FROM '+t)])
            c.execute('UPDATE orders SET actual_delivered=11 WHERE id=?',(self.orders[0],))
            self.assertEqual(1,preview(c,scope)['rows'])
            c.execute('UPDATE orders SET actual_delivered=10 WHERE id=?',(self.orders[0],))
        h=self.client.post(endpoint,json=scope).json['history'][0]['id']
        self.assertTrue(self.client.post(endpoint,json={'action':'restore','id':h,'confirmed':True}).json['ok'])
        self.assertEqual(1,self.client.post(endpoint,json=scope).json['rows'])

    def test_changed_snapshot_cannot_hide_and_other_scope_untouched(self):
        scope={k:self.body[k] for k in ('contractor','from','to')}
        endpoint='/api/outgoing-invoices/download-archive'
        p=self.client.post(endpoint,json=scope).json
        with server.db() as c:c.execute('UPDATE orders SET sell_price=21 WHERE id=?',(self.orders[0],))
        self.assertEqual(409,self.client.post(endpoint,json={**scope,'action':'hide','token':p['token'],'confirmed':True}).status_code)

if __name__=='__main__':unittest.main()
