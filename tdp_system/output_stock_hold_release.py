"""Explicitly retire one product from an unsigned draft, preserving its evidence."""
import hashlib
import json
import sqlite3
import uuid

from flask import jsonify, request

try:
    from .output_stock_remap import _store, _load, RemapError
    from .outgoing_signed_guard import signed_draft_sources
    from .outgoing_export_lineage import catalog, matches
    from .outgoing_substitution import _recompute_draft_totals
    from .contract_modules import audit
except ImportError:
    from output_stock_remap import _store, _load, RemapError
    from outgoing_signed_guard import signed_draft_sources
    from outgoing_export_lineage import catalog, matches
    from outgoing_substitution import _recompute_draft_totals
    from contract_modules import audit


def state(conn, draft_id, code):
    draft = conn.execute('SELECT * FROM outgoing_invoice_drafts WHERE id=?', (draft_id,)).fetchone()
    if not draft:
        raise RemapError('Không tìm thấy dự thảo. Bấm Cập nhật số liệu rồi kiểm tra lại.')
    draft = dict(draft)
    if (draft['status'] != 'draft' or draft['minvoice_status'] not in (None, '', 'not_sent')
            or any(draft.get(k) for k in ('minvoice_remote_id', 'minvoice_key_api', 'issued_invoice_number', 'issued_at'))
            or draft_id in signed_draft_sources(conn)):
        raise RemapError('Dự thảo đã gửi hoặc cần đối chiếu M-Invoice. Không thể bỏ mặt hàng tại đây.')
    if conn.execute("SELECT 1 FROM outgoing_substitution_actions WHERE draft_id=? AND status='active'", (draft_id,)).fetchone():
        raise RemapError('Dự thảo có lựa chọn hàng thay thế. Cần xử lý tại phần lựa chọn hàng thay thế trước.')
    exports = [r for r in catalog(conn) if r['id'] == draft_id]
    for invoice in (conn.execute("SELECT * FROM outgoing_source_invoices WHERE source_status_class='issued'") if exports else []):
        if any(r['id'] == draft_id for r in matches(conn, invoice, draft['contractor'], exports)):
            raise RemapError('File của dự thảo đã khớp hóa đơn phát hành. Cần đối chiếu hóa đơn, không bỏ mặt hàng khỏi dự thảo.')
    lines = [dict(r) for r in conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=? ORDER BY id', (draft_id,))]
    holds = [dict(r) for r in conn.execute("SELECT * FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved' ORDER BY id", (str(draft_id),))]
    allocations = [dict(r) for r in conn.execute('SELECT a.* FROM outgoing_line_allocations a JOIN outgoing_invoice_lines l ON l.id=a.line_id WHERE l.draft_id=? ORDER BY a.line_id,a.order_id', (draft_id,))]
    days = [r[0] for r in conn.execute('SELECT batch_id FROM outgoing_consolidated_days WHERE draft_id=? ORDER BY batch_id', (draft_id,))]
    removed = [r for r in lines if r['product_code'] == code]
    if not removed:
        raise RemapError('Mặt hàng không còn trong dự thảo. Bấm Cập nhật số liệu rồi kiểm tra lại.')
    # Never copy a broken or ambiguous reservation into another draft.
    if {str(r['id']) for r in lines} != {r['source_line'] for r in holds}:
        raise RemapError('Phần giữ tồn của dự thảo chưa khớp các dòng hàng. Cần đối chiếu dự thảo trước.')
    for line in lines:
        rows = [r for r in holds if r['source_line'] == str(line['id'])]
        if (len(rows) != 1 or rows[0]['product_code'] != line['product_code']
                or abs(rows[0]['qty_out'] - line['qty']) > 1e-8):
            raise RemapError('Số lượng giữ tồn chưa khớp dự thảo. Cần đối chiếu dự thảo trước.')
    result = dict(draft=draft, lines=lines, holds=holds, allocations=allocations, days=days, code=code)
    result['version'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def preview(conn, draft_id, code):
    current = state(conn, draft_id, code)
    token = _store(conn, 'hold_release', current)
    return dict(token=token, draft_id=draft_id, contractor=current['draft']['contractor'], product_code=code,
                removed=[r for r in current['lines'] if r['product_code'] == code],
                kept=[r for r in current['lines'] if r['product_code'] != code])


def _insert(conn, table, values):
    # Table and column identifiers come exclusively from internal SQLite rows.
    keys = list(values)
    return conn.execute('INSERT INTO ' + table + '(' + ','.join(keys) + ') VALUES(' + ','.join('?' for _ in keys) + ')',
                        [values[k] for k in keys]).lastrowid


def confirm(conn, body, timestamp):
    if body.get('confirmed') is not True or not str(body.get('actor') or '').strip():
        raise RemapError('Điền Người xác nhận và tích ô xác nhận bỏ mặt hàng khỏi dự thảo.')
    token = str(body.get('token') or '')
    done = conn.execute("SELECT metadata_json FROM audit_log WHERE event_type='outgoing.release_product' AND entity_id=? AND status='ok'", (token,)).fetchone()
    if done:
        return dict(json.loads(done[0]), idempotent=True)
    _, saved = _load(conn, token, 'hold_release', 1800)
    current = state(conn, saved['draft']['id'], saved['code'])
    if current['version'] != saved['version']:
        raise RemapError('Dự thảo vừa thay đổi. Bấm Bỏ riêng mặt hàng này để xem trước lại; chưa thay đổi dữ liệu.')
    draft, code = current['draft'], current['code']
    kept = [r for r in current['lines'] if r['product_code'] != code]
    new_id = None
    if kept:
        round_no = conn.execute('SELECT COALESCE(MAX(round_no),0)+1 FROM outgoing_invoice_drafts WHERE batch_id=? AND contractor=?', (draft['batch_id'], draft['contractor'])).fetchone()[0]
        new_id = _insert(conn, 'outgoing_invoice_drafts', dict(batch_id=draft['batch_id'], contractor=draft['contractor'],
            invoice_date=draft['invoice_date'], status='draft', created_at=timestamp, round_no=round_no,
            draft_kind=draft['draft_kind'], external_key_uuid=uuid.uuid4().hex.upper()))
        for line in kept:
            lid = _insert(conn, 'outgoing_invoice_lines', {**{k:v for k,v in line.items() if k not in ('id', 'draft_id')}, 'draft_id':new_id})
            for row in current['allocations']:
                if row['line_id'] == line['id']:
                    _insert(conn, 'outgoing_line_allocations', {**row, 'line_id':lid})
            hold = next(r for r in current['holds'] if r['source_line'] == str(line['id']))
            _insert(conn, 'inventory_transactions', {**{k:v for k,v in hold.items() if k != 'id'},
                'source_id':str(new_id), 'source_line':str(lid), 'created_at':timestamp, 'updated_at':timestamp})
        for day in current['days']:
            conn.execute('INSERT INTO outgoing_consolidated_days VALUES(?,?)', (new_id, day))
        _recompute_draft_totals(conn, new_id)
    # Keep original lines, allocations, downloaded evidence and original dates intact.
    conn.execute("UPDATE outgoing_invoice_drafts SET status='cancelled' WHERE id=?", (draft['id'],))
    conn.execute("UPDATE inventory_transactions SET status='cancelled',updated_at=? WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'", (timestamp, str(draft['id'])))
    result = dict(draft_id=draft['id'], replacement_draft_id=new_id, product_code=code,
                  released_qty=sum(r['qty'] for r in current['lines'] if r['product_code'] == code),
                  kept_lines=len(kept), actor=str(body['actor']).strip()[:100])
    audit(conn, lambda:timestamp, 'outgoing.release_product', 'ok', entity_type='outgoing_invoice', entity_id=token, metadata=result)
    return dict(result, idempotent=False)


def register_routes(app, ctx):
    @app.post('/api/inventory/output-remap/release-product/preview')
    def release_preview():
        body = request.get_json(silent=True) or {}
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                result = preview(conn, body.get('draft_id'), str(body.get('product_code') or ''))
            return jsonify(ok=True, **result)
        except (ValueError, sqlite3.Error) as exc:
            return jsonify(ok=False, error=str(exc) if isinstance(exc, ValueError) else 'Dự thảo đang được cập nhật. Thử lại bước xem trước.'), 409

    @app.post('/api/inventory/output-remap/release-product/confirm')
    def release_confirm():
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                result = confirm(conn, request.get_json(silent=True) or {}, ctx['now_iso']())
            return jsonify(ok=True, **result)
        except (ValueError, sqlite3.Error) as exc:
            return jsonify(ok=False, error=str(exc) if isinstance(exc, ValueError) else 'Chưa thay đổi dự thảo. Bấm Bỏ riêng mặt hàng này để kiểm tra lại.'), 409
