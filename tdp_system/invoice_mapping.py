"""Direction-scoped, explicitly confirmed invoice line mappings."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from flask import jsonify, request


INPUT_INVOICE = "INPUT_ELECTRONIC_INVOICE"
OUTPUT_INVOICE = "OUTPUT_ELECTRONIC_INVOICE"
INPUT_MAPPING_SOURCE = "msmi"


class InvoiceMappingError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"\s+", " ", text)


def _scope_key(source_code: Any, source_name: Any, source_unit: Any) -> str:
    values = (_normalized(source_code), _normalized(source_name), _normalized(source_unit))
    if not values[0] and not values[1]:
        raise InvoiceMappingError(
            "Dòng nguồn thiếu cả mã và tên nên không thể ghi nhớ mapping an toàn",
            code="missing_source_identity",
        )
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()


def _direction(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in {"input", INPUT_INVOICE.casefold()}:
        return "input"
    if normalized in {"output", OUTPUT_INVOICE.casefold()}:
        return "output"
    raise InvoiceMappingError("Chiều hóa đơn không hợp lệ")


def _line_context(conn, direction: str, item_id: int):
    if direction == "input":
        return conn.execute(
            """SELECT li.*,i.id invoice_id,i.tenant,i.invoice_type,
                      COALESCE(i.seller_tax_code,'') partner_key,
                      i.receipt_status parent_status,i.sync_status parent_sync_status,i.invoice_date,
                      ? mapping_source
               FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
               WHERE li.id=?""",
            (INPUT_MAPPING_SOURCE, item_id),
        ).fetchone()
    return conn.execute(
        """SELECT li.*,i.id invoice_id,i.tenant,? invoice_type,
                  COALESCE(i.buyer_tax_code,'') partner_key,
                  i.stock_status parent_status,i.sync_status parent_sync_status,
                  i.source_status_class,i.invoice_date,i.source mapping_source
           FROM outgoing_source_invoice_items li
           JOIN outgoing_source_invoices i ON i.id=li.invoice_id WHERE li.id=?""",
        (OUTPUT_INVOICE, item_id),
    ).fetchone()


def _product(conn, product_code: Any):
    code = str(product_code or "").strip()
    if not code:
        raise InvoiceMappingError("Cần chọn mã hàng TĐP", code="missing_product")
    rows = conn.execute(
        "SELECT code,name,COALESCE(unit,'') unit FROM products WHERE code=? COLLATE NOCASE",
        (code,),
    ).fetchall()
    if len(rows) != 1:
        raise InvoiceMappingError(
            "Mã hàng TĐP không tồn tại hoặc không duy nhất",
            code="product_not_found",
        )
    return rows[0]


def _mapping_status(source_unit: Any, target_unit: Any) -> str:
    source = _normalized(source_unit)
    target = _normalized(target_unit)
    return "confirmed" if source and target and source == target else "unit_review"


def mapping_units_match(source_unit: Any, target_unit: Any) -> bool:
    """Use the same strict unit rule for previews and confirmed mappings."""
    return _mapping_status(source_unit, target_unit) == "confirmed"


def mapping_scope_key(source_code: Any, source_name: Any, source_unit: Any) -> str:
    """Expose the persisted mapping identity without duplicating its normalization."""
    return _scope_key(source_code, source_name, source_unit)


def _stock_values(qty: Any, amount: Any, factor: float | None) -> tuple[float, float]:
    if factor is None:
        return 0.0, 0.0
    try:
        source_qty = Decimal(str(qty or 0))
        source_amount = Decimal(str(amount or 0))
        safe_factor = Decimal(str(factor))
    except (InvalidOperation, ValueError):
        raise InvoiceMappingError("Số lượng/thành tiền nguồn không hợp lệ", code="invalid_source_number") from None
    stock_qty = source_qty * safe_factor
    if not stock_qty.is_finite() or stock_qty < 0:
        raise InvoiceMappingError("Số lượng sau quy đổi không hợp lệ", code="invalid_converted_quantity")
    stock_price = source_amount / stock_qty if stock_qty else Decimal("0")
    quant = Decimal("0.000001")
    return (
        float(stock_qty.quantize(quant, rounding=ROUND_HALF_UP)),
        float(stock_price.quantize(quant, rounding=ROUND_HALF_UP)),
    )


def _update_line_snapshot(conn, table: str, line_id: int, product_code: str, status: str, factor, *, clear_group_choice=True) -> None:
    if clear_group_choice and table == 'msmi_invoice_items' and conn.execute("SELECT 1 FROM sqlite_master WHERE name='invoice_input_group_choices'").fetchone():
        conn.execute('DELETE FROM invoice_input_group_choices WHERE (invoice_id,line_index) IN (SELECT invoice_id,line_index FROM msmi_invoice_items WHERE id=?)',(line_id,))
    row = conn.execute(f"SELECT qty,amount FROM {table} WHERE id=?", (line_id,)).fetchone()
    stock_qty, stock_price = _stock_values(row["qty"], row["amount"], factor) if status == "mapped" else (0, 0)
    conn.execute(
        f"""UPDATE {table} SET product_code=?,mapping_status=?,conversion_factor=?,
                  stock_qty=?,stock_unit_price=? WHERE id=?""",
        (product_code, status, factor, stock_qty, stock_price, line_id),
    )


def _strict_date(value: Any, label: str, *, allow_empty: bool = True) -> str:
    text = str(value or "").strip()
    if not text and allow_empty:
        return ""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise InvoiceMappingError(f"{label} phải là ngày YYYY-MM-DD hợp lệ") from None


def _refresh_input_invoice(conn, invoice_id: int) -> None:
    invoice = conn.execute("SELECT receipt_status FROM msmi_invoices WHERE id=?", (invoice_id,)).fetchone()
    if not invoice or invoice["receipt_status"] in {"posted", "blocked"}:
        return
    counts = conn.execute(
        """SELECT SUM(CASE WHEN inventory_eligible=1 THEN 1 ELSE 0 END) eligible,
                  SUM(CASE WHEN inventory_eligible=1 AND mapping_status='mapped' THEN 1 ELSE 0 END) mapped
           FROM msmi_invoice_items WHERE invoice_id=?""",
        (invoice_id,),
    ).fetchone()
    eligible = int(counts["eligible"] or 0)
    mapped = int(counts["mapped"] or 0)
    status = "not_inventory" if not eligible else "ready" if mapped == eligible else "pending_mapping"
    try:
        from .invoice_expenses import expense_state
    except ImportError:
        from invoice_expenses import expense_state
    if expense_state(conn,invoice_id)[1]:
        status = 'pending_mapping'
    conn.execute("UPDATE msmi_invoices SET receipt_status=? WHERE id=?", (status, invoice_id))


def _refresh_output_invoice(conn, invoice_id: int) -> None:
    invoice = conn.execute(
        "SELECT source_status_class,sync_status,stock_status FROM outgoing_source_invoices WHERE id=?",
        (invoice_id,),
    ).fetchone()
    if not invoice or invoice["stock_status"] in {"posted", "reversal_required", "reversed"}:
        return
    if invoice["source_status_class"] != "issued" or invoice["sync_status"] != "synced":
        conn.execute("UPDATE outgoing_source_invoices SET stock_status='blocked' WHERE id=?", (invoice_id,))
        return
    counts = conn.execute(
        """SELECT SUM(CASE WHEN inventory_eligible=1 THEN 1 ELSE 0 END) eligible,
                  SUM(CASE WHEN inventory_eligible=1 AND mapping_status='mapped' THEN 1 ELSE 0 END) mapped
           FROM outgoing_source_invoice_items WHERE invoice_id=?""",
        (invoice_id,),
    ).fetchone()
    eligible = int(counts["eligible"] or 0)
    mapped = int(counts["mapped"] or 0)
    status = "not_inventory" if not eligible else "ready" if mapped == eligible else "pending_mapping"
    conn.execute("UPDATE outgoing_source_invoices SET stock_status=? WHERE id=?", (status, invoice_id))


def _matching_line_ids(conn, direction: str, context, scope_key: str) -> list[tuple[int, int, str]]:
    if direction == "input":
        rows = conn.execute(
            """SELECT li.id,li.invoice_id,li.source_item_code,li.source_item_name,li.source_unit,
                      i.invoice_date
               FROM msmi_invoice_items li JOIN msmi_invoices i ON i.id=li.invoice_id
               WHERE i.tenant=? AND i.invoice_type=? AND COALESCE(i.seller_tax_code,'')=?
                 AND i.sync_status='synced'
                 AND i.receipt_status NOT IN ('posted','blocked') AND li.inventory_eligible=1""",
            (context["tenant"], INPUT_INVOICE, context["partner_key"]),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT li.id,li.invoice_id,li.source_item_code,li.source_item_name,li.source_unit,
                      i.invoice_date
               FROM outgoing_source_invoice_items li
               JOIN outgoing_source_invoices i ON i.id=li.invoice_id
               WHERE i.tenant=? AND i.source=? AND COALESCE(i.buyer_tax_code,'')=?
                 AND i.sync_status='synced' AND i.source_status_class='issued'
                 AND i.stock_status NOT IN ('posted','reversal_required','reversed') AND li.inventory_eligible=1""",
            (context["tenant"], context["mapping_source"], context["partner_key"]),
        ).fetchall()
    return [
        (int(row["id"]), int(row["invoice_id"]), str(row["invoice_date"] or "")) for row in rows
        if _scope_key(row["source_item_code"], row["source_item_name"], row["source_unit"]) == scope_key
    ]


def _refresh_batches(conn, direction: str, invoice_ids: set[int], now: str) -> None:
    if not invoice_ids:
        return
    placeholders = ",".join("?" for _ in invoice_ids)
    if direction == "input":
        batch_rows = conn.execute(
            f"SELECT DISTINCT batch_id FROM invoice_sync_batch_invoices WHERE invoice_id IN ({placeholders})",
            tuple(sorted(invoice_ids)),
        ).fetchall()
        link_table, invoice_table = "invoice_sync_batch_invoices", "msmi_invoices"
        status_column = "receipt_status"
    else:
        batch_rows = conn.execute(
            f"SELECT DISTINCT batch_id FROM invoice_sync_batch_output_invoices WHERE invoice_id IN ({placeholders})",
            tuple(sorted(invoice_ids)),
        ).fetchall()
        link_table, invoice_table = "invoice_sync_batch_output_invoices", "outgoing_source_invoices"
        status_column = "stock_status"
    for batch_row in batch_rows:
        batch_id = int(batch_row["batch_id"])
        counts = conn.execute(
            f"""SELECT COUNT(*) fetched,
                       SUM(CASE WHEN i.{status_column}='pending_mapping' THEN 1 ELSE 0 END) needs_mapping,
                       SUM(CASE WHEN EXISTS(
                           SELECT 1 FROM {'msmi_invoice_items' if direction == 'input' else 'outgoing_source_invoice_items'} li
                           WHERE li.invoice_id=i.id AND li.mapping_status='unit_review'
                       ) THEN 1 ELSE 0 END) unit_review,
                       SUM(CASE WHEN i.{status_column}='ready' THEN 1 ELSE 0 END) ready,
                       SUM(CASE WHEN i.{status_column}='posted' THEN 1 ELSE 0 END) posted,
                       SUM(CASE WHEN i.sync_status!='synced' OR i.{status_column} IN ('blocked','reversal_required')
                                THEN 1 ELSE 0 END) errors
                FROM {link_table} bi JOIN {invoice_table} i ON i.id=bi.invoice_id
                WHERE bi.batch_id=?""",
            (batch_id,),
        ).fetchone()
        batch = conn.execute(
            "SELECT source_cursor FROM invoice_sync_batches WHERE id=?", (batch_id,)
        ).fetchone()
        try:
            complete = bool(json.loads(batch["source_cursor"] or "{}").get("complete"))
        except (TypeError, ValueError, json.JSONDecodeError):
            complete = False
        values = {key: int(counts[key] or 0) for key in counts.keys()}
        if not complete:
            batch_status = "partial"
        elif values["errors"]:
            batch_status = "quarantined"
        elif values["fetched"] and values["posted"] == values["fetched"]:
            batch_status = "posted"
        elif values["unit_review"] or values["needs_mapping"]:
            batch_status = "needs_mapping"
        else:
            batch_status = "ready"
        conn.execute(
            """UPDATE invoice_sync_batches SET status=?,fetched_count=?,needs_mapping_count=?,
                      unit_review_count=?,ready_count=?,posted_count=?,error_count=?,updated_at=?
               WHERE id=?""",
            (
                batch_status, values["fetched"], values["needs_mapping"], values["unit_review"],
                values["ready"], values["posted"], values["errors"], now, batch_id,
            ),
        )


def refresh_linked_batches(conn, direction: str, invoice_ids: set[int], now: str) -> None:
    _refresh_batches(conn, _direction(direction), invoice_ids, now)


def apply_saved_mappings(conn, direction: str, invoice_id: int) -> int:
    """Restore only exact, direction-scoped mappings after a safe re-sync."""
    safe_direction = _direction(direction)
    if safe_direction == "input":
        invoice = conn.execute(
            """SELECT tenant,COALESCE(seller_tax_code,'') partner_key,invoice_date
               FROM msmi_invoices WHERE id=?""",
            (invoice_id,),
        ).fetchone()
        line_table = "msmi_invoice_items"
        invoice_type = INPUT_INVOICE
        mapping_source = INPUT_MAPPING_SOURCE
    else:
        invoice = conn.execute(
            """SELECT tenant,source mapping_source,
                      COALESCE(buyer_tax_code,'') partner_key,invoice_date,
                      sync_status,stock_status,source_status_class
               FROM outgoing_source_invoices WHERE id=?""",
            (invoice_id,),
        ).fetchone()
        line_table = "outgoing_source_invoice_items"
        invoice_type = OUTPUT_INVOICE
    if not invoice:
        return 0
    if safe_direction == "output":
        if (invoice["sync_status"] != "synced" or invoice["source_status_class"] != "issued"
                or invoice["stock_status"] in {"posted", "reversal_required", "reversed"}):
            return 0
        mapping_source = invoice["mapping_source"]
    applied = 0
    rows = conn.execute(
        f"SELECT * FROM {line_table} WHERE invoice_id=? AND inventory_eligible=1",
        (invoice_id,),
    ).fetchall()
    for row in rows:
        if safe_direction == 'input':
            try:
                from invoice_line_groups import restore_group_choice
            except ImportError:
                from .invoice_line_groups import restore_group_choice
            if restore_group_choice(conn, row):
                applied += 1
                continue
        scope = _scope_key(row["source_item_code"], row["source_item_name"], row["source_unit"])
        mappings = conn.execute(
            """SELECT m.* FROM invoice_line_mappings m JOIN products p ON p.code=m.product_code
               WHERE m.tenant=? AND m.source=? AND m.invoice_type=?
                 AND m.partner_key=? AND m.scope_key=?
                 AND (m.effective_from='' OR m.effective_from<=?)
                 AND (m.effective_to='' OR m.effective_to>=?)
               ORDER BY m.effective_from DESC,m.id DESC""",
            (
                invoice["tenant"], mapping_source, invoice_type, invoice["partner_key"], scope,
                invoice["invoice_date"], invoice["invoice_date"],
            ),
        ).fetchall()
        if len(mappings) != 1:
            continue
        mapping = mappings[0]
        line_status = "mapped" if mapping["mapping_status"] == "confirmed" else "unit_review"
        factor = float(mapping["conversion_factor"]) if line_status == "mapped" else None
        _update_line_snapshot(
            conn, line_table, row["id"], mapping["product_code"], line_status, factor
        )
        applied += 1
    if safe_direction == "input":
        _refresh_input_invoice(conn, invoice_id)
    else:
        _refresh_output_invoice(conn, invoice_id)
    return applied


def validated_input_stock_snapshot(conn, item_id: int) -> dict[str, Any]:
    """Return a current, reconciled input stock snapshot or fail closed."""
    context = _line_context(conn, "input", int(item_id))
    if not context or not context["inventory_eligible"]:
        raise InvoiceMappingError("Dòng hóa đơn không đủ điều kiện ghi kho", code="not_inventory")
    if context["mapping_status"] != "mapped" or not context["product_code"]:
        raise InvoiceMappingError("Dòng hóa đơn chưa ghép mã hoặc chưa quy đổi xong", code="mapping_incomplete")
    scope = _scope_key(
        context["source_item_code"], context["source_item_name"], context["source_unit"]
    )
    rows = conn.execute(
        """SELECT m.* FROM invoice_line_mappings m JOIN products p ON p.code=m.product_code
           WHERE m.tenant=? AND m.source=? AND m.invoice_type=?
             AND m.partner_key=? AND m.scope_key=? AND m.mapping_status='confirmed'
             AND (m.effective_from='' OR m.effective_from<=?)
             AND (m.effective_to='' OR m.effective_to>=?)
           ORDER BY m.effective_from DESC,m.id DESC""",
        (
            context["tenant"], context["mapping_source"], INPUT_INVOICE,
            context["partner_key"], scope,
            context["invoice_date"], context["invoice_date"],
        ),
    ).fetchall()
    try:
        from invoice_line_groups import selected_stock_mapping, GroupError
    except ImportError:
        from .invoice_line_groups import selected_stock_mapping, GroupError
    try:
        selected = selected_stock_mapping(conn, item_id)
    except GroupError as error:
        raise InvoiceMappingError(str(error), code='stale_conversion_snapshot') from None
    if selected:
        rows = [selected]
    if len(rows) != 1:
        raise InvoiceMappingError(
            "Mapping/quy đổi của dòng không còn duy nhất ở ngày hóa đơn",
            code="mapping_conflict",
        )
    mapping = rows[0]
    factor = float(mapping["conversion_factor"] or 0)
    if not math.isfinite(factor) or factor <= 0:
        raise InvoiceMappingError("Mapping chưa có hệ số quy đổi hợp lệ", code="conversion_missing")
    expected_qty, expected_price = _stock_values(context["qty"], context["amount"], factor)
    if (
        context["product_code"] != mapping["product_code"]
        or abs(float(context["conversion_factor"] or 0) - factor) > 1e-9
        or abs(float(context["stock_qty"] or 0) - expected_qty) > 1e-6
        or abs(float(context["stock_unit_price"] or 0) - expected_price) > 1e-6
    ):
        raise InvoiceMappingError(
            "Snapshot quy đổi của dòng đã cũ; hãy xác nhận lại trước khi ghi kho",
            code="stale_conversion_snapshot",
        )
    if expected_qty <= 0 or expected_price < 0:
        raise InvoiceMappingError("Số lượng/giá kho sau quy đổi không hợp lệ", code="invalid_stock_snapshot")
    revision = conn.execute(
        """SELECT id FROM invoice_mapping_revisions
           WHERE mapping_id=? AND product_code=? AND conversion_factor=?
             AND effective_from=? AND effective_to=? ORDER BY id DESC LIMIT 1""",
        (
            mapping["id"], mapping["product_code"], factor,
            mapping["effective_from"], mapping["effective_to"],
        ),
    ).fetchone()
    if not revision:
        raise InvoiceMappingError("Mapping thiếu revision audit", code="mapping_revision_missing")
    return {
        "item_id": int(item_id),
        "line_index": int(context["line_index"]),
        "product_code": mapping["product_code"],
        "conversion_factor": factor,
        "stock_qty": expected_qty,
        "stock_unit_price": expected_price,
        "amount": float(context["amount"] or 0),
        "mapping_id": int(mapping["id"]),
        "mapping_revision_id": int(revision["id"]),
    }


def validated_output_stock_snapshot(conn, item_id: int) -> dict[str, Any]:
    context = _line_context(conn, "output", int(item_id))
    if not context or not context["inventory_eligible"]:
        raise InvoiceMappingError("Dòng hóa đơn không đủ điều kiện ghi kho", code="not_inventory")
    if context["mapping_status"] != "mapped" or not context["product_code"]:
        raise InvoiceMappingError("Dòng đầu ra chưa ghép mã hoặc chưa quy đổi xong", code="mapping_incomplete")
    scope = _scope_key(
        context["source_item_code"], context["source_item_name"], context["source_unit"]
    )
    rows = conn.execute(
        """SELECT m.* FROM invoice_line_mappings m JOIN products p ON p.code=m.product_code
           WHERE m.tenant=? AND m.source=? AND m.invoice_type=?
             AND m.partner_key=? AND m.scope_key=? AND m.mapping_status='confirmed'
             AND (m.effective_from='' OR m.effective_from<=?)
             AND (m.effective_to='' OR m.effective_to>=?)
           ORDER BY m.effective_from DESC,m.id DESC""",
        (
            context["tenant"], context["mapping_source"], OUTPUT_INVOICE,
            context["partner_key"], scope,
            context["invoice_date"], context["invoice_date"],
        ),
    ).fetchall()
    if len(rows) != 1:
        raise InvoiceMappingError(
            "Mapping/quy đổi đầu ra không còn duy nhất ở ngày hóa đơn",
            code="mapping_conflict",
        )
    mapping = rows[0]
    factor = float(mapping["conversion_factor"] or 0)
    expected_qty, expected_price = _stock_values(context["qty"], context["amount"], factor)
    if (
        not math.isfinite(factor)
        or factor <= 0
        or context["product_code"] != mapping["product_code"]
        or abs(float(context["conversion_factor"] or 0) - factor) > 1e-9
        or abs(float(context["stock_qty"] or 0) - expected_qty) > 1e-6
        or abs(float(context["stock_unit_price"] or 0) - expected_price) > 1e-6
        or expected_qty <= 0
    ):
        raise InvoiceMappingError(
            "Snapshot quy đổi đầu ra đã cũ hoặc không hợp lệ",
            code="stale_conversion_snapshot",
        )
    revision = conn.execute(
        """SELECT id FROM invoice_mapping_revisions
           WHERE mapping_id=? AND product_code=? AND conversion_factor=?
             AND effective_from=? AND effective_to=? ORDER BY id DESC LIMIT 1""",
        (
            mapping["id"], mapping["product_code"], factor,
            mapping["effective_from"], mapping["effective_to"],
        ),
    ).fetchone()
    if not revision:
        raise InvoiceMappingError("Mapping đầu ra thiếu revision audit", code="mapping_revision_missing")
    return {
        "item_id": int(item_id),
        "line_index": int(context["line_index"]),
        "product_code": mapping["product_code"],
        "conversion_factor": factor,
        "stock_qty": expected_qty,
        "stock_unit_price": expected_price,
        "amount": float(context["amount"] or 0),
        "mapping_id": int(mapping["id"]),
        "mapping_revision_id": int(revision["id"]),
    }


def _record_revision(conn, mapping, now: str) -> None:
    factor = float(mapping["conversion_factor"] or 1)
    revision_key = hashlib.sha256("\0".join((
        str(mapping["id"]), str(mapping["product_code"]), str(mapping["source_unit"]),
        str(mapping["target_unit"]), f"{factor:.12g}", str(mapping["effective_from"]),
        str(mapping["effective_to"]), now,
    )).encode("utf-8")).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO invoice_mapping_revisions(
               revision_key,mapping_id,product_code,source_unit,target_unit,conversion_factor,
               effective_from,effective_to,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            revision_key, mapping["id"], mapping["product_code"], mapping["source_unit"],
            mapping["target_unit"], factor, mapping["effective_from"], mapping["effective_to"], now,
        ),
    )


def _check_expected(context, expected):
    if expected is None:
        return
    keys = ('product_code', 'mapping_status', 'conversion_factor', 'source_unit', 'qty', 'amount')
    if not isinstance(expected, dict) or any(k not in expected or expected[k] != context[k] for k in keys):
        raise InvoiceMappingError('Dòng đã được thay đổi từ lần bạn mở bảng. Hãy đọc lại trước khi sửa.',
                                  code='mapping_stale', status=409)


def _active_mappings(conn, context, scope):
    return conn.execute(
        """SELECT * FROM invoice_line_mappings WHERE tenant=? AND source=? AND invoice_type=?
           AND partner_key=? AND scope_key=? AND (effective_from='' OR effective_from<=?)
           AND (effective_to='' OR effective_to>=?) ORDER BY effective_from DESC,id DESC""",
        (context['tenant'], context['mapping_source'], context['invoice_type'], context['partner_key'],
         scope, context['invoice_date'], context['invoice_date']),
    ).fetchall()


def save_mapping(
    conn,
    *,
    direction: Any,
    item_id: int,
    product_code: Any,
    now_iso,
    expected=None,
) -> dict[str, Any]:
    safe_direction = _direction(direction)
    try:
        safe_item_id = int(item_id)
    except (TypeError, ValueError):
        raise InvoiceMappingError("Mã dòng hóa đơn không hợp lệ") from None
    context = _line_context(conn, safe_direction, safe_item_id)
    if not context:
        raise InvoiceMappingError("Không tìm thấy dòng hóa đơn", code="not_found", status=404)
    if not context["inventory_eligible"]:
        raise InvoiceMappingError(
            "Dòng điều chỉnh/dịch vụ không ảnh hưởng kho nên không được ghép mã",
            code="not_inventory",
            status=409,
        )
    if safe_direction == "output" and context["mapping_source"] != "minvoice":
        raise InvoiceMappingError("Dữ liệu kết nối cũ chỉ được xem trong lịch sử", code="archived_source", status=409)
    if context["parent_sync_status"] != "synced":
        raise InvoiceMappingError(
            "Nguồn hóa đơn đang lỗi hoặc đã thay đổi; cần đồng bộ và đối chiếu trước khi ghép mã",
            code="source_not_safe",
            status=409,
        )
    if safe_direction == "output" and context["source_status_class"] != "issued":
        raise InvoiceMappingError(
            "Chỉ hóa đơn đầu ra đã phát hành hợp lệ mới được ghép mã kho",
            code="source_not_issued",
            status=409,
        )
    if context["parent_status"] in {"posted", "reversal_required", "reversed"}:
        raise InvoiceMappingError(
            "Hóa đơn đã ghi kho hoặc đang chờ hoàn tác xuất kho; không được đổi ghép mã",
            code="frozen",
            status=409,
        )
    product = _product(conn, product_code)
    _check_expected(context, expected)
    scope = _scope_key(
        context["source_item_code"], context["source_item_name"], context["source_unit"]
    )
    mapping_status = _mapping_status(context["source_unit"], product["unit"])
    factor = 1.0 if mapping_status == "confirmed" else None
    existing = _active_mappings(conn, context, scope)
    if len(existing) > 1:
        raise InvoiceMappingError('Có nhiều quy tắc cùng hiệu lực; cần đối chiếu trước khi sửa mã.', code='mapping_conflict', status=409)
    if not existing and conn.execute(
        'SELECT 1 FROM invoice_line_mappings WHERE tenant=? AND source=? AND invoice_type=? AND partner_key=? AND scope_key=?',
        (context['tenant'], context['mapping_source'], context['invoice_type'], context['partner_key'], scope),
    ).fetchone():
        raise InvoiceMappingError('Mặt hàng đã có quy tắc ở kỳ khác. Cần đối chiếu kỳ hiệu lực trước khi ghép dòng này.', code='mapping_period_conflict', status=409)
    date_from = existing[0]['effective_from'] if existing else ''
    date_to = existing[0]['effective_to'] if existing else ''
    # Re-saving the current code must not discard an already confirmed factor.
    if existing and existing[0]['product_code'] == product['code'] and existing[0]['target_unit'] == product['unit']:
        mapping_status = existing[0]['mapping_status']
        factor = existing[0]['conversion_factor']
    timestamp = now_iso()
    conn.execute(
        """INSERT INTO invoice_line_mappings(
               tenant,source,invoice_type,partner_key,scope_key,source_item_code,
               source_item_name,source_unit,product_code,target_unit,mapping_status,
               conversion_factor,effective_from,effective_to,confirmed_at,updated_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(tenant,source,invoice_type,partner_key,scope_key,effective_from) DO UPDATE SET
               product_code=excluded.product_code,target_unit=excluded.target_unit,
               mapping_status=excluded.mapping_status,conversion_factor=excluded.conversion_factor,
               effective_to=excluded.effective_to,
               confirmed_at=excluded.confirmed_at,updated_at=excluded.updated_at""",
        (
            context["tenant"], context["mapping_source"], context["invoice_type"],
            context["partner_key"], scope,
            str(context["source_item_code"] or ""), str(context["source_item_name"] or ""),
            str(context["source_unit"] or ""), product["code"], product["unit"],
            mapping_status, factor, date_from, date_to, timestamp, timestamp,
        ),
    )
    mapping = conn.execute(
        """SELECT * FROM invoice_line_mappings WHERE tenant=? AND source=?
           AND invoice_type=? AND partner_key=? AND scope_key=? AND effective_from=?""",
        (
            context["tenant"], context["mapping_source"], context["invoice_type"],
            context["partner_key"], scope, date_from,
        ),
    ).fetchone()
    if factor is not None:
        _record_revision(conn, mapping, timestamp)
    matching = _matching_line_ids(conn, safe_direction, context, scope)
    matching = [(line_id, invoice_id, day) for line_id, invoice_id, day in matching
                if (not date_from or day >= date_from) and (not date_to or day <= date_to)]
    line_status = "mapped" if mapping_status == "confirmed" else "unit_review"
    if safe_direction == "input":
        line_table = "msmi_invoice_items"
    else:
        line_table = "outgoing_source_invoice_items"
    affected_invoices: set[int] = set()
    for line_id, invoice_id, _invoice_date in matching:
        _update_line_snapshot(conn, line_table, line_id, product["code"], line_status, factor)
        affected_invoices.add(invoice_id)
    for invoice_id in affected_invoices:
        if safe_direction == "input":
            _refresh_input_invoice(conn, invoice_id)
        else:
            _refresh_output_invoice(conn, invoice_id)
    _refresh_batches(conn, safe_direction, affected_invoices, timestamp)
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone():
        conn.execute(
            """INSERT INTO audit_log(
                   event_type,entity_type,entity_id,status,message,metadata_json,created_at
               ) VALUES('invoice_mapping.confirm','invoice_line_mapping',?,'ok','',?,?)""",
            (
                scope,
                json.dumps({
                    "direction": safe_direction,
                    "invoice_type": context["invoice_type"],
                    "product_code": product["code"],
                    "mapping_status": mapping_status,
                    "applied_lines": len(matching),
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                timestamp,
            ),
        )
    return {
        "direction": safe_direction,
        "item_id": safe_item_id,
        "product_code": product["code"],
        "product_name": product["name"],
        "source_unit": str(context["source_unit"] or ""),
        "target_unit": product["unit"],
        "mapping_status": mapping_status,
        "requires_unit_conversion": mapping_status == "unit_review",
        "applied_lines": len(matching),
    }


def save_conversion(
    conn,
    *,
    direction: Any,
    item_id: int,
    conversion_factor: Any,
    effective_from: Any = None,
    effective_to: Any = None,
    now_iso,
    expected=None,
) -> dict[str, Any]:
    safe_direction = _direction(direction)
    context = _line_context(conn, safe_direction, int(item_id))
    if not context:
        raise InvoiceMappingError("Không tìm thấy dòng hóa đơn", code="not_found", status=404)
    if not context["inventory_eligible"]:
        raise InvoiceMappingError("Dòng này không ảnh hưởng kho", code="not_inventory", status=409)
    if safe_direction == "output" and context["mapping_source"] != "minvoice":
        raise InvoiceMappingError("Dữ liệu kết nối cũ chỉ được xem trong lịch sử", code="archived_source", status=409)
    if context["parent_sync_status"] != "synced":
        raise InvoiceMappingError(
            "Nguồn hóa đơn đang lỗi hoặc đã thay đổi; cần đồng bộ và đối chiếu trước khi quy đổi",
            code="source_not_safe",
            status=409,
        )
    if safe_direction == "output" and context["source_status_class"] != "issued":
        raise InvoiceMappingError(
            "Chỉ hóa đơn đầu ra đã phát hành hợp lệ mới được quy đổi đơn vị kho",
            code="source_not_issued",
            status=409,
        )
    if context["parent_status"] in {"posted", "reversal_required", "reversed"}:
        raise InvoiceMappingError(
            "Hóa đơn đã ghi kho hoặc đang chờ hoàn tác xuất kho; không được đổi quy đổi",
            code="frozen",
            status=409,
        )
    try:
        factor = float(conversion_factor)
    except (TypeError, ValueError):
        raise InvoiceMappingError("Hệ số quy đổi phải là số dương") from None
    if not math.isfinite(factor) or factor <= 0 or factor > 1_000_000_000:
        raise InvoiceMappingError("Hệ số quy đổi phải lớn hơn 0 và trong giới hạn an toàn")
    _check_expected(context, expected)
    if safe_direction == 'input':
        try:
            from invoice_line_groups import edit_selected_conversion, GroupError
        except ImportError:
            from .invoice_line_groups import edit_selected_conversion, GroupError
        try:
            selected_result = edit_selected_conversion(conn, int(item_id), factor, now_iso())
        except GroupError as error:
            raise InvoiceMappingError(str(error), code='stale_conversion_snapshot', status=409) from None
        if selected_result:
            return selected_result
    active = _active_mappings(conn, context, _scope_key(context['source_item_code'], context['source_item_name'], context['source_unit']))
    if len(active) != 1:
        raise InvoiceMappingError('Không có đúng một quy tắc hiệu lực; hãy kiểm tra lại mã hàng.', code='mapping_conflict' if active else 'mapping_missing', status=409)
    date_from = _strict_date(active[0]['effective_from'] if effective_from is None else effective_from, "Ngày hiệu lực từ")
    date_to = _strict_date(active[0]['effective_to'] if effective_to is None else effective_to, "Ngày hiệu lực đến")
    if date_from and date_to and date_from > date_to:
        raise InvoiceMappingError("Ngày hiệu lực từ không được lớn hơn ngày hiệu lực đến")
    invoice_date = str(context["invoice_date"] or "")
    if (date_from and invoice_date < date_from) or (date_to and invoice_date > date_to):
        raise InvoiceMappingError("Khoảng hiệu lực phải bao gồm hóa đơn đang quy đổi")

    scope = _scope_key(
        context["source_item_code"], context["source_item_name"], context["source_unit"]
    )
    mappings = conn.execute(
        """SELECT m.* FROM invoice_line_mappings m
           WHERE m.tenant=? AND m.source=? AND m.invoice_type=?
             AND m.partner_key=? AND m.scope_key=?
             AND (m.effective_from='' OR m.effective_from<=?)
             AND (m.effective_to='' OR m.effective_to>=?)
           ORDER BY m.effective_from DESC,m.id DESC""",
        (
            context["tenant"], context["mapping_source"], context["invoice_type"],
            context["partner_key"], scope,
            invoice_date, invoice_date,
        ),
    ).fetchall()
    if len(mappings) != 1:
        raise InvoiceMappingError(
            "Không có đúng một mapping mã để gắn quy đổi; hãy chốt lại mã hàng trước",
            code="mapping_conflict" if mappings else "mapping_missing",
            status=409,
        )
    mapping = mappings[0]
    timestamp = now_iso()
    try:
        conn.execute(
            """UPDATE invoice_line_mappings SET mapping_status='confirmed',conversion_factor=?,
                      effective_from=?,effective_to=?,confirmed_at=?,updated_at=? WHERE id=?""",
            (factor, date_from, date_to, timestamp, timestamp, mapping["id"]),
        )
    except Exception as error:
        if error.__class__.__name__ == "IntegrityError":
            raise InvoiceMappingError(
                "Khoảng hiệu lực quy đổi xung đột với mapping đã có",
                code="mapping_conflict",
                status=409,
            ) from None
        raise
    updated_mapping = conn.execute(
        "SELECT * FROM invoice_line_mappings WHERE id=?", (mapping["id"],)
    ).fetchone()
    _record_revision(conn, updated_mapping, timestamp)

    matching = _matching_line_ids(conn, safe_direction, context, scope)
    line_table = "msmi_invoice_items" if safe_direction == "input" else "outgoing_source_invoice_items"
    affected_invoices: set[int] = set()
    applied = 0
    for line_id, invoice_id, candidate_date in matching:
        in_period = (not date_from or candidate_date >= date_from) and (
            not date_to or candidate_date <= date_to
        )
        if in_period:
            _update_line_snapshot(
                conn, line_table, line_id, mapping["product_code"], "mapped", factor
            )
            applied += 1
        elif effective_from is not None or effective_to is not None:
            current = conn.execute(
                f"SELECT product_code,mapping_status FROM {line_table} WHERE id=?", (line_id,)
            ).fetchone()
            if current["product_code"] == mapping["product_code"]:
                conn.execute(
                    f"""UPDATE {line_table} SET product_code='',mapping_status='unmapped',
                              conversion_factor=NULL,stock_qty=0,stock_unit_price=0 WHERE id=?""",
                    (line_id,),
                )
        if in_period or effective_from is not None or effective_to is not None:
            affected_invoices.add(invoice_id)
    for invoice_id in affected_invoices:
        if safe_direction == "input":
            _refresh_input_invoice(conn, invoice_id)
        else:
            _refresh_output_invoice(conn, invoice_id)
    _refresh_batches(conn, safe_direction, affected_invoices, timestamp)
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone():
        conn.execute(
            """INSERT INTO audit_log(
                   event_type,entity_type,entity_id,status,message,metadata_json,created_at
               ) VALUES('invoice_mapping.conversion','invoice_line_mapping',?,'ok','',?,?)""",
            (
                str(mapping["id"]),
                json.dumps({
                    "direction": safe_direction,
                    "product_code": mapping["product_code"],
                    "source_unit": mapping["source_unit"],
                    "target_unit": mapping["target_unit"],
                    "conversion_factor": factor,
                    "effective_from": date_from,
                    "effective_to": date_to,
                    "applied_lines": applied,
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                timestamp,
            ),
        )
    current_line = conn.execute(
        f"SELECT stock_qty,stock_unit_price FROM {line_table} WHERE id=?", (int(item_id),)
    ).fetchone()
    return {
        "direction": safe_direction,
        "item_id": int(item_id),
        "product_code": mapping["product_code"],
        "source_unit": mapping["source_unit"],
        "target_unit": mapping["target_unit"],
        "conversion_factor": factor,
        "effective_from": date_from,
        "effective_to": date_to,
        "stock_qty": current_line["stock_qty"],
        "stock_unit_price": current_line["stock_unit_price"],
        "applied_lines": applied,
    }


def register_invoice_mapping_routes(app, ctx) -> None:
    db_factory = ctx["db"]
    now_iso = ctx["now_iso"]

    @app.put("/api/invoice-workbench/items/<direction>/<int:item_id>/mapping")
    def api_save_invoice_mapping(direction: str, item_id: int):
        body = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = save_mapping(
                    conn,
                    direction=direction,
                    item_id=item_id,
                    product_code=body.get("product_code"),
                    now_iso=now_iso,
                    expected=body.get('expected'),
                )
                # A standalone row can confirm its code and unit conversion together.
                # Both writes share the lock/transaction, so a rejected factor cannot
                # leave a partially saved mapping or propagate it to other invoices.
                if 'conversion_factor' in body:
                    converted = save_conversion(
                        conn, direction=direction, item_id=item_id,
                        conversion_factor=body['conversion_factor'], now_iso=now_iso,
                    )
                    result.update(converted)
                    result.update(mapping_status='confirmed', requires_unit_conversion=False)
                return jsonify({"ok": True, **result})
        except InvoiceMappingError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.put("/api/invoice-workbench/items/<direction>/<int:item_id>/conversion")
    def api_save_invoice_conversion(direction: str, item_id: int):
        body = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = save_conversion(
                    conn,
                    direction=direction,
                    item_id=item_id,
                    conversion_factor=body.get("conversion_factor"),
                    effective_from=body.get("effective_from"),
                    effective_to=body.get("effective_to"),
                    now_iso=now_iso,
                    expected=body.get('expected'),
                )
                return jsonify({"ok": True, **result})
        except InvoiceMappingError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status
