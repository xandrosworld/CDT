"""Reviewed, transactional correction of posted input quantity and cost."""
import calendar
import hashlib
import json
import math
import sqlite3
from decimal import Decimal

from . import invoice_mapping as mapping
from .invoice_line_groups import source_fingerprint
from .invoice_monthly_valuation import monthly_average_report
from .invoice_valuation import moving_average_report
from .input_discount import _saved, state as discount_state, _context as discount_context


class ConversionError(ValueError):
    pass


def init_schema(c):
    c.execute('''CREATE TABLE IF NOT EXISTS input_conversion_corrections (
        id INTEGER PRIMARY KEY, request_token TEXT NOT NULL UNIQUE, item_id INTEGER NOT NULL,
        actor TEXT NOT NULL, reason TEXT NOT NULL, journal TEXT NOT NULL, created_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS input_conversion_preferences (
        tenant TEXT, partner TEXT, source_code TEXT, source_name TEXT, source_unit TEXT,
        product_code TEXT, target_unit TEXT, factor REAL NOT NULL, from_date TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(tenant,partner,source_code,source_name,source_unit,product_code))''')


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def rows(c,sql,args=()):
    return [dict(r) for r in c.execute(sql,args)]


def table_exists(c,name):
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())


def factor_number(value):
    try:
        result=float(value)
        if isinstance(value,bool) or not math.isfinite(result) or not 0 < result <= 1e9: raise ValueError()
        return result
    except (TypeError,ValueError,OverflowError):
        raise ConversionError('Hệ số quy đổi phải là số lớn hơn 0.') from None


def set_choice(c,row,factor,now):
    product=mapping._product(c,row['product_code'])
    scope=f"selected-line:{row['invoice_id']}:{row['line_index']}"
    c.execute('''INSERT INTO invoice_line_mappings(tenant,source,invoice_type,partner_key,scope_key,
        source_item_code,source_item_name,source_unit,product_code,target_unit,mapping_status,
        conversion_factor,confirmed_at,updated_at)
        VALUES(?,'msmi','INPUT_ELECTRONIC_INVOICE',?,?,?,?,?,?,?,'confirmed',?,?,?)
        ON CONFLICT(tenant,source,invoice_type,partner_key,scope_key,effective_from) DO UPDATE SET
        product_code=excluded.product_code,target_unit=excluded.target_unit,mapping_status='confirmed',
        conversion_factor=excluded.conversion_factor,confirmed_at=excluded.confirmed_at,updated_at=excluded.updated_at''',
        (row['tenant'],row['partner_key'],scope,row['source_item_code'] or '',row['source_item_name'],row['source_unit'],
         row['product_code'],product['unit'],factor,now,now))
    rule=c.execute("SELECT * FROM invoice_line_mappings WHERE tenant=? AND source='msmi' AND invoice_type='INPUT_ELECTRONIC_INVOICE' AND partner_key=? AND scope_key=? AND effective_from=''",
                   (row['tenant'],row['partner_key'],scope)).fetchone()
    mapping._record_revision(c,rule,now)
    mapping._update_line_snapshot(c,'msmi_invoice_items',row['id'],row['product_code'],'mapped',factor)
    c.execute('INSERT OR REPLACE INTO invoice_input_group_choices VALUES(?,?,?,?,?,?,?,?)',
              (row['invoice_id'],row['line_index'],source_fingerprint(row),row['product_code'],factor,product['unit'],rule['id'],now))


def apply_preference(c,item_id):
    """Only previously unmapped new lines; never rewrite existing or posted rows."""
    if not table_exists(c,'input_conversion_preferences'): return False
    row=mapping._line_context(c,'input',item_id)
    if not row or row['parent_status'] in ('posted','blocked','reversed','reversal_required') or row['parent_sync_status']!='synced' or row['mapping_status']!='unmapped' or row['product_code']:
        return False
    row=dict(row)
    prefs=rows(c,'''SELECT f.* FROM input_conversion_preferences f JOIN products p ON p.code=f.product_code
        WHERE f.tenant=? AND f.partner=? AND f.source_code=? AND f.source_name=? AND f.source_unit=?
        AND f.from_date<=? AND p.unit=f.target_unit''',
        (row['tenant'],row['partner_key'],row['source_item_code'] or '',row['source_item_name'],row['source_unit'],row['invoice_date']))
    if len(prefs)!=1: return False
    pref=prefs[0];row['product_code']=pref['product_code']
    set_choice(c,row,pref['factor'],pref['updated_at'])
    return True


def context(c,item_id,tenant):
    row=mapping._line_context(c,'input',item_id)
    if not row or row['tenant']!=tenant: raise ConversionError('Không tìm thấy dòng hóa đơn trong dữ liệu đang dùng.')
    row=dict(row)
    if row['parent_status']!='posted' or row['parent_sync_status']!='synced' or not row['inventory_eligible']:
        raise ConversionError('Chỉ sửa quy đổi của dòng hàng đã nhập kho, nguồn hóa đơn chưa thay đổi.')
    invoice=dict(c.execute('SELECT * FROM msmi_invoices WHERE id=?',(row['invoice_id'],)).fetchone())
    if table_exists(c,'inventory_period_closures') and c.execute("SELECT 1 FROM inventory_period_closures WHERE period>=? AND status='closed'",(row['invoice_date'][:7],)).fetchone():
        raise ConversionError('Tháng này hoặc kỳ sau đã chốt. Mở lại kỳ kho liên quan trước khi sửa quy đổi.')
    if c.execute("SELECT 1 FROM inventory_transactions WHERE source_type='OPENING' AND status='posted' AND txn_date>?",(row['invoice_date'],)).fetchone():
        raise ConversionError('Đã chuyển tồn sang kỳ sau. Mở lại kỳ kho liên quan trước khi sửa quy đổi.')
    old=mapping.validated_input_stock_snapshot(c,item_id)
    events=rows(c,"SELECT * FROM invoice_inventory_ledger WHERE source_invoice_table='msmi_invoices' AND source_invoice_id=? AND source_line_id=?",(row['invoice_id'],item_id))
    txns=rows(c,"SELECT * FROM inventory_transactions WHERE source_type='MSMI_INPUT' AND source_id=? AND source_line=?",(invoice['remote_id'],str(row['line_index'])))
    if len(events)!=1 or len(txns)!=1: raise ConversionError('Sổ nhập không còn duy nhất; cần đối chiếu trước khi sửa.')
    event,txn=events[0],txns[0]
    revision_fields=('mapping_id','product_code','source_unit','target_unit','conversion_factor','effective_from','effective_to')
    stored=c.execute('SELECT * FROM invoice_mapping_revisions WHERE id=?',(event['mapping_revision_id'],)).fetchone()
    current=c.execute('SELECT * FROM invoice_mapping_revisions WHERE id=?',(old['mapping_revision_id'],)).fetchone()
    if not stored or not current or any(stored[k]!=current[k] for k in revision_fields):
        raise ConversionError('Lịch sử quy đổi không khớp bút toán; cần đối chiếu trước khi sửa.')
    if event['status']!='posted' or event['event_type']!='POST' or event['direction']!='input' or txn['status']!='posted' or txn['qty_out']!=0:
        raise ConversionError('Bút toán nhập đã thay đổi; tải lại dữ liệu trước khi sửa.')
    for r,qty in ((event,'qty_delta'),(txn,'qty_in')):
        if r['product_code']!=old['product_code'] or r['txn_date']!=row['invoice_date'] or not math.isclose(r[qty],old['stock_qty'],rel_tol=0,abs_tol=1e-6) or not math.isclose(r['unit_cost'],old['stock_unit_price'],rel_tol=0,abs_tol=1e-6):
            raise ConversionError('Lượng hoặc giá trên sổ không khớp quy đổi đã lưu; dừng sửa.')
    first=row['invoice_date'][:7]+'-01'
    downstream=rows(c,"SELECT * FROM invoice_inventory_effective_ledger WHERE product_code=? AND txn_date>=? ORDER BY txn_date,id",(old['product_code'],first))
    last=max([row['invoice_date']]+[r['txn_date'] for r in downstream])
    raw_source=[invoice['raw_json'],[{k:r[k] for k in ('id','source_item_code','source_item_name','source_unit','qty','unit_price','amount','tax_rate')} for r in rows(c,'SELECT * FROM msmi_invoice_items WHERE invoice_id=? ORDER BY id',(row['invoice_id'],))]]
    token=digest([row,invoice,old,event,txn,downstream,_saved(c,row['invoice_id']),rows(c,"SELECT * FROM inventory_transactions WHERE source_type='OPENING' AND product_code=?",(old['product_code'],))])
    return dict(row=row,invoice=invoice,old=old,event=event,txn=txn,first=first,last=last,source=raw_source,token=token)


def monthly(c,code,day):
    year,month=map(int,day[:7].split('-'));end=f'{year:04}-{month:02}-{calendar.monthrange(year,month)[1]}'
    report=monthly_average_report(c,date_from=day[:7]+'-01',date_to=end,include_zero=True)
    return next(r for r in report['items'] if r['product_code']==code)


def mutate(c,s,factor,now):
    row=s['row'];before_discount=discount_state(c,row['invoice_id']) if _saved(c,row['invoice_id']) else None
    if before_discount and not before_discount['valid']: raise ConversionError('Phân bổ chiết khấu không còn khớp; cần đối chiếu trước khi sửa quy đổi.')
    set_choice(c,row,factor,now)
    if before_discount:
        # Only quantity conversion changed; the reviewed monetary allocation stays identical.
        fingerprint=discount_context(c,row['invoice_id'])[2]
        c.execute('UPDATE invoice_input_discounts SET source_hash=? WHERE invoice_id=?',(fingerprint,row['invoice_id']))
    new=mapping.validated_input_stock_snapshot(c,row['id'])
    if not math.isclose(new['amount'],s['old']['amount'],rel_tol=0,abs_tol=.000001): raise ConversionError('Tiền nhập thay đổi ngoài quy đổi; dừng sửa.')
    c.execute('UPDATE invoice_inventory_ledger SET qty_delta=?,unit_cost=?,mapping_revision_id=? WHERE id=?',
              (new['stock_qty'],new['stock_unit_price'],new['mapping_revision_id'],s['event']['id']))
    c.execute('UPDATE inventory_transactions SET qty_in=?,unit_cost=?,updated_at=? WHERE id=?',
              (new['stock_qty'],new['stock_unit_price'],now,s['txn']['id']))
    # Group membership is display-only; a changed conversion invalidates its old fingerprint.
    if table_exists(c,'invoice_input_line_groups'):
        from .invoice_line_groups import _fingerprint,_rows
        for g in rows(c,'SELECT * FROM invoice_input_line_groups WHERE invoice_id=? AND active=1',(row['invoice_id'],)):
            indices=json.loads(g['member_indices'])
            if row['line_index'] in indices:
                ids=[r['id'] for r in rows(c,'SELECT id,line_index FROM msmi_invoice_items WHERE invoice_id=?',(row['invoice_id'],)) if r['line_index'] in indices]
                c.execute('UPDATE invoice_input_line_groups SET fingerprint=?,updated_at=? WHERE id=?',(_fingerprint(_rows(c,ids)),now,g['id']))
    return new


def preview(c,item_id,tenant,factor=None):
    s=context(c,item_id,tenant);row=s['row'];factor=factor_number(s['old']['conversion_factor'] if factor is None else factor)
    new_qty=float(Decimal(str(row['qty']))*Decimal(str(factor)))
    if not math.isfinite(new_qty) or new_qty<=0 or abs(new_qty-round(new_qty,6))>1e-7:
        raise ConversionError('Lượng kho phải lớn hơn 0 và tối đa 6 số lẻ.')
    before=monthly(c,row['product_code'],row['invoice_date'])
    c.execute('SAVEPOINT preview_conversion')
    try:
        new=mutate(c,s,factor,'preview')
        after=monthly(c,row['product_code'],row['invoice_date'])
        report=moving_average_report(c,date_from=s['first'],date_to=s['last'],include_zero=True,include_events=True)
        repriced=[r for r in report['events'] if r['product_code']==row['product_code'] and r['movement'] in ('output','reversal')]
    finally:
        c.execute('ROLLBACK TO preview_conversion');c.execute('RELEASE preview_conversion')
    return {'ok':True,'item_id':item_id,'token':s['token'],'invoice':s['invoice']['invoice_series']+' / '+s['invoice']['invoice_number'],
            'date':row['invoice_date'],'name':row['source_item_name'],'code':row['product_code'],
            'source_qty':row['qty'],'source_unit':row['source_unit'],'unit':mapping._product(c,row['product_code'])['unit'],
            'old_factor':s['old']['conversion_factor'],'factor':factor,'old_qty':s['old']['stock_qty'],'qty':new['stock_qty'],
            'amount':new['amount'],'old_unit_cost':s['old']['stock_unit_price'],'unit_cost':new['stock_unit_price'],
            'before':before,'after':after,'output_events':len(repriced),'changed':factor!=s['old']['conversion_factor']}


def save(c,item_id,tenant,body,now):
    if not c.in_transaction: raise ConversionError('Cần giao dịch để sửa quy đổi đã nhập.')
    factor=factor_number(body.get('factor'));actor=str(body.get('actor') or '').strip();reason=str(body.get('reason') or '').strip()
    if not actor or len(actor)>100 or not reason or len(reason)>500: raise ConversionError('Nhập người xác nhận (tối đa 100 ký tự) và lý do (tối đa 500 ký tự).')
    if body.get('confirmed') is not True: raise ConversionError('Kiểm tra lượng và giá mới rồi xác nhận sửa.')
    remember=body.get('remember') is True
    payload=digest([item_id,tenant,factor,actor,reason,remember,body.get('token')])
    previous=c.execute('SELECT journal FROM input_conversion_corrections WHERE request_token=?',(payload,)).fetchone()
    if previous: return {**json.loads(previous[0])['result'],'idempotent':True}
    p=preview(c,item_id,tenant,factor)
    if p['token']!=body.get('token'): raise ConversionError('Dữ liệu kho đã thay đổi sau khi xem. Bấm Kiểm tra thay đổi lại trước khi lưu.')
    if not p['changed']: raise ConversionError('Hệ số mới chưa thay đổi.')
    s=context(c,item_id,tenant)
    c.execute('SAVEPOINT save_conversion_repair')
    try:
        new=mutate(c,s,factor,now)
        row=s['row']
        if remember:
            c.execute('''INSERT INTO input_conversion_preferences VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant,partner,source_code,source_name,source_unit,product_code) DO UPDATE SET
                target_unit=excluded.target_unit,factor=excluded.factor,from_date=excluded.from_date,updated_at=excluded.updated_at''',
                (tenant,row['partner_key'],row['source_item_code'] or '',row['source_item_name'],row['source_unit'],row['product_code'],p['unit'],factor,row['invoice_date'],now))
        # Reports derive dependent output costs from the corrected receipt. The journal records that impact.
        result={**p,'ok':True,'saved':True,'actor':actor,'reason':reason,'remember':remember}
        journal={'before':s,'after':new,'result':result,'discount_after':_saved(c,row['invoice_id'])}
        if context(c,item_id,tenant)['source']!=s['source']: raise ConversionError('Nguồn hóa đơn thay đổi; dừng sửa.')
        data=json.dumps(journal,ensure_ascii=False,sort_keys=True)
        c.execute('INSERT INTO input_conversion_corrections(request_token,item_id,actor,reason,journal,created_at) VALUES(?,?,?,?,?,?)',(payload,item_id,actor,reason,data,now))
        c.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('invoice_input.posted_conversion','msmi_invoice_item',?,'ok','Sửa quy đổi đã nhập kho',?,?)",(str(item_id),data,now))
        c.execute('RELEASE save_conversion_repair')
        return result
    except Exception:
        c.execute('ROLLBACK TO save_conversion_repair');c.execute('RELEASE save_conversion_repair');raise


def register_routes(app,ctx):
    from flask import request,jsonify
    @app.route('/api/invoice-workbench/input-conversion-repair/<int:item_id>',methods=['GET','POST','PUT'])
    def repair_conversion(item_id):
        try:
            with ctx['db']() as c:
                tenant=ctx['setting_get'](c,'tenant_code','TDP')
                body=request.get_json(silent=True) or {}
                if not isinstance(body,dict): raise ConversionError('Yêu cầu không hợp lệ.')
                if request.method=='PUT':
                    c.execute('BEGIN IMMEDIATE');result=save(c,item_id,tenant,body,ctx['now_iso']())
                else:
                    # Simulate only on a private database, never modifying live inventory during review.
                    copy=sqlite3.connect(':memory:');copy.row_factory=sqlite3.Row
                    try:
                        c.backup(copy);result=preview(copy,item_id,tenant,body.get('factor'))
                    finally: copy.close()
                result['history']=[{'actor':r['actor'],'reason':r['reason'],'created_at':r['created_at'],'before':json.loads(r['journal'])['result']['old_qty'],'after':json.loads(r['journal'])['result']['qty']} for r in rows(c,'SELECT * FROM input_conversion_corrections WHERE item_id=? ORDER BY id DESC LIMIT 20',(item_id,))]
                return jsonify(result)
        except (ValueError,sqlite3.IntegrityError) as exc: return jsonify(ok=False,error=str(exc)),409
