"""Resolve the approved order backlog without relying on the active day."""
from datetime import datetime, timedelta, timezone


def business_today():
    return datetime.now(timezone(timedelta(hours=7))).date().isoformat()


def resolve_scope(conn, body, validate_date):
    cumulative = body.get('scope') == 'unissued' or not (body.get('from') or body.get('to'))
    if body.get('scope') not in (None, '', 'unissued', 'approved_range'):
        raise ValueError('Phạm vi bảng kê không hợp lệ')
    contractor = str(body.get('contractor') or '').strip().upper()
    if contractor == '*':
        contractor = ''
    if cumulative:
        end = validate_date(body['to'], 'Đến hết ngày đơn') if body.get('to') else business_today()
        first = conn.execute("""SELECT MIN(b.work_date) FROM batches b
            WHERE b.status='approved' AND b.work_date<=?
              AND EXISTS(SELECT 1 FROM orders o WHERE o.batch_id=b.id
                         AND (?='' OR o.contractor=?))""", (end, contractor, contractor)).fetchone()[0]
        start = first or end
    else:
        start = validate_date(body.get('from'), 'Từ ngày')
        end = validate_date(body.get('to'), 'Đến ngày')
        if start > end:
            raise ValueError('Từ ngày phải nhỏ hơn hoặc bằng Đến ngày')
    return start, end, contractor, cumulative
