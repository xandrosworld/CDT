"""Calendar-month weighted average, independent of invoice sales revenue."""
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

try:
    from .invoice_valuation import InvoiceValuationError, moving_average_report, _date
except ImportError:
    from invoice_valuation import InvoiceValuationError, moving_average_report, _date


def monthly_average_report(conn, *, date_from, date_to, include_zero=False, include_events=False):
    start, end = _date(date_from, 'Từ ngày'), _date(date_to, 'Đến ngày')
    first = date.fromisoformat(start)
    last = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    if first.day != 1 or end != last.isoformat():
        raise InvoiceValuationError('Báo cáo NXT bình quân tháng cần chọn từ ngày đầu đến ngày cuối cùng của một tháng.',
                                    code='full_calendar_month_required', status=400)
    report = moving_average_report(conn, date_from=start, date_to=end, include_zero=True, include_events=False)
    opening_date = report['opening_date']
    if not opening_date:
        earliest = conn.execute("SELECT MIN(txn_date) FROM invoice_inventory_ledger WHERE status='posted'").fetchone()[0]
        opening_date = earliest or start
    previous = {}
    if opening_date[:7] < start[:7]:
        previous_end = first - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
        previous = {r['product_code']: r for r in monthly_average_report(conn,
            date_from=previous_start.isoformat(), date_to=previous_end.isoformat(), include_zero=True)['items']}
    money = lambda value: value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    number = lambda value: Decimal(str(value))
    result = []
    for item in report['items']:
        if item['product_code'] in previous:
            item['opening_value'] = previous[item['product_code']]['closing_value']
        available_qty = number(item['opening_qty']) + number(item['input_qty'])
        available_value = number(item['opening_value']) + number(item['input_value'])
        average = available_value / available_qty if available_qty != 0 else Decimal(0)
        closing = money(number(item['closing_qty']) * average) if available_qty != 0 else available_value
        item.update(average_unit_cost=float(average.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)),
                    closing_value=float(closing), output_value=float(available_value - closing))
        # Chronological shortages and old moving-cost snapshots do not determine
        # a month's average. Negative quantities/values still require review.
        if number(item['opening_qty']) < 0:
            item['valuation_status'] = 'negative_opening_review'
        elif number(item['closing_qty']) < 0 or available_qty < 0 or available_value < 0:
            item['valuation_status'] = 'pending_source_cost'
        elif available_qty == 0 and available_value != 0:
            item['valuation_status'] = 'zero_qty_value_review'
        else:
            item['valuation_status'] = 'ok'
        if include_zero or any(item[k] != 0 for k in ('opening_qty', 'input_qty', 'output_qty', 'closing_qty',
                                                     'opening_value', 'input_value', 'closing_value')):
            result.append(item)
    report.update(items=result, valuation_method='monthly_weighted_average', events=[],
                  rounding=dict(quantity_decimals=6, unit_cost_decimals=6, money_decimals=2,
                                method='MONTHLY_WEIGHTED_AVERAGE'))
    return report
