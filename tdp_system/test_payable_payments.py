from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from . import server
    from .payable_ledger import sync_payable_ledger
    from .payable_payments import init_payable_payment_schema
except ImportError:  # pragma: no cover - direct invocation
    import server
    from payable_ledger import sync_payable_ledger
    from payable_payments import init_payable_payment_schema


class PayablePaymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.original_db_path = server.DB_PATH
        cls.original_data_dir = server.DATA_DIR
        cls.original_export_dir = server.EXPORT_DIR
        cls.original_testing = server.app.config.get("TESTING", False)
        server.DATA_DIR = Path(cls.temp_dir.name) / "data"
        server.EXPORT_DIR = Path(cls.temp_dir.name) / "exports"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "payable_payments.sqlite3"
        server.app.config["TESTING"] = True
        server.init_database()
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        server.DB_PATH = cls.original_db_path
        server.DATA_DIR = cls.original_data_dir
        server.EXPORT_DIR = cls.original_export_dir
        server.app.config["TESTING"] = cls.original_testing
        cls.temp_dir.cleanup()

    def setUp(self):
        with server.db() as conn:
            conn.execute("DROP TRIGGER IF EXISTS fail_payable_allocation")
            conn.execute("DELETE FROM payable_payment_revisions")
            conn.execute("DELETE FROM payable_payment_allocations")
            conn.execute("DELETE FROM payments")
            conn.execute("DELETE FROM payable_ledger_revisions")
            conn.execute("DELETE FROM payable_ledger_lines")
            conn.execute("DELETE FROM purchase_workbook_line_revisions")
            conn.execute("DELETE FROM purchase_workbook_lines")
            conn.execute("DELETE FROM purchase_order_imports")
            conn.execute("DELETE FROM purchase_order_lines")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM batches")
            conn.execute("DELETE FROM historical_payable_lines")
            conn.execute("DELETE FROM settings WHERE key='historical_payables_through_date'")
            conn.execute("DELETE FROM audit_log")
            conn.execute(
                "INSERT OR REPLACE INTO suppliers(code,name) VALUES('S1','Nhà cung cấp Một')"
            )
            conn.execute(
                "INSERT OR REPLACE INTO suppliers(code,name) VALUES('S2','Nhà cung cấp Hai')"
            )

    @staticmethod
    def _batch(conn, work_date="2026-09-01") -> int:
        timestamp = server.now_iso()
        return int(conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES(?,'payment fixture','approved',?,?)""",
            (work_date, timestamp, timestamp),
        ).lastrowid)

    @staticmethod
    def _purchase(
        conn, batch_id: int, *, row_key: str, amount: int,
        supplier="S1", work_date="2026-09-01",
    ) -> None:
        timestamp = server.now_iso()
        conn.execute(
            """INSERT INTO purchase_workbook_lines(
                   batch_id,row_key,source_sheet,source_row,product_code,kitchen,work_date,
                   product_name,base_qty,unit,supplier,note,buy_price,price_source,
                   damaged_qty,added_qty,reduced_qty,missing_qty,actual_qty,amount,status,
                   source_hash,revision,created_at,updated_at
               ) VALUES(?,?,'đặt hàng',3,?,'K1',?, ?,1,'kg',?,'',?,
                        'fixture',0,0,0,0,1,?,'confirmed',?,1,?,?)""",
            (
                batch_id, row_key, f"P-{row_key}", work_date, f"Hàng {row_key}",
                supplier, amount, amount, f"HASH-{row_key}", timestamp, timestamp,
            ),
        )

    def _ledger_lines(self, specifications):
        with server.db() as conn:
            batch_id = self._batch(conn)
            for row_key, amount, supplier in specifications:
                self._purchase(
                    conn, batch_id, row_key=row_key, amount=amount, supplier=supplier,
                )
            sync_payable_ledger(conn, timestamp=server.now_iso())
            return [dict(row) for row in conn.execute(
                "SELECT * FROM payable_ledger_lines ORDER BY id"
            )]

    @staticmethod
    def _payload(request_id, supplier, payment_date, amount, allocations, **extra):
        return {
            "request_id": request_id,
            "party_code": supplier,
            "payment_date": payment_date,
            "amount": amount,
            "method": extra.get("method", "Chuyển khoản"),
            "reference_code": extra.get("reference_code", "UNC-001"),
            "note": extra.get("note", "Thanh toán fixture"),
            "allocations": allocations,
        }

    def test_full_partial_multiple_payments_and_idempotent_replay(self):
        lines = self._ledger_lines([
            ("ROW-1", 100, "S1"), ("ROW-2", 200, "S1"),
        ])
        first_payload = self._payload(
            "PAY-REQ-0001", "S1", "2026-09-01", 150,
            [
                {"ledger_line_id": lines[0]["id"], "amount": 100, "expected_revision": 1},
                {"ledger_line_id": lines[1]["id"], "amount": 50, "expected_revision": 1},
            ],
        )
        first = self.client.post("/api/debts/payables/payments", json=first_payload)
        self.assertEqual(first.status_code, 201, first.get_data(as_text=True))
        self.assertEqual(
            [(item["line"]["status"], item["line"]["paid_amount"])
             for item in first.get_json()["allocations"]],
            [("paid", 100), ("partially_paid", 50)],
        )

        second_payload = self._payload(
            "PAY-REQ-0002", "S1", "2026-09-02", 150,
            [{"ledger_line_id": lines[1]["id"], "amount": 150, "expected_revision": 2}],
        )
        second = self.client.post("/api/payments", json={
            **second_payload, "kind": "payment", "party_type": "supplier",
        })
        self.assertEqual(second.status_code, 201, second.get_data(as_text=True))
        replay = self.client.post("/api/payments", json={
            **second_payload, "kind": "payment", "party_type": "supplier",
        })
        self.assertEqual(replay.status_code, 200, replay.get_data(as_text=True))
        self.assertTrue(replay.get_json()["idempotent"])
        request_conflict = self.client.post("/api/payments", json={
            **second_payload, "kind": "payment", "party_type": "supplier",
            "note": "Nội dung khác nhưng dùng lại request id",
        })
        self.assertEqual(request_conflict.status_code, 409)
        self.assertEqual(request_conflict.get_json()["code"], "payment_request_conflict")

        open_view = self.client.get(
            "/api/debts/payables/ledger?from=2026-09-01&to=2026-09-30"
        ).get_json()
        self.assertEqual(open_view["rows"], [])
        all_view = self.client.get(
            "/api/debts/payables/ledger?from=2026-09-01&to=2026-09-30&status=all"
        ).get_json()
        self.assertEqual([item["status"] for item in all_view["rows"]], ["paid", "paid"])
        self.assertEqual(all_view["summary"]["paid_amount"], 300)

        history = self.client.get(
            "/api/debts/payables/payments?from=2026-09-01&to=2026-09-30&supplier=s1&status=posted"
        )
        self.assertEqual(history.status_code, 200, history.get_data(as_text=True))
        self.assertEqual(
            (history.get_json()["pagination"]["total"], history.get_json()["summary"]["posted_amount"]),
            (2, 300),
        )
        debt = self.client.get("/api/debts?from=2026-09-01&to=2026-09-30").get_json()
        self.assertEqual(
            (debt["suppliers"]["S1"]["period_charge"],
             debt["suppliers"]["S1"]["period_paid"],
             debt["suppliers"]["S1"]["closing"]),
            (300, 300, 0),
        )
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) n FROM payments").fetchone()["n"], 2)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) n FROM payable_payment_allocations").fetchone()["n"], 3,
            )

    def test_schema_migrates_legacy_payment_rows_without_loss(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                """CREATE TABLE payments(
                       id INTEGER PRIMARY KEY AUTOINCREMENT,payment_date TEXT NOT NULL,
                       kind TEXT NOT NULL,party_type TEXT NOT NULL,party_code TEXT NOT NULL,
                       amount REAL NOT NULL,note TEXT,created_at TEXT NOT NULL
                   )"""
            )
            conn.execute(
                """INSERT INTO payments(
                       payment_date,kind,party_type,party_code,amount,note,created_at
                   ) VALUES('2026-08-31','payment','supplier','S1',125,'legacy','old-time')"""
            )
            init_payable_payment_schema(conn)
            init_payable_payment_schema(conn)
            row = conn.execute("SELECT * FROM payments").fetchone()
            tables = {
                item["name"] for item in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()
        self.assertEqual(
            (row["party_code"], row["amount"], row["note"], row["status"], row["revision"]),
            ("S1", 125, "legacy", "posted", 1),
        )
        self.assertTrue({
            "payable_payment_allocations", "payable_payment_revisions",
        }.issubset(tables))

    def test_reversal_restores_open_balance_and_never_deletes_transaction(self):
        line = self._ledger_lines([("REV", 100, "S1")])[0]
        created = self.client.post("/api/debts/payables/payments", json=self._payload(
            "PAY-REV-0001", "S1", "2026-09-01", 100,
            [{"ledger_line_id": line["id"], "amount": 100, "expected_revision": 1}],
        ))
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        payment_id = created.get_json()["id"]
        reversed_response = self.client.post(
            f"/api/debts/payables/payments/{payment_id}/reverse",
            json={"actor": "Người kiểm thử", "expected_revision": 1, "reason": "Chuyển khoản bị ngân hàng hoàn"},
        )
        self.assertEqual(
            reversed_response.status_code, 200, reversed_response.get_data(as_text=True),
        )
        self.assertEqual(
            (reversed_response.get_json()["status"], reversed_response.get_json()["revision"]),
            ("reversed", 2),
        )
        replay = self.client.post(
            f"/api/debts/payables/payments/{payment_id}/reverse",
            json={"actor": "Người kiểm thử", "expected_revision": 1, "reason": "Chuyển khoản bị ngân hàng hoàn"},
        )
        self.assertEqual(replay.status_code, 200, replay.get_data(as_text=True))
        self.assertTrue(replay.get_json()["idempotent"])
        revision_payload = self.client.get(
            f"/api/debts/payables/payments/{payment_id}/revisions"
        ).get_json()
        self.assertEqual(
            [(item["revision"], item["change_kind"], item["status"])
             for item in revision_payload["revisions"]],
            [(1, "create", "posted"), (2, "reverse", "reversed")],
        )
        self.assertEqual(
            revision_payload["revisions"][0]["allocations"][0]["amount"], 100,
        )
        self.assertEqual(self.client.delete(f"/api/payments/{payment_id}").status_code, 409)

        open_row = self.client.get(
            "/api/debts/payables/ledger?from=2026-09-01&to=2026-09-30"
        ).get_json()["rows"][0]
        self.assertEqual(
            (open_row["status"], open_row["paid_amount"], open_row["remaining_amount"]),
            ("open", 0, 100),
        )
        debt = self.client.get("/api/debts?from=2026-09-01&to=2026-09-30").get_json()
        self.assertEqual(
            (debt["suppliers"]["S1"]["period_paid"], debt["suppliers"]["S1"]["closing"]),
            (0, 100),
        )
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) n FROM payments").fetchone()["n"], 1)
            self.assertEqual(
                [tuple(row) for row in conn.execute(
                    "SELECT revision,change_kind,status FROM payable_payment_revisions ORDER BY revision"
                )],
                [(1, "create", "posted"), (2, "reverse", "reversed")],
            )
            self.assertEqual(
                conn.execute("SELECT status FROM payable_payment_allocations").fetchone()["status"],
                "reversed",
            )
            self.assertEqual(
                [row["event_type"] for row in conn.execute(
                    "SELECT event_type FROM audit_log ORDER BY id"
                )],
                ["payable_payment.create", "payable_payment.reverse"],
            )

    def test_reversing_payment_after_source_line_reversal_keeps_source_reversed(self):
        line = self._ledger_lines([("SOURCE-REV", 100, "S1")])[0]
        created = self.client.post("/api/debts/payables/payments", json=self._payload(
            "PAY-SRC-REV1", "S1", "2026-09-01", 40,
            [{"ledger_line_id": line["id"], "amount": 40, "expected_revision": 1}],
        ))
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        with server.db() as conn:
            conn.execute("DELETE FROM purchase_workbook_lines WHERE row_key='SOURCE-REV'")
            sync_payable_ledger(conn, timestamp=server.now_iso())
            before = dict(conn.execute(
                "SELECT * FROM payable_ledger_lines WHERE id=?", (line["id"],)
            ).fetchone())
        self.assertEqual((before["status"], before["paid_amount"]), ("reversed", 40))
        undone = self.client.post(
            f"/api/debts/payables/payments/{created.get_json()['id']}/reverse",
            json={"actor": "Người kiểm thử", "expected_revision": 1, "reason": "Nguồn mua đã hoàn tác"},
        )
        self.assertEqual(undone.status_code, 200, undone.get_data(as_text=True))
        with server.db() as conn:
            after = dict(conn.execute(
                "SELECT * FROM payable_ledger_lines WHERE id=?", (line["id"],)
            ).fetchone())
        self.assertEqual((after["status"], after["paid_amount"]), ("reversed", 0))

    def test_rejects_implicit_mismatch_cross_supplier_duplicate_and_overpayment(self):
        lines = self._ledger_lines([
            ("S1-LINE", 100, "S1"), ("S2-LINE", 200, "S2"),
        ])
        implicit = self.client.post("/api/payments", json={
            "request_id": "PAY-BAD-0001", "payment_date": "2026-09-01",
            "kind": "payment", "party_type": "supplier", "party_code": "S1", "amount": 10,
        })
        self.assertEqual(implicit.status_code, 400)
        self.assertEqual(implicit.get_json()["code"], "payable_allocations_required")
        cases = [
            ("PAY-BAD-0002", 50, [
                {"ledger_line_id": lines[0]["id"], "amount": 40, "expected_revision": 1},
            ], "payment_allocation_total_mismatch"),
            ("PAY-BAD-0003", 50, [
                {"ledger_line_id": lines[1]["id"], "amount": 50, "expected_revision": 1},
            ], "payment_supplier_mismatch"),
            ("PAY-BAD-0004", 101, [
                {"ledger_line_id": lines[0]["id"], "amount": 101, "expected_revision": 1},
            ], "payable_overpayment"),
            ("PAY-BAD-0005", 100, [
                {"ledger_line_id": lines[0]["id"], "amount": 50, "expected_revision": 1},
                {"ledger_line_id": lines[0]["id"], "amount": 50, "expected_revision": 1},
            ], "duplicate_payable_allocation"),
        ]
        for request_id, amount, allocations, code in cases:
            with self.subTest(code=code):
                response = self.client.post("/api/debts/payables/payments", json=self._payload(
                    request_id, "S1", "2026-09-01", amount, allocations,
                ))
                self.assertIn(response.status_code, {400, 409})
                self.assertEqual(response.get_json()["code"], code)
        with server.db() as conn:
            self.assertEqual(
                tuple(conn.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"] for table in (
                    "payments", "payable_payment_allocations", "payable_payment_revisions",
                )),
                (0, 0, 0),
            )
            self.assertEqual(
                [row["paid_amount"] for row in conn.execute(
                    "SELECT paid_amount FROM payable_ledger_lines ORDER BY id"
                )],
                [0, 0],
            )

    def test_concurrent_requests_allow_one_writer_and_reject_stale_revision(self):
        line = self._ledger_lines([("RACE", 100, "S1")])[0]

        def send(index):
            with server.app.test_client() as client:
                response = client.post("/api/debts/payables/payments", json=self._payload(
                    f"PAY-RACE-00{index}", "S1", "2026-09-01", 60,
                    [{"ledger_line_id": line["id"], "amount": 60, "expected_revision": 1}],
                ))
                return response.status_code, response.get_json()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(send, (1, 2)))
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        rejected = next(payload for status, payload in results if status == 409)
        self.assertEqual(rejected["code"], "stale_payable_revision")
        with server.db() as conn:
            current = dict(conn.execute(
                "SELECT * FROM payable_ledger_lines WHERE id=?", (line["id"],)
            ).fetchone())
            self.assertEqual(
                conn.execute("SELECT COUNT(*) n FROM payments").fetchone()["n"], 1,
            )
        self.assertEqual(
            (current["paid_amount"], current["status"], current["revision"]),
            (60, "partially_paid", 2),
        )

    def test_period_status_filters_and_atomic_failure(self):
        line = self._ledger_lines([("PERIOD", 100, "S1")])[0]
        august = self.client.post("/api/debts/payables/payments", json=self._payload(
            "PAY-PER-0001", "S1", "2026-08-31", 40,
            [{"ledger_line_id": line["id"], "amount": 40, "expected_revision": 1}],
        ))
        self.assertEqual(august.status_code, 201, august.get_data(as_text=True))
        september = self.client.post("/api/debts/payables/payments", json=self._payload(
            "PAY-PER-0002", "S1", "2026-09-01", 60,
            [{"ledger_line_id": line["id"], "amount": 60, "expected_revision": 2}],
        ))
        self.assertEqual(september.status_code, 201, september.get_data(as_text=True))
        august_only = self.client.get(
            "/api/debts/payables/payments?from=2026-08-31&to=2026-08-31&status=posted"
        ).get_json()
        september_only = self.client.get(
            "/api/debts/payables/payments?from=2026-09-01&to=2026-09-01&status=posted"
        ).get_json()
        self.assertEqual(
            ([item["amount"] for item in august_only["payments"]],
             [item["amount"] for item in september_only["payments"]]),
            ([40], [60]),
        )
        reversed_response = self.client.post(
            f"/api/debts/payables/payments/{august.get_json()['id']}/reverse",
            json={"actor": "Người kiểm thử", "expected_revision": 1, "reason": "Sai ngày ngân hàng"},
        )
        self.assertEqual(reversed_response.status_code, 200)
        reversed_only = self.client.get(
            "/api/debts/payables/payments?from=2026-08-01&to=2026-09-30&status=reversed"
        ).get_json()
        self.assertEqual([item["amount"] for item in reversed_only["payments"]], [40])

        # A failure after the payment row is inserted must roll back the
        # transaction, ledger status, allocation, revision and audit together.
        fresh = next(
            item for item in self._ledger_lines([("ATOMIC", 50, "S1")])
            if item["source_ref"].endswith("purchase:ATOMIC")
        )
        with server.db() as conn:
            conn.execute(
                """CREATE TRIGGER fail_payable_allocation
                   BEFORE INSERT ON payable_payment_allocations
                   BEGIN SELECT RAISE(ABORT,'forced allocation failure'); END"""
            )
        failed = self.client.post("/api/debts/payables/payments", json=self._payload(
            "PAY-FAIL-001", "S1", "2026-09-02", 50,
            [{"ledger_line_id": fresh["id"], "amount": 50, "expected_revision": 1}],
        ))
        self.assertEqual(failed.status_code, 500)
        with server.db() as conn:
            conn.execute("DROP TRIGGER fail_payable_allocation")
            row = dict(conn.execute(
                "SELECT * FROM payable_ledger_lines WHERE id=?", (fresh["id"],)
            ).fetchone())
            failed_payment = conn.execute(
                "SELECT COUNT(*) n FROM payments WHERE request_key='PAY-FAIL-001'"
            ).fetchone()["n"]
        self.assertEqual((row["paid_amount"], row["status"], row["revision"]), (0, "open", 1))
        self.assertEqual(failed_payment, 0)


if __name__ == "__main__":
    unittest.main()
