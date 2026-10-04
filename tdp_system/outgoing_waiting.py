"""Persist invoiceable approved quantities until the user chooses to issue them."""
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

try:
    from .outgoing_unissued import issued_allocations, warning_applies_to_order
    from .outgoing_consolidation import _write_draft, decimal, export_quantity
    from .outgoing_readiness import canonical_available_stock, invoice_order_issues, validate_demand_orders, OutgoingReadinessError
    from .stock_tax_policy import exempt_order_codes, is_kkknt
    from .outgoing_line_policy import unit_issues, draft_policy_rows
    from .outgoing_price_guard import same_price, price_message
except ImportError:
    from outgoing_unissued import issued_allocations, warning_applies_to_order
    from outgoing_consolidation import _write_draft, decimal, export_quantity
    from outgoing_readiness import canonical_available_stock, invoice_order_issues, validate_demand_orders, OutgoingReadinessError
    from stock_tax_policy import exempt_order_codes, is_kkknt
    from outgoing_line_policy import unit_issues, draft_policy_rows
    from outgoing_price_guard import same_price, price_message


def reconcile_shared_issued_holds(conn, orders, timestamp):
    """Reconcile only editable holds sharing stock and proven newly issued orders."""
    codes={o['product_code'] for o in orders}
    external={}
    issued_allocations(conn, external_quantities=external)
    settled={r['order_id']:r['external_issued_qty'] for r in conn.execute(
        'SELECT order_id,external_issued_qty FROM outgoing_waiting_settlements')}
    candidates=defaultdict(set)
    for row in conn.execute("""SELECT d.contractor,a.order_id,a.product_code
        FROM outgoing_order_allocations a JOIN outgoing_invoice_drafts d ON d.id=a.draft_id
        WHERE d.status='draft' AND COALESCE(d.minvoice_status,'not_sent')
        NOT IN ('saved','saving','unknown')"""):
        if row['product_code'] in codes and external.get(row['order_id'],0)>settled.get(row['order_id'],0)+1e-8:
            candidates[row['contractor']].add(row['order_id'])
    for party, ids in candidates.items():
        refresh_waiting(conn,timestamp,fill=False,contractor=party,order_ids=ids,settle_shared=True)


def refresh_waiting(conn, timestamp, *, fill=True, contractor='', order_ids=None, settle_shared=False):
    """Caller owns the transaction. Downloads/refreshes never mark invoices issued."""
    try:
        from .outgoing_contractors import excluded_codes, release_disabled_drafts, selected_orders
    except ImportError:
        from outgoing_contractors import excluded_codes, release_disabled_drafts, selected_orders
    excluded=excluded_codes(conn)
    release_disabled_drafts(conn,timestamp)
    if contractor in excluded:
        return {'created':[], 'replaced':[], 'warnings':[]}
    try:
        from .contract_modules import invoice_tax_percent, audit
    except ImportError:
        from contract_modules import invoice_tax_percent, audit
    external={}
    issued,warnings=issued_allocations(conn,external_quantities=external)
    warnings=[w for w in warnings if w['contractor'] not in excluded and (not contractor or not w['contractor'] or w['contractor']==contractor)]
    orders=[dict(r) for r in conn.execute("""SELECT o.* FROM orders o JOIN batches b ON b.id=o.batch_id
        WHERE b.status='approved' AND (?='' OR o.contractor=?) ORDER BY o.work_date,o.id""",(contractor,contractor))]
    orders=selected_orders(conn,orders)
    if order_ids is not None:
        order_ids=set(order_ids)
        # Keep a mixed-date draft indivisible: include its complete lineage
        # before checking warnings or changing any holds.
        links=defaultdict(set)
        for r in conn.execute('''SELECT a.draft_id,a.order_id FROM outgoing_order_allocations a
            JOIN outgoing_invoice_drafts d ON d.id=a.draft_id WHERE d.status='draft'
            AND (?='' OR d.contractor=?)''',(contractor,contractor)):
            links[r['draft_id']].add(r['order_id'])
        while True:
            expanded=order_ids.union(*(ids for ids in links.values() if ids & order_ids))
            if expanded==order_ids:break
            order_ids=expanded
        orders=[o for o in orders if o['id'] in order_ids]
        warnings=[w for w in warnings if any(warning_applies_to_order(w,o) for o in orders)]
    if settle_shared:
        if fill or order_ids is None:
            raise ValueError('Shared settlement requires explicit orders and cannot add quantities')
        # This only reduces existing holds using exact issued allocations. An
        # unmatched DIFFERENT code still blocks new exports for that buyer,
        # but must not prevent settling a proven line in another tax draft.
        scope_codes={o['product_code'] for o in orders}
        warnings=[w for w in warnings if not w.get('product_code') or w['product_code'] in scope_codes]
    if warnings:
        return {'created':[], 'replaced':[], 'warnings':warnings}
    need={r['id']:max(decimal(r['actual_delivered'])-decimal(r['customer_return_qty'])-decimal(issued.get(r['id'],0)),Decimal(0)) for r in orders}
    settled={r['order_id']:r['external_issued_qty'] for r in conn.execute('SELECT * FROM outgoing_waiting_settlements')}
    if contractor or order_ids is not None:
        settlement_ids={r['id'] for r in orders}
        external={oid:q for oid,q in external.items() if oid in settlement_ids}
        settled={oid:q for oid,q in settled.items() if oid in settlement_ids}
    consume={oid:max(decimal(q)-decimal(settled.get(oid,0)),Decimal(0)) for oid,q in external.items()}
    old=[];replacement=[];created=[]
    # Remote saved drafts cannot be rewritten. Allocate their holds first.
    drafts=[dict(r) for r in conn.execute("""SELECT * FROM outgoing_invoice_drafts WHERE status='draft'
        AND (?='' OR contractor=?)
        ORDER BY CASE WHEN minvoice_status IN ('saved','saving','unknown') THEN 0 ELSE 1 END,id""",(contractor,contractor))]
    drafts=[r for r in drafts if r['contractor'] not in excluded]
    if order_ids is not None:
        drafts=[r for r in drafts if links[r['id']] & order_ids]
    try:from .outgoing_queue_archive import archived_order_ids
    except ImportError:from outgoing_queue_archive import archived_order_ids
    archived=archived_order_ids(conn)
    stock=canonical_available_stock(conn)
    capacity={code:decimal(r['raw_available_qty']) for code,r in stock.items()}
    # Recheck old holds too: a changed policy or stock cannot keep an invalid
    # quantity invoiceable. Restore only this scope's holds into its budget.
    for d in drafts:
        for r in conn.execute("SELECT product_code,qty_out FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",(str(d['id']),)):
            capacity[r['product_code']]=capacity.get(r['product_code'],Decimal(0))+decimal(r['qty_out'])
    capacity={code:max(q,Decimal(0)) for code,q in capacity.items()}
    for d in drafts:
        rows=[dict(r) for r in conn.execute("""SELECT l.*,o.batch_id,o.work_date,o.buy_price,o.purchase_list,o.unit order_unit,o.sell_price order_sell_price,a.source_unit_price
            FROM outgoing_order_allocations l JOIN orders o ON o.id=l.order_id
            LEFT JOIN outgoing_line_allocations a ON a.line_id=l.id AND a.order_id=l.order_id
            WHERE l.draft_id=? ORDER BY o.work_date,o.id,l.id""",(d['id'],))]
        kept=[];changed=False
        changed_price=price_message(conn,d['id'])
        exempt=exempt_order_codes(conn,rows)
        units=unit_issues(conn,rows)
        for r in rows:
            if r['order_id'] in archived and d['minvoice_status'] in ('saved','saving','unknown'):
                # Retiring demand is not permission to cancel a remote draft or release its hold.
                capacity[r['product_code']]=max(capacity.get(r['product_code'],Decimal(0))-decimal(r['qty']),Decimal(0))
                continue
            used=min(decimal(r['qty']),consume.get(r['order_id'],Decimal(0)))
            consume[r['order_id']]=max(consume.get(r['order_id'],Decimal(0))-used,Decimal(0))
            qty=min(decimal(r['qty'])-used,need.get(r['order_id'],Decimal(0)))
            code=r['product_code']
            if code not in exempt and not is_kkknt(r['tax']):qty=min(qty,capacity.get(code,Decimal(0)))
            if r['order_id'] in units:qty=Decimal(0)
            capacity[code]=max(capacity.get(code,Decimal(0))-qty,Decimal(0))
            if qty<=Decimal('0.00000001'):qty=Decimal(0)
            changed=changed or (qty==0 and decimal(r['qty'])>0) or abs(qty-decimal(r['qty']))>Decimal('0.00000001')
            need[r['order_id']]=max(need.get(r['order_id'],Decimal(0))-qty,Decimal(0))
            if qty>0:
                source_price=r['source_unit_price'] if r['source_unit_price'] is not None else r['unit_price']
                changed=changed or not same_price(source_price,r['order_sell_price'])
                kept.append({**r,'qty':float(qty),'_source_price':decimal(r['order_sell_price'])})
        changed=changed or bool(changed_price)
        if not changed:continue
        if d['minvoice_status'] in ('saved','saving','unknown'):
            warnings.append({'contractor':d['contractor'],'message':changed_price or 'Bản đã lưu M-Invoice còn chồng với lượng đã phát hành; cần đối chiếu bản số '+str(d['id'])+'.'})
            continue
        old.append(d['id'])
        if kept:replacement.append((d['contractor'],kept))
    # Ambiguous remote drafts leave the selected contractors' waiting pool unchanged.
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
        exempt_by_party={party:exempt_order_codes(conn,[o for o in orders if o['contractor']==party]) for party in {o['contractor'] for o in orders}}
        units=unit_issues(conn,orders)
        additions=defaultdict(list)
        already_held=defaultdict(lambda:Decimal(0))
        def price_key(o):
            return (o['contractor'],o['product_code'],o['unit'].strip().casefold(),invoice_tax_percent(o['tax']),o.get('invoice_nature') or '1',decimal(o['sell_price']))
        for o in orders:
            already_held[price_key(o)]+=max(decimal(o['actual_delivered'])-decimal(o['customer_return_qty'])-decimal(issued.get(o['id'],0))-need.get(o['id'],Decimal(0)),Decimal(0))
        for o in orders:
            if need.get(o['id'],0)<=Decimal('0.00000001'):continue
            if o['id'] in units:continue
            issues=invoice_order_issues([o])
            try:
                validate_demand_orders(conn,[o])
            except OutgoingReadinessError as exc:
                issues.append({'messages':[str(exc)]})
            if issues:
                warnings.append({'contractor':o['contractor'],'message':o['product_code']+': '+ '; '.join(issues[0]['messages'])})
                continue
            code=o['product_code'];have=available.get(code,Decimal(0))
            qty=need[o['id']] if is_kkknt(o['tax']) or code in exempt_by_party[o['contractor']] else min(need[o['id']],have)
            available[code]=max(have-qty,Decimal(0))
            if qty<=Decimal('0.00000001'):continue
            row={**o,'order_id':o['id'],'qty':float(qty),'_source_price':decimal(o['sell_price'])}
            additions[price_key(o)].append(row)
        by_tax=defaultdict(list)
        for key,rows in additions.items():
            total=sum((decimal(r['qty']) for r in rows),Decimal(0))
            total=max(export_quantity(already_held[key]+total,key[2],key[3])-already_held[key],Decimal(0))
            for r in rows:
                take=min(total,decimal(r['qty']));total-=take
                if take>0:by_tax[(key[0],key[3])].append({**r,'qty':float(take)})
        for (party,_),rows in by_tax.items():
            did=_write_draft(conn,party,rows,{r['batch_id'] for r in rows},invoice_tax_percent,timestamp,floor_kg=False,kind='waiting')
            if did:created.append(did)
    if old or created:
        audit(conn,lambda:timestamp,'outgoing.waiting_pool','ok',entity_type='outgoing_invoice',metadata={'replaced_drafts':old,'created_drafts':created,'signed_or_issued':False})
    return {'created':created,'replaced':old,'warnings':warnings}


def waiting_readiness(conn,orders,issued,*,stock=None):
    """Read only; a broken reservation or changed stock is never labelled safe."""
    held=defaultdict(float);valid=defaultdict(float);warnings=[]
    try:
        from .outgoing_contractors import excluded_codes
    except ImportError:
        from outgoing_contractors import excluded_codes
    excluded=excluded_codes(conn)
    if stock is None:stock=canonical_available_stock(conn)
    by_order={r['id']:r for r in orders}
    units=unit_issues(conn,orders)
    for d in conn.execute("SELECT id,contractor FROM outgoing_invoice_drafts WHERE status='draft'"):
        if d['contractor'] in excluded:continue
        exempt=exempt_order_codes(conn,draft_policy_rows(conn,d['id']))
        expected={r['product_code']:r['qty'] for r in conn.execute('SELECT product_code,SUM(qty) qty FROM outgoing_invoice_lines WHERE draft_id=? GROUP BY product_code',(d['id'],))}
        reserved={r['product_code']:r['qty'] for r in conn.execute("SELECT product_code,SUM(qty_out) qty FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved' GROUP BY product_code",(str(d['id']),))}
        for r in conn.execute('SELECT order_id,product_code,qty,tax FROM outgoing_order_allocations WHERE draft_id=?',(d['id'],)):
            if r['order_id'] not in by_order:continue
            oid=r['order_id'];code=r['product_code'];held[oid]+=r['qty']
            if abs(expected.get(code,0)-reserved.get(code,0))>1e-8 or (code not in exempt and not is_kkknt(r['tax']) and stock.get(code,{}).get('raw_available_qty',0)+stock.get(code,{}).get('kkknt_reserved_qty',0)<-1e-8):
                warnings.append({'contractor':d['contractor'],'message':code+': lượng giữ chờ cần đối chiếu lại với tồn hiện tại.'})
            elif oid not in units:valid[oid]+=r['qty']
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
        # Supplementary historical purchases update stock only. They must not
        # generate or replace any outgoing invoice drafts as a side effect.
        if path=='/api/bk-import/draft/confirm':return response
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
