from __future__ import annotations

import sqlite3
import unittest
from copy import deepcopy
from pathlib import Path

from flask import Flask

try:
    from .invoice_input_sync import sync_input_batch
    from .invoice_inventory import (
        InvoiceInventoryError,
        invoice_inventory_trace,
        invoice_stock_rows,
        post_output_invoice,
        register_invoice_inventory_routes,
        reverse_output_invoice,
    )
    from .invoice_mapping import save_mapping
    from .invoice_output_sync import sync_output_batch
    from .invoice_receipt import create_input_receipt
    from .invoice_workbench import prepare_sync_batch
    from .test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from .test_invoice_output_sync import OutputFixtureMsmi, STATUS_MAP, output_invoice
    from .test_msmi_sync import remote_invoice
except ImportError:  # pragma: no cover - direct invocation
    from invoice_input_sync import sync_input_batch
    from invoice_inventory import (
        InvoiceInventoryError,
        invoice_inventory_trace,
        invoice_stock_rows,
        post_output_invoice,
        register_invoice_inventory_routes,
        reverse_output_invoice,
    )
    from invoice_mapping import save_mapping
    from invoice_output_sync import sync_output_batch
    from invoice_receipt import create_input_receipt
    from invoice_workbench import prepare_sync_batch
    from test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from test_invoice_output_sync import OutputFixtureMsmi, STATUS_MAP, output_invoice
    from test_msmi_sync import remote_invoice


NOW = "2026-09-02T16:00:00"


def now_iso() -> str:
    return NOW


class InvoiceInventoryLedgerTests(unittest.TestCase):
    def test_future_receipt_does_not_hide_negative_balance_on_output_date(self):
        self._input(qty=5)
        self.conn.execute("UPDATE inventory_transactions SET qty_in=0 WHERE source_type='OPENING'")
        self.conn.execute("UPDATE invoice_inventory_ledger SET txn_date='2026-08-31' WHERE direction='input'")
        output_id, *_ = self._output(qty=4)
        self.conn.execute("UPDATE outgoing_source_invoices SET invoice_date='2026-08-20' WHERE id=?", (output_id,))
        with self.assertRaises(InvoiceInventoryError) as caught:
            post_output_invoice(self.conn, output_id, confirmed=True, now_iso=now_iso)
        self.assertEqual(caught.exception.code, "negative_stock")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM invoice_inventory_ledger WHERE direction='output'").fetchone()[0], 0)

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_test_database(self.conn)
        self.conn.execute(
            "INSERT INTO products(code,name,unit) VALUES('P-INV','Hàng kiểm thử sổ hóa đơn','kg')"
        )
        self.conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                   source_line,status,note,created_at,updated_at
               ) VALUES('2026-08-01','P-INV',10,0,100,'OPENING','2026-08','1',
                        'posted','fixture',?,?)""",
            (NOW, NOW),
        )

    def tearDown(self):
        self.conn.close()

    def _input(self, number: int = 2, qty: float = 5) -> int:
        remote = remote_invoice(number)
        remote["hdhhdvu"][0].update(ma="IN-INV", ten="Hàng nhập fixture", sluong=qty,
                                      dgia=100, thtien=qty * 100)
        remote["tgtcthue"] = qty * 100
        remote["tgtttbso"] = qty * 100
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
            product_code="P-INV", now_iso=now_iso,
        )
        create_input_receipt(self.conn, invoice_id, now_iso)
        return invoice_id

    def _output(self, number: int = 3, qty: float = 4, status: str = "FIXTURE_ISSUED"):
        remote = output_invoice(number, status=status, series=f"OUT-{number}")
        remote["hdhhdvu"][0].update(ma=f"OUT-INV-{number}", ten=f"Hàng xuất {number}",
                                      sluong=qty, dgia=200, thtien=qty * 200)
        remote["tgtcthue"] = qty * 200
        remote["tgtttbso"] = qty * 200
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
        item_ids = [int(row[0]) for row in self.conn.execute(
            "SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index",
            (invoice_id,),
        )]
        if status == "FIXTURE_ISSUED":
            for item_id in item_ids:
                save_mapping(
                    self.conn, direction="output", item_id=item_id,
                    product_code="P-INV", now_iso=now_iso,
                )
        return invoice_id, remote, client, batch, item_ids

    def test_equation_idempotence_and_traceability_ignore_operational_projection(self):
        input_id = self._input()
        # Both rows belong to the operational/compatibility ledger and must not
        # change the canonical invoice balance a second time.
        self.conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                   source_line,status,note,created_at,updated_at
               ) VALUES('2026-08-03','P-INV',0,100,0,'OUTGOING_DRAFT','DRAFT-1','1',
                        'reserved','fixture',?,?)""",
            (NOW, NOW),
        )
        output_id, _remote, _client, _batch, _items = self._output()
        first = post_output_invoice(self.conn, output_id, confirmed=True, now_iso=now_iso)
        repeat = post_output_invoice(self.conn, output_id, confirmed=True, now_iso=now_iso)

        row = invoice_stock_rows(self.conn, "2026-08-31")[0]
        self.assertEqual(10, row["opening_qty"])
        self.assertEqual(5, row["input_qty"])
        self.assertEqual(4, row["output_qty"])
        self.assertEqual(11, row["closing_qty"])
        self.assertEqual(1, first["new_inventory_lines"])
        self.assertTrue(repeat["idempotent"])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_inventory_ledger WHERE event_type='POST'"
        ).fetchone()[0])
        self.assertEqual(2, self.conn.execute(
            """SELECT COUNT(*) FROM invoice_inventory_ledger
               WHERE mapping_revision_id IS NOT NULL AND confirmation_id IS NOT NULL"""
        ).fetchone()[0])
        self.assertEqual(1, len(invoice_inventory_trace(self.conn, "input", input_id)["events"]))
        output_trace = invoice_inventory_trace(self.conn, "output", output_id)["events"]
        self.assertEqual(1, len(output_trace))
        self.assertEqual(output_id, output_trace[0]["source_invoice_id"])
        self.assertGreater(output_trace[0]["source_line_id"], 0)

    def test_draft_unknown_unconfirmed_and_insufficient_stock_never_subtract(self):
        issued_id, _remote, _client, _batch, _items = self._output(number=4, qty=11)
        with self.assertRaisesRegex(InvoiceInventoryError, "xác nhận rõ"):
            post_output_invoice(self.conn, issued_id, confirmed=False, now_iso=now_iso)
        with self.assertRaisesRegex(InvoiceInventoryError, "không đủ tồn"):
            post_output_invoice(self.conn, issued_id, confirmed=True, now_iso=now_iso)
        for number, status in ((5, "FIXTURE_DRAFT"), (6, "UNDOCUMENTED")):
            invoice_id, *_ = self._output(number=number, qty=1, status=status)
            with self.assertRaisesRegex(InvoiceInventoryError, "đã phát hành"):
                post_output_invoice(self.conn, invoice_id, confirmed=True, now_iso=now_iso)
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_inventory_ledger"
        ).fetchone()[0])

    def test_legacy_msmi_output_can_never_post_inventory(self):
        invoice_id, *_ = self._output(number=12, qty=1)
        self.conn.execute(
            "UPDATE outgoing_source_invoices SET source='msmi' WHERE id=?", (invoice_id,)
        )
        with self.assertRaises(InvoiceInventoryError) as raised:
            post_output_invoice(self.conn, invoice_id, confirmed=True, now_iso=now_iso)
        self.assertEqual("invalid_output_source", raised.exception.code)
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_inventory_ledger WHERE direction='output'"
        ).fetchone()[0])

    def test_backdated_post_checks_every_later_daily_balance(self):
        first_id, *_ = self._output(number=2, qty=8)
        post_output_invoice(self.conn, first_id, confirmed=True, now_iso=now_iso)
        self._input(number=3, qty=10)
        # Current balance is 12, but posting 5 on 01/08 would make the 02/08
        # historical balance negative before the 03/08 input arrives.
        older_id, *_ = self._output(number=1, qty=5)
        with self.assertRaisesRegex(InvoiceInventoryError, "các mốc sau đó"):
            post_output_invoice(self.conn, older_id, confirmed=True, now_iso=now_iso)
        self.assertEqual(12, invoice_stock_rows(self.conn, "2026-08-31")[0]["closing_qty"])

    def test_cancel_reversal_is_append_only_and_idempotent(self):
        output_id, original, client, batch, _items = self._output(number=4, qty=4)
        post_output_invoice(self.conn, output_id, confirmed=True, now_iso=now_iso)
        changed = deepcopy(original)
        changed["fixtureStatus"] = "FIXTURE_CANCELLED"
        changed["fixtureReference"] = "FIXTURE-CANCEL-REFERENCE"
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
        self.assertEqual("reversal_required", self.conn.execute(
            "SELECT stock_status FROM outgoing_source_invoices WHERE id=?", (output_id,)
        ).fetchone()[0])
        first = reverse_output_invoice(
            self.conn, output_id, confirmed=True, note="Đã kiểm tra hóa đơn hủy", now_iso=now_iso
        )
        repeat = reverse_output_invoice(
            self.conn, output_id, confirmed=True, note="ignored on retry", now_iso=now_iso
        )
        events = invoice_inventory_trace(self.conn, "output", output_id)["events"]
        self.assertEqual(1, first["new_reversal_lines"])
        self.assertTrue(repeat["idempotent"])
        self.assertEqual(["POST", "REVERSAL"], [event["event_type"] for event in events])
        self.assertEqual(events[0]["qty_delta"], -events[1]["qty_delta"])
        self.assertTrue(events[1]["reverses_event_key"])
        self.assertEqual(6, invoice_stock_rows(self.conn, "2026-08-31")[0]["closing_qty"])
        self.assertEqual(10, invoice_stock_rows(self.conn)[0]["closing_qty"])
        self.assertEqual("reversed", self.conn.execute(
            "SELECT stock_status FROM outgoing_source_invoices WHERE id=?", (output_id,)
        ).fetchone()[0])

    def test_output_mid_write_failure_rolls_back_confirmation_events_and_status(self):
        invoice_id, _remote, _client, _batch, item_ids = self._output(number=7, qty=2)
        self.conn.execute(
            "UPDATE outgoing_source_invoice_items SET source_item_code='OUT-INV-7-B' WHERE id=?",
            (item_ids[0],),
        )
        # Re-sync a fresh two-line invoice so each line has a stable unique
        # source identity and an independently auditable mapping revision.
        self.conn.execute("DELETE FROM outgoing_source_invoice_items WHERE invoice_id=?", (invoice_id,))
        for index in (1, 2):
            self.conn.execute(
                """INSERT INTO outgoing_source_invoice_items(
                       invoice_id,line_index,source_item_code,source_item_name,source_unit,qty,
                       unit_price,amount,inventory_eligible,product_code,mapping_status,
                       conversion_factor,stock_qty,stock_unit_price
                   ) VALUES(?,?,?,?,?,1,200,200,1,'','unmapped',NULL,0,0)""",
                (invoice_id, index, f"OUT-7-{index}", f"Hàng {index}", "kg"),
            )
        item_ids = [row[0] for row in self.conn.execute(
            "SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index",
            (invoice_id,),
        )]
        for item_id in item_ids:
            save_mapping(
                self.conn, direction="output", item_id=item_id,
                product_code="P-INV", now_iso=now_iso,
            )
        self.conn.execute(
            """CREATE TRIGGER fail_second_invoice_ledger BEFORE INSERT ON invoice_inventory_ledger
               WHEN NEW.direction='output' AND NEW.source_line_index=2
               BEGIN SELECT RAISE(ABORT,'fixture second line failure'); END"""
        )
        with self.assertRaisesRegex(InvoiceInventoryError, "toàn bộ bút toán đã hoàn tác"):
            post_output_invoice(self.conn, invoice_id, confirmed=True, now_iso=now_iso)
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_inventory_ledger"
        ).fetchone()[0])
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_inventory_confirmations"
        ).fetchone()[0])
        self.assertEqual("ready", self.conn.execute(
            "SELECT stock_status FROM outgoing_source_invoices WHERE id=?", (invoice_id,)
        ).fetchone()[0])

    def test_routes_require_confirmation_and_return_read_only_stock_and_trace(self):
        output_id, *_ = self._output(number=8, qty=2)
        self.conn.commit()
        app = Flask(__name__)
        app.config["TESTING"] = True

        class SharedDb:
            def __enter__(inner):
                return self.conn

            def __exit__(inner, exc_type, exc, tb):
                if exc_type:
                    self.conn.rollback()
                else:
                    self.conn.commit()
                return False

        register_invoice_inventory_routes(app, {"db": SharedDb, "now_iso": now_iso})
        client = app.test_client()
        denied = client.post(f"/api/invoice-workbench/output/{output_id}/post", json={})
        posted = client.post(
            f"/api/invoice-workbench/output/{output_id}/post", json={"confirmed": True}
        )
        stock = client.get("/api/invoice-inventory?as_of=2026-08-31")
        trace = client.get(f"/api/invoice-inventory/source/output/{output_id}")
        invalid_date = client.get("/api/invoice-inventory?as_of=2026-02-30")
        self.assertEqual(400, denied.status_code)
        self.assertEqual(200, posted.status_code)
        self.assertTrue(stock.get_json()["read_only"])
        self.assertEqual(8, stock.get_json()["items"][0]["closing_qty"])
        self.assertEqual(1, len(trace.get_json()["events"]))
        self.assertEqual(400, invalid_date.status_code)

    def test_compact_output_hides_actions_and_retains_explicit_write_guards(self):
        from .test_invoice_workbench_listing import rendered_invoice_html
        source = (Path(__file__).resolve().parent / "static" / "app.js").read_text(encoding="utf-8")
        rendered = rendered_invoice_html()
        self.assertNotIn('data-action="post-invoice-output"', rendered)
        self.assertNotIn('data-action="reverse-invoice-output"', rendered)
        for expected in (
            'action === "post-invoice-output"',
            "Xác nhận hoàn tác xuất kho",
            'action === "reverse-invoice-output"',
            "Bút toán xuất cũ sẽ được giữ nguyên",
            "confirmed: true",
        ):
            self.assertTrue(expected in source, expected)


if __name__ == "__main__":
    unittest.main()
