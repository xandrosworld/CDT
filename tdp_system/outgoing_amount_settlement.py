"""Signed-invoice money review: save progress separately from period completion."""
import hashlib
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

from flask import jsonify, request

SCHEMA = '''
CREATE TABLE IF NOT EXISTS outgoing_amount_settlements (
 id INTEGER PRIMARY KEY, contractor TEXT NOT NULL, date_from TEXT NOT NULL,
 date_to TEXT NOT NULL, snapshot_json TEXT NOT NULL, fingerprint TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
 revoked_at TEXT NOT NULL DEFAULT '', revoked_by TEXT NOT NULL DEFAULT '',
 revoke_reason TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS outgoing_amount_progress (
 id INTEGER PRIMARY KEY, contractor TEXT NOT NULL, date_from TEXT NOT NULL,
 date_to TEXT NOT NULL, snapshot_json TEXT NOT NULL, fingerprint TEXT NOT NULL,
 actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS outgoing_amount_progress_scope
 ON outgoing_amount_progress(contractor,date_from,date_to,id);
'''


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def records(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_amount_settlements'").fetchone():
        return []
    return [dict(r) for r in conn.execute("SELECT * FROM outgoing_amount_settlements WHERE revoked_at='' ORDER BY id")]


def order_snapshot(conn, party, start, end):
    try:
        from .receivable_ledger import _vnd_product, _tax_percent, _number
    except ImportError:
        from receivable_ledger import _vnd_product, _tax_percent, _number
    result = []
    for r in conn.execute("""SELECT o.* FROM orders o JOIN batches b ON b.id=o.batch_id
        WHERE b.status='approved' AND o.contractor=? AND o.work_date BETWEEN ? AND ? ORDER BY o.id""", (party, start, end)):
        # Exactly the operational receivable ledger's net quantity and VND rounding.
        qty = max(_number(r['actual_delivered'], 'Thực giao') - _number(r['customer_return_qty'], 'Khách trả'), 0)
        subtotal = _vnd_product(qty, r['sell_price'])
        percent = _tax_percent(r['tax'])
        tax = _vnd_product(subtotal, percent / 100) if percent > 0 else 0
        if qty <= 0 or subtotal + tax <= 0:
            continue
        result.append({**{k: r[k] for k in ('id', 'batch_id', 'work_date', 'contractor', 'product_code', 'unit',
                       'actual_delivered', 'customer_return_qty', 'sell_price', 'tax')},
                       'subtotal': subtotal, 'tax_amount': tax, 'amount': subtotal + tax})
    return result


def source_snapshot(conn, ids, party):
    try:
        from .outgoing_source_scope import resolve_scope
    except ImportError:
        from outgoing_source_scope import resolve_scope
    profiles = defaultdict(list)
    for r in conn.execute('SELECT contractor,tax_code FROM outgoing_buyer_profiles'):
        profiles[(r['tax_code'] or '').strip().upper()].append(r['contractor'])
    result = []
    for iid in sorted(ids):
        r = conn.execute("SELECT * FROM outgoing_source_invoices WHERE id=? AND source='minvoice'", (iid,)).fetchone()
        if not r or r['source_status_class'] != 'issued' or r['sync_status'] != 'synced':
            raise ValueError(f'Hóa đơn nguồn {iid} chưa đủ trạng thái đã ký và đồng bộ; cần cập nhật/đối chiếu lại.')
        resolved, error = resolve_scope(conn, r, profiles)
        if error or resolved != party:
            raise ValueError(f'Hóa đơn {r["invoice_number"]} chưa thuộc đúng nhà thầu {party}.')
        total = Decimal(str(r['total_amount']))
        if not total.is_finite() or total <= 0 or total != total.to_integral_value():
            raise ValueError('Tổng hóa đơn phải là số tiền VND dương đến đơn vị đồng.')
        if conn.execute("""SELECT COUNT(*) FROM outgoing_source_invoices WHERE source='minvoice' AND tenant=?
            AND invoice_series=? AND invoice_number=? AND invoice_date=? AND source_status_class='issued'""",
            (r['tenant'], r['invoice_series'], r['invoice_number'], r['invoice_date'])).fetchone()[0] != 1:
            raise ValueError('Trùng định danh hóa đơn nguồn; cần đối chiếu trước.')
        result.append({**{k: r[k] for k in ('id', 'tenant', 'identity_key', 'invoice_series', 'invoice_number',
                      'invoice_date', 'buyer_tax_code', 'buyer_name', 'subtotal', 'tax_amount')},
                      'total_amount': int(total), 'content_hash': digest(json.loads(r['raw_json'] or '{}'))})
    return result


def current_snapshot(conn, party, start, end, ids):
    return {'orders': order_snapshot(conn, party, start, end), 'invoices': source_snapshot(conn, ids, party)}


def progress(conn, party, start, end):
    """An exact-scope review note, never an allocation or a completed period."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_amount_progress'").fetchone():
        return None
    row = conn.execute('''SELECT * FROM outgoing_amount_progress
        WHERE contractor=? AND date_from=? AND date_to=? ORDER BY id DESC LIMIT 1''',
        (party, start, end)).fetchone()
    if not row:
        return None
    saved = json.loads(row['snapshot_json'])
    ids = [r['id'] for r in saved['invoices']]
    error = ''
    try:
        if digest(current_snapshot(conn, party, start, end, ids)) != row['fingerprint']:
            error = 'Đơn hoặc hóa đơn đã thay đổi. Bấm Kiểm tra tổng tiền đã chọn để cập nhật tiến độ.'
    except ValueError as exc:
        error = str(exc)
    demand = sum(r['amount'] for r in saved['orders'])
    signed = sum(r['total_amount'] for r in saved['invoices'])
    return {'id': row['id'], 'from': start, 'to': end, 'invoice_ids': ids,
            'orders_total': demand, 'signed_total': signed, 'remaining': demand-signed,
            'actor': row['actor'], 'reason': row['reason'], 'created_at': row['created_at'],
            'needs_review': bool(error), 'message': error}


def save_progress(conn, body, timestamp):
    actor, reason = str(body.get('actor') or '').strip(), str(body.get('reason') or '').strip()
    if not actor or not reason or len(actor) > 120 or len(reason) > 1000:
        raise ValueError('Điền Người đối chiếu và Lý do / ghi chú để lưu tiến độ.')
    report = preview(conn, body)
    if report['token'] != body.get('token'):
        raise ValueError('Số liệu vừa thay đổi. Bấm Kiểm tra tổng tiền đã chọn trước khi lưu tiến độ.')
    if not report['can_save_progress']:
        raise ValueError('Chỉ lưu tiến độ khi đã chọn hóa đơn đã ký, còn tiền chưa xuất và không có thông tin đối chiếu bị xung đột.')
    snapshot = report['_snapshot']
    previous = progress(conn, report['contractor'], report['from'], report['to'])
    if previous and not previous['needs_review'] and previous['invoice_ids'] == sorted(report['invoice_ids']) and previous['actor'] == actor and previous['reason'] == reason:
        return {'id': previous['id'], 'unchanged': True}
    iid = conn.execute('''INSERT INTO outgoing_amount_progress
        (contractor,date_from,date_to,snapshot_json,fingerprint,actor,reason,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', (report['contractor'], report['from'], report['to'],
        json.dumps(snapshot, ensure_ascii=False), digest(snapshot), actor, reason, timestamp)).lastrowid
    conn.execute('''INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('outgoing.amount_progress','outgoing_amount_progress',?,'ok',?,?,?)''',
        (str(iid), reason, json.dumps({'actor': actor, 'invoice_ids': report['invoice_ids'],
                                     'signed_total': report['signed_total'], 'remaining': report['remaining']}), timestamp))
    return {'id': iid, 'unchanged': False}


def coverage(conn):
    order_ids, invoice_ids, reviews = set(), set(), []
    for record in records(conn):
        before = json.loads(record['snapshot_json'])
        try:
            current = current_snapshot(conn, record['contractor'], record['date_from'], record['date_to'],
                                       [r['id'] for r in before['invoices']])
            if digest(current) != record['fingerprint']:
                raise ValueError('Đơn hoặc hóa đơn đã thay đổi sau khi xác nhận đối trừ tiền.')
        except ValueError as exc:
            reviews.append({'contractor': record['contractor'], 'code': 'amount_settlement_changed',
                            'settlement_id': record['id'],
                            'message': f'Đối trừ tiền #{record["id"]}: {exc} Mở đối trừ theo tiền để kiểm tra lại.'})
            continue
        order_ids.update(r['id'] for r in current['orders'])
        invoice_ids.update(r['id'] for r in current['invoices'])
    return order_ids, invoice_ids, reviews


def history(conn, party=''):
    result = []
    _, _, errors = coverage(conn)
    invalid = {e['settlement_id'] for e in errors}
    for r in records(conn):
        if party and r['contractor'] != party:
            continue
        saved = json.loads(r['snapshot_json'])
        result.append({k: r[k] for k in ('id', 'contractor', 'date_from', 'date_to', 'actor', 'reason', 'created_at')})
        result[-1].update(amount=sum(o['amount'] for o in saved['orders']),
                          order_rows=len(saved['orders']), invoices=saved['invoices'],
                          needs_review=r['id'] in invalid)
    return result


def validate_scope(conn, body):
    party = str(body.get('contractor') or '').strip()
    start, end = body.get('from'), body.get('to')
    try:
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Chọn đúng khoảng ngày đơn cần đối trừ.') from None
    if not conn.execute('SELECT 1 FROM contractors WHERE code=?', (party,)).fetchone():
        raise ValueError('Chọn một nhà thầu để đối trừ tiền.')
    return party, start, end


def preview(conn, body):
    party, start, end = validate_scope(conn, body)
    ids = body.get('invoice_ids', [])
    if not isinstance(ids, list) or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Danh sách hóa đơn không hợp lệ hoặc bị trùng.')
    snapshot = current_snapshot(conn, party, start, end, ids)
    if not snapshot['orders']:
        raise ValueError('Không có doanh thu từ đơn đã duyệt trong kỳ đã chọn.')
    conflicts = []
    order_ids = {o['id'] for o in snapshot['orders']}
    for rec in records(conn):
        prior = json.loads(rec['snapshot_json'])
        if order_ids.intersection(o['id'] for o in prior['orders']) or set(ids).intersection(i['id'] for i in prior['invoices']):
            conflicts.append(f'Đã có đối trừ #{rec["id"]} dùng đơn/hóa đơn này. Kiểm tra hoặc mở lại bản đó trước.')
    try:
        from .outgoing_unissued import issued_allocations
    except ImportError:
        from outgoing_unissued import issued_allocations
    lineage = {}
    issued_allocations(conn, source_order_allocations=lineage)
    for iid, allocated in lineage.items():
        if order_ids.intersection(allocated) and iid not in ids:
            conflicts.append(f'Hóa đơn nguồn {iid} đang đối trừ mặt hàng trong kỳ nhưng chưa được chọn; phải đối chiếu cùng để tránh dùng lại tiền.')
    for iid in ids:
        if set(lineage.get(iid, {})) - order_ids:
            conflicts.append(f'Hóa đơn nguồn {iid} đang đối trừ cho đơn ngoài kỳ đã chọn; không được dùng toàn bộ tiền lần nữa.')
    # Every locally linked issue for this period must appear in the reviewed list.
    sources = {(s['invoice_series'].strip().upper(), s['invoice_number'].strip(), s['invoice_date']) for s in snapshot['invoices']}
    drafts = []
    for d in conn.execute("""SELECT DISTINCT d.* FROM outgoing_invoice_drafts d JOIN outgoing_order_allocations a ON a.draft_id=d.id
        WHERE a.order_id IN (SELECT value FROM json_each(?)) AND d.status IN ('draft','issued')""", (json.dumps(sorted(order_ids)),)):
        if d['status'] == 'issued':
            key = ((d['issued_invoice_series'] or '').strip().upper(), (d['issued_invoice_number'] or '').strip(), d['issued_invoice_date'] or d['invoice_date'])
            if key not in sources:
                conflicts.append(f'Hóa đơn đã xác nhận của bản #{d["id"]} chưa có trong danh sách đối trừ.')
        elif d['minvoice_status'] in ('saved', 'saving', 'unknown'):
            conflicts.append(f'Bản #{d["id"]} đã gửi/đang gửi/chưa rõ kết quả M-Invoice; phải đối chiếu bản đó trước.')
        else:
            drafts.append(d['id'])
    demand = sum(r['amount'] for r in snapshot['orders'])
    signed = sum(r['total_amount'] for r in snapshot['invoices'])
    basis = {'snapshot': snapshot, 'conflicts': conflicts,
             'scope': [party, start, end]}
    return {'contractor': party, 'from': start, 'to': end, 'invoice_ids': ids,
            'orders_total': demand, 'signed_total': signed, 'remaining': demand - signed,
            'orders_tax': sum(r['tax_amount'] for r in snapshot['orders']),
            'signed_tax': float(sum((Decimal(str(r['tax_amount'])) for r in snapshot['invoices']), Decimal(0))),
            'order_rows': len(order_ids), 'invoices': snapshot['invoices'], 'conflicts': conflicts,
            'can_confirm': bool(ids) and demand == signed and not conflicts,
            'can_save_progress': bool(ids) and 0 < signed < demand and not conflicts,
            'token': digest(basis), '_snapshot': snapshot, '_drafts': drafts}


def public(report):
    return {k: v for k, v in report.items() if not k.startswith('_')}


def confirm(conn, body, timestamp):
    actor, reason = str(body.get('actor') or '').strip(), str(body.get('reason') or '').strip()
    if body.get('confirmed') is not True or not actor or not reason or len(actor) > 120 or len(reason) > 1000:
        raise ValueError('Xác nhận đúng hóa đơn/kỳ đơn, điền người đối chiếu và lý do.')
    # Exact retried request is idempotent even after its editable drafts retired.
    for rec in records(conn):
        saved = json.loads(rec['snapshot_json'])
        if [rec['contractor'], rec['date_from'], rec['date_to']] == [body.get('contractor'), body.get('from'), body.get('to')] and sorted(i['id'] for i in saved['invoices']) == sorted(body.get('invoice_ids') or []):
            current = current_snapshot(conn, rec['contractor'], rec['date_from'], rec['date_to'], body['invoice_ids'])
            if digest(current) == rec['fingerprint']:
                return {'id': rec['id'], 'unchanged': True}
    report = preview(conn, body)
    if report['token'] != body.get('token'):
        raise ValueError('Số liệu vừa thay đổi. Kiểm tra lại tổng tiền trước khi xác nhận.')
    if not report['can_confirm']:
        raise ValueError('Chưa thể xác nhận đã xuất đủ. Nếu còn tiền chưa xuất, bấm Lưu tiến độ — còn chưa xuất; không cần xuất bù để khép kỳ đơn.')
    snapshot = report['_snapshot']
    iid = conn.execute('''INSERT INTO outgoing_amount_settlements(contractor,date_from,date_to,snapshot_json,fingerprint,actor,reason,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', (report['contractor'], report['from'], report['to'], json.dumps(snapshot, ensure_ascii=False),
        digest(snapshot), actor, reason, timestamp)).lastrowid
    try:
        from .outgoing_contractors import release_disabled_drafts
    except ImportError:
        from outgoing_contractors import release_disabled_drafts
    retired = release_disabled_drafts(conn, timestamp)
    conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('outgoing.amount_settlement','outgoing_amount_settlement',?,'ok',?,?,?)""",
        (str(iid), reason, json.dumps({'actor': actor, 'invoice_ids': body['invoice_ids'], 'total': report['orders_total'], 'retired_drafts': retired}), timestamp))
    return {'id': iid, 'unchanged': False}


def revoke(conn, iid, body, timestamp):
    actor, reason = str(body.get('actor') or '').strip(), str(body.get('reason') or '').strip()
    if not actor or not reason or len(actor) > 120 or len(reason) > 1000:
        raise ValueError('Điền người mở lại và lý do để lưu lịch sử.')
    record = conn.execute('SELECT * FROM outgoing_amount_settlements WHERE id=?', (iid,)).fetchone()
    if not record:
        raise ValueError('Không tìm thấy bản đối trừ.')
    if not record['revoked_at']:
        conn.execute('UPDATE outgoing_amount_settlements SET revoked_at=?,revoked_by=?,revoke_reason=? WHERE id=?', (timestamp, actor, reason, iid))
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
            VALUES('outgoing.amount_settlement.revoke','outgoing_amount_settlement',?,'ok',?,?,?)""", (str(iid), reason, json.dumps({'actor': actor}), timestamp))
    return {'id': iid}


def register_routes(app, ctx):
    @app.route('/api/outgoing-invoices/amount-settlement', methods=['GET', 'POST'])
    def amount_settlement():
        try:
            body = request.get_json(silent=True) or dict(request.args)
            if not isinstance(body, dict):
                raise ValueError('Yêu cầu đối trừ không hợp lệ.')
            if request.method == 'POST' and body.get('action') == 'confirm':
                try:
                    from .outgoing_source_refresh import refresh_sources
                    from .order_export_scope import business_today
                except ImportError:
                    from outgoing_source_refresh import refresh_sources
                    from order_export_scope import business_today
                with ctx['db']() as conn:
                    _, start, end = validate_scope(conn, body)
                try:
                    refresh_sources(ctx['db'], ctx['create_minvoice_client'], ctx['now_iso'], start, max(end, business_today()))
                except Exception as exc:
                    raise ValueError('Chưa cập nhật đầy đủ M-Invoice; chưa xác nhận đối trừ. Thử cập nhật hóa đơn rồi kiểm tra lại.') from exc
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE' if request.method == 'POST' and body.get('action') in ('confirm', 'revoke', 'save_progress') else 'BEGIN')
                action = body.get('action', 'list')
                if request.method == 'POST' and action == 'save_progress':
                    return jsonify(ok=True, **save_progress(conn, body, ctx['now_iso']()))
                if request.method == 'POST' and action == 'confirm':
                    return jsonify(ok=True, **confirm(conn, body, ctx['now_iso']()))
                if request.method == 'POST' and action == 'revoke':
                    return jsonify(ok=True, **revoke(conn, int(body.get('id')), body, ctx['now_iso']()))
                if request.method == 'POST' and action == 'preview':
                    return jsonify(ok=True, **public(preview(conn, body)))
                party, start, end = validate_scope(conn, body)
                orders = order_snapshot(conn, party, start, end)
                invoices, unavailable = [], []
                try:
                    from .outgoing_source_scope import resolve_scope
                except ImportError:
                    from outgoing_source_scope import resolve_scope
                profiles = defaultdict(list)
                for profile in conn.execute('SELECT contractor,tax_code FROM outgoing_buyer_profiles'):
                    profiles[(profile['tax_code'] or '').strip().upper()].append(profile['contractor'])
                # Include late and early invoices for explicit review. No inferred period assignment.
                for r in conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice' AND source_status_class='issued' ORDER BY invoice_date,id"):
                    resolved, error = resolve_scope(conn, r, profiles)
                    if resolved != party and party not in profiles.get((r['buyer_tax_code'] or '').strip().upper(), []):
                        continue
                    try:
                        invoices.extend(source_snapshot(conn, [r['id']], party))
                    except ValueError as exc:
                        unavailable.append({'id': r['id'], 'number': r['invoice_series']+'/'+r['invoice_number'], 'error': str(exc)})
                return jsonify(ok=True, orders_total=sum(o['amount'] for o in orders), invoices=invoices,
                               unavailable_invoices=unavailable, history=history(conn, party),
                               progress=progress(conn, party, start, end))
        except (ValueError, TypeError) as exc:
            return jsonify(ok=False, error=str(exc)), 409
