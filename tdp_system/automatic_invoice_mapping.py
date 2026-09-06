"""Apply provable input mappings in the caller's write transaction."""
import json


def apply_automatic_input_mappings(conn, *, tenant, date_from, date_to, now_iso, workbook=None):
    try:
        from contract_modules import safe_input_mapping_suggestion_plan
        from legacy_invoice_mapping import legacy_input_mapping_plan
        from invoice_mapping import mapping_scope_key, save_mapping
    except ImportError:
        from .contract_modules import safe_input_mapping_suggestion_plan
        from .legacy_invoice_mapping import legacy_input_mapping_plan
        from .invoice_mapping import mapping_scope_key, save_mapping

    def mapped_count():
        return conn.execute(
            """SELECT COUNT(*) FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
               WHERE i.tenant=? AND i.invoice_type='INPUT_ELECTRONIC_INVOICE'
                 AND i.invoice_date>=? AND i.invoice_date<=?
                 AND li.inventory_eligible=1 AND li.mapping_status='mapped'""",
            (tenant, date_from, date_to),
        ).fetchone()[0]

    # Protect old snapshots even when an older import left no reusable rule.
    protected = set()
    for row in conn.execute(
        """SELECT li.source_item_code,li.source_item_name,li.source_unit,i.seller_tax_code
           FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
           WHERE i.tenant=? AND i.invoice_type='INPUT_ELECTRONIC_INVOICE'
             AND li.inventory_eligible=1 AND li.mapping_status!='unmapped'""", (tenant,),
    ):
        protected.add((str(row["seller_tax_code"] or ""), mapping_scope_key(
            row["source_item_code"], row["source_item_name"], row["source_unit"])))
    before = mapped_count()
    rules = affected = 0
    sources = []
    conn.execute("SAVEPOINT automatic_input_mapping")
    try:
        # The historical file is stronger evidence than a name in the catalog.
        for source in (["legacy", "catalog"] if workbook is not None else ["catalog"]):
            args = dict(tenant=tenant, date_from=date_from, date_to=date_to)
            plan = (legacy_input_mapping_plan(conn, workbook, **args) if source == "legacy"
                    else safe_input_mapping_suggestion_plan(conn, **args))
            source_rules = 0
            for item in plan["_representatives"]:
                row = conn.execute(
                    """SELECT li.*,i.seller_tax_code FROM msmi_invoice_items li
                       JOIN msmi_invoices i ON i.id=li.invoice_id WHERE li.id=?""",
                    (item["item_id"],),
                ).fetchone()
                scope = mapping_scope_key(row["source_item_code"], row["source_item_name"], row["source_unit"])
                # A human's previous choice/conversion has precedence, including
                # dated rules. Automatic catalog matching must never replace it.
                existing = conn.execute(
                    """SELECT 1 FROM invoice_line_mappings WHERE tenant=? AND source='msmi'
                       AND invoice_type='INPUT_ELECTRONIC_INVOICE' AND partner_key=? AND scope_key=?""",
                    (tenant, str(row["seller_tax_code"] or "").strip(), scope),
                ).fetchone()
                if existing or (str(row["seller_tax_code"] or ""), scope) in protected or row["mapping_status"] != "unmapped":
                    continue
                result = save_mapping(conn, direction="input", item_id=item["item_id"],
                                      product_code=item["product_code"], now_iso=now_iso)
                if result["requires_unit_conversion"]:
                    raise ValueError("Đơn vị đã thay đổi; chưa tự ghép mã")
                rules += 1
                source_rules += 1
                affected += result["applied_lines"]
            sources.append({"source": source, "applied_rules": source_rules,
                            "skipped": plan.get("skipped", {})})
        counts = dict(conn.execute(
            """SELECT receipt_status,COUNT(*) FROM msmi_invoices
               WHERE tenant=? AND invoice_type='INPUT_ELECTRONIC_INVOICE'
                 AND invoice_date>=? AND invoice_date<=? GROUP BY receipt_status""",
            (tenant, date_from, date_to),
        ).fetchall())
        result = dict(applied_rules=rules, mapped_lines_in_period=mapped_count() - before,
                      mapped_lines_all_periods=affected, sources=sources,
                      ready_invoices_in_period=counts.get("ready", 0),
                      pending_invoices_in_period=counts.get("pending_mapping", 0), stock_changed=False)
        if rules:
            conn.execute(
                """INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
                   VALUES('msmi.mapping_auto','invoice_period',?,'ok','',?,?)""",
                (f"{date_from}:{date_to}", json.dumps(result, ensure_ascii=False), now_iso()),
            )
        conn.execute("RELEASE automatic_input_mapping")
        return result
    except Exception:
        conn.execute("ROLLBACK TO automatic_input_mapping")
        conn.execute("RELEASE automatic_input_mapping")
        raise
