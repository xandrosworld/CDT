from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask

try:
    from .invoice_workbench import (
        INPUT_INVOICE,
        OUTPUT_INVOICE,
        InvoiceWorkbenchError,
        init_invoice_workbench_schema,
        list_sync_batches,
        prepare_sync_batch,
        register_invoice_workbench_routes,
        validate_date_range,
    )
except ImportError:  # pragma: no cover - direct file invocation
    from invoice_workbench import (  # type: ignore
        INPUT_INVOICE,
        OUTPUT_INVOICE,
        InvoiceWorkbenchError,
        init_invoice_workbench_schema,
        list_sync_batches,
        prepare_sync_batch,
        register_invoice_workbench_routes,
        validate_date_range,
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class InvoiceWorkbenchDomainTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
               CREATE TABLE audit_log(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,
                   entity_type TEXT,entity_id TEXT,status TEXT NOT NULL,message TEXT,
                   metadata_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL
               );"""
        )
        init_invoice_workbench_schema(self.connection)

    def tearDown(self):
        self.connection.close()

    def audit_event(self, conn, event_type, **kwargs):
        conn.execute(
            "INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) "
            "VALUES(?,?,?,'ok','',?,?)",
            (
                event_type,
                kwargs.get("entity_type", ""),
                kwargs.get("entity_id", ""),
                "{}",
                now_iso(),
            ),
        )

    def test_date_range_is_inclusive_and_rejects_invalid_order(self):
        self.assertEqual(
            ("2026-08-01", "2026-08-31"), validate_date_range("2026-08-01", "2026-08-31")
        )
        self.assertEqual(
            ("2026-08-31", "2026-08-31"), validate_date_range("2026-08-31", "2026-08-31")
        )
        for start, end in (("2026-08-32", "2026-08-31"), ("2026-09-01", "2026-08-31"), ("", "")):
            with self.assertRaises(InvoiceWorkbenchError):
                validate_date_range(start, end)

    def test_prepare_is_idempotent_and_separates_input_from_output(self):
        common = {
            "tenant": "TDP",
            "source": "msmi",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
            "now_iso": now_iso,
            "audit_event": self.audit_event,
        }
        first, created_first = prepare_sync_batch(
            self.connection, invoice_type="input", **common
        )
        repeated, created_repeated = prepare_sync_batch(
            self.connection, invoice_type=INPUT_INVOICE, **common
        )
        output, created_output = prepare_sync_batch(
            self.connection, invoice_type="output", **common
        )

        self.assertTrue(created_first)
        self.assertFalse(created_repeated)
        self.assertTrue(created_output)
        self.assertEqual(first["id"], repeated["id"])
        self.assertNotEqual(first["id"], output["id"])
        self.assertEqual(OUTPUT_INVOICE, output["invoice_type"])
        self.assertEqual("msmi", first["source"])
        self.assertEqual("minvoice", output["source"])
        self.assertEqual(
            2, self.connection.execute("SELECT COUNT(*) FROM invoice_sync_batches").fetchone()[0]
        )
        self.assertEqual(2, self.connection.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0])

    def test_source_direction_contract_rejects_minvoice_as_input(self):
        with self.assertRaisesRegex(
            InvoiceWorkbenchError, "đầu vào dùng mSMI; hóa đơn đầu ra dùng M-Invoice",
        ):
            prepare_sync_batch(
                self.connection,
                tenant="TDP",
                source="minvoice",
                invoice_type="input",
                date_from="2026-08-01",
                date_to="2026-08-31",
                now_iso=now_iso,
            )

    def test_payload_filters_direction_and_exposes_no_raw_invoice_data(self):
        for direction in ("input", "output"):
            prepare_sync_batch(
                self.connection,
                tenant="TDP",
                source="msmi",
                invoice_type=direction,
                date_from="2026-08-01",
                date_to="2026-08-31",
                now_iso=now_iso,
            )
        payload = list_sync_batches(
            self.connection,
            tenant="TDP",
            invoice_type="input",
            date_from="2026-08-01",
            date_to="2026-08-31",
        )
        self.assertEqual("input", payload["filters"]["direction"])
        self.assertEqual(1, len(payload["batches"]))
        self.assertNotIn("raw_json", str(payload))
        self.assertTrue(payload["read_only_source"])


class InvoiceWorkbenchRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tdp_invoice_workbench_")
        self.database = Path(self.temp.name) / "workbench.sqlite3"
        with self.db() as conn:
            conn.executescript(
                """CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                   CREATE TABLE audit_log(
                       id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,
                       entity_type TEXT,entity_id TEXT,status TEXT NOT NULL,message TEXT,
                       metadata_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL
                   );"""
            )
            init_invoice_workbench_schema(conn)
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        register_invoice_workbench_routes(
            self.app,
            {
                "db": self.db,
                "now_iso": now_iso,
                "setting_get": lambda conn, key, default="": default,
                "audit_event": None,
            },
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def test_route_round_trip_and_validation(self):
        body = {
            "source": "msmi",
            "invoice_type": "input",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }
        first = self.client.post("/api/invoice-workbench/batches", json=body)
        repeated = self.client.post("/api/invoice-workbench/batches", json=body)
        listing = self.client.get(
            "/api/invoice-workbench?invoice_type=input&from=2026-08-01&to=2026-08-31"
        )

        self.assertEqual(200, first.status_code)
        self.assertTrue(first.get_json()["created"])
        self.assertFalse(repeated.get_json()["created"])
        self.assertEqual(1, len(listing.get_json()["batches"]))
        self.assertEqual(
            400,
            self.client.get(
                "/api/invoice-workbench?invoice_type=output&from=2026-09-01&to=2026-08-31"
            ).status_code,
        )


class InvoiceWorkbenchStaticUITests(unittest.TestCase):
    def test_input_sync_refreshes_its_bounded_batch_and_reenables_the_view(self):
        source = (Path(__file__).resolve().parent / "static" / "app.js").read_text(encoding="utf-8")
        handler = source.split("async function prepareInvoiceSyncBatch", 1)[1].split(
            "function renderBatchSelect", 1
        )[0]
        input_branch = handler.split('if (state.invoiceDirection === "input")', 1)[1].split(
            "} else {", 1
        )[0]

        self.assertIn("loadInvoiceWorkbench(true)", input_branch)
        self.assertIn("render();", input_branch)

    def test_ui_exposes_two_directions_date_range_filters_and_safe_action(self):
        from .test_invoice_workbench_listing import rendered_invoice_html
        static_dir = Path(__file__).resolve().parent / "static"
        source = (static_dir / "app.js").read_text(encoding="utf-8")
        source += rendered_invoice_html()
        page = (static_dir / "index.html").read_text(encoding="utf-8")

        for required in (
            'data-direction="input"',
            'data-direction="output"',
            'id="invoiceFrom"',
            'id="invoiceTo"',
            'id="invoiceStatus"',
            'data-action="prepare-invoice-sync"',
            'tdp.invoiceWorkbenchFilters',
        ):
            self.assertTrue(required in source, required)
        self.assertIn("Hóa đơn đầu vào + đầu ra", page)
        self.assertIn("Chưa ghép mã", source)
        self.assertTrue("Cần quy đổi đơn vị" in source)
        self.assertTrue("Phải ghép đủ mã, đơn vị và xác nhận mới ghi kho hóa đơn" in source)

    def test_server_wiring_uses_only_a_temporary_database(self):
        root = Path(__file__).resolve().parent.parent
        code = textwrap.dedent(
            """
            import os
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory(prefix="tdp069_server_") as temp_name:
                root = Path(temp_name)
                os.environ["TDP_DATA_DIR"] = str(root / "data")
                os.environ["TDP_EXPORT_DIR"] = str(root / "exports")
                os.environ["TDP_DB_PATH"] = str(root / "data" / "tdp.sqlite3")
                from tdp_system import server
                server.init_database()
                client = server.app.test_client()
                body = {
                    "source": "msmi",
                    "invoice_type": "output",
                    "date_from": "2026-08-01",
                    "date_to": "2026-08-31",
                }
                prepared = client.post("/api/invoice-workbench/batches", json=body)
                listing = client.get(
                    "/api/invoice-workbench?invoice_type=output&from=2026-08-01&to=2026-08-31"
                )
                health = client.get("/health")
                assert prepared.status_code == 200 and prepared.get_json()["created"]
                assert listing.status_code == 200 and len(listing.get_json()["batches"]) == 1
                assert health.status_code == 200 and health.get_json()["integrity"] == "ok"
            """
        )
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
