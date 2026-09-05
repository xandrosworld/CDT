"""Explicit supplier-payment allocation and reversal contract.

Every supplier payment must name the payable ledger lines and the amount
assigned to each line.  This module deliberately contains no FIFO, oldest-line
selection, proportional allocation, credit balance, or overpayment policy.
Transactions and allocations are reversed in place and retained for audit;
they are never deleted.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from flask import jsonify, request

try:
    from payable_ledger import set_payable_allocation_total
except ImportError:  # pragma: no cover - package invocation
    from .payable_ledger import set_payable_allocation_total


PAYMENT_STATUSES = ("posted", "reversed")
REQUEST_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class PayablePaymentError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_payable_payment", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


SCHEMA = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_request_key
    ON payments(request_key) WHERE request_key!='';
CREATE INDEX IF NOT EXISTS idx_payments_supplier_date_status
    ON payments(party_type,party_code,payment_date,status,id);

CREATE TABLE IF NOT EXISTS payable_payment_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL REFERENCES payments(id),
    ledger_line_id INTEGER NOT NULL REFERENCES payable_ledger_lines(id),
    amount REAL NOT NULL,
    ledger_revision_before INTEGER NOT NULL,
    ledger_revision_after INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'posted',
    created_at TEXT NOT NULL,
    reversed_at TEXT,
    reversal_reason TEXT NOT NULL DEFAULT '',
    UNIQUE(payment_id,ledger_line_id),
    CHECK(amount > 0),
    CHECK(ledger_revision_before >= 1),
    CHECK(ledger_revision_after > ledger_revision_before),
    CHECK(status IN ('posted','reversed'))
);
CREATE INDEX IF NOT EXISTS idx_payable_allocations_line_status
    ON payable_payment_allocations(ledger_line_id,status,payment_id);

CREATE TABLE IF NOT EXISTS payable_payment_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL REFERENCES payments(id),
    revision INTEGER NOT NULL,
    change_kind TEXT NOT NULL,
    payment_date TEXT NOT NULL,
    supplier_code TEXT NOT NULL,
    amount REAL NOT NULL,
    method TEXT NOT NULL DEFAULT '',
    reference_code TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    allocations_json TEXT NOT NULL DEFAULT '[]',
    reversal_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(payment_id,revision),
    CHECK(revision >= 1),
    CHECK(change_kind IN ('create','reverse')),
    CHECK(status IN ('posted','reversed'))
);
CREATE INDEX IF NOT EXISTS idx_payable_payment_revisions_payment
    ON payable_payment_revisions(payment_id,revision);
"""


PAYMENT_COLUMNS = {
    "created_by": "TEXT NOT NULL DEFAULT ''",
    "reversed_by": "TEXT NOT NULL DEFAULT ''",
    "method": "TEXT NOT NULL DEFAULT ''",
    "reference_code": "TEXT NOT NULL DEFAULT ''",
    "status": "TEXT NOT NULL DEFAULT 'posted'",
    "request_key": "TEXT NOT NULL DEFAULT ''",
    "request_hash": "TEXT NOT NULL DEFAULT ''",
    "revision": "INTEGER NOT NULL DEFAULT 1",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
    "reversed_at": "TEXT",
    "reversal_reason": "TEXT NOT NULL DEFAULT ''",
}


def init_payable_payment_schema(conn) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(payments)")}
    for name, definition in PAYMENT_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE payments ADD COLUMN {name} {definition}")
    conn.executescript(SCHEMA)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _strict_date(value: Any, label: str) -> str:
    text = _clean(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise PayablePaymentError(
            f"{label} phải là ngày YYYY-MM-DD hợp lệ",
            code="invalid_payment_date",
            status=400,
        ) from None


def _decimal(value: Any, label: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise PayablePaymentError(f"{label} phải là số hợp lệ", status=400) from None
    if not number.is_finite():
        raise PayablePaymentError(f"{label} phải là số hữu hạn", status=400)
    return number


def _vnd(value: Any, label: str) -> int:
    number = _decimal(value, label)
    integral = number.to_integral_value()
    if number != integral:
        raise PayablePaymentError(f"{label} phải là số VND nguyên", status=400)
    return int(integral)


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise PayablePaymentError(f"{label} không hợp lệ", status=400)
    number = _decimal(value, label)
    integral = number.to_integral_value()
    if number != integral or integral < 1:
        raise PayablePaymentError(f"{label} không hợp lệ", status=400)
    return int(integral)


def _bounded(value: Any, label: str, maximum: int, *, required: bool = False) -> str:
    text = _clean(value)
    if required and not text:
        raise PayablePaymentError(f"Thiếu {label}", status=400)
    if len(text) > maximum:
        raise PayablePaymentError(f"{label} vượt {maximum} ký tự", status=400)
    return text


def _normalize_create_request(
    conn, payload: dict[str, Any], canonical_party_code: Callable,
) -> dict[str, Any]:
    request_key = _clean(payload.get("request_id") or payload.get("request_key"))
    if not REQUEST_KEY_PATTERN.fullmatch(request_key):
        raise PayablePaymentError(
            "Mã chống gửi trùng phải dài 8-128 ký tự và chỉ gồm chữ, số, . _ : -",
            code="invalid_payment_request_id",
            status=400,
        )
    supplier_input = _clean(payload.get("supplier_code") or payload.get("party_code"))
    if not supplier_input:
        raise PayablePaymentError("Thiếu mã nhà cung cấp", status=400)
    try:
        supplier_code = canonical_party_code(conn, "supplier", supplier_input)
    except ValueError as error:
        raise PayablePaymentError(str(error), code="invalid_supplier", status=400) from None
    payment_date = _strict_date(payload.get("payment_date"), "Ngày thanh toán")
    amount = _vnd(payload.get("amount"), "Số tiền thanh toán")
    if amount <= 0:
        raise PayablePaymentError("Số tiền thanh toán phải lớn hơn 0", status=400)
    method = _bounded(payload.get("method"), "Phương thức", 100)
    reference_code = _bounded(
        payload.get("reference_code") or payload.get("reference"), "Mã tham chiếu", 200,
    )
    note = _bounded(payload.get("note"), "Nội dung", 1000)
    _bounded(payload.get("actor"), "Người ghi nhận", 120)
    raw_allocations = payload.get("allocations")
    if not isinstance(raw_allocations, list) or not raw_allocations:
        raise PayablePaymentError(
            "Phải chọn rõ ít nhất một dòng nợ và số tiền phân bổ cho dòng đó",
            code="payable_allocations_required",
            status=400,
        )
    if len(raw_allocations) > 500:
        raise PayablePaymentError("Một giao dịch chỉ được phân bổ tối đa 500 dòng", status=400)
    allocations = []
    seen: set[int] = set()
    for index, raw in enumerate(raw_allocations, 1):
        if not isinstance(raw, dict):
            raise PayablePaymentError(f"Phân bổ dòng {index} không hợp lệ", status=400)
        line_id = _positive_int(
            raw.get("ledger_line_id") or raw.get("line_id"), f"Mã dòng nợ {index}",
        )
        if line_id in seen:
            raise PayablePaymentError(
                f"Dòng nợ {line_id} được chọn hai lần",
                code="duplicate_payable_allocation",
                status=400,
            )
        seen.add(line_id)
        allocated = _vnd(raw.get("amount"), f"Số tiền phân bổ dòng {index}")
        if allocated <= 0:
            raise PayablePaymentError(
                f"Số tiền phân bổ dòng {index} phải lớn hơn 0", status=400,
            )
        expected_revision = _positive_int(
            raw.get("expected_revision"), f"Revision dòng nợ {index}",
        )
        allocations.append({
            "ledger_line_id": line_id,
            "amount": allocated,
            "expected_revision": expected_revision,
        })
    allocations.sort(key=lambda item: item["ledger_line_id"])
    if sum(item["amount"] for item in allocations) != amount:
        raise PayablePaymentError(
            "Tổng tiền phân bổ phải bằng đúng số tiền thanh toán",
            code="payment_allocation_total_mismatch",
            status=400,
        )
    normalized = {
        "request_key": request_key,
        "supplier_code": supplier_code,
        "payment_date": payment_date,
        "amount": amount,
        "method": method,
        "reference_code": reference_code,
        "note": note,
        "allocations": allocations,
    }
    normalized["request_hash"] = hashlib.sha256(
        json.dumps(
            normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest().upper()
    return normalized


def _allocation_rows(conn, payment_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        """SELECT a.*,l.source_key,l.source_ref,l.work_date,l.kitchen,
                  l.product_code,l.product_name,l.unit,l.supplier_code,
                  l.amount line_amount,l.paid_amount line_paid_amount,l.status line_status,
                  l.revision line_revision
           FROM payable_payment_allocations a
           JOIN payable_ledger_lines l ON l.id=a.ledger_line_id
           WHERE a.payment_id=? ORDER BY a.id""",
        (int(payment_id),),
    )]


def payable_payment_payload(conn, payment_id: int) -> dict[str, Any]:
    payment = conn.execute("SELECT * FROM payments WHERE id=?", (int(payment_id),)).fetchone()
    if payment is None:
        raise PayablePaymentError(
            "Không tìm thấy giao dịch thanh toán", code="payment_not_found", status=404,
        )
    item = dict(payment)
    allocations = _allocation_rows(conn, payment_id)
    supplier = conn.execute(
        "SELECT name FROM suppliers WHERE code=?", (item["party_code"],)
    ).fetchone()
    return {
        "id": int(item["id"]),
        "payment_date": item["payment_date"],
        "supplier": {
            "code": item["party_code"],
            "name": _clean(supplier["name"] if supplier else item["party_code"]),
        },
        "amount": _vnd(item["amount"], "Số tiền thanh toán"),
        "method": item["method"],
        "reference_code": item["reference_code"],
        "note": item["note"] or "",
        "status": item["status"],
        "revision": int(item["revision"]),
        "request_id": item["request_key"] or None,
        "created_at": item["created_at"],
        "created_by": item["created_by"],
        "reversed_by": item["reversed_by"],
        "updated_at": item["updated_at"] or item["created_at"],
        "reversed_at": item["reversed_at"],
        "reversal_reason": item["reversal_reason"] or "",
        "allocations": [{
            "id": int(row["id"]),
            "ledger_line_id": int(row["ledger_line_id"]),
            "amount": _vnd(row["amount"], "Số tiền phân bổ"),
            "status": row["status"],
            "ledger_revision_before": int(row["ledger_revision_before"]),
            "ledger_revision_after": int(row["ledger_revision_after"]),
            "reversed_at": row["reversed_at"],
            "reversal_reason": row["reversal_reason"] or "",
            "line": {
                "source_key": row["source_key"],
                "source_ref": row["source_ref"],
                "work_date": row["work_date"],
                "kitchen": row["kitchen"],
                "product_code": row["product_code"],
                "product_name": row["product_name"],
                "unit": row["unit"],
                "supplier_code": row["supplier_code"],
                "amount": _vnd(row["line_amount"], "Thành tiền dòng nợ"),
                "paid_amount": _vnd(row["line_paid_amount"], "Đã phân bổ dòng nợ"),
                "status": row["line_status"],
                "revision": int(row["line_revision"]),
            },
        } for row in allocations],
    }


def _revision_allocations(allocations: list[dict[str, Any]]) -> str:
    snapshot = [{
        "allocation_id": int(row["id"]),
        "ledger_line_id": int(row["ledger_line_id"]),
        "amount": _vnd(row["amount"], "Số tiền phân bổ"),
        "status": row["status"],
    } for row in allocations]
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _append_revision(
    conn, payment: dict[str, Any], change_kind: str,
    allocations: list[dict[str, Any]], timestamp: str,
) -> None:
    conn.execute(
        """INSERT INTO payable_payment_revisions(
               payment_id,revision,change_kind,payment_date,supplier_code,amount,
               method,reference_code,note,status,allocations_json,reversal_reason,created_at
           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            payment["id"], payment["revision"], change_kind, payment["payment_date"],
            payment["party_code"], payment["amount"], payment["method"],
            payment["reference_code"], payment["note"] or "", payment["status"],
            _revision_allocations(allocations), payment["reversal_reason"] or "", timestamp,
        ),
    )


def create_payable_payment(
    conn, payload: dict[str, Any], *, timestamp: str,
    canonical_party_code: Callable, audit_event: Callable,
) -> dict[str, Any]:
    normalized = _normalize_create_request(conn, payload, canonical_party_code)
    prior = conn.execute(
        "SELECT id,request_hash FROM payments WHERE request_key=?",
        (normalized["request_key"],),
    ).fetchone()
    if prior is not None:
        if prior["request_hash"] != normalized["request_hash"]:
            raise PayablePaymentError(
                "Mã chống gửi trùng đã được dùng cho nội dung thanh toán khác",
                code="payment_request_conflict",
            )
        return {**payable_payment_payload(conn, int(prior["id"])), "idempotent": True}

    line_ids = [item["ledger_line_id"] for item in normalized["allocations"]]
    placeholders = ",".join("?" for _ in line_ids)
    lines = {
        int(row["id"]): dict(row)
        for row in conn.execute(
            f"SELECT * FROM payable_ledger_lines WHERE id IN ({placeholders}) ORDER BY id",
            line_ids,
        )
    }
    if len(lines) != len(line_ids):
        missing = [line_id for line_id in line_ids if line_id not in lines]
        raise PayablePaymentError(
            f"Không tìm thấy dòng phải trả {missing[0]}", code="payable_not_found", status=404,
        )
    for allocation in normalized["allocations"]:
        line = lines[allocation["ledger_line_id"]]
        if line["supplier_code"] != normalized["supplier_code"]:
            raise PayablePaymentError(
                f"Dòng {line['id']} không thuộc NCC {normalized['supplier_code']}",
                code="payment_supplier_mismatch",
            )
        if int(line["revision"]) != allocation["expected_revision"]:
            raise PayablePaymentError(
                f"Dòng {line['id']} đã thay đổi; hãy tải lại danh sách còn phải trả",
                code="stale_payable_revision",
            )
        if line["status"] not in {"open", "partially_paid"}:
            raise PayablePaymentError(
                f"Dòng {line['id']} không còn ở trạng thái có thể thanh toán",
                code="payable_not_open",
            )
        remaining = _vnd(
            _decimal(line["amount"], "Thành tiền dòng nợ")
            - _decimal(line["paid_amount"], "Đã phân bổ dòng nợ"),
            "Còn phải trả",
        )
        if allocation["amount"] > remaining:
            raise PayablePaymentError(
                f"Phân bổ cho dòng {line['id']} vượt số còn phải trả {remaining}",
                code="payable_overpayment",
            )

    cursor = conn.execute(
        """INSERT INTO payments(
               payment_date,kind,party_type,party_code,amount,note,created_at,
               method,reference_code,status,request_key,request_hash,revision,updated_at,
               reversed_at,reversal_reason
           ) VALUES(?,'payment','supplier',?,?,?,?,?,?,'posted',?,?,1,?,NULL,'')""",
        (
            normalized["payment_date"], normalized["supplier_code"], normalized["amount"],
            normalized["note"], timestamp, normalized["method"],
            normalized["reference_code"], normalized["request_key"],
            normalized["request_hash"], timestamp,
        ),
    )
    payment_id = int(cursor.lastrowid)
    conn.execute("UPDATE payments SET created_by=? WHERE id=?", (_clean(payload.get("actor")), payment_id))
    allocation_snapshots = []
    for allocation in normalized["allocations"]:
        line = lines[allocation["ledger_line_id"]]
        before = int(line["revision"])
        updated = set_payable_allocation_total(
            conn,
            ledger_line_id=int(line["id"]),
            paid_amount=_vnd(line["paid_amount"], "Đã phân bổ") + allocation["amount"],
            timestamp=timestamp,
        )
        after = int(updated["revision"])
        allocation_cursor = conn.execute(
            """INSERT INTO payable_payment_allocations(
                   payment_id,ledger_line_id,amount,ledger_revision_before,
                   ledger_revision_after,status,created_at,reversed_at,reversal_reason
               ) VALUES(?,?,?,?,?,'posted',?,NULL,'')""",
            (payment_id, line["id"], allocation["amount"], before, after, timestamp),
        )
        allocation_snapshots.append({
            "id": int(allocation_cursor.lastrowid),
            "ledger_line_id": int(line["id"]),
            "amount": allocation["amount"],
            "status": "posted",
        })
    payment = dict(conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone())
    _append_revision(conn, payment, "create", allocation_snapshots, timestamp)
    audit_event(
        conn, "payable_payment.create", entity_type="supplier",
        entity_id=normalized["supplier_code"], metadata={
            "payment_id": payment_id,
            "payment_date": normalized["payment_date"],
            "amount": normalized["amount"],
            "allocation_count": len(allocation_snapshots),
            "request_id": normalized["request_key"],
            "actor": _clean(payload.get("actor")),
        },
    )
    return {**payable_payment_payload(conn, payment_id), "idempotent": False}


def reverse_payable_payment(
    conn, payment_id: int, payload: dict[str, Any], *, timestamp: str,
    audit_event: Callable,
) -> dict[str, Any]:
    reason = _bounded(payload.get("reason"), "lý do hoàn tác", 500, required=True)
    actor = _bounded(payload.get("actor"), "người hoàn tác", 120, required=True)
    expected_revision = _positive_int(
        payload.get("expected_revision"), "Revision giao dịch",
    )
    row = conn.execute("SELECT * FROM payments WHERE id=?", (int(payment_id),)).fetchone()
    if row is None:
        raise PayablePaymentError(
            "Không tìm thấy giao dịch thanh toán", code="payment_not_found", status=404,
        )
    payment = dict(row)
    if payment["kind"] != "payment" or payment["party_type"] != "supplier":
        raise PayablePaymentError(
            "Giao dịch này không phải khoản trả nhà cung cấp",
            code="not_supplier_payment",
        )
    current_revision = int(payment["revision"])
    if payment["status"] == "reversed":
        if payment["reversal_reason"] == reason and payment["reversed_by"] == actor and expected_revision in {
            current_revision, current_revision - 1,
        }:
            return {**payable_payment_payload(conn, payment_id), "idempotent": True}
        raise PayablePaymentError(
            "Giao dịch đã được hoàn tác", code="payment_already_reversed",
        )
    if expected_revision != current_revision:
        raise PayablePaymentError(
            "Giao dịch đã thay đổi; hãy tải lại lịch sử thanh toán",
            code="stale_payment_revision",
        )
    allocations = [dict(item) for item in conn.execute(
        "SELECT * FROM payable_payment_allocations WHERE payment_id=? AND status='posted' ORDER BY id",
        (int(payment_id),),
    )]
    conn.execute(
        """UPDATE payable_payment_allocations
           SET status='reversed',reversed_at=?,reversal_reason=?
           WHERE payment_id=? AND status='posted'""",
        (timestamp, reason, int(payment_id)),
    )
    affected_lines = sorted({int(item["ledger_line_id"]) for item in allocations})
    for line_id in affected_lines:
        total = conn.execute(
            """SELECT COALESCE(SUM(amount),0) total
               FROM payable_payment_allocations
               WHERE ledger_line_id=? AND status='posted'""",
            (line_id,),
        ).fetchone()["total"]
        set_payable_allocation_total(
            conn, ledger_line_id=line_id, paid_amount=_vnd(total, "Tổng phân bổ"),
            timestamp=timestamp, allow_reversed=True,
        )
    revision = current_revision + 1
    conn.execute(
        """UPDATE payments SET status='reversed',revision=?,updated_at=?,reversed_at=?,
                   reversal_reason=?,reversed_by=? WHERE id=?""",
        (revision, timestamp, timestamp, reason, actor, int(payment_id)),
    )
    payment.update(
        status="reversed", revision=revision, updated_at=timestamp,
        reversed_at=timestamp, reversal_reason=reason,
    )
    reversed_allocations = [
        {**item, "status": "reversed"} for item in allocations
    ]
    _append_revision(conn, payment, "reverse", reversed_allocations, timestamp)
    audit_event(
        conn, "payable_payment.reverse", entity_type="supplier",
        entity_id=payment["party_code"], metadata={
            "payment_id": int(payment_id), "amount": _vnd(payment["amount"], "Số tiền"),
            "allocation_count": len(allocations), "reason": reason,
            "actor": actor,
        },
    )
    return {**payable_payment_payload(conn, payment_id), "idempotent": False}


def payable_payment_history_payload(
    conn, *, date_from: Any, date_to: Any, supplier: Any, status: Any,
    limit: Any, offset: Any, canonical_party_code: Callable,
) -> dict[str, Any]:
    safe_from = _strict_date(date_from, "Từ ngày")
    safe_to = _strict_date(date_to, "Đến ngày")
    if safe_from > safe_to:
        raise PayablePaymentError(
            "Từ ngày không được lớn hơn Đến ngày", code="invalid_period", status=400,
        )
    requested_supplier = _clean(supplier)
    supplier_code = ""
    if requested_supplier:
        try:
            supplier_code = canonical_party_code(conn, "supplier", requested_supplier)
        except ValueError as error:
            raise PayablePaymentError(str(error), code="invalid_supplier", status=400) from None
    selected_status = _clean(status).casefold() or "all"
    if selected_status not in {"all", *PAYMENT_STATUSES}:
        raise PayablePaymentError("Trạng thái thanh toán không hợp lệ", status=400)
    try:
        safe_limit = int(limit)
        safe_offset = int(offset)
    except (TypeError, ValueError):
        raise PayablePaymentError("Phân trang không hợp lệ", status=400) from None
    if safe_limit < 1 or safe_limit > 5000 or safe_offset < 0:
        raise PayablePaymentError("Phân trang vượt giới hạn", status=400)
    clauses = [
        "kind='payment'", "party_type='supplier'", "payment_date>=?", "payment_date<=?",
    ]
    params: list[Any] = [safe_from, safe_to]
    if supplier_code:
        clauses.append("party_code=?")
        params.append(supplier_code)
    where = " AND ".join(clauses)
    base = [dict(row) for row in conn.execute(
        f"SELECT * FROM payments WHERE {where} ORDER BY payment_date,id", params,
    )]
    status_counts = Counter(item["status"] for item in base)
    selected = base if selected_status == "all" else [
        item for item in base if item["status"] == selected_status
    ]
    page = selected[safe_offset:safe_offset + safe_limit]
    return {
        "date_from": safe_from,
        "date_to": safe_to,
        "supplier": supplier_code or None,
        "status": selected_status,
        "payments": [payable_payment_payload(conn, int(item["id"])) for item in page],
        "pagination": {
            "total": len(selected), "limit": safe_limit, "offset": safe_offset,
            "returned": len(page),
        },
        "summary": {
            "transaction_count": len(base),
            "posted_count": int(status_counts.get("posted", 0)),
            "reversed_count": int(status_counts.get("reversed", 0)),
            "posted_amount": sum(
                _vnd(item["amount"], "Số tiền") for item in base if item["status"] == "posted"
            ),
            "reversed_amount": sum(
                _vnd(item["amount"], "Số tiền") for item in base if item["status"] == "reversed"
            ),
        },
    }


def payable_payment_revision_payload(conn, payment_id: int) -> dict[str, Any]:
    payment = conn.execute(
        "SELECT id,kind,party_type,party_code FROM payments WHERE id=?", (int(payment_id),)
    ).fetchone()
    if payment is None:
        raise PayablePaymentError(
            "Không tìm thấy giao dịch thanh toán", code="payment_not_found", status=404,
        )
    if payment["kind"] != "payment" or payment["party_type"] != "supplier":
        raise PayablePaymentError(
            "Giao dịch này không phải khoản trả nhà cung cấp",
            code="not_supplier_payment",
        )
    revisions = []
    for row in conn.execute(
        """SELECT revision,change_kind,payment_date,supplier_code,amount,method,
                  reference_code,note,status,allocations_json,reversal_reason,created_at
           FROM payable_payment_revisions WHERE payment_id=? ORDER BY revision""",
        (int(payment_id),),
    ):
        item = dict(row)
        try:
            item["allocations"] = json.loads(item.pop("allocations_json") or "[]")
        except json.JSONDecodeError:
            raise PayablePaymentError(
                "Lịch sử phân bổ thanh toán bị hỏng",
                code="invalid_payment_revision_history",
                status=500,
            ) from None
        item["revision"] = int(item["revision"])
        item["amount"] = _vnd(item["amount"], "Số tiền thanh toán")
        revisions.append(item)
    return {
        "payment_id": int(payment["id"]),
        "supplier_code": payment["party_code"],
        "revisions": revisions,
    }


def register_payable_payment_routes(app, ctx: dict[str, Any]) -> None:
    db_factory: Callable = ctx["db"]
    now_iso: Callable = ctx["now_iso"]
    canonical_party_code: Callable = ctx["canonical_party_code"]
    audit_event: Callable = ctx["audit_event"]

    @app.post("/api/debts/payables/payments")
    def api_create_payable_payment():
        payload = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = create_payable_payment(
                    conn, payload, timestamp=now_iso(),
                    canonical_party_code=canonical_party_code, audit_event=audit_event,
                )
            return jsonify({"ok": True, **result}), 200 if result["idempotent"] else 201
        except PayablePaymentError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.get("/api/debts/payables/payments")
    def api_payable_payment_history():
        today = date.today()
        try:
            with db_factory() as conn:
                result = payable_payment_history_payload(
                    conn,
                    date_from=request.args.get("from") or today.replace(day=1).isoformat(),
                    date_to=request.args.get("to") or today.isoformat(),
                    supplier=request.args.get("supplier") or "",
                    status=request.args.get("status") or "all",
                    limit=request.args.get("limit", 500),
                    offset=request.args.get("offset", 0),
                    canonical_party_code=canonical_party_code,
                )
            return jsonify({"ok": True, **result})
        except PayablePaymentError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.post("/api/debts/payables/payments/<int:payment_id>/reverse")
    def api_reverse_payable_payment(payment_id: int):
        payload = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = reverse_payable_payment(
                    conn, payment_id, payload, timestamp=now_iso(), audit_event=audit_event,
                )
            return jsonify({"ok": True, **result})
        except PayablePaymentError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status

    @app.get("/api/debts/payables/payments/<int:payment_id>/revisions")
    def api_payable_payment_revisions(payment_id: int):
        try:
            with db_factory() as conn:
                result = payable_payment_revision_payload(conn, payment_id)
            return jsonify({"ok": True, **result})
        except PayablePaymentError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status
