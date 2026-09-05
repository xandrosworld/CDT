"""Explicit, isolated imports for safe reference roles in a daily workbook.

The identity, price and intermediate sheets never enter this module's parsers.
Product-catalog updates keep using the established catalog preview/confirm
flow; this module owns only contractor/kitchen and default-supplier mappings.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import threading
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path
from typing import Any

from flask import jsonify, request
from openpyxl import load_workbook


WRITABLE_ROLES = {
    "contractor_kitchen_reference", "product_reference", "supplier_reference",
}
ROLE_TITLES = {
    "contractor_kitchen_reference": "t.chieu",
    "product_reference": "danh muc hang hoa",
    "supplier_reference": "danh muc nha cc",
}
PENDING_DAILY_REFERENCE_IMPORTS: dict[str, dict[str, Any]] = {}
DAILY_REFERENCE_IMPORT_LOCK = threading.Lock()
REFERENCE_IMPORT_TTL_SECONDS = 15 * 60
REFERENCE_IMPORT_MAX_BYTES = 20 * 1024 * 1024
REFERENCE_IMPORT_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
REFERENCE_IMPORT_MAX_ROWS = 100_000


DAILY_REFERENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_reference_import_receipts (
    import_key TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    counts_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK(role IN ('contractor_kitchen_reference','product_reference','supplier_reference'))
);
CREATE INDEX IF NOT EXISTS idx_daily_reference_receipts_role
    ON daily_reference_import_receipts(role,created_at DESC);
"""


class DailyReferenceError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def init_daily_reference_schema(conn) -> None:
    conn.executescript(DAILY_REFERENCE_SCHEMA)


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _key(value: Any) -> str:
    text = str(value or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text)


def _source_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _hash_json(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _reference_content_hash(role: str, items: list[dict[str, Any]]) -> str:
    """Hash role-owned cell values, excluding database-derived preview actions.

    XLSX package metadata changes whenever an otherwise identical workbook is
    saved.  Idempotency therefore cannot safely use the ZIP bytes alone.
    """
    fields = {
        "contractor_kitchen_reference": (
            "source_row", "contractor", "kitchen", "source_kitchen_name", "source_address",
        ),
        "supplier_reference": ("source_row", "product_code", "supplier"),
        "product_reference": (
            "source_row", "product_code", "product_name", "product_group",
            "invoice_name", "unit", "tax",
        ),
    }[role]
    return _hash_json([
        {field: item.get(field, "") for field in fields}
        for item in items
    ])


def _database_state_hash(conn, role: str) -> str:
    queries = {
        "contractor_kitchen_reference": (
            "SELECT code,name,COALESCE(price_group,''),pricing_mode FROM contractors ORDER BY code",
            "SELECT code,COALESCE(contractor,''),COALESCE(name,''),COALESCE(address,'') "
            "FROM kitchens ORDER BY code",
        ),
        "supplier_reference": (
            "SELECT code,name FROM suppliers ORDER BY code",
            "SELECT code,COALESCE(supplier,'') FROM products ORDER BY code",
        ),
        "product_reference": (
            "SELECT code,name,COALESCE(unit,''),COALESCE(tax,''),COALESCE(product_group,'') "
            "FROM products ORDER BY code",
            "SELECT product_code,invoice_name FROM outgoing_product_names ORDER BY product_code",
        ),
    }
    digest = hashlib.sha256()
    for sql in queries[role]:
        digest.update(sql.encode("utf-8"))
        digest.update(b"\0")
        for row in conn.execute(sql):
            digest.update(json.dumps(list(row), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest().upper()


def _find_role_sheet(workbook, role: str):
    expected = ROLE_TITLES[role]
    matches = [sheet for sheet in workbook.worksheets if _key(sheet.title) == _key(expected)]
    if len(matches) != 1:
        raise DailyReferenceError(
            "Workbook phải có đúng một sheet tham chiếu cho vai trò đã chọn",
            code="reference_sheet_missing",
        )
    return matches[0]


def _best_header(worksheet, aliases: dict[str, set[str]]) -> tuple[int, dict[str, int]]:
    reverse = {alias: field for field, values in aliases.items() for alias in values}
    best = (0, 0, {})
    for row in range(1, min(worksheet.max_row, 15) + 1):
        mapping = {}
        for column in range(1, min(worksheet.max_column, 60) + 1):
            field = reverse.get(_key(worksheet.cell(row, column).value))
            if field and field not in mapping:
                mapping[field] = column
        candidate = (len(mapping), row, mapping)
        if candidate[0] > best[0]:
            best = candidate
    return best[1], best[2]


def _parse_contractor_kitchens(conn, worksheet) -> dict[str, Any]:
    aliases = {
        "contractor": {"nhathau"},
        "kitchen": {"mabep", "tenbepormabep"},
        "kitchen_name": {"tenbepghitrendonhan", "tenbepghitrendondathang"},
        "address": {"diachigiaohang", "diachi"},
    }
    header_row, mapping = _best_header(worksheet, aliases)
    if not {"contractor", "kitchen"}.issubset(mapping):
        raise DailyReferenceError(
            "Sheet T.chiếu thiếu cột Nhà thầu hoặc Mã bếp",
            code="invalid_reference_header",
        )
    current_contractors = {
        row["code"]: dict(row) for row in conn.execute(
            "SELECT code,name,COALESCE(price_group,'') price_group,pricing_mode FROM contractors"
        )
    }
    current_kitchens = {
        row["code"]: dict(row) for row in conn.execute(
            "SELECT code,COALESCE(contractor,'') contractor,COALESCE(name,'') name,"
            "COALESCE(address,'') address FROM kitchens"
        )
    }
    rows = []
    seen = {}
    errors = 0
    for row_index in range(header_row + 1, min(worksheet.max_row, header_row + REFERENCE_IMPORT_MAX_ROWS) + 1):
        contractor = _plain(worksheet.cell(row_index, mapping["contractor"]).value).upper()
        kitchen = _plain(worksheet.cell(row_index, mapping["kitchen"]).value).upper()
        if not contractor and not kitchen:
            continue
        incoming_name = _plain(worksheet.cell(row_index, mapping.get("kitchen_name", 0)).value) if mapping.get("kitchen_name") else ""
        incoming_address = _plain(worksheet.cell(row_index, mapping.get("address", 0)).value) if mapping.get("address") else ""
        current = current_kitchens.get(kitchen)
        # Formula caches can be blank. A blank reference cell validates as
        # "no proposed change" and must never erase a durable master value.
        name = incoming_name or _plain((current or {}).get("name")) or kitchen
        address = incoming_address or _plain((current or {}).get("address"))
        item = {
            "source_row": row_index,
            "contractor": contractor,
            "kitchen": kitchen,
            "source_kitchen_name": incoming_name,
            "source_address": incoming_address,
            "kitchen_name": name or kitchen,
            "address": address,
            "errors": [],
        }
        if not contractor:
            item["errors"].append("missing_contractor")
        if not kitchen:
            item["errors"].append("missing_kitchen")
        signature = (contractor, item["kitchen_name"], address)
        if kitchen and kitchen in seen and seen[kitchen] != signature:
            item["errors"].append("conflicting_kitchen")
        elif kitchen:
            seen[kitchen] = signature
        changed_fields = []
        if current:
            for field, incoming in (
                ("contractor", contractor), ("name", item["kitchen_name"]), ("address", address),
            ):
                if _plain(current.get(field)) != incoming:
                    changed_fields.append(field)
        item["action"] = "error" if item["errors"] else (
            "new" if not current else ("update" if changed_fields else "unchanged")
        )
        item["changed_fields"] = changed_fields
        errors += bool(item["errors"])
        rows.append(item)
    if worksheet.max_row > header_row + REFERENCE_IMPORT_MAX_ROWS:
        raise DailyReferenceError("Sheet tham chiếu vượt giới hạn dòng", code="too_many_rows", status=413)
    if not rows:
        raise DailyReferenceError("Sheet T.chiếu không có dữ liệu", code="empty_reference")
    counts = {
        "processed": len(rows),
        "new_contractors": len({
            item["contractor"] for item in rows
            if item["contractor"] and item["contractor"] not in current_contractors
        }),
        "new_kitchens": sum(item["action"] == "new" for item in rows),
        "updated_kitchens": sum(item["action"] == "update" for item in rows),
        "unchanged": sum(item["action"] == "unchanged" for item in rows),
        "errors": errors,
    }
    return {"header_row": header_row, "items": rows, "counts": counts}


def _parse_supplier_mappings(conn, worksheet) -> dict[str, Any]:
    aliases = {
        "product_code": {"mahang", "mavt", "mavattu"},
        "supplier": {"ncc", "nhacungcap", "chonncc"},
        "product_name": {"tenhang", "tenhanghoa", "tenthanhdatphat"},
        "unit": {"dvt", "donvitinh"},
    }
    header_row, mapping = _best_header(worksheet, aliases)
    if not {"product_code", "supplier"}.issubset(mapping):
        raise DailyReferenceError(
            "Sheet danh mục nhà cc thiếu cột Mã hàng hoặc NCC",
            code="invalid_reference_header",
        )
    products = {
        row["code"]: dict(row) for row in conn.execute(
            "SELECT code,name,unit,COALESCE(supplier,'') supplier FROM products"
        )
    }
    rows = []
    seen = {}
    blank_supplier = placeholders = errors = 0
    for row_index in range(header_row + 1, min(worksheet.max_row, header_row + REFERENCE_IMPORT_MAX_ROWS) + 1):
        code = _plain(worksheet.cell(row_index, mapping["product_code"]).value).upper()
        supplier = _plain(worksheet.cell(row_index, mapping["supplier"]).value)
        if not code and not supplier:
            continue
        if not code:
            errors += 1
            rows.append({
                "source_row": row_index, "product_code": "", "supplier": supplier,
                "action": "error", "errors": ["missing_product_code"], "changed_fields": [],
            })
            continue
        if not supplier:
            blank_supplier += 1
            continue
        if _key(supplier) in {"chon ncc", "chonncc", "kiemtra", "-"} or supplier == "-":
            placeholders += 1
            continue
        item_errors = []
        if code not in products:
            item_errors.append("unknown_product")
        if code in seen and _key(seen[code]) != _key(supplier):
            item_errors.append("conflicting_supplier")
        else:
            seen[code] = supplier
        current = products.get(code, {}).get("supplier", "")
        action = "error" if item_errors else (
            "update" if _key(current) != _key(supplier) else "unchanged"
        )
        errors += bool(item_errors)
        rows.append({
            "source_row": row_index,
            "product_code": code,
            "supplier": supplier,
            "action": action,
            "errors": item_errors,
            "changed_fields": ["supplier"] if action == "update" else [],
        })
    if worksheet.max_row > header_row + REFERENCE_IMPORT_MAX_ROWS:
        raise DailyReferenceError("Sheet tham chiếu vượt giới hạn dòng", code="too_many_rows", status=413)
    if not rows and not blank_supplier:
        raise DailyReferenceError("Sheet danh mục nhà cc không có dữ liệu", code="empty_reference")
    counts = {
        "processed": len(rows),
        "updated_mappings": sum(item["action"] == "update" for item in rows),
        "unchanged": sum(item["action"] == "unchanged" for item in rows),
        "blank_supplier": blank_supplier,
        "placeholder_supplier": placeholders,
        "errors": errors,
    }
    return {"header_row": header_row, "items": rows, "counts": counts}


def _catalog_tax(value: Any) -> str:
    raw = _plain(value).upper()
    if not raw:
        return ""
    if _key(raw) in {"kkknt", "khongkekhai"}:
        return "KKKNT"
    if _key(raw) in {"kct", "khongchiuthue"}:
        return "KCT"
    text = raw.replace("%", "").replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return raw
    if number > 1:
        number /= 100
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _parse_product_catalog(conn, worksheet) -> dict[str, Any]:
    aliases = {
        "product_code": {"mahang", "mavt", "mavattu"},
        "product_group": {"nhomhang", "nhomhanghoa"},
        "product_name": {"tenhang", "tenhanghoa", "tenthanhdatphat"},
        "invoice_name": {"tenxuathoadon", "tenhoadon"},
        "unit": {"dvt", "donvitinh"},
        "tax": {"thue", "thuegtgt", "thuesuat"},
    }
    header_row, mapping = _best_header(worksheet, aliases)
    required = {"product_code", "product_name", "unit", "tax"}
    if not required.issubset(mapping):
        raise DailyReferenceError(
            "Sheet danh mục hàng hóa thiếu Mã hàng, Tên Thành Đạt Phát, ĐVT hoặc Thuế",
            code="invalid_reference_header",
        )
    products = {
        row["code"]: dict(row) for row in conn.execute(
            "SELECT code,name,COALESCE(unit,'') unit,COALESCE(tax,'') tax,"
            "COALESCE(product_group,'') product_group FROM products"
        )
    }
    invoice_names = {
        row["product_code"]: row["invoice_name"]
        for row in conn.execute("SELECT product_code,invoice_name FROM outgoing_product_names")
    }
    rows = []
    seen = {}
    errors = duplicate = 0
    for row_index in range(header_row + 1, min(worksheet.max_row, header_row + REFERENCE_IMPORT_MAX_ROWS) + 1):
        code = _plain(worksheet.cell(row_index, mapping["product_code"]).value).upper()
        name = _plain(worksheet.cell(row_index, mapping["product_name"]).value)
        unit = _plain(worksheet.cell(row_index, mapping["unit"]).value)
        tax = _catalog_tax(worksheet.cell(row_index, mapping["tax"]).value)
        group = _plain(worksheet.cell(row_index, mapping.get("product_group", 0)).value).upper() if mapping.get("product_group") else ""
        invoice_name = _plain(worksheet.cell(row_index, mapping.get("invoice_name", 0)).value) if mapping.get("invoice_name") else ""
        if not any((code, name, unit, tax, group, invoice_name)):
            continue
        item_errors = []
        if not code:
            item_errors.append("missing_product_code")
        if not name:
            item_errors.append("missing_product_name")
        if not unit:
            item_errors.append("missing_unit")
        if not tax:
            item_errors.append("missing_tax")
        signature = (_key(name), _key(unit), tax, _key(group), _key(invoice_name))
        if code and code in seen:
            if seen[code] == signature:
                duplicate += 1
                rows.append({
                    "source_row": row_index, "product_code": code, "action": "duplicate",
                    "changed_fields": [], "errors": [], "apply": False,
                })
                continue
            item_errors.append("conflicting_product")
        elif code:
            seen[code] = signature
        current = products.get(code)
        changed_fields = []
        if current:
            for field, incoming in (
                ("name", name), ("unit", unit), ("tax", tax), ("product_group", group),
            ):
                current_value = _catalog_tax(current.get(field)) if field == "tax" else _key(current.get(field))
                incoming_value = tax if field == "tax" else _key(incoming)
                if current_value != incoming_value:
                    changed_fields.append(field)
            if invoice_name and _key(invoice_names.get(code)) != _key(invoice_name):
                changed_fields.append("invoice_name")
        action = "error" if item_errors else (
            "new" if not current else ("update" if changed_fields else "unchanged")
        )
        errors += bool(item_errors)
        rows.append({
            "source_row": row_index,
            "product_code": code,
            "product_name": name,
            "product_group": group,
            "invoice_name": invoice_name,
            "unit": unit,
            "tax": tax,
            "action": action,
            "changed_fields": changed_fields,
            "errors": item_errors,
            "apply": not item_errors,
        })
    if worksheet.max_row > header_row + REFERENCE_IMPORT_MAX_ROWS:
        raise DailyReferenceError("Sheet tham chiếu vượt giới hạn dòng", code="too_many_rows", status=413)
    if not rows:
        raise DailyReferenceError("Sheet danh mục hàng hóa không có dữ liệu", code="empty_reference")
    counts = {
        "processed": len(rows),
        "new_products": sum(item["action"] == "new" for item in rows),
        "updated_products": sum(item["action"] == "update" for item in rows),
        "unchanged": sum(item["action"] == "unchanged" for item in rows),
        "duplicate": duplicate,
        "errors": errors,
    }
    return {"header_row": header_row, "items": rows, "counts": counts}


def _safe_changes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_row": item["source_row"],
            "key": item.get("kitchen") or item.get("product_code") or "",
            "action": item["action"],
            "changed_fields": item.get("changed_fields", []),
            "error_codes": item.get("errors", []),
        }
        for item in items[:250]
    ]


def _parse_reference(conn, workbook, role: str) -> dict[str, Any]:
    worksheet = _find_role_sheet(workbook, role)
    if role == "contractor_kitchen_reference":
        parsed = _parse_contractor_kitchens(conn, worksheet)
    elif role == "product_reference":
        parsed = _parse_product_catalog(conn, worksheet)
    else:
        parsed = _parse_supplier_mappings(conn, worksheet)
    parsed["sheet"] = worksheet.title
    return parsed


def _apply_reference(conn, role: str, items: list[dict[str, Any]], timestamp: str) -> None:
    if role == "contractor_kitchen_reference":
        for item in items:
            if item["errors"]:
                continue
            contractor = item["contractor"]
            pricing_mode = "daily" if contractor in {"GIANHAPTAY", "YLKHAN"} else "group"
            conn.execute(
                """INSERT INTO contractors(code,name,price_group,pricing_mode)
                   VALUES(?,?,?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name""",
                (contractor, contractor, contractor, pricing_mode),
            )
            conn.execute(
                """INSERT INTO kitchens(code,contractor,name,address)
                   VALUES(?,?,?,?) ON CONFLICT(code) DO UPDATE SET
                   contractor=excluded.contractor,name=excluded.name,address=excluded.address""",
                (item["kitchen"], contractor, item["kitchen_name"], item["address"]),
            )
    elif role == "product_reference":
        for item in items:
            if item["errors"] or not item.get("apply"):
                continue
            conn.execute(
                """INSERT INTO products(
                       code,name,unit,tax,supplier,buy_price,purchase_list,product_group,catalog_updated_at
                   ) VALUES(?,?,?,?, '',0,0,?,?) ON CONFLICT(code) DO UPDATE SET
                   name=excluded.name,unit=excluded.unit,tax=excluded.tax,
                   product_group=excluded.product_group,catalog_updated_at=excluded.catalog_updated_at""",
                (
                    item["product_code"], item["product_name"], item["unit"], item["tax"],
                    item["product_group"], timestamp,
                ),
            )
            if item["invoice_name"]:
                conn.execute(
                    """INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at)
                       VALUES(?,?,?) ON CONFLICT(product_code) DO UPDATE SET
                       invoice_name=excluded.invoice_name,updated_at=excluded.updated_at""",
                    (item["product_code"], item["invoice_name"], timestamp),
                )
    else:
        for item in items:
            if item["errors"]:
                continue
            conn.execute(
                "INSERT INTO suppliers(code,name) VALUES(?,?) ON CONFLICT(code) DO NOTHING",
                (item["supplier"], item["supplier"]),
            )
            conn.execute(
                "UPDATE products SET supplier=? WHERE code=?",
                (item["supplier"], item["product_code"]),
            )


def register_daily_reference_routes(app, db_factory, now_iso, clean_text) -> None:
    @app.post("/api/daily-references/preview")
    def api_daily_reference_preview():
        role = clean_text(request.form.get("role"))
        if role not in WRITABLE_ROLES:
            return jsonify({
                "ok": False,
                "error": "Vai trò này chỉ được đọc ở nghiệp vụ chuyên trách, không được ghi từ workbook ngày",
                "code": "reference_role_locked",
            }), 400
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "Chưa chọn workbook ngày"}), 400
        if Path(upload.filename).suffix.lower() not in {".xlsx", ".xlsm"}:
            return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
        payload = upload.read(REFERENCE_IMPORT_MAX_BYTES + 1)
        if len(payload) > REFERENCE_IMPORT_MAX_BYTES:
            return jsonify({"ok": False, "error": "Workbook vượt giới hạn 20 MB"}), 413
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                if sum(item.file_size for item in archive.infolist()) > REFERENCE_IMPORT_MAX_UNCOMPRESSED_BYTES:
                    raise DailyReferenceError("Workbook có cấu trúc quá lớn", code="expanded_too_large", status=413)
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "error": "Workbook bị hỏng hoặc sai định dạng"}), 400
        workbook = None
        try:
            workbook = load_workbook(
                io.BytesIO(payload), read_only=False, data_only=True, keep_links=False,
            )
            with db_factory() as conn:
                parsed = _parse_reference(conn, workbook, role)
                database_state_hash = _database_state_hash(conn, role)
        except DailyReferenceError as exc:
            return jsonify({"ok": False, "error": str(exc), "code": exc.code}), exc.status
        finally:
            if workbook is not None:
                workbook.close()
        source_hash = _source_hash(payload)
        content_hash = _reference_content_hash(role, parsed["items"])
        import_key = hashlib.sha256(f"{role}\0{content_hash}".encode("utf-8")).hexdigest().upper()
        proposal_hash = _hash_json([
            {key: value for key, value in item.items() if key != "errors"}
            for item in parsed["items"]
        ])
        state_hash = hashlib.sha256(
            f"{source_hash}\0{role}\0{database_state_hash}\0{proposal_hash}".encode("utf-8")
        ).hexdigest().upper()
        token = uuid.uuid4().hex
        pending = {
            "created": time.time(),
            "role": role,
            "source_hash": source_hash,
            "content_hash": content_hash,
            "import_key": import_key,
            "state_hash": state_hash,
            "database_state_hash": database_state_hash,
            "sheet": parsed["sheet"],
            "header_row": parsed["header_row"],
            "items": parsed["items"],
            "counts": parsed["counts"],
        }
        with DAILY_REFERENCE_IMPORT_LOCK:
            cutoff = time.time() - REFERENCE_IMPORT_TTL_SECONDS
            for old_token, item in list(PENDING_DAILY_REFERENCE_IMPORTS.items()):
                if item["created"] < cutoff:
                    PENDING_DAILY_REFERENCE_IMPORTS.pop(old_token, None)
            PENDING_DAILY_REFERENCE_IMPORTS[token] = pending
        return jsonify({
            "ok": True,
            "token": token,
            "role": role,
            "sheet": parsed["sheet"],
            "headerRow": parsed["header_row"],
            "sourceHash": source_hash,
            "stateHash": state_hash,
            "counts": parsed["counts"],
            "canConfirm": parsed["counts"]["errors"] == 0,
            "changes": _safe_changes(parsed["items"]),
            "changesTruncated": len(parsed["items"]) > 250,
        })

    @app.post("/api/daily-references/confirm")
    def api_daily_reference_confirm():
        body = request.get_json(force=True) or {}
        token = clean_text(body.get("token"))
        with DAILY_REFERENCE_IMPORT_LOCK:
            pending = PENDING_DAILY_REFERENCE_IMPORTS.pop(token, None)
        if not pending or time.time() - pending["created"] > REFERENCE_IMPORT_TTL_SECONDS:
            return jsonify({"ok": False, "error": "Phiên preview đã hết hạn", "code": "preview_expired"}), 410
        if body.get("confirmed") is not True:
            return jsonify({"ok": False, "error": "Cần xác nhận rõ trước khi ghi", "code": "confirmation_required"}), 400
        if clean_text(body.get("state_hash") or body.get("stateHash")).upper() != pending["state_hash"]:
            return jsonify({"ok": False, "error": "Preview không còn đúng trạng thái", "code": "stale_preview"}), 409
        if pending["counts"]["errors"]:
            return jsonify({"ok": False, "error": "Preview còn lỗi nên không thể ghi", "code": "preview_has_errors"}), 400
        with db_factory() as conn:
            conn.execute("BEGIN IMMEDIATE")
            receipt = conn.execute(
                "SELECT counts_json FROM daily_reference_import_receipts WHERE import_key=?",
                (pending["import_key"],),
            ).fetchone()
            if receipt:
                return jsonify({
                    "ok": True,
                    "role": pending["role"],
                    "sourceHash": pending["source_hash"],
                    "counts": json.loads(receipt["counts_json"]),
                    "idempotent": True,
                })
            if _database_state_hash(conn, pending["role"]) != pending["database_state_hash"]:
                return jsonify({
                    "ok": False,
                    "error": "Master data đã đổi sau preview; chưa ghi gì, vui lòng preview lại",
                    "code": "stale_database",
                }), 409
            timestamp = now_iso()
            _apply_reference(conn, pending["role"], pending["items"], timestamp)
            conn.execute(
                """INSERT INTO daily_reference_import_receipts(
                       import_key,role,source_hash,state_hash,counts_json,created_at
                   ) VALUES(?,?,?,?,?,?)""",
                (
                    pending["import_key"], pending["role"], pending["source_hash"],
                    pending["state_hash"], json.dumps(pending["counts"], sort_keys=True), timestamp,
                ),
            )
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
            ).fetchone():
                conn.execute(
                    """INSERT INTO audit_log(
                           event_type,entity_type,entity_id,status,message,metadata_json,created_at
                       ) VALUES('daily_reference.confirm','daily_reference',?,'ok','',?,?)""",
                    (
                        pending["import_key"][:16],
                        json.dumps({
                            "role": pending["role"],
                            "source_hash": pending["source_hash"],
                            "counts": pending["counts"],
                        }, sort_keys=True, separators=(",", ":")),
                        timestamp,
                    ),
                )
            return jsonify({
                "ok": True,
                "role": pending["role"],
                "sourceHash": pending["source_hash"],
                "counts": pending["counts"],
                "idempotent": False,
            })
