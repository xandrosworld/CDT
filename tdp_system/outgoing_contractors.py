"""Choose which contractors participate in new M-Invoice export files."""
import hashlib
import json
import uuid

SCHEMA = '''
CREATE TABLE IF NOT EXISTS outgoing_contractor_choices (
    contractor TEXT PRIMARY KEY REFERENCES contractors(code) ON DELETE CASCADE,
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    revision TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outgoing_order_choices (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    revision TEXT NOT NULL, updated_at TEXT NOT NULL
);
'''


def excluded_codes(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_contractor_choices'").fetchone():
        return set()
    return {r[0] for r in conn.execute('SELECT contractor FROM outgoing_contractor_choices WHERE enabled=0')}


def assert_enabled(conn, contractor):
    if contractor and contractor in excluded_codes(conn):
        raise ValueError(f'Nhà thầu {contractor} đang bỏ chọn khỏi file M-Invoice. Bật lại ở “Nhà thầu đưa vào file” nếu cần xuất.')


def selected_orders(conn, rows):
    excluded = excluded_codes(conn)
    skipped = excluded_order_ids(conn)
    return [r for r in rows if r['contractor'] not in excluded and r['id'] not in skipped]


def excluded_order_ids(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_order_choices'").fetchone():
        return set()
    return {r[0] for r in conn.execute('SELECT order_id FROM outgoing_order_choices WHERE enabled=0')}


def assert_draft_lines_enabled(conn, draft_id):
    skipped = excluded_order_ids(conn)
    if any(r[0] in skipped for r in conn.execute('SELECT order_id FROM outgoing_order_allocations WHERE draft_id=?',(draft_id,))):
        raise ValueError('Dự thảo có dòng đã bỏ chọn khỏi file M-Invoice. Tải lại bảng kê để cập nhật lựa chọn.')


def assert_order_enabled(conn, contractor, order_id):
    assert_enabled(conn, contractor)
    if order_id in excluded_order_ids(conn):
        raise ValueError('Dòng đơn đã bỏ chọn khỏi file M-Invoice; chưa được tạo dự thảo hoặc giữ tồn cho dòng này.')


def _token(code, enabled, revision):
    return hashlib.sha256(json.dumps([code, enabled, revision]).encode()).hexdigest()


def choices_payload(conn):
    settings = {r['contractor']: dict(r) for r in conn.execute('SELECT * FROM outgoing_contractor_choices')}
    drafts = {}
    for row in conn.execute("""SELECT contractor,
        SUM(CASE WHEN COALESCE(minvoice_status,'not_sent') IN ('saved','saving','unknown') THEN 1 ELSE 0 END) protected,
        SUM(CASE WHEN COALESCE(minvoice_status,'not_sent') NOT IN ('saved','saving','unknown') THEN 1 ELSE 0 END) editable
        FROM outgoing_invoice_drafts WHERE status='draft' GROUP BY contractor"""):
        drafts[row['contractor']] = dict(row)
    items = []
    for row in conn.execute('SELECT code,name FROM contractors ORDER BY code'):
        setting = settings.get(row['code'], {})
        enabled = bool(setting.get('enabled', 1))
        counts = drafts.get(row['code'], {})
        items.append({'code': row['code'], 'name': row['name'], 'enabled': enabled,
            'token': _token(row['code'], enabled, setting.get('revision', '')),
            'editable_drafts': counts.get('editable', 0), 'protected_drafts': counts.get('protected', 0),
            'updated_at': setting.get('updated_at', '')})
    return {'items': items, 'excluded': [r['code'] for r in items if not r['enabled']]}


def release_disabled_drafts(conn, timestamp):
    """Only retire locally editable drafts. Issued/remote snapshots stay intact."""
    excluded = excluded_codes(conn)
    skipped = excluded_order_ids(conn)
    if not excluded and not skipped:
        return []
    ids = [r[0] for r in conn.execute("""SELECT id FROM outgoing_invoice_drafts
        WHERE status='draft' AND COALESCE(minvoice_status,'not_sent') NOT IN ('saved','saving','unknown')
        AND (contractor IN (SELECT value FROM json_each(?)) OR id IN (
            SELECT draft_id FROM outgoing_order_allocations WHERE order_id IN (SELECT value FROM json_each(?))))
        ORDER BY id""", (json.dumps(sorted(excluded)),json.dumps(sorted(skipped))))]
    if not ids:
        return []
    payload = json.dumps(ids)
    conn.execute("UPDATE outgoing_invoice_drafts SET status='cancelled' WHERE id IN (SELECT value FROM json_each(?))", (payload,))
    conn.execute("""UPDATE inventory_transactions SET status='cancelled',updated_at=?
        WHERE source_type='OUTGOING_DRAFT' AND status='reserved'
        AND CAST(source_id AS INTEGER) IN (SELECT value FROM json_each(?))""", (timestamp, payload))
    try:
        from .outgoing_substitution import mark_substitution_actions_reversed_for_draft
    except ImportError:
        from outgoing_substitution import mark_substitution_actions_reversed_for_draft
    for draft_id in ids:
        mark_substitution_actions_reversed_for_draft(conn, draft_id, timestamp)
    conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('outgoing.contractor_choices.release','outgoing_invoice','','ok',?,?,?)""",
        ('Bỏ dự thảo chưa gửi có nhà thầu hoặc dòng đã bỏ chọn khỏi file M-Invoice',
         json.dumps({'contractors': sorted(excluded), 'order_ids':sorted(skipped), 'draft_ids': ids}), timestamp))
    return ids


def save_choices(conn, body, timestamp):
    if not isinstance(body, dict) or not isinstance(body.get('items'), list) or not body['items']:
        raise ValueError('Chọn nhà thầu cần thay đổi trước khi lưu.')
    current = {r['code']: r for r in choices_payload(conn)['items']}
    changed, seen = [], set()
    for item in body['items']:
        if not isinstance(item, dict):
            raise ValueError('Lựa chọn nhà thầu không hợp lệ.')
        code = str(item.get('code') or '').strip().upper()
        if code not in current or code in seen or type(item.get('enabled')) is not bool:
            raise ValueError('Nhà thầu hoặc trạng thái chọn xuất không hợp lệ.')
        seen.add(code)
        if item.get('token') != current[code]['token']:
            raise ValueError(f'Lựa chọn của {code} vừa thay đổi. Tải lại trước khi lưu để không ghi đè.')
        if current[code]['enabled'] != item['enabled']:
            changed.append({'code': code, 'enabled': item['enabled']})
    for item in changed:
        conn.execute('''INSERT INTO outgoing_contractor_choices VALUES(?,?,?,?)
            ON CONFLICT(contractor) DO UPDATE SET enabled=excluded.enabled,
            revision=excluded.revision,updated_at=excluded.updated_at''',
            (item['code'], int(item['enabled']), uuid.uuid4().hex, timestamp))
    released = release_disabled_drafts(conn, timestamp) if changed else []
    if changed:
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
            VALUES('outgoing.contractor_choices.save','contractor','','ok','',?,?)""",
            (json.dumps({'changes': changed, 'released_draft_ids': released}), timestamp))
    return {**choices_payload(conn), 'changed': changed, 'released_draft_ids': released}


def line_choices_payload(conn, cutoff, contractor='', *, orders=None, issued=None):
    try:
        from .outgoing_unissued import issued_allocations
    except ImportError:
        from outgoing_unissued import issued_allocations
    if issued is None:
        issued,_ = issued_allocations(conn)
    if orders is None:
        orders=[dict(r) for r in conn.execute("""SELECT o.* FROM orders o JOIN batches b ON b.id=o.batch_id
            WHERE b.status='approved' AND o.work_date<=? AND (?='' OR o.contractor=?)
            ORDER BY o.work_date,o.contractor,o.id""",(cutoff,contractor,contractor))]
    excluded=excluded_codes(conn)
    settings={r['order_id']:dict(r) for r in conn.execute('SELECT * FROM outgoing_order_choices')}
    names={r['product_code']:r['invoice_name'] for r in conn.execute('SELECT * FROM outgoing_product_names')}
    protected={r[0] for r in conn.execute("""SELECT a.order_id FROM outgoing_order_allocations a JOIN outgoing_invoice_drafts d ON d.id=a.draft_id
        WHERE d.status='draft' AND d.minvoice_status IN ('saved','saving','unknown')""")}
    result=[]
    for o in orders:
        remaining=max(float(o['actual_delivered'] or 0)-float(o['customer_return_qty'] or 0)-issued.get(o['id'],0),0)
        if o['contractor'] in excluded or remaining<=1e-8:
            continue
        setting=settings.get(o['id'],{})
        enabled=bool(setting.get('enabled',1))
        locked=o['id'] in protected
        token=_token(o['id'],enabled,[setting.get('revision',''),o['updated_at'],remaining,o['product_code'],o['unit'],o['sell_price'],locked])
        result.append({'order_id':o['id'],'contractor':o['contractor'],'date':o['work_date'],'kitchen':o['kitchen'],
            'product_code':o['product_code'],'invoice_name':names.get(o['product_code']) or o['product_name'],
            'qty':remaining,'unit':o['unit'],'price':o['sell_price'],'enabled':enabled,'token':token,
            'editable':not locked,'reason':'Đang có bản đã lưu/đang gửi M-Invoice; đối chiếu bản đó trước.' if locked else ''})
    return result


def save_line_choices(conn, body, timestamp):
    if not isinstance(body,dict) or not isinstance(body.get('items'),list) or not body['items']:
        raise ValueError('Chọn dòng cần thay đổi trước khi lưu.')
    current={r['order_id']:r for r in line_choices_payload(conn,'9999-12-31')}
    changed=[];seen=set()
    for item in body['items']:
        if not isinstance(item,dict) or type(item.get('order_id')) is not int or type(item.get('enabled')) is not bool:
            raise ValueError('Lựa chọn dòng không hợp lệ.')
        oid=item['order_id'];row=current.get(oid)
        if not row or oid in seen or item.get('token')!=row['token']:
            raise ValueError('Dòng đơn, phần đã ký hoặc lựa chọn vừa thay đổi. Tải lại danh sách trước khi lưu.')
        seen.add(oid)
        if not row['editable']:
            raise ValueError(row['reason'])
        if row['enabled']!=item['enabled']:
            changed.append({'order_id':oid,'enabled':item['enabled']})
    for item in changed:
        conn.execute('''INSERT INTO outgoing_order_choices VALUES(?,?,?,?)
            ON CONFLICT(order_id) DO UPDATE SET enabled=excluded.enabled,revision=excluded.revision,updated_at=excluded.updated_at''',
            (item['order_id'],int(item['enabled']),uuid.uuid4().hex,timestamp))
    released=release_disabled_drafts(conn,timestamp) if changed else []
    if changed:
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
            VALUES('outgoing.line_choices.save','order','','ok','',?,?)""",(json.dumps({'changes':changed,'released_draft_ids':released}),timestamp))
    return {'changed':changed,'released_draft_ids':released}
