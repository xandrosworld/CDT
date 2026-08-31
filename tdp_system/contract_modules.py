from __future__ import annotations

import io
import hashlib
import json
import math
import os
import re
import subprocess
import threading
import time
import unicodedata
import uuid
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import jsonify, request, send_file
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt
except ImportError:  # Kept optional until a payment-request DOCX is requested.
    Document = None

try:
    from msmi_client import MsmiClient, MsmiConfig, MsmiError
except ImportError:
    from .msmi_client import MsmiClient, MsmiConfig, MsmiError


ADVANCED_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    status TEXT NOT NULL,
    message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);

CREATE TABLE IF NOT EXISTS supplier_rules (
    supplier_code TEXT PRIMARY KEY,
    combine_kitchens INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date TEXT NOT NULL,
    product_code TEXT NOT NULL,
    qty_in REAL NOT NULL DEFAULT 0,
    qty_out REAL NOT NULL DEFAULT 0,
    unit_cost REAL NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_line TEXT NOT NULL DEFAULT '',
    kitchen TEXT,
    status TEXT NOT NULL DEFAULT 'posted',
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_type, source_id, source_line)
);
CREATE INDEX IF NOT EXISTS idx_inventory_product_date ON inventory_transactions(product_code,txn_date);
CREATE INDEX IF NOT EXISTS idx_inventory_source ON inventory_transactions(source_type,source_id);

CREATE TABLE IF NOT EXISTS msmi_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    remote_id TEXT NOT NULL UNIQUE,
    tenant TEXT NOT NULL DEFAULT 'default',
    invoice_type TEXT NOT NULL,
    seller_tax_code TEXT,
    seller_name TEXT,
    invoice_number TEXT,
    invoice_series TEXT,
    invoice_date TEXT,
    subtotal REAL NOT NULL DEFAULT 0,
    tax_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT 'synced',
    receipt_status TEXT NOT NULL DEFAULT 'pending_mapping',
    raw_json TEXT NOT NULL,
    error_message TEXT,
    synced_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msmi_invoice_date ON msmi_invoices(invoice_date DESC);

CREATE TABLE IF NOT EXISTS msmi_invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES msmi_invoices(id) ON DELETE CASCADE,
    line_index INTEGER NOT NULL,
    source_item_code TEXT,
    source_item_name TEXT,
    source_unit TEXT,
    qty REAL NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0,
    tax_rate TEXT,
    product_code TEXT,
    mapping_status TEXT NOT NULL DEFAULT 'unmapped',
    UNIQUE(invoice_id,line_index)
);
CREATE INDEX IF NOT EXISTS idx_msmi_items_invoice ON msmi_invoice_items(invoice_id);

CREATE TABLE IF NOT EXISTS item_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant TEXT NOT NULL DEFAULT 'default',
    seller_tax_code TEXT NOT NULL DEFAULT '',
    source_item_code TEXT NOT NULL DEFAULT '',
    source_item_name TEXT NOT NULL DEFAULT '',
    product_code TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(tenant,seller_tax_code,source_item_code,source_item_name)
);

CREATE TABLE IF NOT EXISTS msmi_sync_state (
    invoice_type TEXT PRIMARY KEY,
    last_remote_id TEXT,
    last_invoice_date TEXT,
    last_synced_at TEXT,
    last_status TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS outgoing_invoice_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    contractor TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    subtotal REAL NOT NULL DEFAULT 0,
    tax_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    issued_at TEXT,
    UNIQUE(batch_id,contractor)
);
CREATE TABLE IF NOT EXISTS outgoing_invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL REFERENCES outgoing_invoice_drafts(id) ON DELETE CASCADE,
    order_id INTEGER NOT NULL,
    product_code TEXT NOT NULL,
    product_name TEXT,
    qty REAL NOT NULL,
    unit TEXT,
    unit_price REAL NOT NULL,
    tax TEXT,
    amount REAL NOT NULL,
    UNIQUE(draft_id,order_id)
);

CREATE TABLE IF NOT EXISTS outgoing_product_names (
    product_code TEXT PRIMARY KEY,
    invoice_name TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS debt_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adjustment_date TEXT NOT NULL,
    party_type TEXT NOT NULL,
    party_code TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kitchen_units (
    kitchen_code TEXT PRIMARY KEY,
    unit_code TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dated_prices (
    product_code TEXT NOT NULL,
    price_group TEXT NOT NULL,
    period TEXT NOT NULL,
    price_value REAL NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(product_code,price_group,period)
);
CREATE TABLE IF NOT EXISTS meal_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_date TEXT NOT NULL,
    kitchen TEXT NOT NULL,
    shift TEXT NOT NULL,
    meal_count REAL NOT NULL,
    unit_code TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meal_plan_date ON meal_plans(work_date,kitchen);
CREATE TABLE IF NOT EXISTS meal_plan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    dish_name TEXT,
    product_code TEXT NOT NULL,
    product_name TEXT,
    norm_qty REAL NOT NULL,
    unit TEXT,
    supplier TEXT,
    buy_price REAL NOT NULL DEFAULT 0,
    price_source TEXT,
    UNIQUE(plan_id,dish_name,product_code)
);

CREATE TABLE IF NOT EXISTS meal_attendance (
    work_date TEXT NOT NULL,
    kitchen TEXT NOT NULL,
    shift TEXT NOT NULL,
    actual_count REAL NOT NULL DEFAULT 0,
    ordered_count REAL NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL DEFAULT 'MONTHLY_WORKBOOK',
    source_file TEXT,
    source_sheet TEXT,
    source_column TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(work_date,kitchen,shift)
);
CREATE INDEX IF NOT EXISTS idx_meal_attendance_month
    ON meal_attendance(work_date,kitchen);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role_name TEXT,
    kitchen TEXT,
    base_salary REAL NOT NULL DEFAULT 0,
    standard_days REAL NOT NULL DEFAULT 26,
    standard_hours REAL NOT NULL DEFAULT 8,
    bhxh_employee_rate REAL NOT NULL DEFAULT 0,
    bhxh_company_rate REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    work_date TEXT NOT NULL,
    normal_hours REAL NOT NULL DEFAULT 0,
    overtime_hours REAL NOT NULL DEFAULT 0,
    sunday_hours REAL NOT NULL DEFAULT 0,
    night_hours REAL NOT NULL DEFAULT 0,
    holiday_hours REAL NOT NULL DEFAULT 0,
    note TEXT,
    source TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(employee_id,work_date)
);
CREATE TABLE IF NOT EXISTS payroll_adjustments (
    employee_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    month TEXT NOT NULL,
    allowance REAL NOT NULL DEFAULT 0,
    responsibility REAL NOT NULL DEFAULT 0,
    advance REAL NOT NULL DEFAULT 0,
    probation_deduction REAL NOT NULL DEFAULT 0,
    bhxh_employee_amount REAL NOT NULL DEFAULT 0,
    bhxh_company_amount REAL NOT NULL DEFAULT 0,
    note TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(employee_id,month)
);
CREATE TABLE IF NOT EXISTS kitchen_labor_costs (
    work_date TEXT NOT NULL,
    kitchen TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    source TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(work_date,kitchen,source)
);

CREATE TABLE IF NOT EXISTS print_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'prepared',
    approved_at TEXT,
    printed_at TEXT,
    printer_name TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(batch_id,document_type)
);
"""


MAPPING_IMPORT_MAX_BYTES = 10 * 1024 * 1024
MAPPING_IMPORT_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAPPING_IMPORT_MAX_ROWS = 10_000
MAPPING_IMPORT_TTL_SECONDS = 30 * 60
PENDING_MAPPING_IMPORTS = {}
MAPPING_IMPORT_LOCK = threading.Lock()
PENDING_CATALOG_IMPORTS = {}
CATALOG_IMPORT_LOCK = threading.Lock()
PENDING_KITCHEN_IMPORTS = {}
KITCHEN_IMPORT_LOCK = threading.Lock()
PENDING_OPENING_IMPORTS = {}
OPENING_IMPORT_LOCK = threading.Lock()
PENDING_MEAL_ATTENDANCE_IMPORTS = {}
MEAL_ATTENDANCE_IMPORT_LOCK = threading.Lock()

MAPPING_ALIASES = {
    "invoice_names": {
        "product_code": {
            "mahang", "mahanghoa", "mahh", "mavt", "mavattu", "mavattutdp", "masp",
            "masanpham", "matdp", "masptdp", "mahhtdp",
            "productcode", "itemcode", "code",
        },
        "product_name": {
            "tenhang", "tenhanghoa", "tenhanghoatdp", "tenhh", "tenvattu", "tensp",
            "tensanpham", "tentdp", "tenthanhdatphat", "tentrenphanmem", "tenhientai",
            "tengoc", "productname", "itemname",
        },
        "target_value": {
            "tenxuathoadon", "tenxuathd", "tenxhd", "tenhoadon", "tenhd", "tendaura",
            "tenhangxuathoadon", "tenhanghoaxuathoadon", "tenhangxhd", "tenhanghoadon",
            "tenchuanhoadon", "invoicename",
        },
    },
    "kitchen_units": {
        "source_code": {
            "mabep", "bep", "kitchen", "kitchencode", "code",
        },
        "source_name": {
            "tenbep", "tennhabep", "kitchenname",
        },
        "target_value": {
            "unit", "maunit", "unitcode", "donvi", "donvigop", "nhomunit",
            "xcom", "maxcom", "xuongcom", "maxuongcom", "xcomxuongcom",
        },
    },
}

CATALOG_ALIASES = {
    "product_code": {
        "mahang", "mahanghoa", "mahh", "mavt", "mavattu", "matdp", "masp",
        "masanpham", "mahhtdp", "productcode", "itemcode", "code",
    },
    "product_group": {"nhomhang", "nhomhanghoa", "nhom", "category", "group"},
    "product_name": {
        "tenhang", "tenhanghoa", "tenhanghoatdp", "tentdp", "tenthanhdatphat",
        "productname", "itemname",
    },
    "invoice_name": {
        "tenxuathoadon", "tenxuathd", "tenxhd", "tenhoadon", "tenhd", "tendaura",
        "tenhangxuathoadon", "tenhanghoaxuathoadon", "tenhangxhd", "invoicename",
    },
    "unit": {"dvt", "donvitinh", "unit"},
    "tax": {"thue", "thuesuat", "thuegtgt", "tsuat", "vat", "tax"},
}

CATALOG_CANONICAL_UNITS = {
    "kg": "Kg", "cai": "Cái", "goi": "Gói", "hop": "Hộp", "chai": "Chai",
    "can": "Can", "qua": "Quả", "thung": "Thùng", "lo": "Lọ", "tui": "Túi",
    "doi": "Đôi", "lit": "Lít", "cuon": "Cuộn", "bich": "Bịch", "coc": "Cốc",
    "vi": "Vỉ", "bo": "Bộ", "mo": "Mớ", "la": "Lá", "bao": "Bao",
    "tuyp": "Tuýp", "con": "Con", "to": "Tô", "binh": "Bình",
    "cay": "Cây", "vien": "Viên", "ly": "Ly", "cu": "Củ", "tap": "Tập",
    "lon": "Lon", "ong": "Ống", "le": "Lễ", "tep": "Tệp", "dia": "Đĩa",
    "mieng": "Miếng", "day": "Dây", "suat": "Suất",
}


def ensure_column(conn, table: str, name: str, definition: str):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if name not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_contract_schema(conn):
    conn.executescript(ADVANCED_SCHEMA)
    ensure_column(conn, "products", "product_group", "TEXT")
    ensure_column(conn, "products", "catalog_updated_at", "TEXT")
    ensure_column(conn, "orders", "damaged_qty", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "orders", "supplier_return_qty", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "orders", "customer_return_qty", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "payroll_adjustments", "gross_override", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "payroll_adjustments", "net_override", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "payroll_adjustments", "use_override", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "meal_plans", "import_key", "TEXT")
    ensure_column(conn, "meal_plans", "source_file", "TEXT")
    ensure_column(conn, "meal_plans", "source_sheet", "TEXT")
    ensure_column(conn, "meal_plans", "source_row_start", "INTEGER")
    ensure_column(conn, "meal_plans", "source_row_end", "INTEGER")
    ensure_column(conn, "meal_plans", "menu_count", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "meal_plans", "servings_per_menu", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "meal_plans", "meal_price", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "meal_plans", "other_cost", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "meal_plans", "source_financials_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(conn, "meal_plan_items", "source_norm_per_1000", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "meal_plan_items", "applicable_meal_count", "REAL NOT NULL DEFAULT 0")
    ensure_column(conn, "meal_plan_items", "source_row", "INTEGER")
    ensure_column(conn, "meal_plan_items", "source_amount", "REAL NOT NULL DEFAULT 0")
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_meal_plan_import_key
           ON meal_plans(import_key) WHERE import_key IS NOT NULL AND import_key!=''"""
    )
    defaults = {
        "tenant_code": "TDP",
        "printer_name": "",
        "print_copies": "1",
        "print_paper": "A4",
        # Từ mẫu "Đề nghị Thanh toán TĐP (T04.26).xlsx" khách đã cung cấp.
        "payment_requester": "VŨ THỊ THỤY",
        "payment_bank_name": "Ngân hàng TMCP Ngoại Thương Việt Nam",
        "payment_bank_account": "1052787580",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING",
            (key, value),
        )
    # Bản demo cũ đã tạo ba khóa này với giá trị rỗng; chỉ điền phần còn trống để
    # không ghi đè cấu hình mà người dùng đã chủ động sửa.
    for key in ("payment_requester", "payment_bank_name", "payment_bank_account"):
        conn.execute(
            "UPDATE settings SET value=? WHERE key=? AND TRIM(COALESCE(value,''))=''",
            (defaults[key], key),
        )


def first_value(data: dict, *keys, default=""):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def as_number(value, default=0.0) -> float:
    if value in (None, ""):
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return float(default)


def as_date(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return text[:10]


def audit(conn, now_iso, event_type: str, status: str, message: str = "", entity_type="", entity_id="", metadata=None):
    conn.execute(
        "INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (event_type, entity_type, str(entity_id or ""), status, message,
         json.dumps(metadata or {}, ensure_ascii=False), now_iso()),
    )


def mapping_key(value) -> str:
    text = str(value or "").strip().lower().replace("đ", "d")
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "", text)


def mapping_cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r"\s+", " ", str(value).strip())


def catalog_unit(value) -> str:
    text = mapping_cell_text(value)
    return CATALOG_CANONICAL_UNITS.get(mapping_key(text), text)


def catalog_tax(value) -> str:
    if value in (None, "") or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = mapping_cell_text(value).upper()
        if mapping_key(text) in {"kkknt", "kct", "khongkekhai"}:
            return "KKKNT"
        text = text.replace("%", "").replace(",", ".").strip()
        try:
            number = float(text)
        except ValueError:
            return mapping_cell_text(value)
    if number > 1:
        number /= 100
    return f"{number:.6f}".rstrip("0").rstrip(".")


def catalog_header_fields(row) -> dict:
    found = {}
    for column_index, value in enumerate(row, start=1):
        key = mapping_key(value)
        if not key:
            continue
        for field_name, accepted in CATALOG_ALIASES.items():
            if field_name not in found and key in accepted:
                found[field_name] = column_index
                break
    return found


def find_catalog_sheet(workbook):
    candidates = []
    required = {"product_code", "product_name", "unit", "tax"}
    for sheet_index, worksheet in enumerate(workbook.worksheets):
        for row_index, row in enumerate(
            worksheet.iter_rows(min_row=1, max_row=25, max_col=30, values_only=True),
            start=1,
        ):
            fields = catalog_header_fields(row)
            if required.issubset(fields):
                candidates.append((len(fields), -sheet_index, -row_index, worksheet, row_index, fields))
    if not candidates:
        return None
    _, _, _, worksheet, row_index, fields = max(candidates, key=lambda item: item[:3])
    return worksheet, row_index, fields


def catalog_database_state_hash(conn) -> str:
    digest = hashlib.sha256()
    for row in conn.execute(
        "SELECT code,name,unit,tax,COALESCE(product_group,'') product_group FROM products ORDER BY code"
    ):
        digest.update(json.dumps(list(row), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    for row in conn.execute(
        "SELECT product_code,invoice_name FROM outgoing_product_names ORDER BY product_code"
    ):
        digest.update(json.dumps(list(row), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def parse_catalog_workbook(conn, workbook) -> dict:
    found = find_catalog_sheet(workbook)
    if not found:
        raise ValueError("Không tìm thấy bảng có Mã hàng, Tên Thành Đạt Phát, ĐVT và Thuế")
    worksheet, header_row, fields = found
    existing_products = {
        row["code"]: dict(row)
        for row in conn.execute(
            "SELECT code,name,unit,tax,COALESCE(product_group,'') product_group FROM products"
        )
    }
    existing_names = {
        row["product_code"]: row["invoice_name"]
        for row in conn.execute("SELECT product_code,invoice_name FROM outgoing_product_names")
    }
    rows = []
    unique_items = {}
    scanned = 0
    max_column = max(fields.values())
    for row_index, row in enumerate(
        worksheet.iter_rows(
            min_row=header_row + 1,
            max_row=min(worksheet.max_row, header_row + MAPPING_IMPORT_MAX_ROWS + 1),
            max_col=max_column,
            values_only=True,
        ),
        start=header_row + 1,
    ):
        code = mapping_cell_text(row[fields["product_code"] - 1]).upper()
        name = mapping_cell_text(row[fields["product_name"] - 1])
        unit = catalog_unit(row[fields["unit"] - 1])
        tax = catalog_tax(row[fields["tax"] - 1])
        group = mapping_cell_text(row[fields["product_group"] - 1]).upper() if "product_group" in fields else ""
        invoice_name = mapping_cell_text(row[fields["invoice_name"] - 1]) if "invoice_name" in fields else ""
        if not any((code, name, unit, tax, group, invoice_name)):
            continue
        scanned += 1
        item = {
            "source_row": row_index,
            "product_code": code,
            "product_group": group,
            "product_name": name,
            "invoice_name": invoice_name,
            "unit": unit,
            "tax": tax,
            "product_status": "error",
            "invoice_status": "none",
            "warnings": [],
            "errors": [],
            "apply": False,
        }
        if not code:
            item["errors"].append("Thiếu mã hàng")
        if not name:
            item["errors"].append("Thiếu tên Thành Đạt Phát")
        if not unit:
            item["errors"].append("Thiếu đơn vị tính")
        if not tax:
            item["errors"].append("Thiếu thuế")
        if "invoice_name" in fields and not invoice_name:
            item["errors"].append("Thiếu tên xuất hóa đơn")

        previous = unique_items.get(code) if code else None
        if previous:
            signature = (mapping_key(name), mapping_key(invoice_name), mapping_key(unit), tax, group)
            previous_signature = (
                mapping_key(previous["product_name"]), mapping_key(previous["invoice_name"]),
                mapping_key(previous["unit"]), previous["tax"], previous["product_group"],
            )
            if signature == previous_signature:
                item["product_status"] = "duplicate"
                item["invoice_status"] = "duplicate"
                item["warnings"].append(
                    f"Trùng hoàn toàn với dòng {previous['source_row']}; chỉ nhập một lần"
                )
            else:
                item["errors"].append(
                    f"Cùng mã nhưng khác dữ liệu với dòng {previous['source_row']}"
                )
                previous["errors"].append(f"Cùng mã nhưng khác dữ liệu với dòng {row_index}")
                previous["product_status"] = "error"
                previous["invoice_status"] = "error"
                previous["apply"] = False
            rows.append(item)
            continue

        if code:
            unique_items[code] = item
        if item["errors"]:
            rows.append(item)
            continue

        current = existing_products.get(code)
        if not current:
            item["product_status"] = "new"
        else:
            base_changed = any((
                mapping_key(current.get("name")) != mapping_key(name),
                mapping_key(current.get("unit")) != mapping_key(unit),
                catalog_tax(current.get("tax")) != tax,
                mapping_key(current.get("product_group")) != mapping_key(group),
            ))
            item["product_status"] = "update" if base_changed else "unchanged"

        if invoice_name:
            current_invoice_name = existing_names.get(code, "")
            if not current_invoice_name:
                item["invoice_status"] = "new"
            elif mapping_key(current_invoice_name) == mapping_key(invoice_name):
                item["invoice_status"] = "unchanged"
            else:
                item["invoice_status"] = "update"
                item["warnings"].append("Tên xuất hóa đơn sẽ được cập nhật sau khi xác nhận")
        item["apply"] = True
        rows.append(item)

    if scanned > MAPPING_IMPORT_MAX_ROWS:
        raise ValueError(f"File vượt quá giới hạn {MAPPING_IMPORT_MAX_ROWS:,} dòng dữ liệu")
    if not rows:
        raise ValueError("Sheet được nhận diện nhưng không có dòng dữ liệu")

    unique_rows = [item for item in rows if item["apply"] and item["product_status"] != "duplicate"]
    incoming_codes = {item["product_code"] for item in unique_rows}
    retained_codes = sorted(set(existing_products) - incoming_codes)
    counts = {
        "total": len(rows),
        "unique_products": len(unique_rows),
        "new_products": sum(item["product_status"] == "new" for item in unique_rows),
        "update_products": sum(item["product_status"] == "update" for item in unique_rows),
        "unchanged_products": sum(item["product_status"] == "unchanged" for item in unique_rows),
        "retained_products": len(retained_codes),
        "new_names": sum(item["invoice_status"] == "new" for item in unique_rows),
        "update_names": sum(item["invoice_status"] == "update" for item in unique_rows),
        "unchanged_names": sum(item["invoice_status"] == "unchanged" for item in unique_rows),
        "duplicate": sum(item["product_status"] == "duplicate" for item in rows),
        "error": sum(bool(item["errors"]) for item in rows),
    }
    return {
        "sheet": worksheet.title,
        "header_row": header_row,
        "rows": rows,
        "items": unique_rows,
        "counts": counts,
        "retained_codes": retained_codes,
        "database_state_hash": catalog_database_state_hash(conn),
        "can_confirm": counts["error"] == 0,
    }


def mapping_header_fields(row, mapping_type: str) -> dict:
    aliases = MAPPING_ALIASES[mapping_type]
    found = {}
    for column_index, value in enumerate(row, start=1):
        key = mapping_key(value)
        if not key:
            continue
        for field_name, accepted in aliases.items():
            if field_name not in found and key in accepted:
                found[field_name] = column_index
                break
    return found


def mapping_header_is_valid(fields: dict, mapping_type: str) -> bool:
    if "target_value" not in fields:
        return False
    if mapping_type == "invoice_names":
        return "product_code" in fields or "product_name" in fields
    return "source_code" in fields or "source_name" in fields


def find_mapping_sheet(workbook, mapping_type: str):
    candidates = []
    for sheet_index, worksheet in enumerate(workbook.worksheets):
        for row_index, row in enumerate(
            worksheet.iter_rows(min_row=1, max_row=25, max_col=30, values_only=True),
            start=1,
        ):
            fields = mapping_header_fields(row, mapping_type)
            if mapping_header_is_valid(fields, mapping_type):
                candidates.append((len(fields), -sheet_index, -row_index, worksheet, row_index, fields))
    if not candidates:
        return None
    _, _, _, worksheet, row_index, fields = max(candidates, key=lambda item: item[:3])
    return worksheet, row_index, fields


def mapping_catalog(conn, mapping_type: str) -> dict:
    if mapping_type == "invoice_names":
        rows = [dict(row) for row in conn.execute("SELECT code,name FROM products ORDER BY code")]
    else:
        rows = [dict(row) for row in conn.execute("SELECT code,name FROM kitchens ORDER BY code")]
    by_code = {mapping_cell_text(row["code"]).upper(): row for row in rows}
    by_name = defaultdict(list)
    for row in rows:
        name_key = mapping_key(row.get("name"))
        if name_key:
            by_name[name_key].append(row)
    return {"by_code": by_code, "by_name": by_name}


def resolve_mapping_source(raw_code: str, raw_name: str, catalog: dict) -> tuple[dict | None, list, list]:
    warnings = []
    errors = []
    code = mapping_cell_text(raw_code).upper()
    name = mapping_cell_text(raw_name)
    resolved = catalog["by_code"].get(code) if code else None
    if resolved:
        if name and mapping_key(name) != mapping_key(resolved.get("name")):
            warnings.append("Tên trong file khác danh mục; hệ thống dùng mã để ghép")
        return resolved, warnings, errors

    lookup_name = name or (raw_code if code else "")
    matches = catalog["by_name"].get(mapping_key(lookup_name), []) if lookup_name else []
    if len(matches) == 1:
        if code:
            warnings.append(f"Mã/giá trị {code} chưa có trong danh mục; hệ thống ghép theo tên")
        return matches[0], warnings, errors
    if len(matches) > 1:
        errors.append("Tên nguồn trùng nhiều mã trong danh mục; cần bổ sung mã")
    elif code:
        errors.append(f"Mã {code} chưa có trong danh mục")
    elif name:
        errors.append("Tên nguồn chưa khớp danh mục")
    else:
        errors.append("Thiếu mã hoặc tên nguồn")
    return None, warnings, errors


def parse_mapping_workbook(conn, workbook, mapping_type: str) -> dict:
    found = find_mapping_sheet(workbook, mapping_type)
    if not found:
        expected = "Mã/Tên hàng và Tên xuất hóa đơn" if mapping_type == "invoice_names" else "Mã/Tên bếp và XCOM (xưởng cơm)"
        raise ValueError(f"Không tìm thấy dòng tiêu đề có {expected}")
    worksheet, header_row, fields = found
    catalog = mapping_catalog(conn, mapping_type)
    existing_table = "outgoing_product_names" if mapping_type == "invoice_names" else "kitchen_units"
    existing_key = "product_code" if mapping_type == "invoice_names" else "kitchen_code"
    existing_value = "invoice_name" if mapping_type == "invoice_names" else "unit_code"
    existing = {
        row[existing_key]: row[existing_value]
        for row in conn.execute(f"SELECT {existing_key},{existing_value} FROM {existing_table}")
    }
    source_code_field = "product_code" if mapping_type == "invoice_names" else "source_code"
    source_name_field = "product_name" if mapping_type == "invoice_names" else "source_name"
    rows = []
    seen = {}
    scanned = 0
    for row_index, row in enumerate(
        worksheet.iter_rows(
            min_row=header_row + 1,
            max_row=header_row + MAPPING_IMPORT_MAX_ROWS + 1,
            max_col=max(fields.values()),
            values_only=True,
        ),
        start=header_row + 1,
    ):
        raw_code = mapping_cell_text(row[fields[source_code_field] - 1]) if source_code_field in fields else ""
        raw_name = mapping_cell_text(row[fields[source_name_field] - 1]) if source_name_field in fields else ""
        target = mapping_cell_text(row[fields["target_value"] - 1])
        if not raw_code and not raw_name and not target:
            continue
        if mapping_key(target) in MAPPING_ALIASES[mapping_type]["target_value"]:
            continue
        scanned += 1
        item = {
            "source_row": row_index,
            "source_code": raw_code,
            "source_name": raw_name,
            "resolved_code": "",
            "resolved_name": "",
            "target_value": target.upper() if mapping_type == "kitchen_units" else target,
            "current_value": "",
            "status": "error",
            "warnings": [],
            "errors": [],
            "apply": False,
        }
        if not target:
            item["errors"].append("Thiếu giá trị cần nhập")
        resolved, warnings, errors = resolve_mapping_source(raw_code, raw_name, catalog)
        item["warnings"].extend(warnings)
        item["errors"].extend(errors)
        if resolved:
            code = mapping_cell_text(resolved["code"]).upper()
            item["resolved_code"] = code
            item["resolved_name"] = mapping_cell_text(resolved.get("name"))
            item["current_value"] = mapping_cell_text(existing.get(code))
        if item["errors"]:
            rows.append(item)
            continue

        code = item["resolved_code"]
        target_compare = mapping_key(item["target_value"])
        previous = seen.get(code)
        if previous:
            if mapping_key(previous["target_value"]) == target_compare:
                item["status"] = "duplicate"
                item["warnings"].append(f"Trùng nội dung với dòng {previous['source_row']}; chỉ nhập một lần")
                previous["warnings"].append(f"Có dòng trùng {row_index}; chỉ nhập một lần")
            else:
                message = f"Cùng mã nhưng khác giá trị với dòng {previous['source_row']}"
                item["errors"].append(message)
                item["status"] = "error"
                previous["errors"].append(f"Cùng mã nhưng khác giá trị với dòng {row_index}")
                previous["status"] = "error"
                previous["apply"] = False
            rows.append(item)
            continue

        seen[code] = item
        if not item["current_value"]:
            item["status"] = "new"
        elif mapping_key(item["current_value"]) == target_compare:
            item["status"] = "unchanged"
        else:
            item["status"] = "update"
            item["warnings"].append("Sẽ thay giá trị đang lưu sau khi xác nhận")
        item["apply"] = True
        rows.append(item)

    if scanned > MAPPING_IMPORT_MAX_ROWS:
        raise ValueError(f"File vượt quá giới hạn {MAPPING_IMPORT_MAX_ROWS:,} dòng dữ liệu")
    if not rows:
        raise ValueError("Sheet được nhận diện nhưng không có dòng dữ liệu")

    counts = {
        "total": len(rows),
        "new": sum(item["status"] == "new" for item in rows),
        "update": sum(item["status"] == "update" for item in rows),
        "unchanged": sum(item["status"] == "unchanged" for item in rows),
        "duplicate": sum(item["status"] == "duplicate" for item in rows),
        "error": sum(bool(item["errors"]) for item in rows),
    }
    return {
        "sheet": worksheet.title,
        "header_row": header_row,
        "rows": rows,
        "items": [
            {"code": item["resolved_code"], "target_value": item["target_value"]}
            for item in rows if item["apply"] and not item["errors"]
        ],
        "counts": counts,
        "can_confirm": counts["error"] == 0,
    }


OPENING_ALIASES = {
    "product_code": {"matdp", "mahangtdp", "mavattutdp", "masptdp", "mahhtdp"},
    "product_name": {"tentdp", "tenhangtdp", "tenhanghoatdp", "tenvattutdp"},
    "invoice_name": {"tentrenhd", "tentrenhoadon", "tenhoadon", "tenxuathoadon"},
    "warehouse_code": {"makho", "mahangkho", "mavattukho"},
    "tax": {"tsuat", "thuesuat", "thuegtgt", "vat"},
    "unit": {"dvt", "donvitinh", "unit"},
    "qty": {"soluong", "toncuoikysoluong", "tondaukysoluong", "toncuoiky", "tondauky"},
    "unit_cost": {"dongia", "giavon", "dongiavon"},
    "amount": {"thanhtien", "giatriton", "giatritonkho"},
}


def opening_header_fields(*header_rows) -> dict:
    width = max((len(row) for row in header_rows), default=0)
    fields = {}
    for column in range(width):
        parts = [mapping_key(row[column]) for row in header_rows if column < len(row)]
        keys = {part for part in parts if part}
        combined = "".join(part for part in parts if part)
        if combined:
            keys.add(combined)
        for field, aliases in OPENING_ALIASES.items():
            if field not in fields and keys.intersection(aliases):
                fields[field] = column + 1
    return fields


def find_opening_sheet(workbook):
    candidates = []
    for sheet_index, worksheet in enumerate(workbook.worksheets):
        rows = list(worksheet.iter_rows(
            min_row=1, max_row=min(worksheet.max_row or 0, 26), max_col=30, values_only=True,
        ))
        for index, row in enumerate(rows):
            single = opening_header_fields(row)
            if {"product_code", "qty"}.issubset(single):
                candidates.append((len(single), -sheet_index, -(index + 1), worksheet, index + 1, single))
            if index + 1 < len(rows):
                double = opening_header_fields(row, rows[index + 1])
                if {"product_code", "qty"}.issubset(double):
                    candidates.append((len(double), -sheet_index, -(index + 2), worksheet, index + 2, double))
    if not candidates:
        return None
    _, _, _, worksheet, header_end, fields = max(candidates, key=lambda item: item[:3])
    return worksheet, header_end, fields


def opening_number(value):
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(" ", "").replace("₫", "").replace("đ", "")
        if not text:
            return None
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") > 1:
            text = text.replace(".", "")
        try:
            number = float(text)
        except (TypeError, ValueError):
            return None
    return number if math.isfinite(number) else None


def first_most_common(values) -> str:
    values = [mapping_cell_text(value) for value in values if mapping_cell_text(value)]
    return Counter(values).most_common(1)[0][0] if values else ""


def parse_opening_workbook(conn, workbook, period: str) -> dict:
    found = find_opening_sheet(workbook)
    if not found:
        raise ValueError("Không tìm thấy dòng tiêu đề có Mã TĐP và Số lượng tồn")
    worksheet, header_end, fields = found
    missing_columns = [
        label for field, label in (
            ("product_name", "Tên TĐP"), ("unit", "ĐVT"),
            ("unit_cost", "Đơn giá"), ("amount", "Thành tiền"),
        ) if field not in fields
    ]
    if missing_columns:
        raise ValueError("File thiếu cột: " + ", ".join(missing_columns))

    source_rows = []
    scanned = 0
    max_column = max(fields.values())
    for row_index, row in enumerate(
        worksheet.iter_rows(
            min_row=header_end + 1,
            max_row=header_end + MAPPING_IMPORT_MAX_ROWS + 1,
            max_col=max_column,
            values_only=True,
        ),
        start=header_end + 1,
    ):
        raw = {field: row[column - 1] for field, column in fields.items()}
        code = mapping_cell_text(raw.get("product_code")).upper()
        if not code and not any(value not in (None, "") for value in raw.values()):
            continue
        if mapping_key(code) in OPENING_ALIASES["product_code"]:
            continue
        scanned += 1
        item = {
            "source_row": row_index,
            "product_code": code,
            "product_name": mapping_cell_text(raw.get("product_name")),
            "invoice_name": mapping_cell_text(raw.get("invoice_name")),
            "warehouse_code": mapping_cell_text(raw.get("warehouse_code")).upper(),
            "tax": mapping_cell_text(raw.get("tax")),
            "unit": mapping_cell_text(raw.get("unit")),
            "qty": opening_number(raw.get("qty")),
            "unit_cost": opening_number(raw.get("unit_cost")),
            "amount": opening_number(raw.get("amount")),
            "warnings": [],
            "errors": [],
        }
        if not code:
            item["errors"].append("Thiếu Mã TĐP")
        if item["qty"] is None:
            item["errors"].append("Số lượng tồn không hợp lệ")
        if item["unit_cost"] is None and item["amount"] is None:
            item["warnings"].append("Thiếu cả đơn giá và thành tiền; giá trị tồn được ghi là 0")
        if item["qty"] is not None:
            if item["amount"] is None and item["unit_cost"] is not None:
                item["amount"] = item["qty"] * item["unit_cost"]
                item["warnings"].append("Thiếu thành tiền; hệ thống tính Số lượng × Đơn giá")
            elif item["amount"] is not None and item["unit_cost"] is None and item["qty"]:
                item["unit_cost"] = abs(item["amount"] / item["qty"])
                item["warnings"].append("Thiếu đơn giá; hệ thống suy ra từ Thành tiền / Số lượng")
            elif item["amount"] is not None and item["unit_cost"] is not None:
                calculated = item["qty"] * item["unit_cost"]
                if abs(item["amount"] - calculated) > max(1, abs(item["amount"]) * 0.000001):
                    item["warnings"].append("Thành tiền lệch Số lượng × Đơn giá; ưu tiên Thành tiền sổ sách")
        item["amount"] = item["amount"] if item["amount"] is not None else 0.0
        item["unit_cost"] = item["unit_cost"] if item["unit_cost"] is not None else 0.0
        source_rows.append(item)

    if scanned > MAPPING_IMPORT_MAX_ROWS:
        raise ValueError(f"File vượt quá giới hạn {MAPPING_IMPORT_MAX_ROWS:,} dòng dữ liệu")
    if not source_rows:
        raise ValueError("Sheet được nhận diện nhưng không có dòng tồn đầu kỳ")

    products = {
        row["code"]: dict(row)
        for row in conn.execute("SELECT code,name,unit,tax,buy_price FROM products")
    }
    existing_openings = {
        row["source_line"]: dict(row)
        for row in conn.execute(
            """SELECT source_line,qty_in,qty_out,unit_cost FROM inventory_transactions
               WHERE source_type='OPENING' AND source_id=?""",
            (period,),
        )
    }
    grouped = defaultdict(list)
    orphan_errors = []
    for item in source_rows:
        if item["product_code"]:
            grouped[item["product_code"]].append(item)
        elif item["errors"]:
            orphan_errors.append(item)

    rows = []
    items = []
    for code, parts in grouped.items():
        names = [part["product_name"] for part in parts if part["product_name"]]
        units = [part["unit"] for part in parts if part["unit"]]
        taxes = [part["tax"] for part in parts if part["tax"]]
        invoice_names = [part["invoice_name"] for part in parts if part["invoice_name"]]
        qty = sum(part["qty"] or 0 for part in parts)
        amount = sum(part["amount"] or 0 for part in parts)
        source_row_numbers = [part["source_row"] for part in parts]
        warehouse_codes = list(dict.fromkeys(
            part["warehouse_code"] for part in parts if part["warehouse_code"]
        ))
        product = products.get(code)
        item = {
            "product_code": code,
            "product_name": first_most_common(names),
            "unit": first_most_common(units),
            "tax": first_most_common(taxes),
            "invoice_name": first_most_common(invoice_names),
            "qty": qty,
            "amount": amount,
            "unit_cost": abs(amount / qty) if abs(qty) > 1e-12 else 0,
            "source_rows": source_row_numbers,
            "warehouse_codes": warehouse_codes,
            "source_row_count": len(parts),
            "create_product": product is None,
            "status": "update" if code in existing_openings else "new",
            "current_qty": (
                existing_openings[code]["qty_in"] - existing_openings[code]["qty_out"]
                if code in existing_openings else 0
            ),
            "warnings": [],
            "errors": [],
        }
        for part in parts:
            item["warnings"].extend(part["warnings"])
            item["errors"].extend(part["errors"])
        if len(parts) > 1:
            item["warnings"].append(
                f"Đã gộp {len(parts)} dòng/mã kho theo cùng Mã TĐP"
            )
        distinct_names = list(dict.fromkeys(mapping_cell_text(value) for value in names if value))
        distinct_units = list(dict.fromkeys(mapping_cell_text(value) for value in units if value))
        if len({mapping_key(value) for value in distinct_names}) > 1:
            item["warnings"].append("Một Mã TĐP có nhiều tên nguồn; tồn được gộp theo mã")
        if len({mapping_key(value) for value in distinct_units}) > 1:
            item["warnings"].append("Một Mã TĐP có nhiều ĐVT nguồn; cần hiểu số lượng là tổng theo mã")
        if abs(qty) <= 1e-12:
            item["errors"].append("Tổng số lượng sau gộp bằng 0")
        if qty < 0:
            item["warnings"].append("Tồn đầu kỳ âm; hệ thống giữ đúng số sổ sách")
        if amount and qty and amount * qty < 0:
            item["errors"].append("Thành tiền và số lượng trái dấu")
        if product:
            if distinct_names and all(
                mapping_key(name) != mapping_key(product["name"]) for name in distinct_names
            ):
                item["warnings"].append(
                    f"Tên trong file khác danh mục ({product['name']}); hệ thống giữ danh mục hiện tại"
                )
            if distinct_units and all(
                mapping_key(unit) != mapping_key(product["unit"]) for unit in distinct_units
            ):
                item["warnings"].append(
                    f"ĐVT trong file khác danh mục ({product['unit']}); hệ thống giữ danh mục hiện tại"
                )
        else:
            if not item["product_name"]:
                item["errors"].append("Mã mới thiếu Tên TĐP")
            if not item["unit"]:
                item["errors"].append("Mã mới thiếu ĐVT")
            item["warnings"].append("Mã mới sẽ được thêm vào danh mục; chưa có NCC mặc định")
        item["warnings"] = list(dict.fromkeys(item["warnings"]))
        item["errors"] = list(dict.fromkeys(item["errors"]))
        rows.append(item)
        if not item["errors"]:
            items.append({key: item[key] for key in (
                "product_code", "product_name", "unit", "tax", "invoice_name", "qty",
                "amount", "unit_cost", "source_rows", "warehouse_codes", "create_product",
            )})

    rows.extend({
        "product_code": "", "product_name": item["product_name"], "unit": item["unit"],
        "tax": item["tax"], "invoice_name": item["invoice_name"], "qty": item["qty"] or 0,
        "amount": item["amount"], "unit_cost": item["unit_cost"],
        "source_rows": [item["source_row"]], "warehouse_codes": [item["warehouse_code"]],
        "source_row_count": 1, "create_product": False, "status": "error", "current_qty": 0,
        "warnings": item["warnings"], "errors": item["errors"],
    } for item in orphan_errors)
    rows.sort(key=lambda item: (not bool(item["errors"]), not bool(item["warnings"]), item["product_code"]))
    counts = {
        "source_rows": len(source_rows),
        "items": len(grouped),
        "new_products": sum(item["create_product"] for item in rows),
        "new": sum(item["status"] == "new" for item in rows),
        "update": sum(item["status"] == "update" for item in rows),
        "negative": sum(item["qty"] < 0 for item in rows),
        "warning": sum(bool(item["warnings"]) for item in rows),
        "error": sum(bool(item["errors"]) for item in rows),
    }
    return {
        "sheet": worksheet.title,
        "header_row": header_end,
        "period": period,
        "rows": rows,
        "items": items,
        "counts": counts,
        "totals": {
            "qty": sum(item["qty"] for item in rows),
            "amount": sum(item["amount"] for item in rows),
        },
        "can_confirm": counts["error"] == 0,
    }


MEAL_ATTENDANCE_GROUPS = (
    ("dainam", "DAINAM"),
    ("havico", "HAVICO"),
    ("thaco", "THACO"),
    ("sunby", "SUNBY"),
    ("lucky", "LUCKY"),
    ("vina", "VINA"),
    ("united", "UNI"),
    ("uni", "UNI"),
    ("bot", "BOT"),
    ("pot", "BOT"),
    ("tq", "TQ"),
)


def meal_attendance_group(value) -> str:
    key = mapping_key(value)
    for token, code in MEAL_ATTENDANCE_GROUPS:
        if token in key:
            return code
    return ""


def meal_attendance_shift(value) -> str:
    key = mapping_key(value)
    if "sang" in key:
        return "Sáng"
    if "trua" in key:
        return "Trưa"
    if "chieu" in key:
        return "Chiều"
    if "dem" in key or "toi" in key:
        return "Đêm"
    if "vaosuat" in key:
        return "Tổng"
    return ""


def meal_attendance_header_kind(value) -> str:
    key = mapping_key(value)
    if not key or any(token in key for token in ("chenhlech", "cl", "tong")):
        return ""
    if "dat" in key:
        return "ordered"
    if "an" in key or "vaosuat" in key or key.startswith("ca"):
        return "actual"
    return ""


def parse_meal_attendance_workbook(conn, workbook) -> dict:
    if "SUẤT ĂN" not in workbook.sheetnames:
        raise ValueError("File thiếu sheet SUẤT ĂN làm nguồn chấm suất")
    worksheet = workbook["SUẤT ĂN"]
    columns = {}
    current_group = ""
    for column in range(3, min(worksheet.max_column or 0, 80) + 1):
        group_label = worksheet.cell(1, column).value
        if group_label not in (None, ""):
            current_group = meal_attendance_group(group_label)
        shift = meal_attendance_shift(worksheet.cell(2, column).value)
        kind = meal_attendance_header_kind(worksheet.cell(2, column).value)
        if current_group and shift and kind:
            columns.setdefault((current_group, shift), {})[kind] = column
    if not columns:
        raise ValueError("Không nhận diện được cột bếp/ca trong sheet SUẤT ĂN")

    raw_items = []
    for row_index in range(3, min(worksheet.max_row or 0, 380) + 1):
        work_date = as_date(worksheet.cell(row_index, 2).value)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", work_date):
            continue
        for (kitchen, shift), source_columns in columns.items():
            actual = as_number(worksheet.cell(row_index, source_columns.get("actual", 0)).value) \
                if source_columns.get("actual") else 0
            ordered = as_number(worksheet.cell(row_index, source_columns.get("ordered", 0)).value) \
                if source_columns.get("ordered") else 0
            if abs(actual) <= 1e-12 and abs(ordered) <= 1e-12:
                continue
            source_column = "/".join(
                get_column_letter(column) for column in sorted(set(source_columns.values()))
            )
            raw_items.append({
                "work_date": work_date, "kitchen": kitchen, "shift": shift,
                "actual_count": actual, "ordered_count": ordered,
                "source_sheet": worksheet.title, "source_column": source_column,
                "errors": ["Số suất không được âm"] if actual < 0 or ordered < 0 else [],
                "warnings": [],
            })

    # TTS dùng ma trận ngày theo cột, nhóm người ăn theo dòng; tổng từng ngày là
    # số suất thực tế. Không lấy cột B dư từ file cũ vì dãy tháng chính bắt đầu ở C.
    if "TTS" in workbook.sheetnames:
        tts = workbook["TTS"]
        for column in range(3, min(tts.max_column or 0, 80) + 1):
            if mapping_key(tts.cell(4, column).value) == "tong":
                break
            work_date = as_date(tts.cell(4, column).value)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", work_date):
                continue
            actual = 0.0
            for row_index in range(6, min(tts.max_row or 0, 300) + 1):
                label = mapping_key(tts.cell(row_index, 1).value)
                if label == "tong":
                    break
                if label:
                    actual += max(as_number(tts.cell(row_index, column).value), 0)
            if actual > 0:
                raw_items.append({
                    "work_date": work_date, "kitchen": "TTS", "shift": "Tổng",
                    "actual_count": actual, "ordered_count": 0,
                    "source_sheet": tts.title, "source_column": tts.cell(4, column).column_letter,
                    "errors": [], "warnings": [],
                })

    if not raw_items:
        raise ValueError("File không có số suất ăn theo ngày để nhập")
    grouped = {}
    for item in raw_items:
        key = (item["work_date"], item["kitchen"], item["shift"])
        if key in grouped:
            grouped[key]["actual_count"] += item["actual_count"]
            grouped[key]["ordered_count"] += item["ordered_count"]
            grouped[key]["source_column"] += "+" + item["source_column"]
            grouped[key]["warnings"].append("Đã gộp nhiều vùng nguồn cùng ngày/bếp/ca")
        else:
            grouped[key] = item

    existing = {
        (row["work_date"], row["kitchen"], row["shift"]): dict(row)
        for row in conn.execute("SELECT * FROM meal_attendance")
    }
    rows = []
    items = []
    for key in sorted(grouped):
        item = grouped[key]
        previous = existing.get(key)
        if previous is None:
            status = "new"
        elif (
            abs(previous["actual_count"] - item["actual_count"]) <= 1e-9
            and abs(previous["ordered_count"] - item["ordered_count"]) <= 1e-9
        ):
            status = "unchanged"
        else:
            status = "update"
        item["status"] = status
        if item["ordered_count"] > 0 and abs(item["ordered_count"] - item["actual_count"]) > 1e-9:
            item["warnings"].append("Số đặt và số ăn thực tế chênh nhau")
        item["warnings"] = list(dict.fromkeys(item["warnings"]))
        rows.append(item)
        if not item["errors"]:
            items.append({key: item[key] for key in (
                "work_date", "kitchen", "shift", "actual_count", "ordered_count",
                "source_sheet", "source_column",
            )})
    periods = sorted({item["work_date"][:7] for item in rows})
    counts = {
        "items": len(rows),
        "dates": len({item["work_date"] for item in rows}),
        "kitchens": len({item["kitchen"] for item in rows}),
        "new": sum(item["status"] == "new" for item in rows),
        "update": sum(item["status"] == "update" for item in rows),
        "unchanged": sum(item["status"] == "unchanged" for item in rows),
        "warning": sum(bool(item["warnings"]) for item in rows),
        "error": sum(bool(item["errors"]) for item in rows),
    }
    return {
        "sheet": worksheet.title,
        "periods": periods,
        "rows": rows,
        "items": items,
        "counts": counts,
        "totals": {
            "actual": sum(item["actual_count"] for item in rows),
            "ordered": sum(item["ordered_count"] for item in rows),
        },
        "can_confirm": counts["error"] == 0,
    }


def kitchen_shift_label(values, previous="Ca sáng") -> str:
    for value in values:
        key = mapping_key(value)
        if "cachieu" in key:
            return "Ca chiều"
        if "catrua" in key:
            return "Ca trưa"
        if "cadem" in key:
            return "Ca đêm"
        if "casang" in key:
            return "Ca sáng"
    return previous or "Ca sáng"


def kitchen_block_name(segment, xcom_code: str) -> str:
    ignored = ("sosuat", "casang", "cachieu", "catrua", "cadem", "mahang", "mabep", "nhathau")
    candidates = []
    for row in segment:
        value = mapping_cell_text(row[4])
        key = mapping_key(value)
        if value and not any(token in key for token in ignored):
            candidates.append(value)
    name = candidates[-1] if candidates else xcom_code
    return re.sub(r"^(BẾP|BEP)\s+", "", name, flags=re.IGNORECASE).strip().upper()


def kitchen_financials(block_rows) -> dict:
    result = {
        "meal_price": 0,
        "source_revenue": 0,
        "source_food_cost": 0,
        "source_total_cost": 0,
        "source_profit": 0,
        "other_cost": 0,
        "components": [],
        "warnings": [],
    }
    for row in block_rows:
        label = mapping_cell_text(row[10])
        if not label:
            continue
        key = mapping_key(label)
        raw_value = row[11]
        value = as_number(raw_value)
        result["components"].append({"label": label, "value": value if raw_value not in (None, "") else None})
        if "tientinhcost" in key or key == "suatan":
            result["meal_price"] = value
        elif "doanhthu" in key or "tienthukhachhang" in key:
            result["source_revenue"] = value
        elif "tienchiphithucpham" in key:
            result["source_food_cost"] = value
        elif "tongchi" in key:
            result["source_total_cost"] = value
        elif "loinhuan" in key or "costca" in key:
            result["source_profit"] = value
        elif any(token in key for token in ("giavi", "matbang", "nhancong", "vanchuyen")) or key.startswith("gachi"):
            if raw_value in (None, ""):
                result["warnings"].append(f"{label}: chưa có số tiền")
            else:
                result["other_cost"] += value
    return result


def parse_kitchen_workbook(conn, workbook, work_date: str) -> dict:
    products = {
        row["code"]: dict(row)
        for row in conn.execute("SELECT code,name,unit,supplier FROM products")
    }
    known_kitchens = {row["code"] for row in conn.execute("SELECT code FROM kitchens")}
    plans = []
    plan_occurrences = Counter()
    for worksheet in workbook.worksheets:
        values = [
            list(row)
            for row in worksheet.iter_rows(
                min_row=1,
                max_row=min(worksheet.max_row or 0, 2_000),
                max_col=13,
                values_only=True,
            )
        ]
        header_row = 0
        for index, row in enumerate(values, start=1):
            if mapping_key(row[0]) == "nhathau" and mapping_key(row[1]) in {"mahang", "mavt", "masp"} and mapping_key(row[2]) == "mabep":
                header_row = index
                break
        if not header_row:
            continue

        markers = [header_row]
        for row_number in range(header_row + 1, len(values) + 1):
            row = values[row_number - 1]
            code = mapping_cell_text(row[1]).upper()
            label = mapping_cell_text(row[4])
            if (not code or code == "-") and label and as_number(row[5]) > 0:
                markers.append(row_number)

        previous_shift = "Ca sáng"
        for run_index, marker_row in enumerate(markers, start=1):
            block_end = (markers[run_index] - 1) if run_index < len(markers) else len(values)
            run = []
            for row_number in range(marker_row + 1, block_end + 1):
                row = values[row_number - 1]
                code = mapping_cell_text(row[1]).upper()
                xcom = mapping_cell_text(row[2]).upper()
                if code and code != "-" and xcom and as_number(row[5]) > 0:
                    run.append(row_number)
            if not run:
                continue
            start_row, end_row = run[0], run[-1]
            marker = values[marker_row - 1]
            marker_label = mapping_cell_text(marker[4])
            previous_shift = kitchen_shift_label([marker_label], previous_shift)
            servings_per_menu = as_number(marker[5])
            marker_total = as_number(marker[6])
            meal_count = marker_total if marker_total >= servings_per_menu > 0 else servings_per_menu
            ratio = meal_count / servings_per_menu if servings_per_menu > 0 else 1
            menu_count = max(int(round(ratio)), 1) if abs(ratio - round(ratio)) <= 0.01 else 1
            xcom_counts = Counter(
                mapping_cell_text(values[row_number - 1][2]).upper() for row_number in run
            )
            xcom_code = xcom_counts.most_common(1)[0][0]
            marker_key = mapping_key(marker_label)
            if marker_label and not any(token in marker_key for token in (
                "sosuat", "casang", "cachieu", "catrua", "cadem", "mahang", "mabep", "nhathau",
            )):
                kitchen = re.sub(r"^(BẾP|BEP)\s+", "", marker_label, flags=re.IGNORECASE).strip().upper()
            elif xcom_code and xcom_code != "XCOM":
                kitchen = xcom_code
            else:
                segment = values[max(0, marker_row - 2):marker_row - 1]
                kitchen = kitchen_block_name(segment, xcom_code)
            plan_errors = []
            plan_warnings = []
            if meal_count <= 0:
                plan_errors.append("Không tìm thấy số suất của nhóm")
            if servings_per_menu > 0 and marker_total > 0 and abs(ratio - round(ratio)) > 0.01:
                plan_warnings.append("Tổng suất không chia hết cho số suất/thực đơn; cần kiểm tra lại")
            if kitchen not in known_kitchens:
                plan_warnings.append(f"{kitchen}: chưa có trong danh mục bếp; sẽ ghi nhận từ file xưởng cơm")
            if len(xcom_counts) > 1:
                plan_errors.append("Một nhóm có nhiều mã XCOM khác nhau")

            items = []
            current_dish = ""
            seen_item_keys = set()
            for row_number in run:
                row = values[row_number - 1]
                code = mapping_cell_text(row[1]).upper()
                dish = mapping_cell_text(row[3])
                if dish:
                    current_dish = dish
                norm_raw = as_number(row[5])
                file_required = as_number(row[6])
                formula_norm_qty = norm_raw / 1000
                formula_required = formula_norm_qty * meal_count
                required_qty = file_required if file_required > 0 else formula_required
                norm_qty = required_qty / meal_count if meal_count > 0 else formula_norm_qty
                applicable_meal_count = (
                    required_qty * 1000 / norm_raw if norm_raw > 0 and required_qty > 0 else meal_count
                )
                price = as_number(row[8])
                price_group = mapping_cell_text(row[0]).upper()
                source_amount_raw = row[9]
                source_amount = as_number(source_amount_raw)
                calculated_amount = required_qty * price
                item_errors = []
                item_warnings = []
                product = products.get(code)
                if not product:
                    item_errors.append(f"Mã {code} chưa có trong danh mục")
                item_key = (mapping_key(current_dish), code)
                if item_key in seen_item_keys:
                    item_errors.append(f"Mã {code} bị lặp trong cùng món {current_dish or '(chưa có tên)'}")
                seen_item_keys.add(item_key)
                if price <= 0:
                    item_warnings.append("Thiếu giá nguyên liệu")
                if file_required > 0 and abs(file_required - formula_required) > max(0.01, formula_required * 0.01):
                    item_warnings.append("Số lượng áp dụng khác tổng suất (có thể do chia thực đơn); hệ thống giữ đúng số trong file")
                if calculated_amount > 0 and source_amount_raw in (None, ""):
                    item_warnings.append("Cột Thành tiền đang trống; hệ thống tự tính Số lượng × Đơn giá")
                elif source_amount_raw not in (None, "") and abs(source_amount - calculated_amount) > max(1, calculated_amount * 0.001):
                    item_warnings.append("Thành tiền trong file lệch Số lượng × Đơn giá; hệ thống dùng số tính lại")
                item = {
                    "source_row": row_number,
                    "product_code": code,
                    "source_name": mapping_cell_text(row[4]),
                    "product_name": product["name"] if product else mapping_cell_text(row[4]),
                    "dish_name": current_dish,
                    "norm_per_1000": norm_raw,
                    "norm_qty": norm_qty,
                    "applicable_meal_count": applicable_meal_count,
                    "required_qty": required_qty,
                    "file_required_qty": file_required,
                    "source_amount": source_amount,
                    "calculated_amount": calculated_amount,
                    "unit": mapping_cell_text(row[7]) or (product["unit"] if product else ""),
                    "supplier": product["supplier"] if product else "",
                    "buy_price": price,
                    "price_source": f"{price_group} · File xưởng cơm" if price_group else "File xưởng cơm",
                    "errors": item_errors,
                    "warnings": item_warnings,
                }
                items.append(item)
                plan_errors.extend(item_errors)
                plan_warnings.extend(item_warnings)

            financials = kitchen_financials(values[marker_row:block_end])
            plan_warnings.extend(financials["warnings"])
            food_cost = sum(item["calculated_amount"] for item in items)
            calculated_revenue = meal_count * financials["meal_price"]
            calculated_total_cost = food_cost + financials["other_cost"]
            calculated_profit = calculated_revenue - calculated_total_cost
            if financials["meal_price"] <= 0:
                plan_warnings.append("Chưa tìm thấy đơn giá suất ăn trong bảng tính cost")
            if financials["source_revenue"] > 0 and abs(financials["source_revenue"] - calculated_revenue) > 1:
                plan_warnings.append("Doanh thu trong file lệch Tổng suất × Đơn giá suất")
            if financials["source_food_cost"] > 0 and abs(financials["source_food_cost"] - food_cost) > 1:
                plan_warnings.append("Chi phí thực phẩm tổng trong file bị thiếu/cũ; hệ thống đã tính lại từng nguyên liệu")
            if financials["source_total_cost"] > 0 and abs(financials["source_total_cost"] - calculated_total_cost) > 1:
                plan_warnings.append("Tổng chi trong file bị thiếu/cũ; hệ thống đã tính lại từ chi tiết")
            financials.update({
                "calculated_revenue": calculated_revenue,
                "calculated_food_cost": food_cost,
                "calculated_total_cost": calculated_total_cost,
                "calculated_profit": calculated_profit,
            })
            financials["warnings"] = list(dict.fromkeys(
                warning for warning in plan_warnings
                if "chưa có trong danh mục bếp" not in warning
            ))
            occurrence_key = (kitchen, previous_shift)
            plan_occurrences[occurrence_key] += 1
            key_source = "|".join([
                work_date, kitchen, previous_shift, str(plan_occurrences[occurrence_key]),
            ])
            import_key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()
            existing = conn.execute("SELECT id FROM meal_plans WHERE import_key=?", (import_key,)).fetchone()
            if not existing:
                existing = conn.execute(
                    """SELECT id FROM meal_plans WHERE work_date=? AND kitchen=? AND shift=?
                       AND COALESCE(source_file,'')!='' ORDER BY id DESC LIMIT 1""",
                    (work_date, kitchen, previous_shift),
                ).fetchone()
            dishes = list(dict.fromkeys(item["dish_name"] for item in items if item["dish_name"]))
            plans.append({
                "import_key": import_key,
                "existing_id": existing["id"] if existing else None,
                "status": "update" if existing else "new",
                "sheet": worksheet.title,
                "source_row_start": start_row,
                "source_row_end": end_row,
                "kitchen": kitchen,
                "xcom_code": xcom_code,
                "shift": previous_shift,
                "meal_count": meal_count,
                "menu_count": menu_count,
                "servings_per_menu": servings_per_menu,
                "meal_price": financials["meal_price"],
                "other_cost": financials["other_cost"],
                "source_financials": financials,
                "menu_name": " · ".join(dishes),
                "items": items,
                "errors": list(dict.fromkeys(plan_errors)),
                "warnings": list(dict.fromkeys(plan_warnings)),
            })
    if not plans:
        raise ValueError("Không tìm thấy bảng xưởng cơm có Nhà thầu, Mã hàng, Mã bếp và định lượng")
    xcom_by_kitchen = defaultdict(set)
    for plan in plans:
        xcom_by_kitchen[plan["kitchen"]].add(plan["xcom_code"])
    for kitchen, xcom_codes in xcom_by_kitchen.items():
        if len(xcom_codes) > 1:
            message = f"Bếp {kitchen} có nhiều mã XCOM trong cùng file: {', '.join(sorted(xcom_codes))}"
            for plan in plans:
                if plan["kitchen"] == kitchen:
                    plan["errors"].append(message)
    counts = {
        "plans": len(plans),
        "items": sum(len(plan["items"]) for plan in plans),
        "new": sum(plan["status"] == "new" for plan in plans),
        "update": sum(plan["status"] == "update" for plan in plans),
        "errors": sum(bool(plan["errors"]) for plan in plans),
        "warnings": sum(bool(plan["warnings"]) for plan in plans),
    }
    return {"plans": plans, "counts": counts, "can_confirm": counts["errors"] == 0}


def net_received(order) -> float:
    return max(
        as_number(order["actual_received"])
        - as_number(order.get("damaged_qty") if isinstance(order, dict) else order["damaged_qty"])
        - as_number(order.get("supplier_return_qty") if isinstance(order, dict) else order["supplier_return_qty"]),
        0,
    )


def net_delivered(order) -> float:
    return max(
        as_number(order["actual_delivered"])
        - as_number(order.get("customer_return_qty") if isinstance(order, dict) else order["customer_return_qty"]),
        0,
    )


def inventory_rows(conn, as_of="", include_zero=False):
    params = []
    date_sql = ""
    if as_of:
        date_sql = " AND t.txn_date<=?"
        params.append(as_of)
    query = f"""
        SELECT p.code product_code,p.name product_name,p.unit,
               COALESCE(SUM(CASE WHEN t.status='posted' THEN t.qty_in-t.qty_out ELSE 0 END),0) accounting_qty,
               COALESCE(SUM(CASE WHEN t.status IN ('posted','reserved') THEN t.qty_in-t.qty_out ELSE 0 END),0) available_qty,
               COALESCE(SUM(CASE WHEN t.status='posted' THEN t.qty_in*t.unit_cost ELSE 0 END),0) input_value,
               COALESCE(SUM(CASE WHEN t.status='posted' THEN t.qty_out*t.unit_cost ELSE 0 END),0) output_value
        FROM products p LEFT JOIN inventory_transactions t ON t.product_code=p.code {date_sql}
        GROUP BY p.code,p.name,p.unit
        ORDER BY p.name
    """
    rows = [dict(row) for row in conn.execute(query, params)]
    if not include_zero:
        rows = [row for row in rows if abs(row["accounting_qty"]) > 1e-9 or abs(row["available_qty"]) > 1e-9]
    return rows


def inventory_lookup(conn, as_of=""):
    return {row["product_code"]: row for row in inventory_rows(conn, as_of, include_zero=True)}


def post_purchase_list_inventory(conn, batch_id: int, now_iso):
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        return 0
    rate_row = conn.execute("SELECT value FROM settings WHERE key='purchase_rate'").fetchone()
    purchase_rate = as_number(rate_row["value"] if rate_row else 0.95, 0.95)
    posted = 0
    for row in conn.execute("SELECT * FROM orders WHERE batch_id=? AND purchase_list=1", (batch_id,)):
        item = dict(row)
        qty = net_received(item)
        if qty <= 0 or not item.get("product_code"):
            continue
        conn.execute(
            """INSERT INTO inventory_transactions(
                txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,
                kitchen,status,note,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,'posted',?,?,?)
            ON CONFLICT(source_type,source_id,source_line) DO UPDATE SET
                txn_date=excluded.txn_date,product_code=excluded.product_code,qty_in=excluded.qty_in,
                unit_cost=excluded.unit_cost,kitchen=excluded.kitchen,updated_at=excluded.updated_at""",
            (batch["work_date"], item["product_code"], qty, 0, round(as_number(item["sell_price"]) * purchase_rate), "BK_INPUT",
             str(batch_id), str(item["id"]), item["kitchen"], "Bảng kê mua vào đã duyệt", now_iso(), now_iso()),
        )
        posted += 1
    if posted:
        audit(conn, now_iso, "inventory.post_bk", "ok", entity_type="batch", entity_id=batch_id,
              metadata={"lines": posted})
    return posted


def invoice_details(remote: dict) -> list[dict]:
    details = first_value(remote, "hdhhdvu", "invoiceItems", "details", default=[])
    return details if isinstance(details, list) else []


def normalize_invoice(remote: dict, invoice_type: str, now: str) -> dict:
    remote_id = str(first_value(remote, "_id", "id", "invoiceId", default="")).strip()
    if not remote_id:
        raise MsmiError("Hóa đơn mSMI thiếu khóa _id")
    subtotal = as_number(first_value(remote, "tgtcthue", "subtotal", "totalBeforeTax"))
    tax_amount = as_number(first_value(remote, "tgtthue", "taxAmount", "totalTax"))
    total = as_number(first_value(remote, "tgtttbso", "tgtttbchu", "totalAmount", "total"))
    if total <= 0:
        total = subtotal + tax_amount
    return {
        "remote_id": remote_id,
        "invoice_type": invoice_type,
        "seller_tax_code": str(first_value(remote, "mstNban", "nbmst", "sellerTaxCode", "sellerTaxId")),
        "seller_name": str(first_value(remote, "tenNban", "nbten", "sellerName")),
        "invoice_number": str(first_value(remote, "shdon", "soHoaDon", "invoiceNumber")),
        "invoice_series": str(first_value(remote, "khhdon", "khmshdon", "series", "invoiceSeries")),
        "invoice_date": as_date(first_value(remote, "tdlap", "nlap", "invoiceDate", "signedDate")),
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_amount": total,
        "raw_json": json.dumps(remote, ensure_ascii=False, separators=(",", ":")),
        "synced_at": now,
    }


def normalize_invoice_item(remote_item: dict, line_index: int) -> dict:
    return {
        "line_index": line_index,
        "source_item_code": str(first_value(remote_item, "ma", "mhhhoa", "itemCode", "code")),
        "source_item_name": str(first_value(remote_item, "ten", "tenhh", "itemName", "name")),
        "source_unit": str(first_value(remote_item, "dvtinh", "dvt", "unit")),
        "qty": as_number(first_value(remote_item, "sluong", "quantity", "qty")),
        "unit_price": as_number(first_value(remote_item, "dgia", "unitPrice", "price")),
        "amount": as_number(first_value(remote_item, "thtien", "amount", "total")),
        "tax_rate": str(first_value(remote_item, "tsuat", "taxRate", "tax")),
    }


def saved_mapping(conn, tenant: str, seller_tax_code: str, item: dict):
    return conn.execute(
        """SELECT product_code FROM item_mappings
           WHERE tenant=? AND seller_tax_code=? AND source_item_code=? AND source_item_name=?""",
        (tenant, seller_tax_code, item["source_item_code"], item["source_item_name"]),
    ).fetchone()


def upsert_msmi_invoice(conn, remote: dict, invoice_type: str, tenant: str, now: str) -> tuple[int, bool]:
    data = normalize_invoice(remote, invoice_type, now)
    existing = conn.execute("SELECT id FROM msmi_invoices WHERE remote_id=?", (data["remote_id"],)).fetchone()
    conn.execute(
        """INSERT INTO msmi_invoices(
            remote_id,tenant,invoice_type,seller_tax_code,seller_name,invoice_number,invoice_series,
            invoice_date,subtotal,tax_amount,total_amount,sync_status,receipt_status,raw_json,
            synced_at,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'synced','pending_mapping',?,?,?,?)
        ON CONFLICT(remote_id) DO UPDATE SET
            seller_tax_code=excluded.seller_tax_code,seller_name=excluded.seller_name,
            invoice_number=excluded.invoice_number,invoice_series=excluded.invoice_series,
            invoice_date=excluded.invoice_date,subtotal=excluded.subtotal,tax_amount=excluded.tax_amount,
            total_amount=excluded.total_amount,raw_json=excluded.raw_json,synced_at=excluded.synced_at,
            sync_status='synced',error_message=NULL,updated_at=excluded.updated_at""",
        (data["remote_id"], tenant, data["invoice_type"], data["seller_tax_code"], data["seller_name"],
         data["invoice_number"], data["invoice_series"], data["invoice_date"], data["subtotal"],
         data["tax_amount"], data["total_amount"], data["raw_json"], now, now, now),
    )
    invoice_id = conn.execute("SELECT id FROM msmi_invoices WHERE remote_id=?", (data["remote_id"],)).fetchone()["id"]
    mapped = 0
    detail_rows = invoice_details(remote)
    for index, raw_item in enumerate(detail_rows, start=1):
        item = normalize_invoice_item(raw_item if isinstance(raw_item, dict) else {}, index)
        mapping = saved_mapping(conn, tenant, data["seller_tax_code"], item)
        product_code = mapping["product_code"] if mapping else ""
        conn.execute(
            """INSERT INTO msmi_invoice_items(
                invoice_id,line_index,source_item_code,source_item_name,source_unit,qty,unit_price,
                amount,tax_rate,product_code,mapping_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(invoice_id,line_index) DO UPDATE SET
                source_item_code=excluded.source_item_code,source_item_name=excluded.source_item_name,
                source_unit=excluded.source_unit,qty=excluded.qty,unit_price=excluded.unit_price,
                amount=excluded.amount,tax_rate=excluded.tax_rate,
                product_code=CASE WHEN msmi_invoice_items.product_code!='' THEN msmi_invoice_items.product_code ELSE excluded.product_code END,
                mapping_status=CASE WHEN msmi_invoice_items.product_code!='' OR excluded.product_code!='' THEN 'mapped' ELSE 'unmapped' END""",
            (invoice_id, index, item["source_item_code"], item["source_item_name"], item["source_unit"],
             item["qty"], item["unit_price"], item["amount"], item["tax_rate"], product_code,
             "mapped" if product_code else "unmapped"),
        )
        mapped += bool(product_code)
    receipt_status = "ready" if detail_rows and mapped == len(detail_rows) else "pending_mapping"
    current = conn.execute("SELECT receipt_status FROM msmi_invoices WHERE id=?", (invoice_id,)).fetchone()
    if current and current["receipt_status"] != "posted":
        conn.execute("UPDATE msmi_invoices SET receipt_status=? WHERE id=?", (receipt_status, invoice_id))
    return invoice_id, existing is None


def sync_msmi(conn, client, now_iso, tenant="default", max_pages=5, page_size=199):
    invoice_type = "INPUT_ELECTRONIC_INVOICE"
    new_count = 0
    seen_count = 0
    item_count = 0
    pages = 0
    newest_id = ""
    newest_date = ""
    try:
        for page in range(max(1, min(int(max_pages), 50))):
            result = client.list_invoices(invoice_type=invoice_type, page=page, size=page_size)
            pages += 1
            remote_items = result["items"]
            if not remote_items:
                break
            page_all_seen = True
            for remote in remote_items:
                if not isinstance(remote, dict):
                    continue
                invoice_id, created = upsert_msmi_invoice(conn, remote, invoice_type, tenant, now_iso())
                if created:
                    new_count += 1
                    page_all_seen = False
                else:
                    seen_count += 1
                item_count += conn.execute(
                    "SELECT COUNT(*) n FROM msmi_invoice_items WHERE invoice_id=?", (invoice_id,)
                ).fetchone()["n"]
                normalized = normalize_invoice(remote, invoice_type, now_iso())
                if not newest_id:
                    newest_id = normalized["remote_id"]
                    newest_date = normalized["invoice_date"]
            # mSMI returns newest records first. Once a complete page is already
            # known, older pages have already been synchronized.
            if page_all_seen or not result["has_more"]:
                break
        conn.execute(
            """INSERT INTO msmi_sync_state(invoice_type,last_remote_id,last_invoice_date,last_synced_at,last_status,last_error)
               VALUES(?,?,?,?,?,'') ON CONFLICT(invoice_type) DO UPDATE SET
               last_remote_id=excluded.last_remote_id,last_invoice_date=excluded.last_invoice_date,
               last_synced_at=excluded.last_synced_at,last_status='ok',last_error=''""",
            (invoice_type, newest_id, newest_date, now_iso(), "ok"),
        )
        audit(conn, now_iso, "msmi.sync", "ok", metadata={
            "new_invoices": new_count, "known_invoices": seen_count,
            "invoice_items": item_count, "pages": pages,
        })
        return {"new_invoices": new_count, "known_invoices": seen_count, "items": item_count, "pages": pages}
    except Exception as error:
        message = str(error)[:300]
        conn.execute(
            """INSERT INTO msmi_sync_state(invoice_type,last_synced_at,last_status,last_error)
               VALUES(?,?,'error',?) ON CONFLICT(invoice_type) DO UPDATE SET
               last_synced_at=excluded.last_synced_at,last_status='error',last_error=excluded.last_error""",
            (invoice_type, now_iso(), message),
        )
        audit(conn, now_iso, "msmi.sync", "error", message=message)
        raise


def payroll_rows(conn, month: str):
    start = month + "-01"
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Tháng tính lương phải có dạng YYYY-MM") from None
    if start_date.month == 12:
        end_date = date(start_date.year + 1, 1, 1)
    else:
        end_date = date(start_date.year, start_date.month + 1, 1)
    output = []
    for staff_row in conn.execute("SELECT * FROM staff WHERE active=1 ORDER BY full_name"):
        person = dict(staff_row)
        hours = conn.execute(
            """SELECT COALESCE(SUM(normal_hours),0) normal,COALESCE(SUM(overtime_hours),0) overtime,
                      COALESCE(SUM(sunday_hours),0) sunday,COALESCE(SUM(night_hours),0) night,
                      COALESCE(SUM(holiday_hours),0) holiday
               FROM attendance_entries WHERE employee_id=? AND work_date>=? AND work_date<?""",
            (person["id"], start_date.isoformat(), end_date.isoformat()),
        ).fetchone()
        adjustment = conn.execute(
            "SELECT * FROM payroll_adjustments WHERE employee_id=? AND month=?",
            (person["id"], month),
        ).fetchone()
        adj = dict(adjustment) if adjustment else defaultdict(float)
        hourly = person["base_salary"] / max(person["standard_days"] * person["standard_hours"], 1)
        normal_pay = hourly * hours["normal"]
        overtime_pay = hourly * hours["overtime"] * 1.5
        sunday_pay = hourly * hours["sunday"] * 2
        night_pay = hourly * hours["night"] * 1.3
        holiday_pay = hourly * hours["holiday"] * 3
        gross = (normal_pay + overtime_pay + sunday_pay + night_pay + holiday_pay
                 + as_number(adj["allowance"]) + as_number(adj["responsibility"]))
        employee_bhxh = as_number(adj["bhxh_employee_amount"])
        if employee_bhxh <= 0:
            employee_bhxh = person["base_salary"] * person["bhxh_employee_rate"]
        company_bhxh = as_number(adj["bhxh_company_amount"])
        if company_bhxh <= 0:
            company_bhxh = person["base_salary"] * person["bhxh_company_rate"]
        net = gross - as_number(adj["advance"]) - as_number(adj["probation_deduction"]) - employee_bhxh
        if int(as_number(adj["use_override"])):
            gross = as_number(adj["gross_override"])
            net = as_number(adj["net_override"])
        output.append({
            **person, "month": month, "normal_hours": hours["normal"], "overtime_hours": hours["overtime"],
            "sunday_hours": hours["sunday"], "night_hours": hours["night"], "holiday_hours": hours["holiday"],
            "normal_pay": normal_pay, "overtime_pay": overtime_pay, "sunday_pay": sunday_pay,
            "night_pay": night_pay, "holiday_pay": holiday_pay, "allowance": as_number(adj["allowance"]),
            "responsibility": as_number(adj["responsibility"]), "advance": as_number(adj["advance"]),
            "probation_deduction": as_number(adj["probation_deduction"]), "bhxh_employee": employee_bhxh,
            "bhxh_company": company_bhxh, "gross_salary": gross, "net_salary": net,
        })
    return output


VIET_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def number_to_vietnamese(value: float) -> str:
    number = int(round(value))
    if number == 0:
        return "Không đồng"

    def three_digits(group: int, full=False) -> str:
        hundred, remainder = divmod(group, 100)
        ten, unit = divmod(remainder, 10)
        words = []
        if hundred or full:
            words += [VIET_DIGITS[hundred], "trăm"]
        if ten > 1:
            words += [VIET_DIGITS[ten], "mươi"]
            if unit == 1:
                words.append("mốt")
            elif unit == 5:
                words.append("lăm")
            elif unit:
                words.append(VIET_DIGITS[unit])
        elif ten == 1:
            words.append("mười")
            if unit == 5:
                words.append("lăm")
            elif unit:
                words.append(VIET_DIGITS[unit])
        elif unit:
            if hundred or full:
                words.append("lẻ")
            words.append(VIET_DIGITS[unit])
        return " ".join(words)

    groups = []
    while number:
        groups.append(number % 1000)
        number //= 1000
    units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    words = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if group:
            words.append(three_digits(group, full=bool(words) and group < 100))
            if index < len(units) and units[index]:
                words.append(units[index])
    text = " ".join(words).strip()
    return text[:1].upper() + text[1:] + " đồng"


def register_contract_routes(app, ctx):
    db_factory = ctx["db"]
    now_iso = ctx["now_iso"]
    clean_text = ctx["clean_text"]
    number_value = ctx["number_value"]
    tax_factor = ctx["tax_factor"]
    setting_get = ctx["setting_get"]
    setting_set = ctx["setting_set"]
    root = ctx["root"]
    data_dir = ctx["data_dir"]

    def create_msmi_client():
        return MsmiClient(MsmiConfig.from_env_files([root / ".env", data_dir.parent / ".env"]))

    def invoice_payload(conn, limit=100, invoice_id=None):
        params = []
        where = ""
        if invoice_id:
            where = " WHERE i.id=?"
            params.append(invoice_id)
        query = f"""SELECT i.id,i.remote_id,i.invoice_type,i.seller_tax_code,i.seller_name,
                           i.invoice_number,i.invoice_series,i.invoice_date,i.subtotal,i.tax_amount,
                           i.total_amount,i.sync_status,i.receipt_status,i.error_message,i.synced_at,
                           COUNT(li.id) item_count,
                           SUM(CASE WHEN li.mapping_status='mapped' THEN 1 ELSE 0 END) mapped_count
                    FROM msmi_invoices i LEFT JOIN msmi_invoice_items li ON li.invoice_id=i.id
                    {where} GROUP BY i.id ORDER BY i.invoice_date DESC,i.id DESC LIMIT ?"""
        params.append(max(1, min(int(limit), 500)))
        invoices = [dict(row) for row in conn.execute(query, params)]
        for item in invoices:
            item["mapped_count"] = item["mapped_count"] or 0
            item["items"] = [dict(row) for row in conn.execute(
                """SELECT li.id,li.line_index,li.source_item_code,li.source_item_name,li.source_unit,
                          li.qty,li.unit_price,li.amount,li.tax_rate,li.product_code,li.mapping_status,
                          p.name product_name,p.unit product_unit
                   FROM msmi_invoice_items li LEFT JOIN products p ON p.code=li.product_code
                   WHERE li.invoice_id=? ORDER BY li.line_index""",
                (item["id"],),
            )]
        return invoices

    @app.post("/api/catalog/import/preview")
    def api_catalog_import_preview():
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "Chưa chọn file danh mục Excel"}), 400
        filename = Path(upload.filename).name
        if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
            return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
        payload = upload.read(MAPPING_IMPORT_MAX_BYTES + 1)
        if len(payload) > MAPPING_IMPORT_MAX_BYTES:
            return jsonify({"ok": False, "error": "File Excel vượt quá giới hạn 10 MB"}), 413
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries = archive.infolist()
                expanded_size = sum(item.file_size for item in entries)
                if len(entries) > 2_000 or expanded_size > MAPPING_IMPORT_MAX_UNCOMPRESSED_BYTES:
                    return jsonify({"ok": False, "error": "File Excel có cấu trúc quá lớn để đọc an toàn"}), 413
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "error": "File Excel bị hỏng hoặc không đúng định dạng"}), 400

        cutoff = time.time() - MAPPING_IMPORT_TTL_SECONDS
        with CATALOG_IMPORT_LOCK:
            for old_token, item in list(PENDING_CATALOG_IMPORTS.items()):
                if item["created"] < cutoff:
                    PENDING_CATALOG_IMPORTS.pop(old_token, None)
        workbook = None
        try:
            workbook = load_workbook(
                io.BytesIO(payload), read_only=True, data_only=True, keep_links=False,
            )
            with db_factory() as conn:
                preview = parse_catalog_workbook(conn, workbook)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Không đọc được file danh mục Excel"}), 400
        finally:
            if workbook is not None:
                workbook.close()

        token = uuid.uuid4().hex
        source_hash = hashlib.sha256(payload).hexdigest().upper()
        pending = {
            "created": time.time(),
            "filename": filename,
            "source_hash": source_hash,
            "sheet": preview["sheet"],
            "header_row": preview["header_row"],
            "items": preview.pop("items"),
            "counts": preview["counts"],
            "retained_codes": preview["retained_codes"],
            "database_state_hash": preview.pop("database_state_hash"),
            "has_errors": not preview["can_confirm"],
        }
        with CATALOG_IMPORT_LOCK:
            PENDING_CATALOG_IMPORTS[token] = pending
        return jsonify({
            "ok": True,
            "token": token,
            "filename": filename,
            "source_hash": source_hash,
            "expires_in_minutes": MAPPING_IMPORT_TTL_SECONDS // 60,
            **preview,
        })

    @app.post("/api/catalog/import/confirm")
    def api_catalog_import_confirm():
        body = request.get_json(force=True) or {}
        if body.get("confirmed") is not True:
            return jsonify({"ok": False, "error": "Cần xác nhận trước khi ghi danh mục"}), 400
        token = clean_text(body.get("token"))
        with CATALOG_IMPORT_LOCK:
            pending = PENDING_CATALOG_IMPORTS.pop(token, None)
        if not pending or time.time() - pending["created"] > MAPPING_IMPORT_TTL_SECONDS:
            return jsonify({"ok": False, "error": "Phiên xem trước đã hết hạn; vui lòng chọn lại file"}), 410
        if pending["has_errors"]:
            return jsonify({"ok": False, "error": "File còn dòng lỗi nên chưa thể nhập"}), 400

        inserted_products = updated_products = unchanged_products = 0
        inserted_names = updated_names = unchanged_names = 0
        try:
            with db_factory() as conn:
                if catalog_database_state_hash(conn) != pending["database_state_hash"]:
                    raise ValueError(
                        "Danh mục đã thay đổi sau khi xem trước; dữ liệu chưa được ghi, vui lòng chọn lại file"
                    )
                timestamp = now_iso()
                for item in pending["items"]:
                    code = item["product_code"]
                    current_product = conn.execute(
                        "SELECT code FROM products WHERE code=?", (code,),
                    ).fetchone()
                    if current_product:
                        if item["product_status"] == "update":
                            updated_products += 1
                        else:
                            unchanged_products += 1
                    else:
                        inserted_products += 1
                    conn.execute(
                        """INSERT INTO products(
                               code,name,unit,tax,supplier,buy_price,purchase_list,
                               product_group,catalog_updated_at
                           ) VALUES(?,?,?,?, '',0,0,?,?)
                           ON CONFLICT(code) DO UPDATE SET
                               name=excluded.name,
                               unit=excluded.unit,
                               tax=excluded.tax,
                               product_group=excluded.product_group,
                               catalog_updated_at=excluded.catalog_updated_at""",
                        (
                            code, item["product_name"], item["unit"], item["tax"],
                            item["product_group"], timestamp,
                        ),
                    )

                    invoice_name = item["invoice_name"]
                    if invoice_name:
                        current_name = conn.execute(
                            "SELECT invoice_name FROM outgoing_product_names WHERE product_code=?",
                            (code,),
                        ).fetchone()
                        if not current_name:
                            inserted_names += 1
                        elif mapping_key(current_name["invoice_name"]) == mapping_key(invoice_name):
                            unchanged_names += 1
                        else:
                            updated_names += 1
                        conn.execute(
                            """INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at)
                               VALUES(?,?,?) ON CONFLICT(product_code) DO UPDATE SET
                               invoice_name=excluded.invoice_name,updated_at=excluded.updated_at""",
                            (code, invoice_name, timestamp),
                        )
                result_counts = {
                    "inserted_products": inserted_products,
                    "updated_products": updated_products,
                    "unchanged_products": unchanged_products,
                    "retained_products": len(pending["retained_codes"]),
                    "inserted_names": inserted_names,
                    "updated_names": updated_names,
                    "unchanged_names": unchanged_names,
                    "processed": len(pending["items"]),
                }
                audit(
                    conn, now_iso, "catalog.bulk_import", "ok",
                    entity_type="catalog", entity_id=pending["source_hash"][:16],
                    metadata={
                        "filename": pending["filename"], "sheet": pending["sheet"],
                        "header_row": pending["header_row"], "source_hash": pending["source_hash"],
                        **result_counts,
                    },
                )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        return jsonify({"ok": True, "source_hash": pending["source_hash"], **result_counts})

    @app.post("/api/mappings/import/preview")
    def api_mapping_import_preview():
        mapping_type = clean_text(request.form.get("mapping_type"))
        if mapping_type not in MAPPING_ALIASES:
            return jsonify({"ok": False, "error": "Loại dữ liệu mapping không hợp lệ"}), 400
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "Chưa chọn file Excel"}), 400
        filename = Path(upload.filename).name
        if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
            return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
        payload = upload.read(MAPPING_IMPORT_MAX_BYTES + 1)
        if len(payload) > MAPPING_IMPORT_MAX_BYTES:
            return jsonify({"ok": False, "error": "File Excel vượt quá giới hạn 10 MB"}), 413
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries = archive.infolist()
                expanded_size = sum(item.file_size for item in entries)
                if len(entries) > 2_000 or expanded_size > MAPPING_IMPORT_MAX_UNCOMPRESSED_BYTES:
                    return jsonify({"ok": False, "error": "File Excel có cấu trúc quá lớn để đọc an toàn"}), 413
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "error": "File Excel bị hỏng hoặc không đúng định dạng"}), 400

        cutoff = time.time() - MAPPING_IMPORT_TTL_SECONDS
        with MAPPING_IMPORT_LOCK:
            for old_token, item in list(PENDING_MAPPING_IMPORTS.items()):
                if item["created"] < cutoff:
                    PENDING_MAPPING_IMPORTS.pop(old_token, None)
        workbook = None
        try:
            workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True, keep_links=False)
            with db_factory() as conn:
                preview = parse_mapping_workbook(conn, workbook, mapping_type)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Không đọc được file Excel; vui lòng kiểm tra lại file"}), 400
        finally:
            if workbook is not None:
                workbook.close()

        token = uuid.uuid4().hex
        pending = {
            "created": time.time(),
            "mapping_type": mapping_type,
            "filename": filename,
            "sheet": preview["sheet"],
            "header_row": preview["header_row"],
            "items": preview.pop("items"),
            "counts": preview["counts"],
            "has_errors": not preview["can_confirm"],
        }
        with MAPPING_IMPORT_LOCK:
            PENDING_MAPPING_IMPORTS[token] = pending
        return jsonify({
            "ok": True,
            "token": token,
            "mapping_type": mapping_type,
            "filename": filename,
            "expires_in_minutes": MAPPING_IMPORT_TTL_SECONDS // 60,
            **preview,
        })

    @app.post("/api/mappings/import/confirm")
    def api_mapping_import_confirm():
        body = request.get_json(force=True) or {}
        if body.get("confirmed") is not True:
            return jsonify({"ok": False, "error": "Cần xác nhận trước khi ghi dữ liệu"}), 400
        token = clean_text(body.get("token"))
        with MAPPING_IMPORT_LOCK:
            pending = PENDING_MAPPING_IMPORTS.pop(token, None)
        if not pending or time.time() - pending["created"] > MAPPING_IMPORT_TTL_SECONDS:
            return jsonify({"ok": False, "error": "Phiên xem trước đã hết hạn; vui lòng chọn lại file"}), 410
        if pending["has_errors"]:
            return jsonify({"ok": False, "error": "File còn dòng lỗi nên chưa thể nhập"}), 400

        mapping_type = pending["mapping_type"]
        is_invoice = mapping_type == "invoice_names"
        catalog_table = "products" if is_invoice else "kitchens"
        mapping_table = "outgoing_product_names" if is_invoice else "kitchen_units"
        mapping_key_column = "product_code" if is_invoice else "kitchen_code"
        mapping_value_column = "invoice_name" if is_invoice else "unit_code"
        inserted = updated = unchanged = 0
        try:
            with db_factory() as conn:
                for item in pending["items"]:
                    code = item["code"]
                    target_value = item["target_value"]
                    if not conn.execute(f"SELECT 1 FROM {catalog_table} WHERE code=?", (code,)).fetchone():
                        raise ValueError(f"Mã {code} không còn trong danh mục; dữ liệu chưa được ghi")
                    current = conn.execute(
                        f"SELECT {mapping_value_column} value FROM {mapping_table} WHERE {mapping_key_column}=?",
                        (code,),
                    ).fetchone()
                    if current and mapping_key(current["value"]) == mapping_key(target_value):
                        unchanged += 1
                        continue
                    if current:
                        updated += 1
                    else:
                        inserted += 1
                    conn.execute(
                        f"""INSERT INTO {mapping_table}({mapping_key_column},{mapping_value_column},updated_at)
                            VALUES(?,?,?) ON CONFLICT({mapping_key_column}) DO UPDATE SET
                            {mapping_value_column}=excluded.{mapping_value_column},updated_at=excluded.updated_at""",
                        (code, target_value, now_iso()),
                    )
                result_counts = {
                    "inserted": inserted,
                    "updated": updated,
                    "unchanged": unchanged,
                    "processed": len(pending["items"]),
                }
                audit(
                    conn,
                    now_iso,
                    "mapping.bulk_import",
                    "ok",
                    entity_type="mapping",
                    entity_id=mapping_type,
                    metadata={
                        "filename": pending["filename"],
                        "sheet": pending["sheet"],
                        "header_row": pending["header_row"],
                        **result_counts,
                    },
                )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        return jsonify({"ok": True, "mapping_type": mapping_type, **result_counts})

    @app.post("/api/kitchen/import/preview")
    def api_kitchen_import_preview():
        work_date = clean_text(request.form.get("work_date"))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", work_date):
            return jsonify({"ok": False, "error": "Ngày xưởng cơm phải có dạng YYYY-MM-DD"}), 400
        try:
            datetime.strptime(work_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"ok": False, "error": "Ngày xưởng cơm không hợp lệ"}), 400
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "Chưa chọn file xưởng cơm"}), 400
        filename = Path(upload.filename).name
        if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
            return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
        payload = upload.read(MAPPING_IMPORT_MAX_BYTES + 1)
        if len(payload) > MAPPING_IMPORT_MAX_BYTES:
            return jsonify({"ok": False, "error": "File Excel vượt quá giới hạn 10 MB"}), 413
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries = archive.infolist()
                expanded_size = sum(item.file_size for item in entries)
                if len(entries) > 2_000 or expanded_size > MAPPING_IMPORT_MAX_UNCOMPRESSED_BYTES:
                    return jsonify({"ok": False, "error": "File Excel có cấu trúc quá lớn để đọc an toàn"}), 413
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "error": "File Excel bị hỏng hoặc không đúng định dạng"}), 400

        cutoff = time.time() - MAPPING_IMPORT_TTL_SECONDS
        with KITCHEN_IMPORT_LOCK:
            for old_token, item in list(PENDING_KITCHEN_IMPORTS.items()):
                if item["created"] < cutoff:
                    PENDING_KITCHEN_IMPORTS.pop(old_token, None)
        workbook = None
        try:
            workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True, keep_links=False)
            with db_factory() as conn:
                preview = parse_kitchen_workbook(conn, workbook, work_date)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Không đọc được file xưởng cơm; vui lòng kiểm tra lại file"}), 400
        finally:
            if workbook is not None:
                workbook.close()

        token = uuid.uuid4().hex
        with KITCHEN_IMPORT_LOCK:
            PENDING_KITCHEN_IMPORTS[token] = {
                "created": time.time(),
                "filename": filename,
                "work_date": work_date,
                "plans": preview["plans"],
                "counts": preview["counts"],
                "has_errors": not preview["can_confirm"],
            }
        return jsonify({
            "ok": True,
            "token": token,
            "filename": filename,
            "work_date": work_date,
            "expires_in_minutes": MAPPING_IMPORT_TTL_SECONDS // 60,
            **preview,
        })

    @app.post("/api/kitchen/import/confirm")
    def api_kitchen_import_confirm():
        body = request.get_json(force=True) or {}
        if body.get("confirmed") is not True:
            return jsonify({"ok": False, "error": "Cần xác nhận trước khi ghi dữ liệu"}), 400
        token = clean_text(body.get("token"))
        with KITCHEN_IMPORT_LOCK:
            pending = PENDING_KITCHEN_IMPORTS.pop(token, None)
        if not pending or time.time() - pending["created"] > MAPPING_IMPORT_TTL_SECONDS:
            return jsonify({"ok": False, "error": "Phiên xem trước đã hết hạn; vui lòng chọn lại file"}), 410
        if pending["has_errors"]:
            return jsonify({"ok": False, "error": "File còn nhóm lỗi nên chưa thể nhập"}), 400

        inserted = updated = saved_items = saved_mappings = 0
        try:
            with db_factory() as conn:
                for plan in pending["plans"]:
                    conn.execute(
                        "INSERT INTO kitchens(code,name) VALUES(?,?) ON CONFLICT(code) DO NOTHING",
                        (plan["kitchen"], plan["kitchen"]),
                    )
                    conn.execute(
                        """INSERT INTO kitchen_units(kitchen_code,unit_code,updated_at) VALUES(?,?,?)
                           ON CONFLICT(kitchen_code) DO UPDATE SET
                           unit_code=excluded.unit_code,updated_at=excluded.updated_at""",
                        (plan["kitchen"], plan["xcom_code"], now_iso()),
                    )
                    saved_mappings += 1
                    existing = conn.execute(
                        "SELECT id FROM meal_plans WHERE import_key=?", (plan["import_key"],)
                    ).fetchone()
                    if not existing and plan.get("existing_id"):
                        existing = conn.execute(
                            "SELECT id FROM meal_plans WHERE id=?", (plan["existing_id"],)
                        ).fetchone()
                    if existing:
                        plan_id = existing["id"]
                        conn.execute(
                            """UPDATE meal_plans SET work_date=?,kitchen=?,shift=?,meal_count=?,unit_code=?,
                               status='draft',note=?,source_file=?,source_sheet=?,source_row_start=?,
                               source_row_end=?,menu_count=?,servings_per_menu=?,meal_price=?,other_cost=?,
                               source_financials_json=?,import_key=?,updated_at=? WHERE id=?""",
                            (pending["work_date"], plan["kitchen"], plan["shift"], plan["meal_count"],
                             plan["xcom_code"], plan["menu_name"], pending["filename"], plan["sheet"],
                             plan["source_row_start"], plan["source_row_end"], plan["menu_count"],
                             plan["servings_per_menu"], plan["meal_price"], plan["other_cost"],
                             json.dumps(plan["source_financials"], ensure_ascii=False), plan["import_key"],
                             now_iso(), plan_id),
                        )
                        conn.execute("DELETE FROM meal_plan_items WHERE plan_id=?", (plan_id,))
                        updated += 1
                    else:
                        cur = conn.execute(
                            """INSERT INTO meal_plans(
                               work_date,kitchen,shift,meal_count,unit_code,status,note,created_at,updated_at,
                               import_key,source_file,source_sheet,source_row_start,source_row_end,menu_count,
                               servings_per_menu,meal_price,other_cost,source_financials_json
                               ) VALUES(?,?,?,?,?,'draft',?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (pending["work_date"], plan["kitchen"], plan["shift"], plan["meal_count"],
                             plan["xcom_code"], plan["menu_name"], now_iso(), now_iso(), plan["import_key"],
                             pending["filename"], plan["sheet"], plan["source_row_start"], plan["source_row_end"],
                             plan["menu_count"], plan["servings_per_menu"], plan["meal_price"], plan["other_cost"],
                             json.dumps(plan["source_financials"], ensure_ascii=False)),
                        )
                        plan_id = cur.lastrowid
                        inserted += 1
                    for item in plan["items"]:
                        if not conn.execute(
                            "SELECT 1 FROM products WHERE code=?", (item["product_code"],)
                        ).fetchone():
                            raise ValueError(
                                f"Mã {item['product_code']} không còn trong danh mục; dữ liệu chưa được ghi"
                            )
                        conn.execute(
                            """INSERT INTO meal_plan_items(
                               plan_id,dish_name,product_code,product_name,norm_qty,unit,supplier,buy_price,
                               price_source,source_norm_per_1000,applicable_meal_count,source_row,source_amount
                               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (plan_id, item["dish_name"], item["product_code"], item["product_name"],
                             item["norm_qty"], item["unit"], item["supplier"], item["buy_price"],
                             item["price_source"], item["norm_per_1000"], item["applicable_meal_count"],
                             item["source_row"], item["source_amount"]),
                        )
                        saved_items += 1
                result_counts = {
                    "inserted": inserted,
                    "updated": updated,
                    "items": saved_items,
                    "mappings": saved_mappings,
                }
                audit(
                    conn,
                    now_iso,
                    "kitchen.bulk_import",
                    "ok",
                    entity_type="meal_plan",
                    entity_id=pending["work_date"],
                    metadata={"filename": pending["filename"], **result_counts},
                )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        except Exception:
            return jsonify({"ok": False, "error": "Không ghi được file xưởng cơm; dữ liệu chưa được thay đổi"}), 409
        return jsonify({"ok": True, "work_date": pending["work_date"], **result_counts})

    @app.get("/api/mappings/<mapping_type>")
    def api_mapping_list(mapping_type):
        with db_factory() as conn:
            if mapping_type == "invoice_names":
                rows = [dict(row) for row in conn.execute(
                    """SELECT m.product_code code,p.name source_name,m.invoice_name target_value,m.updated_at
                       FROM outgoing_product_names m JOIN products p ON p.code=m.product_code
                       ORDER BY m.product_code"""
                )]
            elif mapping_type == "kitchen_units":
                rows = [dict(row) for row in conn.execute(
                    """SELECT m.kitchen_code code,k.name source_name,m.unit_code target_value,m.updated_at
                       FROM kitchen_units m LEFT JOIN kitchens k ON k.code=m.kitchen_code
                       ORDER BY m.kitchen_code"""
                )]
            else:
                return jsonify({"ok": False, "error": "Loại dữ liệu mapping không hợp lệ"}), 404
            return jsonify({"ok": True, "mapping_type": mapping_type, "items": rows})

    @app.get("/api/operations/bootstrap")
    def api_operations_bootstrap():
        as_of = request.args.get("as_of") or date.today().isoformat()
        month = request.args.get("month") or as_of[:7]
        with db_factory() as conn:
            sync_state = [dict(row) for row in conn.execute("SELECT * FROM msmi_sync_state")]
            inventory = inventory_rows(conn, as_of)
            labor = [dict(row) for row in conn.execute(
                "SELECT work_date,kitchen,amount,source FROM kitchen_labor_costs WHERE substr(work_date,1,7)=? ORDER BY work_date,kitchen",
                (month,),
            )]
            meal_attendance = [dict(row) for row in conn.execute(
                """SELECT work_date,kitchen,shift,actual_count,ordered_count,source_file,source_sheet
                   FROM meal_attendance WHERE substr(work_date,1,7)=?
                   ORDER BY work_date,kitchen,shift""",
                (month,),
            )]
            return jsonify({
                "ok": True,
                "inventory": inventory,
                "inventory_as_of": as_of,
                "inventory_totals": {
                    "products": len(inventory),
                    "accounting_qty": sum(row["accounting_qty"] for row in inventory),
                    "available_qty": sum(row["available_qty"] for row in inventory),
                },
                "msmi": {"state": sync_state, "invoices": invoice_payload(conn, 30)},
                "meal_plans": meal_plan_payload(conn, request.args.get("date", "")),
                "meal_attendance": meal_attendance,
                "meal_attendance_totals": {
                    "actual": sum(row["actual_count"] for row in meal_attendance),
                    "ordered": sum(row["ordered_count"] for row in meal_attendance),
                    "rows": len(meal_attendance),
                    "kitchens": len({row["kitchen"] for row in meal_attendance}),
                },
                "kitchen_units": [dict(row) for row in conn.execute("SELECT * FROM kitchen_units ORDER BY kitchen_code")],
                "payroll": payroll_rows(conn, month),
                "labor_costs": labor,
                "staff": [dict(row) for row in conn.execute("SELECT * FROM staff ORDER BY full_name")],
                "print_jobs": [dict(row) for row in conn.execute("SELECT * FROM print_jobs ORDER BY id DESC LIMIT 50")],
                "printer": {
                    "name": setting_get(conn, "printer_name", ""),
                    "copies": int(as_number(setting_get(conn, "print_copies", "1"), 1)),
                    "paper": setting_get(conn, "print_paper", "A4"),
                },
                "document_settings": {
                    "requester": setting_get(conn, "payment_requester", ""),
                    "bank_name": setting_get(conn, "payment_bank_name", ""),
                    "bank_account": setting_get(conn, "payment_bank_account", ""),
                },
            })

    @app.get("/api/inventory")
    def api_inventory():
        with db_factory() as conn:
            as_of = request.args.get("as_of") or date.today().isoformat()
            return jsonify({"ok": True, "as_of": as_of, "items": inventory_rows(conn, as_of)})

    @app.post("/api/inventory/opening/import/preview")
    def api_inventory_opening_import_preview():
        period = clean_text(request.form.get("period"))
        if not re.fullmatch(r"\d{4}-\d{2}", period):
            return jsonify({"ok": False, "error": "Kỳ tồn đầu phải có dạng YYYY-MM"}), 400
        try:
            datetime.strptime(period + "-01", "%Y-%m-%d")
        except ValueError:
            return jsonify({"ok": False, "error": "Kỳ tồn đầu không hợp lệ"}), 400
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "Chưa chọn file tồn đầu kỳ"}), 400
        filename = Path(upload.filename).name
        if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
            return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
        payload = upload.read(MAPPING_IMPORT_MAX_BYTES + 1)
        if len(payload) > MAPPING_IMPORT_MAX_BYTES:
            return jsonify({"ok": False, "error": "File Excel vượt quá giới hạn 10 MB"}), 413
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries = archive.infolist()
                expanded_size = sum(item.file_size for item in entries)
                if len(entries) > 2_000 or expanded_size > MAPPING_IMPORT_MAX_UNCOMPRESSED_BYTES:
                    return jsonify({"ok": False, "error": "File Excel có cấu trúc quá lớn để đọc an toàn"}), 413
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "error": "File Excel bị hỏng hoặc không đúng định dạng"}), 400

        cutoff = time.time() - MAPPING_IMPORT_TTL_SECONDS
        with OPENING_IMPORT_LOCK:
            for old_token, item in list(PENDING_OPENING_IMPORTS.items()):
                if item["created"] < cutoff:
                    PENDING_OPENING_IMPORTS.pop(old_token, None)
        workbook = None
        try:
            workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True, keep_links=False)
            with db_factory() as conn:
                preview = parse_opening_workbook(conn, workbook, period)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Không đọc được file tồn đầu kỳ; vui lòng kiểm tra lại file"}), 400
        finally:
            if workbook is not None:
                workbook.close()

        token = uuid.uuid4().hex
        pending_items = preview.pop("items")
        with OPENING_IMPORT_LOCK:
            PENDING_OPENING_IMPORTS[token] = {
                "created": time.time(),
                "filename": filename,
                "source_hash": hashlib.sha256(payload).hexdigest().upper(),
                "period": period,
                "sheet": preview["sheet"],
                "header_row": preview["header_row"],
                "items": pending_items,
                "counts": preview["counts"],
                "totals": preview["totals"],
                "has_errors": not preview["can_confirm"],
            }
        return jsonify({
            "ok": True,
            "token": token,
            "filename": filename,
            "expires_in_minutes": MAPPING_IMPORT_TTL_SECONDS // 60,
            **preview,
        })

    @app.post("/api/inventory/opening/import/confirm")
    def api_inventory_opening_import_confirm():
        body = request.get_json(force=True) or {}
        if body.get("confirmed") is not True:
            return jsonify({"ok": False, "error": "Cần xác nhận trước khi ghi tồn đầu kỳ"}), 400
        token = clean_text(body.get("token"))
        with OPENING_IMPORT_LOCK:
            pending = PENDING_OPENING_IMPORTS.pop(token, None)
        if not pending or time.time() - pending["created"] > MAPPING_IMPORT_TTL_SECONDS:
            return jsonify({"ok": False, "error": "Phiên xem trước đã hết hạn; vui lòng chọn lại file"}), 410
        if pending["has_errors"]:
            return jsonify({"ok": False, "error": "File còn dòng lỗi nên chưa thể nhập"}), 400

        inserted_products = inserted = updated = 0
        try:
            with db_factory() as conn:
                for item in pending["items"]:
                    code = item["product_code"]
                    product = conn.execute("SELECT code FROM products WHERE code=?", (code,)).fetchone()
                    if not product and not item["create_product"]:
                        raise ValueError(f"Mã {code} không còn trong danh mục; dữ liệu chưa được ghi")
                    if not product:
                        conn.execute(
                            """INSERT INTO products(
                               code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd
                               ) VALUES(?,?,?,?,?, ?,0,'','')""",
                            (code, item["product_name"], item["unit"], item["tax"], "",
                             max(number_value(item["unit_cost"]), 0)),
                        )
                        inserted_products += 1
                    existing = conn.execute(
                        """SELECT id FROM inventory_transactions
                           WHERE source_type='OPENING' AND source_id=? AND source_line=?""",
                        (pending["period"], code),
                    ).fetchone()
                    if existing:
                        updated += 1
                    else:
                        inserted += 1
                    qty = number_value(item["qty"])
                    note = (
                        f"Tồn đầu kỳ {pending['period']} từ {pending['filename']}; "
                        f"sheet {pending['sheet']}; dòng {','.join(map(str, item['source_rows']))}"
                    )
                    conn.execute(
                        """INSERT INTO inventory_transactions(
                           txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,
                           status,note,created_at,updated_at
                           ) VALUES(?,?,?,?,?,'OPENING',?,?,'posted',?,?,?)
                           ON CONFLICT(source_type,source_id,source_line) DO UPDATE SET
                           txn_date=excluded.txn_date,product_code=excluded.product_code,
                           qty_in=excluded.qty_in,qty_out=excluded.qty_out,unit_cost=excluded.unit_cost,
                           status='posted',note=excluded.note,updated_at=excluded.updated_at""",
                        (pending["period"] + "-01", code, max(qty, 0), max(-qty, 0),
                         max(number_value(item["unit_cost"]), 0), pending["period"], code,
                         note, now_iso(), now_iso()),
                    )
                result_counts = {
                    "inserted_products": inserted_products,
                    "inserted": inserted,
                    "updated": updated,
                    "processed": len(pending["items"]),
                }
                audit(
                    conn, now_iso, "inventory.opening.bulk_import", "ok",
                    entity_type="period", entity_id=pending["period"],
                    metadata={
                        "filename": pending["filename"], "source_hash": pending["source_hash"],
                        "sheet": pending["sheet"], "header_row": pending["header_row"],
                        **result_counts,
                    },
                )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        except Exception:
            return jsonify({"ok": False, "error": "Không ghi được tồn đầu kỳ; dữ liệu chưa được thay đổi"}), 409
        year, month = map(int, pending["period"].split("-"))
        next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        as_of = (next_month - timedelta(days=1)).isoformat()
        with db_factory() as conn:
            inventory = inventory_rows(conn, as_of)
        return jsonify({
            "ok": True, "period": pending["period"], **result_counts,
            "totals": pending["totals"], "items": inventory,
        })

    @app.post("/api/kitchen/attendance/import/preview")
    def api_meal_attendance_import_preview():
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "Chưa chọn file chấm suất ăn"}), 400
        filename = Path(upload.filename).name
        if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
            return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
        payload = upload.read(MAPPING_IMPORT_MAX_BYTES + 1)
        if len(payload) > MAPPING_IMPORT_MAX_BYTES:
            return jsonify({"ok": False, "error": "File Excel vượt quá giới hạn 10 MB"}), 413
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                entries = archive.infolist()
                expanded_size = sum(item.file_size for item in entries)
                if len(entries) > 2_000 or expanded_size > MAPPING_IMPORT_MAX_UNCOMPRESSED_BYTES:
                    return jsonify({"ok": False, "error": "File Excel có cấu trúc quá lớn để đọc an toàn"}), 413
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "error": "File Excel bị hỏng hoặc không đúng định dạng"}), 400

        cutoff = time.time() - MAPPING_IMPORT_TTL_SECONDS
        with MEAL_ATTENDANCE_IMPORT_LOCK:
            for old_token, item in list(PENDING_MEAL_ATTENDANCE_IMPORTS.items()):
                if item["created"] < cutoff:
                    PENDING_MEAL_ATTENDANCE_IMPORTS.pop(old_token, None)
        workbook = None
        try:
            workbook = load_workbook(io.BytesIO(payload), read_only=False, data_only=True, keep_links=False)
            with db_factory() as conn:
                preview = parse_meal_attendance_workbook(conn, workbook)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Không đọc được file chấm suất ăn; vui lòng kiểm tra lại file"}), 400
        finally:
            if workbook is not None:
                workbook.close()

        token = uuid.uuid4().hex
        pending_items = preview.pop("items")
        with MEAL_ATTENDANCE_IMPORT_LOCK:
            PENDING_MEAL_ATTENDANCE_IMPORTS[token] = {
                "created": time.time(),
                "filename": filename,
                "source_hash": hashlib.sha256(payload).hexdigest().upper(),
                "periods": preview["periods"],
                "items": pending_items,
                "counts": preview["counts"],
                "totals": preview["totals"],
                "has_errors": not preview["can_confirm"],
            }
        return jsonify({
            "ok": True, "token": token, "filename": filename,
            "expires_in_minutes": MAPPING_IMPORT_TTL_SECONDS // 60,
            **preview,
        })

    @app.post("/api/kitchen/attendance/import/confirm")
    def api_meal_attendance_import_confirm():
        body = request.get_json(force=True) or {}
        if body.get("confirmed") is not True:
            return jsonify({"ok": False, "error": "Cần xác nhận trước khi ghi chấm suất ăn"}), 400
        token = clean_text(body.get("token"))
        with MEAL_ATTENDANCE_IMPORT_LOCK:
            pending = PENDING_MEAL_ATTENDANCE_IMPORTS.pop(token, None)
        if not pending or time.time() - pending["created"] > MAPPING_IMPORT_TTL_SECONDS:
            return jsonify({"ok": False, "error": "Phiên xem trước đã hết hạn; vui lòng chọn lại file"}), 410
        if pending["has_errors"]:
            return jsonify({"ok": False, "error": "File còn dòng lỗi nên chưa thể nhập"}), 400

        inserted = updated = unchanged = deleted = 0
        try:
            with db_factory() as conn:
                existing = {
                    (row["work_date"], row["kitchen"], row["shift"]): dict(row)
                    for period in pending["periods"]
                    for row in conn.execute(
                        "SELECT * FROM meal_attendance WHERE source_type='MONTHLY_WORKBOOK' AND substr(work_date,1,7)=?",
                        (period,),
                    )
                }
                incoming_keys = set()
                for item in pending["items"]:
                    key = (item["work_date"], item["kitchen"], item["shift"])
                    incoming_keys.add(key)
                    previous = existing.get(key)
                    if previous is None:
                        inserted += 1
                    elif (
                        abs(previous["actual_count"] - item["actual_count"]) <= 1e-9
                        and abs(previous["ordered_count"] - item["ordered_count"]) <= 1e-9
                    ):
                        unchanged += 1
                    else:
                        updated += 1
                    conn.execute(
                        """INSERT INTO meal_attendance(
                           work_date,kitchen,shift,actual_count,ordered_count,source_type,
                           source_file,source_sheet,source_column,updated_at
                           ) VALUES(?,?,?,?,?,'MONTHLY_WORKBOOK',?,?,?,?)
                           ON CONFLICT(work_date,kitchen,shift) DO UPDATE SET
                           actual_count=excluded.actual_count,ordered_count=excluded.ordered_count,
                           source_type='MONTHLY_WORKBOOK',source_file=excluded.source_file,
                           source_sheet=excluded.source_sheet,source_column=excluded.source_column,
                           updated_at=excluded.updated_at""",
                        (item["work_date"], item["kitchen"], item["shift"], item["actual_count"],
                         item["ordered_count"], pending["filename"], item["source_sheet"],
                         item["source_column"], now_iso()),
                    )
                for key in set(existing).difference(incoming_keys):
                    conn.execute(
                        "DELETE FROM meal_attendance WHERE work_date=? AND kitchen=? AND shift=? AND source_type='MONTHLY_WORKBOOK'",
                        key,
                    )
                    deleted += 1
                result_counts = {
                    "inserted": inserted, "updated": updated, "unchanged": unchanged,
                    "deleted": deleted, "processed": len(pending["items"]),
                }
                audit(
                    conn, now_iso, "kitchen.meal_attendance.bulk_import", "ok",
                    entity_type="period", entity_id=",".join(pending["periods"]),
                    metadata={
                        "filename": pending["filename"], "source_hash": pending["source_hash"],
                        **result_counts,
                    },
                )
        except Exception:
            return jsonify({"ok": False, "error": "Không ghi được chấm suất ăn; dữ liệu chưa được thay đổi"}), 409
        return jsonify({
            "ok": True, "periods": pending["periods"], **result_counts,
            "totals": pending["totals"],
        })

    @app.post("/api/inventory/opening")
    def api_inventory_opening():
        body = request.get_json(force=True) or {}
        period = clean_text(body.get("period"))
        items = body.get("items") or []
        if not re.fullmatch(r"\d{4}-\d{2}", period) or not isinstance(items, list):
            return jsonify({"ok": False, "error": "Kỳ tồn đầu phải có dạng YYYY-MM và có danh sách hàng"}), 400
        txn_date = period + "-01"
        with db_factory() as conn:
            saved = 0
            for item in items:
                code = clean_text(item.get("product_code")).upper()
                if not code or not conn.execute("SELECT 1 FROM products WHERE code=?", (code,)).fetchone():
                    continue
                conn.execute(
                    """INSERT INTO inventory_transactions(
                        txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,
                        status,note,created_at,updated_at
                    ) VALUES(?,?,?,?,?,'OPENING',?,?,'posted',?,?,?)
                    ON CONFLICT(source_type,source_id,source_line) DO UPDATE SET
                        qty_in=excluded.qty_in,qty_out=excluded.qty_out,unit_cost=excluded.unit_cost,
                        note=excluded.note,updated_at=excluded.updated_at""",
                    (txn_date, code, max(number_value(item.get("qty")), 0),
                     max(-number_value(item.get("qty")), 0),
                     max(number_value(item.get("unit_cost")), 0), period, code,
                     clean_text(item.get("note")), now_iso(), now_iso()),
                )
                saved += 1
            audit(conn, now_iso, "inventory.opening", "ok", entity_type="period", entity_id=period,
                  metadata={"items": saved})
            return jsonify({"ok": True, "saved": saved, "items": inventory_rows(conn, date.today().isoformat())})

    @app.post("/api/inventory/adjustments")
    def api_inventory_adjustment():
        body = request.get_json(force=True) or {}
        code = clean_text(body.get("product_code")).upper()
        qty = number_value(body.get("qty"))
        if not code or qty == 0:
            return jsonify({"ok": False, "error": "Cần mã hàng và số lượng điều chỉnh khác 0"}), 400
        with db_factory() as conn:
            if not conn.execute("SELECT 1 FROM products WHERE code=?", (code,)).fetchone():
                return jsonify({"ok": False, "error": "Mã hàng chưa có trong danh mục"}), 400
            source_id = clean_text(body.get("reference")) or f"ADJ-{datetime.now():%Y%m%d%H%M%S%f}"
            conn.execute(
                """INSERT INTO inventory_transactions(
                    txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,
                    status,note,created_at,updated_at
                ) VALUES(?,?,?,?,?,'ADJUSTMENT',?,'','posted',?,?,?)""",
                (body.get("txn_date") or date.today().isoformat(), code, max(qty, 0), max(-qty, 0),
                 max(number_value(body.get("unit_cost")), 0), source_id, clean_text(body.get("note")),
                 now_iso(), now_iso()),
            )
            audit(conn, now_iso, "inventory.adjust", "ok", entity_type="product", entity_id=code,
                  metadata={"qty": qty, "reference": source_id})
            return jsonify({"ok": True})

    @app.get("/api/supplier-needs/<int:batch_id>")
    def api_supplier_needs(batch_id):
        with db_factory() as conn:
            batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
            if not batch:
                return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
            stock = inventory_lookup(conn, batch["work_date"])
            available = {code: max(row["available_qty"], 0) for code, row in stock.items()}
            groups = {}
            ordered_total = 0
            required_total = 0
            for row in conn.execute("SELECT * FROM orders WHERE batch_id=? ORDER BY id", (batch_id,)):
                item = dict(row)
                qty = max(number_value(item["qty"]), 0)
                use_stock = min(qty, available.get(item["product_code"], 0))
                available[item["product_code"]] = max(available.get(item["product_code"], 0) - use_stock, 0)
                required = max(qty - use_stock, 0)
                ordered_total += qty
                required_total += required
                if required <= 0:
                    continue
                rule = conn.execute(
                    "SELECT combine_kitchens FROM supplier_rules WHERE supplier_code=?", (item["supplier"],)
                ).fetchone()
                combined = bool(rule and rule["combine_kitchens"])
                key = f"{item['supplier']}|{'ALL' if combined else item['kitchen']}"
                group = groups.setdefault(key, {
                    "supplier": item["supplier"], "kitchen": "GỘP NHIỀU BẾP" if combined else item["kitchen"],
                    "combine_kitchens": combined, "items": [], "total_qty": 0,
                })
                group["items"].append({
                    "order_id": item["id"], "product_code": item["product_code"],
                    "product_name": item["product_name"], "unit": item["unit"],
                    "kitchen": item["kitchen"], "customer_qty": qty, "stock_used": use_stock,
                    "required_qty": required, "note": item["note"],
                })
                group["total_qty"] += required
            return jsonify({
                "ok": True, "batch_id": batch_id, "work_date": batch["work_date"],
                "formula": "max(lượng khách đặt - tồn khả dụng, 0)",
                "ordered_qty": ordered_total, "required_qty": required_total,
                "groups": list(groups.values()),
            })

    @app.put("/api/supplier-rules/<supplier_code>")
    def api_supplier_rule(supplier_code):
        body = request.get_json(force=True) or {}
        code = clean_text(supplier_code)
        with db_factory() as conn:
            conn.execute(
                """INSERT INTO supplier_rules(supplier_code,combine_kitchens,updated_at) VALUES(?,?,?)
                   ON CONFLICT(supplier_code) DO UPDATE SET combine_kitchens=excluded.combine_kitchens,updated_at=excluded.updated_at""",
                (code, 1 if body.get("combine_kitchens") else 0, now_iso()),
            )
            return jsonify({"ok": True})

    @app.get("/api/msmi/status")
    def api_msmi_status():
        try:
            return jsonify({"ok": True, **create_msmi_client().status()})
        except MsmiError as error:
            return jsonify({"ok": False, "connected": False, "read_only": True, "error": str(error)}), 502

    @app.post("/api/msmi/sync")
    def api_msmi_sync():
        body = request.get_json(silent=True) or {}
        with db_factory() as conn:
            tenant = setting_get(conn, "tenant_code", "TDP")
            try:
                result = sync_msmi(
                    conn, create_msmi_client(), now_iso, tenant=tenant,
                    max_pages=body.get("max_pages", 5), page_size=body.get("page_size", 199),
                )
                return jsonify({"ok": True, **result, "invoices": invoice_payload(conn, 30)})
            except MsmiError as error:
                return jsonify({"ok": False, "error": str(error), "read_only": True}), 502

    @app.get("/api/msmi/invoices")
    def api_msmi_invoices():
        with db_factory() as conn:
            return jsonify({"ok": True, "items": invoice_payload(
                conn, request.args.get("limit", 100, type=int), request.args.get("id", type=int)
            )})

    @app.put("/api/msmi/items/<int:item_id>/mapping")
    def api_msmi_mapping(item_id):
        body = request.get_json(force=True) or {}
        product_code = clean_text(body.get("product_code")).upper()
        with db_factory() as conn:
            item = conn.execute(
                """SELECT li.*,i.tenant,i.seller_tax_code,i.id invoice_id FROM msmi_invoice_items li
                   JOIN msmi_invoices i ON i.id=li.invoice_id WHERE li.id=?""", (item_id,)
            ).fetchone()
            if not item:
                return jsonify({"ok": False, "error": "Không tìm thấy dòng hóa đơn"}), 404
            if not conn.execute("SELECT 1 FROM products WHERE code=?", (product_code,)).fetchone():
                return jsonify({"ok": False, "error": "Mã hàng đích chưa có trong danh mục"}), 400
            conn.execute(
                """INSERT INTO item_mappings(
                    tenant,seller_tax_code,source_item_code,source_item_name,product_code,updated_at
                ) VALUES(?,?,?,?,?,?) ON CONFLICT(tenant,seller_tax_code,source_item_code,source_item_name)
                DO UPDATE SET product_code=excluded.product_code,updated_at=excluded.updated_at""",
                (item["tenant"], item["seller_tax_code"] or "", item["source_item_code"] or "",
                 item["source_item_name"] or "", product_code, now_iso()),
            )
            conn.execute(
                "UPDATE msmi_invoice_items SET product_code=?,mapping_status='mapped' WHERE id=?",
                (product_code, item_id),
            )
            remaining = conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoice_items WHERE invoice_id=? AND mapping_status!='mapped'",
                (item["invoice_id"],),
            ).fetchone()["n"]
            conn.execute(
                "UPDATE msmi_invoices SET receipt_status=?,updated_at=? WHERE id=? AND receipt_status!='posted'",
                ("ready" if remaining == 0 else "pending_mapping", now_iso(), item["invoice_id"]),
            )
            audit(conn, now_iso, "msmi.mapping", "ok", entity_type="invoice_item", entity_id=item_id,
                  metadata={"product_code": product_code})
            return jsonify({"ok": True, "invoice": invoice_payload(conn, 1, item["invoice_id"])[0]})

    @app.post("/api/msmi/invoices/<int:invoice_id>/receipt")
    def api_msmi_receipt(invoice_id):
        with db_factory() as conn:
            invoice = conn.execute("SELECT * FROM msmi_invoices WHERE id=?", (invoice_id,)).fetchone()
            if not invoice:
                return jsonify({"ok": False, "error": "Không tìm thấy hóa đơn đầu vào"}), 404
            items = [dict(row) for row in conn.execute(
                "SELECT * FROM msmi_invoice_items WHERE invoice_id=? ORDER BY line_index", (invoice_id,)
            )]
            if not items:
                return jsonify({"ok": False, "error": "Hóa đơn không có chi tiết hàng hóa"}), 400
            missing = [item for item in items if item["mapping_status"] != "mapped" or not item["product_code"]]
            if missing:
                return jsonify({"ok": False, "error": f"Còn {len(missing)} dòng chưa ghép mã hàng"}), 400
            posted = 0
            for item in items:
                conn.execute(
                    """INSERT INTO inventory_transactions(
                        txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,
                        status,note,created_at,updated_at
                    ) VALUES(?,?,?,?,?,'MSMI_INPUT',?,?,'posted',?,?,?)
                    ON CONFLICT(source_type,source_id,source_line) DO NOTHING""",
                    (invoice["invoice_date"] or date.today().isoformat(), item["product_code"], item["qty"], 0,
                     item["unit_price"], invoice["remote_id"], str(item["line_index"]),
                     f"Hóa đơn {invoice['invoice_series']} {invoice['invoice_number']}", now_iso(), now_iso()),
                )
                posted += conn.execute("SELECT changes() n").fetchone()["n"]
            conn.execute(
                "UPDATE msmi_invoices SET receipt_status='posted',updated_at=? WHERE id=?",
                (now_iso(), invoice_id),
            )
            audit(conn, now_iso, "msmi.create_receipt", "ok", entity_type="msmi_invoice", entity_id=invoice_id,
                  metadata={"new_inventory_lines": posted})
            return jsonify({"ok": True, "new_inventory_lines": posted, "idempotent": posted == 0})

    @app.post("/api/outgoing-invoices/draft/<int:batch_id>")
    def api_create_outgoing_drafts(batch_id):
        with db_factory() as conn:
            batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
            if not batch:
                return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
            if batch["status"] != "approved":
                return jsonify({"ok": False, "error": "Phải duyệt phiên đơn trước khi lập hóa đơn đầu ra"}), 400
            orders = [dict(row) for row in conn.execute(
                "SELECT * FROM orders WHERE batch_id=? ORDER BY contractor,id", (batch_id,)
            )]
            stock = inventory_lookup(conn, batch["work_date"])
            available = {code: max(row["available_qty"], 0) for code, row in stock.items()}
            # Khi người dùng bấm tạo lại, tồn khả dụng đã trừ phần chính dự thảo
            # của batch này đang giữ. Cộng phần giữ đó lại trước khi kiểm tra để
            # thao tác idempotent, rồi phía dưới thay thế đúng các dòng reserve.
            for reserved in conn.execute(
                """SELECT t.product_code,SUM(t.qty_out) qty
                   FROM inventory_transactions t
                   JOIN outgoing_invoice_drafts d ON CAST(d.id AS TEXT)=t.source_id
                   WHERE t.source_type='OUTGOING_DRAFT' AND t.status='reserved'
                     AND d.batch_id=? AND d.status!='issued'
                   GROUP BY t.product_code""",
                (batch_id,),
            ):
                available[reserved["product_code"]] = (
                    available.get(reserved["product_code"], 0) + reserved["qty"]
                )
            shortages = defaultdict(lambda: {"required": 0, "available": 0, "product_name": ""})
            for item in orders:
                qty = net_delivered(item)
                code = item["product_code"]
                have = available.get(code, 0)
                if qty > have + 1e-9:
                    shortages[code]["required"] += qty - have
                    shortages[code]["available"] = have
                    shortages[code]["product_name"] = item["product_name"]
                available[code] = max(have - qty, 0)
            if shortages:
                return jsonify({
                    "ok": False,
                    "error": "Không đủ tồn hóa đơn để lập toàn bộ hóa đơn đầu ra",
                    "shortages": [{"product_code": code, **values} for code, values in shortages.items()],
                }), 409

            created = []
            for contractor, group in _group_rows(orders, "contractor").items():
                existing = conn.execute(
                    "SELECT * FROM outgoing_invoice_drafts WHERE batch_id=? AND contractor=?",
                    (batch_id, contractor),
                ).fetchone()
                if existing and existing["status"] == "issued":
                    created.append(dict(existing))
                    continue
                subtotal = sum(net_delivered(item) * number_value(item["sell_price"]) for item in group)
                total = sum(net_delivered(item) * number_value(item["sell_price"]) * tax_factor(item["tax"]) for item in group)
                tax_amount = total - subtotal
                conn.execute(
                    """INSERT INTO outgoing_invoice_drafts(
                        batch_id,contractor,invoice_date,status,subtotal,tax_amount,total_amount,created_at
                    ) VALUES(?,?,?,'draft',?,?,?,?)
                    ON CONFLICT(batch_id,contractor) DO UPDATE SET
                        invoice_date=excluded.invoice_date,status='draft',subtotal=excluded.subtotal,
                        tax_amount=excluded.tax_amount,total_amount=excluded.total_amount""",
                    (batch_id, contractor, batch["work_date"], subtotal, tax_amount, total, now_iso()),
                )
                draft = conn.execute(
                    "SELECT * FROM outgoing_invoice_drafts WHERE batch_id=? AND contractor=?",
                    (batch_id, contractor),
                ).fetchone()
                draft_id = draft["id"]
                conn.execute("DELETE FROM outgoing_invoice_lines WHERE draft_id=?", (draft_id,))
                conn.execute(
                    "UPDATE inventory_transactions SET status='cancelled',updated_at=? "
                    "WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",
                    (now_iso(), str(draft_id)),
                )
                for item in group:
                    qty = net_delivered(item)
                    amount = qty * number_value(item["sell_price"])
                    invoice_name_row = conn.execute(
                        "SELECT invoice_name FROM outgoing_product_names WHERE product_code=?",
                        (item["product_code"],),
                    ).fetchone()
                    invoice_name = invoice_name_row["invoice_name"] if invoice_name_row else item["product_name"]
                    conn.execute(
                        """INSERT INTO outgoing_invoice_lines(
                            draft_id,order_id,product_code,product_name,qty,unit,unit_price,tax,amount
                        ) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (draft_id, item["id"], item["product_code"], invoice_name, qty,
                         item["unit"], item["sell_price"], item["tax"], amount),
                    )
                    conn.execute(
                        """INSERT INTO inventory_transactions(
                            txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,
                            kitchen,status,note,created_at,updated_at
                        ) VALUES(?,?,0,?,?, 'OUTGOING_DRAFT',?,?,?,'reserved',?,?,?)
                        ON CONFLICT(source_type,source_id,source_line) DO UPDATE SET
                            txn_date=excluded.txn_date,product_code=excluded.product_code,qty_out=excluded.qty_out,
                            unit_cost=excluded.unit_cost,kitchen=excluded.kitchen,status='reserved',updated_at=excluded.updated_at""",
                        (batch["work_date"], item["product_code"], qty, item["buy_price"], str(draft_id),
                         str(item["id"]), item["kitchen"], f"Dự thảo hóa đơn {contractor}", now_iso(), now_iso()),
                    )
                created.append(dict(draft))
            audit(conn, now_iso, "outgoing.draft", "ok", entity_type="batch", entity_id=batch_id,
                  metadata={"drafts": len(created)})
            return jsonify({"ok": True, "drafts": created, "requires_user_sign_and_issue": True})

    @app.put("/api/outgoing-product-names/<product_code>")
    def api_outgoing_product_name(product_code):
        body = request.get_json(force=True) or {}
        code = clean_text(product_code).upper()
        invoice_name = clean_text(body.get("invoice_name"))
        if not code or not invoice_name:
            return jsonify({"ok": False, "error": "Cần mã hàng và tên xuất hóa đơn"}), 400
        with db_factory() as conn:
            product = conn.execute("SELECT code FROM products WHERE code=?", (code,)).fetchone()
            if not product:
                return jsonify({"ok": False, "error": "Mã hàng chưa có trong danh mục"}), 404
            conn.execute(
                """INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES(?,?,?)
                   ON CONFLICT(product_code) DO UPDATE SET invoice_name=excluded.invoice_name,updated_at=excluded.updated_at""",
                (code, invoice_name, now_iso()),
            )
            audit(conn, now_iso, "outgoing.name_mapping", "ok", entity_type="product", entity_id=code)
            return jsonify({"ok": True, "product_code": code, "invoice_name": invoice_name})

    @app.post("/api/outgoing-invoices/<int:draft_id>/confirm-issued")
    def api_confirm_outgoing_issued(draft_id):
        body = request.get_json(silent=True) or {}
        if not body.get("confirmed"):
            return jsonify({"ok": False, "error": "Cần xác nhận người dùng đã ký và phát hành hóa đơn"}), 400
        with db_factory() as conn:
            draft = conn.execute("SELECT * FROM outgoing_invoice_drafts WHERE id=?", (draft_id,)).fetchone()
            if not draft:
                return jsonify({"ok": False, "error": "Không tìm thấy dự thảo hóa đơn"}), 404
            if draft["status"] == "cancelled":
                return jsonify({"ok": False, "error": "Dự thảo đã hủy; cần tạo lại trước khi xác nhận phát hành"}), 409
            if draft["status"] != "issued":
                conn.execute(
                    "UPDATE outgoing_invoice_drafts SET status='issued',issued_at=? WHERE id=?",
                    (now_iso(), draft_id),
                )
                conn.execute(
                    "UPDATE inventory_transactions SET status='posted',updated_at=? "
                    "WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'",
                    (now_iso(), str(draft_id)),
                )
                audit(conn, now_iso, "outgoing.confirm_issued", "ok", entity_type="outgoing_invoice", entity_id=draft_id)
            return jsonify({"ok": True, "idempotent": draft["status"] == "issued"})

    @app.post("/api/outgoing-invoices/<int:draft_id>/cancel")
    def api_cancel_outgoing_draft(draft_id):
        body = request.get_json(silent=True) or {}
        if not body.get("confirmed"):
            return jsonify({"ok": False, "error": "Cần xác nhận hủy dự thảo hóa đơn"}), 400
        with db_factory() as conn:
            draft = conn.execute("SELECT * FROM outgoing_invoice_drafts WHERE id=?", (draft_id,)).fetchone()
            if not draft:
                return jsonify({"ok": False, "error": "Không tìm thấy dự thảo hóa đơn"}), 404
            if draft["status"] == "issued":
                return jsonify({"ok": False, "error": "Hóa đơn đã phát hành nên không thể hủy dự thảo"}), 409
            if draft["status"] != "cancelled":
                conn.execute(
                    "UPDATE outgoing_invoice_drafts SET status='cancelled' WHERE id=?", (draft_id,)
                )
                conn.execute(
                    """UPDATE inventory_transactions SET status='cancelled',updated_at=?
                       WHERE source_type='OUTGOING_DRAFT' AND source_id=? AND status='reserved'""",
                    (now_iso(), str(draft_id)),
                )
                audit(conn, now_iso, "outgoing.cancel", "ok", entity_type="outgoing_invoice", entity_id=draft_id)
            return jsonify({"ok": True, "idempotent": draft["status"] == "cancelled"})

    @app.get("/api/outgoing-invoices")
    def api_outgoing_invoices():
        with db_factory() as conn:
            rows = [dict(row) for row in conn.execute(
                "SELECT * FROM outgoing_invoice_drafts ORDER BY invoice_date DESC,id DESC LIMIT 200"
            )]
            return jsonify({"ok": True, "items": rows})

    @app.post("/api/debt-adjustments")
    def api_debt_adjustment():
        body = request.get_json(force=True) or {}
        if body.get("party_type") not in {"contractor", "supplier"}:
            return jsonify({"ok": False, "error": "Nhóm công nợ không hợp lệ"}), 400
        with db_factory() as conn:
            cur = conn.execute(
                """INSERT INTO debt_adjustments(
                    adjustment_date,party_type,party_code,amount,note,created_at
                ) VALUES(?,?,?,?,?,?)""",
                (body.get("adjustment_date") or date.today().isoformat(), body["party_type"],
                 clean_text(body.get("party_code")), number_value(body.get("amount")),
                 clean_text(body.get("note")), now_iso()),
            )
            return jsonify({"ok": True, "id": cur.lastrowid})

    @app.get("/api/debts")
    def api_debts():
        period_from = request.args.get("from") or date.today().replace(day=1).isoformat()
        period_to = request.args.get("to") or date.today().isoformat()
        try:
            validate_date_range(period_from, period_to)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        with db_factory() as conn:
            return jsonify({"ok": True, **debt_period_payload(conn, period_from, period_to, tax_factor)})

    @app.get("/api/export/debts")
    def api_export_debts():
        period_from = request.args.get("from") or date.today().replace(day=1).isoformat()
        period_to = request.args.get("to") or date.today().isoformat()
        try:
            validate_date_range(period_from, period_to)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        with db_factory() as conn:
            payload = debt_period_payload(conn, period_from, period_to, tax_factor)
            workbook = debt_period_workbook(conn, payload)
            return send_workbook(
                workbook,
                f"Cong_no_{period_from}_{period_to}.xlsx",
            )

    @app.put("/api/kitchen-units/<kitchen_code>")
    def api_kitchen_unit(kitchen_code):
        body = request.get_json(force=True) or {}
        unit_code = clean_text(body.get("xcom_code") or body.get("unit_code")).upper()
        if not unit_code:
            return jsonify({"ok": False, "error": "Cần mã XCOM (xưởng cơm)"}), 400
        with db_factory() as conn:
            conn.execute(
                """INSERT INTO kitchen_units(kitchen_code,unit_code,updated_at) VALUES(?,?,?)
                   ON CONFLICT(kitchen_code) DO UPDATE SET unit_code=excluded.unit_code,updated_at=excluded.updated_at""",
                (clean_text(kitchen_code).upper(), unit_code, now_iso()),
            )
            return jsonify({"ok": True})

    @app.put("/api/dated-prices/<product_code>")
    def api_dated_price(product_code):
        body = request.get_json(force=True) or {}
        period = clean_text(body.get("period"))
        if not re.fullmatch(r"\d{4}-\d{2}", period):
            return jsonify({"ok": False, "error": "Kỳ giá phải có dạng YYYY-MM"}), 400
        with db_factory() as conn:
            conn.execute(
                """INSERT INTO dated_prices(product_code,price_group,period,price_value,updated_at)
                   VALUES(?,?,?,?,?) ON CONFLICT(product_code,price_group,period)
                   DO UPDATE SET price_value=excluded.price_value,updated_at=excluded.updated_at""",
                (clean_text(product_code).upper(), clean_text(body.get("price_group") or "HATRAN").upper(),
                 period, number_value(body.get("price_value")), now_iso()),
            )
            return jsonify({"ok": True})

    @app.get("/api/kitchen/plans")
    def api_meal_plans():
        with db_factory() as conn:
            return jsonify({"ok": True, "items": meal_plan_payload(conn, request.args.get("date", ""))})

    @app.post("/api/kitchen/plans")
    def api_save_meal_plan():
        body = request.get_json(force=True) or {}
        items = body.get("items") or []
        if not body.get("work_date") or not body.get("kitchen") or not body.get("shift"):
            return jsonify({"ok": False, "error": "Cần ngày, bếp và ca"}), 400
        if number_value(body.get("meal_count")) <= 0:
            return jsonify({"ok": False, "error": "Số suất phải lớn hơn 0"}), 400
        with db_factory() as conn:
            kitchen = clean_text(body["kitchen"]).upper()
            unit = conn.execute("SELECT unit_code FROM kitchen_units WHERE kitchen_code=?", (kitchen,)).fetchone()
            unit_code = clean_text(body.get("xcom_code") or body.get("unit_code")) or (unit["unit_code"] if unit else "")
            meal_count = number_value(body.get("meal_count"))
            menu_count = max(int(number_value(body.get("menu_count"), 1)), 1)
            servings_per_menu = number_value(body.get("servings_per_menu")) or meal_count / menu_count
            meal_price = max(number_value(body.get("meal_price")), 0)
            other_cost = max(number_value(body.get("other_cost")), 0)
            plan_id = int(body.get("id") or 0)
            if plan_id:
                conn.execute(
                    """UPDATE meal_plans SET work_date=?,kitchen=?,shift=?,meal_count=?,unit_code=?,
                       menu_count=?,servings_per_menu=?,meal_price=?,other_cost=?,status='draft',note=?,
                       updated_at=? WHERE id=?""",
                    (body["work_date"], kitchen, clean_text(body["shift"]), meal_count, unit_code,
                     menu_count, servings_per_menu, meal_price, other_cost, clean_text(body.get("note")),
                     now_iso(), plan_id),
                )
                conn.execute("DELETE FROM meal_plan_items WHERE plan_id=?", (plan_id,))
            else:
                cur = conn.execute(
                    """INSERT INTO meal_plans(
                        work_date,kitchen,shift,meal_count,unit_code,status,note,created_at,updated_at,
                        menu_count,servings_per_menu,meal_price,other_cost
                    ) VALUES(?,?,?,?,?,'draft',?,?,?,?,?,?,?)""",
                    (body["work_date"], kitchen, clean_text(body["shift"]), meal_count,
                     unit_code, clean_text(body.get("note")), now_iso(), now_iso(), menu_count,
                     servings_per_menu, meal_price, other_cost),
                )
                plan_id = cur.lastrowid
            period = body["work_date"][:7]
            saved = 0
            warnings = []
            for raw in items:
                code = clean_text(raw.get("product_code")).upper()
                product = conn.execute("SELECT * FROM products WHERE code=?", (code,)).fetchone()
                if not product or number_value(raw.get("norm_qty")) <= 0:
                    continue
                price = number_value(raw.get("buy_price"))
                source = "Nhập tại kế hoạch"
                if price <= 0:
                    dated = conn.execute(
                        "SELECT price_value FROM dated_prices WHERE product_code=? AND price_group='HATRAN' AND period=?",
                        (code, period),
                    ).fetchone()
                    if dated:
                        price = dated["price_value"]
                        source = f"HATRAN {period}"
                    else:
                        group_price = conn.execute(
                            "SELECT price_value FROM product_prices WHERE product_code=? AND price_group='HATRAN'",
                            (code,),
                        ).fetchone()
                        price = group_price["price_value"] if group_price and group_price["price_value"] else 0
                        source = "HATRAN danh mục"
                        warnings.append(f"{code}: chưa có giá HATRAN đúng kỳ {period}")
                conn.execute(
                    """INSERT INTO meal_plan_items(
                        plan_id,dish_name,product_code,product_name,norm_qty,unit,supplier,buy_price,price_source,
                        source_norm_per_1000,applicable_meal_count,source_amount
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (plan_id, clean_text(raw.get("dish_name")), code, product["name"],
                     number_value(raw.get("norm_qty")), clean_text(raw.get("unit")) or product["unit"],
                     clean_text(raw.get("supplier")) or product["supplier"], price, source,
                     number_value(raw.get("source_norm_per_1000")) or number_value(raw.get("norm_qty")) * 1000,
                     number_value(raw.get("applicable_meal_count")) or meal_count, 0),
                )
                saved += 1
            audit(conn, now_iso, "kitchen.save_plan", "ok", entity_type="meal_plan", entity_id=plan_id,
                  metadata={"items": saved, "warnings": len(warnings)})
            return jsonify({"ok": True, "id": plan_id, "warnings": warnings,
                            "items": meal_plan_payload(conn, body["work_date"])})

    @app.post("/api/kitchen/plans/<int:plan_id>/approve")
    def api_approve_meal_plan(plan_id):
        with db_factory() as conn:
            plan = conn.execute(
                """SELECT mp.*,
                          COALESCE(NULLIF(mp.unit_code,''),ku.unit_code,'') mapped_unit
                   FROM meal_plans mp
                   LEFT JOIN kitchen_units ku ON ku.kitchen_code=mp.kitchen
                   WHERE mp.id=?""",
                (plan_id,),
            ).fetchone()
            if not plan:
                return jsonify({"ok": False, "error": "Không tìm thấy kế hoạch xưởng cơm"}), 404
            if not clean_text(plan["mapped_unit"]):
                return jsonify({"ok": False, "error": "Phải ghép bếp vào XCOM trước khi duyệt"}), 400
            if number_value(plan["meal_price"]) <= 0:
                return jsonify({"ok": False, "error": "Phải có đơn giá suất ăn trước khi duyệt"}), 400
            count = conn.execute("SELECT COUNT(*) n FROM meal_plan_items WHERE plan_id=?", (plan_id,)).fetchone()["n"]
            if count == 0:
                return jsonify({"ok": False, "error": "Kế hoạch chưa có định lượng nguyên liệu"}), 400
            missing_price = conn.execute(
                "SELECT COUNT(*) n FROM meal_plan_items WHERE plan_id=? AND buy_price<=0", (plan_id,)
            ).fetchone()["n"]
            if missing_price:
                return jsonify({"ok": False, "error": f"Còn {missing_price} nguyên liệu thiếu giá"}), 400
            conn.execute("UPDATE meal_plans SET status='approved',updated_at=? WHERE id=?", (now_iso(), plan_id))
            return jsonify({"ok": True})

    @app.get("/api/kitchen/po")
    def api_kitchen_po():
        work_date = request.args.get("date") or date.today().isoformat()
        with db_factory() as conn:
            plans = meal_plan_payload(conn, work_date)
            if not plans:
                return jsonify({"ok": False, "error": "Ngày này chưa có kế hoạch xưởng cơm"}), 404
            wb = meal_po_workbook(plans, work_date)
            approval_label = "DA_DUYET" if all(plan["status"] == "approved" for plan in plans) else "NHAP"
            stream = io.BytesIO()
            wb.save(stream)
            stream.seek(0)
            return send_file(stream, as_attachment=True,
                             download_name=f"PO_xuong_com_{approval_label}_{work_date}.xlsx",
                             mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.post("/api/staff")
    def api_save_staff():
        body = request.get_json(force=True) or {}
        code = clean_text(body.get("employee_code")).upper()
        name = clean_text(body.get("full_name"))
        if not code or not name:
            return jsonify({"ok": False, "error": "Cần mã và họ tên nhân sự"}), 400
        with db_factory() as conn:
            conn.execute(
                """INSERT INTO staff(
                    employee_code,full_name,role_name,kitchen,base_salary,standard_days,standard_hours,
                    bhxh_employee_rate,bhxh_company_rate,active,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(employee_code) DO UPDATE SET
                    full_name=excluded.full_name,role_name=excluded.role_name,kitchen=excluded.kitchen,
                    base_salary=excluded.base_salary,standard_days=excluded.standard_days,
                    standard_hours=excluded.standard_hours,bhxh_employee_rate=excluded.bhxh_employee_rate,
                    bhxh_company_rate=excluded.bhxh_company_rate,active=excluded.active,updated_at=excluded.updated_at""",
                (code, name, clean_text(body.get("role_name")), clean_text(body.get("kitchen")).upper(),
                 number_value(body.get("base_salary")), number_value(body.get("standard_days"), 26),
                 number_value(body.get("standard_hours"), 8), number_value(body.get("bhxh_employee_rate")),
                 number_value(body.get("bhxh_company_rate")), 0 if body.get("active") is False else 1,
                 now_iso(), now_iso()),
            )
            return jsonify({"ok": True})

    @app.post("/api/attendance")
    def api_save_attendance():
        body = request.get_json(force=True) or {}
        with db_factory() as conn:
            staff_row = conn.execute(
                "SELECT id FROM staff WHERE employee_code=?", (clean_text(body.get("employee_code")).upper(),)
            ).fetchone()
            if not staff_row or not body.get("work_date"):
                return jsonify({"ok": False, "error": "Nhân sự hoặc ngày chấm công không hợp lệ"}), 400
            conn.execute(
                """INSERT INTO attendance_entries(
                    employee_id,work_date,normal_hours,overtime_hours,sunday_hours,night_hours,
                    holiday_hours,note,source,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(employee_id,work_date) DO UPDATE SET
                    normal_hours=excluded.normal_hours,overtime_hours=excluded.overtime_hours,
                    sunday_hours=excluded.sunday_hours,night_hours=excluded.night_hours,
                    holiday_hours=excluded.holiday_hours,note=excluded.note,source=excluded.source,
                    updated_at=excluded.updated_at""",
                (staff_row["id"], body["work_date"], number_value(body.get("normal_hours")),
                 number_value(body.get("overtime_hours")), number_value(body.get("sunday_hours")),
                 number_value(body.get("night_hours")), number_value(body.get("holiday_hours")),
                 clean_text(body.get("note")), "manual", now_iso()),
            )
            return jsonify({"ok": True})

    @app.post("/api/attendance/import")
    def api_import_attendance():
        upload = request.files.get("file")
        if not upload or not upload.filename or Path(upload.filename).suffix.lower() not in {".xlsx", ".xlsm"}:
            return jsonify({"ok": False, "error": "Cần file chấm công .xlsx/.xlsm"}), 400
        temp = data_dir / f"attendance_{datetime.now():%Y%m%d%H%M%S%f}.xlsx"
        upload.save(temp)
        try:
            with db_factory() as conn:
                result = import_legacy_attendance(conn, temp, upload.filename, now_iso)
                audit(conn, now_iso, "attendance.import", "ok", metadata=result)
                return jsonify({"ok": True, **result})
        finally:
            try:
                temp.unlink()
            except OSError:
                pass

    @app.put("/api/payroll-adjustments/<employee_code>/<month>")
    def api_payroll_adjustment(employee_code, month):
        body = request.get_json(force=True) or {}
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            return jsonify({"ok": False, "error": "Tháng phải có dạng YYYY-MM"}), 400
        with db_factory() as conn:
            person = conn.execute("SELECT id FROM staff WHERE employee_code=?", (employee_code.upper(),)).fetchone()
            if not person:
                return jsonify({"ok": False, "error": "Không tìm thấy nhân sự"}), 404
            conn.execute(
                """INSERT INTO payroll_adjustments(
                    employee_id,month,allowance,responsibility,advance,probation_deduction,
                    bhxh_employee_amount,bhxh_company_amount,gross_override,net_override,use_override,note,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(employee_id,month) DO UPDATE SET
                    allowance=excluded.allowance,responsibility=excluded.responsibility,
                    advance=excluded.advance,probation_deduction=excluded.probation_deduction,
                    bhxh_employee_amount=excluded.bhxh_employee_amount,
                    bhxh_company_amount=excluded.bhxh_company_amount,
                    gross_override=excluded.gross_override,net_override=excluded.net_override,
                    use_override=excluded.use_override,note=excluded.note,updated_at=excluded.updated_at""",
                (person["id"], month, number_value(body.get("allowance")),
                 number_value(body.get("responsibility")), number_value(body.get("advance")),
                 number_value(body.get("probation_deduction")), number_value(body.get("bhxh_employee_amount")),
                 number_value(body.get("bhxh_company_amount")), number_value(body.get("gross_override")),
                 number_value(body.get("net_override")), 1 if body.get("use_override") else 0,
                 clean_text(body.get("note")), now_iso()),
            )
            return jsonify({"ok": True, "payroll": payroll_rows(conn, month)})

    @app.get("/api/payroll")
    def api_payroll():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            return jsonify({"ok": False, "error": "Tháng tính lương phải có dạng YYYY-MM"}), 400
        with db_factory() as conn:
            try:
                rows = payroll_rows(conn, month)
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            labor = [dict(row) for row in conn.execute(
                """SELECT kitchen,SUM(amount) amount FROM kitchen_labor_costs
                   WHERE substr(work_date,1,7)=? GROUP BY kitchen ORDER BY kitchen""", (month,)
            )]
            return jsonify({"ok": True, "month": month, "items": rows, "labor_by_kitchen": labor,
                            "total_net": sum(row["net_salary"] for row in rows)})

    @app.get("/api/export/payroll")
    def api_export_payroll():
        month = request.args.get("month") or date.today().strftime("%Y-%m")
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            return jsonify({"ok": False, "error": "Tháng tính lương phải có dạng YYYY-MM"}), 400
        with db_factory() as conn:
            try:
                workbook = payroll_workbook(conn, month)
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            return send_workbook(workbook, f"Bang_luong_{month}.xlsx")

    @app.put("/api/print/settings")
    def api_print_settings():
        body = request.get_json(force=True) or {}
        with db_factory() as conn:
            setting_set(conn, "printer_name", clean_text(body.get("printer_name")))
            setting_set(conn, "print_copies", max(1, min(int(number_value(body.get("copies"), 1)), 10)))
            setting_set(conn, "print_paper", clean_text(body.get("paper")) or "A4")
            return jsonify({"ok": True})

    @app.post("/api/print/prepare/<int:batch_id>")
    def api_prepare_print(batch_id):
        export_dir = data_dir / "print_jobs" / str(batch_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        with db_factory() as conn:
            batch, orders = ctx["require_batch"](conn, batch_id)
            if batch["status"] != "approved":
                return jsonify({"ok": False, "error": "Phải duyệt phiên đơn trước khi chuẩn bị in"}), 400
            documents = {
                "supplier_orders": (ctx["export_supplier_orders"](conn, batch, orders), f"Don_NCC_{batch['work_date']}.xlsx"),
                "deliveries": (ctx["export_deliveries"](conn, batch, orders), f"Phieu_giao_{batch['work_date']}.xlsx"),
                "purchases": (ctx["export_purchase_documents"](conn, batch, orders), f"Bang_ke_{batch['work_date']}.xlsx"),
                "report": (ctx["export_report"](conn, batch, orders), f"Bao_cao_{batch['work_date']}.xlsx"),
            }
            prepared = []
            for document_type, (workbook, filename) in documents.items():
                path = export_dir / filename
                workbook.save(path)
                conn.execute(
                    """INSERT INTO print_jobs(
                        batch_id,document_type,file_path,status,created_at
                    ) VALUES(?,?,?,'prepared',?) ON CONFLICT(batch_id,document_type) DO UPDATE SET
                        file_path=excluded.file_path,status='prepared',approved_at=NULL,printed_at=NULL,
                        error_message=NULL,created_at=excluded.created_at""",
                    (batch_id, document_type, str(path.resolve()), now_iso()),
                )
                prepared.append(document_type)
            audit(conn, now_iso, "print.prepare", "ok", entity_type="batch", entity_id=batch_id,
                  metadata={"documents": prepared})
            return jsonify({"ok": True, "prepared": prepared, "requires_approval": True})

    @app.post("/api/print/approve/<int:batch_id>")
    def api_approve_print(batch_id):
        with db_factory() as conn:
            count = conn.execute("SELECT COUNT(*) n FROM print_jobs WHERE batch_id=?", (batch_id,)).fetchone()["n"]
            if not count:
                return jsonify({"ok": False, "error": "Chưa chuẩn bị bộ chứng từ in"}), 400
            conn.execute(
                "UPDATE print_jobs SET status='approved',approved_at=?,error_message=NULL WHERE batch_id=?",
                (now_iso(), batch_id),
            )
            audit(conn, now_iso, "print.approve", "ok", entity_type="batch", entity_id=batch_id,
                  metadata={"jobs": count})
            return jsonify({"ok": True, "approved": count})

    @app.post("/api/print/run/<int:batch_id>")
    def api_run_print(batch_id):
        body = request.get_json(silent=True) or {}
        dry_run = bool(body.get("dry_run"))
        with db_factory() as conn:
            jobs = [dict(row) for row in conn.execute(
                "SELECT * FROM print_jobs WHERE batch_id=? AND status='approved' ORDER BY id", (batch_id,)
            )]
            if not jobs:
                return jsonify({"ok": False, "error": "Không có chứng từ đã duyệt để in"}), 400
            missing = [job for job in jobs if not Path(job["file_path"]).exists()]
            if missing:
                return jsonify({"ok": False, "error": "Có file in bị thiếu; cần chuẩn bị lại"}), 400
            printer_name = setting_get(conn, "printer_name", "")
            copies = max(1, min(int(as_number(setting_get(conn, "print_copies", "1"), 1)), 10))
            if not dry_run:
                if os.name != "nt" or not hasattr(os, "startfile"):
                    return jsonify({"ok": False, "error": "In trực tiếp chỉ hỗ trợ trên PC Windows bàn giao"}), 400
                for job in jobs:
                    try:
                        for _ in range(copies):
                            os.startfile(job["file_path"], "print")
                        conn.execute(
                            "UPDATE print_jobs SET status='printed',printed_at=?,printer_name=?,error_message=NULL WHERE id=?",
                            (now_iso(), printer_name or "Máy in mặc định Windows", job["id"]),
                        )
                    except OSError:
                        conn.execute(
                            "UPDATE print_jobs SET status='error',error_message=? WHERE id=?",
                            ("Windows không mở được lệnh in cho file này", job["id"]),
                        )
                        return jsonify({"ok": False, "error": "Windows không gửi được một file sang máy in"}), 500
            audit(conn, now_iso, "print.run", "dry_run" if dry_run else "ok", entity_type="batch", entity_id=batch_id,
                  metadata={"jobs": len(jobs), "copies": copies})
            return jsonify({"ok": True, "dry_run": dry_run, "jobs": len(jobs), "copies": copies,
                            "printer": printer_name or "Máy in mặc định Windows"})

    @app.get("/api/print/jobs/<int:batch_id>")
    def api_print_jobs(batch_id):
        with db_factory() as conn:
            return jsonify({"ok": True, "items": [dict(row) for row in conn.execute(
                "SELECT * FROM print_jobs WHERE batch_id=? ORDER BY id", (batch_id,)
            )]})

    @app.put("/api/document-settings")
    def api_document_settings():
        body = request.get_json(force=True) or {}
        allowed = {"payment_requester", "payment_bank_name", "payment_bank_account"}
        with db_factory() as conn:
            for key in allowed:
                if key in body:
                    setting_set(conn, key, clean_text(body[key]))
            return jsonify({"ok": True})

    @app.get("/api/export/payment-request/<contractor>")
    def api_payment_request(contractor):
        if Document is None:
            return jsonify({"ok": False, "error": "Máy chưa cài thư viện python-docx"}), 500
        period_from = request.args.get("from") or date.today().replace(day=1).isoformat()
        period_to = request.args.get("to") or date.today().isoformat()
        contractor = clean_text(contractor).upper()
        with db_factory() as conn:
            rows = [dict(row) for row in conn.execute(
                """SELECT o.*,b.work_date FROM orders o JOIN batches b ON b.id=o.batch_id
                   WHERE b.status='approved' AND o.contractor=? AND b.work_date BETWEEN ? AND ?""",
                (contractor, period_from, period_to),
            )]
            amount = sum(net_delivered(row) * number_value(row["sell_price"]) * tax_factor(row["tax"]) for row in rows)
            if not rows:
                return jsonify({"ok": False, "error": "Không có dữ liệu đã duyệt trong kỳ"}), 404
            requester = setting_get(conn, "payment_requester", "")
            bank_name = setting_get(conn, "payment_bank_name", "")
            bank_account = setting_get(conn, "payment_bank_account", "")
            if not requester or not bank_name or not bank_account:
                return jsonify({
                    "ok": False,
                    "error": "Thiếu người đại diện hoặc tài khoản nhận tiền; cập nhật tại Cấu hình trước khi xuất",
                }), 409
            contractor_row = conn.execute("SELECT name FROM contractors WHERE code=?", (contractor,)).fetchone()
            daily_amounts = defaultdict(float)
            for row in rows:
                daily_amounts[row["work_date"]] += (
                    net_delivered(row) * number_value(row["sell_price"]) * tax_factor(row["tax"])
                )
            document = payment_request_document(
                company=setting_get(conn, "company", ""),
                recipient=contractor_row["name"] if contractor_row else contractor,
                requester=requester,
                bank_name=bank_name,
                bank_account=bank_account,
                amount=amount, period_from=period_from, period_to=period_to,
                details=[
                    {"work_date": work_date, "amount": daily_amounts[work_date]}
                    for work_date in sorted(daily_amounts)
                ],
            )
            stream = io.BytesIO()
            document.save(stream)
            stream.seek(0)
            return send_file(stream, as_attachment=True,
                             download_name=f"De_nghi_thanh_toan_{contractor}_{period_from}_{period_to}.docx",
                             mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


def _group_rows(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get(key) or "CHƯA XÁC ĐỊNH"].append(row)
    return groups


def debt_period_payload(conn, period_from: str, period_to: str, tax_factor):
    if period_from > period_to:
        raise ValueError("Ngày bắt đầu phải trước ngày kết thúc")
    parties = {
        "contractor": defaultdict(lambda: {
            "opening": 0, "period_charge": 0, "period_paid": 0,
            "period_adjustment": 0, "closing": 0,
        }),
        "supplier": defaultdict(lambda: {
            "opening": 0, "period_charge": 0, "period_paid": 0,
            "period_adjustment": 0, "closing": 0,
        }),
    }
    for row in conn.execute("SELECT * FROM balances"):
        if row["party_type"] in parties:
            parties[row["party_type"]][row["party_code"]]["opening"] += row["opening"]
    for row in conn.execute(
        """SELECT o.*,b.work_date FROM orders o JOIN batches b ON b.id=o.batch_id
           WHERE b.status='approved' AND b.work_date<=? ORDER BY b.work_date,o.id""", (period_to,)
    ):
        item = dict(row)
        contractor_charge = net_delivered(item) * as_number(item["sell_price"]) * tax_factor(item["tax"])
        supplier_charge = net_received(item) * as_number(item["buy_price"])
        for party_type, code, amount in (
            ("contractor", item["contractor"], contractor_charge),
            ("supplier", item["supplier"], supplier_charge),
        ):
            if not code:
                continue
            target = parties[party_type][code]
            if item["work_date"] < period_from:
                target["opening"] += amount
            else:
                target["period_charge"] += amount
    for row in conn.execute("SELECT * FROM payments WHERE payment_date<=?", (period_to,)):
        party_type = row["party_type"]
        if party_type not in parties:
            continue
        target = parties[party_type][row["party_code"]]
        if row["payment_date"] < period_from:
            target["opening"] -= row["amount"]
        else:
            target["period_paid"] += row["amount"]
    for row in conn.execute("SELECT * FROM debt_adjustments WHERE adjustment_date<=?", (period_to,)):
        if row["party_type"] not in parties:
            continue
        target = parties[row["party_type"]][row["party_code"]]
        if row["adjustment_date"] < period_from:
            target["opening"] += row["amount"]
        else:
            target["period_adjustment"] += row["amount"]
    for group in parties.values():
        for values in group.values():
            values["closing"] = (
                values["opening"] + values["period_charge"]
                + values["period_adjustment"] - values["period_paid"]
            )
    return {
        "period_from": period_from,
        "period_to": period_to,
        "contractors": dict(parties["contractor"]),
        "suppliers": dict(parties["supplier"]),
    }


def validate_date_range(period_from: str, period_to: str):
    try:
        start = datetime.strptime(period_from, "%Y-%m-%d").date()
        end = datetime.strptime(period_to, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Kỳ công nợ phải dùng ngày hợp lệ dạng YYYY-MM-DD") from None
    if start > end:
        raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")


def style_export_sheet(ws, title: str, subtitle: str, headers: list[str], money_columns=()):
    end_col = max(len(headers), 1)
    ws.insert_rows(1, 2)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=end_col)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end_col)
    ws.cell(1, 1, title)
    ws.cell(2, 1, subtitle)
    ws.cell(1, 1).font = Font(name="Arial", size=16, bold=True, color="FFFFFF")
    ws.cell(1, 1).fill = PatternFill("solid", fgColor="17324D")
    ws.cell(1, 1).alignment = Alignment(horizontal="center")
    ws.cell(2, 1).font = Font(name="Arial", italic=True, color="475569")
    ws.cell(2, 1).alignment = Alignment(horizontal="center")
    for cell in ws[3]:
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="087F73")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in ws.iter_rows(min_row=4):
        for cell in row:
            cell.font = Font(name="Arial", size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for column in money_columns:
        for row in range(4, ws.max_row + 1):
            ws.cell(row, column).number_format = "#,##0"
    ws.freeze_panes = "A4"
    if ws.max_row >= 3:
        ws.auto_filter.ref = f"A3:{get_column_letter(end_col)}{ws.max_row}"
    for index in range(1, end_col + 1):
        values = [str(ws.cell(row, index).value or "") for row in range(3, ws.max_row + 1)]
        width = min(max([len(value) for value in values] + [10]) + 2, 42)
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1


def send_workbook(workbook: Workbook, filename: str):
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def debt_period_workbook(conn, payload: dict):
    period_from = payload["period_from"]
    period_to = payload["period_to"]
    workbook = Workbook()
    for index, (sheet_name, title, items) in enumerate((
        ("Phải thu", "CÔNG NỢ PHẢI THU", payload["contractors"]),
        ("Phải trả", "CÔNG NỢ PHẢI TRẢ", payload["suppliers"]),
    )):
        ws = workbook.active if index == 0 else workbook.create_sheet()
        ws.title = sheet_name
        headers = ["Đối tượng", "Số dư đầu kỳ", "Phát sinh", "Điều chỉnh", "Đã thu/trả", "Số dư cuối kỳ"]
        ws.append(headers)
        for code, values in sorted(items.items()):
            ws.append([
                code,
                values["opening"],
                values["period_charge"],
                values["period_adjustment"],
                values["period_paid"],
                values["closing"],
            ])
        style_export_sheet(
            ws,
            title,
            f"Từ {period_from} đến {period_to} · đầu kỳ + phát sinh + điều chỉnh − đã thu/trả",
            headers,
            money_columns=(2, 3, 4, 5, 6),
        )

    ws = workbook.create_sheet("Thu chi")
    payment_headers = ["Ngày", "Loại", "Nhóm", "Đối tượng", "Số tiền", "Nội dung", "Ngày tạo"]
    ws.append(payment_headers)
    for row in conn.execute(
        "SELECT * FROM payments WHERE payment_date>=? AND payment_date<=? ORDER BY payment_date,id",
        (period_from, period_to),
    ):
        ws.append([
            row["payment_date"],
            "Thu khách hàng" if row["kind"] == "receipt" else "Trả nhà cung cấp",
            "Phải thu" if row["party_type"] == "contractor" else "Phải trả",
            row["party_code"],
            row["amount"],
            row["note"],
            row["created_at"],
        ])
    style_export_sheet(ws, "LỊCH SỬ THU – CHI", f"Từ {period_from} đến {period_to}", payment_headers, (5,))

    ws = workbook.create_sheet("Điều chỉnh")
    adjustment_headers = ["Ngày", "Nhóm", "Đối tượng", "Số điều chỉnh", "Lý do", "Ngày tạo"]
    ws.append(adjustment_headers)
    for row in conn.execute(
        "SELECT * FROM debt_adjustments WHERE adjustment_date>=? AND adjustment_date<=? ORDER BY adjustment_date,id",
        (period_from, period_to),
    ):
        ws.append([
            row["adjustment_date"],
            "Phải thu" if row["party_type"] == "contractor" else "Phải trả",
            row["party_code"],
            row["amount"],
            row["note"],
            row["created_at"],
        ])
    style_export_sheet(ws, "ĐIỀU CHỈNH CÔNG NỢ", f"Từ {period_from} đến {period_to}", adjustment_headers, (4,))
    return workbook


def payroll_workbook(conn, month: str):
    rows = payroll_rows(conn, month)
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Bảng lương"
    headers = [
        "STT", "Mã nhân sự", "Họ tên", "Chức vụ", "Bếp", "Giờ thường", "Tăng ca",
        "Chủ nhật", "Ca đêm", "Ngày lễ", "Phụ cấp", "Trách nhiệm", "Tổng lương",
        "BHXH NLĐ", "Tạm ứng", "Khấu trừ thử việc", "Thực lĩnh", "BHXH công ty",
    ]
    ws.append(headers)
    for index, item in enumerate(rows, 1):
        ws.append([
            index, item["employee_code"], item["full_name"], item["role_name"], item["kitchen"],
            item["normal_hours"], item["overtime_hours"], item["sunday_hours"], item["night_hours"],
            item["holiday_hours"], item["allowance"], item["responsibility"], item["gross_salary"],
            item["bhxh_employee"], item["advance"], item["probation_deduction"], item["net_salary"],
            item["bhxh_company"],
        ])
    style_export_sheet(
        ws,
        f"BẢNG LƯƠNG THÁNG {month}",
        "Công thường · tăng ca · Chủ nhật · ca đêm · ngày lễ · phụ cấp · BHXH · tạm ứng",
        headers,
        money_columns=(11, 12, 13, 14, 15, 16, 17, 18),
    )

    ws = workbook.create_sheet("Chi phí theo bếp")
    labor_headers = ["Bếp", "Chi phí lao động"]
    ws.append(labor_headers)
    for row in conn.execute(
        """SELECT kitchen,SUM(amount) amount FROM kitchen_labor_costs
           WHERE substr(work_date,1,7)=? GROUP BY kitchen ORDER BY kitchen""",
        (month,),
    ):
        ws.append([row["kitchen"], row["amount"]])
    style_export_sheet(ws, f"CHI PHÍ LAO ĐỘNG THÁNG {month}", "Tổng hợp theo bếp", labor_headers, (2,))
    return workbook


def meal_plan_payload(conn, work_date=""):
    params = []
    where = ""
    if work_date:
        where = "WHERE mp.work_date=?"
        params.append(work_date)
    plans = [dict(row) for row in conn.execute(
        f"""SELECT mp.*,COALESCE(NULLIF(mp.unit_code,''),ku.unit_code,'') mapped_unit
             FROM meal_plans mp LEFT JOIN kitchen_units ku ON ku.kitchen_code=mp.kitchen
             {where} ORDER BY mp.work_date DESC,mp.kitchen,mp.shift,mp.id""", params
    )]
    for plan in plans:
        items = [dict(row) for row in conn.execute(
            "SELECT * FROM meal_plan_items WHERE plan_id=? ORDER BY dish_name,product_name", (plan["id"],)
        )]
        for item in items:
            item["required_qty"] = plan["meal_count"] * item["norm_qty"]
            item["cost"] = item["required_qty"] * item["buy_price"]
            if not item.get("applicable_meal_count"):
                item["applicable_meal_count"] = plan["meal_count"]
            if not item.get("source_norm_per_1000"):
                item["source_norm_per_1000"] = item["norm_qty"] * 1000
        plan["items"] = items
        plan["food_cost"] = sum(item["cost"] for item in items)
        plan["revenue"] = plan["meal_count"] * plan.get("meal_price", 0)
        plan["total_cost"] = plan["food_cost"] + plan.get("other_cost", 0)
        plan["profit"] = plan["revenue"] - plan["total_cost"]
        plan["profit_margin"] = plan["profit"] / plan["revenue"] if plan["revenue"] else 0
        plan["cost_per_meal"] = plan["total_cost"] / plan["meal_count"] if plan["meal_count"] else 0
        try:
            plan["source_financials"] = json.loads(plan.get("source_financials_json") or "{}")
        except (TypeError, ValueError):
            plan["source_financials"] = {}
        plan["warnings"] = []
        if not plan["mapped_unit"]:
            plan["warnings"].append("Bếp chưa được ghép XCOM (xưởng cơm)")
        if any(item["buy_price"] <= 0 for item in items):
            plan["warnings"].append("Có nguyên liệu thiếu giá")
        if plan.get("meal_price", 0) <= 0:
            plan["warnings"].append("Chưa có đơn giá suất ăn")
        plan["warnings"].extend(plan["source_financials"].get("warnings") or [])
    return plans


def meal_po_workbook(plans, work_date: str):
    groups = defaultdict(list)
    for plan in plans:
        for item in plan["items"]:
            groups[plan["mapped_unit"] or "CHƯA CÓ XCOM"].append((plan, item))
    wb = Workbook()
    wb.remove(wb.active)
    for unit_code, rows in sorted(groups.items()):
        unique_plans = []
        seen_plans = set()
        for plan, _ in rows:
            if plan["id"] not in seen_plans:
                seen_plans.add(plan["id"])
                unique_plans.append(plan)
        approval_label = "ĐÃ DUYỆT" if all(
            plan["status"] == "approved" for plan in unique_plans
        ) else "BẢN NHÁP"
        title = re.sub(r"[\\/*?:\[\]]", "-", unit_code)[:31]
        ws = wb.create_sheet(title or "PO")
        ws.append([f"PO XƯỞNG CƠM – {approval_label}"])
        ws.merge_cells("A1:L1")
        ws["A1"].font = Font(name="Arial", size=16, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor="17324D")
        ws["A1"].alignment = Alignment(horizontal="center")
        price_sources = sorted({item["price_source"] for _, item in rows if item.get("price_source")})
        ws.append([f"Ngày {work_date}", "", "", f"XCOM {unit_code}", "", "", "",
                   f"Nguồn giá: {', '.join(price_sources)}"])
        for cell in ws[2]:
            cell.font = Font(name="Arial", bold=True)
        ws.append(["STT", "Bếp / ca", "Mã hàng", "Tên nguyên liệu", "ĐVT", "Suất áp dụng",
                   "Định lượng/1.000 suất", "Số lượng cần", "Đơn giá", "Thành tiền", "NCC", "Nguồn giá"])
        for index, (plan, item) in enumerate(rows, 1):
            ws.append([
                index, f"{plan['kitchen']} / {plan['shift']}", item["product_code"], item["product_name"],
                item["unit"], item["applicable_meal_count"], item["source_norm_per_1000"],
                item["required_qty"], item["buy_price"], item["cost"], item["supplier"], item["price_source"],
            ])
        for cell in ws[3]:
            cell.font = Font(name="Arial", bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="087F73")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        detail_end = ws.max_row
        ws.append([])
        ws.append(["TỔNG HỢP SUẤT ĂN / COST"])
        ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=12)
        ws.cell(ws.max_row, 1).font = Font(name="Arial", bold=True, color="FFFFFF")
        ws.cell(ws.max_row, 1).fill = PatternFill("solid", fgColor="17324D")
        ws.cell(ws.max_row, 1).alignment = Alignment(horizontal="center")
        ws.append(["Bếp / ca", "Số thực đơn", "Suất/thực đơn", "Tổng suất", "Đơn giá suất",
                   "Doanh thu", "Chi phí thực phẩm", "Chi phí khác", "Tổng chi", "Lợi nhuận",
                   "Biên lợi nhuận", "Thực đơn"])
        summary_header = ws.max_row
        for plan in unique_plans:
            ws.append([
                f"{plan['kitchen']} / {plan['shift']}", plan.get("menu_count", 1),
                plan.get("servings_per_menu") or plan["meal_count"], plan["meal_count"],
                plan.get("meal_price", 0), plan["revenue"], plan["food_cost"], plan.get("other_cost", 0),
                plan["total_cost"], plan["profit"], plan["profit_margin"], plan.get("note", ""),
            ])
        for cell in ws[summary_header]:
            cell.font = Font(name="Arial", bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="087F73")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.freeze_panes = "A4"
        ws.auto_filter.ref = f"A3:L{detail_end}"
        widths = [7, 20, 14, 30, 10, 14, 20, 15, 14, 16, 16, 32]
        for index, width in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + index)].width = width
        for row in range(4, detail_end + 1):
            for col in (9, 10):
                ws.cell(row, col).number_format = "#,##0"
        for row in range(summary_header + 1, ws.max_row + 1):
            for col in range(5, 11):
                ws.cell(row, col).number_format = "#,##0"
            ws.cell(row, 11).number_format = "0.0%"
    if not wb.sheetnames:
        wb.create_sheet("PO")
    return wb


def employee_code(name: str) -> str:
    text = unicodedata.normalize("NFD", name.upper())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^A-Z0-9]+", "", text)[:30] or "NV"


def import_legacy_attendance(conn, path: Path, source_name: str, now_iso):
    values_book = load_workbook(path, data_only=True, read_only=False)
    attendance_sheet = next(
        (ws for ws in values_book.worksheets if "xưởng cơm" in ws.title.lower()), None
    )
    staff_count = entry_count = labor_count = payroll_override_count = 0
    month = ""
    if attendance_sheet:
        year = int(as_number(attendance_sheet["C2"].value, date.today().year))
        month_num = int(as_number(attendance_sheet["C3"].value, date.today().month))
        month = f"{year:04d}-{month_num:02d}"
        base_salary = 0
        payroll_sheet = next((ws for ws in values_book.worksheets if "lương xưởng" in ws.title.lower()), None)
        if payroll_sheet:
            base_salary = as_number(payroll_sheet["C2"].value)
        for row in range(6, attendance_sheet.max_row + 1):
            name = str(attendance_sheet.cell(row, 2).value or "").strip()
            if not name or name.upper() in {"HỌ& TÊN", "HỌ VÀ TÊN"}:
                continue
            code = employee_code(name)
            conn.execute(
                """INSERT INTO staff(
                    employee_code,full_name,base_salary,standard_days,standard_hours,created_at,updated_at
                ) VALUES(?,?,?,26,8,?,?) ON CONFLICT(employee_code) DO UPDATE SET
                    full_name=excluded.full_name,
                    base_salary=CASE WHEN staff.base_salary<=0 THEN excluded.base_salary ELSE staff.base_salary END,
                    updated_at=excluded.updated_at""",
                (code, name, base_salary, now_iso(), now_iso()),
            )
            staff_id = conn.execute("SELECT id FROM staff WHERE employee_code=?", (code,)).fetchone()["id"]
            staff_count += 1
            overtime_row = row + 1 if row + 1 <= attendance_sheet.max_row and not attendance_sheet.cell(row + 1, 2).value else None
            for day_index, col in enumerate(range(6, 37), start=1):
                try:
                    work_date = date(year, month_num, day_index)
                except ValueError:
                    break
                normal = as_number(attendance_sheet.cell(row, col).value)
                overtime = as_number(attendance_sheet.cell(overtime_row, col).value) if overtime_row else 0
                # Some legacy rows store a VND daily wage in the date cells,
                # not hours. Those amounts are imported from LƯƠNG XƯỞNG below.
                if abs(normal) > 24 or abs(overtime) > 24:
                    continue
                if normal == 0 and overtime == 0:
                    continue
                sunday = work_date.weekday() == 6
                conn.execute(
                    """INSERT INTO attendance_entries(
                        employee_id,work_date,normal_hours,overtime_hours,sunday_hours,night_hours,
                        holiday_hours,note,source,updated_at
                    ) VALUES(?,?,?,?,?,0,0,'',?,?) ON CONFLICT(employee_id,work_date) DO UPDATE SET
                        normal_hours=excluded.normal_hours,overtime_hours=excluded.overtime_hours,
                        sunday_hours=excluded.sunday_hours,source=excluded.source,updated_at=excluded.updated_at""",
                    (staff_id, work_date.isoformat(), 0 if sunday else normal,
                     0 if sunday else overtime, normal + overtime if sunday else 0,
                     source_name, now_iso()),
                )
                entry_count += 1

        if payroll_sheet and month:
            payroll_records = {}
            for row in range(4, payroll_sheet.max_row + 1):
                raw_name = payroll_sheet.cell(row, 2).value
                name = str(raw_name or "").strip()
                if not name or name == "0":
                    continue
                code = employee_code(name)
                next_row = row + 1
                detail_row = row
                if (next_row <= payroll_sheet.max_row
                        and not payroll_sheet.cell(next_row, 1).value
                        and not payroll_sheet.cell(next_row, 2).value
                        and any(as_number(payroll_sheet.cell(next_row, col).value) for col in range(4, 17))):
                    detail_row = next_row
                gross = as_number(payroll_sheet.cell(detail_row, 11).value)
                net = as_number(payroll_sheet.cell(detail_row, 15).value)
                if gross == 0 and net != 0:
                    gross = net
                payroll_records[code] = {
                    "name": name,
                    "role": str(payroll_sheet.cell(row, 3).value or "").strip(),
                    "allowance": as_number(payroll_sheet.cell(detail_row, 9).value),
                    "responsibility": as_number(payroll_sheet.cell(detail_row, 10).value),
                    "advance": as_number(payroll_sheet.cell(detail_row, 12).value),
                    "probation": as_number(payroll_sheet.cell(detail_row, 13).value),
                    "bhxh_employee": as_number(payroll_sheet.cell(detail_row, 14).value),
                    "bhxh_company": as_number(payroll_sheet.cell(detail_row, 16).value),
                    "gross": gross,
                    "net": net,
                }

            # The legacy sheet can carry named supplements below the employee
            # grid, e.g. "Cho chị An". Attach them to the matching person.
            for row in range(4, payroll_sheet.max_row + 1):
                supplement = as_number(payroll_sheet.cell(row, 15).value)
                label = str(payroll_sheet.cell(row, 16).value or "").strip()
                if supplement == 0 or not label.lower().startswith("cho "):
                    continue
                label_code = employee_code(re.sub(r"^cho\s+(chị|anh|em)?\s*", "", label, flags=re.IGNORECASE))
                match = next((key for key in payroll_records if key == label_code or key in label_code or label_code in key), None)
                if match:
                    payroll_records[match]["gross"] += supplement
                    payroll_records[match]["net"] += supplement

            for code, record in payroll_records.items():
                conn.execute(
                    """INSERT INTO staff(
                        employee_code,full_name,role_name,base_salary,standard_days,standard_hours,created_at,updated_at
                    ) VALUES(?,?,?,?,26,8,?,?) ON CONFLICT(employee_code) DO UPDATE SET
                        full_name=excluded.full_name,role_name=excluded.role_name,
                        base_salary=CASE WHEN excluded.base_salary>0 THEN excluded.base_salary ELSE staff.base_salary END,
                        updated_at=excluded.updated_at""",
                    (code, record["name"], record["role"], base_salary, now_iso(), now_iso()),
                )
                staff_id = conn.execute("SELECT id FROM staff WHERE employee_code=?", (code,)).fetchone()["id"]
                conn.execute(
                    """INSERT INTO payroll_adjustments(
                        employee_id,month,allowance,responsibility,advance,probation_deduction,
                        bhxh_employee_amount,bhxh_company_amount,gross_override,net_override,use_override,note,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?) ON CONFLICT(employee_id,month) DO UPDATE SET
                        allowance=excluded.allowance,responsibility=excluded.responsibility,
                        advance=excluded.advance,probation_deduction=excluded.probation_deduction,
                        bhxh_employee_amount=excluded.bhxh_employee_amount,
                        bhxh_company_amount=excluded.bhxh_company_amount,
                        gross_override=excluded.gross_override,net_override=excluded.net_override,
                        use_override=1,note=excluded.note,updated_at=excluded.updated_at""",
                    (staff_id, month, record["allowance"], record["responsibility"], record["advance"],
                     record["probation"], record["bhxh_employee"], record["bhxh_company"],
                     record["gross"], record["net"], f"Nạp từ {source_name}", now_iso()),
                )
                payroll_override_count += 1

    labor_sheet = next((ws for ws in values_book.worksheets if "chấm công chợ" in ws.title.lower()), None)
    if labor_sheet:
        year = int(as_number(labor_sheet["B1"].value, date.today().year))
        month_num = int(as_number(labor_sheet["D1"].value, date.today().month))
        month = month or f"{year:04d}-{month_num:02d}"
        for row in range(4, min(labor_sheet.max_row, 40) + 1):
            raw_date = labor_sheet.cell(row, 1).value
            work_date = as_date(raw_date)
            if not work_date:
                try:
                    work_date = date(year, month_num, row - 3).isoformat()
                except ValueError:
                    continue
            for col in range(3, min(labor_sheet.max_column, 24) + 1):
                kitchen = str(labor_sheet.cell(3, col).value or "").strip().upper()
                amount = as_number(labor_sheet.cell(row, col).value)
                if not kitchen or amount == 0:
                    continue
                conn.execute(
                    """INSERT INTO kitchen_labor_costs(work_date,kitchen,amount,source,updated_at)
                       VALUES(?,?,?,?,?) ON CONFLICT(work_date,kitchen,source) DO UPDATE SET
                       amount=excluded.amount,updated_at=excluded.updated_at""",
                    (work_date, kitchen, amount, source_name, now_iso()),
                )
                labor_count += 1
    values_book.close()
    return {"month": month, "staff": staff_count, "attendance_entries": entry_count,
            "labor_cost_entries": labor_count, "payroll_overrides": payroll_override_count,
            "source": source_name}


def payment_request_document(company: str, recipient: str, requester: str, bank_name: str,
                             bank_account: str, amount: float, period_from: str, period_to: str,
                             details=None):
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(1.7)
    section.bottom_margin = Cm(1.7)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(13)
    header = document.add_table(rows=1, cols=2)
    header.autofit = False
    header.columns[0].width = Cm(8)
    header.columns[1].width = Cm(9)
    left = header.cell(0, 0).paragraphs[0]
    left.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = left.add_run(company.upper())
    run.bold = True
    right = header.cell(0, 1).paragraphs[0]
    right.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = right.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc")
    run.bold = True
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(18)
    title.paragraph_format.space_after = Pt(8)
    run = title.add_run("ĐỀ NGHỊ THANH TOÁN")
    run.bold = True
    run.font.size = Pt(16)
    today = date.today()
    date_line = document.add_paragraph(f"Ngày {today.day:02d} tháng {today.month:02d} năm {today.year}")
    date_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    lines = [
        ("Kính gửi: ", recipient.upper()),
        ("Đơn vị đề nghị: ", company),
        ("Người đại diện: ", requester),
        ("Nội dung: ", f"Đề nghị thanh toán tiền hàng/dịch vụ từ {period_from} đến {period_to}"),
    ]
    for label, value in lines:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(4)
        label_run = paragraph.add_run(label)
        label_run.bold = True
        paragraph.add_run(value)

    detail_rows = details or [{"work_date": f"{period_from} – {period_to}", "amount": amount}]
    detail_table = document.add_table(rows=1, cols=4)
    detail_table.style = "Table Grid"
    detail_table.autofit = False
    widths = (Cm(1.4), Cm(3.2), Cm(8.4), Cm(3.8))
    headers = ("STT", "Ngày", "Nội dung", "Thành tiền (VNĐ)")
    for index, cell in enumerate(detail_table.rows[0].cells):
        cell.width = widths[index]
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(headers[index])
        run.bold = True
    for index, item in enumerate(detail_rows, start=1):
        row_cells = detail_table.add_row().cells
        work_date = str(item.get("work_date") or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", work_date):
            work_date = datetime.strptime(work_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        values = (
            str(index),
            work_date,
            "Tiền hàng/dịch vụ đã giao",
            f"{as_number(item.get('amount')):,.0f}".replace(",", "."),
        )
        for column, value in enumerate(values):
            row_cells[column].width = widths[column]
            paragraph = row_cells[column].paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT if column == 3 else WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run(value)
    total_cells = detail_table.add_row().cells
    total_cells[0].merge(total_cells[2])
    total_label = total_cells[0].paragraphs[0]
    total_label.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = total_label.add_run("TỔNG CỘNG")
    run.bold = True
    total_value = total_cells[3].paragraphs[0]
    total_value.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = total_value.add_run(f"{amount:,.0f}".replace(",", "."))
    run.bold = True

    payment_lines = [
        ("Số tiền bằng chữ: ", number_to_vietnamese(amount) + "./."),
        ("Hình thức thanh toán: ", "Chuyển khoản"),
        ("Đơn vị thụ hưởng: ", company),
        ("Số tài khoản: ", bank_account),
        ("Tại ngân hàng: ", bank_name),
    ]
    for label, value in payment_lines:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(4)
        label_run = paragraph.add_run(label)
        label_run.bold = True
        paragraph.add_run(value)

    closing = document.add_paragraph("Rất mong Quý đơn vị xem xét và thanh toán.\nTrân trọng cảm ơn!")
    closing.paragraph_format.space_after = Pt(8)
    signatures = document.add_table(rows=1, cols=2)
    signatures.autofit = False
    signatures.columns[0].width = Cm(8)
    signatures.columns[1].width = Cm(8)
    for cell, text in zip(signatures.rows[0].cells, (
        "NGƯỜI LẬP\n(Ký, ghi rõ họ tên)",
        "ĐẠI DIỆN CÔNG TY\n(Ký, ghi rõ họ tên, đóng dấu)",
    )):
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(text)
        run.bold = True
    document.add_paragraph("\n\n\n")
    return document
