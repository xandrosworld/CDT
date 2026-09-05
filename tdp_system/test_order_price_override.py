from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from . import server
except ImportError:  # pragma: no cover - direct file invocation
    import server


class OrderPriceOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_db_path = server.DB_PATH
        cls.original_data_dir = server.DATA_DIR
        cls.original_master_source = server.MASTER_SOURCE
        cls.original_testing = server.app.config.get("TESTING", False)
        server.DATA_DIR = Path(cls.temp.name) / "data"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "price-override.sqlite3"
        server.MASTER_SOURCE = Path(cls.temp.name) / "master-disabled.xlsx"
        server.app.config["TESTING"] = True
        server.init_database()
        cls.client = server.app.test_client()
        with server.db() as conn:
            conn.execute(
                "INSERT INTO contractors(code,name,price_group,pricing_mode) VALUES('C1','C1','C1','group')"
            )
            conn.execute("INSERT INTO kitchens(code,contractor,name) VALUES('K1','C1','Kitchen 1')")
            conn.execute("INSERT INTO suppliers(code,name) VALUES('S1','Supplier 1')")
            conn.execute(
                """INSERT INTO products(
                       code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
                   ) VALUES('P1','Product 1','kg','KKKNT','S1',10000,0,'','')"""
            )
            conn.execute(
                "INSERT INTO product_prices(product_code,price_group,price_text,price_value) VALUES('P1','C1','12000',12000)"
            )

    @classmethod
    def tearDownClass(cls):
        server.DB_PATH = cls.original_db_path
        server.DATA_DIR = cls.original_data_dir
        server.MASTER_SOURCE = cls.original_master_source
        server.app.config["TESTING"] = cls.original_testing
        cls.temp.cleanup()

    def setUp(self):
        with server.db() as conn:
            conn.execute("DROP TRIGGER IF EXISTS fail_second_price_history")
            conn.execute("DELETE FROM order_sell_price_overrides")
            conn.execute("DELETE FROM audit_log WHERE event_type='order.sell_price.override'")
            conn.execute("DELETE FROM order_import_receipts")
            conn.execute("DELETE FROM batches")

    def create_order(self, *, price=12000, nature="1", qty=2):
        with server.db() as conn:
            batch_id = int(conn.execute(
                "INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-09-01','test','draft',?)",
                (server.now_iso(),),
            ).lastrowid)
            order_id = int(conn.execute(
                """INSERT INTO orders(
                       batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                       actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
                       invoice_nature,purchase_list,errors,warnings,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    batch_id, "2026-09-01", "C1", "K1", "P1", "Product 1", qty,
                    qty, qty, "kg", "S1", 10000, price, "KKKNT", nature, 0, "[]", "[]",
                    server.now_iso(),
                ),
            ).lastrowid)
        return batch_id, order_id

    def add_order(self, batch_id, *, price=12000, qty=1):
        with server.db() as conn:
            return int(conn.execute(
                """INSERT INTO orders(
                       batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                       actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
                       invoice_nature,purchase_list,errors,warnings,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    batch_id, "2026-09-01", "C1", "K1", "P1", "Product 1", qty,
                    qty, qty, "kg", "S1", 10000, price, "KKKNT", "1", 0, "[]", "[]",
                    server.now_iso(),
                ),
            ).lastrowid)

    def override(self, batch_id, items, *, actor="Operator A", reason="Khách chốt lại giá"):
        return self.client.put(
            "/api/orders/sell-price-overrides",
            json={"batch_id": batch_id, "actor": actor, "reason": reason, "items": items},
        )

    def test_single_override_updates_revenue_receivable_and_queryable_audit(self):
        batch_id, order_id = self.create_order()
        with server.db() as conn:
            standard_before = tuple(conn.execute(
                "SELECT price_text,price_value FROM product_prices WHERE product_code='P1' AND price_group='C1'"
            ).fetchone())
        response = self.override(batch_id, [{
            "id": order_id, "sell_price": 15000, "expected_revision": 1,
        }])
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["updated"], 1)
        self.assertEqual(payload["summary"]["totals"]["revenue"], 30000)
        order = payload["orders"][0]
        self.assertEqual(
            (order["sell_price"], order["sell_price_revision"], order["sell_price_source"]),
            (15000, 2, "manual_override"),
        )
        history = self.client.get(
            f"/api/orders/sell-price-overrides?order_id={order_id}"
        ).get_json()["items"]
        self.assertEqual(len(history), 1)
        self.assertEqual(
            (history[0]["old_price"], history[0]["new_price"], history[0]["actor"], history[0]["reason"]),
            (12000, 15000, "Operator A", "Khách chốt lại giá"),
        )
        with server.db() as conn:
            standard_after = tuple(conn.execute(
                "SELECT price_text,price_value FROM product_prices WHERE product_code='P1' AND price_group='C1'"
            ).fetchone())
            audit = conn.execute(
                "SELECT metadata_json,created_at FROM audit_log WHERE event_type='order.sell_price.override'"
            ).fetchone()
        self.assertEqual(standard_after, standard_before)
        metadata = json.loads(audit["metadata_json"])
        self.assertEqual((metadata["actor"], metadata["reason"], metadata["new_revision"]),
                         ("Operator A", "Khách chốt lại giá", 2))
        self.assertTrue(audit["created_at"])

        approved = self.client.post(f"/api/batches/{batch_id}/approve")
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        debts = self.client.get("/api/debts?from=2026-09-01&to=2026-09-30").get_json()
        self.assertEqual(debts["contractors"]["C1"]["period_charge"], 30000)

    def test_bulk_failure_rolls_back_every_price_history_and_audit(self):
        batch_id, first_id = self.create_order()
        second_id = self.add_order(batch_id)
        with server.db() as conn:
            conn.execute(
                f"""CREATE TRIGGER fail_second_price_history BEFORE INSERT ON order_sell_price_overrides
                    WHEN NEW.order_id={second_id}
                    BEGIN SELECT RAISE(ABORT,'forced second price failure'); END"""
            )
        response = self.override(batch_id, [
            {"id": first_id, "sell_price": 13000, "expected_revision": 1},
            {"id": second_id, "sell_price": 14000, "expected_revision": 1},
        ])
        self.assertEqual(response.status_code, 500, response.get_data(as_text=True))
        with server.db() as conn:
            conn.execute("DROP TRIGGER fail_second_price_history")
            rows = conn.execute(
                "SELECT sell_price,sell_price_revision,sell_price_source FROM orders ORDER BY id"
            ).fetchall()
            history_count = conn.execute("SELECT COUNT(*) FROM order_sell_price_overrides").fetchone()[0]
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE event_type='order.sell_price.override'"
            ).fetchone()[0]
        self.assertEqual([tuple(row) for row in rows], [
            (12000, 1, "import_or_standard"), (12000, 1, "import_or_standard"),
        ])
        self.assertEqual((history_count, audit_count), (0, 0))

    def test_stale_revision_cannot_overwrite_newer_price(self):
        batch_id, order_id = self.create_order()
        first = self.override(batch_id, [{
            "id": order_id, "sell_price": 13000, "expected_revision": 1,
        }])
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        stale = self.override(batch_id, [{
            "id": order_id, "sell_price": 14000, "expected_revision": 1,
        }])
        self.assertEqual(stale.status_code, 409, stale.get_data(as_text=True))
        self.assertEqual(stale.get_json()["code"], "stale_price_revision")
        with server.db() as conn:
            order = conn.execute("SELECT sell_price,sell_price_revision FROM orders WHERE id=?", (order_id,)).fetchone()
            self.assertEqual(tuple(order), (13000, 2))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM order_sell_price_overrides").fetchone()[0], 1)

    def test_nonfinite_negative_zero_and_promotion_prices_are_blocked(self):
        invalid_cases = [(-1, "invalid_price_patch"), ("NaN", "invalid_price_patch"), (0, "positive_price_required")]
        for price, expected_code in invalid_cases:
            with self.subTest(price=price):
                batch_id, order_id = self.create_order()
                response = self.override(batch_id, [{
                    "id": order_id, "sell_price": price, "expected_revision": 1,
                }])
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertEqual(response.get_json()["code"], expected_code)
                with server.db() as conn:
                    conn.execute("DELETE FROM batches WHERE id=?", (batch_id,))
        batch_id, order_id = self.create_order(price=0, nature="2")
        promotion = self.override(batch_id, [{
            "id": order_id, "sell_price": 1, "expected_revision": 1,
        }])
        self.assertEqual(promotion.status_code, 400, promotion.get_data(as_text=True))
        self.assertEqual(promotion.get_json()["code"], "promotion_price_must_be_zero")
        with server.db() as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM order_sell_price_overrides").fetchone())

    def test_actor_reason_required_and_generic_update_cannot_bypass_audit(self):
        batch_id, order_id = self.create_order()
        missing_actor = self.override(
            batch_id, [{"id": order_id, "sell_price": 13000, "expected_revision": 1}], actor="",
        )
        self.assertEqual(missing_actor.status_code, 400)
        self.assertEqual(missing_actor.get_json()["code"], "actor_required")
        missing_reason = self.override(
            batch_id, [{"id": order_id, "sell_price": 13000, "expected_revision": 1}], reason="",
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.assertEqual(missing_reason.get_json()["code"], "reason_required")

        direct = self.client.put(f"/api/orders/{order_id}", json={"sell_price": 13000})
        self.assertEqual(direct.status_code, 409, direct.get_data(as_text=True))
        self.assertEqual(direct.get_json()["code"], "sell_price_override_required")
        bulk = self.client.put("/api/orders/bulk-update", json={
            "batch_id": batch_id, "items": [{"id": order_id, "sell_price": 13000}],
        })
        self.assertEqual(bulk.status_code, 409, bulk.get_data(as_text=True))
        self.assertEqual(bulk.get_json()["code"], "sell_price_override_required")
        with server.db() as conn:
            self.assertEqual(conn.execute("SELECT sell_price FROM orders WHERE id=?", (order_id,)).fetchone()[0], 12000)
            self.assertFalse(conn.execute("SELECT 1 FROM order_sell_price_overrides").fetchone())

    def test_frontend_has_inline_bulk_and_keyboard_price_flow(self):
        script = (Path(server.STATIC_DIR) / "app.js").read_text(encoding="utf-8")
        self.assertIn('class="quick-sell-price"', script)
        self.assertIn('data-action="save-price-overrides"', script)
        self.assertIn('saveSellPriceOverrides([quickPrice])', script)
        self.assertIn('expected_revision: Number(input.dataset.revision || 1)', script)
        self.assertIn('readonly title="Sửa giá trên bảng để lưu lịch sử thay đổi"', script)


if __name__ == "__main__":
    unittest.main()
