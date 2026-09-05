"""Invoice-only scope for official contractor payment documents.

The customer supplied the approved payment-request workbook on 03/09/2026.
This module freezes and reconciles the financial/source scope before the
official request and delivery statement are rendered from literal values.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


SNAPSHOT_FIELDS = (
    "buyer_name_snapshot",
    "buyer_tax_code_snapshot",
    "buyer_address_snapshot",
    "company_name_snapshot",
    "company_tax_code_snapshot",
    "company_address_snapshot",
    "payment_requester_snapshot",
    "payment_bank_name_snapshot",
    "payment_bank_account_snapshot",
)


class InvoicePaymentScopeError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_invoice_payment_scope", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _strict_date(value: Any, label: str) -> str:
    text = _plain(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise InvoicePaymentScopeError(
            f"{label} phải đúng dạng YYYY-MM-DD", code="invalid_date_range", status=400,
        ) from None


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise InvoicePaymentScopeError(f"{label} không hợp lệ")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise InvoicePaymentScopeError(f"{label} không phải số hữu hạn") from None
    if not math.isfinite(result):
        raise InvoicePaymentScopeError(f"{label} không phải số hữu hạn")
    return result


def _vnd(*values: Any) -> int:
    try:
        result = Decimal("1")
        for value in values:
            result *= Decimal(str(value))
        return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        raise InvoicePaymentScopeError("Không thể làm tròn số tiền hóa đơn") from None


def _tax_percent(value: Any) -> float:
    text = _plain(value).upper().replace(" ", "")
    if text in {"", "KKKNT", "KHÔNGKÊKHAI", "KHONGKEKHAI", "-2", "-2.0"}:
        return -2 if text else 0
    if text in {"KCT", "KHÔNGCHỊUTHUẾ", "KHONGCHIUTHUE", "-1", "-1.0"}:
        return -1
    if text.endswith("%"):
        text = text[:-1]
    try:
        result = float(text)
    except ValueError:
        raise InvoicePaymentScopeError("Dòng hóa đơn có thuế suất không hợp lệ") from None
    if 0 < abs(result) < 1:
        result *= 100
    if not math.isfinite(result) or result < 0 or result > 100:
        raise InvoicePaymentScopeError("Dòng hóa đơn có thuế suất không hợp lệ")
    return result


def _table_exists(conn, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,),
    ).fetchone())


def _source_match(conn, draft: dict[str, Any]) -> dict[str, Any] | None:
    if not _table_exists(conn, "outgoing_source_invoices"):
        return None
    rows = [dict(row) for row in conn.execute(
        """SELECT id,source,source_status_class,sync_status,stock_status,
                  invoice_series,invoice_number,invoice_date,subtotal,tax_amount,total_amount,
                  buyer_tax_code,buyer_name,relation_reference,error_message
             FROM outgoing_source_invoices
            WHERE source='minvoice'
              AND UPPER(TRIM(COALESCE(invoice_series,'')))=UPPER(TRIM(?))
              AND TRIM(COALESCE(invoice_number,''))=TRIM(?)
              AND TRIM(COALESCE(invoice_date,''))=TRIM(?)
            ORDER BY id""",
        (
            draft.get("issued_invoice_series") or "",
            draft.get("issued_invoice_number") or "",
            draft.get("issued_invoice_date") or "",
        ),
    )]
    if len(rows) > 1:
        raise InvoicePaymentScopeError(
            "Một định danh hóa đơn khớp nhiều bản nguồn; cần đối chiếu trước khi lập hồ sơ",
            code="invoice_source_identity_conflict",
        )
    return rows[0] if rows else None


def _verify_source(draft: dict[str, Any], source: dict[str, Any] | None) -> dict[str, Any]:
    if source is None:
        return {
            "verification_source": "local_issued_confirmation",
            "source_invoice_id": None,
            "source_status_class": "not_synced",
            "source_stock_status": "not_synced",
        }
    if source["source_status_class"] != "issued" or source["sync_status"] != "synced" or source[
        "stock_status"
    ] in {"blocked", "reversal_required", "reversed"}:
        raise InvoicePaymentScopeError(
            "Hóa đơn nguồn đã hủy/thay thế/điều chỉnh hoặc đang chờ đối chiếu; không được đưa vào đề nghị thanh toán",
            code="invoice_source_not_payable",
        )
    source_tax_code = _plain(source.get("buyer_tax_code")).upper()
    snapshot_tax_code = _plain(draft.get("buyer_tax_code_snapshot")).upper()
    if source_tax_code and snapshot_tax_code and source_tax_code != snapshot_tax_code:
        raise InvoicePaymentScopeError(
            "Mã số thuế bên mua trên hóa đơn nguồn lệch snapshot đã phát hành",
            code="invoice_source_buyer_mismatch",
        )
    local_totals = tuple(_vnd(draft[field]) for field in ("subtotal", "tax_amount", "total_amount"))
    source_totals = tuple(_vnd(source[field]) for field in ("subtotal", "tax_amount", "total_amount"))
    if any(abs(left - right) > 1 for left, right in zip(local_totals, source_totals)):
        raise InvoicePaymentScopeError(
            "Tổng hóa đơn xác nhận cục bộ lệch bản nguồn; cần đối chiếu trước khi lập hồ sơ",
            code="invoice_source_total_mismatch",
        )
    return {
        "verification_source": "synced_issued_source",
        "source_invoice_id": int(source["id"]),
        "source_status_class": source["source_status_class"],
        "source_stock_status": source["stock_status"],
    }


def _verify_lines(drafts: list[dict[str, Any]], lines: list[dict[str, Any]]) -> None:
    totals: dict[int, dict[str, int]] = {
        int(draft["id"]): {"subtotal": 0, "tax": 0, "total": 0} for draft in drafts
    }
    for line in lines:
        draft_id = int(line["draft_id"])
        if draft_id not in totals:
            raise InvoicePaymentScopeError("Dòng giao hàng không thuộc phạm vi hóa đơn đã khóa")
        qty = _number(line.get("qty"), "Số lượng hóa đơn")
        unit_price = _number(line.get("unit_price"), "Đơn giá hóa đơn")
        amount = _vnd(line.get("amount"))
        if qty <= 0 or unit_price < 0 or amount < 0 or _vnd(qty, unit_price) != amount:
            raise InvoicePaymentScopeError(
                "Dòng hóa đơn không thỏa Số lượng × Đơn giá = Thành tiền",
                code="invoice_line_amount_mismatch",
            )
        tax_percent = _tax_percent(line.get("tax"))
        tax_amount = 0 if tax_percent <= 0 else _vnd(amount, tax_percent / 100)
        totals[draft_id]["subtotal"] += amount
        totals[draft_id]["tax"] += tax_amount
        totals[draft_id]["total"] += amount + tax_amount
    mismatches = []
    for draft in drafts:
        calculated = totals[int(draft["id"])]
        expected = {
            "subtotal": _vnd(draft["subtotal"]),
            "tax": _vnd(draft["tax_amount"]),
            "total": _vnd(draft["total_amount"]),
        }
        if any(abs(calculated[key] - expected[key]) > 1 for key in expected):
            mismatches.append(_plain(draft.get("issued_invoice_number")) or str(draft["id"]))
    if mismatches:
        raise InvoicePaymentScopeError(
            "Tổng hóa đơn lệch chi tiết giao hàng: " + ", ".join(mismatches),
            code="invoice_delivery_total_mismatch",
        )


def issued_invoice_payment_scope(
    conn,
    contractor: Any,
    date_from: Any,
    date_to: Any,
) -> dict[str, Any]:
    """Return a reconciled, invoice-only payment scope with explicit provenance."""
    safe_from = _strict_date(date_from, "Từ ngày")
    safe_to = _strict_date(date_to, "Đến ngày")
    if safe_from > safe_to:
        raise InvoicePaymentScopeError(
            "Từ ngày không được sau đến ngày", code="invalid_date_range", status=400,
        )
    party = _plain(contractor).upper()
    if not party:
        raise InvoicePaymentScopeError("Cần mã nhà thầu", code="contractor_required", status=400)
    drafts = [dict(row) for row in conn.execute(
        """SELECT * FROM outgoing_invoice_drafts
            WHERE UPPER(TRIM(contractor))=? AND status='issued'
              AND issued_invoice_date BETWEEN ? AND ?
            ORDER BY issued_invoice_date,issued_invoice_series,issued_invoice_number,id""",
        (party, safe_from, safe_to),
    )]
    if not drafts:
        raise InvoicePaymentScopeError(
            "Không có hóa đơn đã phát hành đủ số/ngày trong kỳ",
            code="issued_invoice_scope_empty",
            status=404,
        )
    for draft in drafts:
        if not _plain(draft.get("issued_invoice_number")) or not _plain(draft.get("issued_invoice_date")):
            raise InvoicePaymentScopeError(
                "Còn hóa đơn chưa ghi đủ số/ngày phát hành",
                code="issued_invoice_identity_incomplete",
            )
        missing = [field for field in SNAPSHOT_FIELDS if not _plain(draft.get(field))]
        if missing:
            raise InvoicePaymentScopeError(
                "Hóa đơn cũ chưa khóa đủ hồ sơ pháp lý/thanh toán; không dùng hồ sơ hiện tại ghi đè lịch sử",
                code="issued_invoice_snapshot_incomplete",
            )
    snapshot_keys = {
        tuple(_plain(draft.get(field)) for field in SNAPSHOT_FIELDS) for draft in drafts
    }
    if len(snapshot_keys) != 1:
        raise InvoicePaymentScopeError(
            "Các hóa đơn trong kỳ thuộc hồ sơ pháp lý/thanh toán khác nhau; hãy xuất tách kỳ",
            code="issued_invoice_snapshot_conflict",
        )

    draft_ids = [int(draft["id"]) for draft in drafts]
    placeholders = ",".join("?" for _ in draft_ids)
    lines = [dict(row) for row in conn.execute(
        f"""SELECT l.*,d.issued_invoice_number,d.issued_invoice_series,d.issued_invoice_date,
                    d.subtotal invoice_subtotal,d.tax_amount invoice_tax_amount,
                    d.total_amount invoice_total,b.work_date,o.kitchen
               FROM outgoing_invoice_lines l
               JOIN outgoing_invoice_drafts d ON d.id=l.draft_id
               JOIN orders o ON o.id=l.order_id
               JOIN batches b ON b.id=o.batch_id
              WHERE l.draft_id IN ({placeholders})
              ORDER BY d.issued_invoice_date,d.id,b.work_date,l.id""",
        tuple(draft_ids),
    )]
    if not lines:
        raise InvoicePaymentScopeError(
            "Hóa đơn đã phát hành không còn dòng giao hàng để đối chiếu",
            code="issued_invoice_lines_missing",
        )
    _verify_lines(drafts, lines)

    invoices = []
    for draft in drafts:
        source = _source_match(conn, draft)
        provenance = _verify_source(draft, source)
        invoices.append({
            "draft_id": int(draft["id"]),
            "invoice_date": draft["issued_invoice_date"],
            "invoice_series": _plain(draft.get("issued_invoice_series")),
            "invoice_number": _plain(draft.get("issued_invoice_number")),
            "subtotal": _vnd(draft["subtotal"]),
            "tax_amount": _vnd(draft["tax_amount"]),
            "total_amount": _vnd(draft["total_amount"]),
            **provenance,
        })
    totals = {
        "subtotal": sum(item["subtotal"] for item in invoices),
        "tax_amount": sum(item["tax_amount"] for item in invoices),
        "total_amount": sum(item["total_amount"] for item in invoices),
    }
    if totals["total_amount"] <= 0:
        raise InvoicePaymentScopeError(
            "Tổng đề nghị từ hóa đơn phải lớn hơn 0",
            code="invoice_payment_total_not_positive",
        )
    scope_payload = {
        "contractor": party,
        "date_from": safe_from,
        "date_to": safe_to,
        "invoices": invoices,
        "line_fingerprint": [
            {
                "draft_id": int(line["draft_id"]),
                "order_id": int(line["order_id"]),
                "product_code": _plain(line.get("product_code")),
                "product_name": _plain(line.get("product_name")),
                "unit": _plain(line.get("unit")),
                "kitchen": _plain(line.get("kitchen")),
                "work_date": _plain(line.get("work_date")),
                "invoice_nature": _plain(line.get("invoice_nature")),
                "qty": round(_number(line.get("qty"), "Số lượng"), 9),
                "unit_price": _vnd(line.get("unit_price")),
                "amount": _vnd(line.get("amount")),
                "tax": _plain(line.get("tax")),
            }
            for line in lines
        ],
        "totals": totals,
    }
    frozen_snapshot = {field: drafts[0][field] for field in SNAPSHOT_FIELDS}
    scope_id = hashlib.sha256(json.dumps(
        {**scope_payload, "snapshot": frozen_snapshot},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest().upper()
    return {
        **scope_payload,
        "scope_id": scope_id,
        "drafts": drafts,
        "lines": lines,
        "snapshot": frozen_snapshot,
        "template_status": "official_customer_xlsx",
        "official_template_ready": True,
        "warning": (
            "Số liệu chỉ lấy từ hóa đơn đỏ đã phát hành và đã đối chiếu. "
            "Nếu phạm vi thay đổi sau khi xem trước, hệ thống sẽ chặn file cũ."
        ),
    }


def public_payment_scope(scope: dict[str, Any]) -> dict[str, Any]:
    """Remove internal rendering rows while keeping the full proof summary."""
    return {
        key: value for key, value in scope.items()
        if key not in {"drafts", "lines", "snapshot", "line_fingerprint"}
    }


__all__ = [
    "InvoicePaymentScopeError",
    "SNAPSHOT_FIELDS",
    "issued_invoice_payment_scope",
    "public_payment_scope",
]
