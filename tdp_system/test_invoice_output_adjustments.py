import json
import sqlite3
import unittest
from contextlib import contextmanager
from copy import deepcopy

from flask import Flask

from .test_invoice_input_sync import init_test_database
from .test_minvoice_portal import document
from .minvoice_portal import normalize_portal_document, portal_document_role
from .invoice_output_sync import upsert_output_invoice
from .invoice_output_adjustments import adjustment_reviews, confirm_tax_adjustment, AdjustmentError, EVENT
from .invoice_workbench import register_invoice_workbench_routes
from .invoice_workbench_listing import invoice_range_payload
from .invoice_inventory import post_output_invoice, InvoiceInventoryError

NOW = '2026-09-08T23:40:00'


def adjustment_document(number, qty, tax):
    raw = document()
    raw.update(id=f'00000000-0000-0000-0000-{number:012d}',invoiceNumber=number,invoiceStatus=2,
               totalAmountWithoutVAT=qty*10000,vatAmount=tax,totalAmount=qty*10000+tax,
               relatedInvoiceId=f'10000000-0000-0000-0000-{number-10:012d}',relatedInvoiceNumber=str(number-10),
               relatedInvoiceSerial='C26TYY',relatedInvoiceDate='2026-07-31T00:00:00',relatedInvoiceProperty=2,
               invoiceNote='Xuất sai thuế suất hàng mặt hàng đá viên' if qty<0 else None)
    raw['invoiceDetail'][0].update(productCode='',productName='Đá viên',unitCode='túi' if qty<0 else 'Túi',
        quantity=qty,unitPrice=10000,amount=qty*10000,amountWithoutVAT=qty*10000,vatAmount=tax,vatCode='8' if tax else '-2')
    return raw


def seed_adjustments(conn, now=NOW):
    conn.execute("INSERT INTO products(code,name,unit) VALUES('K000035','Đá viên','Túi')")
    ids = []
    for raw in [adjustment_document(695,-887,0),adjustment_document(696,887,709600)]:
        ids.append(upsert_output_invoice(conn,normalize_portal_document(raw),tenant='TDP',now=now,
                                        status_map={},status_fields=(),reference_fields=())[0])
    return ids


class OutputAdjustmentTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');init_test_database(self.conn)
        self.ids=seed_adjustments(self.conn);self.conn.commit()
        @contextmanager
        def db():
            with self.conn:yield self.conn
        app=Flask(__name__);app.config['TESTING']=True
        register_invoice_workbench_routes(app,{'db':db,'now_iso':lambda:NOW,'setting_get':lambda c,k,d='':d})
        self.client=app.test_client()

    def tearDown(self):
        self.conn.close()

    def review(self):
        return adjustment_reviews(self.conn,'TDP')[self.ids[0]]

    def listing(self,**kw):
        return invoice_range_payload(self.conn,tenant='TDP',invoice_type='output',date_from='2026-08-01',date_to='2026-08-31',**kw)

    def confirm(self,**kw):
        return confirm_tax_adjustment(self.conn,tenant='TDP',invoice_id=self.ids[0],expected=self.review()['token'],
                                      confirmed=True,now=NOW,**kw)

    def test_source_document_roles_distinguish_originals(self):
        for code,role in [(2,'adjustment'),(3,'replacement'),(5,'adjusted_original'),(6,'replaced_original')]:
            self.assertEqual(portal_document_role({'invoiceStatus':code}),role)
        self.assertEqual(portal_document_role({'invoiceStatus':'2'}),'unknown')

    def test_read_only_review_shows_both_original_references_and_balanced_quantity(self):
        before=list(self.conn.iterdump());r=self.review()
        self.assertFalse(r['confirmed']);self.assertEqual(r['net_qty'],0)
        self.assertEqual(r['net_subtotal'],0);self.assertEqual(r['tax_difference'],709600)
        self.assertEqual([d['reference_number'] for d in r['documents']],['685','686'])
        self.assertEqual([d['lines'][0]['qty'] for d in r['documents']],[-887,887])
        data=self.listing();self.assertEqual(data['totals']['issue_count'],2)
        self.assertTrue(all(i['source_document_role']=='adjustment' for i in data['items']))
        self.assertEqual(before,list(self.conn.iterdump()))

    def test_confirm_marks_both_complete_with_no_source_or_stock_writes(self):
        tables=['outgoing_source_invoices','outgoing_source_invoice_items','invoice_inventory_ledger','products','invoice_line_mappings']
        before={t:[tuple(r) for r in self.conn.execute('SELECT * FROM '+t)] for t in tables}
        r=self.review();response=self.client.post(f'/api/invoice-workbench/output-adjustments/{self.ids[0]}/confirm-tax',
                                              json={'confirmed':True,'expected':r['token']})
        self.assertEqual(response.status_code,200,response.json);self.assertEqual(response.json['stock_qty_change'],0)
        for t in tables:self.assertEqual(before[t],[tuple(r) for r in self.conn.execute('SELECT * FROM '+t)])
        data=self.listing();self.assertEqual(data['totals']['issue_count'],0)
        self.assertEqual(data['counts']['not_inventory'],2);self.assertEqual(data['counts']['ready'],0)
        self.assertTrue(all(r['product_code']=='K000035' for r in data['lines']))
        self.assertEqual(self.listing(line_filter='needs_attention')['lines'],[])
        self.assertEqual(self.listing(scope='pending')['items'],[])
        self.assertEqual(data['totals']['line_amount'],0);self.assertEqual(data['totals']['invoice_amount'],709600)
        for i in self.ids:
            with self.assertRaises(InvoiceInventoryError):post_output_invoice(self.conn,i,confirmed=True,now_iso=lambda:NOW)
        self.conn.commit()
        preview=self.client.get('/api/invoice-workbench/output-postings?from=2026-08-01&to=2026-08-31').json
        self.assertEqual(preview['items'],[]);self.assertEqual(preview['blocked'],[])
        self.assertTrue(self.confirm()['idempotent'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM audit_log WHERE event_type=?',(EVENT,)).fetchone()[0],1)

    def test_confirmation_requires_explicit_choice_and_current_source(self):
        token=self.review()['token'];url=f'/api/invoice-workbench/output-adjustments/{self.ids[0]}/confirm-tax'
        for body in [{},{'confirmed':False,'expected':token},{'confirmed':True,'expected':'stale'},[]]:
            before=list(self.conn.iterdump());response=self.client.post(url,json=body)
            self.assertEqual(response.status_code,409);self.assertEqual(before,list(self.conn.iterdump()))
        with self.assertRaises(AdjustmentError):
            confirm_tax_adjustment(self.conn,tenant='OTHER',invoice_id=self.ids[0],expected=token,confirmed=True,now=NOW)

    def test_resync_preserves_confirmation_but_source_and_catalog_changes_revoke_it(self):
        self.confirm();token=self.review()['token']
        raw=adjustment_document(695,-887,0)
        upsert_output_invoice(self.conn,normalize_portal_document(raw),tenant='TDP',now=NOW,status_map={},status_fields=(),reference_fields=())
        self.assertEqual(self.review()['token'],token);self.assertTrue(self.review()['confirmed'])
        raw['invoiceNote']='Lý do nguồn đã thay đổi'
        upsert_output_invoice(self.conn,normalize_portal_document(raw),tenant='TDP',now=NOW,status_map={},status_fields=(),reference_fields=())
        self.assertFalse(self.review()['confirmed']);self.assertEqual(self.listing()['totals']['issue_count'],2)
        self.conn.execute("UPDATE products SET unit='Kg' WHERE code='K000035'")
        self.assertEqual(adjustment_reviews(self.conn,'TDP'),{})

    def test_unsafe_sources_posted_and_ambiguous_catalog_stay_blocked(self):
        for field,value in [('source','other'),('tenant','OTHER'),('source_status_class','replaced'),
                            ('stock_status','posted'),('stock_status','reversal_required'),('sync_status','review_required')]:
            self.conn.execute('SAVEPOINT unsafe')
            self.conn.execute('UPDATE outgoing_source_invoices SET '+field+'=? WHERE id=?',(value,self.ids[0]))
            self.assertEqual(adjustment_reviews(self.conn,'TDP'),{})
            self.conn.execute('ROLLBACK TO unsafe');self.conn.execute('RELEASE unsafe')
        self.conn.execute("INSERT INTO products(code,name,unit) VALUES('AMB','Đá viên','Túi')")
        self.assertEqual(adjustment_reviews(self.conn,'TDP'),{})

    def test_invalid_reference_tax_status_quantity_or_source_detail_never_forms_pair(self):
        original=json.loads(self.conn.execute('SELECT raw_json FROM outgoing_source_invoices WHERE id=?',(self.ids[0],)).fetchone()[0])
        edits=[{'invoiceStatus':s} for s in [1,3,5,6,'2']]+[{'sendTaxStatus':s} for s in [0,3,6,'4']]
        edits += [{'relatedInvoiceId':None},{'relatedInvoiceProperty':1},{'relatedInvoiceDate':'2026-09-30'},
                  {'totalAmount':0},{'buyerTaxCode':'OTHER'}]
        for edit in edits:
            raw={**original,**edit}
            self.conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',(json.dumps(raw),self.ids[0]))
            self.assertEqual(adjustment_reviews(self.conn,'TDP'),{},edit)
        for edit in [{'quantity':-888},{'quantity':None},{'unitPrice':-10000},{'property':3},{'productCode':'WRONG'}]:
            raw=deepcopy(original);raw['invoiceDetail'][0].update(edit)
            self.conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',(json.dumps(raw),self.ids[0]))
            self.assertEqual(adjustment_reviews(self.conn,'TDP'),{},edit)

    def test_multiple_possible_partners_and_nonzero_net_quantity_are_not_auto_paired(self):
        self.conn.execute('SAVEPOINT duplicate')
        raw=adjustment_document(697,887,709600)
        upsert_output_invoice(self.conn,normalize_portal_document(raw),tenant='TDP',now=NOW,status_map={},status_fields=(),reference_fields=())
        self.assertEqual(adjustment_reviews(self.conn,'TDP'),{})
        self.conn.execute('ROLLBACK TO duplicate');self.conn.execute('RELEASE duplicate')
        raw=adjustment_document(696,888,710400)
        upsert_output_invoice(self.conn,normalize_portal_document(raw),tenant='TDP',now=NOW,status_map={},status_fields=(),reference_fields=())
        self.assertEqual(adjustment_reviews(self.conn,'TDP'),{})

    def test_existing_ledger_prevents_confirmation_even_if_header_is_blocked(self):
        invoice_id=self.ids[0]
        line_id=self.conn.execute('SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=?',(invoice_id,)).fetchone()[0]
        confirmation_id=self.conn.execute("INSERT INTO invoice_inventory_confirmations "
            "(confirmation_key,direction,source_invoice_table,source_invoice_id,action,confirmed,created_at) "
            "VALUES('existing','output','outgoing_source_invoices',?,'post',1,?)",(invoice_id,NOW)).lastrowid
        self.conn.execute("INSERT INTO invoice_inventory_ledger "
            "(event_key,direction,event_type,source_invoice_table,source_invoice_id,source_line_id,source_line_index,"
            "product_code,txn_date,qty_delta,confirmation_id,created_at) "
            "VALUES('existing','output','POST','outgoing_source_invoices',?,?,1,'K000035','2026-08-05',-887,?,?)",
            (invoice_id,line_id,confirmation_id,NOW))
        self.assertEqual(adjustment_reviews(self.conn,'TDP'),{})

    def test_malformed_raw_documents_do_not_break_listing(self):
        for raw in [None,[],42,{'invoiceDetail':[None]}]:
            self.conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',(json.dumps(raw),self.ids[0]))
            self.assertEqual(adjustment_reviews(self.conn,'TDP'),{})
            self.assertEqual(self.listing()['totals']['issue_count'],2)
