import copy
import json
import sqlite3
import unittest
from unittest.mock import Mock

from .minvoice_client import MinvoiceConfig, MinvoiceError
from .minvoice_portal import MinvoicePortalClient, normalize_portal_document, portal_status, portal_date
from .minvoice_account_archive import archive_legacy_test_account, fingerprint, TEST_HOST, ARCHIVE_SOURCE, archive_html
from .test_invoice_input_sync import init_test_database
from .invoice_output_sync import upsert_output_invoice, sync_output_batch
from .invoice_workbench import prepare_sync_batch
from .invoice_workbench_listing import invoice_range_payload, range_workbook
from .invoice_mapping import save_mapping, save_conversion, InvoiceMappingError


def document():
    return {"id": "00000000-0000-0000-0000-000000000001", "sellerTaxCode": "0202265016",
            "invoiceSerial": "1C26TYY", "invoiceNumber": 12, "invoiceDate": "2026-08-31T00:00:00",
            "invoiceStatus": 0, "sendTaxStatus": 4, "totalAmountWithoutVAT": 100000,
            "vatAmount": 8000, "totalAmount": 108000, "buyerTaxCode": "0200000000", "buyerLegalName": "Buyer",
            "invoiceDetail": [{"productCode": "A", "productName": "Goods", "unitCode": "Kg",
                               "quantity": 2, "unitPrice": 50000, "amount": 100000,
                               "amountWithoutVAT": 100000, "vatAmount": 8000, "vatCode": "8", "property": 1}]}


def client():
    return MinvoicePortalClient(MinvoiceConfig("https://0202265016.minvoice.net", "fixture", "fixture", api_mode="portal"))


class PortalTests(unittest.TestCase):
    def test_tenant_cookie_is_selected_before_login_and_profile_checked(self):
        c = client()
        def respond(method, path, **kw):
            if path.startswith("abp/multi-tenancy"):
                return {"success": True, "isActive": True, "tenantId": "tenant-fixture"}
            self.assertEqual([(x.name,x.value,x.domain) for x in c._cookies], [("__tenant","tenant-fixture","0202265016.minvoice.net")])
            if path == "account/login":
                self.assertEqual(kw['payload']['userNameOrEmailAddress'], "fixture")
                return {"result": 1}
            return {"currentUser": {"isAuthenticated": True}, "currentTenant": {"id": "tenant-fixture"}}
        c._portal_json = Mock(side_effect=respond)
        self.assertTrue(c.login())
        self.assertFalse(c.profile_status()['draft_save_available'])
        self.assertEqual(c._portal_json.call_count, 3)

    def test_wrong_tenant_or_unverified_session_fails_closed(self):
        for profile in [{"currentUser": {"isAuthenticated": True}, "currentTenant": {"id": "different"}}, {}]:
            c = client()
            c._portal_json = Mock(side_effect=[{"success": True,"isActive":True,"tenantId":"selected"},{"result":1},profile])
            with self.assertRaises(MinvoiceError): c.login()
            self.assertEqual(c._token, "")

    def test_does_not_send_credentials_to_unvalidated_url(self):
        for url in ['http://0202265016.minvoice.net', 'https://evil.test', 'https://0202265016.minvoice.net/#/hoa-don', 'https://user:pass@0202265016.minvoice.net']:
            with self.assertRaises(MinvoiceError): MinvoicePortalClient(MinvoiceConfig(url,'fixture','fixture',api_mode='portal'))

    def test_portal_enums_are_not_legacy_enums(self):
        expected = {0:'issued',1:'cancelled',2:'adjusted',3:'replaced',4:'unknown',5:'adjusted',6:'replaced',99:'unknown'}
        for code,status in expected.items(): self.assertEqual(portal_status(dict(invoiceStatus=code,sendTaxStatus=4))[1],status)
        for tax in [0,1,2,3,6]: self.assertEqual(portal_status(dict(invoiceStatus=0,sendTaxStatus=tax))[1],'draft')
        for tax in [None,5,99,True,'4']: self.assertEqual(portal_status(dict(invoiceStatus=0,sendTaxStatus=tax))[1],'unknown')

    def test_local_vietnam_dates_and_utc_edges(self):
        self.assertEqual(portal_date('2026-07-31T17:00:00Z'),'2026-08-01')
        self.assertEqual(portal_date('2026-08-31T00:00:00'),'2026-08-31')

    def test_fetch_page_checks_details_and_preserves_decimal_values(self):
        c=client(); c._token='fixture'; d=document()
        c._portal_json=Mock(side_effect=[{'items':[d],'totalCount':3},d])
        result=c.get_outgoing_invoices('2026-08-01','2026-08-31','1C26TYY',start=2,count=20)
        self.assertEqual(result['total'],3)
        self.assertEqual(result['data'][0]['details'][0]['inv_unitCode'],'Kg')
        self.assertIn('/detail',c._portal_json.call_args_list[1].args[1])
        params=c._portal_json.call_args_list[0].kwargs['params']
        self.assertEqual(params['SkipCount'],2)
        self.assertEqual(params['fromDate'],'2026-08-01')

    def test_rejects_other_company_date_serial_and_changed_totals(self):
        for key,val in [('sellerTaxCode','different'),('invoiceDate','2026-09-01'),('invoiceSerial','1C25TYY'),('totalAmount',123)]:
            c=client(); c._token='fixture'; d=document(); changed=dict(d,**{key:val})
            c._portal_json=Mock(side_effect=[{'items':[d],'totalCount':1},changed])
            with self.assertRaises(MinvoiceError): c.get_outgoing_invoices('2026-08-01','2026-08-31','1C26TYY')

    def test_invalid_pagination_and_missing_details_are_errors(self):
        for result in [{'items':[],'totalCount':1},{'items':[], 'totalCount':True},{'items':'wrong','totalCount':1}]:
            with self.assertRaises(MinvoiceError): MinvoicePortalClient._page(result,0)
        c=client();c._token='fixture';d=document();del d['invoiceDetail']
        c._portal_json=Mock(side_effect=[{'items':[d],'totalCount':1},d])
        with self.assertRaises(MinvoiceError):c.get_outgoing_invoices('2026-08-01','2026-08-31','1C26TYY')

    def test_cannot_fall_through_to_remote_write(self):
        c=client(); c._opener=Mock()
        with self.assertRaises(MinvoiceError):c.create_draft({},dry_run=False,confirm_remote_write=True)
        with self.assertRaises(MinvoiceError):c._portal_json('POST','app/invoice',payload={})
        with self.assertRaises(MinvoiceError):c._json('POST','InvoiceApi78/Save',{})
        c._opener.open.assert_not_called()


class ArchiveIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        init_test_database(self.conn)

    def tearDown(self): self.conn.close()

    def insert(self, remote):
        return upsert_output_invoice(self.conn,remote,tenant='TDP',now='2026-09-06T23:00:00',status_map={},status_fields=(),reference_fields=())[0]

    def listing(self):
        return invoice_range_payload(self.conn,tenant='TDP',invoice_type='output',date_from='2026-08-01',date_to='2026-08-31')

    def test_real_shape_normalization_repeat_sync_excel_and_no_stock(self):
        d=normalize_portal_document(document()); original=copy.deepcopy(d)
        batch,_=prepare_sync_batch(self.conn,tenant='TDP',source='minvoice',invoice_type='output',date_from='2026-08-01',date_to='2026-08-31',now_iso=lambda:'2026-09-06')
        c=Mock(spec=MinvoicePortalClient);c.is_test_environment=False
        c.get_invoice_series.return_value=[{'value':'1C26TYY','invoiceYear':26}]
        c.get_outgoing_invoices.return_value={'data':[d],'total':1}
        for _ in range(2):sync_output_batch(self.conn,c,batch['id'],lambda:'2026-09-06')
        payload=self.listing();self.assertEqual(payload['totals']['invoice_amount'],108000)
        self.assertEqual(payload['totals']['line_amount'],100000)
        self.assertEqual(payload['items'][0]['source_status_class'],'issued')
        self.assertEqual(payload['lines'][0]['source_item_name'],'Goods')
        self.assertEqual(payload['lines'][0]['source_unit'],'Kg')
        from openpyxl import load_workbook
        wb=load_workbook(range_workbook(payload));self.assertTrue(any('Goods' in list(row) for row in wb.active.values))
        self.assertEqual(self.conn.execute('select count(*) from invoice_inventory_ledger').fetchone()[0],0)
        self.assertEqual(d,original)

    def legacy(self):
        from .test_invoice_output_sync import documented_minvoice_invoice
        self.insert(documented_minvoice_invoice(1))
        return {str(r['id']):fingerprint(r) for r in self.conn.execute('select * from outgoing_source_invoices')}

    def test_amount_mismatch_blocks_stock_but_preserves_details(self):
        d=document();d['totalAmountWithoutVAT']=120000;d['totalAmount']=128000
        self.insert(normalize_portal_document(d));p=self.listing()
        self.assertEqual(p['totals']['invoice_amount'],128000)
        self.assertEqual(p['totals']['line_amount'],100000)
        self.assertEqual(p['items'][0]['stock_status'],'blocked')
        self.assertIn('lệch tổng',p['items'][0]['error_message'])

    def test_negative_portal_adjustment_is_visible_without_stock(self):
        d=document();d.update(invoiceStatus=2,totalAmountWithoutVAT=-100000,vatAmount=-8000,totalAmount=-108000)
        d['invoiceDetail'][0].update(quantity=-2,amount=-100000,amountWithoutVAT=-100000,vatAmount=-8000)
        self.insert(normalize_portal_document(d));p=self.listing()
        self.assertEqual(p['totals']['invoice_amount'],-108000)
        self.assertEqual(p['totals']['line_amount'],-100000)
        self.assertEqual(p['lines'][0]['qty'],-2)
        self.assertFalse(p['lines'][0]['inventory_eligible'])
        self.assertEqual(p['items'][0]['stock_status'],'blocked')

    def test_archive_preserves_source_rows_and_cannot_map_or_post(self):
        manifest=self.legacy();before=[tuple(r) for r in self.conn.execute('select * from outgoing_source_invoice_items')]
        result=archive_legacy_test_account(self.conn,manifest,previous_base_url=TEST_HOST,now='2026-09-06')
        self.assertEqual(result['archived_invoices'],1)
        self.assertEqual(self.listing()['totals']['invoice_count'],0)
        self.assertIn('chỉ xem',archive_html(self.conn))
        self.assertEqual([tuple(r) for r in self.conn.execute('select * from outgoing_source_invoice_items')],before)
        item=self.conn.execute('select id from outgoing_source_invoice_items').fetchone()[0]
        with self.assertRaises(InvoiceMappingError):save_mapping(self.conn,direction='output',item_id=item,product_code='A',now_iso=lambda:'now')
        with self.assertRaises(InvoiceMappingError):save_conversion(self.conn,direction='output',item_id=item,conversion_factor=1,now_iso=lambda:'now')
        from .invoice_inventory import post_output_invoice, InvoiceInventoryError
        invoice=self.conn.execute('select id from outgoing_source_invoices').fetchone()[0]
        with self.assertRaises(InvoiceInventoryError):post_output_invoice(self.conn,invoice,confirmed=True,now_iso=lambda:'now')
        self.insert(normalize_portal_document(document()))
        self.assertEqual(self.listing()['totals']['invoice_count'],1)

    def test_archive_stale_manifest_and_wrong_host_leave_everything_unchanged(self):
        manifest=self.legacy();self.conn.execute("update outgoing_source_invoices set updated_at='new'")
        for host in [TEST_HOST,'https://0202265016.minvoice.net']:
            with self.assertRaises(ValueError):archive_legacy_test_account(self.conn,manifest,previous_base_url=host,now='now')
        self.assertEqual(self.conn.execute('select source from outgoing_source_invoices').fetchone()[0],'minvoice')

    def test_account_switch_cannot_mix_old_and_new_connections(self):
        from .invoice_output_sync import InvoiceOutputSyncError
        manifest=self.legacy()
        batch,_=prepare_sync_batch(self.conn,tenant='TDP',source='minvoice',invoice_type='output',date_from='2026-08-01',date_to='2026-08-31',now_iso=lambda:'now')
        portal=client();portal._portal_json=Mock()
        with self.assertRaises(InvoiceOutputSyncError):sync_output_batch(self.conn,portal,batch['id'],lambda:'now')
        portal._portal_json.assert_not_called()
        archive_legacy_test_account(self.conn,manifest,previous_base_url=TEST_HOST,now='now')
        new_batch,_=prepare_sync_batch(self.conn,tenant='TDP',source='minvoice',invoice_type='output',date_from='2026-08-01',date_to='2026-08-31',now_iso=lambda:'now')
        from .minvoice_client import MinvoiceClient
        old=MinvoiceClient(MinvoiceConfig(TEST_HOST,'fixture','fixture',allow_test_environment=True))
        old._json=Mock()
        with self.assertRaises(InvoiceOutputSyncError):sync_output_batch(self.conn,old,new_batch['id'],lambda:'now')
        old._json.assert_not_called()

    def test_archive_audit_failure_rolls_back_and_refuses_portal_rows(self):
        manifest=self.legacy()
        self.conn.execute("CREATE TRIGGER fail_archive BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT,'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):archive_legacy_test_account(self.conn,manifest,previous_base_url=TEST_HOST,now='now')
        self.assertEqual(self.conn.execute('select source from outgoing_source_invoices').fetchone()[0],'minvoice')
        self.insert(normalize_portal_document(document()))
        manifest={str(r['id']):fingerprint(r) for r in self.conn.execute('select * from outgoing_source_invoices')}
        with self.assertRaises(ValueError):archive_legacy_test_account(self.conn,manifest,previous_base_url=TEST_HOST,now='now')
