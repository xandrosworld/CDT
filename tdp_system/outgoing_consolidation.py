"""One upload draft per buyer/tax, with exact allocations back to daily orders."""
import json
import uuid
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

try:
    from .invoice_tax_export import InvoiceTaxExportError
    from .outgoing_readiness import validate_draft_export_stock
except ImportError:
    from invoice_tax_export import InvoiceTaxExportError
    from outgoing_readiness import validate_draft_export_stock

SCHEMA = '''
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

def consolidate(conn, batch_ids, contractor, tax_percent, timestamp):
    """Replace local editable rounds atomically; grouped lines retain order lineage."""
    scope=set(batch_ids)
    drafts=[dict(r) for r in conn.execute('''SELECT DISTINCT d.* FROM outgoing_invoice_drafts d
        JOIN outgoing_order_allocations l ON l.draft_id=d.id JOIN orders o ON o.id=l.order_id
        WHERE d.status='draft' AND COALESCE(d.minvoice_status,'not_sent') NOT IN ('saved','saving','unknown')
        AND (?='' OR d.contractor=?) AND (o.batch_id IN (SELECT value FROM json_each(?))
        OR d.id IN (SELECT draft_id FROM outgoing_consolidated_days WHERE batch_id IN (SELECT value FROM json_each(?))))
        ORDER BY d.invoice_date,d.id''',(contractor,contractor,json.dumps(batch_ids),json.dumps(batch_ids)))]
    groups=defaultdict(list)
    for draft in drafts:
        lines=[dict(r) for r in conn.execute('''SELECT l.*,o.batch_id,o.work_date,o.buy_price,a.source_unit_price
            FROM outgoing_order_allocations l JOIN orders o ON o.id=l.order_id
            LEFT JOIN outgoing_line_allocations a ON a.line_id=l.id AND a.order_id=l.order_id
            WHERE l.draft_id=? ORDER BY o.work_date,l.order_id,l.id''',(draft['id'],))]
        for row in lines:
            row['_source_price']=decimal(row['source_unit_price']) if row['source_unit_price'] is not None else decimal(row['amount'])/decimal(row['qty'])
        draft['_days']={r[0] for r in conn.execute('SELECT batch_id FROM outgoing_consolidated_days WHERE draft_id=?',(draft['id'],))} | {r['batch_id'] for r in lines}
        if not draft['_days'].issubset(scope):
            raise InvoiceTaxExportError('Dự thảo đã gộp chứa ngày ngoài khoảng chọn. Chọn đủ các ngày của dự thảo để tải lại.',code='consolidated_scope_incomplete')
        taxes={tax_percent(r['tax']) for r in lines}
        if len(taxes)!=1:
            raise InvoiceTaxExportError('Dự thảo còn lẫn thuế. Cần tính lại trước khi gộp file.')
        validate_draft_export_stock(conn,draft['id'])
        groups[(draft['contractor'],next(iter(taxes)))].append((draft,lines))
    result=[]
    for (party,vat),sources in sorted(groups.items()):
        if len(sources)==1 and sources[0][0]['draft_kind']=='consolidated':
            result.append(sources[0][0]['id']);continue
        source_rows=[r for _,rows in sources for r in rows]
        by_product=defaultdict(list)
        for row in source_rows:
            by_product[(row['product_code'],row['unit'].strip().casefold(),row['invoice_nature'])].append(row)
        # A code cannot be silently combined across incompatible stock units.
        units=defaultdict(set)
        for code,unit,nature in by_product:units[code].add(unit)
        if any(len(v)>1 for v in units.values()):
            raise InvoiceTaxExportError('Cùng mã có nhiều đơn vị tính. Kiểm tra quy đổi trước khi dồn mã.')
        anchor=max(source_rows,key=lambda r:(r['work_date'],r['batch_id']))
        round_no=conn.execute('SELECT COALESCE(MAX(round_no),0)+1 FROM outgoing_invoice_drafts WHERE batch_id=? AND contractor=?',
                             (anchor['batch_id'],party)).fetchone()[0]
        draft_id=conn.execute('''INSERT INTO outgoing_invoice_drafts(batch_id,contractor,invoice_date,status,
            created_at,external_key_uuid,round_no,draft_kind) VALUES(?,?,?,'draft',?,?,?,'consolidated')''',
            (anchor['batch_id'],party,anchor['work_date'],timestamp,uuid.uuid4().hex.upper(),round_no)).lastrowid
        conn.executemany('INSERT INTO outgoing_consolidated_days(draft_id,batch_id) VALUES(?,?)',
                         [(draft_id,bid) for bid in sorted(set().union(*(d['_days'] for d,_ in sources)))])
        subtotal=tax_total=Decimal(0)
        kept=0
        for (code,unit,nature),rows in sorted(by_product.items()):
            total_qty=sum((decimal(r['qty']) for r in rows),Decimal(0))
            total_amount=sum((decimal(r['qty'])*r['_source_price'] for r in rows),Decimal(0))
            qty=total_qty.quantize(Decimal('.1'),rounding=ROUND_DOWN) if unit=='kg' else total_qty
            if qty<=0:continue
            amount=money(total_amount*qty/total_qty)
            price=(amount/qty).quantize(Decimal('.0000000001'),rounding=ROUND_HALF_UP)
            first=rows[0]
            line_id=conn.execute('''INSERT INTO outgoing_invoice_lines(draft_id,order_id,product_code,product_name,
                qty,unit,unit_price,tax,invoice_nature,amount) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (draft_id,first['order_id'],code,first['product_name'],float(qty),first['unit'],float(price),first['tax'],nature,float(amount))).lastrowid
            remaining=qty
            allocations=defaultdict(lambda:Decimal(0))
            source_values=defaultdict(lambda:Decimal(0))
            cost=Decimal(0)
            for row in rows:
                part=min(decimal(row['qty']),remaining)
                if part<=0:break
                allocations[row['order_id']]+=part;source_values[row['order_id']]+=part*row['_source_price']
                cost+=part*decimal(row['buy_price'] or 0);remaining-=part
            amount_left=amount
            for index,(order_id,part) in enumerate(allocations.items()):
                value=amount_left if index==len(allocations)-1 else min(money(amount*part/qty),amount_left)
                amount_left-=value
                conn.execute('INSERT INTO outgoing_line_allocations(line_id,order_id,qty,amount,source_unit_price) VALUES(?,?,?,?,?)',
                             (line_id,order_id,float(part),float(value),float(source_values[order_id]/part)))
            conn.execute('''INSERT INTO inventory_transactions(txn_date,product_code,qty_in,qty_out,unit_cost,
                source_type,source_id,source_line,kitchen,status,note,created_at,updated_at)
                VALUES(?,?,0,?,?,'OUTGOING_DRAFT',?,?,'','reserved','Gộp mã và thuế từ các ngày đơn',?,?)''',
                (anchor['work_date'],code,float(qty),float(cost/qty),str(draft_id),str(line_id),timestamp,timestamp))
            subtotal+=amount;tax_total+=money(amount*decimal(vat)/100) if vat>0 else 0;kept+=1
        for old,_ in sources:
            conn.execute("UPDATE outgoing_invoice_drafts SET status='cancelled' WHERE id=?",(old['id'],))
            conn.execute("UPDATE inventory_transactions SET status='cancelled',updated_at=? WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",(timestamp,str(old['id'])))
        if not kept:
            conn.execute('DELETE FROM outgoing_invoice_drafts WHERE id=?',(draft_id,));continue
        conn.execute('UPDATE outgoing_invoice_drafts SET subtotal=?,tax_amount=?,total_amount=? WHERE id=?',
                     (float(subtotal),float(tax_total),float(subtotal+tax_total),draft_id))
        validate_draft_export_stock(conn,draft_id)
        try:
            from .contract_modules import audit
        except ImportError:
            from contract_modules import audit
        audit(conn,lambda:timestamp,'outgoing.consolidate','ok',entity_type='outgoing_invoice',entity_id=draft_id,
              metadata={'source_draft_ids':[d['id'] for d,_ in sources],'batch_ids':batch_ids,'kg_precision':1,
                        'kg_rounding':'down','subtotal':float(subtotal),'lines':kept})
        result.append(draft_id)
    return result
