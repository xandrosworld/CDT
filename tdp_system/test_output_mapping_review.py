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
from .invoice_output_mapping import match_output_catalog_codes
from .invoice_mapping import apply_saved_mappings, save_mapping, save_conversion, register_invoice_mapping_routes, InvoiceMappingError
from .invoice_inventory import post_output_invoice, InvoiceInventoryError
from .invoice_workbench_listing import invoice_range_payload

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

    def listing(self, **filters):
        return invoice_range_payload(self.conn, tenant='TDP', invoice_type='output',
                                     date_from='2026-08-01', date_to='2026-08-31', **filters)

    def match(self):
        return match_output_catalog_codes(self.conn, tenant='TDP', now_iso=lambda:NOW,
                                          date_from='2026-08-01', date_to='2026-08-31')

    def test_amount_review_auto_matches_exact_code_without_releasing_hold(self):
        header = dict(self.header())
        original = dict(self.conn.execute('SELECT * FROM outgoing_source_invoice_items').fetchone())
        self.assertEqual(self.match()['matched_lines'], 1)
        row = dict(self.conn.execute('SELECT * FROM outgoing_source_invoice_items').fetchone())
        self.assertEqual((row['product_code'],row['mapping_status'],row['stock_qty']), ('A','mapped',2))
        for key in ('source_item_code','source_item_name','source_unit','qty','unit_price','amount'):
            self.assertEqual(row[key], original[key])
        self.assertEqual(dict(self.header()), header)
        self.assertEqual(self.listing()['totals']['issue_count'], 0)
        self.assertEqual(len(self.listing()['amount_reviews']), 1)
        with self.assertRaises(InvoiceInventoryError):
            post_output_invoice(self.conn,self.iid,confirmed=True,now_iso=lambda:NOW)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0],0)
        saved = list(self.conn.iterdump())
        self.assertEqual(self.match()['matched_lines'], 0)
        self.assertEqual(list(self.conn.iterdump()), saved)

    def test_auto_match_restores_existing_rule_without_overwriting_a_chosen_row(self):
        save_mapping(self.conn,direction='output',item_id=self.item,product_code='A',now_iso=lambda:NOW)
        self.conn.execute("UPDATE outgoing_source_invoice_items SET product_code='',mapping_status='unmapped',"
                          "conversion_factor=NULL,stock_qty=0,stock_unit_price=0")
        self.assertEqual(self.match()['matched_lines'],1)
        self.assertEqual(self.conn.execute('SELECT product_code FROM outgoing_source_invoice_items').fetchone()[0],'A')
        # A row with a choice is never overwritten by the automatic action.
        self.conn.execute("UPDATE outgoing_source_invoice_items SET product_code='CUP'")
        before=list(self.conn.iterdump())
        self.assertEqual(self.match()['matched_lines'],0)
        self.assertEqual(list(self.conn.iterdump()),before)

    def test_auto_match_does_not_restore_expired_or_ambiguous_rules(self):
        save_mapping(self.conn,direction='output',item_id=self.item,product_code='A',now_iso=lambda:NOW)
        self.conn.execute("UPDATE outgoing_source_invoice_items SET product_code='',mapping_status='unmapped',"
                          "conversion_factor=NULL,stock_qty=0,stock_unit_price=0")
        self.conn.execute("UPDATE invoice_line_mappings SET effective_from='2026-09-01'")
        before=list(self.conn.iterdump())
        self.assertEqual(self.match()['matched_lines'],0)
        self.assertEqual(list(self.conn.iterdump()),before)

        self.conn.execute("UPDATE invoice_line_mappings SET effective_from=''")
        rule=dict(self.conn.execute('SELECT * FROM invoice_line_mappings').fetchone())
        rule.pop('id')
        rule.update(effective_from='2026-08-01',product_code='CUP')
        self.conn.execute('INSERT INTO invoice_line_mappings('+','.join(rule)+') VALUES('+','.join('?' for _ in rule)+')',
                          list(rule.values()))
        before=list(self.conn.iterdump())
        self.assertEqual(self.match()['matched_lines'],0)
        self.assertEqual(list(self.conn.iterdump()),before)

    def test_amount_review_auto_matches_unique_name_but_not_conflicting_code_or_name(self):
        for source_code, name, duplicate, expected in [
            ('', 'Goods', False, 1),
            ('', 'Goods', True, 0),
            ('A', 'Different goods', False, 0),
            ('UNKNOWN', 'Goods', False, 0),
        ]:
            with self.subTest(source_code=source_code,name=name,duplicate=duplicate):
                self.conn.execute('SAVEPOINT matching_case')
                self.conn.execute('UPDATE outgoing_source_invoice_items SET source_item_code=?,source_item_name=?',
                                  (source_code,name))
                if duplicate:
                    self.conn.execute("INSERT INTO products(code,name,unit) VALUES('DUP','Goods','Kg')")
                self.assertEqual(self.match()['matched_lines'], expected)
                self.assertEqual(self.header()['stock_status'],'blocked')
                self.conn.execute('ROLLBACK TO matching_case')
                self.conn.execute('RELEASE matching_case')

    def test_completed_line_is_clear_but_invoice_total_hold_remains(self):
        save_mapping(self.conn, direction='output', item_id=self.item, product_code='A', now_iso=lambda:NOW)
        before = list(self.conn.iterdump())
        data = self.listing()
        self.assertEqual(data['lines'][0]['issue'], '')
        self.assertEqual(data['totals']['issue_count'], 0)
        self.assertEqual(data['items'][0]['workbench_status'], 'error')
        self.assertEqual(data['items'][0]['stock_status'], 'blocked')
        self.assertEqual(data['counts']['ready'], 0)
        self.assertEqual(len(data['amount_reviews']), 1)
        self.assertEqual(data['amount_reviews'][0]['comparisons'], [
            {'kind':'subtotal', 'detail':100000, 'header':120000, 'difference':20000},
            {'kind':'tax', 'detail':8000, 'header':8000, 'difference':0},
            {'kind':'total', 'detail':108000, 'header':128000, 'difference':20000},
        ])
        for line_filter in ['needs_attention', 'error']:
            filtered = self.listing(line_filter=line_filter)
            self.assertEqual(filtered['lines'], [])
            self.assertEqual(filtered['amount_reviews'], data['amount_reviews'])
        self.assertEqual(self.listing(status='ready')['amount_reviews'], [])
        self.assertEqual(list(self.conn.iterdump()), before)
        with self.assertRaises(InvoiceInventoryError):
            post_output_invoice(self.conn, self.iid, confirmed=True, now_iso=lambda:NOW)

    def test_monetary_hold_does_not_hide_missing_code(self):
        data = self.listing()
        self.assertEqual(data['lines'][0]['issue'], 'Chưa ghép mã trong danh mục')
        self.assertEqual(data['totals']['issue_count'], 1)
        save_mapping(self.conn, direction='output', item_id=self.item, product_code='CUP', now_iso=lambda:NOW)
        self.assertEqual(self.listing()['lines'][0]['issue'], '')
        self.assertEqual(self.header()['stock_status'], 'blocked')

    def test_amount_summary_handles_tax_and_total_only_differences(self):
        for subtotal, tax, total in [(100000, 9000, 109000), (100000, 8000, 110000), (90000, 8000, 98000)]:
            raw = document()
            raw.update(totalAmountWithoutVAT=subtotal, vatAmount=tax, totalAmount=total)
            self.sync(raw)
            review = self.listing()['amount_reviews'][0]
            self.assertEqual([r['difference'] for r in review['comparisons']],
                             [subtotal - 100000, tax - 8000, total - 108000])
        self.sync(document())
        self.assertEqual(self.listing()['amount_reviews'], [])

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

    def test_different_units_need_only_code_and_preserve_amount(self):
        raw=document();raw['invoiceDetail'][0].update(productCode='',productName='Rau câu',unitCode='cái')
        self.iid=self.sync(raw);self.item=self.conn.execute('SELECT id FROM outgoing_source_invoice_items').fetchone()[0]
        save_mapping(self.conn,direction='output',item_id=self.item,product_code='CUP',now_iso=lambda:NOW)
        self.assertEqual(self.conn.execute('SELECT mapping_status FROM outgoing_source_invoice_items').fetchone()[0],'mapped')
        before=self.conn.execute('SELECT source_unit,qty,unit_price,amount FROM outgoing_source_invoice_items').fetchone()[:]
        self.conn.commit()
        response=self.client.put(f'/api/invoice-workbench/items/output/{self.item}/mapping',json={'product_code':'CUP'})
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
        self.assertEqual(response.status_code,409,response.json)
        self.assertEqual(response.json['code'],'output_code_only')
        self.assertEqual(list(self.conn.iterdump()),before)
        response=self.client.put(f'/api/invoice-workbench/items/output/{self.item}/mapping',json={'product_code':'CUP'})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.header()['stock_status'],'blocked')
        self.assertEqual(self.conn.execute('SELECT stock_qty FROM outgoing_source_invoice_items').fetchone()[0],2)

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
                self.assertEqual(self.match()['matched_lines'],0)
                with self.assertRaises(InvoiceMappingError):
                    save_mapping(self.conn,direction='output',item_id=self.item,product_code='A',now_iso=lambda:NOW)
                self.assertEqual(list(self.conn.iterdump()),before)

    def test_financial_message_does_not_allow_incomplete_or_changed_raw_source(self):
        for edit in [{'quantity':None},{'quantity':-1},{'quantity':'NaN'},{'property':3}]:
            raw=normalize_portal_document(deepcopy(self.raw));raw['invoiceDetail'][0].update(edit)
            row=dict(self.header());row['raw_json']=json.dumps(raw)
            self.assertFalse(output_mapping_allowed(row))
            self.conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',(row['raw_json'],self.iid))
            before=list(self.conn.iterdump())
            self.assertEqual(self.match()['matched_lines'],0)
            self.assertEqual(list(self.conn.iterdump()),before)
        row=dict(self.header());row['raw_json']='{}'
        self.assertFalse(output_mapping_allowed(row))
