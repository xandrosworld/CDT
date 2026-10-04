import unittest
from . import server
from . import test_outgoing_upload as fixtures


class ExportReceiptTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.OutgoingUploadTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.OutgoingUploadTests.tearDownClass.__func__)
    business=fixtures.OutgoingUploadTests.business
    export=fixtures.OutgoingUploadTests.export

    def setUp(self):
        fixtures.OutgoingUploadTests.setUp(self)
        with server.db() as c:c.execute('DELETE FROM outgoing_export_receipts')

    def report(self):
        r=self.client.get('/api/outgoing-invoices/unissued?from=2026-09-01&to=2026-09-30&contractor=NT-A')
        self.assertEqual(r.status_code,200,r.json)
        return r.json

    def test_receipt_only_after_success_and_reopen_preserves_business(self):
        before=self.business()
        plan=self.client.post('/api/outgoing-invoice-upload/stock-preview?to=2026-09-30&contractor=NT-A').json
        response=self.export(plan['token']);self.assertEqual(response.status_code,200)
        token=response.headers['X-Export-Receipt']
        self.assertTrue(all(not r['downloaded_qty'] for r in self.report()['line_choices']))
        ack=self.client.post('/api/outgoing-invoices/export-receipts/'+token+'/received')
        self.assertEqual(ack.status_code,200)
        self.assertEqual(sum(r['downloaded_qty'] for r in self.report()['line_choices']),8)
        self.assertEqual(sum(r['issued_qty'] for r in self.report()['line_choices']),0)
        saved=self.client.get('/api/outgoing-invoices/export-receipts/'+token+'/file')
        self.assertEqual(saved.data,response.data)
        self.assertEqual(before,self.business())
        with server.db() as c:c.execute("UPDATE outgoing_invoice_drafts SET status='cancelled'")
        self.assertTrue(all(not r['downloaded_qty'] for r in self.report()['line_choices']))

    def test_partial_export_keeps_missing_quantity_and_choices(self):
        with server.db() as c:
            c.execute("UPDATE inventory_transactions SET qty_in=4 WHERE source_type='OPENING'")
        before=self.business()
        plan=self.client.post('/api/outgoing-invoice-upload/stock-preview?to=2026-09-30&contractor=NT-A').json
        response=self.export(plan['token']);self.assertEqual(response.status_code,200)
        self.client.post('/api/outgoing-invoices/export-receipts/'+response.headers['X-Export-Receipt']+'/received')
        rows=self.report()['line_choices']
        self.assertEqual(sum(r['downloaded_qty'] for r in rows),4)
        self.assertEqual(sum(r['qty']-r['downloaded_qty'] for r in rows),4)
        self.assertTrue(all(r['enabled'] for r in rows))
        self.assertEqual(before,self.business())
