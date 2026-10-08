"""Read-only evidence for payable portal replacements; never changes stock."""
import json


def verified_replacements(conn):
    try:
        from .minvoice_portal import portal_date, portal_validation_error
    except ImportError:
        from minvoice_portal import portal_date, portal_validation_error
    rows=[dict(r) for r in conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice'")]
    by_remote={}
    for r in rows: by_remote.setdefault((r['tenant'],r['remote_id']),[]).append(r)
    pairs=[]
    for new in rows:
        try:
            raw=json.loads(new['raw_json']); status=json.loads(new['source_status_raw'])
            if not isinstance(raw,dict):continue
            if (raw.get('_tdp_source_contract')!='minvoice_portal_v1' or status!={'invoiceStatus':3,'sendTaxStatus':4}
                or raw.get('invoiceStatus')!=3 or raw.get('sendTaxStatus')!=4
                or new['source_status_class']!='replaced' or portal_validation_error(raw)): continue
            candidates=by_remote.get((new['tenant'],raw.get('relatedInvoiceId')),[])
            if len(candidates)!=1: continue
            old=candidates[0]; previous=json.loads(old['source_status_raw']); oldraw=json.loads(old['raw_json'])
            if not isinstance(oldraw,dict):continue
            if (old['source_status_class']!='replaced' or previous!={'invoiceStatus':6,'sendTaxStatus':4}
                or not new['buyer_tax_code'] or old['buyer_tax_code']!=new['buyer_tax_code']
                or not raw.get('sellerTaxCode') or raw['sellerTaxCode']!=oldraw.get('sellerTaxCode')
                or str(raw.get('relatedInvoiceNumber'))!=old['invoice_number']
                or portal_date(raw.get('relatedInvoiceDate'))!=old['invoice_date']
                or str(raw.get('relatedTemplateCode',''))+str(raw.get('relatedInvoiceSerial',''))!=old['invoice_series']
                or raw.get('id')!=new['remote_id'] or raw.get('invoiceSerial')!=new['invoice_series']
                or str(raw.get('invoiceNumber'))!=new['invoice_number']
                or portal_date(raw.get('invoiceDate'))!=new['invoice_date']
                or raw.get('buyerTaxCode')!=new['buyer_tax_code']
                or new['invoice_date']<old['invoice_date']): continue
            if any(abs(float(raw[k])-new[v])>0.000001 for k,v in [('totalAmountWithoutVAT','subtotal'),('vatAmount','tax_amount'),('totalAmount','total_amount')]): continue
            items=[dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(new['id'],))]
            if len(items)!=len(raw['invoiceDetail']): continue
            if any(str(a['source_item_code'])!=str(b.get('productCode') or '') or a['source_unit']!=b.get('unitCode')
                   or any(abs(float(b[k])-a[v])>0.000001 for k,v in [('quantity','qty'),('unitPrice','unit_price'),('amountWithoutVAT','amount')])
                   for a,b in zip(items,raw['invoiceDetail'])): continue
            pairs.append((old['id'],new['id']))
        except (ValueError,TypeError,KeyError): continue
    # An ambiguous fork is not evidence to select a payable document.
    return {old:new for old,new in pairs if sum(a==old for a,b in pairs)==1}


def stock_replacement_reviews(conn):
    """Only identical goods with intact old postings can retain stock once."""
    import hashlib
    from collections import Counter
    result={}
    for old_id,new_id in verified_replacements(conn).items():
        old=dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(old_id,)).fetchone())
        new=dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(new_id,)).fetchone())
        fields=('source_item_code','source_unit','qty','unit_price','amount')
        old_items=[dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(old_id,))]
        new_items=[dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(new_id,))]
        if not old_items or Counter(tuple(r[k] for k in fields) for r in old_items)!=Counter(tuple(r[k] for k in fields) for r in new_items):continue
        ledger=[dict(r) for r in conn.execute("SELECT * FROM invoice_inventory_effective_ledger WHERE source_invoice_table='outgoing_source_invoices' AND source_invoice_id IN (?,?) ORDER BY id",(old_id,new_id))]
        if not ledger or any(r['source_invoice_id']!=old_id or r['event_type']!='POST' or r['status']!='posted' for r in ledger):continue
        expected=Counter()
        for r in old_items:
            if not r['inventory_eligible']:continue
            if not r['product_code'] or r['mapping_status']!='mapped':break
            expected[r['product_code']]+=float(r['stock_qty'])
        else:
            actual=Counter()
            for r in ledger:actual[r['product_code']]-=float(r['qty_delta'])
            if set(expected)!=set(actual) or any(abs(expected[k]-actual[k])>1e-8 for k in expected):continue
            stable=lambda r:{k:v for k,v in r.items() if k not in ('updated_at','synced_at')}
            token=hashlib.sha256(json.dumps([stable(old),stable(new),old_items,new_items,ledger],sort_keys=True,default=str).encode()).hexdigest()
            confirmed=conn.execute("SELECT 1 FROM audit_log WHERE event_type='invoice_output.replacement_keep_stock' AND entity_id=? AND status='ok'",(token,)).fetchone() is not None
            review={'token':token,'confirmed':confirmed,'old_id':old_id,'new_id':new_id,'old_number':old['invoice_number'],'new_number':new['invoice_number'],'buyer':new['buyer_name'],'line_count':len(new_items),'old_total':old['total_amount'],'new_total':new['total_amount']}
            result[old_id]=review;result[new_id]=review
    return result


def confirm_stock_replacement(conn,invoice_id,expected,confirmed,timestamp):
    if confirmed is not True:raise ValueError('Cần xác nhận không giao thêm hoặc nhận trả hàng trước khi giữ nguyên kho.')
    review=stock_replacement_reviews(conn).get(invoice_id)
    if not review or review['token']!=expected:raise ValueError('Hóa đơn hoặc kho đã thay đổi. Mở lại Đối chiếu hóa đơn thay thế để kiểm tra.')
    if not review['confirmed']:
        conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('invoice_output.replacement_keep_stock','invoice_replacement',?,'ok',?,?,?)",(expected,'Xác nhận hóa đơn thay thế giữ nguyên lượng kho đã ghi; không xuất lần hai',json.dumps(review,ensure_ascii=False),timestamp))
    return {'invoice_ids':[review['old_id'],review['new_id']],'stock_qty_change':0}
