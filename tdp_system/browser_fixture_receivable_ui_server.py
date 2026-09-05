"""Temporary source server for TDP-042 receivable UI browser smoke."""

from __future__ import annotations

import sys

from waitress import serve

from . import server
from .receivable_ledger import sync_receivable_ledger


def _batch(conn, work_date: str, status: str) -> int:
    timestamp = server.now_iso()
    return int(conn.execute(
        """INSERT INTO batches(work_date,source_name,status,created_at,approved_at)
           VALUES(?,?,?,?,?)""",
        (
            work_date, "Receivable UI smoke", status, timestamp,
            timestamp if status == "approved" else None,
        ),
    ).lastrowid)


def _order(
    conn, batch_id: int, work_date: str, contractor: str, kitchen: str,
    product_code: str, product_name: str, ordered: float, delivered: float,
    returned: float, sell_price: int, tax: str,
) -> None:
    conn.execute(
        """INSERT INTO orders(
               batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
               actual_received,actual_delivered,unit,supplier,buy_price,sell_price,tax,
               purchase_list,source_sheet,source_row,errors,warnings,updated_at,
               customer_return_qty
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            batch_id, work_date, contractor, kitchen, product_code, product_name,
            ordered, ordered, delivered, "kg", "S1", 5_000, sell_price, tax, 0,
            "đơn hàng", 3, "[]", "[]", server.now_iso(), returned,
        ),
    )


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18791
    server.init_database()
    with server.db() as conn:
        for table in (
            "receivable_ledger_revisions", "receivable_ledger_lines",
            "outgoing_invoice_lines", "outgoing_invoice_drafts", "order_import_receipts",
            "orders", "batches", "debt_adjustments", "payments", "balances",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute(
            "INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) "
            "VALUES('C1','Nhà thầu Một','C1','group')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO contractors(code,name,price_group,pricing_mode) "
            "VALUES('C2','Nhà thầu Hai','C2','group')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kitchens(code,contractor,name) VALUES('K1','C1','Bếp Một')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kitchens(code,contractor,name) VALUES('K2','C1','Bếp Hai')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO kitchens(code,contractor,name) VALUES('K3','C2','Bếp Ba')"
        )
        conn.execute("INSERT OR REPLACE INTO suppliers(code,name) VALUES('S1','NCC Một')")
        first = _batch(conn, "2026-09-01", "approved")
        second = _batch(conn, "2026-09-15", "approved")
        third = _batch(conn, "2026-09-20", "approved")
        draft = _batch(conn, "2026-09-25", "draft")
        _order(conn, first, "2026-09-01", "C1", "K1", "P1", "Cà rốt", 10, 8, 2, 10_000, "10%")
        _order(conn, second, "2026-09-15", "C1", "K2", "P2", "Bí ngòi", 5, 5, 0, 10_000, "0%")
        _order(conn, third, "2026-09-20", "C2", "K3", "P3", "Khoai tây", 2, 2, 0, 20_000, "0%")
        _order(conn, draft, "2026-09-25", "C1", "K1", "P4", "Dòng nháp", 1, 1, 0, 10_000, "0%")
        sync_receivable_ledger(conn, timestamp=server.now_iso())
        conn.execute(
            """INSERT INTO balances(party_type,party_code,opening,as_of_date)
               VALUES('contractor','C1',100000,'2026-08-31')"""
        )
        timestamp = server.now_iso()
        conn.execute(
            """INSERT INTO payments(
                   payment_date,kind,party_type,party_code,amount,note,created_at,updated_at
               ) VALUES('2026-09-10','receipt','contractor','C1',30000,'Khách đã thu',?,?)""",
            (timestamp, timestamp),
        )
        conn.execute(
            """INSERT INTO payments(
                   payment_date,kind,party_type,party_code,amount,note,created_at,updated_at
               ) VALUES('2026-09-11','payment','contractor','C1',999000,
                        'Sai loại phải bỏ qua',?,?)""",
            (timestamp, timestamp),
        )
        conn.execute(
            """INSERT INTO debt_adjustments(
                   adjustment_date,party_type,party_code,amount,note,created_at
               ) VALUES('2026-09-18','contractor','C1',-5000,'Giảm trừ',?)""",
            (timestamp,),
        )
    serve(server.app, host="127.0.0.1", port=port, threads=4)


if __name__ == "__main__":
    main()
