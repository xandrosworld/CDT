"""Detailed, durable supplier-payable ledger.

The operational purchase tables and the customer's historical workbook remain
the authoritative source documents.  This module materializes their payable
effect into stable source-line identities.  Source rows may be replaced by a
new workbook, but ledger rows are never deleted: changes append a revision and
removed/suppressed sources become ``reversed``.

Payment allocation is intentionally not exposed here.  TDP-031 can attach its
allocation transaction to ``set_payable_allocation_total`` without inventing a
FIFO policy or changing the source-line contract established by TDP-030.
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

try:
    from .purchase_money_adjustments import DEDUCTION_KIND, DEDUCTION_LABEL
    from .purchase_returns import RETURN_KIND
except ImportError:
    from purchase_money_adjustments import DEDUCTION_KIND, DEDUCTION_LABEL
    from purchase_returns import RETURN_KIND


PAYABLE_STATUSES = ("open", "partially_paid", "paid", "reversed")
SOURCE_TYPES = ("current_purchase", "current_order", "historical_import")
INTERNAL_STOCK_NAMES = {"kho", "khonoibo", "khohang", "stock"}


class PayableLedgerError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_payable", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


SCHEMA = """
CREATE TABLE IF NOT EXISTS payable_ledger_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_id INTEGER NOT NULL DEFAULT 0,
    source_ref TEXT NOT NULL DEFAULT '',
    source_revision INTEGER NOT NULL DEFAULT 1,
    source_hash TEXT NOT NULL DEFAULT '',
    source_sheet TEXT NOT NULL DEFAULT '',
    source_row INTEGER NOT NULL DEFAULT 0,
    batch_id INTEGER,
    work_date TEXT NOT NULL,
    kitchen TEXT NOT NULL DEFAULT '',
    product_code TEXT NOT NULL DEFAULT '',
    product_name TEXT NOT NULL DEFAULT '',
    actual_qty REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT '',
    supplier_code TEXT NOT NULL DEFAULT '',
    supplier_snapshot TEXT NOT NULL DEFAULT '',
    buy_price REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0,
    paid_amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    reversal_reason TEXT NOT NULL DEFAULT '',
    snapshot_hash TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(source_type IN ('current_purchase','current_order','historical_import')),
    CHECK(status IN ('open','partially_paid','paid','reversed')),
    CHECK(source_revision >= 1),
    CHECK(source_row >= 0),
    CHECK(paid_amount >= 0),
    CHECK(revision >= 1)
);
CREATE INDEX IF NOT EXISTS idx_payable_ledger_date_supplier
    ON payable_ledger_lines(work_date,supplier_code,status,id);
CREATE INDEX IF NOT EXISTS idx_payable_ledger_source
    ON payable_ledger_lines(source_type,source_table,source_id);

CREATE TABLE IF NOT EXISTS payable_ledger_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ledger_line_id INTEGER NOT NULL REFERENCES payable_ledger_lines(id),
    revision INTEGER NOT NULL,
    change_kind TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    source_revision INTEGER NOT NULL DEFAULT 1,
    source_hash TEXT NOT NULL DEFAULT '',
    work_date TEXT NOT NULL,
    kitchen TEXT NOT NULL DEFAULT '',
    product_code TEXT NOT NULL DEFAULT '',
    product_name TEXT NOT NULL DEFAULT '',
    actual_qty REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT '',
    supplier_code TEXT NOT NULL DEFAULT '',
    supplier_snapshot TEXT NOT NULL DEFAULT '',
    buy_price REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0,
    paid_amount REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    reversal_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(ledger_line_id,revision),
    CHECK(change_kind IN ('insert','update','reverse','reactivate','payment_state')),
    CHECK(status IN ('open','partially_paid','paid','reversed')),
    CHECK(revision >= 1)
);
CREATE INDEX IF NOT EXISTS idx_payable_ledger_revisions_line
    ON payable_ledger_revisions(ledger_line_id,revision);
"""


def init_payable_ledger_schema(conn) -> None:
    conn.executescript(SCHEMA)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _mapping_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFD", _clean(value).casefold().replace("đ", "d"))
    return "".join(character for character in normalized if character.isalnum())


def _source_key(*parts: Any) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest().upper()


def _decimal(value: Any, label: str) -> Decimal:
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise PayableLedgerError(f"{label} không phải số hợp lệ") from None
    if not number.is_finite():
        raise PayableLedgerError(f"{label} phải là số hữu hạn")
    return number


def _number(value: Any, label: str) -> float:
    return float(_decimal(value, label))


def _vnd(value: Any) -> int:
    return int(_decimal(value, "Thành tiền").quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _vnd_product(*values: Any) -> int:
    total = Decimal("1")
    for value in values:
        total *= _decimal(value, "Giá trị")
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def payable_line_status(amount: Any, paid_amount: Any, *, reversed_line: bool = False) -> str:
    """Derive one of the four allowed states without auto-allocating payments."""
    if reversed_line:
        return "reversed"
    total = _decimal(amount, "Thành tiền")
    paid = _decimal(paid_amount, "Số đã phân bổ")
    if paid < 0:
        raise PayableLedgerError("Số đã phân bổ không được âm")
    if total <= 0 and paid > 0:
        raise PayableLedgerError(
            "Dòng giá trị không dương không nhận phân bổ thanh toán",
            code="invalid_payable_allocation",
        )
    if total > 0 and paid > total:
        raise PayableLedgerError("Số đã phân bổ vượt thành tiền", code="payable_overpayment")
    if total > 0 and paid == total:
        return "paid"
    if paid > 0:
        return "partially_paid"
    return "open"


def _historical_cutoff(conn) -> str:
    row = conn.execute(
        "SELECT value FROM settings WHERE key='historical_payables_through_date'"
    ).fetchone()
    explicit = _clean(row["value"] if row else "")
    if explicit:
        return explicit
    row = conn.execute(
        "SELECT MAX(purchase_date) through_date FROM historical_payable_lines"
    ).fetchone()
    return _clean(row["through_date"] if row else "")


def _supplier_catalog(
    conn,
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[str]], dict[str, str]]:
    exact_codes: dict[str, str] = {}
    code_aliases: dict[str, list[str]] = defaultdict(list)
    names: dict[str, list[str]] = defaultdict(list)
    current_names: dict[str, str] = {}
    for row in conn.execute("SELECT code,name FROM suppliers ORDER BY code"):
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


def _supplier_reference(
    raw_value: Any,
    *,
    exact_codes: dict[str, str],
    code_aliases: dict[str, list[str]],
    names: dict[str, list[str]],
    current_names: dict[str, str],
    existing: dict[str, Any] | None,
) -> tuple[str, str]:
    snapshot = _clean(raw_value)
    key = _mapping_key(snapshot)
    if snapshot in exact_codes:
        return exact_codes[snapshot], snapshot
    code_matches = code_aliases.get(key, [])
    if len(code_matches) == 1:
        return code_matches[0], snapshot
    # Once a source value has been bound to a stable master code, a later
    # supplier rename must not let another supplier claim that old display
    # name.  Preserve the prior reference while the source value itself is
    # unchanged and the referenced master record still exists.
    if existing:
        prior_code = _clean(existing.get("supplier_code"))
        if (
            prior_code in current_names
            and key
            and key == _mapping_key(existing.get("supplier_snapshot"))
        ):
            return prior_code, snapshot
    name_matches = names.get(key, [])
    if len(name_matches) == 1:
        return name_matches[0], snapshot
    return snapshot, snapshot


def _is_internal_stock(value: Any) -> bool:
    return _mapping_key(value) in INTERNAL_STOCK_NAMES


def _policy_reason(
    *, source_type: str, batch_status: str, source_status: str,
    work_date: str, cutoff: str, supplier: str,
) -> str:
    if source_type == "historical_import":
        return ""
    if batch_status != "approved":
        return "batch_not_approved"
    if source_status and source_status != "confirmed":
        return "source_not_confirmed"
    if _is_internal_stock(supplier):
        return "internal_stock"
    if cutoff and work_date <= cutoff:
        return "covered_by_historical_snapshot"
    return ""


def _candidate_hash(item: dict[str, Any]) -> str:
    fields = (
        "source_type", "source_table", "source_id", "source_ref", "source_revision",
        "source_hash", "source_sheet", "source_row", "batch_id", "work_date",
        "kitchen", "product_code", "product_name", "actual_qty", "unit",
        "supplier_code", "supplier_snapshot", "buy_price", "amount",
    )
    payload = {field: item.get(field) for field in fields}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest().upper()


def _base_candidate(
    *, source_key: str, source_type: str, source_table: str, source_id: int,
    source_ref: str, source_revision: int, source_hash: str, source_sheet: str,
    source_row: int, batch_id: int | None, work_date: str, kitchen: str,
    product_code: str, product_name: str, actual_qty: Any, unit: str,
    raw_supplier: str, buy_price: Any, amount: Any, batch_status: str,
    source_status: str, cutoff: str, supplier_catalog, existing,
) -> dict[str, Any]:
    exact_codes, code_aliases, names, current_names = supplier_catalog
    supplier_code, supplier_snapshot = _supplier_reference(
        raw_supplier, exact_codes=exact_codes, code_aliases=code_aliases,
        names=names, current_names=current_names,
        existing=existing,
    )
    item = {
        "source_key": source_key,
        "source_type": source_type,
        "source_table": source_table,
        "source_id": int(source_id or 0),
        "source_ref": source_ref,
        "source_revision": max(int(source_revision or 1), 1),
        "source_hash": _clean(source_hash),
        "source_sheet": _clean(source_sheet),
        "source_row": max(int(source_row or 0), 0),
        "batch_id": int(batch_id) if batch_id is not None else None,
        "work_date": _clean(work_date),
        "kitchen": _clean(kitchen),
        "product_code": _clean(product_code),
        "product_name": _clean(product_name),
        "actual_qty": _number(actual_qty, "Số lượng thực tế"),
        "unit": _clean(unit),
        "supplier_code": supplier_code,
        "supplier_snapshot": supplier_snapshot,
        "buy_price": _number(buy_price, "Giá mua"),
        "amount": _vnd(amount),
    }
    if not item["work_date"]:
        raise PayableLedgerError("Dòng phải trả thiếu ngày nguồn", code="missing_payable_date")
    item["reversal_reason"] = _policy_reason(
        source_type=source_type,
        batch_status=batch_status,
        source_status=source_status,
        work_date=item["work_date"],
        cutoff=cutoff,
        supplier=supplier_code,
    )
    item["snapshot_hash"] = _candidate_hash(item)
    return item


def _purchase_sheet_sources(conn):
    sources = []
    for source in conn.execute('''SELECT p.*,b.status batch_status,b.work_date
        FROM supplier_plan_sources p JOIN batches b ON b.id=p.batch_id ORDER BY p.batch_id'''):
        sheet = dict(source)
        sheet['items'] = json.loads(sheet['items_json'])
        sheet['issues'] = json.loads(sheet['issues_json'])
        if not sheet['items']:
            sheet['issues'].append('Sheet Đặt hàng chưa có dữ liệu')
        for row in sheet['items']:
            qty = _decimal(row['actual_qty'], 'Số lượng thực tế')
            price = _decimal(row['buy_price'], 'Giá mua')
            amount = _vnd(row['amount'])
            problems = []
            if row['work_date'] != sheet['work_date']:
                problems.append('Ngày mua không khớp phiên đơn')
            if row.get('line_kind') == DEDUCTION_KIND:
                if amount >= 0 or qty != 0 or not row['supplier'] or _is_internal_stock(row['supplier']):
                    problems.append('Khoản trừ tiền mua hộ không hợp lệ')
            else:
                returned = row.get('line_kind') == RETURN_KIND
                if returned and (qty >= 0 or price <= 0 or not row['supplier'] or not row['unit'] or _is_internal_stock(row['supplier'])):
                    problems.append('Dòng trả hàng nhà cung cấp không hợp lệ')
                if (qty < 0 and not returned) or price < 0:
                    problems.append('Số lượng hoặc giá mua âm')
                if qty > 0 and (not row['supplier'] or not row['unit']):
                    problems.append('Thiếu nhà cung cấp hoặc đơn vị tính')
                if qty > 0 and price <= 0 and not _is_internal_stock(row['supplier']):
                    problems.append('Chưa có giá mua trên sheet Đặt hàng')
                if amount != _vnd_product(qty, price):
                    problems.append('Thành tiền lệch số lượng thực tế × giá mua')
            sheet['issues'].extend(f"Dòng {row['source_row']}: {p}" for p in problems)
        sources.append(sheet)
    return sources


def pending_purchase_sheets(conn, date_from, date_to):
    sheets = {s['batch_id']: s for s in _purchase_sheet_sources(conn)}
    result = []
    for batch in conn.execute("SELECT id,work_date FROM batches WHERE status='approved' AND work_date BETWEEN ? AND ? ORDER BY work_date,id", (date_from, date_to)):
        if _historical_cutoff(conn) and batch['work_date'] <= _historical_cutoff(conn):
            continue
        sheet = sheets.get(batch['id'])
        if sheet is not None:
            issues = sheet['issues']
        elif conn.execute("SELECT 1 FROM purchase_workbook_lines WHERE batch_id=? AND status='confirmed' UNION ALL SELECT 1 FROM purchase_order_lines WHERE batch_id=? AND status='confirmed' LIMIT 1", (batch['id'], batch['id'])).fetchone():
            continue
        else:
            issues = ['Web chưa lưu dữ liệu từ sheet Đặt hàng của phiên này; cần đọc bổ sung từ file gốc']
        if issues:
            result.append({'batch_id': batch['id'], 'work_date': batch['work_date'], 'issues': issues})
    return result


def discover_payable_sources(conn, existing_by_key=None) -> list[dict[str, Any]]:
    """Build the complete source projection without changing database state."""
    existing_by_key = existing_by_key or {}
    cutoff = _historical_cutoff(conn)
    catalog = _supplier_catalog(conn)
    candidates: list[dict[str, Any]] = []
    # An approved day's priced purchase sheet is the payable source even when
    # its inventory document is already locked. This projection never posts stock.
    purchase_sheets = _purchase_sheet_sources(conn)
    sheet_batches = {row['batch_id'] for row in purchase_sheets}
    canonical_batches = {
        int(row["batch_id"]) for row in conn.execute(
            "SELECT DISTINCT batch_id FROM purchase_workbook_lines"
        )
    }

    for row in conn.execute(
        """SELECT p.*,b.status batch_status
           FROM purchase_workbook_lines p JOIN batches b ON b.id=p.batch_id
           ORDER BY p.batch_id,p.row_key"""
    ):
        if int(row['batch_id']) in sheet_batches:
            continue
        source_key = _source_key("purchase_workbook_lines", row["batch_id"], row["row_key"])
        candidates.append(_base_candidate(
            source_key=source_key,
            source_type="current_purchase",
            source_table="purchase_workbook_lines",
            source_id=row["id"],
            source_ref=f"batch:{row['batch_id']}/purchase:{row['row_key']}",
            source_revision=row["revision"],
            source_hash=row["source_hash"],
            source_sheet=row["source_sheet"],
            source_row=row["source_row"],
            batch_id=row["batch_id"],
            work_date=row["work_date"],
            kitchen=row["kitchen"],
            product_code=row["product_code"],
            product_name=(DEDUCTION_LABEL + " · " + row["product_name"]
                          if row["line_kind"] == DEDUCTION_KIND else row["product_name"]),
            actual_qty=row["actual_qty"],
            unit=row["unit"],
            raw_supplier=row["supplier"],
            buy_price=row["buy_price"],
            amount=row["amount"],
            batch_status=row["batch_status"],
            source_status=row["status"],
            cutoff=cutoff,
            supplier_catalog=catalog,
            existing=existing_by_key.get(source_key),
        ))

    for sheet in purchase_sheets:
        for row in sheet['items']:
            source_key = _source_key('supplier_plan_sources', sheet['batch_id'], row['row_key'])
            candidates.append(_base_candidate(
                source_key=source_key, source_type='current_purchase',
                source_table='supplier_plan_sources', source_id=sheet['batch_id'],
                source_ref=f"batch:{sheet['batch_id']}/purchase-sheet:{row['row_key']}",
                source_revision=sheet['revision'], source_hash=sheet['source_hash'],
                source_sheet=row['source_sheet'], source_row=row['source_row'],
                batch_id=sheet['batch_id'], work_date=sheet['work_date'],
                kitchen=row['kitchen'], product_code=row['product_code'],
                product_name=(DEDUCTION_LABEL + ' · ' + row['product_name']
                              if row.get('line_kind') == DEDUCTION_KIND else row['product_name']),
                actual_qty=row['actual_qty'], unit=row['unit'], raw_supplier=row['supplier'],
                buy_price=row['buy_price'], amount=row['amount'], batch_status=sheet['batch_status'],
                source_status='confirmed' if not sheet['issues'] else 'invalid_purchase_sheet',
                cutoff=cutoff, supplier_catalog=catalog, existing=existing_by_key.get(source_key),
            ))

    for row in conn.execute(
        """SELECT o.*,b.status batch_status,p.id plan_id,p.order_qty plan_order_qty,
                  p.supplier plan_supplier,p.buy_price plan_buy_price,
                  p.status plan_status,p.source_hash plan_source_hash
           FROM orders o JOIN batches b ON b.id=o.batch_id
           LEFT JOIN purchase_order_lines p ON p.order_id=o.id
           ORDER BY o.batch_id,o.id"""
    ):
        if int(row["batch_id"]) in canonical_batches | sheet_batches:
            continue
        has_plan = row["plan_id"] is not None and row["plan_status"] == "confirmed"
        # A sales order is not evidence of a purchase. Keep compatibility with
        # explicitly confirmed legacy purchases, never infer debt from orders.
        if not has_plan:
            continue
        source_table = "purchase_order_lines"
        source_id = int(row["plan_id"])
        source_hash = row["plan_source_hash"]
        actual_qty = max(_number(row["plan_order_qty"], "Số lượng đặt"), 0)
        supplier = row["plan_supplier"]
        buy_price = row["plan_buy_price"]
        source_status = row["plan_status"]
        source_key = _source_key(source_table, source_id)
        candidates.append(_base_candidate(
            source_key=source_key,
            source_type="current_order",
            source_table=source_table,
            source_id=source_id,
            source_ref=f"batch:{row['batch_id']}/{source_table}:{source_id}",
            source_revision=1,
            source_hash=source_hash,
            source_sheet=row["source_sheet"],
            source_row=row["source_row"],
            batch_id=row["batch_id"],
            work_date=row["work_date"],
            kitchen=row["kitchen"],
            product_code=row["product_code"],
            product_name=row["product_name"],
            actual_qty=actual_qty,
            unit=row["unit"],
            raw_supplier=supplier,
            buy_price=buy_price,
            amount=_vnd_product(actual_qty, buy_price),
            batch_status=row["batch_status"],
            source_status=source_status,
            cutoff=cutoff,
            supplier_catalog=catalog,
            existing=existing_by_key.get(source_key),
        ))

    for row in conn.execute(
        "SELECT * FROM historical_payable_lines ORDER BY source_sheet,source_row,id"
    ):
        source_key = _source_key(
            "historical_payable_lines", _mapping_key(row["source_sheet"]), row["source_row"]
        )
        candidates.append(_base_candidate(
            source_key=source_key,
            source_type="historical_import",
            source_table="historical_payable_lines",
            source_id=row["id"],
            source_ref=f"historical:{row['source_sheet']}:{row['source_row']}",
            source_revision=1,
            source_hash=row["source_hash"],
            source_sheet=row["source_sheet"],
            source_row=row["source_row"],
            batch_id=None,
            work_date=row["purchase_date"],
            kitchen=row["kitchen"],
            product_code="",
            product_name=row["item_name"],
            actual_qty=row["actual_qty"],
            unit=row["unit"],
            raw_supplier=row["supplier"],
            buy_price=row["buy_price"],
            amount=row["amount"],
            batch_status="approved",
            source_status="confirmed",
            cutoff=cutoff,
            supplier_catalog=catalog,
            existing=existing_by_key.get(source_key),
        ))
    return candidates


LINE_FIELDS = (
    "source_type", "source_table", "source_id", "source_ref", "source_revision",
    "source_hash", "source_sheet", "source_row", "batch_id", "work_date",
    "kitchen", "product_code", "product_name", "actual_qty", "unit",
    "supplier_code", "supplier_snapshot", "buy_price", "amount",
)


def _append_revision(conn, line: dict[str, Any], change_kind: str, timestamp: str) -> None:
    conn.execute(
        """INSERT INTO payable_ledger_revisions(
               ledger_line_id,revision,change_kind,snapshot_hash,source_revision,source_hash,
               work_date,kitchen,product_code,product_name,actual_qty,unit,supplier_code,
               supplier_snapshot,buy_price,amount,paid_amount,status,reversal_reason,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            line["id"], line["revision"], change_kind, line["snapshot_hash"],
            line["source_revision"], line["source_hash"], line["work_date"],
            line["kitchen"], line["product_code"], line["product_name"],
            line["actual_qty"], line["unit"], line["supplier_code"],
            line["supplier_snapshot"], line["buy_price"], line["amount"],
            line["paid_amount"], line["status"], line["reversal_reason"], timestamp,
        ),
    )


def sync_payable_ledger(conn, *, timestamp: str) -> dict[str, int]:
    """Synchronize source documents into the append-only payable contract."""
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='payable_ledger_lines'"
    ).fetchone() is None:
        raise PayableLedgerError(
            "Schema sổ phải trả chưa sẵn sàng", code="payable_schema_not_ready", status=503
        )
    existing = {
        row["source_key"]: dict(row)
        for row in conn.execute("SELECT * FROM payable_ledger_lines ORDER BY id")
    }
    candidates = discover_payable_sources(conn, existing)
    seen: set[str] = set()
    counters = Counter(inserted=0, updated=0, reversed=0, reactivated=0, unchanged=0)

    for candidate in candidates:
        key = candidate["source_key"]
        if key in seen:
            raise PayableLedgerError(
                "Nguồn phải trả sinh trùng khóa dòng; đã dừng để tránh cộng hai lần",
                code="duplicate_payable_source",
            )
        seen.add(key)
        previous = existing.get(key)
        forced_reversed = bool(candidate["reversal_reason"])
        if previous is None:
            status = payable_line_status(candidate["amount"], 0, reversed_line=forced_reversed)
            columns = ("source_key", *LINE_FIELDS, "paid_amount", "status", "reversal_reason", "snapshot_hash", "revision", "created_at", "updated_at")
            values = (
                key, *(candidate[field] for field in LINE_FIELDS), 0, status,
                candidate["reversal_reason"], candidate["snapshot_hash"], 1,
                timestamp, timestamp,
            )
            placeholders = ",".join("?" for _ in columns)
            cursor = conn.execute(
                f"INSERT INTO payable_ledger_lines({','.join(columns)}) VALUES({placeholders})",
                values,
            )
            line = dict(candidate)
            line.update(
                id=int(cursor.lastrowid), paid_amount=0, status=status,
                revision=1, reversal_reason=candidate["reversal_reason"],
            )
            _append_revision(conn, line, "insert", timestamp)
            counters["inserted"] += 1
            counters["reversed"] += int(status == "reversed")
            continue

        financial_changed = any(
            previous[field] != candidate[field]
            for field in ("supplier_code", "actual_qty", "buy_price", "amount")
        )
        if previous["paid_amount"] > 0 and (financial_changed or (
            candidate['source_table'] == 'supplier_plan_sources' and
            candidate['reversal_reason'] == 'source_not_confirmed'
        )):
            raise PayableLedgerError(
                "Dòng phải trả đã có phân bổ thanh toán nên nguồn mua không được đổi âm thầm",
                code="paid_payable_source_changed",
            )
        target_status = payable_line_status(
            candidate["amount"], previous["paid_amount"], reversed_line=forced_reversed
        )
        source_changed = candidate["snapshot_hash"] != previous["snapshot_hash"]
        state_changed = (
            target_status != previous["status"]
            or candidate["reversal_reason"] != previous["reversal_reason"]
        )
        if not source_changed and not state_changed:
            counters["unchanged"] += 1
            continue
        revision = int(previous["revision"]) + 1
        assignments = ",".join(f"{field}=?" for field in LINE_FIELDS)
        conn.execute(
            f"""UPDATE payable_ledger_lines SET {assignments},status=?,reversal_reason=?,
                       snapshot_hash=?,revision=?,updated_at=? WHERE id=?""",
            (
                *(candidate[field] for field in LINE_FIELDS), target_status,
                candidate["reversal_reason"], candidate["snapshot_hash"], revision,
                timestamp, previous["id"],
            ),
        )
        line = dict(candidate)
        line.update(
            id=previous["id"], paid_amount=previous["paid_amount"],
            status=target_status, revision=revision,
        )
        if target_status == "reversed" and previous["status"] != "reversed":
            change_kind = "reverse"
            counters["reversed"] += 1
        elif previous["status"] == "reversed" and target_status != "reversed":
            change_kind = "reactivate"
            counters["reactivated"] += 1
        else:
            change_kind = "update"
            counters["updated"] += 1
        _append_revision(conn, line, change_kind, timestamp)

    for key, previous in existing.items():
        if key in seen or previous["status"] == "reversed":
            continue
        if previous["paid_amount"] > 0 and (
            previous['source_table'] == 'orders' or any(
                item['batch_id'] == previous['batch_id'] and item['source_table'] != previous['source_table']
                for item in candidates if item['batch_id'] is not None
            )
        ):
            raise PayableLedgerError(
                "Nguồn phải trả đã có thanh toán; cần đối chiếu phân bổ trước khi thay nguồn",
                code="paid_payable_source_changed",
            )
        revision = int(previous["revision"]) + 1
        conn.execute(
            """UPDATE payable_ledger_lines
               SET status='reversed',reversal_reason='source_removed',revision=?,updated_at=?
               WHERE id=?""",
            (revision, timestamp, previous["id"]),
        )
        line = dict(previous)
        line.update(
            status="reversed", reversal_reason="source_removed",
            revision=revision,
        )
        _append_revision(conn, line, "reverse", timestamp)
        counters["reversed"] += 1

    counters["active"] = int(conn.execute(
        "SELECT COUNT(*) n FROM payable_ledger_lines WHERE status!='reversed'"
    ).fetchone()["n"])
    counters["total"] = int(conn.execute(
        "SELECT COUNT(*) n FROM payable_ledger_lines"
    ).fetchone()["n"])
    return dict(counters)


def set_payable_allocation_total(
    conn, *, ledger_line_id: int, paid_amount: Any, timestamp: str,
    allow_reversed: bool = False,
) -> dict[str, Any]:
    """Apply an already-validated allocation total; no allocation policy lives here."""
    row = conn.execute(
        "SELECT * FROM payable_ledger_lines WHERE id=?", (int(ledger_line_id),)
    ).fetchone()
    if row is None:
        raise PayableLedgerError("Không tìm thấy dòng phải trả", code="payable_not_found", status=404)
    line = dict(row)
    reversed_line = line["status"] == "reversed"
    if reversed_line and not allow_reversed:
        raise PayableLedgerError("Dòng phải trả đã hoàn tác nên không thể phân bổ", code="payable_reversed")
    paid = _number(paid_amount, "Số đã phân bổ")
    status = payable_line_status(line["amount"], paid, reversed_line=reversed_line)
    if paid == line["paid_amount"] and status == line["status"]:
        return {**line, "idempotent": True}
    revision = int(line["revision"]) + 1
    conn.execute(
        """UPDATE payable_ledger_lines
           SET paid_amount=?,status=?,revision=?,updated_at=? WHERE id=?""",
        (paid, status, revision, timestamp, line["id"]),
    )
    line.update(paid_amount=paid, status=status, revision=revision)
    _append_revision(conn, line, "payment_state", timestamp)
    return {**line, "idempotent": False}


def _strict_date(value: Any, label: str) -> str:
    text = _clean(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise PayableLedgerError(
            f"{label} phải là ngày YYYY-MM-DD hợp lệ", code="invalid_period", status=400
        ) from None


def payable_ledger_payload(
    conn, *, date_from: Any, date_to: Any, supplier: Any = "",
    statuses: Any = None, limit: Any = 5000, offset: Any = 0,
) -> dict[str, Any]:
    safe_from = _strict_date(date_from, "Từ ngày")
    safe_to = _strict_date(date_to, "Đến ngày")
    if safe_from > safe_to:
        raise PayableLedgerError(
            "Từ ngày không được lớn hơn Đến ngày", code="invalid_period", status=400
        )
    requested_supplier = _clean(supplier)
    if statuses in (None, ""):
        selected_statuses = {"open", "partially_paid"}
    elif isinstance(statuses, str) and statuses.strip().casefold() == "all":
        selected_statuses = set(PAYABLE_STATUSES)
    else:
        values = statuses if isinstance(statuses, (list, tuple, set)) else str(statuses).split(",")
        selected_statuses = {_clean(value).casefold() for value in values if _clean(value)}
        if not selected_statuses or not selected_statuses.issubset(PAYABLE_STATUSES):
            raise PayableLedgerError("Trạng thái phải trả không hợp lệ", code="invalid_status", status=400)
    try:
        safe_limit = int(limit)
        safe_offset = int(offset)
    except (TypeError, ValueError):
        raise PayableLedgerError("Phân trang không hợp lệ", code="invalid_pagination", status=400) from None
    if safe_limit < 1 or safe_limit > 20_000 or safe_offset < 0:
        raise PayableLedgerError("Phân trang vượt giới hạn", code="invalid_pagination", status=400)

    supplier_codes, supplier_code_aliases, supplier_names, current_names = _supplier_catalog(conn)
    supplier_key = _mapping_key(requested_supplier)
    if requested_supplier in supplier_codes:
        supplier_filter = supplier_codes[requested_supplier]
    elif len(supplier_code_aliases.get(supplier_key, [])) == 1:
        supplier_filter = supplier_code_aliases[supplier_key][0]
    elif len(supplier_names.get(supplier_key, [])) == 1:
        supplier_filter = supplier_names[supplier_key][0]
    else:
        supplier_filter = requested_supplier
    base_rows = [
        dict(row) for row in conn.execute(
            """SELECT * FROM payable_ledger_lines
               WHERE work_date>=? AND work_date<=? ORDER BY work_date,id""",
            (safe_from, safe_to),
        )
        # supplier_filter has already been resolved through the catalog.  Do
        # not compare accent-insensitively here: distinct valid codes such as
        # DUNG and dũng must remain separate payable accounts.
        if not supplier_filter or _clean(row["supplier_code"]).casefold() == supplier_filter.casefold()
    ]
    status_counts = Counter(row["status"] for row in base_rows)
    selected = [row for row in base_rows if row["status"] in selected_statuses]
    page = selected[safe_offset:safe_offset + safe_limit]
    rows = []
    for row in page:
        reversed_line = row["status"] == "reversed"
        remaining = 0 if reversed_line else _vnd(row["amount"] - row["paid_amount"])
        rows.append({
            "id": int(row["id"]),
            "work_date": row["work_date"],
            "batch_id": row["batch_id"],
            "kitchen": row["kitchen"],
            "product_code": row["product_code"],
            "product_name": row["product_name"],
            "actual_qty": row["actual_qty"],
            "unit": row["unit"],
            "buy_price": row["buy_price"],
            "amount": row["amount"],
            "paid_amount": row["paid_amount"],
            "remaining_amount": remaining,
            "status": row["status"],
            "reversal_reason": row["reversal_reason"],
            "supplier": {
                "code": row["supplier_code"],
                "name": current_names.get(row["supplier_code"]) or row["supplier_snapshot"],
                "source_value": row["supplier_snapshot"],
            },
            "source": {
                "key": row["source_key"],
                "type": row["source_type"],
                "table": row["source_table"],
                "id": row["source_id"],
                "ref": row["source_ref"],
                "revision": row["source_revision"],
                "hash": row["source_hash"],
                "sheet": row["source_sheet"],
                "row": row["source_row"],
            },
            "ledger_revision": row["revision"],
        })
    active_rows = [row for row in base_rows if row["status"] != "reversed"]
    return {
        "date_from": safe_from,
        "date_to": safe_to,
        "supplier": supplier_filter or None,
        "statuses": [status for status in PAYABLE_STATUSES if status in selected_statuses],
        "rows": rows,
        "pagination": {
            "total": len(selected), "limit": safe_limit, "offset": safe_offset,
            "returned": len(rows),
        },
        "summary": {
            "source_rows": len(base_rows),
            "active_rows": len(active_rows),
            "quantities_by_unit": quantity_totals(active_rows, "actual_qty"),
            "filtered_quantities_by_unit": quantity_totals(selected, "actual_qty"),
            "status_counts": {status: int(status_counts.get(status, 0)) for status in PAYABLE_STATUSES},
            "quantity": sum(
                _number(row["actual_qty"], "Số lượng thực tế") for row in active_rows
            ),
            "charge_amount": sum(_vnd(row["amount"]) for row in active_rows),
            "paid_amount": sum(_vnd(row["paid_amount"]) for row in active_rows),
            "remaining_amount": sum(
                _vnd(row["amount"] - row["paid_amount"]) for row in active_rows
            ),
            "filtered_quantity": sum(
                _number(row["actual_qty"], "Số lượng thực tế") for row in selected
            ),
            "filtered_amount": sum(_vnd(row["amount"]) for row in selected),
            "filtered_paid_amount": sum(_vnd(row["paid_amount"]) for row in selected),
            "filtered_remaining_amount": sum(
                0 if row["status"] == "reversed"
                else _vnd(row["amount"] - row["paid_amount"])
                for row in selected
            ),
        },
        "historical_through_date": _historical_cutoff(conn) or None,
        "pending_purchase_sheets": pending_purchase_sheets(conn, safe_from, safe_to),
    }


def payable_revision_payload(conn, ledger_line_id: int) -> dict[str, Any]:
    line = conn.execute(
        "SELECT * FROM payable_ledger_lines WHERE id=?", (int(ledger_line_id),)
    ).fetchone()
    if line is None:
        raise PayableLedgerError("Không tìm thấy dòng phải trả", code="payable_not_found", status=404)
    revisions = [dict(row) for row in conn.execute(
        """SELECT revision,change_kind,source_revision,source_hash,work_date,kitchen,
                  product_code,product_name,actual_qty,unit,supplier_code,supplier_snapshot,
                  buy_price,amount,paid_amount,status,reversal_reason,created_at
           FROM payable_ledger_revisions WHERE ledger_line_id=? ORDER BY revision""",
        (int(ledger_line_id),),
    )]
    return {
        "line_id": int(line["id"]),
        "source_key": line["source_key"],
        "source_ref": line["source_ref"],
        "revisions": revisions,
    }


def register_payable_ledger_routes(app, ctx: dict[str, Any]) -> None:
    db_factory: Callable = ctx["db"]

    @app.get("/api/debts/payables/ledger")
    def api_payable_ledger():
        today = date.today()
        try:
            with db_factory() as conn:
                return jsonify({
                    "ok": True,
                    **payable_ledger_payload(
                        conn,
                        date_from=request.args.get("from") or today.replace(day=1).isoformat(),
                        date_to=request.args.get("to") or today.isoformat(),
                        supplier=request.args.get("supplier") or "",
                        statuses=request.args.get("status"),
                        limit=request.args.get("limit", 5000),
                        offset=request.args.get("offset", 0),
                    ),
                })
        except PayableLedgerError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.get("/api/debts/payables/ledger/<int:ledger_line_id>/revisions")
    def api_payable_ledger_revisions(ledger_line_id: int):
        try:
            with db_factory() as conn:
                return jsonify({"ok": True, **payable_revision_payload(conn, ledger_line_id)})
        except PayableLedgerError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status
