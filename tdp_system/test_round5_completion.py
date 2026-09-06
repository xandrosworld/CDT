"""Isolated acceptance checks for checklist 3/6/14; no customer DB/API writes."""
from __future__ import annotations

import hashlib
import io
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from openpyxl import load_workbook
from . import automatic_backup as backups, server, contract_modules
from .purchase_summary_export import collect_purchase_summary_rows, PurchaseSummaryError, aggregate_purchase_summary_rows
from .seller_identity_catalog import EXCLUDED_SELLERS, is_excluded_seller
from .test_selected_document_export import SelectedDocumentExportTests


class AutomaticBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tdp-backup-acceptance-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "khách hàng.sqlite3"
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("CREATE TABLE marker(value TEXT)")
            conn.execute("INSERT INTO marker VALUES('old')")
            conn.commit()
        self.now = datetime(2026, 9, 5, 10)

    def run_backup(self, **kw):
        return backups.automatic_backup(self.db, self.root, now=kw.pop("now", self.now), **kw)

    def content(self, path):
        with closing(sqlite3.connect(path)) as conn:
            self.assertEqual("ok", conn.execute("PRAGMA quick_check").fetchone()[0])
            return conn.execute("SELECT value FROM marker").fetchone()[0]

    def test_snapshot_is_verified_and_includes_committed_wal(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("UPDATE marker SET value='wal committed'")
            conn.commit()
            state = self.run_backup()
            self.assertEqual("", state["error"])
            self.assertEqual("wal committed", self.content(self.root / "auto_backups" / state["filename"]))

    def test_due_interval_refreshes_today_and_new_day_without_restart(self):
        first = self.run_backup()
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("UPDATE marker SET value='new'"); conn.commit()
        self.assertEqual(first["last_success"], self.run_backup(now=self.now + timedelta(minutes=29))["last_success"])
        second = self.run_backup(now=self.now + timedelta(minutes=30))
        self.assertEqual("new", self.content(self.root / "auto_backups" / second["filename"]))
        third = self.run_backup(now=self.now + timedelta(days=1))
        self.assertNotEqual(first["filename"], third["filename"])
        self.assertEqual(2, len(list((self.root / "auto_backups").glob("tdp_*.sqlite3"))))

    def test_failed_publish_preserves_previous_copy_and_reports_then_recovers(self):
        first = self.run_backup()
        target = self.root / "auto_backups" / first["filename"]
        original = hashlib.sha256(target.read_bytes()).hexdigest()
        with patch.object(backups.os, "replace", side_effect=PermissionError("test")):
            failed = self.run_backup(force=True)
        self.assertTrue(failed["error"])
        self.assertEqual(first["last_success"], failed["last_success"])
        self.assertEqual(original, hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertEqual([], list(target.parent.glob("*.tmp")))
        self.assertTrue(backups.backup_status(self.root)["error"])
        self.assertFalse(self.run_backup(force=True)["error"])

    def test_corrupt_source_or_missing_source_cannot_replace_good_copy(self):
        first = self.run_backup(); target = self.root / "auto_backups" / first["filename"]
        self.db.write_bytes(b"not a sqlite database")
        self.assertTrue(self.run_backup(force=True)["error"])
        self.assertEqual("old", self.content(target))
        missing = self.root / "not-created.sqlite3"
        with self.assertRaises(sqlite3.Error): backups.sqlite_snapshot(missing, self.root / "other.sqlite3")
        self.assertFalse(missing.exists())
        self.assertFalse((self.root / "other.sqlite3").exists())

    def test_disk_full_status_remains_visible_and_does_not_create_backup(self):
        with patch.object(backups, "sqlite_snapshot", side_effect=OSError("test disk full")):
            status = self.run_backup()
        self.assertIsNone(status["last_success"])
        self.assertTrue(backups.backup_status(self.root)["error"])
        self.assertFalse(list((self.root / "auto_backups").glob("*.sqlite3")))

    def test_retains_fourteen_daily_copies_and_preserves_unknown_files(self):
        self.run_backup()
        unknown = self.root / "auto_backups" / "customer-file.sqlite3"
        unknown.write_text("do not remove", encoding="utf-8")
        for day in range(1, 17): self.run_backup(now=self.now + timedelta(days=day))
        self.assertEqual(14, len(list(unknown.parent.glob("tdp_*.sqlite3"))))
        self.assertEqual("do not remove", unknown.read_text(encoding="utf-8"))

    def test_persisted_status_survives_process_restart(self):
        status = self.run_backup()
        backups._status_cache.clear()
        self.assertEqual(status["last_success"], backups.backup_status(self.root)["last_success"])

    def test_background_worker_runs_until_stopped(self):
        called = threading.Event()
        stopped, thread = backups.start_backup_worker(called.set, check_seconds=.01)
        try:
            self.assertTrue(called.wait(2))
        finally:
            stopped.set(); thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_before_upgrade_failure_stops_migrations_and_preserves_bytes(self):
        before = self.db.read_bytes()
        with patch.object(server, "DB_PATH", self.db), patch.object(server, "DATA_DIR", self.root), \
                patch.object(server, "sqlite_snapshot", side_effect=OSError("full")):
            with self.assertRaises(RuntimeError): server.init_database()
        self.assertEqual(before, self.db.read_bytes())

    def test_upgrade_retention_keeps_five_verified_copies_and_leaves_customer_files(self):
        folder = self.root / 'migration_backups'; folder.mkdir()
        customer = folder / 'tdp_pre_migration_customer.sqlite3'
        customer.write_text('keep customer file', encoding='utf-8')
        with patch.object(server, 'DB_PATH', self.db), patch.object(server, 'DATA_DIR', self.root):
            for _ in range(7): server.pre_migration_backup()
        self.assertEqual('keep customer file', customer.read_text(encoding='utf-8'))
        copies = [p for p in folder.glob('*.sqlite3') if p != customer]
        self.assertEqual(5, len(copies))
        for copy in copies: self.assertEqual('old', self.content(copy))

    def test_uncommitted_edits_are_not_in_the_snapshot(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("UPDATE marker SET value='not confirmed'")
            status = self.run_backup()
            self.assertFalse(status['error'])
            self.assertEqual('old', self.content(self.root / 'auto_backups' / status['filename']))
            conn.rollback()

    def test_concurrent_backup_calls_publish_one_valid_snapshot(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            states = list(executor.map(lambda _: self.run_backup(), range(4)))
        self.assertTrue(all(not s['error'] for s in states))
        files = list((self.root / 'auto_backups').glob('*.sqlite3'))
        self.assertEqual(1, len(files)); self.assertEqual('old', self.content(files[0]))
        self.assertFalse(list(files[0].parent.glob('*.tmp')))

    def test_application_starts_and_stops_worker_without_background_import_side_effects(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in ('install_seed_database_if_missing', 'init_database', 'open_browser'):
                stack.enter_context(patch.object(server, name))
            stack.enter_context(patch.object(server, 'acquire_single_instance', return_value=True))
            stack.enter_context(patch.object(server, 'tdp_health_available', return_value=False))
            stack.enter_context(patch.object(server.sys, 'argv', ['server.py', '--no-browser']))
            stack.enter_context(patch.object(server.sys, 'stdout', io.StringIO()))
            stop, worker = unittest.mock.Mock(), unittest.mock.Mock()
            started = stack.enter_context(patch.object(server, 'start_backup_worker', return_value=(stop, worker)))
            stack.enter_context(patch.object(server, 'serve', side_effect=KeyboardInterrupt))
            with self.assertRaises(KeyboardInterrupt): server.run_application()
            started.assert_called_once_with(server.auto_backup)
            stop.set.assert_called_once(); worker.join.assert_called_once()

    def test_seed_publish_race_keeps_new_customer_database(self):
        target = self.root / "destination.sqlite3"
        real_link = server.os.link

        def concurrent_create(source, destination):
            with closing(sqlite3.connect(destination)) as conn:
                conn.execute("CREATE TABLE marker(value TEXT)")
                conn.execute("INSERT INTO marker VALUES('customer won')"); conn.commit()
            return real_link(source, destination)

        with patch.object(server.os, "link", side_effect=concurrent_create):
            self.assertFalse(server.install_seed_database_if_missing(self.db, target))
        self.assertEqual("customer won", self.content(target))
        self.assertFalse(list(self.root.glob("*.tmp")))


class Round5IntegrationTests(SelectedDocumentExportTests):
    def prepare_sellers(self, *, all_excluded=False):
        with server.db() as conn:
            conn.execute("INSERT OR REPLACE INTO people(name,cccd,issue_date,issue_place,address) VALUES('Người hợp lệ kiểm thử','012345670000','01/01/2020','Nơi cấp kiểm thử','Thái Bình')")
            orders = conn.execute("SELECT id FROM orders ORDER BY id").fetchall()
            names = EXCLUDED_SELLERS if all_excluded else ("Người hợp lệ kiểm thử", EXCLUDED_SELLERS[0])
            for index, row in enumerate(orders):
                name = names[index % len(names)]
                conn.execute("UPDATE orders SET purchase_list=1,seller=?,cccd=? WHERE id=?", (name, "012345670000", row["id"]))

    def test_excluded_sellers_never_appear_in_choices_even_after_master_reload(self):
        server.sync_master_if_needed(force=True)
        result = self.client.get('/api/bootstrap').get_json()['master']
        self.assertFalse(any(is_excluded_seller(name) for name in result['eligible_sellers']))
        self.assertEqual(list(EXCLUDED_SELLERS), result['excluded_sellers'])
        self.assertIn('Đoàn Văn Giang', result['eligible_sellers'])
        with server.db() as conn:
            for name in EXCLUDED_SELLERS:
                self.assertIsNotNone(conn.execute("SELECT name FROM people WHERE name=?", (name,)).fetchone())

    def test_mixed_receipts_exclude_only_blocked_rows_show_warning_and_keep_database(self):
        self.prepare_sellers()
        with server.db() as conn:
            batch = dict(conn.execute("SELECT * FROM batches WHERE id=?", (self.batch_id,)).fetchone())
            rows = [dict(r) for r in conn.execute("SELECT * FROM orders WHERE batch_id=?", (self.batch_id,))]
            before = list(conn.iterdump())
            excluded = []
            eligible = collect_purchase_summary_rows(conn, batch, rows, excluded_rows=excluded)
            self.assertEqual(1, len(eligible)); self.assertEqual(1, len(excluded))
            self.assertEqual(10000, sum(r['amount'] for r in eligible))
            workbook = server.export_purchase_documents(conn, batch, rows)
            self.assertEqual(before, list(conn.iterdump()))
        try:
            from .document_preview import create_snapshot
            snapshot = create_snapshot(server.DATA_DIR / 'preview-tests', [('receipts.xlsx', workbook)])
            self.assertTrue(snapshot['warnings'])
            for sheet in snapshot['sheets']:
                self.assertFalse(any(name in sheet['html'] for name in EXCLUDED_SELLERS))
            self.assertTrue(workbook.worksheets[0]['A1'].comment)
        finally: workbook.close()

    def test_all_excluded_does_not_silently_return_empty_bundle(self):
        self.prepare_sellers(all_excluded=True)
        with server.db() as conn:
            batch = dict(conn.execute("SELECT * FROM batches WHERE id=?", (self.batch_id,)).fetchone())
            rows = [dict(r) for r in conn.execute("SELECT * FROM orders")]
            with self.assertRaises(PurchaseSummaryError) as caught:
                server.export_optional_purchase_documents(conn, batch, rows)
            self.assertEqual('excluded_sellers_no_rows', caught.exception.code)

    def test_direct_workbook_builder_cannot_bypass_exclusion_with_new_identity(self):
        for name in EXCLUDED_SELLERS:
            with self.assertRaises(PurchaseSummaryError) as caught:
                aggregate_purchase_summary_rows([{'seller': '  ' + name.upper() + ' ', 'work_date': '2026-09-05'}])
            self.assertEqual('excluded_seller', caught.exception.code)

    def test_active_bootstrap_skips_retired_calculations_preserves_history(self):
        with server.db() as conn:
            conn.execute("INSERT OR REPLACE INTO kitchen_labor_costs(work_date,kitchen,amount,source,updated_at) VALUES('2026-09-01','BEP-A',123,'history','2026-09-05')")
            history = [tuple(r) for r in conn.execute("SELECT * FROM kitchen_labor_costs")]
        with patch.object(contract_modules, 'meal_plan_payload', side_effect=AssertionError('retired')), \
                patch.object(contract_modules, 'payroll_rows', side_effect=AssertionError('retired')):
            response = self.client.get('/api/operations/bootstrap?active_only=1&month=2026-09&as_of=2026-09-05')
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.get_json()['labor_costs'])
        self.assertIn('inventory', response.get_json())
        with server.db() as conn:
            self.assertEqual(history, [tuple(r) for r in conn.execute("SELECT * FROM kitchen_labor_costs")])
        legacy = self.client.get('/api/operations/bootstrap?month=2026-09&as_of=2026-09-05').get_json()
        self.assertTrue(legacy['labor_costs'])

    def test_repeated_upgrade_preserves_all_business_rows_and_backup_restores(self):
        def business_dump(conn):
            return [line for line in conn.iterdump() if line.startswith('INSERT INTO') and not line.startswith('INSERT INTO "settings"')]
        # Complete the same normal derived-ledger initialization first.
        server.init_database()
        with server.db() as conn: before = business_dump(conn)
        server.init_database()
        with server.db() as conn: self.assertEqual(before, business_dump(conn))
        newest = max((server.DATA_DIR / 'migration_backups').glob('*.sqlite3'), key=lambda p: p.stat().st_mtime_ns)
        with closing(sqlite3.connect(newest)) as conn:
            self.assertEqual('ok', conn.execute('PRAGMA quick_check').fetchone()[0])
            self.assertEqual(before, business_dump(conn))
        response = self.client.get('/api/backup/status')
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.get_json()['last_success'])

    def test_navigation_has_no_retired_or_duplicate_entries_and_keeps_physical_stock(self):
        with self.client.get('/') as response:
            page = response.get_data(as_text=True)
        nav = page.split('<nav id="nav">')[1].split('</nav>')[0]
        for view in ('kitchen', 'payroll', 'deliveries'):
            self.assertNotIn('data-view="' + view + '"', nav)
        for view in ('physical', 'orders', 'printing', 'msmi', 'inventory'):
            self.assertIn('data-view="' + view + '"', nav)


if __name__ == '__main__':
    unittest.main()
