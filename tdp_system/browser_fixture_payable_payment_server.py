"""Temporary source server with one payable line for TDP-031 HTTP smoke."""

from __future__ import annotations

import sys

from waitress import serve

from . import server
from .payable_ledger import sync_payable_ledger


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18786
    server.init_database()
    with server.db() as conn:
        conn.execute("DELETE FROM payable_payment_revisions")
        conn.execute("DELETE FROM payable_payment_allocations")
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM payable_ledger_revisions")
        conn.execute("DELETE FROM payable_ledger_lines")
        conn.execute("DELETE FROM purchase_workbook_line_revisions")
        conn.execute("DELETE FROM purchase_workbook_lines")
        conn.execute("DELETE FROM purchase_order_imports")
        conn.execute("DELETE FROM purchase_order_lines")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM batches")
        conn.execute("DELETE FROM historical_payable_lines")
        conn.execute("DELETE FROM settings WHERE key='historical_payables_through_date'")
        conn.execute(
            "INSERT OR REPLACE INTO suppliers(code,name) VALUES('S-PAY','NCC thanh toán smoke')"
        )
        timestamp = server.now_iso()
        batch_id = int(conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES('2026-09-01','Payable payment smoke','approved',?,?)""",
            (timestamp, timestamp),
        ).lastrowid)
        conn.execute(
            """INSERT INTO purchase_workbook_lines(
                   batch_id,row_key,source_sheet,source_row,product_code,kitchen,work_date,
                   product_name,base_qty,unit,supplier,note,buy_price,price_source,
                   damaged_qty,added_qty,reduced_qty,missing_qty,actual_qty,amount,status,
                   source_hash,revision,created_at,updated_at
               ) VALUES(?,'PAY-SMOKE','đặt hàng',3,'P-PAY','K-PAY','2026-09-01',
                        'Hàng thanh toán smoke',2,'kg','S-PAY','',50,'fixture',
                        0,0,0,0,2,100,'confirmed','PAY-SMOKE-HASH',1,?,?)""",
            (batch_id, timestamp, timestamp),
        )
        sync_payable_ledger(conn, timestamp=timestamp)
    serve(server.app, host="127.0.0.1", port=port, threads=2)


if __name__ == "__main__":
    main()
