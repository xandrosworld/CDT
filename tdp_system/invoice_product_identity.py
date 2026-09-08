"""A source code is not proof that two differently named goods are the same."""
import hashlib
import json


def catalog_name_matches(conn, source_name, product_code):
    try:
        from .invoice_mapping import _normalized
    except ImportError:
        from invoice_mapping import _normalized
    row = conn.execute('SELECT name FROM products WHERE code=?', (product_code,)).fetchone()
    if not row or not _normalized(source_name):
        return False
    names = {_normalized(row['name'])}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_product_names'").fetchone():
        names.update(_normalized(r[0]) for r in conn.execute(
            'SELECT invoice_name FROM outgoing_product_names WHERE product_code=?', (product_code,)))
    return _normalized(source_name) in names


def identity_key(context, product):
    values = [context[k] for k in ('tenant', 'mapping_source', 'partner_key',
              'source_item_code', 'source_item_name', 'source_unit')]
    values += [product[k] for k in ('code', 'name', 'unit')]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def output_identity_warning(conn, item_id, *, context=None, product_code=None):
    try:
        from .invoice_mapping import _line_context, _normalized
    except ImportError:
        from invoice_mapping import _line_context, _normalized
    context = context or _line_context(conn, 'output', item_id)
    code = product_code if product_code is not None else context['product_code']
    if not code or not context['inventory_eligible'] or context['mapping_source'] != 'minvoice':
        return ''
    product = conn.execute('SELECT code,name,unit FROM products WHERE code=?', (code,)).fetchone()
    if not product or catalog_name_matches(conn, context['source_item_name'], code):
        return ''
    collision = _normalized(context['source_item_code']) == _normalized(code)
    # Also stop a bad source-code choice being taught to uncoded copies of that name.
    if not collision and not str(context['source_item_code'] or '').strip():
        for r in conn.execute(
            "SELECT * FROM invoice_line_mappings "
            "WHERE tenant=? AND source='minvoice' AND invoice_type=? AND product_code=?",
            (context['tenant'], context['invoice_type'], code)):
            if (_normalized(r['source_item_code']) != _normalized(code)
                    or _normalized(r['source_item_name']) != _normalized(context['source_item_name'])):
                continue
            original = dict(context, partner_key=r['partner_key'],source_item_code=r['source_item_code'],
                            source_item_name=r['source_item_name'],source_unit=r['source_unit'])
            if not conn.execute("SELECT 1 FROM audit_log WHERE event_type='invoice_mapping.identity_confirmed' "
                                "AND entity_id=? AND status='ok' LIMIT 1",(identity_key(original,product),)).fetchone():
                collision = True
                break
    if not collision:
        return ''
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='audit_log'").fetchone() and conn.execute(
        "SELECT 1 FROM audit_log WHERE event_type='invoice_mapping.identity_confirmed' "
        "AND entity_id=? AND status='ok' LIMIT 1", (identity_key(context, product),)
    ).fetchone():
        return ''
    return (f"Tên hàng nguồn: {context['source_item_name']} ({context['source_unit']}). "
            f"Mã kho {code}: {product['name']} ({product['unit']}). "
            "Tên không khớp; cần chọn lại mã hoặc xác nhận đây là cùng một mặt hàng trước khi ghi kho.")
