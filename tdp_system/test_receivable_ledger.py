from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from . import server
    from .receivable_ledger import sync_receivable_ledger
except ImportError:  # pragma: no cover - direct invocation
    import server
    from receivable_ledger import sync_receivable_ledger


class ReceivableLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_db_path = server.DB_PATH
        cls.original_data_dir = server.DATA_DIR
        cls.original_master_source = server.MASTER_SOURCE
        cls.original_testing = server.app.config.get("TESTING", False)
        server.DATA_DIR = Path(cls.temp.name) / "data"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "receivable-ledger.sqlite3"
        server.MASTER_SOURCE = Path(cls.temp.name) / "master-disabled.xlsx"
        server.app.config["TESTING"] = True
        server.init_database()
        cls.client = server.app.test_client()
        with server.db() as conn:
            conn.execute(
                "INSERT INTO contractors(code,name,price_group,pricing_mode) "
                "VALUES('C1','Nhà thầu Một','C1','group')"
            )
            conn.execute(
                "INSERT INTO contractors(code,name,price_group,pricing_mode) "
                "VALUES('C2','Nhà thầu Hai','C2','group')"
            )
            conn.execute(
                "INSERT INTO kitchens(code,contractor,name) VALUES('K1','C1','Bếp Một')"
            )
            conn.execute(
                "INSERT INTO kitchens(code,contractor,name) VALUES('K2','C1','Bếp Hai')"
            )
            conn.execute(
                "INSERT INTO kitchens(code,contractor,name) VALUES('K3','C2','Bếp Ba')"
            )
            conn.execute("INSERT INTO suppliers(code,name) VALUES('S1','Nhà cung cấp Một')")
            conn.execute(
                """INSERT INTO products(
                       code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
                   ) VALUES('P1','Cà rốt','kg','10%','S1',5000,0,'','')"""
            )
            conn.execute(
                "INSERT INTO product_prices(product_code,price_group,price_text,price_value) "
                "VALUES('P1','C1','10000',10000)"
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
            conn.execute("DROP TRIGGER IF EXISTS fail_receivable_revision")
            conn.execute("DELETE FROM payable_payment_revisions")
            conn.execute("DELETE FROM payable_payment_allocations")
            conn.execute("DELETE FROM receivable_ledger_revisions")
            conn.execute("DELETE FROM receivable_ledger_lines")
            conn.execute("DELETE FROM payable_ledger_revisions")
            conn.execute("DELETE FROM payable_ledger_lines")
            conn.execute("DELETE FROM outgoing_invoice_lines")
            conn.execute("DELETE FROM outgoing_invoice_drafts")
            conn.execute("DELETE FROM order_sell_price_overrides")
            conn.execute("DELETE FROM inventory_transactions")
            conn.execute("DELETE FROM purchase_workbook_line_revisions")
            conn.execute("DELETE FROM purchase_workbook_lines")
            conn.execute("DELETE FROM purchase_order_imports")
            conn.execute("DELETE FROM purchase_order_lines")
            conn.execute("DELETE FROM order_import_receipts")
            conn.execute("DELETE FROM orders")
            conn.execute("DELETE FROM batches")
            conn.execute("DELETE FROM debt_adjustments")
            conn.execute("DELETE FROM payments")
            conn.execute("DELETE FROM balances")
            conn.execute("DELETE FROM audit_log")

    @staticmethod
    def _batch(conn, work_date: str, *, status: str = "approved") -> int:
        return int(conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES(?,?,?,?,?)""",
            (
                work_date, "receivable-fixture", status, server.now_iso(),
                server.now_iso() if status == "approved" else None,
            ),
        ).lastrowid)

    @staticmethod
    def _order(
        conn, batch_id: int, work_date: str, *, contractor: str = "C1",
        kitchen: str = "K1", ordered: float = 10, delivered: float = 8,
        customer_return: float = 0, sell_price: float = 10_000,
        tax: str = "0%", source_row: int = 3,
    ) -> int:
        return int(conn.execute(
            """INSERT INTO orders(
                   batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                   actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
                   purchase_list,source_sheet,source_row,errors,warnings,updated_at,
                   customer_return_qty
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, work_date, contractor, kitchen, "P1", "Cà rốt", ordered,
                ordered, delivered, "kg", "S1", 5_000, sell_price, tax, 0,
                "đơn hàng", source_row, "[]", "[]", server.now_iso(), customer_return,
            ),
        ).lastrowid)

    def _ledger(
        self, *, date_from: str = "2026-01-01", date_to: str = "2026-12-31",
        status: str = "all", contractor: str = "", kitchen: str = "",
    ) -> dict:
        response = self.client.get(
            "/api/debts/receivables/ledger",
            query_string={
                "from": date_from, "to": date_to, "status": status,
                "contractor": contractor, "kitchen": kitchen, "limit": 20_000,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_net_delivery_transaction_price_tax_and_red_invoice_independence(self):
        with server.db() as conn:
            batch_id = self._batch(conn, "2026-09-01")
            order_id = self._order(
                conn, batch_id, "2026-09-01", ordered=10, delivered=8,
                customer_return=2, sell_price=10_000, tax="10%",
            )
            first = sync_receivable_ledger(conn, timestamp=server.now_iso())
            replay = sync_receivable_ledger(conn, timestamp=server.now_iso())
            conn.execute(
                """INSERT INTO outgoing_invoice_drafts(
                       batch_id,contractor,invoice_date,status,subtotal,tax_amount,
                       total_amount,created_at,round_no
                   ) VALUES(?,?,'2026-09-01','issued',1,1,999999,?,1)""",
                (batch_id, "C1", server.now_iso()),
            )
        self.assertEqual((first["inserted"], first["active"]), (1, 1))
        self.assertEqual((replay["unchanged"], replay["total"]), (1, 1))

        payload = self._ledger()
        self.assertEqual(
            payload["source_of_truth"],
            "approved operational delivery lines; not issued VAT invoices",
        )
        self.assertEqual(payload["summary"]["charge_amount"], 66_000)
        row = payload["rows"][0]
        self.assertEqual(
            (
                row["source"]["table"], row["source"]["id"], row["ordered_qty"],
                row["actual_delivered"], row["customer_return_qty"], row["delivered_qty"],
                row["sell_price"], row["subtotal"], row["tax_amount"], row["amount"],
            ),
            ("orders", order_id, 10, 8, 2, 6, 10_000, 60_000, 6_000, 66_000),
        )
        debt = self.client.get(
            "/api/debts", query_string={"from": "2026-09-01", "to": "2026-09-30"},
        ).get_json()
        self.assertEqual(debt["receivable_source"], "receivable_ledger_lines")
        self.assertEqual(debt["contractors"]["C1"]["period_charge"], 66_000)
        self.assertNotEqual(debt["contractors"]["C1"]["period_charge"], 999_999)

    def test_draft_approve_edit_reapprove_and_delete_are_revisioned(self):
        with server.db() as conn:
            batch_id = self._batch(conn, "2026-09-02", status="draft")
            order_id = self._order(conn, batch_id, "2026-09-02", delivered=8)
            first = sync_receivable_ledger(conn, timestamp=server.now_iso())
            repeat = sync_receivable_ledger(conn, timestamp=server.now_iso())
        self.assertEqual((first["inserted"], first["reversed"]), (1, 1))
        self.assertEqual(repeat["unchanged"], 1)
        self.assertEqual(self._ledger(status="active")["rows"], [])

        approved = self.client.post(f"/api/batches/{batch_id}/approve")
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        self.assertEqual(approved.get_json()["receivable_ledger"]["reactivated"], 1)
        line = self._ledger(status="active")["rows"][0]
        line_id = line["id"]
        self.assertEqual(line["amount"], 80_000)

        edited = self.client.put(
            f"/api/orders/{order_id}",
            json={"actual_delivered": 7, "customer_return_qty": 1, "note": "Khách trả 1 kg"},
        )
        self.assertEqual(edited.status_code, 200, edited.get_data(as_text=True))
        reversed_row = self._ledger(status="reversed")["rows"][0]
        self.assertEqual(
            (reversed_row["reversal_reason"], reversed_row["delivered_qty"], reversed_row["amount"]),
            ("batch_not_approved", 6, 60_000),
        )

        reapproved = self.client.post(f"/api/batches/{batch_id}/approve")
        self.assertEqual(reapproved.status_code, 200, reapproved.get_data(as_text=True))
        active = self._ledger(status="active")["rows"][0]
        self.assertEqual((active["id"], active["amount"]), (line_id, 60_000))

        deleted = self.client.delete(f"/api/orders/{order_id}")
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))
        removed = self._ledger(status="reversed")["rows"][0]
        self.assertEqual((removed["id"], removed["reversal_reason"]), (line_id, "source_removed"))
        history = self.client.get(
            f"/api/debts/receivables/ledger/{line_id}/revisions"
        ).get_json()["revisions"]
        self.assertEqual(
            [item["change_kind"] for item in history],
            ["insert", "reactivate", "reverse", "reactivate", "reverse"],
        )
        self.assertEqual([item["revision"] for item in history], [1, 2, 3, 4, 5])

        # SQLite may reuse the deleted highest order id.  That is a new source,
        # never a reactivation/overwrite of the removed source's audit history.
        with server.db() as conn:
            replacement_id = self._order(conn, batch_id, "2026-09-02", delivered=2)
            if replacement_id != order_id:
                conn.execute("UPDATE orders SET id=? WHERE id=?", (order_id, replacement_id))
                replacement_id = order_id
            replaced = sync_receivable_ledger(conn, timestamp=server.now_iso())
        self.assertEqual(replacement_id, order_id)
        self.assertEqual(replaced["inserted"], 1)
        all_rows = self._ledger(status="all")["rows"]
        self.assertEqual(len(all_rows), 2)
        self.assertEqual(len({row["source"]["key"] for row in all_rows}), 2)
        self.assertEqual(
            sorted(row["reversal_reason"] for row in all_rows),
            ["batch_not_approved", "source_removed"],
        )

    def test_override_price_is_the_receivable_transaction_price(self):
        with server.db() as conn:
            batch_id = self._batch(conn, "2026-09-03", status="draft")
            order_id = self._order(
                conn, batch_id, "2026-09-03", ordered=2, delivered=2,
                sell_price=10_000,
            )
            standard_before = tuple(conn.execute(
                "SELECT price_text,price_value FROM product_prices "
                "WHERE product_code='P1' AND price_group='C1'"
            ).fetchone())
        override = self.client.put("/api/orders/sell-price-overrides", json={
            "batch_id": batch_id,
            "actor": "Kế toán A",
            "reason": "Khách chốt giá giao dịch",
            "items": [{"id": order_id, "sell_price": 15_000, "expected_revision": 1}],
        })
        self.assertEqual(override.status_code, 200, override.get_data(as_text=True))
        draft_line = self._ledger(status="reversed")["rows"][0]
        self.assertEqual(
            (draft_line["sell_price"], draft_line["source"]["revision"], draft_line["amount"]),
            (15_000, 2, 30_000),
        )
        approved = self.client.post(f"/api/batches/{batch_id}/approve")
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))
        active = self._ledger(status="active")["rows"][0]
        self.assertEqual((active["sell_price"], active["amount"]), (15_000, 30_000))
        with server.db() as conn:
            standard_after = tuple(conn.execute(
                "SELECT price_text,price_value FROM product_prices "
                "WHERE product_code='P1' AND price_group='C1'"
            ).fetchone())
            audit = conn.execute(
                "SELECT metadata_json FROM audit_log WHERE event_type='order.sell_price.override'"
            ).fetchone()
        self.assertEqual(standard_after, standard_before)
        self.assertEqual(json.loads(audit["metadata_json"])["new_revision"], 2)

    def test_period_account_uses_many_batches_receipts_adjustments_and_never_payable_kind(self):
        with server.db() as conn:
            old_batch = self._batch(conn, "2026-08-30")
            self._order(conn, old_batch, "2026-08-30", delivered=9, sell_price=10_000)
            first_batch = self._batch(conn, "2026-09-01")
            self._order(
                conn, first_batch, "2026-09-01", kitchen="K1", ordered=10,
                delivered=8, customer_return=2, sell_price=10_000, tax="10%",
            )
            second_batch = self._batch(conn, "2026-09-15")
            self._order(
                conn, second_batch, "2026-09-15", kitchen="K2", ordered=5,
                delivered=5, sell_price=10_000,
            )
            other_batch = self._batch(conn, "2026-09-20")
            self._order(
                conn, other_batch, "2026-09-20", contractor="C2", kitchen="K3",
                ordered=2, delivered=2, sell_price=20_000,
            )
            sync_receivable_ledger(conn, timestamp=server.now_iso())

        balance = self.client.post("/api/balances", json={
            "party_type": "contractor", "party_code": "C1",
            "opening": 100_000, "as_of_date": "2026-08-31",
        })
        receipt = self.client.post("/api/payments", json={
            "kind": "receipt", "party_type": "contractor", "party_code": "C1",
            "payment_date": "2026-09-10", "amount": 30_000, "note": "Khách trả tiền",
            "actor": "Người thử", "request_id": "LEDGER-RECEIPT-0001",
        })
        adjustment = self.client.post("/api/debt-adjustments", json={
            "party_type": "contractor", "party_code": "C1",
            "adjustment_date": "2026-09-18", "amount": -5_000,
            "note": "Giảm trừ được duyệt",
        })
        supplier_adjustment = self.client.post("/api/debt-adjustments", json={
            "party_type": "supplier", "party_code": "S1",
            "adjustment_date": "2026-09-18", "amount": 777_000,
            "note": "Điều chỉnh riêng NCC",
        })
        self.assertEqual(receipt.status_code, 201, receipt.get_json())
        for response in (balance, adjustment, supplier_adjustment):
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with server.db() as conn:
            # A legacy/corrupt cross-kind row must not be interpreted as customer receipt.
            conn.execute(
                """INSERT INTO payments(
                       payment_date,kind,party_type,party_code,amount,note,created_at,updated_at
                   ) VALUES('2026-09-11','payment','contractor','C1',999000,
                            'wrong kind',?,?)""",
                (server.now_iso(), server.now_iso()),
            )

        debt_response = self.client.get(
            "/api/debts", query_string={"from": "2026-09-01", "to": "2026-09-30"},
        )
        self.assertEqual(debt_response.status_code, 200, debt_response.get_data(as_text=True))
        debt = debt_response.get_json()
        self.assertEqual(debt["contractors"]["C1"], {
            "opening": 100_000,
            "period_charge": 116_000,
            "period_paid": 30_000,
            "period_adjustment": -5_000,
            "closing": 181_000,
        })
        self.assertEqual(debt["contractors"]["C2"], {
            "opening": 0,
            "period_charge": 40_000,
            "period_paid": 0,
            "period_adjustment": 0,
            "closing": 40_000,
        })
        ledger = self._ledger(
            date_from="2026-09-01", date_to="2026-09-30", status="active",
        )
        self.assertEqual(ledger["summary"]["charge_amount"], 156_000)
        self.assertEqual(
            [(item["contractor_code"], item["kitchen_code"], item["amount"])
             for item in ledger["kitchen_summary"]],
            [("C1", "K1", 66_000), ("C1", "K2", 50_000), ("C2", "K3", 40_000)],
        )
        filtered = self._ledger(
            date_from="2026-09-01", date_to="2026-09-30", status="active",
            contractor="Nhà thầu Một", kitchen="Bếp Hai",
        )
        self.assertEqual([row["amount"] for row in filtered["rows"]], [50_000])
        with server.db() as conn:
            audit_types = {
                row["event_type"] for row in conn.execute(
                    "SELECT event_type FROM audit_log ORDER BY id"
                )
            }
        self.assertTrue({"balance.upsert", "payment.create", "debt.adjustment.create"} <= audit_types)

    def test_filters_validation_and_approve_rollback_are_fail_closed(self):
        bad_cases = [
            ({"from": "2026-09-xx", "to": "2026-09-30"}, "invalid_period"),
            ({"from": "2026-10-01", "to": "2026-09-30"}, "invalid_period"),
            ({"from": "2026-09-01", "to": "2026-09-30", "status": "paid"}, "invalid_status"),
            ({"from": "2026-09-01", "to": "2026-09-30", "limit": 0}, "invalid_pagination"),
        ]
        for query, code in bad_cases:
            with self.subTest(query=query):
                response = self.client.get("/api/debts/receivables/ledger", query_string=query)
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertEqual(response.get_json()["code"], code)

        with server.db() as conn:
            batch_id = self._batch(conn, "2026-09-25", status="draft")
            self._order(conn, batch_id, "2026-09-25", ordered=3, delivered=3)
            sync_receivable_ledger(conn, timestamp=server.now_iso())
            conn.execute(
                """CREATE TRIGGER fail_receivable_revision
                   BEFORE INSERT ON receivable_ledger_revisions
                   WHEN NEW.status='active'
                   BEGIN SELECT RAISE(ABORT,'forced receivable revision failure'); END"""
            )
        response = self.client.post(f"/api/batches/{batch_id}/approve")
        self.assertEqual(response.status_code, 500, response.get_data(as_text=True))
        with server.db() as conn:
            conn.execute("DROP TRIGGER fail_receivable_revision")
            batch = conn.execute("SELECT status,approved_at FROM batches WHERE id=?", (batch_id,)).fetchone()
            line = conn.execute(
                "SELECT status,reversal_reason,revision FROM receivable_ledger_lines"
            ).fetchone()
            revisions = conn.execute(
                "SELECT COUNT(*) n FROM receivable_ledger_revisions"
            ).fetchone()["n"]
            inventory = conn.execute(
                "SELECT COUNT(*) n FROM inventory_transactions "
                "WHERE source_type='BK_INPUT' AND source_id=?", (str(batch_id),)
            ).fetchone()["n"]
        self.assertEqual(tuple(batch), ("draft", None))
        self.assertEqual(tuple(line), ("reversed", "batch_not_approved", 1))
        self.assertEqual((revisions, inventory), (1, 0))


if __name__ == "__main__":
    unittest.main()
