"""Last-mile regression tests for numeric, print and invoice snapshot safety."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from flask import Flask

try:
    from . import contract_modules, server
except ImportError:  # pragma: no cover - direct file invocation
    import contract_modules
    import server


INVALID_NUMBERS = (float("nan"), float("inf"), float("-inf"), "not-a-number")


class NumericMutationRouteTests(unittest.TestCase):
    """No request-controlled numeric field may persist a non-finite/fallback value."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="tdp_final_numeric_")
        cls.old_db_path = server.DB_PATH
        cls.old_data_dir = server.DATA_DIR
        cls.old_testing = server.app.config.get("TESTING", False)
        server.DATA_DIR = Path(cls.temp.name) / "data"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "numeric.sqlite3"
        server.app.config["TESTING"] = True
        server.init_database()
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        server.DB_PATH = cls.old_db_path
        server.DATA_DIR = cls.old_data_dir
        server.app.config["TESTING"] = cls.old_testing
        cls.temp.cleanup()

    def setUp(self):
        with server.db() as conn:
            for table in (
                "outgoing_invoice_lines", "outgoing_invoice_drafts",
                "inventory_transactions", "meal_plan_items", "meal_plans",
                "dated_prices", "xcom_meal_tariffs", "xcom_payment_profile_scopes",
                "xcom_payment_previews", "xcom_payment_profiles",
                "payroll_adjustments", "attendance_entries", "staff",
                "debt_adjustments", "payments", "balances", "print_jobs",
                "orders", "batches", "audit_log",
            ):
                conn.execute(f"DELETE FROM {table}")
            conn.execute(
                "INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) "
                "VALUES('HATRAN','Ha Tran','HATRAN','group')"
            )
            conn.execute(
                "INSERT OR REPLACE INTO suppliers(code,name) VALUES('NCC-A','Supplier A')"
            )
            conn.execute(
                """INSERT OR REPLACE INTO products(
                       code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
                   ) VALUES('SAFE-P1','Safe product','kg','0%','NCC-A',10,0,'','')"""
            )
            conn.execute(
                """INSERT INTO batches(id,work_date,source_name,status,created_at)
                   VALUES(101,'2026-08-30','numeric.xlsx','draft',?)""",
                (server.now_iso(),),
            )
            conn.execute(
                """INSERT INTO staff(
                       employee_code,full_name,base_salary,standard_days,standard_hours,
                       active,created_at,updated_at
                   ) VALUES('NV01','Original employee',5000000,26,8,1,?,?)""",
                (server.now_iso(), server.now_iso()),
            )
            conn.execute(
                """INSERT INTO xcom_payment_profiles(
                       profile_code,display_name,document_type,updated_at
                   ) VALUES('BOT','BOT','MEAL_SIMPLE',?)""",
                (server.now_iso(),),
            )
            server.setting_set(conn, "print_copies", "2")
            server.setting_set(conn, "printer_name", "")
            server.setting_set(conn, "print_paper", "A4")

    @staticmethod
    def _order_payload(**overrides):
        payload = {
            "batch_id": 101,
            "contractor": "HATRAN",
            "kitchen": "POT",
            "product_code": "SAFE-P1",
            "product_name": "Safe product",
            "qty": 2,
            "actual_received": 2,
            "actual_delivered": 2,
            "damaged_qty": 0,
            "supplier_return_qty": 0,
            "customer_return_qty": 0,
            "supplier": "NCC-A",
            "buy_price": 10,
            "sell_price": 20,
            "tax": "0%",
        }
        payload.update(overrides)
        return payload

    def _rows(self, query, params=()):
        with server.db() as conn:
            return [tuple(row) for row in conn.execute(query, params).fetchall()]

    def _assert_rejected_without_change(self, method, url, payload, query, params=()):
        before = self._rows(query, params)
        response = getattr(self.client, method)(url, json=payload)
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertEqual(self._rows(query, params), before)

    def test_core_financial_and_inventory_routes_reject_non_finite_atomically(self):
        route_cases = (
            (
                "post", "/api/payments",
                {"payment_date": "2026-08-30", "kind": "receipt",
                 "party_type": "contractor", "party_code": "HATRAN"},
                "amount", "SELECT payment_date,amount FROM payments ORDER BY id",
            ),
            (
                "post", "/api/balances",
                {"party_type": "contractor", "party_code": "HATRAN",
                 "as_of_date": "2026-08-01"},
                "opening", "SELECT party_type,party_code,opening,as_of_date FROM balances ORDER BY party_code",
            ),
            (
                "post", "/api/debt-adjustments",
                {"adjustment_date": "2026-08-30", "party_type": "supplier",
                 "party_code": "NCC-A", "note": "numeric guard"},
                "amount", "SELECT adjustment_date,amount FROM debt_adjustments ORDER BY id",
            ),
            (
                "post", "/api/inventory/adjustments",
                {"txn_date": "2026-08-30", "product_code": "SAFE-P1",
                 "unit_cost": 10, "reference": "BAD-NUMBER"},
                "qty", "SELECT source_id,qty_in,qty_out,unit_cost FROM inventory_transactions ORDER BY id",
            ),
            (
                "put", "/api/dated-prices/SAFE-P1",
                {"period": "2026-08", "price_group": "HATRAN"},
                "price_value", "SELECT product_code,period,price_value FROM dated_prices ORDER BY product_code",
            ),
            (
                "put", "/api/kitchen/payment-profiles/BOT/tariffs/2026-08/TRUA",
                {}, "unit_price",
                "SELECT profile_code,period,shift,unit_price FROM xcom_meal_tariffs ORDER BY profile_code",
            ),
        )
        for method, url, base, field, query in route_cases:
            for invalid in INVALID_NUMBERS:
                with self.subTest(url=url, field=field, invalid=repr(invalid)):
                    self._assert_rejected_without_change(
                        method, url, {**base, field: invalid}, query
                    )

        for invalid in INVALID_NUMBERS:
            with self.subTest(url="/api/inventory/opening", invalid=repr(invalid)):
                payload = {
                    "period": "2026-08",
                    "items": [
                        {"product_code": "SAFE-P1", "qty": 5, "unit_cost": 10},
                        {"product_code": "SAFE-P1", "qty": invalid, "unit_cost": 10,
                         "note": "must make the whole request fail"},
                    ],
                }
                self._assert_rejected_without_change(
                    "post", "/api/inventory/opening", payload,
                    "SELECT source_id,source_line,qty_in,qty_out FROM inventory_transactions ORDER BY id",
                )

    def test_staff_attendance_payroll_and_print_settings_are_atomic(self):
        # Establish prior values so a bad request must not partially overwrite them.
        self.assertEqual(self.client.post("/api/attendance", json={
            "employee_code": "NV01", "work_date": "2026-08-30",
            "normal_hours": 8, "overtime_hours": 1,
        }).status_code, 200)
        self.assertEqual(self.client.put("/api/payroll-adjustments/NV01/2026-08", json={
            "allowance": 100, "advance": 20,
        }).status_code, 200)

        cases = (
            (
                "post", "/api/staff",
                {"employee_code": "NV01", "full_name": "Must not replace",
                 "standard_days": 26, "standard_hours": 8},
                "base_salary",
                "SELECT employee_code,full_name,base_salary,standard_days,standard_hours FROM staff WHERE employee_code='NV01'",
            ),
            (
                "post", "/api/attendance",
                {"employee_code": "NV01", "work_date": "2026-08-30",
                 "normal_hours": 2, "overtime_hours": 1},
                "night_hours",
                "SELECT work_date,normal_hours,overtime_hours,night_hours FROM attendance_entries ORDER BY id",
            ),
            (
                "put", "/api/payroll-adjustments/NV01/2026-08",
                {"allowance": 999, "advance": 20},
                "responsibility",
                "SELECT allowance,responsibility,advance FROM payroll_adjustments ORDER BY employee_id,month",
            ),
            (
                "put", "/api/print/settings",
                {"paper": "A4", "printer_name": ""},
                "copies",
                "SELECT key,value FROM settings WHERE key IN ('print_copies','printer_name','print_paper') ORDER BY key",
            ),
        )
        printer_state = {"supported": False, "default": "", "installed": [], "error": "test"}
        with patch.object(contract_modules, "windows_printer_state", return_value=printer_state):
            for method, url, base, field, query in cases:
                for invalid in INVALID_NUMBERS:
                    with self.subTest(url=url, field=field, invalid=repr(invalid)):
                        self._assert_rejected_without_change(
                            method, url, {**base, field: invalid}, query
                        )

    def test_meal_plan_create_and_update_reject_bad_numbers_before_writes(self):
        valid = {
            "work_date": "2026-08-30", "kitchen": "POT", "shift": "TRUA",
            "meal_count": 100, "menu_count": 1, "servings_per_menu": 100,
            "meal_price": 30000, "other_cost": 0,
            "items": [{"product_code": "SAFE-P1", "dish_name": "Dish",
                       "norm_qty": 0.1, "source_norm_per_1000": 100,
                       "applicable_meal_count": 100}],
        }
        created = self.client.post("/api/kitchen/plans", json=valid)
        self.assertEqual(created.status_code, 200, created.get_data(as_text=True))
        plan_id = created.get_json()["id"]
        query = (
            "SELECT p.id,p.meal_count,p.menu_count,p.meal_price,p.other_cost,i.norm_qty "
            "FROM meal_plans p LEFT JOIN meal_plan_items i ON i.plan_id=p.id ORDER BY p.id,i.id"
        )
        for invalid in INVALID_NUMBERS:
            with self.subTest(invalid=repr(invalid)):
                self._assert_rejected_without_change(
                    "post", "/api/kitchen/plans",
                    {**valid, "id": plan_id, "meal_count": 999,
                     "items": [{**valid["items"][0], "norm_qty": invalid}]},
                    query,
                )

        before_count = len(self._rows("SELECT id FROM meal_plans"))
        for invalid in INVALID_NUMBERS:
            with self.subTest(create_invalid=repr(invalid)):
                response = self.client.post(
                    "/api/kitchen/plans", json={**valid, "other_cost": invalid}
                )
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
                self.assertEqual(len(self._rows("SELECT id FROM meal_plans")), before_count)

    def test_order_draft_grid_quarantines_bad_numbers_and_blocks_approval(self):
        """Editable draft rows may be saved, but only with finite fallbacks and errors."""
        order_query = (
            "SELECT id,qty,actual_received,actual_delivered,buy_price,sell_price,errors "
            "FROM orders ORDER BY id"
        )

        def assert_all_numeric_finite(rows):
            for row in rows:
                for value in row[1:6]:
                    self.assertTrue(math.isfinite(value), row)

        def assert_approval_blocked():
            response = self.client.post("/api/batches/101/approve")
            self.assertEqual(response.status_code, 400, response.get_data(as_text=True))

        for invalid in INVALID_NUMBERS:
            with self.subTest(operation="create", invalid=repr(invalid)):
                response = self.client.post(
                    "/api/orders", json=self._order_payload(qty=invalid)
                )
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                rows = self._rows(order_query)
                self.assertEqual(len(rows), 1)
                assert_all_numeric_finite(rows)
                self.assertTrue(json.loads(rows[0][-1]))
                assert_approval_blocked()
                with server.db() as conn:
                    conn.execute("DELETE FROM orders")

        valid = self.client.post("/api/orders", json=self._order_payload())
        self.assertEqual(valid.status_code, 200, valid.get_data(as_text=True))
        order_id = valid.get_json()["id"]

        for invalid in INVALID_NUMBERS:
            with self.subTest(operation="single-update", invalid=repr(invalid)):
                response = self.client.put(
                    f"/api/orders/{order_id}", json={"qty": 8, "sell_price": invalid}
                )
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                rows = self._rows(order_query)
                assert_all_numeric_finite(rows)
                self.assertTrue(json.loads(rows[0][-1]))
                assert_approval_blocked()
                with server.db() as conn:
                    conn.execute(
                        """UPDATE orders SET qty=2,actual_received=2,actual_delivered=2,
                                  buy_price=10,sell_price=20,errors='[]' WHERE id=?""",
                        (order_id,),
                    )

        second = self.client.post("/api/orders", json=self._order_payload(qty=3))
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        second_id = second.get_json()["id"]
        for invalid in INVALID_NUMBERS:
            with self.subTest(operation="bulk-update", invalid=repr(invalid)):
                response = self.client.put(
                    "/api/orders/bulk-update", json={"batch_id": 101, "items": [
                        {"id": order_id, "qty": 9},
                        {"id": second_id, "buy_price": invalid},
                    ]},
                )
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                rows = self._rows(order_query)
                assert_all_numeric_finite(rows)
                self.assertTrue(json.loads(rows[1][-1]))
                assert_approval_blocked()
                with server.db() as conn:
                    conn.execute(
                        """UPDATE orders SET qty=CASE id WHEN ? THEN 2 ELSE 3 END,
                                  actual_received=CASE id WHEN ? THEN 2 ELSE 3 END,
                                  actual_delivered=CASE id WHEN ? THEN 2 ELSE 3 END,
                                  buy_price=10,sell_price=20,errors='[]'
                           WHERE id IN (?,?)""",
                        (order_id, order_id, order_id, order_id, second_id),
                    )

        # A pasted grid remains editable: the malformed line is quarantined in
        # draft and the entire batch remains impossible to approve.
        for invalid_text in ("NaN", "Infinity", "-Infinity", "not-a-number"):
            with self.subTest(operation="bulk-paste", invalid=invalid_text):
                response = self.client.post("/api/orders/bulk", json={
                    "batch_id": 101,
                    "text": (
                        "POT\tSafe product\t1\tNCC-A\t10\t20\t0%\n"
                        f"POT\tSafe product\t{invalid_text}\tNCC-A\t10\t20\t0%"
                    ),
                })
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                rows = self._rows(order_query)
                self.assertEqual(len(rows), 4)
                assert_all_numeric_finite(rows)
                self.assertTrue(json.loads(rows[-1][-1]))
                assert_approval_blocked()
                with server.db() as conn:
                    conn.execute("DELETE FROM orders WHERE id NOT IN (?,?)", (order_id, second_id))


class FakeMinvoiceClient:
    def __init__(self):
        self.payloads = []

    def get_invoice_info(self, *, key_api):
        return {"found": False, "data": None, "key_api": key_api}

    def create_draft(self, payload, *, dry_run=True, confirm_remote_write=False):
        self.payloads.append(json.loads(json.dumps(payload)))
        return {
            "ok": True,
            "dry_run": dry_run,
            "remote_write": not dry_run and confirm_remote_write,
            "data": {"inv_invoiceAuth_Id": "REMOTE-SNAPSHOT-1"},
            "requires_user_sign_and_issue": True,
        }


class MinvoiceFrozenSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="tdp_final_invoice_")
        cls.old_db_path = server.DB_PATH
        cls.old_data_dir = server.DATA_DIR
        cls.old_testing = server.app.config.get("TESTING", False)
        cls.old_factory = server.app.config.get("MINVOICE_CLIENT_FACTORY")
        server.DATA_DIR = Path(cls.temp.name) / "data"
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.DB_PATH = server.DATA_DIR / "invoice.sqlite3"
        server.app.config["TESTING"] = True
        server.init_database()
        cls.fake = FakeMinvoiceClient()
        server.app.config["MINVOICE_CLIENT_FACTORY"] = lambda: cls.fake
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if cls.old_factory is None:
            server.app.config.pop("MINVOICE_CLIENT_FACTORY", None)
        else:
            server.app.config["MINVOICE_CLIENT_FACTORY"] = cls.old_factory
        server.DB_PATH = cls.old_db_path
        server.DATA_DIR = cls.old_data_dir
        server.app.config["TESTING"] = cls.old_testing
        cls.temp.cleanup()

    def setUp(self):
        self.fake.payloads.clear()
        with server.db() as conn:
            conn.execute("DELETE FROM outgoing_invoice_lines")
            conn.execute("DELETE FROM outgoing_invoice_drafts")
            conn.execute("DELETE FROM outgoing_buyer_profiles")
            conn.execute("DELETE FROM audit_log")
            conn.execute(
                """INSERT INTO outgoing_invoice_drafts(
                       id,batch_id,contractor,invoice_date,status,subtotal,tax_amount,total_amount,
                       created_at,minvoice_status
                   ) VALUES(1,1,'HATRAN','2026-08-30','draft',100000,0,100000,?,'not_sent')""",
                (server.now_iso(),),
            )
            conn.execute(
                """INSERT INTO outgoing_invoice_lines(
                       draft_id,order_id,product_code,product_name,qty,unit,unit_price,tax,
                       invoice_nature,amount
                   ) VALUES(1,1,'SAFE-P1','Meal',1,'Suất',100000,'0%','1',100000)"""
            )
            conn.execute(
                """INSERT INTO outgoing_buyer_profiles(
                       contractor,display_name,legal_name,tax_code,address,email,updated_at
                   ) VALUES('HATRAN','Buyer A','BUYER LEGAL A','0201234567',
                            'Address A','a@example.test',?)""",
                (server.now_iso(),),
            )
            settings = {
                "company": "SELLER A",
                "company_tax_code": "0202265016",
                "company_address": "Seller address A",
                "payment_requester": "SELLER A",
                "payment_bank_name": "BANK A",
                "payment_bank_account": "111111",
            }
            for key, value in settings.items():
                server.setting_set(conn, key, value)

    def test_remote_save_freezes_profile_before_later_edit_and_issue(self):
        saved = self.client.post("/api/minvoice/drafts/1", json={
            "series": "1C26TDP", "dry_run": False, "confirm_remote_write": True,
        })
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        self.assertEqual(saved.get_json()["remote_id"], "REMOTE-SNAPSHOT-1")
        self.assertEqual(len(self.fake.payloads), 1)
        self.assertEqual(self.fake.payloads[0]["buyer"]["legal_name"], "BUYER LEGAL A")

        with server.db() as conn:
            snapshot_a = dict(conn.execute(
                """SELECT buyer_name_snapshot,buyer_tax_code_snapshot,buyer_address_snapshot,
                          buyer_email_snapshot,company_name_snapshot,company_tax_code_snapshot,
                          company_address_snapshot,payment_requester_snapshot,
                          payment_bank_name_snapshot,payment_bank_account_snapshot
                   FROM outgoing_invoice_drafts WHERE id=1"""
            ).fetchone())
        self.assertEqual(snapshot_a["buyer_name_snapshot"], "BUYER LEGAL A")
        self.assertEqual(snapshot_a["payment_bank_account_snapshot"], "111111")

        edited = self.client.put("/api/outgoing-buyers/HATRAN", json={
            "display_name": "Buyer B", "legal_name": "BUYER LEGAL B",
            "tax_code": "0207654321", "address": "Address B", "email": "b@example.test",
        })
        self.assertEqual(edited.status_code, 200, edited.get_data(as_text=True))
        settings_edited = self.client.put("/api/document-settings", json={
            "payment_requester": "SELLER B", "payment_bank_name": "BANK B",
            "payment_bank_account": "222222",
        })
        self.assertEqual(settings_edited.status_code, 200, settings_edited.get_data(as_text=True))

        issued = self.client.post("/api/outgoing-invoices/1/confirm-issued", json={
            "confirmed": True, "invoice_number": "123", "invoice_series": "1C26TDP",
            "invoice_date": "2026-08-30",
        })
        self.assertEqual(issued.status_code, 200, issued.get_data(as_text=True))

        with server.db() as conn:
            row = conn.execute(
                """SELECT status,buyer_name_snapshot,buyer_tax_code_snapshot,
                          buyer_address_snapshot,buyer_email_snapshot,company_name_snapshot,
                          company_tax_code_snapshot,company_address_snapshot,
                          payment_requester_snapshot,payment_bank_name_snapshot,
                          payment_bank_account_snapshot
                   FROM outgoing_invoice_drafts WHERE id=1"""
            ).fetchone()
            profile = conn.execute(
                "SELECT legal_name,tax_code,address,email FROM outgoing_buyer_profiles WHERE contractor='HATRAN'"
            ).fetchone()
        self.assertEqual(row["status"], "issued")
        self.assertEqual(
            {key: row[key] for key in snapshot_a},
            snapshot_a,
            "confirm-issued must reuse the remote-save snapshot, not mutable current settings",
        )
        self.assertEqual(tuple(profile), ("BUYER LEGAL B", "0207654321", "Address B", "b@example.test"))


class FakeWorkbook:
    def __init__(self, marker):
        self.marker = marker

    def save(self, path):
        Path(path).write_bytes(f"workbook:{self.marker}".encode("utf-8"))

    def close(self):
        return None


class PrintPrepareGenerationRaceTests(unittest.TestCase):
    def test_obsolete_generation_cannot_publish_or_poison_replacement(self):
        with tempfile.TemporaryDirectory(prefix="tdp_final_print_race_") as temp_name:
            root = Path(temp_name)
            data_dir = root / "data"
            data_dir.mkdir()
            database = data_dir / "print.sqlite3"

            @contextmanager
            def db_factory():
                conn = sqlite3.connect(database, timeout=10, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                try:
                    yield conn
                    conn.commit()
                finally:
                    conn.close()

            with db_factory() as conn:
                conn.executescript(server.SCHEMA)
                contract_modules.init_contract_schema(conn)
                conn.execute(
                    """INSERT INTO batches(id,work_date,source_name,status,created_at,approved_at)
                       VALUES(1,'2026-08-30','print.xlsx','approved','now','now')"""
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                    [("company", "TDP"), ("print_copies", "1"),
                     ("printer_name", "Printer A"), ("print_paper", "A4")],
                )

            first_claim_visible = threading.Event()
            release_first = threading.Event()

            def export_document(*_args):
                marker = threading.current_thread().name
                if marker == "prepare-A" and not first_claim_visible.is_set():
                    first_claim_visible.set()
                    if not release_first.wait(timeout=10):
                        raise TimeoutError("test did not release first print generation")
                return FakeWorkbook(marker)

            def setting_get(conn, key, default=None):
                row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
                return row["value"] if row else default

            def setting_set(conn, key, value):
                conn.execute(
                    "INSERT INTO settings(key,value) VALUES(?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(value)),
                )

            def require_batch(conn, batch_id):
                return dict(conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()), [{}]

            app = Flask("print-generation-race")
            app.testing = True
            contract_modules.register_contract_routes(app, {
                "db": db_factory,
                "now_iso": lambda: "2026-09-01T01:02:03",
                "clean_text": lambda value: str(value or "").strip(),
                "number_value": lambda value, default=0: float(
                    value if value not in (None, "") else default
                ),
                "tax_factor": lambda _value: 1.0,
                "setting_get": setting_get,
                "setting_set": setting_set,
                "root": root,
                "data_dir": data_dir,
                "require_batch": require_batch,
                "export_supplier_orders": export_document,
                "export_deliveries": export_document,
                "export_purchase_documents": export_document,
                "export_report": export_document,
            })

            def fake_build(_sections, output_path, **_kwargs):
                marker = threading.current_thread().name
                payload = f"pdf:{marker}".encode("utf-8")
                Path(output_path).write_bytes(payload)
                return {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "input_sha256": hashlib.sha256(marker.encode("utf-8")).hexdigest(),
                    "pages": 1,
                    "section_count": 4,
                }

            def fake_manifest(manifest, path):
                Path(path).write_text(json.dumps(manifest), encoding="utf-8")
                return Path(path)

            responses = {}

            def prepare(name):
                try:
                    with app.test_client() as client:
                        responses[name] = client.post("/api/print/prepare/1")
                except BaseException as exc:  # make worker failures visible without leaking DB handles
                    responses[name] = exc

            printer_state = {
                "supported": True, "default": "Printer A",
                "installed": ["Printer A", "Printer B"], "error": "",
            }
            with (
                patch.object(contract_modules, "windows_printer_state", return_value=printer_state),
                patch.object(contract_modules, "workbooks_to_sections", return_value={}),
                patch.object(contract_modules, "build_pdf_bundle", side_effect=fake_build),
                patch.object(contract_modules, "write_manifest", side_effect=fake_manifest),
            ):
                first = threading.Thread(target=prepare, args=("A",), name="prepare-A")
                first.start()
                self.assertTrue(first_claim_visible.wait(timeout=10), "A never published its preparing claim")

                with app.test_client() as client:
                    changed = client.put("/api/print/settings", json={
                        "paper": "A4", "copies": 3, "printer_name": "Printer B",
                    })
                self.assertEqual(changed.status_code, 200, changed.get_data(as_text=True))
                self.assertEqual(changed.get_json()["invalidated_jobs"], 1)

                second = threading.Thread(target=prepare, args=("B",), name="prepare-B")
                second.start()
                second.join(timeout=10)
                release_first.set()
                first.join(timeout=10)

                self.assertFalse(second.is_alive(), "replacement generation B did not finish")
                self.assertFalse(first.is_alive(), "obsolete generation A did not finish")

            if isinstance(responses.get("B"), BaseException):
                raise responses["B"]
            if isinstance(responses.get("A"), BaseException):
                raise responses["A"]
            self.assertEqual(responses["B"].status_code, 200, responses["B"].get_data(as_text=True))
            self.assertEqual(responses["A"].status_code, 409, responses["A"].get_data(as_text=True))
            with db_factory() as conn:
                row = dict(conn.execute(
                    "SELECT * FROM print_jobs WHERE batch_id=1 AND document_type='pdf_bundle'"
                ).fetchone())
            self.assertEqual(row["status"], "prepared")
            self.assertEqual(row["copies"], 3)
            self.assertEqual(row["printer_name"], "Printer B")
            self.assertIn("attempts", Path(row["file_path"]).parts)
            self.assertEqual(Path(row["file_path"]).read_bytes(), b"pdf:prepare-B")
            self.assertEqual(
                row["file_sha256"], hashlib.sha256(b"pdf:prepare-B").hexdigest()
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
