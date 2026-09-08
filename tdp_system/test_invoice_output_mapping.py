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

    def sync(self, code='I000127', unit='Kg', status='FIXTURE_ISSUED', number=1,
             name='Quả quất', buyer='0209999999'):
        remote = output_invoice(number, status=status)
        remote['mstNmua'] = buyer
        remote['hdhhdvu'][0].update(ma=code, ten=name, dvtinh=unit)
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

    def test_missing_code_matches_unique_name_unit_and_keeps_source_blank(self):
        self.product()
        self.sync(code='')
        row=self.line()
        self.assertEqual(('', 'I000127', 'mapped', 1),
                         (row['source_item_code'],row['product_code'],row['mapping_status'],row['conversion_factor']))
        self.assertEqual(0,self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0])
        before=list(self.conn.iterdump());self.match()
        self.assertEqual(before,list(self.conn.iterdump()))

    def test_invoice_alias_matches_without_overriding_ambiguous_or_different_units(self):
        self.product()
        self.conn.execute("UPDATE products SET name='Tên danh mục riêng'")
        self.conn.execute("INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES('I000127','  QUẢ   QUẤT  ',?)",(now_iso(),))
        self.sync(code='')
        self.assertEqual('I000127',self.line()['product_code'])

    def test_missing_code_does_not_guess_ambiguous_name_or_conversion(self):
        self.product()
        self.product('OTHER')
        self.sync(code='')
        self.assertEqual('unmapped',self.line()['mapping_status'])
        self.conn.execute("DELETE FROM products WHERE code='OTHER'")
        self.conn.execute("UPDATE products SET unit='Thùng'")
        self.assertEqual(0,self.match()['matched_lines'])
        self.assertEqual('unmapped',self.line()['mapping_status'])

    def test_missing_code_preserves_manual_choice_and_frozen_lines(self):
        self.sync(code='')
        self.product('MANUAL')
        save_mapping(self.conn,direction='output',item_id=self.line()['id'],product_code='MANUAL',now_iso=now_iso)
        self.product()
        before=list(self.conn.iterdump());self.match()
        self.assertEqual(before,list(self.conn.iterdump()))
        self.conn.execute("UPDATE invoice_line_mappings SET effective_from='2026-09-01'")
        self.sync(code='')
        self.assertEqual('unmapped',self.line()['mapping_status'])
        before=list(self.conn.iterdump());self.match()
        self.assertEqual(before,list(self.conn.iterdump()))

    def test_unknown_or_ambiguous_code_does_not_match_by_name(self):
        self.product('OTHER')
        self.sync()
        self.assertEqual(0, self.match()['matched_lines'])
        self.product('I000127')
        self.product('i000127')
        self.assertEqual(0, self.match()['matched_lines'])
        self.assertEqual('unmapped', self.line()['mapping_status'])

    def test_unique_canonical_name_wins_over_shared_invoice_alias(self):
        self.product()
        self.conn.execute("INSERT INTO products(code,name,unit) VALUES('VARIANT','Quả quất loại to','Kg')")
        self.conn.execute("INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES('VARIANT','Quả quất',?)", (now_iso(),))
        self.sync(code='')
        self.assertEqual('I000127', self.line()['product_code'])

    def test_confirmed_short_name_reused_for_another_buyer_and_is_idempotent(self):
        self.product()
        self.sync(name='Quất', buyer='FIRST')
        self.sync(code='', name='Quất', buyer='SECOND', number=2)
        rows=self.conn.execute('SELECT * FROM outgoing_source_invoice_items ORDER BY id').fetchall()
        self.assertEqual(['I000127','I000127'], [r['product_code'] for r in rows])
        self.assertEqual('',rows[1]['source_item_code'])
        validated_output_stock_snapshot(self.conn,rows[1]['id'])
        before=list(self.conn.iterdump());self.match()
        self.assertEqual(before,list(self.conn.iterdump()))

    def test_conflicting_buyer_choices_do_not_teach_other_buyers(self):
        self.product()
        self.product('OTHER')
        self.sync(name='Quất',buyer='FIRST')
        self.sync(code='OTHER',name='Quất',buyer='SECOND',number=2)
        self.sync(code='',name='Quất',buyer='THIRD',number=3)
        rows=self.conn.execute('SELECT product_code FROM outgoing_source_invoice_items ORDER BY id').fetchall()
        self.assertEqual(['I000127','OTHER',''],[r[0] for r in rows])

    def test_history_cannot_override_a_conflicting_canonical_name(self):
        self.product()
        self.conn.execute("INSERT INTO products(code,name,unit) VALUES('OTHER','Tên khác','Kg')")
        self.sync(code='OTHER',buyer='FIRST')
        self.sync(code='',buyer='SECOND',number=2)
        self.assertEqual('',self.conn.execute('SELECT product_code FROM outgoing_source_invoice_items ORDER BY id DESC').fetchone()[0])

    def test_history_requires_valid_revision_current_unit_and_active_period(self):
        for scenario in ('revision','unit','expired','factor'):
            with self.subTest(scenario=scenario):
                self.conn.execute('SAVEPOINT scenario')
                self.product()
                self.sync(name='Quất',buyer='FIRST')
                if scenario=='revision':self.conn.execute('DELETE FROM invoice_mapping_revisions')
                if scenario=='unit':self.conn.execute("UPDATE products SET unit='Hộp'")
                if scenario=='expired':self.conn.execute("UPDATE invoice_line_mappings SET effective_to='2026-08-01'")
                if scenario=='factor':self.conn.execute('UPDATE invoice_line_mappings SET conversion_factor=2')
                self.sync(code='',name='Quất',buyer='SECOND',number=2)
                self.assertEqual('',self.conn.execute('SELECT product_code FROM outgoing_source_invoice_items ORDER BY id DESC').fetchone()[0])
                self.conn.execute('ROLLBACK TO scenario');self.conn.execute('RELEASE scenario')

    def test_blocked_source_with_known_code_remains_untouched(self):
        self.sync()
        self.product()
        self.conn.execute("UPDATE outgoing_source_invoices SET sync_status='review_required',stock_status='blocked',error_message='Nguồn lệch tổng'")
        before=list(self.conn.iterdump());self.match()
        self.assertEqual(before,list(self.conn.iterdump()))

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
