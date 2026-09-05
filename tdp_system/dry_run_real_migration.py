from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "tdp_system" / "data" / "tdp.sqlite3"
INPUTS = ROOT / "_HANDOFF" / "EXTERNAL_INPUTS"
BOSUNG = ROOT / "bosung.30.8.26"
ATTENDANCE_ROOT = BOSUNG / "CHẤM CÔNG+ SUẤT ĂN  2026"
MEAL_ROOT = ATTENDANCE_ROOT / "SUẤT ĂN XƯỞNG CƠM 2026"

# Volatile/supporting tables may legitimately receive bookkeeping rows when the
# new source starts. Every other pre-existing business table is fingerprinted
# before and immediately after schema initialization.
PRESERVATION_EXCLUSIONS = {
    "audit_log",
    "print_jobs",
    "settings",
    "sqlite_sequence",
}

# Tables carrying quantities, balances, prices, debt, or payroll amounts.
# Only hashes and row counts are ever written to the migration report.
FINANCIAL_TABLES = {
    "attendance_entries",
    "balances",
    "dated_prices",
    "debt_adjustments",
    "historical_payable_lines",
    "inventory_transactions",
    "kitchen_labor_costs",
    "meal_attendance",
    "meal_plan_items",
    "meal_plans",
    "orders",
    "outgoing_invoice_drafts",
    "outgoing_invoice_lines",
    "payments",
    "payroll_adjustments",
    "product_prices",
    "purchase_order_lines",
    "xcom_meal_tariffs",
    "xcom_payment_previews",
}

SAFE_COUNT_METRICS = {
    "attendance_entries", "dates", "duplicate", "error", "errors", "items",
    "kitchens", "labor_cost_entries", "manual_attendance_preserved",
    "manual_payroll_preserved", "negative", "new", "new_names", "new_products",
    "payroll_overrides", "plans", "ready", "retained_products", "skipped",
    "rows", "source_rows", "staff", "suppliers", "total", "unchanged", "unchanged_names",
    "unchanged_products", "unique_products", "update", "update_names",
    "update_products", "warning", "warnings",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def clone_sqlite(source_path: Path, target_path: Path) -> None:
    source_uri = source_path.resolve().as_uri() + "?mode=ro"
    source = sqlite3.connect(source_uri, uri=True)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def unique_file(root: Path, pattern: str) -> Path:
    candidates = sorted(path for path in root.glob(pattern) if path.is_file())
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected exactly one source matching {pattern!r}; found {len(candidates)}"
        )
    return candidates[0]


def meal_attendance_file(period: str, preferred_name: str) -> Path:
    preferred = MEAL_ROOT / preferred_name
    if preferred.is_file():
        return preferred
    month = int(period[-2:])
    month_pattern = re.compile(rf"^SU.*?\s+T{month}(?:[-.]|$)", re.IGNORECASE)
    candidates = [
        path
        for path in BOSUNG.rglob("*.xlsx")
        if not path.name.startswith("~$")
        and month_pattern.search(path.name)
        and ("XƯỞNG CƠM" in path.parent.name.upper() or "XU_NG COM" in path.parent.name.upper())
    ]
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected exactly one meal-attendance source for {period}; found {len(candidates)}"
        )
    return candidates[0]


def canonical_digest(connection: sqlite3.Connection, statements: list[tuple[str, tuple]]) -> str:
    digest = hashlib.sha256()
    for sql, params in statements:
        digest.update(sql.encode("utf-8"))
        digest.update(b"\n")
        for row in connection.execute(sql, params):
            digest.update(
                json.dumps(list(row), ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
            )
            digest.update(b"\n")
    return digest.hexdigest().upper()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def user_tables(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """SELECT name FROM sqlite_master
               WHERE type='table' AND name NOT LIKE 'sqlite_%'
               ORDER BY name"""
        )
    ]


def capture_existing_table_fingerprints(
    connection: sqlite3.Connection,
    table_names: list[str] | None = None,
    baseline: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Fingerprint existing values without returning or logging any raw data."""
    available = set(user_tables(connection))
    selected = table_names or sorted(available - PRESERVATION_EXCLUSIONS)
    result: dict[str, dict[str, Any]] = {}
    for table in selected:
        if table not in available:
            continue
        quoted_table = quote_identifier(table)
        columns = (
            list(baseline[table]["columns"])
            if baseline is not None and table in baseline
            else [
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({quoted_table})")
            ]
        )
        quoted_columns = ",".join(quote_identifier(column) for column in columns)
        order_clause = ",".join(quote_identifier(column) for column in columns)
        rows_sql = f"SELECT {quoted_columns} FROM {quoted_table}"
        if order_clause:
            rows_sql += f" ORDER BY {order_clause}"
        row_count = int(
            connection.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
        )
        result[table] = {
            "columns": columns,
            "row_count": row_count,
            "digest": canonical_digest(connection, [(rows_sql, ())]),
        }
    return result


def compare_table_fingerprints(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    missing_tables = sorted(set(before) - set(after))
    count_changes = sorted(
        table for table in set(before) & set(after)
        if before[table]["row_count"] != after[table]["row_count"]
    )
    content_changes = sorted(
        table for table in set(before) & set(after)
        if before[table]["digest"] != after[table]["digest"]
    )
    financial_changes = sorted(
        table for table in content_changes if table in FINANCIAL_TABLES
    )
    return {
        "tables_checked": len(before),
        "missing_tables": missing_tables,
        "count_changes": count_changes,
        "content_changes": content_changes,
        "financial_changes": financial_changes,
        "counts_unchanged": not missing_tables and not count_changes,
        "content_unchanged": not missing_tables and not content_changes,
        "financial_values_unchanged": not missing_tables and not financial_changes,
    }


def safe_step_summary(step: dict[str, Any]) -> dict[str, Any]:
    """Reduce an import result to non-sensitive operational evidence."""
    preview = step.get("preview") if isinstance(step.get("preview"), dict) else {}
    counts = preview.get("counts") if isinstance(preview.get("counts"), dict) else {}
    summary: dict[str, Any] = {
        "name": str(step.get("name") or ""),
        "status": "blocked" if step.get("blocked") is True else "ready",
        "semantic_idempotent": step.get("semantic_idempotent") is True,
        "preview_row_count": int(preview.get("preview_rows_returned") or 0),
        "preview_issue_count": int(preview.get("issue_rows_returned") or 0),
        "preview_warning_count": int(preview.get("warning_messages") or 0),
        "count_metrics": {
            str(key): int(value)
            for key, value in counts.items()
            if key in SAFE_COUNT_METRICS
            and isinstance(value, int)
            and not isinstance(value, bool)
        },
    }
    for key in (
        "rows_first",
        "rows_repeat",
        "ledger_rows_first",
        "ledger_rows_repeat",
        "batches_first",
        "batches_repeat",
    ):
        if isinstance(step.get(key), int) and not isinstance(step.get(key), bool):
            summary[key] = int(step[key])
    return summary


def sensitive_log_policy(report: dict[str, Any]) -> dict[str, bool]:
    """Declare and mechanically validate the report's strict allowlist shape."""
    allowed_top_level = {
        "run_dir", "source_db", "source_hash_before", "source_hash_after",
        "source_db_unchanged", "clone_backup_path", "clone_hash_before_schema",
        "clone_hash_after_schema", "clone_hash_final", "clone_integrity_before",
        "schema_migration", "source_new_health", "source_new_bootstrap",
        "steps", "blocked_steps", "all_ready_steps_idempotent",
        "clone_final_counts", "clone_integrity", "checks", "migration_passed",
        "sensitive_data_policy",
    }
    allowed_step_keys = {
        "name", "status", "semantic_idempotent", "preview_row_count",
        "preview_issue_count", "preview_warning_count", "count_metrics",
        "rows_first", "rows_repeat", "ledger_rows_first", "ledger_rows_repeat",
        "batches_first", "batches_repeat",
    }
    top_level_ok = set(report).issubset(allowed_top_level)
    steps_ok = isinstance(report.get("steps"), list) and all(
        isinstance(step, dict) and set(step).issubset(allowed_step_keys)
        and isinstance(step.get("count_metrics", {}), dict)
        and set(step.get("count_metrics", {})).issubset(SAFE_COUNT_METRICS)
        for step in report.get("steps", [])
    )
    return {
        "environment_values_logged": False,
        "raw_rows_logged": False,
        "personal_identifiers_logged": False,
        "business_amounts_logged": False,
        "allowlist_shape_valid": bool(top_level_ok and steps_ok),
    }


def compact_error(response) -> str:
    payload = response.get_json(silent=True)
    if isinstance(payload, dict):
        return str(payload.get("error") or payload)[:1200]
    return response.get_data(as_text=True)[:1200]


def require_ok(response, label: str) -> dict:
    payload = response.get_json(silent=True)
    if response.status_code != 200 or not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError(f"{label}: HTTP {response.status_code}: {compact_error(response)}")
    return payload


def upload(client, url: str, path: Path, fields: dict | None = None) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = dict(fields or {})
    data["file"] = (io.BytesIO(path.read_bytes()), path.name)
    return require_ok(
        client.post(url, data=data, content_type="multipart/form-data"),
        f"POST {url} ({path.name})",
    )


def confirm(client, url: str, token: str, extra: dict | None = None) -> dict:
    body = {"token": token, "confirmed": True}
    body.update(extra or {})
    return require_ok(client.post(url, json=body), f"POST {url}")


def preview_summary(payload: dict) -> dict:
    summary = {}
    for key in (
        "filename", "sheet", "header_row", "period", "periods", "work_date", "work_dates",
        "weekly", "can_confirm", "can_confirm_with_overrides", "counts", "totals",
        "preview_truncated", "source_hash",
    ):
        if key in payload:
            summary[key] = payload[key]
    if isinstance(payload.get("warnings"), list):
        summary["warning_messages"] = len(payload["warnings"])
    if isinstance(payload.get("issues"), list):
        summary["issue_rows_returned"] = len(payload["issues"])
    if isinstance(payload.get("rows"), list):
        summary["preview_rows_returned"] = len(payload["rows"])
    if isinstance(payload.get("plans"), list):
        summary["plans"] = [
            {
                "sheet": item.get("sheet"),
                "work_date": item.get("work_date"),
                "kitchen": item.get("kitchen"),
                "unit_code": item.get("xcom_code"),
                "shift": item.get("shift"),
                "meal_count": item.get("meal_count"),
                "items": len(item.get("items") or []),
                "errors": len(item.get("errors") or []),
                "warnings": len(item.get("warnings") or []),
            }
            for item in payload["plans"]
        ]
    return summary


def connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fixture_work_date(*labels: str, year: int = 2026) -> str:
    """Resolve a dated fixture label exactly as the import UI does.

    Legacy daily workbooks carry only ``dd.mm`` in the filename/sheet name, so
    the API intentionally leaves ``detectedWorkDate`` empty and the operator UI
    supplies the date.  This release dry-run is pinned to the 2026 snapshot and
    must emulate that explicit UI choice instead of reporting a false blocker.
    """

    for label in labels:
        match = re.search(r"(?:^|\D)(\d{1,2})[.\-_/](\d{1,2})(?:\D|$)", str(label or ""))
        if not match:
            continue
        try:
            return date(year, int(match.group(2)), int(match.group(1))).isoformat()
        except ValueError:
            continue
    return ""


def run_order_import_replay(client, clone_path: Path, orders_path: Path) -> dict[str, Any]:
    order_analyze = upload(client, "/api/import/analyze", orders_path)
    order_work_date = str(order_analyze.get("detectedWorkDate") or "")
    candidates = order_analyze.get("sheets") or []
    selected_sheets = [
        item["name"] for item in candidates
        if re.search(r"(?<!\d)29\D*0?8(?!\d)", str(item.get("name") or ""))
    ]
    if not order_work_date and len(selected_sheets) == 1:
        order_work_date = fixture_work_date(orders_path.name, selected_sheets[0])
    if (
        not re.fullmatch(r"\d{4}-\d{2}-\d{2}", order_work_date)
        or len(selected_sheets) != 1
    ):
        client.post("/api/import/cancel", json={"token": order_analyze.get("token")})
        return {
            "name": "orders_detected_daily_workbook",
            "preview": {
                "preview_rows_returned": sum(
                    int(item.get("rows") or 0) for item in candidates
                    if isinstance(item, dict)
                ),
                "issue_rows_returned": 1,
            },
            "blocked": True,
            "semantic_idempotent": False,
        }

    order_first_payload = require_ok(
        client.post("/api/import/confirm", json={
            "token": order_analyze["token"], "sheets": selected_sheets,
            "work_date": order_work_date,
            "state_hash": order_analyze.get("stateHash", ""),
        }),
        "POST /api/import/confirm first",
    )
    order_query = [(
        """SELECT b.id,b.work_date,b.source_name,b.status,o.work_date,o.contractor,o.kitchen,
                  o.product_code,o.product_name,o.qty,o.actual_received,o.actual_delivered,
                  o.damaged_qty,o.supplier_return_qty,o.customer_return_qty,o.unit,o.supplier,
                  o.buy_price,o.sell_price,o.tax,o.invoice_nature,o.purchase_list,o.seller,o.cccd,
                  o.note,o.source_sheet,o.source_row,o.errors,o.warnings
           FROM batches b JOIN orders o ON o.batch_id=b.id
           WHERE b.source_name=? ORDER BY b.id,o.id""",
        (orders_path.name,),
    )]
    with connection(clone_path) as conn:
        order_digest_first = canonical_digest(conn, order_query)
        batches_first = conn.execute(
            "SELECT COUNT(*) n FROM batches WHERE source_name=?", (orders_path.name,),
        ).fetchone()["n"]
        order_rows_first = conn.execute(
            """SELECT COUNT(*) n FROM orders o JOIN batches b ON b.id=o.batch_id
               WHERE b.source_name=?""", (orders_path.name,),
        ).fetchone()["n"]

    order_repeat_analyze = upload(client, "/api/import/analyze", orders_path)
    if order_repeat_analyze.get("detectedWorkDate") != order_work_date:
        client.post("/api/import/cancel", json={"token": order_repeat_analyze.get("token")})
        raise RuntimeError("Order workbook detected date changed between repeated analyses")
    order_repeat_payload = require_ok(
        client.post("/api/import/confirm", json={
            "token": order_repeat_analyze["token"], "sheets": selected_sheets,
            "work_date": order_work_date,
            "state_hash": order_repeat_analyze.get("stateHash", ""),
        }),
        "POST /api/import/confirm repeat",
    )
    with connection(clone_path) as conn:
        order_digest_repeat = canonical_digest(conn, order_query)
        batches_repeat = conn.execute(
            "SELECT COUNT(*) n FROM batches WHERE source_name=?", (orders_path.name,),
        ).fetchone()["n"]
        order_rows_repeat = conn.execute(
            """SELECT COUNT(*) n FROM orders o JOIN batches b ON b.id=o.batch_id
               WHERE b.source_name=?""", (orders_path.name,),
        ).fetchone()["n"]

    return {
        "name": "orders_detected_daily_workbook",
        "preview": {
            "preview_rows_returned": order_rows_first,
            "issue_rows_returned": 0,
        },
        "batches_first": batches_first,
        "batches_repeat": batches_repeat,
        "rows_first": order_rows_first,
        "rows_repeat": order_rows_repeat,
        "semantic_idempotent": (
            order_digest_first == order_digest_repeat
            and order_first_payload.get("batch", {}).get("id")
            == order_repeat_payload.get("batch", {}).get("id")
        ),
    }


def main() -> int:
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(SOURCE_DB)

    source_hash_before = file_sha256(SOURCE_DB)
    run_dir = Path(tempfile.mkdtemp(prefix="tdp-real-migration-dry-run-"))
    clone_path = run_dir / "tdp-migration-clone.sqlite3"
    clone_sqlite(SOURCE_DB, clone_path)
    clone_hash_before_schema = file_sha256(clone_path)
    with connection(clone_path) as conn:
        clone_integrity_before = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        legacy_before = capture_existing_table_fingerprints(conn)

    # The application must be imported only after its DB path points at the clone.
    os.environ["TDP_DB_PATH"] = str(clone_path)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tdp_system import server

    server.DB_PATH = clone_path
    server.DATA_DIR = run_dir / "runtime-data"
    server.DATA_DIR.mkdir(parents=True, exist_ok=True)
    server.MASTER_SOURCE = run_dir / "master-sync-disabled.xlsx"
    server.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=True)
    server.init_database()
    client = server.app.test_client()

    clone_hash_after_schema = file_sha256(clone_path)
    with connection(clone_path) as conn:
        legacy_after = capture_existing_table_fingerprints(
            conn,
            table_names=sorted(legacy_before),
            baseline=legacy_before,
        )
    schema_migration = compare_table_fingerprints(legacy_before, legacy_after)

    health_response = client.get("/health")
    health_payload = health_response.get_json(silent=True) or {}
    source_new_health = {
        "status_code": health_response.status_code,
        "ok": health_payload.get("ok") is True,
        "database_ready": health_payload.get("database_ready") is True,
        "schema_ready": health_payload.get("schema_ready") is True,
        "integrity": str(health_payload.get("integrity") or ""),
        "duplicate_invoice_identity_warning": (
            health_payload.get("duplicate_invoice_identity_warning") is True
        ),
        "duplicate_payable_source_warning": (
            health_payload.get("duplicate_payable_source_warning") is True
        ),
    }
    bootstrap_response = client.get("/api/bootstrap")
    bootstrap_payload = bootstrap_response.get_json(silent=True) or {}
    source_new_bootstrap = {
        "status_code": bootstrap_response.status_code,
        "ok": bootstrap_payload.get("ok") is True,
    }

    report: dict = {
        "run_dir": str(run_dir),
        "source_db": str(SOURCE_DB),
        "source_hash_before": source_hash_before,
        "clone_backup_path": str(clone_path),
        "clone_hash_before_schema": clone_hash_before_schema,
        "clone_hash_after_schema": clone_hash_after_schema,
        "clone_integrity_before": clone_integrity_before,
        "schema_migration": schema_migration,
        "source_new_health": source_new_health,
        "source_new_bootstrap": source_new_bootstrap,
        "steps": [],
    }

    catalog_path = unique_file(INPUTS, "08410fad*.xlsx")
    catalog_preview = upload(client, "/api/catalog/import/preview", catalog_path)
    catalog_first = confirm(client, "/api/catalog/import/confirm", catalog_preview["token"])
    with connection(clone_path) as conn:
        catalog_digest_first = canonical_digest(conn, [
            ("SELECT code,name,unit,tax,COALESCE(product_group,'') FROM products ORDER BY code", ()),
            ("SELECT product_code,invoice_name FROM outgoing_product_names ORDER BY product_code", ()),
        ])
    catalog_repeat_preview = upload(client, "/api/catalog/import/preview", catalog_path)
    catalog_repeat = confirm(client, "/api/catalog/import/confirm", catalog_repeat_preview["token"])
    with connection(clone_path) as conn:
        catalog_digest_repeat = canonical_digest(conn, [
            ("SELECT code,name,unit,tax,COALESCE(product_group,'') FROM products ORDER BY code", ()),
            ("SELECT product_code,invoice_name FROM outgoing_product_names ORDER BY product_code", ()),
        ])
    report["steps"].append({
        "name": "catalog_final",
        "file": str(catalog_path),
        "preview": preview_summary(catalog_preview),
        "confirm_first": catalog_first,
        "confirm_repeat": catalog_repeat,
        "semantic_idempotent": catalog_digest_first == catalog_digest_repeat,
    })

    opening_path = INPUTS / "TĐK T8-2026.xlsx thụy.xlsx"
    opening_preview = upload(
        client, "/api/inventory/opening/import/preview", opening_path, {"period": "2026-08"},
    )
    opening_first = confirm(client, "/api/inventory/opening/import/confirm", opening_preview["token"])
    opening_query = [(
        """SELECT txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,source_line,status,note
           FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-08'
           ORDER BY source_line""",
        (),
    )]
    with connection(clone_path) as conn:
        opening_digest_first = canonical_digest(conn, opening_query)
        opening_rows_first = conn.execute(
            "SELECT COUNT(*) n FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-08'"
        ).fetchone()["n"]
    opening_repeat_preview = upload(
        client, "/api/inventory/opening/import/preview", opening_path, {"period": "2026-08"},
    )
    opening_repeat = confirm(client, "/api/inventory/opening/import/confirm", opening_repeat_preview["token"])
    with connection(clone_path) as conn:
        opening_digest_repeat = canonical_digest(conn, opening_query)
        opening_rows_repeat = conn.execute(
            "SELECT COUNT(*) n FROM inventory_transactions WHERE source_type='OPENING' AND source_id='2026-08'"
        ).fetchone()["n"]
    report["steps"].append({
        "name": "opening_2026_08",
        "file": str(opening_path),
        "preview": preview_summary(opening_preview),
        "confirm_first": {key: opening_first.get(key) for key in (
            "period", "inserted_products", "inserted", "updated", "deleted_stale", "processed", "totals"
        )},
        "confirm_repeat": {key: opening_repeat.get(key) for key in (
            "period", "inserted_products", "inserted", "updated", "deleted_stale", "processed", "totals"
        )},
        "rows_first": opening_rows_first,
        "rows_repeat": opening_rows_repeat,
        "semantic_idempotent": opening_digest_first == opening_digest_repeat,
    })

    kitchen_path = INPUTS / "xưởng cơm.xlsx"
    kitchen_preview = upload(
        client, "/api/kitchen/import/preview", kitchen_path, {"work_date": "2026-09-01"},
    )
    kitchen_first = confirm(
        client, "/api/kitchen/import/confirm", kitchen_preview["token"],
        {"meal_count_overrides": {}},
    )
    kitchen_query = [
        (
            """SELECT import_key,work_date,kitchen,shift,meal_count,unit_code,status,note,source_file,
                      source_sheet,source_row_start,source_row_end,menu_count,servings_per_menu,
                      meal_price,other_cost,source_financials_json
               FROM meal_plans WHERE source_file=? ORDER BY import_key""",
            (kitchen_path.name,),
        ),
        (
            """SELECT p.import_key,i.dish_name,i.product_code,i.product_name,i.norm_qty,i.unit,
                      i.supplier,i.buy_price,i.price_source,i.source_norm_per_1000,
                      i.applicable_meal_count,i.source_row,i.source_amount
               FROM meal_plan_items i JOIN meal_plans p ON p.id=i.plan_id
               WHERE p.source_file=? ORDER BY p.import_key,i.source_row,i.id""",
            (kitchen_path.name,),
        ),
        ("SELECT kitchen_code,unit_code FROM kitchen_units ORDER BY kitchen_code", ()),
        (
            """SELECT product_code,price_group,period,price_value FROM dated_prices
               WHERE price_group='HATRAN' AND period='2026-09' ORDER BY product_code""",
            (),
        ),
    ]
    with connection(clone_path) as conn:
        kitchen_digest_first = canonical_digest(conn, kitchen_query)
    kitchen_repeat_preview = upload(
        client, "/api/kitchen/import/preview", kitchen_path, {"work_date": "2026-09-01"},
    )
    kitchen_repeat = confirm(
        client, "/api/kitchen/import/confirm", kitchen_repeat_preview["token"],
        {"meal_count_overrides": {}},
    )
    with connection(clone_path) as conn:
        kitchen_digest_repeat = canonical_digest(conn, kitchen_query)
    report["steps"].append({
        "name": "kitchen_2026_09_01",
        "file": str(kitchen_path),
        "preview": preview_summary(kitchen_preview),
        "confirm_first": kitchen_first,
        "confirm_repeat": kitchen_repeat,
        "semantic_idempotent": kitchen_digest_first == kitchen_digest_repeat,
    })

    meal_files = {
        "2026-01": "SUẤT ĂN T1-2026 -.xlsx",
        "2026-02": "SUẤT ĂN T2-2026.xlsx",
        "2026-03": "SUẤT ĂN T3-2026 .xlsx",
        "2026-04": "SUẤT ĂN T4-2026.xlsx",
        "2026-05": "SUẤT ĂN T5-2026.xlsx",
        "2026-06": "SUẤT ĂN T6.2026.xlsx",
        "2026-07": "SUẤT ĂN T7.2026.xlsx",
        "2026-08": "SUẤT ĂN T8.2026.xlsx",
    }
    for period, filename in meal_files.items():
        path = meal_attendance_file(period, filename)
        meal_preview = upload(
            client, "/api/kitchen/attendance/import/preview", path, {"period": period},
        )
        if meal_preview.get("can_confirm") is not True:
            issue_sample = [
                {
                    "work_date": item.get("work_date"),
                    "kitchen": item.get("kitchen"),
                    "shift": item.get("shift"),
                    "errors": item.get("errors"),
                    "warnings": item.get("warnings"),
                }
                for item in (meal_preview.get("rows") or []) if item.get("errors")
            ][:20]
            report["steps"].append({
                "name": f"meal_attendance_{period}",
                "file": str(path),
                "preview": preview_summary(meal_preview),
                "blocked": True,
                "blocker_issues": issue_sample,
                "semantic_idempotent": False,
            })
            continue
        meal_first = confirm(client, "/api/kitchen/attendance/import/confirm", meal_preview["token"])
        meal_query = [(
            """SELECT work_date,kitchen,shift,actual_count,ordered_count,source_type,source_sheet,source_column
               FROM meal_attendance WHERE substr(work_date,1,7)=? ORDER BY work_date,kitchen,shift""",
            (period,),
        )]
        with connection(clone_path) as conn:
            meal_digest_first = canonical_digest(conn, meal_query)
            month_rows_first = conn.execute(
                "SELECT COUNT(*) n FROM meal_attendance WHERE substr(work_date,1,7)=?", (period,),
            ).fetchone()["n"]
        meal_repeat_preview = upload(
            client, "/api/kitchen/attendance/import/preview", path, {"period": period},
        )
        meal_repeat = confirm(client, "/api/kitchen/attendance/import/confirm", meal_repeat_preview["token"])
        with connection(clone_path) as conn:
            meal_digest_repeat = canonical_digest(conn, meal_query)
            month_rows_repeat = conn.execute(
                "SELECT COUNT(*) n FROM meal_attendance WHERE substr(work_date,1,7)=?", (period,),
            ).fetchone()["n"]
        report["steps"].append({
            "name": f"meal_attendance_{period}",
            "file": str(path),
            "preview": preview_summary(meal_preview),
            "confirm_first": meal_first,
            "confirm_repeat": meal_repeat,
            "rows_first": month_rows_first,
            "rows_repeat": month_rows_repeat,
            "semantic_idempotent": meal_digest_first == meal_digest_repeat,
        })

    attendance_path = ATTENDANCE_ROOT / "CHẤM CÔNG T8.2026.xlsx"
    attendance_preview = upload(
        client, "/api/attendance/import/preview", attendance_path, {"period": "2026-08"},
    )
    attendance_first = confirm(client, "/api/attendance/import/confirm", attendance_preview["token"])
    attendance_query = [
        (
            """SELECT s.employee_code,s.full_name,s.role_name,s.base_salary,a.work_date,a.normal_hours,
                      a.overtime_hours,a.sunday_hours,a.night_hours,a.holiday_hours,a.note,a.source
               FROM attendance_entries a JOIN staff s ON s.id=a.employee_id
               WHERE substr(a.work_date,1,7)='2026-08' ORDER BY s.employee_code,a.work_date""",
            (),
        ),
        (
            """SELECT s.employee_code,p.month,p.allowance,p.responsibility,p.advance,
                      p.probation_deduction,p.bhxh_employee_amount,p.bhxh_company_amount,
                      p.gross_override,p.net_override,p.use_override,p.note
               FROM payroll_adjustments p JOIN staff s ON s.id=p.employee_id
               WHERE p.month='2026-08' ORDER BY s.employee_code""",
            (),
        ),
        (
            """SELECT work_date,kitchen,amount,source FROM kitchen_labor_costs
               WHERE substr(work_date,1,7)='2026-08' ORDER BY work_date,kitchen,source""",
            (),
        ),
    ]
    with connection(clone_path) as conn:
        attendance_digest_first = canonical_digest(conn, attendance_query)
    attendance_repeat_preview = upload(
        client, "/api/attendance/import/preview", attendance_path, {"period": "2026-08"},
    )
    attendance_repeat = confirm(client, "/api/attendance/import/confirm", attendance_repeat_preview["token"])
    with connection(clone_path) as conn:
        attendance_digest_repeat = canonical_digest(conn, attendance_query)
    report["steps"].append({
        "name": "attendance_payroll_2026_08",
        "file": str(attendance_path),
        "preview": preview_summary(attendance_preview),
        "confirm_first": attendance_first,
        "confirm_repeat": attendance_repeat,
        "semantic_idempotent": attendance_digest_first == attendance_digest_repeat,
    })

    payables_path = BOSUNG / "Công nợ phải trả Thành Đạt Phát.xlsx"
    payables_preview = upload(client, "/api/debts/payables/import/preview", payables_path)
    payables_first = confirm(client, "/api/debts/payables/import/confirm", payables_preview["token"])
    payables_query = [(
        """SELECT purchase_date,kitchen,item_name,qty,unit,supplier,buy_price,damaged_qty,
                  added_qty,reduced_qty,missing_qty,actual_qty,source_amount,calculated_amount,
                  amount,note,source_sheet,source_row,source_hash
           FROM historical_payable_lines ORDER BY source_hash,source_sheet,source_row""",
        (),
    )]
    payable_ledger_query = [
        (
            """SELECT source_key,source_type,source_table,source_ref,source_revision,
                      source_hash,source_sheet,source_row,batch_id,work_date,kitchen,
                      product_code,product_name,actual_qty,unit,supplier_code,
                      supplier_snapshot,buy_price,amount,paid_amount,status,reversal_reason,
                      snapshot_hash,revision
               FROM payable_ledger_lines ORDER BY source_key""",
            (),
        ),
        (
            """SELECT l.source_key,r.revision,r.change_kind,r.snapshot_hash,
                      r.source_revision,r.source_hash,r.amount,r.paid_amount,r.status,
                      r.reversal_reason
               FROM payable_ledger_revisions r
               JOIN payable_ledger_lines l ON l.id=r.ledger_line_id
               ORDER BY l.source_key,r.revision""",
            (),
        ),
    ]
    with connection(clone_path) as conn:
        payables_digest_first = canonical_digest(conn, payables_query)
        payables_rows_first = conn.execute("SELECT COUNT(*) n FROM historical_payable_lines").fetchone()["n"]
        payable_ledger_digest_first = canonical_digest(conn, payable_ledger_query)
        payable_ledger_rows_first = conn.execute(
            "SELECT COUNT(*) n FROM payable_ledger_lines WHERE source_type='historical_import'"
        ).fetchone()["n"]
    payables_repeat_preview = upload(client, "/api/debts/payables/import/preview", payables_path)
    payables_repeat = confirm(client, "/api/debts/payables/import/confirm", payables_repeat_preview["token"])
    with connection(clone_path) as conn:
        payables_digest_repeat = canonical_digest(conn, payables_query)
        payables_rows_repeat = conn.execute("SELECT COUNT(*) n FROM historical_payable_lines").fetchone()["n"]
        payable_ledger_digest_repeat = canonical_digest(conn, payable_ledger_query)
        payable_ledger_rows_repeat = conn.execute(
            "SELECT COUNT(*) n FROM payable_ledger_lines WHERE source_type='historical_import'"
        ).fetchone()["n"]
    report["steps"].append({
        "name": "historical_payables",
        "file": str(payables_path),
        "preview": preview_summary(payables_preview),
        "confirm_first": payables_first,
        "confirm_repeat": payables_repeat,
        "rows_first": payables_rows_first,
        "rows_repeat": payables_rows_repeat,
        "ledger_rows_first": payable_ledger_rows_first,
        "ledger_rows_repeat": payable_ledger_rows_repeat,
        "semantic_idempotent": (
            payables_digest_first == payables_digest_repeat
            and payable_ledger_digest_first == payable_ledger_digest_repeat
        ),
    })

    orders_path = unique_file(INPUTS, "*29.08*.xlsx")
    report["steps"].append(run_order_import_replay(client, clone_path, orders_path))

    with connection(clone_path) as conn:
        clone_final_counts = {
            table: conn.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"]
            for table in (
                "products", "outgoing_product_names", "inventory_transactions", "meal_plans",
                "meal_plan_items", "meal_attendance", "staff", "attendance_entries",
                "payroll_adjustments", "kitchen_labor_costs", "historical_payable_lines",
                "payable_ledger_lines", "payable_ledger_revisions",
                "payable_payment_allocations", "payable_payment_revisions",
                "receivable_ledger_lines", "receivable_ledger_revisions",
                "batches", "orders",
            )
        }
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_issue_count = sum(1 for _ in conn.execute("PRAGMA foreign_key_check"))
        clone_integrity = {
            "integrity_check": integrity,
            "foreign_key_issue_count": foreign_key_issue_count,
        }

    source_hash_after = file_sha256(SOURCE_DB)
    source_db_unchanged = source_hash_after == source_hash_before
    blocked_steps = [
        step["name"] for step in report["steps"] if step.get("blocked") is True
    ]
    all_ready_steps_idempotent = all(
        step.get("semantic_idempotent") is True
        for step in report["steps"] if step.get("blocked") is not True
    )
    clone_hash_final = file_sha256(clone_path)
    safe_report: dict[str, Any] = {
        "run_dir": str(run_dir),
        "source_db": str(SOURCE_DB),
        "source_hash_before": source_hash_before,
        "source_hash_after": source_hash_after,
        "source_db_unchanged": source_db_unchanged,
        "clone_backup_path": str(clone_path),
        "clone_hash_before_schema": clone_hash_before_schema,
        "clone_hash_after_schema": clone_hash_after_schema,
        "clone_hash_final": clone_hash_final,
        "clone_integrity_before": clone_integrity_before,
        "schema_migration": schema_migration,
        "source_new_health": source_new_health,
        "source_new_bootstrap": source_new_bootstrap,
        "steps": [safe_step_summary(step) for step in report["steps"]],
        "blocked_steps": blocked_steps,
        "all_ready_steps_idempotent": all_ready_steps_idempotent,
        "clone_final_counts": clone_final_counts,
        "clone_integrity": clone_integrity,
    }
    safe_report["sensitive_data_policy"] = sensitive_log_policy(safe_report)
    checks = {
        "source_db_unchanged": source_db_unchanged,
        "clone_integrity_before_ok": clone_integrity_before.lower() == "ok",
        "legacy_counts_unchanged": schema_migration["counts_unchanged"],
        "legacy_content_unchanged": schema_migration["content_unchanged"],
        "legacy_financial_values_unchanged": schema_migration["financial_values_unchanged"],
        "source_new_health_ok": (
            source_new_health["status_code"] == 200
            and source_new_health["ok"]
            and source_new_health["database_ready"]
            and source_new_health["schema_ready"]
            and source_new_health["integrity"] == "ok"
            and not source_new_health["duplicate_invoice_identity_warning"]
            and not source_new_health["duplicate_payable_source_warning"]
        ),
        "source_new_bootstrap_ok": (
            source_new_bootstrap["status_code"] == 200 and source_new_bootstrap["ok"]
        ),
        "clone_final_integrity_ok": (
            str(clone_integrity["integrity_check"]).lower() == "ok"
            and clone_integrity["foreign_key_issue_count"] == 0
        ),
        "ready_import_steps_idempotent": all_ready_steps_idempotent,
        "sensitive_report_allowlist_ok": safe_report["sensitive_data_policy"][
            "allowlist_shape_valid"
        ],
    }
    safe_report["checks"] = checks
    safe_report["migration_passed"] = all(checks.values())
    safe_report["sensitive_data_policy"] = sensitive_log_policy(safe_report)
    report_path = run_dir / "migration-report.json"
    report_path.write_text(
        json.dumps(safe_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "migration_passed": safe_report["migration_passed"],
        "checks": safe_report["checks"],
        "blocked_steps": safe_report["blocked_steps"],
        "source_hash_before": source_hash_before,
        "source_hash_after": source_hash_after,
        "clone_hash_before_schema": clone_hash_before_schema,
        "clone_hash_after_schema": clone_hash_after_schema,
        "clone_hash_final": clone_hash_final,
    }, ensure_ascii=False, indent=2))
    print(f"REPORT_PATH={report_path}")
    return 0 if safe_report["migration_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
