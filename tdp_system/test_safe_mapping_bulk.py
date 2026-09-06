"""Safe bulk confirmation for exact input-invoice mapping suggestions."""

import sqlite3
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

from flask import Flask

from .contract_modules import (
    init_contract_schema,
    register_contract_routes,
    safe_input_mapping_suggestion_plan,
    upsert_msmi_invoice,
)
from .invoice_mapping import InvoiceMappingError, save_mapping
from .invoice_workbench import init_invoice_workbench_schema
from .test_msmi_sync import remote_invoice


NOW = "2026-09-06T06:00:00+00:00"


def now_iso():
    return NOW


class SafeBulkMappingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(
            """
            CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE products(code TEXT PRIMARY KEY,name TEXT,unit TEXT);
            CREATE TABLE balances(id INTEGER PRIMARY KEY);
            CREATE TABLE orders(id INTEGER PRIMARY KEY);
            INSERT INTO settings(key,value) VALUES('tenant_code','TDP');
            INSERT INTO products(code,name,unit) VALUES('P-GAO','Gạo','kg');
            """
        )
        init_contract_schema(self.conn)
        init_invoice_workbench_schema(self.conn)

        first = remote_invoice(1)
        first["hdhhdvu"][0].update(ma="GAO", ten="Gạo", dvtinh="kg")
        first["hdhhdvu"].append({
            **deepcopy(first["hdhhdvu"][0]),
            "ma": "KHAC",
            "ten": "Hàng chưa có trong danh mục",
            "stt": 2,
        })
        second = remote_invoice(2)
        second["hdhhdvu"][0].update(ma="GAO", ten="Gạo", dvtinh="kg")
        unit_review = remote_invoice(3)
        unit_review["hdhhdvu"][0].update(ma="GAO-THUNG", ten="Gạo", dvtinh="thùng")
        later = remote_invoice(4)
        later["tdlap"] = "2026-09-01"
        later["hdhhdvu"][0].update(ma="GAO", ten="Gạo", dvtinh="kg")
        unsafe = remote_invoice(5)
        unsafe["hdhhdvu"][0].update(ma="GAO", ten="Gạo", dvtinh="kg")

        self.invoice_ids = []
        for item in (first, second, unit_review, later, unsafe):
            invoice_id, _created = upsert_msmi_invoice(
                self.conn, item, "INPUT_ELECTRONIC_INVOICE", "TDP", NOW,
            )
            self.invoice_ids.append(invoice_id)
        self.conn.execute(
            "UPDATE msmi_invoices SET sync_status='review_required' WHERE id=?",
            (self.invoice_ids[-1],),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def plan(self):
        return safe_input_mapping_suggestion_plan(
            self.conn, tenant="TDP", date_from="2026-08-01", date_to="2026-08-31",
        )

    def test_preview_counts_only_unique_names_with_the_same_unit(self):
        plan = self.plan()
        self.assertEqual(2, plan["safe_lines_in_period"])
        self.assertEqual(1, plan["safe_rules"])
        self.assertEqual(2, plan["invoices_with_safe_lines"])
        self.assertEqual(1, plan["invoices_ready_after"])
        self.assertEqual(3, plan["affected_lines_all_periods"])
        self.assertEqual(1, plan["exact_name_needing_unit_review"])
        self.assertEqual(1, plan["lines_without_unique_name"])
        self.assertEqual(64, len(plan["snapshot"]))

    def test_official_mapping_propagates_safe_scope_but_excludes_unsafe_source(self):
        plan = self.plan()
        result = save_mapping(
            self.conn,
            direction="input",
            item_id=plan["_representatives"][0]["item_id"],
            product_code="P-GAO",
            now_iso=now_iso,
        )
        self.assertEqual(3, result["applied_lines"])
        mapped = self.conn.execute(
            "SELECT COUNT(*) FROM msmi_invoice_items WHERE mapping_status='mapped'"
        ).fetchone()[0]
        self.assertEqual(3, mapped)
        unsafe_item = self.conn.execute(
            "SELECT id,mapping_status FROM msmi_invoice_items WHERE invoice_id=?",
            (self.invoice_ids[-1],),
        ).fetchone()
        self.assertEqual("unmapped", unsafe_item["mapping_status"])
        with self.assertRaises(InvoiceMappingError) as raised:
            save_mapping(
                self.conn,
                direction="input",
                item_id=unsafe_item["id"],
                product_code="P-GAO",
                now_iso=now_iso,
            )
        self.assertEqual("source_not_safe", raised.exception.code)

    def test_preview_then_confirm_route_is_explicit_and_does_not_post_stock(self):
        @contextmanager
        def db_factory():
            yield self.conn
            self.conn.commit()

        def setting_get(conn, key, default=""):
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

        app = Flask("safe-bulk-mapping")
        register_contract_routes(app, {
            "db": db_factory,
            "now_iso": now_iso,
            "clean_text": lambda value: str(value or "").strip(),
            "number_value": lambda value: float(value or 0),
            "tax_factor": lambda _value: 1.0,
            "setting_get": setting_get,
            "setting_set": lambda conn, key, value: conn.execute(
                "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value)
            ),
            "root": Path.cwd(),
            "data_dir": Path.cwd(),
        })
        client = app.test_client()
        preview = client.get(
            "/api/msmi/suggested-mappings/preview?from=2026-08-01&to=2026-08-31"
        )
        self.assertEqual(200, preview.status_code)
        body = preview.get_json()
        self.assertNotIn("_representatives", body)
        unconfirmed = client.post(
            "/api/msmi/suggested-mappings",
            json={"from": "2026-08-01", "to": "2026-08-31", "snapshot": body["snapshot"]},
        )
        self.assertEqual(400, unconfirmed.status_code)
        applied = client.post(
            "/api/msmi/suggested-mappings",
            json={
                "from": "2026-08-01",
                "to": "2026-08-31",
                "snapshot": body["snapshot"],
                "confirmed": True,
            },
        )
        self.assertEqual(200, applied.status_code, applied.get_data(as_text=True))
        result = applied.get_json()
        self.assertEqual((2, 3, 1, False), (
            result["mapped_lines_in_period"],
            result["mapped_lines_all_periods"],
            result["ready_invoices_in_period"],
            result["stock_changed"],
        ))
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_inventory_ledger"
        ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
