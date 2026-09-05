from __future__ import annotations

import json
import sqlite3
import unittest

try:
    from .daily_import_lifecycle import (
        DailyImportError,
        confirm_daily_import_scope,
        daily_payload_hash,
        daily_row_key,
        finalize_daily_workday,
        init_daily_import_schema,
        prepare_daily_import_version,
    )
except ImportError:  # pragma: no cover - direct invocation
    from daily_import_lifecycle import (
        DailyImportError,
        confirm_daily_import_scope,
        daily_payload_hash,
        daily_row_key,
        finalize_daily_workday,
        init_daily_import_schema,
        prepare_daily_import_version,
    )


NOW = "2026-09-02T16:40:00"


def now_iso() -> str:
    return NOW


def base_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE batches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_date TEXT NOT NULL,
            source_name TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            approved_at TEXT
        );
        CREATE TABLE orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,
            product_name TEXT
        );
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
        """
    )
    return conn


def preview_rows(qty: float = 2) -> dict:
    return {
        "customer_orders": [{
            "identity": {
                "contractor": "ATV",
                "kitchen": "BEP-01",
                "product_code": "P-01",
                "product_name": "Cà rốt",
                "unit": "kg",
                "occurrence": 1,
            },
            "payload": {"qty": qty, "sell_price": 12000, "customer_note": "PRIVATE-CUSTOMER"},
            "source_row": 8,
        }],
        "purchase_orders": [{
            "identity": {
                "contractor": "ATV",
                "kitchen": "BEP-01",
                "product_code": "P-01",
                "product_name": "Cà rốt",
                "unit": "kg",
                "occurrence": 1,
            },
            "payload": {"qty": qty, "buy_price": 10000, "cccd": "PRIVATE-CCCD"},
            "source_row": 260,
        }],
    }


class DailyImportLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.conn = base_database()
        init_daily_import_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def prepare(self, *, source="A", phase="first_load", rows=None, sheet="01.09"):
        return prepare_daily_import_version(
            self.conn,
            source_hash=source * 64,
            work_date="2026-09-01",
            day_sheet=sheet,
            phase=phase,
            rows_by_scope=rows or preview_rows(),
            now_iso=now_iso,
        )

    def test_migration_is_minimal_repeatable_and_preserves_old_rows(self):
        self.conn.execute(
            "INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-08-31','legacy','draft',?)",
            (NOW,),
        )
        batch_id = self.conn.execute("SELECT id FROM batches").fetchone()[0]
        self.conn.execute(
            "INSERT INTO orders(batch_id,product_name) VALUES(?, 'Legacy product')", (batch_id,)
        )
        init_daily_import_schema(self.conn)
        init_daily_import_schema(self.conn)
        self.assertEqual((1, 1), (
            self.conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        ))
        self.assertEqual(
            {"daily_workdays", "daily_import_versions", "daily_import_scopes", "daily_import_rows"},
            {row[0] for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'daily_%'"
            )},
        )
        self.assertEqual("ok", self.conn.execute("PRAGMA integrity_check").fetchone()[0])

    def test_migration_rolls_back_all_new_tables_when_ddl_fails_midway(self):
        conn = base_database()
        try:
            def authorizer(action, arg1, _arg2, _db_name, _trigger):
                if action == sqlite3.SQLITE_CREATE_TABLE and arg1 == "daily_import_versions":
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            conn.set_authorizer(authorizer)
            with self.assertRaisesRegex(DailyImportError, "đã được hoàn tác"):
                init_daily_import_schema(conn)
            conn.set_authorizer(None)
            self.assertEqual([], [row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'daily_%'"
            )])
            self.assertEqual("ok", conn.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            conn.close()

    def test_same_workbook_scope_replay_never_creates_a_second_batch(self):
        first = self.prepare()
        replay = self.prepare(sheet="  01.09  ")
        self.assertFalse(first["idempotent"])
        self.assertTrue(replay["idempotent"])
        self.assertEqual(first["batch_id"], replay["batch_id"])
        self.assertEqual(first["version_id"], replay["version_id"])
        self.assertEqual((1, 1, 2, 2), tuple(
            self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "batches", "daily_import_versions", "daily_import_scopes", "daily_import_rows"
            )
        ))

    def test_changed_workbook_becomes_new_version_of_same_workday_batch(self):
        first = self.prepare(source="A", phase="first_load", rows=preview_rows(2))
        second = self.prepare(source="B", phase="finalization", rows=preview_rows(3))
        self.assertEqual(first["batch_id"], second["batch_id"])
        self.assertEqual((1, 2), (first["version_no"], second["version_no"]))
        self.assertEqual(2, second["lifecycle_revision"])
        self.assertEqual(1, self.conn.execute("SELECT COUNT(*) FROM batches").fetchone()[0])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM daily_import_versions"
        ).fetchone()[0])

    def test_business_row_identity_survives_qty_change_but_payload_version_changes(self):
        identity = preview_rows(2)["customer_orders"][0]["identity"]
        key_before = daily_row_key(
            work_date="2026-09-01", scope="customer_orders", identity=identity
        )
        key_after = daily_row_key(
            work_date="2026-09-01", scope="customer_orders", identity={**identity, "qty": 999}
        )
        self.assertEqual(key_before, key_after)
        self.assertNotEqual(daily_payload_hash({"qty": 2}), daily_payload_hash({"qty": 3}))
        self.assertNotEqual(
            key_before,
            daily_row_key(
                work_date="2026-09-01",
                scope="purchase_orders",
                identity=identity,
            ),
        )

    def test_scope_confirmation_is_separate_stale_safe_and_audit_has_no_pii(self):
        prepared = self.prepare()
        scopes = {row["scope"]: row for row in prepared["scopes"]}
        with self.assertRaisesRegex(DailyImportError, "Preview đã cũ"):
            confirm_daily_import_scope(
                self.conn,
                version_id=prepared["version_id"],
                scope="customer_orders",
                expected_state_hash="F" * 64,
                now_iso=now_iso,
            )
        confirmed = confirm_daily_import_scope(
            self.conn,
            version_id=prepared["version_id"],
            scope="customer_orders",
            expected_state_hash=scopes["customer_orders"]["state_hash"],
            now_iso=now_iso,
        )
        replay = confirm_daily_import_scope(
            self.conn,
            version_id=prepared["version_id"],
            scope="customer_orders",
            expected_state_hash=scopes["customer_orders"]["state_hash"],
            now_iso=now_iso,
        )
        self.assertEqual("update_customer_orders", confirmed["write_capability"])
        self.assertFalse(confirmed["idempotent"])
        self.assertTrue(replay["idempotent"])
        states = {row["scope"]: row["state"] for row in self.conn.execute(
            "SELECT scope,state FROM daily_import_scopes WHERE version_id=?",
            (prepared["version_id"],),
        )}
        self.assertEqual({"customer_orders": "confirmed", "purchase_orders": "previewed"}, states)
        audit = "\n".join(row[0] for row in self.conn.execute(
            "SELECT metadata_json FROM audit_log WHERE event_type LIKE 'daily_import.%'"
        ))
        self.assertNotIn("PRIVATE-CUSTOMER", audit)
        self.assertNotIn("PRIVATE-CCCD", audit)
        self.assertNotIn("Cà rốt", audit)
        for metadata in self.conn.execute(
            "SELECT metadata_json FROM audit_log WHERE event_type LIKE 'daily_import.%'"
        ):
            json.loads(metadata[0])

    def test_prepare_failure_rolls_back_batch_version_scopes_and_rows(self):
        self.conn.execute(
            """CREATE TRIGGER fail_second_daily_row BEFORE INSERT ON daily_import_rows
               WHEN NEW.source_row=260
               BEGIN SELECT RAISE(ABORT,'fixture second scope failure'); END"""
        )
        with self.assertRaisesRegex(DailyImportError, "toàn bộ migration dữ liệu đã hoàn tác"):
            self.prepare()
        for table in (
            "batches", "daily_workdays", "daily_import_versions",
            "daily_import_scopes", "daily_import_rows", "audit_log",
        ):
            self.assertEqual(0, self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        self.assertEqual("ok", self.conn.execute("PRAGMA integrity_check").fetchone()[0])

    def test_finalization_is_explicit_and_does_not_bypass_legacy_batch_approval(self):
        self.prepare(source="A", phase="first_load")
        final = self.prepare(source="B", phase="finalization", rows={
            "purchase_orders": preview_rows(3)["purchase_orders"]
        })
        scope = final["scopes"][0]
        with self.assertRaisesRegex(DailyImportError, "xác nhận ít nhất một phạm vi"):
            finalize_daily_workday(self.conn, version_id=final["version_id"], now_iso=now_iso)
        confirm_daily_import_scope(
            self.conn,
            version_id=final["version_id"],
            scope="purchase_orders",
            expected_state_hash=scope["state_hash"],
            now_iso=now_iso,
        )
        completed = finalize_daily_workday(
            self.conn, version_id=final["version_id"], now_iso=now_iso
        )
        replay = finalize_daily_workday(
            self.conn, version_id=final["version_id"], now_iso=now_iso
        )
        self.assertFalse(completed["idempotent"])
        self.assertTrue(replay["idempotent"])
        self.assertEqual("finalized", completed["lifecycle_status"])
        self.assertEqual("draft", self.conn.execute(
            "SELECT status FROM batches WHERE id=?", (final["batch_id"],)
        ).fetchone()[0])
        with self.assertRaisesRegex(DailyImportError, "Ngày đã chốt"):
            self.prepare(source="C", phase="finalization")

    def test_confirm_and_finalize_failures_roll_back_their_state(self):
        final = self.prepare(source="B", phase="finalization", rows={
            "purchase_orders": preview_rows(3)["purchase_orders"]
        })
        scope = final["scopes"][0]
        self.conn.execute(
            """CREATE TRIGGER fail_scope_audit BEFORE INSERT ON audit_log
               WHEN NEW.event_type='daily_import.scope_confirm'
               BEGIN SELECT RAISE(ABORT,'fixture confirm audit failure'); END"""
        )
        with self.assertRaisesRegex(DailyImportError, "toàn bộ thay đổi đã hoàn tác"):
            confirm_daily_import_scope(
                self.conn,
                version_id=final["version_id"],
                scope="purchase_orders",
                expected_state_hash=scope["state_hash"],
                now_iso=now_iso,
            )
        self.assertEqual("previewed", self.conn.execute(
            "SELECT state FROM daily_import_scopes WHERE version_id=?",
            (final["version_id"],),
        ).fetchone()[0])
        self.assertEqual("previewed", self.conn.execute(
            "SELECT state FROM daily_import_rows WHERE version_id=?",
            (final["version_id"],),
        ).fetchone()[0])
        self.conn.execute("DROP TRIGGER fail_scope_audit")
        confirm_daily_import_scope(
            self.conn,
            version_id=final["version_id"],
            scope="purchase_orders",
            expected_state_hash=scope["state_hash"],
            now_iso=now_iso,
        )
        self.conn.execute(
            """CREATE TRIGGER fail_finalize_audit BEFORE INSERT ON audit_log
               WHEN NEW.event_type='daily_import.finalize'
               BEGIN SELECT RAISE(ABORT,'fixture finalize audit failure'); END"""
        )
        with self.assertRaisesRegex(DailyImportError, "trạng thái đã hoàn tác"):
            finalize_daily_workday(self.conn, version_id=final["version_id"], now_iso=now_iso)
        self.assertEqual("picking", self.conn.execute(
            "SELECT lifecycle_status FROM daily_workdays"
        ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
