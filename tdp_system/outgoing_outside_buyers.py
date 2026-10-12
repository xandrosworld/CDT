"""Customer-approved outside buyers. Classify future sources, never post stock."""
import hashlib
import json
import unicodedata

PREFIX = 'outgoing.outside_buyer.'


def normalized(value):
    return ' '.join(unicodedata.normalize('NFC', str(value or '')).split()).casefold()


def buyer_key(source):
    identity = [source['tenant'], source['source'], normalized(source['buyer_tax_code']),
                normalized(source['buyer_name'])]
    return PREFIX + hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()


def rules(conn):
    return [json.loads(r[0]) for r in conn.execute(
        'SELECT value FROM settings WHERE key LIKE ? ORDER BY key', (PREFIX+'%',))]


def known_contractor(conn, source):
    name, tax = normalized(source['buyer_name']), normalized(source['buyer_tax_code'])
    for r in conn.execute('SELECT legal_name,display_name,tax_code FROM outgoing_buyer_profiles'):
        if tax and tax == normalized(r['tax_code']):
            return True
        if name and name in (normalized(r['legal_name']), normalized(r['display_name'])):
            return True
    return any(name and name in (normalized(r['code']), normalized(r['name']))
               for r in conn.execute('SELECT code,name FROM contractors'))


def remember(conn, source, note, timestamp):
    if not normalized(source['buyer_name']):
        raise ValueError('Hóa đơn thiếu Tên người mua; chỉ lưu bán ngoài cho hóa đơn này, chưa thể ghi nhớ người mua.')
    if known_contractor(conn, source):
        raise ValueError('Người mua đã có trong nhà thầu. Bỏ tích Ghi nhớ người mua này là khách bán ngoài rồi lưu riêng hóa đơn này.')
    key = buyer_key(source)
    existing = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    if existing:
        return
    rule = {'invoice_id': source['id'], 'buyer': source['buyer_name'],
            'tax_code': source['buyer_tax_code'], 'tenant': source['tenant'],
            'source': source['source'], 'key': key,
            'after_id': conn.execute('SELECT COALESCE(MAX(id),0) FROM outgoing_source_invoices').fetchone()[0],
            'note': note, 'created_at': timestamp}
    conn.execute('INSERT INTO settings(key,value) VALUES(?,?)', (key,json.dumps(rule,ensure_ascii=False)))
    audit(conn, source['id'], 'remember', rule, timestamp)


def audit(conn, invoice_id, action, data, timestamp):
    conn.execute('''INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('outgoing.outside_buyer','outgoing_source_invoice',?,'ok',?,?,?)''',
        (str(invoice_id), action, json.dumps(data,ensure_ascii=False),timestamp))


def forget(conn, invoice_id, timestamp):
    for rule in rules(conn):
        if rule['invoice_id'] == invoice_id:
            conn.execute('DELETE FROM settings WHERE key=?', (rule['key'],))
            audit(conn,invoice_id,'forget',rule,timestamp)
            return
    raise ValueError('Người mua này không còn trong danh sách ghi nhớ. Tải lại danh sách.')


def apply_remembered(conn, invoice_id, timestamp):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'").fetchone():
        return False
    if not conn.execute('SELECT 1 FROM settings WHERE key LIKE ? LIMIT 1',(PREFIX+'%',)).fetchone():
        return False
    source = conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(invoice_id,)).fetchone()
    if not source or source['source'] != 'minvoice' or source['source_status_class'] != 'issued' or source['sync_status'] != 'synced':
        return False
    if conn.execute('SELECT 1 FROM outgoing_source_order_scopes WHERE invoice_id=?',(invoice_id,)).fetchone():
        return False  # Explicit decisions (including stale ones) always take precedence.
    stored = conn.execute('SELECT value FROM settings WHERE key=?',(buyer_key(source),)).fetchone()
    if not stored:
        return False
    rule = json.loads(stored[0])
    if invoice_id <= rule['after_id'] or known_contractor(conn,source):
        return False
    if conn.execute('''SELECT 1 FROM outgoing_invoice_drafts WHERE
        TRIM(issued_invoice_series)=? AND TRIM(issued_invoice_number)=?
        AND COALESCE(issued_invoice_date,invoice_date)=?''',
        (source['invoice_series'],source['invoice_number'],source['invoice_date'])).fetchone():
        return False
    # A matching downloaded order file is conflicting evidence, even if the
    # customer changed the buyer. Do not silently classify that invoice outside.
    try:
        from .outgoing_export_lineage import catalog, signature
        from .outgoing_source_scope import identity_snapshot
    except ImportError:
        from outgoing_export_lineage import catalog, signature
        from outgoing_source_scope import identity_snapshot
    lines = list(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=?',(invoice_id,)))
    if not lines:
        return False
    try:
        actual = signature(lines,True)
    except (ValueError,TypeError,ArithmeticError):
        return False
    for export in catalog(conn):
        if export['created_at'] <= source['created_at'] and export['signature'] == actual:
            return False
    note = 'Bán ngoài theo người mua đã ghi nhớ: '+rule['buyer']+'. '+rule['note']
    conn.execute('''INSERT INTO outgoing_source_order_scopes
        (invoice_id,scope,contractor,identity_snapshot,note,updated_at) VALUES(?,'outside','',?,?,?)''',
        (invoice_id,identity_snapshot(source),note,timestamp))
    audit(conn,invoice_id,'apply',{'rule':rule['key'],'confirmed_from':rule['invoice_id']},timestamp)
    return True
