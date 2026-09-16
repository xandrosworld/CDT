"""Round a purchase sheet once, with stable whole-dong line allocations.

Keep source quantity, price and amount unchanged. Distribute only the rounding
remainder to fractional lines, minimizing their rounding error. The resulting
line amounts sum to the rounded sheet total and remain additive by supplier.
"""
from decimal import Decimal, ROUND_HALF_UP


def line_rounding_adjustment(row):
    if row.get('source_type') != 'current_purchase' or not row['actual_qty']:
        return 0
    raw = (Decimal(str(row['actual_qty'])) * Decimal(str(row['buy_price']))).quantize(Decimal('.000001'))
    rounded = int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    delta = int(row['amount']) - rounded
    return delta if raw != rounded and abs(delta) == 1 else 0


def rounded_purchase_amounts(rows):
    exact = []
    for row in rows:
        amount = Decimal(str(row['amount']))
        product = (Decimal(str(row['actual_qty'])) * Decimal(str(row['buy_price']))).quantize(Decimal('.000001'))
        # Monetary deductions and explicit source amounts must keep their own
        # value; they are not reconstructed as zero quantity times zero price.
        if not row['actual_qty'] or abs(amount - product) > 1:
            product = amount
        exact.append(product)
    amounts = [int(v.quantize(Decimal('1'), rounding=ROUND_HALF_UP)) for v in exact]
    delta = int(sum(exact, Decimal(0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) - sum(amounts)
    if delta:
        direction = 1 if delta > 0 else -1
        fractional = [i for i, value in enumerate(exact) if value != amounts[i]]
        fractional.sort(key=lambda i: (
            -direction * (exact[i] - amounts[i]),
            int(rows[i].get('source_row') or 0),
            str(rows[i].get('row_key') or rows[i].get('source_key') or ''),
        ))
        assert abs(delta) <= len(fractional)
        for i in fractional[:abs(delta)]:
            amounts[i] += direction
    return amounts
