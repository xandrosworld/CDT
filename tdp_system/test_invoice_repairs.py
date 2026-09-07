import sqlite3
import unittest

from .invoice_repairs import correct_unused_product_unit, correct_input_line_product
from .invoice_mapping import save_mapping, apply_saved_mappings, validated_input_stock_snapshot
from .test_invoice_input_sync import init_test_database, now_iso
from .test_msmi_sync import remote_invoice
from .contract_modules import upsert_msmi_invoice


class InvoiceRepairTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');init_test_database(self.conn)
        self.conn.executemany('INSERT INTO products(code,name,unit) VALUES(?,?,?)',[
            ('H000001','Đậu phụ rán (cái)','Cái'),('H000002','Đậu phụ trắng (cái)','Kg')])
        self.remote=remote_invoice(1)
        self.remote['hdhhdvu'][0].update(dvtinh='Cái')
        self.i=upsert_msmi_invoice(self.conn,self.remote,'INPUT_ELECTRONIC_INVOICE','TDP',now_iso())[0]
        self.item=self.conn.execute('SELECT id FROM msmi_invoice_items').fetchone()[0]
        save_mapping(self.conn,direction='input',item_id=self.item,product_code='H000001',now_iso=now_iso)

    def tearDown(self):
        self.conn.close()

    def unit(self):
        correct_unused_product_unit(self.conn,code='H000002',expected_name='Đậu phụ trắng (cái)',expected_unit='Kg',unit='Cái',now=now_iso())

    def test_corrects_only_selected_line_preserving_source_and_survives_sync(self):
        self.unit()
        before=dict(self.conn.execute('SELECT * FROM msmi_invoice_items').fetchone())
        expected={k:before[k] for k in ('product_code','mapping_status','conversion_factor','source_unit','qty','amount')}
        correct_input_line_product(self.conn,item_id=self.item,expected=expected,code='H000002',now=now_iso())
        self.assertEqual('H000002',validated_input_stock_snapshot(self.conn,self.item)['product_code'])
        rule=self.conn.execute("SELECT product_code FROM invoice_line_mappings WHERE scope_key NOT LIKE 'selected-line:%'").fetchone()
        self.assertEqual('H000001',rule[0])
        upsert_msmi_invoice(self.conn,self.remote,'INPUT_ELECTRONIC_INVOICE','TDP',now_iso())
        apply_saved_mappings(self.conn,'input',self.i)
        row=self.conn.execute('SELECT * FROM msmi_invoice_items').fetchone()
        self.assertEqual('H000002',row['product_code'])
        for k in ('source_unit','source_item_name','qty','amount'):
            self.assertEqual(before[k],row[k])

    def test_rejects_unit_correction_after_code_used(self):
        save_mapping(self.conn,direction='input',item_id=self.item,product_code='H000002',now_iso=now_iso)
        with self.assertRaises(ValueError):self.unit()
        self.assertEqual('Kg',self.conn.execute("SELECT unit FROM products WHERE code='H000002'").fetchone()[0])


if __name__=='__main__':unittest.main()
