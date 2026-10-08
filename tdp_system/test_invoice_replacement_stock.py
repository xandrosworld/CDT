import sqlite3
import unittest
from unittest.mock import patch
from .invoice_payment_replacements import stock_replacement_reviews,confirm_stock_replacement

class ReplacementStockTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.executescript('''
        CREATE TABLE outgoing_source_invoices(id INTEGER,invoice_number TEXT,buyer_name TEXT,total_amount REAL);
        INSERT INTO outgoing_source_invoices VALUES(1,'857','Buyer',100),(2,'888','Buyer',101);
        CREATE TABLE outgoing_source_invoice_items(invoice_id INTEGER,line_index INTEGER,source_item_code TEXT,source_unit TEXT,qty REAL,unit_price REAL,amount REAL,inventory_eligible INTEGER,product_code TEXT,mapping_status TEXT,stock_qty REAL);
        INSERT INTO outgoing_source_invoice_items VALUES(1,1,'A','Kg',2,50,100,1,'A','mapped',2),(2,1,'A','Kg',2,50,100,0,'','pending',2);
        CREATE TABLE invoice_inventory_effective_ledger(id INTEGER,source_invoice_table TEXT,source_invoice_id INTEGER,event_type TEXT,status TEXT,product_code TEXT,qty_delta REAL);
        INSERT INTO invoice_inventory_effective_ledger VALUES(1,'outgoing_source_invoices',1,'POST','posted','A',-2);
        CREATE TABLE audit_log(event_type TEXT,entity_type TEXT,entity_id TEXT,status TEXT,message TEXT,metadata_json TEXT,created_at TEXT);
        ''')
        self.patch=patch('tdp_system.invoice_payment_replacements.verified_replacements',return_value={1:2});self.patch.start()
    def tearDown(self):self.patch.stop();self.c.close()
    def test_confirm_keeps_existing_stock_once_and_invalidates_changes(self):
        review=stock_replacement_reviews(self.c)[2]
        before=list(self.c.execute('SELECT * FROM invoice_inventory_effective_ledger'))
        with self.assertRaises(ValueError):confirm_stock_replacement(self.c,2,review['token'],False,'now')
        confirm_stock_replacement(self.c,2,review['token'],True,'now')
        confirm_stock_replacement(self.c,2,review['token'],True,'now')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0],1)
        self.assertEqual(before,list(self.c.execute('SELECT * FROM invoice_inventory_effective_ledger')))
        self.assertTrue(stock_replacement_reviews(self.c)[2]['confirmed'])
        self.c.execute('UPDATE outgoing_source_invoice_items SET qty=3 WHERE invoice_id=2')
        self.assertEqual(stock_replacement_reviews(self.c),{})
    def test_reversed_or_changed_stock_cannot_be_retained(self):
        self.c.execute("UPDATE invoice_inventory_effective_ledger SET qty_delta=-1")
        self.assertEqual(stock_replacement_reviews(self.c),{})
