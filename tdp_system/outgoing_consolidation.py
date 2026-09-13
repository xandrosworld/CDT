"""One upload draft per buyer/tax, with exact allocations back to daily orders."""
import json
import uuid
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

try:
    from .invoice_tax_export import InvoiceTaxExportError
    from .outgoing_readiness import validate_draft_export_stock
    from .outgoing_names import invoice_name
except ImportError:
    from invoice_tax_export import InvoiceTaxExportError
    from outgoing_readiness import validate_draft_export_stock
    from outgoing_names import invoice_name

SCHEMA = '''
CREATE TABLE IF NOT EXISTS outgoing_waiting_settlements (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
    external_issued_qty REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outgoing_consolidated_days (
    draft_id INTEGER NOT NULL REFERENCES outgoing_invoice_drafts(id) ON DELETE CASCADE,
    batch_id INTEGER NOT NULL, PRIMARY KEY(draft_id,batch_id)
);
CREATE TABLE IF NOT EXISTS outgoing_line_allocations (
    line_id INTEGER NOT NULL REFERENCES outgoing_invoice_lines(id) ON DELETE CASCADE,
    order_id INTEGER NOT NULL, qty REAL NOT NULL, amount REAL NOT NULL, source_unit_price REAL NOT NULL,
    PRIMARY KEY(line_id,order_id)
);
CREATE VIEW IF NOT EXISTS outgoing_order_allocations AS
SELECT l.id,l.draft_id,COALESCE(a.order_id,l.order_id) order_id,l.product_code,l.product_name,
       COALESCE(a.qty,l.qty) qty,l.unit,
       CASE WHEN a.line_id IS NULL THEN l.unit_price ELSE a.amount/a.qty END unit_price,
       l.tax,l.invoice_nature,COALESCE(a.amount,l.amount) amount
FROM outgoing_invoice_lines l LEFT JOIN outgoing_line_allocations a ON a.line_id=l.id;
'''

def decimal(value):
    return Decimal(str(value))

def money(value):
    return decimal(value).quantize(Decimal('1'),rounding=ROUND_HALF_UP)


def export_quantity(value, unit):
    unit=str(unit or '').strip().casefold()
    quantum=Decimal('.1') if unit=='kg' else Decimal('1') if unit in {'cái','quả','con','chiếc'} else None
    if quantum is None:return value
    # SQLite REAL subtraction can leave 0.7999999999999999 for 0.8.
    # Remove only noise below the stock guard's epsilon before flooring;
    # a real remainder such as 0.799999 must still export 0.7, not 0.8.
    nearest=value.quantize(quantum,rounding=ROUND_HALF_UP)
    if abs(nearest-value)<Decimal('0.000000001'):value=nearest
    return value.quantize(quantum,rounding=ROUND_DOWN)

def replenishable_scopes(conn, orders, batch_ids):
    """Add newly available stock only when it increases an exported quantity."""
    try:
        from .outgoing_readiness import _project_rows
    except ImportError:
        from outgoing_readiness import _project_rows
    source={r['id']:r for r in orders}
    groups=defaultdict(list)
    for r in _project_rows(conn,orders,batch_ids):
        o=source[r['order_id']]
        groups[(r['contractor'],r['product_code'],r['unit'].strip().casefold(),o['tax'],o.get('invoice_nature') or '1',r['unit_price'])].append(r)
    result=set()
    for key,rows in groups.items():
        held=sum((decimal(r['drafted_qty']) for r in rows),Decimal(0))
        extra=sum((decimal(r['invoiceable_qty']) for r in rows),Decimal(0))
        increased=export_quantity(held+extra,key[2])>export_quantity(held,key[2])
        if increased:
            result.update((r['batch_id'],r['contractor']) for r in rows if r['invoiceable_qty']>1e-8)
    return result


def _groups(rows, floor_kg=True):
    grouped=defaultdict(list)
    for row in rows:
        key=(row['product_code'],row['unit'].strip().casefold(),row['invoice_nature'],row['_source_price'])
        grouped[key].append(row)
    result=[]
    units=defaultdict(set)
    for (code,unit,nature,price),items in sorted(grouped.items()):
        units[code].add(unit)
        qty=sum((decimal(r['qty']) for r in items),Decimal(0))
        if floor_kg:qty=export_quantity(qty,unit)
        if qty>0:result.append((code,unit,nature,price,qty,items))
    conflicts=[code+' ('+', '.join(sorted(values))+')' for code,values in units.items() if len(values)>1]
    if conflicts:
        raise InvoiceTaxExportError('Cùng mã có nhiều đơn vị tính: '+ '; '.join(conflicts)+'. Kiểm tra quy đổi trước khi dồn mã.')
    return result


def _write_draft(conn,party,rows,days,tax_percent,timestamp,*,floor_kg=True,kind='consolidated'):
    groups=_groups(rows,floor_kg)
    if not groups:return None
    anchor=max(rows,key=lambda r:(r['work_date'],r['batch_id']))
    round_no=conn.execute('SELECT COALESCE(MAX(round_no),0)+1 FROM outgoing_invoice_drafts WHERE batch_id=? AND contractor=?',(anchor['batch_id'],party)).fetchone()[0]
    did=conn.execute("""INSERT INTO outgoing_invoice_drafts(batch_id,contractor,invoice_date,status,created_at,external_key_uuid,round_no,draft_kind)
        VALUES(?,?,?,'draft',?,?,?,?)""",(anchor['batch_id'],party,anchor['work_date'],timestamp,uuid.uuid4().hex.upper(),round_no,kind)).lastrowid
    conn.executemany('INSERT INTO outgoing_consolidated_days(draft_id,batch_id) VALUES(?,?)',[(did,b) for b in sorted(days)])
    subtotal=tax_total=Decimal(0)
    for code,unit,nature,price,qty,items in groups:
        first=items[0];amount=money(qty*price)
        lid=conn.execute('''INSERT INTO outgoing_invoice_lines(draft_id,order_id,product_code,product_name,qty,unit,unit_price,tax,invoice_nature,amount)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',(did,first['order_id'],code,invoice_name(conn,code,first['product_name']),float(qty),first['unit'],float(price),first['tax'],nature,float(amount))).lastrowid
        remaining=qty;allocations=defaultdict(lambda:Decimal(0));cost=Decimal(0)
        for row in items:
            part=min(decimal(row['qty']),remaining)
            if part<=0:break
            allocations[row['order_id']]+=part;cost+=part*decimal(row['buy_price'] or 0);remaining-=part
        amount_left=amount
        for index,(oid,part) in enumerate(allocations.items()):
            value=amount_left if index==len(allocations)-1 else min(money(part*price),amount_left);amount_left-=value
            conn.execute('INSERT INTO outgoing_line_allocations(line_id,order_id,qty,amount,source_unit_price) VALUES(?,?,?,?,?)',(lid,oid,float(part),float(value),float(price)))
        conn.execute("""INSERT INTO inventory_transactions(txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,kitchen,status,note,created_at,updated_at)
            VALUES(?,?,0,?,?,'OUTGOING_DRAFT',?,?,'','reserved','Chọn phạm vi đơn chưa phát hành',?,?)""",(anchor['work_date'],code,float(qty),float(cost/qty),str(did),str(lid),timestamp,timestamp))
        vat=tax_percent(first['tax']);subtotal+=amount;tax_total+=money(amount*decimal(vat)/100) if vat>0 else 0
    conn.execute('UPDATE outgoing_invoice_drafts SET subtotal=?,tax_amount=?,total_amount=? WHERE id=?',(float(subtotal),float(tax_total),float(subtotal+tax_total),did))
    return did


def consolidate(conn,batch_ids,contractor,tax_percent,timestamp):
    """Select editable quantities by day; preserve sale prices and other days' holds."""
    scope=set(batch_ids)
    drafts=[dict(r) for r in conn.execute('''SELECT DISTINCT d.* FROM outgoing_invoice_drafts d
        JOIN outgoing_order_allocations l ON l.draft_id=d.id JOIN orders o ON o.id=l.order_id
        WHERE d.status='draft' AND COALESCE(d.minvoice_status,'not_sent') NOT IN ('saved','saving','unknown')
        AND (?='' OR d.contractor=?) AND (o.batch_id IN (SELECT value FROM json_each(?))
        OR d.id IN (SELECT draft_id FROM outgoing_consolidated_days WHERE batch_id IN (SELECT value FROM json_each(?))))
        ORDER BY d.invoice_date,d.id''',(contractor,contractor,json.dumps(batch_ids),json.dumps(batch_ids)))]
    grouped=defaultdict(list)
    for d in drafts:
        rows=[dict(r) for r in conn.execute('''SELECT l.*,o.batch_id,o.work_date,o.buy_price,a.source_unit_price
            FROM outgoing_order_allocations l JOIN orders o ON o.id=l.order_id
            LEFT JOIN outgoing_line_allocations a ON a.line_id=l.id AND a.order_id=l.order_id
            WHERE l.draft_id=? ORDER BY o.work_date,l.order_id,l.id''',(d['id'],))]
        for r in rows:r['_source_price']=decimal(r['source_unit_price'] if r['source_unit_price'] is not None else r['unit_price'])
        taxes={tax_percent(r['tax']) for r in rows}
        if len(taxes)!=1:raise InvoiceTaxExportError('Dự thảo còn lẫn thuế. Cần tính lại trước khi gộp file.')
        validate_draft_export_stock(conn,d['id'])
        d['_days']={r[0] for r in conn.execute('SELECT batch_id FROM outgoing_consolidated_days WHERE draft_id=?',(d['id'],))}|{r['batch_id'] for r in rows}
        grouped[(d['contractor'],next(iter(taxes)))].append((d,rows))
    result=[];created=[];old_ids=[]
    for (party,vat),sources in sorted(grouped.items()):
        selected=[r for _,rows in sources for r in rows if r['batch_id'] in scope]
        if len(sources)==1 and sources[0][0]['_days'].issubset(scope):
            old=sources[0][0]
            expected=sorted((code,unit,nature,price,qty) for code,unit,nature,price,qty,_ in _groups(selected))
            actual=sorted((r['product_code'],r['unit'].strip().casefold(),r['invoice_nature'],decimal(r['unit_price']),decimal(r['qty'])) for r in conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=?',(old['id'],)))
            if old['draft_kind']=='consolidated' and expected==actual:
                result.append(old['id']);continue
        # Keep all unselected allocations in separate daily drafts, including fractional Kg.
        outside=defaultdict(list)
        for old,rows in sources:
            old_ids.append(old['id'])
            for r in rows:
                if r['batch_id'] not in scope:outside[r['batch_id']].append(r)
        for bid,rows in outside.items():
            did=_write_draft(conn,party,rows,{bid},tax_percent,timestamp,floor_kg=False)
            if did:created.append(did)
        if selected:
            days=set().union(*(d['_days'] for d,_ in sources))&scope
            did=_write_draft(conn,party,selected,days,tax_percent,timestamp)
            if did:created.append(did);result.append(did)
    for did in old_ids:
        conn.execute("UPDATE outgoing_invoice_drafts SET status='cancelled' WHERE id=?",(did,))
        conn.execute("UPDATE inventory_transactions SET status='cancelled',updated_at=? WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",(timestamp,str(did)))
    for did in created:validate_draft_export_stock(conn,did)
    if old_ids:
        try:from .contract_modules import audit
        except ImportError:from contract_modules import audit
        audit(conn,lambda:timestamp,'outgoing.select_scope','ok',entity_type='outgoing_invoice',
              metadata={'source_draft_ids':old_ids,'created_draft_ids':created,'export_draft_ids':result,'batch_ids':batch_ids,'sale_prices_preserved':True})
    return result
