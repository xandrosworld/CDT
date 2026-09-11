"""Explicitly associate issued source invoices with orders or outside sales."""
import hashlib
import json
from collections import defaultdict


def identity_snapshot(invoice):
    return json.dumps([invoice[k] for k in ('tenant','source','identity_key','invoice_series',
                      'invoice_number','invoice_date','buyer_tax_code','buyer_name')],ensure_ascii=False)


def resolve_scope(conn, invoice, profiles):
    row=conn.execute('SELECT * FROM outgoing_source_order_scopes WHERE invoice_id=?',(invoice['id'],)).fetchone()
    if row:
        if row['identity_snapshot'] != identity_snapshot(invoice):
            return '', 'Hóa đơn '+invoice['invoice_number']+' thay đổi thông tin người mua; cần xác nhận lại đơn liên quan.'
        return (None if row['scope']=='outside' else row['contractor']), ''
    parties=profiles.get(invoice['buyer_tax_code'].strip().upper(),[])
    if len(parties)==1:
        return parties[0], ''
    return '', 'Hóa đơn '+invoice['invoice_number']+' chưa ghép duy nhất với nhà thầu; chưa trừ vào bảng cộng dồn.'


def review_token(invoice):
    return hashlib.sha256(identity_snapshot(invoice).encode()).hexdigest()


def set_scope(conn, invoice_id, body, timestamp):
    source=conn.execute("SELECT * FROM outgoing_source_invoices WHERE id=? AND source='minvoice'",(invoice_id,)).fetchone()
    if not source or source['source_status_class']!='issued':
        raise ValueError('Chỉ xác nhận phạm vi cho hóa đơn đã phát hành.')
    if body.get('token') != review_token(source):
        raise ValueError('Thông tin hóa đơn đã thay đổi; mở lại danh sách để đối chiếu.')
    scope=body.get('scope');contractor=str(body.get('contractor') or '').strip().upper()
    note=str(body.get('note') or '').strip()
    if scope not in ('orders','outside') or not note:
        raise ValueError('Chọn đơn trên phần mềm hoặc đơn riêng và ghi lý do đối chiếu.')
    if scope=='orders' and not conn.execute('SELECT 1 FROM contractors WHERE code=?',(contractor,)).fetchone():
        raise ValueError('Chọn đúng nhà thầu của đơn đã duyệt.')
    linked=conn.execute("""SELECT contractor FROM outgoing_invoice_drafts WHERE status='issued'
        AND TRIM(issued_invoice_series)=? AND TRIM(issued_invoice_number)=?
        AND COALESCE(issued_invoice_date,invoice_date)=?""",
        (source['invoice_series'],source['invoice_number'],source['invoice_date'])).fetchall()
    if linked and (scope=='outside' or any(r['contractor']!=contractor for r in linked)):
        raise ValueError('Hóa đơn đã được xác nhận gắn với đơn trên phần mềm; cần đối chiếu liên kết đó trước khi đổi phạm vi.')
    if scope=='outside':contractor=''
    conn.execute('''INSERT INTO outgoing_source_order_scopes(invoice_id,scope,contractor,identity_snapshot,note,updated_at)
        VALUES(?,?,?,?,?,?) ON CONFLICT(invoice_id) DO UPDATE SET scope=excluded.scope,contractor=excluded.contractor,
        identity_snapshot=excluded.identity_snapshot,note=excluded.note,updated_at=excluded.updated_at''',
        (invoice_id,scope,contractor,identity_snapshot(source),note,timestamp))
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('outgoing.source.order_scope','outgoing_source_invoice',?,'ok',?,?,?)",
                 (str(invoice_id),note,json.dumps({'scope':scope,'contractor':contractor}),timestamp))
    return {'invoice_id':invoice_id,'scope':scope,'contractor':contractor}


def scope_report(conn, start, end):
    profiles=defaultdict(list)
    for r in conn.execute("SELECT contractor,tax_code FROM outgoing_buyer_profiles WHERE TRIM(COALESCE(tax_code,''))!=''"):
        profiles[r['tax_code'].strip().upper()].append(r['contractor'])
    rows=[]
    for source in conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice' AND invoice_date BETWEEN ? AND ? ORDER BY invoice_date,id",(start,end)):
        if source['source_status_class']!='issued':continue
        party,error=resolve_scope(conn,source,profiles)
        rows.append({'id':source['id'],'number':source['invoice_series']+' / '+source['invoice_number'],
                     'date':source['invoice_date'],'buyer':source['buyer_name'],'contractor':party or '',
                     'scope':'outside' if party is None else 'orders' if party else 'unresolved',
                     'stock_status':source['stock_status'],'error':error,'token':review_token(source)})
    return rows
