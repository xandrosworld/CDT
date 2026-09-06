from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

try:
    from minvoice_client import (
        MinvoiceClient, MinvoiceConfig, MinvoiceError, MinvoiceOutcomeUnknown,
    )
except ImportError:  # pragma: no cover - package invocation
    from .minvoice_client import (
        MinvoiceClient, MinvoiceConfig, MinvoiceError, MinvoiceOutcomeUnknown,
    )


def valid_draft() -> dict:
    return {
        "invoice_date": "2026-08-31",
        "series": "1C26TDP",
        "currency": "VND",
        "payment_method": "TM/CK",
        "order_number": "TDP-BATCH-408",
        "key_api": "TDP-OUTGOING-408-UNI",
        "buyer": {
            "display_name": "Chị Thu",
            "legal_name": "CÔNG TY TNHH KHÁCH HÀNG",
            "tax_code": "0201234567",
            "address": "Hải Phòng, Việt Nam",
            "email": "ketoan@example.test",
        },
        "lines": [
            {
                "code": "A000001",
                "name": "Bắp cải",
                "unit": "Kg",
                "quantity": 2,
                "unit_price": 100_000,
                "tax": "8%",
            },
            {
                "code": "A000002",
                "name": "Cà rốt",
                "unit": "Kg",
                "quantity": 1,
                "unit_price": 50_000,
                "tax": "KCT",
            },
        ],
    }


def reconciled_promotion_data(remote_id: str) -> dict:
    return {
        "inv_invoiceAuth_Id": remote_id,
        "inv_invoiceSeries": "1C26TDP",
        "inv_invoiceIssuedDate": "2026-08-31",
        "inv_buyerTaxCode": "0201234567",
        "inv_TotalAmountWithoutVat": 0,
        "inv_vatAmount": 0,
        "inv_TotalAmount": 0,
        "details": [{"data": [{
            "inv_itemCode": "KM-01",
            "inv_quantity": 4,
            "inv_unitPrice": 0,
            "ma_thue": "10",
            "tchat": "2",
        }]}],
    }


class RecordingMinvoiceClient(MinvoiceClient):
    def __init__(self):
        super().__init__(MinvoiceConfig("https://example.invalid", "user", "password"))
        self.calls = []
        self.responses = {}

    def _json(self, method, path, payload=None, params=None, authenticated=False):
        self.calls.append({
            "method": method,
            "path": path,
            "payload": payload,
            "params": params,
            "authenticated": authenticated,
        })
        response = self.responses.get(path)
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise AssertionError(f"Unexpected HTTP call: {method} {path}")
        return response


class MinvoiceDraftTests(unittest.TestCase):
    def setUp(self):
        self.client = RecordingMinvoiceClient()

    def test_test_server_is_reported_and_cannot_receive_business_drafts(self):
        self.client.config = MinvoiceConfig('https://0106026495-999.minvoice.site', 'user', 'password')
        self.client._token = 'fixture'
        self.assertTrue(self.client.profile_status()['test_environment'])
        with self.assertRaisesRegex(MinvoiceError, 'kiểm thử'):
            self.client.create_draft(valid_draft(), dry_run=False, confirm_remote_write=True)
        self.assertEqual(self.client.calls, [])
        self.assertTrue(self.client.create_draft(valid_draft())['dry_run'])

    def test_outgoing_range_is_sent_to_minvoice_with_inclusive_page_contract(self):
        self.client.responses["InvoiceApi78/GetInvoices"] = {
            "ok": True,
            "code": "00",
            "data": [],
            "total": 0,
        }

        result = self.client.get_outgoing_invoices(
            "2026-08-01", "2026-08-31", "1C26TDP",
            start=199, count=199, include_details=True,
        )

        self.assertEqual(0, result["total"])
        call = self.client.calls[-1]
        self.assertEqual("POST", call["method"])
        self.assertEqual("InvoiceApi78/GetInvoices", call["path"])
        self.assertEqual({
            "tuNgay": "2026-08-01",
            "denngay": "2026-08-31",
            "khieu": "1C26TDP",
            "start": 199,
            "count": 199,
            "coChiTiet": True,
        }, call["payload"])
        self.assertTrue(call["authenticated"])

    def test_validate_and_build_vat_draft(self):
        summary = self.client.validate_draft(valid_draft())
        self.assertEqual(summary, {
            "valid": True,
            "remote_write": False,
            "series": "1C26TDP",
            "invoice_date": "2026-08-31",
            "key_api": "TDP-OUTGOING-408-UNI",
            "line_count": 2,
            "subtotal": 250_000,
            "tax_amount": 16_000,
            "total_amount": 266_000,
        })
        payload = self.client.build_draft_payload(valid_draft())
        self.assertEqual(payload["editmode"], 1)
        self.assertEqual(len(payload["data"]), 1)
        invoice = payload["data"][0]
        self.assertEqual(invoice["inv_invoiceSeries"], "1C26TDP")
        self.assertEqual(invoice["inv_TotalAmountWithoutVat"], 250_000)
        self.assertEqual(invoice["inv_vatAmount"], 16_000)
        self.assertEqual(invoice["inv_TotalAmount"], 266_000)
        self.assertEqual(invoice["key_api"], "TDP-OUTGOING-408-UNI")
        lines = invoice["details"][0]["data"]
        self.assertEqual(lines[0]["stt_rec0"], "0001")
        self.assertEqual(lines[0]["ma_thue"], "8")
        self.assertEqual(lines[0]["inv_vatAmount"], 16_000)
        self.assertEqual(lines[1]["ma_thue"], "-1")
        self.assertEqual(lines[1]["inv_vatAmount"], 0)

    def test_default_dry_run_never_calls_network(self):
        result = self.client.create_draft(valid_draft())
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["remote_write"])
        self.assertEqual(result["endpoint"], "/api/InvoiceApi78/Save")
        self.assertTrue(result["requires_user_sign_and_issue"])
        self.assertEqual(self.client.calls, [])

    def test_remote_write_requires_second_explicit_confirmation(self):
        with self.assertRaisesRegex(MinvoiceError, "Cần xác nhận rõ"):
            self.client.create_draft(valid_draft(), dry_run=False)
        self.assertEqual(self.client.calls, [])

    def test_confirmed_remote_write_checks_series_then_only_saves_unsigned_draft(self):
        self.client.config = MinvoiceConfig('https://0106026495-999.minvoice.site', 'user', 'password',
                                            allow_test_environment=True)
        self.client._token = 'fixture'
        self.assertTrue(self.client.profile_status()['test_environment'])
        self.assertTrue(self.client.profile_status()['draft_save_available'])
        self.client.responses = {
            "Invoice68/GetTypeInvoiceSeries": {
                "ok": True,
                "code": "00",
                "data": [{"value": "1C26TDP", "invoiceYear": 26}],
            },
            "InvoiceApi78/Save": {
                "ok": True,
                "code": "00",
                "message": "Thành công",
                "data": {"inv_invoiceAuth_Id": "mock-draft-id"},
            },
        }
        result = self.client.create_draft(
            valid_draft(), dry_run=False, confirm_remote_write=True
        )
        self.assertTrue(result["remote_write"])
        self.assertTrue(result["requires_user_sign_and_issue"])
        self.assertEqual(result["data"]["inv_invoiceAuth_Id"], "mock-draft-id")
        self.assertEqual(
            [(call["method"], call["path"]) for call in self.client.calls],
            [("GET", "Invoice68/GetTypeInvoiceSeries"), ("POST", "InvoiceApi78/Save")],
        )
        self.assertNotIn("InvoiceApi78/Sign", [call["path"] for call in self.client.calls])
        self.assertNotIn("InvoiceApi78/SaveSign", [call["path"] for call in self.client.calls])

    def test_read_only_lookup_by_key_api_found_and_not_found(self):
        self.client.responses["InvoiceApi78/GetInfoInvoice"] = {
            "ok": True, "code": "00",
            "data": {"inv_invoiceAuth_Id": "remote-id"},
        }
        found = self.client.get_invoice_info(key_api="TDP-OUTGOING-1")
        self.assertTrue(found["found"])
        self.assertTrue(found["read_only"])
        self.assertEqual(found["data"]["inv_invoiceAuth_Id"], "remote-id")
        self.assertEqual(self.client.calls[-1]["method"], "GET")
        self.assertEqual(self.client.calls[-1]["path"], "InvoiceApi78/GetInfoInvoice")
        self.assertEqual(self.client.calls[-1]["params"], {"keyApi": "TDP-OUTGOING-1"})

        self.client.responses["InvoiceApi78/GetInfoInvoice"] = {
            "ok": False, "code": "29404", "data": None,
        }
        missing = self.client.get_invoice_info(key_api="TDP-OUTGOING-2")
        self.assertFalse(missing["found"])
        self.assertIsNone(missing["data"])

    def test_save_transport_failure_has_unknown_outcome(self):
        self.client.responses = {
            "Invoice68/GetTypeInvoiceSeries": {
                "ok": True, "code": "00",
                "data": [{"value": "1C26TDP", "invoiceYear": 26}],
            },
            "InvoiceApi78/Save": MinvoiceError("transport detail must stay private"),
        }
        with self.assertRaises(MinvoiceOutcomeUnknown) as caught:
            self.client.create_draft(
                valid_draft(), dry_run=False, confirm_remote_write=True
            )
        self.assertIn("đối soát key_api", str(caught.exception))
        self.assertNotIn("transport detail", str(caught.exception))

        # Some urllib/SSL stacks surface a response-read timeout directly,
        # rather than wrapping it in URLError/MinvoiceError.  It is still an
        # ambiguous POST outcome and must enter the same reconciliation path.
        self.client.calls.clear()
        self.client.responses["InvoiceApi78/Save"] = TimeoutError("socket detail")
        with self.assertRaises(MinvoiceOutcomeUnknown) as timed_out:
            self.client.create_draft(
                valid_draft(), dry_run=False, confirm_remote_write=True
            )
        self.assertIn("đối soát key_api", str(timed_out.exception))
        self.assertNotIn("socket detail", str(timed_out.exception))

    def test_remote_write_rejects_unavailable_or_wrong_year_series(self):
        self.client.responses["Invoice68/GetTypeInvoiceSeries"] = {
            "ok": True,
            "code": "00",
            "data": [{"value": "1C25OLD", "invoiceYear": 25}],
        }
        with self.assertRaisesRegex(MinvoiceError, "không có trong tài khoản"):
            self.client.create_draft(
                valid_draft(), dry_run=False, confirm_remote_write=True
            )
        self.assertEqual(len(self.client.calls), 1)

        self.client.calls.clear()
        self.client.responses["Invoice68/GetTypeInvoiceSeries"] = {
            "ok": True,
            "code": "00",
            "data": [{"value": "1C26TDP", "invoiceYear": 25}],
        }
        with self.assertRaisesRegex(MinvoiceError, "không đúng năm"):
            self.client.create_draft(
                valid_draft(), dry_run=False, confirm_remote_write=True
            )
        self.assertEqual(len(self.client.calls), 1)

    def test_validation_rejects_missing_idempotency_key_and_bad_tax(self):
        draft = valid_draft()
        draft["key_api"] = ""
        with self.assertRaisesRegex(MinvoiceError, "key_api"):
            self.client.validate_draft(draft)

        draft = valid_draft()
        draft["lines"][0]["tax"] = "7%"
        with self.assertRaisesRegex(MinvoiceError, "Thuế suất"):
            self.client.validate_draft(draft)

        self.assertEqual(self.client._tax_code("10%"), "10")
        self.assertEqual(self.client._tax_code("0%"), "0")
        self.assertEqual(self.client._tax_code("KKKNT"), "-2")

    def test_validation_rejects_inconsistent_amounts(self):
        draft = valid_draft()
        draft["total_amount"] = 999
        with self.assertRaisesRegex(MinvoiceError, "không khớp chi tiết"):
            self.client.validate_draft(draft)

        draft = valid_draft()
        draft["lines"][0]["inv_vatAmount"] = 1
        with self.assertRaisesRegex(MinvoiceError, "Tiền thuế dòng 1"):
            self.client.validate_draft(draft)

    def test_individual_buyer_and_tax_decimal_alias(self):
        draft = valid_draft()
        draft["buyer"] = {
            "display_name": "Nguyễn Văn A",
            "address": "Hải Phòng",
        }
        draft["lines"] = [{
            "product_code": "HH01",
            "product_name": "Suất ăn",
            "unit": "Suất",
            "qty": "3",
            "unit_price": "100000",
            "tax_rate": 0.08,
        }]
        payload = self.client.build_draft_payload(draft)
        invoice = payload["data"][0]
        self.assertEqual(invoice["inv_buyerDisplayName"], "Nguyễn Văn A")
        self.assertEqual(invoice["inv_buyerLegalName"], "")
        self.assertEqual(invoice["details"][0]["data"][0]["ma_thue"], "8")
        self.assertEqual(invoice["inv_TotalAmount"], 324_000)

    def test_vnd_fractional_quantity_uses_whole_dong_rounding(self):
        draft = valid_draft()
        draft["lines"] = [{
            "code": "HH-LE",
            "name": "Hàng số lượng lẻ",
            "unit": "Kg",
            "quantity": "0.1",
            "unit_price": "6233",
            "tax": "10%",
        }]
        payload = self.client.build_draft_payload(draft)
        invoice = payload["data"][0]
        line = invoice["details"][0]["data"][0]
        self.assertEqual(line["inv_TotalAmountWithoutVat"], 623)
        self.assertEqual(line["inv_vatAmount"], 62)
        self.assertEqual(line["inv_TotalAmount"], 685)
        self.assertEqual(invoice["inv_TotalAmountWithoutVat"], 623)
        self.assertEqual(invoice["inv_vatAmount"], 62)
        self.assertEqual(invoice["inv_TotalAmount"], 685)

        # Lock the .5 boundary to financial half-up rounding, not Python's
        # built-in banker rounding.
        draft["lines"][0].update(quantity="0.5", unit_price="1", tax="0%")
        line = self.client.build_draft_payload(draft)["data"][0]["details"][0]["data"][0]
        self.assertEqual(line["inv_TotalAmountWithoutVat"], 1)
        self.assertEqual(line["inv_TotalAmount"], 1)

    def test_explicit_promotion_nature_does_not_depend_on_item_name(self):
        draft = valid_draft()
        draft["lines"] = [{
            "code": "KM-01",
            "name": "Nước tăng lực",
            "unit": "Chai",
            "quantity": 4,
            "unit_price": 0,
            "tax": "10%",
            "tchat": 2,
        }]
        invoice = self.client.build_draft_payload(draft)["data"][0]
        line = invoice["details"][0]["data"][0]
        self.assertEqual(line["tchat"], 2)
        self.assertTrue(line["inv_promotion"])
        self.assertEqual(line["inv_TotalAmountWithoutVat"], 0)
        self.assertEqual(line["inv_vatAmount"], 0)
        self.assertEqual(line["inv_TotalAmount"], 0)
        self.assertEqual(invoice["inv_TotalAmount"], 0)

    def test_route_carries_explicit_invoice_nature_to_minvoice_tchat(self):
        from flask import Flask
        try:
            import server
            from contract_modules import init_contract_schema, register_contract_routes
        except ImportError:  # pragma: no cover - package invocation
            from . import server
            from .contract_modules import init_contract_schema, register_contract_routes

        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "route.sqlite3"

            @contextmanager
            def db_factory():
                connection = sqlite3.connect(database)
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                try:
                    yield connection
                    connection.commit()
                finally:
                    connection.close()

            with db_factory() as connection:
                connection.executescript(server.SCHEMA)
                init_contract_schema(connection)
                server.init_invoice_workbench_schema(connection)
                connection.execute(
                    """INSERT INTO outgoing_invoice_drafts(
                           batch_id,contractor,invoice_date,status,subtotal,tax_amount,
                           total_amount,created_at
                       ) VALUES(1,'UNI','2026-08-31','draft',0,0,0,'2026-08-31 00:00:00')"""
                )
                draft_id = connection.execute(
                    "SELECT id FROM outgoing_invoice_drafts"
                ).fetchone()["id"]
                connection.execute(
                    """INSERT INTO outgoing_buyer_profiles(
                           contractor,display_name,legal_name,tax_code,address,email,updated_at
                       ) VALUES('UNI','','CONG TY KHACH','0201234567','Hai Phong','',
                                '2026-08-31 00:00:00')"""
                )
                connection.executemany(
                    "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                    [
                        ("company", "CONG TY TDP"),
                        ("company_tax_code", "0202265016"),
                        ("company_address", "Hai Phong"),
                        ("payment_requester", "CONG TY TDP"),
                        ("payment_bank_name", "NGAN HANG TEST"),
                        ("payment_bank_account", "123456789"),
                    ],
                )
                connection.execute(
                    """INSERT INTO outgoing_invoice_lines(
                           draft_id,order_id,product_code,product_name,qty,unit,unit_price,
                           tax,invoice_nature,amount
                       ) VALUES(?,1,'KM-01','Nuoc tang luc',4,'Chai',0,'10','2',0)""",
                    (draft_id,),
                )
                connection.execute("INSERT INTO products(code,name,unit) VALUES('KM-01','Nuoc tang luc','Chai')")
                for source_type, qty_in, qty_out, source_id, status in (
                    ("OPENING", 4, 0, "PROMO-OPENING", "posted"),
                    ("OUTGOING_DRAFT", 0, 4, str(draft_id), "reserved"),
                ):
                    connection.execute(
                        """INSERT INTO inventory_transactions(
                           txn_date,product_code,qty_in,qty_out,unit_cost,source_type,
                           source_id,source_line,status,created_at,updated_at
                           ) VALUES('2026-08-01','KM-01',?,?,0,?,?,'1',?,
                                    '2026-08-01','2026-08-01')""",
                        (qty_in, qty_out, source_type, source_id, status),
                    )

            app = Flask("minvoice-route-test")
            register_contract_routes(app, {
                "db": db_factory,
                "now_iso": lambda: "2026-08-31 00:00:00",
                "clean_text": server.clean_text,
                "number_value": server.number_value,
                "tax_factor": server.tax_factor,
                "setting_get": server.setting_get,
                "setting_set": server.setting_set,
                "create_minvoice_client": lambda: self.client,
                "root": Path(temp_dir),
                "data_dir": Path(temp_dir),
                "require_batch": lambda *_: None,
                "export_supplier_orders": lambda *_: None,
                "export_deliveries": lambda *_: None,
                "export_purchase_documents": lambda *_: None,
                "export_report": lambda *_: None,
            })
            route_client = app.test_client()
            response = route_client.post(
                f"/api/minvoice/drafts/{draft_id}", json={"series": "1C26TDP"}
            )
            self.assertEqual(response.status_code, 200)
            line = response.get_json()["payload"]["data"][0]["details"][0]["data"][0]
            self.assertEqual(line["tchat"], 2)
            self.assertTrue(line["inv_promotion"])
            self.assertEqual(self.client.calls, [])

            unconfirmed = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26TDP", "dry_run": False},
            )
            self.assertEqual(unconfirmed.status_code, 400)
            self.assertEqual(self.client.calls, [])

            with db_factory() as connection:
                connection.execute(
                    """UPDATE outgoing_invoice_drafts
                       SET minvoice_status='saving',minvoice_series='1C26TDP',
                           minvoice_key_api='TDP-OUTGOING-1',
                           minvoice_started_at='2026-08-31 00:00:00'
                       WHERE id=?""",
                    (draft_id,),
                )
            concurrent = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26TDP", "dry_run": False,
                      "confirm_remote_write": True},
            )
            self.assertEqual(concurrent.status_code, 409)
            self.assertEqual(concurrent.get_json()["minvoice_status"], "saving")
            self.assertEqual(self.client.calls, [])

            with db_factory() as connection:
                connection.execute(
                    "UPDATE outgoing_invoice_drafts SET minvoice_status='unknown' WHERE id=?",
                    (draft_id,),
                )
            mismatched_series = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26ALT", "dry_run": False,
                      "confirm_remote_write": True},
            )
            self.assertEqual(mismatched_series.status_code, 409)
            self.assertIn("không được đổi ký hiệu", mismatched_series.get_json()["error"].lower())
            self.assertEqual(self.client.calls, [])

            self.client.responses = {
                "InvoiceApi78/GetInfoInvoice": {
                    "ok": True, "code": "00",
                    "data": reconciled_promotion_data("recovered-id"),
                },
            }
            recovered = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26TDP", "dry_run": False,
                      "confirm_remote_write": True},
            )
            self.assertEqual(recovered.status_code, 200)
            self.assertTrue(recovered.get_json()["reconciled"])
            self.assertEqual(recovered.get_json()["remote_id"], "recovered-id")
            self.assertEqual(
                [(call["method"], call["path"]) for call in self.client.calls],
                [("GET", "InvoiceApi78/GetInfoInvoice")],
            )
            with db_factory() as connection:
                saved = connection.execute(
                    "SELECT minvoice_status,minvoice_remote_id FROM outgoing_invoice_drafts WHERE id=?",
                    (draft_id,),
                ).fetchone()
                self.assertEqual(saved["minvoice_status"], "saved")
                self.assertEqual(saved["minvoice_remote_id"], "recovered-id")

            self.client.calls.clear()
            self.client.responses = {
                "InvoiceApi78/GetInfoInvoice": {
                    "ok": False, "code": "29404", "data": None,
                },
            }
            with db_factory() as connection:
                connection.execute(
                    """UPDATE outgoing_invoice_drafts
                       SET minvoice_status='unknown',minvoice_remote_id=NULL WHERE id=?""",
                    (draft_id,),
                )
            not_found = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26TDP", "dry_run": False,
                      "confirm_remote_write": True},
            )
            self.assertEqual(not_found.status_code, 409)
            self.assertTrue(not_found.get_json()["retry_requires_new_confirmation"])
            self.assertEqual(
                [(call["method"], call["path"]) for call in self.client.calls],
                [("GET", "InvoiceApi78/GetInfoInvoice")],
            )
            with db_factory() as connection:
                status = connection.execute(
                    "SELECT minvoice_status FROM outgoing_invoice_drafts WHERE id=?",
                    (draft_id,),
                ).fetchone()["minvoice_status"]
                self.assertEqual(status, "not_sent")

            # Only a separate, newly confirmed request may POST after a clean
            # not-found reconciliation.
            self.client.calls.clear()
            self.client.responses = {
                "InvoiceApi78/GetInfoInvoice": {
                    "ok": False, "code": "29404", "data": None,
                },
                "Invoice68/GetTypeInvoiceSeries": {
                    "ok": True, "code": "00",
                    "data": [{"value": "1C26TDP", "invoiceYear": 26}],
                },
                "InvoiceApi78/Save": {
                    "ok": True, "code": "00",
                    "data": {"inv_invoiceAuth_Id": "new-id"},
                },
            }
            saved_response = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26TDP", "dry_run": False,
                      "confirm_remote_write": True},
            )
            self.assertEqual(saved_response.status_code, 200)
            self.assertEqual(saved_response.get_json()["remote_id"], "new-id")
            self.assertNotIn("data", saved_response.get_json())
            self.assertEqual(
                [(call["method"], call["path"]) for call in self.client.calls],
                [
                    ("GET", "InvoiceApi78/GetInfoInvoice"),
                    ("GET", "Invoice68/GetTypeInvoiceSeries"),
                    ("POST", "InvoiceApi78/Save"),
                ],
            )

            with db_factory() as connection:
                connection.execute(
                    """UPDATE outgoing_invoice_drafts
                       SET minvoice_status='not_sent',minvoice_remote_id=NULL WHERE id=?""",
                    (draft_id,),
                )
            self.client.calls.clear()
            self.client.responses = {
                "InvoiceApi78/GetInfoInvoice": {
                    "ok": False, "code": "29404", "data": None,
                },
                "Invoice68/GetTypeInvoiceSeries": {
                    "ok": True, "code": "00",
                    "data": [{"value": "1C26TDP", "invoiceYear": 26}],
                },
                "InvoiceApi78/Save": MinvoiceError("simulated lost response"),
            }
            unknown = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26TDP", "dry_run": False,
                      "confirm_remote_write": True},
            )
            self.assertEqual(unknown.status_code, 409)
            self.assertTrue(unknown.get_json()["reconcile_required"])
            with db_factory() as connection:
                status = connection.execute(
                    "SELECT minvoice_status FROM outgoing_invoice_drafts WHERE id=?",
                    (draft_id,),
                ).fetchone()["minvoice_status"]
                self.assertEqual(status, "unknown")

            self.client.calls.clear()
            self.client.responses = {
                "InvoiceApi78/GetInfoInvoice": {
                    "ok": True, "code": "00",
                    "data": reconciled_promotion_data("recovered-after-timeout"),
                },
            }
            reconciled = route_client.post(
                f"/api/minvoice/drafts/{draft_id}",
                json={"series": "1C26TDP", "dry_run": False,
                      "confirm_remote_write": True},
            )
            self.assertEqual(reconciled.status_code, 200)
            self.assertEqual(reconciled.get_json()["remote_id"], "recovered-after-timeout")
            self.assertEqual(
                [(call["method"], call["path"]) for call in self.client.calls],
                [("GET", "InvoiceApi78/GetInfoInvoice")],
            )

    def test_api_failure_is_sanitized(self):
        self.client.responses = {
            "Invoice68/GetTypeInvoiceSeries": {
                "ok": True,
                "code": "00",
                "data": [{"value": "1C26TDP", "invoiceYear": 26}],
            },
            "InvoiceApi78/Save": {"ok": False, "code": "99", "message": "remote detail"},
        }
        with self.assertRaisesRegex(MinvoiceError, "không lưu được") as caught:
            self.client.create_draft(
                valid_draft(), dry_run=False, confirm_remote_write=True
            )
        self.assertNotIn("remote detail", str(caught.exception))

    def test_input_is_not_mutated(self):
        draft = valid_draft()
        before = copy.deepcopy(draft)
        self.client.build_draft_payload(draft)
        self.assertEqual(draft, before)


if __name__ == "__main__":
    unittest.main()
