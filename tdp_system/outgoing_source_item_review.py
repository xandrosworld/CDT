"""Customer-confirmed changed invoice items: order reconciliation only."""
import hashlib
import json
import math


def fingerprint(conn, invoice_id, items, *, legacy=False):
    source=dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(invoice_id,)).fetchone())
    # Sync timestamps may change without changing the invoice.
    source={k:source[k] for k in ('tenant','identity_key','invoice_series','invoice_number','invoice_date',
        'buyer_tax_code','buyer_name','source_status_class','subtotal','total_amount')}
    fields='*' if legacy else 'line_index,source_item_code,source_item_name,source_unit,qty,unit_price,amount,tax_rate,source_nature,inventory_eligible,product_code,mapping_status'
    lines=[tuple(r) for r in conn.execute('SELECT '+fields+' FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY '+('id' if legacy else 'line_index'),(invoice_id,))]
    orders=[]
    for item in items:
        for oid in item['order_ids']:
            row=conn.execute('SELECT id,contractor,work_date,product_code,unit,actual_delivered,customer_return_qty,sell_price,tax FROM orders WHERE id=?',(oid,)).fetchone()
            orders.append(tuple(row) if row else None)
    period=conn.execute('SELECT date_from,date_to,identity_snapshot FROM outgoing_source_order_periods WHERE invoice_id=?',(invoice_id,)).fetchone()
    ledger=[tuple(r) for r in conn.execute("SELECT product_code,qty_delta,status FROM invoice_inventory_effective_ledger WHERE source_invoice_table='outgoing_source_invoices' AND source_invoice_id=? ORDER BY product_code,qty_delta",(invoice_id,))]
    digest=hashlib.sha256(json.dumps([source,lines,orders,list(period) if period else None,ledger,items],sort_keys=True,default=str).encode()).hexdigest()
    return digest if legacy else 'v2:'+digest


def upgrade_fingerprints(conn):
    # Upgrade only reviews still valid under their original rules. Never turn a
    # stale customer confirmation back into a valid one during deployment.
    for row in conn.execute("SELECT * FROM outgoing_source_item_reviews WHERE fingerprint NOT LIKE 'v2:%'").fetchall():
        if not conn.execute('SELECT 1 FROM outgoing_source_invoices WHERE id=?',(row['invoice_id'],)).fetchone():continue
        items=json.loads(row['items_json'])
        if row['fingerprint']==fingerprint(conn,row['invoice_id'],items,legacy=True):
            conn.execute('UPDATE outgoing_source_item_reviews SET fingerprint=? WHERE invoice_id=?',
                         (fingerprint(conn,row['invoice_id'],items),row['invoice_id']))


def reviewed_items(conn, invoice_id):
    row=conn.execute('SELECT * FROM outgoing_source_item_reviews WHERE invoice_id=?',(invoice_id,)).fetchone()
    if not row:return [],False
    items=json.loads(row['items_json'])
    return items,row['fingerprint']!=fingerprint(conn,invoice_id,items,legacy=not row['fingerprint'].startswith('v2:'))


def save_review(conn, source, party, start, end, items, note, timestamp):
    if not start or not end or not isinstance(items,list) or not items:
        raise ValueError('Cần xác nhận khoảng ngày đơn và các dòng đã đổi mặt hàng.')
    normalized=[];seen=set();codes=set()
    for item in items:
        code=str(item.get('source_code','')).strip();ids=item.get('order_ids',[])
        if not code or code in codes or not ids or any(type(x) is not int or x in seen for x in ids) or len(set(ids))!=len(ids):
            raise ValueError('Mã hóa đơn hoặc dòng đơn đối chiếu bị trùng / chưa đủ.')
        codes.add(code);seen.update(ids)
        posted=conn.execute("SELECT p.unit,-SUM(l.qty_delta) qty FROM invoice_inventory_effective_ledger l JOIN products p ON p.code=l.product_code WHERE l.source_invoice_table='outgoing_source_invoices' AND l.source_invoice_id=? AND l.direction='output' AND l.status='posted' AND l.product_code=? GROUP BY p.unit",(source['id'],code)).fetchone()
        rows=[conn.execute("SELECT o.*,b.status batch_status FROM orders o JOIN batches b ON b.id=o.batch_id WHERE o.id=?",(oid,)).fetchone() for oid in ids]
        if not posted or any(not r or r['batch_status']!='approved' or r['contractor']!=party or not start<=r['work_date']<=min(end,source['invoice_date']) or r['unit'].strip().casefold()!=posted['unit'].strip().casefold() for r in rows):
            raise ValueError('Dòng đơn phải đã duyệt, cùng nhà thầu, đúng khoảng ngày và cùng đơn vị với lượng hóa đơn đã ghi kho.')
        qty=sum(max(r['actual_delivered']-r['customer_return_qty'],0) for r in rows)
        if not math.isfinite(qty) or qty<=0 or abs(qty-posted['qty'])>1e-8:
            raise ValueError('Tổng lượng dòng đơn đã chọn phải khớp lượng mặt hàng đổi trên hóa đơn.')
        normalized.append({'source_code':code,'order_ids':sorted(ids)})
    conn.execute('INSERT OR REPLACE INTO outgoing_source_item_reviews VALUES(?,?,?,?,?)',
        (source['id'],json.dumps(normalized),fingerprint(conn,source['id'],normalized),note,timestamp))
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('outgoing.source.item_review','outgoing_source_invoice',?,'ok',?,?,?)",(str(source['id']),note,json.dumps(normalized),timestamp))
