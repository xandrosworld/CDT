"""Explicit input-invoice expense choices; source amounts and stock stay separate."""
import hashlib
import json

from flask import jsonify, request

SCHEMA = """CREATE TABLE IF NOT EXISTS invoice_input_expense_choices (
 invoice_id INTEGER NOT NULL, line_index INTEGER NOT NULL,
 source_fingerprint TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(invoice_id,line_index)
);"""


class ExpenseError(ValueError):
    pass


def _exists(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name='invoice_input_expense_choices'").fetchone() is not None


def _source_key(row):
    keys = ('invoice_id','line_index','source_item_code','source_item_name','source_unit',
            'qty','unit_price','amount','tax_rate','source_nature')
    values = [float(row[k] or 0) if k in ('qty','unit_price','amount') else row[k] for k in keys]
    return hashlib.sha256(json.dumps(values,ensure_ascii=False).encode()).hexdigest()


def _choices(conn, invoice_id):
    if not _exists(conn):
        return {}
    return {r['line_index']:dict(r) for r in conn.execute(
        'SELECT * FROM invoice_input_expense_choices WHERE invoice_id=?', (invoice_id,))}


def expense_state(conn, invoice_id):
    choices = _choices(conn, invoice_id)
    rows = {r['line_index']:r for r in conn.execute('SELECT * FROM msmi_invoice_items WHERE invoice_id=?',(invoice_id,))}
    conflicts = [index for index, choice in choices.items()
                 if index not in rows or _source_key(rows[index]) != choice['source_fingerprint']]
    return choices, conflicts


def expense_token(conn, invoice_id):
    header = dict(conn.execute('SELECT id,tenant,invoice_type,sync_status,receipt_status FROM msmi_invoices WHERE id=?',(invoice_id,)).fetchone())
    rows = [dict(r) for r in conn.execute('SELECT * FROM msmi_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice_id,))]
    return hashlib.sha256(json.dumps([header,rows,_choices(conn,invoice_id)],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def annotate_expenses(conn, invoice):
    choices, conflicts = expense_state(conn, invoice['id'])
    invoice['expense_review_count'] = len(conflicts)
    invoice['expense_token'] = expense_token(conn, invoice['id'])
    for row in invoice['items']:
        row['is_expense'] = row['line_index'] in choices
        row['expense_needs_review'] = row['line_index'] in conflicts


def restore_expenses(conn, invoice_id):
    """Apply stored choices before mapping rebuilt rows; changed sources require review."""
    choices, conflicts = expense_state(conn, invoice_id)
    for index in choices:
        note = ('Chi phí: dữ liệu nguồn đã thay đổi; cần xác nhận lại phân loại'
                if index in conflicts else 'Chi phí · không nhập kho')
        conn.execute("""UPDATE msmi_invoice_items SET inventory_eligible=0,product_code='',
            mapping_status=?,conversion_factor=NULL,stock_qty=0,stock_unit_price=0,validation_note=?
            WHERE invoice_id=? AND line_index=?""",
            ('review' if index in conflicts else 'not_inventory',note,invoice_id,index))
    return len(conflicts)


def set_expenses(conn, *, tenant, invoice_id, expense, item_ids, expected, now):
    if type(expense) is not bool:
        raise ExpenseError('Chọn rõ Chi phí hoặc Hàng nhập kho.')
    invoice = conn.execute('SELECT * FROM msmi_invoices WHERE id=? AND tenant=?',(invoice_id,tenant)).fetchone()
    if not invoice or invoice['invoice_type'] != 'INPUT_ELECTRONIC_INVOICE':
        raise ExpenseError('Không tìm thấy hóa đơn đầu vào trong phạm vi đang dùng.')
    if invoice['receipt_status'] in ('posted','blocked') or invoice['sync_status'] != 'synced':
        raise ExpenseError('Hóa đơn đã ghi kho hoặc nguồn cần đối chiếu; không được đổi phân loại.')
    if (conn.execute("SELECT 1 FROM invoice_inventory_ledger WHERE source_invoice_table='msmi_invoices' AND source_invoice_id=? LIMIT 1",(invoice_id,)).fetchone()
            or conn.execute("SELECT 1 FROM inventory_transactions WHERE source_type='MSMI_INPUT' AND source_id=? LIMIT 1",(invoice['remote_id'],)).fetchone()):
        raise ExpenseError('Hóa đơn đã có bút toán kho; cần đối chiếu trước khi đổi phân loại.')
    if not expected or expected != expense_token(conn,invoice_id):
        raise ExpenseError('Hóa đơn đã thay đổi. Hãy tải lại bảng trước khi đổi phân loại.')
    rows = [dict(r) for r in conn.execute('SELECT * FROM msmi_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice_id,))]
    if item_ids is not None:
        if (not isinstance(item_ids,list) or not item_ids or any(type(i) is not int for i in item_ids)
                or len(set(item_ids)) != len(item_ids) or not set(item_ids).issubset({r['id'] for r in rows})):
            raise ExpenseError('Danh sách dòng không hợp lệ hoặc không cùng hóa đơn.')
        rows = [r for r in rows if r['id'] in item_ids]
    choices = _choices(conn,invoice_id)
    changed = 0
    # Whole-invoice confirmation also acknowledges source lines removed on resync.
    if item_ids is None:
        present = {r['line_index'] for r in rows}
        for index in choices.keys() - present:
            conn.execute('DELETE FROM invoice_input_expense_choices WHERE invoice_id=? AND line_index=?',(invoice_id,index))
            changed += 1
    for row in rows:
        index = row['line_index']
        if expense:
            if not row['inventory_eligible'] and index not in choices:
                continue  # Keep source discounts/financial adjustments as they are.
            if index in choices and choices[index]['source_fingerprint'] == _source_key(row):
                continue
            conn.execute('INSERT OR REPLACE INTO invoice_input_expense_choices VALUES(?,?,?,?)',
                         (invoice_id,index,_source_key(row),now))
        else:
            if index not in choices:
                continue
            conn.execute('DELETE FROM invoice_input_expense_choices WHERE invoice_id=? AND line_index=?',(invoice_id,index))
            eligible = row['qty'] > 0 and (row['unit_price'] > 0 or row['amount'] == 0)
            conn.execute("""UPDATE msmi_invoice_items SET inventory_eligible=?,product_code='',mapping_status=?,
                conversion_factor=NULL,stock_qty=0,stock_unit_price=0,validation_note='' WHERE id=?""",
                (int(eligible),'unmapped' if eligible else 'not_inventory',row['id']))
        changed += 1
    if changed:
        if expense and conn.execute("SELECT 1 FROM sqlite_master WHERE name='invoice_input_line_groups'").fetchone():
            selected = {r['line_index'] for r in rows}
            for group in conn.execute('SELECT id,member_indices FROM invoice_input_line_groups WHERE invoice_id=? AND active=1',(invoice_id,)).fetchall():
                if selected.intersection(json.loads(group['member_indices'])):
                    conn.execute('UPDATE invoice_input_line_groups SET active=0,updated_at=? WHERE id=?',(now,group['id']))
        restore_expenses(conn,invoice_id)
        try:
            from .invoice_mapping import apply_saved_mappings, refresh_linked_batches
        except ImportError:
            from invoice_mapping import apply_saved_mappings, refresh_linked_batches
        apply_saved_mappings(conn,'input',invoice_id)
        refresh_linked_batches(conn,'input',{invoice_id},now)
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
            VALUES('invoice_input.expense','msmi_invoice',?,'ok','',?,?)""",
            (str(invoice_id),json.dumps({'expense':expense,'item_ids':item_ids,'changed':changed},sort_keys=True),now))
    return {'changed_lines':changed,'expense':expense}


def register_expense_routes(app, ctx):
    @app.post('/api/invoice-workbench/input-invoices/<int:invoice_id>/expense')
    def invoice_expense(invoice_id):
        body = request.get_json(silent=True)
        if not isinstance(body,dict):
            return jsonify(ok=False,error='Dữ liệu phân loại không hợp lệ.'),400
        if body.get('confirmed') is not True:
            return jsonify(ok=False,error='Cần kiểm tra và xác nhận phân loại. Nếu đang dùng trang cũ, hãy tải lại trang.'),400
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                result = set_expenses(conn,tenant=ctx['setting_get'](conn,'tenant_code','TDP'),
                    invoice_id=invoice_id,expense=body.get('expense'),item_ids=body.get('item_ids'),
                    expected=body.get('expected'),now=ctx['now_iso']())
            return jsonify(ok=True,**result)
        except ExpenseError as error:
            return jsonify(ok=False,error=str(error)),409
