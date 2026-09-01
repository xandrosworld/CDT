"""Meal-factory payment documents built from *actual* attendance.

The module is deliberately independent from Flask so the HTTP layer can wire it
in without duplicating accounting rules.  It never reads ``ordered_count``:
payment is calculated only from ``meal_attendance.actual_count``.  Rates are
profile-scoped and period-scoped; a missing exact ``YYYY-MM`` rate is a hard
error instead of silently reusing another month.

The generated DOCX/XLSX packages are canonicalised after creation.  Given the
same profile, source data and issue date, the returned bytes are identical.  In
addition to making tests reliable, that gives the caller a stable SHA-256 for
approval/audit workflows.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
import secrets
import sqlite3
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable, Iterable

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


XCOM_PAYMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS xcom_payment_profiles (
    profile_code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    document_type TEXT NOT NULL DEFAULT 'MEAL_SIMPLE',
    issuer_name TEXT NOT NULL DEFAULT '',
    issuer_tax_code TEXT NOT NULL DEFAULT '',
    issuer_address TEXT NOT NULL DEFAULT '',
    recipient_name TEXT NOT NULL DEFAULT '',
    recipient_tax_code TEXT NOT NULL DEFAULT '',
    recipient_address TEXT NOT NULL DEFAULT '',
    contract_no TEXT NOT NULL DEFAULT '',
    contract_date TEXT NOT NULL DEFAULT '',
    beneficiary_name TEXT NOT NULL DEFAULT '',
    bank_account TEXT NOT NULL DEFAULT '',
    bank_name TEXT NOT NULL DEFAULT '',
    requester TEXT NOT NULL DEFAULT '',
    seller_signer_name TEXT NOT NULL DEFAULT '',
    seller_signer_title TEXT NOT NULL DEFAULT '',
    buyer_signer_name TEXT NOT NULL DEFAULT '',
    buyer_signer_title TEXT NOT NULL DEFAULT '',
    vat_rate TEXT NOT NULL DEFAULT '0',
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS xcom_payment_profile_scopes (
    profile_code TEXT NOT NULL REFERENCES xcom_payment_profiles(profile_code) ON DELETE CASCADE,
    scope_type TEXT NOT NULL,
    scope_code TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(scope_type, scope_code)
);
CREATE INDEX IF NOT EXISTS idx_xcom_payment_scope_profile
    ON xcom_payment_profile_scopes(profile_code, scope_type, scope_code);

CREATE TABLE IF NOT EXISTS xcom_meal_tariffs (
    profile_code TEXT NOT NULL REFERENCES xcom_payment_profiles(profile_code) ON DELETE CASCADE,
    period TEXT NOT NULL,
    shift TEXT NOT NULL,
    unit_price TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(profile_code, period, shift)
);
CREATE INDEX IF NOT EXISTS idx_xcom_meal_tariff_period
    ON xcom_meal_tariffs(profile_code, period);

CREATE TABLE IF NOT EXISTS xcom_payment_previews (
    token_sha256 TEXT PRIMARY KEY,
    profile_code TEXT NOT NULL REFERENCES xcom_payment_profiles(profile_code) ON DELETE CASCADE,
    date_from TEXT NOT NULL,
    date_to TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_xcom_payment_preview_expiry
    ON xcom_payment_previews(expires_at, used_at);
"""


PROFILE_FIELDS = (
    "display_name",
    "issuer_name",
    "issuer_tax_code",
    "issuer_address",
    "recipient_name",
    "recipient_tax_code",
    "recipient_address",
    "contract_no",
    "contract_date",
    "beneficiary_name",
    "bank_account",
    "bank_name",
    "requester",
    "seller_signer_name",
    "seller_signer_title",
    "buyer_signer_name",
    "buyer_signer_title",
    "note",
)
DOCUMENT_TYPES = {"MEAL_SIMPLE", "MEAL_BOT_BUNDLE"}
SCOPE_TYPES = {"KITCHEN", "XCOM"}
SHIFT_LABELS = {
    "SANG": "Sáng",
    "TRUA": "Trưa",
    "CHIEU": "Chiều",
    "DEM": "Đêm",
    "TONG": "Tổng",
}
PAYMENT_PREVIEW_TTL_MINUTES = 15


class XcomPaymentError(ValueError):
    """Safe, user-displayable validation error."""

    def __init__(self, message: str, *, code: str = "invalid", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _code(value: Any, field: str = "mã") -> str:
    text = _clean(value).upper()
    if not text:
        raise XcomPaymentError(f"Thiếu {field}", code="missing_config", details=[field])
    if len(text) > 100:
        raise XcomPaymentError(f"{field.capitalize()} quá dài", code="invalid")
    return text


def _ascii_key(value: Any) -> str:
    text = _clean(value).lower().replace("đ", "d")
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "", text)


def canonical_shift(value: Any) -> str:
    key = _ascii_key(value)
    if not key:
        raise XcomPaymentError("Thiếu ca ăn", code="invalid_shift")
    if "dem" in key or "toi" in key:
        return "DEM"
    if "sang" in key:
        return "SANG"
    if "trua" in key:
        return "TRUA"
    if "chieu" in key:
        return "CHIEU"
    if key in {"tong", "vaosuat", "tatca"}:
        return "TONG"
    if key.upper() in SHIFT_LABELS:
        return key.upper()
    raise XcomPaymentError(f"Ca ăn không hợp lệ: {_clean(value)}", code="invalid_shift")


def _decimal(value: Any, field: str, *, minimum: Decimal | None = None) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, TypeError, ValueError):
        raise XcomPaymentError(f"{field} không hợp lệ", code="invalid_number") from None
    if not result.is_finite():
        raise XcomPaymentError(f"{field} không hợp lệ", code="invalid_number")
    if minimum is not None and result < minimum:
        raise XcomPaymentError(f"{field} phải từ {minimum} trở lên", code="invalid_number")
    return result


def vnd_half_up(value: Any) -> int:
    return int(_decimal(value, "Số tiền").quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _normal_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _iso_date(value: Any, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _clean(value)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise XcomPaymentError(f"{field} phải theo định dạng YYYY-MM-DD", code="invalid_date") from None


def _iso_timestamp(value: Any, field: str = "Thời điểm") -> tuple[str, datetime]:
    text = _clean(value)
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        raise XcomPaymentError(f"{field} không hợp lệ", code="invalid_timestamp") from None
    parsed = parsed.replace(microsecond=0)
    return parsed.isoformat(), parsed


def _period(value: Any) -> str:
    text = _clean(value)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", text):
        raise XcomPaymentError("Kỳ giá phải theo định dạng YYYY-MM", code="invalid_period")
    return text


def _validate_tax_code(value: Any, field: str) -> str:
    """Vietnamese enterprise MST: 10 digits or 10 digits + '-' + 3 digits."""

    text = _clean(value)
    if text and not re.fullmatch(r"\d{10}(?:-\d{3})?", text):
        raise XcomPaymentError(
            f"{field} phải gồm 10 chữ số hoặc dạng 10 chữ số-3 chữ số",
            code="invalid_tax_code",
            details=[field],
        )
    return text


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if isinstance(row, sqlite3.Row):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    raise TypeError("Database rows must be mapping-compatible")


def init_xcom_payment_schema(conn) -> None:
    """Create the isolated profile/scope/tariff schema on the caller's DB."""

    conn.executescript(XCOM_PAYMENT_SCHEMA)


def upsert_payment_profile(
    conn,
    profile: dict[str, Any],
    *,
    now_iso: Callable[[], str] = _now_iso,
) -> dict[str, Any]:
    """Create/update a profile without inventing absent legal or bank fields."""

    profile_code = _code(profile.get("profile_code"), "mã hồ sơ thanh toán")
    document_type = _clean(profile.get("document_type") or "MEAL_SIMPLE").upper()
    if document_type not in DOCUMENT_TYPES:
        raise XcomPaymentError("Loại chứng từ không hợp lệ", code="invalid_document_type")
    vat_rate = _decimal(profile.get("vat_rate", 0), "Thuế suất", minimum=Decimal("0"))
    if vat_rate > 100:
        raise XcomPaymentError("Thuế suất không được lớn hơn 100%", code="invalid_number")
    values = {field: _clean(profile.get(field)) for field in PROFILE_FIELDS}
    values["issuer_tax_code"] = _validate_tax_code(values["issuer_tax_code"], "MST bên bán")
    values["recipient_tax_code"] = _validate_tax_code(values["recipient_tax_code"], "MST bên mua")
    values.update({
        "profile_code": profile_code,
        "document_type": document_type,
        "vat_rate": format(vat_rate.normalize(), "f"),
    })
    existing_row = conn.execute(
        "SELECT * FROM xcom_payment_profiles WHERE profile_code=?", (profile_code,)
    ).fetchone()
    if existing_row:
        existing = _row_dict(existing_row)
        changed = any(str(existing.get(key) or "") != str(values[key] or "") for key in values)
        if changed:
            assignments = ",".join(f"{field}=?" for field in (*PROFILE_FIELDS, "document_type", "vat_rate"))
            conn.execute(
                f"UPDATE xcom_payment_profiles SET {assignments},updated_at=? WHERE profile_code=?",
                tuple(values[field] for field in (*PROFILE_FIELDS, "document_type", "vat_rate"))
                + (now_iso(), profile_code),
            )
        return {"profile_code": profile_code, "created": False, "changed": changed}
    columns = ("profile_code", *PROFILE_FIELDS, "document_type", "vat_rate", "updated_at")
    conn.execute(
        f"INSERT INTO xcom_payment_profiles({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
        tuple(values.get(field, now_iso() if field == "updated_at" else "") for field in columns),
    )
    return {"profile_code": profile_code, "created": True, "changed": True}


def assign_payment_scope(
    conn,
    profile_code: str,
    scope_type: str,
    scope_code: str,
    *,
    now_iso: Callable[[], str] = _now_iso,
) -> dict[str, Any]:
    """Assign a kitchen or XCOM unit to exactly one payment profile."""

    profile_code = _code(profile_code, "mã hồ sơ thanh toán")
    if not conn.execute(
        "SELECT 1 FROM xcom_payment_profiles WHERE profile_code=?", (profile_code,)
    ).fetchone():
        raise XcomPaymentError("Hồ sơ thanh toán không tồn tại", code="not_found")
    scope_type = _clean(scope_type).upper()
    if scope_type not in SCOPE_TYPES:
        raise XcomPaymentError("Phạm vi phải là KITCHEN hoặc XCOM", code="invalid_scope")
    scope_code = _code(scope_code, "mã phạm vi")
    previous = conn.execute(
        "SELECT profile_code FROM xcom_payment_profile_scopes WHERE scope_type=? AND scope_code=?",
        (scope_type, scope_code),
    ).fetchone()
    previous_code = _row_dict(previous)["profile_code"] if previous else ""
    changed = previous_code != profile_code
    if changed:
        conn.execute(
            """INSERT INTO xcom_payment_profile_scopes(profile_code,scope_type,scope_code,updated_at)
               VALUES(?,?,?,?) ON CONFLICT(scope_type,scope_code) DO UPDATE SET
               profile_code=excluded.profile_code,updated_at=excluded.updated_at""",
            (profile_code, scope_type, scope_code, now_iso()),
        )
    return {
        "profile_code": profile_code,
        "scope_type": scope_type,
        "scope_code": scope_code,
        "changed": changed,
    }


def upsert_meal_tariff(
    conn,
    profile_code: str,
    period: str,
    shift: str,
    unit_price: Any,
    *,
    now_iso: Callable[[], str] = _now_iso,
) -> dict[str, Any]:
    """Persist an exact-period rate.  There is intentionally no fallback rate."""

    profile_code = _code(profile_code, "mã hồ sơ thanh toán")
    if not conn.execute(
        "SELECT 1 FROM xcom_payment_profiles WHERE profile_code=?", (profile_code,)
    ).fetchone():
        raise XcomPaymentError("Hồ sơ thanh toán không tồn tại", code="not_found")
    period = _period(period)
    shift = canonical_shift(shift)
    price = _decimal(unit_price, "Đơn giá suất ăn", minimum=Decimal("0"))
    if price == 0:
        raise XcomPaymentError("Đơn giá suất ăn phải lớn hơn 0", code="invalid_number")
    # VND has no fractional minor unit.  Normalise the configured tariff once
    # with HALF_UP so every visible formula uses the exact same integer rate as
    # the server-side calculation.
    price_text = str(vnd_half_up(price))
    previous = conn.execute(
        "SELECT unit_price FROM xcom_meal_tariffs WHERE profile_code=? AND period=? AND shift=?",
        (profile_code, period, shift),
    ).fetchone()
    previous_price = str(_row_dict(previous)["unit_price"]) if previous else ""
    changed = previous_price != price_text
    if changed:
        conn.execute(
            """INSERT INTO xcom_meal_tariffs(profile_code,period,shift,unit_price,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(profile_code,period,shift) DO UPDATE SET
               unit_price=excluded.unit_price,updated_at=excluded.updated_at""",
            (profile_code, period, shift, price_text, now_iso()),
        )
    return {
        "profile_code": profile_code,
        "period": period,
        "shift": shift,
        "unit_price": price_text,
        "changed": changed,
    }


def get_payment_profile(conn, profile_code: str) -> dict[str, Any]:
    code = _code(profile_code, "mã hồ sơ thanh toán")
    row = conn.execute("SELECT * FROM xcom_payment_profiles WHERE profile_code=?", (code,)).fetchone()
    if not row:
        raise XcomPaymentError("Hồ sơ thanh toán không tồn tại", code="not_found")
    profile = _row_dict(row)
    profile["scopes"] = [
        _row_dict(item)
        for item in conn.execute(
            """SELECT scope_type,scope_code FROM xcom_payment_profile_scopes
               WHERE profile_code=? ORDER BY scope_type,scope_code""",
            (code,),
        ).fetchall()
    ]
    return profile


def list_payment_profiles(conn) -> list[dict[str, Any]]:
    """Return profiles with their exact scopes and period tariffs."""

    profiles = []
    for row in conn.execute("SELECT profile_code FROM xcom_payment_profiles ORDER BY profile_code"):
        profile = get_payment_profile(conn, row["profile_code"])
        profile["tariffs"] = [
            _row_dict(item)
            for item in conn.execute(
                """SELECT period,shift,unit_price,updated_at FROM xcom_meal_tariffs
                   WHERE profile_code=? ORDER BY period DESC,shift""",
                (profile["profile_code"],),
            ).fetchall()
        ]
        profiles.append(profile)
    return profiles


def delete_payment_profile(conn, profile_code: str) -> bool:
    code = _code(profile_code, "mã hồ sơ thanh toán")
    return conn.execute(
        "DELETE FROM xcom_payment_profiles WHERE profile_code=?", (code,)
    ).rowcount == 1


def remove_payment_scope(conn, scope_type: str, scope_code: str) -> bool:
    scope_type = _clean(scope_type).upper()
    if scope_type not in SCOPE_TYPES:
        raise XcomPaymentError("Phạm vi phải là KITCHEN hoặc XCOM", code="invalid_scope")
    scope_code = _code(scope_code, "mã phạm vi")
    return conn.execute(
        "DELETE FROM xcom_payment_profile_scopes WHERE scope_type=? AND scope_code=?",
        (scope_type, scope_code),
    ).rowcount == 1


def delete_meal_tariff(conn, profile_code: str, period: str, shift: str) -> bool:
    code = _code(profile_code, "mã hồ sơ thanh toán")
    period = _period(period)
    shift = canonical_shift(shift)
    return conn.execute(
        "DELETE FROM xcom_meal_tariffs WHERE profile_code=? AND period=? AND shift=?",
        (code, period, shift),
    ).rowcount == 1


def _validate_profile_for_output(profile: dict[str, Any]) -> None:
    required = [
        "issuer_name",
        "recipient_name",
        "beneficiary_name",
        "bank_account",
        "bank_name",
        "requester",
    ]
    if profile.get("document_type") == "MEAL_BOT_BUNDLE":
        required.extend([
            "issuer_tax_code",
            "issuer_address",
            "recipient_tax_code",
            "recipient_address",
            "contract_no",
            "contract_date",
            "seller_signer_name",
            "seller_signer_title",
            "buyer_signer_name",
            "buyer_signer_title",
        ])
    missing = [field for field in required if not _clean(profile.get(field))]
    if missing:
        raise XcomPaymentError(
            "Hồ sơ thanh toán còn thiếu dữ liệu bắt buộc; hệ thống không tự đoán thông tin pháp lý, người ký hoặc tài khoản",
            code="missing_config",
            details=missing,
        )
    _validate_tax_code(profile.get("issuer_tax_code"), "MST bên bán")
    _validate_tax_code(profile.get("recipient_tax_code"), "MST bên mua")


def _attendance_rows_for_profile(
    conn,
    profile_code: str,
    date_from: str,
    date_to: str,
) -> list[dict[str, Any]]:
    scopes = {
        (str(row["scope_type"]).upper(), str(row["scope_code"]).upper()): str(row["profile_code"]).upper()
        for row in conn.execute("SELECT profile_code,scope_type,scope_code FROM xcom_payment_profile_scopes")
    }
    if not any(value == profile_code for value in scopes.values()):
        raise XcomPaymentError("Hồ sơ chưa được gán bếp hoặc XCOM", code="missing_scope")
    unit_by_kitchen = {
        str(row["kitchen_code"]).upper(): str(row["unit_code"]).upper()
        for row in conn.execute("SELECT kitchen_code,unit_code FROM kitchen_units")
    }
    result = []
    rows = conn.execute(
        """SELECT work_date,kitchen,shift,actual_count
           FROM meal_attendance
           WHERE work_date>=? AND work_date<=? AND actual_count!=0
           ORDER BY work_date,kitchen,shift""",
        (date_from, date_to),
    ).fetchall()
    for raw in rows:
        row = _row_dict(raw)
        kitchen = _clean(row.get("kitchen")).upper()
        unit_code = unit_by_kitchen.get(kitchen, "")
        assigned_profile = scopes.get(("KITCHEN", kitchen)) or scopes.get(("XCOM", unit_code))
        if assigned_profile != profile_code:
            continue
        quantity = _decimal(row.get("actual_count"), "Số suất ăn thực tế", minimum=Decimal("0"))
        if quantity == 0:
            continue
        if quantity != quantity.to_integral_value():
            raise XcomPaymentError(
                "Số suất ăn thực tế phải là số nguyên; hệ thống không tự làm tròn suất ăn",
                code="invalid_actual_count",
                details={
                    "work_date": _clean(row.get("work_date")),
                    "kitchen": kitchen,
                    "shift": _clean(row.get("shift")),
                    "actual_count": str(quantity),
                },
            )
        work_date = _iso_date(row.get("work_date"), "Ngày chấm suất")
        result.append({
            "work_date": work_date,
            "period": work_date[:7],
            "kitchen": kitchen,
            "unit_code": unit_code,
            "shift": canonical_shift(row.get("shift")),
            "quantity_decimal": quantity,
        })
    return result


def build_meal_payment_summary(
    conn,
    profile_code: str,
    date_from: Any,
    date_to: Any,
) -> dict[str, Any]:
    """Calculate a payment summary from actual_count using exact-period rates."""

    profile = get_payment_profile(conn, profile_code)
    profile_code = str(profile["profile_code"]).upper()
    _validate_profile_for_output(profile)
    date_from = _iso_date(date_from, "Từ ngày")
    date_to = _iso_date(date_to, "Đến ngày")
    if date_from > date_to:
        raise XcomPaymentError("Từ ngày không được sau đến ngày", code="invalid_date_range")
    raw_rows = _attendance_rows_for_profile(conn, profile_code, date_from, date_to)
    if not raw_rows:
        raise XcomPaymentError("Không có suất ăn thực tế trong khoảng đã chọn", code="no_actual_attendance")

    tariff_rows = conn.execute(
        "SELECT period,shift,unit_price FROM xcom_meal_tariffs WHERE profile_code=?",
        (profile_code,),
    ).fetchall()
    tariffs = {
        (str(row["period"]), str(row["shift"]).upper()): _decimal(row["unit_price"], "Đơn giá")
        for row in tariff_rows
    }
    missing_tariffs = sorted({
        f"{row['period']} / {SHIFT_LABELS[row['shift']]}"
        for row in raw_rows
        if (row["period"], row["shift"]) not in tariffs
    })
    if missing_tariffs:
        raise XcomPaymentError(
            "Thiếu đơn giá đúng kỳ; hệ thống không dùng lại giá tháng khác",
            code="missing_tariff",
            details=missing_tariffs,
        )

    grouped: dict[tuple[str, str, str, str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for row in raw_rows:
        key = (row["work_date"], row["period"], row["kitchen"], row["unit_code"], row["shift"])
        grouped[key] += row["quantity_decimal"]

    detail_rows = []
    for (work_date, period, kitchen, unit_code, shift), quantity in sorted(grouped.items()):
        price = tariffs[(period, shift)]
        amount = vnd_half_up(quantity * price)
        detail_rows.append({
            "work_date": work_date,
            "period": period,
            "kitchen": kitchen,
            "unit_code": unit_code,
            "shift": shift,
            "shift_label": SHIFT_LABELS[shift],
            "actual_count": _normal_number(quantity),
            "unit_price": vnd_half_up(price),
            "amount": amount,
        })

    summary_grouped: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in detail_rows:
        key = (row["period"], row["shift"], row["unit_price"])
        entry = summary_grouped.setdefault(key, {
            "period": row["period"],
            "shift": row["shift"],
            "shift_label": row["shift_label"],
            "quantity_decimal": Decimal("0"),
            "unit_price": row["unit_price"],
            "amount": 0,
        })
        entry["quantity_decimal"] += Decimal(str(row["actual_count"]))
        entry["amount"] += int(row["amount"])
    summary_lines = []
    for key in sorted(summary_grouped):
        entry = summary_grouped[key]
        summary_lines.append({
            "period": entry["period"],
            "shift": entry["shift"],
            "shift_label": entry["shift_label"],
            "actual_count": _normal_number(entry["quantity_decimal"]),
            "unit_price": entry["unit_price"],
            "amount": entry["amount"],
        })

    subtotal = sum(row["amount"] for row in detail_rows)
    vat_rate = _decimal(profile.get("vat_rate", "0"), "Thuế suất", minimum=Decimal("0"))
    vat_amount = vnd_half_up(Decimal(subtotal) * vat_rate / Decimal("100"))
    total = subtotal + vat_amount
    canonical_source = {
        "profile_code": profile_code,
        "profile": {
            key: profile.get(key, "")
            for key in ("document_type", *PROFILE_FIELDS, "vat_rate")
        },
        "scopes": sorted(
            ({"scope_type": row["scope_type"], "scope_code": row["scope_code"]} for row in profile["scopes"]),
            key=lambda row: (row["scope_type"], row["scope_code"]),
        ),
        "date_from": date_from,
        "date_to": date_to,
        "rows": detail_rows,
        "vat_rate": format(vat_rate.normalize(), "f"),
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "total": total,
    }
    input_sha256 = hashlib.sha256(
        json.dumps(canonical_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "profile": profile,
        "profile_code": profile_code,
        "document_type": profile["document_type"],
        "date_from": date_from,
        "date_to": date_to,
        "detail_rows": detail_rows,
        "summary_lines": summary_lines,
        "attendance_rows": len(detail_rows),
        "actual_count": _normal_number(sum(
            (Decimal(str(row["actual_count"])) for row in detail_rows), Decimal("0")
        )),
        "vat_rate": format(vat_rate.normalize(), "f"),
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "total": total,
        "input_sha256": input_sha256,
    }


VIET_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def number_to_vietnamese(value: Any) -> str:
    number = vnd_half_up(value)
    if number < 0:
        raise XcomPaymentError("Số tiền không được âm", code="invalid_number")
    if number == 0:
        return "Không đồng"

    def three_digits(group: int, full: bool = False) -> str:
        hundred, remainder = divmod(group, 100)
        ten, unit = divmod(remainder, 10)
        words: list[str] = []
        if hundred or full:
            words.extend((VIET_DIGITS[hundred], "trăm"))
        if ten > 1:
            words.extend((VIET_DIGITS[ten], "mươi"))
            words.append("mốt" if unit == 1 else "lăm" if unit == 5 else VIET_DIGITS[unit] if unit else "")
        elif ten == 1:
            words.append("mười")
            words.append("lăm" if unit == 5 else VIET_DIGITS[unit] if unit else "")
        elif unit:
            if hundred or full:
                words.append("lẻ")
            words.append(VIET_DIGITS[unit])
        return " ".join(word for word in words if word)

    groups: list[int] = []
    while number:
        groups.append(number % 1000)
        number //= 1000
    group_units = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]
    words = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if group:
            words.append(three_digits(group, full=bool(words) and group < 100))
            if index < len(group_units) and group_units[index]:
                words.append(group_units[index])
    text = " ".join(words)
    return text[:1].upper() + text[1:] + " đồng"


def _set_docx_run_font(run, *, size: float = 12, bold: bool | None = None) -> None:
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:ascii"), "Times New Roman")
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), "Times New Roman")
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def _set_cell_margins(cell, *, top=80, start=100, bottom=80, end=100) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _set_table_geometry(table, widths_dxa: Iterable[int], *, indent_dxa: int = 0) -> None:
    widths = [int(width) for width in widths_dxa]
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.first_child_found_in("w:tblW")
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.first_child_found_in("w:tblInd")
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            width = widths[min(index, len(widths) - 1)]
            tc_w = cell._tc.get_or_add_tcPr().get_or_add_tcW()
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            _set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _mark_repeat_header(row) -> None:
    properties = row._tr.get_or_add_trPr()
    header = properties.find(qn("w:tblHeader"))
    if header is None:
        header = OxmlElement("w:tblHeader")
        properties.append(header)
    header.set(qn("w:val"), "true")


def _canonicalize_office_zip(payload: bytes) -> bytes:
    """Remove ZIP timestamps/order as a source of non-deterministic output."""

    source = io.BytesIO(payload)
    output = io.BytesIO()
    with zipfile.ZipFile(source, "r") as archive, zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as canonical:
        for name in sorted(archive.namelist()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            canonical.writestr(info, archive.read(name))
    return output.getvalue()


def _format_vnd(value: Any) -> str:
    return f"{vnd_half_up(value):,}".replace(",", ".")


def _format_date_vn(value: str) -> str:
    parsed = date.fromisoformat(value)
    return parsed.strftime("%d/%m/%Y")


def build_simple_payment_request_docx(summary: dict[str, Any], issue_date: Any) -> bytes:
    """Create the compact meal-payment request used by non-BOT profiles."""

    profile = dict(summary["profile"])
    _validate_profile_for_output(profile)
    issue_date = _iso_date(issue_date, "Ngày lập chứng từ")
    document = Document()
    section = document.sections[0]
    # Named form override: Vietnamese accounting forms are A4, not US Letter.
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    normal.font.size = Pt(12)
    normal.paragraph_format.space_after = Pt(3)
    normal.paragraph_format.line_spacing = 1.08

    header = document.add_table(rows=1, cols=2)
    _set_table_geometry(header, (4200, 5000))
    left = header.cell(0, 0).paragraphs[0]
    left.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_docx_run_font(left.add_run(profile["issuer_name"].upper()), size=11.5, bold=True)
    right = header.cell(0, 1).paragraphs[0]
    right.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_docx_run_font(
        right.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc"),
        size=11.5,
        bold=True,
    )
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(14)
    title.paragraph_format.space_after = Pt(4)
    _set_docx_run_font(title.add_run("ĐỀ NGHỊ THANH TOÁN"), size=16, bold=True)
    issue = date.fromisoformat(issue_date)
    issue_paragraph = document.add_paragraph()
    issue_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_docx_run_font(
        issue_paragraph.add_run(f"Ngày {issue.day:02d} tháng {issue.month:02d} năm {issue.year}"),
        size=11.5,
    )

    metadata = [
        ("Kính gửi: ", profile["recipient_name"].upper()),
        ("Đơn vị đề nghị: ", profile["issuer_name"]),
        ("Người đề nghị: ", profile["requester"]),
        (
            "Nội dung: ",
            f"Thanh toán tiền suất ăn thực tế từ {_format_date_vn(summary['date_from'])} "
            f"đến {_format_date_vn(summary['date_to'])}",
        ),
    ]
    if profile.get("contract_no"):
        contract_text = profile["contract_no"]
        if profile.get("contract_date"):
            contract_text += f" ngày {_format_date_vn(_iso_date(profile['contract_date'], 'Ngày hợp đồng'))}"
        metadata.append(("Theo hợp đồng: ", contract_text))
    for label, value in metadata:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(2)
        _set_docx_run_font(paragraph.add_run(label), bold=True)
        _set_docx_run_font(paragraph.add_run(str(value)))

    table = document.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    widths = (580, 1100, 1600, 1250, 1850, 2820)
    _set_table_geometry(table, widths)
    headers = ("STT", "Kỳ", "Ca ăn", "Suất thực tế", "Đơn giá", "Thành tiền (VNĐ)")
    for index, (cell, label) in enumerate(zip(table.rows[0].cells, headers)):
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_docx_run_font(paragraph.add_run(label), size=10.5, bold=True)
    _mark_repeat_header(table.rows[0])
    for index, line in enumerate(summary["summary_lines"], start=1):
        cells = table.add_row().cells
        values = (
            index,
            line["period"],
            line["shift_label"],
            line["actual_count"],
            _format_vnd(line["unit_price"]),
            _format_vnd(line["amount"]),
        )
        for column, (cell, value) in enumerate(zip(cells, values)):
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT if column >= 3 else WD_ALIGN_PARAGRAPH.CENTER
            _set_docx_run_font(paragraph.add_run(str(value)), size=10.5)
    for label, value in (
        ("Cộng tiền trước thuế", summary["subtotal"]),
        (f"Thuế GTGT ({summary['vat_rate']}%)", summary["vat_amount"]),
        ("TỔNG CỘNG", summary["total"]),
    ):
        cells = table.add_row().cells
        merged = cells[0]
        for merge_cell in cells[1:5]:
            merged = merged.merge(merge_cell)
        label_paragraph = cells[0].paragraphs[0]
        label_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_docx_run_font(label_paragraph.add_run(label), size=10.5, bold=True)
        value_paragraph = cells[5].paragraphs[0]
        value_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_docx_run_font(value_paragraph.add_run(_format_vnd(value)), size=10.5, bold=True)

    payment_lines = [
        ("Số tiền bằng chữ: ", number_to_vietnamese(summary["total"]) + "./."),
        ("Hình thức thanh toán: ", "Chuyển khoản"),
        ("Đơn vị thụ hưởng: ", profile["beneficiary_name"]),
        ("Số tài khoản: ", profile["bank_account"]),
        ("Tại ngân hàng: ", profile["bank_name"]),
    ]
    for label, value in payment_lines:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(2)
        _set_docx_run_font(paragraph.add_run(label), bold=True)
        _set_docx_run_font(paragraph.add_run(str(value)))
    signatures = document.add_table(rows=1, cols=2)
    _set_table_geometry(signatures, (4600, 4600))
    signature_values = (
        ("NGƯỜI LẬP", profile.get("requester", "")),
        ("ĐẠI DIỆN ĐƠN VỊ", profile.get("seller_signer_name", "")),
    )
    for cell, (heading, signer) in zip(signatures.rows[0].cells, signature_values):
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_docx_run_font(paragraph.add_run(heading + "\n(Ký, ghi rõ họ tên)"), bold=True)
        if signer:
            _set_docx_run_font(paragraph.add_run("\n\n\n" + signer), bold=True)

    fixed_datetime = datetime.combine(date.fromisoformat(issue_date), datetime.min.time())
    document.core_properties.created = fixed_datetime
    document.core_properties.modified = fixed_datetime
    document.core_properties.author = "Xandro Systems"
    document.core_properties.last_modified_by = "Xandro Systems"
    document.core_properties.title = f"Đề nghị thanh toán {summary['profile_code']} {summary['date_from']} {summary['date_to']}"
    stream = io.BytesIO()
    document.save(stream)
    return _canonicalize_office_zip(stream.getvalue())


THIN_BORDER = Border(
    left=Side(style="thin", color="808080"),
    right=Side(style="thin", color="808080"),
    top=Side(style="thin", color="808080"),
    bottom=Side(style="thin", color="808080"),
)
HEADER_FILL = PatternFill("solid", fgColor="D9EAF7")
TOTAL_FILL = PatternFill("solid", fgColor="FFF2CC")


def _style_xlsx_table(ws, start_row: int, end_row: int, end_column: int) -> None:
    for row in ws.iter_rows(min_row=start_row, max_row=end_row, min_col=1, max_col=end_column):
        for cell in row:
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    for cell in ws[start_row]:
        if cell.column <= end_column:
            cell.font = Font(name="Times New Roman", size=11, bold=True)
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _sheet_setup(ws, *, repeat_rows: str = "") -> None:
    ws.sheet_view.showGridLines = False
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins.left = 0.3
    ws.page_margins.right = 0.3
    ws.page_margins.top = 0.5
    ws.page_margins.bottom = 0.5
    if repeat_rows:
        ws.print_title_rows = repeat_rows


def build_bot_payment_bundle_xlsx(summary: dict[str, Any], issue_date: Any) -> bytes:
    """Create BOT's four-sheet attendance/payment/reconciliation workbook."""

    profile = dict(summary["profile"])
    _validate_profile_for_output(profile)
    if profile.get("document_type") != "MEAL_BOT_BUNDLE":
        raise XcomPaymentError("Hồ sơ không được cấu hình loại MEAL_BOT_BUNDLE", code="invalid_document_type")
    issue_date = _iso_date(issue_date, "Ngày lập chứng từ")
    workbook = Workbook()
    attendance = workbook.active
    attendance.title = "Bảng chấm suất"
    summary_sheet = workbook.create_sheet("Tổng hợp")
    payment = workbook.create_sheet("Đề nghị thanh toán")
    reconcile = workbook.create_sheet("Đối chiếu")
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"

    attendance.merge_cells("A1:I1")
    attendance["A1"] = f"BẢNG CHẤM SUẤT ĂN THỰC TẾ - {profile['recipient_name'].upper()}"
    attendance["A1"].font = Font(name="Times New Roman", size=14, bold=True)
    attendance["A1"].alignment = Alignment(horizontal="center")
    attendance.merge_cells("A2:I2")
    attendance["A2"] = f"Từ {_format_date_vn(summary['date_from'])} đến {_format_date_vn(summary['date_to'])}"
    attendance["A2"].alignment = Alignment(horizontal="center")
    headers = ("STT", "Ngày", "Kỳ", "Bếp", "XCOM", "Ca ăn", "Suất thực tế", "Đơn giá", "Thành tiền")
    for column, label in enumerate(headers, start=1):
        attendance.cell(4, column, label)
    first_data_row = 5
    for index, row in enumerate(summary["detail_rows"], start=first_data_row):
        values = (
            index - first_data_row + 1,
            date.fromisoformat(row["work_date"]),
            row["period"],
            row["kitchen"],
            row["unit_code"],
            row["shift_label"],
            row["actual_count"],
            row["unit_price"],
        )
        for column, value in enumerate(values, start=1):
            attendance.cell(index, column, value)
        attendance.cell(index, 9, f"=ROUND(G{index}*H{index},0)")
        attendance.cell(index, 2).number_format = "dd/mm/yyyy"
        for column in (8, 9):
            attendance.cell(index, column).number_format = "#,##0"
    attendance_end = first_data_row + len(summary["detail_rows"]) - 1
    _style_xlsx_table(attendance, 4, attendance_end, 9)
    widths = (7, 13, 11, 15, 15, 12, 15, 16, 19)
    for column, width in enumerate(widths, start=1):
        attendance.column_dimensions[get_column_letter(column)].width = width
    attendance.freeze_panes = "A5"
    attendance.auto_filter.ref = f"A4:I{attendance_end}"
    attendance.print_area = f"A1:I{attendance_end}"
    _sheet_setup(attendance, repeat_rows="$4:$4")

    summary_sheet.merge_cells("A1:E1")
    summary_sheet["A1"] = "TỔNG HỢP SUẤT ĂN VÀ GIÁ TRỊ THANH TOÁN"
    summary_sheet["A1"].font = Font(name="Times New Roman", size=14, bold=True)
    summary_sheet["A1"].alignment = Alignment(horizontal="center")
    for column, label in enumerate(("Kỳ", "Ca ăn", "Suất thực tế", "Đơn giá", "Thành tiền"), start=1):
        summary_sheet.cell(3, column, label)
    summary_start = 4
    for index, line in enumerate(summary["summary_lines"], start=summary_start):
        summary_sheet.cell(index, 1, line["period"])
        summary_sheet.cell(index, 2, line["shift_label"])
        # SUMIFS keeps the visible calculation tied to the detailed attendance sheet.
        summary_sheet.cell(
            index,
            3,
            f'=SUMIFS(\'Bảng chấm suất\'!$G$5:$G${attendance_end},'
            f'\'Bảng chấm suất\'!$C$5:$C${attendance_end},A{index},'
            f'\'Bảng chấm suất\'!$F$5:$F${attendance_end},B{index})',
        )
        summary_sheet.cell(index, 4, line["unit_price"])
        # Sum the already HALF_UP-rounded daily lines.  Multiplying the monthly
        # aggregate again could differ by 1 VND if a source legitimately
        # contains fractional attendance quantities.
        summary_sheet.cell(
            index,
            5,
            f'=SUMIFS(\'Bảng chấm suất\'!$I$5:$I${attendance_end},'
            f'\'Bảng chấm suất\'!$C$5:$C${attendance_end},A{index},'
            f'\'Bảng chấm suất\'!$F$5:$F${attendance_end},B{index})',
        )
    summary_end = summary_start + len(summary["summary_lines"]) - 1
    subtotal_row = summary_end + 1
    vat_row = summary_end + 2
    total_row = summary_end + 3
    summary_sheet.cell(subtotal_row, 4, "Cộng trước thuế")
    summary_sheet.cell(subtotal_row, 5, f"=SUM(E{summary_start}:E{summary_end})")
    summary_sheet.cell(vat_row, 3, float(Decimal(summary["vat_rate"]) / Decimal("100")))
    summary_sheet.cell(vat_row, 3).number_format = "0.##%"
    summary_sheet.cell(vat_row, 4, f"Thuế GTGT ({summary['vat_rate']}%)")
    summary_sheet.cell(vat_row, 5, f"=ROUND(E{subtotal_row}*C{vat_row},0)")
    summary_sheet.cell(total_row, 4, "TỔNG CỘNG")
    summary_sheet.cell(total_row, 5, f"=E{subtotal_row}+E{vat_row}")
    for row in range(summary_start, total_row + 1):
        for column in (4, 5):
            summary_sheet.cell(row, column).number_format = "#,##0"
    _style_xlsx_table(summary_sheet, 3, total_row, 5)
    for cell in summary_sheet[total_row]:
        cell.fill = TOTAL_FILL
        cell.font = Font(name="Times New Roman", bold=True)
    for column, width in enumerate((13, 18, 18, 18, 21), start=1):
        summary_sheet.column_dimensions[get_column_letter(column)].width = width
    summary_sheet.print_area = f"A1:E{total_row}"
    _sheet_setup(summary_sheet, repeat_rows="$3:$3")

    payment.merge_cells("A1:F1")
    payment["A1"] = profile["issuer_name"].upper()
    payment["A1"].font = Font(name="Times New Roman", size=11, bold=True)
    payment["A1"].alignment = Alignment(horizontal="center")
    payment.merge_cells("G1:L1")
    payment["G1"] = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc"
    payment["G1"].font = Font(name="Times New Roman", size=11, bold=True)
    payment["G1"].alignment = Alignment(horizontal="center", wrap_text=True)
    payment.merge_cells("A3:L3")
    payment["A3"] = "ĐỀ NGHỊ THANH TOÁN"
    payment["A3"].font = Font(name="Times New Roman", size=16, bold=True)
    payment["A3"].alignment = Alignment(horizontal="center")
    payment.merge_cells("A4:L4")
    payment["A4"] = f"Ngày {_format_date_vn(issue_date)}"
    payment["A4"].alignment = Alignment(horizontal="center")
    payment.merge_cells("A6:L6")
    payment["A6"] = f"Kính gửi: {profile['recipient_name'].upper()}"
    payment.merge_cells("A7:L7")
    payment["A7"] = f"MST bên mua: {profile['recipient_tax_code']} | Địa chỉ: {profile['recipient_address']}"
    payment.merge_cells("A8:L8")
    payment["A8"] = f"Đơn vị cung cấp: {profile['issuer_name']}"
    payment.merge_cells("A9:L9")
    payment["A9"] = f"MST bên bán: {profile['issuer_tax_code']} | Địa chỉ: {profile['issuer_address']}"
    payment.merge_cells("A10:L10")
    payment["A10"] = f"Theo hợp đồng số {profile['contract_no']} ngày {_format_date_vn(_iso_date(profile['contract_date'], 'Ngày hợp đồng'))}"
    payment.merge_cells("A11:L11")
    payment["A11"] = f"Thanh toán suất ăn thực tế từ {_format_date_vn(summary['date_from'])} đến {_format_date_vn(summary['date_to'])}"
    payment_header_row = 13
    for column, label in enumerate(("STT", "Kỳ", "Ca", "Suất", "Đơn giá", "Thành tiền"), start=1):
        payment.cell(payment_header_row, column * 2 - 1, label)
        payment.merge_cells(
            start_row=payment_header_row,
            start_column=column * 2 - 1,
            end_row=payment_header_row,
            end_column=column * 2,
        )
    pay_start = payment_header_row + 1
    for index, line in enumerate(summary["summary_lines"], start=pay_start):
        payment.cell(index, 1, index - pay_start + 1)
        payment.merge_cells(start_row=index, start_column=1, end_row=index, end_column=2)
        payment.cell(index, 3, line["period"])
        payment.merge_cells(start_row=index, start_column=3, end_row=index, end_column=4)
        payment.cell(index, 5, line["shift_label"])
        payment.merge_cells(start_row=index, start_column=5, end_row=index, end_column=6)
        payment.cell(index, 7, f"='Tổng hợp'!C{summary_start + index - pay_start}")
        payment.merge_cells(start_row=index, start_column=7, end_row=index, end_column=8)
        payment.cell(index, 9, line["unit_price"])
        payment.cell(index, 9).number_format = "#,##0"
        payment.merge_cells(start_row=index, start_column=9, end_row=index, end_column=10)
        payment.cell(index, 11, f"='Tổng hợp'!E{summary_start + index - pay_start}")
        payment.cell(index, 11).number_format = "#,##0"
        payment.merge_cells(start_row=index, start_column=11, end_row=index, end_column=12)
    pay_end = pay_start + len(summary["summary_lines"]) - 1
    payment_totals = (
        ("Cộng tiền trước thuế", f"='Tổng hợp'!E{subtotal_row}"),
        (f"Thuế GTGT ({summary['vat_rate']}%)", f"='Tổng hợp'!E{vat_row}"),
        ("TỔNG CỘNG", f"='Tổng hợp'!E{total_row}"),
    )
    for offset, (label, formula) in enumerate(payment_totals, start=1):
        row_number = pay_end + offset
        payment.merge_cells(start_row=row_number, start_column=1, end_row=row_number, end_column=10)
        payment.cell(row_number, 1, label)
        payment.cell(row_number, 11, formula)
        payment.cell(row_number, 11).number_format = "#,##0"
        payment.merge_cells(start_row=row_number, start_column=11, end_row=row_number, end_column=12)
    total_pay_row = pay_end + len(payment_totals)
    for row in payment.iter_rows(min_row=payment_header_row, max_row=total_pay_row, min_col=1, max_col=12):
        for cell in row:
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.font = Font(
                name="Times New Roman",
                size=10.5,
                bold=cell.row in (payment_header_row, total_pay_row),
            )
    bank_row = total_pay_row + 2
    bank_lines = (
        f"Số tiền bằng chữ: {number_to_vietnamese(summary['total'])}./.",
        f"Đơn vị thụ hưởng: {profile['beneficiary_name']}",
        f"Số tài khoản: {profile['bank_account']}",
        f"Tại ngân hàng: {profile['bank_name']}",
    )
    for offset, text in enumerate(bank_lines):
        payment.merge_cells(start_row=bank_row + offset, start_column=1, end_row=bank_row + offset, end_column=12)
        payment.cell(bank_row + offset, 1, text)
    signature_row = bank_row + len(bank_lines) + 2
    payment.merge_cells(start_row=signature_row, start_column=1, end_row=signature_row, end_column=3)
    payment.merge_cells(start_row=signature_row, start_column=5, end_row=signature_row, end_column=8)
    payment.merge_cells(start_row=signature_row, start_column=10, end_row=signature_row, end_column=12)
    payment.cell(signature_row, 1, f"ĐẠI DIỆN BÊN MUA\n{profile['buyer_signer_title']}\n\n\n{profile['buyer_signer_name']}")
    payment.cell(signature_row, 5, f"NGƯỜI ĐỀ NGHỊ\n\n\n\n{profile['requester']}")
    payment.cell(signature_row, 10, f"ĐẠI DIỆN BÊN BÁN\n{profile['seller_signer_title']}\n\n\n{profile['seller_signer_name']}")
    payment.row_dimensions[signature_row].height = 88
    for cell in payment[signature_row]:
        cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        cell.font = Font(name="Times New Roman", size=11, bold=True)
    for column in range(1, 13):
        payment.column_dimensions[get_column_letter(column)].width = 9
    payment.print_area = f"A1:L{signature_row}"
    _sheet_setup(payment, repeat_rows=f"${payment_header_row}:${payment_header_row}")

    frozen_values = (
        ("Tổng suất thực tế", summary["actual_count"], f"=SUM('Tổng hợp'!C{summary_start}:C{summary_end})"),
        ("Tiền trước thuế", summary["subtotal"], f"='Tổng hợp'!E{subtotal_row}"),
        ("Thuế GTGT", summary["vat_amount"], f"='Tổng hợp'!E{vat_row}"),
        ("Tổng thanh toán", summary["total"], f"='Tổng hợp'!E{total_row}"),
    )
    for column, label in enumerate(("Chỉ tiêu", "Giá trị nguồn đã khóa", "Giá trị trên chứng từ", "Chênh lệch", "Kết quả"), start=1):
        reconcile.cell(3, column, label)
    for row_index, (label, expected, formula) in enumerate(frozen_values, start=4):
        reconcile.cell(row_index, 1, label)
        reconcile.cell(row_index, 2, expected)
        reconcile.cell(row_index, 3, formula)
        reconcile.cell(row_index, 4, f"=C{row_index}-B{row_index}")
        reconcile.cell(row_index, 5, f'=IF(ABS(D{row_index})<0.000001,"KHỚP","LỆCH")')
        if row_index > 4:
            for column in (2, 3, 4):
                reconcile.cell(row_index, column).number_format = "#,##0"
    reconcile["A1"] = "ĐỐI CHIẾU NGUỒN - CHỨNG TỪ"
    reconcile["A1"].font = Font(name="Times New Roman", size=14, bold=True)
    reconcile.merge_cells("A1:E1")
    reconcile["A2"] = f"SHA-256 dữ liệu đầu vào: {summary['input_sha256']}"
    reconcile.merge_cells("A2:E2")
    _style_xlsx_table(reconcile, 3, 7, 5)
    for column, width in enumerate((24, 24, 24, 18, 16), start=1):
        reconcile.column_dimensions[get_column_letter(column)].width = width
    reconcile.print_area = "A1:E7"
    _sheet_setup(reconcile, repeat_rows="$3:$3")

    fixed_datetime = datetime.combine(date.fromisoformat(issue_date), datetime.min.time())
    workbook.properties.creator = "Xandro Systems"
    workbook.properties.lastModifiedBy = "Xandro Systems"
    workbook.properties.created = fixed_datetime
    workbook.properties.modified = fixed_datetime
    workbook.properties.title = f"Bộ chứng từ suất ăn {summary['profile_code']} {summary['date_from']} {summary['date_to']}"
    stream = io.BytesIO()
    workbook.save(stream)
    return _canonicalize_office_zip(stream.getvalue())


def create_payment_document(
    conn,
    profile_code: str,
    date_from: Any,
    date_to: Any,
    issue_date: Any,
) -> dict[str, Any]:
    """High-level API helper for the Flask route.

    Returns ``payload``, ``filename``, ``mimetype``, the calculated ``summary``
    and stable hashes.  The caller should persist the hashes in its approval
    audit before allowing print/download.
    """

    summary = build_meal_payment_summary(conn, profile_code, date_from, date_to)
    if summary["document_type"] == "MEAL_BOT_BUNDLE":
        payload = build_bot_payment_bundle_xlsx(summary, issue_date)
        extension = "xlsx"
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        payload = build_simple_payment_request_docx(summary, issue_date)
        extension = "docx"
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = (
        f"De_nghi_thanh_toan_suat_an_{summary['profile_code']}_"
        f"{summary['date_from']}_{summary['date_to']}.{extension}"
    )
    return {
        "payload": payload,
        "filename": filename,
        "mimetype": mimetype,
        "summary": summary,
        "input_sha256": summary["input_sha256"],
        "file_sha256": hashlib.sha256(payload).hexdigest(),
    }


def create_payment_preview(
    conn,
    profile_code: str,
    date_from: Any,
    date_to: Any,
    issue_date: Any,
    *,
    now_iso: Callable[[], str] = _now_iso,
    token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ttl_minutes: int = PAYMENT_PREVIEW_TTL_MINUTES,
) -> dict[str, Any]:
    """Create a short-lived approval token bound to the exact preview inputs.

    The raw random token is returned once and only its SHA-256 is persisted.
    The calculation hash covers profile fields, scopes, exact-period tariffs and
    every actual attendance row, so any relevant edit invalidates the preview.
    """

    issue_date = _iso_date(issue_date, "Ngày lập chứng từ")
    summary = build_meal_payment_summary(conn, profile_code, date_from, date_to)
    created_at, created = _iso_timestamp(now_iso(), "Thời điểm tạo bản xem trước")
    if not isinstance(ttl_minutes, int) or ttl_minutes <= 0 or ttl_minutes > 1440:
        raise XcomPaymentError("Thời hạn bản xem trước không hợp lệ", code="invalid_preview_ttl")
    expires_at = (created + timedelta(minutes=ttl_minutes)).isoformat()
    token = str(token_factory() or "")
    if len(token) < 20:
        raise XcomPaymentError("Không tạo được mã bản xem trước an toàn", code="preview_token_error")
    token_sha256 = hashlib.sha256(token.encode("utf-8")).hexdigest()
    # Retain recent used/expired rows for an intelligible single-use error, but
    # prevent this transient table from growing forever.
    cleanup_before = (created - timedelta(days=1)).isoformat()
    conn.execute(
        "DELETE FROM xcom_payment_previews WHERE expires_at<?", (cleanup_before,)
    )
    try:
        conn.execute(
            """INSERT INTO xcom_payment_previews(
                   token_sha256,profile_code,date_from,date_to,issue_date,input_sha256,
                   created_at,expires_at,used_at
               ) VALUES(?,?,?,?,?,?,?,?, '')""",
            (
                token_sha256,
                summary["profile_code"],
                summary["date_from"],
                summary["date_to"],
                issue_date,
                summary["input_sha256"],
                created_at,
                expires_at,
            ),
        )
    except sqlite3.IntegrityError:
        raise XcomPaymentError("Mã bản xem trước bị trùng; vui lòng thử lại", code="preview_token_error") from None
    return {
        "summary": summary,
        "preview_token": token,
        "issue_date": issue_date,
        "expires_at": expires_at,
    }


def consume_payment_preview(
    conn,
    preview_token: Any,
    profile_code: Any,
    date_from: Any,
    date_to: Any,
    issue_date: Any,
    *,
    now_iso: Callable[[], str] = _now_iso,
) -> dict[str, Any]:
    """Atomically verify and consume a preview before generating its document."""

    token = _clean(preview_token)
    if not token:
        raise XcomPaymentError(
            "Cần kiểm tra số liệu trước khi tải chứng từ",
            code="preview_required",
        )
    token_sha256 = hashlib.sha256(token.encode("utf-8")).hexdigest()
    raw = conn.execute(
        "SELECT * FROM xcom_payment_previews WHERE token_sha256=?", (token_sha256,)
    ).fetchone()
    if not raw:
        raise XcomPaymentError("Bản xem trước không tồn tại", code="preview_not_found")
    preview = _row_dict(raw)
    if preview.get("used_at"):
        raise XcomPaymentError(
            "Bản xem trước đã được dùng; hãy kiểm tra lại trước khi tải lần nữa",
            code="preview_used",
        )
    used_at, used = _iso_timestamp(now_iso(), "Thời điểm tải chứng từ")
    _, expires = _iso_timestamp(preview["expires_at"], "Hạn bản xem trước")
    if used >= expires:
        raise XcomPaymentError(
            "Bản xem trước đã hết hạn; hãy kiểm tra lại số liệu",
            code="preview_expired",
        )
    requested = {
        "profile_code": _code(profile_code, "mã hồ sơ thanh toán"),
        "date_from": _iso_date(date_from, "Từ ngày"),
        "date_to": _iso_date(date_to, "Đến ngày"),
        "issue_date": _iso_date(issue_date, "Ngày lập chứng từ"),
    }
    mismatched = [key for key, value in requested.items() if value != preview[key]]
    if mismatched:
        raise XcomPaymentError(
            "Thông tin tải không khớp bản đã kiểm tra; hãy kiểm tra lại số liệu",
            code="preview_mismatch",
            details=mismatched,
        )
    result = create_payment_document(
        conn,
        requested["profile_code"],
        requested["date_from"],
        requested["date_to"],
        requested["issue_date"],
    )
    if not hmac.compare_digest(result["input_sha256"], preview["input_sha256"]):
        raise XcomPaymentError(
            "Dữ liệu suất ăn, đơn giá hoặc hồ sơ đã thay đổi sau khi kiểm tra",
            code="stale_preview",
        )
    consumed = conn.execute(
        """UPDATE xcom_payment_previews SET used_at=?
           WHERE token_sha256=? AND used_at=''""",
        (used_at, token_sha256),
    ).rowcount
    if consumed != 1:
        raise XcomPaymentError(
            "Bản xem trước đã được dùng; hãy kiểm tra lại trước khi tải lần nữa",
            code="preview_used",
        )
    result.update({"preview_created_at": preview["created_at"], "preview_expires_at": preview["expires_at"]})
    return result
