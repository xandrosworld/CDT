"""Measured invoice weights, with unchanged order quantities and stock lineage."""
import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SCHEMA = '''
CREATE TABLE IF NOT EXISTS outgoing_order_weights (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
    order_snapshot TEXT NOT NULL, base_qty REAL NOT NULL, actual_kg REAL NOT NULL,
    revision TEXT NOT NULL, note TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outgoing_weight_exports (
    line_id INTEGER PRIMARY KEY REFERENCES outgoing_invoice_lines(id) ON DELETE CASCADE,
    input_snapshot TEXT NOT NULL, output_json TEXT NOT NULL,
    mapping_revision_id INTEGER NOT NULL REFERENCES invoice_mapping_revisions(id),
    created_at TEXT NOT NULL
);
'''


def key(value):
    import unicodedata
    return unicodedata.normalize('NFKC', str(value or '')).strip().casefold()


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def dec(value):
    return Decimal(str(value))


def order_snapshot(order):
    return packed({k: order[k] for k in ('id', 'batch_id', 'product_code', 'contractor',
        'unit', 'actual_delivered', 'customer_return_qty', 'sell_price', 'tax', 'invoice_nature')})


def confirmed_weights(conn):
    result = {}
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_order_weights'").fetchone():
        return result
    for row in conn.execute('''SELECT w.*,o.*,p.unit stock_unit,u.invoice_unit
        FROM outgoing_order_weights w JOIN orders o ON o.id=w.order_id
        JOIN products p ON p.code=o.product_code
        JOIN outgoing_product_units u ON u.product_code=p.code
        JOIN batches b ON b.id=o.batch_id WHERE b.status='approved' '''):
        if (row['order_snapshot'] == order_snapshot(row) and key(row['unit']) == key(row['stock_unit'])
                and key(row['invoice_unit']) == 'kg' and key(row['unit']) != 'kg'):
            result[row['order_id']] = dict(row)
    return result


def _lock(conn, order_id):
    return conn.execute('''SELECT DISTINCT d.id FROM outgoing_order_allocations a
        JOIN outgoing_invoice_drafts d ON d.id=a.draft_id
        LEFT JOIN outgoing_weight_exports e ON e.line_id=a.id
        WHERE a.order_id=? AND ((d.status='issued' AND e.line_id IS NOT NULL) OR (d.status='draft' AND
        (e.line_id IS NOT NULL OR COALESCE(d.minvoice_status,'') IN ('saved','saving','unknown'))))
        LIMIT 1''', (order_id,)).fetchone()


def workbench(conn, cutoff, contractor=''):
    from_module = __package__
    if from_module:
        from .outgoing_unissued import issued_allocations
        from .outgoing_contractors import excluded_codes, excluded_order_ids
    else:
        from outgoing_unissued import issued_allocations
        from outgoing_contractors import excluded_codes, excluded_order_ids
    issued, warnings = issued_allocations(conn)
    excluded=excluded_codes(conn)
    skipped=excluded_order_ids(conn)
    warnings=[w for w in warnings if w['contractor'] not in excluded]
    weights = confirmed_weights(conn)
    result = []
    for row in conn.execute('''SELECT o.*,p.unit stock_unit,
        COALESCE(NULLIF(u.invoice_unit,''),p.unit) invoice_unit,
        COALESCE(NULLIF(n.invoice_name,''),o.product_name) invoice_name
        FROM orders o JOIN batches b ON b.id=o.batch_id JOIN products p ON p.code=o.product_code
        LEFT JOIN outgoing_product_units u ON u.product_code=p.code
        LEFT JOIN outgoing_product_names n ON n.product_code=p.code
        WHERE b.status='approved' AND o.work_date<=? AND (?='' OR o.contractor=?)
        ORDER BY o.work_date,o.contractor,o.kitchen,o.id''', (cutoff, contractor, contractor)):
        if row['contractor'] in excluded or row['id'] in skipped:
            continue
        remaining = max(float(row['actual_delivered'] or 0)-float(row['customer_return_qty'] or 0)-issued.get(row['id'], 0), 0)
        if remaining <= 1e-8 or (key(row['unit']) == key(row['stock_unit']) == key(row['invoice_unit'])):
            continue
        saved = conn.execute('SELECT * FROM outgoing_order_weights WHERE order_id=?', (row['id'],)).fetchone()
        confirmed = weights.get(row['id'])
        lock = _lock(conn, row['id'])
        reason = ''
        if key(row['unit']) != key(row['stock_unit']):
            reason = f'Đơn ghi {row["unit"]}, kho ghi {row["stock_unit"]}. Cần xác định ĐVT đúng và đối chiếu số lượng của đơn gốc.'
        elif key(row['invoice_unit']) != 'kg':
            reason = f'Đơn/kho ghi {row["stock_unit"]}, hóa đơn ghi {row["invoice_unit"]}. Cần xác nhận cách gọi/quy cách tương ứng trước khi đổi ĐVT hoặc số lượng.'
        elif lock:
            reason = f'Đã dùng trong dự thảo {lock[0]} hoặc hóa đơn. Cần đối chiếu file đã tải trước khi đổi kg.'
        elif any(not w['contractor'] or w['contractor'] == row['contractor'] for w in warnings):
            reason = 'Cần cập nhật/đối chiếu hóa đơn đã ký để xác định đúng phần chưa xuất.'
        kg = float(dec(remaining)*dec(confirmed['actual_kg'])/dec(confirmed['base_qty'])) if confirmed else None
        amount = int((dec(remaining)*dec(row['sell_price'] or 0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        token = hashlib.sha256(packed([order_snapshot(row), remaining, row['stock_unit'],
            row['invoice_unit'], saved['revision'] if saved else '', bool(lock)]).encode()).hexdigest()
        result.append({'order_id': row['id'], 'date': row['work_date'], 'contractor': row['contractor'],
            'kitchen': row['kitchen'], 'product_code': row['product_code'], 'invoice_name': row['invoice_name'],
            'unit': row['unit'], 'stock_unit': row['stock_unit'], 'invoice_unit': row['invoice_unit'],
            'review_kind': 'actual_kg' if key(row['unit'])==key(row['stock_unit']) and key(row['invoice_unit'])=='kg' else 'unit_mismatch',
            'remaining_qty': remaining, 'amount': amount, 'actual_kg': kg,
            'price_per_kg': float(dec(amount)/dec(kg)) if kg else None,
            'confirmed': bool(confirmed), 'editable': not reason, 'reason': reason,
            'token': token, 'note': saved['note'] if saved else '',
            'updated_at': saved['updated_at'] if saved else ''})
    result.sort(key=lambda r: (not r['editable'], r['confirmed'], r['date'], r['contractor'], r['order_id']))
    return {'rows': result, 'asof': cutoff, 'contractor': contractor, 'warnings': warnings}


def save_weight(conn, order_id, body, timestamp):
    if not isinstance(body, dict):
        raise ValueError('Dữ liệu quy đổi không hợp lệ.')
    order = conn.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    if not order:
        raise ValueError('Không tìm thấy dòng đơn.')
    current = next((r for r in workbench(conn, order['work_date'], order['contractor'])['rows']
                    if r['order_id'] == order_id), None)
    if not current or body.get('token') != current['token']:
        raise ValueError('Dòng đơn hoặc số chưa xuất đã thay đổi. Tải lại danh sách trước khi lưu.')
    if not current['editable']:
        raise ValueError(current['reason'])
    try:
        raw = body.get('actual_kg')
        if isinstance(raw, bool):
            raise InvalidOperation
        kg = dec(raw)
        if not kg.is_finite() or not 0 < kg < 1_000_000 or kg != kg.quantize(Decimal('.000001')):
            raise InvalidOperation
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Nhập tổng kg thực tế lớn hơn 0, nhỏ hơn 1.000.000 và tối đa 6 số lẻ.') from None
    note = str(body.get('note') or '').strip()
    if not note or len(note) > 500 or body.get('confirmed_actual_weight') is not True:
        raise ValueError('Ghi căn cứ số kg và xác nhận đây là tổng kg thực tế của phần chưa xuất.')
    conn.execute('''INSERT INTO outgoing_order_weights VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(order_id) DO UPDATE SET order_snapshot=excluded.order_snapshot,
        base_qty=excluded.base_qty,actual_kg=excluded.actual_kg,revision=excluded.revision,
        note=excluded.note,updated_at=excluded.updated_at''',
        (order_id, order_snapshot(order), current['remaining_qty'], float(kg), uuid.uuid4().hex, note, timestamp))
    conn.execute('''INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('outgoing.actual_weight','order',?,'ok',?,?,?)''', (str(order_id), note,
        packed({'base_qty': current['remaining_qty'], 'base_unit': current['unit'], 'actual_kg': float(kg),
                'previous_kg': current['actual_kg'], 'amount': current['amount']}), timestamp))
    return {'order_id': order_id, 'actual_kg': float(kg), 'amount': current['amount'],
            'price_per_kg': float(dec(current['amount'])/kg)}


def invoice_rows(conn, rows, *, freeze=False, timestamp=''):
    """One stock line stays one invoice line; distinct measured orders never merge."""
    weights = confirmed_weights(conn)
    rows = [dict(r) for r in rows]
    snapshots = {r['line_id']: r for r in conn.execute('''SELECT * FROM outgoing_weight_exports
        WHERE line_id IN (SELECT value FROM json_each(?))''',
        (packed([r.get('line_id') or r.get('id') for r in rows]),))}
    codes = {w['product_code'] for w in weights.values()}
    result = []
    for source in rows:
        row = dict(source)
        lid = row.get('line_id') or row.get('id')
        frozen = snapshots.get(lid)
        if row['product_code'] not in codes and not frozen:
            result.append(row)
            continue
        allocations = [dict(r) for r in conn.execute('SELECT * FROM outgoing_order_allocations WHERE id=? ORDER BY order_id', (lid,))]
        converted = [weights.get(r['order_id']) for r in allocations]
        if not any(converted):
            if frozen:
                raise ValueError('Đơn hoặc quy đổi đã thay đổi sau khi tải file; cần đối chiếu dự thảo trước khi xuất tiếp.')
            result.append(row)
            continue
        if not allocations or not all(converted) or len({w['order_id'] for w in converted}) != 1:
            raise ValueError('Dự thảo gộp nhiều dòng quy đổi; tính lại dự thảo để tách đúng số kg từng dòng.')
        w = converted[0]
        if key(row['unit']) != key(w['unit']) or row['product_code'] != w['product_code']:
            raise ValueError('Dòng hóa đơn không khớp đơn đã xác nhận kg.')
        if abs(sum(r['qty'] for r in allocations)-row['qty']) > 1e-8:
            raise ValueError('Phân bổ quy đổi không khớp số lượng dự thảo.')
        snapshot = packed([row['product_code'], row['product_name'], row['qty'], row['unit'], row['unit_price'],
                           row['amount'], row['tax'], row['invoice_nature'], w['revision']])
        if frozen:
            if snapshot != frozen['input_snapshot']:
                raise ValueError('Dự thảo đã thay đổi sau khi tải file có quy đổi; cần đối chiếu bản đã tải.')
            result.append({**row, **json.loads(frozen['output_json'])})
            continue
        kg = (dec(row['qty'])*dec(w['actual_kg'])/dec(w['base_qty'])).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)
        if kg <= 0:
            raise ValueError('Kg của phần được xuất quá nhỏ; giữ chờ để xuất cùng phần còn lại.')
        price = (dec(row['amount'])/kg).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)
        if (kg*price).quantize(Decimal('1'), rounding=ROUND_HALF_UP) != dec(row['amount']):
            raise ValueError('Chưa thể giữ đúng thành tiền với độ chính xác đơn giá M-Invoice; cần đối chiếu số kg.')
        output = {'qty': float(kg), 'unit': 'Kg', 'unit_price': float(price), 'stock_qty': row['qty'],
                  'stock_unit': row['unit'], 'weight_order_id': w['order_id']}
        if freeze:
            factor = float(dec(row['qty'])/kg)
            scope = f'actual-weight-export-{lid}-{w["revision"]}'
            mid = conn.execute('''INSERT INTO invoice_line_mappings(tenant,source,invoice_type,scope_key,
                source_item_code,source_item_name,source_unit,product_code,target_unit,mapping_status,
                conversion_factor,confirmed_at,updated_at) VALUES('TDP','tdp_actual_weight',
                'OUTPUT_ELECTRONIC_INVOICE',?,?,?,?,?,?,'confirmed',?,?,?)''',
                (scope,row['product_code'],row['product_name'],'Kg',row['product_code'],row['unit'],factor,timestamp,timestamp)).lastrowid
            rid = conn.execute('''INSERT INTO invoice_mapping_revisions(revision_key,mapping_id,product_code,
                source_unit,target_unit,conversion_factor,created_at) VALUES(?,?,?,'Kg',?,?,?)''',
                (scope,mid,row['product_code'],row['unit'],factor,timestamp)).lastrowid
            conn.execute('INSERT INTO outgoing_weight_exports VALUES(?,?,?,?,?)',
                         (lid,snapshot,packed(output),rid,timestamp))
        result.append({**row, **output})
    return result


def signed_stock_snapshot(conn, item_id):
    """Resolve only an explicitly linked issued draft and an identical signed file.

    Other Kg sources for products with measured package conversions must wait;
    the historical code-only rule cannot treat kg as a count of packages.
    """
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_order_weights'").fetchone():
        return None
    if not conn.execute('SELECT 1 FROM outgoing_order_weights UNION ALL SELECT 1 FROM outgoing_weight_exports LIMIT 1').fetchone():
        return None
    item = conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?', (item_id,)).fetchone()
    if not item:
        return None
    code = item['product_code'] or item['source_item_code']
    product = conn.execute('SELECT unit FROM products WHERE code=?', (code,)).fetchone()
    source = conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?', (item['invoice_id'],)).fetchone()
    linked_weight = conn.execute('''SELECT 1 FROM outgoing_invoice_drafts d
        JOIN outgoing_invoice_lines l ON l.draft_id=d.id JOIN outgoing_weight_exports e ON e.line_id=l.id
        WHERE d.status='issued' AND UPPER(TRIM(d.issued_invoice_series))=UPPER(TRIM(?))
        AND TRIM(d.issued_invoice_number)=TRIM(?) AND COALESCE(d.issued_invoice_date,d.invoice_date)=?''',
        (source['invoice_series'],source['invoice_number'],source['invoice_date'])).fetchone()
    protected = linked_weight or (product and key(item['source_unit']) == 'kg' and key(product['unit']) != 'kg' and conn.execute(
        'SELECT 1 FROM outgoing_order_weights w JOIN orders o ON o.id=w.order_id WHERE o.product_code=?', (code,)).fetchone())
    if not protected:
        return None
    def blocked():
        try:
            from .invoice_mapping import InvoiceMappingError
        except ImportError:
            from invoice_mapping import InvoiceMappingError
        return InvoiceMappingError('Hóa đơn Kg cần liên kết với dự thảo đã xác nhận kg thực tế; chưa được lấy số kg làm số gói trừ kho.', code='actual_weight_source_unlinked', status=409)
    if source['source'] != 'minvoice' or source['source_status_class'] != 'issued' or source['sync_status'] != 'synced':
        raise blocked()
    drafts = conn.execute('''SELECT * FROM outgoing_invoice_drafts WHERE status='issued'
        AND UPPER(TRIM(issued_invoice_series))=UPPER(TRIM(?)) AND TRIM(issued_invoice_number)=TRIM(?)
        AND COALESCE(issued_invoice_date,invoice_date)=?''',
        (source['invoice_series'],source['invoice_number'],source['invoice_date'])).fetchall()
    if len(drafts) != 1 or not source['buyer_tax_code'] or key(drafts[0]['buyer_tax_code_snapshot']) != key(source['buyer_tax_code']):
        raise blocked()
    local = [dict(r) for r in conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=? ORDER BY id', (drafts[0]['id'],))]
    # Issued names/weights are frozen; never derive a signed quantity from later catalog edits.
    expected = []
    for row in local:
        saved = conn.execute('SELECT * FROM outgoing_weight_exports WHERE line_id=?', (row['id'],)).fetchone()
        expected.append((row, {**row, **json.loads(saved['output_json'])} if saved else row, saved))
    actual = conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index', (source['id'],)).fetchall()
    if len(actual) != len(expected):
        raise blocked()
    answer = None
    for remote, (stock, exported, saved) in zip(actual, expected):
        try:
            from .contract_modules import invoice_tax_percent
        except ImportError:
            from contract_modules import invoice_tax_percent
        if (remote['source_item_code'] != stock['product_code'] or key(remote['source_item_name']) != key(stock['product_name'])
                or key(remote['source_unit']) != key(exported['unit']) or abs(remote['qty']-exported['qty']) > 1e-6
                or abs(remote['amount']-stock['amount']) > .01
                or invoice_tax_percent(remote['tax_rate']) != invoice_tax_percent(stock['tax'])
                or str(remote['source_nature'] or '1') != str(stock['invoice_nature'])
                or abs(remote['unit_price']-exported['unit_price']) > .00001):
            raise blocked()
        if remote['id'] == item_id:
            if remote['product_code'] != stock['product_code']:
                raise blocked()
            if not saved:
                return None  # Unconverted line in the same verified invoice uses its ordinary mapping.
            answer = {'item_id': item_id, 'line_index': remote['line_index'], 'product_code': code,
                'conversion_factor': stock['qty']/exported['qty'], 'stock_qty': stock['qty'],
                'stock_unit_price': stock['amount']/stock['qty'], 'amount': stock['amount'],
                'mapping_id': conn.execute('SELECT mapping_id FROM invoice_mapping_revisions WHERE id=?',
                                           (saved['mapping_revision_id'],)).fetchone()[0],
                'mapping_revision_id': saved['mapping_revision_id'], 'actual_weight': True}
    if not answer:
        raise blocked()
    return answer
