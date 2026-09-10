"""Read-only receipt review and atomic posting of an explicitly selected group."""
import hashlib
import json
import sqlite3
from decimal import Decimal

try:
    from .invoice_receipt import InvoiceReceiptError, create_input_receipt
except ImportError:
    from invoice_receipt import InvoiceReceiptError, create_input_receipt


def receipt_review(conn, invoice_id, tenant):
    invoice = conn.execute('SELECT * FROM msmi_invoices WHERE id=? AND tenant=?', (invoice_id, tenant)).fetchone()
    if not invoice or invoice['invoice_type'] != 'INPUT_ELECTRONIC_INVOICE':
        raise InvoiceReceiptError('Không tìm thấy hóa đơn đầu vào trong phạm vi này', status=404)
    header = dict(invoice)
    for key in ('receipt_status', 'updated_at'):
        header.pop(key, None)
    items = [dict(r) for r in conn.execute('SELECT * FROM msmi_invoice_items WHERE invoice_id=? ORDER BY id', (invoice_id,))]
    products = [dict(r) for r in conn.execute('SELECT code,name,unit FROM products WHERE code IN (SELECT product_code FROM msmi_invoice_items WHERE invoice_id=?) ORDER BY code', (invoice_id,))]
    # Rules and units must still be those the user reviewed, including dated rules.
    rules = [dict(r) for r in conn.execute("SELECT * FROM invoice_line_mappings WHERE tenant=? AND source='msmi' AND partner_key=? ORDER BY id", (tenant, invoice['seller_tax_code']))]
    try:
        from .input_discount import _saved, state, DiscountError
    except ImportError:
        from input_discount import _saved, state, DiscountError
    allocation=_saved(conn,invoice_id);discounts={}
    if allocation:
        try:
            s=state(conn,invoice_id)
            if s['valid']: discounts=s['values']
        except DiscountError: pass
    source=[header, items, products, rules]
    if allocation: source.append(allocation)
    token = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    units = {p['code']: p['unit'] for p in products}
    quantities = {}
    eligible = [r for r in items if r['inventory_eligible']]
    amount = Decimal(0)
    for item in eligible:
        unit = units.get(item['product_code'], '')
        quantities[unit] = quantities.get(unit, Decimal(0)) + Decimal(str(item['stock_qty'] or 0))
        amount += Decimal(str(item['amount'] or 0))-discounts.get(item['id'],Decimal(0))
    return {'id': invoice_id, 'token': token, 'number': invoice['invoice_series'] + ' / ' + invoice['invoice_number'],
            'date': invoice['invoice_date'], 'seller': invoice['seller_name'], 'line_count': len(eligible),
            'amount': float(amount), 'qty_by_unit': {k: float(v) for k,v in quantities.items()}}


def preview_receipts(conn, ids, tenant, now_iso):
    if not ids or len(ids) > 500 or len(set(ids)) != len(ids):
        raise InvoiceReceiptError('Chọn từ 1 đến 500 hóa đơn khác nhau; thu hẹp bộ lọc nếu cần.', status=400)
    # Exercise the real posting checks on a private in-memory copy, including
    # period locks and ledger conflicts. Viewing never writes to the live DB.
    copy = sqlite3.connect(':memory:')
    copy.row_factory = sqlite3.Row
    conn.backup(copy)
    ready, blocked = [], []
    try:
        for invoice_id in ids:
            row = receipt_review(copy, invoice_id, tenant)
            copy.execute('SAVEPOINT receipt_preview')
            try:
                result = create_input_receipt(copy, invoice_id, now_iso)
                if result['idempotent']:
                    blocked.append({'id': invoice_id, 'number': row['number'], 'reason': 'Hóa đơn đã nhập kho.'})
                else:
                    ready.append(row)
            except InvoiceReceiptError as error:
                blocked.append({'id': invoice_id, 'number': row['number'], 'reason': str(error)})
            finally:
                copy.execute('ROLLBACK TO receipt_preview')
                copy.execute('RELEASE receipt_preview')
    finally:
        copy.close()
    return {'items': ready, 'blocked': blocked}


def post_receipts(conn, selection, tenant, now_iso):
    if not isinstance(selection, list) or not 1 <= len(selection) <= 500:
        raise InvoiceReceiptError('Chọn từ 1 đến 500 hóa đơn để nhập kho.', status=400)
    if any(not isinstance(r, dict) or type(r.get('id')) is not int or not isinstance(r.get('token'), str) for r in selection):
        raise InvoiceReceiptError('Danh sách xác nhận không hợp lệ; mở lại bảng kiểm tra.', status=400)
    ids = [r['id'] for r in selection]
    if len(set(ids)) != len(ids):
        raise InvoiceReceiptError('Danh sách có hóa đơn trùng.', status=400)
    conn.execute('SAVEPOINT receipt_group')
    try:
        for selected in selection:
            current = receipt_review(conn, selected['id'], tenant)
            if current['token'] != selected['token']:
                raise InvoiceReceiptError('Hóa đơn ' + current['number'] + ' đã thay đổi. Chưa nhập nhóm này; đóng và mở lại bảng kiểm tra.', code='stale_review')
        results = []
        for selected in selection:
            try:
                results.append(create_input_receipt(conn, selected['id'], now_iso))
            except InvoiceReceiptError as error:
                current = receipt_review(conn, selected['id'], tenant)
                raise InvoiceReceiptError('Hóa đơn ' + current['number'] + ': ' + str(error) + '. Chưa nhập nhóm này.', code=error.code) from error
        conn.execute('RELEASE receipt_group')
        return {'items': results, 'posted_count': sum(not r['idempotent'] for r in results),
                'already_posted_count': sum(r['idempotent'] for r in results)}
    except Exception:
        conn.execute('ROLLBACK TO receipt_group')
        conn.execute('RELEASE receipt_group')
        raise
