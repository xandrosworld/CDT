"""Persist invoiceable approved quantities until the user chooses to issue them."""
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

try:
    from .outgoing_unissued import issued_allocations
    from .outgoing_consolidation import _write_draft, decimal
    from .outgoing_readiness import canonical_available_stock, invoice_order_issues, validate_demand_orders, OutgoingReadinessError
    from .stock_tax_policy import exempt_order_codes
except ImportError:
    from outgoing_unissued import issued_allocations
    from outgoing_consolidation import _write_draft, decimal
    from outgoing_readiness import canonical_available_stock, invoice_order_issues, validate_demand_orders, OutgoingReadinessError
    from stock_tax_policy import exempt_order_codes


def refresh_waiting(conn, timestamp, *, fill=True):
    """Caller owns the transaction. Downloads/refreshes never mark invoices issued."""
    try:
        from .contract_modules import invoice_tax_percent, audit
    except ImportError:
        from contract_modules import invoice_tax_percent, audit
    external={}
    issued,warnings=issued_allocations(conn,external_quantities=external)
    if warnings:
        return {'created':[], 'replaced':[], 'warnings':warnings}
    orders=[dict(r) for r in conn.execute("""SELECT o.* FROM orders o JOIN batches b ON b.id=o.batch_id
        WHERE b.status='approved' ORDER BY o.work_date,o.id""")]
    need={r['id']:max(decimal(r['actual_delivered'])-decimal(r['customer_return_qty'])-decimal(issued.get(r['id'],0)),Decimal(0)) for r in orders}
    settled={r['order_id']:r['external_issued_qty'] for r in conn.execute('SELECT * FROM outgoing_waiting_settlements')}
    consume={oid:max(decimal(q)-decimal(settled.get(oid,0)),Decimal(0)) for oid,q in external.items()}
    old=[];replacement=[];created=[]
    # Remote saved drafts cannot be rewritten. Allocate their holds first.
    drafts=[dict(r) for r in conn.execute("""SELECT * FROM outgoing_invoice_drafts WHERE status='draft'
        ORDER BY CASE WHEN minvoice_status IN ('saved','saving','unknown') THEN 0 ELSE 1 END,id""")]
    for d in drafts:
        rows=[dict(r) for r in conn.execute("""SELECT l.*,o.batch_id,o.work_date,o.buy_price,a.source_unit_price
            FROM outgoing_order_allocations l JOIN orders o ON o.id=l.order_id
            LEFT JOIN outgoing_line_allocations a ON a.line_id=l.id AND a.order_id=l.order_id
            WHERE l.draft_id=? ORDER BY o.work_date,o.id,l.id""",(d['id'],))]
        kept=[];changed=False
        for r in rows:
            used=min(decimal(r['qty']),consume.get(r['order_id'],Decimal(0)))
            consume[r['order_id']]=max(consume.get(r['order_id'],Decimal(0))-used,Decimal(0))
            qty=min(decimal(r['qty'])-used,need.get(r['order_id'],Decimal(0)))
            if qty<=Decimal('0.00000001'):qty=Decimal(0)
            changed=changed or (qty==0 and decimal(r['qty'])>0) or abs(qty-decimal(r['qty']))>Decimal('0.00000001')
            need[r['order_id']]=max(need.get(r['order_id'],Decimal(0))-qty,Decimal(0))
            if qty>0:
                kept.append({**r,'qty':float(qty),'_source_price':decimal(r['source_unit_price'] if r['source_unit_price'] is not None else r['unit_price'])})
        if not changed:continue
        if d['minvoice_status'] in ('saved','saving','unknown'):
            warnings.append({'contractor':d['contractor'],'message':'Bản đã lưu M-Invoice còn chồng với lượng đã phát hành; cần đối chiếu bản số '+str(d['id'])+'.'})
            continue
        old.append(d['id'])
        if kept:replacement.append((d['contractor'],kept))
    # Ambiguous remote drafts leave the complete waiting pool unchanged.
    if warnings:return {'created':[], 'replaced':[], 'warnings':warnings}
    for oid in settled.keys()|external.keys():
        qty=external.get(oid,0)
        if abs(qty-settled.get(oid,0))>1e-8:
            conn.execute('''INSERT INTO outgoing_waiting_settlements(order_id,external_issued_qty,updated_at) VALUES(?,?,?)
                ON CONFLICT(order_id) DO UPDATE SET external_issued_qty=excluded.external_issued_qty,updated_at=excluded.updated_at''',(oid,qty,timestamp))
    for did in old:
        conn.execute("UPDATE outgoing_invoice_drafts SET status='cancelled' WHERE id=?",(did,))
        conn.execute("UPDATE inventory_transactions SET status='cancelled',updated_at=? WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",(timestamp,str(did)))
    for party,rows in replacement:
        # Do not round away a held remainder after a partial external issue.
        did=_write_draft(conn,party,rows,{r['batch_id'] for r in rows},invoice_tax_percent,timestamp,floor_kg=False,kind='waiting')
        if did:created.append(did)
    if fill:
        stock=canonical_available_stock(conn)
        available={code:max(decimal(r['raw_available_qty']),Decimal(0)) for code,r in stock.items()}
        exempt=exempt_order_codes(conn,orders)
        additions=defaultdict(list)
        already_held=defaultdict(lambda:Decimal(0))
        def price_key(o):
            return (o['contractor'],o['product_code'],o['unit'].strip().casefold(),invoice_tax_percent(o['tax']),o.get('invoice_nature') or '1',decimal(o['sell_price']))
        for o in orders:
            already_held[price_key(o)]+=max(decimal(o['actual_delivered'])-decimal(o['customer_return_qty'])-decimal(issued.get(o['id'],0))-need.get(o['id'],Decimal(0)),Decimal(0))
        for o in orders:
            if need.get(o['id'],0)<=Decimal('0.00000001'):continue
            issues=invoice_order_issues([o])
            try:
                validate_demand_orders(conn,[o])
            except OutgoingReadinessError as exc:
                issues.append({'messages':[str(exc)]})
            if issues:
                warnings.append({'contractor':o['contractor'],'message':o['product_code']+': '+ '; '.join(issues[0]['messages'])})
                continue
            code=o['product_code'];have=available.get(code,Decimal(0))
            qty=need[o['id']] if code in exempt else min(need[o['id']],have)
            available[code]=max(have-qty,Decimal(0))
            if qty<=Decimal('0.00000001'):continue
            row={**o,'order_id':o['id'],'qty':float(qty),'_source_price':decimal(o['sell_price'])}
            additions[price_key(o)].append(row)
        by_tax=defaultdict(list)
        for key,rows in additions.items():
            total=sum((decimal(r['qty']) for r in rows),Decimal(0))
            if key[2]=='kg':total=max((already_held[key]+total).quantize(Decimal('.1'),rounding=ROUND_DOWN)-already_held[key],Decimal(0))
            for r in rows:
                take=min(total,decimal(r['qty']));total-=take
                if take>0:by_tax[(key[0],key[3])].append({**r,'qty':float(take)})
        for (party,_),rows in by_tax.items():
            did=_write_draft(conn,party,rows,{r['batch_id'] for r in rows},invoice_tax_percent,timestamp,floor_kg=False,kind='waiting')
            if did:created.append(did)
    if old or created:
        audit(conn,lambda:timestamp,'outgoing.waiting_pool','ok',entity_type='outgoing_invoice',metadata={'replaced_drafts':old,'created_drafts':created,'signed_or_issued':False})
    return {'created':created,'replaced':old,'warnings':warnings}


def waiting_readiness(conn,orders,issued):
    """Read only; a broken reservation or changed stock is never labelled safe."""
    held=defaultdict(float);valid=defaultdict(float);warnings=[]
    stock=canonical_available_stock(conn)
    by_order={r['id']:r for r in orders}
    exempt=exempt_order_codes(conn,orders)
    for d in conn.execute("SELECT id,contractor FROM outgoing_invoice_drafts WHERE status='draft'"):
        expected={r['product_code']:r['qty'] for r in conn.execute('SELECT product_code,SUM(qty) qty FROM outgoing_invoice_lines WHERE draft_id=? GROUP BY product_code',(d['id'],))}
        reserved={r['product_code']:r['qty'] for r in conn.execute("SELECT product_code,SUM(qty_out) qty FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved' GROUP BY product_code",(str(d['id']),))}
        for r in conn.execute('SELECT order_id,product_code,qty FROM outgoing_order_allocations WHERE draft_id=?',(d['id'],)):
            if r['order_id'] not in by_order:continue
            oid=r['order_id'];code=r['product_code'];held[oid]+=r['qty']
            if abs(expected.get(code,0)-reserved.get(code,0))>1e-8 or (code not in exempt and stock.get(code,{}).get('raw_available_qty',0)<-1e-8):
                warnings.append({'contractor':d['contractor'],'message':code+': lượng giữ chờ cần đối chiếu lại với tồn hiện tại.'})
            else:valid[oid]+=r['qty']
    for oid,o in by_order.items():
        remaining=max(o['actual_delivered']-o['customer_return_qty']-issued.get(oid,0),0)
        if held[oid]>remaining+1e-8:
            valid[oid]=0
            warnings.append({'contractor':o['contractor'],'message':o['product_code']+': có lượng đã phát hành chưa giải phóng khỏi phần giữ chờ; bấm cập nhật.'})
    return dict(valid),[dict(contractor=p,message=m) for p,m in sorted({(w['contractor'],w['message']) for w in warnings})]


def refresh_after_change(conn,timestamp):
    """A valid stock/approval operation must not be lost to a waiting-pool conflict."""
    conn.execute('SAVEPOINT update_waiting_pool')
    try:
        result=refresh_waiting(conn,timestamp)
    except ValueError as exc:
        conn.execute('ROLLBACK TO update_waiting_pool')
        result={'created':[], 'replaced':[], 'warnings':[{'contractor':'','message':'Phần giữ chờ cần đối chiếu: '+str(exc)}]}
    finally:
        conn.execute('RELEASE update_waiting_pool')
    return result


def register_waiting_hooks(app,db_factory,now_iso):
    from flask import request
    @app.after_request
    def update_waiting_after_stock_change(response):
        path=request.path
        affects_stock=(path.startswith('/api/invoice-workbench/') and path.endswith(('/sync','/input-receipts','/output-postings')))
        affects_stock=affects_stock or (path.startswith('/api/outgoing-invoices/') and path.endswith('/confirm-issued'))
        affects_stock=affects_stock or (path.startswith('/api/bk-import/') and path.endswith(('/confirm','/reversal')))
        if request.method!='POST' or not 200<=response.status_code<300 or not affects_stock:return response
        with db_factory() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='orders' AND type='table'").fetchone():return response
            conn.execute('BEGIN IMMEDIATE')
            result=refresh_after_change(conn,now_iso())
        if response.is_json:
            payload=response.get_json()
            if isinstance(payload,dict):
                payload['waiting']=result
                response.set_data(app.json.dumps(payload))
        return response
