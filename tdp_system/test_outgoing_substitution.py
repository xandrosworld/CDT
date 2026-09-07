import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from openpyxl import load_workbook

try:
    from . import server
    from . import outgoing_substitution
except ImportError:  # pragma: no cover - direct invocation
    import server
    import outgoing_substitution


class OutgoingSubstitutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.original_db_path = server.DB_PATH
        cls.original_data_dir = server.DATA_DIR
        cls.original_testing = server.app.config.get("TESTING", False)
        server.DATA_DIR = Path(cls.temp_dir.name) / "data"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "outgoing_substitution.sqlite3"
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
        with outgoing_substitution.SUBSTITUTION_PREVIEW_LOCK:
            outgoing_substitution.PENDING_SUBSTITUTION_PREVIEWS.clear()
        with server.db() as conn:
            conn.execute("DELETE FROM outgoing_substitution_actions")
            conn.execute("DELETE FROM invoice_inventory_ledger")
            conn.execute("DELETE FROM invoice_inventory_confirmations")
            conn.execute("DELETE FROM outgoing_source_invoice_items")
            conn.execute("DELETE FROM outgoing_source_events")
            conn.execute("DELETE FROM outgoing_source_invoices")
            conn.execute("DELETE FROM outgoing_invoice_lines")
            conn.execute("DELETE FROM outgoing_invoice_drafts")
            conn.execute("DELETE FROM inventory_transactions")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM batches")
            conn.execute("DELETE FROM quote_version_prices")
            conn.execute("DELETE FROM quote_version_products")
            conn.execute("DELETE FROM quote_versions")
            conn.execute("DELETE FROM audit_log")
            for code, name, group in (
                ("NT-A", "Nhà thầu A", "GROUP-A"),
                ("NT-B", "Nhà thầu B", "GROUP-B"),
            ):
                conn.execute(
                    """INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode)
                       VALUES(?,?,?,'group')""",
                    (code, name, group),
                )
            for code, name, unit, tax, buy_price in (
                ("ORIG-1", "Hàng gốc", "kg", "8%", 100),
                ("SUB-1", "Hàng thay thế", "kg", "8%", 999_999),
                ("SUB-UNIT", "Hàng sai đơn vị", "thùng", "8%", 1),
            ):
                conn.execute(
                    """INSERT OR REPLACE INTO products(
                           code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
                       ) VALUES(?,?,?,?, 'NCC',?,0,'','')""",
                    (code, name, unit, tax, buy_price),
                )

    @staticmethod
    def add_batch(conn, *, qty=5, contractor="NT-A", work_date="2026-09-03"):
        timestamp = server.now_iso()
        batch_id = conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES(?,'substitution.xlsx','approved',?,?)""",
            (work_date, timestamp, timestamp),
        ).lastrowid
        order_id = conn.execute(
            """INSERT INTO orders(
                   batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                   actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
                   purchase_list,errors,warnings,updated_at
               ) VALUES(?,?,?,'BẾP A','ORIG-1','Hàng gốc',?,?,?,'kg','NCC',100,150,
                        '8%',0,'[]','[]',?)""",
            (batch_id, work_date, contractor, qty, qty, qty, timestamp),
        ).lastrowid
        return batch_id, order_id

    @staticmethod
    def add_opening(conn, qty, *, code="SUB-1"):
        timestamp = server.now_iso()
        conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                   source_line,kitchen,status,note,created_at,updated_at
               ) VALUES('2026-08-01',?,?,0,321,'OPENING',?,?,'','posted','opening',?,?)""",
            (code, qty, f"OPEN-{code}", code, timestamp, timestamp),
        )

    @staticmethod
    def add_quote(conn, period, prices):
        """prices is an iterable of (product code, group, sell price)."""
        timestamp = server.now_iso()
        version_id = conn.execute(
            """INSERT INTO quote_versions(
                   effective_period,version_no,source_hash,source_name,source_sheet,
                   content_hash,product_count,price_count,status,created_at,confirmed_at
               ) VALUES(?,1,?,?, 'BÁO GIÁ',?,1,?,'confirmed',?,?)""",
            (
                period, f"SOURCE-{period}", f"quote-{period}.xlsx", f"CONTENT-{period}",
                len(prices), timestamp, timestamp,
            ),
        ).lastrowid
        product_lines = {}
        for source_row, (code, group, price) in enumerate(prices, start=5):
            if code not in product_lines:
                product_lines[code] = conn.execute(
                    """INSERT INTO quote_version_products(
                           version_id,source_row,product_code,product_name,unit,tax,supplier,
                           buy_price,buy_price_state
                       ) VALUES(?,?,?,?, 'kg','8%','NCC',321,'numeric')""",
                    (version_id, source_row, code, f"Tên {code}"),
                ).lastrowid
            conn.execute(
                """INSERT INTO quote_version_prices(
                       version_id,product_line_id,source_row,source_column,product_code,
                       price_group,source_header,price_text,price_value,price_state
                   ) VALUES(?,?,?,?,?,?,?,?,?,'numeric')""",
                (
                    version_id, product_lines[code], source_row, 20 + source_row, code,
                    group, group, str(price), price,
                ),
            )
        return version_id

    @staticmethod
    def request_body(batch_id, order_id, *, qty=3, **extra):
        return {
            "batch_id": batch_id,
            "order_id": order_id,
            "substitute_product_code": "SUB-1",
            "qty": qty,
            "actor": "Kế toán A",
            "reason": "Khách xác nhận đổi mã do thiếu tồn hóa đơn",
            **extra,
        }

    def preview(self, body):
        return self.client.post("/api/outgoing-substitutions/preview", json=body)

    def confirm(self, body, preview):
        return self.client.post(
            "/api/outgoing-substitutions/confirm",
            json={**body, "preview_id": preview["preview_id"], "confirmed": True},
        )

    def test_missing_period_price_is_blocked_even_when_product_has_buy_price(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 5)
        body = self.request_body(batch_id, order_id)
        preview_response = self.preview(body)
        self.assertEqual(preview_response.status_code, 200, preview_response.get_data(as_text=True))
        preview = preview_response.get_json()
        self.assertFalse(preview["can_confirm"])
        self.assertEqual(preview["blocked_code"], "missing_period_price")
        self.assertEqual(preview["unit_price"], 0)
        blocked = self.confirm(body, preview)
        self.assertEqual(blocked.status_code, 409, blocked.get_data(as_text=True))
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outgoing_substitution_actions").fetchone()[0], 0)

    def test_correct_period_and_contractor_price_flows_to_export_and_is_idempotent(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 5)
            self.add_quote(conn, "2026-08", [("SUB-1", "GROUP-A", 11_111)])
            self.add_quote(conn, "2026-09", [
                ("SUB-1", "GROUP-A", 77_777),
                ("SUB-1", "GROUP-B", 88_888),
            ])
        body = self.request_body(batch_id, order_id)
        preview_response = self.preview(body)
        self.assertEqual(preview_response.status_code, 200, preview_response.get_data(as_text=True))
        preview = preview_response.get_json()
        self.assertTrue(preview["can_confirm"])
        self.assertEqual((preview["unit_price"], preview["price_period"]), (77_777, "2026-09"))
        first = self.confirm(body, preview)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertFalse(first.get_json()["idempotent"])
        replay = self.confirm(body, preview)
        self.assertEqual(replay.status_code, 200, replay.get_data(as_text=True))
        self.assertTrue(replay.get_json()["idempotent"])

        with server.db() as conn:
            action = conn.execute("SELECT * FROM outgoing_substitution_actions").fetchone()
            line = conn.execute("SELECT * FROM outgoing_invoice_lines").fetchone()
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            reservation = conn.execute(
                "SELECT * FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT'"
            ).fetchone()
            draft = conn.execute("SELECT * FROM outgoing_invoice_drafts").fetchone()
            self.assertEqual((action["unit_price"], action["price_source"]), (77_777, "quote_version"))
            self.assertEqual((line["product_code"], line["unit_price"], line["qty"]), ("SUB-1", 77_777, 3))
            self.assertEqual((reservation["product_code"], reservation["qty_out"], reservation["kitchen"]),
                             ("SUB-1", 3, "BẾP A"))
            self.assertEqual((draft["draft_kind"], draft["round_no"]), ("substitution", 1))
            self.assertEqual((order["product_code"], order["sell_price"]), ("ORIG-1", 150))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outgoing_substitution_actions").fetchone()[0], 1)

        readiness = self.client.get(f"/api/outgoing-invoices/readiness/{batch_id}").get_json()
        self.assertEqual((readiness["drafted_qty"], readiness["pending_qty"]), (3, 2))
        exported = self.client.get(f"/api/export/invoices/{batch_id}")
        self.assertEqual(exported.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(exported.data)) as archive:
            filename = next(name for name in archive.namelist() if name.endswith(".xlsx"))
            workbook = load_workbook(io.BytesIO(archive.read(filename)), data_only=True, keep_links=False)
            try:
                self.assertEqual((workbook.active["A2"].value, workbook.active["E2"].value),
                                 ("SUB-1", 77_777))
            finally:
                workbook.close()

    def test_insufficient_substitute_stock_and_unit_mismatch_are_blocked(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 2)
            self.add_quote(conn, "2026-09", [("SUB-1", "GROUP-A", 20_000)])
        body = self.request_body(batch_id, order_id, qty=3)
        insufficient = self.preview(body)
        self.assertEqual(insufficient.status_code, 409)
        self.assertEqual(insufficient.get_json()["code"], "substitute_stock_insufficient")
        mismatch = self.preview({**body, "substitute_product_code": "SUB-UNIT", "qty": 1})
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(mismatch.get_json()["code"], "substitute_unit_mismatch")

    def test_preview_becomes_stale_when_available_stock_changes(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 5)
            self.add_quote(conn, "2026-09", [("SUB-1", "GROUP-A", 20_000)])
        body = self.request_body(batch_id, order_id, qty=3)
        preview = self.preview(body).get_json()
        with server.db() as conn:
            timestamp = server.now_iso()
            conn.execute(
                """INSERT INTO inventory_transactions(
                       txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                       source_line,kitchen,status,note,created_at,updated_at
                   ) VALUES('2026-09-03','SUB-1',0,1,0,'OUTGOING_DRAFT','OTHER-DRAFT',
                            'OTHER-LINE','','reserved','other hold',?,?)""",
                (timestamp, timestamp),
            )
        stale = self.confirm(body, preview)
        self.assertEqual(stale.status_code, 409, stale.get_data(as_text=True))
        self.assertEqual(stale.get_json()["code"], "stale_substitution_preview")
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outgoing_substitution_actions").fetchone()[0], 0)

    def test_override_requires_explicit_approval_and_reason(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 5)
        body = self.request_body(
            batch_id, order_id, override_price=45_000, override_reason="",
        )
        blocked = self.preview(body).get_json()
        self.assertFalse(blocked["can_confirm"])
        self.assertEqual(blocked["blocked_code"], "missing_period_price")
        approved_body = {
            **body,
            "approve_price_override": True,
            "override_reason": "Giám đốc duyệt giá bán riêng cho lượt này",
        }
        approved = self.preview(approved_body).get_json()
        self.assertTrue(approved["can_confirm"])
        self.assertEqual((approved["unit_price"], approved["price_source"]), (45_000, "approved_override"))
        response = self.confirm(approved_body, approved)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def test_reverse_releases_stock_restores_shortage_and_keeps_history(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 5)
            self.add_quote(conn, "2026-09", [("SUB-1", "GROUP-A", 20_000)])
        body = self.request_body(batch_id, order_id)
        preview = self.preview(body).get_json()
        confirmed = self.confirm(body, preview).get_json()
        action_id = confirmed["action"]["id"]
        reversed_response = self.client.post(
            f"/api/outgoing-substitutions/{action_id}/reverse",
            json={"confirmed": True, "actor": "Kế toán B", "reason": "Khách đổi lại mã gốc"},
        )
        self.assertEqual(reversed_response.status_code, 200, reversed_response.get_data(as_text=True))
        self.assertFalse(reversed_response.get_json()["idempotent"])
        replay = self.client.post(
            f"/api/outgoing-substitutions/{action_id}/reverse",
            json={"confirmed": True, "actor": "Kế toán B", "reason": "Khách đổi lại mã gốc"},
        )
        self.assertTrue(replay.get_json()["idempotent"])
        readiness = self.client.get(f"/api/outgoing-invoices/readiness/{batch_id}").get_json()
        self.assertEqual((readiness["drafted_qty"], readiness["pending_qty"]), (0, 5))
        with server.db() as conn:
            action = conn.execute(
                "SELECT * FROM outgoing_substitution_actions WHERE id=?", (action_id,)
            ).fetchone()
            self.assertEqual((action["status"], action["reversal_actor"]), ("reversed", "Kế toán B"))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outgoing_invoice_lines").fetchone()[0], 0)
            stock = conn.execute(
                """SELECT status FROM inventory_transactions
                    WHERE source_type='OUTGOING_DRAFT'"""
            ).fetchone()
            self.assertEqual(stock["status"], "cancelled")
        old_replay = self.confirm(body, preview)
        self.assertEqual(old_replay.status_code, 409)
        self.assertEqual(old_replay.get_json()["code"], "substitution_already_reversed")
        fresh_preview = self.preview(body).get_json()
        reapplied = self.confirm(body, fresh_preview)
        self.assertEqual(reapplied.status_code, 200, reapplied.get_data(as_text=True))
        self.assertFalse(reapplied.get_json()["idempotent"])
        self.assertNotEqual(reapplied.get_json()["action"]["id"], action_id)

    def test_issued_substitution_cannot_be_locally_reversed(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 5)
            self.add_quote(conn, "2026-09", [("SUB-1", "GROUP-A", 20_000)])
        body = self.request_body(batch_id, order_id)
        preview = self.preview(body).get_json()
        action = self.confirm(body, preview).get_json()["action"]
        with server.db() as conn:
            conn.execute("UPDATE outgoing_invoice_drafts SET status='issued' WHERE id=?", (action["draft_id"],))
        blocked = self.client.post(
            f"/api/outgoing-substitutions/{action['id']}/reverse",
            json={"confirmed": True, "actor": "Kế toán B", "reason": "Muốn sửa sau phát hành"},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["code"], "issued_substitution_requires_invoice_reversal")
        with server.db() as conn:
            self.assertEqual(conn.execute(
                "SELECT status FROM outgoing_substitution_actions WHERE id=?", (action["id"],)
            ).fetchone()["status"], "active")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outgoing_invoice_lines").fetchone()[0], 1)

    def test_multiple_rounds_and_standard_draft_recalculation_preserve_substitutions(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn, qty=5)
            self.add_opening(conn, 5)
            self.add_quote(conn, "2026-09", [("SUB-1", "GROUP-A", 20_000)])
        first_body = self.request_body(batch_id, order_id, qty=2, reason="Khách duyệt đổi lượt một")
        first_preview = self.preview(first_body).get_json()
        first_action = self.confirm(first_body, first_preview).get_json()["action"]
        with server.db() as conn:
            conn.execute("UPDATE outgoing_invoice_drafts SET status='issued' WHERE id=?", (first_action["draft_id"],))
            conn.execute(
                """UPDATE inventory_transactions SET status='posted'
                    WHERE source_type='OUTGOING_DRAFT' AND source_id=?""",
                (str(first_action["draft_id"]),),
            )
        second_body = self.request_body(batch_id, order_id, qty=2, reason="Khách duyệt đổi lượt hai")
        second_preview_response = self.preview(second_body)
        self.assertEqual(second_preview_response.status_code, 200, second_preview_response.get_data(as_text=True))
        second_action = self.confirm(second_body, second_preview_response.get_json()).get_json()["action"]
        self.assertNotEqual(first_action["draft_id"], second_action["draft_id"])
        with server.db() as conn:
            rounds = conn.execute(
                """SELECT round_no,draft_kind,status FROM outgoing_invoice_drafts
                    WHERE batch_id=? ORDER BY round_no""",
                (batch_id,),
            ).fetchall()
            self.assertEqual(
                [(row["round_no"], row["draft_kind"], row["status"]) for row in rounds],
                [(1, "substitution", "issued"), (2, "substitution", "draft")],
            )
        recalculated = self.client.post(f"/api/outgoing-invoices/draft/{batch_id}")
        self.assertEqual(recalculated.status_code, 200, recalculated.get_data(as_text=True))
        with server.db() as conn:
            substitutions = conn.execute(
                """SELECT d.round_no,l.product_code,l.qty,d.status
                      FROM outgoing_invoice_drafts d JOIN outgoing_invoice_lines l ON l.draft_id=d.id
                     WHERE d.batch_id=? AND d.draft_kind='substitution' ORDER BY d.round_no""",
                (batch_id,),
            ).fetchall()
            self.assertEqual(
                [(row["round_no"], row["product_code"], row["qty"], row["status"])
                 for row in substitutions],
                [(1, "SUB-1", 2, "issued"), (2, "SUB-1", 2, "draft")],
            )

    def test_whole_draft_cancel_marks_substitution_history_reversed(self):
        with server.db() as conn:
            batch_id, order_id = self.add_batch(conn)
            self.add_opening(conn, 5)
            self.add_quote(conn, "2026-09", [("SUB-1", "GROUP-A", 20_000)])
        body = self.request_body(batch_id, order_id)
        preview = self.preview(body).get_json()
        action = self.confirm(body, preview).get_json()["action"]
        cancelled = self.client.post(
            f"/api/outgoing-invoices/{action['draft_id']}/cancel", json={"confirmed": True},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.get_data(as_text=True))
        with server.db() as conn:
            history = conn.execute(
                "SELECT status,reversal_actor,reversal_reason FROM outgoing_substitution_actions"
            ).fetchone()
            self.assertEqual(
                (history["status"], history["reversal_actor"], history["reversal_reason"]),
                ("reversed", "SYSTEM", "Hủy toàn bộ dự thảo"),
            )

    def test_ui_requires_manual_code_preview_and_explicit_confirmation(self):
        project_root = Path(__file__).resolve().parent.parent
        app_js = (project_root / "tdp_system" / "static" / "app.js").read_text(encoding="utf-8")
        index_html = (project_root / "tdp_system" / "static" / "index.html").read_text(encoding="utf-8")
        build_script = (project_root / "BUILD_PORTABLE.ps1").read_text(encoding="utf-8")
        for marker in (
            "Luân chuyển / mặt hàng thay thế có xác nhận",
            "Mã hàng thay thế (tự chọn)",
            "Xem trước, chưa ghi",
            "Xác nhận đúng mã thay thế này",
            "Dữ liệu đã thay đổi sau lần kiểm tra",
            "/api/outgoing-substitutions/preview",
            "/api/outgoing-substitutions/confirm",
        ):
            self.assertIn(marker, app_js)
        self.assertNotIn("Gợi ý mã thay thế", app_js)
        self.assertIn("/static/app.js?v=20260907-8", index_html)
        self.assertIn("outgoing_substitution.py", build_script)
        self.assertIn("--hidden-import outgoing_substitution", build_script)


if __name__ == "__main__":
    unittest.main()
