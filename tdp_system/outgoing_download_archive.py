"""Reversible visibility for the unissued template download, never invoice coverage."""
import hashlib
import json
from datetime import date
from flask import request, jsonify

SCHEMA = '''CREATE TABLE IF NOT EXISTS outgoing_download_archives (
 id INTEGER PRIMARY KEY, contractor TEXT NOT NULL, date_from TEXT NOT NULL,
 date_to TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
 restored_at TEXT NOT NULL DEFAULT ''
);'''

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def signature(row):
    return digest({k:row.get(k) for k in ('order_id','contractor','work_date','product_code','unit','approved_qty','unit_price','tax')})

def records(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_download_archives'").fetchone():return []
    return [dict(r) for r in conn.execute("SELECT * FROM outgoing_download_archives WHERE restored_at='' ORDER BY id DESC")]

def visible_payload(conn,payload):
    hidden={s for rec in records(conn) for s in json.loads(rec['snapshot_json'])}
    filtered={key:[r for r in payload.get(key,[]) if signature(r) not in hidden] for key in ('details','skipped_details')}
    return {**payload, **filtered, 'download_hidden_rows':sum(len(payload.get(k,[]))-len(filtered[k]) for k in filtered)}

def preview(conn,body):
    try:
        start,end=str(body['from']),str(body['to'])
        if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError()
    except (KeyError,TypeError,ValueError):raise ValueError('Chọn Từ ngày đơn và Đến ngày đơn hợp lệ.') from None
    party=str(body.get('contractor') or '')
    try:from .outgoing_unissued import unissued_payload
    except ImportError:from outgoing_unissued import unissued_payload
    payload=visible_payload(conn,unissued_payload(conn,end,party,start=start,respect_export_choices=True))
    rows=payload['details']+payload['skipped_details']
    snapshot=sorted(signature(r) for r in rows)
    summary={}
    for r in rows:
        s=summary.setdefault(r['contractor'],{'contractor':r['contractor'],'rows':0,'amount':0})
        s['rows']+=1;s['amount']+=r['unissued_amount']
    history=[{k:r[k] for k in ('id','contractor','date_from','date_to','created_at')} for r in records(conn)
             if (not party or r['contractor']==party or not r['contractor']) and r['date_from']<=end and r['date_to']>=start]
    return dict(snapshot=snapshot,token=digest([party,start,end,snapshot]),rows=len(rows),summary=list(summary.values()),history=history)

def register_routes(app,ctx):
    @app.post('/api/outgoing-invoices/download-archive')
    def download_archive():
        body=request.get_json(silent=True) or {}
        try:
            if not isinstance(body,dict):raise ValueError('Yêu cầu không hợp lệ.')
            with ctx['db']() as conn:
                conn.execute(SCHEMA)
                conn.execute('BEGIN IMMEDIATE')
                action=body.get('action','preview')
                if action=='restore':
                    if body.get('confirmed') is not True:raise ValueError('Xác nhận khôi phục phần đã ẩn.')
                    rec=conn.execute('SELECT * FROM outgoing_download_archives WHERE id=?',(body.get('id'),)).fetchone()
                    if not rec:raise ValueError('Không tìm thấy lần ẩn cần khôi phục.')
                    conn.execute("UPDATE outgoing_download_archives SET restored_at=? WHERE id=? AND restored_at=''",(ctx['now_iso'](),rec['id']))
                    return jsonify(ok=True)
                report=preview(conn,body)
                if action=='hide':
                    if body.get('confirmed') is not True:raise ValueError('Tích xác nhận ẩn phần cũ khỏi bảng tải.')
                    if body.get('token')!=report['token']:raise ValueError('Dữ liệu vừa thay đổi. Bấm Xem lại trước khi xác nhận.')
                    if not report['rows']:raise ValueError('Không còn dòng để ẩn trong phạm vi này.')
                    conn.execute('INSERT INTO outgoing_download_archives(contractor,date_from,date_to,snapshot_json,created_at) VALUES(?,?,?,?,?)',
                                 (body.get('contractor') or '',body['from'],body['to'],json.dumps(report['snapshot']),ctx['now_iso']()))
                elif action!='preview':raise ValueError('Thao tác không hợp lệ.')
                return jsonify(ok=True,**{k:v for k,v in report.items() if k!='snapshot'})
        except (ValueError,TypeError) as exc:return jsonify(ok=False,error=str(exc)),409
