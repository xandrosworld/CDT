"""Temporary source server with supplier-merge fixtures for TDP-022 smoke."""

from __future__ import annotations

import sys

from waitress import serve

from . import server


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18774
    server.init_database()
    with server.db() as conn:
        conn.execute("DELETE FROM invoice_inventory_ledger")
        conn.execute("DELETE FROM invoice_inventory_confirmations")
        conn.execute("DELETE FROM outgoing_invoice_lines")
        conn.execute("DELETE FROM outgoing_invoice_drafts")
        conn.execute("DELETE FROM inventory_transactions")
        conn.execute("DELETE FROM purchase_workbook_line_revisions")
        conn.execute("DELETE FROM purchase_workbook_lines")
        conn.execute("DELETE FROM purchase_order_imports")
        conn.execute("DELETE FROM purchase_order_lines")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM batches")
        conn.execute("DELETE FROM supplier_rules")
        timestamp = server.now_iso()
        batch_id = int(conn.execute(
            """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
               VALUES('2026-09-01','Supplier merge browser fixture','approved',?,?)""",
            (timestamp, timestamp),
        ).lastrowid)
        conn.execute(
            "INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) "
            "VALUES('BROWSER-CUSTOMER','Khách smoke','BROWSER-CUSTOMER','group')"
        )
        conn.execute(
            """INSERT OR REPLACE INTO kitchens(code,contractor,name,address,show_price)
               VALUES('BROWSER-KITCHEN','BROWSER-CUSTOMER','Bếp smoke','',0)"""
        )
        conn.execute(
            """INSERT OR REPLACE INTO products(
                   code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
               ) VALUES('P-BROWSER-SALES','Cà rốt smoke','kg','0%','DUNG',0,0,'','')"""
        )
        conn.execute(
            """INSERT INTO orders(
                   batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                   actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
                   purchase_list,note,errors,warnings,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'','[]','[]',?)""",
            (
                batch_id, "2026-09-01", "BROWSER-CUSTOMER", "BROWSER-KITCHEN",
                "P-BROWSER-SALES", "Cà rốt smoke", 10, 10, 10, "kg", "DUNG",
                0, 30000, "0%", timestamp,
            ),
        )
        conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,qty_in,qty_out,unit_cost,source_type,
                   source_id,source_line,status,note,created_at,updated_at
               ) VALUES('2026-08-31','P-BROWSER-SALES',12,0,10000,'OPENING',
                        'BROWSER-OPENING','1','posted','browser opening',?,?)""",
            (timestamp, timestamp),
        )
        confirmation_id = int(conn.execute(
            """INSERT INTO invoice_inventory_confirmations(
                   confirmation_key,direction,source_invoice_table,source_invoice_id,
                   action,confirmed,note,created_at
               ) VALUES('browser-input-post','input','msmi_invoices',98001,
                        'post',1,'browser fixture',?)""",
            (timestamp,),
        ).lastrowid)
        conn.execute(
            """INSERT INTO invoice_inventory_ledger(
                   event_key,direction,event_type,source_invoice_table,source_invoice_id,
                   source_line_id,source_line_index,product_code,txn_date,qty_delta,
                   unit_cost,mapping_revision_id,confirmation_id,reverses_event_key,
                   status,created_at
               ) VALUES('browser-ledger-post','input','POST','msmi_invoices',98001,
                        98101,1,'P-BROWSER-SALES','2026-09-01',40,12000,NULL,?,'',
                        'posted',?)""",
            (confirmation_id, timestamp),
        )
        fixtures = [
            ("Nhà Dũng", "POT", "Cà rốt", 2, "Giao trước 06:00"),
            ("DUNG", "BIA", "cà rốt", 3, ""),
            ("NHÀ HOÀI", "POT", "CÀ-RỐT", 4, "Loại 1"),
            ("hoài", "BIA", "cà rốt", 5, ""),
            ("Nhà Hoài", "POT", "Rau muống", 6, ""),
            ("HOÀI", "BIA", "rau MUỐNG", 7, ""),
            ("HƯƠNG", "POT", "Hành lá", 8, "Không dập lá"),
            ("Nhà Hương", "BIA", "hành LÁ", 9, ""),
        ]
        for index, (supplier, kitchen, product_name, qty, note) in enumerate(fixtures, start=1):
            conn.execute(
                """INSERT INTO purchase_workbook_lines(
                       batch_id,row_key,source_sheet,source_row,product_code,kitchen,
                       work_date,product_name,base_qty,unit,supplier,note,buy_price,
                       actual_qty,amount,source_hash,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    batch_id, f"browser-raw-{index}", "đặt hàng", index + 2,
                    f"P-BROWSER-{index}", kitchen, "2026-09-01", product_name,
                    qty, "kg", supplier, note, 1000, qty, qty * 1000,
                    "supplier-merge-browser", timestamp, timestamp,
                ),
            )
    serve(server.app, host="127.0.0.1", port=port, threads=2)


if __name__ == "__main__":
    main()
