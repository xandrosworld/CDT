from __future__ import annotations

import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from flask import Flask

from .invoice_mapping import apply_saved_mappings, save_mapping, validated_output_stock_snapshot
from .invoice_output_mapping import match_output_catalog_codes
from .invoice_output_sync import sync_output_batch
from .invoice_workbench import prepare_sync_batch, register_invoice_workbench_routes
from .test_invoice_input_sync import init_test_database
from .test_invoice_mapping import OutputFixtureMinvoice, now_iso
from .test_invoice_output_sync import STATUS_MAP, output_invoice


class OutputCatalogMappingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        init_test_database(self.conn)
        self.batch = prepare_sync_batch(self.conn, tenant='TDP', source='minvoice',
            invoice_type='output', date_from='2026-08-01', date_to='2026-08-31', now_iso=now_iso)[0]

    def tearDown(self):
        self.conn.close()

    def sync(self, code='I000127', unit='Kg', status='FIXTURE_ISSUED', number=1):
        remote = output_invoice(number, status=status)
        remote['hdhhdvu'][0].update(ma=code, ten='Quả quất', dvtinh=unit)
        return sync_output_batch(self.conn, OutputFixtureMinvoice([remote]), self.batch['id'],
            now_iso, status_map=STATUS_MAP, status_fields=['fixtureStatus'])

    def product(self, code='I000127', unit='kg'):
        self.conn.execute('INSERT INTO products(code,name,unit) VALUES(?,?,?)', (code, 'Quả quất', unit))

    def match(self, **kw):
        return match_output_catalog_codes(self.conn, now_iso=now_iso,
            **{'tenant':'TDP', 'date_from':'2026-08-01', 'date_to':'2026-08-31', **kw})

    def line(self):
        return self.conn.execute('SELECT * FROM outgoing_source_invoice_items ORDER BY id').fetchone()

    def test_sync_matches_exact_code_and_creates_valid_revision_without_posting(self):
        self.product()
        self.sync(' i000127 ')
        row = self.line()
        self.assertEqual(('I000127', 'mapped', 1), (row['product_code'], row['mapping_status'], row['conversion_factor']))
        snapshot = validated_output_stock_snapshot(self.conn, row['id'])
        self.assertEqual(row['qty'], snapshot['stock_qty'])
        self.assertGreater(snapshot['mapping_revision_id'], 0)
        self.assertEqual('ready', self.conn.execute('SELECT stock_status FROM outgoing_source_invoices').fetchone()[0])
        self.assertEqual(0, self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])
        self.sync(' i000127 ')
        self.assertEqual('mapped', self.line()['mapping_status'])
        self.assertEqual(1, self.conn.execute('SELECT COUNT(*) FROM invoice_line_mappings').fetchone()[0])

    def test_existing_rows_match_after_catalog_added_and_repeat_is_noop(self):
        self.sync()
        before = dict(self.line())
        self.assertEqual('unmapped', before['mapping_status'])
        self.product()
        self.assertEqual({'matched_lines':1, 'unit_review_lines':0}, self.match())
        for key in ('qty', 'unit_price', 'amount', 'source_item_code', 'source_item_name', 'source_unit'):
            self.assertEqual(before[key], self.line()[key])
        saved = list(self.conn.iterdump())
        self.assertEqual(0, self.match()['matched_lines'])
        self.assertEqual(saved, list(self.conn.iterdump()))

    def test_different_unit_does_not_assume_one(self):
        self.product()
        self.sync(unit='Hộp')
        row = self.line()
        self.assertEqual(('I000127','unit_review',None), (row['product_code'],row['mapping_status'],row['conversion_factor']))
        self.assertEqual(0, row['stock_qty'])
        self.assertEqual('pending_mapping', self.conn.execute('SELECT stock_status FROM outgoing_source_invoices').fetchone()[0])

    def test_unknown_or_ambiguous_code_does_not_match_by_name(self):
        self.product('OTHER')
        self.sync()
        self.assertEqual(0, self.match()['matched_lines'])
        self.product('I000127')
        self.product('i000127')
        self.assertEqual(0, self.match()['matched_lines'])
        self.assertEqual('unmapped', self.line()['mapping_status'])

    def test_manual_choice_and_other_period_rules_take_priority(self):
        self.product('MANUAL')
        self.sync()
        save_mapping(self.conn, direction='output', item_id=self.line()['id'], product_code='MANUAL', now_iso=now_iso)
        self.product()
        self.assertEqual(0, self.match()['matched_lines'])
        self.sync()
        self.assertEqual('MANUAL', self.line()['product_code'])
        self.conn.execute("UPDATE invoice_line_mappings SET effective_from='2026-09-01'")
        self.sync()
        self.assertEqual('unmapped', self.line()['mapping_status'])
        self.assertEqual(0, self.match()['matched_lines'])

    def test_unsafe_frozen_archived_and_other_tenant_are_untouched(self):
        self.sync()
        self.product()
        for field, value in [('stock_status','posted'), ('stock_status','reversed'),
                             ('stock_status','reversal_required'), ('source_status_class','draft'),
                             ('source','minvoice_test_0106026495_999'), ('tenant','OTHER')]:
            old = self.conn.execute('SELECT '+field+' FROM outgoing_source_invoices').fetchone()[0]
            self.conn.execute('UPDATE outgoing_source_invoices SET '+field+'=?', (value,))
            before = list(self.conn.iterdump())
            self.assertEqual(0, self.match()['matched_lines'])
            self.assertEqual(before, list(self.conn.iterdump()))
            self.conn.execute('UPDATE outgoing_source_invoices SET '+field+'=?', (old,))
        self.assertEqual(0, self.match(date_from='2026-09-01', date_to='2026-09-30')['matched_lines'])
        self.assertEqual(0, self.match(tenant='OTHER')['matched_lines'])

    def test_saved_mapping_cannot_change_posted_snapshot(self):
        self.product()
        self.sync()
        self.conn.execute("UPDATE outgoing_source_invoices SET stock_status='posted'")
        self.conn.execute('UPDATE invoice_line_mappings SET conversion_factor=2')
        before = dict(self.line())
        self.assertEqual(0, apply_saved_mappings(self.conn, 'output', before['invoice_id']))
        self.assertEqual(before, dict(self.line()))

    def test_route_validates_period_and_rolls_back_failed_bulk(self):
        self.sync()
        self.product()
        self.conn.commit()
        @contextmanager
        def db():
            with self.conn:
                yield self.conn
        app = Flask(__name__)
        app.config['TESTING'] = True
        register_invoice_workbench_routes(app, {'db':db, 'now_iso':now_iso,
            'setting_get':lambda conn,key,default='': default})
        client = app.test_client()
        path = '/api/invoice-workbench/output-match-codes'
        body = {'from':'2026-08-01', 'to':'2026-08-31'}
        self.assertEqual(400, client.post(path, json={}).status_code)
        self.assertEqual(400, client.post(path, json=['bad']).status_code)
        before = list(self.conn.iterdump())
        def fail_after_save(*args, **kwargs):
            save_mapping(*args, **kwargs)
            raise RuntimeError('test rollback')
        with patch('tdp_system.invoice_output_mapping.save_mapping', side_effect=fail_after_save):
            with self.assertRaises(RuntimeError):
                client.post(path, json=body)
        self.assertEqual(before, list(self.conn.iterdump()))
        result = client.post(path, json=body)
        self.assertEqual(200, result.status_code)
        self.assertEqual(1, result.json['matched_lines'])
        self.assertEqual(0, client.post(path, json=body).json['matched_lines'])


if __name__ == '__main__':
    unittest.main()
