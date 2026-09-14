"""Supplier returns retain signed quantities and costs in the purchase source."""
try:
    from .purchase_money_adjustments import key
except ImportError:
    from purchase_money_adjustments import key

RETURN_KIND = 'supplier_return'
RETURN_LABEL = 'Trả hàng nhà cung cấp'


def approved_return_source(work_date, supplier, kitchen, code, name, unit, numbers):
    """Source facts confirmed by the customer on 14/09; never infer other negatives."""
    return (
        work_date == '2026-09-08' and key(unit) == 'kg'
        and numbers['base_qty'] == -1
        and all(numbers[f] == 0 for f in ('damaged_qty', 'added_qty', 'reduced_qty', 'missing_qty'))
        and (key(supplier), key(kitchen), key(code), key(name), numbers['buy_price']) in {
            ('phong', 'suppy', 'j000024', 'quanhan', 80000),
            ('viet', 'sumi', 'm000309', 'tralaidongtrung', 270000),
        }
    )
