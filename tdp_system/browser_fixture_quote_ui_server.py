"""Isolated source server and workbooks for the TDP-051 quote UI browser smoke."""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from waitress import serve

from . import server


PRICE_HEADERS = (
    "ATV", "HATRAN", "BIADAUVOI", "NGUYENGIA", "SUPPY", "TOYOTA", "NHUAHAIPHONG",
)


def _write_workbook(path: Path, rows: list[dict]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BÁO GIÁ"
    sheet.append(["BẢNG BÁO GIÁ TỔNG"])
    sheet.append([
        "STT", "MÃ THAM CHIẾU", "MÃ HÀNG", "TÊN THÀNH ĐẠT PHÁT",
        "Giá mua", "NCC", None, "bk", "Tên làm bảng kê", "ĐVT", "THUẾ",
        *PRICE_HEADERS, "Thêm", "=L2",
    ])
    sheet.append([None, 1, 2, 3, 4, 5, None, 6, 7, 8, 9])
    for index, row in enumerate(rows, 1):
        sheet.append([
            index, f"{row['code']}S1", row["code"], row["name"], row["buy"], "S1",
            None, None, None, "kg", "8%", *row["prices"], None, "=1+1",
        ])
    workbook.save(path)
    workbook.close()


def _build_fixtures(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_workbook(output_dir / "quote-conflict.xlsx", [
        {"code": "P1", "name": "Hàng xung đột", "buy": 7_000,
         "prices": [10_000, 11_000, 12_000, 13_000, 14_000, 15_000, 16_000]},
        {"code": "P1", "name": "Hàng xung đột", "buy": 8_000,
         "prices": [10_000, 11_000, 12_000, 13_000, 14_000, 16_000, 16_000]},
    ])
    _write_workbook(output_dir / "quote-clean.xlsx", [
        {"code": "P1", "name": "Giá bằng không", "buy": 7_000,
         "prices": [10_000, 11_000, 12_000, 13_000, 14_000, 0, 16_000]},
        {"code": "P2", "name": "Giá Toyota", "buy": 8_000,
         "prices": [10_000, 11_000, 12_000, 13_000, 14_000, 16_000, 17_000]},
        {"code": "P3", "name": "Dòng chữ X", "buy": 9_000,
         "prices": [10_000, 11_000, 12_000, 13_000, 14_000, "X", 18_000]},
        {"code": "P4", "name": "Dòng để rỗng", "buy": 10_000,
         "prices": [10_000, 11_000, 12_000, 13_000, 14_000, None, 19_000]},
    ])


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18794
    output_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else server.DATA_DIR
    server.MASTER_SOURCE = output_dir / "master-disabled.xlsx"
    server.init_database()
    with server.db() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) "
            "VALUES(?,?,?,'group')",
            [(code, code, code) for code in PRICE_HEADERS],
        )
        conn.execute("INSERT OR REPLACE INTO suppliers(code,name) VALUES('S1','NCC smoke')")
        conn.executemany(
            """INSERT OR REPLACE INTO products(
                   code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
               ) VALUES(?,?,?,?,?,?,0,'','')""",
            [
                ("P1", "Giá bằng không", "kg", "8%", "S1", 7_000),
                ("P2", "Giá Toyota", "kg", "8%", "S1", 8_000),
                ("P3", "Dòng chữ X", "kg", "8%", "S1", 9_000),
                ("P4", "Dòng để rỗng", "kg", "8%", "S1", 10_000),
            ],
        )
    _build_fixtures(output_dir)
    serve(server.app, host="127.0.0.1", port=port, threads=4)


if __name__ == "__main__":
    main()
