from __future__ import annotations

import sqlite3
import unittest
from copy import deepcopy

try:
    from .invoice_input_sync import sync_input_batch
    from .invoice_mapping import save_conversion, save_mapping
    from .invoice_receipt import InvoiceReceiptError, create_input_receipt
    from .invoice_workbench import prepare_sync_batch
    from .test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from .test_msmi_sync import remote_invoice
except ImportError:  # pragma: no cover - direct invocation
    from invoice_input_sync import sync_input_batch
    from invoice_mapping import save_conversion, save_mapping
    from invoice_receipt import InvoiceReceiptError, create_input_receipt
    from invoice_workbench import prepare_sync_batch
    from test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from test_msmi_sync import remote_invoice


NOW = "2026-09-02T15:35:00"


def now_iso() -> str:
    return NOW


def receipt_remote() -> dict:
    remote = remote_invoice(8)
    remote["hdhhdvu"] = [
        {
            "ma": "BOXED",
            "ten": "Hàng đóng thùng",
            "dvtinh": "thùng",
            "sluong": 2,
            "dgia": 5000,
            "thtien": 10000,
            "tchat": 1,
            "tsuat": "8%",
        },
        {
            "ma": "BOXED",
            "ten": "Hàng đóng thùng",
            "dvtinh": "thùng",
            "sluong": 1,
            "dgia": 0,
            "thtien": 0,
            "tchat": 2,
            "tsuat": 0,
        },
        {
            "ma": "DISCOUNT",
            "ten": "Chiết khấu thương mại",
            "sluong": 0,
            "dgia": 0,
            "thtien": -500,
            "tchat": 3,
            "tsuat": 0,
        },
    ]
    return remote


class ConvertedInputReceiptTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_test_database(self.conn)
        self.conn.execute(
            "INSERT INTO products(code,name,unit) VALUES('P-PACK','Hàng theo gói','gói')"
        )
        self.batch = prepare_sync_batch(
            self.conn,
            tenant="TDP",
            source="msmi",
            invoice_type="input",
            date_from="2026-08-01",
            date_to="2026-08-31",
            now_iso=now_iso,
        )[0]
        self.remote = receipt_remote()
        self.client = DateBoundedMsmi([self.remote])
        sync_input_batch(self.conn, self.client, self.batch["id"], now_iso)
        self.invoice_id = self.conn.execute("SELECT id FROM msmi_invoices").fetchone()[0]
        self.first_item = self.conn.execute(
            "SELECT id FROM msmi_invoice_items WHERE line_index=1"
        ).fetchone()[0]

    def tearDown(self):
        self.conn.close()

    def confirm_conversion(self):
        save_mapping(
            self.conn,
            direction="input",
            item_id=self.first_item,
            product_code="P-PACK",
            now_iso=now_iso,
        )
        return save_conversion(
            self.conn,
            direction="input",
            item_id=self.first_item,
            conversion_factor=30,
            now_iso=now_iso,
        )

    def test_receipt_uses_converted_snapshots_promo_zero_cost_and_skips_discount(self):
        conversion = self.confirm_conversion()
        self.assertEqual(2, conversion["applied_lines"])
        result = create_input_receipt(self.conn, self.invoice_id, now_iso)
        rows = self.conn.execute(
            """SELECT source_line,product_code,qty_in,unit_cost
               FROM inventory_transactions WHERE source_type='MSMI_INPUT' ORDER BY source_line"""
        ).fetchall()
        self.assertEqual(2, result["new_inventory_lines"])
        self.assertEqual(1, result["non_inventory_lines"])
        self.assertEqual([60, 30], [row["qty_in"] for row in rows])
        self.assertAlmostEqual(166.666667, rows[0]["unit_cost"], places=6)
        self.assertEqual(0, rows[1]["unit_cost"])
        self.assertEqual({"1", "2"}, {row["source_line"] for row in rows})
        self.assertAlmostEqual(10000, sum(row["qty_in"] * row["unit_cost"] for row in rows), places=3)
        self.assertEqual("posted", self.conn.execute(
            "SELECT receipt_status FROM msmi_invoices WHERE id=?", (self.invoice_id,)
        ).fetchone()[0])
        batch = self.conn.execute(
            "SELECT posted_count,status FROM invoice_sync_batches WHERE id=?", (self.batch["id"],)
        ).fetchone()
        self.assertEqual(1, batch["posted_count"])

    def test_repeat_post_is_idempotent_and_does_not_duplicate_ledger(self):
        self.confirm_conversion()
        first = create_input_receipt(self.conn, self.invoice_id, now_iso)
        repeat = create_input_receipt(self.conn, self.invoice_id, now_iso)
        self.assertEqual(2, first["new_inventory_lines"])
        self.assertEqual(0, repeat["new_inventory_lines"])
        self.assertTrue(repeat["idempotent"])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions WHERE source_type='MSMI_INPUT'"
        ).fetchone()[0])

    def test_unconverted_or_stale_mapping_is_blocked_without_writes(self):
        save_mapping(
            self.conn,
            direction="input",
            item_id=self.first_item,
            product_code="P-PACK",
            now_iso=now_iso,
        )
        with self.assertRaisesRegex(InvoiceReceiptError, "chưa ghép đủ mã"):
            create_input_receipt(self.conn, self.invoice_id, now_iso)
        self.confirm_conversion()
        self.conn.execute("UPDATE invoice_line_mappings SET conversion_factor=99")
        with self.assertRaisesRegex(InvoiceReceiptError, "Snapshot quy đổi"):
            create_input_receipt(self.conn, self.invoice_id, now_iso)
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions"
        ).fetchone()[0])

    def test_mid_write_failure_rolls_back_every_inventory_line_and_receipt_status(self):
        self.confirm_conversion()
        self.conn.execute(
            """CREATE TRIGGER fail_second_receipt_line BEFORE INSERT ON inventory_transactions
               WHEN NEW.source_type='MSMI_INPUT' AND NEW.source_line='2'
               BEGIN SELECT RAISE(ABORT,'simulated second line failure'); END"""
        )
        with self.assertRaisesRegex(InvoiceReceiptError, "toàn bộ bút toán đã hoàn tác"):
            create_input_receipt(self.conn, self.invoice_id, now_iso)
        self.assertEqual(0, self.conn.execute(
            "SELECT COUNT(*) FROM inventory_transactions"
        ).fetchone()[0])
        self.assertEqual("ready", self.conn.execute(
            "SELECT receipt_status FROM msmi_invoices WHERE id=?", (self.invoice_id,)
        ).fetchone()[0])

    def test_remote_change_after_post_freezes_receipt_and_inventory(self):
        self.confirm_conversion()
        create_input_receipt(self.conn, self.invoice_id, now_iso)
        before = [tuple(row) for row in self.conn.execute(
            "SELECT product_code,qty_in,unit_cost FROM inventory_transactions ORDER BY source_line"
        )]
        changed = deepcopy(self.remote)
        changed["hdhhdvu"][0]["sluong"] = 99
        changed["hdhhdvu"][0]["thtien"] = 495000
        self.client.items = [changed]
        sync_input_batch(self.conn, self.client, self.batch["id"], now_iso)
        self.assertEqual("review_required", self.conn.execute(
            "SELECT sync_status FROM msmi_invoices WHERE id=?", (self.invoice_id,)
        ).fetchone()[0])
        self.assertEqual(before, [tuple(row) for row in self.conn.execute(
            "SELECT product_code,qty_in,unit_cost FROM inventory_transactions ORDER BY source_line"
        )])
        repeat = create_input_receipt(self.conn, self.invoice_id, now_iso)
        self.assertTrue(repeat["idempotent"])


if __name__ == "__main__":
    unittest.main()
