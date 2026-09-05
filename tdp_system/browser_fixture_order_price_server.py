"""Temporary source server for the TDP-013 browser smoke."""

from __future__ import annotations

import sys

from waitress import serve

from . import server


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8771
    server.init_database()
    with server.db() as conn:
        conn.execute("DELETE FROM batches")
        conn.execute(
            "INSERT INTO contractors(code,name,price_group,pricing_mode) VALUES('C-BROWSER','C-BROWSER','C-BROWSER','group') "
            "ON CONFLICT(code) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO kitchens(code,contractor,name) VALUES('K-BROWSER','C-BROWSER','Kitchen browser') "
            "ON CONFLICT(code) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO products(code,name,unit,tax,supplier,buy_price,purchase_list)
               VALUES('P-PRICE-BROWSER','Price browser','kg','KKKNT','S-BROWSER',10000,0)
               ON CONFLICT(code) DO UPDATE SET name=excluded.name,unit=excluded.unit"""
        )
        conn.execute(
            "INSERT INTO suppliers(code,name) VALUES('S-BROWSER','Supplier browser') ON CONFLICT(code) DO NOTHING"
        )
        batch_id = int(conn.execute(
            "INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-09-01','Price browser fixture','draft',?)",
            (server.now_iso(),),
        ).lastrowid)
        conn.execute(
            """INSERT INTO orders(
                   batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                   actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
                   invoice_nature,purchase_list,errors,warnings,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, "2026-09-01", "C-BROWSER", "K-BROWSER", "P-PRICE-BROWSER",
                "Price browser", 2, 2, 2, "kg", "S-BROWSER", 10000, 12000,
                "KKKNT", "1", 0, "[]", "[]", server.now_iso(),
            ),
        )
    serve(server.app, host="127.0.0.1", port=port, threads=2)


if __name__ == "__main__":
    main()
