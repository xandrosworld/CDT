from __future__ import annotations

import io
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from shutil import rmtree

from docx import Document as DocxDocument
from openpyxl import Workbook, load_workbook

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))
import server  # noqa: E402
import contract_modules  # noqa: E402
from msmi_client import MsmiClient, MsmiConfig  # noqa: E402


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


def catalog_workbook_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "danh mục hàng hóa"
    headers = ["STT", "MÃ HÀNG", "Nhóm hàng", "TÊN THÀNH ĐẠT PHÁT", "TÊN XUẤT HÓA ĐƠN", "ĐVT", "Thuế"]
    for column, value in enumerate(headers, start=1):
        sheet.cell(1, column, value)
    for row_index, values in enumerate(rows, start=2):
        sheet.cell(row_index, 1, row_index - 1)
        for column, value in enumerate(values, start=2):
            sheet.cell(row_index, column, value)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def preview_catalog(client, payload, filename="danh-muc.xlsx"):
    return client.post(
        "/api/catalog/import/preview",
        data={"file": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def kitchen_workbook_bytes(product_code="A000047", duplicate_first=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "T2"
    sheet.cell(3, 5, "VINA")
    headers = ["Nhà thầu", "Mã hàng", "Mã bếp", "Món ăn", "SỐ SUẤT ĂN CA SÁNG",
               10, "số lượng", None, "Giá bán", "Thành tiền"]
    for column, value in enumerate(headers, start=1):
        sheet.cell(4, column, value)
    first = ["HATRAN", product_code, "XCOM", "THỊT LUỘC", "Thịt nách heo",
             100, 1, "Kg", 105000, 105000]
    for column, value in enumerate(first, start=1):
        sheet.cell(5, column, value)
    next_row = 6
    if duplicate_first:
        duplicate = list(first)
        duplicate[6] = 0.5
        duplicate[9] = 52500
        for column, value in enumerate(duplicate, start=1):
            sheet.cell(next_row, column, value)
        next_row += 1
    placeholder = ["HATRAN", "-", "VINA", None, None, None, 0, "-", 0, 0]
    for column, value in enumerate(placeholder, start=1):
        sheet.cell(next_row, column, value)
    next_row += 1
    sheet.cell(next_row, 5, "CA SÁNG")
    sheet.cell(next_row, 6, 4)
    next_row += 1
    second = ["HATRAN", "H000007", "MAZDA", "TRỨNG ỐP LA", "Trứng gà CN",
              1000, 8, "Quả", 3000, 24000]
    for column, value in enumerate(second, start=1):
        sheet.cell(next_row, column, value)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def preview_kitchen(client, payload, work_date="2026-09-02", filename="xưởng cơm QC.xlsx"):
    return client.post(
        "/api/kitchen/import/preview",
        data={"work_date": work_date, "file": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def opening_workbook_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tồn cuối tháng"
    headers = ["MÃ TĐP", "TÊN TDP", "Tên trên HĐ", "MÃ KHO", "T/Suất", "ĐVT"]
    for column, value in enumerate(headers, start=1):
        sheet.cell(5, column, value)
    sheet.cell(5, 7, "Tồn cuối kỳ")
    sheet.cell(6, 7, "Số lượng")
    sheet.cell(6, 8, "Đơn giá")
    sheet.cell(6, 9, "Thành tiền")
    for row_index, values in enumerate(rows, start=7):
        for column, value in enumerate(values, start=1):
            sheet.cell(row_index, column, value)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def preview_opening(client, payload, period="2026-08", filename="tồn đầu kỳ.xlsx"):
    return client.post(
        "/api/inventory/opening/import/preview",
        data={"period": period, "file": (io.BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )


def run_catalog_import_qc():
    catalog_db = APP_DIR / "data" / "qc_catalog_test.sqlite3"
    clean_test_db(catalog_db)
    actual_source = next((ROOT / "_HANDOFF" / "EXTERNAL_INPUTS").glob("08410fad*.xlsx"), None)
    try:
        server.DB_PATH = catalog_db
        server.init_database()
        client = server.app.test_client()

        conflict_file = catalog_workbook_bytes([
            ["QC-CAT-01", "QC", "Hàng QC A", "Tên hóa đơn A", "Kg", "8%"],
            ["QC-CAT-01", "QC", "Hàng QC B", "Tên hóa đơn B", "Kg", "8%"],
        ])
        conflict_preview = preview_catalog(client, conflict_file).get_json()
        assert conflict_preview["can_confirm"] is False
        assert conflict_preview["counts"]["error"] == 2
        assert client.post(
            "/api/catalog/import/confirm",
            json={"token": conflict_preview["token"], "confirmed": True},
        ).status_code == 400

        if actual_source is None or not actual_source.exists():
            return "synthetic conflict/atomic block passed; customer workbook not present"

        source_hash = hashlib.sha256(actual_source.read_bytes()).hexdigest().upper()
        assert source_hash == "635308AF3F203BA51456BB4F7984BE3034D18FBBE10E005B2827C394CFA4C305"
        with server.db() as conn:
            protected_before = dict(conn.execute(
                """SELECT code,supplier,buy_price,purchase_list,seller,cccd
                   FROM products WHERE code='A000001'"""
            ).fetchone())
            price_before = [tuple(row) for row in conn.execute(
                "SELECT price_group,price_text,price_value FROM product_prices WHERE product_code='A000001' ORDER BY price_group"
            )]

        with actual_source.open("rb") as handle:
            preview_response = client.post(
                "/api/catalog/import/preview",
                data={"file": (handle, actual_source.name)},
                content_type="multipart/form-data",
            )
        assert preview_response.status_code == 200, preview_response.get_data(as_text=True)
        preview = preview_response.get_json()
        assert preview["source_hash"] == source_hash
        assert preview["sheet"] == "danh mục hàng hóa" and preview["header_row"] == 1
        assert preview["can_confirm"] is True
        assert preview["counts"] == {
            "total": 1249,
            "unique_products": 1249,
            "new_products": 380,
            "update_products": 869,
            "unchanged_products": 0,
            "retained_products": 2,
            "new_names": 1249,
            "update_names": 0,
            "unchanged_names": 0,
            "duplicate": 0,
            "error": 0,
        }
        assert client.post(
            "/api/catalog/import/confirm", json={"token": preview["token"]},
        ).status_code == 400
        confirmed = client.post(
            "/api/catalog/import/confirm",
            json={"token": preview["token"], "confirmed": True},
        )
        assert confirmed.status_code == 200, confirmed.get_data(as_text=True)
        confirmed_data = confirmed.get_json()
        assert confirmed_data["processed"] == 1249
        assert confirmed_data["inserted_products"] == 380
        assert confirmed_data["inserted_names"] == 1249
        assert client.post(
            "/api/catalog/import/confirm",
            json={"token": preview["token"], "confirmed": True},
        ).status_code == 410

        with server.db() as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1251
            assert conn.execute("SELECT COUNT(*) FROM outgoing_product_names").fetchone()[0] == 1249
            assert conn.execute(
                "SELECT invoice_name FROM outgoing_product_names WHERE product_code='I000164'"
            ).fetchone()[0] == "Bắp cải"
            assert conn.execute("SELECT unit FROM products WHERE code='D000021'").fetchone()[0] == "Kg"
            assert conn.execute("SELECT unit FROM products WHERE code='I000090'").fetchone()[0] == "Kg"
            assert conn.execute("SELECT product_group FROM products WHERE code='A000001'").fetchone()[0] == "A"
            assert conn.execute("SELECT 1 FROM products WHERE code='G000074'").fetchone()
            assert conn.execute("SELECT 1 FROM products WHERE code='I000189'").fetchone()
            protected_after = dict(conn.execute(
                """SELECT code,supplier,buy_price,purchase_list,seller,cccd
                   FROM products WHERE code='A000001'"""
            ).fetchone())
            price_after = [tuple(row) for row in conn.execute(
                "SELECT price_group,price_text,price_value FROM product_prices WHERE product_code='A000001' ORDER BY price_group"
            )]
            assert protected_after == protected_before
            assert price_after == price_before

        with actual_source.open("rb") as handle:
            repeat_response = client.post(
                "/api/catalog/import/preview",
                data={"file": (handle, "danh-muc-doi-ten.xlsx")},
                content_type="multipart/form-data",
            )
        repeat = repeat_response.get_json()
        assert repeat["counts"]["new_products"] == 0
        assert repeat["counts"]["update_products"] == 0
        assert repeat["counts"]["unchanged_products"] == 1249
        assert repeat["counts"]["unchanged_names"] == 1249
        repeat_confirm = client.post(
            "/api/catalog/import/confirm",
            json={"token": repeat["token"], "confirmed": True},
        )
        assert repeat_confirm.status_code == 200
        assert repeat_confirm.get_json()["unchanged_names"] == 1249

        with actual_source.open("rb") as handle:
            stale_response = client.post(
                "/api/catalog/import/preview",
                data={"file": (handle, actual_source.name)},
                content_type="multipart/form-data",
            )
        stale = stale_response.get_json()
        with server.db() as conn:
            conn.execute("UPDATE products SET unit='QC-CHANGED' WHERE code='A000001'")
        stale_confirm = client.post(
            "/api/catalog/import/confirm",
            json={"token": stale["token"], "confirmed": True},
        )
        assert stale_confirm.status_code == 409
        assert "thay đổi" in stale_confirm.get_json()["error"]
        return "1,249 products / 380 new / 1,249 confirmed invoice names / repeat safe"
    finally:
        contract_modules.PENDING_CATALOG_IMPORTS.clear()
        clean_test_db(catalog_db)


def main():
    catalog_import_result = run_catalog_import_qc()
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
    assert bootstrap["master"]["settings"]["payment_requester"] == "VŨ THỊ THỤY"
    assert bootstrap["master"]["settings"]["payment_bank_account"] == "1052787580"
    assert bootstrap["master"]["settings"]["payment_bank_name"] == "Ngân hàng TMCP Ngoại Thương Việt Nam"

    class CapturingMsmiClient(MsmiClient):
        def _get(self, path, params=None):
            self.captured_path = path
            self.captured_params = params
            return {"listInvoice": [{} for _ in range(params["size"])]}

    paging_client = CapturingMsmiClient(MsmiConfig("https://example.invalid", "not-a-real-token"))
    paging_result = paging_client.list_invoices(size=200)
    assert paging_client.captured_path == "api/qlhd-api/invoices"
    assert paging_client.captured_params["size"] == 199 and paging_result["has_more"] is True

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
        ["Tên bếp", "Mã bếp", "XCOM (xưởng cơm)"],
        [
            [mapping_kitchens[0]["name"], "", "XCOM-QC-01"],
            ["", mapping_kitchens[1]["code"], "xcom-qc-02"],
            [mapping_kitchens[0]["name"], "", "XCOM-QC-01"],
        ],
        sheet_name="Bếp - XCOM",
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
    assert any(item["code"] == mapping_kitchens[1]["code"] and item["target_value"] == "XCOM-QC-02" for item in kitchen_list)
    legacy_unit_file = mapping_workbook_bytes(
        ["Mã bếp", "Unit"], [[mapping_kitchens[1]["code"], "XCOM-QC-02"]], sheet_name="File cũ",
    )
    legacy_unit_preview = preview_mapping(client, "kitchen_units", legacy_unit_file)
    assert legacy_unit_preview.status_code == 200 and legacy_unit_preview.get_json()["can_confirm"] is True

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
    orphan_pending = APP_DIR / "data" / "pending_qc_orphan.xlsx"
    orphan_pending.write_bytes(b"orphaned preview")
    with master_source.open("rb") as handle:
        cancelled_analysis = client.post(
            "/api/import/analyze",
            data={"file": (handle, master_source.name)},
            content_type="multipart/form-data",
        )
    assert cancelled_analysis.status_code == 200
    assert not orphan_pending.exists()
    cancelled_token = cancelled_analysis.get_json()["token"]
    cancelled_path = APP_DIR / "data" / f"pending_{cancelled_token}.xlsx"
    assert cancelled_path.exists()
    assert client.post("/api/import/cancel", json={"token": cancelled_token}).status_code == 200
    assert not cancelled_path.exists()
    assert client.post("/api/import/cancel", json={"token": cancelled_token}).get_json()["idempotent"]
    assert client.post("/api/import/confirm", json={
        "token": cancelled_token, "work_date": "2026-08-27", "sheets": ["đơn hàng27.08 "],
    }).status_code == 400

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
    debt_adjustment = client.post("/api/debt-adjustments", json={
        "adjustment_date": "2026-08-29", "party_type": "contractor",
        "party_code": "HATRAN", "amount": 2500, "note": "QC điều chỉnh",
    })
    assert debt_adjustment.status_code == 200
    debt_period = client.get("/api/debts?from=2026-08-01&to=2026-08-31")
    assert debt_period.status_code == 200
    assert debt_period.get_json()["contractors"]["HATRAN"]["period_adjustment"] == 2500
    assert client.get("/api/debts?from=2026-09-01&to=2026-08-31").status_code == 400
    debt_export = client.get("/api/export/debts?from=2026-08-01&to=2026-08-31")
    assert debt_export.status_code == 200 and len(debt_export.data) > 1000
    debt_book = load_workbook(io.BytesIO(debt_export.data), data_only=True)
    assert debt_book.sheetnames == ["Phải thu", "Phải trả", "Thu chi", "Điều chỉnh"]
    assert debt_book["Phải thu"]["A3"].value == "Đối tượng"
    assert any(row[0].value == "HATRAN" and row[3].value == 2500 for row in debt_book["Phải thu"].iter_rows(min_row=4))
    debt_book.close()

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
    drafted_again = client.post(f"/api/outgoing-invoices/draft/{manual_id}")
    assert drafted_again.status_code == 200, drafted_again.get_data(as_text=True)
    assert drafted_again.get_json()["drafts"][0]["id"] == draft_id
    with server.db() as conn:
        assert conn.execute(
            "SELECT COUNT(*) n FROM outgoing_invoice_lines WHERE draft_id=? AND product_code='I000060' AND product_name='HÀNH TÂY XUẤT HĐ QC'",
            (draft_id,),
        ).fetchone()["n"] >= 1
        assert conn.execute(
            "SELECT COUNT(*) n FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",
            (str(draft_id),),
        ).fetchone()["n"] == 2
    cancelled = client.post(f"/api/outgoing-invoices/{draft_id}/cancel", json={"confirmed": True})
    assert cancelled.status_code == 200
    assert client.post(
        f"/api/outgoing-invoices/{draft_id}/confirm-issued", json={"confirmed": True}
    ).status_code == 409
    with server.db() as conn:
        assert conn.execute(
            "SELECT COUNT(*) n FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",
            (str(draft_id),),
        ).fetchone()["n"] == 0
    recreated = client.post(f"/api/outgoing-invoices/draft/{manual_id}")
    assert recreated.status_code == 200 and recreated.get_json()["drafts"][0]["status"] == "draft"
    issued = client.post(f"/api/outgoing-invoices/{draft_id}/confirm-issued", json={"confirmed": True})
    assert issued.status_code == 200
    assert client.post(f"/api/outgoing-invoices/{draft_id}/cancel", json={"confirmed": True}).status_code == 409

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

    # Customer-style kitchen workbook: preview, explicit confirmation, exact quantities and idempotent re-import.
    kitchen_file = kitchen_workbook_bytes()
    kitchen_file_preview = preview_kitchen(client, kitchen_file)
    assert kitchen_file_preview.status_code == 200, kitchen_file_preview.get_data(as_text=True)
    kitchen_file_data = kitchen_file_preview.get_json()
    assert kitchen_file_data["can_confirm"] is True
    assert kitchen_file_data["counts"]["plans"] == 2 and kitchen_file_data["counts"]["items"] == 2
    assert [(plan["kitchen"], plan["xcom_code"]) for plan in kitchen_file_data["plans"]] == [
        ("VINA", "XCOM"), ("MAZDA", "MAZDA"),
    ]
    assert client.post(
        "/api/kitchen/import/confirm", json={"token": kitchen_file_data["token"]}
    ).status_code == 400
    kitchen_file_confirm = client.post(
        "/api/kitchen/import/confirm",
        json={"token": kitchen_file_data["token"], "confirmed": True},
    )
    assert kitchen_file_confirm.status_code == 200, kitchen_file_confirm.get_data(as_text=True)
    assert kitchen_file_confirm.get_json()["inserted"] == 2
    imported_plans = client.get("/api/kitchen/plans?date=2026-09-02").get_json()["items"]
    assert len(imported_plans) == 2
    mazda_egg = next(
        item for plan in imported_plans if plan["kitchen"] == "MAZDA"
        for item in plan["items"] if item["product_code"] == "H000007"
    )
    assert mazda_egg["required_qty"] == 8 and mazda_egg["norm_qty"] == 2
    kitchen_file_po = client.get("/api/kitchen/po?date=2026-09-02")
    assert kitchen_file_po.status_code == 200 and len(kitchen_file_po.data) > 1000
    kitchen_file_po_book = load_workbook(io.BytesIO(kitchen_file_po.data), data_only=True)
    assert any("XCOM " in str(sheet.cell(2, 4).value) for sheet in kitchen_file_po_book.worksheets)
    kitchen_file_po_book.close()
    kitchen_repeat_data = preview_kitchen(client, kitchen_file).get_json()
    assert kitchen_repeat_data["counts"]["new"] == 0 and kitchen_repeat_data["counts"]["update"] == 2
    kitchen_repeat_confirm = client.post(
        "/api/kitchen/import/confirm",
        json={"token": kitchen_repeat_data["token"], "confirmed": True},
    )
    assert kitchen_repeat_confirm.status_code == 200 and kitchen_repeat_confirm.get_json()["updated"] == 2
    assert len(client.get("/api/kitchen/plans?date=2026-09-02").get_json()["items"]) == 2
    invalid_kitchen_data = preview_kitchen(
        client, kitchen_workbook_bytes("MA-KHONG-TON-TAI"), work_date="2026-09-03"
    ).get_json()
    assert invalid_kitchen_data["can_confirm"] is False and invalid_kitchen_data["counts"]["errors"] == 1
    assert client.post(
        "/api/kitchen/import/confirm",
        json={"token": invalid_kitchen_data["token"], "confirmed": True},
    ).status_code == 400
    assert not client.get("/api/kitchen/plans?date=2026-09-03").get_json()["items"]
    assert preview_kitchen(client, kitchen_file, work_date="2026-02-30").status_code == 400
    assert preview_kitchen(client, b"not-an-xlsx", work_date="2026-09-03").status_code == 400
    duplicate_kitchen = preview_kitchen(
        client, kitchen_workbook_bytes(duplicate_first=True), work_date="2026-09-03"
    ).get_json()
    assert duplicate_kitchen["can_confirm"] is False and duplicate_kitchen["counts"]["errors"] == 1

    with server.db() as conn:
        conn.execute(
            """INSERT INTO products(code,name,unit,supplier,buy_price)
               VALUES('QC-XCOM-ROLLBACK','Hàng rollback xưởng cơm','kg','QC',10000)"""
        )
    rollback_kitchen = preview_kitchen(
        client, kitchen_workbook_bytes("QC-XCOM-ROLLBACK"), work_date="2026-09-04"
    ).get_json()
    assert rollback_kitchen["can_confirm"] is True
    with server.db() as conn:
        conn.execute("DELETE FROM products WHERE code='QC-XCOM-ROLLBACK'")
    rollback_kitchen_confirm = client.post(
        "/api/kitchen/import/confirm",
        json={"token": rollback_kitchen["token"], "confirmed": True},
    )
    assert rollback_kitchen_confirm.status_code == 409
    assert not client.get("/api/kitchen/plans?date=2026-09-04").get_json()["items"]

    actual_kitchen_source = ROOT / "_HANDOFF" / "EXTERNAL_INPUTS" / "xưởng cơm.xlsx"
    actual_kitchen_result = "not_present"
    if actual_kitchen_source.exists():
        assert hashlib.sha256(actual_kitchen_source.read_bytes()).hexdigest().upper() == (
            "4CCF1957C53DE932EF87EFEAEBBD398A3F45A60161FC04409BC6A471664ACE8B"
        )
        with actual_kitchen_source.open("rb") as handle:
            actual_preview_response = client.post(
                "/api/kitchen/import/preview",
                data={"work_date": "2026-09-01", "file": (handle, actual_kitchen_source.name)},
                content_type="multipart/form-data",
            )
        assert actual_preview_response.status_code == 200, actual_preview_response.get_data(as_text=True)
        actual_preview = actual_preview_response.get_json()
        assert actual_preview["can_confirm"] is True
        assert actual_preview["counts"]["plans"] == 5 and actual_preview["counts"]["items"] == 54
        assert [(plan["kitchen"], plan["xcom_code"], plan["meal_count"]) for plan in actual_preview["plans"]] == [
            ("VINA", "XCOM", 28), ("SUNBY", "XCOM", 32), ("DAINAM", "XCOM", 48),
            ("MAZDA", "MAZDA", 46), ("TTS", "TTS", 40),
        ]
        mazda_preview = next(plan for plan in actual_preview["plans"] if plan["kitchen"] == "MAZDA")
        assert mazda_preview["menu_count"] == 2 and mazda_preview["servings_per_menu"] == 23
        assert mazda_preview["meal_price"] == 35000
        actual_confirm = client.post(
            "/api/kitchen/import/confirm",
            json={"token": actual_preview["token"], "confirmed": True},
        )
        assert actual_confirm.status_code == 200 and actual_confirm.get_json()["inserted"] == 5
        actual_plans = client.get("/api/kitchen/plans?date=2026-09-01").get_json()["items"]
        assert len(actual_plans) == 5 and sum(len(plan["items"]) for plan in actual_plans) == 54
        actual_by_kitchen = {plan["kitchen"]: plan for plan in actual_plans}
        expected_financials = {
            "VINA": (28, 30000, 503580, 297962.962962963),
            "SUNBY": (32, 25000, 488000, 338814.814814815),
            "DAINAM": (48, 25000, 710880, 502222.222222222),
            "MAZDA": (46, 35000, 821100, 576538.461538462),
            "TTS": (40, 40000, 1327640, 190909.090909091),
        }
        for kitchen, (meals, price, food_cost, other_cost) in expected_financials.items():
            plan = actual_by_kitchen[kitchen]
            assert plan["meal_count"] == meals and plan["meal_price"] == price
            assert abs(plan["food_cost"] - food_cost) < 0.01
            assert abs(plan["other_cost"] - other_cost) < 0.01
            assert abs(plan["revenue"] - meals * price) < 0.01
            assert abs(plan["total_cost"] - (food_cost + other_cost)) < 0.01
            assert abs(plan["profit"] - (meals * price - food_cost - other_cost)) < 0.01
        assert client.put("/api/kitchen-units/VINA", json={"xcom_code": "XCOM-NEW"}).status_code == 200
        historic_vina = next(
            plan for plan in client.get("/api/kitchen/plans?date=2026-09-01").get_json()["items"]
            if plan["kitchen"] == "VINA"
        )
        assert historic_vina["mapped_unit"] == "XCOM", "Kế hoạch cũ phải giữ XCOM tại thời điểm nhập"
        assert client.put("/api/kitchen-units/VINA", json={"xcom_code": "XCOM"}).status_code == 200
        mazda_items = actual_by_kitchen["MAZDA"]["items"]
        assert {round(item["applicable_meal_count"]) for item in mazda_items} == {23, 46}
        assert next(item for item in mazda_items if item["product_code"] == "H000007")["required_qty"] == 46

        actual_po_response = client.get("/api/kitchen/po?date=2026-09-01")
        assert actual_po_response.status_code == 200 and len(actual_po_response.data) > 1000
        assert "PO_xuong_com_NHAP_2026-09-01.xlsx" in actual_po_response.headers["Content-Disposition"]
        actual_po_book = load_workbook(io.BytesIO(actual_po_response.data), data_only=True)
        assert set(actual_po_book.sheetnames) == {"XCOM", "MAZDA", "TTS"}
        expected_headers = [
            "STT", "Bếp / ca", "Mã hàng", "Tên nguyên liệu", "ĐVT", "Suất áp dụng",
            "Định lượng/1.000 suất", "Số lượng cần", "Đơn giá", "Thành tiền", "NCC", "Nguồn giá",
        ]
        po_rows = []
        for sheet in actual_po_book.worksheets:
            assert sheet.cell(1, 1).value == "PO XƯỞNG CƠM – BẢN NHÁP"
            assert [sheet.cell(3, col).value for col in range(1, 13)] == expected_headers
            assert sheet.cell(2, 4).value == f"XCOM {sheet.title}"
            row = 4
            while sheet.cell(row, 1).value is not None:
                po_rows.append(tuple(sheet.cell(row, col).value for col in range(1, 13)))
                row += 1
            assert sheet.cell(row + 1, 1).value == "TỔNG HỢP SUẤT ĂN / COST"
        actual_po_book.close()
        assert len(po_rows) == 54
        assert abs(sum(float(row[9] or 0) for row in po_rows) - 3851200) < 0.01
        assert all(row[7] and row[8] and row[9] and row[10] and "HATRAN" in row[11] for row in po_rows)
        with actual_kitchen_source.open("rb") as handle:
            repeat_actual_response = client.post(
                "/api/kitchen/import/preview",
                data={"work_date": "2026-09-01", "file": (handle, "renamed-kitchen-file.xlsx")},
                content_type="multipart/form-data",
            )
        repeat_actual = repeat_actual_response.get_json()
        assert repeat_actual["counts"]["new"] == 0 and repeat_actual["counts"]["update"] == 5
        repeat_actual_confirm = client.post(
            "/api/kitchen/import/confirm",
            json={"token": repeat_actual["token"], "confirmed": True},
        )
        assert repeat_actual_confirm.status_code == 200 and repeat_actual_confirm.get_json()["updated"] == 5
        assert len(client.get("/api/kitchen/plans?date=2026-09-01").get_json()["items"]) == 5
        actual_kitchen_result = "5 plans / 54 items / 3 XCOM sheets / financial reconciliation passed"

    # Actual monthly meal-attendance workbook: keep actual meals separate from PO planned meals.
    meal_attendance_source = (
        ROOT / "bosung.30.8.26" / "CHẤM CÔNG+ SUẤT ĂN  2026"
        / "SUẤT ĂN XƯỞNG CƠM 2026" / "SUẤT ĂN T8.2026.xlsx"
    )
    assert hashlib.sha256(meal_attendance_source.read_bytes()).hexdigest().upper() == (
        "1117786C6356E75CA75329926E1F3717BD8EADAE3857F8E5BED3B36B1C9E1EBF"
    )
    with meal_attendance_source.open("rb") as handle:
        meal_attendance_preview_response = client.post(
            "/api/kitchen/attendance/import/preview",
            data={"file": (handle, meal_attendance_source.name)},
            content_type="multipart/form-data",
        )
    assert meal_attendance_preview_response.status_code == 200, meal_attendance_preview_response.get_data(as_text=True)
    meal_attendance_preview = meal_attendance_preview_response.get_json()
    assert meal_attendance_preview["periods"] == ["2026-08"]
    assert meal_attendance_preview["counts"] == {
        "items": 205, "dates": 28, "kitchens": 6, "new": 205,
        "update": 0, "unchanged": 0, "warning": 0, "error": 0,
    }
    assert meal_attendance_preview["totals"] == {"actual": 6020, "ordered": 0}
    assert client.post(
        "/api/kitchen/attendance/import/confirm",
        json={"token": meal_attendance_preview["token"]},
    ).status_code == 400
    meal_attendance_confirm = client.post(
        "/api/kitchen/attendance/import/confirm",
        json={"token": meal_attendance_preview["token"], "confirmed": True},
    )
    assert meal_attendance_confirm.status_code == 200, meal_attendance_confirm.get_data(as_text=True)
    assert meal_attendance_confirm.get_json()["inserted"] == 205
    with server.db() as conn:
        meal_totals_by_kitchen = {
            row["kitchen"]: row["actual"]
            for row in conn.execute(
                """SELECT kitchen,SUM(actual_count) actual FROM meal_attendance
                   WHERE substr(work_date,1,7)='2026-08' GROUP BY kitchen"""
            )
        }
    assert meal_totals_by_kitchen == {
        "BOT": 1313, "DAINAM": 1433, "SUNBY": 874,
        "THACO": 1063, "TTS": 627, "VINA": 710,
    }
    with meal_attendance_source.open("rb") as handle:
        repeat_meal_attendance_response = client.post(
            "/api/kitchen/attendance/import/preview",
            data={"file": (handle, "renamed-meal-attendance.xlsx")},
            content_type="multipart/form-data",
        )
    repeat_meal_attendance = repeat_meal_attendance_response.get_json()
    assert repeat_meal_attendance["counts"]["unchanged"] == 205
    repeat_meal_confirm = client.post(
        "/api/kitchen/attendance/import/confirm",
        json={"token": repeat_meal_attendance["token"], "confirmed": True},
    )
    assert repeat_meal_confirm.status_code == 200
    assert repeat_meal_confirm.get_json()["unchanged"] == 205
    assert client.post(
        "/api/kitchen/attendance/import/preview",
        data={"file": (io.BytesIO(b"not-an-xlsx"), "bad.xlsx")},
        content_type="multipart/form-data",
    ).status_code == 400

    # Normalized kitchen/menu/cost/XCOM/PO manual flow remains backward compatible.
    assert client.put("/api/kitchen-units/POT", json={"xcom_code": "XCOM-POT"}).status_code == 200
    assert client.put("/api/dated-prices/I000060", json={
        "period": "2026-08", "price_group": "HATRAN", "price_value": 16000,
    }).status_code == 200
    meal = client.post("/api/kitchen/plans", json={
        "work_date": "2026-08-30", "kitchen": "POT", "shift": "Trưa", "meal_count": 100,
        "items": [{"dish_name": "Canh", "product_code": "I000060", "norm_qty": 0.08}],
    })
    assert meal.status_code == 200, meal.get_data(as_text=True)
    meal_id = meal.get_json()["id"]
    missing_meal_price = client.post(f"/api/kitchen/plans/{meal_id}/approve")
    assert missing_meal_price.status_code == 400 and "đơn giá suất ăn" in missing_meal_price.get_json()["error"]
    meal = client.post("/api/kitchen/plans", json={
        "id": meal_id, "work_date": "2026-08-30", "kitchen": "POT", "shift": "Trưa",
        "meal_count": 100, "meal_price": 25000,
        "items": [{"dish_name": "Canh", "product_code": "I000060", "norm_qty": 0.08}],
    })
    assert meal.status_code == 200, meal.get_data(as_text=True)
    assert client.post(f"/api/kitchen/plans/{meal_id}/approve").status_code == 200
    kitchen_po = client.get("/api/kitchen/po?date=2026-08-30")
    assert kitchen_po.status_code == 200 and len(kitchen_po.data) > 1000
    assert "PO_xuong_com_DA_DUYET_2026-08-30.xlsx" in kitchen_po.headers["Content-Disposition"]
    approved_po_book = load_workbook(io.BytesIO(kitchen_po.data), data_only=True)
    assert approved_po_book.active.cell(1, 1).value == "PO XƯỞNG CƠM – ĐÃ DUYỆT"
    approved_po_book.close()
    unmapped_plan = client.post("/api/kitchen/plans", json={
        "work_date": "2026-08-31", "kitchen": "CHUA-GHEP", "shift": "Trưa",
        "meal_count": 10, "meal_price": 25000,
        "items": [{"dish_name": "Canh", "product_code": "I000060", "norm_qty": 0.08}],
    })
    assert unmapped_plan.status_code == 200
    unmapped_approval = client.post(
        f"/api/kitchen/plans/{unmapped_plan.get_json()['id']}/approve"
    )
    assert unmapped_approval.status_code == 400 and "XCOM" in unmapped_approval.get_json()["error"]

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
    payroll_export = client.get("/api/export/payroll?month=2026-08")
    assert payroll_export.status_code == 200 and len(payroll_export.data) > 1000
    payroll_book = load_workbook(io.BytesIO(payroll_export.data), data_only=True)
    assert payroll_book.sheetnames == ["Bảng lương", "Chi phí theo bếp"]
    assert payroll_book["Bảng lương"]["A3"].value == "STT"
    assert any(
        row[1].value == "TRIEN" and round(row[16].value) == 8000000
        for row in payroll_book["Bảng lương"].iter_rows(min_row=4)
    )
    payroll_book.close()
    assert client.get("/api/export/payroll?month=2026-13").status_code == 400

    # Opening inventory workbook: safe preview/confirm, signed quantities, aggregation and rollback.
    with server.db() as conn:
        conn.execute(
            """INSERT INTO products(code,name,unit,supplier,buy_price)
               VALUES('QC-OPEN-ROLLBACK','Hàng rollback tồn đầu','kg','QC',10000)"""
        )
    rollback_opening_file = opening_workbook_bytes([
        ["QC-OPEN-NEW", "Hàng mới phải rollback", "", "QC-OPEN-NEW", "KKKNT", "kg", 2, 20000, 40000],
        ["QC-OPEN-ROLLBACK", "Hàng rollback tồn đầu", "", "QC-OPEN-ROLLBACK", "KKKNT", "kg", 1, 10000, 10000],
    ])
    rollback_opening = preview_opening(client, rollback_opening_file, period="2026-07").get_json()
    assert rollback_opening["can_confirm"] is True and rollback_opening["counts"]["new_products"] == 1
    with server.db() as conn:
        conn.execute("DELETE FROM products WHERE code='QC-OPEN-ROLLBACK'")
    rollback_opening_confirm = client.post(
        "/api/inventory/opening/import/confirm",
        json={"token": rollback_opening["token"], "confirmed": True},
    )
    assert rollback_opening_confirm.status_code == 409
    with server.db() as conn:
        assert not conn.execute("SELECT 1 FROM products WHERE code='QC-OPEN-NEW'").fetchone()
        assert conn.execute(
            "SELECT COUNT(*) n FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-07'"
        ).fetchone()["n"] == 0

    actual_opening_source = ROOT / "_HANDOFF" / "EXTERNAL_INPUTS" / "TĐK T8-2026.xlsx thụy.xlsx"
    actual_opening_result = "not_present"
    if actual_opening_source.exists():
        assert hashlib.sha256(actual_opening_source.read_bytes()).hexdigest().upper() == (
            "36DF2BA86D13307F96BB5944FCECB19A4A81C093B4AC6A98EA71330D68204DA6"
        )
        assert preview_opening(client, b"not-an-xlsx").status_code == 400
        assert preview_opening(client, actual_opening_source.read_bytes(), period="2026-13").status_code == 400
        with actual_opening_source.open("rb") as handle:
            actual_opening_response = client.post(
                "/api/inventory/opening/import/preview",
                data={"period": "2026-08", "file": (handle, actual_opening_source.name)},
                content_type="multipart/form-data",
            )
        assert actual_opening_response.status_code == 200, actual_opening_response.get_data(as_text=True)
        actual_opening = actual_opening_response.get_json()
        print("OPENING_PREVIEW", json.dumps(actual_opening["counts"], ensure_ascii=False))
        assert actual_opening["can_confirm"] is True
        assert actual_opening["counts"] == {
            "source_rows": 395, "items": 334, "new_products": 113,
            "new": 334, "update": 0, "negative": 4, "warning": 181, "error": 0,
        }
        assert abs(actual_opening["totals"]["qty"] - 101383.26) < 0.0001
        assert abs(actual_opening["totals"]["amount"] - 2419360717.80439) < 0.01
        c000021 = next(row for row in actual_opening["rows"] if row["product_code"] == "C000021")
        assert c000021["source_row_count"] == 3 and abs(c000021["qty"] - 79.97) < 0.0001
        d000056 = next(row for row in actual_opening["rows"] if row["product_code"] == "D000056")
        assert d000056["qty"] == -1.5 and any("âm" in warning for warning in d000056["warnings"])
        m000277 = next(row for row in actual_opening["rows"] if row["product_code"] == "M000277")
        assert any("Thành tiền lệch" in warning for warning in m000277["warnings"])
        k000066 = next(row for row in actual_opening["rows"] if row["product_code"] == "K000066")
        assert any("Tên trong file khác danh mục" in warning for warning in k000066["warnings"])
        assert client.post(
            "/api/inventory/opening/import/confirm", json={"token": actual_opening["token"]}
        ).status_code == 400
        actual_opening_confirm = client.post(
            "/api/inventory/opening/import/confirm",
            json={"token": actual_opening["token"], "confirmed": True},
        )
        assert actual_opening_confirm.status_code == 200, actual_opening_confirm.get_data(as_text=True)
        assert actual_opening_confirm.get_json()["inserted_products"] == 113
        assert actual_opening_confirm.get_json()["inserted"] == 334
        assert actual_opening_confirm.get_json()["updated"] == 0
        with server.db() as conn:
            opening_totals = conn.execute(
                """SELECT COUNT(*) n,SUM(qty_in-qty_out) qty,
                          SUM((qty_in-qty_out)*unit_cost) amount,
                          SUM(CASE WHEN qty_out>0 THEN 1 ELSE 0 END) negative
                   FROM inventory_transactions
                   WHERE source_type='OPENING' AND source_id='2026-08'
                     AND note LIKE 'Tồn đầu kỳ 2026-08 từ %'"""
            ).fetchone()
            assert opening_totals["n"] == 334 and opening_totals["negative"] == 4
            assert abs(opening_totals["qty"] - 101383.26) < 0.0001
            assert abs(opening_totals["amount"] - 2419360717.80439) < 0.01
            assert conn.execute("SELECT COUNT(*) n FROM products").fetchone()["n"] == 984
            assert conn.execute("SELECT name FROM products WHERE code='K000066'").fetchone()["name"] == "Thịt vịt xông khói"
            added_product = conn.execute(
                "SELECT name,unit,supplier FROM products WHERE code='HT00241'"
            ).fetchone()
            assert added_product and added_product["supplier"] == ""
        with actual_opening_source.open("rb") as handle:
            repeat_opening_response = client.post(
                "/api/inventory/opening/import/preview",
                data={"period": "2026-08", "file": (handle, "renamed-opening.xlsx")},
                content_type="multipart/form-data",
            )
        repeat_opening = repeat_opening_response.get_json()
        assert repeat_opening["counts"]["new_products"] == 0
        assert repeat_opening["counts"]["new"] == 0 and repeat_opening["counts"]["update"] == 334
        repeat_opening_confirm = client.post(
            "/api/inventory/opening/import/confirm",
            json={"token": repeat_opening["token"], "confirmed": True},
        )
        assert repeat_opening_confirm.status_code == 200
        assert repeat_opening_confirm.get_json()["inserted"] == 0
        assert repeat_opening_confirm.get_json()["updated"] == 334
        actual_opening_result = "395 rows / 334 TDP codes / signed quantity and VND value reconciled"

    # Multi-period debts, payment request and approval-gated print dry-run.
    debts = client.get("/api/debts?from=2026-08-01&to=2026-08-31")
    assert debts.status_code == 200 and "HATRAN" in debts.get_json()["contractors"]
    blank_settings = client.put("/api/document-settings", json={"payment_bank_account": ""})
    assert blank_settings.status_code == 200
    blocked_request = client.get("/api/export/payment-request/HATRAN?from=2026-08-01&to=2026-08-31")
    assert blocked_request.status_code == 409 and "Cấu hình" in blocked_request.get_json()["error"]
    restored_settings = client.put("/api/document-settings", json={
        "payment_requester": "VŨ THỊ THỤY",
        "payment_bank_name": "Ngân hàng TMCP Ngoại Thương Việt Nam",
        "payment_bank_account": "1052787580",
    })
    assert restored_settings.status_code == 200
    payment_request = client.get("/api/export/payment-request/HATRAN?from=2026-08-01&to=2026-08-31")
    assert payment_request.status_code == 200 and len(payment_request.data) > 1000
    payment_document = DocxDocument(io.BytesIO(payment_request.data))
    payment_text = "\n".join(
        [paragraph.text for paragraph in payment_document.paragraphs]
        + [cell.text for table in payment_document.tables for row in table.rows for cell in row.cells]
    )
    for required_text in (
        "ĐỀ NGHỊ THANH TOÁN", "CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT",
        "VŨ THỊ THỤY", "1052787580", "Ngân hàng TMCP Ngoại Thương Việt Nam",
        "TỔNG CỘNG", "Số tiền bằng chữ", "ĐẠI DIỆN CÔNG TY",
    ):
        assert required_text in payment_text, required_text
    assert "................................" not in payment_text
    prepared = client.post(f"/api/print/prepare/{manual_id}")
    assert prepared.status_code == 200, prepared.get_data(as_text=True)
    assert client.post(f"/api/print/approve/{manual_id}").status_code == 200
    print_dry_run = client.post(f"/api/print/run/{manual_id}", json={"dry_run": True})
    assert print_dry_run.status_code == 200 and print_dry_run.get_json()["jobs"] == 4

    operations = client.get("/api/operations/bootstrap?as_of=2026-08-31&month=2026-08&date=2026-08-30")
    assert operations.status_code == 200
    assert operations.get_json()["msmi"]["invoices"]
    assert operations.get_json()["meal_plans"]
    assert operations.get_json()["meal_attendance_totals"] == {
        "actual": 6020, "ordered": 0, "rows": 205, "kitchens": 6,
    }
    assert operations.get_json()["document_settings"] == {
        "requester": "VŨ THỊ THỤY",
        "bank_name": "Ngân hàng TMCP Ngoại Thương Việt Nam",
        "bank_account": "1052787580",
    }

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
        "kitchenWorkbookImport": "passed",
        "actualCustomerKitchenWorkbook": actual_kitchen_result,
        "actualMealAttendanceWorkbook": "205 daily kitchen/shift rows / 6,020 meals / repeat safe",
        "actualOpeningInventoryWorkbook": actual_opening_result,
        "actualCustomerCatalogWorkbook": catalog_import_result,
        "attendancePayrollLegacyImport": "passed",
        "paymentRequestAndPrintApproval": "passed",
    }, ensure_ascii=False, indent=2))
    print_dir = APP_DIR / "data" / "print_jobs" / str(manual_id)
    if print_dir.exists() and print_dir.resolve().is_relative_to((APP_DIR / "data" / "print_jobs").resolve()):
        rmtree(print_dir)
    payment_qc = APP_DIR / "data" / "qc_payment_request.docx"
    if payment_qc.exists() and payment_qc.parent.resolve() == (APP_DIR / "data").resolve():
        payment_qc.unlink()
    payment_render_qc = APP_DIR / "data" / "qc_payment_request_render"
    if payment_render_qc.exists() and payment_render_qc.resolve().is_relative_to((APP_DIR / "data").resolve()):
        rmtree(payment_render_qc)
    clean_test_db(qc_db)


if __name__ == "__main__":
    main()
