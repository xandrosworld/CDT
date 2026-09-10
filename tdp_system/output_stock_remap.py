"""Excel round trip for internal inventory codes; issued invoice fields are immutable."""
import hashlib
import io
import json
import sqlite3
import time
import uuid
import zipfile
from collections import defaultdict
from decimal import Decimal

from flask import jsonify, request, send_file
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.views import Selection
from xml.etree.ElementTree import ParseError

try:
    from .invoice_monthly_valuation import monthly_average_report
    from .stock_tax_policy import kkknt_codes
    from .invoice_line_tax import annotate_invoice_tax
    from .invoice_output_editing import output_amount_review
    from .invoice_inventory import _minimum_balance_from
    from .inventory_tax_review import compare_tax, display_tax, format_review_sheet
except ImportError:
    from invoice_monthly_valuation import monthly_average_report
    from stock_tax_policy import kkknt_codes
    from invoice_line_tax import annotate_invoice_tax
    from invoice_output_editing import output_amount_review
    from invoice_inventory import _minimum_balance_from
    from inventory_tax_review import compare_tax, display_tax, format_review_sheet

HEADERS = ['ID dòng kho', 'Ngày', 'Ký hiệu / Số HĐ', 'Mã trên HĐ', 'Tên trên HĐ',
           'ĐVT trên HĐ', 'Số lượng HĐ', 'Đơn giá bán', 'Tiền hàng', 'Thuế suất',
           'Tiền thuế', 'Mã nội bộ hiện tại', 'Tên nội bộ hiện tại', 'ĐVT kho',
           'Lượng trừ kho', 'Tồn cuối kỳ', 'Mã nội bộ mới', 'Tên nội bộ mới']
# Keep the original layout readable for files already being edited by customers.
NEW_HEADERS = ['Mã hàng muốn chuyển sang', 'Tên hàng muốn chuyển sang',
               'Mã nội bộ đang trừ kho', 'Tên hàng đang trừ kho', 'Lượng chuyển',
               'ĐVT kho', 'Tồn cuối kỳ', 'Ngày hóa đơn', 'Ký hiệu / Số HĐ',
               'Mã trên hóa đơn gốc (có thể trống)', 'Tên trên hóa đơn gốc',
               'ĐVT trên HĐ', 'Số lượng HĐ', 'Đơn giá bán', 'Tiền hàng',
               'Thuế suất', 'Tiền thuế', 'ID dòng kho']
NEW_COLUMN_ORDER = (16, 17, 11, 12, 14, 13, 15, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0)
SCHEMA = '''
CREATE TABLE IF NOT EXISTS output_stock_remaps (
    ledger_id INTEGER PRIMARY KEY REFERENCES invoice_inventory_ledger(id),
    product_code TEXT NOT NULL REFERENCES products(code),
    revision INTEGER NOT NULL, updated_at TEXT NOT NULL, unit_cost REAL
);
CREATE TABLE IF NOT EXISTS output_stock_excel_sessions (
    token TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
    created REAL NOT NULL, result TEXT
);
CREATE TABLE IF NOT EXISTS output_stock_remap_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ledger_id INTEGER NOT NULL REFERENCES invoice_inventory_ledger(id),
    product_code TEXT NOT NULL REFERENCES products(code),
    qty REAL NOT NULL CHECK(qty >= 0), unit_cost REAL NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE(ledger_id, product_code)
);
'''


def init_schema(conn):
    conn.executescript(SCHEMA)
    if 'unit_cost' not in {r['name'] for r in conn.execute('PRAGMA table_info(output_stock_remaps)')}:
        conn.execute('ALTER TABLE output_stock_remaps ADD COLUMN unit_cost REAL')
    columns = [r['name'] for r in conn.execute('PRAGMA table_info(invoice_inventory_ledger)')]
    select = ','.join(f'COALESCE(m.{col},l.{col}) AS {col}'
                      if col in {'product_code','unit_cost'} else 'l.' + col for col in columns)
    conn.execute('DROP VIEW IF EXISTS invoice_inventory_effective_ledger')
    conn.execute('DROP VIEW IF EXISTS invoice_inventory_remap_base_ledger')
    conn.execute('CREATE VIEW invoice_inventory_remap_base_ledger AS SELECT ' + select +
                 ' FROM invoice_inventory_ledger l LEFT JOIN output_stock_remaps m ON m.ledger_id=l.id')
    # A partial transfer partitions the original stock event without changing
    # the invoice or append-only ledger. A later full reversal uses the same
    # partition, with distinct event keys so valuation restores each component.
    expressions = {
        'id': '-2*p.id-CASE WHEN l.event_type=\'REVERSAL\' THEN 1 ELSE 0 END',
        'product_code': 'p.product_code',
        'qty_delta': "CASE WHEN l.event_type='POST' THEN -p.qty ELSE p.qty END",
        'unit_cost': 'p.unit_cost',
        'event_key': "l.event_key || ':stock:' || p.id",
        'reverses_event_key': "CASE WHEN l.event_type='REVERSAL' THEN l.reverses_event_key || ':stock:' || p.id ELSE l.reverses_event_key END",
    }
    parts_select = ','.join(expressions.get(col,'l.'+col)+' AS '+col for col in columns)
    conn.execute('''CREATE VIEW invoice_inventory_effective_ledger AS
        SELECT l.* FROM invoice_inventory_remap_base_ledger l
        WHERE NOT EXISTS (
            SELECT 1 FROM output_stock_remap_parts p JOIN invoice_inventory_ledger original ON original.id=p.ledger_id
            WHERE l.id=original.id OR (l.event_type='REVERSAL' AND l.reverses_event_key=original.event_key))
        UNION ALL SELECT '''+parts_select+''' FROM output_stock_remap_parts p
        JOIN invoice_inventory_ledger original ON original.id=p.ledger_id
        JOIN invoice_inventory_remap_base_ledger l ON l.id=original.id
          OR (l.event_type='REVERSAL' AND l.reverses_event_key=original.event_key)
        WHERE p.qty>0''')


class RemapError(ValueError):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _excel_value(value):
    # Excel saves numbers to 15 significant digits. Compare the exported
    # representation, while retaining the full source precision in the snapshot
    # and database. This is not a quantity or monetary edit from the workbook.
    if isinstance(value, float):
        return float(format(value, '.15g'))
    return '' if value is None else value


def _snapshot(conn, start, end):
    report = monthly_average_report(conn, date_from=start, date_to=end, include_zero=True)
    stock = {r['product_code']: r for r in report['items']}
    rows = []
    raw_hashes = {}
    source_allowed = {}
    for r in conn.execute('''SELECT l.*,i.invoice_series,i.invoice_number,i.stock_status,
            i.source_status_class,i.sync_status,i.source,i.error_message,i.invoice_date,
            i.subtotal,i.total_amount,i.tax_amount header_tax,i.buyer_name,i.buyer_tax_code,
            li.source_item_code,li.source_item_name,
            li.source_unit,li.qty,li.unit_price,li.amount,li.tax_rate,i.raw_json,
            p.name,p.unit,COALESCE(part.revision,m.revision,0) remap_revision
          FROM invoice_inventory_effective_ledger l
          JOIN outgoing_source_invoices i ON i.id=l.source_invoice_id
          JOIN outgoing_source_invoice_items li ON li.id=l.source_line_id AND li.invoice_id=i.id
          JOIN products p ON p.code=l.product_code
          LEFT JOIN output_stock_remaps m ON m.ledger_id=l.id
          LEFT JOIN output_stock_remap_parts part ON l.id=-2*part.id
          WHERE l.source_invoice_table='outgoing_source_invoices' AND l.direction='output'
            AND l.event_type='POST' AND i.source='minvoice' AND i.stock_status='posted'
            AND i.source_status_class='issued'
            AND l.txn_date>=? AND l.txn_date<=? ORDER BY l.txn_date,l.id''', (start, end)):
        item = dict(r)
        invoice_id = r['source_invoice_id']
        if invoice_id not in source_allowed:
            source_allowed[invoice_id] = r['sync_status'] == 'synced' or output_amount_review(item) is not None
        if not source_allowed[invoice_id]:
            continue
        tax_line = dict(item, line_index=r['source_line_index'])
        annotate_invoice_tax({'items': [tax_line]}, r['raw_json'])
        if invoice_id not in raw_hashes:
            raw_hashes[invoice_id] = hashlib.sha256(r['raw_json'].encode()).hexdigest()
        item.pop('raw_json')
        item['source_json_hash'] = raw_hashes[invoice_id]
        item['closing_qty'] = stock[r['product_code']]['closing_qty']
        item['cells'] = [r['id'], r['txn_date'], str(r['invoice_series'] or '') + ' / ' + str(r['invoice_number'] or ''),
                         r['source_item_code'] or '', r['source_item_name'] or '', r['source_unit'] or '',
                         r['qty'], r['unit_price'], r['amount'], tax_line['tax_rate'], tax_line['line_tax_amount'],
                         r['product_code'], r['name'], r['unit'], -r['qty_delta'], item['closing_qty']]
        rows.append(item)
    snapshot = {'from': start, 'to': end, 'rows': rows, 'stock': report['items'],
            'catalog': [dict(r) for r in conn.execute('SELECT code,name,unit,tax FROM products ORDER BY code')],
            'closures': [dict(r) for r in conn.execute('SELECT period,status,revision FROM inventory_period_closures ORDER BY period')],
            'holds': [dict(r) for r in conn.execute("SELECT id,product_code,qty_out,status FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' ORDER BY id")],
            'local_invoices': [dict(r) for r in conn.execute("SELECT id,status,issued_invoice_number,issued_invoice_series,issued_invoice_date FROM outgoing_invoice_drafts WHERE status!='cancelled' ORDER BY id")],
            'openings': [dict(r) for r in conn.execute("SELECT id,txn_date,product_code,qty_in,qty_out,unit_cost FROM inventory_transactions WHERE source_type='OPENING' AND status='posted' ORDER BY id")]}
    parts = [dict(r) for r in conn.execute('SELECT * FROM output_stock_remap_parts ORDER BY id')]
    if parts: snapshot['parts'] = parts
    return snapshot


def _editable_period(conn, start):
    if conn.execute("SELECT 1 FROM inventory_period_closures WHERE period>=? AND status='closed' LIMIT 1", (start[:7],)).fetchone():
        raise RemapError('Kỳ này hoặc kỳ sau đã chốt. Mở lại các kỳ liên quan trước khi đổi mã xuất kho.')
    if conn.execute("SELECT 1 FROM inventory_transactions WHERE source_type='OPENING' AND status='posted' AND txn_date>? LIMIT 1", (start,)).fetchone():
        raise RemapError('Đã có tồn đầu kỳ sau. Cần mở lại kỳ đã chuyển tồn trước khi đổi mã xuất kho.')


def _store(conn, kind, payload):
    conn.execute('DELETE FROM output_stock_excel_sessions WHERE created<?', (time.time() - 7 * 86400,))
    token = uuid.uuid4().hex
    conn.execute('INSERT INTO output_stock_excel_sessions(token,kind,payload,created) VALUES(?,?,?,?)',
                 (token, kind, _json(payload), time.time()))
    return token


def _load(conn, token, kind, ttl):
    row = conn.execute('SELECT * FROM output_stock_excel_sessions WHERE token=? AND kind=?', (token, kind)).fetchone()
    if not row or time.time() - row['created'] > ttl:
        raise RemapError('File hoặc lượt xem trước đã hết hạn. Tải Excel mới và kiểm tra lại.')
    return row, json.loads(row['payload'])


def _source_hash(snapshot):
    # Export scope is saved server-side; the source hash still covers ALL stock
    # and source lines, including lines not included in a focused workbook.
    return _hash({k:v for k,v in snapshot.items() if k != 'exported_row_ids'})


def _quantity_text(value):
    return format(float(value), ',.6f').rstrip('0').rstrip('.').replace(',', '_').replace('.', ',').replace('_', '.')


def export_workbook(conn, start, end, scope='all'):
    if not conn.in_transaction:
        conn.execute('BEGIN')
    snapshot = _snapshot(conn, start, end)
    _editable_period(conn, snapshot['from'])
    if scope not in {'all', 'blocking'}:
        raise RemapError('Phạm vi tải Excel không hợp lệ.')
    blocked = {r['product_code'] for r in snapshot['stock'] if r['closing_qty'] < -1e-9} - kkknt_codes(conn)
    rows = [r for r in snapshot['rows'] if scope == 'all' or r['product_code'] in blocked]
    if scope == 'blocking':
        snapshot['exported_row_ids'] = [r['id'] for r in rows]
    token = _store(conn, 'export', snapshot)
    wb = Workbook(); ws = wb.active; ws.title = 'Doi ma xuat kho'
    for area, text in [
        ('A1:K1', 'THÔNG TIN HÓA ĐƠN GỐC · GIỮ NGUYÊN'),
        ('L1:R1', f"{len(rows)} dòng {'cần xử lý' if scope == 'blocking' else 'xuất'} / {len({r['product_code'] for r in rows})} mã hàng · Chỉ sửa 2 cột vàng Q–R."),
        ('A2:K2', 'Mã trên HĐ có thể trống. Mã nội bộ đang trừ kho ở cột L. Hóa đơn gốc giữ nguyên.'),
        ('L2:R2', 'Sao chép cặp mã + tên từ sheet Danh muc ma hang. Sửa Q–R, lưu file rồi tải lên lại. Giữ các dòng không cần đổi.'),
        ('A3:K3', 'THÔNG TIN NGUỒN · KHÔNG SỬA'),
        ('L3:P3', 'HÀNG ĐANG TRỪ KHO · ĐỐI CHIẾU'),
        ('Q3:R3', 'HÀNG MUỐN CHUYỂN SANG · SỬA Ở ĐÂY'),
    ]:
        ws.merge_cells(area)
        cell = ws[area.split(':')[0]]; cell.value = text
        cell.alignment = Alignment(wrap_text=True, vertical='center')
        cell.font = Font(bold=cell.row != 2, color='17354A', size=11)
        cell.fill = PatternFill('solid', fgColor='FFF2CC' if cell.column == 1 else 'EDF2F5')
    ws.append(HEADERS)
    for r in rows:
        values = [_excel_value(v) for v in r['cells']] + [r['product_code'], r['name']]
        ws.append(values)
    ws.freeze_panes = 'A5'; ws.auto_filter.ref = f'A4:R{max(ws.max_row,4)}'
    ws.sheet_view.topLeftCell = 'L1'
    ws.sheet_view.pane.topLeftCell = 'L5'
    ws.sheet_view.selection = [Selection(pane='bottomLeft',activeCell='Q5',sqref='Q5')]
    ws.sheet_view.showGridLines = False
    for row in ws.iter_rows(min_row=4):
        for cell in row:
            if isinstance(cell.value, str): cell.data_type = 's'
            editable = cell.column >= 17
            source = cell.column <= 11
            cell.alignment = Alignment(wrap_text=True, vertical='center')
            cell.fill = PatternFill('solid', fgColor='FFF2CC' if editable else 'F2F4F6' if source else 'EFF7FB')
            cell.font = Font(bold=cell.row == 4, color='17354A' if not source else '4B5563', size=11)
            if editable and cell.row > 4:
                cell.protection = Protection(locked=False)
            if cell.row > 4 and cell.column in (7,8,9,11,15,16):
                cell.number_format = '#,##0.######;[Red]-#,##0.######'
    for index, width in enumerate((14,16,23,22,38,12,14,18,18,14,18,18,42,12,14,16,22,42),1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.column_dimensions['A'].hidden = True
    for row, height in ((1,34),(2,34),(3,26),(4,46)): ws.row_dimensions[row].height = height
    ws['D4'].comment = Comment('Mã hóa đơn nguồn có thể trống. Mã nội bộ đang trừ kho ở cột L.', 'TDP')
    ws['Q4'].comment = Comment('Chọn mã + tên mới ở Q–R. Chỉ chuyển đủ phần âm của mỗi mã, theo thứ tự hàng Excel; không chuyển toàn bộ lượng ở O.', 'TDP')
    ws['P4'].comment = Comment('Tồn lặp ở các dòng xuất cùng mã. Không cộng lặp; xem Tổng hợp hàng âm để đếm theo mã.', 'TDP')
    ws['J4'].comment = Comment('Thuế hóa đơn nguồn; có thể khác thuế danh mục trên báo cáo tồn.', 'TDP')
    summary = wb.create_sheet('Tổng hợp hàng âm')
    catalog_by_code = {p['code']:p for p in snapshot['catalog']}
    by_code = defaultdict(list)
    first_rows = {}
    for index, row in enumerate(rows, 5):
        by_code[row['product_code']].append(row)
        first_rows.setdefault(row['product_code'], index)
    negatives = [r for r in snapshot['stock'] if r['closing_qty'] < -1e-9]
    summary.append([f'{len(negatives)} mã tồn âm · Mỗi mã chỉ một dòng. Lọc cột Thuế danh mục để so với báo cáo tồn.'])
    summary.merge_cells('A1:I1')
    summary.append(['Mã nội bộ','Tên hàng','Thuế danh mục (như báo cáo tồn)','Thuế HĐ trong file đổi mã',
                    'ĐVT','Tồn cuối kỳ (mỗi mã một lần)','Số dòng xuất có thể đổi','Đối chiếu thuế','Mở dòng xuất'])
    for item in negatives:
        code = item['product_code']; lines = by_code[code]
        review = compare_tax(catalog_by_code[code], [{'tax_rate':r['cells'][9]} for r in lines])
        summary.append([code, catalog_by_code[code]['name'], review['catalog'], review['source'], item['unit'],
                        item['closing_qty'], len(lines), review['note'],
                        'Đến dòng xuất đầu tiên; có thể lọc mã ở cột L' if lines else 'Không có dòng xuất trong file đổi mã'])
        if lines:
            summary.cell(summary.max_row,9).hyperlink = f"#'Doi ma xuat kho'!L{first_rows[code]}"
        if review['differs']:
            for cell in summary[summary.max_row]: cell.fill = PatternFill('solid',fgColor='FFF2CC')
        summary.cell(summary.max_row,6).number_format = '#,##0.######;[Red]-#,##0.######'
    format_review_sheet(summary, 2, (18,40,26,26,12,25,20,62,48))
    catalog = wb.create_sheet('Danh muc ma hang'); catalog.append(['Mã nội bộ', 'Tên nội bộ', 'ĐVT', 'Thuế'])
    for p in snapshot['catalog']: catalog.append([p[k] for k in ('code','name','unit')] + [display_tax(p['tax'])])
    catalog.auto_filter.ref = catalog.dimensions; catalog.freeze_panes = 'A2'; catalog.column_dimensions['B'].width = 48
    guide = wb.create_sheet('Huong dan')
    for line in [f"File gồm {len(rows)} dòng xuất / {len({r['product_code'] for r in rows})} mã hàng. " + ('Chỉ gồm dòng xuất của mã âm đang chặn chuyển tháng.' if scope == 'blocking' else 'Gồm toàn bộ dòng xuất có thể đổi mã trong kỳ.'),
                 'Chỉ sửa hai cột vàng Q–R: Mã nội bộ mới và Tên nội bộ mới, theo sheet Danh muc ma hang.',
                 'Cột L–P là hàng đang trừ kho và tồn để đối chiếu. Cột A–K là thông tin hóa đơn gốc, không sửa.',
                 'Mã trên hóa đơn gốc có thể trống do nguồn M-Invoice không có mã; không có nghĩa là thiếu mã nội bộ.',
                 'File đổi mã giữ từng dòng xuất hóa đơn. Một mã có thể xuất nhiều dòng; không cộng lặp Tồn cuối kỳ.',
                 'Sheet Tổng hợp hàng âm gom mỗi mã một dòng. Lọc Thuế danh mục để so với báo cáo tồn; Thuế HĐ là nguồn riêng, có thể khác danh mục.',
                 'Chỉ chuyển phần tồn âm của mỗi mã một lần. Xét các dòng đã chọn từ trên xuống; mỗi dòng chuyển tối đa lượng trừ kho của dòng đó và dừng khi đủ phần âm.',
                 'Ví dụ mã âm 64 Gói: dù chọn các dòng 64, 350 và 800, tổng chuyển chỉ 64. Bột tiêu âm 0,3 Kg chỉ chuyển 0,3.',
                 'Phần chuyển dùng đơn vị của mã nhận, không quy đổi tỷ lệ. Phần xuất còn lại vẫn trừ mã cũ. KKKNT được bỏ qua.',
                 'Không đổi tên, đơn vị, lượng, tiền, thuế hay nội dung hóa đơn gốc.',
                 'Có thể lọc các dòng Tồn cuối kỳ âm; giữ nguyên các dòng không cần đổi. Không xóa dòng hoặc cột.',
                 'Tải file lên để xem trước đơn vị cũ → mới. Hệ thống kiểm tra mã/tên, tồn mã nhận, kỳ chốt và dữ liệu đã thay đổi.',
                 'KKKNT được lập bảng kê và chuyển nguyên tồn âm. KCT và 0% không thuộc ngoại lệ này.',
                 'Mã âm từ đầu kỳ không có dòng xuất: đối chiếu tồn đầu; KKKNT có thể lập bảng kê mua vào bổ sung theo nguồn thực tế.']:
        guide.append([line])
    guide.column_dimensions['A'].width = 130
    meta = wb.create_sheet('_meta'); meta.append(['token', token]); meta.sheet_state = 'veryHidden'
    for sheet in (catalog, guide):
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str): cell.data_type = 's'
    output = io.BytesIO(); wb.save(output); return output.getvalue()


def _set_overrides(conn, changes, timestamp):
    for c in changes:
        if c['ledger_id'] < 0:
            part = conn.execute('SELECT * FROM output_stock_remap_parts WHERE id=?',(-c['ledger_id']//2,)).fetchone()
            base_id = part['ledger_id']
        else:
            base_id = c['ledger_id']
            part = None
        base = conn.execute('SELECT * FROM invoice_inventory_remap_base_ledger WHERE id=?',(base_id,)).fetchone()
        if not part and abs(c['qty'] + base['qty_delta']) < 1e-9:
            conn.execute('''INSERT INTO output_stock_remaps(ledger_id,product_code,revision,updated_at,unit_cost) VALUES(?,?,1,?,?)
                           ON CONFLICT(ledger_id) DO UPDATE SET product_code=excluded.product_code,
                           revision=output_stock_remaps.revision+1,updated_at=excluded.updated_at,unit_cost=excluded.unit_cost''',
                         (base_id, c['new_code'], timestamp, c.get('new_unit_cost')))
            continue
        if not part:
            conn.execute('INSERT INTO output_stock_remap_parts(ledger_id,product_code,qty,unit_cost) VALUES(?,?,?,?)',
                         (base_id,c['old_code'],-base['qty_delta'],c['old_unit_cost']))
            part = conn.execute('SELECT * FROM output_stock_remap_parts WHERE ledger_id=? AND product_code=?',(base_id,c['old_code'])).fetchone()
        remaining = Decimal(str(part['qty'])) - Decimal(str(c['qty']))
        if remaining < 0:
            raise RemapError('Lượng chuyển vượt phần xuất nội bộ còn lại; tải lại file để đối chiếu.')
        conn.execute('UPDATE output_stock_remap_parts SET qty=?,revision=revision+1 WHERE id=?',(float(remaining),part['id']))
        existing = conn.execute('SELECT * FROM output_stock_remap_parts WHERE ledger_id=? AND product_code=?',(base_id,c['new_code'])).fetchone()
        new_qty = Decimal(str(c['qty'])) + (Decimal(str(existing['qty'])) if existing else 0)
        conn.execute('''INSERT INTO output_stock_remap_parts(ledger_id,product_code,qty,unit_cost) VALUES(?,?,?,?)
            ON CONFLICT(ledger_id,product_code) DO UPDATE SET qty=excluded.qty,unit_cost=excluded.unit_cost,revision=revision+1''',
                     (base_id,c['new_code'],float(new_qty),c.get('new_unit_cost') or 0))


def _evaluate(conn, snapshot, changes):
    _editable_period(conn, snapshot['from'])
    conn.execute('SAVEPOINT remap_preview')
    try:
        _set_overrides(conn, changes, 'preview')
        report = monthly_average_report(conn, date_from=snapshot['from'], date_to=snapshot['to'], include_zero=True)
        stocks = {r['product_code']: r for r in report['items']}
        exempt = kkknt_codes(conn)
        try:
            from .outgoing_readiness import canonical_available_stock
        except ImportError:
            from outgoing_readiness import canonical_available_stock
        available = canonical_available_stock(conn)
        # A later receipt must not conceal a shortage in an earlier month-after
        # checkpoint. Check each recipient once, including all active holds.
        future_available = {}
        for code in {c['new_code'] for c in changes} - exempt:
            holds = available.get(code, {})
            future_available[code] = (_minimum_balance_from(conn, code, snapshot['to'])
                                      - holds.get('reserved_qty', 0)
                                      - holds.get('pending_sync_issued_qty', 0))
        errors = []
        before = {r['product_code']:r for r in snapshot['stock']}
        grouped = defaultdict(list)
        returned = defaultdict(float)
        for change in changes:
            grouped[change['new_code']].append(change)
            returned[change['old_code']] += change['qty']
        for c in changes:
            target = stocks[c['new_code']]
            c['old_closing_after'] = stocks[c['old_code']]['closing_qty']
            c['new_closing_after'] = target['closing_qty']
            c['new_unit_cost'] = target['average_unit_cost']
            if c['new_unit_cost'] < 0:
                errors.append(f"Mã nhận {c['new_code']} có giá tồn không hợp lệ; đối chiếu tồn đầu và nhập trước khi chuyển.")
            if c['new_code'] not in exempt and target['closing_qty'] < -1e-9:
                code = c['new_code']; unit = c['unit']; selections = grouped[code]
                total = sum(Decimal(str(r['qty'])) for r in selections)
                positions = ', '.join(f"{r['excel_row']}: {_quantity_text(r['qty'])}" for r in selections)
                credit = f"; đồng thời hoàn về {_quantity_text(returned[code])} {unit}" if returned[code] else ''
                errors.append(f"{code} · {c['new_name']}: tồn cuối kỳ trước chuyển {_quantity_text(before[code]['closing_qty'])} {unit}{credit}. "
                              f"Tổng lượng xử lý âm chuyển sang {_quantity_text(total)} {unit} (hàng Excel {positions}). "
                              f"Còn thiếu {_quantity_text(-target['closing_qty'])} {unit}. Chọn mã nhận khác cho một số hàng Excel trên.")
            elif c['new_code'] not in exempt and future_available[c['new_code']] < -1e-9:
                errors.append(f"Mã nhận {c['new_code']} không đủ tồn tại một thời điểm từ cuối kỳ trở đi, đã trừ dự thảo đang giữ. Chọn mã khác hoặc kiểm tra giao dịch tháng sau và dự thảo.")
        return sorted(set(errors))
    finally:
        conn.execute('ROLLBACK TO remap_preview'); conn.execute('RELEASE remap_preview')


def preview_workbook(conn, data):
    if not conn.in_transaction:
        conn.execute('BEGIN')
    if len(data) > 10 * 1024 * 1024:
        raise RemapError('File vượt 10 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist()) > 80 * 1024 * 1024:
                raise RemapError('File Excel giải nén quá lớn.')
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
        token = wb['_meta']['B1'].value
        _, snapshot = _load(conn, token, 'export', 7 * 86400)
        if _source_hash(_snapshot(conn, snapshot['from'], snapshot['to'])) != _source_hash(snapshot):
            raise RemapError('Dữ liệu kho, danh mục hoặc hóa đơn đã thay đổi từ lúc tải file. Tải Excel mới để sửa.')
        ws = wb['Doi ma xuat kho']
        if ws.max_row > 30000 or ws.max_column != len(HEADERS):
            raise RemapError('Bố cục file không hợp lệ.')
        if [c.value for c in next(ws.iter_rows())] == HEADERS:
            first_data_row, column_order = 2, tuple(range(len(HEADERS)))
        elif [c.value for c in next(ws.iter_rows(min_row=4,max_row=4))] == NEW_HEADERS:
            first_data_row, column_order = 5, NEW_COLUMN_ORDER
        elif [c.value for c in next(ws.iter_rows(min_row=4,max_row=4))] == HEADERS:
            first_data_row, column_order = 5, tuple(range(len(HEADERS)))
        else:
            raise RemapError('Không được đổi tiêu đề hoặc thứ tự cột.')
        allowed_ids = set(snapshot.get('exported_row_ids', [r['id'] for r in snapshot['rows']]))
        originals = {r['id']: r for r in snapshot['rows'] if r['id'] in allowed_ids}
        products = {p['code']: p for p in snapshot['catalog']}
        stocks = {r['product_code']:r for r in snapshot['stock']}
        exempt = kkknt_codes(conn)
        deficits = {code:max(Decimal(0),-Decimal(str(r['closing_qty']))) for code,r in stocks.items() if code not in exempt}
        seen = set(); changes = []; errors = []; skipped = []
        for excel_row, cells in enumerate(ws.iter_rows(min_row=first_data_row), first_data_row):
            values = [None] * len(HEADERS)
            for cell, original_column in zip(cells,column_order):
                values[original_column] = cell.value
            if all(v is None for v in values): continue
            if any(c.data_type == 'f' for c in cells):
                raise RemapError(f'Dòng {excel_row}: không nhận công thức; dán giá trị vào hai cột vàng.')
            key = values[0]
            if key not in originals or key in seen:
                raise RemapError(f'Dòng {excel_row}: ID không thuộc file hoặc bị lặp.')
            seen.add(key); old = originals[key]
            if [_excel_value(v) for v in values[:16]] != [_excel_value(v) for v in old['cells']]:
                raise RemapError(f'Dòng {excel_row}: đã sửa cột gốc. Chỉ được đổi mã và tên nội bộ mới.')
            code, name = str(values[16] or '').strip(), str(values[17] or '').strip()
            if code == old['product_code'] and name == old['name']: continue
            remaining = deficits.get(old['product_code'],Decimal(0))
            if remaining <= 0:
                skipped.append({'excel_row':excel_row,'old_code':old['product_code'],'old_name':old['name'],
                                'reason':'KKKNT: bỏ qua' if old['product_code'] in exempt else 'Đã đủ lượng xử lý âm hoặc mã không âm'})
                continue
            p = products.get(code)
            if not p or name != p['name']:
                expected = f'Tên đúng của mã {code}: {p["name"]}.' if p else f'Mã mới {code or "(trống)"} không có trong danh mục.'
                errors.append(f'Hàng số {excel_row} trong Excel · {old["product_code"]} · {old["name"]}: mã/tên mới không khớp danh mục. {expected} Sao chép đúng cặp mã + tên từ Danh muc ma hang.'); continue
            if code == old['product_code']: continue
            qty = min(remaining,Decimal(str(-old['qty_delta'])))
            deficits[old['product_code']] -= qty
            changes.append({'ledger_id': key, 'line_id': old['source_line_id'], 'invoice_id': old['source_invoice_id'],
                            'old_code': old['product_code'], 'old_name': old['name'], 'new_code': code,
                            'new_name': name, 'qty': float(qty), 'old_unit': old['unit'],
                            'source_stock_qty':-old['qty_delta'], 'old_unit_cost':stocks[old['product_code']]['average_unit_cost'],
                            'unit': p['unit'], 'excel_row': excel_row})
        if seen != set(originals): raise RemapError('File bị thiếu dòng. Giữ nguyên các dòng không cần đổi mã.')
        if not changes and not errors: errors.append('Không có lượng tồn âm cần chuyển trong các dòng đã chọn. KKKNT được bỏ qua.')
        if changes and not errors: errors.extend(_evaluate(conn, snapshot, changes))
        preview = {'snapshot': snapshot, 'changes': changes, 'errors': errors, 'mode':'deficit_only_v1'}
        preview_token = _store(conn, 'preview', preview)
        return {'token': preview_token, 'changes': changes, 'errors': errors, 'can_confirm': bool(changes) and not errors,
                'from': snapshot['from'], 'to': snapshot['to'], 'skipped':skipped, 'mode':'deficit_only_v1'}
    except (KeyError, zipfile.BadZipFile, InvalidFileException, ParseError, ValueError, TypeError) as exc:
        if isinstance(exc, RemapError): raise
        raise RemapError('File không phải mẫu đổi mã đã tải từ hệ thống hoặc chứa dữ liệu không hợp lệ.') from exc
    finally:
        if 'wb' in locals(): wb.close()


def confirm_preview(conn, token, actor, timestamp):
    row, preview = _load(conn, token, 'preview', 900)
    if row['result']: return {**json.loads(row['result']), 'idempotent': True}
    if preview.get('mode') != 'deficit_only_v1':
        raise RemapError('Cách tính đã đổi sang chỉ xử lý tồn âm. Chọn lại file đã sửa ở bước 2 để xem đúng lượng trước khi xác nhận.')
    if not actor or len(actor) > 100: raise RemapError('Cần tên người xác nhận, tối đa 100 ký tự.')
    if preview['errors'] or not preview['changes']: raise RemapError('File còn lỗi hoặc chưa có thay đổi.')
    snapshot, changes = preview['snapshot'], preview['changes']
    if _source_hash(_snapshot(conn, snapshot['from'], snapshot['to'])) != _source_hash(snapshot):
        raise RemapError('Dữ liệu đã thay đổi sau khi xem trước. Tải Excel mới để đối chiếu.')
    errors = _evaluate(conn, snapshot, changes)
    if errors: raise RemapError('; '.join(errors))
    conn.execute('SAVEPOINT apply_stock_remap')
    try:
        _set_overrides(conn, changes, timestamp)
        for c in changes:
            # These are local mapping fields only. Source names, codes, amounts,
            # quantities, tax, raw source JSON and issued invoice headers stay intact.
            # Split lines have several stock identities. Keep the source line's
            # existing mapping instead of relabelling the whole issued line.
            if c['ledger_id'] > 0 and not conn.execute('SELECT 1 FROM output_stock_remap_parts WHERE ledger_id=?',(c['ledger_id'],)).fetchone():
                conn.execute('UPDATE outgoing_source_invoice_items SET product_code=? WHERE id=? AND invoice_id=?',
                             (c['new_code'], c['line_id'], c['invoice_id']))
        conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) VALUES('inventory.output.remap','excel',?,'ok',?,?,?)",
                     (token, 'Đổi mã nội bộ theo Excel', _json({'actor': actor, 'from': snapshot['from'], 'to': snapshot['to'], 'changes': changes}), timestamp))
        result = {'changed_lines': len(changes), 'idempotent': False}
        conn.execute('UPDATE output_stock_excel_sessions SET result=? WHERE token=?', (_json(result), token))
        conn.execute('RELEASE apply_stock_remap')
        return result
    except Exception:
        conn.execute('ROLLBACK TO apply_stock_remap'); conn.execute('RELEASE apply_stock_remap'); raise


def register_routes(app, ctx):
    @app.get('/api/inventory/output-remap/export')
    def output_remap_export():
        try:
            with ctx['db']() as conn:
                data = export_workbook(conn, request.args.get('from'), request.args.get('to'), scope=request.args.get('scope','blocking'))
            return send_file(io.BytesIO(data), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             as_attachment=True, download_name='Doi_ma_noi_bo_xuat_kho.xlsx')
        except ValueError as exc: return jsonify(ok=False, error=str(exc)), 400
        except sqlite3.Error: return jsonify(ok=False, error='Dữ liệu đang được cập nhật. Thử tải Excel lại sau ít giây.'), 409

    @app.post('/api/inventory/output-remap/preview')
    def output_remap_preview():
        try:
            file = request.files.get('file')
            if not file: raise RemapError('Chọn file Excel đã sửa.')
            with ctx['db']() as conn:
                result = preview_workbook(conn, file.read(10 * 1024 * 1024 + 1))
            return jsonify(ok=True, **result)
        except ValueError as exc: return jsonify(ok=False, error=str(exc)), 400
        except sqlite3.Error: return jsonify(ok=False, error='Dữ liệu đang được cập nhật. Chọn lại file để kiểm tra.'), 409

    @app.post('/api/inventory/output-remap/confirm')
    def output_remap_confirm():
        try:
            body = request.get_json(silent=True) or {}
            if body.get('confirmed') is not True: raise RemapError('Cần xác nhận sau khi xem trước.')
            with ctx['db']() as conn:
                conn.execute('BEGIN IMMEDIATE')
                result = confirm_preview(conn, body.get('token'), str(body.get('actor') or '').strip(), ctx['now_iso']())
            return jsonify(ok=True, **result)
        except ValueError as exc: return jsonify(ok=False, error=str(exc)), 409
        except sqlite3.Error: return jsonify(ok=False, error='Chưa lưu được đổi mã; dữ liệu đã hoàn tác. Kiểm tra lại rồi xác nhận.'), 409
