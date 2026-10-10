"""Keep a customer-accepted KKKNT invoice under its buyer without closing orders.

Freeze only the allocations already present at review time. The unmatched
goods remain an explicit exception, never demand for another date/contractor.
"""
import json
from collections import defaultdict
from flask import jsonify, request

SCHEMA='''CREATE TABLE IF NOT EXISTS outgoing_source_acceptances (
 id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, contractor TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, fingerprint TEXT NOT NULL, actor TEXT NOT NULL,
 reason TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT NOT NULL DEFAULT '',
 revoked_by TEXT NOT NULL DEFAULT '', revoke_reason TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS outgoing_source_acceptance_active
 ON outgoing_source_acceptances(invoice_id) WHERE revoked_at='';'''


def records(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_source_acceptances'").fetchone():return []
    return [dict(r) for r in conn.execute("SELECT * FROM outgoing_source_acceptances WHERE revoked_at='' ORDER BY id")]


def digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def basis(conn, invoice_id, party, allocations):
    try:
        from .outgoing_amount_settlement import source_snapshot
    except ImportError:
        from outgoing_amount_settlement import source_snapshot
    source=source_snapshot(conn,[invoice_id],party)[0]
    status=conn.execute('SELECT stock_status FROM outgoing_source_invoices WHERE id=?',(invoice_id,)).fetchone()[0]
    if status!='posted':raise ValueError('Hóa đơn chưa ở trạng thái Đã ghi xuất kho. Kiểm tra hóa đơn trước khi giữ chênh lệch riêng.')
    lines=[dict(r) for r in conn.execute('''SELECT line_index,source_item_code,source_item_name,source_unit,qty,
        unit_price,amount,tax_rate,source_nature,product_code,mapping_status
        FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index''',(invoice_id,))]
    if not lines or any(str(r['tax_rate']).strip().upper() not in ('KKKNT','-2') for r in lines):
        raise ValueError('Giữ chênh lệch riêng chỉ áp dụng cho hóa đơn toàn bộ hàng KKKNT.')
    ledger=[dict(r) for r in conn.execute("""SELECT product_code,SUM(qty_delta) qty,status FROM invoice_inventory_effective_ledger
        WHERE source_invoice_table='outgoing_source_invoices' AND source_invoice_id=? AND direction='output'
        GROUP BY product_code,status ORDER BY product_code,status""",(invoice_id,))]
    orders=[]
    for oid,qty in sorted((int(k),float(v)) for k,v in allocations.items()):
        row=conn.execute('''SELECT o.id,o.contractor,o.work_date,o.product_code,o.unit,o.actual_delivered,
            o.customer_return_qty,o.sell_price,o.tax,b.status batch_status FROM orders o
            JOIN batches b ON b.id=o.batch_id WHERE o.id=?''',(oid,)).fetchone()
        if not row or row['contractor']!=party or row['batch_status']!='approved' or str(row['tax']).upper()!='KKKNT':
            raise ValueError('Dòng đã đối trừ phải là đơn đã duyệt KKKNT của đúng nhà thầu.')
        if not 0<qty<=max(row['actual_delivered']-row['customer_return_qty'],0)+1e-8:
            raise ValueError('Lượng đơn đã đối trừ vừa thay đổi. Kiểm tra lại trước khi xác nhận.')
        orders.append({**dict(row),'allocated_qty':qty})
    scope=conn.execute('SELECT scope,contractor,identity_snapshot FROM outgoing_source_order_scopes WHERE invoice_id=?',(invoice_id,)).fetchone()
    period=conn.execute('SELECT date_from,date_to,identity_snapshot FROM outgoing_source_order_periods WHERE invoice_id=?',(invoice_id,)).fetchone()
    return {'source':source,'lines':lines,'ledger':ledger,'orders':orders,
            'scope':dict(scope) if scope else None,'period':dict(period) if period else None}


def coverage(conn):
    result={}
    for record in records(conn):
        snapshot=json.loads(record['snapshot_json']);allocations={int(k):v for k,v in snapshot['allocations'].items()}
        try:
            valid=digest(basis(conn,record['invoice_id'],record['contractor'],allocations))==record['fingerprint']
        except (ValueError,TypeError):valid=False
        result[record['invoice_id']]={**record,'snapshot':snapshot,'allocations':allocations,'valid':valid}
    return result


def summary(record):
    snap=record['snapshot']
    return {'id':record['id'],'invoice_id':record['invoice_id'],'contractor':record['contractor'],
        'valid':record['valid'],'actor':record['actor'],'reason':record['reason'],'created_at':record['created_at'],
        'allocated_order_rows':len(record['allocations']),'unmatched':snap['unmatched'],
        'orders':snap['basis']['orders'],
        'message':'Đã xác nhận giữ hóa đơn cho '+record['contractor']+'. Phần chênh lệch giữ riêng, không tự trừ thêm đơn.' if record['valid'] else
            'Hóa đơn hoặc đơn đã thay đổi sau xác nhận giữ chênh lệch riêng. Mở lại để kiểm tra.'}


def preview(conn, invoice_id):
    existing=coverage(conn).get(invoice_id)
    if existing:return {'ok':True,'accepted':summary(existing),'can_confirm':False}
    try:
        from .outgoing_unissued import issued_allocations, _stock_only_remap_sources
        from .outgoing_source_scope import resolve_scope
        from .outgoing_amount_settlement import coverage as money_coverage
    except ImportError:
        from outgoing_unissued import issued_allocations, _stock_only_remap_sources
        from outgoing_source_scope import resolve_scope
        from outgoing_amount_settlement import coverage as money_coverage
    source=conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(invoice_id,)).fetchone()
    if not source:raise ValueError('Không tìm thấy hóa đơn cần xác nhận.')
    profiles=defaultdict(list)
    for r in conn.execute('SELECT contractor,tax_code FROM outgoing_buyer_profiles'):
        profiles[(r['tax_code'] or '').strip().upper()].append(r['contractor'])
    party,error=resolve_scope(conn,source,profiles)
    if error or not party:raise ValueError('Chọn đúng nhà thầu trong Hóa đơn này thuộc trước khi giữ chênh lệch riêng.')
    if invoice_id in money_coverage(conn)[1]:raise ValueError('Hóa đơn đã được đối trừ theo tiền; không xác nhận thêm lần nữa.')
    if invoice_id in _stock_only_remap_sources(conn):raise ValueError('Hóa đơn đã đổi mã kho; cần đối chiếu lượng đã ghi kho trước.')
    if conn.execute("SELECT 1 FROM outgoing_invoice_drafts WHERE status='issued' AND TRIM(issued_invoice_series)=? AND TRIM(issued_invoice_number)=? AND COALESCE(issued_invoice_date,invoice_date)=?",(source['invoice_series'],source['invoice_number'],source['invoice_date'])).fetchone():
        raise ValueError('Hóa đơn đã liên kết trực tiếp với bảng kê phát hành; kiểm tra liên kết đó trước.')
    links={};quantities,warnings=issued_allocations(conn,source_order_allocations=links)
    selected=[w for w in warnings if w.get('invoice_id')==invoice_id]
    if not selected or any(w.get('code') not in ('unmatched_posted_quantity','export_source_required') for w in selected):
        raise ValueError('Chỉ xác nhận phần hàng chưa khớp đơn. Lỗi trạng thái, mã kho hoặc nguồn chưa đủ phải được xử lý trước.')
    allocations=links.get(invoice_id,{})
    snapshot={'basis':basis(conn,invoice_id,party,allocations),'allocations':allocations,
        'unmatched':[{'product_code':w.get('product_code',''),'qty':w.get('unmatched_qty'),
                      'unit':w.get('unit',''),'message':w['message']} for w in selected]}
    return {'ok':True,'can_confirm':True,'invoice_id':invoice_id,'contractor':party,
        'number':source['invoice_series']+' / '+source['invoice_number'],'total_amount':source['total_amount'],
        'allocated_order_rows':len(allocations),'orders':snapshot['basis']['orders'],'unmatched':snapshot['unmatched'],
        'token':digest({'snapshot':snapshot,'all_allocations':links}),'_snapshot':snapshot}


def confirm(conn, invoice_id, body, timestamp):
    actor=str(body.get('actor') or '').strip();reason=str(body.get('reason') or '').strip()
    if body.get('confirmed') is not True or not actor or not reason or len(actor)>120 or len(reason)>1500:
        raise ValueError('Tích xác nhận giữ hóa đơn, điền Người xác nhận và Lý do xác nhận.')
    report=preview(conn,invoice_id)
    if report.get('accepted'):
        if report['accepted']['valid']:return {'unchanged':True,'accepted':report['accepted']}
        raise ValueError('Xác nhận cũ đã thay đổi dữ liệu. Mở lại để kiểm tra trước khi xác nhận.')
    if body.get('token')!=report['token']:raise ValueError('Dữ liệu vừa thay đổi. Bấm Kiểm tra lại; nội dung đã nhập được giữ nguyên.')
    snapshot=report['_snapshot']
    record_id=conn.execute('''INSERT INTO outgoing_source_acceptances
        (invoice_id,contractor,snapshot_json,fingerprint,actor,reason,created_at) VALUES(?,?,?,?,?,?,?)''',
        (invoice_id,report['contractor'],json.dumps(snapshot,ensure_ascii=False),digest(snapshot['basis']),actor,reason,timestamp)).lastrowid
    # This operation writes review/audit only, never stock, invoices, order dates,
    # amounts, choices or drafts. Subsequent normal preparation settles holds.
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('outgoing.source.acceptance','outgoing_source_invoice',?,'ok',?,?,?)",
        (str(invoice_id),reason,json.dumps({'actor':actor,'acceptance_id':record_id,'allocations':snapshot['allocations'],'unmatched':snapshot['unmatched']},ensure_ascii=False),timestamp))
    return {'unchanged':False,'accepted':summary(coverage(conn)[invoice_id])}


def register_routes(app, ctx):
    @app.route('/api/outgoing-invoices/source-scopes/<int:invoice_id>/acceptance',methods=['GET','POST'])
    def source_acceptance(invoice_id):
        try:
            body=request.get_json(silent=True) or {}
            if not isinstance(body,dict):raise ValueError('Thông tin xác nhận không hợp lệ.')
            if request.method=='POST' and body.get('action')=='confirm':
                try:
                    from .outgoing_source_refresh import refresh_sources
                    from .order_export_scope import business_today
                except ImportError:
                    from outgoing_source_refresh import refresh_sources
                    from order_export_scope import business_today
                with ctx['db']() as conn:
                    row=conn.execute('SELECT invoice_date FROM outgoing_source_invoices WHERE id=?',(invoice_id,)).fetchone()
                    if not row:raise ValueError('Không tìm thấy hóa đơn cần xác nhận.')
                try:
                    refresh_sources(ctx['db'],ctx['create_minvoice_client'],ctx['now_iso'],row['invoice_date'],max(row['invoice_date'],business_today()))
                except Exception as exc:
                    raise ValueError('Chưa cập nhật đầy đủ M-Invoice; chưa lưu xác nhận. Bấm Kiểm tra lại rồi xác nhận lại; nội dung đã nhập được giữ nguyên.') from exc
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE' if request.method=='POST' else 'BEGIN')
                if request.method=='GET':return jsonify({k:v for k,v in preview(conn,invoice_id).items() if not k.startswith('_')})
                if body.get('action')=='confirm':return jsonify(ok=True,**confirm(conn,invoice_id,body,ctx['now_iso']()))
                if body.get('action')=='revoke':
                    actor=str(body.get('actor') or '').strip();reason=str(body.get('reason') or '').strip()
                    if not actor or not reason or len(actor)>120 or len(reason)>1500:raise ValueError('Điền Người xác nhận và Lý do xác nhận để mở lại.')
                    conn.execute("UPDATE outgoing_source_acceptances SET revoked_at=?,revoked_by=?,revoke_reason=? WHERE invoice_id=? AND revoked_at=''",(ctx['now_iso'](),actor,reason,invoice_id))
                    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('outgoing.source.acceptance.revoke','outgoing_source_invoice',?,'ok',?,?,?)",(str(invoice_id),reason,json.dumps({'actor':actor}),ctx['now_iso']()))
                    return jsonify(ok=True)
                raise ValueError('Chọn thao tác xác nhận hoặc mở lại.')
        except (ValueError,TypeError) as exc:return jsonify(ok=False,error=str(exc)),409
