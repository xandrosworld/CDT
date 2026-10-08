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
            if (raw.get('_tdp_source_contract')!='minvoice_portal_v1' or status!={'invoiceStatus':3,'sendTaxStatus':4}
                or raw.get('invoiceStatus')!=3 or raw.get('sendTaxStatus')!=4
                or new['source_status_class']!='replaced' or portal_validation_error(raw)): continue
            candidates=by_remote.get((new['tenant'],raw.get('relatedInvoiceId')),[])
            if len(candidates)!=1: continue
            old=candidates[0]; previous=json.loads(old['source_status_raw']); oldraw=json.loads(old['raw_json'])
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
