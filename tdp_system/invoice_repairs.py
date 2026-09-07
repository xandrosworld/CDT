"""Guarded data corrections. Call only in a backed-up, explicit transaction."""
import json

try:
    from . import invoice_mapping as mapping
    from .invoice_line_groups import source_fingerprint
except ImportError:
    import invoice_mapping as mapping
    from invoice_line_groups import source_fingerprint


def correct_unused_product_unit(conn, *, code, expected_name, expected_unit, unit, now):
    product = conn.execute('SELECT code,name,unit FROM products WHERE code=?',(code,)).fetchone()
    if not product or (product['name'],product['unit']) != (expected_name,expected_unit) or not unit.strip():
        raise ValueError('Danh mục đã thay đổi; dừng sửa đơn vị.')
    # References in stock, orders, opening balances, and saved mappings must all be absent.
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        table = row[0]
        if table in ('products','product_prices','outgoing_product_names'):
            continue
        quoted = '"' + table.replace('"','""') + '"'
        columns = {r['name'] for r in conn.execute('PRAGMA table_info('+quoted+')')}
        if 'product_code' in columns and conn.execute('SELECT 1 FROM '+quoted+' WHERE product_code=? LIMIT 1',(code,)).fetchone():
            raise ValueError('Mã đã được sử dụng trong '+table+'; cần đối chiếu trước khi đổi đơn vị.')
    conn.execute('UPDATE products SET unit=? WHERE code=?',(unit,code))
    if 'catalog_updated_at' in {r['name'] for r in conn.execute('PRAGMA table_info(products)')}:
        conn.execute('UPDATE products SET catalog_updated_at=? WHERE code=?',(now,code))
    conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('catalog.unit_correction','product',?,'ok','',?,?)""",
        (code,json.dumps({'before':expected_unit,'after':unit},ensure_ascii=False),now))


def correct_input_line_product(conn, *, item_id, expected, code, now):
    row = mapping._line_context(conn,'input',item_id)
    if not row or not row['inventory_eligible'] or row['parent_status'] in ('posted','blocked') or row['parent_sync_status']!='synced':
        raise ValueError('Dòng không còn được phép sửa mã.')
    mapping._check_expected(row,expected)
    product = mapping._product(conn,code)
    if not mapping.mapping_units_match(row['source_unit'],product['unit']):
        raise ValueError('Đơn vị chưa trùng khớp; không tự suy đoán quy đổi.')
    groups = conn.execute('SELECT member_indices FROM invoice_input_line_groups WHERE invoice_id=? AND active=1',(row['invoice_id'],)).fetchall()
    if any(row['line_index'] in json.loads(g[0]) for g in groups):
        raise ValueError('Dòng đã gộp; tách nhóm trước khi sửa mã riêng.')
    scope = f"selected-line:{row['invoice_id']}:{row['line_index']}"
    conn.execute("""INSERT INTO invoice_line_mappings(tenant,source,invoice_type,partner_key,scope_key,
        source_item_code,source_item_name,source_unit,product_code,target_unit,mapping_status,conversion_factor,confirmed_at,updated_at)
        VALUES(?,'msmi','INPUT_ELECTRONIC_INVOICE',?,?,?,?,?,?,?,'confirmed',1,?,?)
        ON CONFLICT(tenant,source,invoice_type,partner_key,scope_key,effective_from) DO UPDATE SET
        product_code=excluded.product_code,target_unit=excluded.target_unit,mapping_status='confirmed',
        conversion_factor=1,updated_at=excluded.updated_at""",
        (row['tenant'],row['partner_key'],scope,row['source_item_code'],row['source_item_name'],row['source_unit'],code,product['unit'],now,now))
    rule = conn.execute("SELECT * FROM invoice_line_mappings WHERE tenant=? AND source='msmi' AND invoice_type='INPUT_ELECTRONIC_INVOICE' AND partner_key=? AND scope_key=? AND effective_from=''",
        (row['tenant'],row['partner_key'],scope)).fetchone()
    mapping._record_revision(conn,rule,now)
    mapping._update_line_snapshot(conn,'msmi_invoice_items',item_id,code,'mapped',1)
    conn.execute('INSERT OR REPLACE INTO invoice_input_group_choices VALUES(?,?,?,?,?,?,?,?)',
        (row['invoice_id'],row['line_index'],source_fingerprint(row),code,1,product['unit'],rule['id'],now))
    mapping._refresh_input_invoice(conn,row['invoice_id'])
    mapping.refresh_linked_batches(conn,'input',{row['invoice_id']},now)
    conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
        VALUES('invoice_input.product_correction','msmi_invoice_item',?,'ok','',?,?)""",
        (str(item_id),json.dumps({'before':row['product_code'],'after':code,'scope':'single_line'},ensure_ascii=False),now))
