"""Match outgoing codes, or a missing code's exact name/unit, without posting stock."""
from __future__ import annotations

try:
    from .invoice_mapping import (
        InvoiceMappingError, _line_context, _matching_line_ids, _product,
        mapping_scope_key, save_mapping, _normalized,
    )
except ImportError:
    from invoice_mapping import (
        InvoiceMappingError, _line_context, _matching_line_ids, _product,
        mapping_scope_key, save_mapping, _normalized,
    )


def _catalog_names(conn):
    """Names entered in the catalog, including the customer's invoice-name aliases."""
    aliases = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='outgoing_product_names'").fetchone():
        aliases = {r['product_code']: r['invoice_name'] for r in conn.execute(
            'SELECT product_code,invoice_name FROM outgoing_product_names')}
    names = {}
    for product in conn.execute('SELECT code,name,unit FROM products'):
        unit = _normalized(product['unit'])
        if not unit:
            continue
        for name in (product['name'], aliases.get(product['code'], '')):
            key = (_normalized(name), unit)
            if key[0]:
                names.setdefault(key, set()).add(product['code'])
    return names


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
        "SELECT li.id FROM outgoing_source_invoice_items li "
        "JOIN outgoing_source_invoices i ON i.id=li.invoice_id WHERE " + " AND ".join(clauses),
        args,
    ).fetchall()
    matched = 0
    unit_review = 0
    names = _catalog_names(conn)
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
                candidates = names.get((_normalized(context['source_item_name']),
                                        _normalized(context['source_unit'])), set())
                if len(candidates) != 1:
                    continue
                product = _product(conn, next(iter(candidates)))
        except InvoiceMappingError as error:
            if error.code in {"missing_product", "product_not_found"}:
                continue
            raise
        matching = _matching_line_ids(conn, "output", context, scope)
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
