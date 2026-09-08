"""Synthetic amount hold with a controllable read-only source. No external connectors."""
import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace
from . import server
from .test_minvoice_portal import document
from .minvoice_portal import normalize_portal_document
from .invoice_output_sync import upsert_output_invoice
from .invoice_mapping import save_mapping
from waitress import serve

server.init_database(sync_master=False)
raw = document(); raw.update(totalAmountWithoutVAT=120000, totalAmount=128000)
raw['invoiceDetail'][0]['productName'] = 'Hàng kiểm thử <an toàn>'
mode = {'fixed': False}
with server.db() as conn:
    conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax) VALUES('A', ?, 'Kg', '8%')", (raw['invoiceDetail'][0]['productName'],))
    iid = upsert_output_invoice(conn, normalize_portal_document(raw), tenant='TDP', now=server.now_iso(),
                               status_map={}, status_fields=(), reference_fields=())[0]
    item = conn.execute('SELECT id FROM outgoing_source_invoice_items WHERE invoice_id=?', (iid,)).fetchone()[0]
    save_mapping(conn, direction='output', item_id=item, product_code='A', now_iso=server.now_iso)

def source(**kwargs):
    data = deepcopy(raw)
    if mode['fixed']: data.update(totalAmountWithoutVAT=100000, totalAmount=108000)
    return normalize_portal_document(data)

server.app.config['MINVOICE_CLIENT_FACTORY'] = lambda: SimpleNamespace(get_outgoing_invoice=source)

@server.app.post('/fixture/fix-source')
def fix_source():
    mode['fixed'] = True
    return {'ok': True}

@server.app.get('/fixture/snapshot')
def snapshot():
    with server.db() as conn:
        tables = ('outgoing_source_invoices','outgoing_source_invoice_items','invoice_line_mappings',
                  'invoice_inventory_ledger','inventory_transactions','orders')
        data = {t: [tuple(r) for r in conn.execute('SELECT * FROM ' + t)] for t in tables}
        return {t: hashlib.sha256(json.dumps(rows).encode()).hexdigest() for t, rows in data.items()}

print('AMOUNT_REVIEW_FIXTURE_READY', flush=True)
serve(server.app, host='127.0.0.1', port=18855, threads=4)
