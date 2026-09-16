"""Approve a reviewed order and its BK receipts in one database transaction."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

try:
    from . import bk_import as bk
    from .purchase_returns import RETURN_KIND
    from .purchase_summary_export import _people_by_name, _resolved_identity
    from .seller_identity_catalog import is_excluded_seller
    from .invoice_product_identity import catalog_name_matches
except ImportError:
    import bk_import as bk
    from purchase_returns import RETURN_KIND
    from purchase_summary_export import _people_by_name, _resolved_identity
    from seller_identity_catalog import is_excluded_seller
    from invoice_product_identity import catalog_name_matches


def init_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS batch_bk_approvals (
        batch_id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL,
        source_hash TEXT NOT NULL, approved_at TEXT NOT NULL)""")


def linked_document(conn, batch_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='batch_bk_approvals'").fetchone():
        return None
    return conn.execute("""SELECT d.*,a.source_hash batch_source_hash
        FROM batch_bk_approvals a LEFT JOIN bk_import_documents d ON d.id=a.document_id
        WHERE a.batch_id=?""", (batch_id,)).fetchone()


def mutation_blocker(conn, batch_id):
    doc = linked_document(conn, batch_id)
    if doc and (doc['status'] == 'posted' or doc['id'] is None):
        return 'Bảng kê của đơn đã ghi nhập kho. Hoàn tác bảng kê trong lịch sử nhập trước khi sửa đơn.'
    return ''


def _number(value, label):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0:
            raise ValueError()
        return n
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(label + ' không hợp lệ') from None


def source_state_hash(batch, orders, canonical):
    """Hash the immutable financial source plus its reviewed seller metadata."""
    fields = ('id', 'order_id', 'source_row', 'source_sheet', 'work_date', 'product_code',
              'product_name', 'unit', 'supplier', 'purchase_list', 'actual_qty', 'actual_received',
              'damaged_qty', 'supplier_return_qty', 'buy_price', 'sell_price', 'seller', 'cccd', 'status')
    return bk._hash_json({'date': batch['work_date'], 'canonical': bool(canonical),
        'rows': [{k: r.get(k) for k in fields} for r in (canonical or list(orders.values()))],
        'orders': [{k: r.get(k) for k in fields} for r in orders.values()]})


def prepare(conn, batch_id):
    batch = conn.execute('SELECT * FROM batches WHERE id=?', (batch_id,)).fetchone()
    if not batch:
        raise bk.BKImportError('Không tìm thấy phiên đơn', status=404)
    orders = {r['id']: dict(r) for r in conn.execute('SELECT * FROM orders WHERE batch_id=? ORDER BY id', (batch_id,))}
    canonical = [dict(r) for r in conn.execute('SELECT * FROM purchase_workbook_lines WHERE batch_id=? ORDER BY id', (batch_id,))]
    products = {r['code']: dict(r) for r in conn.execute('SELECT * FROM products')}
    people = _people_by_name(conn)
    rate = bk._purchase_rate(conn)
    sources = canonical if canonical else list(orders.values())
    previous = linked_document(conn, batch_id)
    reference = f'TDP-BATCH-{batch_id}'
    if previous and previous['status'] == 'reversed':
        reference += f'-AFTER-{previous["id"]}'
    # Capture all source rows, including flags becoming false or quantities becoming zero.
    source_hash = source_state_hash(batch, orders, canonical)
    prior_bk = [dict(r) for r in conn.execute('''SELECT l.product_code,l.document_id,l.source_key,l.snapshot_hash,l.source_reference
        FROM bk_import_lines l JOIN bk_import_documents d ON d.id=l.document_id
        WHERE d.status='posted' AND l.document_date=? ORDER BY l.id''', (batch['work_date'],))]
    fingerprint = bk._hash_json({'source': source_hash, 'rate': str(rate),
        'products': {r.get('product_code'): products.get(r.get('product_code')) for r in sources},
        'people': people, 'prior_bk': prior_bk})
    result = {'rows': [], 'issues': [], 'overlaps': [], 'excludedRows': 0, 'sourceHash': fingerprint,
              'alreadyPosted': False, 'documentId': None, 'amount': 0, 'ratePercent': float(rate * 100),
              'purchasePricedRows': 0, 'purchasePricedAmount': 0,
              '_source_state_hash': source_hash}
    if previous and previous['status'] == 'posted':
        if previous['batch_source_hash'] != source_hash:
            raise bk.BKImportError('Đơn đã đổi sau khi ghi bảng kê; cần đối chiếu, không ghi thêm kho.', status=409)
        count = bk._verify_posted_document(conn, previous)
        result.update(alreadyPosted=True, documentId=previous['id'], rowCount=count,
                      amount=previous['amount_total'], canApprove=True)
        return result
    if previous and previous['id'] is None:
        raise bk.BKImportError('Thiếu chứng từ bảng kê đã duyệt; cần đối chiếu lịch sử.', status=409)
    for line in sources:
        # A supplier return reduces purchasing/payables; it is not a new BK
        # receipt. Importing this sheet must not fabricate invoice stock.
        if canonical and line.get('line_kind') == RETURN_KIND:
            continue
        order = orders.get(line.get('order_id')) if canonical else line
        product = products.get(str(line.get('product_code') or '').upper(), {})
        flag = (order or product).get('purchase_list', 0)
        if not flag or bk._key(line.get('supplier')) == 'kho':
            continue
        seller, _, _, identity_issues = _resolved_identity(order, product, people)
        if is_excluded_seller(seller):
            result['excludedRows'] += 1
            continue
        row_ref = line.get('source_row') or line['id']
        errors = []
        try:
            if canonical:
                qty = _number(line.get('actual_qty'), 'Lượng thực nhận')
                if qty and line.get('status') != 'confirmed':
                    errors.append('Phần mua chưa được chốt')
            else:
                qty = _number(line.get('actual_received'), 'Lượng thực nhận')
                qty -= _number(line.get('damaged_qty', 0), 'Lượng hỏng')
                qty -= _number(line.get('supplier_return_qty', 0), 'Lượng trả NCC')
                if qty < 0:
                    raise ValueError('Lượng hỏng/trả vượt lượng thực nhận')
            if qty == 0:
                continue
            purchase_only = bool(canonical) and line.get('order_id') is None
            if canonical and not purchase_only and order is None:
                raise ValueError('Dòng bán liên kết không thuộc phiên đơn; cần đối chiếu phần mua')
            cost = bk._prefilled_unit_cost(line if purchase_only else order, rate, purchase_only=purchase_only)
        except ValueError as exc:
            errors.append(str(exc))
            qty = cost = Decimal(0)
        errors.extend(identity_issues)
        if not product or not catalog_name_matches(conn, line.get('product_name'), line.get('product_code')):
            errors.append('Tên hàng chưa khớp mã danh mục')
        if product and bk._key(line.get('unit')) != bk._key(product.get('unit')):
            errors.append('Đơn vị nhập khác danh mục; cần kiểm tra lượng nhập')
        if line.get('work_date') != batch['work_date']:
            errors.append('Ngày mua khác ngày đơn')
        if errors:
            result['issues'].append({'row': row_ref, 'code': line.get('product_code'),
                                     'name': line.get('product_name'), 'orderId': (order or {}).get('id'),
                                     'sourceSheet': line.get('source_sheet') or '',
                                     'workDate': line.get('work_date') or '',
                                     'kitchen': line.get('kitchen') or '', 'errors': errors})
            continue
        result['rows'].append({'document_date': line['work_date'], 'source_type': bk.BK_IMPORT_SOURCE_TYPE,
            '_source_row': row_ref, '_order_id': (order or {}).get('id'),
            'source_reference': reference, 'source_line': line['id'], 'product_code': product['code'],
            'product_name': product['name'], 'unit': product['unit'], 'qty': float(qty),
            'unit_cost': float(cost), 'amount': float((qty*cost).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)),
            'source_party': line.get('supplier') or seller,
            'note': f'Duyệt đơn và bảng kê; dòng nguồn {row_ref}; ' + (
                'giá BK theo giá mua đã chốt (không có dòng bán).' if purchase_only
                else f'giá BK {rate * 100}% giá bán.')})
        if purchase_only:
            result['purchasePricedRows'] += 1
            result['purchasePricedAmount'] += result['rows'][-1]['amount']
        matches = conn.execute("""SELECT DISTINCT i.invoice_series,i.invoice_number FROM invoice_inventory_effective_ledger l
            JOIN msmi_invoices i ON i.id=l.source_invoice_id
            WHERE l.source_invoice_table='msmi_invoices' AND l.direction='input' AND l.status='posted'
              AND l.event_type='POST' AND l.product_code=? AND l.txn_date=?
              AND NOT EXISTS (SELECT 1 FROM invoice_inventory_effective_ledger r
                  WHERE r.reverses_event_key=l.event_key AND r.status='posted')""",
            (product['code'], line['work_date'])).fetchall()
        if matches:
            result['overlaps'].append({'row': row_ref, 'code': product['code'],
                'invoices': [f'{m[0]} / {m[1]}' for m in matches]})
        existing_bk = sorted({r['document_id'] for r in prior_bk if r['product_code'] == product['code']
                              and r['source_reference'].casefold() != reference.casefold()})
        if existing_bk:
            result['overlaps'].append({'row': row_ref, 'code': product['code'], 'kind': 'bk',
                'invoices': [f'Bảng kê đã nhập #{doc_id}' for doc_id in existing_bk]})
    result['rowCount'] = len(result['rows'])
    if result['rows'] and not result['issues']:
        payload = bk.build_bk_import_template(result['rows'])
        parsed = bk.parse_bk_preview(conn, payload)
        for item in parsed['rows']:
            if item['errors']:
                source = result['rows'][item['sourceRow'] - 4]
                result['issues'].append({'row': source['_source_row'], 'code': item['productCode'],
                                         'orderId': source['_order_id'], 'errors': item['errors']})
        result['_pending'] = {'rows': parsed['rows'], 'content_hash': parsed['contentHash'],
            'source_hash': fingerprint, 'database_state_hash': bk._database_state_hash(conn, parsed['rows']),
            'filename': f'Bang-ke-duyet-don-{batch["work_date"]}-{batch_id}.xlsx'}
        result['amount'] = parsed['totals']['amount']
    result['canApprove'] = not result['issues']
    return result


def public_preview(result):
    return {key: value for key, value in result.items() if key != 'rows' and not key.startswith('_')}


def approve(conn, batch_id, body, timestamp, audit_event):
    result = prepare(conn, batch_id)
    if result['alreadyPosted']:
        return {'inventoryLines': result['rowCount'], 'newInventoryLines': 0,
                'documentId': result['documentId'], 'idempotent': True}
    if body.get('source_hash') and body['source_hash'] != result['sourceHash']:
        raise bk.BKImportError('Đơn đã thay đổi; hãy kiểm tra và duyệt lại.', code='batch_bk_stale', status=409)
    if result['issues']:
        detail = '; '.join(f"Dòng {r['row']} ({r['code']}): {', '.join(r['errors'])}" for r in result['issues'][:8])
        raise bk.BKImportError('Bảng kê chưa đủ dữ liệu. ' + detail, code='batch_bk_invalid', status=409)
    if result['rows'] and body.get('confirm_bk') is not True:
        raise bk.BKImportError('Duyệt đơn kèm bảng kê: cần xác nhận số lượng và giá đang hiển thị.',
                               code='batch_bk_confirmation_required', status=409)
    if result['rows'] and body.get('source_hash') != result['sourceHash']:
        raise bk.BKImportError('Hãy xem lại đơn và bảng kê trước khi duyệt.', code='batch_bk_stale', status=409)
    if result['overlaps'] and body.get('confirm_separate_purchases') is not True:
        raise bk.BKImportError('Có mã đã nhập kho cùng ngày từ hóa đơn hoặc bảng kê. Xác nhận đây là lần mua riêng trước khi duyệt.',
                               code='batch_bk_overlap', status=409)
    if not result['rows']:
        return {'inventoryLines': 0, 'newInventoryLines': 0, 'idempotent': False}
    posted = bk._post_pending(conn, result['_pending'], timestamp, audit_event)
    conn.execute('''INSERT INTO batch_bk_approvals(batch_id,document_id,source_hash,approved_at) VALUES(?,?,?,?)
        ON CONFLICT(batch_id) DO UPDATE SET document_id=excluded.document_id,
        source_hash=excluded.source_hash,approved_at=excluded.approved_at''',
        (batch_id, posted['documentId'], result['_source_state_hash'], timestamp))
    return posted
