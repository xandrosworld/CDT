"""Explicitly retire pending demand without claiming that it was invoiced."""
import json
from datetime import date
from flask import request, jsonify

try:
    from .outgoing_download_archive import digest, signature
except ImportError:
    from outgoing_download_archive import digest, signature

SCHEMA = '''CREATE TABLE IF NOT EXISTS outgoing_queue_archives (
 id INTEGER PRIMARY KEY, contractor TEXT NOT NULL, date_from TEXT NOT NULL,
 date_to TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
 restored_at TEXT NOT NULL DEFAULT ''
);'''

def records(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_queue_archives'").fetchone():
        return []
    return [dict(r) for r in conn.execute("SELECT * FROM outgoing_queue_archives WHERE restored_at='' ORDER BY id DESC")]

def order_signature(row):
    return signature(dict(order_id=row['id'], contractor=row['contractor'], work_date=row['work_date'],
        product_code=row['product_code'], unit=row['unit'],
        approved_qty=max(float(row['actual_delivered'] or 0)-float(row['customer_return_qty'] or 0),0),
        unit_price=row['sell_price'], tax=row['tax']))

def archived_order_ids(conn):
    saved={}
    for rec in records(conn):
        for r in json.loads(rec['snapshot_json']):
            saved.setdefault(r['order_id'],set()).add(r['signature'])
    if not saved:return set()
    return {r['id'] for r in conn.execute('SELECT * FROM orders WHERE id IN (SELECT value FROM json_each(?))',
            (json.dumps(list(saved)),)) if order_signature(r) in saved[r['id']]}

def preview(conn, body):
    try:
        start,end=str(body['from']),str(body['to'])
        if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise ValueError('Chọn Từ ngày đơn và Đến ngày đơn hợp lệ.') from None
    party=str(body.get('contractor') or '').strip()
    if party and not conn.execute('SELECT 1 FROM contractors WHERE code=?',(party,)).fetchone():
        raise ValueError('Chọn nhà thầu hợp lệ.')
    try:from .outgoing_unissued import unissued_payload
    except ImportError:from outgoing_unissued import unissued_payload
    p=unissued_payload(conn,end,party,start=start,respect_export_choices=True)
    rows=p['details']+p['skipped_details']
    snapshot=sorted((dict(order_id=r['order_id'],signature=signature(r)) for r in rows),key=lambda r:r['order_id'])
    ids=[r['order_id'] for r in rows]
    drafts=[dict(r) for r in conn.execute('''SELECT DISTINCT d.id,d.minvoice_status,d.total_amount
        FROM outgoing_invoice_drafts d JOIN outgoing_order_allocations a ON a.draft_id=d.id
        WHERE d.status='draft' AND a.order_id IN (SELECT value FROM json_each(?)) ORDER BY d.id''', (json.dumps(ids),))]
    summary={}
    for r in rows:
        s=summary.setdefault(r['contractor'],dict(contractor=r['contractor'],rows=0,amount=0))
        s['rows']+=1;s['amount']+=r['unissued_amount']
    history=[{k:r[k] for k in ('id','contractor','date_from','date_to','created_at')} for r in records(conn)
        if (not party or not r['contractor'] or r['contractor']==party) and r['date_from']<=end and r['date_to']>=start]
    # Include live quantities and draft state: a signature used to persist visibility alone is not a review token.
    token=digest([party,start,end,snapshot,[(r['order_id'],r['unissued_qty'],r['unit_price']) for r in rows],drafts])
    return dict(rows=len(rows),summary=list(summary.values()),history=history,token=token,snapshot=snapshot,
        remote_drafts=[r for r in drafts if r['minvoice_status'] in ('saved','saving','unknown')])

def audit(conn,action,iid,timestamp,metadata):
    conn.execute('''INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES(?,?,?,'ok',?,?,?)''',('outgoing.queue_archive.'+action,'outgoing_queue_archive',str(iid),
        'Bỏ phần cũ khỏi chờ xuất và bảng tải' if action=='hide' else 'Khôi phục phần chờ xuất',json.dumps(metadata),timestamp))

def change(conn,body,timestamp):
    if body.get('confirmed') is not True:raise ValueError('Tích xác nhận trước khi bỏ hoặc khôi phục phần chờ xuất.')
    if body.get('action')=='restore':
        rec=conn.execute('SELECT * FROM outgoing_queue_archives WHERE id=?',(body.get('id'),)).fetchone()
        if not rec:raise ValueError('Không tìm thấy lần bỏ phần cũ cần khôi phục.')
        if rec['restored_at']:return dict(unchanged=True)
        conn.execute('UPDATE outgoing_queue_archives SET restored_at=? WHERE id=?',(timestamp,rec['id']))
        # A customer restoring the queue expects its download to return as well.
        try:from .outgoing_download_archive import records as file_records
        except ImportError:from outgoing_download_archive import records as file_records
        restored={r['signature'] for r in json.loads(rec['snapshot_json'])}
        old_files=[]
        for f in file_records(conn):
            old=json.loads(f['snapshot_json']);remaining=[s for s in old if s not in restored]
            if old!=remaining:
                old_files.append(dict(id=f['id'],snapshot=old))
                conn.execute('UPDATE outgoing_download_archives SET snapshot_json=? WHERE id=?',(json.dumps(remaining),f['id']))
        audit(conn,'restore',rec['id'],timestamp,dict(previous_file_archives=old_files))
        return dict(unchanged=False)
    report=preview(conn,body)
    if body.get('token')!=report['token']:raise ValueError('Dữ liệu vừa thay đổi. Bấm Xem lại trước khi xác nhận.')
    if not report['rows']:raise ValueError('Không còn phần chờ xuất để bỏ trong phạm vi này.')
    iid=conn.execute('INSERT INTO outgoing_queue_archives(contractor,date_from,date_to,snapshot_json,created_at) VALUES(?,?,?,?,?)',
        (body.get('contractor') or '',body['from'],body['to'],json.dumps(report['snapshot']),timestamp)).lastrowid
    try:from .outgoing_contractors import release_disabled_drafts
    except ImportError:from outgoing_contractors import release_disabled_drafts
    released=release_disabled_drafts(conn,timestamp,order_ids={r['order_id'] for r in report['snapshot']})
    audit(conn,'hide',iid,timestamp,dict(summary=report['summary'],released_drafts=released,remote_drafts=report['remote_drafts']))
    return dict(id=iid,released_drafts=released,remote_drafts=report['remote_drafts'])

def register_routes(app,ctx):
    @app.post('/api/outgoing-invoices/queue-archive')
    def queue_archive():
        body=request.get_json(silent=True) or {}
        try:
            if not isinstance(body,dict):raise ValueError('Yêu cầu không hợp lệ.')
            with ctx['db']() as conn:
                conn.execute(SCHEMA);conn.execute('BEGIN IMMEDIATE')
                action=body.get('action','preview')
                if action=='preview':
                    return jsonify(ok=True,**{k:v for k,v in preview(conn,body).items() if k!='snapshot'})
                if action not in ('hide','restore'):raise ValueError('Thao tác không hợp lệ.')
                return jsonify(ok=True,**change(conn,body,ctx['now_iso']()))
        except (TypeError,ValueError) as exc:return jsonify(ok=False,error=str(exc)),409
