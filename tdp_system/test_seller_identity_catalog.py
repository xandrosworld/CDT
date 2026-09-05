import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from .seller_identity_catalog import CATALOG_FILENAME, HEADERS, VERSION_KEY, read_catalog, sync_catalog
from .receipt_export import ReceiptExportError, enrich_receipt_identity_rows, build_purchase_documents_workbook
from .test_receipt_export import receipt_row, GOLDEN


SEED = Path(__file__).parent / "templates" / CATALOG_FILENAME


class SellerIdentityCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executescript("""
            CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE people(name TEXT PRIMARY KEY,cccd TEXT,issue_date TEXT,issue_place TEXT,address TEXT);
            CREATE TABLE orders(id INTEGER PRIMARY KEY,cccd TEXT,amount REAL);
            INSERT INTO orders VALUES(1,'historical',123);
        """)

    def source(self, rows):
        path = Path(self.temp.name) / "source.xlsx"
        book = Workbook()
        book.active.title = "CCCD"
        book.active.append(HEADERS)
        for row in rows:
            book.active.append(row)
        book.save(path)
        book.close()
        return path

    def test_source_counts_addresses_and_text_identities(self):
        records = read_catalog(SEED)
        self.assertEqual(len(records), 52)
        self.assertEqual(sum("Hải Phòng" in row[4] for row in records), 29)
        self.assertEqual(sum("Thái Bình" in row[4] for row in records), 23)
        self.assertTrue(any(row[1].startswith("0") for row in records))
        # Customer source contains one ID used by two different named people.
        self.assertEqual(sorted(Counter(r[1] for r in records).values()).count(2), 1)

    def test_correction_all_fields_once_preserves_orders_and_later_edits(self):
        records = read_catalog(SEED)
        for name, *_ in records:
            self.conn.execute("INSERT INTO people VALUES(?,?,?,?,?)", (name, "old", "old", "old", "Hải Phòng"))
        self.assertEqual(sync_catalog(self.conn, SEED), 52)
        actual = [tuple(r) for r in self.conn.execute("SELECT name,cccd,issue_date,issue_place,address FROM people")]
        self.assertEqual(sorted(actual), sorted(records))
        self.assertEqual(tuple(self.conn.execute("SELECT * FROM orders").fetchone()), (1, "historical", 123))
        name = records[0][0]
        self.conn.execute("UPDATE people SET address='Customer correction' WHERE name=?", (name,))
        self.assertEqual(sync_catalog(self.conn, SEED), 0)
        self.assertEqual(self.conn.execute("SELECT address FROM people WHERE name=?", (name,)).fetchone()[0], "Customer correction")

    def test_bad_source_does_not_partially_write_or_expose_identity(self):
        valid = [1, "Người A", "Địa chỉ A", "012345678901", "2/1/2020", "Nơi cấp A"]
        for column, value in [(2, ""), (3, 123456789), (4, "31/2/2020"), (5, ""), (1, "=1+1")]:
            with self.subTest(column=column):
                broken = [2, "Người B", "Địa chỉ B", "123456789012", "1/1/2020", "Nơi cấp B"]
                broken[column] = value
                with self.assertRaises(ValueError) as caught:
                    sync_catalog(self.conn, self.source([valid, broken]))
                self.assertNotIn(valid[3], str(caught.exception))
                self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0], 0)
                self.assertIsNone(self.conn.execute("SELECT value FROM settings WHERE key=?", (VERSION_KEY,)).fetchone())

    def test_duplicate_names_in_source_and_existing_catalog_are_rejected(self):
        row = [1, "Người A", "Địa chỉ A", "012345678901", "2/1/2020", "Nơi cấp A"]
        with self.assertRaises(ValueError):
            sync_catalog(self.conn, self.source([row, [2, " người a ", *row[2:]]]))
        for name in ("Người A", "người a"):
            self.conn.execute("INSERT INTO people(name,address) VALUES(?,?)", (name, "keep"))
        with self.assertRaises(ValueError):
            sync_catalog(self.conn, self.source([row]))
        self.assertEqual([r[0] for r in self.conn.execute("SELECT address FROM people")], ["keep", "keep"])

    def test_new_source_revision_updates_all_fields_without_duplicating_person(self):
        row = [1, "Người A", "Địa chỉ A", "012345678901", "2/1/2020", "Nơi cấp A"]
        self.assertEqual(sync_catalog(self.conn, self.source([row])), 1)
        row[2:] = ["Địa chỉ B", "012345678902", "3/2/2021", "Nơi cấp B"]
        self.assertEqual(sync_catalog(self.conn, self.source([row])), 1)
        self.assertEqual(tuple(self.conn.execute("SELECT * FROM people").fetchone()), ("Người A", row[3], "03/02/2021", row[5], row[2]))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM people").fetchone()[0], 1)

    def test_all_source_receipts_use_same_person_fields_and_block_two_conflicts(self):
        sync_catalog(self.conn, SEED)
        counts = Counter(row[1] for row in read_catalog(SEED))
        exported = blocked = 0
        for name, identity, issued, place, address in read_catalog(SEED):
            rows = [receipt_row(seller=name, cccd=identity, address="Stale address")]
            if counts[identity] > 1:
                with self.assertRaises(ReceiptExportError) as caught:
                    enrich_receipt_identity_rows(self.conn, rows)
                self.assertNotIn(identity, str(caught.exception))
                blocked += 1
                continue
            enriched = enrich_receipt_identity_rows(self.conn, rows)
            self.assertEqual((enriched[0]["address"], enriched[0]["issue_date"], enriched[0]["issue_place"]), (address, issued, place))
            book = build_purchase_documents_workbook(enriched, template_path=GOLDEN)
            try:
                sheet = book["biên nhận"]
                self.assertEqual(sheet["D9"].value, address)
                self.assertEqual(sheet["D10"].value, identity)
                self.assertEqual(sheet["D11"].value, issued)
                self.assertEqual(sheet["D12"].value, place)
            finally:
                book.close()
            exported += 1
        self.assertEqual((exported, blocked), (50, 2))

    def test_missing_or_unknown_person_cannot_use_stale_order_address(self):
        sync_catalog(self.conn, SEED)
        name, identity, *_ = read_catalog(SEED)[0]
        self.conn.execute("UPDATE people SET address='' WHERE name=?", (name,))
        for seller in (name, "Unknown seller"):
            with self.assertRaises(ReceiptExportError):
                enrich_receipt_identity_rows(self.conn, [receipt_row(seller=seller, cccd=identity)])

    def test_startup_with_old_master_version_and_force_refresh_never_revert(self):
        from . import server
        target = Path(self.temp.name) / "integration.sqlite3"
        with patch.object(server, "DB_PATH", target):
            with server.db() as conn:
                conn.executescript(server.SCHEMA)
                conn.execute("INSERT INTO settings VALUES('master_version',?)", (f"{server.MASTER_FORMAT_VERSION}-{int(server.MASTER_SOURCE.stat().st_mtime)}",))
            server.sync_master_if_needed()
            server.sync_master_if_needed(force=True)
            with server.db() as conn:
                for name, identity, issued, place, address in read_catalog(SEED):
                    self.assertEqual(tuple(conn.execute("SELECT name,cccd,issue_date,issue_place,address FROM people WHERE name=?", (name,)).fetchone()), (name, identity, issued, place, address))


if __name__ == "__main__":
    unittest.main()
