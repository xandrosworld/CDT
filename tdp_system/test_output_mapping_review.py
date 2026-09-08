import json
import sqlite3
import unittest
from contextlib import contextmanager
from copy import deepcopy

from flask import Flask
from .test_invoice_input_sync import init_test_database
from .test_minvoice_portal import document
from .minvoice_portal import normalize_portal_document
from .invoice_output_sync import upsert_output_invoice, output_invoice_payload
from .invoice_output_editing import output_mapping_allowed
from .invoice_mapping import apply_saved_mappings, save_mapping, save_conversion, register_invoice_mapping_routes, InvoiceMappingError
from .invoice_inventory import post_output_invoice, InvoiceInventoryError

NOW = '2026-09-08T20:00:00'


class OutputReviewMappingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        init_test_database(self.conn)
        self.conn.executemany('INSERT INTO products(code,name,unit) VALUES(?,?,?)',
                             [('A','Goods','Kg'), ('CUP','Rau câu','Cốc')])
        self.raw = document()
        self.raw.update(totalAmountWithoutVAT=120000,totalAmount=128000)
        self.iid = self.sync(self.raw)
        self.item = self.conn.execute('SELECT id FROM outgoing_source_invoice_items').fetchone()[0]
        @contextmanager
        def db():
            with self.conn:
                yield self.conn
        app = Flask(__name__)
        register_invoice_mapping_routes(app, {'db':db, 'now_iso':lambda:NOW})
        self.client = app.test_client()
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def sync(self, raw):
        iid = upsert_output_invoice(self.conn,normalize_portal_document(raw),tenant='TDP',now=NOW,
                                    status_map={},status_fields=(),reference_fields=())[0]
        apply_saved_mappings(self.conn,'output',iid)
        return iid

    def header(self):
        return self.conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(self.iid,)).fetchone()

    def test_amount_review_can_save_and_resync_but_cannot_post_stock(self):
        self.assertTrue(output_mapping_allowed(self.header()))
        before = dict(self.header())
        response = self.client.put(f'/api/invoice-workbench/items/output/{self.item}/mapping',json={'product_code':'A'})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['applied_lines'],1)
        self.assertEqual(self.conn.execute('SELECT product_code,mapping_status FROM outgoing_source_invoice_items').fetchone()[:],('A','mapped'))
        self.assertEqual(dict(self.header()),before)
        with self.assertRaises(InvoiceInventoryError) as error:
            post_output_invoice(self.conn,self.iid,confirmed=True,now_iso=lambda:NOW)
        self.assertEqual(error.exception.code,'output_not_ready')
        self.sync(self.raw)
        self.assertEqual(self.conn.execute('SELECT product_code,mapping_status FROM outgoing_source_invoice_items').fetchone()[:],('A','mapped'))
        payload=output_invoice_payload(self.conn,invoice_ids=[self.iid])['items'][0]
        self.assertTrue(payload['can_edit_mapping'])
        self.assertEqual(payload['stock_status'],'blocked')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0],0)

    def test_unit_review_saves_code_and_explicit_factor_together_preserving_amount(self):
        raw=document();raw['invoiceDetail'][0].update(productCode='',productName='Rau câu',unitCode='cái')
        self.iid=self.sync(raw);self.item=self.conn.execute('SELECT id FROM outgoing_source_invoice_items').fetchone()[0]
        save_mapping(self.conn,direction='output',item_id=self.item,product_code='CUP',now_iso=lambda:NOW)
        self.assertEqual(self.conn.execute('SELECT mapping_status FROM outgoing_source_invoice_items').fetchone()[0],'unit_review')
        before=self.conn.execute('SELECT source_unit,qty,unit_price,amount FROM outgoing_source_invoice_items').fetchone()[:]
        self.conn.commit()
        response=self.client.put(f'/api/invoice-workbench/items/output/{self.item}/mapping',json={'product_code':'CUP','conversion_factor':1})
        self.assertEqual(response.status_code,200,response.json)
        self.assertFalse(response.json['requires_unit_conversion'])
        self.assertEqual(self.conn.execute('SELECT mapping_status,stock_qty,stock_unit_price FROM outgoing_source_invoice_items').fetchone()[:],('mapped',2,50000))
        self.assertEqual(self.conn.execute('SELECT source_unit,qty,unit_price,amount FROM outgoing_source_invoice_items').fetchone()[:],before)
        self.sync(raw)
        self.assertEqual(self.conn.execute('SELECT conversion_factor,mapping_status FROM outgoing_source_invoice_items').fetchone()[:],(1,'mapped'))

    def test_review_code_and_factor_save_is_atomic_and_source_remains_blocked(self):
        self.conn.commit()
        before=list(self.conn.iterdump())
        response=self.client.put(f'/api/invoice-workbench/items/output/{self.item}/mapping',json={'product_code':'CUP','conversion_factor':0})
        self.assertEqual(response.status_code,400)
        self.assertEqual(list(self.conn.iterdump()),before)
        response=self.client.put(f'/api/invoice-workbench/items/output/{self.item}/mapping',json={'product_code':'CUP','conversion_factor':2})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.header()['stock_status'],'blocked')
        self.assertEqual(self.conn.execute('SELECT stock_qty FROM outgoing_source_invoice_items').fetchone()[0],4)

    def test_other_source_errors_and_frozen_states_remain_uneditable(self):
        original=dict(self.header())
        cases=[{'source_status_class':s} for s in ['cancelled','adjusted','replaced','draft','unknown']]
        cases += [{'stock_status':s} for s in ['posted','reversed','reversal_required']]
        cases += [{'error_message':'Nguồn đã thay đổi'}, {'source':'msmi'}, {'sync_status':'reconcile_required'}]
        for change in cases:
            with self.subTest(change=change):
                current={**original,**change}
                self.conn.execute('UPDATE outgoing_source_invoices SET '+','.join(k+'=?' for k in current if k!='id')+' WHERE id=?',
                                  [v for k,v in current.items() if k!='id']+[self.iid])
                self.assertFalse(output_mapping_allowed(self.header()))
                before=list(self.conn.iterdump())
                with self.assertRaises(InvoiceMappingError):
                    save_mapping(self.conn,direction='output',item_id=self.item,product_code='A',now_iso=lambda:NOW)
                self.assertEqual(list(self.conn.iterdump()),before)

    def test_financial_message_does_not_allow_incomplete_or_changed_raw_source(self):
        for edit in [{'quantity':None},{'quantity':-1},{'quantity':'NaN'},{'property':3}]:
            raw=normalize_portal_document(deepcopy(self.raw));raw['invoiceDetail'][0].update(edit)
            row=dict(self.header());row['raw_json']=json.dumps(raw)
            self.assertFalse(output_mapping_allowed(row))
        row=dict(self.header());row['raw_json']='{}'
        self.assertFalse(output_mapping_allowed(row))
