"""Outgoing invoices use the chosen product code and the unchanged source quantity."""
import json
from datetime import datetime


def confirm_code_only_rule(conn, mapping, *, timestamp=None):
    try:
        from .invoice_mapping import _product, _record_revision, OUTPUT_INVOICE
    except ImportError:
        from invoice_mapping import _product, _record_revision, OUTPUT_INVOICE
    if mapping['invoice_type'] != OUTPUT_INVOICE or mapping['source'] != 'minvoice':
        raise ValueError('Code-only policy applies to M-Invoice output only')
    product = _product(conn, mapping['product_code'])
    if (mapping['mapping_status'] == 'confirmed' and mapping['conversion_factor'] == 1
            and mapping['target_unit'] == product['unit']):
        return mapping
    timestamp = timestamp or datetime.now().isoformat(timespec='seconds')
    conn.execute("UPDATE invoice_line_mappings SET mapping_status='confirmed',conversion_factor=1,"
                 "target_unit=?,confirmed_at=?,updated_at=? WHERE id=?",
                 (product['unit'], timestamp, timestamp, mapping['id']))
    current = conn.execute('SELECT * FROM invoice_line_mappings WHERE id=?', (mapping['id'],)).fetchone()
    _record_revision(conn, current, timestamp)
    conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) "
                 "VALUES('invoice_output.code_only_rule','invoice_line_mapping',?,'ok','',?,?)",
                 (str(mapping['id']), json.dumps({
                     'product_code': mapping['product_code'],
                     'previous_status': mapping['mapping_status'],
                     'previous_factor': mapping['conversion_factor'],
                     'previous_target_unit': mapping['target_unit'],
                     'quantity_policy': 'source_quantity',
                 }, ensure_ascii=False), timestamp))
    return current


def repair_output_code_only(conn, *, timestamp):
    """Upgrade saved, unposted choices once. Never infer a code or touch a ledger."""
    try:
        from .invoice_mapping import (_line_context, _active_mappings, _scope_key,
                                      _editable_mapping_source, _stock_values,
                                      _update_line_snapshot, _refresh_output_invoice, _refresh_batches)
    except ImportError:
        from invoice_mapping import (_line_context, _active_mappings, _scope_key,
                                     _editable_mapping_source, _stock_values,
                                     _update_line_snapshot, _refresh_output_invoice, _refresh_batches)
    candidates = conn.execute(
        "SELECT li.id FROM outgoing_source_invoice_items li JOIN outgoing_source_invoices i ON i.id=li.invoice_id "
        "WHERE i.source='minvoice' AND i.source_status_class='issued' "
        "AND i.stock_status NOT IN ('posted','reversed','reversal_required') "
        "AND li.inventory_eligible=1 AND li.product_code!='' "
        "AND li.mapping_status IN ('mapped','unit_review') "
        "AND NOT EXISTS(SELECT 1 FROM invoice_inventory_ledger l WHERE l.direction='output' AND l.source_invoice_id=i.id)"
    ).fetchall()
    changed, invoices = [], set()
    for candidate in candidates:
        line = _line_context(conn, 'output', candidate['id'])
        if not _editable_mapping_source('output', line):
            continue
        scope = _scope_key(line['source_item_code'], line['source_item_name'], line['source_unit'])
        rules = _active_mappings(conn, line, scope)
        if len(rules) != 1 or rules[0]['product_code'] != line['product_code']:
            continue
        confirm_code_only_rule(conn, rules[0], timestamp=timestamp)
        qty, price = _stock_values(line['qty'], line['amount'], 1)
        if (line['mapping_status'] == 'mapped' and line['conversion_factor'] == 1
                and line['stock_qty'] == qty and line['stock_unit_price'] == price):
            continue
        _update_line_snapshot(conn, 'outgoing_source_invoice_items', line['id'], line['product_code'], 'mapped', 1)
        changed.append({'item_id': line['id'], 'previous_status': line['mapping_status'],
                        'previous_factor': line['conversion_factor'], 'previous_stock_qty': line['stock_qty'],
                        'stock_qty': qty})
        invoices.add(line['invoice_id'])
    for invoice_id in invoices:
        _refresh_output_invoice(conn, invoice_id)
    if changed:
        _refresh_batches(conn, 'output', invoices, timestamp)
        conn.execute("INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) "
                     "VALUES('invoice_output.code_only_migration','invoice_output','source_quantity','ok','',?,?)",
                     (json.dumps({'lines': changed}, ensure_ascii=False), timestamp))
    return {'changed_lines': len(changed), 'invoice_ids': sorted(invoices)}
