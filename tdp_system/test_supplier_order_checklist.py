import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from . import contract_modules, server
except ImportError:  # pragma: no cover - direct file invocation
    import contract_modules
    import server


class SupplierOrderChecklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.original_db_path = server.DB_PATH
        cls.original_data_dir = server.DATA_DIR
        cls.original_testing = server.app.config.get("TESTING", False)
        server.DATA_DIR = Path(cls.temp_dir.name) / "data"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "supplier_checklist.sqlite3"
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
            conn.execute("DELETE FROM supplier_order_statuses")
            conn.execute("DELETE FROM purchase_workbook_line_revisions")
            conn.execute("DELETE FROM purchase_workbook_lines")
            conn.execute("DELETE FROM purchase_order_imports")
            conn.execute("DELETE FROM purchase_order_lines")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM batches")
            conn.execute("DELETE FROM supplier_rules")
            conn.execute("DELETE FROM audit_log")

    @staticmethod
    def _create_batch(conn, source_name="checklist.xlsx", fixtures=None):
        timestamp = server.now_iso()
        batch_id = int(conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES('2026-09-01',?,'approved',?,?)""",
            (source_name, timestamp, timestamp),
        ).lastrowid)
        fixtures = fixtures or [
            ("DUNG", "POT", "Cà rốt", 2),
            ("HƯƠNG", "POT", "Hành lá", 3),
            ("Nhà Hương", "BIA", "hành LÁ", 4),
        ]
        for index, (supplier, kitchen, name, qty) in enumerate(fixtures, start=1):
            conn.execute(
                """INSERT INTO purchase_workbook_lines(
                       batch_id,row_key,source_sheet,source_row,product_code,kitchen,
                       work_date,product_name,base_qty,unit,supplier,buy_price,
                       actual_qty,amount,source_hash,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    batch_id, f"{source_name}-{index}", "đặt hàng", index + 2,
                    f"P-{batch_id}-{index}", kitchen, "2026-09-01", name,
                    qty, "kg", supplier, 1000, qty, qty * 1000,
                    f"hash-{batch_id}", timestamp, timestamp,
                ),
            )
        return batch_id

    def test_ordered_reopened_ordered_persists_and_never_hides_lines(self):
        with server.db() as conn:
            batch_id = self._create_batch(conn)
            raw_before = [tuple(row) for row in conn.execute(
                """SELECT row_key,kitchen,product_name,actual_qty,supplier
                   FROM purchase_workbook_lines WHERE batch_id=? ORDER BY source_row""",
                (batch_id,),
            )]

        initial = self.client.get(f"/api/supplier-needs/{batch_id}").get_json()
        self.assertEqual(
            [(item["key"], item["label"]) for item in initial["image_contract"]["columns"]],
            [
                ("kitchen", "Mã bếp"), ("work_date", "Ngày"),
                ("product_name", "Tên hàng"), ("order_qty", "Số lượng"),
                ("unit", "ĐVT"), ("supplier", "NCC"), ("note", "Ghi chú"),
            ],
        )
        self.assertEqual(
            set(initial["image_contract"]["forbidden_text"]),
            {
                "Tồn tủ", "Giá mua", "Thành tiền", "Tổng cần mua sau trừ tồn",
                "Mã dòng hệ thống", "Số lượng thực tế", "Hỏng", "Thêm", "Giảm", "Thiếu",
            },
        )
        self.assertEqual(initial["checklist_counts"], {
            "pending": 2, "reopened": 0, "ordered": 0,
        })
        self.assertEqual(initial["raw_line_count"], 3)
        self.assertEqual(len(initial["groups"]), 3)
        huong_groups = [g for g in initial["groups"] if g["supplier_key"] == "huong"]
        self.assertEqual((len(huong_groups), {g["order_status_revision"] for g in huong_groups}), (2, {0}))

        ordered = self.client.put(
            f"/api/supplier-order-status/{batch_id}/huong",
            json={"status": "ordered", "revision": 0},
        )
        self.assertEqual(ordered.status_code, 200, ordered.get_data(as_text=True))
        self.assertEqual((ordered.get_json()["status"], ordered.get_json()["revision"]), ("ordered", 1))

        # A new client models a full browser reload; status comes from SQLite,
        # not from in-memory UI state.
        with server.app.test_client() as reloaded_client:
            after_reload = reloaded_client.get(f"/api/supplier-needs/{batch_id}").get_json()
        self.assertEqual(after_reload["checklist_counts"], {
            "pending": 1, "reopened": 0, "ordered": 1,
        })
        self.assertEqual([item["supplier_key"] for item in after_reload["checklist"]], ["dung", "huong"])
        huong_after = [g for g in after_reload["groups"] if g["supplier_key"] == "huong"]
        self.assertEqual(len(huong_after), 2)
        self.assertTrue(all(g["order_status"] == "ordered" for g in huong_after))
        self.assertTrue(all(g["order_status_revision"] == 1 for g in huong_after))

        reopened = self.client.put(
            f"/api/supplier-order-status/{batch_id}/huong",
            json={"status": "reopened", "revision": 1},
        )
        self.assertEqual(reopened.status_code, 200, reopened.get_data(as_text=True))
        reopened_payload = self.client.get(f"/api/supplier-needs/{batch_id}").get_json()
        self.assertEqual(reopened_payload["checklist_counts"], {
            "pending": 1, "reopened": 1, "ordered": 0,
        })
        self.assertEqual(reopened_payload["checklist"][0]["supplier_key"], "huong")

        reordered = self.client.put(
            f"/api/supplier-order-status/{batch_id}/huong",
            json={"status": "ordered", "revision": 2},
        )
        self.assertEqual(reordered.status_code, 200, reordered.get_data(as_text=True))
        self.assertEqual(reordered.get_json()["revision"], 3)

        with server.db() as conn:
            raw_after = [tuple(row) for row in conn.execute(
                """SELECT row_key,kitchen,product_name,actual_qty,supplier
                   FROM purchase_workbook_lines WHERE batch_id=? ORDER BY source_row""",
                (batch_id,),
            )]
            status_row = dict(conn.execute(
                "SELECT * FROM supplier_order_statuses WHERE batch_id=? AND supplier_key='huong'",
                (batch_id,),
            ).fetchone())
            events = [json.loads(row["metadata_json"]) for row in conn.execute(
                """SELECT metadata_json FROM audit_log
                   WHERE event_type='supplier_order.status' ORDER BY id"""
            )]
        self.assertEqual(raw_after, raw_before)
        self.assertEqual((status_row["status"], status_row["revision"]), ("ordered", 3))
        self.assertEqual(
            [(item["previous_status"], item["status"], item["revision"]) for item in events],
            [("pending", "ordered", 1), ("ordered", "reopened", 2), ("reopened", "ordered", 3)],
        )

    def test_two_concurrent_marks_use_revision_and_only_one_wins(self):
        with server.db() as conn:
            batch_id = self._create_batch(
                conn, "concurrent.xlsx", [("DUNG", "POT", "Cà rốt", 2)],
            )
        barrier = threading.Barrier(2)

        def mark_ordered():
            with server.app.test_client() as client:
                barrier.wait(timeout=5)
                response = client.put(
                    f"/api/supplier-order-status/{batch_id}/dung",
                    json={"status": "ordered", "revision": 0},
                )
                return response.status_code, response.get_json()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: mark_ordered(), range(2)))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        stale = next(payload for status, payload in results if status == 409)
        self.assertEqual((stale["code"], stale["status"], stale["revision"]), (
            "stale_supplier_order_status", "ordered", 1,
        ))
        with server.db() as conn:
            state = conn.execute(
                "SELECT status,revision FROM supplier_order_statuses WHERE batch_id=?",
                (batch_id,),
            ).fetchone()
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE event_type='supplier_order.status'"
            ).fetchone()[0]
        self.assertEqual(tuple(state), ("ordered", 1))
        self.assertEqual(audit_count, 1)

    def test_batch_isolation_and_invalid_transitions_fail_closed(self):
        with server.db() as conn:
            first = self._create_batch(
                conn, "first.xlsx", [("DUNG", "POT", "Cà rốt", 2)],
            )
            second = self._create_batch(
                conn, "second.xlsx", [("DUNG", "POT", "Cà rốt", 3)],
            )
        self.assertEqual(self.client.put(
            f"/api/supplier-order-status/{first}/dung",
            json={"status": "ordered", "revision": 0},
        ).status_code, 200)
        second_payload = self.client.get(f"/api/supplier-needs/{second}").get_json()
        self.assertEqual((second_payload["checklist"][0]["status"], second_payload["checklist"][0]["revision"]), (
            "pending", 0,
        ))
        invalid_undo = self.client.put(
            f"/api/supplier-order-status/{second}/dung",
            json={"status": "reopened", "revision": 0},
        )
        self.assertEqual((invalid_undo.status_code, invalid_undo.get_json()["code"]), (
            409, "invalid_supplier_order_transition",
        ))
        missing_revision = self.client.put(
            f"/api/supplier-order-status/{second}/dung",
            json={"status": "ordered"},
        )
        self.assertEqual((missing_revision.status_code, missing_revision.get_json()["code"]), (
            400, "supplier_status_revision_required",
        ))
        unknown = self.client.put(
            f"/api/supplier-order-status/{second}/huong",
            json={"status": "ordered", "revision": 0},
        )
        self.assertEqual((unknown.status_code, unknown.get_json()["code"]), (
            404, "supplier_not_in_batch",
        ))
        with server.db() as conn:
            first_state = conn.execute(
                "SELECT status,revision FROM supplier_order_statuses WHERE batch_id=?",
                (first,),
            ).fetchone()
            second_count = conn.execute(
                "SELECT COUNT(*) FROM supplier_order_statuses WHERE batch_id=?",
                (second,),
            ).fetchone()[0]
        self.assertEqual(tuple(first_state), ("ordered", 1))
        self.assertEqual(second_count, 0)


if __name__ == "__main__":
    unittest.main()
