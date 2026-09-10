"""Explicit, source-preserving allocation of input invoice discounts."""
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_DOWN


class DiscountError(ValueError):
    pass


def init_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS invoice_input_discounts (
        invoice_id INTEGER PRIMARY KEY REFERENCES msmi_invoices(id),
        source_hash TEXT NOT NULL, allocations TEXT NOT NULL,
        actor TEXT NOT NULL, updated_at TEXT NOT NULL)''')


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def _number(value):
    try:
        n=Decimal(str(value))
        if not n.is_finite(): raise ValueError()
        return n
    except (ValueError,TypeError,InvalidOperation):
        raise DiscountError('Số tiền không hợp lệ.') from None


def _saved(conn, invoice_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='invoice_input_discounts'").fetchone(): return None
    r=conn.execute('SELECT * FROM invoice_input_discounts WHERE invoice_id=?',(invoice_id,)).fetchone()
    return dict(r) if r else None


def _context(conn, invoice_id):
    header=conn.execute('SELECT * FROM msmi_invoices WHERE id=?',(invoice_id,)).fetchone()
    if not header or header['invoice_type']!='INPUT_ELECTRONIC_INVOICE':
        raise DiscountError('Không tìm thấy hóa đơn đầu vào.')
    h=dict(header)
    rows=[dict(r) for r in conn.execute('SELECT * FROM msmi_invoice_items WHERE invoice_id=? ORDER BY line_index,id',(invoice_id,))]
    try: raw=json.loads(h['raw_json'] or '{}')
    except (ValueError,TypeError): raise DiscountError('Không đọc được tổng tiền hóa đơn nguồn.') from None
    if not isinstance(raw,dict): raise DiscountError('Không đọc được tổng tiền hóa đơn nguồn.')
    fields=('id','line_index','source_item_code','source_item_name','source_unit','qty','unit_price','amount','source_nature','inventory_eligible','product_code','conversion_factor','stock_qty')
    fingerprint=_hash([h['raw_json'],h['invoice_date'],h['seller_tax_code'],[{k:r.get(k) for k in fields} for r in rows]])
    gross=sum((_number(r['amount']) for r in rows if str(r['source_nature'])!='3' and _number(r['amount'])>=0),Decimal(0))
    discount_lines=sum((abs(_number(r['amount'])) for r in rows if str(r['source_nature'])=='3' or _number(r['amount'])<0),Decimal(0))
    header_discount=_number(raw.get('ttcktmai') or 0)
    has_discount=bool(discount_lines or header_discount)
    net=raw.get('tgtcthue',raw.get('subtotal',raw.get('totalBeforeTax')))
    total=raw.get('tgtttbso',raw.get('totalAmount',raw.get('total')))
    tax=raw.get('tgtthue',raw.get('taxAmount',raw.get('tax')))
    if total is not None and tax is not None: net=_number(total)-_number(tax)
    net=None if net is None else _number(net)
    error=''
    discount=Decimal(0)
    if has_discount:
        if net is None: error='Thiếu tổng tiền chưa thuế để xác định chiết khấu. Cần đối chiếu nguồn hóa đơn.'
        elif abs(gross-net)<=Decimal(1): pass  # Already net on source lines; do not subtract again.
        elif net<0 or net>gross: error='Tổng tiền có điều chỉnh khác chiết khấu giảm giá; cần đối chiếu nguồn.'
        else:
            discount=gross-net
            if not any(abs(discount-v)<=Decimal(1) for v in (discount_lines,abs(header_discount)) if v):
                error='Chênh lệch tổng tiền không khớp số chiết khấu nguồn. Cần đối chiếu hóa đơn trước khi phân bổ.'
    goods=[r for r in rows if r['inventory_eligible'] and _number(r['qty'])>0 and str(r['source_nature']) not in ('3','4')]
    return h,goods,fingerprint,gross,net,discount,error,has_discount


def _validated(goods, discount, amounts):
    if not isinstance(amounts,list): raise DiscountError('Cần danh sách tiền chiết khấu từng dòng.')
    allowed={r['id']:r for r in goods};result={};total=Decimal(0)
    for item in amounts:
        if not isinstance(item,dict): raise DiscountError('Dòng phân bổ không hợp lệ.')
        key=item.get('item_id')
        if type(key) is not int or key not in allowed or key in result: raise DiscountError('Dòng phân bổ trùng hoặc không thuộc hàng nhập kho của hóa đơn.')
        value=_number(item.get('discount'))
        if value<0 or value>_number(allowed[key]['amount']) or value!=value.quantize(Decimal('.01')):
            raise DiscountError(f"Dòng {allowed[key]['line_index']}: chiết khấu phải từ 0 đến tiền hàng, tối đa 2 số lẻ.")
        result[key]=value;total+=value
    if total!=discount: raise DiscountError(f'Tổng phân bổ {total:,.2f} đ chưa bằng chiết khấu {discount:,.2f} đ.')
    return result


def _auto(goods, discount, selected):
    if selected is not None and (not isinstance(selected,list) or any(type(k) is not int for k in selected) or len(set(selected))!=len(selected)):
        raise DiscountError('Danh sách dòng hưởng chiết khấu không hợp lệ.')
    allowed={r['id'] for r in goods}
    if selected is not None and any(k not in allowed for k in selected): raise DiscountError('Dòng chọn không thuộc hàng nhập của hóa đơn.')
    eligible=[r for r in goods if _number(r['amount'])>0 and (selected is None or r['id'] in selected)]
    total=sum((_number(r['amount']) for r in eligible),Decimal(0))
    if total<discount or total<=0: raise DiscountError('Tiền hàng đã chọn không đủ để phân bổ chiết khấu.')
    quantum=Decimal(1) if discount==discount.to_integral_value() and all(_number(r['amount'])==_number(r['amount']).to_integral_value() for r in eligible) else Decimal('.01')
    shares={r['id']:discount*_number(r['amount'])/total for r in eligible}
    result={k:(v/quantum).to_integral_value(rounding=ROUND_DOWN)*quantum for k,v in shares.items()}
    remainder=int((discount-sum(result.values()))/quantum)
    for key in sorted(shares,key=lambda k:(-(shares[k]-result[k]),k))[:remainder]: result[key]+=quantum
    return [{'item_id':r['id'],'discount':str(result.get(r['id'],0))} for r in goods]


def state(conn, invoice_id):
    h,goods,fingerprint,gross,net,discount,error,has_discount=_context(conn,invoice_id)
    saved=_saved(conn,invoice_id);values={};valid=False
    if saved and saved['source_hash']==fingerprint and not error:
        try:
            values=_validated(goods,discount,json.loads(saved['allocations']));valid=True
        except (ValueError,TypeError): pass
    return {'header':h,'goods':goods,'source_hash':fingerprint,'gross':gross,'net':net,'discount':discount,
            'error':error,'has_discount':has_discount,'saved':saved,'valid':valid,'values':values}


def preview(conn, invoice_id, *, selected=None, amounts=None):
    s=state(conn,invoice_id);h=s['header'];error=s['error']
    proposed=s['values'] if s['valid'] and selected is None and amounts is None else {}
    if not error and s['discount']>0 and not proposed:
        try: proposed=_validated(s['goods'],s['discount'],amounts if amounts is not None else _auto(s['goods'],s['discount'],selected))
        except DiscountError as exc: error=str(exc)
    editable=h['receipt_status']!='posted' and h['sync_status']=='synced' and h['receipt_status'] not in ('reversed','reversal_required')
    lines=[]
    for r in s['goods']:
        deduction=proposed.get(r['id'],Decimal(0));amount=_number(r['amount'])-deduction;qty=_number(r['stock_qty'] or 0)
        lines.append({'item_id':r['id'],'line_index':r['line_index'],'name':r['source_item_name'],'product_code':r['product_code'],
                      'source_qty':r['qty'],'source_unit':r['source_unit'],'stock_qty':float(qty),
                      'amount':r['amount'],'discount':float(deduction),'net_amount':float(amount),
                      'net_unit_cost':float(amount/qty) if qty>0 else None})
    return {'invoice_id':invoice_id,'invoice_series':h['invoice_series'],'invoice_number':h['invoice_number'],
            'gross':float(s['gross']),'net':None if s['net'] is None else float(s['net']),'discount':float(s['discount']),
            'lines':lines,'error':error,'saved':s['valid'],'stale':bool(s['saved'] and not s['valid']),
            'can_save':editable and s['discount']>0 and not error,'editable':editable,
            'token':_hash([s['source_hash'],s['saved'],h['receipt_status'],h['sync_status']])}


def save(conn, invoice_id, body, timestamp):
    current=preview(conn,invoice_id)
    if body.get('expected_token')!=current['token']: raise DiscountError('Dữ liệu hoặc phân bổ đã thay đổi. Mở lại bảng phân bổ để kiểm tra.')
    if not current['editable']: raise DiscountError('Hóa đơn đã ghi kho hoặc đang cần đối chiếu; không được sửa phân bổ.')
    actor=str(body.get('actor') or '').strip()
    if not actor or len(actor)>100: raise DiscountError('Nhập người xác nhận, tối đa 100 ký tự.')
    s=state(conn,invoice_id)
    if s['error'] or s['discount']<=0: raise DiscountError(s['error'] or 'Hóa đơn không còn chiết khấu cần phân bổ.')
    amounts=_validated(s['goods'],s['discount'],body.get('amounts'))
    data=json.dumps([{'item_id':k,'discount':str(v)} for k,v in sorted(amounts.items())],ensure_ascii=False)
    init_schema(conn)
    conn.execute('''INSERT INTO invoice_input_discounts VALUES(?,?,?,?,?) ON CONFLICT(invoice_id) DO UPDATE SET
        source_hash=excluded.source_hash,allocations=excluded.allocations,actor=excluded.actor,updated_at=excluded.updated_at''',
        (invoice_id,s['source_hash'],data,actor,timestamp))
    conn.execute('''INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('invoice_input.discount','msmi_invoice',?,'ok','Phân bổ chiết khấu vào giá nhập',?,?)''',
        (str(invoice_id),json.dumps({'actor':actor,'discount':str(s['discount']),'amounts':json.loads(data)},ensure_ascii=False),timestamp))
    return preview(conn,invoice_id)


def allocated_amount(conn, invoice_id, item_id, source_amount):
    if not _saved(conn,invoice_id): return float(source_amount)
    s=state(conn,invoice_id)
    if not s['valid']: raise DiscountError('Phân bổ chiết khấu đã cũ. Mở Phân bổ chiết khấu để xác nhận lại.')
    return float(_number(source_amount)-s['values'].get(item_id,Decimal(0)))


def annotate(conn, invoice):
    s=state(conn,invoice['id'])
    invoice['discount_available']=s['has_discount'] or bool(s['saved'])
    invoice['discount_allocated']=s['valid']
    invoice['discount_amount']=float(s['discount'])
    invoice['discount_net_total']=None if s['net'] is None else float(s['net'])
    for r in invoice['items']:
        if s['valid']:
            r['allocated_discount']=float(s['values'].get(r['id'],Decimal(0)))
            r['stock_amount']=float(_number(r['amount'])-s['values'].get(r['id'],Decimal(0)))


def register_routes(app,ctx):
    from flask import request,jsonify
    @app.route('/api/invoice-workbench/input-discount/<int:invoice_id>',methods=['GET','POST','PUT'])
    def discount_route(invoice_id):
        try:
            with ctx['db']() as conn:
                if request.method=='PUT': conn.execute('BEGIN IMMEDIATE')
                tenant=ctx['setting_get'](conn,'tenant_code','TDP')
                h=conn.execute('SELECT invoice_type FROM msmi_invoices WHERE id=? AND tenant=?',(invoice_id,tenant)).fetchone()
                if not h: raise DiscountError('Không tìm thấy hóa đơn.')
                body=request.get_json(silent=True) or {}
                if not isinstance(body,dict): raise DiscountError('Yêu cầu phân bổ không hợp lệ.')
                result=save(conn,invoice_id,body,ctx['now_iso']()) if request.method=='PUT' else preview(conn,invoice_id,selected=body.get('selected'),amounts=body.get('amounts'))
            return jsonify(ok=True,**result)
        except (DiscountError,InvalidOperation) as exc: return jsonify(ok=False,error=str(exc)),409
