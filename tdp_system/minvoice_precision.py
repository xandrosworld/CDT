"""Compare linked invoice numbers using the provider's recorded currency precision.

Never use this to match unrelated invoices or to change source quantities.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def matches(actual, expected, document, field):
    try:
        a,b=Decimal(str(actual)),Decimal(str(expected))
        if not a.is_finite() or not b.is_finite():return False
        if abs(a-b)<=Decimal('.000001'):return True
        precision=document.get('_tdp_currency_precision') or {}
        places=precision.get(field)
        if not isinstance(places,int) or isinstance(places,bool) or not 0<=places<=6:return False
        # Only a currency configuration already in effect when the invoice was
        # created can explain its rounding. Later configuration is not evidence.
        changed=precision.get('effective_at') or ''
        created=document.get('creationTime') or ''
        if not changed or not created or changed[:19]>created[:19]:return False
        if precision.get('currency_id')!=document.get('currencyId'):return False
        # The sender serializes six decimals before the portal applies its
        # currency format. Remove SQLite float noise at that exact boundary.
        sent=b.quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
        return a==sent.quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
    except (InvalidOperation,ValueError,TypeError):return False
