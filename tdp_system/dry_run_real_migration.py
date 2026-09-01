from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "tdp_system" / "data" / "tdp.sqlite3"
INPUTS = ROOT / "_HANDOFF" / "EXTERNAL_INPUTS"
BOSUNG = ROOT / "bosung.30.8.26"
ATTENDANCE_ROOT = BOSUNG / "CHẤM CÔNG+ SUẤT ĂN  2026"
MEAL_ROOT = ATTENDANCE_ROOT / "SUẤT ĂN XƯỞNG CƠM 2026"


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


def main() -> int:
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(SOURCE_DB)

    source_hash_before = file_sha256(SOURCE_DB)
    run_dir = Path(tempfile.mkdtemp(prefix="tdp-real-migration-dry-run-"))
    clone_path = run_dir / "tdp-migration-clone.sqlite3"
    clone_sqlite(SOURCE_DB, clone_path)
    clone_hash_before_schema = file_sha256(clone_path)

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

    report: dict = {
        "run_dir": str(run_dir),
        "source_db": str(SOURCE_DB),
        "source_hash_before": source_hash_before,
        "clone_hash_before_schema": clone_hash_before_schema,
        "steps": [],
    }

    catalog_path = INPUTS / "08410fad-ten_hang_dung_ma_hang thụy.xlsx"
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
        path = MEAL_ROOT / filename
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
    with connection(clone_path) as conn:
        payables_digest_first = canonical_digest(conn, payables_query)
        payables_rows_first = conn.execute("SELECT COUNT(*) n FROM historical_payable_lines").fetchone()["n"]
    payables_repeat_preview = upload(client, "/api/debts/payables/import/preview", payables_path)
    payables_repeat = confirm(client, "/api/debts/payables/import/confirm", payables_repeat_preview["token"])
    with connection(clone_path) as conn:
        payables_digest_repeat = canonical_digest(conn, payables_query)
        payables_rows_repeat = conn.execute("SELECT COUNT(*) n FROM historical_payable_lines").fetchone()["n"]
    report["steps"].append({
        "name": "historical_payables",
        "file": str(payables_path),
        "preview": preview_summary(payables_preview),
        "confirm_first": payables_first,
        "confirm_repeat": payables_repeat,
        "rows_first": payables_rows_first,
        "rows_repeat": payables_rows_repeat,
        "semantic_idempotent": payables_digest_first == payables_digest_repeat,
    })

    orders_path = INPUTS / "Đơn hàng 29.08.xlsx"
    order_analyze = upload(client, "/api/import/analyze", orders_path)
    candidates = order_analyze.get("sheets") or []
    selected_sheets = [
        item["name"] for item in candidates
        if re.search(r"(?<!\d)29\D*0?8(?!\d)", str(item.get("name") or ""))
    ]
    if not selected_sheets:
        raise RuntimeError(
            "Order workbook has no analyzed sheet matching day 29.08; candidates="
            + json.dumps(candidates, ensure_ascii=False)
        )
    order_first_payload = require_ok(
        client.post("/api/import/confirm", json={
            "token": order_analyze["token"], "sheets": selected_sheets, "work_date": "2026-08-29",
        }),
        "POST /api/import/confirm first",
    )
    first_batch_id = order_first_payload["batch"]["id"]
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
    order_repeat_payload = require_ok(
        client.post("/api/import/confirm", json={
            "token": order_repeat_analyze["token"], "sheets": selected_sheets, "work_date": "2026-08-29",
        }),
        "POST /api/import/confirm repeat",
    )
    second_batch_id = order_repeat_payload["batch"]["id"]
    with connection(clone_path) as conn:
        order_digest_repeat = canonical_digest(conn, order_query)
        batches_repeat = conn.execute(
            "SELECT COUNT(*) n FROM batches WHERE source_name=?", (orders_path.name,),
        ).fetchone()["n"]
        order_rows_repeat = conn.execute(
            """SELECT COUNT(*) n FROM orders o JOIN batches b ON b.id=o.batch_id
               WHERE b.source_name=?""", (orders_path.name,),
        ).fetchone()["n"]

    def order_result(payload: dict) -> dict:
        orders = payload.get("orders") or []
        return {
            "batch_id": (payload.get("batch") or {}).get("id"),
            "batch_status": (payload.get("batch") or {}).get("status"),
            "idempotent": payload.get("idempotent"),
            "import_key": payload.get("importKey"),
            "source_hash": payload.get("sourceHash"),
            "selected_sheets": payload.get("selectedSheets"),
            "orders": len(orders),
            "error_rows": sum(bool(item.get("errors")) for item in orders),
            "warning_rows": sum(bool(item.get("warnings")) for item in orders),
            "summary": payload.get("summary"),
            "skippedSheets": payload.get("skippedSheets"),
        }

    report["steps"].append({
        "name": "orders_2026_08_29",
        "file": str(orders_path),
        "analyzed_candidates": candidates,
        "selected_sheets": selected_sheets,
        "confirm_first": order_result(order_first_payload),
        "confirm_repeat": order_result(order_repeat_payload),
        "first_batch_id": first_batch_id,
        "second_batch_id": second_batch_id,
        "batches_first": batches_first,
        "batches_repeat": batches_repeat,
        "rows_first": order_rows_first,
        "rows_repeat": order_rows_repeat,
        "semantic_idempotent": order_digest_first == order_digest_repeat,
    })

    with connection(clone_path) as conn:
        report["clone_final_counts"] = {
            table: conn.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"]
            for table in (
                "products", "outgoing_product_names", "inventory_transactions", "meal_plans",
                "meal_plan_items", "meal_attendance", "staff", "attendance_entries",
                "payroll_adjustments", "kitchen_labor_costs", "historical_payable_lines",
                "batches", "orders",
            )
        }
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_issues = [list(row) for row in conn.execute("PRAGMA foreign_key_check")]
        report["clone_integrity"] = {
            "integrity_check": integrity,
            "foreign_key_issues": foreign_key_issues,
        }

    report["source_hash_after"] = file_sha256(SOURCE_DB)
    report["source_db_unchanged"] = report["source_hash_after"] == source_hash_before
    report["blocked_steps"] = [
        step["name"] for step in report["steps"] if step.get("blocked") is True
    ]
    report["all_ready_steps_idempotent"] = all(
        step.get("semantic_idempotent") is True
        for step in report["steps"] if step.get("blocked") is not True
    )
    report["all_semantic_idempotent"] = all(
        step.get("semantic_idempotent") is True for step in report["steps"]
    )
    report_path = run_dir / "migration-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"REPORT_PATH={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
