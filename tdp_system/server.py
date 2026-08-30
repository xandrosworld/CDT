from __future__ import annotations

import io
import json
import os
import re
import socket
import sqlite3
import sys
import threading
import time
import unicodedata
import uuid
import webbrowser
import zipfile
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from waitress import serve
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

try:
    from minvoice_client import MinvoiceClient, MinvoiceConfig, MinvoiceError
except ImportError:  # Allows importing as tdp_system.server in tests/tools.
    from .minvoice_client import MinvoiceClient, MinvoiceConfig, MinvoiceError

try:
    from contract_modules import (
        init_contract_schema,
        inventory_lookup,
        net_delivered,
        net_received,
        post_purchase_list_inventory,
        register_contract_routes,
    )
except ImportError:
    from .contract_modules import (
        init_contract_schema,
        inventory_lookup,
        net_delivered,
        net_received,
        post_purchase_list_inventory,
        register_contract_routes,
    )


FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    ROOT = APP_DIR
    STATIC_DIR = BUNDLE_DIR / "static"
    SHARED_DIR = BUNDLE_DIR / "shared"
    MASTER_SOURCE = BUNDLE_DIR / "Em Thành.xlsx"
else:
    APP_DIR = Path(__file__).resolve().parent
    ROOT = APP_DIR.parent
    STATIC_DIR = APP_DIR / "static"
    SHARED_DIR = ROOT / "demo_tdp"
    MASTER_SOURCE = ROOT / "Em Thành.xlsx"
DATA_DIR = APP_DIR / "data"
EXPORT_DIR = APP_DIR / "exports"
DB_PATH = Path(os.environ.get("TDP_DB_PATH", str(DATA_DIR / "tdp.sqlite3")))

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

NAVY = "17324D"
TEAL = "087F73"
PALE = "F5F8FB"
WHITE = "FFFFFF"
GRAY = "5E7083"
RED = "C2413A"

INVOICE_HEADERS = [
    "NCC", "Ma_Vt", "Ma_Bep", "Ten_Vt", "So_Luong", "Dvt",
    "Don_Gia", "Thanh_Tien", "Thue_GTGT", "Tong_Cong", "CCCD",
]
MASTER_FORMAT_VERSION = "2"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
PENDING_IMPORTS = {}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


def slug(value) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", text)


def number_value(value, default=0.0):
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value).replace("₫", "").replace("đ", "").replace(" ", "")
    if not text:
        return default
    # Vietnamese input commonly uses dot for thousands and comma for decimals.
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return default


def normalize_tax(value):
    text = clean_text(value).upper()
    if text in {"KKKNT", "KHÔNG KÊ KHAI", "KHONG KE KHAI", "K"}:
        return "KKKNT"
    if text.endswith("%"):
        return number_value(text[:-1]) / 100
    num = number_value(value, 0.0)
    if num > 1:
        num /= 100
    return round(num, 4)


def tax_factor(value) -> float:
    return 1.0 if clean_text(value).upper() == "KKKNT" else 1.0 + number_value(value)


def safe_sheet_name(value: str) -> str:
    return re.sub(r"[\\/*?:\[\]]", "-", clean_text(value) or "Sheet")[:31]


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contractors (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_group TEXT,
    pricing_mode TEXT NOT NULL DEFAULT 'group'
);
CREATE TABLE IF NOT EXISTS kitchens (
    code TEXT PRIMARY KEY,
    contractor TEXT,
    name TEXT,
    address TEXT,
    show_price INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS suppliers (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS people (
    name TEXT PRIMARY KEY,
    cccd TEXT,
    issue_date TEXT,
    issue_place TEXT,
    address TEXT
);
CREATE TABLE IF NOT EXISTS products (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT,
    tax TEXT,
    supplier TEXT,
    buy_price REAL NOT NULL DEFAULT 0,
    purchase_list INTEGER NOT NULL DEFAULT 0,
    seller TEXT,
    cccd TEXT
);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE TABLE IF NOT EXISTS product_prices (
    product_code TEXT NOT NULL,
    price_group TEXT NOT NULL,
    price_text TEXT,
    price_value REAL,
    PRIMARY KEY(product_code, price_group)
);
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_date TEXT NOT NULL,
    source_name TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    approved_at TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    work_date TEXT NOT NULL,
    contractor TEXT,
    kitchen TEXT,
    product_code TEXT,
    product_name TEXT,
    qty REAL NOT NULL DEFAULT 0,
    actual_received REAL NOT NULL DEFAULT 0,
    actual_delivered REAL NOT NULL DEFAULT 0,
    unit TEXT,
    supplier TEXT,
    buy_price REAL NOT NULL DEFAULT 0,
    sell_price REAL NOT NULL DEFAULT 0,
    tax TEXT,
    purchase_list INTEGER NOT NULL DEFAULT 0,
    seller TEXT,
    cccd TEXT,
    note TEXT,
    source_sheet TEXT,
    source_row INTEGER,
    errors TEXT NOT NULL DEFAULT '[]',
    warnings TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_batch ON orders(batch_id);
CREATE TABLE IF NOT EXISTS balances (
    party_type TEXT NOT NULL,
    party_code TEXT NOT NULL,
    opening REAL NOT NULL DEFAULT 0,
    PRIMARY KEY(party_type, party_code)
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_date TEXT NOT NULL,
    kind TEXT NOT NULL,
    party_type TEXT NOT NULL,
    party_code TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);
"""


def setting_get(conn, key: str, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def setting_set(conn, key: str, value):
    conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def init_database():
    with db() as conn:
        conn.executescript(SCHEMA)
        init_contract_schema(conn)
        order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
        if "warnings" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN warnings TEXT NOT NULL DEFAULT '[]'")
        defaults = {
            "company": "CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT",
            "purchase_rate": "0.95",
            "master_version": "0",
        }
        for key, value in defaults.items():
            if setting_get(conn, key) is None:
                setting_set(conn, key, value)
    sync_master_if_needed()
    auto_backup()


def auto_backup():
    backup_dir = DATA_DIR / "auto_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    target = backup_dir / f"tdp_{today}.sqlite3"
    if target.exists() or not DB_PATH.exists():
        return
    source = sqlite3.connect(DB_PATH)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    backups = sorted(backup_dir.glob("tdp_*.sqlite3"), key=lambda path: path.name, reverse=True)
    for old in backups[14:]:
        old.unlink()


def sync_master_if_needed(force=False):
    if not MASTER_SOURCE.exists():
        return
    version = f"{MASTER_FORMAT_VERSION}-{int(MASTER_SOURCE.stat().st_mtime)}"
    with db() as conn:
        if not force and setting_get(conn, "master_version") == version:
            return

    wb = load_workbook(MASTER_SOURCE, data_only=True, read_only=False)
    with db() as conn:
        # People / CCCD
        if "CCCD" in wb.sheetnames:
            ws = wb["CCCD"]
            for row in range(2, ws.max_row + 1):
                name = clean_text(ws.cell(row, 2).value)
                if not name:
                    continue
                issue = ws.cell(row, 4).value
                issue_date = issue.strftime("%d/%m/%Y") if isinstance(issue, datetime) else clean_text(issue)
                conn.execute(
                    "INSERT INTO people(name,cccd,issue_date,issue_place,address) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(name) DO UPDATE SET cccd=excluded.cccd,issue_date=excluded.issue_date,"
                    "issue_place=excluded.issue_place",
                    (name, clean_text(ws.cell(row, 3).value), issue_date,
                     clean_text(ws.cell(row, 5).value), "Hải Phòng"),
                )

        # Contractor and kitchen mapping.
        if "T.chiếu" in wb.sheetnames:
            ws = wb["T.chiếu"]
            for row in range(3, ws.max_row + 1):
                contractor = clean_text(ws.cell(row, 2).value).upper()
                kitchen = clean_text(ws.cell(row, 3).value).upper()
                if not kitchen:
                    continue
                if contractor:
                    mode = "daily" if contractor in {"GIANHAPTAY", "YLKHAN"} else "group"
                    conn.execute(
                        "INSERT INTO contractors(code,name,price_group,pricing_mode) VALUES(?,?,?,?) "
                        "ON CONFLICT(code) DO UPDATE SET name=excluded.name",
                        (contractor, contractor, contractor, mode),
                    )
                conn.execute(
                    "INSERT INTO kitchens(code,contractor,name,address,show_price) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(code) DO UPDATE SET contractor=excluded.contractor,name=excluded.name,"
                    "address=excluded.address",
                    (kitchen, contractor, clean_text(ws.cell(row, 4).value) or kitchen,
                     clean_text(ws.cell(row, 5).value), 1 if kitchen == "NHUAHP" else 0),
                )

        # Product catalog, supplier and all price groups.
        if "BÁO GIÁ" in wb.sheetnames:
            ws = wb["BÁO GIÁ"]
            price_cols = {}
            # Only columns L:R are the seven real selling-price groups.
            # Columns after R repeat group names for margin calculations.
            for col in range(12, min(ws.max_column, 18) + 1):
                header = clean_text(ws.cell(2, col).value).upper()
                if header and not header.startswith("=") and slug(header) not in {"them"}:
                    price_cols[col] = header
                    mode = "daily" if header in {"GIANHAPTAY", "YLKHAN"} else "group"
                    conn.execute(
                        "INSERT INTO contractors(code,name,price_group,pricing_mode) VALUES(?,?,?,?) "
                        "ON CONFLICT(code) DO NOTHING",
                        (header, header, header, mode),
                    )
            for row in range(4, ws.max_row + 1):
                code = clean_text(ws.cell(row, 3).value).upper()
                name = clean_text(ws.cell(row, 4).value)
                if not code or not name:
                    continue
                supplier = clean_text(ws.cell(row, 6).value)
                seller = clean_text(ws.cell(row, 9).value)
                cccd_row = conn.execute("SELECT cccd FROM people WHERE name=?", (seller,)).fetchone()
                cccd = cccd_row["cccd"] if cccd_row else ""
                if supplier:
                    conn.execute(
                        "INSERT INTO suppliers(code,name) VALUES(?,?) ON CONFLICT(code) DO NOTHING",
                        (supplier, supplier),
                    )
                conn.execute(
                    "INSERT INTO products(code,name,unit,tax,supplier,buy_price,purchase_list,seller,cccd) "
                    "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET "
                    "name=excluded.name,unit=excluded.unit,tax=excluded.tax,"
                    "supplier=COALESCE(NULLIF(products.supplier,''),excluded.supplier),"
                    "buy_price=CASE WHEN excluded.buy_price>0 THEN excluded.buy_price ELSE products.buy_price END,"
                    "purchase_list=excluded.purchase_list,seller=excluded.seller,cccd=excluded.cccd",
                    (code, name, clean_text(ws.cell(row, 10).value),
                     clean_text(normalize_tax(ws.cell(row, 11).value)), supplier,
                     number_value(ws.cell(row, 5).value), 1 if slug(ws.cell(row, 8).value) == "bk" else 0,
                     seller, cccd),
                )
                for col, group in price_cols.items():
                    raw = ws.cell(row, col).value
                    text = clean_text(raw)
                    value = number_value(raw, None) if isinstance(raw, (int, float)) else None
                    conn.execute(
                        "INSERT INTO product_prices(product_code,price_group,price_text,price_value) VALUES(?,?,?,?) "
                        "ON CONFLICT(product_code,price_group) DO UPDATE SET "
                        "price_text=excluded.price_text,price_value=excluded.price_value",
                        (code, group, text, value),
                    )
        setting_set(conn, "master_version", version)
        setting_set(conn, "master_synced_at", now_iso())


def rows_dict(cursor):
    return [dict(row) for row in cursor.fetchall()]


def product_lookup(conn):
    by_code = {}
    by_name = defaultdict(list)
    for row in conn.execute("SELECT * FROM products"):
        item = dict(row)
        by_code[item["code"].upper()] = item
        by_name[slug(item["name"])].append(item)
    return by_code, by_name


def get_sell_price(conn, product_code: str, contractor: str):
    contractor_row = conn.execute(
        "SELECT price_group,pricing_mode FROM contractors WHERE code=?", (contractor,)
    ).fetchone()
    if not contractor_row or contractor_row["pricing_mode"] == "daily":
        return 0.0, "Giá theo ngày: cần nhập giá bán"
    row = conn.execute(
        "SELECT price_text,price_value FROM product_prices WHERE product_code=? AND price_group=?",
        (product_code, contractor_row["price_group"] or contractor),
    ).fetchone()
    if not row:
        return 0.0, "Chưa có giá cho nhóm nhà thầu"
    if row["price_value"] is not None and row["price_value"] > 0:
        return float(row["price_value"]), ""
    text = clean_text(row["price_text"])
    return 0.0, text or "Chưa có giá cho nhóm nhà thầu"


HEADER_ALIASES = {
    "contractor": {"nhathau", "nhomkhachhang"},
    "supplier": {"ncc", "nhacungcap", "chon ncc", "chonncc"},
    "product_code": {"mahang", "mavt", "mavattu"},
    "kitchen": {"mabep", "tenbepormabep"},
    "product_name": {"tenhang", "tenvt", "tenhanghoa", "tenthanhdatphat"},
    "qty": {"khoiluong", "soluong", "sldat", "sl"},
    "unit": {"dvt", "donvitinh"},
    "buy_price": {"giamua", "dongiamua"},
    "sell_price": {"giaban", "dongia", "dongiaban"},
    "tax": {"thue", "thuegtgt", "thuesuat"},
    "cccd": {"cccd", "socmtnhandan", "socccd"},
    "date": {"ngaythang", "ngay", "ngaygiao"},
    "note": {"ghichu", "ghichudathang"},
    "seller": {"tenlambangke", "nguoiban"},
    "purchase_list": {"bangke", "bk"},
    "actual_received": {"thucnhan", "soluongthucnhan"},
    "actual_delivered": {"thucgiao", "soluongthucgiao"},
    "damaged_qty": {"hanghong", "soluonghong", "slhong"},
    "supplier_return_qty": {"trancc", "tranhacungcap", "soluongtrancc"},
    "customer_return_qty": {"khachtra", "khachhangtra", "soluongkhachtra"},
}


def canonical_header(value):
    key = slug(value)
    for field, aliases in HEADER_ALIASES.items():
        if key in {slug(x) for x in aliases}:
            return field
    text = clean_text(value).lower()
    if "tên hàng" in text:
        return "product_name"
    if "khối" in text and "lượng" in text:
        return "qty"
    if "giá bán" in text:
        return "sell_price"
    if "giá mua" in text:
        return "buy_price"
    if "thuế" in text:
        return "tax"
    return None


def detect_header(ws):
    best = None
    for row in range(1, min(ws.max_row, 15) + 1):
        mapping = {}
        for col in range(1, min(ws.max_column, 40) + 1):
            field = canonical_header(ws.cell(row, col).value)
            if field and field not in mapping:
                mapping[field] = col
        score = sum(key in mapping for key in ("product_name", "qty", "kitchen", "product_code"))
        score += min(len(mapping), 8) / 10
        if best is None or score > best[0]:
            best = (score, row, mapping)
    if not best or best[0] < 2:
        return None, {}
    mapping = best[2]
    required = "qty" in mapping and "kitchen" in mapping and (
        "product_name" in mapping or "product_code" in mapping
    )
    if not required:
        return None, {}
    return best[1], mapping


def display_date(value, fallback: str):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    text = clean_text(value)
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return fallback


def resolve_order(conn, raw: dict, fallback_date: str, by_code, by_name):
    code = clean_text(raw.get("product_code")).upper()
    name = clean_text(raw.get("product_name"))
    product = by_code.get(code)
    if not product and name:
        matches = by_name.get(slug(name), [])
        if len(matches) == 1:
            product = matches[0]
            code = product["code"]
    if product and not name:
        name = product["name"]

    kitchen = clean_text(raw.get("kitchen")).upper()
    contractor = clean_text(raw.get("contractor")).upper()
    kitchen_row = conn.execute("SELECT * FROM kitchens WHERE code=?", (kitchen,)).fetchone()
    if not contractor and kitchen_row:
        contractor = clean_text(kitchen_row["contractor"]).upper()

    supplier = clean_text(raw.get("supplier"))
    if supplier.lower() in {"-", "kiểm tra", "chon ncc", "chọn ncc"}:
        supplier = ""
    if not supplier and product:
        supplier = clean_text(product["supplier"])

    qty = number_value(raw.get("qty"))
    actual_received = number_value(raw.get("actual_received"), qty)
    actual_delivered = number_value(raw.get("actual_delivered"), qty)
    damaged_qty = max(number_value(raw.get("damaged_qty")), 0)
    supplier_return_qty = max(number_value(raw.get("supplier_return_qty")), 0)
    customer_return_qty = max(number_value(raw.get("customer_return_qty")), 0)
    unit = clean_text(raw.get("unit")) or (clean_text(product["unit"]) if product else "")
    buy_price = number_value(raw.get("buy_price"))
    if buy_price <= 0 and product:
        buy_price = number_value(product["buy_price"])
    sell_price = number_value(raw.get("sell_price"))
    price_message = ""
    if sell_price <= 0 and code and contractor:
        sell_price, price_message = get_sell_price(conn, code, contractor)
    tax = clean_text(normalize_tax(raw.get("tax")))
    if tax in {"", "0.0"} and product:
        tax = clean_text(product["tax"])
    if not tax:
        tax = "KKKNT"

    purchase_list_raw = clean_text(raw.get("purchase_list")).lower()
    purchase_list = 1 if purchase_list_raw in {"bk", "x", "1", "true", "có", "co"} else 0
    if product and raw.get("purchase_list") in (None, ""):
        purchase_list = int(product["purchase_list"] or 0)
    seller = clean_text(raw.get("seller")) or (clean_text(product["seller"]) if product else "")
    cccd = clean_text(raw.get("cccd")) or (clean_text(product["cccd"]) if product else "")

    errors = []
    warnings = []
    if buy_price <= 0 and sell_price > 0 and (supplier.lower() == "bk" or purchase_list):
        rate = number_value(setting_get(conn, "purchase_rate", "0.95"), 0.95)
        buy_price = round(sell_price * rate)
        warnings.append(f"Giá mua tạm tính {rate:.0%} giá bán – cần xác nhận")
    if not kitchen:
        errors.append("Thiếu mã bếp")
    elif not kitchen_row:
        errors.append("Mã bếp chưa có trong danh mục")
    if not contractor:
        errors.append("Chưa xác định nhà thầu")
    if not code:
        errors.append("Chưa tìm thấy mã hàng")
    if not name:
        errors.append("Thiếu tên hàng")
    if qty <= 0:
        errors.append("Số lượng phải lớn hơn 0")
    if not supplier:
        errors.append("Thiếu nhà cung cấp")
    if buy_price <= 0:
        errors.append("Thiếu giá mua")
    if sell_price <= 0:
        errors.append(price_message or "Thiếu giá bán")
    if sell_price > 0 and buy_price > sell_price:
        warnings.append("Giá bán thấp hơn giá mua – cần xác nhận bán lỗ")
    if purchase_list and not cccd:
        errors.append("Hàng bảng kê thiếu CCCD")
    if damaged_qty + supplier_return_qty > actual_received:
        errors.append("Hàng hỏng + trả NCC không được vượt số thực nhận")
    if customer_return_qty > actual_delivered:
        errors.append("Khách trả không được vượt số thực giao")

    return {
        "work_date": display_date(raw.get("date"), fallback_date),
        "contractor": contractor,
        "kitchen": kitchen,
        "product_code": code,
        "product_name": name,
        "qty": qty,
        "actual_received": actual_received,
        "actual_delivered": actual_delivered,
        "damaged_qty": damaged_qty,
        "supplier_return_qty": supplier_return_qty,
        "customer_return_qty": customer_return_qty,
        "unit": unit,
        "supplier": supplier,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "tax": tax,
        "purchase_list": purchase_list,
        "seller": seller,
        "cccd": cccd,
        "note": clean_text(raw.get("note")),
        "errors": errors,
        "warnings": warnings,
    }


def parse_workbook(path: Path, fallback_date: str, selected_sheets=None):
    wb = load_workbook(path, data_only=True, read_only=False)
    parsed = []
    skipped_sheets = []
    selected = set(selected_sheets) if selected_sheets else None
    with db() as conn:
        by_code, by_name = product_lookup(conn)
        for ws in wb.worksheets:
            if selected is not None and ws.title not in selected:
                continue
            header_row, mapping = detect_header(ws)
            if not header_row:
                skipped_sheets.append(ws.title)
                continue
            sheet_count = 0
            empty_run = 0
            for row in range(header_row + 1, ws.max_row + 1):
                raw = {field: ws.cell(row, col).value for field, col in mapping.items()}
                identity = [
                    raw.get("product_name"), raw.get("product_code"),
                    raw.get("kitchen"), raw.get("qty"),
                ]
                if not any(value not in (None, "") for value in identity):
                    empty_run += 1
                    if empty_run > 200:
                        break
                    continue
                empty_run = 0
                # Formula-filled template rows and zero-quantity lines are not orders.
                if number_value(raw.get("qty")) <= 0:
                    continue
                order = resolve_order(conn, raw, fallback_date, by_code, by_name)
                order["source_sheet"] = ws.title
                order["source_row"] = row
                parsed.append(order)
                sheet_count += 1
            if sheet_count == 0:
                skipped_sheets.append(ws.title)
    return parsed, skipped_sheets


def analyze_workbook(path: Path):
    wb = load_workbook(path, data_only=True, read_only=False)
    candidates = []
    for ws in wb.worksheets:
        header_row, mapping = detect_header(ws)
        if not header_row:
            continue
        count = 0
        empty_run = 0
        for row in range(header_row + 1, ws.max_row + 1):
            values = [
                ws.cell(row, mapping[key]).value
                for key in ("product_name", "product_code", "kitchen", "qty")
                if key in mapping
            ]
            if not any(value not in (None, "") for value in values):
                empty_run += 1
                if empty_run > 200:
                    break
                continue
            empty_run = 0
            if number_value(ws.cell(row, mapping["qty"]).value) > 0:
                count += 1
        if count:
            candidates.append({
                "name": ws.title,
                "rows": count,
                "headerRow": header_row,
                "fields": sorted(mapping),
            })
    return candidates


def save_imported_batch(conn, orders, work_date, source_name):
    cur = conn.execute(
        "INSERT INTO batches(work_date,source_name,status,created_at) VALUES(?,?,?,?)",
        (work_date, source_name, "draft", now_iso()),
    )
    batch_id = cur.lastrowid
    for item in orders:
        conn.execute(
            """INSERT INTO orders(
                batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                actual_received,actual_delivered,damaged_qty,supplier_return_qty,customer_return_qty,
                unit,supplier,buy_price,sell_price,tax,
                purchase_list,seller,cccd,note,source_sheet,source_row,errors,warnings,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, item["work_date"], item["contractor"], item["kitchen"],
                item["product_code"], item["product_name"], item["qty"],
                item["actual_received"], item["actual_delivered"], item["damaged_qty"],
                item["supplier_return_qty"], item["customer_return_qty"], item["unit"],
                item["supplier"], item["buy_price"], item["sell_price"], item["tax"],
                item["purchase_list"], item["seller"], item["cccd"], item["note"],
                item["source_sheet"], item["source_row"],
                json.dumps(item["errors"], ensure_ascii=False),
                json.dumps(item["warnings"], ensure_ascii=False), now_iso(),
            ),
        )
    return batch_id


def validate_existing_order(conn, item: dict):
    raw = dict(item)
    resolved = resolve_order(conn, raw, item.get("work_date") or date.today().isoformat(),
                             *product_lookup(conn))
    return resolved["errors"]


ORDER_FIELDS = {
    "work_date", "contractor", "kitchen", "product_code", "product_name", "qty",
    "actual_received", "actual_delivered", "unit", "supplier", "buy_price",
    "sell_price", "tax", "purchase_list", "seller", "cccd", "note",
    "damaged_qty", "supplier_return_qty", "customer_return_qty",
}


def order_totals(order):
    revenue = net_delivered(order) * number_value(order["sell_price"])
    cost = net_received(order) * number_value(order["buy_price"])
    total = revenue * tax_factor(order["tax"])
    return revenue, cost, revenue - cost, total


def batch_payload(conn, batch_id=None):
    if batch_id is None:
        batch = conn.execute("SELECT * FROM batches ORDER BY id DESC LIMIT 1").fetchone()
    else:
        batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        return {"batch": None, "orders": [], "summary": calculate_summary(conn, [])}
    orders = rows_dict(conn.execute("SELECT * FROM orders WHERE batch_id=? ORDER BY id", (batch["id"],)))
    for item in orders:
        item["errors"] = json.loads(item["errors"] or "[]")
        item["warnings"] = json.loads(item["warnings"] or "[]")
        revenue, cost, profit, total = order_totals(item)
        item.update(revenue=revenue, cost=cost, profit=profit, total=total)
    return {"batch": dict(batch), "orders": orders, "summary": calculate_summary(conn, orders)}


def calculate_summary(conn, orders):
    contractors = defaultdict(lambda: {
        "revenue": 0, "cost": 0, "profit": 0, "total": 0,
        "opening": 0, "paid": 0, "balance": 0,
    })
    kitchens = defaultdict(lambda: {
        "contractor": "", "revenue": 0, "total": 0, "paid": 0, "balance": 0,
    })
    suppliers = defaultdict(lambda: {
        "cost": 0, "opening": 0, "paid": 0, "balance": 0, "lines": 0,
    })
    totals = {"revenue": 0, "cost": 0, "profit": 0, "total": 0, "errors": 0, "warnings": 0}
    for item in orders:
        revenue, cost, profit, total = order_totals(item)
        totals["revenue"] += revenue
        totals["cost"] += cost
        totals["profit"] += profit
        totals["total"] += total
        totals["errors"] += 1 if item.get("errors") else 0
        totals["warnings"] += 1 if item.get("warnings") else 0
        c = contractors[item["contractor"] or "CHƯA XÁC ĐỊNH"]
        c["revenue"] += revenue
        c["cost"] += cost
        c["profit"] += profit
        c["total"] += total
        k = kitchens[item["kitchen"] or "CHƯA XÁC ĐỊNH"]
        k["contractor"] = item["contractor"]
        k["revenue"] += revenue
        k["total"] += total
        s = suppliers[item["supplier"] or "CHƯA XÁC ĐỊNH"]
        s["cost"] += cost
        s["lines"] += 1

    for row in conn.execute("SELECT * FROM balances"):
        if row["party_type"] == "contractor":
            contractors[row["party_code"]]["opening"] = row["opening"]
        elif row["party_type"] == "supplier":
            suppliers[row["party_code"]]["opening"] = row["opening"]
    for row in conn.execute("SELECT * FROM payments"):
        if row["kind"] == "receipt":
            contractors[row["party_code"]]["paid"] += row["amount"]
        elif row["kind"] == "payment":
            suppliers[row["party_code"]]["paid"] += row["amount"]
    for values in contractors.values():
        values["balance"] = values["opening"] + values["total"] - values["paid"]
    for values in suppliers.values():
        values["balance"] = values["opening"] + values["cost"] - values["paid"]
    return {
        "totals": totals,
        "contractors": dict(contractors),
        "kitchens": dict(kitchens),
        "suppliers": dict(suppliers),
    }


@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        return jsonify({"ok": False, "error": error.description}), error.code
    app.logger.exception("Unhandled error")
    return jsonify({"ok": False, "error": str(error)}), 500


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/favicon.ico")
def favicon():
    return Response(status=204)


@app.get("/shared/<path:name>")
def shared_asset(name):
    return send_from_directory(SHARED_DIR, name)


@app.get("/health")
def health():
    return jsonify({"ok": True, "time": now_iso(), "database": str(DB_PATH)})


def create_minvoice_client():
    config = MinvoiceConfig.from_env_files([
        ROOT / ".env",
        APP_DIR / ".env",
    ])
    return MinvoiceClient(config)


@app.get("/api/minvoice/status")
def api_minvoice_status():
    """Verify M-Invoice without creating, signing or changing any remote invoice."""
    try:
        client = create_minvoice_client()
        account = client.profile_status()
        outgoing = client.outgoing_summary()
        return jsonify({
            "ok": True,
            "connected": True,
            "account": account,
            "outgoing": outgoing,
            "incoming": {
                "available": False,
                "requires": "mSMI OpenAPI",
                "reason": "Tài khoản/cổng phát hành M-Invoice hiện tại không cung cấp hóa đơn đầu vào từ Tổng cục Thuế.",
            },
            "read_only": True,
            "official_api": True,
        })
    except MinvoiceError as error:
        return jsonify({"ok": False, "connected": False, "error": str(error), "read_only": True}), 502


@app.get("/api/bootstrap")
def api_bootstrap():
    with db() as conn:
        payload = batch_payload(conn, request.args.get("batch_id", type=int))
        payload["batches"] = rows_dict(conn.execute("SELECT * FROM batches ORDER BY id DESC LIMIT 100"))
        payload["master"] = {
            "contractors": rows_dict(conn.execute("SELECT * FROM contractors ORDER BY code")),
            "kitchens": rows_dict(conn.execute("SELECT * FROM kitchens ORDER BY code")),
            "suppliers": rows_dict(conn.execute("SELECT * FROM suppliers ORDER BY code")),
            "product_count": conn.execute("SELECT COUNT(*) n FROM products").fetchone()["n"],
            "settings": {row["key"]: row["value"] for row in conn.execute("SELECT * FROM settings")},
        }
        payload["payments"] = rows_dict(conn.execute("SELECT * FROM payments ORDER BY payment_date DESC,id DESC LIMIT 100"))
        payload["ok"] = True
        return jsonify(payload)


@app.post("/api/import")
def api_import():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "Chưa chọn file Excel"}), 400
    if Path(upload.filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
    work_date = request.form.get("work_date") or date.today().isoformat()
    temp = DATA_DIR / f"import_{int(time.time() * 1000)}_{secure_filename(upload.filename)}"
    upload.save(temp)
    try:
        orders, skipped = parse_workbook(temp, work_date)
    finally:
        try:
            temp.unlink()
        except OSError:
            pass
    if not orders:
        return jsonify({
            "ok": False,
            "error": "Không tìm thấy bảng đơn hàng. File cần có các cột Tên hàng, Số lượng và Mã bếp/Mã hàng.",
            "skippedSheets": skipped,
        }), 400
    with db() as conn:
        batch_id = save_imported_batch(conn, orders, work_date, upload.filename)
        payload = batch_payload(conn, batch_id)
        payload.update(ok=True, skippedSheets=skipped)
        return jsonify(payload)


@app.post("/api/import/analyze")
def api_import_analyze():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "Chưa chọn file Excel"}), 400
    if Path(upload.filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
    # Clear abandoned pending uploads older than one hour.
    cutoff = time.time() - 3600
    for old_token, item in list(PENDING_IMPORTS.items()):
        if item["created"] < cutoff:
            try:
                item["path"].unlink()
            except OSError:
                pass
            PENDING_IMPORTS.pop(old_token, None)
    token = uuid.uuid4().hex
    suffix = Path(upload.filename).suffix.lower()
    temp = DATA_DIR / f"pending_{token}{suffix}"
    upload.save(temp)
    try:
        sheets = analyze_workbook(temp)
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise
    if not sheets:
        temp.unlink(missing_ok=True)
        return jsonify({
            "ok": False,
            "error": "Không tìm thấy sheet đơn hàng có Mã bếp, Tên/Mã hàng và Số lượng.",
        }), 400
    PENDING_IMPORTS[token] = {
        "path": temp,
        "name": upload.filename,
        "created": time.time(),
    }
    return jsonify({"ok": True, "token": token, "filename": upload.filename, "sheets": sheets})


@app.post("/api/import/confirm")
def api_import_confirm():
    body = request.get_json(force=True) or {}
    token = clean_text(body.get("token"))
    pending = PENDING_IMPORTS.pop(token, None)
    if not pending or not pending["path"].exists():
        return jsonify({"ok": False, "error": "Phiên chọn sheet đã hết hạn. Vui lòng chọn lại file."}), 400
    sheets = body.get("sheets") or []
    work_date = body.get("work_date") or date.today().isoformat()
    if not sheets:
        PENDING_IMPORTS[token] = pending
        return jsonify({"ok": False, "error": "Cần chọn ít nhất một sheet"}), 400
    try:
        orders, skipped = parse_workbook(pending["path"], work_date, sheets)
    finally:
        try:
            pending["path"].unlink()
        except OSError:
            pass
    if not orders:
        return jsonify({"ok": False, "error": "Các sheet đã chọn không có dòng đơn hợp lệ"}), 400
    with db() as conn:
        batch_id = save_imported_batch(conn, orders, work_date, pending["name"])
        payload = batch_payload(conn, batch_id)
        payload.update(ok=True, skippedSheets=skipped)
        return jsonify(payload)


@app.post("/api/batches")
def api_create_batch():
    body = request.get_json(force=True) or {}
    work_date = body.get("work_date") or date.today().isoformat()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO batches(work_date,source_name,status,created_at) VALUES(?,?,?,?)",
            (work_date, "Nhập tay", "draft", now_iso()),
        )
        return jsonify({"ok": True, **batch_payload(conn, cur.lastrowid)})


@app.post("/api/batches/<int:batch_id>/approve")
def api_approve_batch(batch_id):
    with db() as conn:
        bad = conn.execute(
            "SELECT COUNT(*) n FROM orders WHERE batch_id=? AND errors!='[]'", (batch_id,)
        ).fetchone()["n"]
        total = conn.execute("SELECT COUNT(*) n FROM orders WHERE batch_id=?", (batch_id,)).fetchone()["n"]
        if total == 0:
            return jsonify({"ok": False, "error": "Đơn đang trống"}), 400
        if bad:
            return jsonify({"ok": False, "error": f"Còn {bad} dòng lỗi cần xử lý"}), 400
        conn.execute(
            "UPDATE batches SET status='approved',approved_at=? WHERE id=?",
            (now_iso(), batch_id),
        )
        post_purchase_list_inventory(conn, batch_id, now_iso)
        return jsonify({"ok": True, **batch_payload(conn, batch_id)})


@app.post("/api/orders")
def api_add_order():
    body = request.get_json(force=True) or {}
    batch_id = int(body.get("batch_id") or 0)
    with db() as conn:
        batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
        resolved = resolve_order(conn, body, batch["work_date"], *product_lookup(conn))
        cur = conn.execute(
            """INSERT INTO orders(
                batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                actual_received,actual_delivered,damaged_qty,supplier_return_qty,customer_return_qty,
                unit,supplier,buy_price,sell_price,tax,
                purchase_list,seller,cccd,note,source_sheet,source_row,errors,warnings,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, resolved["work_date"], resolved["contractor"], resolved["kitchen"],
                resolved["product_code"], resolved["product_name"], resolved["qty"],
                resolved["actual_received"], resolved["actual_delivered"], resolved["damaged_qty"],
                resolved["supplier_return_qty"], resolved["customer_return_qty"], resolved["unit"],
                resolved["supplier"], resolved["buy_price"], resolved["sell_price"], resolved["tax"],
                resolved["purchase_list"], resolved["seller"], resolved["cccd"], resolved["note"],
                "Nhập tay", 0, json.dumps(resolved["errors"], ensure_ascii=False),
                json.dumps(resolved["warnings"], ensure_ascii=False), now_iso(),
            ),
        )
        conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?", (batch_id,))
        return jsonify({"ok": True, "id": cur.lastrowid, **batch_payload(conn, batch_id)})


@app.post("/api/orders/bulk")
def api_add_orders_bulk():
    body = request.get_json(force=True) or {}
    batch_id = int(body.get("batch_id") or 0)
    text = clean_text(body.get("text"))
    if not text:
        return jsonify({"ok": False, "error": "Chưa có dữ liệu để dán"}), 400
    lines = [line for line in text.splitlines() if line.strip()]
    matrix = [[cell.strip() for cell in line.split("\t")] for line in lines]
    if not matrix:
        return jsonify({"ok": False, "error": "Không đọc được dữ liệu đã dán"}), 400

    header = {}
    for idx, value in enumerate(matrix[0]):
        field = canonical_header(value)
        if field and field not in header:
            header[field] = idx
    if len(header) >= 2:
        data_rows = matrix[1:]
    else:
        # Simple paste order: bếp, tên hàng, số lượng, NCC, giá mua, giá bán, thuế, ghi chú.
        fields = ["kitchen", "product_name", "qty", "supplier", "buy_price", "sell_price", "tax", "note"]
        header = {field: idx for idx, field in enumerate(fields)}
        data_rows = matrix

    with db() as conn:
        batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
        by_code, by_name = product_lookup(conn)
        inserted = 0
        for cells in data_rows:
            raw = {
                field: cells[idx] if idx < len(cells) else ""
                for field, idx in header.items()
            }
            if not any(clean_text(raw.get(key)) for key in ("product_name", "product_code", "kitchen")):
                continue
            resolved = resolve_order(conn, raw, batch["work_date"], by_code, by_name)
            conn.execute(
                """INSERT INTO orders(
                    batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                    actual_received,actual_delivered,damaged_qty,supplier_return_qty,customer_return_qty,
                    unit,supplier,buy_price,sell_price,tax,
                    purchase_list,seller,cccd,note,source_sheet,source_row,errors,warnings,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    batch_id, resolved["work_date"], resolved["contractor"], resolved["kitchen"],
                    resolved["product_code"], resolved["product_name"], resolved["qty"],
                    resolved["actual_received"], resolved["actual_delivered"], resolved["damaged_qty"],
                    resolved["supplier_return_qty"], resolved["customer_return_qty"], resolved["unit"],
                    resolved["supplier"], resolved["buy_price"], resolved["sell_price"], resolved["tax"],
                    resolved["purchase_list"], resolved["seller"], resolved["cccd"], resolved["note"],
                    "Dán từ Excel", inserted + 1,
                    json.dumps(resolved["errors"], ensure_ascii=False),
                    json.dumps(resolved["warnings"], ensure_ascii=False), now_iso(),
                ),
            )
            inserted += 1
        if inserted == 0:
            return jsonify({"ok": False, "error": "Không có dòng hợp lệ để thêm"}), 400
        conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?", (batch_id,))
        payload = batch_payload(conn, batch_id)
        payload.update(ok=True, inserted=inserted)
        return jsonify(payload)


@app.put("/api/orders/<int:order_id>")
def api_update_order(order_id):
    body = request.get_json(force=True) or {}
    with db() as conn:
        current = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not current:
            return jsonify({"ok": False, "error": "Không tìm thấy dòng đơn"}), 404
        item = dict(current)
        for key in ORDER_FIELDS:
            if key in body:
                item[key] = body[key]
        resolved = resolve_order(
            conn, item, item.get("work_date") or date.today().isoformat(), *product_lookup(conn)
        )
        for key in ORDER_FIELDS:
            if key in resolved:
                item[key] = resolved[key]
        errors = resolved["errors"]
        warnings = resolved["warnings"]
        columns = [
            "work_date", "contractor", "kitchen", "product_code", "product_name", "qty",
            "actual_received", "actual_delivered", "unit", "supplier", "buy_price",
            "sell_price", "tax", "purchase_list", "seller", "cccd", "note",
            "damaged_qty", "supplier_return_qty", "customer_return_qty",
        ]
        conn.execute(
            f"UPDATE orders SET {','.join(f'{col}=?' for col in columns)},errors=?,warnings=?,updated_at=? WHERE id=?",
            tuple(item[col] for col in columns) + (
                json.dumps(errors, ensure_ascii=False),
                json.dumps(warnings, ensure_ascii=False), now_iso(), order_id
            ),
        )
        conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?", (current["batch_id"],))
        return jsonify({"ok": True, **batch_payload(conn, current["batch_id"])})


@app.delete("/api/orders/<int:order_id>")
def api_delete_order(order_id):
    with db() as conn:
        current = conn.execute("SELECT batch_id FROM orders WHERE id=?", (order_id,)).fetchone()
        if not current:
            return jsonify({"ok": False, "error": "Không tìm thấy dòng đơn"}), 404
        conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
        conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?", (current["batch_id"],))
        return jsonify({"ok": True, **batch_payload(conn, current["batch_id"])})


@app.post("/api/payments")
def api_payment():
    body = request.get_json(force=True) or {}
    required = ["payment_date", "kind", "party_type", "party_code", "amount"]
    if any(body.get(key) in (None, "") for key in required):
        return jsonify({"ok": False, "error": "Thiếu thông tin thanh toán"}), 400
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO payments(payment_date,kind,party_type,party_code,amount,note,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (body["payment_date"], body["kind"], body["party_type"],
             clean_text(body["party_code"]), number_value(body["amount"]),
             clean_text(body.get("note")), now_iso()),
        )
        return jsonify({"ok": True, "id": cur.lastrowid})


@app.delete("/api/payments/<int:payment_id>")
def api_delete_payment(payment_id):
    with db() as conn:
        conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
    return jsonify({"ok": True})


@app.post("/api/balances")
def api_balance():
    body = request.get_json(force=True) or {}
    with db() as conn:
        conn.execute(
            "INSERT INTO balances(party_type,party_code,opening) VALUES(?,?,?) "
            "ON CONFLICT(party_type,party_code) DO UPDATE SET opening=excluded.opening",
            (body["party_type"], clean_text(body["party_code"]), number_value(body["opening"])),
        )
    return jsonify({"ok": True})


@app.post("/api/master/sync")
def api_master_sync():
    sync_master_if_needed(force=True)
    return jsonify({"ok": True, "message": "Đã đồng bộ danh mục từ Em Thành.xlsx"})


@app.get("/api/products/search")
def api_product_search():
    term = request.args.get("q", "").strip()
    with db() as conn:
        if not term:
            rows = rows_dict(conn.execute("SELECT * FROM products ORDER BY name LIMIT 30"))
        else:
            like = f"%{term}%"
            rows = rows_dict(conn.execute(
                "SELECT * FROM products WHERE code LIKE ? OR name LIKE ? ORDER BY name LIMIT 30",
                (like, like),
            ))
        return jsonify({"ok": True, "items": rows})


def workbook_bytes(wb: Workbook):
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def set_title(ws, text, subtitle="", end_col=8):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=end_col)
    cell = ws.cell(1, 1, text)
    cell.font = Font(name="Arial", size=17, bold=True, color=WHITE)
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30
    if subtitle:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end_col)
        ws.cell(2, 1, subtitle)
        ws.cell(2, 1).font = Font(name="Arial", italic=True, color=GRAY)
        ws.cell(2, 1).alignment = Alignment(horizontal="center")


def style_table(ws, header_row, end_col, last_row=None):
    last_row = last_row or ws.max_row
    thin = Side(style="thin", color="D8E1EA")
    for cell in ws[header_row][:end_col]:
        cell.font = Font(name="Arial", bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    for row in ws.iter_rows(min_row=header_row + 1, max_row=last_row, min_col=1, max_col=end_col):
        for cell in row:
            cell.font = Font(name="Arial", size=10)
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if cell.row % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=PALE)
    if last_row >= header_row:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(end_col)}{last_row}"
    ws.freeze_panes = f"A{header_row + 1}"


def autosize(ws, max_width=48):
    for col in range(1, ws.max_column + 1):
        width = 8
        for row in range(1, min(ws.max_row, 180) + 1):
            value = ws.cell(row, col).value
            if value is not None:
                lines = str(value).splitlines() or [""]
                width = max(width, max(len(line) for line in lines))
        ws.column_dimensions[get_column_letter(col)].width = min(width + 2, max_width)


def money_format(wb):
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, (int, float)) and cell.column > 1:
                    if any(key in clean_text(ws.cell(4 if ws.max_row >= 4 else 1, cell.column).value).lower()
                           for key in ("giá", "tiền", "thu", "trả", "vốn", "lợi nhuận")):
                        cell.number_format = "#,##0"


def require_batch(conn, batch_id):
    batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not batch:
        raise ValueError("Không tìm thấy phiên đơn")
    orders = rows_dict(conn.execute("SELECT * FROM orders WHERE batch_id=? ORDER BY id", (batch_id,)))
    for item in orders:
        item["errors"] = json.loads(item["errors"] or "[]")
        item["warnings"] = json.loads(item["warnings"] or "[]")
    if not orders:
        raise ValueError("Phiên đơn đang trống")
    return dict(batch), orders


def send_xlsx(wb, filename):
    return send_file(
        workbook_bytes(wb),
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def export_supplier_orders(conn, batch, orders):
    wb = Workbook()
    wb.remove(wb.active)
    groups = defaultdict(list)
    stock = inventory_lookup(conn, batch["work_date"])
    available = {code: max(item["available_qty"], 0) for code, item in stock.items()}
    for item in orders:
        qty = max(number_value(item["qty"]), 0)
        used = min(qty, available.get(item["product_code"], 0))
        available[item["product_code"]] = max(available.get(item["product_code"], 0) - used, 0)
        required = max(qty - used, 0)
        if required <= 0:
            continue
        rule = conn.execute(
            "SELECT combine_kitchens FROM supplier_rules WHERE supplier_code=?", (item["supplier"],)
        ).fetchone()
        combined = bool(rule and rule["combine_kitchens"])
        key = (item["supplier"] or "CHƯA XÁC ĐỊNH", "ALL" if combined else item["kitchen"])
        output = dict(item)
        output["required_qty"] = required
        output["stock_used"] = used
        groups[key].append(output)
    for (supplier, kitchen_key), rows in sorted(groups.items()):
        sheet_label = supplier if kitchen_key == "ALL" else f"{supplier}-{kitchen_key}"
        ws = wb.create_sheet(safe_sheet_name(sheet_label.upper()))
        set_title(ws, f"ĐƠN ĐẶT HÀNG – NCC {supplier.upper()}",
                  f"Ngày giao: {batch['work_date']}", 7)
        ws.append([])
        ws.append(["STT", "Mã hàng", "Tên hàng", "SL cần mua", "ĐVT", "Bếp", "Ghi chú"])
        for idx, item in enumerate(rows, 1):
            note = item["note"] or ""
            if item["stock_used"]:
                note = (note + f" · Đã trừ tồn {item['stock_used']:g}").strip(" ·")
            ws.append([idx, item["product_code"], item["product_name"], item["required_qty"],
                       item["unit"], item["kitchen"], note])
        style_table(ws, 4, 7)
        autosize(ws)
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
    if not wb.sheetnames:
        ws = wb.create_sheet("KHÔNG CẦN MUA")
        set_title(ws, "KHÔNG PHÁT SINH NHU CẦU MUA", "Tồn khả dụng đã đáp ứng toàn bộ lượng khách đặt", 4)
        ws.append([])
        ws.append(["Ngày", "Trạng thái", "Công thức", "Ghi chú"])
        ws.append([batch["work_date"], "Không cần đặt NCC", "max(lượng khách đặt - tồn khả dụng, 0)", ""])
        style_table(ws, 4, 4)
        autosize(ws)
    return wb


def export_deliveries(conn, batch, orders):
    wb = Workbook()
    wb.remove(wb.active)
    groups = defaultdict(list)
    for item in orders:
        groups[item["kitchen"] or "CHƯA XÁC ĐỊNH"].append(item)
    for kitchen, rows in sorted(groups.items()):
        meta = conn.execute("SELECT * FROM kitchens WHERE code=?", (kitchen,)).fetchone()
        meta = dict(meta) if meta else {"name": kitchen, "address": "", "show_price": 0}
        show_price = bool(meta.get("show_price"))
        end_col = 8 if show_price else 6
        ws = wb.create_sheet(safe_sheet_name(kitchen))
        set_title(ws, "PHIẾU GIAO HÀNG",
                  f"{meta.get('name') or kitchen} – Ngày {batch['work_date']}", end_col)
        ws.cell(3, 1, "Địa chỉ giao hàng:").font = Font(bold=True, color=NAVY)
        ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=end_col)
        ws.cell(3, 2, meta.get("address") or "")
        headers = ["STT", "Mã hàng", "Tên hàng", "SL thực giao", "ĐVT", "Ghi chú"]
        if show_price:
            headers += ["Đơn giá", "Thành tiền"]
        ws.append(headers)
        for idx, item in enumerate(rows, 1):
            delivered = net_delivered(item)
            values = [idx, item["product_code"], item["product_name"], delivered,
                      item["unit"], item["note"]]
            if show_price:
                values += [item["sell_price"], delivered * item["sell_price"]]
            ws.append(values)
        style_table(ws, 4, end_col)
        autosize(ws)
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
    return wb


def export_report(conn, batch, orders):
    summary = calculate_summary(conn, orders)
    wb = Workbook()
    ws = wb.active
    ws.title = "Tổng hợp"
    set_title(ws, "DOANH THU – GIÁ VỐN – LỢI NHUẬN",
              f"Ngày {batch['work_date']} · Doanh thu theo số thực giao, giá vốn theo số thực nhận", 7)
    ws.append([])
    ws.append(["Nhà thầu", "Doanh thu chưa VAT", "Giá vốn", "Lợi nhuận",
               "Tổng thanh toán", "Đã thu", "Còn phải thu"])
    for contractor, values in sorted(summary["contractors"].items()):
        ws.append([contractor, values["revenue"], values["cost"], values["profit"],
                   values["total"], values["paid"], values["balance"]])
    style_table(ws, 4, 7)
    autosize(ws)

    ws = wb.create_sheet("Công nợ phải thu")
    set_title(ws, "CÔNG NỢ PHẢI THU", "Bao gồm số dư đầu kỳ và thanh toán đã ghi nhận", 6)
    ws.append([])
    ws.append(["Nhà thầu", "Số dư đầu kỳ", "Phát sinh", "Đã thu", "Còn phải thu", "Ngày dữ liệu"])
    for contractor, values in sorted(summary["contractors"].items()):
        ws.append([contractor, values["opening"], values["total"], values["paid"],
                   values["balance"], batch["work_date"]])
    style_table(ws, 4, 6)
    autosize(ws)

    ws = wb.create_sheet("Công nợ phải trả")
    set_title(ws, "CÔNG NỢ PHẢI TRẢ NHÀ CUNG CẤP",
              "Giá vốn theo số thực nhận · Bao gồm số dư đầu kỳ", 6)
    ws.append([])
    ws.append(["NCC", "Số dư đầu kỳ", "Phát sinh", "Đã trả", "Còn phải trả", "Số dòng"])
    for supplier, values in sorted(summary["suppliers"].items()):
        ws.append([supplier, values["opening"], values["cost"], values["paid"],
                   values["balance"], values["lines"]])
    style_table(ws, 4, 6)
    autosize(ws)

    ws = wb.create_sheet("Lịch sử thanh toán")
    set_title(ws, "LỊCH SỬ THU – CHI", "Dữ liệu đã ghi nhận trong hệ thống", 7)
    ws.append([])
    ws.append(["Ngày", "Loại", "Nhóm", "Đối tượng", "Số tiền", "Nội dung", "Ngày tạo"])
    for row in conn.execute("SELECT * FROM payments ORDER BY payment_date,id"):
        ws.append([row["payment_date"], "Thu khách" if row["kind"] == "receipt" else "Trả NCC",
                   row["party_type"], row["party_code"], row["amount"], row["note"], row["created_at"]])
    style_table(ws, 4, 7)
    autosize(ws)
    money_format(wb)
    return wb


def export_purchase_documents(conn, batch, orders):
    rate = number_value(setting_get(conn, "purchase_rate", "0.95"), 0.95)
    rows = [item for item in orders if item["purchase_list"]]
    wb = Workbook()
    ws = wb.active
    ws.title = "Bảng kê"
    set_title(ws, "BẢNG KÊ THU MUA HÀNG HÓA MUA VÀO KHÔNG CÓ HÓA ĐƠN",
              f"Ngày {batch['work_date']} · Đơn giá bảng kê = {rate:.0%} giá bán", 9)
    ws.append([])
    ws.append(["Ngày", "Người bán", "Địa chỉ", "CCCD", "Tên hàng", "ĐVT",
               "Số lượng thực nhận", "Đơn giá", "Thành tiền"])
    grouped = defaultdict(list)
    for item in rows:
        person = conn.execute("SELECT * FROM people WHERE name=?", (item["seller"],)).fetchone()
        address = person["address"] if person else "Hải Phòng"
        unit_price = round(item["sell_price"] * rate)
        received = net_received(item)
        amount = received * unit_price
        ws.append([batch["work_date"], item["seller"], address, item["cccd"],
                   item["product_name"], item["unit"], received, unit_price, amount])
        grouped[item["seller"] or "CHƯA XÁC ĐỊNH"].append((item, unit_price, amount))
    style_table(ws, 4, 9)
    autosize(ws)

    for seller, seller_rows in sorted(grouped.items()):
        person = conn.execute("SELECT * FROM people WHERE name=?", (seller,)).fetchone()
        person = dict(person) if person else {}
        ws = wb.create_sheet(safe_sheet_name(f"BN {seller}"))
        set_title(ws, "GIẤY BIÊN NHẬN", f"Ngày {batch['work_date']}", 5)
        labels = [
            ("Đơn vị mua", setting_get(conn, "company", "")),
            ("Người bán", seller),
            ("Số CCCD", person.get("cccd") or seller_rows[0][0]["cccd"]),
            ("Ngày cấp", person.get("issue_date") or ""),
            ("Nơi cấp", person.get("issue_place") or ""),
        ]
        for idx, (label, value) in enumerate(labels, 4):
            ws.cell(idx, 1, label).font = Font(bold=True, color=NAVY)
            ws.cell(idx, 2, value)
        ws.append([])
        ws.append(["STT", "Tên hàng", "ĐVT", "Số lượng", "Thành tiền"])
        total = 0
        for idx, (item, _, amount) in enumerate(seller_rows, 1):
            total += amount
            ws.append([idx, item["product_name"], item["unit"], net_received(item), amount])
        ws.append(["", "TỔNG CỘNG", "", "", total])
        style_table(ws, 10, 5)
        autosize(ws)
    money_format(wb)
    return wb


def invoice_workbook(rows, invoice_names=None):
    invoice_names = invoice_names or {}
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(INVOICE_HEADERS)
    for item in rows:
        qty = net_delivered(item)
        unit_price = round(number_value(item["sell_price"]))
        amount = round(qty * unit_price)
        total = round(amount * tax_factor(item["tax"]))
        tax = "KKKNT" if clean_text(item["tax"]).upper() == "KKKNT" else number_value(item["tax"])
        ws.append([
            item["supplier"], item["product_code"], item["kitchen"],
            invoice_names.get(item["product_code"], item["product_name"]),
            qty, item["unit"], unit_price, amount, tax, total,
            item["cccd"] or "",
        ])
    style_table(ws, 1, 11)
    for col in (7, 8, 10):
        for row in range(2, ws.max_row + 1):
            ws.cell(row, col).number_format = "#,##0"
    autosize(ws)
    return wb


def export_invoices_zip(conn, batch, orders):
    invoice_names = {
        row["product_code"]: row["invoice_name"]
        for row in conn.execute("SELECT product_code,invoice_name FROM outgoing_product_names")
    }
    groups = defaultdict(list)
    for item in orders:
        tax_key = "KKKNT" if clean_text(item["tax"]).upper() == "KKKNT" else f"{number_value(item['tax']):.0%}"
        groups[(item["contractor"] or "KHAC", tax_key)].append(item)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = ["FILE TẢI PHẦN MỀM TRUNG GIAN", "",
                    "Các file đúng 11 cột theo mẫu khách cung cấp.",
                    "Tải lên phần mềm trung gian để kiểm tra tồn rồi mới đẩy M-Invoice.", ""]
        for (contractor, tax_key), rows in sorted(groups.items()):
            wb_stream = workbook_bytes(invoice_workbook(rows, invoice_names))
            filename = f"Hoa_don_{safe_sheet_name(contractor)}_{tax_key}_{batch['work_date']}.xlsx"
            archive.writestr(filename, wb_stream.getvalue())
            manifest.append(f"- {filename}: {len(rows)} dòng")
        archive.writestr("HUONG_DAN.txt", "\r\n".join(manifest).encode("utf-8-sig"))
    stream.seek(0)
    return stream


def get_quote_rows(conn, contractor: str, batch_id=None):
    row = conn.execute("SELECT * FROM contractors WHERE code=?", (contractor,)).fetchone()
    group = row["price_group"] if row else contractor
    mode = row["pricing_mode"] if row else "group"
    rows = []
    if mode == "daily" and batch_id:
        seen = set()
        for item in conn.execute(
            "SELECT product_code,product_name,unit,tax,sell_price FROM orders "
            "WHERE batch_id=? AND contractor=? ORDER BY product_name", (batch_id, contractor)
        ):
            if item["product_code"] in seen:
                continue
            seen.add(item["product_code"])
            data = dict(item)
            data["status"] = "Giá theo ngày"
            rows.append(data)
    else:
        for item in conn.execute(
            """SELECT p.code product_code,p.name product_name,p.unit,p.tax,
                      pp.price_value sell_price,pp.price_text
               FROM products p JOIN product_prices pp ON pp.product_code=p.code
               WHERE pp.price_group=? ORDER BY p.name""", (group,)
        ):
            data = dict(item)
            text = clean_text(data.pop("price_text", ""))
            data["status"] = text if not data["sell_price"] else ""
            rows.append(data)
    return mode, rows


@app.get("/api/quotes")
def api_quotes():
    contractor = clean_text(request.args.get("contractor")).upper()
    batch_id = request.args.get("batch_id", type=int)
    with db() as conn:
        mode, rows = get_quote_rows(conn, contractor, batch_id)
        return jsonify({"ok": True, "contractor": contractor, "mode": mode, "items": rows})


@app.get("/api/export/<kind>/<int:batch_id>")
def api_export(kind, batch_id):
    with db() as conn:
        batch, orders = require_batch(conn, batch_id)
        stamp = batch["work_date"]
        if kind == "suppliers":
            return send_xlsx(export_supplier_orders(conn, batch, orders), f"Don_dat_hang_NCC_{stamp}.xlsx")
        if kind == "deliveries":
            return send_xlsx(export_deliveries(conn, batch, orders), f"Phieu_giao_hang_{stamp}.xlsx")
        if kind == "report":
            return send_xlsx(export_report(conn, batch, orders), f"Bao_cao_cong_no_{stamp}.xlsx")
        if kind == "purchases":
            return send_xlsx(export_purchase_documents(conn, batch, orders), f"Bang_ke_bien_nhan_{stamp}.xlsx")
        if kind == "invoices":
            return send_file(
                export_invoices_zip(conn, batch, orders), as_attachment=True,
                download_name=f"File_tai_phan_mem_trung_gian_{stamp}.zip",
                mimetype="application/zip",
            )
    return jsonify({"ok": False, "error": "Loại file không hợp lệ"}), 404


@app.get("/api/export/quote/<contractor>")
def api_export_quote(contractor):
    contractor = clean_text(contractor).upper()
    batch_id = request.args.get("batch_id", type=int)
    with db() as conn:
        mode, rows = get_quote_rows(conn, contractor, batch_id)
        wb = Workbook()
        ws = wb.active
        ws.title = "BÁO GIÁ"
        subtitle = "Giá theo ngày từ phiên đơn đang chọn" if mode == "daily" else "Theo nhóm giá đã cấu hình"
        set_title(ws, f"BẢNG BÁO GIÁ – {contractor}", subtitle, 6)
        ws.append([])
        ws.append(["STT", "Mã hàng", "Tên hàng", "ĐVT", "Thuế", "Đơn giá"])
        output = [item for item in rows if number_value(item.get("sell_price")) > 0]
        for idx, item in enumerate(output, 1):
            ws.append([idx, item["product_code"], item["product_name"], item["unit"],
                       item["tax"], item["sell_price"]])
        style_table(ws, 4, 6)
        autosize(ws)
        return send_xlsx(wb, f"Bao_gia_{contractor}.xlsx")


@app.get("/api/backup")
def api_backup():
    # A consistent SQLite copy while the app is live.
    memory = io.BytesIO()
    backup_path = DATA_DIR / f"backup_{datetime.now():%Y%m%d_%H%M%S}.sqlite3"
    source = sqlite3.connect(DB_PATH)
    target = sqlite3.connect(backup_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    response = send_file(
        backup_path, as_attachment=True, download_name=backup_path.name,
        mimetype="application/vnd.sqlite3",
    )

    @response.call_on_close
    def _cleanup():
        try:
            backup_path.unlink()
        except OSError:
            pass

    return response


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8765")


register_contract_routes(app, {
    "db": db,
    "now_iso": now_iso,
    "clean_text": clean_text,
    "number_value": number_value,
    "tax_factor": tax_factor,
    "setting_get": setting_get,
    "setting_set": setting_set,
    "root": ROOT,
    "data_dir": DATA_DIR,
    "require_batch": require_batch,
    "export_supplier_orders": export_supplier_orders,
    "export_deliveries": export_deliveries,
    "export_purchase_documents": export_purchase_documents,
    "export_report": export_report,
})


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    init_database()
    print("\nTHÀNH ĐẠT PHÁT – HỆ THỐNG VẬN HÀNH")
    print("Máy này: http://127.0.0.1:8765")
    print(f"Máy thứ hai cùng Wi-Fi/LAN: http://{local_ip()}:8765")
    print("Giữ cửa sổ này mở trong lúc sử dụng. Nhấn Ctrl+C để dừng.\n")
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_browser, daemon=True).start()
    serve(app, host="0.0.0.0", port=8765, threads=8)
