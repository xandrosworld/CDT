import sqlite3,unittest
from unittest.mock import patch
from .invoice_replacement_correction import quantity_correction_reviews,confirm_original_quantity

class QuantityCorrectionTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript('''
  CREATE TABLE outgoing_source_invoices(id INTEGER,invoice_number TEXT,buyer_name TEXT,total_amount REAL,invoice_date TEXT);
  INSERT INTO outgoing_source_invoices VALUES(1,'984','Buyer',100,'2026-10-30'),(2,'993','Buyer',30,'2026-10-31');
  CREATE TABLE products(code TEXT,unit TEXT); INSERT INTO products VALUES('A','Gói');
  CREATE TABLE outgoing_source_invoice_items(id INTEGER,invoice_id INTEGER,line_index INTEGER,source_item_code TEXT,source_item_name TEXT,source_unit TEXT,qty REAL,stock_qty REAL,inventory_eligible INTEGER,product_code TEXT,mapping_status TEXT);
  INSERT INTO outgoing_source_invoice_items VALUES(10,1,1,'A','Product','Gói',56,56,1,'A','mapped'),(20,2,1,'A','Product','Gói',13,13,0,'','pending');
  CREATE TABLE invoice_inventory_ledger(id INTEGER,source_invoice_table TEXT,source_invoice_id INTEGER,source_line_id INTEGER,event_type TEXT,direction TEXT,status TEXT,product_code TEXT,txn_date TEXT,qty_delta REAL,unit_cost REAL);
  INSERT INTO invoice_inventory_ledger VALUES(100,'outgoing_source_invoices',1,10,'POST','output','posted','A','2026-10-30',-56,20);
  CREATE TABLE output_stock_remaps(ledger_id INTEGER);
  CREATE TABLE output_stock_remap_parts(ledger_id INTEGER,product_code TEXT,qty REAL,unit_cost REAL,revision INTEGER,UNIQUE(ledger_id,product_code));
  CREATE TABLE audit_log(event_type TEXT,entity_type TEXT,entity_id TEXT,status TEXT,message TEXT,metadata_json TEXT,created_at TEXT);
  CREATE TABLE inventory_period_closures(period TEXT,status TEXT);
  CREATE TABLE inventory_transactions(source_type TEXT,status TEXT,txn_date TEXT);
  ''')
  self.p=patch('tdp_system.invoice_payment_replacements.verified_replacements',return_value={1:2});self.p.start()
 def tearDown(self):self.p.stop();self.c.close()
 def review(self):return quantity_correction_reviews(self.c)[2]
 def confirm(self,token=None,confirmed=True):return confirm_original_quantity(self.c,2,token or self.review()['token'],confirmed,'Ghi nhầm; thực giao 13 từ đầu','2026-10-31 16:00:00')
 def test_confirmation_corrects_once_preserves_source_and_survives_item_refresh(self):
  before=[tuple(r) for r in self.c.execute('SELECT * FROM invoice_inventory_ledger')]
  old=[tuple(r) for r in self.c.execute('SELECT * FROM outgoing_source_invoice_items')]
  token=self.review()['token']
  with self.assertRaises(ValueError):self.confirm(token,False)
  self.confirm(token);self.assertTrue(self.review()['confirmed']);self.assertTrue(self.confirm(token)['idempotent'])
  self.assertEqual(before,[tuple(r) for r in self.c.execute('SELECT * FROM invoice_inventory_ledger')])
  self.assertEqual(old,[tuple(r) for r in self.c.execute('SELECT * FROM outgoing_source_invoice_items')])
  self.assertEqual(self.c.execute('SELECT qty FROM output_stock_remap_parts').fetchone()[0],13)
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0],1)
  self.c.execute('UPDATE outgoing_source_invoice_items SET id=21 WHERE invoice_id=2')
  self.assertTrue(self.review()['confirmed'])
 def test_stale_source_and_closed_period_do_not_write(self):
  token=self.review()['token'];self.c.execute('UPDATE outgoing_source_invoice_items SET qty=14 WHERE invoice_id=2')
  with self.assertRaises(ValueError):self.confirm(token)
  self.c.execute("INSERT INTO inventory_period_closures VALUES('2026-10','closed')")
  with self.assertRaises(ValueError):self.confirm()
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM output_stock_remap_parts').fetchone()[0],0)
 def test_audit_failure_rolls_back_quantity(self):
  self.c.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT,'test'); END")
  with self.assertRaises(sqlite3.IntegrityError):self.confirm()
  self.assertEqual(self.c.execute('SELECT COUNT(*) FROM output_stock_remap_parts').fetchone()[0],0)
 def test_existing_remap_or_reversal_cannot_be_overwritten(self):
  self.c.execute('INSERT INTO output_stock_remaps VALUES(100)');self.assertEqual(quantity_correction_reviews(self.c),{})
  self.c.execute('DELETE FROM output_stock_remaps');self.c.execute("UPDATE invoice_inventory_ledger SET event_type='REVERSAL'")
  self.assertEqual(quantity_correction_reviews(self.c),{})
 def test_new_source_change_invalidates_confirmation(self):
  self.confirm();self.c.execute('UPDATE outgoing_source_invoice_items SET qty=12 WHERE invoice_id=2')
  self.assertEqual(quantity_correction_reviews(self.c),{})
 def test_same_day_future_opening_blocks(self):
  self.c.execute("INSERT INTO inventory_transactions VALUES('OPENING','posted','2026-11-01')")
  with self.assertRaises(ValueError):self.confirm()
 def test_increase_or_conversion_never_uses_original_quantity_correction(self):
  self.c.execute('UPDATE outgoing_source_invoice_items SET qty=60 WHERE invoice_id=2')
  self.assertEqual(quantity_correction_reviews(self.c),{})
  self.c.execute('UPDATE outgoing_source_invoice_items SET qty=13 WHERE invoice_id=2')
  self.c.execute('UPDATE outgoing_source_invoice_items SET stock_qty=28 WHERE invoice_id=1')
  self.assertEqual(quantity_correction_reviews(self.c),{})
 def test_changed_overlay_invalidates_confirmation(self):
  self.confirm();self.c.execute('UPDATE output_stock_remap_parts SET qty=12')
  self.assertEqual(quantity_correction_reviews(self.c),{})
