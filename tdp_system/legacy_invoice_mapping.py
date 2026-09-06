"""Preview exact mappings from a customer old-system input-invoice report."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from typing import Any

try:
    from invoice_mapping import mapping_scope_key, mapping_units_match
    from invoice_workbench import validate_date_range
except ImportError:  # pragma: no cover - package invocation
    from .invoice_mapping import mapping_scope_key, mapping_units_match
    from .invoice_workbench import validate_date_range


MAX_ROWS = 10_000
HEADER_ALIASES = {
    "description": {"diengiai", "tenhang", "tenhanghoa"},
    "product_code": {"mavt", "mavattu", "mahang", "mahanghoa"},
    "unit": {"dvt", "donvitinh"},
    "qty": {"soluong"},
    "amount": {"thanhtien"},
    "seller_tax_code": {"madoituong", "masothue", "mst"},
    "invoice_number": {"sohd", "sohoadon"},
}
REQUIRED_FIELDS = frozenset(HEADER_ALIASES)


def _key(value: Any) -> str:
    text = str(value or "").strip().lower().replace("đ", "d")
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "", text)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _description(value: Any) -> str:
    return re.sub(r"^[\s.]+", "", str(value or "")).strip()


def _invoice_number(value: Any) -> str:
    text = _text(value)
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text.lstrip("0") or ("0" if text else "")


def _number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("File phần mềm cũ có số lượng hoặc thành tiền không hợp lệ") from None


def _find_sheet(workbook):
    candidates = []
    for sheet_index, worksheet in enumerate(workbook.worksheets):
        for row_index, row in enumerate(
            worksheet.iter_rows(min_row=1, max_row=30, max_col=40, values_only=True), start=1,
        ):
            fields = {}
            for column, value in enumerate(row, start=1):
                normalized = _key(value)
                for field, aliases in HEADER_ALIASES.items():
                    if field not in fields and normalized in aliases:
                        fields[field] = column
            if REQUIRED_FIELDS.issubset(fields):
                candidates.append((len(fields), -sheet_index, -row_index, worksheet, row_index, fields))
    if not candidates:
        raise ValueError(
            "Không tìm thấy bảng kê có đủ Diễn giải, Mã Vt, Đvt, Số lượng, Thành tiền, Mã đối tượng và Số HĐ"
        )
    _, _, _, worksheet, header_row, fields = max(candidates, key=lambda item: item[:3])
    return worksheet, header_row, fields


def legacy_input_mapping_plan(conn, workbook, *, tenant: str, date_from: str, date_to: str) -> dict:
    """Match only exact invoice identity, line values, valid code and equal units."""
    start, end = validate_date_range(date_from, date_to)
    safe_tenant = str(tenant or "TDP").strip() or "TDP"
    worksheet, header_row, fields = _find_sheet(workbook)
    max_column = max(fields.values())
    legacy_by_invoice = defaultdict(list)
    scanned = 0
    rows_with_code = 0
    for source_row, row in enumerate(
        worksheet.iter_rows(
            min_row=header_row + 1,
            max_row=header_row + MAX_ROWS + 1,
            max_col=max_column,
            values_only=True,
        ),
        start=header_row + 1,
    ):
        values = {field: row[column - 1] for field, column in fields.items()}
        description = _description(values["description"])
        tax_code = _text(values["seller_tax_code"])
        invoice_number = _invoice_number(values["invoice_number"])
        product_code = _text(values["product_code"]).upper()
        if not description and not tax_code and not invoice_number and not product_code:
            continue
        scanned += 1
        if scanned > MAX_ROWS:
            raise ValueError(f"File vượt quá giới hạn {MAX_ROWS:,} dòng dữ liệu")
        if not tax_code or not invoice_number or not description:
            continue
        if product_code:
            rows_with_code += 1
        legacy_by_invoice[(tax_code, invoice_number)].append({
            "source_row": source_row,
            "description_key": _key(description),
            "product_code": product_code,
            "unit": _text(values["unit"]),
            "qty": _number(values["qty"]),
            "amount": _number(values["amount"]),
        })

    products = {
        str(row["code"]).strip().upper(): dict(row)
        for row in conn.execute("SELECT code,name,COALESCE(unit,'') unit FROM products")
    }
    source_rows = conn.execute(
        """SELECT li.id,li.invoice_id,li.source_item_code,li.source_item_name,li.source_unit,
                  li.qty,li.amount,i.seller_tax_code,i.seller_name,i.invoice_number
             FROM msmi_invoice_items li
             JOIN msmi_invoices i ON i.id=li.invoice_id
            WHERE i.tenant=? AND i.invoice_type='INPUT_ELECTRONIC_INVOICE'
              AND i.invoice_date>=? AND i.invoice_date<=? AND i.sync_status='synced'
              AND i.receipt_status NOT IN ('posted','blocked')
              AND li.inventory_eligible=1 AND li.mapping_status!='mapped'
            ORDER BY li.id""",
        (safe_tenant, start, end),
    ).fetchall()

    skipped = defaultdict(int)
    candidates = []
    for source in source_rows:
        invoice_rows = legacy_by_invoice.get((
            _text(source["seller_tax_code"]), _invoice_number(source["invoice_number"]),
        ), [])
        if not invoice_rows:
            skipped["invoice_not_found"] += 1
            continue
        matches = [
            item for item in invoice_rows
            if item["description_key"] == _key(source["source_item_name"])
            and abs(item["qty"] - float(source["qty"] or 0)) <= 0.000001
            and abs(item["amount"] - float(source["amount"] or 0)) <= 1.01
        ]
        if len(matches) != 1:
            skipped["line_not_unique"] += 1
            continue
        legacy = matches[0]
        product = products.get(legacy["product_code"])
        if not product:
            skipped["product_code_missing"] += 1
            continue
        if (
            not mapping_units_match(source["source_unit"], product["unit"])
            or not mapping_units_match(legacy["unit"], product["unit"])
        ):
            skipped["unit_review"] += 1
            continue
        scope = mapping_scope_key(
            source["source_item_code"], source["source_item_name"], source["source_unit"],
        )
        candidates.append({
            "item_id": int(source["id"]),
            "invoice_id": int(source["invoice_id"]),
            "partner_key": _text(source["seller_tax_code"]),
            "seller_name": _text(source["seller_name"]),
            "scope": scope,
            "source_name": _text(source["source_item_name"]),
            "source_unit": _text(source["source_unit"]),
            "product_code": str(product["code"]),
            "product_name": _text(product["name"]),
        })

    codes_by_scope = defaultdict(set)
    for item in candidates:
        codes_by_scope[(item["partner_key"], item["scope"])].add(item["product_code"])
    conflicting_scopes = {key for key, codes in codes_by_scope.items() if len(codes) != 1}
    if conflicting_scopes:
        skipped["mapping_conflict"] += sum(
            (item["partner_key"], item["scope"]) in conflicting_scopes for item in candidates
        )
    safe = [
        item for item in candidates
        if (item["partner_key"], item["scope"]) not in conflicting_scopes
    ]
    safe_line_ids = {item["item_id"] for item in safe}
    representatives = {}
    for item in safe:
        representatives.setdefault((item["partner_key"], item["scope"]), {
            "item_id": item["item_id"], "product_code": item["product_code"],
        })

    affected_line_ids = set()
    if representatives:
        for row in conn.execute(
            """SELECT li.id,li.source_item_code,li.source_item_name,li.source_unit,
                      i.seller_tax_code,i.invoice_date
                 FROM msmi_invoice_items li
                 JOIN msmi_invoices i ON i.id=li.invoice_id
                WHERE i.tenant=? AND i.invoice_type='INPUT_ELECTRONIC_INVOICE'
                  AND i.sync_status='synced' AND i.receipt_status NOT IN ('posted','blocked')
                  AND li.inventory_eligible=1 AND li.mapping_status!='mapped'""",
            (safe_tenant,),
        ):
            scope = mapping_scope_key(row["source_item_code"], row["source_item_name"], row["source_unit"])
            if (_text(row["seller_tax_code"]), scope) in representatives:
                affected_line_ids.add(int(row["id"]))

    affected_line_ids_in_period = {
        int(row["id"])
        for row in conn.execute(
            """SELECT li.id,li.source_item_code,li.source_item_name,li.source_unit,
                      i.seller_tax_code
                 FROM msmi_invoice_items li
                 JOIN msmi_invoices i ON i.id=li.invoice_id
                WHERE i.tenant=? AND i.invoice_type='INPUT_ELECTRONIC_INVOICE'
                  AND i.invoice_date>=? AND i.invoice_date<=? AND i.sync_status='synced'
                  AND i.receipt_status NOT IN ('posted','blocked')
                  AND li.inventory_eligible=1 AND li.mapping_status!='mapped'""",
            (safe_tenant, start, end),
        )
        if (_text(row["seller_tax_code"]), mapping_scope_key(
            row["source_item_code"], row["source_item_name"], row["source_unit"],
        )) in representatives
    } if representatives else set()

    remaining_by_invoice = defaultdict(set)
    for row in source_rows:
        remaining_by_invoice[int(row["invoice_id"])].add(int(row["id"]))
    ready_after = sum(
        bool(ids) and ids.issubset(affected_line_ids_in_period)
        for ids in remaining_by_invoice.values()
    )
    preview_rows = []
    grouped = defaultdict(list)
    for item in safe:
        grouped[(item["partner_key"], item["scope"])].append(item)
    for items in grouped.values():
        item = items[0]
        preview_rows.append({
            "seller_name": item["seller_name"],
            "source_name": item["source_name"],
            "source_unit": item["source_unit"],
            "product_code": item["product_code"],
            "product_name": item["product_name"],
            "line_count_in_period": len(items),
        })
    preview_rows.sort(key=lambda item: (-item["line_count_in_period"], item["seller_name"], item["source_name"]))
    snapshot_data = {
        "tenant": safe_tenant,
        "date_from": start,
        "date_to": end,
        "sheet": worksheet.title,
        "header_row": header_row,
        "rules": sorted((partner, scope, item["product_code"]) for (partner, scope), item in representatives.items()),
        "selected_line_ids": sorted(safe_line_ids),
        "affected_line_ids": sorted(affected_line_ids),
    }
    snapshot = hashlib.sha256(
        json.dumps(snapshot_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "tenant": safe_tenant,
        "date_from": start,
        "date_to": end,
        "sheet": worksheet.title,
        "header_row": header_row,
        "source_lines_in_period": len(source_rows),
        "legacy_invoice_groups": len(legacy_by_invoice),
        "legacy_rows_with_code": rows_with_code,
        "safe_lines_in_period": len(safe_line_ids),
        "safe_rules": len(representatives),
        "invoices_with_safe_lines": len({item["invoice_id"] for item in safe}),
        "invoices_ready_after": ready_after,
        "affected_lines_in_period": len(affected_line_ids_in_period),
        "affected_lines_all_periods": len(affected_line_ids),
        "skipped": dict(skipped),
        "rows": preview_rows,
        "snapshot": snapshot,
        "can_confirm": bool(representatives),
        "_representatives": list(representatives.values()),
    }
