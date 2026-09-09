"""The issued-invoice register records source quantities independently of valuation."""
import json


def uses_source_quantity_posting(invoice):
    row = dict(invoice)
    if row.get('source') != 'minvoice':
        return False
    try:
        return json.loads(row.get('raw_json') or '{}').get('_tdp_source_contract') == 'minvoice_portal_v1'
    except (TypeError, ValueError, AttributeError):
        return False


def source_quantity_invoice_ids(conn):
    return {r['id'] for r in conn.execute('SELECT id,source,raw_json FROM outgoing_source_invoices')
            if uses_source_quantity_posting(r)}
