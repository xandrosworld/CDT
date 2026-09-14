"""Canonical, append-only inventory ledger for electronic invoices.

The operational ``inventory_transactions`` table remains available to legacy
workflows.  This module deliberately reads only OPENING rows from that table;
all input/output invoice movement comes from ``invoice_inventory_ledger`` so a
compatibility projection can never be counted twice.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from typing import Any

from flask import jsonify, request

try:
    from invoice_mapping import (
        InvoiceMappingError,
        refresh_linked_batches,
        validated_output_stock_snapshot,
    )
except ImportError:  # pragma: no cover - package invocation
    from .invoice_mapping import (
        InvoiceMappingError,
        refresh_linked_batches,
        validated_output_stock_snapshot,
    )


INPUT_TABLE = "msmi_invoices"
OUTPUT_TABLE = "outgoing_source_invoices"


class InvoiceInventoryError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def _key(*parts: Any) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _strict_date(value: Any, *, allow_empty: bool = True) -> str:
    text = str(value or "").strip()
    if not text and allow_empty:
        return ""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise InvoiceInventoryError(
            "Ngày chốt kho phải là ngày YYYY-MM-DD hợp lệ", code="invalid_date", status=400
        ) from None


def _confirmation(
    conn,
    *,
    direction: str,
    source_table: str,
    invoice_id: int,
    action: str,
    note: str,
    timestamp: str,
) -> int:
    confirmation_key = _key(direction, action, source_table, invoice_id)
    conn.execute(
        """INSERT OR IGNORE INTO invoice_inventory_confirmations(
               confirmation_key,direction,source_invoice_table,source_invoice_id,
               action,confirmed,note,created_at
           ) VALUES(?,?,?,?,?,1,?,?)""",
        (confirmation_key, direction, source_table, invoice_id, action, note, timestamp),
    )
    row = conn.execute(
        """SELECT id,direction,source_invoice_table,source_invoice_id,action
           FROM invoice_inventory_confirmations WHERE confirmation_key=?""",
        (confirmation_key,),
    ).fetchone()
    if not row or tuple(row[key] for key in (
        "direction", "source_invoice_table", "source_invoice_id", "action"
    )) != (direction, source_table, invoice_id, action):
        raise InvoiceInventoryError(
            "Xác nhận kho trùng khóa nhưng khác nguồn; đã dừng an toàn",
            code="confirmation_conflict",
        )
    return int(row["id"])


def _same_number(left: Any, right: Any, tolerance: float = 1e-6) -> bool:
    try:
        return math.isfinite(float(left)) and abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def _append_event(
    conn,
    *,
    direction: str,
    event_type: str,
    source_table: str,
    invoice_id: int,
    line_id: int,
    line_index: int,
    product_code: str,
    txn_date: str,
    qty_delta: float,
    unit_cost: float,
    mapping_revision_id: int,
    confirmation_id: int,
    reverses_event_key: str,
    timestamp: str,
) -> bool:
    event_key = _key(event_type, source_table, invoice_id, line_id)
    existing = conn.execute(
        "SELECT * FROM invoice_inventory_ledger WHERE event_key=?", (event_key,)
    ).fetchone()
    expected = {
        "direction": direction,
        "event_type": event_type,
        "source_invoice_table": source_table,
        "source_invoice_id": invoice_id,
        "source_line_id": line_id,
        "source_line_index": line_index,
        "product_code": product_code,
        "txn_date": txn_date,
        "mapping_revision_id": mapping_revision_id,
        "confirmation_id": confirmation_id,
        "reverses_event_key": reverses_event_key,
    }
    if existing:
        if (
            any(existing[key] != value for key, value in expected.items())
            or not _same_number(existing["qty_delta"], qty_delta)
            or not _same_number(existing["unit_cost"], unit_cost)
        ):
            raise InvoiceInventoryError(
                "Bút toán hóa đơn cùng khóa nguồn khác snapshot; không được ghi đè",
                code="ledger_conflict",
            )
        return False
    conn.execute(
        """INSERT INTO invoice_inventory_ledger(
               event_key,direction,event_type,source_invoice_table,source_invoice_id,
               source_line_id,source_line_index,product_code,txn_date,qty_delta,unit_cost,
               mapping_revision_id,confirmation_id,reverses_event_key,status,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'posted',?)""",
        (
            event_key, direction, event_type, source_table, invoice_id, line_id, line_index,
            product_code, txn_date, qty_delta, unit_cost, mapping_revision_id,
            confirmation_id, reverses_event_key, timestamp,
        ),
    )
    return True


def record_input_invoice_events(
    conn,
    *,
    invoice_id: int,
    invoice_date: str,
    snapshots: list[dict[str, Any]],
    timestamp: str,
) -> int:
    """Append the canonical input movements inside the caller's transaction."""
    confirmation_id = _confirmation(
        conn,
        direction="input",
        source_table=INPUT_TABLE,
        invoice_id=int(invoice_id),
        action="post",
        note="Xác nhận tạo phiếu nhập từ hóa đơn đầu vào",
        timestamp=timestamp,
    )
    created = 0
    for snapshot in snapshots:
        created += int(_append_event(
            conn,
            direction="input",
            event_type="POST",
            source_table=INPUT_TABLE,
            invoice_id=int(invoice_id),
            line_id=int(snapshot["item_id"]),
            line_index=int(snapshot["line_index"]),
            product_code=str(snapshot["product_code"]),
            txn_date=invoice_date,
            qty_delta=float(snapshot["stock_qty"]),
            unit_cost=float(snapshot["stock_unit_price"]),
            mapping_revision_id=int(snapshot["mapping_revision_id"]),
            confirmation_id=confirmation_id,
            reverses_event_key="",
            timestamp=timestamp,
        ))
    return created


def _posted_input_trace_count(conn, invoice_id: int) -> int:
    return int(conn.execute(
        """SELECT COUNT(*) n FROM invoice_inventory_effective_ledger
           WHERE direction='input' AND event_type='POST'
             AND source_invoice_table=? AND source_invoice_id=?""",
        (INPUT_TABLE, int(invoice_id)),
    ).fetchone()["n"])


def verify_posted_input_trace(conn, invoice_id: int, expected_lines: int) -> None:
    count = _posted_input_trace_count(conn, int(invoice_id))
    if count != int(expected_lines) or count <= 0:
        raise InvoiceInventoryError(
            "Hóa đơn đã ghi kho nhưng thiếu sổ hóa đơn chuẩn; cần đối chiếu thủ công",
            code="posted_without_invoice_ledger",
        )


def selected_opening_snapshot(conn, anchor_date: str) -> tuple[str, str] | None:
    """Pick one latest opening snapshot; OPENING periods are not additive."""
    rows = conn.execute(
        """SELECT source_id,MIN(txn_date) txn_date,MAX(txn_date) max_date
           FROM inventory_transactions
           WHERE source_type='OPENING' AND status='posted' AND txn_date<=?
           GROUP BY source_id ORDER BY txn_date DESC,source_id DESC""",
        (anchor_date,),
    ).fetchall()
    if not rows:
        return None
    latest_date = str(rows[0]["txn_date"])
    same_date = [row for row in rows if str(row["txn_date"]) == latest_date]
    if len(same_date) != 1 or str(rows[0]["max_date"]) != latest_date:
        raise InvoiceInventoryError(
            "Có nhiều kỳ tồn đầu cùng mốc hoặc ngày trong một kỳ không thống nhất; cần đối chiếu",
            code="opening_period_conflict",
        )
    return str(rows[0]["source_id"]), latest_date


def invoice_stock_rows(conn, as_of: Any = "", *, include_zero: bool = False) -> list[dict[str, Any]]:
    """Return canonical quantities; this is a read-only projection."""
    safe_date = _strict_date(as_of) or "9999-12-31"
    opening = selected_opening_snapshot(conn, safe_date)
    opening_source = opening[0] if opening else ""
    opening_start = opening[1] if opening else "0001-01-01"
    rows = conn.execute(
        """WITH opening AS (
                SELECT t.product_code,SUM(t.qty_in-t.qty_out) qty
                FROM inventory_transactions t
                WHERE t.source_type='OPENING' AND t.status='posted' AND t.source_id=?
                GROUP BY t.product_code
            ), movements AS (
                SELECT l.product_code,
                       SUM(CASE WHEN l.direction='input' AND l.event_type='POST'
                                THEN l.qty_delta ELSE 0 END) input_qty,
                       SUM(CASE WHEN l.direction='output' AND l.event_type='POST'
                                THEN -l.qty_delta ELSE 0 END) output_qty,
                       SUM(CASE WHEN l.event_type='REVERSAL' THEN l.qty_delta ELSE 0 END)
                           reversal_qty,
                       SUM(l.qty_delta) net_qty
                FROM invoice_inventory_effective_ledger l
                WHERE l.status='posted' AND l.txn_date>=? AND l.txn_date<=?
                GROUP BY l.product_code
            )
            SELECT p.code product_code,p.name product_name,COALESCE(p.unit,'') unit,
                   COALESCE(o.qty,0) opening_qty,
                   COALESCE(m.input_qty,0) input_qty,
                   COALESCE(m.output_qty,0) output_qty,
                   COALESCE(m.reversal_qty,0) reversal_qty,
                   COALESCE(o.qty,0)+COALESCE(m.net_qty,0) closing_qty
            FROM products p
            LEFT JOIN opening o ON o.product_code=p.code
            LEFT JOIN movements m ON m.product_code=p.code
            ORDER BY p.code""",
        (opening_source, opening_start, safe_date),
    ).fetchall()
    payload = [dict(row) for row in rows]
    if not include_zero:
        payload = [row for row in payload if abs(float(row["closing_qty"] or 0)) > 1e-9]
    return payload


def _minimum_balance_from(conn, product_code: str, txn_date: str) -> float:
    opening = selected_opening_snapshot(conn, txn_date)
    opening_source = opening[0] if opening else ""
    opening_start = opening[1] if opening else "0001-01-01"
    balance = float(conn.execute(
        """SELECT COALESCE(SUM(qty_in-qty_out),0) qty FROM inventory_transactions
           WHERE source_type='OPENING' AND status='posted'
             AND source_id=? AND product_code=?""",
        (opening_source, product_code),
    ).fetchone()["qty"])
    rows = conn.execute(
        """SELECT txn_date,SUM(qty_delta) delta FROM invoice_inventory_effective_ledger
           WHERE status='posted' AND product_code=? AND txn_date>=?
           GROUP BY txn_date ORDER BY txn_date""",
        (product_code, opening_start),
    ).fetchall()
    # Include the balance on the requested date even when no ledger event
    # exists that day. A receipt tomorrow cannot fund an issue today.
    later = []
    for row in rows:
        if str(row["txn_date"]) <= txn_date:
            balance += float(row["delta"] or 0)
        else:
            later.append(float(row["delta"] or 0))
    candidates = [balance]
    for delta in later:
        balance += delta
        candidates.append(balance)
    return min(candidates)


def _audit(conn, *, event_type: str, invoice_id: int, timestamp: str, metadata: dict[str, Any]) -> None:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone():
        return
    conn.execute(
        """INSERT INTO audit_log(
               event_type,entity_type,entity_id,status,message,metadata_json,created_at
           ) VALUES(?,'outgoing_source_invoice',?,'ok','',?,?)""",
        (
            event_type,
            str(invoice_id),
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            timestamp,
        ),
    )


def post_output_invoice(
    conn,
    invoice_id: int,
    *,
    confirmed: Any,
    now_iso,
) -> dict[str, Any]:
    if confirmed is not True:
        raise InvoiceInventoryError(
            "Cần xác nhận rõ trước khi trừ kho theo hóa đơn đầu ra",
            code="confirmation_required",
            status=400,
        )
    safe_id = int(invoice_id)
    invoice = conn.execute("SELECT * FROM outgoing_source_invoices WHERE id=?", (safe_id,)).fetchone()
    if not invoice:
        raise InvoiceInventoryError("Không tìm thấy hóa đơn đầu ra", code="not_found", status=404)
    # Output inventory is authoritative only when it came from M-Invoice.
    # Keep reversal below source-agnostic so a bad legacy mSMI posting can
    # still be neutralised through the append-only reversal workflow.
    if str(invoice["source"] or "").strip().casefold() != "minvoice":
        raise InvoiceInventoryError(
            "Chỉ hóa đơn đầu ra từ M-Invoice mới được trừ kho",
            code="invalid_output_source",
        )
    existing = conn.execute(
        """SELECT COUNT(*) n FROM invoice_inventory_effective_ledger
           WHERE direction='output' AND event_type='POST'
             AND source_invoice_table=? AND source_invoice_id=?""",
        (OUTPUT_TABLE, safe_id),
    ).fetchone()["n"]
    if invoice["stock_status"] == "posted":
        if not existing:
            raise InvoiceInventoryError(
                "Hóa đơn đã đánh dấu xuất kho nhưng thiếu sổ hóa đơn chuẩn; cần đối chiếu",
                code="posted_without_invoice_ledger",
            )
        return {
            "invoice_id": safe_id,
            "new_inventory_lines": 0,
            "inventory_lines": int(existing),
            "idempotent": True,
        }
    if existing:
        raise InvoiceInventoryError(
            "Đã có bút toán xuất nhưng trạng thái hóa đơn không khớp; cần đối chiếu",
            code="ledger_state_conflict",
        )
    try:
        from .invoice_output_policy import uses_source_quantity_posting
        from .invoice_output_editing import output_mapping_allowed
    except ImportError:
        from invoice_output_policy import uses_source_quantity_posting
        from invoice_output_editing import output_mapping_allowed
    source_quantity_posting = uses_source_quantity_posting(invoice)
    if not (source_quantity_posting and output_mapping_allowed(invoice)) and (
        invoice["source_status_class"] != "issued"
        or invoice["sync_status"] != "synced"
        or invoice["stock_status"] != "ready"
    ):
        raise InvoiceInventoryError(
            "Chỉ hóa đơn đã phát hành, đồng bộ an toàn và ghép mã đầy đủ mới được trừ kho",
            code="output_not_ready",
        )
    invoice_date = _strict_date(invoice["invoice_date"], allow_empty=False)
    newer_opening = conn.execute(
        """SELECT 1 FROM inventory_transactions
           WHERE source_type='OPENING' AND status='posted' AND txn_date>? LIMIT 1""",
        (invoice_date,),
    ).fetchone()
    if newer_opening:
        raise InvoiceInventoryError(
            "Hóa đơn nằm trước một kỳ tồn đầu đã chốt; cần đối chiếu/rebuild kỳ sau trước khi post",
            code="backdated_before_opening_snapshot",
        )
    items = conn.execute(
        """SELECT * FROM outgoing_source_invoice_items
           WHERE invoice_id=? AND inventory_eligible=1 ORDER BY line_index""",
        (safe_id,),
    ).fetchall()
    if not items:
        raise InvoiceInventoryError(
            "Hóa đơn không có dòng hàng ảnh hưởng kho", code="no_inventory_lines", status=400
        )
    snapshots = []
    try:
        snapshots = [validated_output_stock_snapshot(conn, int(item["id"])) for item in items]
    except InvoiceMappingError as error:
        raise InvoiceInventoryError(str(error), code=error.code, status=error.status) from None
    required: dict[str, float] = {}
    for snapshot in snapshots:
        product = str(snapshot["product_code"])
        required[product] = required.get(product, 0.0) + float(snapshot["stock_qty"])
    for product, quantity in required.items():
        if not math.isfinite(quantity) or quantity <= 0:
            raise InvoiceInventoryError("Số lượng xuất quy đổi không hợp lệ", code="invalid_quantity")
        available = _minimum_balance_from(conn, product, invoice_date)
        if not source_quantity_posting and available + 1e-9 < quantity:
            raise InvoiceInventoryError(
                f"Mã {product}: cần {quantity:g}, có thể xuất {max(available, 0):g}, "
                f"thiếu {quantity - max(available, 0):g}; không đủ tồn tại ngày hóa đơn và các mốc sau đó",
                code="negative_stock",
            )
    try:
        try:
            from invoice_valuation import InvoiceValuationError, moving_average_costs
        except ImportError:  # pragma: no cover - package invocation
            from .invoice_valuation import InvoiceValuationError, moving_average_costs
        valuation_costs = moving_average_costs(conn, invoice_date)
    except InvoiceValuationError as error:
        if source_quantity_posting and error.code in {'negative_stock', 'negative_inventory_value'}:
            # Quantity posting does not certify a cost. Reports mark unresolved
            # valuation explicitly and monthly close continues to check it.
            valuation_costs = {}
        else:
            raise InvoiceInventoryError(str(error), code=error.code, status=error.status) from None

    savepoint = "invoice_output_post_atomic"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        timestamp = now_iso()
        confirmation_id = _confirmation(
            conn,
            direction="output",
            source_table=OUTPUT_TABLE,
            invoice_id=safe_id,
            action="post",
            note="Xác nhận trừ kho theo hóa đơn đầu ra đã phát hành",
            timestamp=timestamp,
        )
        created = 0
        for snapshot in snapshots:
            if snapshot.get('actual_weight'):
                # Preserve source Kg/price/amount. Only the derived stock fields
                # use the frozen, explicitly confirmed package quantity.
                conn.execute('''UPDATE outgoing_source_invoice_items SET conversion_factor=?,
                    stock_qty=?,stock_unit_price=? WHERE id=? AND invoice_id=?''',
                    (snapshot['conversion_factor'],snapshot['stock_qty'],snapshot['stock_unit_price'],
                     snapshot['item_id'],safe_id))
            created += int(_append_event(
                conn,
                direction="output",
                event_type="POST",
                source_table=OUTPUT_TABLE,
                invoice_id=safe_id,
                line_id=int(snapshot["item_id"]),
                line_index=int(snapshot["line_index"]),
                product_code=str(snapshot["product_code"]),
                txn_date=invoice_date,
                qty_delta=-float(snapshot["stock_qty"]),
                # Snapshot the current moving-average cost for cross-period
                # reversals. Rebuilds still derive valuation from source events.
                unit_cost=float(valuation_costs.get(str(snapshot["product_code"]), 0)),
                mapping_revision_id=int(snapshot["mapping_revision_id"]),
                confirmation_id=confirmation_id,
                reverses_event_key="",
                timestamp=timestamp,
            ))
        conn.execute(
            "UPDATE outgoing_source_invoices SET stock_status='posted',updated_at=? WHERE id=?",
            (timestamp, safe_id),
        )
        refresh_linked_batches(conn, "output", {safe_id}, timestamp)
        _audit(
            conn,
            event_type="invoice_output.inventory_post",
            invoice_id=safe_id,
            timestamp=timestamp,
            metadata={"inventory_lines": len(snapshots), "stock_qty_total": sum(required.values()),
                      "quantity_policy": "invoice_source" if source_quantity_posting else "available_stock",
                      "source_amount_warning": invoice['error_message'] if source_quantity_posting else ''},
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return {
            "invoice_id": safe_id,
            "new_inventory_lines": created,
            "inventory_lines": len(snapshots),
            "idempotent": created == 0,
        }
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if isinstance(error, InvoiceInventoryError):
            raise
        raise InvoiceInventoryError(
            "Không ghi được phiếu xuất; toàn bộ bút toán đã hoàn tác",
            code="output_write_failed",
        ) from error


def reverse_output_invoice(
    conn,
    invoice_id: int,
    *,
    confirmed: Any,
    note: Any,
    now_iso,
) -> dict[str, Any]:
    if confirmed is not True:
        raise InvoiceInventoryError(
            "Cần xác nhận rõ trước khi tạo bút toán reversal",
            code="confirmation_required",
            status=400,
        )
    safe_id = int(invoice_id)
    invoice = conn.execute("SELECT * FROM outgoing_source_invoices WHERE id=?", (safe_id,)).fetchone()
    if not invoice:
        raise InvoiceInventoryError("Không tìm thấy hóa đơn đầu ra", code="not_found", status=404)
    original = conn.execute(
        """SELECT * FROM invoice_inventory_remap_base_ledger
           WHERE direction='output' AND event_type='POST'
             AND source_invoice_table=? AND source_invoice_id=? ORDER BY source_line_index""",
        (OUTPUT_TABLE, safe_id),
    ).fetchall()
    reversed_count = int(conn.execute(
        """SELECT COUNT(*) n FROM invoice_inventory_remap_base_ledger
           WHERE direction='output' AND event_type='REVERSAL'
             AND source_invoice_table=? AND source_invoice_id=?""",
        (OUTPUT_TABLE, safe_id),
    ).fetchone()["n"])
    if invoice["stock_status"] == "reversed":
        if not original or reversed_count != len(original):
            raise InvoiceInventoryError(
                "Trạng thái reversal không khớp sổ hóa đơn; cần đối chiếu",
                code="reversal_trace_conflict",
            )
        return {
            "invoice_id": safe_id,
            "new_reversal_lines": 0,
            "reversal_lines": reversed_count,
            "idempotent": True,
        }
    if invoice["stock_status"] != "reversal_required" or invoice["source_status_class"] not in {
        "cancelled", "replaced", "adjusted"
    }:
        raise InvoiceInventoryError(
            "Hóa đơn chưa ở trạng thái cần reversal có kiểm soát",
            code="reversal_not_required",
        )
    if not original:
        raise InvoiceInventoryError(
            "Không có bút toán xuất gốc để reversal; không được tự tạo lịch sử",
            code="missing_original_event",
        )
    if reversed_count:
        raise InvoiceInventoryError(
            "Hoàn tác xuất kho dở dang hoặc trạng thái không khớp; cần đối chiếu",
            code="partial_reversal",
        )
    safe_note = str(note or "").strip()[:500]
    savepoint = "invoice_output_reversal_atomic"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        timestamp = now_iso()
        confirmation_id = _confirmation(
            conn,
            direction="output",
            source_table=OUTPUT_TABLE,
            invoice_id=safe_id,
            action="reversal",
            note=safe_note or "Xác nhận hoàn tác xuất kho theo trạng thái nguồn",
            timestamp=timestamp,
        )
        created = 0
        for event in original:
            created += int(_append_event(
                conn,
                direction="output",
                event_type="REVERSAL",
                source_table=OUTPUT_TABLE,
                invoice_id=safe_id,
                line_id=int(event["source_line_id"]),
                line_index=int(event["source_line_index"]),
                product_code=str(event["product_code"]),
                txn_date=_strict_date(timestamp[:10], allow_empty=False),
                qty_delta=-float(event["qty_delta"]),
                unit_cost=float(event["unit_cost"]),
                mapping_revision_id=int(event["mapping_revision_id"]),
                confirmation_id=confirmation_id,
                reverses_event_key=str(event["event_key"]),
                timestamp=timestamp,
            ))
        conn.execute(
            "UPDATE outgoing_source_invoices SET stock_status='reversed',updated_at=? WHERE id=?",
            (timestamp, safe_id),
        )
        refresh_linked_batches(conn, "output", {safe_id}, timestamp)
        _audit(
            conn,
            event_type="invoice_output.inventory_reversal",
            invoice_id=safe_id,
            timestamp=timestamp,
            metadata={"reversal_lines": len(original)},
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return {
            "invoice_id": safe_id,
            "new_reversal_lines": created,
            "reversal_lines": len(original),
            "idempotent": created == 0,
        }
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if isinstance(error, InvoiceInventoryError):
            raise
        raise InvoiceInventoryError(
            "Không tạo được reversal; toàn bộ bút toán đã hoàn tác",
            code="reversal_write_failed",
        ) from error


def invoice_inventory_trace(conn, direction: Any, invoice_id: int) -> dict[str, Any]:
    safe_direction = str(direction or "").strip().casefold()
    if safe_direction not in {"input", "output"}:
        raise InvoiceInventoryError("Chiều hóa đơn không hợp lệ", status=400)
    source_table = INPUT_TABLE if safe_direction == "input" else OUTPUT_TABLE
    partner = "seller_name" if safe_direction == "input" else "buyer_name"
    invoice = conn.execute(
        f"SELECT id,invoice_number,invoice_series,invoice_date,{partner} partner_name FROM {source_table} WHERE id=?",
        (int(invoice_id),),
    ).fetchone()
    if invoice is None:
        raise InvoiceInventoryError("Không tìm thấy hóa đơn", status=404)
    rows = conn.execute(
        """SELECT l.id,l.direction,l.event_type,l.source_invoice_table,l.source_invoice_id,
                  l.source_line_id,l.source_line_index,l.product_code,l.txn_date,l.qty_delta,
                  l.unit_cost,l.mapping_revision_id,l.confirmation_id,l.reverses_event_key,
                  l.status,l.created_at,c.action,c.note confirmation_note,c.created_at confirmed_at,
                  p.name product_name,
                  CASE WHEN l.direction='input' THEN COALESCE(NULLIF(r.target_unit,''),p.unit)
                       ELSE COALESCE(NULLIF(p.unit,''),r.target_unit) END product_unit
           FROM invoice_inventory_effective_ledger l
           JOIN invoice_inventory_confirmations c ON c.id=l.confirmation_id
           LEFT JOIN products p ON p.code=l.product_code
           LEFT JOIN invoice_mapping_revisions r ON r.id=l.mapping_revision_id
           WHERE l.direction=? AND l.source_invoice_table=? AND l.source_invoice_id=?
           ORDER BY l.id""",
        (safe_direction, source_table, int(invoice_id)),
    ).fetchall()
    return {
        "direction": safe_direction,
        "invoice_id": int(invoice_id),
        "invoice": dict(invoice),
        "events": [dict(row) for row in rows],
        "read_only": True,
    }


def register_invoice_inventory_routes(app, ctx) -> None:
    db_factory = ctx["db"]
    now_iso = ctx["now_iso"]

    @app.get("/api/invoice-inventory")
    def api_invoice_inventory():
        try:
            with db_factory() as conn:
                safe_date = _strict_date(request.args.get("as_of", ""))
                return jsonify({
                    "ok": True,
                    "as_of": safe_date,
                    "items": invoice_stock_rows(
                        conn,
                        safe_date,
                        include_zero=request.args.get("include_zero") == "1",
                    ),
                    "formula": "opening + valid_input - issued_confirmed_output + reversals",
                    "read_only": True,
                })
        except InvoiceInventoryError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.get("/api/invoice-inventory/source/<direction>/<int:invoice_id>")
    def api_invoice_inventory_trace(direction: str, invoice_id: int):
        try:
            with db_factory() as conn:
                return jsonify({"ok": True, **invoice_inventory_trace(conn, direction, invoice_id)})
        except InvoiceInventoryError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.post("/api/invoice-workbench/output/<int:invoice_id>/post")
    def api_post_output_invoice(invoice_id: int):
        body = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                return jsonify({
                    "ok": True,
                    **post_output_invoice(
                        conn, invoice_id, confirmed=body.get("confirmed"), now_iso=now_iso
                    ),
                })
        except InvoiceInventoryError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.post("/api/invoice-workbench/output/<int:invoice_id>/reversal")
    def api_reverse_output_invoice(invoice_id: int):
        body = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                return jsonify({
                    "ok": True,
                    **reverse_output_invoice(
                        conn,
                        invoice_id,
                        confirmed=body.get("confirmed"),
                        note=body.get("note"),
                        now_iso=now_iso,
                    ),
                })
        except InvoiceInventoryError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status
