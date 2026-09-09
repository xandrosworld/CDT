"""Review issued invoices on an isolated copy, then explicitly post one group."""
import hashlib
import json
import sqlite3
from decimal import Decimal

try:
    from .invoice_inventory import InvoiceInventoryError, post_output_invoice
except ImportError:
    from invoice_inventory import InvoiceInventoryError, post_output_invoice


def output_review(conn, invoice_id, tenant):
    row = conn.execute("SELECT * FROM outgoing_source_invoices WHERE id=? AND tenant=? AND source='minvoice'",
                       (invoice_id, tenant)).fetchone()
    if not row:
        raise InvoiceInventoryError('Không tìm thấy hóa đơn đầu ra trong phạm vi này', status=404)
    header = dict(row)
    for key in ('stock_status', 'updated_at'):
        header.pop(key, None)
    items = [dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY id', (invoice_id,))]
    products = [dict(r) for r in conn.execute('SELECT code,name,unit FROM products WHERE code IN (SELECT product_code FROM outgoing_source_invoice_items WHERE invoice_id=?) ORDER BY code', (invoice_id,))]
    rules = [dict(r) for r in conn.execute("SELECT * FROM invoice_line_mappings WHERE tenant=? AND source='minvoice' AND partner_key=? ORDER BY id", (tenant, row['buyer_tax_code']))]
    token = hashlib.sha256(json.dumps(['invoice-source-quantity-v1', header, items, products, rules], sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    quantities, amount = {}, Decimal(0)
    eligible = [r for r in items if r['inventory_eligible']]
    for item in eligible:
        unit = item['source_unit']
        quantities[unit] = quantities.get(unit, Decimal(0)) + Decimal(str(item['qty'] or 0))
        amount += Decimal(str(item['amount'] or 0))
    return {'id': invoice_id, 'token': token, 'number': row['invoice_series'] + ' / ' + row['invoice_number'],
            'date': row['invoice_date'], 'seller': row['buyer_name'], 'line_count': len(eligible),
            'amount': float(row['subtotal']), 'detail_amount': float(amount),
            'qty_by_unit': {k: float(v) for k, v in quantities.items()}}


def preview_outputs(conn, ids, tenant, now_iso):
    if not isinstance(ids, list) or not 1 <= len(ids) <= 500 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise InvoiceInventoryError('Chọn từ 1 đến 500 hóa đơn khác nhau; thu hẹp bộ lọc nếu cần.', status=400)
    copy = sqlite3.connect(':memory:')
    copy.row_factory = sqlite3.Row
    conn.backup(copy)
    ready, blocked = [], []
    try:
        rows = sorted((output_review(copy, i, tenant) for i in ids), key=lambda r: (r['date'], r['id']))
        for row in rows:
            try:
                result = post_output_invoice(copy, row['id'], confirmed=True, now_iso=now_iso)
                if result['idempotent']:
                    blocked.append({'id': row['id'], 'number': row['number'], 'reason': 'Hóa đơn đã xuất kho.'})
                else:
                    ready.append(row)
                # Keep successful simulated issues: two invoices cannot each
                # consume the same stock. The source connection is never written.
            except InvoiceInventoryError as error:
                blocked.append({'id': row['id'], 'number': row['number'], 'reason': str(error)})
    finally:
        copy.close()
    return {'items': ready, 'blocked': blocked}


def post_outputs(conn, selection, tenant, now_iso, *, confirmed):
    if confirmed is not True:
        raise InvoiceInventoryError('Cần xác nhận rõ trước khi ghi xuất kho.', status=400, code='confirmation_required')
    if not isinstance(selection, list) or not 1 <= len(selection) <= 500 or any(
        not isinstance(r, dict) or type(r.get('id')) is not int or not isinstance(r.get('token'), str) for r in selection
    ):
        raise InvoiceInventoryError('Danh sách xác nhận không hợp lệ; mở lại bảng kiểm tra.', status=400)
    if len({r['id'] for r in selection}) != len(selection):
        raise InvoiceInventoryError('Danh sách có hóa đơn trùng.', status=400)
    conn.execute('SAVEPOINT output_group')
    try:
        reviewed = []
        for selected in selection:
            current = output_review(conn, selected['id'], tenant)
            if current['token'] != selected['token']:
                raise InvoiceInventoryError('Hóa đơn ' + current['number'] + ' đã thay đổi. Chưa xuất nhóm này; mở lại bảng kiểm tra.', code='stale_review')
            reviewed.append(current)
        results = []
        for row in sorted(reviewed, key=lambda r: (r['date'], r['id'])):
            try:
                results.append(post_output_invoice(conn, row['id'], confirmed=True, now_iso=now_iso))
            except InvoiceInventoryError as error:
                raise InvoiceInventoryError('Hóa đơn ' + row['number'] + ': ' + str(error) + '. Chưa xuất nhóm này.', code=error.code) from error
        conn.execute('RELEASE output_group')
        return {'items': results, 'posted_count': sum(not r['idempotent'] for r in results),
                'already_posted_count': sum(r['idempotent'] for r in results)}
    except Exception:
        conn.execute('ROLLBACK TO output_group')
        conn.execute('RELEASE output_group')
        raise
