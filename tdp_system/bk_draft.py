"""Prepare supplementary BK files and printouts without posting inventory."""
import io
import math
import threading
import time
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import jsonify, request, send_file
from openpyxl.styles import Alignment, Border, Font
from openpyxl.utils import get_column_letter, range_boundaries

REVIEW_PENDING = {}
REVIEW_LOCK = threading.Lock()

try:
    from .bk_import import build_bk_import_template, BK_IMPORT_SOURCE_TYPE
    from .document_preview import create_snapshot
    from .invoice_inventory import invoice_stock_rows, InvoiceInventoryError
    from .stock_tax_policy import is_kkknt
    from .contract_modules import mapping_key
except ImportError:
    from bk_import import build_bk_import_template, BK_IMPORT_SOURCE_TYPE
    from document_preview import create_snapshot
    from invoice_inventory import invoice_stock_rows, InvoiceInventoryError
    from stock_tax_policy import is_kkknt
    from contract_modules import mapping_key


def period(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError):
        raise ValueError('Chọn đủ Từ ngày và Đến ngày.') from None
    if first > last:
        raise ValueError('Từ ngày phải trước hoặc bằng Đến ngày.')
    return first.isoformat(), last.isoformat()


def suggested_prices(conn, end, codes):
    """95% of a verified selling price in the product's own unit.

    No future/draft sales, tax-inclusive totals or guessed package weights.
    The source is returned for review and the user may override the suggestion.
    """
    period(end, end)
    codes = set(codes)
    products = {r['code']: dict(r) for r in conn.execute('SELECT code,unit FROM products') if r['code'] in codes}
    result = {code: {'unit_cost': '', 'price_source': 'Chưa có giá bán đã duyệt hoặc hóa đơn đã ký cùng ĐVT; nhập đơn giá.'} for code in products}
    found = set()
    for row in conn.execute("""SELECT o.id,o.product_code,o.unit,o.sell_price,o.work_date,o.contractor,o.kitchen
        FROM orders o JOIN batches b ON b.id=o.batch_id
        WHERE b.status='approved' AND o.work_date<=? AND b.work_date<=?
        AND o.sell_price>0 AND COALESCE(o.actual_delivered,0)-COALESCE(o.customer_return_qty,0)>0
        ORDER BY o.work_date DESC,o.id DESC""", (end, end)):
        code = row['product_code']
        if code not in products or code in found or not mapping_key(row['unit']) or mapping_key(row['unit']) != mapping_key(products[code]['unit']):
            continue
        try:
            price = _number(row['sell_price'], 'Giá bán')
            cost = (price * Decimal('0.95')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except (ValueError, InvalidOperation):
            continue
        if cost <= 0:
            continue
        found.add(code)
        source = f"95% × {price:,.0f} giá bán ngày {date.fromisoformat(row['work_date']):%d/%m/%Y} · {row['contractor']} / {row['kitchen']}"
        result[code] = {'unit_cost': float(cost), 'reference_sell_price': float(price),
                        'price_order_id': row['id'], 'price_date': row['work_date'], 'price_source': source}
    # Older shortages may predate the order import. Use a signed, posted sales
    # invoice only when the code and unit match; never assume Kg equals Lit/Goi.
    for row in conn.execute("""SELECT l.id,l.product_code,l.source_unit,l.unit_price,
        i.invoice_number,i.invoice_date FROM outgoing_source_invoice_items l
        JOIN outgoing_source_invoices i ON i.id=l.invoice_id
        WHERE i.source_status_class='issued' AND i.stock_status='posted'
        AND l.mapping_status='mapped' AND l.inventory_eligible=1 AND l.conversion_factor=1
        AND i.invoice_date<=? AND l.qty>0 AND l.unit_price>0
        ORDER BY i.invoice_date DESC,i.id DESC,l.id DESC""", (end,)):
        code = row['product_code']
        if code not in products or code in found or not mapping_key(row['source_unit']) or mapping_key(row['source_unit']) != mapping_key(products[code]['unit']):
            continue
        try:
            price = _number(row['unit_price'], 'Giá bán hóa đơn')
            cost = (price * Decimal('0.95')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except (ValueError, InvalidOperation):
            continue
        if cost <= 0:
            continue
        found.add(code)
        result[code] = {'unit_cost': float(cost), 'reference_sell_price': float(price),
            'price_invoice_item_id': row['id'], 'price_date': row['invoice_date'],
            'price_source': f"95% × {price:,.2f} giá bán HĐ {row['invoice_number']} đã ký ngày {date.fromisoformat(row['invoice_date']):%d/%m/%Y}"}
    return result


def shortage_rows(conn, start, end, tax='KKKNT', day=None):
    start, end = period(start, end)
    cutoff = end
    if day:
        cutoff, _ = period(day, day)
        if not start <= cutoff <= end:
            raise ValueError('Ngày đối chiếu phải nằm trong khoảng Từ ngày – Đến ngày.')
    if tax not in ('KKKNT', 'all'):
        raise ValueError('Bộ lọc thuế không hợp lệ.')
    # Quantity projection also works when a negative item has no usable cost.
    report = invoice_stock_rows(conn, as_of=cutoff)
    products = {r['code']: dict(r) for r in conn.execute('SELECT code,name,unit,tax FROM products')}
    items = []
    for row in report:
        product = products.get(row['product_code'], {})
        if row['closing_qty'] >= -0.000001 or (tax == 'KKKNT' and not is_kkknt(product.get('tax'))):
            continue
        items.append({'product_code': row['product_code'], 'product_name': product.get('name', row['product_name']),
                      'unit': product.get('unit', row['unit']), 'tax': product.get('tax', ''),
                      'closing_qty': round(row['closing_qty'],6), 'suggested_qty': round(-row['closing_qty'],6)})
    prices = suggested_prices(conn, cutoff, [r['product_code'] for r in items])
    for item in items:
        item.update(prices.get(item['product_code'], {}))
    try:
        from .bk_purchase_sources import purchase_sources
    except ImportError:
        from bk_purchase_sources import purchase_sources
    sources, warnings = purchase_sources(conn, start, cutoff, {r['product_code'] for r in items})
    for item in items:
        item['purchase_sources'] = [r for r in sources[item['product_code']] if mapping_key(r['unit']) == mapping_key(item['unit'])]
    return {'ok': True, 'from': start, 'to': end, 'day': cutoff,
            'items': items, 'source_warnings': warnings, 'writesInventory': False}


def _number(value, label):
    if value in (None, ''):
        return None
    try:
        result = Decimal(str(value))
        if isinstance(value, bool) or not result.is_finite() or not math.isfinite(float(result)) or result <= 0 or result > Decimal('1e15'):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        raise ValueError(label + ' phải là số lớn hơn 0.') from None
    return result


def draft_rows(conn, body):
    if not isinstance(body, dict):
        raise ValueError('Dữ liệu bảng kê không hợp lệ.')
    start, end = period(body.get('from'), body.get('to'))
    raw = body.get('rows')
    if not isinstance(raw, list) or not 1 <= len(raw) <= 1000:
        raise ValueError('Chọn từ 1 đến 1.000 dòng để lập bảng kê.')
    document_date = str(body.get('document_date') or '').strip()
    if document_date:
        document_date = period(document_date, document_date)[0]
    reference = str(body.get('reference') or '').strip()[:100]
    result = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise ValueError('Dòng bảng kê không hợp lệ.')
        code = str(item.get('product_code') or '').strip().upper()
        product = conn.execute('SELECT code,name,unit FROM products WHERE code=?', (code,)).fetchone()
        if not product:
            raise ValueError(f'Dòng {index}: mã {code} chưa có trong danh mục.')
        qty, cost = _number(item.get('qty'), f'Dòng {index}: số lượng'), _number(item.get('unit_cost'), f'Dòng {index}: đơn giá')
        try:
            amount = (qty * cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if qty is not None and cost is not None else None
            if amount is not None and amount > Decimal('1e24'):
                raise InvalidOperation
        except InvalidOperation:
            raise ValueError(f'Dòng {index}: lượng hoặc giá quá lớn.') from None
        row_date = str(item.get('document_date') or document_date).strip()
        if row_date:
            row_date = period(row_date, row_date)[0]
            if not start <= row_date <= end:raise ValueError(f'Dòng {index}: Ngày mua thực tế phải nằm trong kỳ đang chọn.')
        result.append({'document_date': row_date, 'source_type': BK_IMPORT_SOURCE_TYPE,
            'source_reference': reference, 'source_line': item.get('source_line',index), 'product_code': code,
            'product_name': product['name'], 'unit': product['unit'],
            'qty': float(qty) if qty is not None else '', 'unit_cost': float(cost) if cost is not None else '',
            'amount': float(amount) if amount is not None else '',
            'source_party': str(item.get('source_party') or '').strip()[:150],
            'note': str(item.get('note') or '').strip()[:1000]})
    return start, end, result


def register_bk_draft_routes(app, ctx):
    try:
        from . import bk_supplement as supplement
        from . import bk_import as bk
        from .receipt_export import build_purchase_documents_workbook
    except ImportError:
        import bk_supplement as supplement
        import bk_import as bk
        from receipt_export import build_purchase_documents_workbook

    @app.get('/api/bk-import/draft/sellers')
    def supplement_sellers():
        with ctx['db']() as conn:
            return jsonify(ok=True,names=[r['name'] for r in conn.execute('SELECT name FROM people ORDER BY name')])

    @app.post('/api/bk-import/draft/file')
    def supplement_file():
        try:
            upload=request.files.get('file')
            if not upload or not upload.filename.lower().endswith('.xlsx'):raise ValueError('Chọn file Excel bảng kê bổ sung .xlsx.')
            blob=upload.read(bk.BK_IMPORT_MAX_BYTES+1)
            if len(blob)>bk.BK_IMPORT_MAX_BYTES:raise ValueError('File vượt giới hạn 10 MB.')
            with ctx['db']() as conn:
                parsed=bk.parse_bk_preview(conn,blob,allow_generated_rebuild=True)
            if not parsed['canConfirm']:
                raise ValueError(' | '.join('Dòng '+str(r['sourceRow'])+': '+'; '.join(r['errors']) for r in parsed['rows'] if r['errors']))
            dates={r['documentDate'] for r in parsed['rows']};refs={r['sourceReference'] for r in parsed['rows']}
            if len(refs)!=1:raise ValueError('Mỗi lần nhập bổ sung chọn một số bảng kê.')
            return jsonify(ok=True,document_date=next(iter(dates)) if len(dates)==1 else '',reference=next(iter(refs)),
                rows=[{'product_code':r['productCode'],'product_name':r['productName'],'unit':r['unit'],
                       'qty':r['qty'],'unit_cost':r['unitCost'],'source_party':r['sourceParty'],
                       'document_date':r['documentDate'],'source_line':r['sourceLine'],'note':r['note'],'selected':True} for r in parsed['rows']])
        except ValueError as exc:return jsonify(ok=False,error=str(exc)),400

    @app.post('/api/bk-import/draft/confirm')
    def supplement_confirm():
        try:
            body=request.get_json(silent=True) or {}
            if not isinstance(body,dict) or body.get('confirmed') is not True:raise ValueError('Xác nhận hàng mua thực tế và nhập kho trước khi lưu.')
            with REVIEW_LOCK:pending=REVIEW_PENDING.get(str(body.get('token') or ''))
            if not pending or pending['expires']<time.time():raise ValueError('Bản xem trước hết hạn; bấm xem và kiểm tra lại.')
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                result=supplement.post(conn,pending['prepared'],body.get('actor'),ctx['now_iso'](),ctx['audit_event'])
            return jsonify(ok=True,**result)
        except ValueError as exc:return jsonify(ok=False,error=str(exc),code=getattr(exc,'code','invalid_supplement'),stock_review=getattr(exc,'stock_review',None)),409

    @app.get('/api/bk-import/suggested-price')
    def get_suggested_price():
        try:
            code = request.args.get('product_code', '').strip().upper()
            with ctx['db']() as conn:
                conn.execute('PRAGMA query_only=ON')
                result = suggested_prices(conn, request.args.get('to'), [code])
                if code not in result:
                    raise ValueError('Mã hàng chưa có trong danh mục.')
                return jsonify(ok=True, product_code=code, **result[code])
        except ValueError as error:
            return jsonify(ok=False, error=str(error)), 400

    @app.get('/api/bk-import/shortages')
    def get_shortages():
        try:
            with ctx['db']() as conn:
                conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
                return jsonify(shortage_rows(conn, request.args.get('from'), request.args.get('to'),request.args.get('tax','KKKNT'),request.args.get('day')))
        except (ValueError, InvoiceInventoryError) as error:
            return jsonify(ok=False,error=str(error)),400

    @app.post('/api/bk-import/draft/<output>')
    def export_draft(output):
        if output not in ('excel','preview'):
            return jsonify(ok=False,error='Định dạng không hợp lệ.'),404
        try:
            with ctx['db']() as conn:
                conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
                start,end,rows=draft_rows(conn,request.get_json(silent=True))
                blob=build_bk_import_template(rows,draft=True)
                if output=='preview':
                    prepared=supplement.prepare(conn,blob,start,end)
                    workbook=build_purchase_documents_workbook(prepared['receipts'],template_path=ctx['template_path'](),
                        date_from=min(r['work_date'] for r in prepared['receipts']),
                        date_to=max(r['work_date'] for r in prepared['receipts']),
                        buyer_name=ctx['setting_get'](conn,'purchase_receipt_buyer_name',''),
                        buyer_title=ctx['setting_get'](conn,'purchase_receipt_buyer_title',''),
                        company_name=ctx['setting_get'](conn,'company',''),
                        company_address=ctx['setting_get'](conn,'company_address',''),
                        location=ctx['setting_get'](conn,'purchase_receipt_location','Hải Phòng'))
            if output=='excel':
                return send_file(io.BytesIO(blob),as_attachment=True,
                    download_name=f'BK_BO_SUNG_{start}_{end}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            try:
                for ws in workbook:
                    for line in ws:
                        for cell in line:
                            if str(cell.value or '').strip()=='Bên mua thanh toán tiền mặt ngay sau khi nhận đủ hàng':
                                cell.value='Hình thức / ngày thanh toán: ........................................'
                    left,top,right,bottom=range_boundaries(str(ws.print_area).split('!')[-1])
                    bottom+=2
                    for rr in range(bottom-1,bottom+1):
                        for cc in range(left,right+1):ws.cell(rr,cc).border=Border()
                    ws.row_dimensions[bottom-1].height=6
                    ws.cell(bottom,left,'Bảng kê bổ sung số '+rows[0]['source_reference']+' · '+('Đã ghi kho; in lại không cộng thêm kho.' if prepared['parsed']['alreadyPosted'] else 'Bản kiểm tra. Chỉ ghi kho sau khi xác nhận trên web.'))
                    ws.cell(bottom,left).data_type='s';ws.cell(bottom,left).alignment=Alignment(wrap_text=True)
                    ws.cell(bottom,left).font=Font(name='Times New Roman',size=9,italic=True)
                    ws.merge_cells(start_row=bottom,start_column=left,end_row=bottom,end_column=right)
                    ws.row_dimensions[bottom].height=32
                    ws.print_area=f'{get_column_letter(left)}{top}:{get_column_letter(right)}{bottom}'
                result=create_snapshot(ctx['data_dir']()/'document_previews',[(f'BO_BANG_KE_{start}_{end}.xlsx',workbook)])
                token=uuid.uuid4().hex
                with REVIEW_LOCK:
                    for key in list(REVIEW_PENDING):
                        if REVIEW_PENDING[key]['expires']<time.time():REVIEW_PENDING.pop(key)
                    if len(REVIEW_PENDING)>=20:raise ValueError('Có nhiều bản xem trước đang mở; thử lại sau ít phút.')
                    REVIEW_PENDING[token]={'expires':time.time()+1800,'prepared':prepared}
                return jsonify(**result,import_token=token,already_posted=prepared['parsed']['alreadyPosted'],
                    totals=prepared['parsed']['totals'],rebuild_periods=[r['period'] for r in prepared['periods']])
            finally:
                workbook.close()
        except (ValueError, InvoiceInventoryError) as error:
            return jsonify(ok=False,error=str(error)),400
