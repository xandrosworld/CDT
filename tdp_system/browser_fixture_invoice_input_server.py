"""Temporary source-server fixture used only by the TDP-070 browser smoke."""

from __future__ import annotations

import sys

from waitress import serve

from . import server
from .contract_modules import upsert_msmi_invoice
from .test_msmi_sync import remote_invoice


class BrowserFixtureMsmi:
    def __init__(self):
        self.items = [remote_invoice(31), remote_invoice(1)]
        for item in self.items:
            item["tenNban"] = "NCC kiểm thử"

    def list_invoices(self, *, invoice_type, page, size, from_date, to_date):
        if (from_date, to_date) != ("2026-08-01", "2026-08-31"):
            raise AssertionError("browser fixture requires the inclusive August range")
        if invoice_type == "INPUT_ELECTRONIC_INVOICE":
            items = self.items
        elif invoice_type == "OUTPUT_ELECTRONIC_INVOICE":
            items = []
            for index, source in enumerate(self.items, start=1):
                item = dict(source)
                item.update({
                    "_id": f"OUTPUT-BROWSER-{index}",
                    "khhdon": "OUT-BROWSER",
                    "shdon": str(index),
                    "mstNmua": "0209999999",
                    "tenNmua": "Khách đầu ra kiểm thử",
                    "fixtureStatus": "FIXTURE_ISSUED",
                })
                items.append(item)
        else:
            raise AssertionError("browser fixture received an unsupported invoice type")
        start = page * size
        selected = items[start:start + size]
        return {
            "items": selected,
            "page": page,
            "size": size,
            "has_more": start + len(selected) < len(items),
        }


class BrowserFixtureMinvoice:
    def __init__(self):
        self.items = []
        for index, source in enumerate((remote_invoice(31), remote_invoice(1)), start=1):
            self.items.append({
                "id": f"MINVOICE-BROWSER-{index}",
                "hoadon68_id": f"AUTH-BROWSER-{index}",
                "inv_invoiceIssuedDate": source["tdlap"],
                "inv_invoiceSeries": "1C26TDP",
                "inv_invoiceNumber": index,
                "shdon": index,
                "inv_buyerTaxCode": "0209999999",
                "inv_buyerLegalName": "Khách đầu ra kiểm thử",
                "tgtcthue": source["tgtcthue"],
                "tgtthue": source["tgtthue"],
                "tgtttbso": source["tgtttbso"],
                "is_tthdon": 0,
                "trang_thai": 4,
                "tthai": "Đã gửi",
                "details": [
                    {
                        "inv_itemCode": line.get("ma"),
                        "inv_itemName": line.get("ten"),
                        "inv_unitCode": line.get("dvtinh"),
                        "inv_quantity": line.get("sluong"),
                        "inv_unitPrice": line.get("dgia"),
                        "inv_TotalAmountWithoutVat": line.get("thtien"),
                        "ma_thue": line.get("tsuat"),
                        "tchat": line.get("tchat"),
                    }
                    for line in source.get("hdhhdvu", [])
                ],
            })

    def get_invoice_series(self):
        return [{"value": "1C26TDP", "invoiceYear": 26, "invoiceForm": "1"}]

    def get_outgoing_invoices(
        self, start_date, end_date, series, start=0, count=300, include_details=True,
    ):
        if (start_date, end_date) != ("2026-08-01", "2026-08-31"):
            raise AssertionError("browser fixture requires the inclusive August range")
        if series != "1C26TDP" or not include_details:
            raise AssertionError("browser fixture requires the M-Invoice series and details")
        selected = self.items[start:start + count]
        return {"ok": True, "code": "00", "data": selected, "total": len(self.items)}


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
    server.app.config["MSMI_CLIENT_FACTORY"] = BrowserFixtureMsmi
    server.app.config["MINVOICE_CLIENT_FACTORY"] = BrowserFixtureMinvoice
    server.init_database()
    with server.db() as conn:
        outside = remote_invoice(30)
        outside.update({
            "_id": "MSMI-OUTSIDE-BOUNDED-BATCH",
            "tdlap": "2026-07-30",
            "tenNban": "NCC NGOÀI PHẠM VI",
        })
        upsert_msmi_invoice(
            conn, outside, "INPUT_ELECTRONIC_INVOICE", "TDP", server.now_iso(),
        )
        conn.execute(
            """INSERT INTO products(code,name,unit,tax,buy_price,purchase_list)
               VALUES('P-BROWSER','Sản phẩm ghép bằng bàn phím','kg','8%',10000,0)
               ON CONFLICT(code) DO UPDATE SET name=excluded.name,unit=excluded.unit"""
        )
        conn.execute(
            """INSERT INTO products(code,name,unit,tax,buy_price,purchase_list)
               VALUES('P-BROWSER-BOX','Sản phẩm quy đổi bằng bàn phím','thùng','8%',10000,0)
               ON CONFLICT(code) DO UPDATE SET name=excluded.name,unit=excluded.unit"""
        )
        conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                   source_line,status,note,created_at,updated_at
               ) VALUES('2026-08-01','P-BROWSER-BOX',1000,0,10000,'OPENING',
                        'BROWSER-FIXTURE-2026-08','1','posted','Browser smoke fixture',?,?)
               ON CONFLICT(source_type,source_id,source_line) DO NOTHING""",
            (server.now_iso(), server.now_iso()),
        )
    serve(server.app, host="127.0.0.1", port=port, threads=2)


if __name__ == "__main__":
    main()
