"""Detailed operational receivable ledger sourced only from delivered orders.

This is deliberately separate from issued VAT invoices.  One approved order
line contributes its net delivered quantity at the order's transaction sell
price; receipts, opening balances and debt adjustments remain party-level
ledger entries handled by the existing debt account contract.

Source rows are materialized with stable identities and append-only revisions.
They are never deleted from this ledger: draft/removed/non-chargeable sources
are retained as reversed rows so a later export or audit can explain changes.
"""

from __future__ import annotations

try:
    from document_totals import quantity_totals, quantity_text, quantity_cell
except ImportError:
    from .document_totals import quantity_totals, quantity_text, quantity_cell

import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable

from flask import jsonify, request


RECEIVABLE_STATUSES = ("active", "reversed")


class ReceivableLedgerError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_receivable", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


SCHEMA = """
CREATE TABLE IF NOT EXISTS receivable_ledger_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    source_table TEXT NOT NULL DEFAULT 'orders',
    source_id INTEGER NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    source_revision INTEGER NOT NULL DEFAULT 1,
    source_hash TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    source_row INTEGER NOT NULL DEFAULT 0,
    batch_id INTEGER,
    work_date TEXT NOT NULL,
    contractor_code TEXT NOT NULL DEFAULT '',
    contractor_snapshot TEXT NOT NULL DEFAULT '',
    kitchen_code TEXT NOT NULL DEFAULT '',
    kitchen_snapshot TEXT NOT NULL DEFAULT '',
    product_code TEXT NOT NULL DEFAULT '',
    product_name TEXT NOT NULL DEFAULT '',
    ordered_qty REAL NOT NULL DEFAULT 0,
    actual_delivered REAL NOT NULL DEFAULT 0,
    customer_return_qty REAL NOT NULL DEFAULT 0,
    delivered_qty REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT '',
    sell_price REAL NOT NULL DEFAULT 0,
    tax_code TEXT NOT NULL DEFAULT '',
    tax_percent REAL NOT NULL DEFAULT 0,
    subtotal INTEGER NOT NULL DEFAULT 0,
    tax_amount INTEGER NOT NULL DEFAULT 0,
    amount INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    reversal_reason TEXT NOT NULL DEFAULT '',
    snapshot_hash TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(source_table='orders'),
    CHECK(source_id > 0),
    CHECK(source_revision >= 1),
    CHECK(source_row >= 0),
    CHECK(delivered_qty >= 0),
    CHECK(subtotal >= 0),
    CHECK(tax_amount >= 0),
    CHECK(amount = subtotal + tax_amount),
    CHECK(status IN ('active','reversed')),
    CHECK(revision >= 1)
);
CREATE INDEX IF NOT EXISTS idx_receivable_ledger_period_party
    ON receivable_ledger_lines(work_date,contractor_code,kitchen_code,status,id);
CREATE INDEX IF NOT EXISTS idx_receivable_ledger_source
    ON receivable_ledger_lines(source_table,source_id);

CREATE TABLE IF NOT EXISTS receivable_ledger_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ledger_line_id INTEGER NOT NULL REFERENCES receivable_ledger_lines(id),
    revision INTEGER NOT NULL,
    change_kind TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    source_revision INTEGER NOT NULL DEFAULT 1,
    source_hash TEXT NOT NULL DEFAULT '',
    work_date TEXT NOT NULL,
    contractor_code TEXT NOT NULL DEFAULT '',
    contractor_snapshot TEXT NOT NULL DEFAULT '',
    kitchen_code TEXT NOT NULL DEFAULT '',
    kitchen_snapshot TEXT NOT NULL DEFAULT '',
    product_code TEXT NOT NULL DEFAULT '',
    product_name TEXT NOT NULL DEFAULT '',
    ordered_qty REAL NOT NULL DEFAULT 0,
    actual_delivered REAL NOT NULL DEFAULT 0,
    customer_return_qty REAL NOT NULL DEFAULT 0,
    delivered_qty REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT '',
    sell_price REAL NOT NULL DEFAULT 0,
    tax_code TEXT NOT NULL DEFAULT '',
    tax_percent REAL NOT NULL DEFAULT 0,
    subtotal INTEGER NOT NULL DEFAULT 0,
    tax_amount INTEGER NOT NULL DEFAULT 0,
    amount INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    reversal_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(ledger_line_id,revision),
    CHECK(change_kind IN ('insert','update','reverse','reactivate')),
    CHECK(status IN ('active','reversed')),
    CHECK(revision >= 1),
    CHECK(amount = subtotal + tax_amount)
);
CREATE INDEX IF NOT EXISTS idx_receivable_ledger_revisions_line
    ON receivable_ledger_revisions(ledger_line_id,revision);
"""


def init_receivable_ledger_schema(conn) -> None:
    conn.executescript(SCHEMA)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _mapping_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFD", _clean(value).casefold().replace("đ", "d"))
    return "".join(character for character in normalized if character.isalnum())


def _source_key(source_id: Any, generation: int = 1) -> str:
    # ``orders.id`` is an INTEGER PRIMARY KEY (without AUTOINCREMENT), so SQLite
    # may reuse a deleted highest id.  Keep the original deterministic key for
    # generation one and mint a new key after a source_removed tombstone.
    identity = f"orders\0{int(source_id)}"
    if generation > 1:
        identity += f"\0generation:{int(generation)}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest().upper()


def _source_identity(source_id: Any, existing_by_key) -> tuple[str, dict[str, Any] | None]:
    matches = sorted(
        (
            dict(row) for row in existing_by_key.values()
            if row.get("source_table") == "orders" and int(row.get("source_id") or 0) == int(source_id)
        ),
        key=lambda row: int(row.get("id") or 0),
    )
    if not matches:
        return _source_key(source_id), None
    latest = matches[-1]
    if not (
        latest.get("status") == "reversed"
        and latest.get("reversal_reason") == "source_removed"
    ):
        return str(latest["source_key"]), latest
    return _source_key(source_id, len(matches) + 1), None


def _decimal(value: Any, label: str) -> Decimal:
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise ReceivableLedgerError(f"{label} không phải số hợp lệ") from None
    if not number.is_finite():
        raise ReceivableLedgerError(f"{label} phải là số hữu hạn")
    return number


def _number(value: Any, label: str) -> float:
    return float(_decimal(value, label))


def _vnd(value: Any, label: str = "Số tiền") -> int:
    return int(_decimal(value, label).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _vnd_product(*values: Any) -> int:
    total = Decimal("1")
    for value in values:
        total *= _decimal(value, "Giá trị")
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _tax_percent(value: Any) -> float:
    try:
        from contract_modules import invoice_tax_percent
    except ImportError:  # pragma: no cover - package invocation
        from .contract_modules import invoice_tax_percent
    return float(invoice_tax_percent(value))


def _contractor_catalog(conn):
    exact_codes: dict[str, str] = {}
    code_aliases: dict[str, list[str]] = defaultdict(list)
    names: dict[str, list[str]] = defaultdict(list)
    current_names: dict[str, str] = {}
    for row in conn.execute("SELECT code,name FROM contractors ORDER BY code"):
        code = _clean(row["code"])
        if not code:
            continue
        exact_codes[code] = code
        code_key = _mapping_key(code)
        if code_key and code not in code_aliases[code_key]:
            code_aliases[code_key].append(code)
        current_names[code] = _clean(row["name"])
        name_key = _mapping_key(row["name"])
        if name_key and code not in names[name_key]:
            names[name_key].append(code)
    return exact_codes, code_aliases, names, current_names


def _contractor_reference(raw_value: Any, *, catalog, existing=None) -> tuple[str, str]:
    exact_codes, code_aliases, names, current_names = catalog
    snapshot = _clean(raw_value)
    key = _mapping_key(snapshot)
    if snapshot in exact_codes:
        return exact_codes[snapshot], snapshot
    code_matches = code_aliases.get(key, [])
    if len(code_matches) == 1:
        return code_matches[0], snapshot
    if existing:
        prior_code = _clean(existing.get("contractor_code"))
        if (
            prior_code in current_names
            and key
            and key == _mapping_key(existing.get("contractor_snapshot"))
        ):
            return prior_code, snapshot
    name_matches = names.get(key, [])
    if len(name_matches) == 1:
        return name_matches[0], snapshot
    return snapshot, snapshot


def _candidate_hash(item: dict[str, Any]) -> str:
    fields = (
        "source_table", "source_id", "source_ref", "source_revision", "source_hash",
        "source_sheet", "source_row", "batch_id", "work_date", "contractor_code",
        "contractor_snapshot", "kitchen_code", "kitchen_snapshot", "product_code",
        "product_name", "ordered_qty", "actual_delivered", "customer_return_qty",
        "delivered_qty", "unit", "sell_price", "tax_code", "tax_percent",
        "subtotal", "tax_amount", "amount",
    )
    return hashlib.sha256(
        json.dumps(
            {field: item.get(field) for field in fields}, ensure_ascii=False,
            sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
    ).hexdigest().upper()


def discover_receivable_sources(conn, existing_by_key=None) -> list[dict[str, Any]]:
    """Return the full order projection without mutating the database."""
    existing_by_key = existing_by_key or {}
    catalog = _contractor_catalog(conn)
    candidates: list[dict[str, Any]] = []
    for row in conn.execute(
        """SELECT o.*,b.status batch_status,
                  k.name current_kitchen_name,
                  COALESCE((
                      SELECT r.source_hash FROM order_import_receipts r
                       WHERE r.batch_id=o.batch_id
                       ORDER BY r.created_at,r.import_key LIMIT 1
                  ),'') batch_source_hash
           FROM orders o JOIN batches b ON b.id=o.batch_id
           LEFT JOIN kitchens k ON k.code=o.kitchen
           ORDER BY o.batch_id,o.id"""
    ):
        source_key, existing = _source_identity(row["id"], existing_by_key)
        contractor_code, contractor_snapshot = _contractor_reference(
            row["contractor"], catalog=catalog, existing=existing,
        )
        actual_delivered = _number(row["actual_delivered"], "Số thực giao")
        customer_return = _number(row["customer_return_qty"], "Số khách trả")
        delivered_qty = max(actual_delivered - customer_return, 0)
        sell_price = _number(row["sell_price"], "Giá bán giao dịch")
        if sell_price < 0:
            raise ReceivableLedgerError(
                "Giá bán giao dịch không được âm", code="negative_receivable_price",
            )
        subtotal = _vnd_product(delivered_qty, sell_price)
        tax_percent = _tax_percent(row["tax"])
        tax_amount = 0 if tax_percent <= 0 else _vnd_product(subtotal, tax_percent / 100)
        reason = ""
        if row["batch_status"] != "approved":
            reason = "batch_not_approved"
        elif not contractor_code:
            reason = "missing_contractor"
        elif delivered_qty <= 0:
            reason = "no_net_delivery"
        elif subtotal + tax_amount <= 0:
            reason = "non_chargeable_line"
        item = {
            "source_key": source_key,
            "source_table": "orders",
            "source_id": int(row["id"]),
            "source_ref": f"batch:{row['batch_id']}/order:{row['id']}",
            "source_revision": max(int(row["sell_price_revision"] or 1), 1),
            "source_hash": _clean(row["batch_source_hash"]),
            "source_sheet": _clean(row["source_sheet"]),
            "source_row": max(int(row["source_row"] or 0), 0),
            "batch_id": int(row["batch_id"]),
            "work_date": _clean(row["work_date"]),
            "contractor_code": contractor_code,
            "contractor_snapshot": contractor_snapshot,
            "kitchen_code": _clean(row["kitchen"]),
            "kitchen_snapshot": _clean(row["current_kitchen_name"] or row["kitchen"]),
            "product_code": _clean(row["product_code"]),
            "product_name": _clean(row["product_name"]),
            "ordered_qty": _number(row["qty"], "Số đặt"),
            "actual_delivered": actual_delivered,
            "customer_return_qty": customer_return,
            "delivered_qty": delivered_qty,
            "unit": _clean(row["unit"]),
            "sell_price": sell_price,
            "tax_code": _clean(row["tax"]),
            "tax_percent": tax_percent,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "amount": subtotal + tax_amount,
            "reversal_reason": reason,
        }
        if not item["work_date"]:
            raise ReceivableLedgerError(
                "Dòng phải thu thiếu ngày nguồn", code="missing_receivable_date",
            )
        item["snapshot_hash"] = _candidate_hash(item)
        candidates.append(item)
    return candidates


LINE_FIELDS = (
    "source_table", "source_id", "source_ref", "source_revision", "source_hash",
    "source_sheet", "source_row", "batch_id", "work_date", "contractor_code",
    "contractor_snapshot", "kitchen_code", "kitchen_snapshot", "product_code",
    "product_name", "ordered_qty", "actual_delivered", "customer_return_qty",
    "delivered_qty", "unit", "sell_price", "tax_code", "tax_percent", "subtotal",
    "tax_amount", "amount",
)


def _append_revision(conn, line: dict[str, Any], change_kind: str, timestamp: str) -> None:
    conn.execute(
        """INSERT INTO receivable_ledger_revisions(
               ledger_line_id,revision,change_kind,snapshot_hash,source_revision,source_hash,
               work_date,contractor_code,contractor_snapshot,kitchen_code,kitchen_snapshot,
               product_code,product_name,ordered_qty,actual_delivered,customer_return_qty,
               delivered_qty,unit,sell_price,tax_code,tax_percent,subtotal,tax_amount,amount,
               status,reversal_reason,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            line["id"], line["revision"], change_kind, line["snapshot_hash"],
            line["source_revision"], line["source_hash"], line["work_date"],
            line["contractor_code"], line["contractor_snapshot"], line["kitchen_code"],
            line["kitchen_snapshot"], line["product_code"], line["product_name"],
            line["ordered_qty"], line["actual_delivered"], line["customer_return_qty"],
            line["delivered_qty"], line["unit"], line["sell_price"], line["tax_code"],
            line["tax_percent"], line["subtotal"], line["tax_amount"], line["amount"],
            line["status"], line["reversal_reason"], timestamp,
        ),
    )


def sync_receivable_ledger(conn, *, timestamp: str) -> dict[str, int]:
    """Materialize current order state and append revisions atomically with its caller."""
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='receivable_ledger_lines'"
    ).fetchone() is None:
        raise ReceivableLedgerError(
            "Schema sổ phải thu chưa sẵn sàng", code="receivable_schema_not_ready", status=503,
        )
    existing = {
        row["source_key"]: dict(row)
        for row in conn.execute("SELECT * FROM receivable_ledger_lines ORDER BY id")
    }
    candidates = discover_receivable_sources(conn, existing)
    seen: set[str] = set()
    counters = Counter(inserted=0, updated=0, reversed=0, reactivated=0, unchanged=0)
    for candidate in candidates:
        key = candidate["source_key"]
        if key in seen:
            raise ReceivableLedgerError(
                "Nguồn phải thu sinh trùng khóa dòng; đã dừng để tránh cộng hai lần",
                code="duplicate_receivable_source",
            )
        seen.add(key)
        previous = existing.get(key)
        status = "reversed" if candidate["reversal_reason"] else "active"
        if previous is None:
            columns = (
                "source_key", *LINE_FIELDS, "status", "reversal_reason", "snapshot_hash",
                "revision", "created_at", "updated_at",
            )
            values = (
                key, *(candidate[field] for field in LINE_FIELDS), status,
                candidate["reversal_reason"], candidate["snapshot_hash"], 1,
                timestamp, timestamp,
            )
            cursor = conn.execute(
                f"INSERT INTO receivable_ledger_lines({','.join(columns)}) "
                f"VALUES({','.join('?' for _ in columns)})",
                values,
            )
            line = dict(candidate)
            line.update(id=int(cursor.lastrowid), status=status, revision=1)
            _append_revision(conn, line, "insert", timestamp)
            counters["inserted"] += 1
            counters["reversed"] += int(status == "reversed")
            continue
        source_changed = candidate["snapshot_hash"] != previous["snapshot_hash"]
        state_changed = (
            status != previous["status"]
            or candidate["reversal_reason"] != previous["reversal_reason"]
        )
        if not source_changed and not state_changed:
            counters["unchanged"] += 1
            continue
        revision = int(previous["revision"]) + 1
        conn.execute(
            f"""UPDATE receivable_ledger_lines
                   SET {','.join(f'{field}=?' for field in LINE_FIELDS)},status=?,
                       reversal_reason=?,snapshot_hash=?,revision=?,updated_at=? WHERE id=?""",
            (
                *(candidate[field] for field in LINE_FIELDS), status,
                candidate["reversal_reason"], candidate["snapshot_hash"], revision,
                timestamp, previous["id"],
            ),
        )
        line = dict(candidate)
        line.update(id=previous["id"], status=status, revision=revision)
        if status == "reversed" and previous["status"] != "reversed":
            change_kind = "reverse"
            counters["reversed"] += 1
        elif previous["status"] == "reversed" and status == "active":
            change_kind = "reactivate"
            counters["reactivated"] += 1
        else:
            change_kind = "update"
            counters["updated"] += 1
        _append_revision(conn, line, change_kind, timestamp)

    for key, previous in existing.items():
        if key in seen or (
            previous["status"] == "reversed"
            and previous["reversal_reason"] == "source_removed"
        ):
            continue
        revision = int(previous["revision"]) + 1
        conn.execute(
            """UPDATE receivable_ledger_lines SET status='reversed',
                      reversal_reason='source_removed',revision=?,updated_at=? WHERE id=?""",
            (revision, timestamp, previous["id"]),
        )
        line = dict(previous)
        line.update(
            status="reversed", reversal_reason="source_removed", revision=revision,
        )
        _append_revision(conn, line, "reverse", timestamp)
        counters["reversed"] += 1

    counters["active"] = int(conn.execute(
        "SELECT COUNT(*) n FROM receivable_ledger_lines WHERE status='active'"
    ).fetchone()["n"])
    counters["total"] = int(conn.execute(
        "SELECT COUNT(*) n FROM receivable_ledger_lines"
    ).fetchone()["n"])
    return dict(counters)


def _strict_date(value: Any, label: str) -> str:
    text = _clean(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ReceivableLedgerError(
            f"{label} phải là ngày YYYY-MM-DD hợp lệ", code="invalid_period", status=400,
        ) from None


def _resolve_catalog_filter(requested: Any, catalog, label: str) -> str:
    value = _clean(requested)
    if not value:
        return ""
    exact_codes, code_aliases, names, _ = catalog
    if value in exact_codes:
        return exact_codes[value]
    key = _mapping_key(value)
    code_matches = code_aliases.get(key, [])
    name_matches = names.get(key, [])
    matches = sorted(set(code_matches + name_matches))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ReceivableLedgerError(
            f"{label} khớp nhiều mã; hãy chọn đúng mã", code="ambiguous_filter", status=400,
        )
    return value


def _kitchen_catalog(conn):
    exact: dict[str, str] = {}
    aliases: dict[str, list[str]] = defaultdict(list)
    names: dict[str, list[str]] = defaultdict(list)
    current_names: dict[str, str] = {}
    for row in conn.execute("SELECT code,name FROM kitchens ORDER BY code"):
        code = _clean(row["code"])
        if not code:
            continue
        exact[code] = code
        key = _mapping_key(code)
        if key and code not in aliases[key]:
            aliases[key].append(code)
        current_names[code] = _clean(row["name"])
        name_key = _mapping_key(row["name"])
        if name_key and code not in names[name_key]:
            names[name_key].append(code)
    return exact, aliases, names, current_names


def receivable_ledger_payload(
    conn, *, date_from: Any, date_to: Any, contractor: Any = "", kitchen: Any = "",
    statuses: Any = None, limit: Any = 5000, offset: Any = 0,
) -> dict[str, Any]:
    safe_from = _strict_date(date_from, "Từ ngày")
    safe_to = _strict_date(date_to, "Đến ngày")
    if safe_from > safe_to:
        raise ReceivableLedgerError(
            "Từ ngày không được lớn hơn Đến ngày", code="invalid_period", status=400,
        )
    if statuses in (None, ""):
        selected_statuses = {"active"}
    elif isinstance(statuses, str) and statuses.strip().casefold() == "all":
        selected_statuses = set(RECEIVABLE_STATUSES)
    else:
        values = statuses if isinstance(statuses, (list, tuple, set)) else str(statuses).split(",")
        selected_statuses = {_clean(value).casefold() for value in values if _clean(value)}
        if not selected_statuses or not selected_statuses.issubset(RECEIVABLE_STATUSES):
            raise ReceivableLedgerError(
                "Trạng thái phải thu không hợp lệ", code="invalid_status", status=400,
            )
    try:
        safe_limit = int(limit)
        safe_offset = int(offset)
    except (TypeError, ValueError):
        raise ReceivableLedgerError(
            "Phân trang không hợp lệ", code="invalid_pagination", status=400,
        ) from None
    if safe_limit < 1 or safe_limit > 20_000 or safe_offset < 0:
        raise ReceivableLedgerError(
            "Phân trang vượt giới hạn", code="invalid_pagination", status=400,
        )

    contractor_catalog = _contractor_catalog(conn)
    kitchen_catalog = _kitchen_catalog(conn)
    contractor_filter = _resolve_catalog_filter(contractor, contractor_catalog, "Nhà thầu")
    kitchen_filter = _resolve_catalog_filter(kitchen, kitchen_catalog, "Bếp")
    contractor_names = contractor_catalog[3]
    kitchen_names = kitchen_catalog[3]
    base_rows = [
        dict(row) for row in conn.execute(
            """SELECT * FROM receivable_ledger_lines
               WHERE work_date>=? AND work_date<=? ORDER BY work_date,id""",
            (safe_from, safe_to),
        )
        if (not contractor_filter or _clean(row["contractor_code"]) == contractor_filter)
        and (not kitchen_filter or _clean(row["kitchen_code"]) == kitchen_filter)
    ]
    status_counts = Counter(row["status"] for row in base_rows)
    selected = [row for row in base_rows if row["status"] in selected_statuses]
    page = selected[safe_offset:safe_offset + safe_limit]
    rows = [{
        "id": int(row["id"]),
        "work_date": row["work_date"],
        "batch_id": row["batch_id"],
        "contractor": {
            "code": row["contractor_code"],
            "name": contractor_names.get(row["contractor_code"]) or row["contractor_snapshot"],
            "source_value": row["contractor_snapshot"],
        },
        "kitchen": {
            "code": row["kitchen_code"],
            "name": kitchen_names.get(row["kitchen_code"]) or row["kitchen_snapshot"],
            "source_value": row["kitchen_snapshot"],
        },
        "product_code": row["product_code"],
        "product_name": row["product_name"],
        "ordered_qty": row["ordered_qty"],
        "actual_delivered": row["actual_delivered"],
        "customer_return_qty": row["customer_return_qty"],
        "delivered_qty": row["delivered_qty"],
        "unit": row["unit"],
        "sell_price": row["sell_price"],
        "tax_code": row["tax_code"],
        "tax_percent": row["tax_percent"],
        "subtotal": int(row["subtotal"]),
        "tax_amount": int(row["tax_amount"]),
        "amount": int(row["amount"]),
        "status": row["status"],
        "reversal_reason": row["reversal_reason"],
        "source": {
            "key": row["source_key"], "table": row["source_table"],
            "id": int(row["source_id"]), "ref": row["source_ref"],
            "revision": int(row["source_revision"]), "hash": row["source_hash"],
            "sheet": row["source_sheet"], "row": int(row["source_row"]),
        },
        "ledger_revision": int(row["revision"]),
    } for row in page]
    active_rows = [row for row in base_rows if row["status"] == "active"]
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for row in active_rows:
        key = (row["contractor_code"], row["kitchen_code"])
        target = groups.setdefault(key, {
            "contractor_code": key[0], "kitchen_code": key[1],
            "line_count": 0, "subtotal": 0, "tax_amount": 0, "amount": 0,
        })
        target["line_count"] += 1
        target["subtotal"] += int(row["subtotal"])
        target["tax_amount"] += int(row["tax_amount"])
        target["amount"] += int(row["amount"])
    return {
        "date_from": safe_from,
        "date_to": safe_to,
        "contractor": contractor_filter or None,
        "kitchen": kitchen_filter or None,
        "statuses": [status for status in RECEIVABLE_STATUSES if status in selected_statuses],
        "rows": rows,
        "pagination": {
            "total": len(selected), "limit": safe_limit, "offset": safe_offset,
            "returned": len(rows),
        },
        "summary": {
            "source_rows": len(base_rows),
            "active_rows": len(active_rows),
            "quantities_by_unit": quantity_totals(active_rows, "delivered_qty"),
            "filtered_quantities_by_unit": quantity_totals(selected, "delivered_qty"),
            "status_counts": {
                status: int(status_counts.get(status, 0)) for status in RECEIVABLE_STATUSES
            },
            "quantity": sum(
                _number(row["delivered_qty"], "Số lượng thực giao") for row in active_rows
            ),
            "subtotal": sum(int(row["subtotal"]) for row in active_rows),
            "tax_amount": sum(int(row["tax_amount"]) for row in active_rows),
            "charge_amount": sum(int(row["amount"]) for row in active_rows),
            "filtered_quantity": sum(
                _number(row["delivered_qty"], "Số lượng thực giao") for row in selected
            ),
            "filtered_subtotal": sum(int(row["subtotal"]) for row in selected),
            "filtered_tax_amount": sum(int(row["tax_amount"]) for row in selected),
            "filtered_amount": sum(int(row["amount"]) for row in selected),
        },
        "kitchen_summary": sorted(
            groups.values(), key=lambda item: (item["contractor_code"], item["kitchen_code"]),
        ),
        "source_of_truth": "approved operational delivery lines; not issued VAT invoices",
    }


def receivable_revision_payload(conn, ledger_line_id: int) -> dict[str, Any]:
    line = conn.execute(
        "SELECT * FROM receivable_ledger_lines WHERE id=?", (int(ledger_line_id),)
    ).fetchone()
    if line is None:
        raise ReceivableLedgerError(
            "Không tìm thấy dòng phải thu", code="receivable_not_found", status=404,
        )
    revisions = [dict(row) for row in conn.execute(
        """SELECT revision,change_kind,source_revision,source_hash,work_date,
                  contractor_code,contractor_snapshot,kitchen_code,kitchen_snapshot,
                  product_code,product_name,ordered_qty,actual_delivered,
                  customer_return_qty,delivered_qty,unit,sell_price,tax_code,tax_percent,
                  subtotal,tax_amount,amount,status,reversal_reason,created_at
           FROM receivable_ledger_revisions WHERE ledger_line_id=? ORDER BY revision""",
        (int(ledger_line_id),),
    )]
    return {
        "line_id": int(line["id"]),
        "source_key": line["source_key"],
        "source_ref": line["source_ref"],
        "revisions": revisions,
    }


def register_receivable_ledger_routes(app, ctx: dict[str, Any]) -> None:
    db_factory: Callable = ctx["db"]

    @app.get("/api/debts/receivables/ledger")
    def api_receivable_ledger():
        today = date.today()
        try:
            with db_factory() as conn:
                return jsonify({
                    "ok": True,
                    **receivable_ledger_payload(
                        conn,
                        date_from=request.args.get("from") or today.replace(day=1).isoformat(),
                        date_to=request.args.get("to") or today.isoformat(),
                        contractor=request.args.get("contractor") or "",
                        kitchen=request.args.get("kitchen") or "",
                        statuses=request.args.get("status"),
                        limit=request.args.get("limit", 5000),
                        offset=request.args.get("offset", 0),
                    ),
                })
        except ReceivableLedgerError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.get("/api/debts/receivables/ledger/<int:ledger_line_id>/revisions")
    def api_receivable_ledger_revisions(ledger_line_id: int):
        try:
            with db_factory() as conn:
                return jsonify({
                    "ok": True,
                    **receivable_revision_payload(conn, ledger_line_id),
                })
        except ReceivableLedgerError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status
