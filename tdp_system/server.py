from __future__ import annotations

import io
import hashlib
import ipaddress
import json
import math
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
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit

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
DATA_DIR = Path(os.environ.get("TDP_DATA_DIR", str(APP_DIR / "data"))).resolve()
EXPORT_DIR = Path(os.environ.get("TDP_EXPORT_DIR", str(APP_DIR / "exports"))).resolve()
DB_PATH = Path(os.environ.get("TDP_DB_PATH", str(DATA_DIR / "tdp.sqlite3")))

def ensure_writable_directory(path: Path, label: str):
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".tdp-write-{uuid.uuid4().hex}.tmp"
        with probe.open("x", encoding="utf-8") as handle:
            handle.write("ok")
        probe.unlink()
    except OSError as exc:
        raise RuntimeError(
            f"{label} không có quyền ghi: {path}. Hãy chuyển bộ cài sang thư mục người dùng "
            "hoặc cấu hình TDP_DATA_DIR/TDP_EXPORT_DIR."
        ) from exc


ensure_writable_directory(DATA_DIR, "Thư mục dữ liệu")
ensure_writable_directory(EXPORT_DIR, "Thư mục xuất file")

NAVY = "17324D"
TEAL = "087F73"
PALE = "F5F8FB"
WHITE = "FFFFFF"
GRAY = "5E7083"
RED = "C2413A"

INVOICE_HEADERS = [
    "Mã hàng", "Tên hàng", "Đơn vị tính", "Số lượng", "Đơn giá",
    "Cộng tiền hàng", "%CK", "Tiền CK", "Tiền trước thuế", "% VAT",
    "Tiền thuế GTGT", "Tổng tiền", "Tính chất",
]
MASTER_FORMAT_VERSION = "2"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
PENDING_IMPORTS = {}
PENDING_IMPORT_LOCK = threading.Lock()
ORDER_IMPORT_MAX_BYTES = 20 * 1024 * 1024
ORDER_IMPORT_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
ORDER_IMPORT_MAX_ENTRIES = 5_000
ORDER_IMPORT_MAX_ROWS = 100_000


@app.before_request
def reject_cross_origin_mutations():
    """Reject DNS-rebinding hosts and browser cross-site writes."""
    host_name = (urlsplit("//" + request.host).hostname or "").casefold()
    trusted_hosts = {"localhost", "127.0.0.1", "::1"}
    configured_hosts = clean_text(os.environ.get("TDP_TRUSTED_HOSTS", ""))
    trusted_hosts.update(
        item.strip().casefold() for item in configured_hosts.split(",") if item.strip()
    )
    allow_lan = clean_text(os.environ.get("TDP_ALLOW_LAN", "")).lower() in {
        "1", "true", "yes", "co", "có",
    }
    if allow_lan:
        trusted_hosts.update({
            clean_text(local_ip()).casefold(),
            clean_text(socket.gethostname()).casefold(),
            clean_text(socket.getfqdn()).casefold(),
        })
    if host_name not in trusted_hosts:
        return jsonify({"ok": False, "error": "Tên máy truy cập không nằm trong danh sách tin cậy"}), 403
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    origin = clean_text(request.headers.get("Origin")).rstrip("/")
    if origin and origin != request.host_url.rstrip("/"):
        return jsonify({"ok": False, "error": "Yêu cầu ghi dữ liệu khác nguồn đã bị chặn"}), 403
    return None


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


def canonical_party_code(conn, party_type: str, value) -> str:
    """Resolve free-text ledger input to one canonical debt key.

    Debt aggregation groups by the stored key exactly.  Accepting ``hatran``
    beside ``HATRAN`` would create a phantom second account, so every ledger
    write resolves against master data and existing charge sources first.
    """

    raw = clean_text(value)
    if not raw:
        raise ValueError("Thiếu mã nhà thầu/nhà cung cấp")
    candidates = {}
    case_keys = {}

    def remember(code, name=None):
        canonical = clean_text(code)
        if not canonical:
            return
        # Case-only variants are the same ledger key.  Prefer the first value
        # encountered (master tables are read before transactional sources)
        # and retain every spelling as an alias.
        preferred = case_keys.setdefault(canonical.casefold(), canonical)
        candidates.setdefault(preferred, set()).update(
            item for item in (canonical, clean_text(name)) if item
        )

    if party_type == "contractor":
        for row in conn.execute("SELECT code,name FROM contractors"):
            remember(row["code"], row["name"])
        for row in conn.execute(
            "SELECT DISTINCT contractor FROM orders WHERE TRIM(COALESCE(contractor,''))!=''"
        ):
            remember(row["contractor"])
    elif party_type == "supplier":
        for row in conn.execute("SELECT code,name FROM suppliers"):
            remember(row["code"], row["name"])
        for sql in (
            "SELECT DISTINCT supplier FROM products WHERE TRIM(COALESCE(supplier,''))!=''",
            "SELECT DISTINCT supplier FROM orders WHERE TRIM(COALESCE(supplier,''))!=''",
            "SELECT DISTINCT supplier FROM historical_payable_lines WHERE TRIM(COALESCE(supplier,''))!=''",
        ):
            for row in conn.execute(sql):
                remember(row["supplier"])
    else:
        raise ValueError("Nhóm công nợ không hợp lệ")

    exact = [code for code in candidates if code.casefold() == raw.casefold()]
    if len(exact) == 1:
        return exact[0]
    wanted = slug(raw)
    matches = [
        code for code, aliases in candidates.items()
        if wanted and any(slug(alias) == wanted for alias in aliases)
    ]
    matches = sorted(set(matches))
    if len(matches) == 1:
        return matches[0]
    label = "nhà thầu" if party_type == "contractor" else "nhà cung cấp"
    if not matches:
        raise ValueError(f"Không tìm thấy {label} {raw!r}; hãy chọn đúng mã đã có trong hệ thống")
    raise ValueError(f"{label.capitalize()} {raw!r} khớp nhiều mã; hãy nhập đúng mã duy nhất")


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


def valid_iso_date(value, label="Ngày") -> str:
    """Return a strict calendar date or raise a user-safe validation error."""
    text = clean_text(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        raise ValueError(f"{label} phải có dạng YYYY-MM-DD và là ngày hợp lệ") from None


def finite_number(value, label: str, *, default=None) -> float:
    """Parse a numeric request field without silently turning bad input into zero."""
    if value in (None, ""):
        if default is not None:
            return float(default)
        raise ValueError(f"Thiếu {label}")
    parsed = number_value(value, float("nan"))
    if not math.isfinite(parsed):
        raise ValueError(f"{label} phải là số hợp lệ")
    return float(parsed)


def audit_event(conn, event_type: str, *, entity_type="", entity_id="", metadata=None):
    """Write a compact business audit record without request bodies or credentials."""
    conn.execute(
        "INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (
            event_type,
            clean_text(entity_type),
            clean_text(entity_id),
            "ok",
            "",
            json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            now_iso(),
        ),
    )


def normalize_tax(value):
    text = clean_text(value).upper()
    if text in {"KKKNT", "KHÔNG KÊ KHAI", "KHONG KE KHAI", "K"}:
        return "KKKNT"
    if text in {"KCT", "KHÔNG CHỊU THUẾ", "KHONG CHIU THUE"}:
        return "KCT"
    if text in {"-2", "-2.0"}:
        return "KKKNT"
    if text in {"-1", "-1.0"}:
        return "KCT"
    if not text:
        return ""
    if text.endswith("%"):
        num = number_value(text[:-1], float("nan")) / 100
    else:
        num = number_value(value, float("nan"))
    if num > 1:
        num /= 100
    if not math.isfinite(num):
        return "INVALID"
    num = round(num, 4)
    if num not in {0.0, 0.05, 0.08, 0.1}:
        return "INVALID"
    return num


def tax_factor(value) -> float:
    return 1.0 if clean_text(value).upper() in {"KKKNT", "KCT"} else 1.0 + number_value(value)


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
CREATE TABLE IF NOT EXISTS order_import_receipts (
    import_key TEXT PRIMARY KEY,
    source_hash TEXT NOT NULL,
    source_name TEXT NOT NULL,
    work_date TEXT NOT NULL,
    selected_sheets_json TEXT NOT NULL,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_import_receipts_batch
    ON order_import_receipts(batch_id);
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
    invoice_nature TEXT NOT NULL DEFAULT '1',
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


def pre_migration_backup():
    """Create a verified SQLite backup before any startup DDL can commit."""

    if not DB_PATH.is_file() or DB_PATH.stat().st_size == 0:
        return None
    backup_dir = DATA_DIR / "migration_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / (
        f"tdp_pre_migration_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:10]}.sqlite3"
    )
    source = destination = None
    try:
        source = sqlite3.connect(DB_PATH, timeout=20)
        destination = sqlite3.connect(target)
        source.backup(destination)
        if str(destination.execute("PRAGMA quick_check(1)").fetchone()[0]).lower() != "ok":
            raise sqlite3.DatabaseError("backup integrity check failed")
    except (OSError, sqlite3.Error) as exc:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("Không tạo được bản sao an toàn trước khi nâng cấp dữ liệu") from exc
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
    backups = sorted(
        backup_dir.glob("tdp_pre_migration_*.sqlite3"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in backups[5:]:
        old.unlink(missing_ok=True)
    return target


def init_database():
    pre_migration_backup()
    with db() as conn:
        conn.executescript(SCHEMA)
        init_contract_schema(conn)
        order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
        if "warnings" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN warnings TEXT NOT NULL DEFAULT '[]'")
        if "invoice_nature" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN invoice_nature TEXT NOT NULL DEFAULT '1'")
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
    "invoice_nature": {"tinhchat", "tinhchathanghoa", "loaibong", "nature"},
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
    errors = []
    warnings = []

    try:
        batch_date = valid_iso_date(fallback_date, "Ngày phiên đơn")
    except ValueError:
        batch_date = date.today().isoformat()
        errors.append("Ngày phiên đơn không hợp lệ")
    supplied_work_date = raw.get("work_date")
    if supplied_work_date not in (None, ""):
        parsed_order_date = display_date(supplied_work_date, "")
        if not parsed_order_date:
            errors.append("Ngày dòng đơn không hợp lệ")
        elif parsed_order_date != batch_date:
            errors.append("Ngày dòng đơn phải trùng ngày của phiên đơn")

    def order_number(value, label, default=0.0):
        parsed = (
            number_value(value, math.nan)
            if value not in (None, "")
            else float(default)
        )
        if not math.isfinite(parsed):
            errors.append(f"{label} phải là số hợp lệ và hữu hạn")
            return float(default) if math.isfinite(float(default)) else 0.0
        return parsed

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

    qty = order_number(raw.get("qty"), "Số lượng")
    actual_received = order_number(raw.get("actual_received"), "Số lượng thực nhận", qty)
    actual_delivered = order_number(raw.get("actual_delivered"), "Số lượng thực giao", qty)
    damaged_qty = order_number(raw.get("damaged_qty"), "Số lượng hỏng")
    supplier_return_qty = order_number(raw.get("supplier_return_qty"), "Số lượng trả NCC")
    customer_return_qty = order_number(raw.get("customer_return_qty"), "Số lượng khách trả")
    unit = clean_text(raw.get("unit")) or (clean_text(product["unit"]) if product else "")
    buy_price = order_number(raw.get("buy_price"), "Giá mua")
    if buy_price <= 0 and product:
        buy_price = order_number(product["buy_price"], "Giá mua trong danh mục")
    raw_invoice_nature = clean_text(raw.get("invoice_nature")) or "1"
    requested_sell_price = order_number(raw.get("sell_price"), "Giá bán")
    promotion_marker = "khuyenmai" in slug(
        f"{name} {clean_text(raw.get('note'))}"
    )
    is_promotion = raw_invoice_nature == "2" or (promotion_marker and requested_sell_price <= 0)
    invoice_nature = "2" if is_promotion else "1"
    sell_price = requested_sell_price
    price_message = ""
    if sell_price <= 0 and code and contractor and not is_promotion:
        sell_price, price_message = get_sell_price(conn, code, contractor)
        if not math.isfinite(sell_price):
            errors.append("Giá bán trong bảng giá phải là số hữu hạn")
            sell_price = 0
    raw_tax = raw.get("tax")
    if raw_tax in (None, "") and product:
        tax = clean_text(normalize_tax(product["tax"]))
    else:
        tax = clean_text(normalize_tax(raw_tax))
    if not tax:
        tax = "KKKNT"

    purchase_list_raw = clean_text(raw.get("purchase_list")).lower()
    purchase_list = 1 if purchase_list_raw in {"bk", "x", "1", "true", "có", "co"} else 0
    if product and raw.get("purchase_list") in (None, ""):
        purchase_list = int(product["purchase_list"] or 0)
    seller = clean_text(raw.get("seller")) or (clean_text(product["seller"]) if product else "")
    cccd = clean_text(raw.get("cccd")) or (clean_text(product["cccd"]) if product else "")

    if raw_invoice_nature not in {"", "1", "2"}:
        errors.append("Tính chất hóa đơn chỉ nhận 1 (hàng hóa) hoặc 2 (khuyến mại)")
    if is_promotion and requested_sell_price > 0:
        errors.append("Dòng khuyến mại phải để giá bán bằng 0")
    if buy_price <= 0 and sell_price > 0 and (supplier.lower() == "bk" or purchase_list):
        rate = order_number(setting_get(conn, "purchase_rate", "0.95"), "Tỷ lệ giá mua", 0.95)
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
    if actual_received < 0:
        errors.append("Số lượng thực nhận không được âm")
    if actual_delivered < 0:
        errors.append("Số lượng thực giao không được âm")
    if damaged_qty < 0 or supplier_return_qty < 0 or customer_return_qty < 0:
        errors.append("Số lượng hỏng/trả lại không được âm")
    if tax == "INVALID":
        errors.append("Thuế suất chỉ nhận 0%, 5%, 8%, 10%, KCT hoặc KKKNT")
    if not supplier:
        errors.append("Thiếu nhà cung cấp")
    if buy_price <= 0:
        errors.append("Thiếu giá mua")
    if sell_price <= 0 and not is_promotion:
        errors.append(price_message or "Thiếu giá bán")
    if sell_price > 0 and buy_price > sell_price and not is_promotion:
        warnings.append("Giá bán thấp hơn giá mua – cần xác nhận bán lỗ")
    if purchase_list and not cccd:
        errors.append("Hàng bảng kê thiếu CCCD")
    if damaged_qty + supplier_return_qty > actual_received:
        errors.append("Hàng hỏng + trả NCC không được vượt số thực nhận")
    if customer_return_qty > actual_delivered:
        errors.append("Khách trả không được vượt số thực giao")

    return {
        "work_date": batch_date,
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
        "invoice_nature": invoice_nature,
        "purchase_list": purchase_list,
        "seller": seller,
        "cccd": cccd,
        "note": clean_text(raw.get("note")),
        "errors": errors,
        "warnings": warnings,
    }


def parse_workbook(path: Path, fallback_date: str, selected_sheets=None):
    wb = load_workbook(io.BytesIO(path.read_bytes()), data_only=True, read_only=False)
    parsed = []
    skipped_sheets = []
    selected = set(selected_sheets) if selected_sheets else None
    with db() as conn:
        by_code, by_name = product_lookup(conn)
        for ws in wb.worksheets:
            if selected is not None and ws.title not in selected:
                continue
            if ws.max_row > ORDER_IMPORT_MAX_ROWS or ws.max_column > 200:
                raise ValueError(
                    f"Sheet {ws.title} vượt giới hạn {ORDER_IMPORT_MAX_ROWS:,} dòng/200 cột"
                )
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
                # Formula-filled template rows and genuine zero-quantity lines are
                # not orders. A non-blank malformed/non-finite quantity must still
                # reach resolve_order so the draft shows an error and cannot be
                # approved; silently dropping such a business row loses data.
                raw_qty = raw.get("qty")
                parsed_qty = number_value(raw_qty, math.nan)
                if raw_qty in (None, "") or (math.isfinite(parsed_qty) and parsed_qty <= 0):
                    continue
                order = resolve_order(conn, raw, fallback_date, by_code, by_name)
                order["source_sheet"] = ws.title
                order["source_row"] = row
                parsed.append(order)
                sheet_count += 1
            if sheet_count == 0:
                skipped_sheets.append(ws.title)
    wb.close()
    return parsed, skipped_sheets


def analyze_workbook(path: Path):
    wb = load_workbook(io.BytesIO(path.read_bytes()), data_only=True, read_only=False)
    candidates = []
    for ws in wb.worksheets:
        if ws.max_row > ORDER_IMPORT_MAX_ROWS or ws.max_column > 200:
            wb.close()
            raise ValueError(
                f"Sheet {ws.title} vượt giới hạn {ORDER_IMPORT_MAX_ROWS:,} dòng/200 cột"
            )
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
            raw_qty = ws.cell(row, mapping["qty"]).value
            parsed_qty = number_value(raw_qty, math.nan)
            # Include malformed non-blank quantities in the sheet preview; the
            # confirmation step will import them as blocked/error rows.
            if (math.isfinite(parsed_qty) and parsed_qty > 0) or (
                raw_qty not in (None, "") and not math.isfinite(parsed_qty)
            ):
                count += 1
        if count:
            candidates.append({
                "name": ws.title,
                "rows": count,
                "headerRow": header_row,
                "fields": sorted(mapping),
            })
    wb.close()
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
                unit,supplier,buy_price,sell_price,tax,invoice_nature,
                purchase_list,seller,cccd,note,source_sheet,source_row,errors,warnings,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, item["work_date"], item["contractor"], item["kitchen"],
                item["product_code"], item["product_name"], item["qty"],
                item["actual_received"], item["actual_delivered"], item["damaged_qty"],
                item["supplier_return_qty"], item["customer_return_qty"], item["unit"],
                item["supplier"], item["buy_price"], item["sell_price"], item["tax"],
                item["invoice_nature"],
                item["purchase_list"], item["seller"], item["cccd"], item["note"],
                item["source_sheet"], item["source_row"],
                json.dumps(item["errors"], ensure_ascii=False),
                json.dumps(item["warnings"], ensure_ascii=False), now_iso(),
            ),
        )
    return batch_id


def order_import_fingerprint(path: Path, work_date: str, selected_sheets) -> tuple[str, str, list[str]]:
    """Bind one import receipt to the exact bytes, date and explicit sheet set."""
    # Worksheet titles are identifiers, not display text.  Excel permits
    # leading/trailing spaces in a title and the customer's workbook contains
    # one (``đơn hàng27.08 ``).  Trimming here would fingerprint one title but
    # ask openpyxl to parse a different, non-existent worksheet.
    canonical_sheets = sorted({
        str(value) for value in selected_sheets if value is not None and str(value) != ""
    })
    source_bytes = path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest().upper()
    digest = hashlib.sha256()
    digest.update(source_bytes)
    digest.update(b"\x00work_date\x00")
    digest.update(work_date.encode("utf-8"))
    for sheet in canonical_sheets:
        digest.update(b"\x00sheet\x00")
        digest.update(sheet.encode("utf-8"))
    return digest.hexdigest().upper(), source_hash, canonical_sheets


def valid_order_import_batch(conn, import_key: str):
    """Return a still-usable imported batch; an empty/deleted batch is not reusable."""
    return conn.execute(
        """SELECT b.id
           FROM order_import_receipts r
           JOIN batches b ON b.id=r.batch_id
           WHERE r.import_key=?
             AND EXISTS(SELECT 1 FROM orders o WHERE o.batch_id=b.id)
           LIMIT 1""",
        (import_key,),
    ).fetchone()


def validate_existing_order(conn, item: dict):
    raw = dict(item)
    resolved = resolve_order(conn, raw, item.get("work_date") or date.today().isoformat(),
                             *product_lookup(conn))
    return resolved["errors"]


ORDER_FIELDS = {
    "contractor", "kitchen", "product_code", "product_name", "qty",
    "actual_received", "actual_delivered", "unit", "supplier", "buy_price",
    "sell_price", "tax", "invoice_nature", "purchase_list", "seller", "cccd", "note",
    "damaged_qty", "supplier_return_qty", "customer_return_qty",
}


def order_totals(order):
    revenue = vnd_product(net_delivered(order), number_value(order["sell_price"]))
    cost = vnd_product(net_received(order), number_value(order["buy_price"]))
    vat_percent = invoice_vat_percent(order["tax"])
    tax_amount = 0 if vat_percent <= 0 else vnd_product(revenue, vat_percent / 100)
    total = revenue + tax_amount
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
    """Summarize only the selected order batch.

    Payments and opening balances are deliberately excluded because they are
    cumulative party-level ledger entries and are not allocated to one batch.
    Multi-period debt is calculated by ``/api/debts`` instead.
    """
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

    for values in contractors.values():
        values["balance"] = values["total"]
    for values in kitchens.values():
        values["balance"] = values["total"]
    for values in suppliers.values():
        values["balance"] = values["cost"]
    return {
        "scope": "batch_only",
        "totals": totals,
        "contractors": dict(contractors),
        "kitchens": dict(kitchens),
        "suppliers": dict(suppliers),
    }


@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        return jsonify({"ok": False, "error": error.description}), error.code
    reference = uuid.uuid4().hex[:10].upper()
    app.logger.exception("Unhandled error [%s]", reference)
    return jsonify({
        "ok": False,
        "error": f"Lỗi nội bộ. Vui lòng thử lại hoặc báo mã {reference} cho bên hỗ trợ.",
        "reference": reference,
    }), 500


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
    required_tables = {
        "settings", "batches", "orders", "order_import_receipts",
        "audit_log", "inventory_transactions",
    }
    if not DB_PATH.is_file():
        return jsonify({
            "ok": False, "time": now_iso(), "database_ready": False,
            "schema_ready": False, "integrity": "not_checked",
        }), 503
    conn = None
    try:
        database_uri = DB_PATH.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(database_uri, uri=True, timeout=3)
        conn.execute("SELECT 1").fetchone()
        integrity = str(conn.execute("PRAGMA quick_check(1)").fetchone()[0])
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        duplicate_invoice_warning = False
        duplicate_payable_warning = False
        if "settings" in tables:
            duplicate_invoice_warning = conn.execute(
                "SELECT 1 FROM settings WHERE key='schema_warning_duplicate_invoice_ids' "
                "AND TRIM(value) NOT IN ('','[]')"
            ).fetchone() is not None
            duplicate_payable_warning = conn.execute(
                "SELECT 1 FROM settings WHERE key='schema_warning_duplicate_payable_source_ids' "
                "AND TRIM(value) NOT IN ('','[]')"
            ).fetchone() is not None
        schema_ready = (
            required_tables.issubset(tables)
            and not duplicate_invoice_warning
            and not duplicate_payable_warning
        )
        ready = integrity.lower() == "ok" and schema_ready
        return jsonify({
            "ok": ready,
            "time": now_iso(),
            "database_ready": ready,
            "schema_ready": schema_ready,
            "integrity": "ok" if integrity.lower() == "ok" else "failed",
            "duplicate_invoice_identity_warning": duplicate_invoice_warning,
            "duplicate_payable_source_warning": duplicate_payable_warning,
        }), 200 if ready else 503
    except (OSError, sqlite3.Error, ValueError):
        return jsonify({
            "ok": False, "time": now_iso(), "database_ready": False,
            "schema_ready": False, "integrity": "failed",
        }), 503
    finally:
        if conn is not None:
            conn.close()


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
            "status_check_read_only": True,
            "draft_save_available": True,
            "automatic_sign_or_issue": False,
            "official_api": True,
        })
    except MinvoiceError as error:
        return jsonify({"ok": False, "connected": False, "error": str(error), "read_only": True}), 502


@app.get("/api/minvoice/series")
def api_minvoice_series():
    """Return only invoice-series metadata; this endpoint never changes M-Invoice."""
    try:
        year = request.args.get("year", date.today().year, type=int)
        target = year % 100
        series = []
        for item in create_minvoice_client().get_invoice_series():
            value = clean_text(item.get("value") or item.get("khhdon")).upper()
            invoice_year = int(number_value(item.get("invoiceYear"), 0))
            if value.startswith("1") and invoice_year == target:
                series.append({"value": value, "invoice_year": invoice_year})
        unique = {item["value"]: item for item in series if item["value"]}
        return jsonify({"ok": True, "year": year, "items": list(unique.values()), "read_only": True})
    except MinvoiceError as error:
        return jsonify({"ok": False, "error": str(error), "read_only": True}), 502


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
            "outgoing_name_count": conn.execute("SELECT COUNT(*) n FROM outgoing_product_names").fetchone()["n"],
            "outgoing_names": rows_dict(conn.execute(
                """SELECT m.product_code,p.name source_name,m.invoice_name,m.updated_at
                   FROM outgoing_product_names m JOIN products p ON p.code=m.product_code
                   ORDER BY m.updated_at DESC,m.product_code LIMIT 100"""
            )),
            "settings": {row["key"]: row["value"] for row in conn.execute("SELECT * FROM settings")},
        }
        payload["payments"] = rows_dict(conn.execute("SELECT * FROM payments ORDER BY payment_date DESC,id DESC LIMIT 100"))
        payload["ok"] = True
        return jsonify(payload)


@app.post("/api/import")
def api_import():
    return jsonify({
        "ok": False,
        "error": "Luồng nhập trực tiếp đã khóa để tránh nhập nhầm toàn bộ lịch sử; hãy phân tích file và chọn rõ sheet ngày",
        "required_flow": ["/api/import/analyze", "/api/import/confirm"],
    }), 410


@app.post("/api/import/analyze")
def api_import_analyze():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "Chưa chọn file Excel"}), 400
    if Path(upload.filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        return jsonify({"ok": False, "error": "Chỉ nhận file .xlsx hoặc .xlsm"}), 400
    token = uuid.uuid4().hex
    suffix = Path(upload.filename).suffix.lower()
    temp = DATA_DIR / f"pending_{token}{suffix}"
    # Register before creating/analysing the file. Holding one lock across the
    # orphan sweep prevents a concurrent request from deleting another request's
    # just-created pending workbook.
    with PENDING_IMPORT_LOCK:
        cutoff = time.time() - 3600
        for old_token, item in list(PENDING_IMPORTS.items()):
            if item["created"] < cutoff:
                try:
                    item["path"].unlink()
                except OSError:
                    pass
                PENDING_IMPORTS.pop(old_token, None)
        active_pending_paths = {
            item["path"].resolve() for item in PENDING_IMPORTS.values()
            if item.get("path")
        }
        for pattern in ("pending_*.xlsx", "pending_*.xlsm"):
            for orphan in DATA_DIR.glob(pattern):
                try:
                    if orphan.is_file() and orphan.resolve() not in active_pending_paths:
                        orphan.unlink()
                except OSError:
                    pass
        PENDING_IMPORTS[token] = {
            "path": temp, "name": upload.filename, "created": time.time(), "state": "analyzing",
        }
    try:
        upload.save(temp)
        if temp.stat().st_size > ORDER_IMPORT_MAX_BYTES:
            raise ValueError("File Excel vượt quá giới hạn 20 MB")
        with zipfile.ZipFile(temp) as archive:
            entries = archive.infolist()
            expanded_size = sum(item.file_size for item in entries)
            if len(entries) > ORDER_IMPORT_MAX_ENTRIES or expanded_size > ORDER_IMPORT_MAX_UNCOMPRESSED_BYTES:
                raise ValueError("File Excel có cấu trúc quá lớn để đọc an toàn")
        sheets = analyze_workbook(temp)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        try:
            temp.unlink()
        except OSError:
            pass
        with PENDING_IMPORT_LOCK:
            PENDING_IMPORTS.pop(token, None)
        message = str(exc) if isinstance(exc, ValueError) else "File Excel bị hỏng hoặc không đúng định dạng"
        return jsonify({"ok": False, "error": message}), 400
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        with PENDING_IMPORT_LOCK:
            PENDING_IMPORTS.pop(token, None)
        raise
    if not sheets:
        temp.unlink(missing_ok=True)
        with PENDING_IMPORT_LOCK:
            PENDING_IMPORTS.pop(token, None)
        return jsonify({
            "ok": False,
            "error": "Không tìm thấy sheet đơn hàng có Mã bếp, Tên/Mã hàng và Số lượng.",
        }), 400
    with PENDING_IMPORT_LOCK:
        PENDING_IMPORTS[token]["state"] = "ready"
    return jsonify({"ok": True, "token": token, "filename": upload.filename, "sheets": sheets})


@app.post("/api/import/cancel")
def api_import_cancel():
    body = request.get_json(silent=True) or {}
    token = clean_text(body.get("token"))
    with PENDING_IMPORT_LOCK:
        pending = PENDING_IMPORTS.pop(token, None)
    if pending:
        try:
            pending["path"].unlink()
        except OSError:
            pass
    return jsonify({"ok": True, "idempotent": pending is None})


@app.post("/api/import/confirm")
def api_import_confirm():
    body = request.get_json(force=True) or {}
    token = clean_text(body.get("token"))
    with PENDING_IMPORT_LOCK:
        pending = PENDING_IMPORTS.pop(token, None)
    if not pending or not pending["path"].exists():
        return jsonify({"ok": False, "error": "Phiên chọn sheet đã hết hạn. Vui lòng chọn lại file."}), 400
    raw_sheets = body.get("sheets") or []
    if not isinstance(raw_sheets, list):
        with PENDING_IMPORT_LOCK:
            PENDING_IMPORTS[token] = pending
        return jsonify({"ok": False, "error": "Danh sách sheet không hợp lệ"}), 400
    # Preserve exact worksheet titles, including legal trailing spaces.
    sheets = sorted({
        str(value) for value in raw_sheets if value is not None and str(value) != ""
    })
    if not sheets:
        with PENDING_IMPORT_LOCK:
            PENDING_IMPORTS[token] = pending
        return jsonify({"ok": False, "error": "Cần chọn ít nhất một sheet"}), 400
    try:
        work_date = valid_iso_date(
            body.get("work_date") or date.today().isoformat(), "Ngày phiên đơn",
        )
        import_key, source_hash, sheets = order_import_fingerprint(
            pending["path"], work_date, sheets,
        )
    except (OSError, ValueError) as exc:
        with PENDING_IMPORT_LOCK:
            PENDING_IMPORTS[token] = pending
        return jsonify({"ok": False, "error": str(exc)}), 400
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
        # Serialize receipt check + write. The unique key also protects a
        # future multi-process deployment that shares this SQLite database.
        conn.execute("BEGIN IMMEDIATE")
        existing = valid_order_import_batch(conn, import_key)
        if existing:
            payload = batch_payload(conn, existing["id"])
            payload.update(
                ok=True,
                skippedSheets=skipped,
                selectedSheets=sheets,
                sourceHash=source_hash,
                importKey=import_key,
                idempotent=True,
            )
            return jsonify(payload)
        conn.execute("DELETE FROM order_import_receipts WHERE import_key=?", (import_key,))
        batch_id = save_imported_batch(conn, orders, work_date, pending["name"])
        conn.execute(
            """INSERT INTO order_import_receipts(
                   import_key,source_hash,source_name,work_date,selected_sheets_json,batch_id,created_at
               ) VALUES(?,?,?,?,?,?,?)""",
            (
                import_key, source_hash, pending["name"], work_date,
                json.dumps(sheets, ensure_ascii=False), batch_id, now_iso(),
            ),
        )
        payload = batch_payload(conn, batch_id)
        payload.update(
            ok=True,
            skippedSheets=skipped,
            selectedSheets=sheets,
            sourceHash=source_hash,
            importKey=import_key,
            idempotent=False,
        )
        return jsonify(payload)


@app.post("/api/batches")
def api_create_batch():
    body = request.get_json(force=True) or {}
    try:
        work_date = valid_iso_date(
            body.get("work_date") or date.today().isoformat(), "Ngày phiên đơn",
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO batches(work_date,source_name,status,created_at) VALUES(?,?,?,?)",
            (work_date, "Nhập tay", "draft", now_iso()),
        )
        return jsonify({"ok": True, **batch_payload(conn, cur.lastrowid)})


@app.post("/api/batches/<int:batch_id>/approve")
def api_approve_batch(batch_id):
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute("SELECT work_date FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
        try:
            valid_iso_date(batch["work_date"], "Ngày phiên đơn")
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        mismatched_dates = conn.execute(
            "SELECT COUNT(*) n FROM orders WHERE batch_id=? AND work_date!=?",
            (batch_id, batch["work_date"]),
        ).fetchone()["n"]
        if mismatched_dates:
            return jsonify({
                "ok": False,
                "error": f"Còn {mismatched_dates} dòng có ngày không trùng phiên đơn",
            }), 400
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
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
        blocked = batch_mutation_blocker(conn, batch_id)
        if blocked:
            return jsonify({"ok": False, "error": blocked}), 409
        resolved = resolve_order(conn, body, batch["work_date"], *product_lookup(conn))
        clear_batch_derived_inventory(conn, batch_id)
        cur = conn.execute(
            """INSERT INTO orders(
                batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                actual_received,actual_delivered,damaged_qty,supplier_return_qty,customer_return_qty,
                unit,supplier,buy_price,sell_price,tax,invoice_nature,
                purchase_list,seller,cccd,note,source_sheet,source_row,errors,warnings,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id, resolved["work_date"], resolved["contractor"], resolved["kitchen"],
                resolved["product_code"], resolved["product_name"], resolved["qty"],
                resolved["actual_received"], resolved["actual_delivered"], resolved["damaged_qty"],
                resolved["supplier_return_qty"], resolved["customer_return_qty"], resolved["unit"],
                resolved["supplier"], resolved["buy_price"], resolved["sell_price"], resolved["tax"],
                resolved["invoice_nature"],
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
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
        blocked = batch_mutation_blocker(conn, batch_id)
        if blocked:
            return jsonify({"ok": False, "error": blocked}), 409
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
            if inserted == 0:
                clear_batch_derived_inventory(conn, batch_id)
            conn.execute(
                """INSERT INTO orders(
                    batch_id,work_date,contractor,kitchen,product_code,product_name,qty,
                    actual_received,actual_delivered,damaged_qty,supplier_return_qty,customer_return_qty,
                    unit,supplier,buy_price,sell_price,tax,invoice_nature,
                    purchase_list,seller,cccd,note,source_sheet,source_row,errors,warnings,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    batch_id, resolved["work_date"], resolved["contractor"], resolved["kitchen"],
                    resolved["product_code"], resolved["product_name"], resolved["qty"],
                    resolved["actual_received"], resolved["actual_delivered"], resolved["damaged_qty"],
                    resolved["supplier_return_qty"], resolved["customer_return_qty"], resolved["unit"],
                    resolved["supplier"], resolved["buy_price"], resolved["sell_price"], resolved["tax"],
                    resolved["invoice_nature"],
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


@app.put("/api/orders/bulk-update")
def api_update_orders_bulk():
    """Atomically revalidate and update the editable order grid."""
    body = request.get_json(force=True) or {}
    batch_id = int(body.get("batch_id") or 0)
    patches = body.get("items")
    if not batch_id or not isinstance(patches, list) or not patches:
        return jsonify({"ok": False, "error": "Cần phiên đơn và danh sách dòng cần cập nhật"}), 400
    if len(patches) > 5000:
        return jsonify({"ok": False, "error": "Mỗi lần chỉ cập nhật tối đa 5.000 dòng"}), 413
    try:
        order_ids = [int(item.get("id") or 0) for item in patches if isinstance(item, dict)]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Danh sách có mã dòng không hợp lệ"}), 400
    if len(order_ids) != len(patches) or any(order_id <= 0 for order_id in order_ids):
        return jsonify({"ok": False, "error": "Mỗi dòng cập nhật phải có mã id hợp lệ"}), 400
    if len(set(order_ids)) != len(order_ids):
        return jsonify({"ok": False, "error": "Danh sách cập nhật bị trùng dòng"}), 400

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        batch = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        if not batch:
            return jsonify({"ok": False, "error": "Không tìm thấy phiên đơn"}), 404
        blocked = batch_mutation_blocker(conn, batch_id)
        if blocked:
            return jsonify({"ok": False, "error": blocked}), 409
        placeholders = ",".join("?" for _ in order_ids)
        current_rows = {
            row["id"]: dict(row)
            for row in conn.execute(
                f"SELECT * FROM orders WHERE batch_id=? AND id IN ({placeholders})",
                (batch_id, *order_ids),
            )
        }
        missing = [order_id for order_id in order_ids if order_id not in current_rows]
        if missing:
            return jsonify({
                "ok": False,
                "error": "Một số dòng không còn thuộc phiên đang mở; hãy tải lại trước khi lưu",
                "missing_ids": missing[:20],
            }), 409

        lookup = product_lookup(conn)
        prepared = []
        for patch_item, order_id in zip(patches, order_ids):
            item = current_rows[order_id]
            for key in ORDER_FIELDS:
                if key in patch_item:
                    item[key] = patch_item[key]
            resolved = resolve_order(
                conn, item, batch["work_date"], *lookup
            )
            for key in ORDER_FIELDS:
                if key in resolved:
                    item[key] = resolved[key]
            prepared.append((order_id, item, resolved["errors"], resolved["warnings"]))

        clear_batch_derived_inventory(conn, batch_id)
        columns = [
            "work_date", "contractor", "kitchen", "product_code", "product_name", "qty",
            "actual_received", "actual_delivered", "unit", "supplier", "buy_price",
            "sell_price", "tax", "invoice_nature", "purchase_list", "seller", "cccd", "note",
            "damaged_qty", "supplier_return_qty", "customer_return_qty",
        ]
        for order_id, item, errors, warnings in prepared:
            conn.execute(
                f"UPDATE orders SET {','.join(f'{column}=?' for column in columns)},"
                "errors=?,warnings=?,updated_at=? WHERE id=? AND batch_id=?",
                tuple(item[column] for column in columns) + (
                    json.dumps(errors, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False), now_iso(), order_id, batch_id,
                ),
            )
        conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?", (batch_id,))
        payload = batch_payload(conn, batch_id)
        payload.update(
            ok=True,
            updated=len(prepared),
            error_rows=sum(bool(errors) for _, _, errors, _ in prepared),
            warning_rows=sum(bool(warnings) for _, _, _, warnings in prepared),
        )
        return jsonify(payload)


@app.put("/api/orders/<int:order_id>")
def api_update_order(order_id):
    body = request.get_json(force=True) or {}
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not current:
            return jsonify({"ok": False, "error": "Không tìm thấy dòng đơn"}), 404
        blocked = batch_mutation_blocker(conn, current["batch_id"])
        if blocked:
            return jsonify({"ok": False, "error": blocked}), 409
        item = dict(current)
        for key in ORDER_FIELDS:
            if key in body:
                item[key] = body[key]
        batch = conn.execute(
            "SELECT work_date FROM batches WHERE id=?", (current["batch_id"],),
        ).fetchone()
        resolved = resolve_order(
            conn, item, batch["work_date"], *product_lookup(conn)
        )
        for key in ORDER_FIELDS:
            if key in resolved:
                item[key] = resolved[key]
        errors = resolved["errors"]
        warnings = resolved["warnings"]
        clear_batch_derived_inventory(conn, current["batch_id"])
        columns = [
            "work_date", "contractor", "kitchen", "product_code", "product_name", "qty",
            "actual_received", "actual_delivered", "unit", "supplier", "buy_price",
            "sell_price", "tax", "invoice_nature", "purchase_list", "seller", "cccd", "note",
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
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT batch_id FROM orders WHERE id=?", (order_id,)).fetchone()
        if not current:
            return jsonify({"ok": False, "error": "Không tìm thấy dòng đơn"}), 404
        blocked = batch_mutation_blocker(conn, current["batch_id"])
        if blocked:
            return jsonify({"ok": False, "error": blocked}), 409
        clear_batch_derived_inventory(conn, current["batch_id"])
        conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
        conn.execute("UPDATE batches SET status='draft',approved_at=NULL WHERE id=?", (current["batch_id"],))
        return jsonify({"ok": True, **batch_payload(conn, current["batch_id"])})


@app.post("/api/payments")
def api_payment():
    body = request.get_json(silent=True) or {}
    kind = clean_text(body.get("kind")).lower()
    party_type = clean_text(body.get("party_type")).lower()
    expected_party_type = {"receipt": "contractor", "payment": "supplier"}.get(kind)
    if expected_party_type is None:
        return jsonify({"ok": False, "error": "Loại thanh toán chỉ nhận thu khách hoặc trả nhà cung cấp"}), 400
    if party_type != expected_party_type:
        return jsonify({"ok": False, "error": "Nhóm đối tượng không khớp loại thu/chi"}), 400
    party_code_input = clean_text(body.get("party_code"))
    if not party_code_input:
        return jsonify({"ok": False, "error": "Thiếu mã nhà thầu/nhà cung cấp"}), 400
    try:
        payment_date = valid_iso_date(body.get("payment_date"), "Ngày thanh toán")
        amount = finite_number(body.get("amount"), "Số tiền")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if amount <= 0:
        return jsonify({"ok": False, "error": "Số tiền thanh toán phải lớn hơn 0"}), 400
    with db() as conn:
        try:
            party_code = canonical_party_code(conn, party_type, party_code_input)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        cur = conn.execute(
            "INSERT INTO payments(payment_date,kind,party_type,party_code,amount,note,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (payment_date, kind, party_type, party_code, amount,
             clean_text(body.get("note")), now_iso()),
        )
        audit_event(
            conn, "payment.create", entity_type=party_type, entity_id=party_code,
            metadata={"payment_id": cur.lastrowid, "payment_date": payment_date,
                      "kind": kind, "amount": amount},
        )
        return jsonify({"ok": True, "id": cur.lastrowid})


@app.delete("/api/payments/<int:payment_id>")
def api_delete_payment(payment_id):
    with db() as conn:
        current = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
        if not current:
            return jsonify({"ok": False, "error": "Không tìm thấy giao dịch thanh toán"}), 404
        conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
        audit_event(
            conn, "payment.delete", entity_type=current["party_type"],
            entity_id=current["party_code"], metadata={
                "payment_id": payment_id, "payment_date": current["payment_date"],
                "kind": current["kind"], "amount": current["amount"],
            },
        )
    return jsonify({"ok": True})


@app.post("/api/balances")
def api_balance():
    body = request.get_json(silent=True) or {}
    party_type = clean_text(body.get("party_type")).lower()
    party_code_input = clean_text(body.get("party_code"))
    if party_type not in {"contractor", "supplier"}:
        return jsonify({"ok": False, "error": "Nhóm số dư chỉ nhận nhà thầu hoặc nhà cung cấp"}), 400
    if not party_code_input:
        return jsonify({"ok": False, "error": "Thiếu mã nhà thầu/nhà cung cấp"}), 400
    try:
        as_of_date = valid_iso_date(
            clean_text(body.get("as_of_date")) or "1900-01-01", "Ngày chốt số dư"
        )
        opening = finite_number(body.get("opening"), "Số dư đầu kỳ")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    with db() as conn:
        try:
            party_code = canonical_party_code(conn, party_type, party_code_input)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        conn.execute(
            "INSERT INTO balances(party_type,party_code,opening,as_of_date) VALUES(?,?,?,?) "
            "ON CONFLICT(party_type,party_code) DO UPDATE SET "
            "opening=excluded.opening,as_of_date=excluded.as_of_date",
            (party_type, party_code, opening, as_of_date),
        )
        audit_event(
            conn, "balance.upsert", entity_type=party_type, entity_id=party_code,
            metadata={"opening": opening, "as_of_date": as_of_date},
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


def batch_mutation_blocker(conn, batch_id: int) -> str:
    """Explain why an order batch is immutable once downstream documents exist."""
    draft = conn.execute(
        """SELECT status,minvoice_status FROM outgoing_invoice_drafts
           WHERE batch_id=? AND status!='cancelled'
           ORDER BY CASE status WHEN 'issued' THEN 0 ELSE 1 END,id LIMIT 1""",
        (batch_id,),
    ).fetchone()
    if draft:
        if draft["status"] == "issued":
            return "Phiên đã có hóa đơn phát hành nên không được sửa/xóa dòng đơn"
        if draft["minvoice_status"] in {"saved", "saving", "unknown"}:
            return "Dự thảo đã lưu hoặc đang đối soát M-Invoice; xử lý dứt điểm trên M-Invoice trước khi sửa đơn"
        return "Phiên đang có dự thảo hóa đơn giữ tồn; hãy hủy dự thảo trước khi sửa đơn"
    print_job = conn.execute(
        """SELECT status FROM print_jobs
           WHERE batch_id=? AND status NOT IN ('stale','cancelled')
           ORDER BY id DESC LIMIT 1""",
        (batch_id,),
    ).fetchone()
    if print_job:
        if print_job["status"] in {"submitting", "submitted", "submission_unknown", "printed"}:
            return "Bộ chứng từ đã gửi sang máy in nên phiên được khóa để bảo toàn lịch sử"
        return "Phiên đang có bộ PDF in đã chuẩn bị/duyệt; hãy hủy bộ in cũ trước khi sửa đơn"
    return ""


def clear_batch_derived_inventory(conn, batch_id: int) -> None:
    """Remove reproducible BK stock lines before reverting a batch to draft."""
    conn.execute(
        "DELETE FROM inventory_transactions WHERE source_type='BK_INPUT' AND source_id=?",
        (str(batch_id),),
    )


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
    ws.title = "Tổng hợp phiên"
    set_title(
        ws, "DOANH THU – GIÁ VỐN – LỢI NHUẬN CỦA PHIÊN",
        f"Ngày {batch['work_date']} · Chỉ gồm phiên đơn này; không trừ số dư hoặc thu/chi của kỳ khác",
        5,
    )
    ws.append([])
    ws.append(["Nhà thầu", "Doanh thu chưa VAT", "Giá vốn", "Lợi nhuận",
               "Phát sinh phải thu của phiên"])
    for contractor, values in sorted(summary["contractors"].items()):
        ws.append([contractor, values["revenue"], values["cost"], values["profit"],
                   values["total"]])
    style_table(ws, 4, 5)
    autosize(ws)

    ws = wb.create_sheet("Phát sinh phải thu")
    set_title(
        ws, "PHÁT SINH PHẢI THU CỦA PHIÊN",
        "Muốn xem số dư đầu kỳ, thu tiền, điều chỉnh và cuối kỳ: dùng báo cáo Công nợ theo kỳ",
        4,
    )
    ws.append([])
    ws.append(["Nhà thầu", "Phát sinh phải thu", "Ngày dữ liệu", "Phạm vi"])
    for contractor, values in sorted(summary["contractors"].items()):
        ws.append([contractor, values["total"], batch["work_date"], "Riêng phiên đơn"])
    style_table(ws, 4, 4)
    autosize(ws)

    ws = wb.create_sheet("Phát sinh phải trả")
    set_title(
        ws, "PHÁT SINH PHẢI TRẢ NHÀ CUNG CẤP CỦA PHIÊN",
        "Giá vốn theo số thực nhận ròng · Không cộng số dư hoặc thanh toán kỳ khác",
        5,
    )
    ws.append([])
    ws.append(["NCC", "Phát sinh phải trả", "Ngày dữ liệu", "Số dòng", "Phạm vi"])
    for supplier, values in sorted(summary["suppliers"].items()):
        ws.append([supplier, values["cost"], batch["work_date"], values["lines"], "Riêng phiên đơn"])
    style_table(ws, 4, 5)
    autosize(ws)

    ws = wb.create_sheet("Thu chi cùng ngày")
    set_title(
        ws, "THU – CHI CÙNG NGÀY (THAM KHẢO)",
        "Giao dịch theo đối tượng, chưa phân bổ tự động vào riêng phiên đơn này",
        7,
    )
    ws.append([])
    ws.append(["Ngày", "Loại", "Nhóm", "Đối tượng", "Số tiền", "Nội dung", "Ngày tạo"])
    for row in conn.execute(
        "SELECT * FROM payments WHERE payment_date=? ORDER BY id", (batch["work_date"],)
    ):
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


def invoice_vat_percent(value):
    """Return the exact percentage/code expected by the customer's 13-column template."""

    raw = clean_text(value).upper().replace(" ", "")
    aliases = {
        "KCT": -1,
        "KHÔNGCHỊUTHUẾ": -1,
        "KHONGCHIUTHUE": -1,
        "KKKNT": -2,
        "KHÔNGKÊKHAI": -2,
        "KHONGKEKHAI": -2,
    }
    if raw in aliases:
        return aliases[raw]
    has_percent = raw.endswith("%")
    numeric = number_value(raw.rstrip("%"), 0)
    if not has_percent and 0 < abs(numeric) < 1:
        numeric *= 100
    return round(numeric, 4)


def vnd_round(value):
    """Round VND with the commercial HALF_UP rule used by M-Invoice."""
    try:
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def vnd_product(*values):
    try:
        total = Decimal("1")
        for value in values:
            total *= Decimal(str(value))
        return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def invoice_workbook(rows, invoice_names=None):
    invoice_names = invoice_names or {}
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(INVOICE_HEADERS)
    for item in rows:
        qty = net_delivered(item)
        unit_price = vnd_round(number_value(item["sell_price"]))
        amount = vnd_product(qty, unit_price)
        invoice_name = invoice_names.get(item["product_code"], item["product_name"])
        name_key = slug(f"{item['product_name']} {invoice_name} {item.get('note', '')}")
        is_promotion = clean_text(item.get("invoice_nature")) == "2" or (
            "khuyenmai" in name_key and unit_price <= 0
        )
        vat_percent = invoice_vat_percent(item["tax"])
        tax_amount = 0 if vat_percent <= 0 else vnd_product(amount, vat_percent / 100)
        total = amount + tax_amount
        if is_promotion:
            money_cells = [None, None, None, None, None]
            nature = "2"
        else:
            money_cells = [unit_price, amount, amount, tax_amount, total]
            nature = "1"
        ws.append([
            item["product_code"], invoice_name, item["unit"], qty,
            money_cells[0], money_cells[1], None, None, money_cells[2],
            vat_percent, money_cells[3], money_cells[4], nature,
        ])
    style_table(ws, 1, 13)
    for col in (4, 5, 6, 8, 9, 11, 12):
        for row in range(2, ws.max_row + 1):
            ws.cell(row, col).number_format = "#,##0"
    ws.column_dimensions["B"].width = max(ws.column_dimensions["B"].width or 0, 42)
    autosize(ws)
    return wb


def export_invoices_zip(conn, batch, orders):
    invoice_names = {
        row["product_code"]: row["invoice_name"]
        for row in conn.execute("SELECT product_code,invoice_name FROM outgoing_product_names")
    }
    groups = defaultdict(list)
    for item in orders:
        vat_percent = invoice_vat_percent(item["tax"])
        tax_key = {-2: "KKKNT", -1: "KCT"}.get(vat_percent, f"{vat_percent:g}%")
        groups[(item["contractor"] or "KHAC", tax_key)].append(item)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = ["FILE TẢI PHẦN MỀM TRUNG GIAN", "",
                    "Các file đúng 13 cột theo mẫu thuế khách cung cấp.",
                    "Dữ liệu đã qua bước kiểm tồn và giữ tồn khi tạo dự thảo đầu ra.", ""]
        for (contractor, tax_key), rows in sorted(groups.items()):
            wb_stream = workbook_bytes(invoice_workbook(rows, invoice_names))
            has_promotion = any(
                clean_text(item.get("invoice_nature")) == "2" or (
                    "khuyenmai" in slug(
                        f"{item['product_name']} {invoice_names.get(item['product_code'], item['product_name'])} {item.get('note', '')}"
                    ) and number_value(item["sell_price"]) <= 0
                )
                for item in rows
            )
            suffix = "_co_khuyen_mai" if has_promotion else ""
            filename = f"Hoa_don_{safe_sheet_name(contractor)}_{tax_key}{suffix}_{batch['work_date']}.xlsx"
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
            return send_xlsx(export_report(conn, batch, orders), f"Bao_cao_phien_{stamp}.xlsx")
        if kind == "purchases":
            return send_xlsx(export_purchase_documents(conn, batch, orders), f"Bang_ke_bien_nhan_{stamp}.xlsx")
        if kind == "invoices":
            if batch["status"] != "approved":
                return jsonify({"ok": False, "error": "Phải duyệt phiên đơn trước khi tạo file hóa đơn"}), 409
            active_drafts = [dict(row) for row in conn.execute(
                """SELECT contractor,status FROM outgoing_invoice_drafts
                   WHERE batch_id=? AND status!='cancelled'""",
                (batch_id,),
            )]
            if not active_drafts:
                return jsonify({
                    "ok": False,
                    "error": "Cần bấm Kiểm tra tồn & tạo dự thảo đầu ra trước khi tải ZIP hóa đơn",
                }), 409
            if any(item["status"] == "issued" for item in active_drafts):
                return jsonify({
                    "ok": False,
                    "error": "Phiên đã có hóa đơn phát hành; không tạo lại ZIP để tránh xuất trùng",
                }), 409
            required_contractors = {
                item["contractor"] or "KHAC" for item in orders if net_delivered(item) > 0
            }
            draft_contractors = {item["contractor"] or "KHAC" for item in active_drafts}
            missing = sorted(required_contractors - draft_contractors)
            if missing:
                return jsonify({
                    "ok": False,
                    "error": "Dự thảo chưa giữ tồn đủ cho: " + ", ".join(missing),
                }), 409
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
    try:
        if not ipaddress.ip_address(request.remote_addr or "").is_loopback:
            return jsonify({
                "ok": False,
                "error": "Chỉ được tải toàn bộ bản sao dữ liệu trực tiếp trên máy chủ",
            }), 403
    except ValueError:
        return jsonify({"ok": False, "error": "Không xác định được máy yêu cầu sao lưu"}), 403
    if not DB_PATH.is_file():
        return jsonify({"ok": False, "error": "Cơ sở dữ liệu chưa sẵn sàng để sao lưu"}), 503
    backup_path = DATA_DIR / (
        f"backup_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:10]}.sqlite3"
    )
    source = target = None
    try:
        source = sqlite3.connect(DB_PATH)
        target = sqlite3.connect(backup_path)
        source.backup(target)
    except (OSError, sqlite3.Error):
        try:
            backup_path.unlink(missing_ok=True)
        except OSError:
            pass
        return jsonify({"ok": False, "error": "Không tạo được bản sao dữ liệu nhất quán"}), 503
    finally:
        if target is not None:
            target.close()
        if source is not None:
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


def api_debt_adjustment_guarded():
    """Validated, audited replacement for the contract-module adjustment route."""
    body = request.get_json(silent=True) or {}
    party_type = clean_text(body.get("party_type")).lower()
    party_code_input = clean_text(body.get("party_code"))
    note = clean_text(body.get("note"))
    if party_type not in {"contractor", "supplier"}:
        return jsonify({"ok": False, "error": "Nhóm công nợ không hợp lệ"}), 400
    if not party_code_input:
        return jsonify({"ok": False, "error": "Thiếu mã nhà thầu/nhà cung cấp"}), 400
    if not note:
        return jsonify({"ok": False, "error": "Điều chỉnh công nợ phải có lý do"}), 400
    try:
        adjustment_date = valid_iso_date(body.get("adjustment_date"), "Ngày điều chỉnh")
        amount = finite_number(body.get("amount"), "Số tiền điều chỉnh")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if amount == 0:
        return jsonify({"ok": False, "error": "Số tiền điều chỉnh phải khác 0"}), 400
    with db() as conn:
        try:
            party_code = canonical_party_code(conn, party_type, party_code_input)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        cur = conn.execute(
            """INSERT INTO debt_adjustments(
                   adjustment_date,party_type,party_code,amount,note,created_at
               ) VALUES(?,?,?,?,?,?)""",
            (adjustment_date, party_type, party_code, amount, note, now_iso()),
        )
        audit_event(
            conn, "debt.adjustment.create", entity_type=party_type, entity_id=party_code,
            metadata={"adjustment_id": cur.lastrowid, "adjustment_date": adjustment_date,
                      "amount": amount},
        )
        return jsonify({"ok": True, "id": cur.lastrowid})


def api_attendance_guarded():
    """Validated, audited replacement for manual attendance entry."""
    body = request.get_json(silent=True) or {}
    employee_code = clean_text(body.get("employee_code")).upper()
    if not employee_code:
        return jsonify({"ok": False, "error": "Thiếu mã nhân sự"}), 400
    try:
        work_date = valid_iso_date(body.get("work_date"), "Ngày chấm công")
        hours = {
            key: finite_number(body.get(key), label, default=0)
            for key, label in (
                ("normal_hours", "Giờ thường"),
                ("overtime_hours", "Giờ tăng ca"),
                ("sunday_hours", "Giờ Chủ nhật"),
                ("night_hours", "Giờ ca đêm"),
                ("holiday_hours", "Giờ ngày lễ"),
            )
        }
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if any(value < 0 or value > 24 for value in hours.values()):
        return jsonify({"ok": False, "error": "Mỗi loại giờ công phải nằm trong khoảng 0–24"}), 400
    primary_hours = sum(hours[key] for key in (
        "normal_hours", "overtime_hours", "sunday_hours", "holiday_hours",
    ))
    if primary_hours > 24:
        return jsonify({"ok": False, "error": "Tổng giờ thường/tăng ca/Chủ nhật/ngày lễ không được vượt 24 giờ/ngày"}), 400

    with db() as conn:
        staff_row = conn.execute(
            "SELECT id FROM staff WHERE employee_code=?", (employee_code,)
        ).fetchone()
        if not staff_row:
            return jsonify({"ok": False, "error": "Nhân sự không tồn tại"}), 404
        conn.execute(
            """INSERT INTO attendance_entries(
                   employee_id,work_date,normal_hours,overtime_hours,sunday_hours,night_hours,
                   holiday_hours,note,source,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(employee_id,work_date) DO UPDATE SET
                   normal_hours=excluded.normal_hours,overtime_hours=excluded.overtime_hours,
                   sunday_hours=excluded.sunday_hours,night_hours=excluded.night_hours,
                   holiday_hours=excluded.holiday_hours,note=excluded.note,source=excluded.source,
                   updated_at=excluded.updated_at""",
            (
                staff_row["id"], work_date, hours["normal_hours"], hours["overtime_hours"],
                hours["sunday_hours"], hours["night_hours"], hours["holiday_hours"],
                clean_text(body.get("note")), "manual", now_iso(),
            ),
        )
        audit_event(
            conn, "attendance.upsert", entity_type="staff", entity_id=employee_code,
            metadata={"work_date": work_date, **hours},
        )
        return jsonify({"ok": True})


register_contract_routes(app, {
    "db": db,
    "now_iso": now_iso,
    "clean_text": clean_text,
    "number_value": number_value,
    "tax_factor": tax_factor,
    "setting_get": setting_get,
    "setting_set": setting_set,
    "create_minvoice_client": create_minvoice_client,
    "root": ROOT,
    "data_dir": DATA_DIR,
    "require_batch": require_batch,
    "export_supplier_orders": export_supplier_orders,
    "export_deliveries": export_deliveries,
    "export_purchase_documents": export_purchase_documents,
    "export_report": export_report,
})

# Keep the route topology in the contract module while enforcing financial and
# attendance invariants here, in the same SQLite transaction as their audit log.
app.view_functions["api_debt_adjustment"] = api_debt_adjustment_guarded
app.view_functions["api_save_attendance"] = api_attendance_guarded


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    init_database()
    allow_lan = clean_text(os.environ.get("TDP_ALLOW_LAN", "")).lower() in {
        "1", "true", "yes", "co", "có",
    }
    bind_host = "0.0.0.0" if allow_lan else "127.0.0.1"
    print("\nTHÀNH ĐẠT PHÁT – HỆ THỐNG VẬN HÀNH")
    print("Máy này: http://127.0.0.1:8765")
    if allow_lan:
        print(f"Đã bật LAN: http://{local_ip()}:8765")
    else:
        print("LAN đang tắt an toàn. Chỉ bật TDP_ALLOW_LAN=1 khi mạng nội bộ đã được kiểm soát.")
    print("Giữ cửa sổ này mở trong lúc sử dụng. Nhấn Ctrl+C để dừng.\n")
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_browser, daemon=True).start()
    serve(app, host=bind_host, port=8765, threads=8)
