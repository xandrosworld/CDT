import copy
import unittest
from unittest.mock import patch, Mock
from . import server, test_outgoing_review as fixture
from .minvoice_client import MinvoiceError, MinvoiceOutcomeUnknown
from .minvoice_portal import MinvoicePortalClient
from .test_minvoice_portal import client as portal_client
from .outgoing_source_refresh import refresh_sources
from .outgoing_unissued import issued_allocations
from .receivable_ledger import sync_receivable_ledger
from .invoice_payment_scope import issued_invoice_payment_scope


class PortalFixture(MinvoicePortalClient):
    def __init__(self):
        super().__init__(portal_client().config)
        self._token='fixture';self._can_create=True;self.documents=[];self.posts=0;self.lose_response=False

    def _portal_json(self,method,path,**kw):
        if method=='POST':
            assert path=='app/invoice' and kw.get('allow_draft_write') is True
            self._guard_unsigned_payload(kw['payload']);self.posts+=1
            p=copy.deepcopy(kw['payload']);p['id']='00000000-0000-0000-0000-000000000001'
            p.update(sendTaxStatus=1,keyApi=None)
            self.documents.append(p)
            if self.lose_response:raise OSError('Connection closed after accepted save')
            return p
        catalogs={
            'app/register-invoice/using-list':[{'id':'register','symbolCode':'1C26TYY','invoiceYear':26,'typeCompany':None}],
            'app/tenant-company':[{'id':'seller','taxCode':'0202265016','name':'TĐP','address':'Hải Phòng'}],
            'app/currency':[{'id':'currency','code':'VND'}],
            'app/payment-type':[{'id':'payment','name':'TM/CK'}],
            'app/tax':[{'id':'tax-'+v,'code':v,'name':v+'%','taxValue':max(0,float(v))} for v in ['-2','-1','0','5','8','10']],
        }
        if path in catalogs:return {'items':catalogs[path],'totalCount':len(catalogs[path])}
        if path=='app/invoice':
            rows=self.documents
            key=kw.get('params',{}).get('OrderNumber')
            if key:rows=[r for r in rows if r['orderNumber']==key]
            return {'items':copy.deepcopy(rows),'totalCount':len(rows)}
        if path.endswith('/detail'):return copy.deepcopy(next(r for r in self.documents if r['id'] in path))
        raise AssertionError((method,path))


class PortalSendTests(unittest.TestCase):
    setUpClass=classmethod(fixture.InvoiceReviewTests.setUpClass.__func__)
    tearDownClass=classmethod(fixture.InvoiceReviewTests.tearDownClass.__func__)

    def setUp(self):
        fixture.InvoiceReviewTests.setUp(self)
        self.remote=PortalFixture();server.app.config['MINVOICE_CLIENT_FACTORY']=lambda:self.remote
        with server.db() as c:
            c.execute("INSERT INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Khách kiểm thử','0209999999','Địa chỉ','now')")
            for k,v in {'company':'TĐP','company_tax_code':'0202265016','company_address':'Hải Phòng','payment_requester':'Thụy','payment_bank_name':'VCB','payment_bank_account':'123'}.items():
                server.setting_set(c,k,v)
            sync_receivable_ledger(c,timestamp=server.now_iso())

    def tearDown(self):server.app.config.pop('MINVOICE_CLIENT_FACTORY',None)

    def prepare(self):
        data=self.client.get('/api/outgoing-invoices/unissued',query_string=self.period).json
        body={**self.period,'scope':'approved_range','invoice_date':'2026-09-14','review_confirmed':True,
              'review_rows':[{'order_id':r['order_id'],'token':r['token']} for r in data['line_choices']]}
        r=self.client.post('/api/outgoing-invoices/prepare',json=body)
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['remote_write'],False)
        return r.json['items'][0]

    def send(self,item,dry=True):
        return self.client.post(f"/api/outgoing-invoices/prepared/{item['id']}/send",json={
            'review_token':item['token'],'series':'1C26TYY','dry_run':dry,'confirm_remote_write':not dry})

    def business(self):
        result=fixture.InvoiceReviewTests.business(self)
        result.pop('invoice_inventory_ledger')
        return result

    def test_draft_send_signed_sync_preserves_exact_order_links_and_stock_once(self):
        before=self.business();item=self.prepare()
        self.assertEqual(item['invoice_date'],'2026-09-14')
        preview=self.send(item);self.assertEqual(preview.status_code,200,preview.json);self.assertEqual(self.remote.posts,0)
        sent=self.send(item,False);self.assertEqual(sent.status_code,200,sent.json)
        self.assertEqual(self.remote.documents[0]['buyerTaxCode'],'0209999999')
        self.assertEqual(self.remote.posts,1)
        again=self.send(item,False);self.assertTrue(again.json['idempotent']);self.assertEqual(self.remote.posts,1)
        self.assertEqual(self.business(),before)
        with server.db() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM invoice_inventory_ledger WHERE direction='output'").fetchone()[0],0)
        waiting=refresh_sources(server.db,lambda:self.remote,server.now_iso,'2026-09-01','2026-09-14')
        self.assertEqual(waiting['sync']['error_count'],0)
        listing=self.client.get('/api/invoice-workbench/invoices?invoice_type=output&from=2026-09-14&to=2026-09-14&status=all').json
        self.assertEqual(listing['items'][0]['workbench_status'],'draft')
        self.assertEqual(listing['totals']['issue_count'],0)
        self.assertFalse(listing['items'][0]['can_edit_mapping'])
        with server.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM invoice_inventory_ledger WHERE direction='output'").fetchone()[0],0)
            self.assertEqual(c.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?',(item['id'],)).fetchone()[0],'draft')
        # A real portal signs this same draft later. The test transport supplies
        # the signed provider response; no signing endpoint exists in our app.
        self.remote.documents[0].update(invoiceNumber=88,sendTaxStatus=4,dateSign='2026-09-14T13:00:00',taxAuthorityCode='fixture')
        for _ in range(2):
            report=refresh_sources(server.db,lambda:self.remote,server.now_iso,'2026-09-01','2026-09-14')
            self.assertEqual(report['blocked'],[],report)
            self.assertEqual(report['waiting']['warnings'],[],report)
            with server.db() as c:
                self.assertEqual(c.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?',(item['id'],)).fetchone()[0],'issued')
                posted=list(c.execute("SELECT product_code,qty_delta FROM invoice_inventory_ledger WHERE direction='output' AND status='posted'"))
                self.assertEqual([tuple(r) for r in posted],[('HH-01',-7)])
                quantities,warnings=issued_allocations(c)
                self.assertEqual(warnings,[])
                self.assertEqual(quantities.get(self.old[0],0),0,'Must not settle earlier unselected orders via FIFO')
                self.assertEqual([quantities.get(oid,0) for oid in self.ids[:2]],[3,4])
                self.assertEqual(c.execute("SELECT COUNT(*) FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",(str(item['id']),)).fetchone()[0],0)
                payment=issued_invoice_payment_scope(c,'NT-A','2026-09-14','2026-09-14')
                self.assertEqual(payment['totals']['total_amount'],140)
                self.assertEqual(len(payment['invoices']),1)
            self.assertEqual(self.business(),before)

    def test_ambiguous_response_reconciles_without_second_post(self):
        item=self.prepare();self.remote.lose_response=True
        r=self.send(item,False);self.assertEqual(r.status_code,409,r.json);self.assertTrue(r.json['reconcile_required'])
        self.assertEqual(self.remote.posts,1)
        reloaded=self.client.get('/api/outgoing-invoices/prepared',query_string=self.period).json
        item=reloaded['items'][0]
        self.assertEqual(item['minvoice_status'],'unknown')
        self.assertFalse(item['stale'])
        r=self.send(item,False);self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.remote.posts,1)

    def test_unsigned_source_with_bad_total_still_requires_review(self):
        item=self.prepare();self.assertEqual(self.send(item,False).status_code,200)
        self.remote.documents[0]['totalAmount']+=10
        report=refresh_sources(server.db,lambda:self.remote,server.now_iso,'2026-09-01','2026-09-14')
        self.assertGreater(report['sync']['error_count'],0)
        listing=self.client.get('/api/invoice-workbench/invoices?invoice_type=output&from=2026-09-14&to=2026-09-14&status=all').json
        self.assertEqual(listing['items'][0]['workbench_status'],'error')
        with server.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM invoice_inventory_ledger WHERE direction='output'").fetchone()[0],0)

    def test_prepare_requires_current_review_and_persists_preview(self):
        r=self.client.post('/api/outgoing-invoices/prepare',json={**self.period,'invoice_date':'2026-09-14','review_confirmed':True,'review_rows':[]})
        self.assertEqual(r.status_code,409,r.json)
        item=self.prepare()
        p=self.client.get('/api/outgoing-invoices/prepared',query_string=self.period).json
        self.assertEqual(p['items'][0]['id'],item['id'])
        self.assertFalse(p['items'][0]['stale'])
        with server.db() as c:c.execute("UPDATE outgoing_buyer_profiles SET address='Đã thay địa chỉ'")
        changed=self.client.get('/api/outgoing-invoices/prepared',query_string=self.period).json
        self.assertTrue(changed['items'][0]['stale'])
        self.assertEqual(self.send(changed['items'][0],False).status_code,409)
        self.assertEqual(self.remote.posts,0)

    def test_deleted_or_modified_order_invalidates_prepared_snapshot(self):
        for change in ['UPDATE orders SET sell_price=21 WHERE id=?','UPDATE orders SET unit=\'Hộp\' WHERE id=?']:
            with self.subTest(change=change):
                item=self.prepare()
                with server.db() as c:c.execute(change,(self.ids[0],))
                r=self.send(item,False);self.assertEqual(r.status_code,409,r.json)
                self.assertEqual(self.remote.posts,0)
                with server.db() as c:c.execute("UPDATE orders SET sell_price=20,unit='kg' WHERE id=?",(self.ids[0],))

    def test_missing_confirmation_and_bad_tokens_cannot_send(self):
        item=self.prepare()
        for body in [{'dry_run':False,'confirm_remote_write':False},
                     {'dry_run':False,'confirm_remote_write':True,'review_token':'forged'}]:
            r=self.client.post(f"/api/outgoing-invoices/prepared/{item['id']}/send",json={**body,'series':'1C26TYY'})
            self.assertIn(r.status_code,[400,409],r.json)
        self.assertEqual(self.remote.posts,0)

    def test_changed_signed_lines_do_not_silently_settle_original_orders(self):
        item=self.prepare();self.assertEqual(self.send(item,False).status_code,200)
        raw=self.remote.documents[0];raw.update(invoiceNumber=89,sendTaxStatus=4)
        raw['invoiceDetail'][0]['productName']='Khác tên đã gửi'
        report=refresh_sources(server.db,lambda:self.remote,server.now_iso,'2026-09-01','2026-09-14')
        self.assertTrue(report['blocked'])
        with server.db() as c:self.assertEqual(c.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?',(item['id'],)).fetchone()[0],'draft')

    def test_raw_portal_writes_signing_and_email_are_rejected(self):
        c=portal_client();c._opener=Mock()
        for method,path in [('POST','app/invoice'),('POST','app/invoice/sign'),('DELETE','app/invoice/id')]:
            with self.assertRaises(MinvoiceError):c._portal_json(method,path,payload={})
        c._opener.open.assert_not_called()
        item=self.prepare();p=self.send(item).json['payload']['data'][0]
        for field,value in [('sendEmail',True),('invoiceStatus',3),('sendTaxStatus',4),('invoiceNumber',1),('relatedInvoiceId','other')]:
            with self.assertRaises(MinvoiceError):self.remote._guard_unsigned_payload({**p,field:value})


if __name__=='__main__':unittest.main()
