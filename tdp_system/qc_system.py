from __future__ import annotations

import io
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))
import server  # noqa: E402


def clean_test_db(path: Path):
    for suffix in ("", "-wal", "-shm"):
        target = Path(str(path) + suffix)
        if target.exists():
            target.unlink()


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

    export_sizes = {}
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
                        assert round(ws.cell(row, 8).value) == round(ws.cell(row, 5).value * ws.cell(row, 7).value)
                        if ws.cell(row, 9).value == "KKKNT":
                            assert round(ws.cell(row, 10).value) == round(ws.cell(row, 8).value)
                        else:
                            assert round(ws.cell(row, 10).value) == round(
                                ws.cell(row, 8).value * (1 + ws.cell(row, 9).value)
                            )

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
    }, ensure_ascii=False, indent=2))
    clean_test_db(qc_db)


if __name__ == "__main__":
    main()
