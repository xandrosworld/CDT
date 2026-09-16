"""Link an unchanged, signed remote draft to its original order allocations.

The source invoice must already have posted its canonical inventory ledger.
This updates provenance and releases reservations, never posts inventory again.
"""
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation

try:
    from .outgoing_weights import invoice_rows
    from .minvoice_portal import portal_date
    from .minvoice_portal_drafts import ordered_draft_lines
    from .minvoice_client import MinvoiceError
except ImportError:
    from outgoing_weights import invoice_rows
    from minvoice_portal import portal_date
    from minvoice_portal_drafts import ordered_draft_lines
    from minvoice_client import MinvoiceError


def text(v):return str(v or '').strip()


def close(a,b):
    try:
        x,y=Decimal(str(a)),Decimal(str(b))
        return x.is_finite() and y.is_finite() and abs(x-y)<=Decimal('0.000001')
    except (InvalidOperation,ValueError,TypeError):return False


def reconcile_sent(conn,timestamp):
    try:
        from .contract_modules import invoice_tax_percent
    except ImportError:
        from contract_modules import invoice_tax_percent
    linked=[];blocked=[]
    drafts=[dict(d) for d in conn.execute("""SELECT * FROM outgoing_invoice_drafts WHERE status='draft'
        AND minvoice_status IN ('saved','unknown') AND COALESCE(minvoice_key_api,'')<>''""")]
    sources=[dict(r) for r in conn.execute("""SELECT * FROM outgoing_source_invoices
        WHERE source='minvoice' AND source_status_class='issued' AND sync_status='synced'
          AND stock_status IN ('posted','not_inventory')""")]
    for d in drafts:
        matches=[]
        for s in sources:
            raw=json.loads(s['raw_json'])
            if (raw.get('_tdp_source_contract')=='minvoice_portal_v1' and raw.get('orderNumber')==d['minvoice_key_api']
                    and raw.get('keyApi') in (None,'',d['minvoice_key_api'])):
                matches.append((s,raw))
        if not matches:continue
        reason=''
        if len(matches)!=1:reason='Có nhiều hóa đơn trùng khóa bản nháp.'
        else:
            s,raw=matches[0]
            base=[dict(r) for r in conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=? ORDER BY id',(d['id'],))]
            try:
                expected=invoice_rows(conn,base);actual=ordered_draft_lines(raw.get('invoiceDetail',[]))
                if (raw.get('orderNumber')!=d['minvoice_key_api']
                        or (d['minvoice_remote_id'] and s['remote_id']!=d['minvoice_remote_id'])
                        or s['invoice_series']!=d['minvoice_series'] or portal_date(raw.get('invoiceDate'))!=d['invoice_date']
                        or text(raw.get('sellerTaxCode'))!=text(d['company_tax_code_snapshot'])
                        or text(raw.get('buyerTaxCode'))!=text(d['buyer_tax_code_snapshot'])
                        or text(raw.get('buyerLegalName') or raw.get('buyerDisplayName'))!=text(d['buyer_name_snapshot'])
                        or text(raw.get('buyerAddress'))!=text(d['buyer_address_snapshot'])
                        or any(not close(s[k],d[k]) for k in ('subtotal','tax_amount','total_amount'))
                        or len(expected)!=len(actual)):
                    reason='Hóa đơn đã ký khác thông tin bản nháp đã gửi.'
                for a,b in zip(actual,expected):
                    if (text(a.get('productCode')).upper()!=text(b['product_code']).upper()
                            or text(a.get('productName'))!=text(b['product_name'])
                            or text(a.get('unitCode')).casefold()!=text(b['unit']).casefold()
                            or not close(a.get('quantity'),b['qty']) or not close(a.get('unitPrice'),b['unit_price'])
                            or invoice_tax_percent(a.get('vatCode'))!=invoice_tax_percent(b['tax'])
                            or text(a.get('property'))!=text(b['invoice_nature'])):
                        reason='Dòng hàng đã ký khác bảng kê đã gửi; cần đối chiếu đơn gốc.'
                stock=defaultdict(float)
                for r in base:stock[r['product_code']]+=r['qty']
                posted={r['product_code']:r['qty'] for r in conn.execute("""SELECT product_code,-SUM(qty_delta) qty
                    FROM invoice_inventory_effective_ledger WHERE direction='output' AND status='posted'
                    AND source_invoice_table='outgoing_source_invoices' AND source_invoice_id=? GROUP BY product_code""",(s['id'],))}
                if set(stock)!=set(posted) or any(not close(q,posted.get(k)) for k,q in stock.items()):
                    reason='Lượng ghi kho chưa khớp lượng đã giữ của bảng kê.'
                duplicate=conn.execute("""SELECT id FROM outgoing_invoice_drafts WHERE id<>? AND status='issued'
                    AND issued_invoice_series=? AND issued_invoice_number=?""",(d['id'],s['invoice_series'],s['invoice_number'])).fetchone()
                if duplicate:reason='Hóa đơn này đã liên kết với bảng kê khác.'
            except (ValueError,KeyError,TypeError,MinvoiceError) as exc:
                reason='Chưa đối chiếu đủ bản nháp với hóa đơn đã ký: '+str(exc)
        if reason:
            blocked.append({'draft_id':d['id'],'contractor':d['contractor'],'error':reason});continue
        conn.execute("""UPDATE outgoing_invoice_drafts SET status='issued',issued_at=?,issued_invoice_number=?,
            issued_invoice_series=?,issued_invoice_date=?,minvoice_status='saved',minvoice_remote_id=?,minvoice_reconciled_at=?
            WHERE id=? AND status='draft'""",(timestamp,s['invoice_number'],s['invoice_series'],s['invoice_date'],s['remote_id'],timestamp,d['id']))
        conn.execute("""UPDATE inventory_transactions SET status='cancelled',updated_at=?,
            note='Đã ghi kho từ hóa đơn M-Invoice; bỏ giữ kho bản nháp'
            WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'""",(timestamp,str(d['id'])))
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
            VALUES('outgoing.signed_source_link','outgoing_invoice',?,'ok','Đối chiếu hóa đơn ký, giữ liên kết đơn gốc',?,?)""",
            (str(d['id']),json.dumps({'source_invoice_id':s['id'],'stock_posted_again':False}),timestamp))
        linked.append({'draft_id':d['id'],'source_invoice_id':s['id']})
    return {'linked':linked,'blocked':blocked}
