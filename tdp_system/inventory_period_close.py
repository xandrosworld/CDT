"""Monthly inventory close and opening-balance carry-forward.

The invoice inventory ledger stays immutable.  Closing a month materializes the
read-only monthly-average projection as the next month's ``OPENING`` snapshot.
The operation is guarded by source/target hashes, is idempotent, and can be
explicitly reopened before a later month is closed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Mapping

from flask import jsonify, request

try:
    from invoice_valuation import InvoiceValuationError
    from invoice_monthly_valuation import monthly_average_report
except ImportError:  # pragma: no cover - package invocation
    from .invoice_valuation import InvoiceValuationError
    from .invoice_monthly_valuation import monthly_average_report


PERIOD_CLOSE_SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory_period_closures (
    period TEXT PRIMARY KEY,
    next_period TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'closed',
    source_hash TEXT NOT NULL,
    target_hash TEXT NOT NULL,
    previous_opening_json TEXT NOT NULL DEFAULT '[]',
    item_count INTEGER NOT NULL DEFAULT 0,
    total_qty REAL NOT NULL DEFAULT 0,
    total_value REAL NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 1,
    closed_at TEXT,
    reopened_at TEXT,
    updated_at TEXT NOT NULL,
    CHECK(status IN ('closed','reopened')),
    CHECK(revision >= 1)
);
CREATE INDEX IF NOT EXISTS idx_inventory_period_closures_status
    ON inventory_period_closures(status,period);
"""

QTY_EPSILON = Decimal("0.0000005")
MONEY_EPSILON = Decimal("0.01")
COST_SCALE = Decimal("0.000000000001")


class InventoryPeriodCloseError(ValueError):
    def __init__(
        self, message: str, *, code: str = "invalid_period_close", status: int = 409,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def init_inventory_period_close_schema(conn) -> None:
    conn.executescript(PERIOD_CLOSE_SCHEMA)


def _confirmation_actor(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
        raise InventoryPeriodCloseError("Nhập tên người xác nhận (tối đa 100 ký tự)", code="actor_required", status=400)
    return value.strip()


def _close_history(conn, period: str) -> list[dict[str, Any]]:
    history = []
    for row in conn.execute(
        """SELECT event_type,created_at,metadata_json FROM audit_log WHERE entity_type='period'
           AND entity_id=? AND event_type IN ('inventory.period.close','inventory.period.reopen')
           ORDER BY id DESC LIMIT 50""", (period,),
    ):
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (TypeError, ValueError):
            metadata = {}
        history.append({"action":"close" if row["event_type"].endswith(".close") else "reopen",
                        "created_at":row["created_at"], "actor":str(metadata.get("actor") or "") if isinstance(metadata,dict) else ""})
    return history


def _period_bounds(value: Any) -> tuple[str, str, str]:
    period = str(value or "").strip()
    try:
        first = datetime.strptime(period + "-01", "%Y-%m-%d").date()
    except ValueError:
        raise InventoryPeriodCloseError(
            "Tháng cần chốt phải có dạng YYYY-MM và là tháng hợp lệ",
            code="invalid_period",
            status=400,
        ) from None
    if len(period) != 7:
        raise InventoryPeriodCloseError(
            "Tháng cần chốt phải có dạng YYYY-MM và là tháng hợp lệ",
            code="invalid_period",
            status=400,
        )
    next_first = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = next_first - timedelta(days=1)
    return first.isoformat(), last.isoformat(), next_first.strftime("%Y-%m")


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise InventoryPeriodCloseError(f"{label} không phải số hợp lệ") from None
    if not result.is_finite():
        raise InventoryPeriodCloseError(f"{label} không phải số hữu hạn")
    return result


def _stable_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _opening_rows(conn, period: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        """SELECT product_code,COALESCE(warehouse_codes_json,'[]') warehouse_codes_json,
                  qty_in,qty_out,unit_cost,source_line,status,COALESCE(note,'') note
             FROM inventory_transactions
            WHERE source_type='OPENING' AND source_id=?
            ORDER BY source_line,product_code,id""",
        (period,),
    )]


def _opening_hash(conn, period: str) -> str:
    return _stable_hash(_opening_rows(conn, period))


def _source_hash(report: Mapping[str, Any]) -> str:
    fields = (
        "product_code", "warehouse_codes", "opening_qty", "opening_value",
        "input_qty", "input_value", "output_qty", "output_value",
        "closing_qty", "closing_value", "average_unit_cost", "valuation_status",
    )
    return _stable_hash({
        "valuation_method": report.get("valuation_method", "moving_average"),
        "date_from": report["date_from"],
        "date_to": report["date_to"],
        "opening_period": report.get("opening_period") or "",
        "opening_date": report.get("opening_date") or "",
        "items": [
            {field: item.get(field) for field in fields}
            for item in sorted(report["items"], key=lambda row: str(row["product_code"]))
        ],
    })


def _safe_previous_opening_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _period_label(period: str) -> str:
    year, month = period.split("-")
    return f"{month}/{year}"


def inventory_period_close_preview(
    conn,
    period: Any,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Return a complete, read-only close preview for one calendar month."""

    date_from, date_to, next_period = _period_bounds(period)
    safe_period = date_from[:7]
    current_day = today or date.today()
    try:
        report = monthly_average_report(
            conn,
            date_from=date_from,
            date_to=date_to,
            include_zero=True,
            include_events=False,
        )
    except InvoiceValuationError as error:
        raise InventoryPeriodCloseError(
            str(error), code=error.code, status=error.status,
        ) from None

    source_hash = _source_hash(report)
    target_rows = _opening_rows(conn, next_period)
    target_hash = _stable_hash(target_rows)
    closure_row = conn.execute(
        "SELECT * FROM inventory_period_closures WHERE period=?", (safe_period,),
    ).fetchone()
    downstream = conn.execute(
        "SELECT period FROM inventory_period_closures WHERE period=? AND status='closed'",
        (next_period,),
    ).fetchone()
    next_date_to = _period_bounds(next_period)[1]
    next_movement_count = int(conn.execute(
        """SELECT COUNT(*) n FROM invoice_inventory_ledger
             WHERE status='posted' AND txn_date>=? AND txn_date<=?""",
        (next_period + "-01", next_date_to),
    ).fetchone()["n"])

    issues: list[str] = []
    if datetime.strptime(date_to, "%Y-%m-%d").date() >= current_day:
        issues.append(f"Chỉ chốt sau khi tháng {_period_label(safe_period)} đã kết thúc")
    invalid_items = [
        item for item in report["items"] if item.get("valuation_status") != "ok"
    ]
    if invalid_items:
        issues.append(
            f"Có {len(invalid_items)} mã hàng cần kiểm tra trước khi chốt"
        )
    negative_items = [
        item for item in report["items"]
        if _decimal(item.get("closing_qty"), "Tồn cuối") < -QTY_EPSILON
        or _decimal(item.get("closing_value"), "Giá trị tồn cuối") < -MONEY_EPSILON
    ]
    if negative_items:
        issues.append(f"Có {len(negative_items)} mã hàng bị âm tồn cuối")
    if downstream:
        issues.append(
            f"Tháng {_period_label(next_period)} đã chốt tiếp; phải mở tháng sau trước"
        )
    if not report["items"]:
        issues.append("Chưa có danh mục hàng để tạo tồn đầu tháng sau")
    has_source_activity = bool(report.get("opening_period")) or any(
        int(item.get("movement_count") or 0) > 0 for item in report["items"]
    )
    if report["items"] and not has_source_activity:
        issues.append("Tháng này chưa có tồn đầu hoặc phát sinh nhập, xuất để chốt")

    close_status = "not_closed"
    source_matches = target_matches = False
    revision = 0
    closed_at = reopened_at = ""
    if closure_row:
        revision = int(closure_row["revision"])
        closed_at = str(closure_row["closed_at"] or "")
        reopened_at = str(closure_row["reopened_at"] or "")
        source_matches = str(closure_row["source_hash"]) == source_hash
        target_matches = str(closure_row["target_hash"]) == target_hash
        if closure_row["status"] == "reopened":
            close_status = "reopened"
        elif source_matches and target_matches:
            close_status = "closed"
        else:
            close_status = "needs_reclose"

    total_qty = sum(_decimal(item["closing_qty"], "Tổng lượng tồn cuối") for item in report["items"])
    total_value = sum(
        _decimal(item["closing_value"], "Tổng giá trị tồn cuối") for item in report["items"]
    )
    already_current = close_status == "closed"
    qty_by_unit = {}
    for item in report["items"]:
        unit = str(item.get("unit") or "Không có ĐVT").strip().casefold()
        qty_by_unit[unit] = qty_by_unit.get(unit, Decimal(0)) + _decimal(item["closing_qty"], "Tồn cuối")
    # Closing carries posted stock only. Make downloaded-but-unposted invoices
    # visible instead of suggesting that a successful close proves completeness.
    unposted_input_count = int(conn.execute(
        """SELECT COUNT(*) FROM msmi_invoices WHERE invoice_date>=? AND invoice_date<=?
           AND invoice_type='INPUT_ELECTRONIC_INVOICE' AND receipt_status NOT IN ('posted','not_inventory')""",
        (date_from, date_to),
    ).fetchone()[0])
    unposted_output_count = int(conn.execute(
        """SELECT COUNT(*) FROM outgoing_source_invoices WHERE source='minvoice' AND invoice_date>=? AND invoice_date<=?
           AND stock_status NOT IN ('posted','reversed','not_inventory')""",
        (date_from, date_to),
    ).fetchone()[0])
    return {
        "period": safe_period,
        "period_label": _period_label(safe_period),
        "date_from": date_from,
        "date_to": date_to,
        "next_period": next_period,
        "next_period_label": _period_label(next_period),
        "status": close_status,
        "revision": revision,
        "closed_at": closed_at,
        "reopened_at": reopened_at,
        "source_hash": source_hash,
        "target_hash": target_hash,
        "source_matches": source_matches,
        "target_matches": target_matches,
        "has_existing_next_opening": bool(target_rows),
        "next_movement_count": next_movement_count,
        "item_count": len(report["items"]),
        "has_source_activity": has_source_activity,
        "nonzero_item_count": sum(
            abs(_decimal(item["closing_qty"], "Tồn cuối")) > QTY_EPSILON
            for item in report["items"]
        ),
        "total_qty": float(total_qty),
        "qty_by_unit": {unit: float(qty) for unit, qty in qty_by_unit.items() if abs(qty) > QTY_EPSILON},
        "history": _close_history(conn, safe_period),
        "total_value": float(total_value),
        "unposted_input_count": unposted_input_count,
        "unposted_output_count": unposted_output_count,
        "issues": issues,
        "problem_items": [{key: item.get(key) for key in ('product_code', 'product_name', 'unit', 'closing_qty', 'closing_value', 'valuation_status')}
                          for item in report['items'] if item in invalid_items or item in negative_items],
        "can_close": not issues and not already_current,
        "can_reopen": bool(closure_row and closure_row["status"] == "closed" and not downstream),
        "read_only": True,
        "_report": report,
    }


def _public_preview(preview: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in preview.items() if not key.startswith("_")}


def close_inventory_period(
    conn,
    period: Any,
    *,
    expected_source_hash: str,
    expected_target_hash: str,
    timestamp: str,
    today: date | None = None,
    actor: str = "",
) -> dict[str, Any]:
    """Atomically carry one month's closing balances into the next opening."""

    preview = inventory_period_close_preview(conn, period, today=today)
    if preview["source_hash"] != str(expected_source_hash or "").strip().upper():
        raise InventoryPeriodCloseError(
            "Số liệu tháng cần chốt đã thay đổi; hãy xem lại rồi xác nhận lần nữa",
            code="stale_source",
        )
    if preview["target_hash"] != str(expected_target_hash or "").strip().upper():
        raise InventoryPeriodCloseError(
            "Tồn đầu tháng sau đã thay đổi; hãy xem lại rồi xác nhận lần nữa",
            code="stale_target",
        )
    if preview["status"] == "closed":
        return {"idempotent": True, "preview": _public_preview(preview)}
    if not preview["can_close"]:
        raise InventoryPeriodCloseError(
            preview["issues"][0] if preview["issues"] else "Kỳ này chưa thể chốt",
            code="period_close_blocked",
        )

    safe_period = preview["period"]
    next_period = preview["next_period"]
    existing_closure = conn.execute(
        "SELECT * FROM inventory_period_closures WHERE period=?", (safe_period,),
    ).fetchone()
    previous_opening_json = (
        str(existing_closure["previous_opening_json"])
        if existing_closure
        else _safe_previous_opening_json(_opening_rows(conn, next_period))
    )
    report = preview["_report"]
    incoming_codes: set[str] = set()
    for item in report["items"]:
        code = str(item["product_code"])
        incoming_codes.add(code)
        qty = _decimal(item["closing_qty"], "Tồn cuối")
        value = _decimal(item["closing_value"], "Giá trị tồn cuối")
        if qty < -QTY_EPSILON or value < -MONEY_EPSILON:
            raise InventoryPeriodCloseError(
                f"Mã {code} bị âm tồn cuối; chưa chuyển sang tháng sau",
                code="negative_closing",
            )
        if abs(qty) <= QTY_EPSILON:
            qty = Decimal(0)
            unit_cost = Decimal(0)
        else:
            unit_cost = (value / qty).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
        warehouses = item.get("warehouse_codes") or []
        conn.execute(
            """INSERT INTO inventory_transactions(
                   txn_date,product_code,warehouse_codes_json,qty_in,qty_out,unit_cost,
                   source_type,source_id,source_line,status,note,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,'OPENING',?,?,'posted',?,?,?)
               ON CONFLICT(source_type,source_id,source_line) DO UPDATE SET
                   txn_date=excluded.txn_date,product_code=excluded.product_code,
                   warehouse_codes_json=excluded.warehouse_codes_json,
                   qty_in=excluded.qty_in,qty_out=excluded.qty_out,
                   unit_cost=excluded.unit_cost,status='posted',note=excluded.note,
                   updated_at=excluded.updated_at""",
            (
                next_period + "-01", code,
                json.dumps(warehouses, ensure_ascii=False, separators=(",", ":")),
                float(max(qty, Decimal(0))), float(max(-qty, Decimal(0))),
                float(max(unit_cost, Decimal(0))), next_period, code,
                f"Tự động chuyển từ tồn cuối tháng {preview['period_label']}",
                timestamp, timestamp,
            ),
        )
    stale_codes = [
        str(row["source_line"])
        for row in conn.execute(
            """SELECT source_line FROM inventory_transactions
                 WHERE source_type='OPENING' AND source_id=?""",
            (next_period,),
        )
        if str(row["source_line"]) not in incoming_codes
    ]
    if stale_codes:
        placeholders = ",".join("?" for _ in stale_codes)
        conn.execute(
            f"DELETE FROM inventory_transactions WHERE source_type='OPENING' "
            f"AND source_id=? AND source_line IN ({placeholders})",
            (next_period, *stale_codes),
        )

    # Existing movements in the next month must still be valid under the new
    # opening snapshot.  Any negative-stock rebuild aborts the whole close.
    try:
        monthly_average_report(
            conn,
            date_from=next_period + "-01",
            date_to=_period_bounds(next_period)[1],
            include_zero=True,
        )
    except InvoiceValuationError as error:
        raise InventoryPeriodCloseError(
            "Không thể chuyển tồn vì số liệu tháng sau sẽ không hợp lệ: " + str(error),
            code="next_period_invalid",
        ) from None

    target_hash = _opening_hash(conn, next_period)
    revision = int(existing_closure["revision"] if existing_closure else 0) + 1
    conn.execute(
        """INSERT INTO inventory_period_closures(
               period,next_period,status,source_hash,target_hash,previous_opening_json,
               item_count,total_qty,total_value,revision,closed_at,reopened_at,updated_at
           ) VALUES(?,?,'closed',?,?,?,?,?,?,?,?,'',?)
           ON CONFLICT(period) DO UPDATE SET
               next_period=excluded.next_period,status='closed',
               source_hash=excluded.source_hash,target_hash=excluded.target_hash,
               item_count=excluded.item_count,total_qty=excluded.total_qty,
               total_value=excluded.total_value,revision=excluded.revision,
               closed_at=excluded.closed_at,reopened_at='',updated_at=excluded.updated_at""",
        (
            safe_period, next_period, preview["source_hash"], target_hash,
            previous_opening_json, preview["item_count"], preview["total_qty"],
            preview["total_value"], revision, timestamp, timestamp,
        ),
    )
    conn.execute(
        """INSERT INTO audit_log(
               event_type,entity_type,entity_id,status,message,metadata_json,created_at
           ) VALUES('inventory.period.close','period',?,'ok','',?,?)""",
        (
            safe_period,
            json.dumps({
                "next_period": next_period,
                "items": preview["item_count"],
                "nonzero_items": preview["nonzero_item_count"],
                "total_qty": preview["total_qty"],
                "total_value": preview["total_value"],
                "revision": revision,
                "actor": actor,
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            timestamp,
        ),
    )
    result = inventory_period_close_preview(conn, safe_period, today=today)
    return {"idempotent": False, "preview": _public_preview(result)}


def reopen_inventory_period(
    conn,
    period: Any,
    *,
    timestamp: str,
    actor: str = "",
) -> dict[str, Any]:
    """Remove a generated next opening so the source month can be rebuilt."""

    date_from, _date_to, next_period = _period_bounds(period)
    safe_period = date_from[:7]
    closure = conn.execute(
        "SELECT * FROM inventory_period_closures WHERE period=?", (safe_period,),
    ).fetchone()
    if not closure or closure["status"] != "closed":
        raise InventoryPeriodCloseError(
            "Tháng này chưa được chốt nên không cần mở lại",
            code="period_not_closed",
            status=400,
        )
    downstream = conn.execute(
        "SELECT 1 FROM inventory_period_closures WHERE period=? AND status='closed'",
        (next_period,),
    ).fetchone()
    if downstream:
        raise InventoryPeriodCloseError(
            f"Tháng {_period_label(next_period)} đã chốt tiếp; phải mở tháng đó trước",
            code="downstream_closed",
        )
    conn.execute(
        "DELETE FROM inventory_transactions WHERE source_type='OPENING' AND source_id=?",
        (next_period,),
    )
    revision = int(closure["revision"]) + 1
    conn.execute(
        """UPDATE inventory_period_closures
              SET status='reopened',target_hash='',revision=?,reopened_at=?,updated_at=?
            WHERE period=?""",
        (revision, timestamp, timestamp, safe_period),
    )
    conn.execute(
        """INSERT INTO audit_log(
               event_type,entity_type,entity_id,status,message,metadata_json,created_at
           ) VALUES('inventory.period.reopen','period',?,'ok','',?,?)""",
        (
            safe_period,
            json.dumps({"removed_opening_period": next_period, "revision": revision, "actor": actor},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            timestamp,
        ),
    )
    return {"period": safe_period, "next_period": next_period, "revision": revision}


def register_inventory_period_close_routes(
    app: Any,
    ctx: Mapping[str, Any],
) -> None:
    db_factory = ctx["db"]
    now_iso: Callable[[], str] = ctx["now_iso"]
    today_factory: Callable[[], date] = ctx.get("today", date.today)

    def error_response(error: InventoryPeriodCloseError):
        return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.get("/api/inventory/month-close/preview")
    def api_inventory_month_close_preview():
        try:
            with db_factory() as conn:
                preview = inventory_period_close_preview(
                    conn, request.args.get("period"), today=today_factory(),
                )
                return jsonify({"ok": True, **_public_preview(preview)})
        except InventoryPeriodCloseError as error:
            return error_response(error)

    @app.post("/api/inventory/month-close")
    def api_inventory_month_close():
        body = request.get_json(force=True) or {}
        if body.get("confirmed") is not True:
            return jsonify({
                "ok": False,
                "error": "Cần xác nhận trước khi chuyển tồn sang tháng sau",
                "code": "confirmation_required",
            }), 400
        try:
            actor = _confirmation_actor(body.get("actor"))
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = close_inventory_period(
                    conn,
                    body.get("period"),
                    expected_source_hash=body.get("source_hash"),
                    expected_target_hash=body.get("target_hash"),
                    timestamp=now_iso(),
                    today=today_factory(),
                    actor=actor,
                )
                return jsonify({"ok": True, **result})
        except InventoryPeriodCloseError as error:
            return error_response(error)

    @app.post("/api/inventory/month-close/reopen")
    def api_inventory_month_close_reopen():
        body = request.get_json(force=True) or {}
        if body.get("confirmed") is not True:
            return jsonify({
                "ok": False,
                "error": "Cần xác nhận trước khi mở lại tháng",
                "code": "confirmation_required",
            }), 400
        try:
            actor = _confirmation_actor(body.get("actor"))
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = reopen_inventory_period(
                    conn, body.get("period"), timestamp=now_iso(), actor=actor,
                )
                return jsonify({"ok": True, **result})
        except InventoryPeriodCloseError as error:
            return error_response(error)


__all__ = [
    "InventoryPeriodCloseError",
    "close_inventory_period",
    "init_inventory_period_close_schema",
    "inventory_period_close_preview",
    "register_inventory_period_close_routes",
    "reopen_inventory_period",
]
