"""Explicitly reconcile offsetting tax adjustments without creating stock events."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from flask import jsonify, request

try:
    from .invoice_mapping import _normalized
    from .minvoice_portal import portal_validation_error, portal_date
except ImportError:
    from invoice_mapping import _normalized
    from minvoice_portal import portal_validation_error, portal_date


EVENT = 'invoice_output.tax_adjustment_confirmed'


class AdjustmentError(ValueError):
    pass


def _number(value):
    if value is None or isinstance(value, bool):
        raise ValueError()
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError()
    return result


def _catalog(conn):
    aliases = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_product_names'").fetchone():
        aliases = {r[0]:r[1] for r in conn.execute('SELECT product_code,invoice_name FROM outgoing_product_names')}
    names, canonical = {}, {}
    for row in conn.execute('SELECT code,name,unit FROM products'):
        product = dict(row)
        key = (_normalized(product['name']), _normalized(product['unit']))
        canonical.setdefault(key, {})[product['code']] = product
        for name in [product['name'], aliases.get(product['code'], '')]:
            if name:
                names.setdefault((_normalized(name), key[1]), {})[product['code']] = product
    return canonical, names


def _candidate(conn, invoice, catalog):
    """Status 2 is an adjusting document; status 5 is an adjusted original."""
    row = dict(invoice)
    if (row['source'] != 'minvoice' or row['source_status_class'] != 'adjusted'
            or row['sync_status'] != 'reconcile_required' or row['stock_status'] != 'blocked'):
        return None
    if conn.execute("SELECT 1 FROM invoice_inventory_ledger WHERE direction='output' "
                    "AND source_invoice_table='outgoing_source_invoices' AND source_invoice_id=? LIMIT 1",
                    (row['id'],)).fetchone():
        return None
    try:
        raw = json.loads(row['raw_json'])
        if not isinstance(raw, dict):
            return None
        if (raw.get('_tdp_source_contract') != 'minvoice_portal_v1'
                or type(raw.get('invoiceStatus')) is not int or raw['invoiceStatus'] != 2
                or type(raw.get('sendTaxStatus')) is not int or raw['sendTaxStatus'] != 4
                or type(raw.get('relatedInvoiceProperty')) is not int or raw['relatedInvoiceProperty'] != 2
                or not raw.get('relatedInvoiceId') or not raw.get('relatedInvoiceNumber')
                or not raw.get('relatedInvoiceSerial')
                or portal_date(raw['relatedInvoiceDate']) > row['invoice_date']
                or portal_date(raw['invoiceDate']) != row['invoice_date']
                or str(raw['invoiceNumber']) != row['invoice_number']
                or raw['invoiceSerial'] != row['invoice_series']
                or raw.get('buyerTaxCode') != row['buyer_tax_code'] or not row['buyer_tax_code']
                or portal_validation_error(raw)):
            return None
        for source, field in [('totalAmountWithoutVAT','subtotal'),('vatAmount','tax_amount'),('totalAmount','total_amount')]:
            if _number(raw[source]) != _number(row[field]):
                return None
        items = conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',
                             (row['id'],)).fetchall()
        if not items or len(items) != len(raw['invoiceDetail']):
            return None
        lines, signs, signature = [], set(), []
        for item, source in zip(items, raw['invoiceDetail']):
            if not isinstance(source, dict):
                return None
            qty, price, amount = (_number(source[k]) for k in ('quantity','unitPrice','amountWithoutVAT'))
            tax = _number(source['vatAmount'])
            if (type(source.get('property')) is not int or source['property'] != 1
                    or not qty or price <= 0 or qty * amount <= 0 or abs(qty * price - amount) > 1
                    or tax * qty < 0 or item['inventory_eligible']
                    or any(_number(item[k]) != v for k,v in [('qty',qty),('unit_price',price),('amount',amount)])
                    or item['source_item_name'] != source['productName'] or item['source_unit'] != source['unitCode']):
                return None
            key = (_normalized(source['productName']), _normalized(source['unitCode']))
            choices = catalog[0].get(key) or catalog[1].get(key, {})
            if len(choices) != 1:
                return None
            product = next(iter(choices.values()))
            code = str(source.get('productCode') or '').strip()
            if code and _normalized(code) != _normalized(product['code']):
                return None
            signs.add(1 if qty > 0 else -1)
            signature.append((product['code'],key[1],str(abs(qty).normalize()),str(price.normalize()),str(abs(amount).normalize())))
            lines.append({'line_index':item['line_index'], 'source_name':item['source_item_name'],
                          'unit':item['source_unit'], 'qty':float(qty), 'amount':float(amount),
                          'tax':float(tax), 'product_code':product['code'], 'product_name':product['name'],
                          'product_unit':product['unit']})
        if len(signs) != 1:
            return None
        return {'invoice':row, 'raw':raw, 'lines':lines, 'sign':next(iter(signs)),
                'signature':(row['buyer_tax_code'],row['invoice_date'],raw.get('sellerTaxCode'),
                             raw.get('currencyCode'),str(raw.get('exchangeRate')),tuple(sorted(signature)))}
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def adjustment_reviews(conn, tenant):
    catalog = _catalog(conn)
    buckets = {}
    for invoice in conn.execute("SELECT * FROM outgoing_source_invoices WHERE tenant=? AND source='minvoice' "
                                "AND source_status_class='adjusted'", (tenant,)).fetchall():
        candidate = _candidate(conn, invoice, catalog)
        if candidate:
            buckets.setdefault(candidate['signature'], []).append(candidate)
    result = {}
    for candidates in buckets.values():
        # Never choose between several possible balancing documents.
        if len(candidates) != 2 or {c['sign'] for c in candidates} != {-1,1}:
            continue
        candidates.sort(key=lambda c:c['sign'])
        invoices = [c['invoice'] for c in candidates]
        subtotal = sum(_number(i['subtotal']) for i in invoices)
        tax = sum(_number(i['tax_amount']) for i in invoices)
        total = sum(_number(i['total_amount']) for i in invoices)
        if subtotal != 0 or tax == 0 or total != tax:
            continue
        documents = [{k:i[k] for k in ('id','invoice_series','invoice_number','invoice_date','buyer_name')}
                     | {'reference_number':c['raw']['relatedInvoiceNumber'], 'reference_series':c['raw']['relatedInvoiceSerial'],
                        'source_note':c['raw'].get('invoiceNote') or '', 'lines':c['lines'],
                        'subtotal':i['subtotal'], 'tax':i['tax_amount'], 'total':i['total_amount']}
                     for c,i in zip(candidates,invoices)]
        # Stable across re-sync row IDs, but revoke when source, related documents or catalog change.
        token = hashlib.sha256(json.dumps([tenant,documents,[c['raw'] for c in candidates]],sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest()
        confirmed = conn.execute("SELECT 1 FROM audit_log WHERE event_type=? AND entity_id=? AND status='ok' LIMIT 1",
                                 (EVENT,token)).fetchone() is not None
        review = {'token':token, 'invoice_ids':[i['id'] for i in invoices], 'documents':documents,
                  'net_qty':0, 'net_subtotal':0, 'tax_difference':float(tax), 'net_total':float(total),
                  'confirmed':confirmed}
        for invoice in invoices:
            result[invoice['id']] = review
    return result


def confirm_tax_adjustment(conn, *, tenant, invoice_id, expected, confirmed, now):
    if confirmed is not True:
        raise AdjustmentError('Cần xác nhận cặp này chỉ điều chỉnh thuế, không giao thêm hoặc nhận trả hàng.')
    review = adjustment_reviews(conn,tenant).get(invoice_id)
    if not review or not expected or expected != review['token']:
        raise AdjustmentError('Hóa đơn, mã hàng hoặc cặp điều chỉnh đã thay đổi. Mở lại bảng đối chiếu.')
    if review['confirmed']:
        return {'invoice_ids':review['invoice_ids'],'idempotent':True,'stock_qty_change':0}
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) "
                 "VALUES(?, 'outgoing_tax_adjustment', ?, 'ok', ?, ?, ?)",
                 (EVENT,review['token'],'Xác nhận chỉ điều chỉnh thuế; không giao/nhận thêm hàng, không thay đổi kho',
                  json.dumps(review,ensure_ascii=False),now))
    return {'invoice_ids':review['invoice_ids'],'idempotent':False,'stock_qty_change':0}


def annotate_adjustment(invoice, review):
    if not review:
        return
    invoice['adjustment_review'] = review
    if review['confirmed']:
        document = next(d for d in review['documents'] if d['id'] == invoice['id'])
        by_index = {l['line_index']:l for l in document['lines']}
        for item in invoice['items']:
            mapped = by_index[item['line_index']]
            item.update(product_code=mapped['product_code'],product_name=mapped['product_name'],
                        product_unit=mapped['product_unit'])


def register_adjustment_routes(app, ctx):
    @app.post('/api/invoice-workbench/output-adjustments/<int:invoice_id>/confirm-tax')
    def confirm(invoice_id):
        body = request.get_json(silent=True) or {}
        try:
            if not isinstance(body,dict):
                raise AdjustmentError('Dữ liệu xác nhận không hợp lệ.')
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                tenant_row = conn.execute("SELECT value FROM settings WHERE key='tenant_code'").fetchone()
                result = confirm_tax_adjustment(conn,tenant=(str(tenant_row[0]).strip() if tenant_row else '') or 'TDP',
                    invoice_id=invoice_id,expected=body.get('expected'),confirmed=body.get('confirmed'),now=ctx['now_iso']())
            return jsonify(ok=True,**result)
        except AdjustmentError as error:
            return jsonify(ok=False,error=str(error)),409
