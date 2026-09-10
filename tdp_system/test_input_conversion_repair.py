import json
import unittest
from unittest.mock import patch
from .test_invoice_input_integrity import InputIntegrityTests as Seed
from .input_conversion_repair import init_schema,preview,save,ConversionError,apply_preference
from .invoice_mapping import save_conversion,validated_input_stock_snapshot,apply_saved_mappings
from .invoice_receipt import create_input_receipt
from .contract_modules import upsert_msmi_invoice
from .input_discount import preview as discount_preview,save as discount_save

NOW='2026-09-10 16:10:00'
class ConversionRepairTests(unittest.TestCase):
    setUp=Seed.setUp
    tearDown=Seed.tearDown
    map=Seed.map
    def prepare(self,discount=False):
        self.raw['hdhhdvu'][0].update(sluong=9,dvtinh='LOC',dgia=119444,thtien=1074996)
        self.raw.update(tgtcthue=1074996,tgtthue=0,tgtttbso=1074996)
        upsert_msmi_invoice(self.conn,self.raw,'INPUT_ELECTRONIC_INVOICE','TDP',NOW)
        self.item=self.conn.execute('SELECT id FROM msmi_invoice_items WHERE invoice_id=?',(self.iid,)).fetchone()[0]
        self.map()
        save_conversion(self.conn,direction='input',item_id=self.item,conversion_factor=12,now_iso=lambda:NOW)
        init_schema(self.conn)
        if discount:
            self.raw.update(ttcktmai=996,tgtcthue=1074000,tgtttbso=1074000)
            self.conn.execute('UPDATE msmi_invoices SET raw_json=?',(json.dumps(self.raw),))
            p=discount_preview(self.conn,self.iid)
            discount_save(self.conn,self.iid,{'expected_token':p['token'],'actor':'Test','amounts':[{'item_id':self.item,'discount':996}]},NOW)
        create_input_receipt(self.conn,self.iid,lambda:NOW);self.conn.commit()
        return preview(self.conn,self.item,'TDP',4)
    def body(self,p):return dict(token=p['token'],factor=p['factor'],actor='Test',reason='1 lốc có 4 hộp theo khách xác nhận',remember=True,confirmed=True)
    def write(self,p):
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            return save(self.conn,self.item,'TDP',self.body(p),NOW)
    def test_corrects_posted_quantity_cost_and_source_is_unchanged(self):
        p=self.prepare();self.assertEqual((108,36,1074996),(p['old_qty'],p['qty'],p['amount']))
        before=self.conn.execute('SELECT raw_json FROM msmi_invoices').fetchone()[0]
        before_dump=list(self.conn.iterdump());preview(self.conn,self.item,'TDP',4)
        self.assertEqual(before_dump,list(self.conn.iterdump()))
        result=self.write(p);self.assertTrue(result['saved'])
        self.assertEqual((36,29861),tuple(self.conn.execute('SELECT qty_in,unit_cost FROM inventory_transactions').fetchone()))
        self.assertEqual((36,29861),tuple(self.conn.execute('SELECT qty_delta,unit_cost FROM invoice_inventory_ledger').fetchone()))
        self.assertEqual(before,self.conn.execute('SELECT raw_json FROM msmi_invoices').fetchone()[0])
        self.assertEqual(1074996,self.conn.execute('SELECT amount FROM msmi_invoice_items').fetchone()[0])
        self.assertEqual(4,validated_input_stock_snapshot(self.conn,self.item)['conversion_factor'])
        self.assertTrue(self.write(p)['idempotent'])
        self.assertTrue(create_input_receipt(self.conn,self.iid,lambda:NOW)['idempotent'])
    def test_wrong_factor_stale_tenant_and_lock_rejected(self):
        p=self.prepare()
        for factor in (0,-1,'NaN','Infinity',True,'oops'):
            with self.subTest(factor=factor),self.assertRaises(ConversionError):preview(self.conn,self.item,'TDP',factor)
        with self.assertRaises(ConversionError):preview(self.conn,self.item,'OTHER',4)
        self.conn.execute('UPDATE msmi_invoices SET updated_at=?',('changed',));self.conn.commit()
        with self.assertRaises(ConversionError):self.write(p)
        self.conn.execute("INSERT INTO inventory_transactions(txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,status,created_at,updated_at) VALUES('2026-09-01','P1',1,0,100,'OPENING','2026-09','P1','posted',?,?)",(NOW,NOW));self.conn.commit()
        with self.assertRaises(ConversionError):preview(self.conn,self.item,'TDP',4)
    def test_audit_failure_rolls_back_every_change(self):
        p=self.prepare()
        self.conn.execute("CREATE TRIGGER fail_repair BEFORE INSERT ON audit_log WHEN NEW.event_type='invoice_input.posted_conversion' BEGIN SELECT RAISE(ABORT,'forced'); END");self.conn.commit()
        before=list(self.conn.iterdump())
        with self.assertRaises(Exception):self.write(p)
        self.assertEqual(before,list(self.conn.iterdump()))
    def test_discount_preserved_and_future_preference_does_not_rewrite_old(self):
        p=self.prepare(discount=True);self.write(p)
        self.assertEqual(1074000,validated_input_stock_snapshot(self.conn,self.item)['amount'])
        self.assertTrue(discount_preview(self.conn,self.iid)['saved'])
        apply_saved_mappings(self.conn,'input',self.iid)
        self.assertEqual(4,validated_input_stock_snapshot(self.conn,self.item)['conversion_factor'])
        raw=json.loads(json.dumps(self.raw));raw['_id']='NEW-REMEMBER';raw['shdon']=999999
        iid=upsert_msmi_invoice(self.conn,raw,'INPUT_ELECTRONIC_INVOICE','TDP',NOW)[0]
        self.assertNotEqual(self.iid,iid)
        item=self.conn.execute('SELECT id FROM msmi_invoice_items WHERE invoice_id=?',(iid,)).fetchone()[0]
        self.assertTrue(apply_preference(self.conn,item))
        self.assertEqual(4,validated_input_stock_snapshot(self.conn,item)['conversion_factor'])

    def test_downstream_monthly_cost_is_recomputed_without_changing_output_invoice(self):
        from .test_invoice_repairs import InvoiceRepairTests
        from .input_conversion_repair import monthly
        self.prepare()
        iid=InvoiceRepairTests.downstream_output(self,'P1')
        self.conn.commit()
        source=[tuple(r) for r in self.conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=?',(iid,))]
        p=preview(self.conn,self.item,'TDP',4)
        self.assertGreater(p['after']['output_value'],p['before']['output_value'])
        self.assertAlmostEqual(p['before']['closing_value']+p['before']['output_value'],p['after']['closing_value']+p['after']['output_value'],places=2)
        self.write(p)
        day=self.conn.execute('SELECT invoice_date FROM msmi_invoices WHERE id=?',(self.iid,)).fetchone()[0]
        self.assertEqual(p['after'],monthly(self.conn,'P1',day))
        self.assertEqual(source,[tuple(r) for r in self.conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=?',(iid,))])

    def test_closed_month_and_changed_mapping_revision_are_blocked(self):
        from .inventory_period_close import init_inventory_period_close_schema
        self.prepare();init_inventory_period_close_schema(self.conn)
        self.conn.execute("INSERT INTO inventory_period_closures(period,next_period,status,source_hash,target_hash,updated_at) VALUES('2026-08','2026-09','closed','a','b',?)",(NOW,));self.conn.commit()
        with self.assertRaisesRegex(ConversionError,'chốt'):preview(self.conn,self.item,'TDP',4)
        self.conn.execute("UPDATE inventory_period_closures SET status='reopened'")
        self.conn.execute('UPDATE invoice_inventory_ledger SET mapping_revision_id=NULL');self.conn.commit()
        with self.assertRaisesRegex(ConversionError,'Lịch sử'):preview(self.conn,self.item,'TDP',4)

