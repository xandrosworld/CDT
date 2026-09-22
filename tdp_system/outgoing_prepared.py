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
    try:
        from .outgoing_signed_guard import signed_draft_sources
    except ImportError:
        from outgoing_signed_guard import signed_draft_sources
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
    data['signed_source'] = signed_draft_sources(conn).get(draft_id)
    try:
        from .outgoing_price_guard import price_message
    except ImportError:
        from outgoing_price_guard import price_message
    data['price_error'] = price_message(conn, draft_id)
    return data


def digest(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def send_coverage(app, conn, draft_id, period, report=None):
    """Compare this draft with selected, still-unissued order quantities, not invoice line counts."""
    try:
        from .outgoing_unissued import unissued_payload
    except ImportError:
        from outgoing_unissued import unissued_payload
    from decimal import Decimal, InvalidOperation
    def tax_key(value):
        text = str(value).strip().upper()
        try:
            number = Decimal(text.rstrip('%'))
            if number == -2: return 'KKKNT'
            if number == -1: return 'KCT'
            if text.endswith('%') or abs(number) > 1: number /= 100
            return str(number.normalize())
        except InvalidOperation:
            return text
    draft = conn.execute('SELECT contractor FROM outgoing_invoice_drafts WHERE id=?', (draft_id,)).fetchone()
    taxes = {tax_key(r[0]) for r in conn.execute('SELECT tax FROM outgoing_invoice_lines WHERE draft_id=?', (draft_id,))}
    if report is None:
        report = unissued_payload(conn, period['to'], period['contractor'], respect_export_choices=True, start=period['from'])
    allocations = {r['order_id']: r['qty'] for r in conn.execute(
        'SELECT order_id,SUM(qty) qty FROM outgoing_order_allocations WHERE draft_id=? GROUP BY order_id', (draft_id,))}
    rows = []; skipped = 0
    for r in report['line_choices']:
        if r['contractor'] != draft['contractor'] or tax_key(r['tax']) not in taxes: continue
        if not r['enabled']:
            skipped += 1
            continue
        included = min(max(allocations.get(r['order_id'], 0), 0), r['qty'])
        remaining = max(r['qty'] - included, 0)
        rows.append({k: r[k] for k in ('order_id', 'batch_id', 'product_code', 'invoice_name', 'unit')} |
                    {'selected_qty': r['qty'], 'included_qty': included, 'remaining_qty': remaining,
                     'pending_reason': r.get('pending_reason') or 'Phần này chưa nằm trong bản nháp đang gửi. Mở các dòng còn lại để kiểm tra.',
                     'pending_codes': r.get('pending_codes', [])})
    data = {'selected_rows': len(rows), 'included_rows': sum(r['included_qty'] > 1e-8 for r in rows),
            'remaining_rows': sum(r['remaining_qty'] > 1e-8 for r in rows), 'skipped_rows': skipped,
            'rows': rows, 'scope': period}
    data['partial'] = data['remaining_rows'] > 0
    data['token'] = signer(app).dumps({'coverage_id': draft_id, 'digest': digest(data)})
    return data


def validate_partial_send(app, conn, draft_id, body):
    scope = conn.execute('SELECT * FROM outgoing_prepared_scopes WHERE draft_id=?', (draft_id,)).fetchone()
    if not scope: return
    coverage = send_coverage(app, conn, draft_id, {'from': scope['date_from'], 'to': scope['date_to'], 'contractor': scope['contractor']})
    if not coverage['partial']: return
    message = 'Bản nháp chỉ có một phần hàng đã chọn. Xem phần còn lại và tích “Tôi đồng ý chỉ gửi phần có trong bản nháp này”.'
    if body.get('confirm_partial') is not True: raise ValueError(message)
    try:
        plan = signer(app).loads(body.get('coverage_token', ''), max_age=30*60)
        current = {k: v for k, v in coverage.items() if k != 'token'}
        if plan.get('coverage_id') != draft_id or plan.get('digest') != digest(current):
            raise ValueError('Phần hàng còn lại đã thay đổi. Tải lại bảng kê, kiểm tra và xác nhận gửi một phần lần nữa.')
    except (BadSignature, TypeError, AttributeError) as exc:
        raise ValueError('Xác nhận gửi một phần đã hết hạn. Tải lại bảng kê và xác nhận lại.') from exc


def prepared_payload(app, conn, draft_ids, period, pending, blocked):
    items = []
    try:
        from .outgoing_unissued import unissued_payload
    except ImportError:
        from outgoing_unissued import unissued_payload
    report = unissued_payload(conn, period['to'], period['contractor'], respect_export_choices=True, start=period['from']) if draft_ids else None
    for did in draft_ids:
        data = snapshot(conn, did)
        if data.get('signed_source'):
            continue
        token = signer(app).dumps({'id': did, 'digest': digest(data)})
        conn.execute('INSERT OR REPLACE INTO outgoing_prepared_scopes VALUES(?,?,?,?,?)',
                     (did,period['from'],period['to'],period['contractor'],digest(data)))
        items.append({k: v for k, v in data.items() if k != 'sources'} |
                     {'token': token, 'coverage': send_coverage(app, conn, did, period, report)})
    return {'ok': True, 'scope': period, 'items': items, 'pending': pending, 'blocked': blocked,
            'remote_write': False, 'requires_user_sign_and_issue': True}


def validate_prepared(app, conn, draft_id, token):
    try:
        from .outgoing_price_guard import assert_current_prices
    except ImportError:
        from outgoing_price_guard import assert_current_prices
    assert_current_prices(conn, draft_id)
    try:
        from .outgoing_signed_guard import signed_draft_sources
    except ImportError:
        from outgoing_signed_guard import signed_draft_sources
    signed = signed_draft_sources(conn).get(draft_id)
    if signed:
        raise ValueError(signed['message'])
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
            period=scope(request.args,ctx['valid_iso_date']);items=[];warnings=[];signed_items=[]
            with ctx['db']() as conn:
                conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
                rows=conn.execute('''SELECT s.*,d.minvoice_status FROM outgoing_prepared_scopes s
                    JOIN outgoing_invoice_drafts d ON d.id=s.draft_id WHERE s.date_from=? AND s.date_to=?
                    AND s.contractor=? AND d.status='draft' ORDER BY d.contractor,d.id''',
                    (period['from'],period['to'],period['contractor'])).fetchall()
                try:
                    from .outgoing_unissued import unissued_payload
                except ImportError:
                    from outgoing_unissued import unissued_payload
                report = unissued_payload(conn, period['to'], period['contractor'], respect_export_choices=True, start=period['from']) if rows else None
                for row in rows:
                    try:data=snapshot(conn,row['draft_id'])
                    except ValueError as exc:warnings.append(str(exc));continue
                    stale=bool(data.get('price_error')) or digest(data)!=row['digest']
                    token=signer(app).dumps({'id':row['draft_id'],'digest':row['digest']})
                    items.append({k:v for k,v in data.items() if k!='sources'}|
                                 {'token':token,'minvoice_status':row['minvoice_status'],'stale':stale,
                                  'coverage':send_coverage(app,conn,row['draft_id'],period,report)})
                try:
                    from .outgoing_signed_guard import signed_draft_sources
                except ImportError:
                    from outgoing_signed_guard import signed_draft_sources
                signed = signed_draft_sources(conn)
                for item in items:
                    item['signed_source'] = signed.get(item['id'])
                signed_items=[item['signed_source'] for item in items if item.get('signed_source')]
                items=[item for item in items if not item.get('signed_source')]
            return jsonify(ok=True,scope=period,items=items,signed_items=signed_items,pending=warnings,blocked=[],remote_write=False)
        except ValueError as exc:return jsonify(ok=False,error=str(exc)),400
