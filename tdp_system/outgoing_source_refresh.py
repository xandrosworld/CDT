"""Refresh actual issued invoices before producing another order export."""
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
    # Source sync is committed independently of export. A blocked export must
    # not discard newly discovered signed invoices and allow the next retry.
    with db_factory() as conn:
        conn.execute('BEGIN IMMEDIATE')
        first=conn.execute("SELECT MIN(work_date) FROM batches WHERE status='approved'").fetchone()[0]
        start=min(start,first) if first else start
        tenant=(conn.execute("SELECT value FROM settings WHERE key='tenant_code'").fetchone() or ['TDP'])[0] or 'TDP'
        batch,_=prepare_sync_batch(conn,tenant=tenant,source='minvoice',invoice_type='output',
                                  date_from=start,date_to=end,now_iso=now_iso,audit_event=None)
        result=sync_output_batch(conn,client_factory(),batch['id'],now_iso,max_pages=10,page_size=199)
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
