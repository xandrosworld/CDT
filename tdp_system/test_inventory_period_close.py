from __future__ import annotations

import sqlite3
import unittest
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from flask import Flask

try:
    from .inventory_period_close import (
        InventoryPeriodCloseError,
        close_inventory_period,
        init_inventory_period_close_schema,
        inventory_period_close_preview,
        register_inventory_period_close_routes,
        reopen_inventory_period,
    )
    from .invoice_valuation import moving_average_report
    from .test_invoice_input_sync import init_test_database
except ImportError:  # pragma: no cover - direct invocation
    from inventory_period_close import (
        InventoryPeriodCloseError,
        close_inventory_period,
        init_inventory_period_close_schema,
        inventory_period_close_preview,
        register_inventory_period_close_routes,
        reopen_inventory_period,
    )
    from invoice_valuation import moving_average_report
    from test_invoice_input_sync import init_test_database


NOW = "2026-09-04T12:00:00"
TODAY = date(2026, 9, 4)


class InventoryPeriodCloseTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_test_database(self.conn)
        init_inventory_period_close_schema(self.conn)
        self.conn.executemany(
            "INSERT INTO products(code,name,unit) VALUES(?,?,?)",
            [("P1", "Hàng một", "kg"), ("P2", "Hàng hết tồn", "kg")],
        )
        self._opening("2026-08", "P1", 10, 100)
        self._opening("2026-08", "P2", 0, 0)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _opening(self, period, product, qty, cost):
        self.conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                   source_line,status,note,created_at,updated_at
               ) VALUES(?,?,?,?,?,'OPENING',?,?,'posted','fixture',?,?)""",
            (period + "-01", product, max(qty, 0), max(-qty, 0), cost,
             period, product, NOW, NOW),
        )

    def _event(self, key, direction, day, qty_delta, cost=0):
        self.conn.execute(
            """INSERT INTO invoice_inventory_confirmations(
                   confirmation_key,direction,source_invoice_table,source_invoice_id,
                   action,confirmed,note,created_at
               ) VALUES(?,?,?,?,'post',1,'fixture',?)""",
            ("CONF-" + key, direction, "fixture_" + direction, len(key), NOW),
        )
        confirmation_id = self.conn.execute(
            "SELECT id FROM invoice_inventory_confirmations WHERE confirmation_key=?",
            ("CONF-" + key,),
        ).fetchone()[0]
        self.conn.execute(
            """INSERT INTO invoice_inventory_ledger(
                   event_key,direction,event_type,source_invoice_table,source_invoice_id,
                   source_line_id,source_line_index,product_code,txn_date,qty_delta,
                   unit_cost,mapping_revision_id,confirmation_id,reverses_event_key,
                   status,created_at
               ) VALUES(?,?,'POST',?,?,?,?,? ,?,?,?,NULL,?,'','posted',?)""",
            (key, direction, "fixture_" + direction, len(key), len(key), 1,
             "P1", day, qty_delta, cost, confirmation_id, NOW),
        )

    def _close(self, preview=None):
        preview = preview or inventory_period_close_preview(
            self.conn, "2026-08", today=TODAY,
        )
        return close_inventory_period(
            self.conn,
            "2026-08",
            expected_source_hash=preview["source_hash"],
            expected_target_hash=preview["target_hash"],
            timestamp=NOW,
            today=TODAY,
        )

    def test_close_transfers_quantity_value_and_is_idempotent(self):
        self._event("IN-1", "input", "2026-08-05", 10, 200)
        self._event("OUT-1", "output", "2026-08-10", -5)
        preview = inventory_period_close_preview(self.conn, "2026-08", today=TODAY)
        self.assertTrue(preview["can_close"])
        self.assertEqual((1, 15, 2250), (
            preview["nonzero_item_count"], preview["total_qty"], preview["total_value"],
        ))

        result = self._close(preview)
        self.assertFalse(result["idempotent"])
        self.assertEqual("closed", result["preview"]["status"])
        september = moving_average_report(
            self.conn, date_from="2026-09-01", date_to="2026-09-30", include_zero=True,
        )
        p1 = next(item for item in september["items"] if item["product_code"] == "P1")
        self.assertEqual((15, 2250, 150), (
            p1["opening_qty"], p1["opening_value"], p1["average_unit_cost"],
        ))
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-09'"
        ).fetchone()[0], "zero-stock products remain part of the complete snapshot")

        repeated = self._close(result["preview"])
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-09'"
        ).fetchone()[0])
        self.assertEqual(1, self.conn.execute(
            "SELECT revision FROM inventory_period_closures WHERE period='2026-08'"
        ).fetchone()[0])

    def test_reopen_then_reclose_rebuilds_august_without_adding_twice(self):
        first = self._close()
        reopened = reopen_inventory_period(self.conn, "2026-08", timestamp=NOW)
        self.assertEqual(2, reopened["revision"])
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-09'"
        ).fetchone()[0])

        self._event("LATE-IN", "input", "2026-08-20", 5, 300)
        second_preview = inventory_period_close_preview(self.conn, "2026-08", today=TODAY)
        self.assertEqual("reopened", second_preview["status"])
        self.assertEqual((15, 2500), (
            second_preview["total_qty"], second_preview["total_value"],
        ))
        second = self._close(second_preview)
        self.assertEqual("closed", second["preview"]["status"])
        opening = self.conn.execute(
            """SELECT qty_in,unit_cost FROM inventory_transactions
                 WHERE source_type='OPENING' AND source_id='2026-09' AND source_line='P1'"""
        ).fetchone()
        self.assertEqual(15, opening["qty_in"])
        self.assertAlmostEqual(2500 / 15, opening["unit_cost"], places=9)
        self.assertEqual(3, self.conn.execute(
            "SELECT revision FROM inventory_period_closures WHERE period='2026-08'"
        ).fetchone()[0])

    def test_changed_source_requires_a_fresh_preview(self):
        old_preview = inventory_period_close_preview(self.conn, "2026-08", today=TODAY)
        self._event("NEW-IN", "input", "2026-08-22", 1, 100)
        with self.assertRaisesRegex(InventoryPeriodCloseError, "đã thay đổi") as caught:
            self._close(old_preview)
        self.assertEqual("stale_source", caught.exception.code)
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_period_closures"
        ).fetchone()[0])

    def test_existing_next_opening_is_replaced_not_added_and_is_hash_guarded(self):
        self._opening("2026-09", "P1", 99, 999)
        old_preview = inventory_period_close_preview(self.conn, "2026-08", today=TODAY)
        self.assertTrue(old_preview["has_existing_next_opening"])
        self.conn.execute(
            """UPDATE inventory_transactions SET qty_in=98
                 WHERE source_type='OPENING' AND source_id='2026-09' AND source_line='P1'"""
        )
        with self.assertRaisesRegex(InventoryPeriodCloseError, "tháng sau đã thay đổi") as caught:
            self._close(old_preview)
        self.assertEqual("stale_target", caught.exception.code)

        fresh = inventory_period_close_preview(self.conn, "2026-08", today=TODAY)
        self._close(fresh)
        opening = self.conn.execute(
            """SELECT qty_in,unit_cost FROM inventory_transactions
                 WHERE source_type='OPENING' AND source_id='2026-09' AND source_line='P1'"""
        ).fetchone()
        self.assertEqual((10, 100), (opening["qty_in"], opening["unit_cost"]))
        self.assertNotEqual(108, opening["qty_in"])

    def test_current_month_and_closed_downstream_are_blocked(self):
        current = inventory_period_close_preview(self.conn, "2026-09", today=TODAY)
        self.assertFalse(current["can_close"])
        self.assertTrue(any("đã kết thúc" in issue for issue in current["issues"]))

        self._close()
        self.conn.execute(
            """INSERT INTO inventory_period_closures(
                   period,next_period,status,source_hash,target_hash,previous_opening_json,
                   item_count,total_qty,total_value,revision,closed_at,reopened_at,updated_at
               ) VALUES('2026-09','2026-10','closed','S','T','[]',0,0,0,1,?,'',?)""",
            (NOW, NOW),
        )
        with self.assertRaisesRegex(InventoryPeriodCloseError, "mở tháng đó trước"):
            reopen_inventory_period(self.conn, "2026-08", timestamp=NOW)

    def test_empty_month_cannot_create_a_zero_only_snapshot(self):
        self.conn.execute(
            "DELETE FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-08'"
        )
        preview = inventory_period_close_preview(self.conn, "2026-08", today=TODAY)
        self.assertFalse(preview["has_source_activity"])
        self.assertFalse(preview["can_close"])
        self.assertTrue(any("chưa có tồn đầu hoặc phát sinh" in issue for issue in preview["issues"]))

    def test_http_preview_confirm_and_reopen_contract(self):
        self.conn.commit()

        @contextmanager
        def db_factory():
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

        app = Flask(__name__)
        register_inventory_period_close_routes(app, {
            "db": db_factory,
            "now_iso": lambda: NOW,
            "today": lambda: TODAY,
        })
        client = app.test_client()
        preview_response = client.get("/api/inventory/month-close/preview?period=2026-08")
        self.assertEqual(200, preview_response.status_code)
        preview = preview_response.get_json()
        self.assertTrue(preview["can_close"])
        self.assertNotIn("_report", preview)

        missing_confirmation = client.post(
            "/api/inventory/month-close", json={"period": "2026-08"},
        )
        self.assertEqual(400, missing_confirmation.status_code)
        for actor in (None, "", "   ", 123, "x" * 101):
            missing_actor = client.post("/api/inventory/month-close", json={"period":"2026-08", "confirmed":True, "actor":actor})
            self.assertEqual(400, missing_actor.status_code)
            self.assertEqual("actor_required", missing_actor.json["code"])
        closed = client.post("/api/inventory/month-close", json={
            "period": "2026-08",
            "source_hash": preview["source_hash"],
            "target_hash": preview["target_hash"],
            "confirmed": True,
            "actor": "Người test chốt tháng",
        })
        self.assertEqual(200, closed.status_code, closed.get_data(as_text=True))
        self.assertEqual("closed", closed.get_json()["preview"]["status"])

        reopened = client.post(
            "/api/inventory/month-close/reopen",
            json={"period": "2026-08", "confirmed": True, "actor":"Người test mở tháng"},
        )
        self.assertEqual(200, reopened.status_code, reopened.get_data(as_text=True))
        self.assertEqual("2026-09", reopened.get_json()["next_period"])
        history = client.get("/api/inventory/month-close/preview?period=2026-08").json["history"]
        self.assertEqual(["reopen","close"], [entry["action"] for entry in history])
        self.assertEqual(["Người test mở tháng","Người test chốt tháng"], [entry["actor"] for entry in history])


class InventoryPeriodCloseUiContractTests(unittest.TestCase):
    def test_ui_is_monthly_plain_language_and_keeps_exports_separate(self):
        root = Path(__file__).resolve().parent
        app_js = (root / "static" / "app.js").read_text(encoding="utf-8")
        styles = (root / "static" / "real.css").read_text(encoding="utf-8")
        index = (root / "static" / "index.html").read_text(encoding="utf-8")
        for phrase in (
            "CHỐT KHO THEO THÁNG",
            "Tổng lượng tồn cuối",
            "Tổng giá trị tồn cuối",
            "không cộng chồng",
            "Mở lại tháng",
        ):
            self.assertIn(phrase, app_js)
        self.assertIn('data-action="close-inventory-month"', app_js)
        self.assertIn('data-action="reopen-inventory-month"', app_js)
        self.assertIn(".inventory-month-close", styles)
        self.assertIn("app.js?v=20260906-6", index)
        self.assertIn("real.css?v=20260906-6", index)
        self.assertIn("invoice-workbench.js?v=20260906-1", index)


if __name__ == "__main__":
    unittest.main()
