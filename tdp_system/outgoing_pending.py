"""Explain the unallocated remainder without changing invoice or stock records."""
from collections import defaultdict
from decimal import Decimal

try:
    from .outgoing_consolidation import decimal, export_quantity
    from .outgoing_readiness import invoice_order_issues
    from .stock_tax_policy import exempt_order_codes
except ImportError:
    from outgoing_consolidation import decimal, export_quantity
    from outgoing_readiness import invoice_order_issues
    from stock_tax_policy import exempt_order_codes


def explain_pending(conn, orders, details, units, warnings, stock):
    """Keep readiness conservative: available but unallocated stock needs refresh."""
    by_id = {o['id']: o for o in orders}
    known = {r['code'] for r in conn.execute('SELECT code FROM products')}
    exempt = {party: exempt_order_codes(conn, [o for o in orders if o['contractor'] == party])
              for party in {o['contractor'] for o in orders}}
    groups = defaultdict(lambda: Decimal(0))
    held_groups = defaultdict(lambda: Decimal(0))
    pending_by_code = defaultdict(float)

    def key(r):
        return (r['contractor'], r['product_code'], r['unit'].strip().casefold(),
                str(r['tax']), decimal(r['unit_price']), r['invoice_nature'])

    for r in details:
        groups[key(r)] += decimal(r['unissued_qty'])
        held_groups[key(r)] += decimal(r['ready_qty'])
        if r['product_code'] not in exempt[r['contractor']] and r['order_id'] not in units:
            pending_by_code[r['product_code']] += r['waiting_qty']
    pending = {}
    for r in details:
        r['pending_reason'] = ''
        if r['waiting_qty'] <= 1e-8:
            continue
        o = by_id[r['order_id']]
        relevant = list(dict.fromkeys(w['message'] for w in warnings
                        if not w['contractor'] or w['contractor'] == r['contractor']))
        reasons = relevant[:1]
        if len(relevant)>1:
            reasons.append(f'Còn {len(relevant)-1} thông báo khác; xem mục đối chiếu hóa đơn / tồn kho.')
        if r['order_id'] in units:
            reasons.append(units[r['order_id']]['message'])
        for issue in invoice_order_issues([o]):
            reasons.extend(issue['messages'])
        if r['product_code'] not in known:
            reasons.append('Mã hàng chưa có trong danh mục; cần đối chiếu mã.')
        if not reasons:
            code = r['product_code']
            available = stock.get(code, {}).get('available_qty', 0)
            shortage = code not in exempt[r['contractor']] and available + 1e-8 < pending_by_code[code]
            if shortage:
                reasons.append('Chưa đủ tồn khả dụng cho phần còn chờ; cần bổ sung đầu vào hoặc kiểm tra lượng đang giữ ở bảng kê khác.')
            total = groups[key(r)]
            remainder = total - export_quantity(total, r['unit'])
            if remainder > Decimal('0.00000001'):
                step='0,1 kg' if r['unit'].strip().casefold()=='kg' else 'số nguyên '+r['unit']
                reasons.append(f'Có phần lẻ chưa đủ {step}; giữ lại để cộng dồn.')
            if not reasons or (not shortage and export_quantity(total,r['unit'])-held_groups[key(r)]>Decimal('0.00000001')):
                reasons.append('Chờ cập nhật phân bổ; bấm “Cập nhật phần còn chờ” để kiểm tra lại. Chưa kết luận là thiếu đầu vào.')
        r['pending_reason'] = ' · '.join(dict.fromkeys(reasons))
        group_key = (r['contractor'], r['product_code'], r['unit'].strip().casefold(), r['pending_reason'])
        item = pending.setdefault(group_key, {
            'contractor': r['contractor'], 'product_code': r['product_code'],
            'product_name': r['product_name'], 'unit': r['unit'], 'waiting_qty': 0,
            'first_date': r['work_date'], 'last_date': r['work_date'],
            'pending_reason': r['pending_reason'], 'order_rows': 0,
            'invoice_name': r.get('invoice_name') or r['product_name'],
            'stock_unit': stock.get(r['product_code'], {}).get('unit', r['unit']),
            'stock_available_qty': stock.get(r['product_code'], {}).get('available_qty', 0),
            'stock_reserved_qty': stock.get(r['product_code'], {}).get('reserved_qty', 0),
        })
        item['waiting_qty'] += r['waiting_qty']
        item['last_date'] = r['work_date']
        item['order_rows'] += 1
    return sorted(pending.values(), key=lambda r: (r['contractor'], r['product_name'], r['first_date'], r['pending_reason']))


def pending_payload(payload):
    """Select only waiting quantities; retain original totals for reconciliation."""
    return {**payload, 'portion': 'waiting',
            'rows': [r for r in payload['rows'] if r['waiting_qty'] > 1e-8],
            'details': [r for r in payload['details'] if r['waiting_qty'] > 1e-8]}
