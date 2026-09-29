"""Confirmed delivery identities from the customer's 2026-09-29 review.

These four goods were explicitly confirmed as delivered, not replaced by
vegetables. Do not treat an invoice label or unit edit as a substitution.
This is a narrow business rule, not fuzzy matching for the whole catalogue.
"""
import re
import unicodedata


CONFIRMED_DELIVERED_NAMES = {
    'N000006': 'Cau, trầu',
    'N000007': 'Chè cúng',
    'N000009': 'Hoa cúng',
    'N000057': 'Xôi cúng',
}


def name_key(value):
    text = unicodedata.normalize('NFKD', str(value or '').casefold()).replace('đ', 'd')
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in text if not unicodedata.combining(c)))


def identity_error(code, invoice_name):
    actual = CONFIRMED_DELIVERED_NAMES.get(str(code or '').strip().upper())
    if actual and invoice_name and name_key(invoice_name) != name_key(actual):
        return (f'{code}: hàng thực giao đã xác nhận là {actual}. '
                f'Tên xuất hóa đơn phải là {actual}; không dùng tên mặt hàng khác. '
                'Sửa Tên xuất hóa đơn rồi bấm Kiểm tra lại.')
    return ''
