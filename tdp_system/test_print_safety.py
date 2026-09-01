"""Regression tests for duplicate-safe Windows print submission."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

try:
    import contract_modules as contract_module
    from contract_modules import (
        claim_approved_print_jobs,
        finish_claimed_print_jobs,
        register_contract_routes,
    )
except ImportError:  # pragma: no cover - package invocation
    from . import contract_modules as contract_module
    from .contract_modules import (
        claim_approved_print_jobs,
        finish_claimed_print_jobs,
        register_contract_routes,
    )


PRINT_SCHEMA = """
CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE batches(
    id INTEGER PRIMARY KEY,
    status TEXT NOT NULL
);
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    status TEXT NOT NULL,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE print_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_at TEXT,
    printed_at TEXT,
    printer_name TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    file_sha256 TEXT,
    input_sha256 TEXT,
    manifest_path TEXT,
    page_count INTEGER NOT NULL DEFAULT 0,
    paper TEXT NOT NULL DEFAULT 'A4',
    copies INTEGER NOT NULL DEFAULT 1,
    submitted_at TEXT,
    UNIQUE(batch_id,document_type)
);
"""


def open_database(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class FakeWin32Print(types.ModuleType):
    def __init__(self, default="Printer A"):
        super().__init__("win32print")
        self.default = default
        self.changes: list[str] = []

    def GetDefaultPrinter(self):
        return self.default

    def SetDefaultPrinter(self, value):
        self.default = value
        self.changes.append(value)


class PrintClaimTests(unittest.TestCase):
    def test_compare_and_swap_allows_only_one_concurrent_claim(self):
        with tempfile.TemporaryDirectory(prefix="tdp_print_claim_") as temp_dir:
            database = Path(temp_dir) / "claim.sqlite3"
            conn = open_database(database)
            conn.executescript(PRINT_SCHEMA)
            job_id = conn.execute(
                """INSERT INTO print_jobs(
                       batch_id,document_type,file_path,status,approved_at,created_at
                   ) VALUES(1,'pdf_bundle','bundle.pdf','approved','now','now')"""
            ).lastrowid
            conn.commit()
            conn.close()

            barrier = threading.Barrier(2)

            def claim():
                worker = open_database(database)
                try:
                    barrier.wait(timeout=5)
                    result = claim_approved_print_jobs(worker, 1, [job_id])
                    worker.commit()
                    return result
                finally:
                    worker.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(claim) for _ in range(2)]
                results = sorted(future.result() for future in futures)
            self.assertEqual(results, [False, True])

            check = open_database(database)
            try:
                row = check.execute("SELECT * FROM print_jobs WHERE id=?", (job_id,)).fetchone()
                self.assertEqual(row["status"], "submitting")
                self.assertIsNone(row["submitted_at"])
                self.assertIsNone(row["printed_at"])
                self.assertTrue(finish_claimed_print_jobs(
                    check,
                    [job_id],
                    status="submitted",
                    submitted_at="2026-09-01T01:02:03",
                    printer_name="Printer B",
                    copies=2,
                ))
                check.commit()
                self.assertFalse(finish_claimed_print_jobs(
                    check, [job_id], status="submission_unknown"
                ))
                row = check.execute("SELECT * FROM print_jobs WHERE id=?", (job_id,)).fetchone()
                self.assertEqual(row["status"], "submitted")
                self.assertIsNone(row["printed_at"])
                self.assertEqual(row["submitted_at"], "2026-09-01T01:02:03")
            finally:
                check.close()

    def test_multi_job_claim_rolls_back_instead_of_partially_claiming(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(PRINT_SCHEMA)
        conn.execute("INSERT INTO batches(id,status) VALUES(1,'approved')")
        first = conn.execute(
            "INSERT INTO print_jobs(batch_id,document_type,file_path,status,created_at) "
            "VALUES(1,'one','one.pdf','approved','now')"
        ).lastrowid
        second = conn.execute(
            "INSERT INTO print_jobs(batch_id,document_type,file_path,status,created_at) "
            "VALUES(1,'two','two.pdf','submitted','now')"
        ).lastrowid
        self.assertFalse(claim_approved_print_jobs(conn, 1, [first, second]))
        statuses = [row["status"] for row in conn.execute(
            "SELECT status FROM print_jobs ORDER BY id"
        )]
        self.assertEqual(statuses, ["approved", "submitted"])
        conn.close()


class PrintRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tdp_print_route_")
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "data"
        self.database = self.data_dir / "test.sqlite3"
        output_dir = self.data_dir / "print_jobs" / "1"
        output_dir.mkdir(parents=True)
        self.pdf = output_dir / "bundle.pdf"
        canvas = Canvas(str(self.pdf), pagesize=A4)
        canvas.drawString(72, 770, "TDP PRINT SAFETY TEST")
        canvas.save()

        conn = open_database(self.database)
        conn.executescript(PRINT_SCHEMA)
        conn.execute("INSERT INTO batches(id,status) VALUES(1,'approved')")
        conn.executemany(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            [("print_paper", "A4"), ("print_copies", "2"), ("printer_name", "Printer B")],
        )
        conn.execute(
            """INSERT INTO print_jobs(
                   batch_id,document_type,file_path,status,approved_at,created_at,
                   file_sha256,page_count,paper,copies,printer_name
               ) VALUES(1,'pdf_bundle',?,'approved','approved','created',?,1,'A4',2,'Printer B')""",
            (str(self.pdf.resolve()), hashlib.sha256(self.pdf.read_bytes()).hexdigest()),
        )
        conn.commit()
        conn.close()

        @contextmanager
        def database_context():
            connection = open_database(self.database)
            try:
                yield connection
                connection.commit()
            finally:
                connection.close()

        def setting_get(conn, key, default=None):
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

        def setting_set(conn, key, value):
            conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

        self.app = Flask(__name__)
        self.app.testing = True
        register_contract_routes(self.app, {
            "db": database_context,
            "now_iso": lambda: "2026-09-01T01:02:03",
            "clean_text": lambda value: str(value or "").strip(),
            "number_value": lambda value, default=0: float(value if value not in (None, "") else default),
            "tax_factor": lambda value: 1.0,
            "setting_get": setting_get,
            "setting_set": setting_set,
            "root": self.root,
            "data_dir": self.data_dir,
            "require_batch": lambda conn, batch_id: ({}, []),
            "export_supplier_orders": lambda *args: None,
            "export_deliveries": lambda *args: None,
            "export_purchase_documents": lambda *args: None,
            "export_report": lambda *args: None,
        })
        self.client = self.app.test_client()
        self.printer_state = {
            "supported": True,
            "default": "Printer A",
            "installed": ["Printer A", "Printer B"],
            "error": "",
        }

    def tearDown(self):
        self.temp.cleanup()

    def job(self):
        conn = open_database(self.database)
        try:
            return dict(conn.execute("SELECT * FROM print_jobs WHERE batch_id=1").fetchone())
        finally:
            conn.close()

    def test_dry_run_does_not_consume_approval(self):
        with patch.object(contract_module, "windows_printer_state", return_value=self.printer_state):
            response = self.client.post("/api/print/run/1", json={"dry_run": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "verified")
        row = self.job()
        self.assertEqual(row["status"], "approved")
        self.assertIsNone(row["submitted_at"])
        self.assertIsNone(row["printed_at"])

    def test_success_is_submitted_once_and_restores_default_printer(self):
        fake = FakeWin32Print()
        calls = []

        def startfile(path, verb):
            connection = open_database(self.database)
            try:
                durable_status = connection.execute(
                    "SELECT status FROM print_jobs WHERE batch_id=1"
                ).fetchone()["status"]
            finally:
                connection.close()
            calls.append((path, verb, fake.default, durable_status))

        with (
            patch.dict(sys.modules, {"win32print": fake}),
            patch.object(contract_module, "windows_printer_state", return_value=self.printer_state),
            patch.object(contract_module.os, "startfile", side_effect=startfile, create=True),
        ):
            first = self.client.post("/api/print/run/1", json={})
            second = self.client.post("/api/print/run/1", json={})
            invalidated = self.client.post(
                "/api/print/invalidate/1", json={"confirmed": True}
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["status"], "submitted")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(invalidated.status_code, 409)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(
            call[1:] == ("print", "Printer B", "submitting") for call in calls
        ))
        self.assertEqual(fake.default, "Printer A")
        self.assertEqual(fake.changes, ["Printer B", "Printer A"])
        row = self.job()
        self.assertEqual(row["status"], "submitted")
        self.assertIsNotNone(row["submitted_at"])
        self.assertIsNone(row["printed_at"])

    def test_ambiguous_shell_error_is_locked_and_default_is_restored(self):
        fake = FakeWin32Print()
        calls = 0

        def failing_startfile(path, verb):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated shell error")

        with (
            patch.dict(sys.modules, {"win32print": fake}),
            patch.object(contract_module, "windows_printer_state", return_value=self.printer_state),
            patch.object(contract_module.os, "startfile", side_effect=failing_startfile, create=True),
        ):
            first = self.client.post("/api/print/run/1", json={})
            second = self.client.post("/api/print/run/1", json={})
            invalidated = self.client.post(
                "/api/print/invalidate/1", json={"confirmed": True}
            )

        self.assertEqual(first.status_code, 500)
        self.assertEqual(first.get_json()["status"], "submission_unknown")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(invalidated.status_code, 409)
        self.assertEqual(calls, 2)
        self.assertEqual(fake.default, "Printer A")
        row = self.job()
        self.assertEqual(row["status"], "submission_unknown")
        self.assertIsNone(row["submitted_at"])
        self.assertIsNone(row["printed_at"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
