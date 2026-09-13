"""Use the order's explicit BK marker and the catalog stock unit at every exit."""
import unicodedata


def unit_key(value):
    return unicodedata.normalize('NFKC',str(value or '')).strip().casefold()


def unit_issues(conn, rows):
    try:
        from .outgoing_weights import confirmed_weights
    except ImportError:
        from outgoing_weights import confirmed_weights
    weights = confirmed_weights(conn)
    catalog={r['code']:r['unit'] for r in conn.execute('SELECT code,unit FROM products')}
    invoice_units={r['product_code']:r['invoice_unit'] for r in conn.execute('SELECT product_code,invoice_unit FROM outgoing_product_units')}
    issues={}
    for row in rows:
        code=row['product_code'];unit=row['unit'];expected=catalog.get(code,'')
        order_unit=row['order_unit'] if 'order_unit' in row.keys() else unit
        invoice_unit=invoice_units.get(code) or expected
        if not unit_key(unit) or unit_key(unit)!=unit_key(expected) or unit_key(order_unit)!=unit_key(unit):
            oid=row['order_id'] if 'order_id' in row.keys() else row['id']
            issues[oid]={'order_id':oid,'product_code':code,'unit':order_unit,'catalog_unit':expected,
                         'message':f'{code}: đơn ghi {order_unit or "(trống)"}, kho dùng {expected or "(trống)"}; giữ dòng này chờ xác nhận đơn vị/quy đổi.'}
        elif unit_key(invoice_unit)!=unit_key(expected):
            oid=row['order_id'] if 'order_id' in row.keys() else row['id']
            if oid in weights and weights[oid]['product_code'] == code:
                continue
            issues[oid]={'order_id':oid,'product_code':code,'unit':order_unit,'catalog_unit':expected,'invoice_unit':invoice_unit,
                         'message':f'{code}: ĐVT hóa đơn {invoice_unit}, đơn/kho {expected}; chưa có quy đổi được xác nhận. Giữ phần này chờ, không tự đổi số lượng hoặc đơn giá.'}
    return issues


def draft_policy_rows(conn, draft_id):
    return conn.execute('''SELECT a.*,o.purchase_list,o.work_date,o.contractor,o.unit order_unit
        FROM outgoing_order_allocations a JOIN orders o ON o.id=a.order_id
        WHERE a.draft_id=?''',(draft_id,)).fetchall()
