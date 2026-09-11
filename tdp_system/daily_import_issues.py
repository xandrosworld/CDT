"""Customer-facing row diagnostics, without identity/reference sheet values."""
from openpyxl.utils import get_column_letter


def issue_details(rows):
    details = []
    fields = (
        ('thuế', ('tax',)), ('giá bán', ('sell_price',)), ('chưa có giá', ('sell_price',)), ('giá mua', ('buy_price',)),
        ('thành tiền', ('amount',)), ('thực tế', ('actual_qty',)),
        ('thực nhận', ('actual_received', 'actual_qty')),
        ('thực giao', ('actual_delivered',)), ('mã bếp', ('kitchen',)),
        ('nhà thầu', ('contractor',)), ('mã hàng', ('product_code',)),
        ('tên hàng', ('product_name',)), ('ncc', ('supplier',)),
        ('nhà cung cấp', ('supplier',)), ('đơn vị', ('unit',)),
        ('số lượng', ('qty', 'base_qty', 'order_qty')),
    )
    for row in rows:
        errors, warnings = row.get('errors') or [], row.get('warnings') or []
        if not errors and not warnings:
            continue
        columns = row.get('_issue_columns') or {}
        number = row.get('source_row')
        cells = []
        for message in errors + warnings:
            for label, keys in fields:
                if label in str(message).lower():
                    for key in keys:
                        if columns.get(key) and number:
                            cell = f'{get_column_letter(columns[key])}{number}'
                            if cell not in cells:
                                cells.append(cell)
                            break
        details.append({'row': number, 'cells': cells,
                        'code': row.get('product_code') or '',
                        'name': row.get('product_name') or '',
                        'kitchen': row.get('kitchen') or '',
                        'errors': errors, 'warnings': warnings})
    return details
