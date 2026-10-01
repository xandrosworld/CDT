import sqlite3
import unittest
from .bk_history import print_source_status


class PurchasePrintSourceTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        self.conn.executescript('''CREATE TABLE batches(id INTEGER,work_date TEXT,status TEXT);
          CREATE TABLE bk_import_documents(id INTEGER,status TEXT);
          CREATE TABLE batch_bk_approvals(batch_id INTEGER,document_id INTEGER,source_hash TEXT);
          INSERT INTO batches VALUES(26,'2026-09-25','approved');''')
    def tearDown(self):self.conn.close()
    def status(self):return print_source_status(self.conn,dict(kind='purchases',selections=[dict(batch_id=26)]))
    def test_approved_order_is_not_stock_confirmation(self):
        before=list(self.conn.iterdump());result=self.status()
        self.assertFalse(result['items'][0]['posted'])
        self.assertEqual('orders',result['source'])
        self.assertIn('25/09/2026',result['items'][0]['message'])
        self.assertEqual(before,list(self.conn.iterdump()))
    def test_posted_reversed_and_missing_link(self):
        self.conn.executescript("INSERT INTO bk_import_documents VALUES(1,'posted'); INSERT INTO batch_bk_approvals VALUES(26,1,'hash');")
        self.assertTrue(self.status()['items'][0]['posted'])
        self.conn.execute("UPDATE bk_import_documents SET status='reversed'")
        self.assertFalse(self.status()['items'][0]['posted'])
        self.assertIn('hoàn tác',self.status()['items'][0]['message'])
        self.conn.execute('DELETE FROM bk_import_documents')
        self.assertFalse(self.status()['items'][0]['posted'])
