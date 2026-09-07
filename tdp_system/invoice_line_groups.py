"""Explicit display groups; immutable invoice source and stock events stay traceable."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from flask import jsonify, request


SCHEMA = """CREATE TABLE IF NOT EXISTS invoice_input_line_groups (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant TEXT NOT NULL, invoice_id INTEGER NOT NULL,
 member_indices TEXT NOT NULL, fingerprint TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);"""


class GroupError(ValueError):
    pass


def _fingerprint(rows):
    fields = ('invoice_id','line_index','source_item_code','source_item_name','source_unit','qty','unit_price','amount',
              'tax_rate','product_code','product_name','product_unit','mapping_status','conversion_factor','stock_qty')
    values = [[r.get(k) for k in fields] for r in sorted(rows, key=lambda r:r['line_index'])]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _groups(conn, tenant, invoice_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='invoice_input_line_groups'").fetchone():
        return []
    return [dict(r) for r in conn.execute('SELECT * FROM invoice_input_line_groups WHERE tenant=? AND invoice_id=? AND active=1 ORDER BY id', (tenant,invoice_id))]


def _rows(conn, item_ids):
    marks=','.join('?' for _ in item_ids)
    return [dict(r) for r in conn.execute(f'''SELECT li.*,p.name product_name,p.unit product_unit,
        i.tenant,i.sync_status,i.receipt_status,i.invoice_number,i.invoice_series,i.invoice_type
        FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
        LEFT JOIN products p ON p.code=li.product_code WHERE li.id IN ({marks})''', item_ids)]


def preview_group(conn, tenant, item_ids):
    if not isinstance(item_ids,list) or not 2 <= len(item_ids) <= 100 or any(type(i) is not int for i in item_ids) or len(set(item_ids)) != len(item_ids):
        raise GroupError('Chọn từ 2 đến 100 dòng khác nhau để gộp.')
    rows=_rows(conn,item_ids)
    if len(rows)!=len(item_ids) or any(r['tenant']!=tenant for r in rows):
        raise GroupError('Dòng đã thay đổi hoặc không thuộc dữ liệu đang sử dụng. Hãy đọc lại bảng.')
    if len({r['invoice_id'] for r in rows})!=1:
        raise GroupError('Chỉ gộp các dòng trong cùng một hóa đơn.')
    if any(r['receipt_status']=='posted' or r['sync_status']!='synced' or r['invoice_type']!='INPUT_ELECTRONIC_INVOICE' for r in rows):
        raise GroupError('Hóa đơn đã nhập kho hoặc nguồn cần kiểm tra; không được tạo nhóm mới.')
    if any(not r['inventory_eligible'] or r['mapping_status']!='mapped' or not r['product_code'] or not r['product_unit'] for r in rows):
        raise GroupError('Cần ghép đúng mã và lưu đủ quy đổi trước khi gộp.')
    if len({(r['product_code'],r['product_unit'],r['tax_rate']) for r in rows})!=1:
        raise GroupError('Các dòng phải cùng mã hàng, đơn vị sau quy đổi và thuế suất. Không gộp khác mặt hàng.')
    indices={r['line_index'] for r in rows}
    for g in _groups(conn,tenant,rows[0]['invoice_id']):
        if indices.intersection(json.loads(g['member_indices'])):
            raise GroupError('Có dòng đã nằm trong nhóm khác. Hãy Tách lại nhóm đó trước.')
    try:
        values=[(Decimal(str(r['stock_qty'])),Decimal(str(r['amount']))) for r in rows]
    except InvalidOperation:
        raise GroupError('Lượng hoặc tiền không hợp lệ để tính giá vốn.') from None
    if any(not q.is_finite() or not a.is_finite() or q<=0 or a<0 for q,a in values):
        raise GroupError('Lượng hoặc tiền không hợp lệ để tính giá vốn.')
    quantity=sum((q for q,a in values),Decimal(0))
    amount=sum((a for q,a in values),Decimal(0))
    return {'invoice_id':rows[0]['invoice_id'],'invoice_number':rows[0]['invoice_series']+' / '+rows[0]['invoice_number'],
            'item_ids':sorted(item_ids),'member_indices':sorted(indices),'token':_fingerprint(rows),
            'product_code':rows[0]['product_code'],'product_name':rows[0]['product_name'],'unit':rows[0]['product_unit'],
            'qty':float(quantity),'amount':float(amount),'unit_cost':float(amount/quantity),'count':len(rows)}


def create_group(conn, tenant, item_ids, token, now):
    if not isinstance(item_ids,list) or any(type(i) is not int for i in item_ids) or not 2<=len(item_ids)<=100 or len(set(item_ids))!=len(item_ids):
        raise GroupError('Chọn từ 2 đến 100 dòng khác nhau để gộp.')
    # A retried successful confirmation must not create another group.
    existing=conn.execute('SELECT * FROM invoice_input_line_groups WHERE tenant=? AND fingerprint=? AND active=1', (tenant,str(token or ''))).fetchone()
    if existing:
        current_ids={r[0] for r in conn.execute('SELECT id FROM msmi_invoice_items WHERE invoice_id=? AND line_index IN ('+','.join('?' for _ in json.loads(existing['member_indices']))+')', (existing['invoice_id'],*json.loads(existing['member_indices'])))}
        if set(item_ids or [])==current_ids and _fingerprint(_rows(conn,item_ids))==token:
            return {'id':existing['id'],'idempotent':True}
    preview=preview_group(conn,tenant,item_ids)
    if not token or token!=preview['token']:
        raise GroupError('Dữ liệu đã thay đổi sau khi xem trước. Hãy chọn và kiểm tra lại trước khi gộp.')
    cur=conn.execute('INSERT INTO invoice_input_line_groups(tenant,invoice_id,member_indices,fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                     (tenant,preview['invoice_id'],json.dumps(preview['member_indices']),token,now,now))
    _audit(conn,cur.lastrowid,'create',now)
    return {'id':cur.lastrowid,'idempotent':False,**preview}


def _audit(conn, group_id, action, now):
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('invoice_group.change','invoice_group',?,'ok','',?,?)",
                 (str(group_id),json.dumps({'action':action}),now))


def split_group(conn, tenant, group_id, now):
    row=conn.execute('SELECT * FROM invoice_input_line_groups WHERE id=? AND tenant=?',(group_id,tenant)).fetchone()
    if not row: raise GroupError('Không tìm thấy nhóm dòng trong dữ liệu đang sử dụng.')
    if row['active']:
        conn.execute('UPDATE invoice_input_line_groups SET active=0,updated_at=? WHERE id=?',(now,group_id))
        _audit(conn,group_id,'split',now)
    return {'id':group_id}


def grouped_lines(conn, tenant, invoices, lines):
    result=list(lines);warnings=[]
    for invoice in invoices:
        for g in _groups(conn,tenant,invoice['id']):
            indices=json.loads(g['member_indices'])
            members=[dict(r,invoice_id=invoice['id']) for r in invoice['items'] if r['line_index'] in indices]
            if len(members)!=len(indices) or _fingerprint(members)!=g['fingerprint']:
                warnings.append({'id':g['id'],'invoice_id':invoice['id'],'message':'Nhóm cũ đã thay đổi dữ liệu. Hiện lại các dòng gốc để kiểm tra.'})
                continue
            positions=[n for n,r in enumerate(result) if r['invoice_id']==invoice['id'] and r['line_index'] in indices]
            if len(positions)!=len(indices): continue
            qty=sum(Decimal(str(r['stock_qty'])) for r in members)
            amount=sum(Decimal(str(r['amount'])) for r in members)
            first=result[min(positions)]
            merged={**first,'group_id':g['id'],'group_members':members,'line_index':' + '.join(map(str,indices)),
                    'source_item_code':'','source_item_name':first['product_name'],'source_unit':first['product_unit'],
                    'qty':float(qty),'stock_qty':float(qty),'amount':float(amount),'unit_price':float(amount/qty),
                    'stock_unit_price':float(amount/qty),'conversion_factor':1}
            result=[merged if n==min(positions) else r for n,r in enumerate(result) if n==min(positions) or n not in positions]
    return result,warnings


def register_group_routes(app,ctx):
    def tenant(conn):
        r=conn.execute("SELECT value FROM settings WHERE key='tenant_code'").fetchone()
        return str(r[0] if r else 'TDP').strip() or 'TDP'
    @app.post('/api/invoice-workbench/input-groups/preview')
    def group_preview():
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN')
                return jsonify(ok=True,**preview_group(conn,tenant(conn),(request.get_json(silent=True) or {}).get('item_ids')))
        except GroupError as e:return jsonify(ok=False,error=str(e)),409
    @app.post('/api/invoice-workbench/input-groups')
    def group_save():
        body=request.get_json(silent=True) or {}
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                return jsonify(ok=True,**create_group(conn,tenant(conn),body.get('item_ids'),body.get('token'),ctx['now_iso']()))
        except GroupError as e:return jsonify(ok=False,error=str(e)),409
    @app.post('/api/invoice-workbench/input-groups/<int:group_id>/split')
    def group_split(group_id):
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                return jsonify(ok=True,**split_group(conn,tenant(conn),group_id,ctx['now_iso']()))
        except GroupError as e:return jsonify(ok=False,error=str(e)),409
