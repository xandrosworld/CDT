import sqlite3
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from flask import Flask

try:
    from .contract_modules import init_contract_schema, register_contract_routes
    from .xcom_payment_documents import init_xcom_payment_schema
except ImportError:
    from contract_modules import init_contract_schema, register_contract_routes
    from xcom_payment_documents import init_xcom_payment_schema


class XcomPaymentRouteTests(unittest.TestCase):
    def test_contract_startup_migrates_xcom_payment_schema_idempotently(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE products(code TEXT PRIMARY KEY);
            CREATE TABLE balances(id INTEGER PRIMARY KEY);
            CREATE TABLE orders(id INTEGER PRIMARY KEY);
            """
        )
        init_contract_schema(connection)
        init_contract_schema(connection)
        tables = {
            row["name"] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertTrue({
            "xcom_payment_profiles", "xcom_payment_profile_scopes", "xcom_meal_tariffs",
            "xcom_payment_previews",
        }.issubset(tables))
        connection.close()

    def setUp(self):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE audit_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                status TEXT NOT NULL,
                message TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE kitchen_units(
                kitchen_code TEXT PRIMARY KEY,
                unit_code TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE meal_attendance(
                work_date TEXT NOT NULL,
                kitchen TEXT NOT NULL,
                shift TEXT NOT NULL,
                actual_count REAL NOT NULL DEFAULT 0,
                ordered_count REAL NOT NULL DEFAULT 0,
                source_type TEXT NOT NULL DEFAULT 'MONTHLY_WORKBOOK',
                source_file TEXT,
                source_sheet TEXT,
                source_column TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(work_date,kitchen,shift)
            );
            INSERT INTO kitchen_units VALUES('VINA','XCOM-A','2026-08-31T20:00:00');
            INSERT INTO meal_attendance(
                work_date,kitchen,shift,actual_count,ordered_count,updated_at
            ) VALUES('2026-08-01','VINA','Sáng',2,999,'2026-08-31T20:00:00');
            """
        )
        init_xcom_payment_schema(self.connection)

        @contextmanager
        def database():
            try:
                yield self.connection
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

        app = Flask(__name__)
        register_contract_routes(app, {
            "db": database,
            "now_iso": lambda: "2026-08-31T20:00:00",
            "clean_text": lambda value: str(value or "").strip(),
            "number_value": lambda value, default=0: float(value if value not in (None, "") else default),
            "tax_factor": lambda value: 1.0,
            "setting_get": lambda conn, key, default="": default,
            "setting_set": lambda conn, key, value: None,
            "create_minvoice_client": None,
            "root": Path.cwd(),
            "data_dir": Path.cwd() / "tdp_system" / "data",
        })
        app.testing = True
        self.client = app.test_client()

    def tearDown(self):
        self.connection.close()

    def test_profile_scope_tariff_preview_export_and_confirmed_deletes(self):
        profile = {
            "document_type": "MEAL_SIMPLE",
            "issuer_name": "CÔNG TY TNHH DỊCH VỤ HÀ TRÂN",
            "recipient_name": "CÔNG TY KHÁCH HÀNG",
            "beneficiary_name": "CÔNG TY TNHH DỊCH VỤ HÀ TRÂN",
            "bank_account": "0031000318858",
            "bank_name": "Vietcombank CN Hải Phòng",
            "requester": "HOÀNG THỊ TUYẾT",
            "vat_rate": "8",
        }
        invalid_bot = {
            **profile,
            "document_type": "MEAL_BOT_BUNDLE",
            "issuer_tax_code": "0201853470",
            "recipient_tax_code": "0201650135-12",
        }
        invalid = self.client.put("/api/kitchen/payment-profiles/INVALID", json=invalid_bot)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["code"], "invalid_tax_code")
        response = self.client.put("/api/kitchen/payment-profiles/VINA", json=profile)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

        invalid_period = self.client.put(
            "/api/kitchen/payment-profiles/VINA/tariffs/2026-13/S%C3%A1ng",
            json={"unit_price": 25_000},
        )
        self.assertEqual(invalid_period.status_code, 400)
        invalid_range = self.client.post("/api/kitchen/payment-documents/preview", json={
            "profile_code": "VINA", "date_from": "2026-08-31", "date_to": "2026-08-01",
            "issue_date": "2026-08-31",
        })
        self.assertEqual(invalid_range.status_code, 400)
        self.assertEqual(invalid_range.get_json()["code"], "invalid_date_range")
        self.assertTrue(response.get_json()["created"])

        response = self.client.put(
            "/api/kitchen/payment-profiles/VINA/scopes/XCOM/XCOM-A", json={}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        response = self.client.put(
            "/api/kitchen/payment-profiles/VINA/tariffs/2026-08/S%C3%A1ng",
            json={"unit_price": 25_000},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

        listed = self.client.get("/api/kitchen/payment-profiles")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["items"][0]["scopes"][0]["scope_code"], "XCOM-A")
        self.assertEqual(listed.get_json()["items"][0]["tariffs"][0]["unit_price"], "25000")

        sql_trace = []
        self.connection.set_trace_callback(sql_trace.append)
        preview = self.client.post("/api/kitchen/payment-documents/preview", json={
            "profile_code": "VINA", "date_from": "2026-08-01", "date_to": "2026-08-31",
            "issue_date": "2026-08-31",
        })
        self.assertEqual(preview.status_code, 200, preview.get_data(as_text=True))
        self.assertTrue(any(statement == "BEGIN IMMEDIATE" for statement in sql_trace))
        summary = preview.get_json()["summary"]
        self.assertEqual(summary["actual_count"], 2)
        self.assertEqual(summary["subtotal"], 50_000)
        self.assertEqual(summary["vat_amount"], 4_000)
        self.assertEqual(summary["total"], 54_000)
        self.assertNotEqual(summary["actual_count"], 999)
        self.assertEqual(preview.get_json()["expires_at"], "2026-08-31T20:15:00")

        self.assertEqual(self.client.get("/api/kitchen/payment-documents/export").status_code, 405)
        export_payload = {
            "profile_code": "VINA", "date_from": "2026-08-01", "date_to": "2026-08-31",
            "issue_date": "2026-08-31",
        }
        unpreviewed = self.client.post(
            "/api/kitchen/payment-documents/export", json=export_payload
        )
        self.assertEqual(unpreviewed.status_code, 409)
        self.assertEqual(unpreviewed.get_json()["code"], "preview_required")

        # An exact-period tariff edit after preview must invalidate that token.
        stale_token = preview.get_json()["preview_token"]
        self.assertEqual(self.client.put(
            "/api/kitchen/payment-profiles/VINA/tariffs/2026-08/S%C3%A1ng",
            json={"unit_price": 26_000},
        ).status_code, 200)
        stale = self.client.post(
            "/api/kitchen/payment-documents/export",
            json={**export_payload, "preview_token": stale_token},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["code"], "stale_preview")
        self.assertEqual(self.client.put(
            "/api/kitchen/payment-profiles/VINA/tariffs/2026-08/S%C3%A1ng",
            json={"unit_price": 25_000},
        ).status_code, 200)
        fresh_preview = self.client.post("/api/kitchen/payment-documents/preview", json={
            "profile_code": "VINA", "date_from": "2026-08-01", "date_to": "2026-08-31",
            "issue_date": "2026-08-31",
        }).get_json()

        sql_trace.clear()
        exported = self.client.post(
            "/api/kitchen/payment-documents/export",
            json={**export_payload, "preview_token": fresh_preview["preview_token"]},
        )
        self.assertEqual(exported.status_code, 200)
        self.assertTrue(any(statement == "BEGIN IMMEDIATE" for statement in sql_trace))
        self.assertGreater(len(exported.data), 10_000)
        self.assertIn("wordprocessingml.document", exported.content_type)
        self.assertIn("De_nghi_thanh_toan_suat_an_VINA", exported.headers["Content-Disposition"])
        reused = self.client.post(
            "/api/kitchen/payment-documents/export",
            json={**export_payload, "preview_token": fresh_preview["preview_token"]},
        )
        self.assertEqual(reused.status_code, 409)
        self.assertEqual(reused.get_json()["code"], "preview_used")

        # Destructive CRUD is always confirmation-gated.
        blocked = self.client.delete(
            "/api/kitchen/payment-profiles/VINA/tariffs/2026-08/S%C3%A1ng", json={}
        )
        self.assertEqual(blocked.status_code, 400)
        deleted = self.client.delete(
            "/api/kitchen/payment-profiles/VINA/tariffs/2026-08/S%C3%A1ng",
            json={"confirmed": True},
        )
        self.assertEqual(deleted.status_code, 200)
        missing = self.client.post("/api/kitchen/payment-documents/preview", json={
            "profile_code": "VINA", "date_from": "2026-08-01", "date_to": "2026-08-31",
            "issue_date": "2026-08-31",
        })
        self.assertEqual(missing.status_code, 409)
        self.assertEqual(missing.get_json()["code"], "missing_tariff")

        deleted_scope = self.client.delete(
            "/api/kitchen/payment-scopes/XCOM/XCOM-A", json={"confirmed": True}
        )
        self.assertEqual(deleted_scope.status_code, 200)
        deleted_profile = self.client.delete(
            "/api/kitchen/payment-profiles/VINA", json={"confirmed": True}
        )
        self.assertEqual(deleted_profile.status_code, 200)
        self.assertEqual(self.client.get("/api/kitchen/payment-profiles").get_json()["items"], [])
        self.assertGreaterEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM audit_log WHERE event_type LIKE 'kitchen.%'"
            ).fetchone()[0],
            6,
        )
        self.connection.set_trace_callback(None)


if __name__ == "__main__":
    unittest.main()
