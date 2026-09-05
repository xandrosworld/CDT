from __future__ import annotations

import sqlite3
import unittest
from copy import deepcopy

from flask import Flask

try:
    from .invoice_input_sync import sync_input_batch
    from .invoice_inventory import (
        InvoiceInventoryError,
        invoice_stock_rows,
        post_output_invoice,
        reverse_output_invoice,
    )
    from .invoice_mapping import save_mapping
    from .invoice_output_sync import sync_output_batch
    from .invoice_receipt import InvoiceReceiptError, create_input_receipt
    from .invoice_valuation import (
        InvoiceValuationError,
        moving_average_report,
        register_invoice_valuation_routes,
    )
    from .invoice_workbench import prepare_sync_batch
    from .test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from .test_invoice_output_sync import OutputFixtureMsmi, STATUS_MAP, output_invoice
    from .test_msmi_sync import remote_invoice
except ImportError:  # pragma: no cover - direct invocation
    from invoice_input_sync import sync_input_batch
    from invoice_inventory import (
        InvoiceInventoryError,
        invoice_stock_rows,
        post_output_invoice,
        reverse_output_invoice,
    )
    from invoice_mapping import save_mapping
    from invoice_output_sync import sync_output_batch
    from invoice_receipt import InvoiceReceiptError, create_input_receipt
    from invoice_valuation import (
        InvoiceValuationError,
        moving_average_report,
        register_invoice_valuation_routes,
    )
    from invoice_workbench import prepare_sync_batch
    from test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from test_invoice_output_sync import OutputFixtureMsmi, STATUS_MAP, output_invoice
    from test_msmi_sync import remote_invoice


NOW = "2026-09-02T16:20:00"


def now_iso() -> str:
    return NOW


class MovingAverageValuationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_test_database(self.conn)
        self.conn.executemany(
            "INSERT INTO products(code,name,unit) VALUES(?,?,?)",
            [
                ("P-AVG", "Hàng giá bình quân", "kg"),
                ("P-NEG", "Hàng tồn âm lịch sử", "kg"),
                ("P-ZERO", "Hàng số lượng không", "kg"),
            ],
        )
        self._opening("2026-08", "P-AVG", 10, 100)

    def tearDown(self):
        self.conn.close()

    def _opening(self, period: str, product: str, qty: float, cost: float) -> None:
        self.conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                   source_line,status,note,created_at,updated_at
               ) VALUES(?,?,?,?,?,'OPENING',?,?,'posted','fixture',?,?)""",
            (
                period + "-01", product, max(qty, 0), max(-qty, 0), cost,
                period, product, NOW, NOW,
            ),
        )

    def _input(self, day: int, qty: float, cost: float) -> int:
        remote = remote_invoice(day)
        remote["hdhhdvu"][0].update(
            ma=f"AVG-IN-{day}", ten=f"Nhập bình quân {day}", dvtinh="kg",
            sluong=qty, dgia=cost, thtien=qty * cost,
        )
        remote["tgtcthue"] = qty * cost
        remote["tgtthue"] = 0
        remote["tgtttbso"] = qty * cost
        batch = prepare_sync_batch(
            self.conn,
            tenant="TDP",
            source="msmi",
            invoice_type="input",
            date_from="2026-08-01",
            date_to="2026-08-31",
            now_iso=now_iso,
        )[0]
        sync_input_batch(self.conn, DateBoundedMsmi([remote]), batch["id"], now_iso)
        invoice_id = int(self.conn.execute(
            "SELECT id FROM msmi_invoices WHERE remote_id=?", (remote["_id"],)
        ).fetchone()[0])
        item_id = int(self.conn.execute(
            "SELECT id FROM msmi_invoice_items WHERE invoice_id=?", (invoice_id,)
        ).fetchone()[0])
        save_mapping(
            self.conn, direction="input", item_id=item_id,
            product_code="P-AVG", now_iso=now_iso,
        )
        create_input_receipt(self.conn, invoice_id, now_iso)
        return invoice_id

    def _output(self, day: int, qty: float, sales_price: float = 9999):
        remote = output_invoice(day, series=f"AVG-OUT-{day}")
        remote["hdhhdvu"][0].update(
            ma=f"AVG-OUT-{day}", ten=f"Xuất bình quân {day}", dvtinh="kg",
            sluong=qty, dgia=sales_price, thtien=qty * sales_price,
        )
        remote["tgtcthue"] = qty * sales_price
        remote["tgtthue"] = 0
        remote["tgtttbso"] = qty * sales_price
        batch = prepare_sync_batch(
            self.conn,
            tenant="TDP",
            source="msmi",
            invoice_type="output",
            date_from="2026-08-01",
            date_to="2026-08-31",
            now_iso=now_iso,
        )[0]
        client = OutputFixtureMsmi([remote])
        sync_output_batch(
            self.conn,
            client,
            batch["id"],
            now_iso,
            status_map=STATUS_MAP,
            status_fields=["fixtureStatus"],
            reference_fields=["fixtureReference"],
        )
        invoice_id = int(self.conn.execute(
            "SELECT id FROM outgoing_source_invoices WHERE remote_id=?", (remote["_id"],)
        ).fetchone()[0])
        item_id = int(self.conn.execute(
            "SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=?", (invoice_id,)
        ).fetchone()[0])
        save_mapping(
            self.conn, direction="output", item_id=item_id,
            product_code="P-AVG", now_iso=now_iso,
        )
        post_output_invoice(self.conn, invoice_id, confirmed=True, now_iso=now_iso)
        return invoice_id, remote, client, batch

    def test_multiple_inputs_outputs_use_moving_average_not_sales_price(self):
        self._input(5, 10, 200)
        self._output(10, 5, sales_price=10000)
        self._input(15, 5, 300)
        self._output(20, 5, sales_price=20000)
        report = moving_average_report(
            self.conn,
            date_from="2026-08-01",
            date_to="2026-08-31",
            include_events=True,
        )
        row = next(item for item in report["items"] if item["product_code"] == "P-AVG")
        self.assertEqual(10, row["opening_qty"])
        self.assertEqual(1000, row["opening_value"])
        self.assertEqual(15, row["input_qty"])
        self.assertEqual(3500, row["input_value"])
        self.assertEqual(10, row["output_qty"])
        self.assertEqual(1687.5, row["output_value"])
        self.assertEqual(15, row["closing_qty"])
        self.assertEqual(2812.5, row["closing_value"])
        self.assertEqual(187.5, row["average_unit_cost"])
        output_events = [event for event in report["events"] if event["movement"] == "output"]
        self.assertEqual([150, 187.5], [event["valuation_unit_cost"] for event in output_events])
        self.assertNotIn(10000, [event["valuation_unit_cost"] for event in output_events])
        self.assertNotIn(20000, [event["valuation_unit_cost"] for event in output_events])
        self.assertEqual(
            [150, 187.5],
            [row[0] for row in self.conn.execute(
                """SELECT unit_cost FROM invoice_inventory_ledger
                   WHERE direction='output' AND event_type='POST' ORDER BY txn_date"""
            )],
        )
        self.assertEqual(
            row["closing_value"],
            row["opening_value"] + row["input_value"] - row["output_value"],
        )

    def test_backdated_input_rebuild_is_deterministic_and_revalues_prior_output(self):
        self._output(10, 5)
        before = moving_average_report(
            self.conn, date_from="2026-08-01", date_to="2026-08-31", include_events=True
        )
        self.assertEqual(100, next(
            event["valuation_unit_cost"] for event in before["events"] if event["movement"] == "output"
        ))
        self._input(5, 10, 300)
        rebuilt = moving_average_report(
            self.conn, date_from="2026-08-01", date_to="2026-08-31", include_events=True
        )
        repeated = moving_average_report(
            self.conn, date_from="2026-08-01", date_to="2026-08-31", include_events=True
        )
        self.assertEqual(rebuilt, repeated)
        output_event = next(event for event in rebuilt["events"] if event["movement"] == "output")
        row = next(item for item in rebuilt["items"] if item["product_code"] == "P-AVG")
        self.assertEqual(200, output_event["valuation_unit_cost"])
        self.assertEqual(15, row["closing_qty"])
        self.assertEqual(3000, row["closing_value"])
        self.assertEqual(200, row["average_unit_cost"])
        self.assertEqual(100, self.conn.execute(
            """SELECT unit_cost FROM invoice_inventory_ledger
               WHERE direction='output' AND event_type='POST'"""
        ).fetchone()[0], "ledger gốc bất biến; rebuild chỉ thay projection giá")

    def test_opening_is_latest_snapshot_not_additive_and_cross_period_is_blocked(self):
        self._input(5, 5, 200)
        self._opening("2026-09", "P-AVG", 7, 250)
        august = moving_average_report(
            self.conn, date_from="2026-08-01", date_to="2026-08-31"
        )
        september = moving_average_report(
            self.conn, date_from="2026-09-01", date_to="2026-09-30"
        )
        aug_row = next(item for item in august["items"] if item["product_code"] == "P-AVG")
        sep_row = next(item for item in september["items"] if item["product_code"] == "P-AVG")
        self.assertEqual(15, aug_row["closing_qty"])
        self.assertEqual("2026-09", september["opening_period"])
        self.assertEqual(7, sep_row["opening_qty"])
        self.assertEqual(1750, sep_row["opening_value"])
        self.assertEqual(7, sep_row["closing_qty"])
        self.assertEqual(7, next(
            row["closing_qty"] for row in invoice_stock_rows(self.conn, "2026-09-30")
            if row["product_code"] == "P-AVG"
        ))
        with self.assertRaisesRegex(InvoiceValuationError, "đi qua một kỳ tồn đầu mới"):
            moving_average_report(
                self.conn, date_from="2026-08-01", date_to="2026-09-30"
            )
        late_remote = remote_invoice(6)
        late_remote["_id"] = "BACKDATED-AFTER-SEPTEMBER-OPENING"
        batch = prepare_sync_batch(
            self.conn, tenant="TDP", source="msmi", invoice_type="input",
            date_from="2026-08-01", date_to="2026-08-31", now_iso=now_iso,
        )[0]
        sync_input_batch(self.conn, DateBoundedMsmi([late_remote]), batch["id"], now_iso)
        late_id = int(self.conn.execute(
            "SELECT id FROM msmi_invoices WHERE remote_id=?", (late_remote["_id"],)
        ).fetchone()[0])
        item_id = int(self.conn.execute(
            "SELECT id FROM msmi_invoice_items WHERE invoice_id=?", (late_id,)
        ).fetchone()[0])
        save_mapping(
            self.conn, direction="input", item_id=item_id,
            product_code="P-AVG", now_iso=now_iso,
        )
        with self.assertRaisesRegex(InvoiceReceiptError, "trước kỳ tồn đầu mới nhất"):
            create_input_receipt(self.conn, late_id, now_iso)
        with self.assertRaisesRegex(InvoiceInventoryError, "trước một kỳ tồn đầu"):
            self._output(7, 1)

    def test_negative_legacy_opening_is_signed_and_flagged_zero_qty_is_safe(self):
        self._opening("2026-08", "P-NEG", -4, 100)
        self._opening("2026-08", "P-ZERO", 0, 999)
        report = moving_average_report(
            self.conn,
            date_from="2026-08-01",
            date_to="2026-08-31",
            include_zero=True,
        )
        negative = next(item for item in report["items"] if item["product_code"] == "P-NEG")
        zero = next(item for item in report["items"] if item["product_code"] == "P-ZERO")
        self.assertEqual(-4, negative["opening_qty"])
        self.assertEqual(-400, negative["opening_value"])
        self.assertEqual("negative_opening_review", negative["valuation_status"])
        self.assertEqual(100, negative["average_unit_cost"])
        self.assertEqual(0, zero["closing_qty"])
        self.assertEqual(0, zero["closing_value"])
        self.assertEqual(0, zero["average_unit_cost"])
        self.assertEqual({
            "quantity_decimals": 6,
            "unit_cost_decimals": 6,
            "money_decimals": 2,
            "method": "ROUND_HALF_UP_PER_MOVEMENT",
        }, report["rounding"])

    def test_reversal_uses_original_cost_and_periods_reconcile(self):
        output_id, original, client, batch = self._output(4, 4, sales_price=9000)
        changed = deepcopy(original)
        changed["fixtureStatus"] = "FIXTURE_CANCELLED"
        changed["fixtureReference"] = "CANCEL-AVG"
        client.items = [changed]
        sync_output_batch(
            self.conn,
            client,
            batch["id"],
            now_iso,
            status_map=STATUS_MAP,
            status_fields=["fixtureStatus"],
            reference_fields=["fixtureReference"],
        )
        reverse_output_invoice(
            self.conn, output_id, confirmed=True, note="fixture reversal", now_iso=now_iso
        )
        august = moving_average_report(
            self.conn, date_from="2026-08-01", date_to="2026-08-31"
        )
        september = moving_average_report(
            self.conn, date_from="2026-09-01", date_to="2026-09-30", include_events=True
        )
        aug_row = next(item for item in august["items"] if item["product_code"] == "P-AVG")
        sep_row = next(item for item in september["items"] if item["product_code"] == "P-AVG")
        reversal = next(event for event in september["events"] if event["movement"] == "reversal")
        self.assertEqual((6, 600), (aug_row["closing_qty"], aug_row["closing_value"]))
        self.assertEqual((6, 600), (sep_row["opening_qty"], sep_row["opening_value"]))
        self.assertEqual((4, 400), (sep_row["reversal_qty"], sep_row["reversal_value"]))
        self.assertEqual((-4, -400), (sep_row["output_qty"], sep_row["output_value"]))
        self.assertEqual((10, 1000), (sep_row["closing_qty"], sep_row["closing_value"]))
        self.assertEqual(100, reversal["valuation_unit_cost"])

    def test_read_only_api_exposes_period_contract_and_rejects_invalid_date(self):
        self.conn.commit()
        app = Flask(__name__)
        app.config["TESTING"] = True

        class SharedDb:
            def __enter__(inner):
                return self.conn

            def __exit__(inner, exc_type, exc, tb):
                return False

        register_invoice_valuation_routes(app, {"db": SharedDb})
        client = app.test_client()
        response = client.get(
            "/api/invoice-valuation?from=2026-08-01&to=2026-08-31&include_events=1"
        )
        invalid = client.get("/api/invoice-valuation?from=2026-02-30&to=2026-08-31")
        payload = response.get_json()
        self.assertEqual(200, response.status_code)
        self.assertTrue(payload["read_only"])
        self.assertEqual("2026-08", payload["opening_period"])
        self.assertEqual(
            ["input", "input_reversal", "output", "reversal"],
            payload["same_day_order"],
        )
        self.assertEqual(400, invalid.status_code)


if __name__ == "__main__":
    unittest.main()
