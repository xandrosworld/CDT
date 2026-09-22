"""An order price change invalidates its unsent invoice snapshot."""
from decimal import Decimal, InvalidOperation


def same_price(left, right):
    try:
        a, b = Decimal(str(left)), Decimal(str(right))
        return a.is_finite() and b.is_finite() and abs(a-b) <= Decimal('0.000001')
    except (InvalidOperation, ValueError, TypeError):
        return False


def price_message(conn, draft_id):
    draft = conn.execute('SELECT status,minvoice_status FROM outgoing_invoice_drafts WHERE id=?', (draft_id,)).fetchone()
    if not draft or draft['status'] != 'draft':
        return ''
    # Allocation amount/qty can differ after rounding VND. Compare the stored
    # source price, not that effective price or the converted price per kg.
    rows = conn.execute('''SELECT COALESCE(a.source_unit_price,l.unit_price) source_price,o.sell_price
        FROM outgoing_order_allocations l JOIN orders o ON o.id=l.order_id
        LEFT JOIN outgoing_line_allocations a ON a.line_id=l.id AND a.order_id=l.order_id
        WHERE l.draft_id=?''', (draft_id,))
    if all(same_price(r['source_price'], r['sell_price']) for r in rows):
        return ''
    if draft['minvoice_status'] in ('saved', 'saving', 'unknown'):
        return ('Giá đơn gốc đã thay đổi sau khi chuẩn bị bản nháp đã gửi M-Invoice. '
                'Đối chiếu bản nháp trên M-Invoice với giá đơn gốc trước khi ký; không gửi thêm bản mới.')
    return ('Giá đơn gốc đã thay đổi; bảng kê đang giữ giá cũ. '
            'Bấm “4. Kiểm tra tồn và tạo file” để cập nhật giá, rồi kiểm tra và xác nhận gửi lại.')


def assert_current_prices(conn, draft_id):
    message = price_message(conn, draft_id)
    if message:
        raise ValueError(message)
