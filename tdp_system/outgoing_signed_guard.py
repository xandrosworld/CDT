"""Identify signed remote drafts independently of pending stock reconciliation."""
import json


def signed_draft_sources(conn):
    result = {}
    drafts = conn.execute("SELECT id,minvoice_key_api,minvoice_remote_id,buyer_tax_code_snapshot FROM outgoing_invoice_drafts WHERE status='draft'").fetchall()
    sources = conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice' AND source_status_class='issued' AND sync_status='synced'").fetchall()
    for source in sources:
        raw = json.loads(source['raw_json'] or '{}')
        if raw.get('_tdp_source_contract') != 'minvoice_portal_v1':
            continue
        for draft in drafts:
            reference = draft['minvoice_key_api']
            if not reference or raw.get('orderNumber') != reference or raw.get('keyApi') not in (None, '', reference):
                continue
            if draft['minvoice_remote_id'] and draft['minvoice_remote_id'] != source['remote_id']:
                continue
            if not draft['buyer_tax_code_snapshot'] or draft['buyer_tax_code_snapshot'].strip() != (source['buyer_tax_code'] or '').strip():
                continue
            result[draft['id']] = {'id': source['id'], 'number': source['invoice_number'], 'series': source['invoice_series'],
                                  'message': 'Hóa đơn '+source['invoice_series']+' / '+source['invoice_number']+' đã ký trên M-Invoice. Đang đối chiếu lượng với đơn gốc; không gửi lại bảng kê này.'}
    return result
