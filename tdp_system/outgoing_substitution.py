"""Explicit, audited replacement-item allocations for outgoing shortages."""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
import unicodedata
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from flask import jsonify, request

try:
    from outgoing_readiness import allocation_by_order, canonical_available_stock
    from quote_import import quote_sell_price
except ImportError:  # pragma: no cover - package invocation
    from .outgoing_readiness import allocation_by_order, canonical_available_stock
    from .quote_import import quote_sell_price


SUBSTITUTION_PREVIEW_TTL_SECONDS = 15 * 60
SUBSTITUTION_PREVIEW_LIMIT = 2_000
PENDING_SUBSTITUTION_PREVIEWS: dict[str, dict[str, Any]] = {}
SUBSTITUTION_PREVIEW_LOCK = threading.Lock()


SUBSTITUTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS outgoing_substitution_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_key TEXT NOT NULL UNIQUE,
    batch_id INTEGER NOT NULL,
    original_order_id INTEGER NOT NULL,
    draft_id INTEGER NOT NULL,
    line_id INTEGER NOT NULL,
    contractor TEXT NOT NULL,
    work_date TEXT NOT NULL,
    original_product_code TEXT NOT NULL,
    original_product_name TEXT NOT NULL DEFAULT '',
    substitute_product_code TEXT NOT NULL,
    substitute_product_name TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL,
    qty REAL NOT NULL,
    unit_price REAL NOT NULL,
    price_source TEXT NOT NULL,
    price_period TEXT NOT NULL,
    quote_version_id INTEGER,
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    override_reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    confirmed_at TEXT NOT NULL,
    reversed_at TEXT,
    reversal_actor TEXT NOT NULL DEFAULT '',
    reversal_reason TEXT NOT NULL DEFAULT '',
    CHECK(qty > 0),
    CHECK(unit_price > 0),
    CHECK(price_source IN ('quote_version','approved_override')),
    CHECK(status IN ('active','reversed'))
);
CREATE INDEX IF NOT EXISTS idx_outgoing_substitution_batch
    ON outgoing_substitution_actions(batch_id,status,id);
CREATE INDEX IF NOT EXISTS idx_outgoing_substitution_order
    ON outgoing_substitution_actions(original_order_id,status,id);
"""


class OutgoingSubstitutionError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_substitution", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def init_outgoing_substitution_schema(conn) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(outgoing_invoice_drafts)")}
    if "draft_kind" not in columns:
        conn.execute(
            "ALTER TABLE outgoing_invoice_drafts "
            "ADD COLUMN draft_kind TEXT NOT NULL DEFAULT 'standard'"
        )
    conn.executescript(SUBSTITUTION_SCHEMA)


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _key(value: Any) -> str:
    text = _plain(value).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).casefold()
    return "".join(char for char in text if not unicodedata.combining(char))


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise OutgoingSubstitutionError(f"{label} không hợp lệ", status=400)
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise OutgoingSubstitutionError(f"{label} không phải là số hữu hạn", status=400) from None
    if not math.isfinite(result):
        raise OutgoingSubstitutionError(f"{label} không phải là số hữu hạn", status=400)
    return result


def _vnd(*values: Any) -> int:
    try:
        result = Decimal("1")
        for value in values:
            result *= Decimal(str(value))
        return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        raise OutgoingSubstitutionError("Không thể làm tròn giá trị thay thế") from None


def _tax_percent(value: Any) -> float:
    text = _plain(value).upper().replace(" ", "")
    if text in {"KKKNT", "KHÔNGKÊKHAI", "KHONGKEKHAI", "-2", "-2.0"}:
        return -2
    if text in {"KCT", "KHÔNGCHỊUTHUẾ", "KHONGCHIUTHUE", "-1", "-1.0"}:
        return -1
    if text.endswith("%"):
        text = text[:-1]
    try:
        result = float(text)
    except ValueError:
        raise OutgoingSubstitutionError("Mặt hàng thay thế thiếu mã thuế hợp lệ") from None
    if 0 < abs(result) < 1:
        result *= 100
    if not math.isfinite(result) or result < 0 or result > 100:
        raise OutgoingSubstitutionError("Mặt hàng thay thế thiếu mã thuế hợp lệ")
    return round(result, 4)


def _net_delivered(order: dict[str, Any]) -> float:
    return max(float(order.get("actual_delivered") or 0) - float(order.get("customer_return_qty") or 0), 0)


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _issue_preview(snapshot_hash: str) -> str:
    now = time.monotonic()
    with SUBSTITUTION_PREVIEW_LOCK:
        expired = [
            key for key, value in PENDING_SUBSTITUTION_PREVIEWS.items()
            if now - float(value["created_monotonic"]) > SUBSTITUTION_PREVIEW_TTL_SECONDS
        ]
        for key in expired:
            PENDING_SUBSTITUTION_PREVIEWS.pop(key, None)
        while len(PENDING_SUBSTITUTION_PREVIEWS) >= SUBSTITUTION_PREVIEW_LIMIT:
            oldest = min(
                PENDING_SUBSTITUTION_PREVIEWS,
                key=lambda key: PENDING_SUBSTITUTION_PREVIEWS[key]["created_monotonic"],
            )
            PENDING_SUBSTITUTION_PREVIEWS.pop(oldest, None)
        token = uuid.uuid4().hex.upper()
        PENDING_SUBSTITUTION_PREVIEWS[token] = {
            "snapshot_hash": snapshot_hash,
            "created_monotonic": now,
        }
    return token


def _preview_snapshot(preview_token: str) -> str:
    with SUBSTITUTION_PREVIEW_LOCK:
        pending = PENDING_SUBSTITUTION_PREVIEWS.get(preview_token)
        if not pending:
            return ""
        if time.monotonic() - float(pending["created_monotonic"]) > SUBSTITUTION_PREVIEW_TTL_SECONDS:
            PENDING_SUBSTITUTION_PREVIEWS.pop(preview_token, None)
            return ""
        return str(pending["snapshot_hash"])


def _price_resolution(conn, order: dict[str, Any], substitute_code: str, body: dict[str, Any]) -> dict[str, Any]:
    quote = quote_sell_price(conn, substitute_code, order["contractor"], order["work_date"])
    override_value = body.get("override_price")
    override_requested = override_value not in (None, "")
    if override_requested:
        override_price = _number(override_value, "Giá bán override")
        override_reason = _plain(body.get("override_reason"))
        approved = body.get("approve_price_override") is True
        valid = override_price > 0 and approved and bool(override_reason)
        return {
            "unit_price": _vnd(override_price) if override_price > 0 else 0,
            "price_source": "approved_override",
            "price_period": str(order["work_date"])[:7],
            "quote_version_id": None,
            "quote_version_no": None,
            "override_reason": override_reason,
            "price_message": "Giá override cần tick xác nhận và ghi lý do" if not valid else "Giá override đã xác nhận rõ",
            "price_ready": valid,
        }
    value = quote.get("value")
    if value is not None and float(value) > 0:
        return {
            "unit_price": _vnd(value),
            "price_source": "quote_version",
            "price_period": quote.get("period") or str(order["work_date"])[:7],
            "quote_version_id": quote.get("version_id"),
            "quote_version_no": quote.get("version_no"),
            "override_reason": "",
            "price_message": "Giá từ báo giá đúng kỳ/nhà thầu",
            "price_ready": True,
        }
    return {
        "unit_price": 0,
        "price_source": "quote_version",
        "price_period": quote.get("period") or str(order["work_date"])[:7],
        "quote_version_id": quote.get("version_id"),
        "quote_version_no": quote.get("version_no"),
        "override_reason": "",
        "price_message": quote.get("message") or "Chưa có giá bán đúng kỳ/nhà thầu",
        "price_ready": False,
    }


def substitution_preview(conn, body: dict[str, Any]) -> dict[str, Any]:
    try:
        batch_id = int(body.get("batch_id") or 0)
        order_id = int(body.get("order_id") or 0)
    except (TypeError, ValueError):
        raise OutgoingSubstitutionError("Phiên/dòng thiếu không hợp lệ", status=400) from None
    substitute_code = _plain(body.get("substitute_product_code")).upper()
    qty = _number(body.get("qty"), "Số lượng thay thế")
    actor = _plain(body.get("actor"))
    reason = _plain(body.get("reason"))
    if not batch_id or not order_id or not substitute_code or qty <= 0:
        raise OutgoingSubstitutionError(
            "Cần phiên, dòng thiếu, mã thay thế và số lượng dương", status=400,
        )
    if len(actor) > 120 or len(reason) > 500 or len(_plain(body.get("override_reason"))) > 500:
        raise OutgoingSubstitutionError("Người thực hiện/lý do quá dài", status=400)

    source = conn.execute(
        """SELECT o.*,b.status batch_status FROM orders o
             JOIN batches b ON b.id=o.batch_id
            WHERE o.id=? AND o.batch_id=?""",
        (order_id, batch_id),
    ).fetchone()
    if not source:
        raise OutgoingSubstitutionError("Không tìm thấy dòng thiếu trong phiên", code="order_not_found", status=404)
    order = dict(source)
    if order["batch_status"] != "approved":
        raise OutgoingSubstitutionError("Chỉ thay thế trên phiên đơn đã duyệt", code="batch_not_approved")
    original_code = _plain(order.get("product_code")).upper()
    if not original_code:
        raise OutgoingSubstitutionError("Dòng gốc thiếu mã hàng TĐP", code="missing_original_code")
    if substitute_code == original_code:
        raise OutgoingSubstitutionError("Mã thay thế phải khác mã hàng gốc", code="same_product")
    contractor = _plain(order.get("contractor"))
    if not contractor:
        raise OutgoingSubstitutionError("Dòng gốc thiếu nhà thầu", code="missing_contractor")
    demand = _net_delivered(order)
    held = allocation_by_order(conn, [batch_id]).get(order_id, {"drafted_qty": 0, "issued_qty": 0})
    allocated = held["drafted_qty"] + held["issued_qty"]
    pending = max(demand - allocated, 0)
    if pending <= 1e-9:
        raise OutgoingSubstitutionError("Dòng này không còn số lượng thiếu", code="no_shortage")
    if qty > pending + 1e-9:
        raise OutgoingSubstitutionError(
            f"Số lượng thay thế vượt phần còn thiếu {pending:g}", code="qty_exceeds_shortage",
        )

    product = conn.execute("SELECT * FROM products WHERE code=?", (substitute_code,)).fetchone()
    if not product:
        raise OutgoingSubstitutionError("Mã thay thế không có trong danh mục", code="substitute_not_found", status=404)
    replacement = dict(product)
    if _key(order.get("unit")) != _key(replacement.get("unit")):
        raise OutgoingSubstitutionError(
            "ĐVT hàng gốc và hàng thay thế khác nhau; chưa có tỷ lệ được khách xác nhận",
            code="substitute_unit_mismatch",
        )
    stock = canonical_available_stock(conn).get(substitute_code, {})
    available = max(float(stock.get("available_qty") or 0), 0)
    if qty > available + 1e-9:
        raise OutgoingSubstitutionError(
            f"Tồn hóa đơn của mã thay thế chỉ còn {available:g}",
            code="substitute_stock_insufficient",
        )
    tax_percent = _tax_percent(replacement.get("tax"))
    price = _price_resolution(conn, order, substitute_code, body)
    unit_price = float(price["unit_price"] or 0)
    amount = _vnd(qty, unit_price) if unit_price > 0 else 0
    actor_ready = bool(actor and reason)
    canonical = {
        "batch_id": batch_id,
        "order_id": order_id,
        "contractor": contractor,
        "work_date": order["work_date"],
        "kitchen": _plain(order.get("kitchen")),
        "original_product_code": original_code,
        "original_unit": _plain(order.get("unit")),
        "substitute_product_code": substitute_code,
        "substitute_unit": _plain(replacement.get("unit")),
        "substitute_tax": _plain(replacement.get("tax")),
        "substitute_tax_percent": tax_percent,
        "qty": round(qty, 9),
        "demand_qty": round(demand, 9),
        "allocated_before": round(allocated, 9),
        "pending_before": round(pending, 9),
        "substitute_available": round(available, 9),
        "unit_price": unit_price,
        "price_source": price["price_source"],
        "price_period": price["price_period"],
        "quote_version_id": price["quote_version_id"],
        "override_reason": price["override_reason"],
        "actor": actor,
        "reason": reason,
    }
    return {
        **canonical,
        "preview_id": _payload_hash(canonical),
        "can_confirm": bool(price["price_ready"] and actor_ready),
        "blocked_code": (
            "actor_reason_required" if not actor_ready
            else "missing_period_price" if not price["price_ready"]
            else ""
        ),
        "price_message": price["price_message"],
        "quote_version_no": price["quote_version_no"],
        "original_product_name": order.get("product_name") or "",
        "substitute_product_name": replacement.get("name") or "",
        "unit": replacement.get("unit") or "",
        "tax": replacement.get("tax") or "",
        "tax_percent": tax_percent,
        "amount": amount,
    }


def _recompute_draft_totals(conn, draft_id: int) -> None:
    subtotal = tax_amount = 0
    for row in conn.execute(
        "SELECT amount,tax FROM outgoing_invoice_lines WHERE draft_id=?", (draft_id,),
    ):
        amount = _vnd(row["amount"])
        percent = _tax_percent(row["tax"])
        subtotal += amount
        if percent > 0:
            tax_amount += _vnd(amount, percent / 100)
    conn.execute(
        "UPDATE outgoing_invoice_drafts SET subtotal=?,tax_amount=?,total_amount=? WHERE id=?",
        (subtotal, tax_amount, subtotal + tax_amount, draft_id),
    )


def _editable_substitution_draft(conn, batch_id: int, contractor: str, order_id: int):
    return conn.execute(
        """SELECT d.* FROM outgoing_invoice_drafts d
            WHERE d.batch_id=? AND d.contractor=? AND d.status='draft'
              AND COALESCE(d.draft_kind,'standard')='substitution'
              AND COALESCE(d.minvoice_status,'not_sent') NOT IN ('saved','saving','unknown')
              AND NOT EXISTS (
                  SELECT 1 FROM outgoing_invoice_lines l
                   WHERE l.draft_id=d.id AND l.order_id=?
              )
            ORDER BY d.round_no DESC,d.id DESC LIMIT 1""",
        (batch_id, contractor, order_id),
    ).fetchone()


def confirm_substitution(conn, body: dict[str, Any], now_iso, audit_event) -> dict[str, Any]:
    preview_id = _plain(body.get("preview_id")).upper()
    if body.get("confirmed") is not True or not preview_id:
        raise OutgoingSubstitutionError(
            "Cần preview hiện hành và xác nhận rõ lựa chọn thay thế",
            code="confirmation_required",
            status=400,
        )
    existing = conn.execute(
        "SELECT * FROM outgoing_substitution_actions WHERE request_key=?", (preview_id,),
    ).fetchone()
    if existing:
        if existing["status"] == "active":
            return {"action": dict(existing), "idempotent": True}
        raise OutgoingSubstitutionError(
            "Lựa chọn này đã được hoàn tác; cần preview lại nếu muốn làm lượt mới",
            code="substitution_already_reversed",
        )

    expected_snapshot = _preview_snapshot(preview_id)
    if not expected_snapshot:
        raise OutgoingSubstitutionError(
            "Preview đã hết hạn hoặc máy chủ đã khởi động lại; cần xem trước lại",
            code="substitution_preview_expired",
        )
    preview = substitution_preview(conn, body)
    if preview["preview_id"] != expected_snapshot:
        raise OutgoingSubstitutionError(
            "Tồn, phần thiếu hoặc giá đã thay đổi; cần preview lại",
            code="stale_substitution_preview",
        )
    if not preview["can_confirm"]:
        message = (
            "Cần ghi người thực hiện và lý do" if preview["blocked_code"] == "actor_reason_required"
            else preview["price_message"]
        )
        raise OutgoingSubstitutionError(message, code=preview["blocked_code"])

    draft = _editable_substitution_draft(
        conn, preview["batch_id"], preview["contractor"], preview["order_id"],
    )
    timestamp = now_iso()
    if draft:
        draft_id = int(draft["id"])
        round_no = int(draft["round_no"])
    else:
        round_no = int(conn.execute(
            """SELECT COALESCE(MAX(round_no),0)+1 n FROM outgoing_invoice_drafts
                WHERE batch_id=? AND contractor=?""",
            (preview["batch_id"], preview["contractor"]),
        ).fetchone()["n"])
        draft_id = int(conn.execute(
            """INSERT INTO outgoing_invoice_drafts(
                   batch_id,contractor,invoice_date,status,subtotal,tax_amount,total_amount,
                   created_at,external_key_uuid,round_no,draft_kind
               ) VALUES(?,?,?,'draft',0,0,0,?,?,?,'substitution')""",
            (
                preview["batch_id"], preview["contractor"], preview["work_date"],
                timestamp, uuid.uuid4().hex.upper(), round_no,
            ),
        ).lastrowid)
    invoice_name = conn.execute(
        "SELECT invoice_name FROM outgoing_product_names WHERE product_code=?",
        (preview["substitute_product_code"],),
    ).fetchone()
    line_name = invoice_name["invoice_name"] if invoice_name else preview["substitute_product_name"]
    line_id = int(conn.execute(
        """INSERT INTO outgoing_invoice_lines(
               draft_id,order_id,product_code,product_name,qty,unit,unit_price,tax,
               invoice_nature,amount
           ) VALUES(?,?,?,?,?,?,?,?, '1',?)""",
        (
            draft_id, preview["order_id"], preview["substitute_product_code"], line_name,
            preview["qty"], preview["unit"], _vnd(preview["unit_price"]), preview["tax"],
            preview["amount"],
        ),
    ).lastrowid)
    conn.execute(
        """INSERT INTO inventory_transactions(
               txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,
               kitchen,status,note,created_at,updated_at
           ) VALUES(?,?,0,?,0,'OUTGOING_DRAFT',?,?,?,'reserved',?,?,?)""",
        (
            preview["work_date"], preview["substitute_product_code"], preview["qty"],
            str(draft_id), str(preview["order_id"]), preview["kitchen"],
            f"Hàng thay thế cho {preview['original_product_code']} · {preview['reason']}",
            timestamp, timestamp,
        ),
    )
    action_id = int(conn.execute(
        """INSERT INTO outgoing_substitution_actions(
               request_key,batch_id,original_order_id,draft_id,line_id,contractor,work_date,
               original_product_code,original_product_name,substitute_product_code,
               substitute_product_name,unit,qty,unit_price,price_source,price_period,
               quote_version_id,actor,reason,override_reason,status,confirmed_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'active',?)""",
        (
            preview_id, preview["batch_id"], preview["order_id"], draft_id, line_id,
            preview["contractor"], preview["work_date"], preview["original_product_code"],
            preview["original_product_name"], preview["substitute_product_code"],
            preview["substitute_product_name"], preview["unit"], preview["qty"],
            preview["unit_price"], preview["price_source"], preview["price_period"],
            preview["quote_version_id"], preview["actor"], preview["reason"],
            preview["override_reason"], timestamp,
        ),
    ).lastrowid)
    _recompute_draft_totals(conn, draft_id)
    audit_event(
        conn,
        "outgoing.substitution.confirm",
        entity_type="outgoing_substitution",
        entity_id=action_id,
        metadata={
            "batch_id": preview["batch_id"], "order_id": preview["order_id"],
            "draft_id": draft_id, "round_no": round_no,
            "original_product_code": preview["original_product_code"],
            "substitute_product_code": preview["substitute_product_code"],
            "qty": preview["qty"], "unit_price": preview["unit_price"],
            "price_source": preview["price_source"], "price_period": preview["price_period"],
            "quote_version_id": preview["quote_version_id"], "actor": preview["actor"],
            "reason": preview["reason"], "override_reason": preview["override_reason"],
        },
    )
    action = dict(conn.execute(
        "SELECT * FROM outgoing_substitution_actions WHERE id=?", (action_id,),
    ).fetchone())
    return {"action": action, "idempotent": False, "round_no": round_no}


def reverse_substitution(conn, action_id: int, body: dict[str, Any], now_iso, audit_event) -> dict[str, Any]:
    if body.get("confirmed") is not True:
        raise OutgoingSubstitutionError("Cần xác nhận hoàn tác", code="confirmation_required", status=400)
    actor = _plain(body.get("actor"))
    reason = _plain(body.get("reason"))
    if not actor or not reason or len(actor) > 120 or len(reason) > 500:
        raise OutgoingSubstitutionError("Cần người thực hiện và lý do hoàn tác", status=400)
    action = conn.execute(
        "SELECT * FROM outgoing_substitution_actions WHERE id=?", (action_id,),
    ).fetchone()
    if not action:
        raise OutgoingSubstitutionError("Không tìm thấy lựa chọn thay thế", code="not_found", status=404)
    if action["status"] == "reversed":
        return {"action": dict(action), "idempotent": True}
    draft = conn.execute(
        "SELECT * FROM outgoing_invoice_drafts WHERE id=?", (action["draft_id"],),
    ).fetchone()
    if (
        not draft or draft["status"] != "draft"
        or str(draft["minvoice_status"] or "not_sent") in {"saved", "saving", "unknown"}
    ):
        raise OutgoingSubstitutionError(
            "Vòng thay thế đã khóa/đã phát hành; phải dùng reversal hóa đơn chuẩn, không được sửa lịch sử",
            code="issued_substitution_requires_invoice_reversal",
        )
    reservation = conn.execute(
        """UPDATE inventory_transactions SET status='cancelled',updated_at=?
            WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND source_line=?
              AND status='reserved'""",
        (now_iso(), str(action["draft_id"]), str(action["original_order_id"])),
    )
    if reservation.rowcount != 1:
        raise OutgoingSubstitutionError(
            "Không tìm thấy đúng lượng tồn đang giữ; dừng hoàn tác để đối chiếu",
            code="substitution_reservation_conflict",
        )
    deleted = conn.execute(
        "DELETE FROM outgoing_invoice_lines WHERE id=? AND draft_id=?",
        (action["line_id"], action["draft_id"]),
    )
    if deleted.rowcount != 1:
        raise OutgoingSubstitutionError(
            "Dòng dự thảo thay thế đã thay đổi; dừng hoàn tác",
            code="substitution_line_conflict",
        )
    timestamp = now_iso()
    conn.execute(
        """UPDATE outgoing_substitution_actions
              SET status='reversed',reversed_at=?,reversal_actor=?,reversal_reason=?
            WHERE id=? AND status='active'""",
        (timestamp, actor, reason, action_id),
    )
    remaining = conn.execute(
        "SELECT COUNT(*) n FROM outgoing_invoice_lines WHERE draft_id=?", (action["draft_id"],),
    ).fetchone()["n"]
    if remaining:
        _recompute_draft_totals(conn, int(action["draft_id"]))
    else:
        conn.execute(
            "UPDATE outgoing_invoice_drafts SET status='cancelled',subtotal=0,tax_amount=0,total_amount=0 WHERE id=?",
            (action["draft_id"],),
        )
    audit_event(
        conn,
        "outgoing.substitution.reverse",
        entity_type="outgoing_substitution",
        entity_id=action_id,
        metadata={
            "draft_id": action["draft_id"], "line_id": action["line_id"],
            "original_product_code": action["original_product_code"],
            "substitute_product_code": action["substitute_product_code"],
            "qty": action["qty"], "actor": actor, "reason": reason,
        },
    )
    return {
        "action": dict(conn.execute(
            "SELECT * FROM outgoing_substitution_actions WHERE id=?", (action_id,),
        ).fetchone()),
        "idempotent": False,
    }


def mark_substitution_actions_reversed_for_draft(conn, draft_id: int, timestamp: str) -> int:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='outgoing_substitution_actions'"
    ).fetchone()
    if not exists:
        return 0
    return conn.execute(
        """UPDATE outgoing_substitution_actions
              SET status='reversed',reversed_at=?,reversal_actor='SYSTEM',
                  reversal_reason='Hủy toàn bộ dự thảo'
            WHERE draft_id=? AND status='active'""",
        (timestamp, draft_id),
    ).rowcount


def register_outgoing_substitution_routes(app, ctx) -> None:
    db_factory = ctx["db"]
    now_iso = ctx["now_iso"]
    audit_event = ctx["audit_event"]

    def error_response(exc: OutgoingSubstitutionError):
        return jsonify({"ok": False, "error": str(exc), "code": exc.code}), exc.status

    @app.post("/api/outgoing-substitutions/preview")
    def api_outgoing_substitution_preview():
        try:
            with db_factory() as conn:
                conn.execute("PRAGMA query_only=ON")
                preview = substitution_preview(conn, request.get_json(silent=True) or {})
        except OutgoingSubstitutionError as exc:
            return error_response(exc)
        preview["preview_id"] = _issue_preview(preview["preview_id"])
        return jsonify({"ok": True, **preview})

    @app.post("/api/outgoing-substitutions/confirm")
    def api_outgoing_substitution_confirm():
        body = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = confirm_substitution(conn, body, now_iso, audit_event)
        except OutgoingSubstitutionError as exc:
            return error_response(exc)
        return jsonify({"ok": True, **result})

    @app.post("/api/outgoing-substitutions/<int:action_id>/reverse")
    def api_outgoing_substitution_reverse(action_id):
        body = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = reverse_substitution(conn, action_id, body, now_iso, audit_event)
        except OutgoingSubstitutionError as exc:
            return error_response(exc)
        return jsonify({"ok": True, **result})

    @app.get("/api/outgoing-substitutions")
    def api_outgoing_substitution_list():
        try:
            batch_id = int(request.args.get("batch_id") or 0)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Phiên không hợp lệ", "code": "invalid_batch"}), 400
        if not batch_id:
            return jsonify({"ok": False, "error": "Cần batch_id", "code": "batch_required"}), 400
        with db_factory() as conn:
            rows = [dict(row) for row in conn.execute(
                """SELECT a.*,d.status draft_status,d.minvoice_status
                      FROM outgoing_substitution_actions a
                      LEFT JOIN outgoing_invoice_drafts d ON d.id=a.draft_id
                     WHERE a.batch_id=? ORDER BY a.id DESC LIMIT 1000""",
                (batch_id,),
            )]
        return jsonify({"ok": True, "items": rows})


__all__ = [
    "OutgoingSubstitutionError",
    "PENDING_SUBSTITUTION_PREVIEWS",
    "SUBSTITUTION_PREVIEW_LOCK",
    "confirm_substitution",
    "init_outgoing_substitution_schema",
    "mark_substitution_actions_reversed_for_draft",
    "register_outgoing_substitution_routes",
    "reverse_substitution",
    "substitution_preview",
]
