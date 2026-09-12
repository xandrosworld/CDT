"""Prepare supplementary BK files and printouts without posting inventory."""
import io
import math
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import jsonify, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Side, Font
from openpyxl.worksheet.page import PageMargins

try:
    from .bk_import import build_bk_import_template, BK_IMPORT_SOURCE_TYPE
    from .document_preview import create_snapshot, white_print_style
    from .invoice_inventory import invoice_stock_rows, InvoiceInventoryError
    from .stock_tax_policy import is_kkknt
except ImportError:
    from bk_import import build_bk_import_template, BK_IMPORT_SOURCE_TYPE
    from document_preview import create_snapshot, white_print_style
    from invoice_inventory import invoice_stock_rows, InvoiceInventoryError
    from stock_tax_policy import is_kkknt


def period(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError):
        raise ValueError('Chọn đủ Từ ngày và Đến ngày.') from None
    if first > last:
        raise ValueError('Từ ngày phải trước hoặc bằng Đến ngày.')
    return first.isoformat(), last.isoformat()


def shortage_rows(conn, start, end, tax='KKKNT'):
    start, end = period(start, end)
    if tax not in ('KKKNT', 'all'):
        raise ValueError('Bộ lọc thuế không hợp lệ.')
    # Quantity projection also works when a negative item has no usable cost.
    report = invoice_stock_rows(conn, as_of=end)
    products = {r['code']: dict(r) for r in conn.execute('SELECT code,name,unit,tax FROM products')}
    items = []
    for row in report:
        product = products.get(row['product_code'], {})
        if row['closing_qty'] >= -0.000001 or (tax == 'KKKNT' and not is_kkknt(product.get('tax'))):
            continue
        items.append({'product_code': row['product_code'], 'product_name': product.get('name', row['product_name']),
                      'unit': product.get('unit', row['unit']), 'tax': product.get('tax', ''),
                      'closing_qty': round(row['closing_qty'],6), 'suggested_qty': round(-row['closing_qty'],6)})
    return {'ok': True, 'from': start, 'to': end, 'items': items, 'writesInventory': False}


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
        result.append({'document_date': document_date, 'source_type': BK_IMPORT_SOURCE_TYPE,
            'source_reference': reference, 'source_line': index, 'product_code': code,
            'product_name': product['name'], 'unit': product['unit'],
            'qty': float(qty) if qty is not None else '', 'unit_cost': float(cost) if cost is not None else '',
            'amount': float(amount) if amount is not None else '',
            'source_party': str(item.get('source_party') or '').strip()[:150],
            'note': str(item.get('note') or '').strip()[:1000]})
    return start, end, result


def print_workbook(rows, start, end):
    wb = Workbook(); ws = wb.active; ws.title = 'Bảng kê bổ sung'
    ws.append(['BẢNG KÊ MUA VÀO KHÔNG CÓ HÓA ĐƠN']); ws.merge_cells('A1:H1')
    ws.append([f"Kỳ đối chiếu: {date.fromisoformat(start):%d/%m/%Y} – {date.fromisoformat(end):%d/%m/%Y}"]); ws.merge_cells('A2:H2')
    ws.append(['Số bảng kê: ' + rows[0]['source_reference'] + '    Ngày chứng từ: ' + rows[0]['document_date']]); ws.merge_cells('A3:H3')
    ws.append(['Bản lập để kiểm tra; tải và in chưa ghi nhập kho.']); ws.merge_cells('A4:H4')
    ws.append(['STT', 'Mã hàng / Tên hàng', 'ĐVT', 'Số lượng', 'Đơn giá', 'Thành tiền', 'NCC', 'Ghi chú'])
    for index, row in enumerate(rows, 1):
        ws.append([index, row['product_code'] + ' · ' + row['product_name'], row['unit'], row['qty'],
                   row['unit_cost'], row['amount'], row['source_party'], row['note']])
    total_row = ws.max_row + 1
    total = sum(Decimal(str(r['amount'])) for r in rows if r['amount'] != '')
    complete = all(r['amount'] != '' for r in rows)
    ws.append(['TỔNG', None, None, None, None, float(total) if complete else None]); ws.merge_cells(start_row=total_row,start_column=1,end_row=total_row,end_column=5)
    if any(r['amount'] == '' for r in rows):
        ws.cell(total_row, 7, 'Còn dòng chưa đủ lượng/giá')
    ws.cell(total_row+2, 7, 'Người lập bảng')
    ws.cell(total_row+5, 7, 'Vũ Thị Thụy')
    widths = [6, 40, 8, 13, 16, 18, 23, 29]
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[chr(64+i)].width = width
    border = Border(**{side: Side(style='hair',color='000000') for side in ('left','right','top','bottom')})
    for cells in ws:
        for cell in cells:
            cell.font = Font(name='Times New Roman',size=12)
            cell.alignment = Alignment(vertical='center',wrap_text=True)
            if 5 <= cell.row <= total_row:
                cell.border = border
                if cell.column in (4,5,6):
                    cell.number_format = '#,##0.######' if cell.column == 4 else '#,##0.00'
                    cell.alignment = Alignment(horizontal='right',vertical='center')
            if cell.data_type == 'f':
                cell.data_type = 's'
    for r in range(6,total_row):
        row = rows[r-6]
        lines = max((len(row['product_name'])+30)//31,(len(row['note'])+24)//25,
                    (len(row['source_party'])+17)//18,1)
        ws.row_dimensions[r].height = max(30,lines*16)
    for r in range(1,6): ws.row_dimensions[r].height=25
    ws['A1'].font=Font(name='Times New Roman',size=16)
    ws['A1'].alignment=Alignment(horizontal='center')
    ws.print_area=f'A1:H{ws.max_row}';ws.print_title_rows='1:5';ws.sheet_view.showGridLines=False
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0;ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_margins=PageMargins(left=.25,right=.25,top=.3,bottom=.3)
    return white_print_style(wb)


def register_bk_draft_routes(app, ctx):
    @app.get('/api/bk-import/shortages')
    def get_shortages():
        try:
            with ctx['db']() as conn:
                conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
                return jsonify(shortage_rows(conn, request.args.get('from'), request.args.get('to'),request.args.get('tax','KKKNT')))
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
            if output=='excel':
                return send_file(io.BytesIO(build_bk_import_template(rows, draft=True)),as_attachment=True,
                    download_name=f'BK_BO_SUNG_{start}_{end}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            workbook=print_workbook(rows,start,end)
            try:
                return jsonify(create_snapshot(ctx['data_dir']()/'document_previews',[(f'BK_BO_SUNG_{start}_{end}.xlsx',workbook)]))
            finally:
                workbook.close()
        except (ValueError, InvoiceInventoryError) as error:
            return jsonify(ok=False,error=str(error)),400
