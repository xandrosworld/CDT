"""Refresh actual issued invoices before producing another order export."""
import threading
import time

REFRESH_LOCK = threading.RLock()


class SourceSnapshot:
    """Complete provider read, reused inside the short local transaction."""
    def __init__(self, client, start, end):
        try:
            from .invoice_output_sync import _minvoice_series_codes, _minvoice_page, _identity
        except ImportError:
            from invoice_output_sync import _minvoice_series_codes, _minvoice_page, _identity
        self.config = getattr(client, 'config', None)
        self.is_test_environment = getattr(client, 'is_test_environment', False)
        self.rows = {}
        deadline = time.monotonic() + 600
        pages = 0
        self.identities = set()
        for code in _minvoice_series_codes(client, start, end):
            rows = []; total = 1; expected_total = None
            while len(rows) < total:
                if pages >= 50 or time.monotonic() >= deadline:
                    raise ValueError('Chưa tải hết hóa đơn M-Invoice; sẽ thử lại, chưa dùng bản tải dở.')
                part, total = _minvoice_page(client, date_from=start, date_to=end,
                                            series=code, offset=len(rows), size=199)
                if expected_total is not None and total != expected_total:
                    raise ValueError('Danh sách M-Invoice thay đổi trong lúc tải; cần cập nhật lại đầy đủ.')
                expected_total = total
                for row in part:
                    identity = _identity(row)['identity_key']
                    if identity in self.identities:
                        raise ValueError('M-Invoice trả trùng hóa đơn giữa các trang; chưa xác nhận đã tải đủ.')
                    self.identities.add(identity)
                rows.extend(part); pages += 1
            self.rows[code] = rows

    def get_invoice_series(self):
        return [{'value': code} for code in self.rows]

    def get_outgoing_invoices(self, start_date, end_date, series, start=0, count=199, **kwargs):
        rows = self.rows[series]
        return {'data': rows[start:start+count], 'total': len(rows)}


def source_version(conn):
    return [tuple(r) for r in conn.execute("SELECT id,raw_json FROM outgoing_source_invoices ORDER BY id")]
try:
    from .invoice_workbench import prepare_sync_batch
    from .invoice_output_sync import sync_output_batch
    from .invoice_inventory import post_output_invoice, InvoiceInventoryError
    from .outgoing_source_scope import scope_report
    from .outgoing_waiting import refresh_waiting
    from .outgoing_sent_reconcile import reconcile_sent
except ImportError:
    from invoice_workbench import prepare_sync_batch
    from invoice_output_sync import sync_output_batch
    from invoice_inventory import post_output_invoice, InvoiceInventoryError
    from outgoing_source_scope import scope_report
    from outgoing_waiting import refresh_waiting
    from outgoing_sent_reconcile import reconcile_sent


def refresh_sources(db_factory, client_factory, now_iso, start, end):
    if not REFRESH_LOCK.acquire(timeout=3):
        raise ValueError('Đang có lượt cập nhật M-Invoice khác. Chờ lượt đó hoàn tất rồi bấm lại “4. Kiểm tra tồn và tạo file”; chưa gửi thêm bản nháp.')
    try:
        return _refresh_sources(db_factory, client_factory, now_iso, start, end)
    finally:
        REFRESH_LOCK.release()


def _refresh_sources(db_factory, client_factory, now_iso, start, end):
    # Source sync is committed independently of export. A blocked export must
    # not discard newly discovered signed invoices and allow the next retry.
    with db_factory() as conn:
        first=conn.execute("SELECT MIN(work_date) FROM batches WHERE status='approved'").fetchone()[0]
        start=min(start,first) if first else start
        tenant=(conn.execute("SELECT value FROM settings WHERE key='tenant_code'").fetchone() or ['TDP'])[0] or 'TDP'
        version=source_version(conn)
        known={r[0] for r in conn.execute("""SELECT identity_key FROM outgoing_source_invoices
            WHERE source='minvoice' AND source_status_class='issued' AND invoice_date BETWEEN ? AND ?""",(start,end))}
    snapshot=SourceSnapshot(client_factory(),start,end)
    if not known.issubset(snapshot.identities):
        raise ValueError('M-Invoice chưa trả đủ hóa đơn đã ký từng được đối chiếu trong kỳ. Chưa dùng danh sách thiếu để tính phần chưa xuất.')
    with db_factory() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if source_version(conn)!=version:
            raise ValueError('Hóa đơn vừa được cập nhật trong lượt khác. Hãy thử lại để lấy dữ liệu mới nhất.')
        batch,_=prepare_sync_batch(conn,tenant=tenant,source='minvoice',invoice_type='output',
                                  date_from=start,date_to=end,now_iso=now_iso,audit_event=None)
        conn.execute("UPDATE invoice_sync_batches SET source_cursor='{}' WHERE id=?",(batch['id'],))
        result=sync_output_batch(conn,snapshot,batch['id'],now_iso,max_pages=50,page_size=199)
    if not result['complete']:
        raise ValueError('M-Invoice chưa tải hết hóa đơn. Bấm cập nhật tiếp trước khi xuất file mới.')
    with db_factory() as conn:
        conn.execute('BEGIN IMMEDIATE')
        postings=[];blocked=[]
        for r in scope_report(conn,start,end):
            if r['scope']=='unresolved' or r['stock_status'] in ('posted','not_inventory'):continue
            try:
                postings.append(post_output_invoice(conn,r['id'],confirmed=True,now_iso=now_iso))
            except InvoiceInventoryError as exc:
                blocked.append({'id':r['id'],'number':r['number'],'error':str(exc)})
        sent=reconcile_sent(conn,now_iso())
        blocked.extend(sent['blocked'])
        waiting=refresh_waiting(conn,now_iso(),fill=False)
        sources=scope_report(conn,start,end)
    return {'sync':result,'posted':postings,'blocked':blocked,'linked_drafts':sent['linked'],'waiting':waiting,'sources':sources,
            'from':start,'to':end,'checked_at':now_iso()}
