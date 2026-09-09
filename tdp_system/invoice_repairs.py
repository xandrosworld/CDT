"""Guarded data corrections. Call only in a backed-up, explicit transaction."""
import json
import math
import re

try:
    from . import invoice_mapping as mapping
    from .invoice_line_groups import source_fingerprint
except ImportError:
    import invoice_mapping as mapping
    from invoice_line_groups import source_fingerprint


def correct_unused_product_unit(conn, *, code, expected_name, expected_unit, unit, now):
    product = conn.execute('SELECT code,name,unit FROM products WHERE code=?',(code,)).fetchone()
    if not product or (product['name'],product['unit']) != (expected_name,expected_unit) or not unit.strip():
        raise ValueError('Danh mục đã thay đổi; dừng sửa đơn vị.')
    # References in stock, orders, opening balances, and saved mappings must all be absent.
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        table = row[0]
        if table in ('products','product_prices','outgoing_product_names'):
            continue
        quoted = '"' + table.replace('"','""') + '"'
        columns = {r['name'] for r in conn.execute('PRAGMA table_info('+quoted+')')}
        if 'product_code' in columns and conn.execute('SELECT 1 FROM '+quoted+' WHERE product_code=? LIMIT 1',(code,)).fetchone():
            raise ValueError('Mã đã được sử dụng trong '+table+'; cần đối chiếu trước khi đổi đơn vị.')
    conn.execute('UPDATE products SET unit=? WHERE code=?',(unit,code))
    if 'catalog_updated_at' in {r['name'] for r in conn.execute('PRAGMA table_info(products)')}:
        conn.execute('UPDATE products SET catalog_updated_at=? WHERE code=?',(now,code))
    conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('catalog.unit_correction','product',?,'ok','',?,?)""",
        (code,json.dumps({'before':expected_unit,'after':unit},ensure_ascii=False),now))


def correct_input_line_product(conn, *, item_id, expected, code, now):
    row = mapping._line_context(conn,'input',item_id)
    if not row or not row['inventory_eligible'] or row['parent_status'] in ('posted','blocked') or row['parent_sync_status']!='synced':
        raise ValueError('Dòng không còn được phép sửa mã.')
    mapping._check_expected(row,expected)
    product = mapping._product(conn,code)
    if not mapping.mapping_units_match(row['source_unit'],product['unit']):
        raise ValueError('Đơn vị chưa trùng khớp; không tự suy đoán quy đổi.')
    groups = conn.execute('SELECT member_indices FROM invoice_input_line_groups WHERE invoice_id=? AND active=1',(row['invoice_id'],)).fetchall()
    if any(row['line_index'] in json.loads(g[0]) for g in groups):
        raise ValueError('Dòng đã gộp; tách nhóm trước khi sửa mã riêng.')
    scope = f"selected-line:{row['invoice_id']}:{row['line_index']}"
    conn.execute("""INSERT INTO invoice_line_mappings(tenant,source,invoice_type,partner_key,scope_key,
        source_item_code,source_item_name,source_unit,product_code,target_unit,mapping_status,conversion_factor,confirmed_at,updated_at)
        VALUES(?,'msmi','INPUT_ELECTRONIC_INVOICE',?,?,?,?,?,?,?,'confirmed',1,?,?)
        ON CONFLICT(tenant,source,invoice_type,partner_key,scope_key,effective_from) DO UPDATE SET
        product_code=excluded.product_code,target_unit=excluded.target_unit,mapping_status='confirmed',
        conversion_factor=1,updated_at=excluded.updated_at""",
        (row['tenant'],row['partner_key'],scope,row['source_item_code'],row['source_item_name'],row['source_unit'],code,product['unit'],now,now))
    rule = conn.execute("SELECT * FROM invoice_line_mappings WHERE tenant=? AND source='msmi' AND invoice_type='INPUT_ELECTRONIC_INVOICE' AND partner_key=? AND scope_key=? AND effective_from=''",
        (row['tenant'],row['partner_key'],scope)).fetchone()
    mapping._record_revision(conn,rule,now)
    mapping._update_line_snapshot(conn,'msmi_invoice_items',item_id,code,'mapped',1)
    conn.execute('INSERT OR REPLACE INTO invoice_input_group_choices VALUES(?,?,?,?,?,?,?,?)',
        (row['invoice_id'],row['line_index'],source_fingerprint(row),code,1,product['unit'],rule['id'],now))
    mapping._refresh_input_invoice(conn,row['invoice_id'])
    mapping.refresh_linked_batches(conn,'input',{row['invoice_id']},now)
    conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('invoice_input.product_correction','msmi_invoice_item',?,'ok','',?,?)""",
        (str(item_id),json.dumps({'before':row['product_code'],'after':code,'scope':'single_line'},ensure_ascii=False),now))


def correct_unconsumed_posted_input_product(conn, *, item_id, expected, code,
                                           evidence, now):
    """Exceptional, backed-up repair of an unused receipt's product identity.

    Not a normal mapping operation and deliberately not exposed as an HTTP
    endpoint. The caller must hold BEGIN IMMEDIATE and retain a backup. A
    complete before/after journal is recorded; source quantities/money and
    unrelated mappings are unchanged. Any downstream issue requires a separate
    valuation/reversal workflow and is rejected here.
    """
    if not conn.in_transaction:
        raise ValueError('Cần giao dịch độc quyền và bản sao trước khi sửa sổ.')
    if (not isinstance(evidence, dict)
            or not re.fullmatch(r'[0-9a-f]{64}', str(evidence.get('sha256', '')))
            or not str(evidence.get('reason', '')).strip()
            or not str(evidence.get('file', '')).strip()
            or type(evidence.get('row')) is not int or evidence['row'] < 1):
        raise ValueError('Cần lưu nguồn đối chiếu cụ thể trước khi sửa sổ.')
    row = mapping._line_context(conn, 'input', item_id)
    if (not row or row['parent_status'] != 'posted'
            or row['parent_sync_status'] != 'synced' or expected is None):
        raise ValueError('Chỉ sửa phiếu nhập đã ghi, nguồn an toàn và chưa đổi.')
    mapping._check_expected(row, expected)
    old = mapping.validated_input_stock_snapshot(conn, item_id)
    if any(expected.get(k) != row[k] for k in (
            'invoice_id', 'line_index', 'source_item_code', 'source_item_name', 'unit_price')):
        raise ValueError('Danh tính dòng nguồn đã thay đổi; dừng sửa sổ.')
    product = mapping._product(conn, code)
    if (code == old['product_code'] or row['conversion_factor'] != 1
            or not mapping.mapping_units_match(row['source_unit'], product['unit'])
            or not math.isfinite(old['stock_qty']) or old['stock_qty'] <= 0):
        raise ValueError('Chỉ sửa mã khác, cùng đơn vị; không tự quy đổi.')
    invoice = conn.execute('SELECT * FROM msmi_invoices WHERE id=?',
                           (row['invoice_id'],)).fetchone()
    if conn.execute("""SELECT 1 FROM inventory_transactions WHERE source_type='OPENING'
        AND status='posted' AND txn_date>? LIMIT 1""", (invoice['invoice_date'],)).fetchone():
        raise ValueError('Đã chuyển tồn kỳ sau; cần đối chiếu lại kỳ đã chốt.')
    if conn.execute("""SELECT 1 FROM invoice_inventory_ledger WHERE status='posted'
        AND direction='output' AND product_code IN (?,?) AND txn_date>=? LIMIT 1""",
        (old['product_code'], code, invoice['invoice_date'])).fetchone():
        raise ValueError('Mã đã phát sinh xuất sau ngày nhập; cần tính lại giá vốn.')
    events = conn.execute("""SELECT * FROM invoice_inventory_ledger
        WHERE source_invoice_table='msmi_invoices' AND source_invoice_id=?
        AND source_line_id=?""", (row['invoice_id'], item_id)).fetchall()
    transactions = conn.execute("""SELECT * FROM inventory_transactions
        WHERE source_type='MSMI_INPUT' AND source_id=? AND source_line=?""",
        (invoice['remote_id'], str(row['line_index']))).fetchall()
    if len(events) != 1 or len(transactions) != 1:
        raise ValueError('Sổ nhập không còn duy nhất; dừng sửa.')
    event, transaction = dict(events[0]), dict(transactions[0])
    if not all(math.isfinite(float(value)) for value in (
            event['qty_delta'], event['unit_cost'], transaction['qty_in'],
            transaction['qty_out'], transaction['unit_cost'])):
        raise ValueError('Bút toán có số không hợp lệ; dừng sửa.')
    if (event['direction'] != 'input' or event['event_type'] != 'POST'
            or event['status'] != 'posted' or transaction['status'] != 'posted'
            or event['product_code'] != old['product_code']
            or transaction['product_code'] != old['product_code']
            or event['txn_date'] != invoice['invoice_date']
            or transaction['txn_date'] != invoice['invoice_date']
            or abs(event['qty_delta'] - old['stock_qty']) > 1e-6
            or abs(transaction['qty_in'] - old['stock_qty']) > 1e-6
            or transaction['qty_out'] != 0
            or abs(event['unit_cost'] - old['stock_unit_price']) > 1e-6
            or abs(transaction['unit_cost'] - old['stock_unit_price']) > 1e-6
            or event['mapping_revision_id'] != old['mapping_revision_id']):
        raise ValueError('Bút toán không khớp snapshot hóa đơn; dừng sửa.')
    conn.execute('SAVEPOINT repair_unused_receipt')
    try:
        # The complete checked ledger remains locked by the caller throughout.
        conn.execute("UPDATE msmi_invoices SET receipt_status='ready' WHERE id=?",
                     (row['invoice_id'],))
        correct_input_line_product(conn, item_id=item_id, expected=expected,
                                   code=code, now=now)
        new = mapping.validated_input_stock_snapshot(conn, item_id)
        conn.execute('UPDATE invoice_inventory_ledger SET product_code=?,mapping_revision_id=? WHERE id=?',
                     (code, new['mapping_revision_id'], event['id']))
        conn.execute('UPDATE inventory_transactions SET product_code=?,updated_at=? WHERE id=?',
                     (code, now, transaction['id']))
        conn.execute("UPDATE msmi_invoices SET receipt_status='posted',updated_at=? WHERE id=?",
                     (now, row['invoice_id']))
        mapping.refresh_linked_batches(conn, 'input', {row['invoice_id']}, now)
        journal = {'evidence': evidence, 'before': {'snapshot': old, 'event': event,
                   'transaction': transaction}, 'after': {'snapshot': new,
                   'event': dict(conn.execute('SELECT * FROM invoice_inventory_ledger WHERE id=?',
                                              (event['id'],)).fetchone()),
                   'transaction': dict(conn.execute('SELECT * FROM inventory_transactions WHERE id=?',
                                                    (transaction['id'],)).fetchone())}}
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
            VALUES('invoice_input.posted_product_correction','msmi_invoice_item',?,'ok','',?,?)""",
            (str(item_id), json.dumps(journal, ensure_ascii=False, sort_keys=True), now))
        conn.execute('RELEASE repair_unused_receipt')
        return {'item_id': item_id, 'before': old['product_code'], 'after': code,
                'qty': new['stock_qty'], 'amount': new['amount']}
    except Exception:
        conn.execute('ROLLBACK TO repair_unused_receipt')
        conn.execute('RELEASE repair_unused_receipt')
        raise
