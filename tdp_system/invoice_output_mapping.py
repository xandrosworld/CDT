"""Match outgoing codes, or a missing code's exact name/unit, without posting stock."""
from __future__ import annotations

try:
    from .invoice_mapping import (
        InvoiceMappingError, _line_context, _matching_line_ids, _product,
        mapping_scope_key, save_mapping, _normalized, validated_output_stock_snapshot,
    )
except ImportError:
    from invoice_mapping import (
        InvoiceMappingError, _line_context, _matching_line_ids, _product,
        mapping_scope_key, save_mapping, _normalized, validated_output_stock_snapshot,
    )


def _catalog_names(conn):
    """Names entered in the catalog, including the customer's invoice-name aliases."""
    aliases = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_product_names'").fetchone():
        aliases = {r['product_code']: r['invoice_name'] for r in conn.execute(
            'SELECT product_code,invoice_name FROM outgoing_product_names')}
    names, canonical = {}, {}
    for product in conn.execute('SELECT code,name,unit FROM products'):
        unit = _normalized(product['unit'])
        if not unit:
            continue
        canonical.setdefault((_normalized(product['name']), unit), set()).add(product['code'])
        for name in (product['name'], aliases.get(product['code'], '')):
            key = (_normalized(name), unit)
            if key[0]:
                names.setdefault(key, set()).add(product['code'])
    return canonical, names


def _confirmed_names(conn, tenant, keys):
    """Reuse audited choices across buyers, never fuzzy names or unit conversions.

    Keep conflicting choices in the index so they prevent automatic selection.
    Frozen invoices may provide evidence but are never modified by this action.
    """
    evidence = {}
    if not keys:
        return evidence
    for row in conn.execute(
        "SELECT li.* FROM outgoing_source_invoice_items li JOIN outgoing_source_invoices i "
        "ON i.id=li.invoice_id WHERE i.tenant=? AND i.source='minvoice' "
        "AND i.sync_status='synced' AND i.source_status_class='issued' "
        "AND i.stock_status NOT IN ('reversed','reversal_required','blocked') "
        "AND li.inventory_eligible=1 AND li.mapping_status='mapped' AND li.product_code!=''", (tenant,)
    ).fetchall():
        key = (_normalized(row['source_item_name']), _normalized(row['source_unit']))
        if key not in keys:
            continue
        choices = evidence.setdefault(key, [])
        try:
            snapshot = validated_output_stock_snapshot(conn, row['id'])
            product = _product(conn, snapshot['product_code'])
            if snapshot['conversion_factor'] != 1 or _normalized(product['unit']) != key[1]:
                choices.append(None)
                continue
            rule = conn.execute('SELECT effective_from,effective_to FROM invoice_line_mappings WHERE id=?',
                                (snapshot['mapping_id'],)).fetchone()
            choices.append((product['code'], rule['effective_from'], rule['effective_to']))
        except InvoiceMappingError:
            choices.append(None)  # Stale or conflicting evidence cannot teach a new rule.
    return evidence


def _name_candidate(context, canonical, names, evidence):
    key = (_normalized(context['source_item_name']), _normalized(context['source_unit']))
    history = evidence.get(key, [])
    if any(choice is None for choice in history):
        return None
    codes = {choice[0] for choice in history}
    if len(codes) > 1:
        return None
    exact = canonical.get(key, set())
    if len(exact) > 1:
        return None
    candidates = exact or names.get(key, set())
    if len(candidates) == 1:
        code = next(iter(candidates))
        return code if not codes or codes == {code} else None
    day = context['invoice_date']
    active = {code for code, start, end in history
              if (not start or start <= day) and (not end or day <= end)}
    return next(iter(active)) if len(active) == 1 and (not candidates or active <= candidates) else None


def match_output_catalog_codes(conn, *, tenant, now_iso, invoice_id=None,
                               date_from=None, date_to=None):
    """Caller owns the transaction. Existing choices/rules always take priority."""
    clauses = ["i.tenant=?", "i.source='minvoice'", "i.sync_status='synced'",
               "i.source_status_class='issued'",
               "i.stock_status NOT IN ('posted','reversal_required','reversed','blocked')",
               "li.inventory_eligible=1", "li.mapping_status='unmapped'", "li.product_code=''" ]
    args = [tenant]
    if invoice_id is not None:
        clauses.append("i.id=?")
        args.append(invoice_id)
    if date_from is not None and date_to is not None:
        clauses.append("i.invoice_date BETWEEN ? AND ?")
        args.extend([date_from, date_to])
    if invoice_id is None and (date_from is None or date_to is None):
        raise ValueError("Cần chọn khoảng ngày để đối chiếu mã đầu ra")
    rows = conn.execute(
        "SELECT li.id,li.source_item_code,li.source_item_name,li.source_unit FROM outgoing_source_invoice_items li "
        "JOIN outgoing_source_invoices i ON i.id=li.invoice_id WHERE " + " AND ".join(clauses),
        args,
    ).fetchall()
    matched = 0
    unit_review = 0
    canonical, names = _catalog_names(conn)
    evidence = _confirmed_names(conn, tenant, {
        (_normalized(r['source_item_name']), _normalized(r['source_unit']))
        for r in rows if not str(r['source_item_code'] or '').strip()
    })
    for row in rows:
        context = _line_context(conn, "output", row["id"])
        if context["mapping_status"] != "unmapped" or context["product_code"]:
            continue  # An earlier rule can have matched several lines already.
        scope = mapping_scope_key(context["source_item_code"], context["source_item_name"], context["source_unit"])
        # Do not replace explicit choices, including rules outside this period.
        if conn.execute(
            "SELECT 1 FROM invoice_line_mappings WHERE tenant=? AND source=? "
            "AND invoice_type=? AND partner_key=? AND scope_key=?",
            (tenant, context["mapping_source"], context["invoice_type"], context["partner_key"], scope),
        ).fetchone():
            continue
        try:
            source_code = str(context['source_item_code'] or '').strip()
            if source_code:
                product = _product(conn, source_code)
            else:
                code = _name_candidate(context, canonical, names, evidence)
                if not code:
                    continue
                product = _product(conn, code)
        except InvoiceMappingError as error:
            if error.code in {"missing_product", "product_not_found"}:
                continue
            raise
        matching = _matching_line_ids(conn, "output", context, scope)
        if not source_code and any(
            _name_candidate(dict(context, invoice_date=day), canonical, names, evidence) != product['code']
            for _, _, day in matching
        ):
            continue  # A remembered choice must also cover every affected date.
        if any(conn.execute(
            "SELECT 1 FROM outgoing_source_invoice_items WHERE id=? "
            "AND (product_code!='' OR mapping_status!='unmapped')", (item_id,),
        ).fetchone() for item_id, _, _ in matching):
            continue
        result = save_mapping(conn, direction="output", item_id=row["id"],
                              product_code=product["code"], now_iso=now_iso)
        in_range = sum(1 for _, parent_id, day in matching
                       if (invoice_id is None or parent_id == invoice_id)
                       and (date_from is None or date_from <= day <= date_to))
        matched += in_range
        if result["requires_unit_conversion"]:
            unit_review += in_range
    return {"matched_lines": matched, "unit_review_lines": unit_review}
