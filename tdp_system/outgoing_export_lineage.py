"""Match signed invoices to immutable downloaded files, never by a single item.

This module is read-only. A receipt is not evidence of issuance: callers must
separately validate the signed source and its posted stock before allocating.
"""
import json
import math
from collections import defaultdict
from decimal import Decimal, InvalidOperation

try:
    from .contract_modules import invoice_tax_percent
    from .outgoing_export_receipts import draft_snapshot, source_basis
except ImportError:
    from contract_modules import invoice_tax_percent
    from outgoing_export_receipts import draft_snapshot, source_basis


def signature(rows, source=False):
    sums=defaultdict(lambda:[Decimal(0),Decimal(0)])
    for row in rows:
        code=str(row['source_item_code'] if source else row['product_code']).strip()
        if not code:raise ValueError('Missing item identity')
        price=Decimal(str(row['unit_price'])).quantize(Decimal('.000001'))
        qty=Decimal(str(row['qty']));amount=Decimal(str(row['amount']))
        if not all(n.is_finite() for n in (price,qty,amount)):raise ValueError('Non-finite invoice value')
        key=(code,str(row['source_unit'] if source else row['unit']).strip().casefold(),price,
             invoice_tax_percent(row['tax_rate'] if source else row['tax']),
             str(row['source_nature'] if source else row['invoice_nature']))
        sums[key][0]+=qty;sums[key][1]+=amount
    return {k:tuple(n.quantize(Decimal('.000001')) for n in v) for k,v in sums.items()}


def catalog(conn):
    result=[];seen=set();bases={}
    for receipt in conn.execute("SELECT token,filename,manifest,created_at,received_at FROM outgoing_export_receipts WHERE received_at<>'' ORDER BY created_at DESC"):
        for entry in json.loads(receipt['manifest']):
            marker=(entry['id'],entry['hash'],json.dumps(entry.get('source_basis'),sort_keys=True))
            if marker in seen:continue
            basis=entry.get('source_basis')
            if not basis:
                # Old receipts can be recovered only while every original row
                # and draft line still has the exact hash saved with the file.
                current=draft_snapshot(conn,entry['id'],active_only=False)
                if not current or current['hash']!=entry['hash']:continue
                try:
                    if marker not in bases:bases[marker]=source_basis(conn,entry['id'])
                    basis=bases[marker]
                except ValueError:continue
            try:sig=signature(basis['lines'])
            except (ValueError,TypeError,KeyError,InvalidOperation):continue
            if not entry['rows'] or not sig:continue
            seen.add(marker)
            result.append({**entry,'source_basis':basis,'signature':sig,
                'legacy_basis':'source_basis' not in entry,
                'token':receipt['token'],'filename':receipt['filename'],'created_at':receipt['created_at']})
    return result


def matches(conn, invoice, party, exports=None):
    actual=list(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice['id'],)))
    try:expected=signature(actual,True)
    except (ValueError,TypeError,InvalidOperation):return []
    if not expected:return []
    period=conn.execute('SELECT * FROM outgoing_source_order_periods WHERE invoice_id=?',(invoice['id'],)).fetchone()
    if period:
        try:
            from .outgoing_source_scope import identity_snapshot
        except ImportError:
            from outgoing_source_scope import identity_snapshot
        if period['identity_snapshot']!=identity_snapshot(invoice):return []
    found={};legacy={}
    for export in catalog(conn) if exports is None else exports:
        # Historical receipts did not freeze the buyer or converted lines.
        # They are useful comparison evidence, not permission to rewrite old
        # reconciliations at deployment time. They must still prevent an
        # ambiguous new match when two different order sets look identical.
        basis=export['source_basis']
        if basis['contractor']!=party or export['created_at']>invoice['created_at']:continue
        if not (basis['buyer_tax_code'] or '').strip() or basis['buyer_tax_code'].strip().upper()!=invoice['buyer_tax_code'].strip().upper():continue
        if (abs(basis['subtotal']-invoice['subtotal'])>1e-6 or
                abs(basis['total_amount']-invoice['total_amount'])>1e-6 or export['signature']!=expected):continue
        rows=export['rows']
        if any(r['contractor']!=party or r['work_date']>invoice['invoice_date'] or
               (period and not period['date_from']<=r['work_date']<=period['date_to']) for r in rows):continue
        links=defaultdict(float)
        for r in rows:links[r['order_id']]+=r['qty']
        key=tuple(sorted(links.items()))
        (legacy if export.get('legacy_basis') else found)[key]={**export,'allocations':dict(links)}
    return list({**legacy,**found}.values()) if found else []


def orders_unchanged(conn, export):
    for row in export['rows']:
        current=conn.execute('SELECT o.*,b.status batch_status FROM orders o JOIN batches b ON b.id=o.batch_id WHERE o.id=?',(row['order_id'],)).fetchone()
        if not current or current['batch_status']!='approved':return False
        for field in ('contractor','work_date','product_code','unit','sell_price','tax','actual_delivered','customer_return_qty'):
            if current[field]!=row[field]:return False
        if not math.isfinite(row['qty']) or row['qty']<=0:return False
    return True


def comparison(conn, invoice, party):
    """Show evidence to the customer; similarity never authorizes allocation."""
    actual=[dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice['id'],))]
    try:expected=signature(actual,True)
    except (ValueError,TypeError,InvalidOperation):expected={}
    candidates=[];other_buyers=[]
    for export in catalog(conn):
        basis=export['source_basis'];rows=export['rows']
        if export['created_at']>invoice['created_at']:continue
        # Show only same-party files; a common food item is not evidence that
        # another contractor's table was used.
        dates=[r['work_date'] for r in rows]
        if max(dates)<invoice['invoice_date'][:7]+'-01' or min(dates)>invoice['invoice_date']:continue
        if basis['contractor']!=party:
            if expected and export['signature']==expected and abs(basis['total_amount']-invoice['total_amount'])<1e-6:
                other_buyers.append({'contractor':basis['contractor'],'from':min(dates),'to':max(dates),
                    'filename':export['filename'],'token':export['token']})
            continue
        same=sum(1 for k,v in expected.items() if export['signature'].get(k)==v)
        candidates.append({'filename':export['filename'],'token':export['token'],
            'draft_id':export['id'],'from':min(dates),'to':max(dates),
            'total':basis['total_amount'],'matched_items':same,'invoice_items':len(expected),
            'file_items':len(export['signature']),'exact':export['signature']==expected and
            abs(basis['total_amount']-invoice['total_amount'])<1e-6,
            'difference':invoice['total_amount']-basis['total_amount']})
    candidates.sort(key=lambda r:(r['exact'],r['matched_items'],-abs(r['difference']),r['draft_id']),reverse=True)
    return {'invoice_total':invoice['total_amount'],'candidates':candidates[:8],'other_buyers':other_buyers[:8],
        'items':[{'code':r['source_item_code'],'name':r['source_item_name'],'unit':r['source_unit'],
                  'qty':r['qty'],'amount':r['amount']} for r in actual]}
