"""Downloaded files are workflow receipts, never evidence of issued invoices."""
import hashlib
import json
import uuid
from io import BytesIO
from flask import request, jsonify, send_file

SCHEMA='''CREATE TABLE IF NOT EXISTS outgoing_export_receipts (
 token TEXT PRIMARY KEY, filename TEXT NOT NULL, manifest TEXT NOT NULL,
 file_data BLOB NOT NULL, created_at TEXT NOT NULL, received_at TEXT NOT NULL DEFAULT ''
);'''


def draft_snapshot(conn,did):
    draft=conn.execute('SELECT status FROM outgoing_invoice_drafts WHERE id=?',(did,)).fetchone()
    if not draft or draft['status']!='draft':return None
    rows=[dict(r) for r in conn.execute('''SELECT a.order_id,a.qty,o.contractor,o.work_date,
        o.product_code,o.unit,o.sell_price,o.tax,o.actual_delivered,o.customer_return_qty
        FROM outgoing_order_allocations a JOIN orders o ON o.id=a.order_id
        WHERE a.draft_id=? ORDER BY a.order_id,a.id''',(did,))]
    lines=[tuple(r) for r in conn.execute('SELECT * FROM outgoing_invoice_lines WHERE draft_id=? ORDER BY id',(did,))]
    return {'id':did,'rows':rows,'hash':hashlib.sha256(json.dumps([rows,lines],sort_keys=True).encode()).hexdigest()}


def create(conn,ids,data,filename,timestamp):
    manifest=[draft_snapshot(conn,int(d)) for d in ids]
    manifest=[d for d in manifest if d and d['rows']]
    if not manifest:return ''
    serialized=json.dumps(manifest)
    previous=conn.execute('SELECT token FROM outgoing_export_receipts WHERE manifest=?',(serialized,)).fetchone()
    if previous:return previous['token']
    token=uuid.uuid4().hex
    conn.execute('INSERT INTO outgoing_export_receipts VALUES(?,?,?,?,?,?)',
                 (token,filename,serialized,data,timestamp,''))
    return token


def annotate(conn,payload):
    quantities={};history=[];seen=set()
    for r in conn.execute("SELECT token,filename,manifest,received_at FROM outgoing_export_receipts WHERE received_at<>'' ORDER BY received_at DESC"):
        relevant=False
        for old in json.loads(r['manifest']):
            relevant=relevant or any((not payload['contractor'] or o['contractor']==payload['contractor'])
                and (not payload['from'] or o['work_date']>=payload['from']) and o['work_date']<=payload['asof'] for o in old['rows'])
            if old['id'] in seen:continue
            current=draft_snapshot(conn,old['id'])
            if not current or current['hash']!=old['hash']:continue
            seen.add(old['id'])
            for o in old['rows']:quantities[o['order_id']]=quantities.get(o['order_id'],0)+o['qty']
        if relevant:history.append({k:r[k] for k in ('token','filename','received_at')})
    for r in payload['line_choices']:
        r['downloaded_qty']=min(r['qty'],quantities.get(r['order_id'],0))
    for r in payload['details']+payload['skipped_details']:
        r['downloaded_qty']=min(r['unissued_qty'],quantities.get(r['order_id'],0))
    payload['export_receipts']=history
    return payload


def register_routes(app,ctx):
    @app.post('/api/outgoing-invoices/export-receipts/<token>/received')
    def received(token):
        with ctx['db']() as c:
            row=c.execute('SELECT token FROM outgoing_export_receipts WHERE token=?',(token,)).fetchone()
            if not row:return jsonify(ok=False,error='Không tìm thấy file đã tải.'),404
            c.execute("UPDATE outgoing_export_receipts SET received_at=? WHERE token=? AND received_at=''",(ctx['now_iso'](),token))
        return jsonify(ok=True)

    @app.get('/api/outgoing-invoices/export-receipts/<token>/file')
    def saved_file(token):
        with ctx['db']() as c:
            row=c.execute("SELECT filename,file_data FROM outgoing_export_receipts WHERE token=? AND received_at<>''",(token,)).fetchone()
            if not row:return jsonify(ok=False,error='Không tìm thấy file đã tải.'),404
            return send_file(BytesIO(row['file_data']),as_attachment=True,download_name=row['filename'],mimetype='application/zip')
