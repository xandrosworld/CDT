"""Recognize the verified B:P purchase layout, including its subtotal header."""
import math
import re
import unicodedata


def normalized_header(value):
    text = str(value or '').replace('đ', 'd').replace('Đ', 'D')
    text = unicodedata.normalize('NFKD', text).casefold()
    return re.sub('[^a-z0-9]', '', ''.join(c for c in text if not unicodedata.combining(c)))


def customer_purchase_fields(values):
    # These positions are verified against the customer's 03/09 workbook.
    # Never infer an amount column from a numeric heading alone.
    expected = {
        2: ('product_code', {'mahang'}), 3: ('kitchen', {'mabep'}),
        4: ('work_date', {'ngay', ''}), 5: ('product_name', {'tenhang'}),
        6: ('base_qty', {'soluong'}), 7: ('unit', {'dvt'}),
        8: ('supplier', {'ncc'}), 9: ('note', {'ghichudathang', 'ghichu'}),
        10: ('buy_price', {'dongia', 'giamua', 'dongiamua'}),
        11: ('damaged_qty', {'hong'}), 12: ('added_qty', {'them'}),
        13: ('reduced_qty', {'giam'}), 14: ('missing_qty', {'thieu'}),
        15: ('actual_qty', {'slthucte'}),
    }
    if len(values) < 16 or any(normalized_header(values[col - 1]) not in aliases
                               for col, (_, aliases) in expected.items()):
        return {}
    amount = values[15]
    numeric = isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount)
    subtotal = bool(re.fullmatch(r'=SUBTOTAL\((?:9|109),\$?P\$?\d+:\$?P\$?\d+\)',
                                str(amount).upper().replace(' ', '')))
    if not (numeric or subtotal or normalized_header(amount) == 'thanhtien'):
        return {}
    return {**{field: col for col, (field, _) in expected.items()}, 'amount': 16}
