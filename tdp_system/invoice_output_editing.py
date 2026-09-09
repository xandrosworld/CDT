"""Keep product/unit editing independent from a portal total reconciliation hold."""
import json
from decimal import Decimal, InvalidOperation


PORTAL_TOTAL_MISMATCH = 'Tổng dòng hàng/thuế trên portal lệch tổng hóa đơn; giữ số nguồn, cần đối chiếu trước khi ghi kho hoặc lập hồ sơ VAT'


def output_amount_review(invoice):
    """Explain a monetary hold using source detail and header totals, without changing either."""
    row = dict(invoice)
    review_source = dict(row)
    if row.get('stock_status') == 'posted':
        review_source['stock_status'] = 'blocked'
    if row.get('error_message') != PORTAL_TOTAL_MISMATCH or not output_mapping_allowed(review_source):
        return None
    raw = json.loads(row['raw_json'])
    line_amount = sum(Decimal(str(line['amountWithoutVAT'])) for line in raw['invoiceDetail'])
    line_tax = sum(Decimal(str(line['vatAmount'])) for line in raw['invoiceDetail'])
    header_amount, header_tax, header_total = (
        Decimal(str(raw[key])) for key in ('totalAmountWithoutVAT', 'vatAmount', 'totalAmount'))
    return {
        'line_count': len(raw['invoiceDetail']),
        'comparisons': [
            {'kind': kind, 'detail': float(detail), 'header': float(header), 'difference': float(header - detail)}
            for kind, detail, header in (
                ('subtotal', line_amount, header_amount),
                ('tax', line_tax, header_tax),
                ('total', line_amount + line_tax, header_total),
            )
        ],
    }


def output_mapping_allowed(invoice):
    row = dict(invoice)
    if (row.get('source', row.get('mapping_source')) != 'minvoice'
            or row.get('source_status_class') != 'issued'
            or row.get('stock_status') in {'posted', 'reversed', 'reversal_required'}):
        return False
    if row.get('sync_status') == 'synced':
        return row.get('stock_status') != 'blocked'
    if (row.get('sync_status') != 'review_required' or row.get('stock_status') != 'blocked'
            or row.get('error_message') != PORTAL_TOTAL_MISMATCH):
        return False
    try:
        raw = json.loads(row.get('raw_json') or '{}')
        if raw.get('_tdp_source_contract') != 'minvoice_portal_v1':
            return False
        try:
            from .minvoice_portal import portal_validation_error, portal_status
        except ImportError:
            from minvoice_portal import portal_validation_error, portal_status
        if portal_status(raw)[1] != 'issued' or portal_validation_error(raw) != PORTAL_TOTAL_MISMATCH:
            return False
        # An amount difference alone is editable; incomplete/unsafe detail is not.
        for line in raw['invoiceDetail']:
            if type(line.get('property')) is not int or line['property'] not in {1, 2, 5}:
                return False
            for key in ('quantity', 'unitPrice', 'amountWithoutVAT', 'vatAmount'):
                value = line[key]
                number = Decimal(str(value))
                if isinstance(value, bool) or not number.is_finite() or number < 0:
                    return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation):
        return False
