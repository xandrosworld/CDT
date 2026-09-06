"""Atomic, optimistic and retry-safe edits from the live worksheet."""
import hashlib
import json
import math

from flask import jsonify, request


def row_revision(row):
    return hashlib.sha256(json.dumps(dict(row), sort_keys=True, default=str,
                                     ensure_ascii=False).encode()).hexdigest()


def init_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS worksheet_receipts (
        request_id TEXT PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES batches(id)
        ON DELETE CASCADE, payload_hash TEXT NOT NULL, created_at TEXT NOT NULL)""")


class EditError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def register(app, h):
    @app.get('/api/orders/worksheet')
    def read_worksheet():
        try:
            batch_id = int(request.args.get('batch_id') or 0)
            if batch_id <= 0: raise ValueError()
        except (ValueError, TypeError):
            return jsonify(ok=False, error='Thiếu phiên đơn'), 400
        with h['db']() as conn:
            conn.execute('BEGIN')
            payload = h['batch_payload'](conn, batch_id)
            if not payload['batch']:
                return jsonify(ok=False, error='Không tìm thấy phiên đơn'), 404
            return jsonify(ok=True, **payload)

    @app.put('/api/orders/worksheet')
    def save_worksheet():
        body = request.get_json(force=True) or {}
        try:
            batch_id = int(body.get('batch_id') or 0)
            receipt = str(body.get('request_id') or '')
            patches = body.get('items')
            if not batch_id or not receipt or len(receipt) > 100 or not isinstance(patches, list) or not patches or len(patches) > 5000:
                raise EditError('Thiếu phiên đơn, mã lần lưu hoặc danh sách ô cần sửa')
            digest = row_revision(body)
            with h['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                previous = conn.execute('SELECT * FROM worksheet_receipts WHERE request_id=?', (receipt,)).fetchone()
                if previous:
                    if previous['payload_hash'] != digest or previous['batch_id'] != batch_id:
                        raise EditError('Mã lần lưu đã được sử dụng cho nội dung khác', 409)
                    return jsonify(ok=True, idempotent=True, **h['batch_payload'](conn, batch_id))
                batch = conn.execute('SELECT * FROM batches WHERE id=?', (batch_id,)).fetchone()
                if not batch:
                    raise EditError('Phiên đơn không còn tồn tại', 404)
                blocked = h['batch_mutation_blocker'](conn, batch_id)
                if blocked:
                    raise EditError(blocked, 409)
                lookup = h['product_lookup'](conn)
                prepared, seen = [], set()
                actor = str(body.get('actor') or '').strip()
                reason = str(body.get('reason') or '').strip()
                numeric = {'qty', 'actual_received', 'actual_delivered', 'buy_price', 'sell_price',
                           'damaged_qty', 'supplier_return_qty', 'customer_return_qty'}
                for patch in patches:
                    if not isinstance(patch, dict):
                        raise EditError('Dòng cập nhật không hợp lệ')
                    ident = int(patch.get('id') or 0)
                    if ident in seen:
                        raise EditError('Danh sách cập nhật bị trùng dòng')
                    seen.add(ident)
                    raw = conn.execute('SELECT * FROM orders WHERE id=? AND batch_id=?', (ident, batch_id)).fetchone()
                    if not raw or row_revision(raw) != patch.get('revision'):
                        raise EditError('Dòng đã thay đổi hoặc được thay bằng file mới. Giữ phần đang nhập; mở lại bảng để đối chiếu.', 409)
                    current = dict(raw)
                    values = patch.get('values')
                    if not isinstance(values, dict) or not values or set(values) - set(h['ORDER_FIELDS']):
                        raise EditError('Có cột không được phép sửa')
                    for field, value in values.items():
                        if field in numeric:
                            if value == '' or value is None:
                                value = 0
                            value = float(value)
                            if not math.isfinite(value) or value < 0:
                                raise EditError('Số lượng và giá phải là số không âm; dòng ' + str(ident))
                        elif field == 'purchase_list':
                            if value not in (0, 1, False, True):
                                raise EditError('Bảng kê chỉ nhận 0 hoặc 1')
                        elif not isinstance(value, str) or len(value) > 4000:
                            raise EditError('Nội dung ô không hợp lệ hoặc quá dài')
                        current[field] = value
                    changed_price = float(current['sell_price']) != float(raw['sell_price'])
                    if changed_price and (not actor or len(actor) > 120 or not reason or len(reason) > 500):
                        raise EditError('Điền người sửa giá và lý do ở thanh trên để tự lưu giá bán')
                    if changed_price and ((str(current['invoice_nature']) == '2' and current['sell_price'] != 0) or
                                          (str(current['invoice_nature']) != '2' and current['sell_price'] <= 0)):
                        raise EditError('Giá hàng thường phải lớn hơn 0; giá khuyến mại phải bằng 0')
                    resolved = h['resolve_order'](conn, current, batch['work_date'], *lookup)
                    selected_price = current['sell_price']
                    current.update({key: resolved[key] for key in h['ORDER_FIELDS'] if key in resolved})
                    # Price edits must use exactly the audited value, including zero for gifts.
                    current['sell_price'] = selected_price
                    # The stored override may differ from the quotation used by resolve_order.
                    # Validate the value actually saved, particularly an unfinished zero price.
                    if selected_price <= 0 and current['invoice_nature'] != '2' and 'Thiếu giá bán' not in resolved['errors']:
                        resolved['errors'].append('Thiếu giá bán')
                    loss_warning = 'Giá bán thấp hơn giá mua – cần xác nhận bán lỗ'
                    resolved['warnings'] = [item for item in resolved['warnings'] if item != loss_warning]
                    if 0 < selected_price < current['buy_price'] and current['invoice_nature'] != '2':
                        resolved['warnings'].append(loss_warning)
                    prepared.append((raw, current, resolved, changed_price))
                timestamp = h['now_iso']()
                h['clear_batch_derived_inventory'](conn, batch_id)
                fields = h['ORDER_FIELDS']
                for raw, current, resolved, changed_price in prepared:
                    conn.execute('UPDATE orders SET ' + ','.join(key + '=?' for key in fields) +
                                 ',errors=?,warnings=?,updated_at=? WHERE id=?',
                                 tuple(current[key] for key in fields) +
                                 (json.dumps(resolved['errors'], ensure_ascii=False),
                                  json.dumps(resolved['warnings'], ensure_ascii=False), timestamp, raw['id']))
                    if changed_price:
                        revision = int(raw['sell_price_revision'] or 1)
                        conn.execute("UPDATE orders SET sell_price_revision=?,sell_price_source='manual_override',sell_price_override_at=? WHERE id=?",
                                     (revision + 1, timestamp, raw['id']))
                        conn.execute('''INSERT INTO order_sell_price_overrides
                            (order_id,batch_id,old_price,new_price,reason,actor,expected_revision,new_revision,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?)''',
                                     (raw['id'], batch_id, raw['sell_price'], current['sell_price'], reason, actor, revision, revision + 1, timestamp))
                    h['audit_event'](conn, 'order.worksheet.edit', entity_type='order', entity_id=raw['id'],
                                     metadata={'actor': actor, 'reason': reason, 'before': dict(raw),
                                               'after': current, 'request_id': receipt})
                conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?", (batch_id,))
                h['sync_payable_ledger'](conn, timestamp=timestamp)
                h['sync_receivable_ledger'](conn, timestamp=timestamp)
                conn.execute('INSERT INTO worksheet_receipts VALUES(?,?,?,?)', (receipt, batch_id, digest, timestamp))
                return jsonify(ok=True, updated=len(prepared), **h['batch_payload'](conn, batch_id))
        except EditError as error:
            return jsonify(ok=False, error=str(error)), error.status
        except (ValueError, TypeError, OverflowError):
            return jsonify(ok=False, error='Giá trị ô không hợp lệ; chưa lưu lần sửa này'), 400
