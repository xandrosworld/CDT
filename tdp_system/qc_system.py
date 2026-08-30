from __future__ import annotations

import io
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from shutil import rmtree

from openpyxl import Workbook, load_workbook

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))
import server  # noqa: E402
import contract_modules  # noqa: E402


def clean_test_db(path: Path):
    for suffix in ("", "-wal", "-shm"):
        target = Path(str(path) + suffix)
        if target.exists():
            target.unlink()


def mapping_workbook_bytes(headers, rows, header_row=3, sheet_name="Mapping"):
    workbook = Workbook()
    notes = workbook.active
    notes.title = "Hướng dẫn"
    notes["A1"] = "Sheet này không phải dữ liệu"
    sheet = workbook.create_sheet(sheet_name)
    sheet.cell(header_row - 1, 1, "Danh sách khách xác nhận")
    for column, header in enumerate(headers, start=1):
        sheet.cell(header_row, column, header)
    for row_index, values in enumerate(rows, start=header_row + 1):
        for column, value in enumerate(values, start=1):
            sheet.cell(row_index, column, value)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def preview_mapping(client, mapping_type, payload, filename="mapping.xlsx"):
    return client.post(
        "/api/mappings/import/preview",
        data={"mapping_type": mapping_type, "file": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def main():
    qc_db = APP_DIR / "data" / "qc_test.sqlite3"
    clean_test_db(qc_db)
    server.DB_PATH = qc_db
    server.init_database()
    client = server.app.test_client()

    health = client.get("/health")
    assert health.status_code == 200 and health.get_json()["ok"]
    bootstrap = client.get("/api/bootstrap").get_json()
    assert bootstrap["master"]["product_count"] >= 800
    assert len(bootstrap["master"]["kitchens"]) >= 20

    with server.db() as conn:
        mapping_products = [dict(row) for row in conn.execute(
            """SELECT code,name FROM products
               WHERE code!='I000060' AND name IN (
                   SELECT name FROM products WHERE trim(name)!='' GROUP BY name HAVING COUNT(*)=1
               ) ORDER BY code LIMIT 4"""
        )]
        mapping_kitchens = [dict(row) for row in conn.execute(
            """SELECT code,name FROM kitchens
               WHERE code!='POT' AND trim(COALESCE(name,''))!='' AND name IN (
                   SELECT name FROM kitchens WHERE trim(COALESCE(name,''))!='' GROUP BY name HAVING COUNT(*)=1
               ) ORDER BY code LIMIT 2"""
        )]
    assert len(mapping_products) == 4 and len(mapping_kitchens) == 2

    invoice_mapping_file = mapping_workbook_bytes(
        ["Mã hàng", "Tên Thành Đạt Phát", "Tên xuất hóa đơn"],
        [
            [mapping_products[0]["code"], "", "TÊN HÓA ĐƠN QC 01"],
            ["", mapping_products[1]["name"], "Tên hóa đơn QC 02"],
            [mapping_products[0]["code"], "", "TÊN HÓA ĐƠN QC 01"],
        ],
        header_row=3,
        sheet_name="Tên đầu ra",
    )
    mapping_preview = preview_mapping(client, "invoice_names", invoice_mapping_file)
    assert mapping_preview.status_code == 200, mapping_preview.get_data(as_text=True)
    mapping_preview_data = mapping_preview.get_json()
    assert mapping_preview_data["sheet"] == "Tên đầu ra"
    assert mapping_preview_data["header_row"] == 3
    assert mapping_preview_data["can_confirm"] is True
    assert mapping_preview_data["counts"] == {
        "total": 3, "new": 2, "update": 0, "unchanged": 0, "duplicate": 1, "error": 0,
    }
    no_confirmation = client.post(
        "/api/mappings/import/confirm", json={"token": mapping_preview_data["token"]}
    )
    assert no_confirmation.status_code == 400
    mapping_confirm = client.post(
        "/api/mappings/import/confirm",
        json={"token": mapping_preview_data["token"], "confirmed": True},
    )
    assert mapping_confirm.status_code == 200, mapping_confirm.get_data(as_text=True)
    assert mapping_confirm.get_json()["inserted"] == 2
    assert mapping_confirm.get_json()["processed"] == 2
    assert client.post(
        "/api/mappings/import/confirm",
        json={"token": mapping_preview_data["token"], "confirmed": True},
    ).status_code == 410

    mapping_repeat = preview_mapping(client, "invoice_names", invoice_mapping_file).get_json()
    assert mapping_repeat["counts"]["unchanged"] == 2 and mapping_repeat["counts"]["duplicate"] == 1
    mapping_repeat_confirm = client.post(
        "/api/mappings/import/confirm", json={"token": mapping_repeat["token"], "confirmed": True}
    )
    assert mapping_repeat_confirm.status_code == 200
    assert mapping_repeat_confirm.get_json()["unchanged"] == 2

    update_mapping_file = mapping_workbook_bytes(
        ["Mã HH", "Tên XHĐ"],
        [[mapping_products[0]["code"], "TÊN HÓA ĐƠN QC 01 - ĐÃ SỬA"]],
    )
    update_preview = preview_mapping(client, "invoice_names", update_mapping_file).get_json()
    assert update_preview["can_confirm"] is True and update_preview["counts"]["update"] == 1
    update_confirm = client.post(
        "/api/mappings/import/confirm", json={"token": update_preview["token"], "confirmed": True}
    )
    assert update_confirm.status_code == 200 and update_confirm.get_json()["updated"] == 1

    invalid_mapping_file = mapping_workbook_bytes(
        ["Mã SP", "Tên xuất hóa đơn"],
        [
            [mapping_products[2]["code"], "DÒNG HỢP LỆ KHÔNG ĐƯỢC GHI DỞ"],
            ["MA-KHONG-TON-TAI", "DÒNG LỖI"],
        ],
    )
    invalid_preview_response = preview_mapping(client, "invoice_names", invalid_mapping_file)
    assert invalid_preview_response.status_code == 200
    invalid_preview = invalid_preview_response.get_json()
    assert invalid_preview["can_confirm"] is False and invalid_preview["counts"]["error"] == 1
    assert client.post(
        "/api/mappings/import/confirm",
        json={"token": invalid_preview["token"], "confirmed": True},
    ).status_code == 400
    with server.db() as conn:
        assert not conn.execute(
            "SELECT 1 FROM outgoing_product_names WHERE product_code=?", (mapping_products[2]["code"],)
        ).fetchone(), "Không được ghi một phần khi file còn lỗi"

    conflict_mapping_file = mapping_workbook_bytes(
        ["Mã vật tư", "Invoice name"],
        [
            [mapping_products[2]["code"], "TÊN A"],
            [mapping_products[2]["code"], "TÊN B"],
        ],
    )
    conflict_preview = preview_mapping(client, "invoice_names", conflict_mapping_file).get_json()
    assert conflict_preview["can_confirm"] is False and conflict_preview["counts"]["error"] == 2

    kitchen_mapping_file = mapping_workbook_bytes(
        ["Tên bếp", "Mã bếp", "Unit"],
        [
            [mapping_kitchens[0]["name"], "", "UNIT-QC-01"],
            ["", mapping_kitchens[1]["code"], "unit-qc-02"],
            [mapping_kitchens[0]["name"], "", "UNIT-QC-01"],
        ],
        sheet_name="Bếp - Unit",
    )
    kitchen_preview_response = preview_mapping(client, "kitchen_units", kitchen_mapping_file)
    assert kitchen_preview_response.status_code == 200, kitchen_preview_response.get_data(as_text=True)
    kitchen_preview = kitchen_preview_response.get_json()
    assert kitchen_preview["can_confirm"] is True and kitchen_preview["counts"]["duplicate"] == 1
    kitchen_confirm = client.post(
        "/api/mappings/import/confirm", json={"token": kitchen_preview["token"], "confirmed": True}
    )
    assert kitchen_confirm.status_code == 200 and kitchen_confirm.get_json()["inserted"] == 2
    kitchen_list = client.get("/api/mappings/kitchen_units").get_json()["items"]
    assert any(item["code"] == mapping_kitchens[1]["code"] and item["target_value"] == "UNIT-QC-02" for item in kitchen_list)

    # Force a catalogue change between preview and confirmation to prove the SQL transaction rolls back.
    with server.db() as conn:
        conn.execute("INSERT INTO products(code,name) VALUES('QC-MAP-A','Hàng tạm QC A')")
        conn.execute("INSERT INTO products(code,name) VALUES('QC-MAP-B','Hàng tạm QC B')")
    rollback_file = mapping_workbook_bytes(
        ["Mã hàng", "Tên hóa đơn"],
        [["QC-MAP-A", "Tên tạm A"], ["QC-MAP-B", "Tên tạm B"]],
    )
    rollback_preview = preview_mapping(client, "invoice_names", rollback_file).get_json()
    assert rollback_preview["can_confirm"] is True
    with server.db() as conn:
        conn.execute("DELETE FROM products WHERE code='QC-MAP-B'")
    rollback_confirm = client.post(
        "/api/mappings/import/confirm", json={"token": rollback_preview["token"], "confirmed": True}
    )
    assert rollback_confirm.status_code == 409
    with server.db() as conn:
        assert not conn.execute(
            "SELECT 1 FROM outgoing_product_names WHERE product_code='QC-MAP-A'"
        ).fetchone(), "Transaction phải rollback toàn bộ nếu danh mục thay đổi giữa chừng"
        conn.execute("DELETE FROM products WHERE code IN ('QC-MAP-A','QC-MAP-B')")
        batch_audits = conn.execute(
            "SELECT COUNT(*) count FROM audit_log WHERE event_type='mapping.bulk_import' AND status='ok'"
        ).fetchone()["count"]
    assert batch_audits == 4
    print("MAPPING_IMPORT", json.dumps({
        "invoice": mapping_confirm.get_json(),
        "repeat": mapping_repeat_confirm.get_json(),
        "update": update_confirm.get_json(),
        "kitchen": kitchen_confirm.get_json(),
        "invalidBlocked": True,
        "rollbackVerified": True,
    }, ensure_ascii=False, indent=2))

    master_source = ROOT / "Em Thành.xlsx"
    with master_source.open("rb") as handle:
        analyzed = client.post(
            "/api/import/analyze",
            data={"file": (handle, master_source.name)},
            content_type="multipart/form-data",
        )
    assert analyzed.status_code == 200, analyzed.get_data(as_text=True)
    analysis = analyzed.get_json()
    detected_names = {item["name"] for item in analysis["sheets"]}
    assert "đơn hàng27.08 " in detected_names
    selected = client.post("/api/import/confirm", json={
        "token": analysis["token"],
        "work_date": "2026-08-27",
        "sheets": ["đơn hàng27.08 "],
    })
    assert selected.status_code == 200, selected.get_data(as_text=True)
    # Ignore the single formula/formatted row whose calculated quantity is zero.
    assert len(selected.get_json()["orders"]) == 323

    source = ROOT / "Tách212223.xlsx"
    with source.open("rb") as handle:
        response = client.post(
            "/api/import",
            data={"work_date": "2026-08-28", "file": (handle, source.name)},
            content_type="multipart/form-data",
        )
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    batch_id = payload["batch"]["id"]
    orders = payload["orders"]
    assert orders, "Không đọc được dòng đơn nào"

    sheets = Counter(item["source_sheet"] for item in orders)
    error_types = Counter(error for item in orders for error in item["errors"])
    warning_types = Counter(warning for item in orders for warning in item["warnings"])
    assert sum(bool(item["errors"]) for item in orders) == 0
    assert sum(bool(item["warnings"]) for item in orders) == 27
    assert sum(any("95%" in warning for warning in item["warnings"]) for item in orders) == 12
    assert sum(any("bán lỗ" in warning for warning in item["warnings"]) for item in orders) == 15
    print("IMPORT", json.dumps({
        "orders": len(orders),
        "sheets": sheets,
        "errorRows": sum(bool(item["errors"]) for item in orders),
        "errorTypes": error_types,
        "warningRows": sum(bool(item["warnings"]) for item in orders),
        "warningTypes": warning_types,
    }, ensure_ascii=False, default=dict, indent=2))
    approved_old_file = client.post(f"/api/batches/{batch_id}/approve")
    assert approved_old_file.status_code == 200, approved_old_file.get_data(as_text=True)
    with server.db() as conn:
        bk_cost_mismatches = conn.execute(
            """SELECT COUNT(*) n FROM inventory_transactions t
               JOIN orders o ON o.id=CAST(t.source_line AS INTEGER)
               WHERE t.source_type='BK_INPUT' AND t.source_id=?
                 AND ABS(t.unit_cost-ROUND(o.sell_price*0.95))>0.001""",
            (str(batch_id),),
        ).fetchone()["n"]
    assert bk_cost_mismatches == 0

    mapped_code = orders[0]["product_code"]
    mapped_invoice_name = "TEN XUAT HOA DON QC"
    mapped_name_response = client.put(
        f"/api/outgoing-product-names/{mapped_code}", json={"invoice_name": mapped_invoice_name}
    )
    assert mapped_name_response.status_code == 200
    export_sizes = {}
    mapped_name_seen = False
    for kind in ("suppliers", "deliveries", "report", "purchases", "invoices"):
        result = client.get(f"/api/export/{kind}/{batch_id}")
        assert result.status_code == 200, (kind, result.get_data(as_text=True))
        assert len(result.data) > 1000, kind
        export_sizes[kind] = len(result.data)
        if kind != "invoices":
            wb = load_workbook(io.BytesIO(result.data), data_only=True)
            assert wb.sheetnames
        else:
            with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
                invoice_files = [name for name in archive.namelist() if name.endswith(".xlsx")]
                assert invoice_files
                for name in invoice_files:
                    wb = load_workbook(io.BytesIO(archive.read(name)), data_only=True)
                    ws = wb.active
                    assert [ws.cell(1, col).value for col in range(1, 12)] == server.INVOICE_HEADERS
                    for row in range(2, ws.max_row + 1):
                        if ws.cell(row, 2).value == mapped_code:
                            assert ws.cell(row, 4).value == mapped_invoice_name
                            mapped_name_seen = True
                        assert round(ws.cell(row, 8).value) == round(ws.cell(row, 5).value * ws.cell(row, 7).value)
                        if ws.cell(row, 9).value == "KKKNT":
                            assert round(ws.cell(row, 10).value) == round(ws.cell(row, 8).value)
                        else:
                            assert round(ws.cell(row, 10).value) == round(
                                ws.cell(row, 8).value * (1 + ws.cell(row, 9).value)
                            )
    assert mapped_name_seen

    # Manual-flow test: new batch, add, edit, approve.
    new_batch = client.post("/api/batches", json={"work_date": "2026-08-29"}).get_json()
    manual_id = new_batch["batch"]["id"]
    add = client.post("/api/orders", json={
        "batch_id": manual_id,
        "work_date": "2026-08-29",
        "kitchen": "POT",
        "product_code": "I000060",
        "qty": 3,
        "actual_received": 3,
        "actual_delivered": 2.8,
        "buy_price": 14000,
        "sell_price": 16000,
        "tax": "KKKNT",
        "supplier": "kho",
    })
    assert add.status_code == 200, add.get_data(as_text=True)
    item = add.get_json()["orders"][0]
    assert item["contractor"] == "HATRAN"
    assert item["product_name"]
    update = client.put(f"/api/orders/{item['id']}", json={"actual_delivered": 3})
    assert update.status_code == 200
    bulk = client.post("/api/orders/bulk", json={
        "batch_id": manual_id,
        "text": "Mã bếp\tMã hàng\tSố lượng\tNCC\tGiá mua\tGiá bán\tThuế\n"
                "POT\tI000060\t2\tkho\t14000\t16000\tKKKNT",
    })
    assert bulk.status_code == 200, bulk.get_data(as_text=True)
    assert bulk.get_json()["inserted"] == 1
    approved = client.post(f"/api/batches/{manual_id}/approve")
    assert approved.status_code == 200, approved.get_data(as_text=True)

    payment = client.post("/api/payments", json={
        "payment_date": "2026-08-29", "kind": "receipt", "party_type": "contractor",
        "party_code": "HATRAN", "amount": 10000, "note": "QC",
    })
    assert payment.status_code == 200
    balance = client.post("/api/balances", json={
        "party_type": "contractor", "party_code": "HATRAN", "opening": 5000,
    })
    assert balance.status_code == 200
    checked = client.get(f"/api/bootstrap?batch_id={manual_id}").get_json()
    assert checked["summary"]["contractors"]["HATRAN"]["opening"] == 5000
    assert checked["summary"]["contractors"]["HATRAN"]["paid"] == 10000

    # Returns/damage: cost and revenue must use net received/net delivered.
    first_item = checked["orders"][0]
    returned = client.put(f"/api/orders/{first_item['id']}", json={
        "actual_received": 3, "damaged_qty": 0.2, "supplier_return_qty": 0.3,
        "actual_delivered": 3, "customer_return_qty": 0.4,
    })
    assert returned.status_code == 200, returned.get_data(as_text=True)
    returned_item = next(row for row in returned.get_json()["orders"] if row["id"] == first_item["id"])
    assert round(returned_item["cost"]) == round(2.5 * returned_item["buy_price"])
    assert round(returned_item["revenue"]) == round(2.6 * returned_item["sell_price"])
    reapproved = client.post(f"/api/batches/{manual_id}/approve")
    assert reapproved.status_code == 200

    # Accounting inventory + supplier need formula.
    opening = client.post("/api/inventory/opening", json={
        "period": "2026-08", "items": [{"product_code": "I000060", "qty": 50, "unit_cost": 14000}],
    })
    assert opening.status_code == 200, opening.get_data(as_text=True)
    needs = client.get(f"/api/supplier-needs/{manual_id}")
    assert needs.status_code == 200, needs.get_data(as_text=True)
    need_data = needs.get_json()
    assert need_data["required_qty"] == 0
    supplier_rule = client.put("/api/supplier-rules/kho", json={"combine_kitchens": True})
    assert supplier_rule.status_code == 200

    # Outgoing invoice drafts reserve stock, but only user confirmation posts output.
    assert client.put(
        "/api/outgoing-product-names/I000060", json={"invoice_name": "HÀNH TÂY XUẤT HĐ QC"}
    ).status_code == 200
    drafted = client.post(f"/api/outgoing-invoices/draft/{manual_id}")
    assert drafted.status_code == 200, drafted.get_data(as_text=True)
    draft_id = drafted.get_json()["drafts"][0]["id"]
    with server.db() as conn:
        assert conn.execute(
            "SELECT COUNT(*) n FROM outgoing_invoice_lines WHERE draft_id=? AND product_code='I000060' AND product_name='HÀNH TÂY XUẤT HĐ QC'",
            (draft_id,),
        ).fetchone()["n"] >= 1
    issued = client.post(f"/api/outgoing-invoices/{draft_id}/confirm-issued", json={"confirmed": True})
    assert issued.status_code == 200

    # mSMI incremental/idempotent sync with a mock response; no external write.
    class DummyMsmi:
        def list_invoices(self, **kwargs):
            if kwargs.get("page", 0) > 0:
                return {"items": [], "has_more": False}
            return {"items": [{
                "_id": "QC-MSMI-001", "mstNban": "0200000001", "tenNban": "NCC QC",
                "shdon": "1", "khhdon": "C26TQC", "tdlap": "2026-08-29",
                "tgtcthue": 28000, "tgtthue": 0, "tgtttbso": 28000,
                "hdhhdvu": [{"ma": "SRC-01", "ten": "Hành tây QC", "dvtinh": "kg",
                               "sluong": 2, "dgia": 14000, "thtien": 28000, "tsuat": "KKKNT"}],
            }], "has_more": False}

    with server.db() as conn:
        synced_once = contract_modules.sync_msmi(conn, DummyMsmi(), server.now_iso, tenant="TDP")
    with server.db() as conn:
        synced_twice = contract_modules.sync_msmi(conn, DummyMsmi(), server.now_iso, tenant="TDP")
    assert synced_once["new_invoices"] == 1
    assert synced_twice["new_invoices"] == 0 and synced_twice["known_invoices"] == 1
    msmi_list = client.get("/api/msmi/invoices").get_json()["items"]
    msmi_invoice = next(row for row in msmi_list if row["remote_id"] == "QC-MSMI-001")
    msmi_item_id = msmi_invoice["items"][0]["id"]
    mapped = client.put(f"/api/msmi/items/{msmi_item_id}/mapping", json={"product_code": "I000060"})
    assert mapped.status_code == 200, mapped.get_data(as_text=True)
    receipt_once = client.post(f"/api/msmi/invoices/{msmi_invoice['id']}/receipt")
    receipt_twice = client.post(f"/api/msmi/invoices/{msmi_invoice['id']}/receipt")
    assert receipt_once.status_code == 200 and receipt_once.get_json()["new_inventory_lines"] == 1
    assert receipt_twice.status_code == 200 and receipt_twice.get_json()["idempotent"]

    # Normalized kitchen/menu/cost/Unit/PO flow.
    assert client.put("/api/kitchen-units/POT", json={"unit_code": "UNIT-POT"}).status_code == 200
    assert client.put("/api/dated-prices/I000060", json={
        "period": "2026-08", "price_group": "HATRAN", "price_value": 16000,
    }).status_code == 200
    meal = client.post("/api/kitchen/plans", json={
        "work_date": "2026-08-30", "kitchen": "POT", "shift": "Trưa", "meal_count": 100,
        "items": [{"dish_name": "Canh", "product_code": "I000060", "norm_qty": 0.08}],
    })
    assert meal.status_code == 200, meal.get_data(as_text=True)
    meal_id = meal.get_json()["id"]
    assert client.post(f"/api/kitchen/plans/{meal_id}/approve").status_code == 200
    kitchen_po = client.get("/api/kitchen/po?date=2026-08-30")
    assert kitchen_po.status_code == 200 and len(kitchen_po.data) > 1000

    # Attendance/payroll manual flow and real legacy workbook import.
    assert client.post("/api/staff", json={
        "employee_code": "NVQC", "full_name": "Nhân viên QC", "role_name": "Bếp",
        "kitchen": "POT", "base_salary": 5200000,
    }).status_code == 200
    assert client.post("/api/attendance", json={
        "employee_code": "NVQC", "work_date": "2026-08-01", "normal_hours": 8,
        "overtime_hours": 2,
    }).status_code == 200
    assert client.put("/api/payroll-adjustments/NVQC/2026-08", json={
        "allowance": 300000, "responsibility": 200000, "advance": 100000,
    }).status_code == 200
    payroll = client.get("/api/payroll?month=2026-08")
    assert payroll.status_code == 200
    qc_pay = next(row for row in payroll.get_json()["items"] if row["employee_code"] == "NVQC")
    assert qc_pay["net_salary"] > 0
    attendance_source = ROOT / "bosung.30.8.26" / "CHẤM CÔNG+ SUẤT ĂN  2026" / "CHẤM CÔNG T8.2026.xlsx"
    with attendance_source.open("rb") as handle:
        imported_attendance = client.post(
            "/api/attendance/import", data={"file": (handle, attendance_source.name)},
            content_type="multipart/form-data",
        )
    assert imported_attendance.status_code == 200, imported_attendance.get_data(as_text=True)
    assert imported_attendance.get_json()["attendance_entries"] > 0
    assert imported_attendance.get_json()["labor_cost_entries"] > 0
    assert imported_attendance.get_json()["payroll_overrides"] >= 7
    imported_payroll = client.get("/api/payroll?month=2026-08").get_json()["items"]
    legacy_payroll = [row for row in imported_payroll if row["employee_code"] != "NVQC"]
    assert max(row["normal_hours"] for row in legacy_payroll) <= 31 * 24
    assert round(next(row for row in legacy_payroll if row["employee_code"] == "TRIEN")["net_salary"]) == 8000000
    assert round(sum(row["net_salary"] for row in legacy_payroll)) == 14379021

    # Multi-period debts, payment request and approval-gated print dry-run.
    debts = client.get("/api/debts?from=2026-08-01&to=2026-08-31")
    assert debts.status_code == 200 and "HATRAN" in debts.get_json()["contractors"]
    payment_request = client.get("/api/export/payment-request/HATRAN?from=2026-08-01&to=2026-08-31")
    assert payment_request.status_code == 200 and len(payment_request.data) > 1000
    prepared = client.post(f"/api/print/prepare/{manual_id}")
    assert prepared.status_code == 200, prepared.get_data(as_text=True)
    assert client.post(f"/api/print/approve/{manual_id}").status_code == 200
    print_dry_run = client.post(f"/api/print/run/{manual_id}", json={"dry_run": True})
    assert print_dry_run.status_code == 200 and print_dry_run.get_json()["jobs"] == 4

    operations = client.get("/api/operations/bootstrap?as_of=2026-08-31&month=2026-08&date=2026-08-30")
    assert operations.status_code == 200
    assert operations.get_json()["msmi"]["invoices"]
    assert operations.get_json()["meal_plans"]

    print("QC", json.dumps({
        "ok": True,
        "masterProducts": bootstrap["master"]["product_count"],
        "selectedSheetOrders": len(selected.get_json()["orders"]),
        "importedOrders": len(orders),
        "importWarnings": sum(bool(item["warnings"]) for item in orders),
        "oldFileApproval": "passed_with_warnings",
        "exportSizes": export_sizes,
        "manualAndPasteFlow": "passed",
        "debtFlow": "passed",
        "inventoryAndReturns": "passed",
        "msmiIdempotentSyncMappingReceipt": "passed",
        "outgoingDraftStockGate": "passed",
        "kitchenMenuCostPo": "passed",
        "attendancePayrollLegacyImport": "passed",
        "paymentRequestAndPrintApproval": "passed",
    }, ensure_ascii=False, indent=2))
    print_dir = APP_DIR / "data" / "print_jobs" / str(manual_id)
    if print_dir.exists() and print_dir.resolve().is_relative_to((APP_DIR / "data" / "print_jobs").resolve()):
        rmtree(print_dir)
    clean_test_db(qc_db)


if __name__ == "__main__":
    main()
