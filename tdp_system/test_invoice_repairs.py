import sqlite3
import unittest
import json

from .invoice_repairs import correct_unused_product_unit, correct_input_line_product
from .invoice_mapping import save_mapping, apply_saved_mappings, validated_input_stock_snapshot
from .test_invoice_input_sync import init_test_database, now_iso
from .test_msmi_sync import remote_invoice
from .contract_modules import upsert_msmi_invoice
from .invoice_receipt import create_input_receipt
from .invoice_repairs import correct_unconsumed_posted_input_product
from .invoice_valuation import moving_average_report


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

    def posted_fixture(self):
        self.unit()
        create_input_receipt(self.conn, self.i, now_iso)
        self.conn.commit()
        self.conn.execute('BEGIN IMMEDIATE')
        return dict(self.conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?', (self.item,)).fetchone())

    def repair(self, expected):
        return correct_unconsumed_posted_input_product(self.conn, item_id=self.item,
            expected=expected, code='H000002', now=now_iso(), evidence={
                'file':'customer-input.xlsx', 'sha256':'a'*64, 'row':12,
                'reason':'Mã trên dòng nhập đã đối chiếu với chứng từ khách gửi'})

    def test_unused_posted_repair_preserves_money_source_and_repeat_receipt(self):
        before = self.posted_fixture()
        raw = self.conn.execute('SELECT raw_json FROM msmi_invoices WHERE id=?', (self.i,)).fetchone()[0]
        self.repair(before)
        after = dict(self.conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?', (self.item,)).fetchone())
        for k in ('source_item_code','source_item_name','source_unit','qty','unit_price','amount','tax_rate'):
            self.assertEqual(before[k], after[k])
        self.assertEqual('H000002', after['product_code'])
        self.assertEqual(raw, self.conn.execute('SELECT raw_json FROM msmi_invoices WHERE id=?', (self.i,)).fetchone()[0])
        create_input_receipt(self.conn, self.i, now_iso)
        self.assertEqual(1, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])
        report = moving_average_report(self.conn, date_from='2026-08-01', date_to='2026-08-31', include_zero=True)
        items = {r['product_code']:r for r in report['items']}
        self.assertEqual(0, items['H000001']['input_qty'])
        self.assertEqual(1, items['H000002']['input_qty'])
        self.assertEqual(10000, items['H000002']['input_value'])
        journal = json.loads(self.conn.execute("SELECT metadata_json FROM audit_log WHERE event_type='invoice_input.posted_product_correction'").fetchone()[0])
        self.assertEqual('H000001', journal['before']['event']['product_code'])
        self.assertEqual('H000002', journal['after']['event']['product_code'])
        with self.assertRaises(ValueError): self.repair(before)

    def test_repair_rejects_downstream_issue_on_either_product(self):
        before = self.posted_fixture()
        for code in ('H000001', 'H000002'):
            self.conn.execute("""INSERT INTO invoice_inventory_ledger
                (event_key,direction,event_type,source_invoice_table,source_invoice_id,source_line_id,
                source_line_index,product_code,txn_date,qty_delta,unit_cost,mapping_revision_id,
                confirmation_id,reverses_event_key,status,created_at)
                SELECT ?, 'output','POST','outgoing_source_invoices',99,99,1,?,txn_date,-0.1,
                unit_cost,mapping_revision_id,confirmation_id,'','posted',created_at
                FROM invoice_inventory_ledger WHERE direction='input'""", ('test-'+code, code))
            with self.assertRaisesRegex(ValueError,'giá vốn'): self.repair(before)
            self.conn.execute('DELETE FROM invoice_inventory_ledger WHERE event_key=?', ('test-'+code,))
        self.assertEqual('H000001', self.conn.execute('SELECT product_code FROM msmi_invoice_items WHERE id=?', (self.item,)).fetchone()[0])

    def test_repair_rejects_closed_period_or_inconsistent_stock(self):
        before = self.posted_fixture()
        self.conn.execute("""INSERT INTO inventory_transactions
            (txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,status,created_at,updated_at)
            VALUES('2026-09-01','H000001',1,0,10000,'OPENING','2026-09','1','posted',?,?)""", (now_iso(),now_iso()))
        with self.assertRaisesRegex(ValueError,'kỳ'): self.repair(before)
        self.conn.execute("DELETE FROM inventory_transactions WHERE source_type='OPENING'")
        self.conn.execute("UPDATE inventory_transactions SET qty_in=2 WHERE source_type='MSMI_INPUT'")
        with self.assertRaisesRegex(ValueError,'snapshot'): self.repair(before)

    def test_repair_rolls_back_if_audit_cannot_be_written(self):
        before = self.posted_fixture()
        self.conn.execute("""CREATE TEMP TRIGGER reject_repair_audit BEFORE INSERT ON audit_log
            WHEN NEW.event_type='invoice_input.posted_product_correction'
            BEGIN SELECT RAISE(ABORT,'audit unavailable'); END""")
        with self.assertRaises(sqlite3.IntegrityError): self.repair(before)
        self.assertEqual(before, dict(self.conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?', (self.item,)).fetchone()))
        self.assertEqual('posted', self.conn.execute('SELECT receipt_status FROM msmi_invoices WHERE id=?', (self.i,)).fetchone()[0])
        self.assertEqual('H000001', self.conn.execute('SELECT product_code FROM invoice_inventory_ledger').fetchone()[0])


if __name__=='__main__':unittest.main()
