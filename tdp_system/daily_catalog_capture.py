"""Add new products from explicitly named daily-workbook catalogue sheets.

Preview is read-only. Apply belongs inside the order import transaction and
never updates existing products, prices, suppliers or identity references.
"""
from types import SimpleNamespace
from openpyxl import load_workbook

try:
    from .contract_modules import parse_catalog_workbook, mapping_key, catalog_database_state_hash, new_products_from_price_sheets
except ImportError:
    from contract_modules import parse_catalog_workbook, mapping_key, catalog_database_state_hash, new_products_from_price_sheets


CATALOG_SHEET_KEYS = {'danhmuchh', 'danhmuchanghoa', 'danhmuchang'}


def preview_catalog_additions(conn, path):
    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    items, errors, sheets = {}, [], []
    try:
        for ws in workbook.worksheets:
            if mapping_key(ws.title) not in CATALOG_SHEET_KEYS:
                continue
            sheets.append(ws.title)
            try:
                parsed = parse_catalog_workbook(conn, SimpleNamespace(worksheets=[ws]), mode='new_only')
            except ValueError as exc:
                errors.append(f'{ws.title}: {exc}')
                continue
            for row in parsed['rows']:
                if row['errors']:
                    errors.append(f"{ws.title} · dòng {row['source_row']} · {row['product_code']}: " + '; '.join(row['errors']))
            for row in parsed['items']:
                code = row['product_code']
                current = items.get(code)
                fields = ('product_name', 'unit', 'tax', 'product_group', 'invoice_name', 'invoice_unit')
                if current and any(current[k] != row[k] for k in fields):
                    errors.append(f"Mã {code} khác dữ liệu giữa {current['sheet']} dòng {current['source_row']} và {ws.title} dòng {row['source_row']}")
                else:
                    items[code] = {**row, 'sheet': ws.title}
        excluded = set(items) | {r['code'] for r in conn.execute('SELECT code FROM products')}
        for row in new_products_from_price_sheets(conn, workbook, excluded):
            source = row['source_sheet']
            if source not in sheets:
                sheets.append(source)
            if row['errors']:
                errors.append(f"{source} · dòng {row['source_row']} · {row['product_code']}: " + '; '.join(row['errors']))
            elif row['apply']:
                items[row['product_code']] = {**row, 'sheet': source}
    finally:
        workbook.close()
    return {'sheets': sheets, 'items': list(items.values()), 'newCount': len(items),
            'errors': errors, 'canConfirm': not errors,
            'databaseHash': catalog_database_state_hash(conn)}


def staged_products(preview):
    if not preview or not preview['canConfirm']:
        return []
    return [dict(code=row['product_code'], name=row['product_name'], unit=row['unit'],
                 tax=row['tax'], supplier='', buy_price=0, purchase_list=0, seller='', cccd='')
            for row in preview['items']]


def apply_catalog_additions(conn, preview, *, timestamp, source_hash, source_name, audit):
    if not preview:
        return {'inserted': 0}
    if preview['errors']:
        raise ValueError('Danh mục hàng hóa còn lỗi: ' + ' | '.join(preview['errors'][:10]))
    if not preview['items']:
        return {'inserted': 0}
    if catalog_database_state_hash(conn) != preview['databaseHash']:
        raise ValueError('Danh mục đã thay đổi sau khi xem trước; hãy nạp lại file đơn hàng.')
    for item in preview['items']:
        code = item['product_code']
        conn.execute('''INSERT INTO products
            (code,name,unit,tax,supplier,buy_price,purchase_list,product_group,catalog_updated_at)
            VALUES(?,?,?,?,'',0,0,?,?)''',
            (code, item['product_name'], item['unit'], item['tax'], item['product_group'], timestamp))
        from tdp_system.catalog_products import clear_missing_product_error
        clear_missing_product_error(conn, code)
        if item['invoice_name']:
            conn.execute('INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES(?,?,?)',
                         (code, item['invoice_name'], timestamp))
        if item['invoice_unit']:
            conn.execute('INSERT INTO outgoing_product_units(product_code,invoice_unit,updated_at) VALUES(?,?,?)',
                         (code, item['invoice_unit'], timestamp))
    result = {'inserted': len(preview['items']), 'codes': [row['product_code'] for row in preview['items']]}
    audit(conn, 'catalog.daily_additions', entity_type='catalog', entity_id=source_hash[:16],
          metadata={'source_hash': source_hash, 'filename': source_name, 'sheets': preview['sheets'], **result})
    return result
