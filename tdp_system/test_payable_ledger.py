from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

try:
    from . import server
    from .payable_ledger import (
        PayableLedgerError,
        payable_line_status,
        set_payable_allocation_total,
        sync_payable_ledger,
    )
except ImportError:  # pragma: no cover - direct invocation
    import server
    from payable_ledger import (
        PayableLedgerError,
        payable_line_status,
        set_payable_allocation_total,
        sync_payable_ledger,
    )


class PayableLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.original_db_path = server.DB_PATH
        cls.original_data_dir = server.DATA_DIR
        cls.original_testing = server.app.config.get("TESTING", False)
        server.DATA_DIR = Path(cls.temp_dir.name) / "data"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "payable_ledger.sqlite3"
        server.app.config["TESTING"] = True
        server.init_database()
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        server.DB_PATH = cls.original_db_path
        server.DATA_DIR = cls.original_data_dir
        server.app.config["TESTING"] = cls.original_testing
        cls.temp_dir.cleanup()

    def setUp(self):
        with server.db() as conn:
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
            conn.execute("DELETE FROM payments")
            conn.execute("DELETE FROM balances")
            conn.execute("DELETE FROM debt_adjustments")
            conn.execute(
                "INSERT OR REPLACE INTO suppliers(code,name) VALUES('S1','Nhà cung cấp cũ')"
            )
            conn.execute(
                """INSERT OR REPLACE INTO products(
                       code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
                   ) VALUES('P1','Cà rốt','kg','0%','S1',5,0,'','')"""
            )

    @staticmethod
    def _batch(conn, work_date: str, *, status="approved") -> int:
        cursor = conn.execute(
            "INSERT INTO batches(work_date,source_name,status,created_at,approved_at) "
            "VALUES(?,?,?,?,?)",
            (work_date, "fixture", status, server.now_iso(), server.now_iso() if status == "approved" else None),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _purchase(
        conn, batch_id: int, work_date: str, *, row_key: str,
        qty=8, buy_price=5, amount=40, supplier="S1", revision=1,
    ) -> int:
        cursor = conn.execute(
            """INSERT INTO purchase_workbook_lines(
                   batch_id,row_key,source_sheet,source_row,product_code,kitchen,work_date,
                   product_name,base_qty,unit,supplier,note,buy_price,price_source,
                   damaged_qty,added_qty,reduced_qty,missing_qty,actual_qty,amount,status,
                   source_hash,revision,created_at,updated_at
               ) VALUES(?,?,'đặt hàng',3,'P1','K1',?,'Cà rốt',?,'kg',?,'',?,
                        'Sheet đặt hàng chuẩn',0,0,0,0,?,?,'confirmed',?,?,?,?)""",
            (
                batch_id, row_key, work_date, qty, supplier, buy_price, qty, amount,
                f"HASH-{revision}", revision, server.now_iso(), server.now_iso(),
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _historical(
        conn, *, source_row: int, purchase_date="2026-08-31", amount=100,
        supplier="S1", source_hash="HIST-1", item_name="Cà rốt",
    ) -> int:
        cursor = conn.execute(
            """INSERT INTO historical_payable_lines(
                   purchase_date,kitchen,item_name,qty,unit,supplier,buy_price,
                   damaged_qty,added_qty,reduced_qty,missing_qty,actual_qty,
                   source_amount,calculated_amount,amount,note,source_file,source_sheet,
                   source_row,source_hash,created_at,updated_at
               ) VALUES(?,'K1',?,20,'kg',?,5,0,0,0,0,20,?,?,?,?,
                        'history.xlsx','Tổng hợp',?,?,?,?)""",
            (
                purchase_date, item_name, supplier, amount, amount, amount, "",
                source_row, source_hash, server.now_iso(), server.now_iso(),
            ),
        )
        return int(cursor.lastrowid)

    def _ledger(self, *, date_from="2026-01-01", date_to="2026-12-31", status="all"):
        response = self.client.get(
            "/api/debts/payables/ledger",
            query_string={"from": date_from, "to": date_to, "status": status, "limit": 20000},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_current_source_line_is_detailed_idempotent_and_never_deleted(self):
        with server.db() as conn:
            batch_id = self._batch(conn, "2026-09-01")
            source_id = self._purchase(conn, batch_id, "2026-09-01", row_key="ROW-1")
            first = sync_payable_ledger(conn, timestamp=server.now_iso())
            replay = sync_payable_ledger(conn, timestamp=server.now_iso())
        self.assertEqual((first["inserted"], first["active"]), (1, 1))
        self.assertEqual((replay["unchanged"], replay["total"]), (1, 1))

        payload = self._ledger()
        self.assertEqual(payload["summary"]["remaining_amount"], 40)
        row = payload["rows"][0]
        self.assertEqual(
            (
                row["work_date"], row["batch_id"], row["kitchen"], row["product_code"],
                row["product_name"], row["actual_qty"], row["unit"],
                row["buy_price"], row["amount"], row["supplier"]["code"],
            ),
            ("2026-09-01", batch_id, "K1", "P1", "Cà rốt", 8, "kg", 5, 40, "S1"),
        )
        self.assertEqual((row["source"]["table"], row["source"]["id"]), (
            "purchase_workbook_lines", source_id,
        ))

        with server.db() as conn:
            conn.execute(
                """UPDATE purchase_workbook_lines
                   SET actual_qty=10,amount=50,revision=2,source_hash='HASH-2'
                   WHERE id=?""",
                (source_id,),
            )
            changed = sync_payable_ledger(conn, timestamp=server.now_iso())
            line_id = int(conn.execute(
                "SELECT id FROM payable_ledger_lines"
            ).fetchone()["id"])
        self.assertEqual((changed["updated"], changed["total"]), (1, 1))
        history = self.client.get(
            f"/api/debts/payables/ledger/{line_id}/revisions"
        ).get_json()
        self.assertEqual(
            [(item["revision"], item["change_kind"], item["amount"]) for item in history["revisions"]],
            [(1, "insert", 40), (2, "update", 50)],
        )

        with server.db() as conn:
            conn.execute("DELETE FROM purchase_workbook_lines WHERE id=?", (source_id,))
            removed = sync_payable_ledger(conn, timestamp=server.now_iso())
            counts = (
                conn.execute("SELECT COUNT(*) n FROM payable_ledger_lines").fetchone()["n"],
                conn.execute("SELECT COUNT(*) n FROM payable_ledger_revisions").fetchone()["n"],
            )
        self.assertEqual((removed["reversed"], counts), (1, (1, 3)))
        reversed_payload = self._ledger(status="reversed")
        self.assertEqual(reversed_payload["rows"][0]["reversal_reason"], "source_removed")
        self.assertEqual(self._ledger(status="open")["rows"], [])

    def test_batch_approval_materializes_confirmed_purchase_automatically(self):
        with server.db() as conn:
            batch_id = self._batch(conn, "2026-09-01", status="draft")
            order_id = int(conn.execute(
                """INSERT INTO orders(
                       batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                       actual_received,actual_delivered,unit,supplier,buy_price,sell_price,
                       tax,source_sheet,source_row,errors,warnings,updated_at
                   ) VALUES(?,'2026-09-01','C1','K1','P1','Cà rốt',8,8,8,'kg',
                            'S1',5,10,'0%','01.09',3,'[]','[]',?)""",
                (batch_id, server.now_iso()),
            ).lastrowid)
            self._purchase(conn, batch_id, "2026-09-01", row_key="AUTO")
        approved = self.client.post(f"/api/batches/{batch_id}/approve")
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        self.assertEqual(approved.get_json()["payable_ledger"]["active"], 1)
        row = self._ledger()["rows"][0]
        self.assertEqual(
            (row["source"]["table"], row["batch_id"], row["amount"], row["status"]),
            ("purchase_workbook_lines", batch_id, 40, "open"),
        )
        reopened = self.client.put(f"/api/orders/{order_id}", json={"note": "Mở lại phiên"})
        self.assertEqual(reopened.status_code, 200, reopened.get_data(as_text=True))
        reversed_row = self._ledger(status="reversed")["rows"][0]
        self.assertEqual(reversed_row["reversal_reason"], "batch_not_approved")

    def test_cutoff_combines_historical_and_current_without_double_count(self):
        with server.db() as conn:
            self._historical(conn, source_row=2, amount=100)
            august_batch = self._batch(conn, "2026-08-31")
            september_batch = self._batch(conn, "2026-09-01")
            self._purchase(
                conn, august_batch, "2026-08-31", row_key="AUG", qty=40, amount=200,
            )
            self._purchase(
                conn, september_batch, "2026-09-01", row_key="SEP", qty=60, amount=300,
            )
            server.setting_set(conn, "historical_payables_through_date", "2026-08-31")
            first = sync_payable_ledger(conn, timestamp=server.now_iso())
            repeat = sync_payable_ledger(conn, timestamp=server.now_iso())
        self.assertEqual((first["inserted"], first["reversed"], first["active"]), (3, 1, 2))
        self.assertEqual((repeat["unchanged"], repeat["total"]), (3, 3))

        payload = self._ledger(date_from="2026-08-01", date_to="2026-09-30")
        self.assertEqual(payload["summary"], {
            "source_rows": 3,
            "active_rows": 2,
            "status_counts": {"open": 2, "partially_paid": 0, "paid": 0, "reversed": 1},
            "charge_amount": 400,
            "paid_amount": 0,
            "remaining_amount": 400,
            "quantity": 80,
            "quantities_by_unit": [{"unit": "kg", "quantity": 80}],
            "filtered_quantities_by_unit": [{"unit": "kg", "quantity": 80}],
            "filtered_quantity": 80,
            "filtered_amount": 400,
            "filtered_paid_amount": 0,
            "filtered_remaining_amount": 400,
        })
        reversed_row = next(row for row in payload["rows"] if row["status"] == "reversed")
        self.assertEqual(reversed_row["reversal_reason"], "covered_by_historical_snapshot")
        debt = self.client.get(
            "/api/debts?from=2026-09-01&to=2026-09-30"
        ).get_json()
        self.assertEqual(debt["suppliers"]["S1"], {
            "opening": 100,
            "period_charge": 300,
            "period_paid": 0,
            "period_adjustment": 0,
            "closing": 400,
        })

    def test_supplier_rename_keeps_code_reference_and_uses_current_name(self):
        with server.db() as conn:
            self._historical(
                conn, source_row=2, supplier="Nhà cung cấp cũ", amount=100,
            )
            first = sync_payable_ledger(conn, timestamp=server.now_iso())
            conn.execute(
                "UPDATE suppliers SET name='Nhà cung cấp mới' WHERE code='S1'"
            )
            conn.execute(
                "INSERT OR REPLACE INTO suppliers(code,name) VALUES('S2','Nhà cung cấp cũ')"
            )
            renamed = sync_payable_ledger(conn, timestamp=server.now_iso())
        self.assertEqual((first["inserted"], renamed["unchanged"]), (1, 1))
        row = self._ledger()["rows"][0]
        self.assertEqual(row["supplier"], {
            "code": "S1",
            "name": "Nhà cung cấp mới",
            "source_value": "Nhà cung cấp cũ",
        })
        debt = self.client.get(
            "/api/debts?from=2026-08-01&to=2026-08-31"
        ).get_json()
        self.assertEqual(debt["suppliers"]["S1"]["period_charge"], 100)
        self.assertNotIn("S2", debt["suppliers"])

    def test_kho_purchase_is_payable_with_approval_confirmation_and_cutoff_guards(self):
        with server.db() as conn:
            approved = self._batch(conn, '2026-09-02')
            draft = self._batch(conn, '2026-09-03', status='draft')
            historical = self._batch(conn, '2026-08-31')
            for bid, day, key in [(approved, '2026-09-02', 'approved'),
                                  (draft, '2026-09-03', 'draft'),
                                  (historical, '2026-08-31', 'historical')]:
                self._purchase(conn, bid, day, row_key=key, supplier='kho', amount=467600)
            unconfirmed = self._purchase(conn, approved, '2026-09-02', row_key='unconfirmed', supplier='kho')
            conn.execute("UPDATE purchase_workbook_lines SET status='draft' WHERE id=?", (unconfirmed,))
            server.setting_set(conn, 'historical_payables_through_date', '2026-08-31')
            sync_payable_ledger(conn, timestamp=server.now_iso())
            rows = {r['source_ref'].rsplit(':', 1)[-1]: dict(r) for r in conn.execute('SELECT * FROM payable_ledger_lines')}
        self.assertEqual((rows['approved']['status'], rows['approved']['amount']), ('open', 467600))
        self.assertEqual(rows['draft']['reversal_reason'], 'batch_not_approved')
        self.assertEqual(rows['historical']['reversal_reason'], 'covered_by_historical_snapshot')
        self.assertEqual(rows['unconfirmed']['reversal_reason'], 'source_not_confirmed')

    def test_supplier_filter_keeps_accent_distinct_master_codes_separate(self):
        with server.db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO suppliers(code,name) VALUES('DUNG','Dung không dấu')"
            )
            conn.execute(
                "INSERT OR REPLACE INTO suppliers(code,name) VALUES('dũng','Dũng có dấu')"
            )
            self._historical(
                conn, source_row=2, supplier="DUNG", amount=100,
            )
            self._historical(
                conn, source_row=3, supplier="dũng", amount=200,
            )
            sync_payable_ledger(conn, timestamp=server.now_iso())

        response = self.client.get(
            "/api/debts/payables/ledger",
            query_string={
                "from": "2026-08-01", "to": "2026-08-31",
                "status": "all", "supplier": "DUNG",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["supplier"], "DUNG")
        self.assertEqual(
            [(row["supplier"]["code"], row["amount"]) for row in payload["rows"]],
            [("DUNG", 100)],
        )

    def test_status_contract_supports_partial_paid_paid_and_filters(self):
        self.assertEqual(payable_line_status(100, 0), "open")
        self.assertEqual(payable_line_status(100, 30), "partially_paid")
        self.assertEqual(payable_line_status(100, 100), "paid")
        self.assertEqual(payable_line_status(100, 0, reversed_line=True), "reversed")
        with self.assertRaises(PayableLedgerError):
            payable_line_status(100, 101)
        with self.assertRaises(PayableLedgerError):
            payable_line_status(-10, 1)

        with server.db() as conn:
            batch_id = self._batch(conn, "2026-09-01")
            for index in range(1, 5):
                self._purchase(
                    conn, batch_id, "2026-09-01", row_key=f"ROW-{index}",
                    qty=20, amount=100,
                )
            sync_payable_ledger(conn, timestamp=server.now_iso())
            lines = [dict(row) for row in conn.execute(
                "SELECT * FROM payable_ledger_lines ORDER BY id"
            )]
            partial = set_payable_allocation_total(
                conn, ledger_line_id=lines[0]["id"], paid_amount=30,
                timestamp=server.now_iso(),
            )
            paid = set_payable_allocation_total(
                conn, ledger_line_id=lines[1]["id"], paid_amount=100,
                timestamp=server.now_iso(),
            )
            replay = set_payable_allocation_total(
                conn, ledger_line_id=lines[1]["id"], paid_amount=100,
                timestamp=server.now_iso(),
            )
            conn.execute(
                "DELETE FROM purchase_workbook_lines WHERE row_key='ROW-3'"
            )
            sync_payable_ledger(conn, timestamp=server.now_iso())
        self.assertEqual((partial["status"], paid["status"], replay["idempotent"]), (
            "partially_paid", "paid", True,
        ))
        filtered = self._ledger(status="partially_paid,paid")
        self.assertEqual(
            [(row["status"], row["remaining_amount"]) for row in filtered["rows"]],
            [("partially_paid", 70), ("paid", 0)],
        )
        all_rows = self._ledger()
        self.assertEqual(all_rows["summary"]["status_counts"], {
            "open": 1, "partially_paid": 1, "paid": 1, "reversed": 1,
        })
        self.assertEqual(all_rows["pagination"]["total"], 4)
        self.assertEqual(all_rows["summary"]["filtered_amount"], 300)
        self.assertEqual(all_rows["summary"]["filtered_paid_amount"], 130)
        self.assertEqual(all_rows["summary"]["filtered_remaining_amount"], 170)
        self.assertEqual(all_rows["summary"]["filtered_quantity"], 60)
        audit = self._ledger(status="reversed")
        self.assertEqual(len(audit["rows"]), 1)
        self.assertEqual(audit["rows"][0]["amount"], 100)
        for key in ("filtered_amount", "filtered_paid_amount", "filtered_remaining_amount", "filtered_quantity"):
            self.assertEqual(audit["summary"][key], 0)
        self.assertEqual(audit["summary"]["filtered_quantities_by_unit"], [])

    def test_replacing_historical_snapshot_appends_revisions_and_reverses_removed_row(self):
        with server.db() as conn:
            self._historical(conn, source_row=2, amount=100, source_hash="OLD")
            self._historical(conn, source_row=3, amount=200, source_hash="OLD", item_name="Bí đỏ")
            sync_payable_ledger(conn, timestamp=server.now_iso())
            conn.execute("DELETE FROM historical_payable_lines")
            self._historical(conn, source_row=2, amount=150, source_hash="NEW")
            self._historical(conn, source_row=4, amount=300, source_hash="NEW", item_name="Su hào")
            changed = sync_payable_ledger(conn, timestamp=server.now_iso())
            repeat = sync_payable_ledger(conn, timestamp=server.now_iso())
            lines = [dict(row) for row in conn.execute(
                "SELECT * FROM payable_ledger_lines ORDER BY source_row"
            )]
            revisions = conn.execute(
                "SELECT COUNT(*) n FROM payable_ledger_revisions"
            ).fetchone()["n"]
        self.assertEqual((changed["updated"], changed["inserted"], changed["reversed"]), (1, 1, 1))
        self.assertEqual((repeat["unchanged"], repeat["total"]), (2, 3))
        self.assertEqual(
            [(row["source_row"], row["amount"], row["status"]) for row in lines],
            [(2, 150, "open"), (3, 200, "reversed"), (4, 300, "open")],
        )
        self.assertEqual(revisions, 5)

    def test_ledger_failure_rolls_back_source_and_ledger_together(self):
        with server.db() as conn:
            conn.execute(
                """CREATE TRIGGER fail_payable_revision
                   BEFORE INSERT ON payable_ledger_revisions
                   BEGIN SELECT RAISE(ABORT,'forced payable ledger failure'); END"""
            )
        with self.assertRaises(sqlite3.IntegrityError):
            with server.db() as conn:
                conn.execute("BEGIN IMMEDIATE")
                batch_id = self._batch(conn, "2026-09-01")
                self._purchase(conn, batch_id, "2026-09-01", row_key="ROLLBACK")
                sync_payable_ledger(conn, timestamp=server.now_iso())
        with server.db() as conn:
            conn.execute("DROP TRIGGER fail_payable_revision")
            counts = tuple(
                conn.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"]
                for table in ("batches", "purchase_workbook_lines", "payable_ledger_lines")
            )
        self.assertEqual(counts, (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
