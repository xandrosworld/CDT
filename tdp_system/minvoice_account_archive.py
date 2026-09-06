"""Explicit, fingerprint-checked preservation of the previous test connection.

Never run on startup. The operator supplies a manifest from the snapshot and
verifies the previous configured host before invoking this one-time operation.
"""
import hashlib
import json

ARCHIVE_SOURCE = "minvoice_test_0106026495_999"
TEST_HOST = "https://0106026495-999.minvoice.site"


def fingerprint(row):
    return hashlib.sha256(json.dumps(dict(row), sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def archive_legacy_test_account(conn, manifest, *, previous_base_url, now):
    if previous_base_url.rstrip("/") != TEST_HOST:
        raise ValueError("Chưa xác minh đúng kết nối kiểm thử cũ")
    conn.execute("SAVEPOINT archive_minvoice_account")
    try:
        rows = conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice' ORDER BY id").fetchall()
        actual = {str(row["id"]): fingerprint(row) for row in rows}
        if not manifest or actual != manifest:
            raise ValueError("Dữ liệu đầu ra thay đổi sau snapshot; cần đối chiếu lại")
        if any(json.loads(row["raw_json"]).get("_tdp_source_contract") for row in rows):
            raise ValueError("Có hóa đơn từ kết nối mới; không lưu trữ chung với nguồn thử")
        if (conn.execute("SELECT 1 FROM invoice_inventory_ledger WHERE direction='output' LIMIT 1").fetchone()
                or conn.execute("SELECT 1 FROM outgoing_invoice_drafts LIMIT 1").fetchone()
                or conn.execute("SELECT 1 FROM invoice_line_mappings WHERE invoice_type='OUTPUT_ELECTRONIC_INVOICE' LIMIT 1").fetchone()):
            raise ValueError("Nguồn cũ có liên kết nghiệp vụ; cần đối chiếu trước khi đổi tài khoản")
        conn.execute("UPDATE outgoing_source_invoices SET source=? WHERE source='minvoice'", (ARCHIVE_SOURCE,))
        conn.execute("UPDATE invoice_sync_batches SET source=?,request_key=?||request_key WHERE source='minvoice'",
                     (ARCHIVE_SOURCE, ARCHIVE_SOURCE + ":"))
        conn.execute("INSERT INTO settings(key,value) VALUES('minvoice_active_connection','portal') ON CONFLICT(key) DO UPDATE SET value='portal'")
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
                        VALUES('minvoice.archive_test_account','connector','minvoice','ok',?,?,?)""",
                     ("Giữ dữ liệu kết nối thử trong lịch sử riêng khi chuyển sang portal công ty",
                      json.dumps({"archived_invoices": len(rows), "previous_host": TEST_HOST,
                                  "manifest_hash": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()}), now))
        conn.execute("RELEASE SAVEPOINT archive_minvoice_account")
        return {"archived_invoices": len(rows), "source": ARCHIVE_SOURCE}
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT archive_minvoice_account")
        conn.execute("RELEASE SAVEPOINT archive_minvoice_account")
        raise


def archive_html(conn):
    from html import escape
    rows = conn.execute("""SELECT i.invoice_series,i.invoice_number,i.invoice_date,i.buyer_name,
                                  l.source_item_name,l.source_unit,l.qty,l.unit_price,l.amount
                           FROM outgoing_source_invoices i LEFT JOIN outgoing_source_invoice_items l ON l.invoice_id=i.id
                           WHERE i.source=? ORDER BY i.invoice_date,i.invoice_series,i.invoice_number,l.line_index""",
                        (ARCHIVE_SOURCE,)).fetchall()
    body = "".join("<tr>" + "".join("<td>" + escape(str(v if v is not None else "")) + "</td>" for v in row) + "</tr>" for row in rows)
    return ('<!doctype html><html lang="vi"><meta charset="utf-8"><title>Lịch sử kết nối M-Invoice cũ</title>'
            '<style>body{font:16px Arial;margin:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px}th{position:sticky;top:0;background:white}</style>'
            '<h1>Lịch sử kết nối M-Invoice cũ · chỉ xem</h1><p>Dữ liệu đã tải từ máy chủ kiểm thử trước khi chuyển tài khoản. '
            'Không cộng vào hóa đơn công ty, công nợ VAT hoặc kho hóa đơn. Số liệu nguồn được giữ nguyên.</p>'
            '<table><thead><tr>' + ''.join('<th>'+x+'</th>' for x in ['Ký hiệu','Số hóa đơn','Ngày','Người mua','Tên hàng','ĐVT','Số lượng','Đơn giá','Thành tiền'])
            + '</tr></thead><tbody>' + body + '</tbody></table></html>')
