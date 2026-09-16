"""Operator repair of reviewed, workbook-proven legacy seller import omissions.

No HTTP route or startup migration. The caller supplies a reviewed manifest,
backs up the database, and owns the transaction. Financial rows are immutable.
"""
import hashlib
import json
import re

from . import batch_bk_approval as approval
from .purchase_summary_export import _people_by_name, _resolved_identity, collect_purchase_summary_rows
from .seller_identity_catalog import is_excluded_seller, name_key


def row_hash(row):
    return hashlib.sha256(json.dumps(dict(row), sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def _export_financial_rows(conn, batch, orders):
    rows = collect_purchase_summary_rows(conn, batch, orders.values())
    return sorted((r['source_ref'], r['product_name'], r['unit'], r['quantity'],
                   r['buy_price'], r['amount']) for r in rows)


def repair_order_sellers(conn, corrections, timestamp, audit_event):
    """Fail closed on stale, ambiguous, financial, or seller-exclusion changes."""
    if not conn.in_transaction:
        raise ValueError('Seller repair requires a caller-owned transaction')
    ids = [int(item['id']) for item in corrections]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate order in seller repair')
    people = _people_by_name(conn)
    prepared = []
    batches = {}
    for item in corrections:
        source_hash = item.get('file_hash', '')
        if not re.fullmatch(r'[0-9A-Fa-f]{64}', source_hash):
            raise ValueError('Missing workbook evidence hash')
        row = conn.execute('SELECT * FROM orders WHERE id=?', (item['id'],)).fetchone()
        if row is None or row_hash(row) != item['expected_row_hash']:
            raise ValueError('Order changed since seller review')
        row = dict(row)
        if not row['purchase_list']:
            raise ValueError('Order is not a BK source')
        product = dict(conn.execute('SELECT * FROM products WHERE code=?',
                                   (row['product_code'],)).fetchone())
        old_seller = row['seller'] or product.get('seller') or ''
        if row['seller'] and name_key(row['seller']) != name_key(product.get('seller')):
            raise ValueError('Explicit seller override requires separate review')
        new_seller = item['seller']
        if (not new_seller or name_key(old_seller) == name_key(new_seller)
                or is_excluded_seller(old_seller) or is_excluded_seller(new_seller)):
            raise ValueError('Invalid seller change or changed exclusion scope')
        # Preserve the exact imported reference cell as a second source witness.
        # Some legacy templates put an address in the CCCD column; do not turn
        # that text into an identity. The validated people catalogue below is
        # authoritative for the actual identity/address printed on receipts.
        evidence_identity = str(item.get('source_cccd') or '').strip()
        if not evidence_identity or evidence_identity != str(row['cccd'] or '').strip():
            raise ValueError('Workbook identity does not match imported order')
        _, _, _, issues = _resolved_identity({**row, 'seller': new_seller}, product, people)
        if issues:
            raise ValueError('Replacement seller identity is incomplete or ambiguous')
        prepared.append((item, row, old_seller))
        batches[row['batch_id']] = None
    # Verify every existing posted-document/source link before making changes.
    for batch_id in batches:
        batch = dict(conn.execute('SELECT * FROM batches WHERE id=?', (batch_id,)).fetchone())
        orders = {r['id']: dict(r) for r in conn.execute(
            'SELECT * FROM orders WHERE batch_id=? ORDER BY id', (batch_id,))}
        canonical = [dict(r) for r in conn.execute(
            'SELECT * FROM purchase_workbook_lines WHERE batch_id=? ORDER BY id', (batch_id,))]
        preview = approval.prepare(conn, batch_id)
        batches[batch_id] = (batch, orders, canonical, preview, _export_financial_rows(conn, batch, orders))
    conn.execute('SAVEPOINT seller_import_repair')
    try:
        for item, row, old_seller in prepared:
            conn.execute('UPDATE orders SET seller=?,updated_at=? WHERE id=?',
                         (item['seller'], timestamp, row['id']))
            batches[row['batch_id']][1][row['id']]['seller'] = item['seller']
            audit_event(conn, 'order.seller_import_repair', entity_type='order', entity_id=row['id'],
                        metadata={'old_seller': old_seller, 'new_seller': item['seller'],
                                  'file_hash': item['file_hash'], 'source_row': item['source_row'],
                                  'reason': 'BK seller column omitted by legacy daily workbook importer',
                                  'financial_fields_changed': False})
        for batch_id, (batch, orders, canonical, preview, financial_rows) in batches.items():
            if financial_rows != _export_financial_rows(conn, batch, orders):
                raise ValueError('Seller correction would change BK quantities or money')
            if preview['alreadyPosted']:
                conn.execute('UPDATE batch_bk_approvals SET source_hash=? WHERE batch_id=?',
                             (approval.source_state_hash(batch, orders, canonical), batch_id))
            checked = approval.prepare(conn, batch_id)
            if (checked['rowCount'], checked['amount'], checked['alreadyPosted']) != (
                    preview['rowCount'], preview['amount'], preview['alreadyPosted']):
                raise ValueError('Seller correction would change approval scope')
        conn.execute('RELEASE seller_import_repair')
    except Exception:
        conn.execute('ROLLBACK TO seller_import_repair')
        conn.execute('RELEASE seller_import_repair')
        raise
    return {'corrected_orders': len(prepared), 'batches': sorted(batches),
            'financial_fields_changed': False, 'stock_posted': False}
