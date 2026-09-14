"""Explain an empty export after its allocation transaction has rolled back."""
from collections import Counter
from urllib.parse import urlencode

try:
    from .outgoing_unissued import unissued_payload
except ImportError:
    from outgoing_unissued import unissued_payload


LABELS = {
    'stock_shortage': 'Chưa đủ tồn khả dụng',
    'rounding': 'Phần lẻ chưa đủ mức xuất',
    'unit_review': 'Đơn vị đơn hàng và danh mục chưa khớp',
    'source_review': 'Hóa đơn đã ký cần đối chiếu',
    'order_data': 'Thông tin đơn cần kiểm tra',
    'unknown_product': 'Mã hàng chưa khớp danh mục',
    'allocation_refresh': 'Cần kiểm tra lại phân bổ',
    'prepared': 'Đang nằm trong bảng kê đã chuẩn bị',
}


def empty_export_diagnostic(conn, period):
    data = unissued_payload(conn, period['to'], period['contractor'], start=period['from'], respect_export_choices=True)
    counts = Counter()
    for row in data['details']:
        codes = row.get('pending_codes') or []
        counts[codes[0] if codes else 'prepared' if row['drafted_qty'] > 0 else 'allocation_refresh'] += 1
    total = len(data['details'])
    party = period['contractor'] or 'Các nhà thầu đã chọn'
    message = (f'{party}: còn {total} dòng chưa xuất, chưa có lượng tạo được bảng kê mới.' if total
               else f'{party}: không còn dòng chưa xuất trong lựa chọn này.')
    groups = [{'code': code, 'label': LABELS[code], 'count': count} for code, count in counts.items()]
    query = urlencode({**period, 'portion': 'all'})
    return {
        'scope': period, 'message': message, 'unissued_rows': total,
        'excluded_rows': sum(not r['enabled'] for r in data['line_choices']),
        'groups': groups, 'rows': data['pending_rows'],
        'download_url': '/api/outgoing-invoices/unissued-template.zip?' + query,
        'read_only': True,
    }
