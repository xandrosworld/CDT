from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from flask import Flask

try:
    from .invoice_input_sync import sync_input_batch
    from .invoice_mapping import (
        apply_saved_mappings,
        register_invoice_mapping_routes,
        save_conversion,
        save_mapping,
        validated_output_stock_snapshot,
    )
    from .invoice_output_sync import sync_output_batch
    from .invoice_workbench import prepare_sync_batch
    from .test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from .test_invoice_output_sync import STATUS_MAP, output_invoice
    from .test_msmi_sync import remote_invoice
except ImportError:  # pragma: no cover - direct invocation
    from invoice_input_sync import sync_input_batch
    from invoice_mapping import (
        apply_saved_mappings,
        register_invoice_mapping_routes,
        save_conversion,
        save_mapping,
        validated_output_stock_snapshot,
    )
    from invoice_output_sync import sync_output_batch
    from invoice_workbench import prepare_sync_batch
    from test_invoice_input_sync import DateBoundedMsmi, init_test_database
    from test_invoice_output_sync import STATUS_MAP, output_invoice
    from test_msmi_sync import remote_invoice


NOW = "2026-09-02T15:20:00"


def now_iso() -> str:
    return NOW


class OutputFixtureMinvoice:
    """Read-only M-Invoice shape used only by mapping tests."""

    def __init__(self, items):
        self.items = list(items)

    def get_invoice_series(self):
        return [
            {"value": series, "invoiceYear": 2026}
            for series in sorted({str(item.get("khhdon") or "") for item in self.items})
            if series
        ]

    def get_outgoing_invoices(
        self,
        date_from,
        date_to,
        series,
        *,
        start=0,
        count=199,
        include_details=True,
    ):
        matching = [item for item in self.items if item.get("khhdon") == series]
        return {"data": matching[start:start + count], "total": len(matching)}


class InvoiceDirectionMappingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        init_test_database(self.conn)
        self.conn.executemany(
            "INSERT INTO products(code,name,unit) VALUES(?,?,?)",
            [
                ("P-IN", "Hàng đích đầu vào", "kg"),
                ("P-OUT", "Hàng đích đầu ra", "kg"),
                ("P-BOX", "Hàng theo thùng", "thùng"),
            ],
        )
        self.input_batch = prepare_sync_batch(
            self.conn,
            tenant="TDP",
            source="msmi",
            invoice_type="input",
            date_from="2026-08-01",
            date_to="2026-08-31",
            now_iso=now_iso,
        )[0]
        self.output_batch = prepare_sync_batch(
            self.conn,
            tenant="TDP",
            source="minvoice",
            invoice_type="output",
            date_from="2026-08-01",
            date_to="2026-08-31",
            now_iso=now_iso,
        )[0]
        self.input_remote = remote_invoice(1)
        self.output_remote = output_invoice(1)
        # Make the partner and source line identical: direction must still
        # isolate the two confirmations.
        self.output_remote["mstNmua"] = "0200000001"
        self.output_remote["hdhhdvu"][0].update(
            ma="SRC-001", ten="Mat hang 1", dvtinh="kg"
        )
        self.input_client = DateBoundedMsmi([self.input_remote])
        self.output_client = OutputFixtureMinvoice([self.output_remote])
        sync_input_batch(self.conn, self.input_client, self.input_batch["id"], now_iso)
        sync_output_batch(
            self.conn,
            self.output_client,
            self.output_batch["id"],
            now_iso,
            status_map=STATUS_MAP,
            status_fields=["fixtureStatus"],
        )

    def tearDown(self):
        self.conn.close()

    def test_combined_output_mapping_preserves_input_and_freezes_after_posting(self):
        self.conn.commit()
        @contextmanager
        def db():
            with self.conn:
                yield self.conn
        app = Flask(__name__)
        register_invoice_mapping_routes(app, {'db': db, 'now_iso': now_iso})
        item = self.conn.execute('SELECT * FROM outgoing_source_invoice_items').fetchone()
        before_input = dict(self.conn.execute('SELECT * FROM msmi_invoice_items').fetchone())
        path = f'/api/invoice-workbench/items/output/{item["id"]}/mapping'
        response = app.test_client().put(path, json={'product_code': 'P-BOX', 'conversion_factor': 0.5})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertFalse(response.json['requires_unit_conversion'])
        self.assertEqual(response.json['stock_qty'], item['qty'] * 0.5)
        self.assertEqual(dict(self.conn.execute('SELECT * FROM msmi_invoice_items').fetchone()), before_input)
        self.conn.execute("UPDATE outgoing_source_invoices SET stock_status='posted'")
        self.conn.commit()
        before = list(self.conn.iterdump())
        frozen = app.test_client().put(path, json={'product_code': 'P-OUT', 'conversion_factor': 2})
        self.assertEqual(frozen.status_code, 409)
        self.assertEqual(list(self.conn.iterdump()), before)

    def test_edit_keeps_period_and_conversion_and_rejects_stale_line(self):
        from .invoice_mapping import InvoiceMappingError
        item = self.conn.execute('SELECT id FROM msmi_invoice_items').fetchone()[0]
        save_mapping(self.conn, direction='input', item_id=item, product_code='P-BOX', now_iso=now_iso)
        save_conversion(self.conn, direction='input', item_id=item, conversion_factor=30,
                        effective_from='2026-08-01', effective_to='2026-08-31', now_iso=now_iso)
        keys = ('product_code', 'mapping_status', 'conversion_factor', 'source_unit', 'qty', 'amount')
        old = dict(self.conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?', (item,)).fetchone())
        expected = {k: old[k] for k in keys}
        result = save_mapping(self.conn, direction='input', item_id=item, product_code='P-BOX', expected=expected, now_iso=now_iso)
        self.assertFalse(result['requires_unit_conversion'])
        self.assertEqual(30, self.conn.execute('SELECT conversion_factor FROM msmi_invoice_items WHERE id=?',(item,)).fetchone()[0])
        save_conversion(self.conn, direction='input', item_id=item, conversion_factor=24, expected=expected, now_iso=now_iso)
        self.assertEqual(('2026-08-01','2026-08-31'), tuple(self.conn.execute('SELECT effective_from,effective_to FROM invoice_line_mappings').fetchone()))
        before = list(self.conn.iterdump())
        with self.assertRaises(InvoiceMappingError) as raised:
            save_mapping(self.conn, direction='input', item_id=item, product_code='P-IN', expected=expected, now_iso=now_iso)
        self.assertEqual('mapping_stale', raised.exception.code)
        self.assertEqual(before, list(self.conn.iterdump()))
        save_mapping(self.conn, direction='input', item_id=item, product_code='P-IN', now_iso=now_iso)
        self.assertEqual(('P-IN','2026-08-01','2026-08-31'), tuple(self.conn.execute('SELECT product_code,effective_from,effective_to FROM invoice_line_mappings').fetchone()))
        after = self.conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?',(item,)).fetchone()
        for key in ('qty','unit_price','amount','source_item_name','source_unit'):
            self.assertEqual(old[key], after[key])

    def test_input_confirmation_never_maps_output_and_both_survive_resync(self):
        input_item = self.conn.execute("SELECT id FROM msmi_invoice_items").fetchone()[0]
        output_item = self.conn.execute("SELECT id FROM outgoing_source_invoice_items").fetchone()[0]
        input_result = save_mapping(
            self.conn,
            direction="input",
            item_id=input_item,
            product_code="P-IN",
            now_iso=now_iso,
        )
        self.assertFalse(input_result["requires_unit_conversion"])
        self.assertEqual(("P-IN", "mapped"), tuple(self.conn.execute(
            "SELECT product_code,mapping_status FROM msmi_invoice_items"
        ).fetchone()))
        self.assertEqual(("", "unmapped"), tuple(self.conn.execute(
            "SELECT product_code,mapping_status FROM outgoing_source_invoice_items"
        ).fetchone()))
        self.assertEqual("ready", self.conn.execute(
            "SELECT receipt_status FROM msmi_invoices"
        ).fetchone()[0])
        self.assertEqual("pending_mapping", self.conn.execute(
            "SELECT stock_status FROM outgoing_source_invoices"
        ).fetchone()[0])

        output_result = save_mapping(
            self.conn,
            direction="output",
            item_id=output_item,
            product_code="P-OUT",
            now_iso=now_iso,
        )
        self.assertFalse(output_result["requires_unit_conversion"])
        self.assertEqual("ready", self.conn.execute(
            "SELECT stock_status FROM outgoing_source_invoices"
        ).fetchone()[0])
        self.assertEqual(
            {"INPUT_ELECTRONIC_INVOICE": "P-IN", "OUTPUT_ELECTRONIC_INVOICE": "P-OUT"},
            {row["invoice_type"]: row["product_code"] for row in self.conn.execute(
                "SELECT invoice_type,product_code FROM invoice_line_mappings"
            )},
        )

        sync_input_batch(self.conn, self.input_client, self.input_batch["id"], now_iso)
        sync_output_batch(
            self.conn,
            self.output_client,
            self.output_batch["id"],
            now_iso,
            status_map=STATUS_MAP,
            status_fields=["fixtureStatus"],
        )
        self.assertEqual(("P-IN", "mapped"), tuple(self.conn.execute(
            "SELECT product_code,mapping_status FROM msmi_invoice_items"
        ).fetchone()))
        self.assertEqual(("P-OUT", "mapped"), tuple(self.conn.execute(
            "SELECT product_code,mapping_status FROM outgoing_source_invoice_items"
        ).fetchone()))
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_line_mappings"
        ).fetchone()[0])

    def test_mapping_source_follows_real_output_source_while_input_remains_msmi(self):
        input_item = self.conn.execute("SELECT id FROM msmi_invoice_items").fetchone()[0]
        output = self.conn.execute(
            "SELECT id FROM outgoing_source_invoices"
        ).fetchone()
        output_id = int(output[0])
        output_item = self.conn.execute(
            "SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=?", (output_id,)
        ).fetchone()[0]
        self.conn.execute(
            "UPDATE outgoing_source_invoices SET source='minvoice' WHERE id=?", (output_id,)
        )

        save_mapping(
            self.conn,
            direction="input",
            item_id=input_item,
            product_code="P-IN",
            now_iso=now_iso,
        )
        save_mapping(
            self.conn,
            direction="output",
            item_id=output_item,
            product_code="P-OUT",
            now_iso=now_iso,
        )

        sources = {
            row["invoice_type"]: row["source"]
            for row in self.conn.execute(
                "SELECT invoice_type,source FROM invoice_line_mappings"
            )
        }
        self.assertEqual("msmi", sources["INPUT_ELECTRONIC_INVOICE"])
        self.assertEqual("minvoice", sources["OUTPUT_ELECTRONIC_INVOICE"])

        self.conn.execute(
            """UPDATE outgoing_source_invoice_items
               SET product_code='',mapping_status='unmapped',conversion_factor=NULL,
                   stock_qty=0,stock_unit_price=0 WHERE id=?""",
            (output_item,),
        )
        self.assertEqual(1, apply_saved_mappings(self.conn, "output", output_id))
        snapshot = validated_output_stock_snapshot(self.conn, output_item)
        self.assertEqual("P-OUT", snapshot["product_code"])

    def test_different_unit_is_highlighted_and_cannot_make_invoice_ready(self):
        input_item = self.conn.execute("SELECT id FROM msmi_invoice_items").fetchone()[0]
        result = save_mapping(
            self.conn,
            direction="input",
            item_id=input_item,
            product_code="P-BOX",
            now_iso=now_iso,
        )
        self.assertTrue(result["requires_unit_conversion"])
        self.assertEqual("unit_review", self.conn.execute(
            "SELECT mapping_status FROM msmi_invoice_items"
        ).fetchone()[0])
        self.assertEqual("pending_mapping", self.conn.execute(
            "SELECT receipt_status FROM msmi_invoices"
        ).fetchone()[0])
        mapping = self.conn.execute(
            "SELECT mapping_status,conversion_factor FROM invoice_line_mappings"
        ).fetchone()
        self.assertEqual("unit_review", mapping["mapping_status"])
        self.assertIsNone(mapping["conversion_factor"])
        batch = self.conn.execute(
            "SELECT unit_review_count,ready_count FROM invoice_sync_batches WHERE id=?",
            (self.input_batch["id"],),
        ).fetchone()
        self.assertEqual((1, 0), tuple(batch))

    def test_posted_or_reversal_invoice_mapping_is_frozen(self):
        output_item = self.conn.execute("SELECT id FROM outgoing_source_invoice_items").fetchone()[0]
        self.conn.execute("UPDATE outgoing_source_invoices SET stock_status='posted'")
        with self.assertRaisesRegex(Exception, "không được đổi ghép mã"):
            save_mapping(
                self.conn,
                direction="output",
                item_id=output_item,
                product_code="P-OUT",
                now_iso=now_iso,
            )
        self.assertEqual("unmapped", self.conn.execute(
            "SELECT mapping_status FROM outgoing_source_invoice_items"
        ).fetchone()[0])

    def test_conversion_reconciles_quantity_and_input_unit_cost_for_factor_above_and_below_one(self):
        input_item = self.conn.execute("SELECT id FROM msmi_invoice_items").fetchone()[0]
        save_mapping(
            self.conn, direction="input", item_id=input_item, product_code="P-BOX", now_iso=now_iso
        )
        converted = save_conversion(
            self.conn,
            direction="input",
            item_id=input_item,
            conversion_factor=30,
            now_iso=now_iso,
        )
        self.assertEqual(30, converted["stock_qty"])
        self.assertAlmostEqual(333.333333, converted["stock_unit_price"], places=6)
        self.assertEqual("ready", self.conn.execute(
            "SELECT receipt_status FROM msmi_invoices"
        ).fetchone()[0])

        output_item = self.conn.execute("SELECT id FROM outgoing_source_invoice_items").fetchone()[0]
        save_mapping(
            self.conn, direction="output", item_id=output_item, product_code="P-BOX", now_iso=now_iso
        )
        output_conversion = save_conversion(
            self.conn,
            direction="output",
            item_id=output_item,
            conversion_factor=0.5,
            now_iso=now_iso,
        )
        self.assertEqual(0.5, output_conversion["stock_qty"])
        self.assertEqual(20000, output_conversion["stock_unit_price"])
        self.assertEqual("ready", self.conn.execute(
            "SELECT stock_status FROM outgoing_source_invoices"
        ).fetchone()[0])
        self.assertEqual(2, self.conn.execute(
            "SELECT COUNT(*) FROM invoice_mapping_revisions"
        ).fetchone()[0])

    def test_promotion_quantity_uses_conversion_but_zero_price_stays_zero(self):
        promo = remote_invoice(2)
        promo["hdhhdvu"] = [{
            "ma": "PROMO-BOX",
            "ten": "Khuyến mại theo thùng",
            "dvtinh": "thùng",
            "sluong": 2,
            "dgia": 0,
            "thtien": 0,
            "tchat": 2,
            "tsuat": 0,
        }]
        second_batch = prepare_sync_batch(
            self.conn,
            tenant="TDP",
            source="msmi",
            invoice_type="input",
            date_from="2026-08-02",
            date_to="2026-08-02",
            now_iso=now_iso,
        )[0]
        sync_input_batch(
            self.conn, DateBoundedMsmi([promo]), second_batch["id"], now_iso
        )
        promo_item = self.conn.execute(
            "SELECT id FROM msmi_invoice_items WHERE source_item_code='PROMO-BOX'"
        ).fetchone()[0]
        save_mapping(
            self.conn, direction="input", item_id=promo_item, product_code="P-IN", now_iso=now_iso
        )
        result = save_conversion(
            self.conn,
            direction="input",
            item_id=promo_item,
            conversion_factor=30,
            now_iso=now_iso,
        )
        self.assertEqual(60, result["stock_qty"])
        self.assertEqual(0, result["stock_unit_price"])

    def test_effective_period_applies_only_to_invoices_inside_period_and_survives_resync(self):
        late = remote_invoice(31)
        late["_id"] = "MSMI-LATE-SAME-SCOPE"
        late["hdhhdvu"][0].update(ma="SRC-001", ten="Mat hang 1", dvtinh="kg")
        range_batch = prepare_sync_batch(
            self.conn,
            tenant="TDP",
            source="msmi",
            invoice_type="input",
            date_from="2026-08-01",
            date_to="2026-08-31",
            now_iso=now_iso,
        )[0]
        range_client = DateBoundedMsmi([late, self.input_remote])
        sync_input_batch(self.conn, range_client, range_batch["id"], now_iso)
        late_item = self.conn.execute(
            """SELECT li.id FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
               WHERE i.remote_id='MSMI-LATE-SAME-SCOPE'"""
        ).fetchone()[0]
        save_mapping(
            self.conn, direction="input", item_id=late_item, product_code="P-BOX", now_iso=now_iso
        )
        save_conversion(
            self.conn,
            direction="input",
            item_id=late_item,
            conversion_factor=2,
            effective_from="2026-08-15",
            effective_to="2026-08-31",
            now_iso=now_iso,
        )
        states = {
            row["invoice_date"]: (row["mapping_status"], row["stock_qty"])
            for row in self.conn.execute(
                """SELECT i.invoice_date,li.mapping_status,li.stock_qty
                   FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
                   WHERE li.source_item_code='SRC-001'"""
            )
        }
        self.assertEqual(("unmapped", 0), states["2026-08-01"])
        self.assertEqual(("mapped", 2), states["2026-08-31"])
        sync_input_batch(self.conn, range_client, range_batch["id"], now_iso)
        states_after = {
            row["invoice_date"]: (row["mapping_status"], row["stock_qty"])
            for row in self.conn.execute(
                """SELECT i.invoice_date,li.mapping_status,li.stock_qty
                   FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
                   WHERE li.source_item_code='SRC-001'"""
            )
        }
        self.assertEqual(states, states_after)
        late_item = self.conn.execute("SELECT li.id FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id WHERE i.remote_id='MSMI-LATE-SAME-SCOPE'").fetchone()[0]
        old_line = tuple(self.conn.execute('SELECT * FROM msmi_invoice_items WHERE id<>? ORDER BY id', (late_item,)).fetchone())
        save_conversion(self.conn, direction='input', item_id=late_item, conversion_factor=3, now_iso=now_iso)
        save_mapping(self.conn, direction='input', item_id=late_item, product_code='P-OUT', now_iso=now_iso)
        self.assertEqual(old_line, tuple(self.conn.execute('SELECT * FROM msmi_invoice_items WHERE id<>? ORDER BY id', (late_item,)).fetchone()))
        self.assertEqual(('2026-08-15','2026-08-31'), tuple(self.conn.execute('SELECT effective_from,effective_to FROM invoice_line_mappings').fetchone()))

    def test_invalid_factor_and_overlapping_mapping_conflict_do_not_change_line(self):
        input_item = self.conn.execute("SELECT id FROM msmi_invoice_items").fetchone()[0]
        save_mapping(
            self.conn, direction="input", item_id=input_item, product_code="P-BOX", now_iso=now_iso
        )
        for bad in (0, -1, float("inf"), "not-a-number"):
            with self.assertRaises(Exception):
                save_conversion(
                    self.conn,
                    direction="input",
                    item_id=input_item,
                    conversion_factor=bad,
                    now_iso=now_iso,
                )
        self.assertEqual("unit_review", self.conn.execute(
            "SELECT mapping_status FROM msmi_invoice_items WHERE id=?", (input_item,)
        ).fetchone()[0])

        base = self.conn.execute("SELECT * FROM invoice_line_mappings").fetchone()
        self.conn.execute(
            """INSERT INTO invoice_line_mappings(
                   tenant,source,invoice_type,partner_key,scope_key,source_item_code,
                   source_item_name,source_unit,product_code,target_unit,mapping_status,
                   conversion_factor,effective_from,effective_to,confirmed_at,updated_at
               ) VALUES(?,'msmi',?,?,?,?,?,?,?,?, 'confirmed',2,'2026-01-01','2026-12-31',?,?)""",
            (
                base["tenant"], base["invoice_type"], base["partner_key"], base["scope_key"],
                base["source_item_code"], base["source_item_name"], base["source_unit"],
                base["product_code"], base["target_unit"], NOW, NOW,
            ),
        )
        with self.assertRaisesRegex(Exception, "đúng một quy tắc"):
            save_conversion(
                self.conn,
                direction="input",
                item_id=input_item,
                conversion_factor=3,
                now_iso=now_iso,
            )

    def test_audit_is_count_only_and_has_no_partner_or_source_item_text(self):
        item_id = self.conn.execute("SELECT id FROM msmi_invoice_items").fetchone()[0]
        save_mapping(
            self.conn,
            direction="input",
            item_id=item_id,
            product_code="P-IN",
            now_iso=now_iso,
        )
        row = self.conn.execute(
            "SELECT entity_id,metadata_json FROM audit_log WHERE event_type='invoice_mapping.confirm'"
        ).fetchone()
        metadata = json.loads(row["metadata_json"])
        self.assertEqual("input", metadata["direction"])
        self.assertEqual("P-IN", metadata["product_code"])
        self.assertNotIn("0200000001", row["metadata_json"])
        self.assertNotIn("Mat hang 1", row["metadata_json"])


class InvoiceMappingRouteAndStaticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tdp071_route_")
        self.path = Path(self.temp.name) / "test.sqlite3"
        with self.db() as conn:
            init_test_database(conn)
            conn.execute("INSERT INTO products(code,name,unit) VALUES('P-API','API product','kg')")
            batch = prepare_sync_batch(
                conn,
                tenant="TDP",
                source="msmi",
                invoice_type="input",
                date_from="2026-08-01",
                date_to="2026-08-31",
                now_iso=now_iso,
            )[0]
            sync_input_batch(conn, DateBoundedMsmi([remote_invoice(1)]), batch["id"], now_iso)
            self.item_id = conn.execute("SELECT id FROM msmi_invoice_items").fetchone()[0]
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_invoice_mapping_routes(app, {"db": self.db, "now_iso": now_iso})
        self.client = app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def test_mapping_route_requires_real_product_and_returns_scope_result(self):
        missing = self.client.put(
            f"/api/invoice-workbench/items/input/{self.item_id}/mapping",
            json={"product_code": "DOES-NOT-EXIST"},
        )
        saved = self.client.put(
            f"/api/invoice-workbench/items/input/{self.item_id}/mapping",
            json={"product_code": "P-API"},
        )
        self.assertEqual(400, missing.status_code)
        self.assertEqual(200, saved.status_code, saved.get_data(as_text=True))
        self.assertEqual("confirmed", saved.get_json()["mapping_status"])

    def test_conversion_route_reconciles_and_returns_stock_snapshot(self):
        with self.db() as conn:
            conn.execute("UPDATE products SET unit='thùng' WHERE code='P-API'")
        mapped = self.client.put(
            f"/api/invoice-workbench/items/input/{self.item_id}/mapping",
            json={"product_code": "P-API"},
        )
        self.assertTrue(mapped.get_json()["requires_unit_conversion"])
        converted = self.client.put(
            f"/api/invoice-workbench/items/input/{self.item_id}/conversion",
            json={"conversion_factor": 30},
        )
        self.assertEqual(200, converted.status_code, converted.get_data(as_text=True))
        self.assertEqual(30, converted.get_json()["stock_qty"])

    def test_single_row_saves_code_and_conversion_without_grouping(self):
        with self.db() as conn:
            conn.execute("UPDATE products SET unit='thùng' WHERE code='P-API'")
            before = dict(conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?', (self.item_id,)).fetchone())
        response = self.client.put(
            f'/api/invoice-workbench/items/input/{self.item_id}/mapping',
            json={'product_code': 'P-API', 'conversion_factor': 0.5, 'expected': before},
        )
        self.assertEqual(response.status_code, 200, response.json)
        self.assertFalse(response.json['requires_unit_conversion'])
        with self.db() as conn:
            after = dict(conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?', (self.item_id,)).fetchone())
            self.assertEqual(after['mapping_status'], 'mapped')
            self.assertEqual(after['stock_qty'], before['qty'] * 0.5)
            self.assertAlmostEqual(after['stock_qty'] * after['stock_unit_price'], before['amount'])
            for key in ('qty', 'amount', 'unit_price', 'source_unit', 'source_item_name'):
                self.assertEqual(before[key], after[key])
        stale = self.client.put(
            f'/api/invoice-workbench/items/input/{self.item_id}/mapping',
            json={'product_code': 'P-API', 'conversion_factor': 2, 'expected': before},
        )
        self.assertEqual(stale.status_code, 409)

    def test_invalid_combined_conversion_rolls_back_mapping_and_audit(self):
        with self.db() as conn:
            before = list(conn.iterdump())
        for factor in (0, -1, 'invalid', None, 1000000001):
            with self.subTest(factor=factor):
                response = self.client.put(
                    f'/api/invoice-workbench/items/input/{self.item_id}/mapping',
                    json={'product_code': 'P-API', 'conversion_factor': factor},
                )
                self.assertEqual(response.status_code, 400, response.json)
                with self.db() as conn:
                    self.assertEqual(list(conn.iterdump()), before)

    def test_ui_has_keyboard_enter_two_directions_filters_and_color_states(self):
        from .test_invoice_workbench_listing import rendered_invoice_html
        static = Path(__file__).resolve().parent / "static"
        source = (static / "app.js").read_text(encoding="utf-8")
        source += rendered_invoice_html()
        css = (static / "real.css").read_text(encoding="utf-8")
        for expected in (
            "invoiceLineFilter",
            "Chưa ghép mã",
            "Cần quy đổi đơn vị",
            "save-invoice-mapping",
            'event.key !== "Enter"',
            'data-direction="input"',
            'data-direction="output"',
        ):
            self.assertTrue(expected in source, expected)
        for expected in (".invoice-row-issue", ".invoice-lines-scroll thead th", "overflow:auto"):
            self.assertIn(expected, css)


if __name__ == "__main__":
    unittest.main()
