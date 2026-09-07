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
);
CREATE TABLE IF NOT EXISTS invoice_input_group_choices (
 invoice_id INTEGER NOT NULL, line_index INTEGER NOT NULL,
 source_fingerprint TEXT NOT NULL, product_code TEXT NOT NULL,
 conversion_factor REAL NOT NULL, product_unit TEXT NOT NULL, mapping_id INTEGER NOT NULL,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(invoice_id,line_index)
);
CREATE TABLE IF NOT EXISTS invoice_input_group_requests (
 token TEXT PRIMARY KEY, group_id INTEGER NOT NULL, payload TEXT NOT NULL
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
        i.tenant,i.sync_status,i.receipt_status,i.invoice_number,i.invoice_series,i.invoice_type,i.seller_tax_code
        FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
        LEFT JOIN products p ON p.code=li.product_code WHERE li.id IN ({marks})''', item_ids)]


def selection_rows(conn, tenant, item_ids):
    if not isinstance(item_ids,list) or not 2 <= len(item_ids) <= 100 or any(type(i) is not int for i in item_ids) or len(set(item_ids)) != len(item_ids):
        raise GroupError('Chọn từ 2 đến 100 dòng khác nhau để gộp.')
    rows=_rows(conn,item_ids)
    if len(rows)!=len(item_ids) or any(r['tenant']!=tenant for r in rows):
        raise GroupError('Dòng đã thay đổi hoặc không thuộc dữ liệu đang sử dụng. Hãy đọc lại bảng.')
    if len({r['invoice_id'] for r in rows})!=1:
        raise GroupError('Chỉ gộp các dòng trong cùng một hóa đơn.')
    if any(r['receipt_status'] in ('posted','blocked') or r['sync_status']!='synced' or r['invoice_type']!='INPUT_ELECTRONIC_INVOICE' for r in rows):
        raise GroupError('Hóa đơn đã nhập kho hoặc nguồn cần kiểm tra; không được tạo nhóm mới.')
    if any(not r['inventory_eligible'] for r in rows):
        raise GroupError('Chỉ chọn dòng hàng được nhập kho; không gộp dịch vụ hoặc điều chỉnh.')
    indices={r['line_index'] for r in rows}
    for g in _groups(conn,tenant,rows[0]['invoice_id']):
        if indices.intersection(json.loads(g['member_indices'])):
            raise GroupError('Có dòng đã nằm trong nhóm khác. Hãy Tách lại nhóm đó trước.')
    return rows


def preview_group(conn, tenant, item_ids):
    rows=selection_rows(conn,tenant,item_ids)
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


def source_fingerprint(row):
    fields=('invoice_id','line_index','source_item_code','source_item_name','source_unit','qty','unit_price','amount','tax_rate')
    return hashlib.sha256(json.dumps([row[k] for k in fields],ensure_ascii=False).encode()).hexdigest()


def _mapping_helpers():
    try:
        import invoice_mapping as mapping
    except ImportError:
        from . import invoice_mapping as mapping
    return mapping


def selection_preview(conn, tenant, item_ids, product_code=None, factors=None):
    rows=selection_rows(conn,tenant,item_ids)
    if len({r['tax_rate'] for r in rows})!=1:
        raise GroupError('Các dòng khác thuế suất không được gộp chung.')
    result={'item_ids':sorted(item_ids),'count':len(rows),'invoice_number':rows[0]['invoice_series']+' / '+rows[0]['invoice_number'],
            'rows':rows,'token':_fingerprint(rows),'source_token':_fingerprint(rows),'ready':False}
    if not product_code:
        return result
    product=conn.execute('SELECT code,name,unit FROM products WHERE code=?',(str(product_code).strip(),)).fetchone()
    if not product or not str(product['unit'] or '').strip():
        raise GroupError('Chọn mã hàng có trong danh mục và có đơn vị kho.')
    if not isinstance(factors,dict) or set(factors)!={str(r['id']) for r in rows}:
        raise GroupError('Nhập đủ quy đổi cho từng dòng đã chọn.')
    mapping=_mapping_helpers()
    converted=[]
    for row in rows:
        if not str(row['source_unit'] or '').strip():
            raise GroupError(f"Dòng {row['line_index']}: thiếu đơn vị nguồn, cần kiểm tra trước khi quy đổi.")
        try:
            factor=Decimal(str(factors[str(row['id'])]))
            qty=Decimal(str(row['qty'])); amount=Decimal(str(row['amount']))
            if not all(v.is_finite() for v in (factor,qty,amount)) or factor<=0 or factor>1_000_000_000 or qty<=0 or amount<0:
                raise ValueError()
            stock_qty,price=mapping._stock_values(row['qty'],row['amount'],float(factor))
            if stock_qty<=0: raise ValueError()
        except (ValueError,InvalidOperation,OverflowError):
            raise GroupError(f"Dòng {row['line_index']}: lượng, tiền hoặc hệ số quy đổi không hợp lệ.") from None
        converted.append({**row,'product_code':product['code'],'product_name':product['name'],'product_unit':product['unit'],
                          'mapping_status':'mapped','conversion_factor':float(factor),'stock_qty':stock_qty,'stock_unit_price':price})
    quantity=sum((Decimal(str(r['stock_qty'])) for r in converted),Decimal(0))
    amount=sum((Decimal(str(r['amount'])) for r in converted),Decimal(0))
    result.update(ready=True,rows=converted,product_code=product['code'],product_name=product['name'],unit=product['unit'],
                  qty=float(quantity),amount=float(amount),unit_cost=float(amount/quantity))
    # Bind both original rows and the proposed choice to the confirmation.
    result['token']=hashlib.sha256((_fingerprint(rows)+_fingerprint(converted)).encode()).hexdigest()
    return result


def save_selection(conn, tenant, body, now):
    ids=body.get('item_ids'); token=str(body.get('token') or '')
    payload=json.dumps({'item_ids':ids,'product_code':body.get('product_code'),'factors':body.get('factors')},sort_keys=True)
    previous=conn.execute('SELECT * FROM invoice_input_group_requests WHERE token=?',(token,)).fetchone()
    if previous and previous['payload']==payload:
        group=conn.execute('SELECT * FROM invoice_input_line_groups WHERE id=? AND tenant=? AND active=1',(previous['group_id'],tenant)).fetchone()
        if group and _fingerprint(_rows(conn,ids))==group['fingerprint']:
            return {'id':group['id'],'idempotent':True}
        raise GroupError('Nhóm đã thay đổi hoặc đã tách. Hãy đọc lại bảng trước khi gộp.')
    preview=selection_preview(conn,tenant,ids,body.get('product_code'),body.get('factors'))
    if not preview['ready'] or token!=preview['token']:
        raise GroupError('Lựa chọn hoặc dữ liệu đã thay đổi. Hãy kiểm tra lại kết quả trước khi lưu.')
    mapping=_mapping_helpers()
    before=_rows(conn,ids)
    for row in preview['rows']:
        mapping._update_line_snapshot(conn,'msmi_invoice_items',row['id'],row['product_code'],'mapped',row['conversion_factor'])
        scope=f"selected-line:{row['invoice_id']}:{row['line_index']}"
        conn.execute('''INSERT INTO invoice_line_mappings(tenant,source,invoice_type,partner_key,scope_key,
            source_item_code,source_item_name,source_unit,product_code,target_unit,mapping_status,conversion_factor,confirmed_at,updated_at)
            VALUES(?,'msmi','INPUT_ELECTRONIC_INVOICE',?,?,?,?,?,?,?,'confirmed',?,?,?)
            ON CONFLICT(tenant,source,invoice_type,partner_key,scope_key,effective_from) DO UPDATE SET
            source_item_code=excluded.source_item_code,source_item_name=excluded.source_item_name,source_unit=excluded.source_unit,
            product_code=excluded.product_code,target_unit=excluded.target_unit,conversion_factor=excluded.conversion_factor,
            confirmed_at=excluded.confirmed_at,updated_at=excluded.updated_at''',
            (tenant,row['seller_tax_code'] or '',scope,row['source_item_code'] or '',row['source_item_name'],row['source_unit'],
             row['product_code'],row['product_unit'],row['conversion_factor'],now,now))
        rule=conn.execute("SELECT * FROM invoice_line_mappings WHERE tenant=? AND source='msmi' AND invoice_type='INPUT_ELECTRONIC_INVOICE' AND partner_key=? AND scope_key=? AND effective_from=''",
                          (tenant,row['seller_tax_code'] or '',scope)).fetchone()
        mapping._record_revision(conn,rule,now)
        conn.execute('INSERT OR REPLACE INTO invoice_input_group_choices VALUES(?,?,?,?,?,?,?,?)',
                     (row['invoice_id'],row['line_index'],source_fingerprint(row),row['product_code'],row['conversion_factor'],row['product_unit'],rule['id'],now))
    invoice_id=preview['rows'][0]['invoice_id']
    mapping._refresh_input_invoice(conn,invoice_id)
    mapping.refresh_linked_batches(conn,'input',{invoice_id},now)
    mapped_preview=preview_group(conn,tenant,ids)
    saved=create_group(conn,tenant,ids,mapped_preview['token'],now)
    conn.execute('INSERT INTO invoice_input_group_requests VALUES(?,?,?)',(token,saved['id'],payload))
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('invoice_group.mapping','invoice_group',?,'ok','',?,?)",
                 (str(saved['id']),json.dumps({'before':before,'after':preview['rows']},ensure_ascii=False),now))
    return saved


def restore_group_choice(conn, row):
    """Keep an explicit choice on its unchanged source line when syncing again."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='invoice_input_group_choices'").fetchone(): return False
    choice=conn.execute('SELECT c.* FROM invoice_input_group_choices c JOIN products p ON p.code=c.product_code AND p.unit=c.product_unit WHERE c.invoice_id=? AND c.line_index=?',
                        (row['invoice_id'],row['line_index'])).fetchone()
    if not choice or choice['source_fingerprint']!=source_fingerprint(row): return False
    _mapping_helpers()._update_line_snapshot(conn,'msmi_invoice_items',row['id'],choice['product_code'],'mapped',choice['conversion_factor'],clear_group_choice=False)
    return True


def selected_stock_mapping(conn, item_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='invoice_input_group_choices'").fetchone(): return None
    row=conn.execute('SELECT * FROM msmi_invoice_items WHERE id=?',(item_id,)).fetchone()
    choice=conn.execute('SELECT * FROM invoice_input_group_choices WHERE invoice_id=? AND line_index=?',(row['invoice_id'],row['line_index'])).fetchone()
    if not choice:return None
    rule=conn.execute('SELECT m.*,p.unit current_unit FROM invoice_line_mappings m JOIN products p ON p.code=m.product_code WHERE m.id=?',(choice['mapping_id'],)).fetchone()
    if not rule or choice['source_fingerprint']!=source_fingerprint(row) or rule['current_unit']!=choice['product_unit'] or rule['product_code']!=choice['product_code'] or rule['conversion_factor']!=choice['conversion_factor']:
        raise GroupError('Lựa chọn mã/quy đổi của dòng đã thay đổi; hãy kiểm tra lại trước khi nhập kho.')
    return rule


def edit_selected_conversion(conn, item_id, factor, now):
    rule=selected_stock_mapping(conn,item_id)
    if not rule:return None
    row=_rows(conn,[item_id])[0]
    mapping=_mapping_helpers()
    mapping._update_line_snapshot(conn,'msmi_invoice_items',item_id,row['product_code'],'mapped',factor,clear_group_choice=False)
    conn.execute('UPDATE invoice_line_mappings SET conversion_factor=?,confirmed_at=?,updated_at=? WHERE id=?',(factor,now,now,rule['id']))
    conn.execute('UPDATE invoice_input_group_choices SET conversion_factor=?,updated_at=? WHERE invoice_id=? AND line_index=?',(factor,now,row['invoice_id'],row['line_index']))
    updated=conn.execute('SELECT * FROM invoice_line_mappings WHERE id=?',(rule['id'],)).fetchone()
    mapping._record_revision(conn,updated,now)
    mapping._refresh_input_invoice(conn,row['invoice_id'])
    mapping.refresh_linked_batches(conn,'input',{row['invoice_id']},now)
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('invoice_group.conversion','msmi_invoice_item',?,'ok','',?,?)",
                 (str(item_id),json.dumps({'before':row['conversion_factor'],'after':factor,'mapping_id':rule['id']}),now))
    line=_rows(conn,[item_id])[0]
    return {'direction':'input','item_id':item_id,'product_code':line['product_code'],'source_unit':line['source_unit'],
            'target_unit':line['product_unit'],'conversion_factor':factor,'stock_qty':line['stock_qty'],
            'stock_unit_price':line['stock_unit_price'],'applied_lines':1,'effective_from':'','effective_to':''}


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
    @app.post('/api/invoice-workbench/input-groups/selection-preview')
    def group_selection_preview():
        body=request.get_json(silent=True) or {}
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN')
                return jsonify(ok=True,**selection_preview(conn,tenant(conn),body.get('item_ids'),body.get('product_code'),body.get('factors')))
        except GroupError as e:return jsonify(ok=False,error=str(e)),409
    @app.post('/api/invoice-workbench/input-groups/save-selection')
    def group_selection_save():
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                return jsonify(ok=True,**save_selection(conn,tenant(conn),request.get_json(silent=True) or {},ctx['now_iso']()))
        except GroupError as e:return jsonify(ok=False,error=str(e)),409
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
