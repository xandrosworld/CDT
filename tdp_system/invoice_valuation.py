"""Deterministic moving-average valuation for the canonical invoice ledger."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from typing import Any

from flask import jsonify, request

try:
    from invoice_inventory import InvoiceInventoryError, selected_opening_snapshot
except ImportError:  # pragma: no cover - package invocation
    from .invoice_inventory import InvoiceInventoryError, selected_opening_snapshot


getcontext().prec = 34
MONEY_SCALE = Decimal("0.01")
QTY_SCALE = Decimal("0.000001")
COST_SCALE = Decimal("0.000001")
EPSILON = Decimal("0.0000005")


class InvoiceValuationError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def _date(value: Any, label: str) -> str:
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise InvoiceValuationError(
            f"{label} phải là ngày YYYY-MM-DD hợp lệ", code="invalid_period", status=400
        ) from None


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        raise InvoiceValuationError(f"{label} không phải số hợp lệ", code="invalid_number") from None
    if not result.is_finite():
        raise InvoiceValuationError(f"{label} không phải số hữu hạn", code="invalid_number")
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


def _number(value: Decimal, scale: Decimal) -> float:
    normalized = value.quantize(scale, rounding=ROUND_HALF_UP)
    if normalized == 0:
        normalized = Decimal(0)
    return float(normalized)


def _state(product) -> dict[str, Any]:
    return {
        "product_code": str(product["code"]),
        "product_name": str(product["name"] or ""),
        "unit": str(product["unit"] or ""),
        "warehouse_codes": [],
        "qty": Decimal(0),
        "value": Decimal(0),
        "negative_opening": False,
        "zero_qty_nonzero_value": False,
        "period_input_qty": Decimal(0),
        "period_input_value": Decimal(0),
        "period_gross_output_qty": Decimal(0),
        "period_gross_output_value": Decimal(0),
        "period_reversal_qty": Decimal(0),
        "period_reversal_value": Decimal(0),
        "movement_count": 0,
    }


def _average(state: dict[str, Any]) -> Decimal:
    if abs(state["qty"]) <= EPSILON:
        return Decimal(0)
    average = state["value"] / state["qty"]
    return average if average >= 0 else Decimal(0)


def _opening_contract(conn, date_from: str, date_to: str) -> tuple[str, str] | None:
    try:
        opening = selected_opening_snapshot(conn, date_from)
    except InvoiceInventoryError as error:
        raise InvoiceValuationError(str(error), code=error.code, status=error.status) from None
    opening_date = opening[1] if opening else "0001-01-01"
    later = conn.execute(
        """SELECT DISTINCT source_id,txn_date FROM inventory_transactions
           WHERE source_type='OPENING' AND status='posted'
             AND txn_date>? AND txn_date<=? ORDER BY txn_date,source_id""",
        (opening_date if opening else date_from, date_to),
    ).fetchall()
    if later:
        raise InvoiceValuationError(
            "Khoảng báo cáo đi qua một kỳ tồn đầu mới; hãy tách báo cáo theo kỳ tồn đầu",
            code="opening_period_crossed",
            status=400,
        )
    return opening


def moving_average_report(
    conn,
    *,
    date_from: Any,
    date_to: Any,
    include_zero: bool = False,
    include_events: bool = False,
) -> dict[str, Any]:
    """Rebuild a period from immutable source events in one stable order.

    Same-day input is valued before output. Output uses the moving weighted
    average immediately before that output. Money is rounded half-up to 0.01
    per movement; quantity and displayed unit cost use six decimals.
    """
    safe_from = _date(date_from, "Từ ngày")
    safe_to = _date(date_to, "Đến ngày")
    if safe_from > safe_to:
        raise InvoiceValuationError(
            "Từ ngày không được lớn hơn Đến ngày", code="invalid_period", status=400
        )
    opening = _opening_contract(conn, safe_from, safe_to)
    opening_source = opening[0] if opening else ""
    opening_date = opening[1] if opening else "0001-01-01"
    products = conn.execute("SELECT code,name,COALESCE(unit,'') unit FROM products ORDER BY code").fetchall()
    states = {str(row["code"]): _state(row) for row in products}

    if opening:
        for row in conn.execute(
            """SELECT product_code,warehouse_codes_json,qty_in,qty_out,unit_cost
               FROM inventory_transactions
               WHERE source_type='OPENING' AND status='posted' AND source_id=?
               ORDER BY product_code,source_line,id""",
            (opening_source,),
        ):
            state = states[str(row["product_code"])]
            try:
                warehouse_codes = json.loads(str(row["warehouse_codes_json"] or "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                warehouse_codes = []
            if not isinstance(warehouse_codes, list):
                warehouse_codes = []
            for warehouse_code in warehouse_codes:
                clean_code = str(warehouse_code or "").strip()
                if clean_code and clean_code not in state["warehouse_codes"]:
                    state["warehouse_codes"].append(clean_code)
            qty = _decimal(row["qty_in"], "SL tồn đầu vào") - _decimal(
                row["qty_out"], "SL tồn đầu ra"
            )
            cost = _decimal(row["unit_cost"], "Đơn giá tồn đầu")
            if cost < 0:
                raise InvoiceValuationError("Đơn giá tồn đầu không được âm", code="negative_cost")
            state["qty"] += qty
            state["value"] += _money(qty * cost)
        for state in states.values():
            state["negative_opening"] = state["qty"] < -EPSILON

    ledger = conn.execute(
        """SELECT l.* FROM invoice_inventory_ledger l
           WHERE l.status='posted' AND l.txn_date>=? AND l.txn_date<=?
           ORDER BY l.txn_date,
                    CASE
                      WHEN l.direction='input' AND l.event_type='POST' THEN 10
                      WHEN l.direction='input' AND l.event_type='REVERSAL' THEN 15
                      WHEN l.direction='output' AND l.event_type='POST' THEN 20
                      WHEN l.direction='output' AND l.event_type='REVERSAL' THEN 30
                      ELSE 90 END,
                    l.source_invoice_table,l.source_invoice_id,l.source_line_index,l.id""",
        (opening_date, safe_to),
    ).fetchall()
    original_output_values: dict[str, tuple[Decimal, Decimal]] = {}
    event_payload: list[dict[str, Any]] = []

    def apply(row, in_period: bool) -> None:
        state = states[str(row["product_code"])]
        delta = _decimal(row["qty_delta"], "Số lượng ledger")
        direction = str(row["direction"])
        event_type = str(row["event_type"])
        cost = Decimal(0)
        amount = Decimal(0)
        movement = ""
        if direction == "input" and event_type == "POST" and delta > 0:
            cost = _decimal(row["unit_cost"], "Đơn giá nhập")
            if cost < 0:
                raise InvoiceValuationError("Đơn giá nhập không được âm", code="negative_cost")
            amount = _money(delta * cost)
            state["qty"] += delta
            state["value"] += amount
            movement = "input"
            if in_period:
                state["period_input_qty"] += delta
                state["period_input_value"] += amount
        elif direction == "input" and event_type == "REVERSAL" and delta < 0:
            reference = str(row["reverses_event_key"] or "")
            source = conn.execute(
                """SELECT direction,event_type,source_invoice_table,source_invoice_id,
                          source_line_id,product_code,qty_delta,unit_cost
                     FROM invoice_inventory_ledger WHERE event_key=?""",
                (reference,),
            ).fetchone()
            if (
                not source or str(source["direction"]) != "input"
                or str(source["event_type"]) != "POST"
                or str(source["source_invoice_table"]) != str(row["source_invoice_table"])
                or int(source["source_invoice_id"]) != int(row["source_invoice_id"])
                or int(source["source_line_id"]) != int(row["source_line_id"])
                or str(source["product_code"]) != str(row["product_code"])
                or abs(_decimal(source["qty_delta"], "SL nhập gốc") + delta) > EPSILON
            ):
                raise InvoiceValuationError(
                    "Hoàn tác nhập không khớp bút toán nhập gốc",
                    code="input_reversal_source_invalid",
                )
            qty_out = -delta
            if state["qty"] + EPSILON < qty_out or state["qty"] <= EPSILON:
                raise InvoiceValuationError(
                    f"Mã {state['product_code']} âm kho khi hoàn tác nhập tại {row['txn_date']}",
                    code="negative_stock",
                )
            cost = _decimal(source["unit_cost"], "Đơn giá nhập gốc")
            if cost <= 0:
                raise InvoiceValuationError(
                    "Đơn giá bút toán nhập gốc phải lớn hơn 0", code="negative_cost",
                )
            amount = _money(delta * cost)
            state["qty"] += delta
            state["value"] += amount
            if state["value"] < -MONEY_SCALE:
                raise InvoiceValuationError(
                    f"Mã {state['product_code']} âm giá trị kho khi hoàn tác nhập tại {row['txn_date']}",
                    code="negative_inventory_value",
                )
            if abs(state["qty"]) <= EPSILON and abs(state["value"]) <= MONEY_SCALE:
                state["qty"] = Decimal(0)
                state["value"] = Decimal(0)
            movement = "input_reversal"
            if in_period:
                state["period_input_qty"] += delta
                state["period_input_value"] += amount
        elif direction == "output" and event_type == "POST" and delta < 0:
            qty_out = -delta
            if state["qty"] + EPSILON < qty_out or state["qty"] <= EPSILON:
                raise InvoiceValuationError(
                    f"Mã {state['product_code']} âm kho khi rebuild tại {row['txn_date']}",
                    code="negative_stock",
                )
            cost = _average(state)
            amount = state["value"] if abs(state["qty"] - qty_out) <= EPSILON else _money(qty_out * cost)
            state["qty"] -= qty_out
            state["value"] -= amount
            if abs(state["qty"]) <= EPSILON:
                state["qty"] = Decimal(0)
                state["value"] = Decimal(0)
            original_output_values[str(row["event_key"])] = (cost, amount)
            movement = "output"
            if in_period:
                state["period_gross_output_qty"] += qty_out
                state["period_gross_output_value"] += amount
        elif direction == "output" and event_type == "REVERSAL" and delta > 0:
            reference = str(row["reverses_event_key"] or "")
            original = original_output_values.get(reference)
            if original:
                cost, original_amount = original
                original_row = conn.execute(
                    "SELECT ABS(qty_delta) qty FROM invoice_inventory_ledger WHERE event_key=?",
                    (reference,),
                ).fetchone()
                original_qty = _decimal(original_row["qty"], "SL xuất gốc") if original_row else Decimal(0)
                amount = original_amount if abs(original_qty - delta) <= EPSILON else _money(delta * cost)
            else:
                source = conn.execute(
                    "SELECT unit_cost FROM invoice_inventory_ledger WHERE event_key=?",
                    (reference,),
                ).fetchone()
                stored_cost = _decimal(source["unit_cost"], "Giá vốn xuất gốc") if source else Decimal(0)
                if not source or stored_cost < 0:
                    raise InvoiceValuationError(
                        "Reversal tham chiếu bút toán trước kỳ tồn nhưng thiếu snapshot giá vốn",
                        code="reversal_cost_missing",
                    )
                cost = stored_cost
                amount = _money(delta * cost)
            state["qty"] += delta
            state["value"] += amount
            movement = "reversal"
            if in_period:
                state["period_reversal_qty"] += delta
                state["period_reversal_value"] += amount
        else:
            raise InvoiceValuationError(
                "Ledger có chiều/loại/số lượng không đúng contract valuation",
                code="ledger_contract_invalid",
            )
        if state["qty"] < -EPSILON:
            raise InvoiceValuationError(
                f"Mã {state['product_code']} âm kho sau {row['txn_date']}", code="negative_stock"
            )
        if abs(state["qty"]) <= EPSILON and abs(state["value"]) > MONEY_SCALE:
            state["zero_qty_nonzero_value"] = True
        if in_period:
            state["movement_count"] += 1
            if include_events:
                event_payload.append({
                    "ledger_event_id": int(row["id"]),
                    "event_type": event_type,
                    "movement": movement,
                    "source_invoice_table": row["source_invoice_table"],
                    "source_invoice_id": int(row["source_invoice_id"]),
                    "source_line_id": int(row["source_line_id"]),
                    "source_line_index": int(row["source_line_index"]),
                    "product_code": row["product_code"],
                    "txn_date": row["txn_date"],
                    "qty_delta": _number(delta, QTY_SCALE),
                    "valuation_unit_cost": _number(cost, COST_SCALE),
                    "valuation_amount": _number(amount, MONEY_SCALE),
                    "mapping_revision_id": (
                        int(row["mapping_revision_id"])
                        if row["mapping_revision_id"] is not None else None
                    ),
                    "confirmation_id": int(row["confirmation_id"]),
                })

    for row in ledger:
        if str(row["txn_date"]) < safe_from:
            apply(row, False)

    opening_balances = {
        code: (state["qty"], state["value"]) for code, state in states.items()
    }
    for row in ledger:
        if str(row["txn_date"]) >= safe_from:
            apply(row, True)

    items = []
    for code, state in states.items():
        opening_qty, opening_value = opening_balances[code]
        net_output_qty = state["period_gross_output_qty"] - state["period_reversal_qty"]
        net_output_value = state["period_gross_output_value"] - state["period_reversal_value"]
        if state["negative_opening"]:
            valuation_status = "negative_opening_review"
        elif state["zero_qty_nonzero_value"]:
            valuation_status = "zero_qty_value_review"
        else:
            valuation_status = "ok"
        item = {
            "product_code": code,
            "product_name": state["product_name"],
            "unit": state["unit"],
            "warehouse_codes": list(state["warehouse_codes"]),
            "opening_qty": _number(opening_qty, QTY_SCALE),
            "opening_value": _number(opening_value, MONEY_SCALE),
            "input_qty": _number(state["period_input_qty"], QTY_SCALE),
            "input_value": _number(state["period_input_value"], MONEY_SCALE),
            "gross_output_qty": _number(state["period_gross_output_qty"], QTY_SCALE),
            "gross_output_value": _number(state["period_gross_output_value"], MONEY_SCALE),
            "reversal_qty": _number(state["period_reversal_qty"], QTY_SCALE),
            "reversal_value": _number(state["period_reversal_value"], MONEY_SCALE),
            "output_qty": _number(net_output_qty, QTY_SCALE),
            "output_value": _number(net_output_value, MONEY_SCALE),
            "closing_qty": _number(state["qty"], QTY_SCALE),
            "closing_value": _number(state["value"], MONEY_SCALE),
            "average_unit_cost": _number(_average(state), COST_SCALE),
            "movement_count": int(state["movement_count"]),
            "valuation_status": valuation_status,
        }
        material = any(abs(float(item[key])) > 1e-9 for key in (
            "opening_qty", "input_qty", "output_qty", "closing_qty", "opening_value",
            "input_value", "output_value", "closing_value",
        ))
        if include_zero or material:
            items.append(item)

    return {
        "date_from": safe_from,
        "date_to": safe_to,
        "opening_period": opening_source,
        "opening_date": opening_date if opening else "",
        "rounding": {"quantity_decimals": 6, "unit_cost_decimals": 6, "money_decimals": 2,
                     "method": "ROUND_HALF_UP_PER_MOVEMENT"},
        "same_day_order": ["input", "input_reversal", "output", "reversal"],
        "items": items,
        "events": event_payload if include_events else [],
        "read_only": True,
    }


def moving_average_costs(conn, as_of: Any) -> dict[str, float]:
    safe_date = _date(as_of, "Ngày tính giá vốn")
    report = moving_average_report(
        conn,
        date_from=safe_date,
        date_to=safe_date,
        include_zero=True,
        include_events=False,
    )
    return {row["product_code"]: float(row["average_unit_cost"]) for row in report["items"]}


def register_invoice_valuation_routes(app, ctx) -> None:
    db_factory = ctx["db"]

    @app.get("/api/invoice-valuation")
    def api_invoice_valuation():
        try:
            with db_factory() as conn:
                return jsonify({
                    "ok": True,
                    **moving_average_report(
                        conn,
                        date_from=request.args.get("from"),
                        date_to=request.args.get("to"),
                        include_zero=request.args.get("include_zero") == "1",
                        include_events=request.args.get("include_events") == "1",
                    ),
                })
        except InvoiceValuationError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status
