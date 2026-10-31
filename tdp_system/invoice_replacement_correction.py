"""Confirmed correction of over-recorded original deliveries, never a goods return.

Use the existing effective-ledger quantity overlay, retaining immutable source
invoices and POST events. A later reversal restores only the corrected quantity.
"""
import hashlib
import json
import math

EVENT = 'invoice_output.replacement_original_quantity'


def _finite(values):
    try:
        return all(math.isfinite(float(value)) for value in values)
    except (TypeError, ValueError, OverflowError):
        return False


def quantity_correction_reviews(conn):
    try:
        from .invoice_payment_replacements import verified_replacements, replacement_basis
    except ImportError:
        from invoice_payment_replacements import verified_replacements, replacement_basis
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='output_stock_remap_parts'").fetchone():
        return {}
    result = {}
    for old_id, new_id in verified_replacements(conn).items():
        old = dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?', (old_id,)).fetchone())
        new = dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?', (new_id,)).fetchone())
        old_items = [dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index', (old_id,))]
        new_items = [dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index', (new_id,))]
        ledger = [dict(r) for r in conn.execute("SELECT * FROM invoice_inventory_ledger WHERE source_invoice_table='outgoing_source_invoices' AND source_invoice_id IN (?,?) ORDER BY id", (old_id, new_id))]
        if (not old_items or len(old_items) != len(new_items) or len(ledger) != len(old_items)
                or any(r['source_invoice_id'] != old_id or r['event_type'] != 'POST'
                       or r['direction'] != 'output' or r['status'] != 'posted' for r in ledger)):
            continue
        by_line = {r['source_line_id']: r for r in ledger}
        def key(r): return (r['source_item_code'], r['source_unit'], r['source_item_name'])
        by_key = {key(r): r for r in new_items}
        if len(by_key) != len(new_items) or {key(r) for r in old_items} != set(by_key):
            continue
        changes = []
        for a in old_items:
            b = by_key[key(a)]
            event = by_line.get(a['id'])
            product = conn.execute('SELECT unit FROM products WHERE code=?', (a['product_code'],)).fetchone()
            if (not event or not product or not a['inventory_eligible'] or a['mapping_status'] != 'mapped'
                    or not a['source_item_code'] or a['product_code'] != a['source_item_code']
                    or event['product_code'] != a['product_code']
                    or str(product['unit']).strip().casefold() != str(a['source_unit']).strip().casefold()
                    or not _finite((a['qty'], b['qty'], a['stock_qty'], event['qty_delta'], event['unit_cost']))
                    or not 0 < b['qty'] <= a['qty'] or abs(a['qty'] - a['stock_qty']) > 1e-8
                    or abs(event['qty_delta'] + a['qty']) > 1e-8 or event['unit_cost'] < 0
                    or event['txn_date'] != old['invoice_date']
                    or conn.execute('SELECT 1 FROM output_stock_remaps WHERE ledger_id=?', (event['id'],)).fetchone()):
                break
            if a['qty'] != b['qty']:
                changes.append({'ledger_id': event['id'], 'product_code': a['product_code'],
                                'name': a['source_item_name'], 'unit': a['source_unit'],
                                'old_qty': a['qty'], 'new_qty': b['qty'], 'unit_cost': event['unit_cost'],
                                'date': event['txn_date']})
        else:
            if not changes:
                continue
            basis = replacement_basis(old, new, old_items, new_items, ledger)
            token = hashlib.sha256(json.dumps({'basis': basis, 'changes': changes}, sort_keys=True, default=str).encode()).hexdigest()
            parts = [dict(r) for r in conn.execute('SELECT p.* FROM output_stock_remap_parts p JOIN invoice_inventory_ledger l ON l.id=p.ledger_id WHERE l.source_invoice_table=\'outgoing_source_invoices\' AND l.source_invoice_id IN (?,?) ORDER BY p.ledger_id', (old_id, new_id))]
            audit = conn.execute("SELECT 1 FROM audit_log WHERE event_type=? AND entity_id=? AND status='ok'", (EVENT, token)).fetchone()
            expected = sorted((r['ledger_id'], r['product_code'], r['new_qty'], r['unit_cost'], 1) for r in changes)
            actual = sorted((r['ledger_id'], r['product_code'], r['qty'], r['unit_cost'], r['revision']) for r in parts)
            confirmed = bool(audit and actual == expected)
            if parts and not confirmed:
                continue
            if audit and not confirmed:
                continue
            review = {'token': token, 'confirmed': confirmed, 'correction_kind': 'original_quantity',
                      'old_id': old_id, 'new_id': new_id, 'old_number': old['invoice_number'],
                      'new_number': new['invoice_number'], 'buyer': new['buyer_name'],
                      'old_total': old['total_amount'], 'new_total': new['total_amount'],
                      'line_count': len(new_items), 'changes': changes}
            result[old_id] = review
            result[new_id] = review
    return result


def confirm_original_quantity(conn, invoice_id, expected, confirmed, reason, timestamp):
    try:
        from .output_stock_remap import _editable_period
    except ImportError:
        from output_stock_remap import _editable_period
    if confirmed is not True:
        raise ValueError('Cần xác nhận lượng trên hóa đơn thay thế là lượng thực giao từ đầu, không phải hàng trả lại.')
    note = str(reason or '').strip()
    if not note or len(note) > 500:
        raise ValueError('Điền Lý do sửa số lượng (tối đa 500 ký tự).')
    review = quantity_correction_reviews(conn).get(invoice_id)
    if not review or review['token'] != expected:
        raise ValueError('Hóa đơn hoặc kho đã thay đổi. Mở lại Xem chênh lệch và lập thanh toán để kiểm tra.')
    if review['confirmed']:
        return {'invoice_ids': [review['old_id'], review['new_id']], 'idempotent': True}
    for change in review['changes']:
        _editable_period(conn, change['date'])
    conn.execute('SAVEPOINT replacement_original_quantity')
    try:
        for change in review['changes']:
            conn.execute('INSERT INTO output_stock_remap_parts(ledger_id,product_code,qty,unit_cost,revision) VALUES(?,?,?,?,1)',
                         (change['ledger_id'], change['product_code'], change['new_qty'], change['unit_cost']))
        conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES(?,'invoice_replacement',?,'ok',?,?,?)",
                     (EVENT, expected, note, json.dumps(review, ensure_ascii=False), timestamp))
        conn.execute('RELEASE SAVEPOINT replacement_original_quantity')
    except Exception:
        conn.execute('ROLLBACK TO SAVEPOINT replacement_original_quantity')
        conn.execute('RELEASE SAVEPOINT replacement_original_quantity')
        raise
    return {'invoice_ids': [review['old_id'], review['new_id']], 'idempotent': False,
            'corrections': review['changes']}
