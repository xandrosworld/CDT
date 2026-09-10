import json
import unittest
from decimal import Decimal
from .test_invoice_input_integrity import InputIntegrityTests as Seed
from .input_discount import preview,save,DiscountError,_auto,_validated
from .invoice_receipt import create_input_receipt,InvoiceReceiptError
from .invoice_receipt_bulk import receipt_review
from .invoice_input_sync import input_invoice_payload
from .invoice_workbench_listing import input_receipt_summary
from .invoice_input_integrity import receipt_cost_warning
from .invoice_mapping import save_mapping
from flask import Flask
from contextlib import contextmanager
from .input_discount import register_routes,init_schema

NOW='2026-09-10T15:00:00'
class DiscountTests(unittest.TestCase):
    setUp=Seed.setUp
    tearDown=Seed.tearDown
    map=Seed.map
    discount=Seed.discount
    def prepare(self):
        self.map();self.discount();return preview(self.conn,self.iid)
    def body(self,p):return {'expected_token':p['token'],'actor':'Test','amounts':[{'item_id':r['item_id'],'discount':r['discount']} for r in p['lines']]}

    def test_post_uses_net_cost_preserves_source_and_summary_and_is_idempotent(self):
        p=self.prepare();self.assertEqual((500,9500),(p['discount'],p['lines'][0]['net_amount']))
        before=[tuple(r) for r in self.conn.execute('SELECT qty,unit_price,amount FROM msmi_invoice_items')]
        token=receipt_review(self.conn,self.iid,'TDP')['token']
        save(self.conn,self.iid,self.body(p),NOW)
        self.assertEqual('',receipt_cost_warning(self.conn,self.iid))
        self.assertNotEqual(token,receipt_review(self.conn,self.iid,'TDP')['token'])
        self.assertEqual(9500,receipt_review(self.conn,self.iid,'TDP')['amount'])
        invoice=input_invoice_payload(self.conn,invoice_ids=[self.iid])['items'][0]
        self.assertEqual(9500,input_receipt_summary(invoice)['items'][0]['amount'])
        create_input_receipt(self.conn,self.iid,lambda:NOW)
        self.assertEqual((2,4750),tuple(self.conn.execute('SELECT qty_in,unit_cost FROM inventory_transactions').fetchone()))
        self.assertEqual(9500,self.conn.execute('SELECT SUM(qty_delta*unit_cost) FROM invoice_inventory_ledger').fetchone()[0])
        self.assertEqual(before,[tuple(r) for r in self.conn.execute('SELECT qty,unit_price,amount FROM msmi_invoice_items')])
        self.assertTrue(create_input_receipt(self.conn,self.iid,lambda:NOW)['idempotent'])
        with self.assertRaises(DiscountError):save(self.conn,self.iid,self.body(preview(self.conn,self.iid)),NOW)

    def test_manual_invalid_totals_negative_nonfinite_and_duplicates_rejected(self):
        p=self.prepare()
        for value in ('-1','501','499','NaN','Infinity','500.001'):
            body=self.body(p);body['amounts'][0]['discount']=value
            with self.subTest(value=value),self.assertRaises(DiscountError):save(self.conn,self.iid,body,NOW)
        body=self.body(p);body['amounts']*=2
        with self.assertRaises(DiscountError):save(self.conn,self.iid,body,NOW)
        self.assertEqual(0,self.conn.execute('SELECT count(*) FROM inventory_transactions').fetchone()[0])

    def test_source_change_and_concurrent_allocation_require_new_review(self):
        p=self.prepare();save(self.conn,self.iid,self.body(p),NOW)
        with self.assertRaises(DiscountError):save(self.conn,self.iid,self.body(p),NOW)
        self.conn.execute('UPDATE msmi_invoice_items SET qty=3 WHERE id=?',(self.item,))
        self.assertTrue(preview(self.conn,self.iid)['stale'])
        with self.assertRaises(InvoiceReceiptError):create_input_receipt(self.conn,self.iid,lambda:NOW)

    def test_source_already_net_not_discounted_twice(self):
        self.prepare();self.conn.execute('UPDATE msmi_invoice_items SET amount=9500');self.map()
        p=preview(self.conn,self.iid);self.assertEqual(0,p['discount']);self.assertFalse(p['can_save'])
        with self.assertRaises(DiscountError):save(self.conn,self.iid,self.body(p),NOW)
        create_input_receipt(self.conn,self.iid,lambda:NOW)
        self.assertEqual(9500,self.conn.execute('SELECT qty_in*unit_cost FROM inventory_transactions').fetchone()[0])

    def test_customer_amounts_round_exactly_and_zero_promotion_gets_zero(self):
        goods=[{'id':1,'amount':2403698,'line_index':1},{'id':2,'amount':0,'line_index':2},
               {'id':3,'amount':3388884,'line_index':3},{'id':4,'amount':0,'line_index':4}]
        values=_validated(goods,Decimal(273137),_auto(goods,Decimal(273137),None))
        self.assertEqual(Decimal(273137),sum(values.values()))
        self.assertEqual((0,0),(values[2],values[4]))
        self.assertEqual(Decimal(5519445),sum(Decimal(r['amount'])-values[r['id']] for r in goods))
        selected=_validated(goods,Decimal(273137),_auto(goods,Decimal(273137),[1]))
        self.assertEqual(Decimal(273137),selected[1]);self.assertEqual(0,selected[3])
        with self.assertRaises(DiscountError):_auto(goods,Decimal(273137),[2])
        for amount in ('0.03','1','999.99'):
            shares=_auto(goods,Decimal(amount),None)
            self.assertEqual(Decimal(amount),sum(Decimal(r['discount']) for r in shares))

    def test_mismatching_or_missing_source_total_cannot_be_allocated(self):
        self.prepare();self.discount(total=9800,subtotal=9000,tax=800)
        p=preview(self.conn,self.iid);self.assertTrue(p['error']);self.assertFalse(p['can_save'])
        with self.assertRaises(DiscountError):save(self.conn,self.iid,self.body(p),NOW)

    def test_routes_read_only_tenant_scope_and_atomic_audit_failure(self):
        p=self.prepare();init_schema(self.conn);self.conn.commit()
        @contextmanager
        def db():
            with self.conn: yield self.conn
        app=Flask(__name__);app.config['TESTING']=False
        register_routes(app,{'db':db,'now_iso':lambda:NOW,'setting_get':lambda c,k,d:'TDP'})
        client=app.test_client();url=f'/api/invoice-workbench/input-discount/{self.iid}'
        before=list(self.conn.iterdump())
        self.assertEqual(200,client.get(url).status_code)
        self.assertEqual(200,client.post(url,json={'selected':[self.item]}).status_code)
        self.assertEqual(before,list(self.conn.iterdump()))
        bad=self.body(p);bad['amounts'][0]['item_id']=[]
        self.assertEqual(409,client.put(url,json=bad).status_code)
        self.conn.execute("UPDATE msmi_invoices SET tenant='OTHER'");self.conn.commit()
        self.assertEqual(409,client.get(url).status_code)
        self.conn.execute("UPDATE msmi_invoices SET tenant='TDP'")
        self.conn.execute("CREATE TRIGGER fail_discount_audit BEFORE INSERT ON audit_log WHEN NEW.event_type='invoice_input.discount' BEGIN SELECT RAISE(ABORT,'test audit failure'); END")
        self.conn.commit()
        with self.assertLogs(app.logger,level='ERROR'):
            self.assertEqual(500,client.put(url,json=self.body(p)).status_code)
        self.assertEqual(0,self.conn.execute('SELECT count(*) FROM invoice_input_discounts').fetchone()[0])

    def test_small_fractional_amounts_do_not_overallocate_a_line(self):
        goods=[{'id':1,'amount':'.6','line_index':1},{'id':2,'amount':'.6','line_index':2}]
        values=_validated(goods,Decimal(1),_auto(goods,Decimal(1),None))
        self.assertEqual([Decimal('.5'),Decimal('.5')],list(values.values()))

    def test_excel_preserves_invoice_amount_and_exports_net_stock_cost(self):
        from .invoice_workbench import prepare_sync_batch
        from .invoice_input_export import input_invoice_export_data
        p=self.prepare();save(self.conn,self.iid,self.body(p),NOW)
        day=self.conn.execute('SELECT invoice_date FROM msmi_invoices WHERE id=?',(self.iid,)).fetchone()[0]
        batch,_=prepare_sync_batch(self.conn,tenant='TDP',source='msmi',invoice_type='input',date_from=day,date_to=day,now_iso=lambda:NOW)
        self.conn.execute('INSERT INTO invoice_sync_batch_invoices(batch_id,invoice_id,linked_at) VALUES(?,?,?)',(batch['id'],self.iid,NOW))
        line=input_invoice_export_data(self.conn,batch['id'])['lines'][0]
        self.assertEqual(10000,line['amount']);self.assertEqual(4750,line['stock_unit_price'])
