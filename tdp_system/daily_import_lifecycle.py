"""Durable contract for the two-stage daily workbook lifecycle.

This module intentionally does not parse or write customer/purchase rows yet.
It owns stable identities, lifecycle state, per-scope confirmation grants and
count-only/hash-only audit. Workbook parsing is added by the dependent tasks.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from typing import Any, Iterable, Mapping


PHASES = {"first_load", "finalization"}
SCOPES = {"customer_orders", "purchase_orders"}
CAPABILITIES = {
    "customer_orders": "update_customer_orders",
    "purchase_orders": "update_purchase_orders",
}
IDENTITY_FIELDS = (
    "contractor", "kitchen", "product_code", "product_name", "unit", "occurrence",
)


DAILY_IMPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_workdays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    daily_key TEXT NOT NULL UNIQUE,
    work_date TEXT NOT NULL,
    day_sheet_key TEXT NOT NULL,
    batch_id INTEGER NOT NULL UNIQUE REFERENCES batches(id) ON DELETE CASCADE,
    lifecycle_status TEXT NOT NULL DEFAULT 'picking',
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finalized_at TEXT,
    CHECK(lifecycle_status IN ('picking','finalized')),
    CHECK(revision >= 1),
    UNIQUE(work_date,day_sheet_key)
);
CREATE INDEX IF NOT EXISTS idx_daily_workdays_date
    ON daily_workdays(work_date,lifecycle_status,id DESC);
CREATE TABLE IF NOT EXISTS daily_import_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_key TEXT NOT NULL UNIQUE,
    daily_workday_id INTEGER NOT NULL REFERENCES daily_workdays(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL,
    phase TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    exact_day_sheet TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    CHECK(phase IN ('first_load','finalization')),
    UNIQUE(daily_workday_id,version_no)
);
CREATE INDEX IF NOT EXISTS idx_daily_import_versions_workday
    ON daily_import_versions(daily_workday_id,version_no DESC);
CREATE TABLE IF NOT EXISTS daily_import_scopes (
    version_id INTEGER NOT NULL REFERENCES daily_import_versions(id) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    write_capability TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'previewed',
    state_hash TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    confirmed_at TEXT,
    PRIMARY KEY(version_id,scope),
    CHECK(scope IN ('customer_orders','purchase_orders')),
    CHECK(write_capability IN ('update_customer_orders','update_purchase_orders')),
    CHECK(state IN ('previewed','confirmed')),
    CHECK(row_count >= 0)
);
CREATE TABLE IF NOT EXISTS daily_import_rows (
    version_id INTEGER NOT NULL,
    scope TEXT NOT NULL,
    row_key TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'previewed',
    PRIMARY KEY(version_id,scope,row_key),
    FOREIGN KEY(version_id,scope) REFERENCES daily_import_scopes(version_id,scope)
        ON DELETE CASCADE,
    CHECK(source_row > 0),
    CHECK(state IN ('previewed','confirmed'))
);
CREATE INDEX IF NOT EXISTS idx_daily_import_rows_key
    ON daily_import_rows(row_key,scope,version_id);
"""


class DailyImportError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def init_daily_import_schema(conn) -> None:
    """Add only new extension tables; existing batches/orders stay untouched."""
    required = {row["name"] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('batches','orders')"
    )}
    if required != {"batches", "orders"}:
        raise DailyImportError(
            "Migration vòng đời import cần schema batches/orders hiện hữu",
            code="base_schema_missing",
        )
    required_columns = {
        "daily_workdays": {"daily_key", "work_date", "day_sheet_key", "batch_id", "lifecycle_status"},
        "daily_import_versions": {"version_key", "daily_workday_id", "version_no", "phase", "source_hash"},
        "daily_import_scopes": {"version_id", "scope", "write_capability", "state", "state_hash"},
        "daily_import_rows": {"version_id", "scope", "row_key", "payload_hash", "source_row"},
    }
    for table, columns in required_columns.items():
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if not columns.issubset(existing):
                raise DailyImportError(
                    f"Schema cũ của {table} không tương thích; migration đã dừng trước khi ghi",
                    code="incompatible_schema",
                )
    savepoint = "daily_import_schema_atomic"
    try:
        conn.executescript(f"SAVEPOINT {savepoint};\n{DAILY_IMPORT_SCHEMA}")
        for table, columns in required_columns.items():
            actual = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if not columns.issubset(actual):
                raise DailyImportError(
                    f"Migration thiếu cột bắt buộc ở {table}", code="migration_incomplete"
                )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception as error:
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            pass
        if isinstance(error, DailyImportError):
            raise
        raise DailyImportError(
            "Migration import ngày thất bại; các bảng mới đã được hoàn tác",
            code="migration_failed",
        ) from error


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"\s+", " ", text)


def _date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise DailyImportError(
            "Ngày vận hành phải là ngày YYYY-MM-DD hợp lệ", code="invalid_work_date", status=400
        ) from None


def _hash_text(*parts: Any) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest().upper()


def _sha256(value: Any, label: str) -> str:
    text = str(value or "").strip().upper()
    if not re.fullmatch(r"[0-9A-F]{64}", text):
        raise DailyImportError(f"{label} phải là SHA-256 hợp lệ", code="invalid_hash", status=400)
    return text


def canonical_day_sheet(value: Any) -> str:
    normalized = _normalized(value)
    if not normalized:
        raise DailyImportError("Thiếu sheet ngày", code="missing_day_sheet", status=400)
    return normalized


def daily_row_key(
    *,
    work_date: Any,
    scope: Any,
    identity: Mapping[str, Any],
) -> str:
    safe_date = _date(work_date)
    safe_scope = str(scope or "").strip()
    if safe_scope not in SCOPES:
        raise DailyImportError("Phạm vi import ngày không hợp lệ", code="invalid_scope", status=400)
    if not isinstance(identity, Mapping):
        raise DailyImportError("Khóa nghiệp vụ dòng không hợp lệ", code="invalid_row_identity", status=400)
    values = {field: _normalized(identity.get(field)) for field in IDENTITY_FIELDS}
    if not values["kitchen"] or not (values["product_code"] or values["product_name"]):
        raise DailyImportError(
            "Khóa dòng cần mã bếp và mã/tên hàng", code="incomplete_row_identity", status=400
        )
    occurrence = str(identity.get("occurrence", "1")).strip()
    if not occurrence.isdigit() or int(occurrence) < 1:
        raise DailyImportError(
            "Số thứ tự dòng trùng phải là số nguyên dương", code="invalid_occurrence", status=400
        )
    values["occurrence"] = str(int(occurrence))
    return _hash_text(safe_date, safe_scope, *(values[field] for field in IDENTITY_FIELDS))


def daily_payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash a normalized row payload without persisting its potentially private values."""
    if not isinstance(payload, Mapping):
        raise DailyImportError("Payload dòng không hợp lệ", code="invalid_payload", status=400)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _scope_rows(
    work_date: str,
    rows_by_scope: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(rows_by_scope, Mapping) or not rows_by_scope:
        raise DailyImportError("Cần ít nhất một phạm vi preview", code="missing_scope", status=400)
    output: dict[str, list[dict[str, Any]]] = {}
    for scope, raw_rows in rows_by_scope.items():
        if scope not in SCOPES:
            raise DailyImportError("Phạm vi import ngày không hợp lệ", code="invalid_scope", status=400)
        normalized_rows = []
        seen: set[str] = set()
        for fallback_row, row in enumerate(raw_rows, start=1):
            if not isinstance(row, Mapping):
                raise DailyImportError("Preview có dòng không hợp lệ", code="invalid_row", status=400)
            key = str(row.get("row_key") or "").strip().upper()
            if not key:
                key = daily_row_key(
                    work_date=work_date, scope=scope, identity=row.get("identity") or {}
                )
            key = _sha256(key, "Khóa dòng")
            payload_hash = str(row.get("payload_hash") or "").strip().upper()
            if not payload_hash:
                payload_hash = daily_payload_hash(row.get("payload") or {})
            payload_hash = _sha256(payload_hash, "Hash payload dòng")
            try:
                source_row = int(row.get("source_row") or fallback_row)
            except (TypeError, ValueError):
                raise DailyImportError("Số dòng nguồn không hợp lệ", code="invalid_source_row", status=400) from None
            if source_row <= 0 or key in seen:
                raise DailyImportError(
                    "Preview có khóa dòng trùng hoặc số dòng không hợp lệ",
                    code="duplicate_row_key",
                    status=400,
                )
            seen.add(key)
            normalized_rows.append({
                "row_key": key,
                "payload_hash": payload_hash,
                "source_row": source_row,
            })
        output[scope] = sorted(normalized_rows, key=lambda row: row["row_key"])
    return output


def _state_hash(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["row_key"].encode("ascii"))
        digest.update(b"\0")
        digest.update(row["payload_hash"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest().upper()


def _version_payload(conn, version_id: int, *, idempotent: bool) -> dict[str, Any]:
    version = conn.execute(
        """SELECT v.*,w.batch_id,w.lifecycle_status,w.revision,w.work_date,w.day_sheet_key
           FROM daily_import_versions v
           JOIN daily_workdays w ON w.id=v.daily_workday_id WHERE v.id=?""",
        (int(version_id),),
    ).fetchone()
    scopes = [dict(row) for row in conn.execute(
        """SELECT scope,write_capability,state,state_hash,row_count,confirmed_at
           FROM daily_import_scopes WHERE version_id=? ORDER BY scope""",
        (int(version_id),),
    )]
    return {
        "daily_workday_id": int(version["daily_workday_id"]),
        "batch_id": int(version["batch_id"]),
        "work_date": version["work_date"],
        "lifecycle_status": version["lifecycle_status"],
        "lifecycle_revision": int(version["revision"]),
        "version_id": int(version["id"]),
        "version_no": int(version["version_no"]),
        "version_key": version["version_key"],
        "source_hash": version["source_hash"],
        "phase": version["phase"],
        "day_sheet": version["exact_day_sheet"],
        "scopes": scopes,
        "idempotent": bool(idempotent),
    }


def _audit(conn, *, event_type: str, entity_id: int, timestamp: str, metadata: dict[str, Any]) -> None:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone():
        return
    conn.execute(
        """INSERT INTO audit_log(
               event_type,entity_type,entity_id,status,message,metadata_json,created_at
           ) VALUES(?,'daily_import_version',?,'ok','',?,?)""",
        (
            event_type,
            str(entity_id),
            json.dumps(metadata, sort_keys=True, separators=(",", ":")),
            timestamp,
        ),
    )


def prepare_daily_import_version(
    conn,
    *,
    source_hash: Any,
    work_date: Any,
    day_sheet: Any,
    phase: Any,
    rows_by_scope: Mapping[str, Iterable[Mapping[str, Any]]],
    now_iso,
) -> dict[str, Any]:
    safe_hash = _sha256(source_hash, "Hash workbook")
    safe_date = _date(work_date)
    exact_sheet = str(day_sheet or "")
    sheet_key = canonical_day_sheet(exact_sheet)
    safe_phase = str(phase or "").strip()
    if safe_phase not in PHASES:
        raise DailyImportError("Giai đoạn import ngày không hợp lệ", code="invalid_phase", status=400)
    scopes = _scope_rows(safe_date, rows_by_scope)
    scope_hashes = {scope: _state_hash(rows) for scope, rows in scopes.items()}
    daily_key = _hash_text(safe_date, sheet_key)
    version_key = _hash_text(
        safe_hash,
        safe_date,
        sheet_key,
        safe_phase,
        *(f"{scope}:{scope_hashes[scope]}" for scope in sorted(scope_hashes)),
    )
    savepoint = "daily_import_prepare_atomic"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        existing = conn.execute(
            "SELECT id FROM daily_import_versions WHERE version_key=?", (version_key,)
        ).fetchone()
        if existing:
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            return _version_payload(conn, int(existing["id"]), idempotent=True)
        timestamp = now_iso()
        workday = conn.execute(
            "SELECT * FROM daily_workdays WHERE daily_key=?", (daily_key,)
        ).fetchone()
        if workday and workday["lifecycle_status"] == "finalized":
            raise DailyImportError(
                "Ngày đã chốt; cần luồng mở lại có chủ đích trước khi tạo phiên bản mới",
                code="workday_finalized",
            )
        if not workday:
            batch_id = int(conn.execute(
                """INSERT INTO batches(work_date,source_name,status,created_at)
                   VALUES(?,'Workbook ngày – contract','draft',?)""",
                (safe_date, timestamp),
            ).lastrowid)
            workday_id = int(conn.execute(
                """INSERT INTO daily_workdays(
                       daily_key,work_date,day_sheet_key,batch_id,lifecycle_status,
                       revision,created_at,updated_at
                   ) VALUES(?,?,?,?,'picking',1,?,?)""",
                (daily_key, safe_date, sheet_key, batch_id, timestamp, timestamp),
            ).lastrowid)
            revision = 1
        else:
            workday_id = int(workday["id"])
            batch_id = int(workday["batch_id"])
            revision = int(workday["revision"]) + 1
            conn.execute(
                "UPDATE daily_workdays SET revision=?,updated_at=? WHERE id=?",
                (revision, timestamp, workday_id),
            )
        version_no = int(conn.execute(
            "SELECT COALESCE(MAX(version_no),0)+1 n FROM daily_import_versions WHERE daily_workday_id=?",
            (workday_id,),
        ).fetchone()["n"])
        version_id = int(conn.execute(
            """INSERT INTO daily_import_versions(
                   version_key,daily_workday_id,version_no,phase,source_hash,
                   exact_day_sheet,created_at
               ) VALUES(?,?,?,?,?,?,?)""",
            (version_key, workday_id, version_no, safe_phase, safe_hash, exact_sheet, timestamp),
        ).lastrowid)
        for scope in sorted(scopes):
            rows = scopes[scope]
            conn.execute(
                """INSERT INTO daily_import_scopes(
                       version_id,scope,write_capability,state,state_hash,row_count
                   ) VALUES(?,?,?,'previewed',?,?)""",
                (version_id, scope, CAPABILITIES[scope], scope_hashes[scope], len(rows)),
            )
            for row in rows:
                conn.execute(
                    """INSERT INTO daily_import_rows(
                           version_id,scope,row_key,payload_hash,source_row,state
                       ) VALUES(?,?,?,?,?,'previewed')""",
                    (version_id, scope, row["row_key"], row["payload_hash"], row["source_row"]),
                )
        _audit(
            conn,
            event_type="daily_import.preview",
            entity_id=version_id,
            timestamp=timestamp,
            metadata={
                "phase": safe_phase,
                "source_hash": safe_hash,
                "version_no": version_no,
                "scope_counts": {scope: len(rows) for scope, rows in scopes.items()},
            },
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return _version_payload(conn, version_id, idempotent=False)
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if isinstance(error, DailyImportError):
            raise
        raise DailyImportError(
            "Không tạo được contract import ngày; toàn bộ migration dữ liệu đã hoàn tác",
            code="prepare_failed",
        ) from error


def confirm_daily_import_scope(
    conn,
    *,
    version_id: int,
    scope: Any,
    expected_state_hash: Any,
    now_iso,
) -> dict[str, Any]:
    safe_scope = str(scope or "").strip()
    if safe_scope not in SCOPES:
        raise DailyImportError("Phạm vi import ngày không hợp lệ", code="invalid_scope", status=400)
    safe_hash = _sha256(expected_state_hash, "State hash")
    row = conn.execute(
        """SELECT s.*,v.phase,v.version_no,w.lifecycle_status
           FROM daily_import_scopes s
           JOIN daily_import_versions v ON v.id=s.version_id
           JOIN daily_workdays w ON w.id=v.daily_workday_id
           WHERE s.version_id=? AND s.scope=?""",
        (int(version_id), safe_scope),
    ).fetchone()
    if not row:
        raise DailyImportError("Không tìm thấy preview phạm vi", code="scope_not_found", status=404)
    if row["state_hash"] != safe_hash:
        raise DailyImportError(
            "Preview đã cũ hoặc phạm vi đã thay đổi; không cấp quyền ghi",
            code="stale_preview",
        )
    if row["state"] == "confirmed":
        return {
            "version_id": int(version_id),
            "scope": safe_scope,
            "write_capability": row["write_capability"],
            "confirmed_at": row["confirmed_at"],
            "idempotent": True,
        }
    if row["lifecycle_status"] == "finalized":
        raise DailyImportError("Ngày đã chốt; không cấp thêm quyền ghi", code="workday_finalized")
    timestamp = now_iso()
    savepoint = "daily_import_scope_confirm_atomic"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            """UPDATE daily_import_scopes SET state='confirmed',confirmed_at=?
               WHERE version_id=? AND scope=?""",
            (timestamp, int(version_id), safe_scope),
        )
        conn.execute(
            "UPDATE daily_import_rows SET state='confirmed' WHERE version_id=? AND scope=?",
            (int(version_id), safe_scope),
        )
        conn.execute(
            """UPDATE daily_import_versions SET confirmed_at=COALESCE(confirmed_at,?) WHERE id=?""",
            (timestamp, int(version_id)),
        )
        _audit(
            conn,
            event_type="daily_import.scope_confirm",
            entity_id=int(version_id),
            timestamp=timestamp,
            metadata={
                "phase": row["phase"],
                "scope": safe_scope,
                "version_no": int(row["version_no"]),
                "row_count": int(row["row_count"]),
                "state_hash": safe_hash,
            },
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if isinstance(error, DailyImportError):
            raise
        raise DailyImportError(
            "Không xác nhận được phạm vi; toàn bộ thay đổi đã hoàn tác",
            code="scope_confirm_failed",
        ) from error
    return {
        "version_id": int(version_id),
        "scope": safe_scope,
        "write_capability": row["write_capability"],
        "confirmed_at": timestamp,
        "idempotent": False,
    }


def finalize_daily_workday(conn, *, version_id: int, now_iso) -> dict[str, Any]:
    version = conn.execute(
        """SELECT v.*,w.id workday_id,w.batch_id,w.lifecycle_status
           FROM daily_import_versions v JOIN daily_workdays w ON w.id=v.daily_workday_id
           WHERE v.id=?""",
        (int(version_id),),
    ).fetchone()
    if not version:
        raise DailyImportError("Không tìm thấy phiên bản import", code="version_not_found", status=404)
    if version["lifecycle_status"] == "finalized":
        return {"batch_id": int(version["batch_id"]), "lifecycle_status": "finalized", "idempotent": True}
    if version["phase"] != "finalization":
        raise DailyImportError(
            "Chỉ phiên bản chốt ngày mới được chuyển trạng thái finalized",
            code="wrong_phase",
        )
    confirmed = int(conn.execute(
        "SELECT COUNT(*) n FROM daily_import_scopes WHERE version_id=? AND state='confirmed'",
        (int(version_id),),
    ).fetchone()["n"])
    if not confirmed:
        raise DailyImportError(
            "Cần xác nhận ít nhất một phạm vi trước khi chốt ngày",
            code="scope_confirmation_required",
        )
    timestamp = now_iso()
    savepoint = "daily_import_finalize_atomic"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            """UPDATE daily_workdays SET lifecycle_status='finalized',finalized_at=?,updated_at=?
               WHERE id=?""",
            (timestamp, timestamp, int(version["workday_id"])),
        )
        # The legacy batch remains draft until its existing approval gates pass;
        # lifecycle finalization never bypasses order validation/approval.
        _audit(
            conn,
            event_type="daily_import.finalize",
            entity_id=int(version_id),
            timestamp=timestamp,
            metadata={"version_no": int(version["version_no"]), "confirmed_scope_count": confirmed},
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if isinstance(error, DailyImportError):
            raise
        raise DailyImportError(
            "Không chốt được ngày; trạng thái đã hoàn tác",
            code="finalize_failed",
        ) from error
    return {"batch_id": int(version["batch_id"]), "lifecycle_status": "finalized", "idempotent": False}
