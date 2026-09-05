"""Audited, optimistic line-level sell-price overrides."""

from __future__ import annotations

import json
import math
from typing import Any

from flask import jsonify, request


ORDER_PRICE_OVERRIDE_SCHEMA = """
CREATE TABLE IF NOT EXISTS order_sell_price_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    batch_id INTEGER NOT NULL,
    old_price REAL NOT NULL,
    new_price REAL NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    expected_revision INTEGER NOT NULL,
    new_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    CHECK(old_price >= 0),
    CHECK(new_price >= 0),
    CHECK(expected_revision >= 1),
    CHECK(new_revision = expected_revision + 1)
);
CREATE INDEX IF NOT EXISTS idx_order_price_overrides_order
    ON order_sell_price_overrides(order_id,id DESC);
CREATE INDEX IF NOT EXISTS idx_order_price_overrides_batch
    ON order_sell_price_overrides(batch_id,id DESC);
"""


def init_order_price_override_schema(conn) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
    savepoint = "order_price_override_schema"
    statements = []
    if "sell_price_revision" not in columns:
        statements.append(
            "ALTER TABLE orders ADD COLUMN sell_price_revision INTEGER NOT NULL DEFAULT 1;"
        )
    if "sell_price_source" not in columns:
        statements.append(
            "ALTER TABLE orders ADD COLUMN sell_price_source TEXT NOT NULL DEFAULT 'import_or_standard';"
        )
    if "sell_price_override_at" not in columns:
        statements.append("ALTER TABLE orders ADD COLUMN sell_price_override_at TEXT;")
    try:
        conn.executescript(
            f"SAVEPOINT {savepoint};\n" + "\n".join(statements) + "\n" + ORDER_PRICE_OVERRIDE_SCHEMA
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception:
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            pass
        raise


def _error(message: str, code: str, status: int):
    return jsonify({"ok": False, "error": message, "code": code}), status


def direct_price_change_ids(current_rows: dict[int, dict[str, Any]], patches) -> list[int]:
    """Detect attempts to bypass the dedicated audited endpoint."""
    changed = []
    for patch in patches:
        if not isinstance(patch, dict) or "sell_price" not in patch:
            continue
        order_id = int(patch.get("id") or 0)
        current = current_rows.get(order_id)
        if not current:
            continue
        try:
            incoming = float(patch["sell_price"])
            old_price = float(current["sell_price"])
        except (TypeError, ValueError):
            changed.append(order_id)
            continue
        if not math.isfinite(incoming) or abs(incoming - old_price) > 1e-9:
            changed.append(order_id)
    return changed


def register_order_price_override_routes(app, helpers) -> None:
    db_factory = helpers["db"]
    now_iso = helpers["now_iso"]
    clean_text = helpers["clean_text"]
    finite_number = helpers["finite_number"]
    batch_mutation_blocker = helpers["batch_mutation_blocker"]
    product_lookup = helpers["product_lookup"]
    resolve_order = helpers["resolve_order"]
    clear_batch_derived_inventory = helpers["clear_batch_derived_inventory"]
    batch_payload = helpers["batch_payload"]
    audit_event = helpers["audit_event"]
    sync_payable_ledger = helpers.get("sync_payable_ledger")
    sync_receivable_ledger = helpers.get("sync_receivable_ledger")

    @app.put("/api/orders/sell-price-overrides")
    def api_order_sell_price_overrides():
        body = request.get_json(force=True) or {}
        try:
            batch_id = int(body.get("batch_id") or 0)
        except (TypeError, ValueError):
            return _error("Phiên đơn không hợp lệ", "invalid_batch", 400)
        actor = clean_text(body.get("actor"))
        reason = clean_text(body.get("reason"))
        items = body.get("items")
        if not batch_id or not isinstance(items, list) or not items:
            return _error("Cần phiên đơn và ít nhất một dòng giá", "missing_items", 400)
        if len(items) > 5000:
            return _error("Mỗi lần chỉ sửa tối đa 5.000 dòng giá", "too_many_items", 413)
        if not actor or len(actor) > 120:
            return _error("Cần ghi người thực hiện (tối đa 120 ký tự)", "actor_required", 400)
        if not reason or len(reason) > 500:
            return _error("Cần ghi lý do thay đổi (tối đa 500 ký tự)", "reason_required", 400)
        prepared_input = []
        seen = set()
        try:
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Dòng giá không hợp lệ")
                order_id = int(item.get("id") or 0)
                revision = int(item.get("expected_revision") or 0)
                price = finite_number(item.get("sell_price"), "Giá bán")
                if order_id <= 0 or revision <= 0 or order_id in seen:
                    raise ValueError("Mã dòng/revision bị thiếu, trùng hoặc không hợp lệ")
                if price < 0:
                    raise ValueError("Giá bán không được âm")
                seen.add(order_id)
                prepared_input.append((order_id, revision, price))
        except (TypeError, ValueError) as exc:
            return _error(str(exc), "invalid_price_patch", 400)

        with db_factory() as conn:
            conn.execute("BEGIN IMMEDIATE")
            batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
            if not batch:
                return _error("Không tìm thấy phiên đơn", "batch_not_found", 404)
            blocked = batch_mutation_blocker(conn, batch_id)
            if blocked:
                return _error(blocked, "batch_locked", 409)
            placeholders = ",".join("?" for _ in prepared_input)
            current_rows = {
                int(row["id"]): dict(row)
                for row in conn.execute(
                    f"SELECT * FROM orders WHERE batch_id=? AND id IN ({placeholders})",
                    (batch_id, *(item[0] for item in prepared_input)),
                )
            }
            if len(current_rows) != len(prepared_input):
                return _error(
                    "Một số dòng không còn thuộc phiên đang mở; hãy tải lại",
                    "order_set_changed",
                    409,
                )
            stale_ids = [
                order_id for order_id, expected_revision, _ in prepared_input
                if int(current_rows[order_id].get("sell_price_revision") or 1) != expected_revision
            ]
            if stale_ids:
                return jsonify({
                    "ok": False,
                    "error": "Giá đã được người khác sửa; hãy tải lại trước khi lưu",
                    "code": "stale_price_revision",
                    "stale_ids": stale_ids[:50],
                }), 409

            lookup = product_lookup(conn)
            changes = []
            for order_id, expected_revision, price in prepared_input:
                current = current_rows[order_id]
                nature = clean_text(current.get("invoice_nature") or "1")
                if nature == "2" and abs(price) > 1e-9:
                    return _error(
                        "Dòng khuyến mại phải giữ giá bán bằng 0",
                        "promotion_price_must_be_zero",
                        400,
                    )
                if nature != "2" and price <= 0:
                    return _error(
                        "Dòng hàng hóa thường phải có giá bán lớn hơn 0",
                        "positive_price_required",
                        400,
                    )
                old_price = float(current["sell_price"])
                if abs(old_price - price) <= 1e-9:
                    continue
                candidate = dict(current)
                candidate["sell_price"] = price
                resolved = resolve_order(
                    conn, candidate, batch["work_date"], *lookup,
                )
                changes.append({
                    "order_id": order_id,
                    "expected_revision": expected_revision,
                    "new_revision": expected_revision + 1,
                    "old_price": old_price,
                    "new_price": price,
                    "errors": resolved["errors"],
                    "warnings": resolved["warnings"],
                })
            if not changes:
                payload = batch_payload(conn, batch_id)
                payload.update(ok=True, updated=0, unchanged=len(prepared_input))
                return jsonify(payload)

            timestamp = now_iso()
            clear_batch_derived_inventory(conn, batch_id)
            for change in changes:
                cursor = conn.execute(
                    """UPDATE orders SET sell_price=?,sell_price_revision=?,
                       sell_price_source='manual_override',sell_price_override_at=?,
                       errors=?,warnings=?,updated_at=?
                       WHERE id=? AND batch_id=? AND sell_price_revision=?""",
                    (
                        change["new_price"], change["new_revision"], timestamp,
                        json.dumps(change["errors"], ensure_ascii=False),
                        json.dumps(change["warnings"], ensure_ascii=False), timestamp,
                        change["order_id"], batch_id, change["expected_revision"],
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("optimistic sell-price update lost inside transaction")
                override_id = int(conn.execute(
                    """INSERT INTO order_sell_price_overrides(
                           order_id,batch_id,old_price,new_price,reason,actor,
                           expected_revision,new_revision,created_at
                       ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        change["order_id"], batch_id, change["old_price"], change["new_price"],
                        reason, actor, change["expected_revision"], change["new_revision"], timestamp,
                    ),
                ).lastrowid)
                audit_event(
                    conn,
                    "order.sell_price.override",
                    entity_type="order",
                    entity_id=change["order_id"],
                    metadata={
                        "override_id": override_id,
                        "batch_id": batch_id,
                        "old_price": change["old_price"],
                        "new_price": change["new_price"],
                        "reason": reason,
                        "actor": actor,
                        "expected_revision": change["expected_revision"],
                        "new_revision": change["new_revision"],
                    },
                )
            conn.execute(
                "UPDATE batches SET status='draft',approved_at=NULL WHERE id=?",
                (batch_id,),
            )
            if sync_payable_ledger is not None:
                sync_payable_ledger(conn, timestamp=timestamp)
            if sync_receivable_ledger is not None:
                sync_receivable_ledger(conn, timestamp=timestamp)
            payload = batch_payload(conn, batch_id)
            payload.update(ok=True, updated=len(changes), unchanged=len(prepared_input) - len(changes))
            return jsonify(payload)

    @app.get("/api/orders/sell-price-overrides")
    def api_order_sell_price_override_history():
        try:
            batch_id = int(request.args.get("batch_id") or 0)
            order_id = int(request.args.get("order_id") or 0)
        except (TypeError, ValueError):
            return _error("Bộ lọc lịch sử không hợp lệ", "invalid_history_filter", 400)
        if not batch_id and not order_id:
            return _error("Cần batch_id hoặc order_id", "history_filter_required", 400)
        where = "batch_id=?" if batch_id else "order_id=?"
        value = batch_id or order_id
        with db_factory() as conn:
            rows = [dict(row) for row in conn.execute(
                f"""SELECT id,order_id,batch_id,old_price,new_price,reason,actor,
                           expected_revision,new_revision,created_at
                    FROM order_sell_price_overrides WHERE {where} ORDER BY id DESC LIMIT 1000""",
                (value,),
            )]
            return jsonify({"ok": True, "items": rows})
