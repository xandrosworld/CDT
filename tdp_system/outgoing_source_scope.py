"""Explicitly associate issued source invoices with orders or outside sales."""
import hashlib
import json
from datetime import date
from decimal import Decimal
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
    tax = invoice['buyer_tax_code'].strip()
    reason = ('Mã số thuế '+tax+' chưa được gắn với nhà thầu nào trong Hồ sơ người mua.' if not parties else
              'Mã số thuế '+tax+' đang được gắn với nhiều nhà thầu: '+', '.join(parties)+'.') if tax else 'Hóa đơn chưa có Mã số thuế người mua để đối chiếu.'
    return '', reason+' Chọn Hóa đơn này thuộc, nhập Lý do xác nhận rồi bấm Lưu đối chiếu bên dưới. Hóa đơn chưa được trừ khỏi phần đơn chờ xuất; không cần xuất lại hóa đơn.'


def review_token(invoice):
    return hashlib.sha256(identity_snapshot(invoice).encode()).hexdigest()


def order_period(conn, invoice):
    row=conn.execute('SELECT * FROM outgoing_source_order_periods WHERE invoice_id=?',(invoice['id'],)).fetchone()
    if row and row['identity_snapshot']==identity_snapshot(invoice):
        return row['date_from'],row['date_to']
    # Excel imports have no remote draft key. Only an exact, unique exported
    # order lineage is evidence; never infer a period from the invoice date.
    try:
        from .contract_modules import invoice_tax_percent
        from .outgoing_weights import invoice_rows
    except ImportError:
        from contract_modules import invoice_tax_percent
        from outgoing_weights import invoice_rows
    profiles=defaultdict(list)
    for r in conn.execute('SELECT contractor,tax_code FROM outgoing_buyer_profiles'):
        profiles[(r['tax_code'] or '').strip().upper()].append(r['contractor'])
    party,error=resolve_scope(conn,invoice,profiles)
    if error or not party:return '', ''
    actual=list(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice['id'],)))
    if not actual:return '', ''
    def signature(rows,source=False):
        sums=defaultdict(lambda:[Decimal(0),Decimal(0)])
        for r in rows:
            key=(str(r['source_item_code'] if source else r['product_code']).strip(),
                 str(r['source_unit'] if source else r['unit']).strip().casefold(),
                 Decimal(str(r['unit_price'])).quantize(Decimal('0.000001')),invoice_tax_percent(r['tax_rate'] if source else r['tax']),
                 str(r['source_nature'] if source else r['invoice_nature']))
            sums[key][0]+=Decimal(str(r['qty']));sums[key][1]+=Decimal(str(r['amount']))
        return {k:tuple(v.quantize(Decimal('0.000001')) for v in values) for k,values in sums.items()}
    try:expected=signature(actual,True)
    except (ValueError,TypeError):return '', ''
    matches={}
    for d in conn.execute('''SELECT id FROM outgoing_invoice_drafts WHERE contractor=?
        AND ABS(subtotal-?)<0.000001 AND ABS(total_amount-?)<0.000001
        AND created_at<=?''',(party,invoice['subtotal'],invoice['total_amount'],invoice['created_at'])):
        base=[dict(r) for r in conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=? ORDER BY id',(d['id'],))]
        try:
            if signature(invoice_rows(conn,base))!=expected:continue
        except (ValueError,TypeError):continue
        links=list(conn.execute('''SELECT a.order_id,a.qty,o.work_date FROM outgoing_order_allocations a
            JOIN orders o ON o.id=a.order_id WHERE a.draft_id=? ORDER BY a.order_id''',(d['id'],)))
        if not links:continue
        lineage=tuple((r['order_id'],r['qty']) for r in links)
        matches[lineage]=(min(r['work_date'] for r in links),max(r['work_date'] for r in links))
    if len(matches)==1:return next(iter(matches.values()))
    return '', ''


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
    start=str(body.get('date_from') or '').strip();end=str(body.get('date_to') or '').strip()
    if scope=='orders' and (start or end):
        try:
            if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError()
        except ValueError:
            raise ValueError('Từ ngày đơn và Đến ngày đơn phải đủ, đúng ngày và không đảo ngược.') from None
        if linked:
            raise ValueError('Hóa đơn đã liên kết với các dòng đơn gốc; không đổi khoảng ngày tại đây.')
    elif scope=='orders':
        start,end=order_period(conn,source)
    conn.execute('''INSERT INTO outgoing_source_order_scopes(invoice_id,scope,contractor,identity_snapshot,note,updated_at)
        VALUES(?,?,?,?,?,?) ON CONFLICT(invoice_id) DO UPDATE SET scope=excluded.scope,contractor=excluded.contractor,
        identity_snapshot=excluded.identity_snapshot,note=excluded.note,updated_at=excluded.updated_at''',
        (invoice_id,scope,contractor,identity_snapshot(source),note,timestamp))
    if scope=='orders' and start:
        conn.execute('''INSERT INTO outgoing_source_order_periods VALUES(?,?,?,?,?)
            ON CONFLICT(invoice_id) DO UPDATE SET date_from=excluded.date_from,date_to=excluded.date_to,
            identity_snapshot=excluded.identity_snapshot,updated_at=excluded.updated_at''',
            (invoice_id,start,end,identity_snapshot(source),timestamp))
    else:
        conn.execute('DELETE FROM outgoing_source_order_periods WHERE invoice_id=?',(invoice_id,))
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('outgoing.source.order_scope','outgoing_source_invoice',?,'ok',?,?,?)",
                 (str(invoice_id),note,json.dumps({'scope':scope,'contractor':contractor,'date_from':start,'date_to':end}),timestamp))
    if scope=='orders' and start:
        try:
            from .outgoing_waiting import refresh_waiting
        except ImportError:
            from outgoing_waiting import refresh_waiting
        ids={r[0] for r in conn.execute('SELECT id FROM orders WHERE contractor=? AND work_date BETWEEN ? AND ?',
                                      (contractor,start,end))}
        refresh_waiting(conn,timestamp,fill=False,contractor=contractor,order_ids=ids,settle_shared=True)
    return {'invoice_id':invoice_id,'scope':scope,'contractor':contractor}


def scope_report(conn, start, end, contractor='', *, order_scope=False):
    relevant_ids = None
    source_warnings = defaultdict(list)
    if order_scope:
        try:
            from .outgoing_unissued import issued_allocations, warning_applies_to_order
            from .outgoing_contractors import selected_orders
        except ImportError:
            from outgoing_unissued import issued_allocations, warning_applies_to_order
            from outgoing_contractors import selected_orders
        orders = selected_orders(conn, [dict(r) for r in conn.execute('''SELECT o.* FROM orders o
            JOIN batches b ON b.id=o.batch_id WHERE b.status='approved' AND o.work_date BETWEEN ? AND ?
            AND (?='' OR o.contractor=?)''', (start,end,contractor,contractor))])
        ids = {o['id'] for o in orders}
        allocations = {}
        _, warnings = issued_allocations(conn, source_order_allocations=allocations)
        for warning in warnings:
            if warning.get('invoice_id'):
                source_warnings[warning['invoice_id']].append(warning['message'])
        relevant_ids = {sid for sid, linked in allocations.items() if ids.intersection(linked)}
        relevant_ids.update(w['invoice_id'] for w in warnings if w.get('invoice_id')
                            and any(warning_applies_to_order(w,o) for o in orders))
        start,end='0001-01-01','9999-12-31'
    profiles=defaultdict(list)
    for r in conn.execute("SELECT contractor,tax_code FROM outgoing_buyer_profiles WHERE TRIM(COALESCE(tax_code,''))!=''"):
        profiles[r['tax_code'].strip().upper()].append(r['contractor'])
    rows=[]
    for source in conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice' AND invoice_date BETWEEN ? AND ? ORDER BY invoice_date,id",(start,end)):
        if relevant_ids is not None and source['id'] not in relevant_ids:continue
        if source['source_status_class']!='issued':continue
        party,error=resolve_scope(conn,source,profiles)
        if not error and source_warnings[source['id']]:
            error=' '.join(source_warnings[source['id']])
        period_from,period_to=order_period(conn,source)
        rows.append({'id':source['id'],'number':source['invoice_series']+' / '+source['invoice_number'],
                     'date':source['invoice_date'],'buyer':source['buyer_name'],'contractor':party or '',
                     'scope':'outside' if party is None else 'orders' if party else 'unresolved',
                     'stock_status':source['stock_status'],'error':error,'token':review_token(source),
                     'date_from':period_from,'date_to':period_to})
    return rows
