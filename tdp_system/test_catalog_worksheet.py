"""Complete catalog edits preserve references, concurrency and transaction boundaries."""
import unittest
import uuid
from unittest.mock import patch

from . import test_catalog_product_create as fixture


class CatalogWorksheetTests(unittest.TestCase):
    def setUp(self):
        fixture.CatalogProductCreateTests.setUp(self)
        self.conn.execute("UPDATE products SET tax='0.08'")
        self.conn.commit()

    tearDown = fixture.CatalogProductCreateTests.tearDown

    def rows(self):
        return self.client.get('/api/catalog/worksheet').json['items']

    def change(self, row, **values):
        return dict(id=row['id'], revision=row['worksheet_revision'], values=values)

    def save(self, *changes, request_id=None):
        return self.client.put('/api/catalog/worksheet', json=dict(request_id=request_id or str(uuid.uuid4()), items=list(changes)))

    def seed(self):
        self.conn.executemany("INSERT INTO products(code,name,unit,tax) VALUES(?,?,'Kg','0.08')",
                              [(f'Z{i:04}', f'Catalog {i}') for i in range(1255 - len(self.rows()))])
        self.conn.commit()

    def test_complete_catalog_last_row_and_search(self):
        self.seed()
        before = '\n'.join(self.conn.iterdump())
        rows = self.rows()
        self.assertEqual(1255, len(rows))
        listed = self.client.get('/api/catalog/products?all=1').json
        self.assertEqual([r['code'] for r in rows], [r['code'] for r in listed['items']])
        self.assertEqual(before, '\n'.join(self.conn.iterdump()))
        last = rows[-1]
        response = self.save(self.change(last, name='Last edited', tax='5%', invoice_name='=literal text'))
        self.assertEqual(200, response.status_code, response.json)
        self.assertEqual('Last edited', self.rows()[-1]['name'])
        self.assertEqual('5%', self.rows()[-1]['tax'])
        self.assertEqual('=literal text', self.rows()[-1]['invoice_name'])
        self.assertEqual(1, self.client.get('/api/catalog/products?all=1&q=Last%20edited').json['total'])

    def test_bulk_save_atomic_invalid_and_used_unit(self):
        self.seed()
        rows = self.rows()
        used = next(r for r in rows if r['code']=='R1-KG')
        for values in [dict(name=''), dict(tax='9%'), dict(unit='Can')]:
            before = '\n'.join(self.conn.iterdump())
            result = self.save(self.change(rows[-1], name='Should roll back'), self.change(used, **values))
            self.assertIn(result.status_code, (400,409), result.json)
            self.assertEqual(before, '\n'.join(self.conn.iterdump()))

    def test_retry_and_conflicting_retry(self):
        row = self.rows()[0]
        request_id = str(uuid.uuid4())
        change = self.change(row, name='New catalog name')
        first = self.save(change, request_id=request_id)
        self.assertEqual(200, first.status_code, first.json)
        before = '\n'.join(self.conn.iterdump())
        self.assertEqual(first.json, self.save(change, request_id=request_id).json)
        self.assertEqual(before, '\n'.join(self.conn.iterdump()))
        self.assertEqual(409, self.save(self.change(row, name='Different'), request_id=request_id).status_code)

    def test_stale_revision_blocks_whole_paste(self):
        self.seed()
        rows = self.rows()
        self.assertEqual(200, self.save(self.change(rows[-1], name='Other person')).status_code)
        before = '\n'.join(self.conn.iterdump())
        result = self.save(self.change(rows[0], name='First'), self.change(rows[-1], name='Stale'))
        self.assertEqual(409, result.status_code)
        self.assertEqual(before, '\n'.join(self.conn.iterdump()))

    def test_code_and_duplicate_rows_are_rejected(self):
        row = self.rows()[0]
        before = '\n'.join(self.conn.iterdump())
        self.assertEqual(400, self.save(self.change(row, code='NEW')).status_code)
        change = self.change(row, name='Same')
        self.assertEqual(409, self.save(change, change).status_code)
        self.assertEqual(before, '\n'.join(self.conn.iterdump()))

    def test_unused_unit_and_multirow_edits(self):
        self.seed()
        rows = self.rows()[-2:]
        response = self.save(*(self.change(r, unit='Can', tax='10%', invoice_name='Invoice '+r['code']) for r in rows))
        self.assertEqual(200, response.status_code, response.json)
        self.assertTrue(all(r['unit']=='Can' and r['tax']=='10%' for r in self.rows()[-2:]))

    def test_audit_failure_rolls_back_every_row_and_request(self):
        self.seed()
        before = '\n'.join(self.conn.iterdump())
        with self.assertLogs(level='ERROR'), patch('tdp_system.contract_modules.audit', side_effect=RuntimeError('audit failure')):
            result = self.save(self.change(self.rows()[-1], name='Failure'))
        self.assertEqual(500, result.status_code)
        self.assertEqual(before, '\n'.join(self.conn.iterdump()))
