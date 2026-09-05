"""Temporary source server for TDP-033 payable UI browser smoke."""

from __future__ import annotations

import sys

from waitress import serve

from . import server
from .payable_ledger import sync_payable_ledger


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18788
    server.init_database()
    with server.db() as conn:
        for table in (
            "payable_payment_revisions", "payable_payment_allocations", "payments",
            "payable_ledger_revisions", "payable_ledger_lines",
            "purchase_workbook_line_revisions", "purchase_workbook_lines",
            "purchase_order_imports", "purchase_order_lines", "orders", "batches",
            "historical_payable_lines",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM settings WHERE key='historical_payables_through_date'")
        conn.execute("INSERT OR REPLACE INTO suppliers(code,name) VALUES('S1','NCC Một')")
        conn.execute("INSERT OR REPLACE INTO suppliers(code,name) VALUES('S2','NCC Hai')")
        timestamp = server.now_iso()
        batch_id = int(conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES('2026-09-01','Payable UI smoke','approved',?,?)""",
            (timestamp, timestamp),
        ).lastrowid)
        fixtures = (
            ("UI-S1-A", "S1", "Hàng S1 A", 2, 50_000, 100_000),
            ("UI-S1-B", "S1", "Hàng S1 B", 4, 50_000, 200_000),
            ("UI-S2-A", "S2", "Hàng S2 A", 6, 50_000, 300_000),
        )
        for row_number, (row_key, supplier, name, qty, price, amount) in enumerate(fixtures, 3):
            conn.execute(
                """INSERT INTO purchase_workbook_lines(
                       batch_id,row_key,source_sheet,source_row,product_code,kitchen,work_date,
                       product_name,base_qty,unit,supplier,note,buy_price,price_source,
                       damaged_qty,added_qty,reduced_qty,missing_qty,actual_qty,amount,status,
                       source_hash,revision,created_at,updated_at
                   ) VALUES(?,?,'đặt hàng',?,?, 'BẾP-UI','2026-09-01',?,?,'kg',?,'',?,
                            'fixture',0,0,0,0,?,?,'confirmed',?,1,?,?)""",
                (
                    batch_id, row_key, row_number, f"P-{row_key}", name, qty,
                    supplier, price, qty, amount, f"HASH-{row_key}", timestamp, timestamp,
                ),
            )
        sync_payable_ledger(conn, timestamp=timestamp)
    serve(server.app, host="127.0.0.1", port=port, threads=4)


if __name__ == "__main__":
    main()
