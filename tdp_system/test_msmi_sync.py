from __future__ import annotations

import json
import sqlite3
import unittest
from copy import deepcopy
from unittest.mock import patch

try:
    from contract_modules import init_contract_schema, sync_msmi, upsert_msmi_invoice
    from msmi_client import MsmiClient, MsmiConfig
except ImportError:  # pragma: no cover - package invocation
    from .contract_modules import init_contract_schema, sync_msmi, upsert_msmi_invoice
    from .msmi_client import MsmiClient, MsmiConfig


def remote_invoice(number: int) -> dict:
    return {
        "_id": f"MSMI-{number:03d}",
        "mstNban": "0200000001",
        "tenNban": "NCC kiem thu",
        "shdon": str(number),
        "khhdon": "C26TST",
        "tdlap": f"2026-08-{number:02d}",
        "tgtcthue": 10_000,
        "tgtthue": 800,
        "tgtttbso": 10_800,
        "hdhhdvu": [{
            "ma": f"SRC-{number:03d}",
            "ten": f"Mat hang {number}",
            "dvtinh": "kg",
            "sluong": 1,
            "dgia": 10_000,
            "thtien": 10_000,
            "tsuat": "8%",
        }],
    }


class PagedMsmi:
    """Newest-first, read-only fake with the same paging contract as mSMI."""

    def __init__(self, items):
        self.items = list(items)
        self.calls = []

    def list_invoices(self, *, invoice_type, page, size):
        self.calls.append({"invoice_type": invoice_type, "page": page, "size": size})
        start = page * size
        selected = self.items[start:start + size]
        return {
            "items": selected,
            "page": page,
            "size": size,
            "has_more": start + len(selected) < len(self.items),
        }


class FailingSecondPage(PagedMsmi):
    def list_invoices(self, *, invoice_type, page, size):
        if page == 1:
            raise RuntimeError("simulated remote page failure")
        return super().list_invoices(invoice_type=invoice_type, page=page, size=size)


def memory_database_with_legacy_sync_state():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    # Base tables normally come from server.py.  Only their presence/columns
    # needed by init_contract_schema are required for this isolated regression.
    conn.executescript(
        """
        CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE products(code TEXT PRIMARY KEY);
        CREATE TABLE balances(id INTEGER PRIMARY KEY);
        CREATE TABLE orders(id INTEGER PRIMARY KEY);
        CREATE TABLE msmi_sync_state (
            invoice_type TEXT PRIMARY KEY,
            last_remote_id TEXT,
            last_invoice_date TEXT,
            last_synced_at TEXT,
            last_status TEXT,
            last_error TEXT
        );
        INSERT INTO msmi_sync_state(
            invoice_type,last_remote_id,last_invoice_date,last_synced_at,last_status,last_error
        ) VALUES(
            'INPUT_ELECTRONIC_INVOICE','MSMI-010','2026-08-10',
            '2026-09-01T00:00:00','ok',''
        );
        """
    )
    init_contract_schema(conn)
    return conn


class MsmiBackfillTests(unittest.TestCase):
    def test_http_client_translates_internal_zero_based_page_to_production_one_based_page(self):
        client = MsmiClient(MsmiConfig("https://example.invalid", "secret"))
        with patch.object(client, "_get", return_value={"listInvoice": []}) as mocked:
            result = client.list_invoices(page=0, size=199)
            self.assertEqual(result["page"], 0)
            self.assertEqual(mocked.call_args.args[1]["page"], 1)
            client.list_invoices(page=7, size=199)
            self.assertEqual(mocked.call_args.args[1]["page"], 8)

    def test_non_inventory_source_lines_sync_without_fabricating_quantity(self):
        conn = memory_database_with_legacy_sync_state()
        now = "2026-09-01T01:02:03"
        try:
            remote = remote_invoice(1)
            remote["hdhhdvu"].extend([
                {
                    "ma": "NOTE", "ten": "Dòng ghi chú", "sluong": 0,
                    "dgia": 0, "thtien": 0, "tchat": 1, "tsuat": 0,
                },
                {
                    "ma": "SERVICE", "ten": "Dịch vụ không theo số lượng",
                    "thtien": 2_000, "tchat": 3, "tsuat": "8%",
                },
            ])
            conn.execute("INSERT INTO products(code) VALUES('P-ONE')")
            conn.execute(
                """INSERT INTO item_mappings(
                       tenant,seller_tax_code,source_item_code,source_item_name,product_code,updated_at
                   ) VALUES('TDP','0200000001','SRC-001','Mat hang 1','P-ONE',?)""",
                (now,),
            )
            invoice_id, created = upsert_msmi_invoice(
                conn, remote, "INPUT_ELECTRONIC_INVOICE", "TDP", now
            )
            self.assertTrue(created)
            rows = conn.execute(
                """SELECT line_index,qty,unit_price,amount,inventory_eligible,
                          mapping_status,product_code,validation_note
                   FROM msmi_invoice_items WHERE invoice_id=? ORDER BY line_index""",
                (invoice_id,),
            ).fetchall()
            self.assertEqual([row["inventory_eligible"] for row in rows], [1, 0, 0])
            self.assertEqual([row["mapping_status"] for row in rows], ["mapped", "not_inventory", "not_inventory"])
            self.assertEqual(rows[1]["qty"], 0)
            self.assertEqual(rows[2]["qty"], 0)
            self.assertTrue(rows[1]["validation_note"])
            self.assertEqual(conn.execute(
                "SELECT receipt_status FROM msmi_invoices WHERE id=?", (invoice_id,)
            ).fetchone()["receipt_status"], "ready")

            only_service = deepcopy(remote)
            only_service["_id"] = "MSMI-SERVICE-ONLY"
            only_service["shdon"] = "SERVICE-ONLY"
            only_service["hdhhdvu"] = [remote["hdhhdvu"][2]]
            service_id, _ = upsert_msmi_invoice(
                conn, only_service, "INPUT_ELECTRONIC_INVOICE", "TDP", now
            )
            self.assertEqual(conn.execute(
                "SELECT receipt_status FROM msmi_invoices WHERE id=?", (service_id,)
            ).fetchone()["receipt_status"], "not_inventory")
        finally:
            conn.close()

    def test_legacy_state_migrates_as_incomplete(self):
        conn = memory_database_with_legacy_sync_state()
        try:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(msmi_sync_state)")}
            self.assertTrue({
                "backfill_anchor_id", "backfill_anchor_date", "backfill_complete",
            }.issubset(columns))
            state = conn.execute(
                "SELECT * FROM msmi_sync_state WHERE invoice_type='INPUT_ELECTRONIC_INVOICE'"
            ).fetchone()
            self.assertEqual(state["backfill_anchor_id"], None)
            self.assertEqual(state["backfill_complete"], 0)
        finally:
            conn.close()

    def test_unposted_resync_rebuilds_items_and_does_not_reuse_mapping_by_line(self):
        conn = memory_database_with_legacy_sync_state()
        now = "2026-09-01T01:02:03"
        try:
            remote = remote_invoice(1)
            remote["hdhhdvu"].append({
                "ma": "SECOND", "ten": "Mat hang thu hai", "dvtinh": "kg",
                "sluong": 2, "dgia": 5000, "thtien": 10000, "tsuat": "8%",
            })
            invoice_id, _ = upsert_msmi_invoice(
                conn, remote, "INPUT_ELECTRONIC_INVOICE", "TDP", now
            )
            first_item = conn.execute(
                "SELECT * FROM msmi_invoice_items WHERE invoice_id=? AND line_index=1", (invoice_id,)
            ).fetchone()
            conn.execute("INSERT INTO products(code) VALUES('P-OLD')")
            conn.execute(
                """INSERT INTO item_mappings(
                       tenant,seller_tax_code,source_item_code,source_item_name,product_code,updated_at
                   ) VALUES('TDP','0200000001',?,?, 'P-OLD',?)""",
                (first_item["source_item_code"], first_item["source_item_name"], now),
            )

            changed = deepcopy(remote_invoice(1))
            changed["hdhhdvu"][0]["ma"] = "DIFFERENT"
            changed["hdhhdvu"][0]["ten"] = "Mat hang khac"
            upsert_msmi_invoice(conn, changed, "INPUT_ELECTRONIC_INVOICE", "TDP", now)

            rows = conn.execute(
                "SELECT * FROM msmi_invoice_items WHERE invoice_id=? ORDER BY line_index", (invoice_id,)
            ).fetchall()
            self.assertEqual(len(rows), 1, "remote detail shrink must remove stale local lines")
            self.assertEqual(rows[0]["source_item_code"], "DIFFERENT")
            self.assertEqual(rows[0]["product_code"], "")
            self.assertEqual(rows[0]["mapping_status"], "unmapped")
        finally:
            conn.close()

    def test_posted_invoice_remote_change_is_frozen_for_manual_review(self):
        conn = memory_database_with_legacy_sync_state()
        now = "2026-09-01T01:02:03"
        try:
            original = remote_invoice(2)
            invoice_id, _ = upsert_msmi_invoice(
                conn, original, "INPUT_ELECTRONIC_INVOICE", "TDP", now
            )
            original_item = dict(conn.execute(
                "SELECT * FROM msmi_invoice_items WHERE invoice_id=?", (invoice_id,)
            ).fetchone())
            conn.execute(
                "UPDATE msmi_invoices SET receipt_status='posted' WHERE id=?", (invoice_id,)
            )
            changed = deepcopy(original)
            changed["hdhhdvu"][0]["sluong"] = 99
            changed["hdhhdvu"][0]["thtien"] = 990000
            upsert_msmi_invoice(conn, changed, "INPUT_ELECTRONIC_INVOICE", "TDP", now)

            invoice = conn.execute("SELECT * FROM msmi_invoices WHERE id=?", (invoice_id,)).fetchone()
            current_item = dict(conn.execute(
                "SELECT * FROM msmi_invoice_items WHERE invoice_id=?", (invoice_id,)
            ).fetchone())
            self.assertEqual(invoice["sync_status"], "review_required")
            self.assertEqual(invoice["receipt_status"], "posted")
            self.assertEqual(current_item["qty"], original_item["qty"])
            self.assertEqual(current_item["amount"], original_item["amount"])
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM audit_log WHERE event_type='msmi.remote_change_after_receipt'"
            ).fetchone()["n"], 1)
        finally:
            conn.close()

    def test_sync_page_failure_rolls_back_partial_invoices_but_records_error_state(self):
        conn = memory_database_with_legacy_sync_state()
        now_iso = lambda: "2026-09-01T01:02:03"
        client = FailingSecondPage([remote_invoice(4), remote_invoice(3), remote_invoice(2)])
        try:
            with self.assertRaisesRegex(RuntimeError, "simulated remote page failure"):
                sync_msmi(conn, client, now_iso, tenant="TDP", max_pages=3, page_size=2)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoices"
            ).fetchone()["n"], 0)
            state = conn.execute(
                "SELECT * FROM msmi_sync_state WHERE invoice_type='INPUT_ELECTRONIC_INVOICE'"
            ).fetchone()
            self.assertEqual(state["last_status"], "error")
            self.assertIn("simulated remote page failure", state["last_error"])
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM audit_log WHERE event_type='msmi.sync' AND status='error'"
            ).fetchone()["n"], 1)
        finally:
            conn.close()

    def test_bad_identifiable_invoice_is_quarantined_without_blocking_history(self):
        conn = memory_database_with_legacy_sync_state()
        now_iso = lambda: "2026-09-01T01:02:03"
        bad = remote_invoice(2)
        bad["tgtttbso"] = -1
        client = PagedMsmi([remote_invoice(3), bad, remote_invoice(1)])
        try:
            result = sync_msmi(
                conn, client, now_iso, tenant="TDP", max_pages=5, page_size=2
            )
            self.assertTrue(result["backfill_complete"])
            self.assertEqual(result["new_invoices"], 3)
            self.assertEqual(result["review_required"], 1)
            quarantined = conn.execute(
                "SELECT * FROM msmi_invoices WHERE remote_id='MSMI-002'"
            ).fetchone()
            self.assertEqual(quarantined["sync_status"], "review_required")
            self.assertEqual(quarantined["receipt_status"], "blocked")
            self.assertEqual(quarantined["total_amount"], 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoice_items WHERE invoice_id=?", (quarantined["id"],)
            ).fetchone()["n"], 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoices WHERE sync_status='synced'"
            ).fetchone()["n"], 2)

            repeat = sync_msmi(
                conn, client, now_iso, tenant="TDP", max_pages=2, page_size=2
            )
            self.assertEqual(repeat["new_invoices"], 0)
            self.assertGreaterEqual(repeat["review_required"], 1)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoices"
            ).fetchone()["n"], 3)
        finally:
            conn.close()

    def test_backfill_resumes_after_page_cap_without_skipping_shifted_pages(self):
        conn = memory_database_with_legacy_sync_state()
        now_iso = lambda: "2026-09-01T01:02:03"
        initial = [remote_invoice(number) for number in range(10, 0, -1)]
        client = PagedMsmi(initial)
        try:
            # Reproduce the database left by the old bug: only the first two
            # pages exist locally, while sync_state remembers merely the newest
            # invoice and therefore used to stop forever on the next run.
            for remote in initial[:4]:
                upsert_msmi_invoice(
                    conn, remote, "INPUT_ELECTRONIC_INVOICE", "TDP", now_iso()
                )

            first = sync_msmi(
                conn, client, now_iso, tenant="TDP", max_pages=2, page_size=2
            )
            self.assertEqual(first["new_invoices"], 0)
            self.assertEqual(first["known_invoices"], 4)
            self.assertFalse(first["backfill_complete"])
            self.assertTrue(first["more_history"])

            # A newly arriving invoice shifts every subsequent page.  Resuming
            # by saved page number would skip one record; the stable ID anchor
            # must be relocated instead.
            client.items.insert(0, remote_invoice(11))
            second = sync_msmi(
                conn, client, now_iso, tenant="TDP", max_pages=2, page_size=2
            )
            self.assertEqual(second["new_invoices"], 4)
            self.assertFalse(second["backfill_complete"])

            third = sync_msmi(
                conn, client, now_iso, tenant="TDP", max_pages=2, page_size=2
            )
            self.assertEqual(third["new_invoices"], 3)
            self.assertTrue(third["backfill_complete"])
            self.assertFalse(third["more_history"])

            remote_ids = [row["remote_id"] for row in conn.execute(
                "SELECT remote_id FROM msmi_invoices ORDER BY remote_id"
            )]
            self.assertEqual(remote_ids, [f"MSMI-{number:03d}" for number in range(1, 12)])
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoice_items"
            ).fetchone()["n"], 11)

            state = conn.execute(
                "SELECT * FROM msmi_sync_state WHERE invoice_type='INPUT_ELECTRONIC_INVOICE'"
            ).fetchone()
            self.assertEqual(state["last_remote_id"], "MSMI-011")
            self.assertEqual(state["backfill_anchor_id"], "MSMI-001")
            self.assertEqual(state["backfill_complete"], 1)

            # Once complete, a normal incremental run remains idempotent while
            # also spending the remaining page budget on rolling reconciliation
            # so a late/back-dated invoice cannot hide behind a known first page.
            fourth = sync_msmi(
                conn, client, now_iso, tenant="TDP", max_pages=2, page_size=2
            )
            self.assertEqual(fourth["new_invoices"], 0)
            self.assertEqual(fourth["known_invoices"], 4)
            self.assertEqual(fourth["pages"], 2)
            self.assertTrue(fourth["backfill_complete"])
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoices"
            ).fetchone()["n"], 11)

            # Audit metadata contains counts/status only; never remote invoice
            # bodies, IDs, credentials or tokens.
            metadata_rows = conn.execute(
                "SELECT metadata_json FROM audit_log WHERE event_type='msmi.sync'"
            ).fetchall()
            self.assertEqual(len(metadata_rows), 4)
            for row in metadata_rows:
                metadata = json.loads(row["metadata_json"])
                self.assertNotIn("remote_id", metadata)
                self.assertNotIn("token", json.dumps(metadata).lower())
                self.assertNotIn("MSMI-", row["metadata_json"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
