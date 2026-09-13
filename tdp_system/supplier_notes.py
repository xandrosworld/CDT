"""Editable supplier instructions, kept separate from sales and purchase money."""
import hashlib
import json
import re


def apply_notes(conn, batch_id, rows):
    saved = {r['note_key']: r['note'] for r in conn.execute(
        'SELECT note_key,note FROM supplier_line_notes WHERE batch_id=?', (batch_id,))}
    for row in rows:
        # A replacement spreadsheet row must not inherit another item's note.
        identity = [row.get(k) for k in ('row_key', 'order_id', 'source_sheet', 'source_row',
                    'work_date', 'kitchen', 'supplier', 'product_code', 'product_name', 'unit', 'note')]
        key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        row['note_key'] = key
        if key in saved:
            row['note'] = saved[key]


def save_notes(conn, batch_id, body, now_iso):
    try:
        from . import contract_modules as cm
    except ImportError:
        import contract_modules as cm
    if not isinstance(body, dict):
        raise ValueError('Dữ liệu ghi chú không hợp lệ.')
    before = cm.purchase_order_payload(conn, batch_id, for_sending=True)
    if not before['send_available']:
        raise ValueError(before['source_message'])
    if not body.get('plan_hash') or body['plan_hash'] != before['plan_hash']:
        raise cm.PurchaseOrderApplyError('Đơn NCC đã thay đổi. Mở lại ghi chú để xem bản mới trước khi lưu.', code='stale_supplier_plan')
    edits = body.get('rows')
    if not isinstance(edits, list) or not 1 <= len(edits) <= 2000:
        raise ValueError('Chọn từ 1 đến 2.000 dòng ghi chú.')
    current = {r['note_key']: r for r in before['rows']}
    checked, seen = [], set()
    for edit in edits:
        if not isinstance(edit, dict) or not isinstance(edit.get('note_key'), str) or edit['note_key'] not in current:
            raise ValueError('Dòng ghi chú không còn thuộc đơn NCC này.')
        key, note = edit['note_key'], edit.get('note')
        if key in seen or not isinstance(note, str) or len(note) > 1000:
            raise ValueError('Mỗi dòng chỉ có một ghi chú, tối đa 1.000 ký tự.')
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', note) or note.lstrip().startswith('='):
            raise ValueError('Ghi chú chỉ nhập chữ, không nhập công thức hoặc ký tự điều khiển.')
        seen.add(key)
        if note != current[key]['note']:
            checked.append((key, note))
    for key, note in checked:
        conn.execute('''INSERT INTO supplier_line_notes(batch_id,note_key,note,updated_at) VALUES(?,?,?,?)
            ON CONFLICT(batch_id,note_key) DO UPDATE SET note=excluded.note,updated_at=excluded.updated_at''',
            (batch_id, key, note, now_iso()))
    if checked:
        try:
            from .supplier_plan import reopen_changed_suppliers
        except ImportError:
            from supplier_plan import reopen_changed_suppliers
        reopen_changed_suppliers(conn, batch_id, before, now_iso)
        cm.audit(conn, now_iso, 'supplier_notes.update', 'ok', entity_type='batch', entity_id=batch_id,
                 metadata={'changes': [{'note_key': k, 'before': current[k]['note'], 'after': n} for k, n in checked]})
    return {'ok': True, 'changed': len(checked), 'plan_hash': cm.purchase_order_database_state_hash(conn, batch_id)}
