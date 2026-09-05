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
    from .invoice_output_sync import (
        OUTPUT_INVOICE,
        InvoiceOutputSyncError,
        minvoice_source_status,
        output_invoice_payload,
        sync_output_batch,
    )
    from .invoice_workbench import prepare_sync_batch, register_invoice_workbench_routes
    from .test_invoice_input_sync import init_test_database
    from .test_msmi_sync import remote_invoice
except ImportError:  # pragma: no cover - direct invocation
    from invoice_output_sync import (
        OUTPUT_INVOICE,
        InvoiceOutputSyncError,
        minvoice_source_status,
        output_invoice_payload,
        sync_output_batch,
    )
    from invoice_workbench import prepare_sync_batch, register_invoice_workbench_routes
    from test_invoice_input_sync import init_test_database
    from test_msmi_sync import remote_invoice


NOW = "2026-09-02T15:10:00"
STATUS_MAP = {
    "FIXTURE_ISSUED": "issued",
    "FIXTURE_DRAFT": "draft",
    "FIXTURE_CANCELLED": "cancelled",
    "FIXTURE_REPLACED": "replaced",
    "FIXTURE_ADJUSTED": "adjusted",
}


def now_iso() -> str:
    return NOW


def output_invoice(
    number: int,
    *,
    status: str = "FIXTURE_ISSUED",
    series: str = "OUT-A",
    invoice_number: str | None = None,
) -> dict:
    item = remote_invoice(number)
    item.update({
        "_id": f"OUTPUT-{number}-{series}",
        "khhdon": series,
        "shdon": invoice_number or str(number),
        "mstNmua": "0209999999",
        "tenNmua": "Khách hàng kiểm thử",
        "is_tthdon": 0,
        "trang_thai": 4,
        "tthai": "Đã gửi",
        "fixtureStatus": status,
    })
    return item


def documented_minvoice_invoice(
    number: int,
    *,
    series: str = "1C26TDP",
    invoice_state: int = 0,
    tax_state: int = 4,
) -> dict:
    return {
        "id": f"MINVOICE-{series}-{number}",
        "hoadon68_id": f"AUTH-{series}-{number}",
        "inv_invoiceIssuedDate": f"2026-08-{number:02d}",
        "inv_invoiceSeries": series,
        "inv_invoiceNumber": number,
        "shdon": number,
        "inv_buyerTaxCode": "0209999999",
        "inv_buyerLegalName": "Khách hàng kiểm thử",
        "tgtcthue": 100000,
        "tgtthue": 8000,
        "tgtttbso": 108000,
        "is_tthdon": invoice_state,
        "trang_thai": tax_state,
        "tthai": "Đã gửi" if tax_state == 4 else "Chờ ký",
        "details": [{
            "stt_rec0": "0001",
            "inv_itemCode": "HH-001",
            "inv_itemName": "Hàng kiểm thử",
            "inv_unitCode": "Kg",
            "inv_quantity": 2,
            "inv_unitPrice": 50000,
            "inv_TotalAmountWithoutVat": 100000,
            "inv_vatAmount": 8000,
            "inv_TotalAmount": 108000,
            "ma_thue": "8",
            "tchat": 1,
        }],
    }


def prepared_output_batch(conn) -> dict:
    batch, created = prepare_sync_batch(
        conn,
        tenant="TDP",
        source="minvoice",
        invoice_type="output",
        date_from="2026-08-01",
        date_to="2026-08-31",
        now_iso=now_iso,
    )
    assert created
    return batch


class OutputFixtureMsmi:
    def __init__(self, items):
        self.items = list(items)
        self.calls = []

    def get_invoice_series(self):
        return [
            {"value": series, "invoiceYear": 26, "invoiceForm": "1"}
            for series in sorted({
                str(item.get("inv_invoiceSeries") or item.get("khhdon") or "OUT-A")
                for item in self.items
            })
        ]

    def get_outgoing_invoices(
        self, start_date, end_date, series, start=0, count=300, include_details=True,
    ):
        self.calls.append({
            "series": series,
            "start": start,
            "size": count,
            "from_date": start_date,
            "to_date": end_date,
            "include_details": include_details,
        })
        matching = [
            item for item in self.items
            if str(item.get("inv_invoiceSeries") or item.get("khhdon") or "OUT-A") == series
        ]
        selected = matching[start:start + count]
        return {
            "ok": True,
            "code": "00",
            "data": selected,
            "total": len(matching),
        }


class FailingOutputPage(OutputFixtureMsmi):
    def get_outgoing_invoices(self, *args, **kwargs):
        if kwargs["start"] > 0:
            raise RuntimeError("fixture output page failed OUTPUT-PRIVATE")
        return super().get_outgoing_invoices(*args, **kwargs)


class InvoiceOutputSyncTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_test_database(self.conn)
        self.batch = prepared_output_batch(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def sync(self, client, **kwargs):
        return sync_output_batch(
            self.conn,
            client,
            self.batch["id"],
            now_iso,
            status_map=STATUS_MAP,
            status_fields=["fixtureStatus"],
            reference_fields=["fixtureReference"],
            **kwargs,
        )

    def test_provider_test_environment_cannot_enter_business_database(self):
        client = OutputFixtureMsmi([output_invoice(1)])
        client.is_test_environment = True
        with self.assertRaisesRegex(InvoiceOutputSyncError, 'kiểm thử'):
            self.sync(client)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM outgoing_source_invoices').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0], 0)

    def test_documented_minvoice_schema_and_status_contract_are_normalized(self):
        cases = {
            (0, 4): "issued",
            (0, 1): "draft",
            (1, 4): "cancelled",
            (2, 4): "adjusted",
            (3, 4): "replaced",
            (4, 4): "unknown",
            (5, 4): "replaced",
            (6, 4): "adjusted",
            (0, 6): "unknown",
        }
        for (invoice_state, tax_state), expected in cases.items():
            remote = documented_minvoice_invoice(
                1, invoice_state=invoice_state, tax_state=tax_state,
            )
            self.assertEqual(expected, minvoice_source_status(remote)[1])

        result = sync_output_batch(
            self.conn,
            OutputFixtureMsmi([documented_minvoice_invoice(1)]),
            self.batch["id"],
            now_iso,
        )
        stored = self.conn.execute(
            "SELECT source,invoice_series,invoice_number,invoice_date,buyer_name,"
            "source_status_class,stock_status FROM outgoing_source_invoices"
        ).fetchone()
        line = self.conn.execute(
            "SELECT source_item_code,source_item_name,source_unit,qty,unit_price,amount,tax_rate "
            "FROM outgoing_source_invoice_items"
        ).fetchone()
        self.assertEqual(
            ("minvoice", "1C26TDP", "1", "2026-08-01", "Khách hàng kiểm thử", "issued", "pending_mapping"),
            tuple(stored),
        )
        self.assertEqual(
            ("HH-001", "Hàng kiểm thử", "Kg", 2.0, 50000.0, 100000.0, "8"),
            tuple(line),
        )
        self.assertEqual("minvoice_api_v1.0.9", result["status_contract"])

    def test_series_cursor_resumes_without_duplicate_invoices(self):
        client = OutputFixtureMsmi([
            documented_minvoice_invoice(1, series="1C26AAA"),
            documented_minvoice_invoice(2, series="1C26BBB"),
        ])
        first = sync_output_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=1, page_size=1,
        )
        second = sync_output_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=1, page_size=1,
        )
        third = sync_output_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=2, page_size=1,
        )
        self.assertFalse(first["complete"])
        self.assertTrue(second["complete"])
        self.assertTrue(third["complete"])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_invoices"
        ).fetchone()[0])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_events"
        ).fetchone()[0])

    def test_reconciliation_reports_partial_until_entire_pass_finishes(self):
        client = OutputFixtureMsmi([
            documented_minvoice_invoice(1, series="1C26AAA"),
            documented_minvoice_invoice(2, series="1C26AAA"),
        ])
        initial = sync_output_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=2, page_size=1,
        )
        partial_reconcile = sync_output_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=1, page_size=1,
        )
        finished_reconcile = sync_output_batch(
            self.conn, client, self.batch["id"], now_iso, max_pages=1, page_size=1,
        )
        self.assertTrue(initial["complete"])
        self.assertFalse(partial_reconcile["complete"])
        self.assertTrue(partial_reconcile["more_history"])
        self.assertEqual("partial", partial_reconcile["status"])
        self.assertTrue(finished_reconcile["complete"])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_invoices"
        ).fetchone()[0])

    def test_output_type_and_august_bounds_reach_every_page_and_repeat_is_idempotent(self):
        client = OutputFixtureMsmi([
            output_invoice(31, series="SERIES-A", invoice_number="0001"),
            output_invoice(1, series="SERIES-B", invoice_number="0001"),
        ])
        first = self.sync(client, page_size=1, max_pages=5)
        repeated = self.sync(client, page_size=1, max_pages=5)

        self.assertTrue(first["complete"])
        self.assertEqual(2, first["new_invoices"])
        self.assertEqual(0, repeated["new_invoices"])
        self.assertEqual(2, repeated["known_invoices"])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_invoices"
        ).fetchone()[0])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_sync_batch_output_invoices"
        ).fetchone()[0])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(DISTINCT business_key) FROM outgoing_source_invoices"
        ).fetchone()[0], "cùng số nhưng khác ký hiệu phải là hai khóa nghiệp vụ")
        for call in client.calls:
            self.assertEqual("2026-08-01", call["from_date"])
            self.assertEqual("2026-08-31", call["to_date"])
            self.assertTrue(call["include_details"])
        payload_text = json.dumps(output_invoice_payload(self.conn, self.batch["id"]), ensure_ascii=False)
        self.assertNotIn("OUTPUT-", payload_text)
        self.assertNotIn("raw_json", payload_text)

    def test_source_invoice_outside_selected_range_is_rejected_and_rolled_back(self):
        outside = output_invoice(1)
        outside["tdlap"] = "2026-09-01"
        client = OutputFixtureMsmi([outside])

        with self.assertRaisesRegex(InvoiceOutputSyncError, "ngoài khoảng ngày"):
            self.sync(client)

        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_invoices"
        ).fetchone()[0])
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_sync_batch_output_invoices"
        ).fetchone()[0])
        batch = self.conn.execute(
            "SELECT status,error_code FROM invoice_sync_batches WHERE id=?", (self.batch["id"],)
        ).fetchone()
        self.assertEqual(("error", "source_data_out_of_range"), tuple(batch))

    def test_only_explicitly_mapped_issued_status_can_enter_mapping_queue(self):
        client = OutputFixtureMsmi([
            output_invoice(3, status="FIXTURE_ISSUED"),
            output_invoice(2, status="FIXTURE_DRAFT"),
            output_invoice(1, status="SOMETHING_UNDOCUMENTED"),
        ])
        result = self.sync(client, page_size=2)
        states = {
            row["source_status_class"]: (row["sync_status"], row["stock_status"])
            for row in self.conn.execute("SELECT * FROM outgoing_source_invoices")
        }
        self.assertEqual(("synced", "pending_mapping"), states["issued"])
        self.assertEqual(("review_required", "blocked"), states["draft"])
        self.assertEqual(("review_required", "blocked"), states["unknown"])
        self.assertEqual("quarantined", result["status"])
        self.assertEqual(2, result["error_count"])
        self.assertEqual(1, result["needs_mapping_count"])
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions"
        ).fetchone()[0], "đồng bộ đầu ra không được tự trừ kho")

        second_conn = sqlite3.connect(":memory:")
        try:
            init_test_database(second_conn)
            second_batch = prepared_output_batch(second_conn)
            undocumented = output_invoice(4)
            undocumented.pop("is_tthdon")
            undocumented.pop("trang_thai")
            undocumented.pop("tthai")
            unmapped = sync_output_batch(
                second_conn,
                OutputFixtureMsmi([undocumented]),
                second_batch["id"],
                now_iso,
                status_map={},
                status_fields=[],
            )
            self.assertTrue(unmapped["status_mapping_configured"])
            self.assertEqual("quarantined", unmapped["status"])
            self.assertEqual("unknown", second_conn.execute(
                "SELECT source_status_class FROM outgoing_source_invoices"
            ).fetchone()[0])
        finally:
            second_conn.close()

    def test_cancel_replace_adjust_events_are_idempotent_and_posted_lines_are_frozen(self):
        originals = [output_invoice(number) for number in (3, 2, 1)]
        client = OutputFixtureMsmi(originals)
        self.sync(client, page_size=3)
        self.conn.execute("UPDATE outgoing_source_invoices SET stock_status='posted'")
        before = {
            row["invoice_id"]: row["qty"] for row in self.conn.execute(
                "SELECT invoice_id,qty FROM outgoing_source_invoice_items"
            )
        }
        transitions = ["FIXTURE_CANCELLED", "FIXTURE_REPLACED", "FIXTURE_ADJUSTED"]
        changed = []
        for remote, status in zip(originals, transitions):
            copy = deepcopy(remote)
            copy["fixtureStatus"] = status
            copy["fixtureReference"] = "FIXTURE-REFERENCE"
            copy["hdhhdvu"][0]["sluong"] = 99
            copy["hdhhdvu"][0]["thtien"] = 990000
            changed.append(copy)
        client.items = changed
        self.sync(client, page_size=3)
        event_count = self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_events"
        ).fetchone()[0]
        self.sync(client, page_size=3)

        self.assertEqual(event_count, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_events"
        ).fetchone()[0], "retry không được nhân đôi sự kiện trạng thái")
        self.assertEqual(
            {"cancelled", "replaced", "adjusted"},
            {row[0] for row in self.conn.execute(
                "SELECT source_status_class FROM outgoing_source_invoices"
            )},
        )
        self.assertTrue(all(row[0] == "reconcile_required" for row in self.conn.execute(
            "SELECT sync_status FROM outgoing_source_invoices"
        )))
        self.assertTrue(all(row[0] == "reversal_required" for row in self.conn.execute(
            "SELECT stock_status FROM outgoing_source_invoices"
        )))
        after = {
            row["invoice_id"]: row["qty"] for row in self.conn.execute(
                "SELECT invoice_id,qty FROM outgoing_source_invoice_items"
            )
        }
        self.assertEqual(before, after, "dòng đã post phải đóng băng cho đến khi reversal có kiểm soát")

    def test_bad_payload_is_quarantined_without_inventing_stock(self):
        bad = output_invoice(8)
        bad["tgtttbso"] = -1
        result = self.sync(OutputFixtureMsmi([bad]))
        row = self.conn.execute("SELECT * FROM outgoing_source_invoices").fetchone()
        self.assertEqual("review_required", row["sync_status"])
        self.assertEqual("blocked", row["stock_status"])
        self.assertEqual("quarantined", result["status"])
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_invoice_items"
        ).fetchone()[0])

    def test_later_page_failure_rolls_back_rows_and_records_count_only_error(self):
        client = FailingOutputPage([output_invoice(3), output_invoice(2), output_invoice(1)])
        with self.assertRaisesRegex(RuntimeError, "fixture output page failed"):
            self.sync(client, page_size=2, max_pages=3)
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM outgoing_source_invoices"
        ).fetchone()[0])
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_sync_batch_output_invoices"
        ).fetchone()[0])
        batch = self.conn.execute(
            "SELECT status,error_code FROM invoice_sync_batches WHERE id=?", (self.batch["id"],)
        ).fetchone()
        self.assertEqual(("error", "sync_failed"), tuple(batch))
        audit = "\n".join(row[0] for row in self.conn.execute(
            "SELECT metadata_json FROM audit_log WHERE event_type='invoice_output.sync'"
        ))
        self.assertNotIn("OUTPUT-PRIVATE", audit)

    def test_invalid_status_configuration_is_rejected_before_source_read(self):
        client = OutputFixtureMsmi([output_invoice(1)])
        with self.assertRaises(InvoiceOutputSyncError):
            sync_output_batch(
                self.conn,
                client,
                self.batch["id"],
                now_iso,
                status_map={"X": "probably-issued"},
                status_fields=["fixtureStatus"],
            )
        self.assertEqual([], client.calls)


class InvoiceOutputRouteAndUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tdp074_route_")
        self.path = Path(self.temp.name) / "test.sqlite3"
        with self.db() as conn:
            init_test_database(conn)
        self.fake = OutputFixtureMsmi([output_invoice(1)])
        config = {
            "tenant_code": "TDP",
        }
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_invoice_workbench_routes(app, {
            "db": self.db,
            "now_iso": now_iso,
            "setting_get": lambda conn, key, default="": config.get(key, default),
            "audit_event": None,
            "create_minvoice_client": lambda: self.fake,
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

    def test_route_syncs_and_returns_sanitized_output_queue(self):
        prepared = self.client.post("/api/invoice-workbench/batches", json={
            "source": "minvoice",
            "invoice_type": "output",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }).get_json()["batch"]
        synced = self.client.post(
            f"/api/invoice-workbench/batches/{prepared['id']}/sync", json={}
        )
        queue = self.client.get(
            f"/api/invoice-workbench/batches/{prepared['id']}/invoices"
        )
        self.assertEqual(200, synced.status_code, synced.get_data(as_text=True))
        self.assertEqual(200, queue.status_code)
        text = queue.get_data(as_text=True)
        self.assertEqual("Khách hàng kiểm thử", queue.get_json()["items"][0]["buyer_name"])
        self.assertNotIn("OUTPUT-", text)
        self.assertNotIn("raw_json", text)

    def test_route_rolls_back_partial_rows_but_persists_safe_error_status(self):
        self.fake = FailingOutputPage([
            output_invoice(1), output_invoice(2), output_invoice(3),
        ])
        prepared = self.client.post("/api/invoice-workbench/batches", json={
            "source": "minvoice",
            "invoice_type": "output",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }).get_json()["batch"]
        response = self.client.post(
            f"/api/invoice-workbench/batches/{prepared['id']}/sync",
            json={"page_size": 1, "max_pages": 3},
        )
        self.assertEqual(502, response.status_code)
        with self.db() as conn:
            self.assertEqual(0, conn.execute(
                "SELECT COUNT(*) FROM outgoing_source_invoices"
            ).fetchone()[0])
            batch = conn.execute(
                "SELECT status,error_code,error_count FROM invoice_sync_batches WHERE id=?",
                (prepared["id"],),
            ).fetchone()
            self.assertEqual(("error", "sync_failed", 1), tuple(batch))
            audit = conn.execute(
                """SELECT event_type,status,message,metadata_json FROM audit_log
                   WHERE entity_type='invoice_sync_batch' AND entity_id=?
                   ORDER BY id DESC LIMIT 1""",
                (str(prepared["id"]),),
            ).fetchone()
            self.assertEqual(("invoice_output.sync", "error", ""), tuple(audit)[:3])
            self.assertEqual(
                {
                    "error_code": "sync_failed",
                    "invoice_type": OUTPUT_INVOICE,
                    "source": "minvoice",
                },
                json.loads(audit["metadata_json"]),
            )
            self.assertNotIn("OUTPUT-PRIVATE", audit["metadata_json"])

    def test_output_payload_validation_error_is_labeled_as_minvoice_source(self):
        # No remote/business identity: strict shared normalization raises its
        # legacy-named MsmiError, but the operational source is still M-Invoice.
        self.fake = OutputFixtureMsmi([{
            "inv_invoiceIssuedDate": "2026-08-01",
            "is_tthdon": 0,
            "trang_thai": 4,
            "details": [],
        }])
        prepared = self.client.post("/api/invoice-workbench/batches", json={
            "source": "minvoice",
            "invoice_type": "output",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }).get_json()["batch"]
        response = self.client.post(
            f"/api/invoice-workbench/batches/{prepared['id']}/sync", json={},
        )
        self.assertEqual(502, response.status_code)
        with self.db() as conn:
            batch = conn.execute(
                "SELECT status,error_code,error_count FROM invoice_sync_batches WHERE id=?",
                (prepared["id"],),
            ).fetchone()
            self.assertEqual(("error", "minvoice_source_error", 1), tuple(batch))

    def test_ui_has_output_sync_queue_and_explicit_status_gate_copy(self):
        from .test_invoice_workbench_listing import rendered_invoice_html
        source = (Path(__file__).resolve().parent / "static" / "app.js").read_text(encoding="utf-8")
        source += rendered_invoice_html()
        for expected in (
            "Tải/tiếp tục đầu ra",
            "Trạng thái hóa đơn",
            "Lịch sử các lần tải liên quan",
            "invoiceOutputRows",
            "M-Invoice",
            "Excel đúng bộ lọc",
            "Không cộng số lượng giữa các lần tải",
            "còn dữ liệu, bấm tiếp để tải hết đúng khoảng ngày",
            "state.invoiceInputRows",
            "Ghi nhận hóa đơn đã phát hành",
            "hàng trong kho vẫn được giữ để chờ đối soát M-Invoice",
            "Phải ghép đủ mã, đơn vị và xác nhận mới ghi kho hóa đơn",
        ):
            self.assertTrue(expected in source, expected)
        self.assertNotIn("o.msmi.state", source)
        self.assertNotIn("o.msmi.invoices", source)
        self.assertNotIn("Đã ghi nhận hóa đơn phát hành và ghi xuất kho", source)


if __name__ == "__main__":
    unittest.main()
