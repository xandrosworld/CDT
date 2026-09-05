import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

try:
    from contract_modules import (
        OPENING_WAREHOUSE_BACKFILL_SETTING,
        OPENING_WAREHOUSE_GOLDEN_SHA256,
        backfill_opening_warehouse_codes,
        init_contract_schema,
    )
    from inventory_export import collect_inventory_export_model
    from invoice_workbench import init_invoice_workbench_schema
except ImportError:  # pragma: no cover - package invocation
    from .contract_modules import (
        OPENING_WAREHOUSE_BACKFILL_SETTING,
        OPENING_WAREHOUSE_GOLDEN_SHA256,
        backfill_opening_warehouse_codes,
        init_contract_schema,
    )
    from .inventory_export import collect_inventory_export_model
    from .invoice_workbench import init_invoice_workbench_schema


def fixture_golden(path: Path) -> str:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ton"
    sheet.append([
        "MÃ TĐP", "TÊN TDP", "Tên trên HĐ", "MÃ KHO", "T/Suất", "ĐVT",
        "Số lượng", "Đơn giá", "Thành tiền",
    ])
    sheet.append(["P-001", "Hàng một", "Hàng một", "KHO-01", "8", "Kg", 2, 10, 20])
    sheet.append(["P-001", "Hàng một", "Hàng một", "KHO-02", "8", "Kg", 3, 10, 30])
    sheet.append(["P-002", "Hàng hai", "Hàng hai", "P-002", "8", "Kg", 1, 20, 20])
    workbook.save(path)
    workbook.close()
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class OpeningWarehouseMigrationUnitTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(
            """
            CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE products(
                code TEXT PRIMARY KEY,name TEXT,unit TEXT,tax TEXT,
                buy_price REAL,sell_price REAL
            );
            CREATE TABLE balances(id INTEGER PRIMARY KEY);
            CREATE TABLE orders(id INTEGER PRIMARY KEY);
            """
        )
        init_contract_schema(self.conn)
        self.conn.executemany(
            "INSERT INTO products(code,name,unit,tax,buy_price,sell_price) VALUES(?,?,?,?,?,?)",
            [
                ("P-001", "Hàng một", "Kg", "8", 10, 12),
                ("P-002", "Hàng hai", "Kg", "8", 20, 24),
            ],
        )
        self.conn.executemany(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,warehouse_codes_json,qty_in,qty_out,unit_cost,
                   source_type,source_id,source_line,status,created_at,updated_at
               ) VALUES('2026-08-01',?,'[]',?,0,?,'OPENING','2026-08',?,'posted','now','now')""",
            [("P-001", 5, 10, "P-001"), ("P-002", 1, 20, "P-002")],
        )

    def tearDown(self):
        self.conn.close()

    def test_hash_gated_backfill_preserves_multiple_codes_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "golden.xlsx"
            digest = fixture_golden(path)
            first = backfill_opening_warehouse_codes(
                self.conn, path, expected_sha256=digest,
            )
            self.assertEqual(("backfilled", 2, 2), (
                first["status"], first["updated"], first["products"],
            ))
            rows = self.conn.execute(
                """SELECT product_code,warehouse_codes_json FROM inventory_transactions
                   WHERE source_type='OPENING' ORDER BY product_code"""
            ).fetchall()
            self.assertEqual(["KHO-01", "KHO-02"], json.loads(rows[0]["warehouse_codes_json"]))
            self.assertEqual(["P-002"], json.loads(rows[1]["warehouse_codes_json"]))

            before = [tuple(row) for row in rows]
            second = backfill_opening_warehouse_codes(
                self.conn, path, expected_sha256=digest,
            )
            after = [tuple(row) for row in self.conn.execute(
                """SELECT product_code,warehouse_codes_json FROM inventory_transactions
                   WHERE source_type='OPENING' ORDER BY product_code"""
            )]
            self.assertEqual(("already_complete", 0), (second["status"], second["updated"]))
            self.assertEqual(before, after)

    def test_wrong_hash_fails_before_any_opening_row_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "altered.xlsx"
            fixture_golden(path)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                backfill_opening_warehouse_codes(
                    self.conn, path, expected_sha256="0" * 64,
                )
        self.assertEqual(
            ["[]", "[]"],
            [row[0] for row in self.conn.execute(
                """SELECT warehouse_codes_json FROM inventory_transactions
                   WHERE source_type='OPENING' ORDER BY product_code"""
            )],
        )

    def test_missing_optional_asset_does_not_break_startup(self):
        result = backfill_opening_warehouse_codes(
            self.conn, Path("does-not-exist") / "golden.xlsx",
        )
        self.assertEqual(("asset_absent", 0), (result["status"], result["updated"]))

    def test_evidence_write_failure_rolls_back_all_row_updates(self):
        self.conn.execute(
            f"""CREATE TRIGGER reject_opening_warehouse_evidence
                BEFORE INSERT ON settings
                WHEN NEW.key='{OPENING_WAREHOUSE_BACKFILL_SETTING}'
                BEGIN SELECT RAISE(ABORT,'simulated evidence failure'); END"""
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "golden.xlsx"
            digest = fixture_golden(path)
            with self.assertRaisesRegex(sqlite3.IntegrityError, "simulated evidence failure"):
                backfill_opening_warehouse_codes(
                    self.conn, path, expected_sha256=digest,
                )
        self.assertEqual(
            ["[]", "[]"],
            [row[0] for row in self.conn.execute(
                """SELECT warehouse_codes_json FROM inventory_transactions
                   WHERE source_type='OPENING' ORDER BY product_code"""
            )],
        )


class OpeningWarehouseSnapshotCloneTest(unittest.TestCase):
    def test_server_and_portable_build_wire_the_hash_pinned_golden(self):
        root = Path(__file__).resolve().parent.parent
        server = (root / "tdp_system" / "server.py").read_text(encoding="utf-8")
        build = (root / "BUILD_PORTABLE.ps1").read_text(encoding="utf-8")
        self.assertIn(
            "init_contract_schema(conn, opening_template_path=OPENING_TEMPLATE_SOURCE)",
            server,
        )
        self.assertIn('--add-data "$openingTemplateSource;."', build)
        self.assertIn(OPENING_WAREHOUSE_GOLDEN_SHA256, build)

    def test_official_golden_backfills_clone_without_touching_source_database(self):
        root = Path(__file__).resolve().parent.parent
        source_db = root / "tdp_system" / "data" / "tdp.sqlite3"
        golden_candidates = [
            path for path in (root / "_HANDOFF" / "EXTERNAL_INPUTS").glob("*T8-2026*.xlsx")
            if hashlib.sha256(path.read_bytes()).hexdigest().upper()
            == OPENING_WAREHOUSE_GOLDEN_SHA256
        ]
        if not source_db.is_file() or not golden_candidates:
            self.skipTest("Snapshot DB/golden chính thức không có trong checkout này")

        source_hash_before = hashlib.sha256(source_db.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            clone_path = Path(directory) / "migration-clone.sqlite3"
            source = sqlite3.connect(source_db.resolve().as_uri() + "?mode=ro", uri=True)
            clone = sqlite3.connect(clone_path)
            clone.row_factory = sqlite3.Row
            try:
                source.backup(clone)
            finally:
                source.close()

            init_contract_schema(clone, opening_template_path=golden_candidates[0])
            clone.commit()
            rows = clone.execute(
                """SELECT product_code,warehouse_codes_json FROM inventory_transactions
                   WHERE source_type='OPENING' AND source_id='2026-08'
                   ORDER BY product_code"""
            ).fetchall()
            decoded = [(row["product_code"], json.loads(row["warehouse_codes_json"])) for row in rows]
            self.assertEqual(334, len(decoded))
            self.assertTrue(all(codes for _product, codes in decoded))
            self.assertEqual(113, sum(
                any(code != product for code in codes) for product, codes in decoded
            ))
            self.assertEqual(43, sum(len(codes) > 1 for _product, codes in decoded))
            evidence = json.loads(clone.execute(
                "SELECT value FROM settings WHERE key=?",
                (OPENING_WAREHOUSE_BACKFILL_SETTING,),
            ).fetchone()["value"])
            self.assertEqual((334, 113, 43), (
                evidence["products"], evidence["different_from_tdp"],
                evidence["multiple_warehouse_codes"],
            ))
            init_invoice_workbench_schema(clone)
            exported = collect_inventory_export_model(
                clone, date_from="2026-08-01", date_to="2026-08-31",
            )
            self.assertEqual(334, len(exported["items"]))
            self.assertEqual(113, sum(
                item["warehouse_code"] != item["product_code"]
                for item in exported["items"]
            ))
            self.assertEqual(43, sum(
                " / " in item["warehouse_code"] for item in exported["items"]
            ))

            snapshot = [tuple(row) for row in rows]
            init_contract_schema(clone, opening_template_path=golden_candidates[0])
            clone.commit()
            self.assertEqual(snapshot, [tuple(row) for row in clone.execute(
                """SELECT product_code,warehouse_codes_json FROM inventory_transactions
                   WHERE source_type='OPENING' AND source_id='2026-08'
                   ORDER BY product_code"""
            )])
            clone.close()

        self.assertEqual(source_hash_before, hashlib.sha256(source_db.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
