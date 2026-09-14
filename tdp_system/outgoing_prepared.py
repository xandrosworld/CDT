"""Reviewable, expiring snapshots for sending prepared order invoices."""
import hashlib
import json
import secrets
from itsdangerous import URLSafeTimedSerializer, BadSignature
from flask import jsonify,request

try:
    from .outgoing_contractors import line_choices_payload, assert_enabled
    from .outgoing_weights import invoice_rows
except ImportError:
    from outgoing_contractors import line_choices_payload, assert_enabled
    from outgoing_weights import invoice_rows

SCHEMA='''CREATE TABLE IF NOT EXISTS outgoing_prepared_scopes (
    draft_id INTEGER PRIMARY KEY REFERENCES outgoing_invoice_drafts(id) ON DELETE CASCADE,
    date_from TEXT NOT NULL,date_to TEXT NOT NULL,contractor TEXT NOT NULL,digest TEXT NOT NULL
);'''


def signer(app):
    key = app.secret_key or app.extensions.setdefault('prepared_invoice_secret', secrets.token_hex(32))
    return URLSafeTimedSerializer(key, salt='tdp-prepared-invoice-v1')


def snapshot(conn, draft_id):
    draft = conn.execute('SELECT * FROM outgoing_invoice_drafts WHERE id=?', (draft_id,)).fetchone()
    if not draft or draft['status'] != 'draft':
        raise ValueError('Bảng kê đã thay đổi hoặc hóa đơn đã phát hành. Chuẩn bị lại trước khi gửi.')
    assert_enabled(conn, draft['contractor'])
    lines = invoice_rows(conn, [dict(r) for r in conn.execute(
        'SELECT * FROM outgoing_invoice_lines WHERE draft_id=? ORDER BY id', (draft_id,))])
    oids = {r[0] for r in conn.execute('SELECT order_id FROM outgoing_order_allocations WHERE draft_id=?', (draft_id,))}
    sources = [r for r in line_choices_payload(conn, '9999-12-31') if r['order_id'] in oids]
    if len(sources) != len(oids) or any(not r['enabled'] for r in sources):
        raise ValueError('Dòng đã bỏ chọn hoặc đã ký không được gửi lại. Chuẩn bị lại bảng kê.')
    buyer = conn.execute('SELECT * FROM outgoing_buyer_profiles WHERE contractor=?', (draft['contractor'],)).fetchone()
    data = {'id': draft_id, 'contractor': draft['contractor'], 'invoice_date': draft['invoice_date'],
            'subtotal': draft['subtotal'], 'tax_amount': draft['tax_amount'], 'total_amount': draft['total_amount'],
            'buyer': dict(buyer) if buyer else {}, 'lines': lines,
            'sources': sorted((r['order_id'],r['date'],r['contractor'],r['product_code'],r['qty'],r['unit'],
                               r['price'],r['enabled'],r['invoice_name'],r['invoice_unit'],r['tax']) for r in sources)}
    return data


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prepared_payload(app, conn, draft_ids, period, pending, blocked):
    items = []
    for did in draft_ids:
        data = snapshot(conn, did)
        token = signer(app).dumps({'id': did, 'digest': digest(data)})
        conn.execute('INSERT OR REPLACE INTO outgoing_prepared_scopes VALUES(?,?,?,?,?)',
                     (did,period['from'],period['to'],period['contractor'],digest(data)))
        items.append({k: v for k, v in data.items() if k != 'sources'} | {'token': token})
    return {'ok': True, 'scope': period, 'items': items, 'pending': pending, 'blocked': blocked,
            'remote_write': False, 'requires_user_sign_and_issue': True}


def validate_prepared(app, conn, draft_id, token):
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise ValueError('Cần kiểm tra bảng kê đã chuẩn bị trước khi gửi M-Invoice.')
    try:
        plan = signer(app).loads(token, max_age=30*60)
        if plan.get('id') != draft_id or plan.get('digest') != digest(snapshot(conn, draft_id)):
            raise ValueError('Đơn, lựa chọn hoặc thông tin hóa đơn vừa thay đổi. Chuẩn bị lại bảng kê trước khi gửi.')
    except BadSignature as exc:
        raise ValueError('Bản kiểm tra đã hết hạn. Chuẩn bị lại bảng kê trước khi gửi.') from exc


def register(app,ctx):
    @app.get('/api/outgoing-invoices/prepared')
    def prepared_get():
        try:
            try:from .outgoing_review import scope
            except ImportError:from outgoing_review import scope
            period=scope(request.args,ctx['valid_iso_date']);items=[];warnings=[]
            with ctx['db']() as conn:
                conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
                rows=conn.execute('''SELECT s.*,d.minvoice_status FROM outgoing_prepared_scopes s
                    JOIN outgoing_invoice_drafts d ON d.id=s.draft_id WHERE s.date_from=? AND s.date_to=?
                    AND s.contractor=? AND d.status='draft' ORDER BY d.contractor,d.id''',
                    (period['from'],period['to'],period['contractor'])).fetchall()
                for row in rows:
                    try:data=snapshot(conn,row['draft_id'])
                    except ValueError as exc:warnings.append(str(exc));continue
                    stale=digest(data)!=row['digest']
                    token=signer(app).dumps({'id':row['draft_id'],'digest':row['digest']})
                    items.append({k:v for k,v in data.items() if k!='sources'}|
                                 {'token':token,'minvoice_status':row['minvoice_status'],'stale':stale})
            return jsonify(ok=True,scope=period,items=items,pending=warnings,blocked=[],remote_write=False)
        except ValueError as exc:return jsonify(ok=False,error=str(exc)),400
