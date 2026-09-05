"""Atomic input-invoice receipt posting from confirmed conversion snapshots."""

from __future__ import annotations

import json
import math
from typing import Any

try:
    from contract_modules import as_date
    from invoice_inventory import (
        InvoiceInventoryError,
        record_input_invoice_events,
        selected_opening_snapshot,
        verify_posted_input_trace,
    )
    from invoice_mapping import (
        InvoiceMappingError,
        refresh_linked_batches,
        validated_input_stock_snapshot,
    )
except ImportError:  # pragma: no cover - package invocation
    from .contract_modules import as_date
    from .invoice_inventory import (
        InvoiceInventoryError,
        record_input_invoice_events,
        selected_opening_snapshot,
        verify_posted_input_trace,
    )
    from .invoice_mapping import (
        InvoiceMappingError,
        refresh_linked_batches,
        validated_input_stock_snapshot,
    )


class InvoiceReceiptError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def _audit(conn, now_iso, status: str, invoice_id: int, metadata: dict[str, Any]) -> None:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone():
        return
    conn.execute(
        """INSERT INTO audit_log(
               event_type,entity_type,entity_id,status,message,metadata_json,created_at
           ) VALUES('invoice_input.receipt','msmi_invoice',?,?,?,?,?)""",
        (
            str(invoice_id), status, "",
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            now_iso(),
        ),
    )


def create_input_receipt(conn, invoice_id: int, now_iso) -> dict[str, Any]:
    try:
        safe_invoice_id = int(invoice_id)
    except (TypeError, ValueError):
        raise InvoiceReceiptError("Mã hóa đơn đầu vào không hợp lệ", status=400) from None
    invoice = conn.execute("SELECT * FROM msmi_invoices WHERE id=?", (safe_invoice_id,)).fetchone()
    if not invoice:
        raise InvoiceReceiptError("Không tìm thấy hóa đơn đầu vào", code="not_found", status=404)
    if invoice["invoice_type"] != "INPUT_ELECTRONIC_INVOICE":
        raise InvoiceReceiptError("Chỉ hóa đơn đầu vào mới được tạo phiếu nhập", status=400)
    source_id = str(invoice["remote_id"])
    existing_rows = conn.execute(
        """SELECT * FROM inventory_transactions
           WHERE source_type='MSMI_INPUT' AND source_id=? ORDER BY source_line""",
        (source_id,),
    ).fetchall()
    if invoice["receipt_status"] == "posted":
        if not existing_rows:
            raise InvoiceReceiptError(
                "Hóa đơn đánh dấu đã ghi kho nhưng thiếu bút toán; cần đối chiếu",
                code="posted_without_ledger",
            )
        try:
            verify_posted_input_trace(conn, safe_invoice_id, len(existing_rows))
        except InvoiceInventoryError as error:
            raise InvoiceReceiptError(str(error), code=error.code) from None
        return {
            "invoice_id": safe_invoice_id,
            "new_inventory_lines": 0,
            "new_invoice_ledger_lines": 0,
            "inventory_lines": len(existing_rows),
            "idempotent": True,
        }
    if invoice["sync_status"] != "synced":
        raise InvoiceReceiptError(
            "Hóa đơn đang cần đối chiếu sau đồng bộ; chưa được tạo phiếu nhập",
            code="source_review_required",
        )
    if invoice["receipt_status"] != "ready":
        raise InvoiceReceiptError(
            "Hóa đơn chưa ghép đủ mã và quy đổi ĐVT",
            code="mapping_incomplete",
            status=400,
        )
    if as_date(invoice["invoice_date"]) != invoice["invoice_date"]:
        raise InvoiceReceiptError("Ngày hóa đơn đầu vào không hợp lệ", code="invalid_invoice_date")
    try:
        latest_opening = selected_opening_snapshot(conn, "9999-12-31")
    except InvoiceInventoryError as error:
        raise InvoiceReceiptError(str(error), code=error.code, status=error.status) from None
    if latest_opening and invoice["invoice_date"] < latest_opening[1]:
        raise InvoiceReceiptError(
            "Hóa đơn nằm trước kỳ tồn đầu mới nhất; cần đối chiếu/rebuild kỳ tồn trước khi post",
            code="backdated_before_opening_snapshot",
        )
    items = conn.execute(
        """SELECT * FROM msmi_invoice_items
           WHERE invoice_id=? AND inventory_eligible=1 ORDER BY line_index""",
        (safe_invoice_id,),
    ).fetchall()
    if not items:
        raise InvoiceReceiptError(
            "Hóa đơn không có dòng hàng ảnh hưởng kho",
            code="no_inventory_lines",
            status=400,
        )
    snapshots = []
    try:
        for item in items:
            snapshots.append(validated_input_stock_snapshot(conn, item["id"]))
    except InvoiceMappingError as error:
        raise InvoiceReceiptError(str(error), code=error.code, status=409) from None
    if any(
        not math.isfinite(row["stock_qty"])
        or not math.isfinite(row["stock_unit_price"])
        or row["stock_qty"] <= 0
        or row["stock_unit_price"] < 0
        for row in snapshots
    ):
        raise InvoiceReceiptError("Snapshot quy đổi có số không hợp lệ", code="invalid_stock_snapshot")

    savepoint = "invoice_input_receipt_atomic"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        new_lines = 0
        timestamp = now_iso()
        new_invoice_ledger_lines = record_input_invoice_events(
            conn,
            invoice_id=safe_invoice_id,
            invoice_date=invoice["invoice_date"],
            snapshots=snapshots,
            timestamp=timestamp,
        )
        for snapshot in snapshots:
            source_line = str(snapshot["line_index"])
            existing = conn.execute(
                """SELECT * FROM inventory_transactions
                   WHERE source_type='MSMI_INPUT' AND source_id=? AND source_line=?""",
                (source_id, source_line),
            ).fetchone()
            if existing:
                if (
                    existing["product_code"] != snapshot["product_code"]
                    or abs(float(existing["qty_in"] or 0) - snapshot["stock_qty"]) > 1e-6
                    or abs(float(existing["unit_cost"] or 0) - snapshot["stock_unit_price"]) > 1e-6
                ):
                    raise InvoiceReceiptError(
                        "Bút toán kho cùng khóa nguồn khác snapshot; không được ghi đè",
                        code="ledger_conflict",
                    )
                continue
            conn.execute(
                """INSERT INTO inventory_transactions(
                       txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,
                       source_line,status,note,created_at,updated_at
                   ) VALUES(?,?,?,?,?,'MSMI_INPUT',?,?,'posted',?,?,?)""",
                (
                    invoice["invoice_date"], snapshot["product_code"], snapshot["stock_qty"], 0,
                    snapshot["stock_unit_price"], source_id, source_line,
                    f"Phiếu nhập hóa đơn {invoice['invoice_series']} {invoice['invoice_number']}",
                    timestamp, timestamp,
                ),
            )
            new_lines += 1
        conn.execute(
            "UPDATE msmi_invoices SET receipt_status='posted',updated_at=? WHERE id=?",
            (timestamp, safe_invoice_id),
        )
        refresh_linked_batches(conn, "input", {safe_invoice_id}, timestamp)
        non_inventory = int(conn.execute(
            "SELECT COUNT(*) n FROM msmi_invoice_items WHERE invoice_id=? AND inventory_eligible=0",
            (safe_invoice_id,),
        ).fetchone()["n"])
        _audit(conn, now_iso, "ok", safe_invoice_id, {
            "new_inventory_lines": new_lines,
            "new_invoice_ledger_lines": new_invoice_ledger_lines,
            "inventory_lines": len(snapshots),
            "non_inventory_lines": non_inventory,
            "stock_qty_total": round(sum(row["stock_qty"] for row in snapshots), 6),
        })
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return {
            "invoice_id": safe_invoice_id,
            "new_inventory_lines": new_lines,
            "new_invoice_ledger_lines": new_invoice_ledger_lines,
            "inventory_lines": len(snapshots),
            "non_inventory_lines": non_inventory,
            "idempotent": new_lines == 0,
        }
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if isinstance(error, InvoiceReceiptError):
            raise
        if isinstance(error, InvoiceInventoryError):
            raise InvoiceReceiptError(str(error), code=error.code, status=error.status) from None
        raise InvoiceReceiptError(
            "Không ghi được phiếu nhập; toàn bộ bút toán đã hoàn tác",
            code="receipt_write_failed",
        ) from error
