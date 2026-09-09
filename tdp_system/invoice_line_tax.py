"""Read line VAT without allocating invoice totals or changing stored invoices."""
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def number(value):
    if value is None or value == '' or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def tax_rate_label(value):
    """M-Invoice's -1/-2 are categories, not negative percentages."""
    rate = '' if value is None else str(value).strip()
    numeric = number(rate.removesuffix('%').replace(',', '.').strip())
    if numeric == Decimal('-1'):
        return 'KCT'
    if numeric == Decimal('-2'):
        return 'KKKNT'
    return rate


def tax_fields(line, raw_line=None):
    raw_line = raw_line if isinstance(raw_line, dict) else {}
    rate = tax_rate_label(line.get('tax_rate'))
    tax, note = None, 'Chưa có tiền thuế nguồn'
    for key in ('vatAmount', 'tthue', 'taxAmount', 'tax_amount'):
        if key in raw_line and raw_line[key] is not None and raw_line[key] != '':
            tax = number(raw_line[key])
            note = 'Thuế theo dòng hóa đơn' if tax is not None else 'Tiền thuế nguồn không hợp lệ'
            break
    else:
        percent = number(rate.removesuffix('%').replace(',', '.').strip())
        amount = number(line.get('amount'))
        if amount is not None and percent is not None and 0 <= percent <= 100:
            tax = (amount * percent / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            note = 'Tính từ tiền dòng × thuế suất; đối chiếu tổng HĐ'
        elif rate.upper() in {'KCT', 'KKKNT', 'KKKNTTHUE'}:
            tax, note = Decimal(0), 'Theo ký hiệu thuế nguồn: ' + rate
    amount = number(line.get('amount'))
    return dict(tax_rate=rate, line_tax_amount=float(tax) if tax is not None else None,
                amount_with_tax=float(amount + tax) if amount is not None and tax is not None else None,
                tax_note=note)


def annotate_invoice_tax(invoice, raw_json):
    try:
        raw = json.loads(raw_json or '{}')
    except (TypeError, ValueError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    keys = ('invoiceDetail', 'details', 'hdhhdvu', 'invoiceItems') if raw.get('_tdp_source_contract') == 'minvoice_portal_v1' else ('hdhhdvu', 'invoiceItems', 'details', 'invoiceDetail')
    details = next((raw[k] for k in keys if isinstance(raw.get(k), list)), [])
    for line in invoice['items']:
        index = int(line.get('line_index') or 0) - 1
        line.update(tax_fields(line, details[index] if 0 <= index < len(details) else None))
    known = complete_sum(invoice['items'], 'line_tax_amount')
    invoice['detail_tax_amount'] = known
    invoice['detail_tax_difference'] = (float(number(invoice.get('tax_amount')) - number(known))
        if known is not None and number(invoice.get('tax_amount')) is not None else None)


def complete_sum(rows, field):
    values = [number(row.get(field)) for row in rows]
    return float(sum(values, Decimal(0))) if all(v is not None for v in values) else None


def grouped_tax(rows):
    return dict(tax_rate=' / '.join(dict.fromkeys(str(r.get('tax_rate') or 'Chưa rõ') for r in rows)),
                line_tax_amount=complete_sum(rows, 'line_tax_amount'),
                amount_with_tax=complete_sum(rows, 'amount_with_tax'),
                tax_note='; '.join(dict.fromkeys(r.get('tax_note') or 'Chưa có tiền thuế nguồn' for r in rows)))
