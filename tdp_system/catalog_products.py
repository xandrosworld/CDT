"""Shared catalog edits for forms and the complete editable worksheet."""
import hashlib
import json
import re

from flask import jsonify, request

SCHEMA = '''CREATE TABLE IF NOT EXISTS outgoing_product_units (
 product_code TEXT PRIMARY KEY REFERENCES products(code),
 invoice_unit TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog_worksheet_requests (
 request_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, response_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);'''
FIELDS = ('name', 'unit', 'tax', 'invoice_name', 'catalog_updated_at', 'invoice_unit')


class CatalogError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def catalog_rows(conn):
    return [dict(r) for r in conn.execute("SELECT p.code,p.name,p.unit,p.tax,p.catalog_updated_at,COALESCE(n.invoice_name,'') invoice_name,COALESCE(u.invoice_unit,'') invoice_unit FROM products p LEFT JOIN outgoing_product_names n ON n.product_code=p.code LEFT JOIN outgoing_product_units u ON u.product_code=p.code ORDER BY p.code")]


def revision(row):
    return hashlib.sha256(json.dumps([row['code'],*[row[k] for k in FIELDS]],ensure_ascii=False).encode()).hexdigest()


def worksheet_row(row):
    tax = row['tax']
    tax_label = {'0':'0%', '0.05':'5%', '0.08':'8%', '0.1':'10%'}.get(str(tax), str(tax or ''))
    return {**row,'id':row['code'],'tax':tax_label,'worksheet_revision':revision(row)}


def clear_missing_product_error(conn, code):
    for row in conn.execute("SELECT o.id,o.errors FROM orders o JOIN batches b ON b.id=o.batch_id WHERE o.product_code=? AND b.status='draft'", (code,)).fetchall():
        errors = json.loads(row['errors'] or '[]')
        remaining = [e for e in errors if e != 'Mã hàng chưa có trong danh mục: ' + code]
        if remaining != errors:
            conn.execute('UPDATE orders SET errors=? WHERE id=?', (json.dumps(remaining, ensure_ascii=False), row['id']))


def save_product(conn, body, *, editing, ctx):
    if not isinstance(body,dict): raise CatalogError('Thông tin mã hàng không hợp lệ.')
    limits={'code':64,'name':255,'unit':50,'tax':20}
    if any(not isinstance(body.get(k),str) or not body[k].strip() or len(body[k].strip())>n for k,n in limits.items()):
        raise CatalogError('Nhập đủ mã hàng, tên hàng, đơn vị và thuế; mã tối đa 64, tên 255, đơn vị 50 ký tự.')
    code=body['code'].strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]*',code):
        raise CatalogError('Mã hàng dùng chữ không dấu, số, dấu chấm, gạch ngang hoặc gạch dưới; không có khoảng trắng.')
    name=ctx['clean_text'](body['name']); unit=ctx['catalog_unit'](body['unit']); tax=ctx['catalog_tax'](body['tax'])
    invoice_name=body.get('invoice_name','')
    if not isinstance(invoice_name,str) or len(invoice_name.strip())>255:
        raise CatalogError('Tên trên hóa đơn tối đa 255 ký tự.')
    invoice_name=invoice_name.strip()
    if not name or not unit or tax not in {'KKKNT','KCT','0','0.05','0.08','0.1'}:
        raise CatalogError('Tên hàng, đơn vị hoặc lựa chọn thuế không hợp lệ.')
    current=conn.execute("SELECT p.*,COALESCE(n.invoice_name,'') invoice_name,COALESCE(u.invoice_unit,'') invoice_unit FROM products p LEFT JOIN outgoing_product_names n ON n.product_code=p.code LEFT JOIN outgoing_product_units u ON u.product_code=p.code WHERE UPPER(p.code)=?",(code,)).fetchone()
    invoice_unit=body.get('invoice_unit',current['invoice_unit'] if current else '')
    if not isinstance(invoice_unit,str) or len(invoice_unit.strip())>50:
        raise CatalogError('ĐVT xuất hóa đơn tối đa 50 ký tự.')
    invoice_unit=ctx['catalog_unit'](invoice_unit)
    if current and not editing:raise CatalogError('Mã '+code+' đã có trong danh mục. Hãy dùng mã khác; mã cũ được giữ nguyên.',409)
    expected=None
    if editing:
        if not current:raise CatalogError('Không tìm thấy mã hàng.',404)
        expected={k:current[k] for k in FIELDS}
        supplied=dict(body.get('expected') or {})
        supplied.setdefault('invoice_unit','')
        if supplied!=expected:raise CatalogError('Mã hàng đã thay đổi. Đóng và mở lại cửa sổ sửa để xem dữ liệu mới.',409)
        if ctx['catalog_unit'](current['unit'])!=unit:
            try:
                from .invoice_repairs import correct_unused_product_unit
            except ImportError:
                from invoice_repairs import correct_unused_product_unit
            try:correct_unused_product_unit(conn,code=current['code'],expected_name=current['name'],expected_unit=current['unit'],unit=unit,now=ctx['now_iso']())
            except ValueError:raise CatalogError('Mã đã được sử dụng; cần đối chiếu các đơn và kho trước khi đổi đơn vị. Có thể sửa tên hàng hoặc tên trên hóa đơn với đơn vị hiện tại.',409) from None
        else:unit=current['unit']
        code=current['code']
        if (name,unit,tax,invoice_name,invoice_unit)==(current['name'],current['unit'],current['tax'],current['invoice_name'],current['invoice_unit']):
            return {'code':code,'name':name,'unit':unit,'tax':tax}
        conn.execute('UPDATE products SET name=?,unit=?,tax=?,catalog_updated_at=? WHERE code=?',(name,unit,tax,ctx['now_iso'](),code))
    else:
        conn.execute("INSERT INTO products(code,name,unit,tax,supplier,buy_price,purchase_list,product_group,catalog_updated_at) VALUES(?,?,?,?,'',0,0,'',?)",(code,name,unit,tax,ctx['now_iso']()))
        # Clear only the now-resolved catalog error; preserve all order values
        # and unrelated validation errors. No approval or stock posting here.
        clear_missing_product_error(conn, code)
    if invoice_name:
        conn.execute('INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES(?,?,?) ON CONFLICT(product_code) DO UPDATE SET invoice_name=excluded.invoice_name,updated_at=excluded.updated_at',(code,invoice_name,ctx['now_iso']()))
    elif editing:conn.execute('DELETE FROM outgoing_product_names WHERE product_code=?',(code,))
    conn.execute('INSERT INTO outgoing_product_units VALUES(?,?,?) ON CONFLICT(product_code) DO UPDATE SET invoice_unit=excluded.invoice_unit,updated_at=excluded.updated_at',(code,invoice_unit,ctx['now_iso']()))
    try:
        from .outgoing_names import refresh_editable_names
    except ImportError:
        from outgoing_names import refresh_editable_names
    refresh_editable_names(conn,ctx['now_iso'](),[code])
    ctx['audit'](conn,ctx['now_iso'],'catalog.product_update' if editing else 'catalog.product_create','ok',entity_type='product',entity_id=code,
                 metadata={'name':name,'unit':unit,'tax':tax,'invoice_name':invoice_name,'invoice_unit':invoice_unit,'before':expected})
    return {'code':code,'name':name,'unit':unit,'tax':tax}


def register_worksheet_routes(app,ctx):
    @app.get('/api/catalog/worksheet')
    def catalog_worksheet_get():
        with ctx['db']() as conn:
            conn.execute('BEGIN')
            rows=catalog_rows(conn)
            return jsonify(ok=True,items=[worksheet_row(r) for r in rows],total=len(rows))

    @app.put('/api/catalog/worksheet')
    def catalog_worksheet_save():
        body=request.get_json(silent=True)
        if not isinstance(body,dict) or not isinstance(body.get('request_id'),str) or not 1<=len(body['request_id'])<=128:
            return jsonify(ok=False,error='Thiếu mã lần lưu. Mở lại bảng để thử lại.'),400
        changes=body.get('items')
        if not isinstance(changes,list) or not 1<=len(changes)<=5000:
            return jsonify(ok=False,error='Mỗi lần lưu cần từ 1 đến 5.000 dòng.'),400
        digest=hashlib.sha256(json.dumps(changes,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        try:
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                previous=conn.execute('SELECT * FROM catalog_worksheet_requests WHERE request_id=?',(body['request_id'],)).fetchone()
                if previous:
                    if previous['payload_hash']!=digest:raise CatalogError('Mã lần lưu đã dùng cho nội dung khác.',409)
                    return jsonify(json.loads(previous['response_json']))
                rows={r['code']:r for r in catalog_rows(conn)}
                seen=set()
                for change in changes:
                    code=change.get('id') if isinstance(change,dict) else None
                    if not isinstance(code,str) or code not in rows or code in seen:raise CatalogError('Mã hàng không tồn tại hoặc bị lặp trong lần lưu.',409)
                    seen.add(code);row=rows[code]; values=change.get('values')
                    if not isinstance(values,dict) or not values or set(values)-{'name','unit','tax','invoice_name','invoice_unit'}:
                        raise CatalogError(code+': chỉ sửa Tên hàng, ĐVT kho, Thuế, Tên và ĐVT xuất hóa đơn.')
                    if change.get('revision')!=revision(row):raise CatalogError(code+': dữ liệu đã được người khác sửa. Đọc lại / đối chiếu; phần đang nhập vẫn được giữ.',409)
                    payload={**row,**values,'expected':{k:row[k] for k in FIELDS}}
                    payload['tax']=str(payload['tax'] or '')
                    try:save_product(conn,payload,editing=True,ctx=ctx)
                    except CatalogError as error:raise CatalogError(code+': '+str(error),error.status) from None
                updated=[worksheet_row(r) for r in catalog_rows(conn) if r['code'] in seen]
                result={'ok':True,'items':updated}
                conn.execute('INSERT INTO catalog_worksheet_requests VALUES(?,?,?,?)',(body['request_id'],digest,json.dumps(result,ensure_ascii=False),ctx['now_iso']()))
                return jsonify(result)
        except CatalogError as error:return jsonify(ok=False,error=str(error)),error.status
