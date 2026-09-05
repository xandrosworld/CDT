"""Temporary source server and canonical sheet fixture for TDP-020/021 smoke."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from waitress import serve

from . import server


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18773
    fixture_path = Path(os.environ["TDP_BROWSER_PURCHASE_FILE"])
    server.init_database()
    with server.db() as conn:
        conn.execute("DELETE FROM purchase_workbook_lines")
        conn.execute("DELETE FROM purchase_order_imports")
        conn.execute("DELETE FROM purchase_order_lines")
        conn.execute("DELETE FROM batches")
        conn.execute(
            "INSERT INTO contractors(code,name,price_group,pricing_mode) "
            "VALUES('C-BRIDGE','Contractor bridge','C-BRIDGE','group') "
            "ON CONFLICT(code) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO kitchens(code,contractor,name) VALUES('K-BRIDGE','C-BRIDGE','Kitchen bridge') "
            "ON CONFLICT(code) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO suppliers(code,name) VALUES('S-BRIDGE','Supplier bridge') "
            "ON CONFLICT(code) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO products(code,name,unit,tax,supplier,buy_price,purchase_list)
               VALUES('P-BRIDGE','Product bridge','kg','KKKNT','S-BRIDGE',0,0)
               ON CONFLICT(code) DO UPDATE SET name=excluded.name,unit=excluded.unit"""
        )
        timestamp = server.now_iso()
        batch_id = int(conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES('2026-09-01','Purchase bridge fixture','approved',?,?)""",
            (timestamp, timestamp),
        ).lastrowid)
        conn.execute(
            """INSERT INTO orders(
                   batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                   actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
                   invoice_nature,purchase_list,errors,warnings,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, "2026-09-01", "C-BRIDGE", "K-BRIDGE", "P-BRIDGE",
                "Product bridge", 10, 10, 10, "kg", "S-BRIDGE", 0, 30000,
                "KKKNT", "1", 0, "[]", "[]", timestamp,
            ),
        )
        batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        orders = [dict(row) for row in conn.execute(
            "SELECT * FROM orders WHERE batch_id=? ORDER BY id", (batch_id,)
        )]
        workbook = server.export_supplier_orders(conn, batch, orders)
        sheet = workbook["đặt hàng"]
        sheet.cell(3, 6, 7)
        sheet.cell(3, 8, "S-BRIDGE")
        sheet.cell(3, 9, "Browser checked physical stock")
        sheet.cell(3, 10, 50000)
        sheet.cell(3, 11, 1)
        sheet.cell(3, 12, 3)
        sheet.cell(3, 13, 1)
        sheet.cell(3, 14, 0)
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(fixture_path)
        workbook.close()
    serve(server.app, host="127.0.0.1", port=port, threads=2)


if __name__ == "__main__":
    main()
