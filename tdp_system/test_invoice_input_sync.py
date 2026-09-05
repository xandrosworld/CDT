from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

from flask import Flask

try:
    from .contract_modules import init_contract_schema
    from .invoice_input_sync import INPUT_INVOICE, input_invoice_payload, sync_input_batch
    from .invoice_workbench import (
        init_invoice_workbench_schema,
        list_sync_batches,
        prepare_sync_batch,
        register_invoice_workbench_routes,
    )
    from .test_msmi_sync import remote_invoice
except ImportError:  # pragma: no cover - direct invocation
    from contract_modules import init_contract_schema
    from invoice_input_sync import INPUT_INVOICE, input_invoice_payload, sync_input_batch
    from invoice_workbench import (
        init_invoice_workbench_schema,
        list_sync_batches,
        prepare_sync_batch,
        register_invoice_workbench_routes,
    )
    from test_msmi_sync import remote_invoice


NOW = "2026-09-02T12:00:00"


def now_iso() -> str:
    return NOW


def init_test_database(conn) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE products(code TEXT PRIMARY KEY,name TEXT,unit TEXT);
        CREATE TABLE balances(id INTEGER PRIMARY KEY);
        CREATE TABLE orders(id INTEGER PRIMARY KEY);
        """
    )
    init_contract_schema(conn)
    init_invoice_workbench_schema(conn)


def prepared_input_batch(conn) -> dict:
    batch, created = prepare_sync_batch(
        conn,
        tenant="TDP",
        source="msmi",
        invoice_type="input",
        date_from="2026-08-01",
        date_to="2026-08-31",
        now_iso=now_iso,
    )
    assert created
    return batch


class DateBoundedMsmi:
    def __init__(self, items):
        self.items = list(items)
        self.calls = []

    def list_invoices(self, *, invoice_type, page, size, from_date, to_date):
        self.calls.append({
            "invoice_type": invoice_type,
            "page": page,
            "size": size,
            "from_date": from_date,
            "to_date": to_date,
        })
        start = page * size
        selected = self.items[start:start + size]
        return {
            "items": selected,
            "page": page,
            "size": size,
            "has_more": start + len(selected) < len(self.items),
        }


class FailingSecondPage(DateBoundedMsmi):
    def list_invoices(self, **kwargs):
        if kwargs["page"] == 1:
            raise RuntimeError("simulated remote page failure MSMI-SECRET-ID")
        return super().list_invoices(**kwargs)


class InvoiceInputBatchSyncTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_test_database(self.conn)
        self.batch = prepared_input_batch(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_august_bounds_are_inclusive_and_passed_on_every_production_page(self):
        items = [remote_invoice(31), remote_invoice(15), remote_invoice(1)]
        client = DateBoundedMsmi(items)

        result = sync_input_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=5, page_size=2
        )

        self.assertTrue(result["complete"])
        self.assertEqual(3, result["new_invoices"])
        self.assertEqual(2, result["pages"])
        self.assertEqual(3, result["fetched_count"])
        self.assertEqual("needs_mapping", result["status"])
        self.assertEqual({"2026-08-01", "2026-08-15", "2026-08-31"}, {
            row["invoice_date"] for row in self.conn.execute("SELECT invoice_date FROM msmi_invoices")
        })
        for call in client.calls:
            self.assertEqual(INPUT_INVOICE, call["invoice_type"])
            self.assertEqual("2026-08-01", call["from_date"])
            self.assertEqual("2026-08-31", call["to_date"])

        public = list_sync_batches(
            self.conn,
            tenant="TDP",
            invoice_type="input",
            date_from="2026-08-01",
            date_to="2026-08-31",
        )["batches"][0]
        self.assertNotIn("source_cursor", public)
        self.assertNotIn("MSMI-", json.dumps(public))

    def test_utc_source_dates_are_filtered_by_vietnam_calendar_month(self):
        august_first = deepcopy(remote_invoice(1))
        august_first.update({
            "_id": "MSMI-AUG-FIRST",
            "shdon": "AUG-FIRST",
            "tdlap": "2026-07-31T17:00:00Z",
        })
        august_last = deepcopy(remote_invoice(31))
        august_last.update({
            "_id": "MSMI-AUG-LAST",
            "shdon": "AUG-LAST",
            "tdlap": "2026-08-30T17:00:00Z",
        })
        september_first = deepcopy(remote_invoice(2))
        september_first.update({
            "_id": "MSMI-SEP-FIRST",
            "shdon": "SEP-FIRST",
            "tdlap": "2026-08-31T17:00:00Z",
        })
        client = DateBoundedMsmi([september_first, august_last, august_first])

        result = sync_input_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=5, page_size=2
        )

        self.assertTrue(result["complete"])
        self.assertEqual(2, result["new_invoices"])
        self.assertEqual(2, result["fetched_count"])
        self.assertEqual(1, result["skipped_out_of_range"])
        self.assertEqual(
            ["2026-08-01", "2026-08-31"],
            [row[0] for row in self.conn.execute(
                "SELECT invoice_date FROM msmi_invoices ORDER BY invoice_date"
            )],
        )

    def test_source_that_ignores_date_filter_is_paged_but_outside_rows_are_never_persisted(self):
        september = deepcopy(remote_invoice(2))
        september.update({"_id": "MSMI-SEP", "shdon": "SEP", "tdlap": "2026-09-02"})
        # This row is deliberately malformed after its identity/date fields.
        # An out-of-range document must be skipped before quarantine logic can
        # accidentally link it to the August batch.
        september["tgtcthue"] = "not-a-number"
        september["hdhhdvu"][0]["ma"] = "SRC-SEP"
        july = deepcopy(remote_invoice(31))
        july.update({"_id": "MSMI-JUL", "shdon": "JUL", "tdlap": "2026-07-31"})
        july["hdhhdvu"][0]["ma"] = "SRC-JUL"
        client = DateBoundedMsmi([
            september,
            remote_invoice(31),
            remote_invoice(1),
            july,
        ])

        result = sync_input_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=5, page_size=2
        )

        self.assertTrue(result["complete"])
        self.assertEqual(2, result["pages"])
        self.assertEqual(2, result["new_invoices"])
        self.assertEqual(2, result["fetched_count"])
        self.assertEqual(2, result["skipped_out_of_range"])
        self.assertEqual(
            ["2026-08-01", "2026-08-31"],
            [row[0] for row in self.conn.execute(
                "SELECT invoice_date FROM msmi_invoices ORDER BY invoice_date"
            )],
        )
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_sync_batch_invoices WHERE batch_id=?",
            (self.batch["id"],),
        ).fetchone()[0])
        audit = self.conn.execute(
            """SELECT metadata_json FROM audit_log
               WHERE event_type='invoice_input.sync' AND status='ok'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()[0]
        self.assertEqual(2, json.loads(audit)["skipped_out_of_range"])
        self.assertNotIn("MSMI-SEP", audit)
        self.assertNotIn("MSMI-JUL", audit)

    def test_repeat_is_idempotent_and_keeps_confirmed_mapping_with_discount_and_promotion(self):
        remote = remote_invoice(8)
        remote["hdhhdvu"].extend([
            {
                "ma": "DISCOUNT",
                "ten": "Chiết khấu thương mại",
                "sluong": 0,
                "dgia": 0,
                "thtien": -500,
                "tchat": 3,
                "tsuat": 0,
            },
            {
                "ma": "PROMO",
                "ten": "Hàng khuyến mại",
                "dvtinh": "kg",
                "sluong": 2,
                "dgia": 0,
                "thtien": 0,
                "tchat": 2,
                "tsuat": 0,
            },
        ])
        client = DateBoundedMsmi([remote])
        first = sync_input_batch(self.conn, client, self.batch["id"], now_iso, page_size=2)
        self.assertEqual(1, first["new_invoices"])

        self.conn.execute("INSERT INTO products(code) VALUES('P-CONFIRMED')")
        self.conn.execute(
            """INSERT INTO item_mappings(
                   tenant,seller_tax_code,source_item_code,source_item_name,product_code,updated_at
               ) VALUES('TDP','0200000001','SRC-008','Mat hang 8','P-CONFIRMED',?)""",
            (NOW,),
        )
        self.conn.execute(
            """UPDATE msmi_invoice_items SET product_code='P-CONFIRMED',mapping_status='mapped'
               WHERE source_item_code='SRC-008'"""
        )

        repeated = sync_input_batch(self.conn, client, self.batch["id"], now_iso, page_size=2)
        self.assertEqual(0, repeated["new_invoices"])
        self.assertEqual(1, repeated["known_invoices"])
        self.assertEqual(1, self.conn.execute("SELECT COUNT(*) FROM msmi_invoices").fetchone()[0])
        self.assertEqual(1, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_sync_batch_invoices"
        ).fetchone()[0])
        lines = self.conn.execute(
            """SELECT source_item_code,amount,inventory_eligible,mapping_status,product_code
               FROM msmi_invoice_items ORDER BY line_index"""
        ).fetchall()
        self.assertEqual("P-CONFIRMED", lines[0]["product_code"])
        self.assertEqual("mapped", lines[0]["mapping_status"])
        self.assertEqual(-500, lines[1]["amount"])
        self.assertEqual(0, lines[1]["inventory_eligible"])
        self.assertEqual("not_inventory", lines[1]["mapping_status"])
        self.assertEqual(1, lines[2]["inventory_eligible"], "hàng khuyến mại có SL vẫn chờ ghép kho")
        self.assertEqual("unmapped", lines[2]["mapping_status"])

    def test_batch_payload_contains_only_linked_rows_and_no_remote_identity(self):
        sync_input_batch(
            self.conn, DateBoundedMsmi([remote_invoice(1)]), self.batch["id"], now_iso,
        )
        other = remote_invoice(31)
        from tdp_system.contract_modules import upsert_msmi_invoice
        upsert_msmi_invoice(self.conn, other, INPUT_INVOICE, "TDP", NOW)
        payload = input_invoice_payload(self.conn, self.batch["id"])
        self.assertEqual(1, len(payload["items"]))
        self.assertEqual("2026-08-01", payload["items"][0]["invoice_date"])
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("remote_id", serialized)
        self.assertNotIn("MSMI-", serialized)

    def test_page_failure_rolls_back_all_partial_rows_and_records_only_safe_evidence(self):
        client = FailingSecondPage([remote_invoice(4), remote_invoice(3), remote_invoice(2)])
        with self.assertRaisesRegex(RuntimeError, "simulated remote page failure"):
            sync_input_batch(
                self.conn, client, self.batch["id"], now_iso, max_pages=3, page_size=2
            )

        self.assertEqual(0, self.conn.execute("SELECT COUNT(*) FROM msmi_invoices").fetchone()[0])
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_sync_batch_invoices"
        ).fetchone()[0])
        batch = self.conn.execute(
            "SELECT status,error_code,error_count FROM invoice_sync_batches WHERE id=?",
            (self.batch["id"],),
        ).fetchone()
        self.assertEqual(("error", "sync_failed", 1), tuple(batch))
        audit_json = "\n".join(
            row[0] for row in self.conn.execute(
                "SELECT metadata_json FROM audit_log WHERE event_type='invoice_input.sync'"
            )
        )
        self.assertNotIn("MSMI-SECRET-ID", audit_json)
        self.assertNotIn("payload", audit_json.casefold())

    def test_stable_anchor_resumes_after_page_cap_even_when_new_invoice_shifts_pages(self):
        client = DateBoundedMsmi([remote_invoice(number) for number in range(6, 0, -1)])
        first = sync_input_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=1, page_size=2
        )
        self.assertFalse(first["complete"])
        self.assertEqual(2, first["fetched_count"])

        client.items.insert(0, remote_invoice(7))
        latest = first
        for _ in range(10):
            latest = sync_input_batch(
                self.conn, client, self.batch["id"], now_iso, max_pages=1, page_size=2
            )
            if latest["complete"]:
                break
        self.assertTrue(latest["complete"])
        self.assertEqual(7, latest["fetched_count"])
        self.assertEqual(
            [f"MSMI-{number:03d}" for number in range(1, 8)],
            [row[0] for row in self.conn.execute(
                "SELECT remote_id FROM msmi_invoices ORDER BY remote_id"
            )],
        )


class InvoiceInputBatchRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tdp070_route_")
        self.path = Path(self.temp.name) / "test.sqlite3"
        with self.db() as conn:
            init_test_database(conn)
        self.fake = DateBoundedMsmi([remote_invoice(1), remote_invoice(31)])
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_invoice_workbench_routes(app, {
            "db": self.db,
            "now_iso": now_iso,
            "setting_get": lambda conn, key, default="": "TDP" if key == "tenant_code" else default,
            "audit_event": None,
            "create_msmi_client": lambda: self.fake,
        })
        self.client = app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def test_prepare_then_sync_route_uses_the_same_bounded_batch(self):
        prepared = self.client.post("/api/invoice-workbench/batches", json={
            "source": "msmi",
            "invoice_type": "input",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        })
        self.assertEqual(200, prepared.status_code)
        batch_id = prepared.get_json()["batch"]["id"]
        response = self.client.post(
            f"/api/invoice-workbench/batches/{batch_id}/sync",
            json={"max_pages": 2, "page_size": 1},
        )
        payload = response.get_json()
        self.assertEqual(200, response.status_code, payload)
        self.assertTrue(payload["read_only"])
        self.assertTrue(payload["complete"])
        self.assertEqual(2, payload["fetched_count"])
        self.assertTrue(all(call["from_date"] == "2026-08-01" for call in self.fake.calls))
        self.assertTrue(all(call["to_date"] == "2026-08-31" for call in self.fake.calls))
        rows = self.client.get(
            f"/api/invoice-workbench/batches/{batch_id}/invoices"
        )
        self.assertEqual(200, rows.status_code)
        self.assertEqual(2, len(rows.get_json()["items"]))
        self.assertNotIn("remote_id", rows.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
