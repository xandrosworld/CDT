"""Input receipt checks that preserve source amounts and explicit expense choices."""
import json
from decimal import Decimal, InvalidOperation


def is_goods_line(qty, unit_price, amount, nature):
    # A supplier can omit unit price while still providing quantity and amount.
    # Stock unit cost is calculated from amount / converted quantity separately.
    return qty > 0 and amount >= 0 and str(nature or '').strip() not in {'3', '4'}


def _number(value):
    if value is None or value == '':
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def receipt_cost_warning(conn, invoice_id, items=None):
    """Fail closed on unallocated source discounts; never invent an allocation."""
    header = conn.execute('SELECT raw_json,receipt_status FROM msmi_invoices WHERE id=?', (invoice_id,)).fetchone()
    if not header or header['receipt_status'] == 'posted':
        return ''
    rows = items if items is not None else [dict(r) for r in conn.execute(
        'SELECT * FROM msmi_invoice_items WHERE invoice_id=?', (invoice_id,))]
    if not any(r['inventory_eligible'] for r in rows):
        return ''
    # Protect an old database even before its eligibility repair has run.
    if any(not r['inventory_eligible'] and r['qty'] > 0 and r['amount'] > 0
           and r['unit_price'] == 0 and str(r['source_nature']) == '1'
           and str(r['validation_note'] or '').startswith('Không ghi kho: dòng nguồn không có số lượng/đơn giá dương')
           for r in rows):
        return 'Còn dòng hàng bị bỏ qua do nguồn thiếu đơn giá. Cần khôi phục dòng hàng trước khi nhập kho.'
    try:
        raw = json.loads(header['raw_json'] or '{}')
    except (TypeError, ValueError):
        return 'Không đọc được tổng tiền nguồn để kiểm tra giá nhập kho.'
    if not isinstance(raw, dict):
        return 'Không đọc được tổng tiền nguồn để kiểm tra giá nhập kho.'
    discount = _number(raw.get('ttcktmai')) or Decimal(0)
    has_adjustment = discount != 0 or any(
        (str(r['source_nature']) == '3' or r['amount'] < 0) and r['amount'] != 0 for r in rows)
    if not has_adjustment:
        return ''
    gross = sum((_number(r['amount']) or Decimal(0) for r in rows
                 if str(r['source_nature']) != '3' and r['amount'] >= 0), Decimal(0))
    net = _number(raw.get('tgtcthue', raw.get('subtotal', raw.get('totalBeforeTax'))))
    total = _number(raw.get('tgtttbso', raw.get('totalAmount', raw.get('total'))))
    tax = _number(raw.get('tgtthue', raw.get('taxAmount', raw.get('tax'))))
    if total is not None and tax is not None:
        net = total - tax
    if net is not None and abs(gross - net) <= Decimal(1):
        return ''  # The source detail amounts already agree with net pre-tax value.
    return ('Hóa đơn có chiết khấu/điều chỉnh chưa khớp với giá trị các dòng hàng. '
            'Cần đối chiếu và phân bổ vào giá nhập trước khi nhập kho.')


def repair_missing_unit_price_goods(conn, timestamp):
    """Re-enable only unposted source goods incorrectly excluded by the old parser."""
    candidates = conn.execute("""SELECT li.*,i.remote_id FROM msmi_invoice_items li
        JOIN msmi_invoices i ON i.id=li.invoice_id
        WHERE i.invoice_type='INPUT_ELECTRONIC_INVOICE' AND i.sync_status='synced'
          AND i.receipt_status IN ('ready','not_inventory','pending_mapping')
          AND li.inventory_eligible=0 AND li.mapping_status='not_inventory'
          AND COALESCE(li.product_code,'')='' AND li.qty>0 AND li.amount>0 AND li.unit_price=0
          AND li.source_nature='1'
          AND li.validation_note LIKE 'Không ghi kho: dòng nguồn không có số lượng/đơn giá dương%'
          AND NOT EXISTS (SELECT 1 FROM invoice_input_expense_choices e
                          WHERE e.invoice_id=i.id AND e.line_index=li.line_index)
          AND NOT EXISTS (SELECT 1 FROM invoice_inventory_ledger l
                          WHERE l.source_invoice_table='msmi_invoices' AND l.source_invoice_id=i.id)
          AND NOT EXISTS (SELECT 1 FROM inventory_transactions t
                          WHERE t.source_type='MSMI_INPUT' AND t.source_id=i.remote_id)""").fetchall()
    changed = []
    for row in candidates:
        conn.execute("""UPDATE msmi_invoice_items SET inventory_eligible=1,mapping_status='unmapped',
            validation_note='',conversion_factor=NULL,stock_qty=0,stock_unit_price=0 WHERE id=?""", (row['id'],))
        conn.execute("UPDATE msmi_invoices SET receipt_status='pending_mapping',updated_at=? WHERE id=?",
                     (timestamp, row['invoice_id']))
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
            VALUES('invoice_input.eligibility_repair','msmi_invoice_item',?,'ok',?,?,?)""",
            (str(row['id']), 'Khôi phục dòng hàng có lượng và tiền, nguồn thiếu đơn giá',
             json.dumps({'invoice_id': row['invoice_id'], 'line_index': row['line_index']}, sort_keys=True), timestamp))
        changed.append(row['id'])
    if changed:
        try:
            from .invoice_mapping import refresh_linked_batches
        except ImportError:
            from invoice_mapping import refresh_linked_batches
        refresh_linked_batches(conn, 'input', {row['invoice_id'] for row in candidates}, timestamp)
    return changed
