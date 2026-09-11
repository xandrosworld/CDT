"""Expose historical signed-stock discrepancies without rewriting source invoices."""
import json


def signed_stock_issues(conn, contractor=''):
    try:
        from .outgoing_readiness import canonical_available_stock
        from .stock_tax_policy import exempt_order_codes
        from .outgoing_source_scope import resolve_scope
    except ImportError:
        from outgoing_readiness import canonical_available_stock
        from stock_tax_policy import exempt_order_codes
        from outgoing_source_scope import resolve_scope
    from collections import defaultdict
    orders=[dict(r) for r in conn.execute("SELECT o.* FROM orders o JOIN batches b ON b.id=o.batch_id WHERE b.status='approved'")]
    if not orders:return []
    exempt=exempt_order_codes(conn,orders)
    stock=canonical_available_stock(conn)
    affected={code:r for code,r in stock.items() if r['canonical_qty'] < -1e-8 and code not in exempt}
    if not affected:return []
    profiles=defaultdict(list)
    for r in conn.execute("SELECT contractor,tax_code FROM outgoing_buyer_profiles WHERE TRIM(tax_code)!=''"):
        profiles[r['tax_code'].strip().upper()].append(r['contractor'])
    earliest=min(o['work_date'] for o in orders)
    results=[]
    for source in conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice' AND source_status_class='issued' AND invoice_date>=? ORDER BY invoice_date,id",(earliest,)):
        party,error=resolve_scope(conn,source,profiles)
        if contractor and party!=contractor:continue
        raw=json.loads(source['raw_json'] or '{}')
        for line in conn.execute("""SELECT product_code,-SUM(qty_delta) qty FROM invoice_inventory_effective_ledger
            WHERE source_invoice_table='outgoing_source_invoices' AND source_invoice_id=? AND direction='output'
            AND status='posted' GROUP BY product_code""",(source['id'],)):
            code=line['product_code']
            if code not in affected or line['qty']<=0:continue
            r=affected[code]
            results.append({'invoice_id':source['id'],'invoice_number':source['invoice_series']+'/'+source['invoice_number'],
                'invoice_date':source['invoice_date'],'signed_at':raw.get('dateSign') or '',
                'contractor':party or '', 'buyer':source['buyer_name'],'product_code':code,'product_name':r['product_name'],
                'unit':r['unit'],'signed_qty':line['qty'],'opening_qty':r.get('opening_qty',0),
                'input_qty':r.get('input_qty',0),'closing_qty':r['canonical_qty'],
                'message':'Đã ký trên M-Invoice; sổ hiện còn âm mã này. Đối chiếu chứng từ đầu vào và hóa đơn nguồn. Phần thiếu không được cấp thêm vào bảng kê mới.'})
    return results
