"""Temporary source server and workbooks for the TDP-012 browser smoke."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from waitress import serve

from . import server


def write_workbook(path: Path, *, actual_delivered: int, sell_price: int,
                   damaged: int, added: int) -> None:
    workbook = Workbook()
    day_sheet = workbook.active
    day_sheet.title = "01.09"
    day_sheet.append(["ĐƠN HÀNG NGÀY"])
    day_sheet.append([
        "Ngày", "Nhà thầu", "Mã bếp", "Mã hàng", "Tên hàng", "Số lượng",
        "Thực giao", "ĐVT", "Chọn NCC", "Giá mua", "Giá bán",
    ])
    day_sheet.append([
        date(2026, 9, 1), "TDP-FINAL-C1", "TDP-FINAL-K1", "TDP-FINAL-P1",
        "Cà rốt", 10, actual_delivered, "kg", "TDP-FINAL-S1", 0, sell_price,
    ])
    purchase = workbook.create_sheet("đặt hàng")
    purchase.append(["ĐẶT NHÀ CUNG CẤP"])
    purchase.append([
        "Mã hàng", "Mã bếp", "Ngày", "Tên hàng", "Số lượng", "ĐVT", "NCC",
        "ghi chú", "giá mua", "hỏng", "thêm", "Giảm", "thiếu",
        "SL thực tế", "Thành tiền",
    ])
    actual = 10 + added - damaged
    purchase.append([
        "TDP-FINAL-P1", "TDP-FINAL-K1", date(2026, 9, 1), "Cà rốt", 10,
        "kg", "TDP-FINAL-S1", "Chốt mua", 9000, damaged, added, 0, 0,
        actual, actual * 9000,
    ])
    workbook.save(path)
    workbook.close()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18778
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else server.EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    server.init_database()
    with server.db() as conn:
        conn.execute("DELETE FROM purchase_workbook_line_revisions")
        conn.execute("DELETE FROM purchase_workbook_lines")
        conn.execute("DELETE FROM purchase_order_imports")
        conn.execute("DELETE FROM purchase_order_lines")
        conn.execute("DELETE FROM order_import_receipts")
        conn.execute("DELETE FROM batches")
        conn.execute(
            "INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) "
            "VALUES('TDP-FINAL-C1','Khách chốt ngày','TDP-FINAL-C1','daily')"
        )
        conn.execute(
            """INSERT OR REPLACE INTO kitchens(code,contractor,name,address,show_price)
               VALUES('TDP-FINAL-K1','TDP-FINAL-C1','Bếp chốt ngày','',0)"""
        )
        conn.execute(
            "INSERT OR REPLACE INTO suppliers(code,name) "
            "VALUES('TDP-FINAL-S1','Nhà cung cấp chốt ngày')"
        )
        conn.execute(
            """INSERT OR REPLACE INTO products(
                   code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
               ) VALUES('TDP-FINAL-P1','Cà rốt','kg','0%','TDP-FINAL-S1',0,0,'','')"""
        )
    write_workbook(
        output_dir / "TDP012_initial.xlsx",
        actual_delivered=10, sell_price=12000, damaged=0, added=0,
    )
    write_workbook(
        output_dir / "TDP012_final.xlsx",
        actual_delivered=8, sell_price=16000, damaged=1, added=2,
    )
    serve(server.app, host="127.0.0.1", port=port, threads=2)


if __name__ == "__main__":
    main()
