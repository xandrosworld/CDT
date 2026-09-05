"""Operational stock. Never a source for invoiceable quantities.

Openings/receipts are explicitly entered, not inferred from a purchase order,
an invoice or the legacy mixed inventory table. Current customer orders are a
live claim, not a second posted issue: edits, removal and reimports therefore
cannot leave duplicate issues. The order audit trail is append-only.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from flask import jsonify, request


def init_physical_inventory_schema(conn):
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(orders)")}
    if "physical_stage" not in columns:
        conn.execute("ALTER TABLE orders ADD COLUMN physical_stage TEXT NOT NULL DEFAULT 'ordered'")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS physical_stock_openings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_code TEXT NOT NULL, unit TEXT NOT NULL, start_date TEXT NOT NULL,
        qty REAL NOT NULL, unit_cost REAL NOT NULL,
        actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS physical_opening_product ON physical_stock_openings(product_code,id);
    CREATE TABLE IF NOT EXISTS physical_stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_key TEXT NOT NULL UNIQUE,
        product_code TEXT NOT NULL, unit TEXT NOT NULL, work_date TEXT NOT NULL,
        qty REAL NOT NULL, unit_cost REAL NOT NULL,
        actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS physical_order_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,
        batch_id INTEGER NOT NULL, action TEXT NOT NULL, before_json TEXT,
        after_json TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS order_reimport_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL,
        previous_source TEXT NOT NULL, next_source TEXT NOT NULL,
        rows_json TEXT NOT NULL, previous_keys_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
    );
    """)
    if 'previous_keys_json' not in {r['name'] for r in conn.execute('PRAGMA table_info(order_reimport_history)')}:
        conn.execute("ALTER TABLE order_reimport_history ADD COLUMN previous_keys_json TEXT NOT NULL DEFAULT '[]'")
    fields = ("work_date", "product_code", "unit", "qty", "actual_delivered",
              "customer_return_qty", "physical_stage", "kitchen")
    def snapshot(prefix):
        return "json_object(" + ",".join(f"'{f}',{prefix}.{f}" for f in fields) + ")"
    for action, old, new, ref in (("INSERT", "NULL", snapshot("NEW"), "NEW"),
                                  ("UPDATE", snapshot("OLD"), snapshot("NEW"), "NEW"),
                                  ("DELETE", snapshot("OLD"), "NULL", "OLD")):
        when = ("WHEN " + " OR ".join(f"OLD.{f} IS NOT NEW.{f}" for f in fields)) if action == "UPDATE" else ""
        conn.execute(f"""CREATE TRIGGER IF NOT EXISTS physical_order_{action.lower()}
            AFTER {action} ON orders {when} BEGIN
              INSERT INTO physical_order_history(order_id,batch_id,action,before_json,after_json,created_at)
              VALUES({ref}.id,{ref}.batch_id,'{action}',{old},{new},datetime('now'));
            END""")
    # A copied plan is stale after a material change, not still 'ordered'.
    for table, fields in (("orders", ("qty", "supplier", "product_name", "unit", "kitchen", "note")),
                          ("purchase_order_lines", ("order_qty", "supplier", "note")),
                          ("purchase_workbook_lines", ("actual_qty", "supplier", "note"))):
        for action, ref in (("INSERT", "NEW"), ("DELETE", "OLD"), ("UPDATE", "NEW")):
            when = ("WHEN " + " OR ".join(f"OLD.{f} IS NOT NEW.{f}" for f in fields)) if action == "UPDATE" else ""
            conn.execute(f"""CREATE TRIGGER IF NOT EXISTS physical_reopen_{table}_{action.lower()}
                AFTER {action} ON {table} {when} BEGIN
                  UPDATE supplier_order_statuses SET status='reopened',revision=revision+1,
                      reopened_at=datetime('now'),updated_at=datetime('now')
                  WHERE batch_id={ref}.batch_id AND status='ordered';
                END""")


def unit_key(value):
    return " ".join(str(value or "").strip().casefold().split())


def number(value, label, *, negative=False):
    if isinstance(value, bool):
        raise ValueError(f"{label} phải là số")
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{label} phải là số") from None
    if not math.isfinite(value) or (not negative and value < 0):
        raise ValueError(f"{label} không hợp lệ")
    return value


def stock_date(value):
    result = str(value or "")
    if date.fromisoformat(result).isoformat() != result:
        raise ValueError("Ngày phải có dạng năm-tháng-ngày")
    return result


def text_field(body, key, label):
    value = str(body.get(key) or "").strip()
    if not value or len(value) > 500:
        raise ValueError(f"Cần {label} (tối đa 500 ký tự)")
    return value


def physical_stock_payload(conn, *, search="", status="all"):
    if status not in {"all", "available", "empty", "short", "uninitialized", "review"}:
        raise ValueError("Bộ lọc kho thực tế không hợp lệ")
    openings = {r["product_code"]: dict(r) for r in conn.execute("""
        SELECT * FROM physical_stock_openings WHERE id IN (
          SELECT MAX(id) FROM physical_stock_openings GROUP BY product_code)""")}
    orders = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY id")]
    movements = [dict(r) for r in conn.execute("SELECT * FROM physical_stock_movements ORDER BY id")]
    by_order, by_movement = defaultdict(list), defaultdict(list)
    for row in orders:
        by_order[row["product_code"]].append(row)
    for row in movements:
        by_movement[row["product_code"]].append(row)
    items, issues = [], []
    product_codes = set()
    for product in conn.execute("SELECT code,name,unit FROM products ORDER BY name,code"):
        code, unit = product["code"], product["unit"] or ""
        product_codes.add(code)
        opening = openings.get(code)
        start_date = opening["start_date"] if opening else ""
        initialized = opening is not None
        opening_qty = opening["qty"] if opening else 0
        if opening and unit_key(opening["unit"]) != unit_key(unit):
            initialized = False
            issues.append({"product_code": code, "error": "ĐVT đã đổi so với tồn đầu; cần đối chiếu và khai lại tồn đầu"})
        used, received, cost = 0.0, 0.0, opening["unit_cost"] if opening else 0
        detail = []
        for order in by_order[code]:
            if opening and order["work_date"] < start_date:
                continue
            if unit_key(order["unit"]) != unit_key(unit):
                issues.append({"order_id": order["id"], "product_code": code, "error": "ĐVT dòng đơn khác danh mục; chưa thể trừ kho"})
                continue
            validation = json.loads(order['errors'] or '[]')
            if any('phải là số' in str(error) and any(word in str(error).lower() for word in ('số lượng', 'thực giao', 'khách trả')) for error in validation):
                issues.append({"order_id": order["id"], "product_code": code, "error": "Lượng trên đơn chưa hợp lệ; cần sửa trước khi kết luận tồn"})
                continue
            quantity = order["actual_delivered"] if order["physical_stage"] == "delivered" else order["qty"]
            returned = order["customer_return_qty"] or 0
            if not all(math.isfinite(float(v or 0)) and float(v or 0) >= 0 for v in (quantity, returned)) or returned > quantity:
                issues.append({"order_id": order["id"], "product_code": code, "error": "Lượng đặt/giao hoặc trả lại không hợp lệ"})
                continue
            qty = float(quantity) - float(returned)
            used += qty
            detail.append({"order_id": order["id"], "batch_id": order["batch_id"], "kitchen": order["kitchen"],
                           "work_date": order["work_date"], "qty": qty, "stage": order["physical_stage"]})
        for movement in by_movement[code]:
            if opening and movement["work_date"] < start_date:
                continue
            if unit_key(movement["unit"]) != unit_key(unit):
                issues.append({"product_code": code, "error": "ĐVT nhập/điều chỉnh khác danh mục"})
                continue
            received += movement["qty"]
            if movement["qty"] > 0:
                cost = movement["unit_cost"]
        balance = opening_qty + received - used if initialized else None
        stock_status = "uninitialized" if balance is None else "short" if balance < -1e-9 else "empty" if abs(balance) <= 1e-9 else "available"
        if any(issue.get('product_code') == code for issue in issues):
            balance, stock_status = None, 'review'
        if search.casefold() not in f"{code} {product['name']}".casefold() or status not in {"all", stock_status}:
            continue
        items.append({"product_code": code, "product_name": product["name"], "unit": unit,
                      "opening": opening, "opening_qty": opening_qty, "received_qty": received,
                      "committed_qty": used, "balance_qty": balance, "unit_cost": cost,
                      "estimated_amount": int((Decimal(str(balance)) * Decimal(str(cost))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) if balance is not None else None,
                      "status": stock_status, "orders": detail})
    for order in orders:
        if order["product_code"] not in product_codes:
            issues.append({"order_id": order["id"], "product_code": order["product_code"], "error": "Dòng đơn chưa có mã hàng đúng; chưa thể trừ kho"})
    quantities = defaultdict(float)
    for item in items:
        if item["balance_qty"] is not None:
            quantities[unit_key(item["unit"])] += item["balance_qty"]
    return {"ok": True, "items": items, "issues": issues,
            "totals": {"rows": len(items), "qty_by_unit": dict(quantities),
                       "estimated_amount": sum(i["estimated_amount"] or 0 for i in items),
                       "uninitialized": sum(i["status"] == "uninitialized" for i in items)},
            "movements": movements,
            "note": "Tồn đầu + nhập/điều chỉnh thực tế − đơn đã đặt (kể cả chưa giao). Không lấy số liệu từ kho hóa đơn. Giá trị tiền chỉ là ước tính theo giá nhập gần nhất."}


def register_physical_inventory_routes(app, deps):
    db, now = deps["db"], deps["now_iso"]

    @app.get("/api/physical-stock")
    def get_physical_stock():
        try:
            with db() as conn:
                conn.execute("BEGIN")
                return jsonify(physical_stock_payload(conn, search=request.args.get("search", ""), status=request.args.get("status", "all")))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.post("/api/physical-stock/<kind>")
    def write_physical_stock(kind):
        if kind not in {"opening", "movement"}:
            return jsonify(ok=False, error="Thao tác kho không hợp lệ"), 404
        body = request.get_json(silent=True) or {}
        try:
            code = text_field(body, "product_code", "mã hàng")
            actor = text_field(body, "actor", "người thực hiện")
            reason = text_field(body, "reason", "nội dung nhập/điều chỉnh")
            work_date = stock_date(body.get("work_date"))
            qty = number(body.get("qty"), "Số lượng", negative=kind == "movement")
            cost = number(body.get("unit_cost"), "Giá nhập")
            if work_date > date.today().isoformat():
                raise ValueError("Không ghi nhận tồn/nhập thực tế trong tương lai")
            with db() as conn:
                conn.execute("BEGIN IMMEDIATE")
                product = conn.execute("SELECT unit FROM products WHERE code=?", (code,)).fetchone()
                if not product or not product["unit"]:
                    raise ValueError("Mã hàng hoặc ĐVT chưa được khai báo")
                unit = product["unit"]
                opening = conn.execute("SELECT * FROM physical_stock_openings WHERE product_code=? ORDER BY id DESC LIMIT 1", (code,)).fetchone()
                if kind == "opening":
                    revision = int(body.get("revision", -1))
                    if revision != (opening["id"] if opening else 0):
                        return jsonify(ok=False, error="Tồn đầu đã đổi; tải lại trước khi lưu"), 409
                    if opening and opening["start_date"] != work_date:
                        raise ValueError("Sửa tồn đầu phải giữ nguyên ngày bắt đầu; không bỏ qua lịch sử đơn/nhập")
                    conn.execute("""INSERT INTO physical_stock_openings(product_code,unit,start_date,qty,unit_cost,actor,reason,created_at)
                        VALUES(?,?,?,?,?,?,?,?)""", (code, unit, work_date, qty, cost, actor, reason, now()))
                else:
                    if not opening or unit_key(opening["unit"]) != unit_key(unit):
                        raise ValueError("Khai tồn đầu đúng ĐVT trước khi ghi nhập/điều chỉnh thực tế")
                    if work_date < opening["start_date"]:
                        raise ValueError("Ngày nhập/điều chỉnh phải từ ngày bắt đầu tồn thực tế")
                    if qty == 0:
                        raise ValueError("Lượng nhập/điều chỉnh không được bằng 0")
                    key = text_field(body, "request_key", "mã lần lưu")
                    previous = conn.execute("SELECT * FROM physical_stock_movements WHERE request_key=?", (key,)).fetchone()
                    values = (code, unit, work_date, qty, cost, actor, reason)
                    if previous:
                        if tuple(previous[f] for f in ("product_code", "unit", "work_date", "qty", "unit_cost", "actor", "reason")) != values:
                            return jsonify(ok=False, error="Mã lần lưu đã dùng cho dữ liệu khác"), 409
                        return jsonify(ok=True, idempotent=True)
                    conn.execute("""INSERT INTO physical_stock_movements(request_key,product_code,unit,work_date,qty,unit_cost,actor,reason,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?)""", (key, *values, now()))
                return jsonify(ok=True)
        except (ValueError, TypeError) as exc:
            return jsonify(ok=False, error=str(exc)), 400

    @app.put("/api/physical-stock/orders/<int:order_id>")
    def settle_physical_order(order_id):
        body = request.get_json(silent=True) or {}
        stage = body.get("stage")
        if stage not in {"ordered", "delivered"}:
            return jsonify(ok=False, error="Chọn đã giao hoặc chưa giao"), 400
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not order:
                return jsonify(ok=False, error="Không còn dòng đơn"), 404
            if body.get("revision") != physical_order_revision(dict(order)):
                return jsonify(ok=False, error="Dòng đơn đã đổi; tải lại và kiểm tra lượng trước khi xác nhận"), 409
            quantity = order["actual_delivered"] if stage == "delivered" else order["qty"]
            if not math.isfinite(quantity) or quantity < 0 or order["customer_return_qty"] > quantity:
                return jsonify(ok=False, error="Số giao/đặt hoặc số trả lại chưa hợp lệ"), 400
            conn.execute("UPDATE orders SET physical_stage=? WHERE id=?", (stage, order_id))
            return jsonify(ok=True, **deps["batch_payload"](conn, order["batch_id"]))


def physical_order_revision(row):
    values = [row.get(k) for k in ("id", "work_date", "product_code", "unit", "kitchen", "qty", "actual_delivered", "customer_return_qty", "physical_stage", "updated_at")]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()
