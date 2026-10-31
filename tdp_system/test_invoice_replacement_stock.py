import sqlite3
import unittest
from unittest.mock import patch
from .invoice_payment_replacements import stock_replacement_reviews,confirm_stock_replacement,replacement_difference_reviews

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

    def test_changed_quantity_is_explained_without_authorizing_stock_changes(self):
        self.c.executescript('''
        ALTER TABLE outgoing_source_invoices ADD COLUMN buyer_tax_code TEXT DEFAULT 'TAX';
        ALTER TABLE outgoing_source_invoices ADD COLUMN invoice_date TEXT DEFAULT '2026-10-31';
        ALTER TABLE outgoing_source_invoice_items ADD COLUMN source_item_name TEXT DEFAULT 'Product A';
        CREATE TABLE outgoing_buyer_profiles(contractor TEXT,tax_code TEXT);
        INSERT INTO outgoing_buyer_profiles VALUES('NT-A','TAX');
        UPDATE outgoing_source_invoice_items SET qty=1,amount=50 WHERE invoice_id=2;
        ''')
        before = self.c.serialize()
        reviews = replacement_difference_reviews(self.c)
        self.assertEqual(reviews[1], reviews[2])
        self.assertEqual(reviews[2]['contractor'], 'NT-A')
        self.assertEqual(len(reviews[2]['changes']), 1)
        self.assertEqual((reviews[2]['changes'][0]['old_qty'], reviews[2]['changes'][0]['new_qty']), (2, 1))
        self.assertEqual(stock_replacement_reviews(self.c), {})
        self.assertEqual(before, self.c.serialize())

    def test_confirmation_survives_reinserted_details_and_download_metadata(self):
        self.c.execute('ALTER TABLE outgoing_source_invoice_items ADD COLUMN id INTEGER')
        self.c.execute('ALTER TABLE outgoing_source_invoices ADD COLUMN raw_json TEXT')
        self.c.execute('ALTER TABLE outgoing_source_invoices ADD COLUMN synced_at TEXT')
        self.c.execute('UPDATE outgoing_source_invoice_items SET id=invoice_id')
        review=stock_replacement_reviews(self.c)[2]
        confirm_stock_replacement(self.c,2,review['token'],True,'now')
        before=list(self.c.execute('SELECT * FROM invoice_inventory_effective_ledger'))
        for attempt in range(3):
            row=dict(self.c.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=2').fetchone())
            self.c.execute('DELETE FROM outgoing_source_invoice_items WHERE invoice_id=2')
            row['id']=100+attempt
            self.c.execute('INSERT INTO outgoing_source_invoice_items('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
            self.c.execute('UPDATE outgoing_source_invoices SET raw_json=?,synced_at=?',
                           ('{"downloadMetadata":'+str(attempt)+'}',str(attempt)))
            after=stock_replacement_reviews(self.c)[2]
            self.assertEqual(after['token'],review['token'])
            self.assertTrue(after['confirmed'])
        self.assertEqual(before,list(self.c.execute('SELECT * FROM invoice_inventory_effective_ledger')))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0],1)

    def test_changed_totals_or_buyer_require_fresh_confirmation(self):
        review=stock_replacement_reviews(self.c)[2]
        confirm_stock_replacement(self.c,2,review['token'],True,'now')
        self.c.execute('UPDATE outgoing_source_invoices SET total_amount=102 WHERE id=2')
        self.assertFalse(stock_replacement_reviews(self.c)[2]['confirmed'])
        with self.assertRaises(ValueError):confirm_stock_replacement(self.c,2,review['token'],True,'later')
        self.c.execute("UPDATE outgoing_source_invoices SET total_amount=101,buyer_name='Changed' WHERE id=2")
        self.assertFalse(stock_replacement_reviews(self.c)[2]['confirmed'])

    def test_changed_posted_mapping_cannot_keep_old_confirmation(self):
        review=stock_replacement_reviews(self.c)[2]
        confirm_stock_replacement(self.c,2,review['token'],True,'now')
        self.c.execute("UPDATE outgoing_source_invoice_items SET product_code='B' WHERE invoice_id=1")
        self.assertEqual(stock_replacement_reviews(self.c),{})
