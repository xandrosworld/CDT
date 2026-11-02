"""On-screen shortage review using the same atomic remap safeguards as Excel."""
from datetime import date
from decimal import Decimal, InvalidOperation
import sqlite3
import json

from flask import jsonify, request

try:
    from .output_stock_remap import RemapError, _snapshot, _source_hash, _store, _evaluate, _editable_period, _quantity_text
    from .stock_tax_policy import kkknt_codes
    from .outgoing_readiness import canonical_available_stock
    from .invoice_inventory import _minimum_balance_from
except ImportError:
    from output_stock_remap import RemapError, _snapshot, _source_hash, _store, _evaluate, _editable_period, _quantity_text
    from stock_tax_policy import kkknt_codes
    from outgoing_readiness import canonical_available_stock
    from invoice_inventory import _minimum_balance_from


def recipient_availability(conn, snapshot, code):
    """Explain the same stock/hold guard used by remap, without releasing holds."""
    stock = next(r for r in snapshot['stock'] if r['product_code'] == code)
    available = canonical_available_stock(conn).get(code, {})
    minimum = _minimum_balance_from(conn, code, snapshot['to'])
    reserved = available.get('reserved_qty', 0)
    pending = available.get('pending_sync_issued_qty', 0)
    holds = []
    for row in conn.execute("""SELECT d.id,d.contractor,d.invoice_date,d.status,d.minvoice_status,
            SUM(t.qty_out) qty,
            (SELECT COUNT(*) FROM outgoing_invoice_lines l WHERE l.draft_id=d.id) line_count
        FROM inventory_transactions t JOIN outgoing_invoice_drafts d ON CAST(d.id AS TEXT)=t.source_id
        WHERE t.source_type='OUTGOING_DRAFT' AND t.status='reserved' AND t.product_code=?
        GROUP BY d.id ORDER BY d.invoice_date,d.id""", (code,)):
        item = dict(row)
        item['can_cancel'] = item['status'] == 'draft' and item['minvoice_status'] not in ('saved', 'saving', 'unknown')
        item['lines'] = [dict(r) for r in conn.execute(
            'SELECT product_code,product_name,qty,unit FROM outgoing_invoice_lines WHERE draft_id=? ORDER BY id', (item['id'],))]
        holds.append(item)
    exempt = code in kkknt_codes(conn)
    return dict(product_code=code, unit=stock['unit'], closing_qty=stock['closing_qty'], holds_enforced=not exempt,
                minimum_qty=minimum, reserved_qty=reserved, pending_qty=pending,
                available_qty=max(0, stock['closing_qty'] if exempt else min(stock['closing_qty'], minimum-reserved-pending)), holds=holds)


def snapshot_for_web(conn, start, end):
    try:
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError()
    except (TypeError, ValueError):
        raise RemapError('Chọn Từ ngày và Đến ngày hợp lệ, theo đúng thứ tự.')
    if not conn.in_transaction:
        conn.execute('BEGIN')
    return _snapshot(conn, start, end)


def review_shortages(conn, start, end):
    snapshot = snapshot_for_web(conn, start, end)
    exempt = kkknt_codes(conn)
    stocks = {r['product_code']: r for r in snapshot['stock']}
    blocked_reason = ''
    try:
        _editable_period(conn, start)
    except RemapError as exc:
        blocked_reason = str(exc)
    items = []
    for stock in snapshot['stock']:
        if stock['closing_qty'] >= -1e-9:
            continue
        code = stock['product_code']
        sources = [dict(ledger_id=r['id'], invoice=r['cells'][2], date=r['txn_date'],
                        source_name=r['source_item_name'], qty=-r['qty_delta'])
                   for r in snapshot['rows'] if r['product_code'] == code]
        items.append(dict(stock, sources=sources, supplementary_allowed=code in exempt))
    items.sort(key=lambda item: (item['supplementary_allowed'], item['product_code']))
    catalog = [dict(r, closing_qty=stocks.get(r['code'], {}).get('closing_qty', 0))
               for r in snapshot['catalog']]
    history, other_history = [], []
    for entry in conn.execute("SELECT id,created_at,entity_type,metadata_json FROM audit_log WHERE event_type='inventory.output.remap' AND status='ok' ORDER BY id DESC"):
        meta = json.loads(entry['metadata_json'])
        destination = other_history if meta.get('from', '') > end or meta.get('to', '') < start else history
        for change in meta.get('changes', []):
            destination.append(dict(id=entry['id'], saved_at=entry['created_at'], origin=entry['entity_type'],
                                actor=meta.get('actor', ''), from_date=meta.get('from'), to_date=meta.get('to'),
                                **{k:change.get(k) for k in ('old_code','old_name','new_code','new_name','qty','old_unit','unit')}))
    return dict(from_date=start, to_date=end, version=_source_hash(snapshot),
                items=items, catalog=catalog, blocked_reason=blocked_reason, history=history, other_history=other_history)


def preview_web(conn, body):
    snapshot = snapshot_for_web(conn, body.get('from'), body.get('to'))
    issues = []

    def issue(field, message):
        issues.append(dict(field=field, message=message))

    if body.get('version') != _source_hash(snapshot):
        issue('reload', 'Số liệu kho vừa thay đổi. Bấm Cập nhật số liệu rồi xem trước lại; mã hàng và số lượng đang nhập được giữ lại.')
        return dict(can_confirm=False, issues=issues, changes=[])
    try:
        _editable_period(conn, snapshot['from'])
    except RemapError as exc:
        issue('period', str(exc))
        return dict(can_confirm=False, issues=issues, changes=[])
    code = str(body.get('product_code') or '')
    stock = next((r for r in snapshot['stock'] if r['product_code'] == code), None)
    source = next((r for r in snapshot['rows'] if r['id'] == body.get('ledger_id') and r['product_code'] == code), None)
    target = next((r for r in snapshot['catalog'] if r['code'] == body.get('new_code')), None)
    if not stock or stock['closing_qty'] >= -1e-9:
        issue('reload', 'Mặt hàng này hiện không còn âm. Bấm Cập nhật số liệu để xem lại.')
    if code in kkknt_codes(conn):
        issue('supplement', 'Hàng KKKNT: dùng Lập bảng kê bổ sung khi có hàng thực mua chưa ghi nhận.')
    if not source:
        issue('ledger_id', 'Chọn Dòng xuất cần sửa trong danh sách của mặt hàng này.')
    if not target or target['code'] == code:
        issue('new_code', 'Chọn Mặt hàng thực tế đã xuất khác mã đang bị trừ nhầm, từ danh mục bên dưới.')
    elif source and str(target['unit']).strip().casefold() != str(source['unit']).strip().casefold():
        issue('new_code', 'Mặt hàng thực tế đã xuất phải cùng đơn vị tính với dòng đang sửa. Không tự đổi số lượng giữa hai đơn vị.')
    try:
        qty = Decimal(str(body.get('qty')))
        if not qty.is_finite() or qty <= 0:
            raise ValueError()
        limit = min(Decimal(str(-stock['closing_qty'])), Decimal(str(-source['qty_delta']))) if stock and source else Decimal(0)
        if qty > limit + Decimal('0.000000001'):
            issue('qty', f'Số lượng sửa tối đa {float(max(limit, 0)):g}: không vượt phần còn âm hoặc lượng của dòng xuất đã chọn.')
    except (InvalidOperation, ValueError, TypeError):
        qty = Decimal(0)
        issue('qty', 'Nhập Số lượng sửa là số lớn hơn 0.')
    if issues:
        return dict(can_confirm=False, issues=issues, changes=[])
    change = dict(ledger_id=source['id'], line_id=source['source_line_id'],
                  invoice_id=source['source_invoice_id'], old_code=code, old_name=source['name'],
                  new_code=target['code'], new_name=target['name'], qty=float(qty),
                  old_unit=source['unit'], unit=target['unit'], source_stock_qty=-source['qty_delta'],
                  old_unit_cost=source['unit_cost'], excel_row=1)
    availability = recipient_availability(conn, snapshot, target['code'])
    errors = _evaluate(conn, snapshot, [change])
    # Do not offer another negative item as a convenient recipient, including KKKNT.
    if change['new_closing_after'] < -1e-9:
        errors = ['Mặt hàng thực tế đã xuất không đủ tồn để nhận số lượng này. Kiểm tra hàng nhập còn thiếu hoặc sửa Số lượng sửa theo thực tế.']
    for error in errors:
        if 'không đủ tồn tại một thời điểm' in error:
            issue('availability', f"Mặt hàng thực tế đã xuất {target['code']}: tồn cuối kỳ {_quantity_text(availability['closing_qty'])} {target['unit']}, "
                  f"dự thảo đang giữ {_quantity_text(availability['reserved_qty'])} {target['unit']}. "
                  f"Có thể dùng để sửa tối đa {_quantity_text(availability['available_qty'])} {target['unit']}; "
                  f"Số lượng sửa đang nhập {_quantity_text(float(qty))} {target['unit']}. "
                  'Bấm Xem tồn và dự thảo để đối chiếu. Chưa thay đổi kho.')
        else:
            issue('new_code', error.replace('hàng Excel', 'dòng xuất').replace('Excel', '').replace('Mã nhận', 'Mặt hàng thực tế đã xuất'))
    token = None
    if not issues:
        token = _store(conn, 'preview', dict(snapshot=snapshot, changes=[change], errors=[],
                                           mode='deficit_only_v1', origin='web'))
    return dict(token=token, can_confirm=not issues, issues=issues, changes=[change], availability=availability)


def register_routes(app, ctx):
    try:
        from .output_stock_hold_release import register_routes as register_release
    except ImportError:
        from output_stock_hold_release import register_routes as register_release
    register_release(app, ctx)

    @app.get('/api/inventory/output-remap/shortages')
    def output_web_shortages():
        try:
            with ctx['db']() as conn:
                result = review_shortages(conn, request.args.get('from'), request.args.get('to'))
            return jsonify(ok=True, **result)
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except sqlite3.Error:
            return jsonify(ok=False, error='Kho đang được cập nhật. Bấm Cập nhật số liệu để thử lại.'), 409

    @app.post('/api/inventory/output-remap/web-preview')
    def output_web_preview():
        try:
            with ctx['db']() as conn:
                result = preview_web(conn, request.get_json(silent=True) or {})
            return jsonify(ok=True, **result)
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except sqlite3.Error:
            return jsonify(ok=False, error='Chưa xem trước được vì kho đang được cập nhật. Thông tin đã nhập vẫn còn; bấm Cập nhật số liệu rồi xem trước lại.'), 409
