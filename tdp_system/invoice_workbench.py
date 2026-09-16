"""Shared, read-only-first workbench contract for invoice synchronization.

This module owns only batch/filter state. Source-specific fetching, line
mapping, unit conversion and inventory posting stay in focused modules/tasks.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from flask import jsonify, request


INPUT_INVOICE = "INPUT_ELECTRONIC_INVOICE"
OUTPUT_INVOICE = "OUTPUT_ELECTRONIC_INVOICE"
INVOICE_ALIASES = {
    "input": INPUT_INVOICE,
    "output": OUTPUT_INVOICE,
    INPUT_INVOICE: INPUT_INVOICE,
    OUTPUT_INVOICE: OUTPUT_INVOICE,
}
INVOICE_LABELS = {INPUT_INVOICE: "Đầu vào", OUTPUT_INVOICE: "Đầu ra"}
ALLOWED_SOURCES = {"msmi", "minvoice"}
SOURCE_BY_INVOICE_TYPE = {
    INPUT_INVOICE: "msmi",
    OUTPUT_INVOICE: "minvoice",
}
SOURCE_LABELS = {"msmi": "mSMI", "minvoice": "M-Invoice"}
ALLOWED_STATUSES = {
    "prepared",
    "syncing",
    "needs_mapping",
    "ready",
    "posted",
    "partial",
    "error",
    "quarantined",
}

INVOICE_WORKBENCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice_sync_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_key TEXT NOT NULL UNIQUE,
    tenant TEXT NOT NULL DEFAULT 'TDP',
    source TEXT NOT NULL,
    invoice_type TEXT NOT NULL,
    date_from TEXT NOT NULL,
    date_to TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'prepared',
    source_cursor TEXT NOT NULL DEFAULT '',
    source_hash TEXT NOT NULL DEFAULT '',
    fetched_count INTEGER NOT NULL DEFAULT 0,
    needs_mapping_count INTEGER NOT NULL DEFAULT 0,
    unit_review_count INTEGER NOT NULL DEFAULT 0,
    ready_count INTEGER NOT NULL DEFAULT 0,
    posted_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK (invoice_type IN ('INPUT_ELECTRONIC_INVOICE','OUTPUT_ELECTRONIC_INVOICE')),
    CHECK (status IN ('prepared','syncing','needs_mapping','ready','posted','partial','error','quarantined')),
    CHECK (fetched_count >= 0 AND needs_mapping_count >= 0 AND unit_review_count >= 0),
    CHECK (ready_count >= 0 AND posted_count >= 0 AND error_count >= 0)
);
CREATE INDEX IF NOT EXISTS idx_invoice_sync_batches_range
    ON invoice_sync_batches(tenant,invoice_type,date_from,date_to,id DESC);
CREATE INDEX IF NOT EXISTS idx_invoice_sync_batches_status
    ON invoice_sync_batches(status,updated_at DESC);
CREATE TABLE IF NOT EXISTS invoice_sync_batch_invoices (
    batch_id INTEGER NOT NULL REFERENCES invoice_sync_batches(id) ON DELETE CASCADE,
    invoice_id INTEGER NOT NULL REFERENCES msmi_invoices(id) ON DELETE RESTRICT,
    linked_at TEXT NOT NULL,
    PRIMARY KEY(batch_id,invoice_id)
);
CREATE INDEX IF NOT EXISTS idx_invoice_sync_batch_invoices_invoice
    ON invoice_sync_batch_invoices(invoice_id,batch_id);
CREATE TABLE IF NOT EXISTS outgoing_source_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant TEXT NOT NULL,
    source TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    remote_id TEXT NOT NULL DEFAULT '',
    business_key TEXT NOT NULL DEFAULT '',
    buyer_tax_code TEXT NOT NULL DEFAULT '',
    buyer_name TEXT NOT NULL DEFAULT '',
    invoice_number TEXT NOT NULL DEFAULT '',
    invoice_series TEXT NOT NULL DEFAULT '',
    invoice_date TEXT NOT NULL DEFAULT '',
    subtotal REAL NOT NULL DEFAULT 0,
    tax_amount REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL DEFAULT 0,
    source_status_raw TEXT NOT NULL DEFAULT '',
    source_status_class TEXT NOT NULL DEFAULT 'unknown',
    source_status_field TEXT NOT NULL DEFAULT '',
    relation_reference TEXT NOT NULL DEFAULT '',
    sync_status TEXT NOT NULL DEFAULT 'review_required',
    stock_status TEXT NOT NULL DEFAULT 'blocked',
    raw_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT NOT NULL DEFAULT '',
    synced_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(tenant,source,identity_key),
    CHECK(source_status_class IN ('issued','draft','unknown','cancelled','replaced','adjusted')),
    CHECK(sync_status IN ('synced','review_required','reconcile_required')),
    CHECK(stock_status IN ('blocked','pending_mapping','ready','not_inventory','posted','reversal_required','reversed'))
);
CREATE INDEX IF NOT EXISTS idx_outgoing_source_invoices_period
    ON outgoing_source_invoices(tenant,invoice_date,id DESC);
CREATE INDEX IF NOT EXISTS idx_outgoing_source_invoices_status
    ON outgoing_source_invoices(source_status_class,stock_status,id DESC);
CREATE TABLE IF NOT EXISTS outgoing_source_order_scopes (
    invoice_id INTEGER PRIMARY KEY REFERENCES outgoing_source_invoices(id) ON DELETE CASCADE,
    scope TEXT NOT NULL CHECK(scope IN ('orders','outside')),
    contractor TEXT NOT NULL DEFAULT '',
    identity_snapshot TEXT NOT NULL,
    note TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outgoing_source_invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES outgoing_source_invoices(id) ON DELETE CASCADE,
    line_index INTEGER NOT NULL,
    source_item_code TEXT NOT NULL DEFAULT '',
    source_item_name TEXT NOT NULL DEFAULT '',
    source_unit TEXT NOT NULL DEFAULT '',
    qty REAL NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL DEFAULT 0,
    amount REAL NOT NULL DEFAULT 0,
    tax_rate TEXT NOT NULL DEFAULT '',
    source_nature TEXT NOT NULL DEFAULT '',
    inventory_eligible INTEGER NOT NULL DEFAULT 1,
    validation_note TEXT NOT NULL DEFAULT '',
    product_code TEXT NOT NULL DEFAULT '',
    mapping_status TEXT NOT NULL DEFAULT 'unmapped',
    conversion_factor REAL,
    stock_qty REAL NOT NULL DEFAULT 0,
    stock_unit_price REAL NOT NULL DEFAULT 0,
    UNIQUE(invoice_id,line_index),
    CHECK(inventory_eligible IN (0,1)),
    CHECK(mapping_status IN ('unmapped','mapped','unit_review','not_inventory','review'))
);
CREATE TABLE IF NOT EXISTS outgoing_source_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    invoice_id INTEGER NOT NULL REFERENCES outgoing_source_invoices(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    previous_status_class TEXT NOT NULL DEFAULT '',
    current_status_class TEXT NOT NULL,
    relation_reference TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outgoing_source_events_invoice
    ON outgoing_source_events(invoice_id,id DESC);
CREATE TABLE IF NOT EXISTS invoice_sync_batch_output_invoices (
    batch_id INTEGER NOT NULL REFERENCES invoice_sync_batches(id) ON DELETE CASCADE,
    invoice_id INTEGER NOT NULL REFERENCES outgoing_source_invoices(id) ON DELETE RESTRICT,
    linked_at TEXT NOT NULL,
    PRIMARY KEY(batch_id,invoice_id)
);
CREATE INDEX IF NOT EXISTS idx_invoice_sync_batch_output_invoice
    ON invoice_sync_batch_output_invoices(invoice_id,batch_id);
CREATE TABLE IF NOT EXISTS invoice_line_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant TEXT NOT NULL,
    source TEXT NOT NULL,
    invoice_type TEXT NOT NULL,
    partner_key TEXT NOT NULL DEFAULT '',
    scope_key TEXT NOT NULL,
    source_item_code TEXT NOT NULL DEFAULT '',
    source_item_name TEXT NOT NULL DEFAULT '',
    source_unit TEXT NOT NULL DEFAULT '',
    product_code TEXT NOT NULL REFERENCES products(code) ON DELETE RESTRICT,
    target_unit TEXT NOT NULL DEFAULT '',
    mapping_status TEXT NOT NULL,
    conversion_factor REAL,
    effective_from TEXT NOT NULL DEFAULT '',
    effective_to TEXT NOT NULL DEFAULT '',
    confirmed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(tenant,source,invoice_type,partner_key,scope_key,effective_from),
    CHECK(invoice_type IN ('INPUT_ELECTRONIC_INVOICE','OUTPUT_ELECTRONIC_INVOICE')),
    CHECK(mapping_status IN ('confirmed','unit_review')),
    CHECK(conversion_factor IS NULL OR conversion_factor > 0)
);
CREATE INDEX IF NOT EXISTS idx_invoice_line_mappings_target
    ON invoice_line_mappings(product_code,invoice_type,partner_key);
CREATE TABLE IF NOT EXISTS invoice_mapping_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_key TEXT NOT NULL UNIQUE,
    mapping_id INTEGER NOT NULL REFERENCES invoice_line_mappings(id) ON DELETE RESTRICT,
    product_code TEXT NOT NULL,
    source_unit TEXT NOT NULL DEFAULT '',
    target_unit TEXT NOT NULL DEFAULT '',
    conversion_factor REAL NOT NULL,
    effective_from TEXT NOT NULL DEFAULT '',
    effective_to TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    CHECK(conversion_factor > 0)
);
CREATE TABLE IF NOT EXISTS invoice_inventory_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    confirmation_key TEXT NOT NULL UNIQUE,
    direction TEXT NOT NULL,
    source_invoice_table TEXT NOT NULL,
    source_invoice_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    confirmed INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    CHECK(direction IN ('input','output')),
    CHECK(action IN ('post','reversal')),
    CHECK(confirmed=1)
);
CREATE TABLE IF NOT EXISTS invoice_inventory_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    direction TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_invoice_table TEXT NOT NULL,
    source_invoice_id INTEGER NOT NULL,
    source_line_id INTEGER NOT NULL,
    source_line_index INTEGER NOT NULL,
    product_code TEXT NOT NULL REFERENCES products(code) ON DELETE RESTRICT,
    txn_date TEXT NOT NULL,
    qty_delta REAL NOT NULL,
    unit_cost REAL NOT NULL DEFAULT 0,
    mapping_revision_id INTEGER REFERENCES invoice_mapping_revisions(id) ON DELETE RESTRICT,
    confirmation_id INTEGER NOT NULL REFERENCES invoice_inventory_confirmations(id) ON DELETE RESTRICT,
    reverses_event_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'posted',
    created_at TEXT NOT NULL,
    CHECK(direction IN ('input','output')),
    CHECK(event_type IN ('POST','REVERSAL')),
    CHECK(status='posted'),
    CHECK(qty_delta != 0),
    UNIQUE(event_type,source_invoice_table,source_invoice_id,source_line_id)
);
CREATE INDEX IF NOT EXISTS idx_invoice_inventory_ledger_product_date
    ON invoice_inventory_ledger(product_code,txn_date,id);
CREATE INDEX IF NOT EXISTS idx_invoice_inventory_ledger_source
    ON invoice_inventory_ledger(source_invoice_table,source_invoice_id,event_type);
"""


class InvoiceWorkbenchError(ValueError):
    """A validation error safe to return to the local UI."""


def init_invoice_workbench_schema(conn) -> None:
    conn.executescript(INVOICE_WORKBENCH_SCHEMA)
    try:
        from .output_stock_remap import init_schema as init_remap_schema
    except ImportError:
        from output_stock_remap import init_schema as init_remap_schema
    init_remap_schema(conn)
    try:
        from invoice_line_groups import SCHEMA
    except ImportError:
        from .invoice_line_groups import SCHEMA
    conn.executescript(SCHEMA)
    try:
        from .invoice_expenses import SCHEMA as EXPENSE_SCHEMA
    except ImportError:
        from invoice_expenses import SCHEMA as EXPENSE_SCHEMA
    conn.executescript(EXPENSE_SCHEMA)
    # Input invoice tables predate the shared workbench. Add conversion
    # snapshots in place without rebuilding or touching existing source rows.
    for table in ("msmi_invoice_items", "outgoing_source_invoice_items"):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not columns:
            continue
        for name, declaration in (
            ("conversion_factor", "REAL"),
            ("stock_qty", "REAL NOT NULL DEFAULT 0"),
            ("stock_unit_price", "REAL NOT NULL DEFAULT 0"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def normalize_invoice_type(value: Any) -> str:
    normalized = str(value or "").strip()
    invoice_type = INVOICE_ALIASES.get(normalized)
    if invoice_type is None:
        raise InvoiceWorkbenchError("Loại hóa đơn chỉ nhận đầu vào hoặc đầu ra")
    return invoice_type


def normalize_source(value: Any) -> str:
    source = str(value or "msmi").strip().casefold()
    if source not in ALLOWED_SOURCES:
        raise InvoiceWorkbenchError("Nguồn hóa đơn chưa được cấu hình an toàn")
    return source


def validate_date_range(date_from: Any, date_to: Any) -> tuple[str, str]:
    start_text = str(date_from or "").strip()
    end_text = str(date_to or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_text) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", end_text
    ):
        raise InvoiceWorkbenchError("Cần chọn đủ Từ ngày và Đến ngày theo định dạng YYYY-MM-DD")
    try:
        start = datetime.strptime(start_text, "%Y-%m-%d").date()
        end = datetime.strptime(end_text, "%Y-%m-%d").date()
    except ValueError as error:
        raise InvoiceWorkbenchError("Khoảng ngày hóa đơn không hợp lệ") from error
    if start > end:
        raise InvoiceWorkbenchError("Từ ngày không được lớn hơn Đến ngày")
    return start.isoformat(), end.isoformat()


def batch_request_key(tenant: str, source: str, invoice_type: str, date_from: str, date_to: str) -> str:
    canonical = "\n".join((tenant.strip(), source, invoice_type, date_from, date_to))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _batch_dict(row) -> dict[str, Any]:
    item = dict(row)
    # Stable source anchors are operational cursor state. They may contain a
    # remote invoice identifier, so keep them server-side instead of exposing
    # them in the workbench response.
    item.pop("source_cursor", None)
    item["direction"] = "input" if item["invoice_type"] == INPUT_INVOICE else "output"
    item["direction_label"] = INVOICE_LABELS[item["invoice_type"]]
    item["source_label"] = SOURCE_LABELS.get(item["source"], item["source"])
    item["read_only_source"] = True
    item["archived"] = item["source"] == "minvoice_test_0106026495_999"
    return item


def prepare_sync_batch(
    conn,
    *,
    tenant: str,
    source: Any,
    invoice_type: Any,
    date_from: Any,
    date_to: Any,
    now_iso,
    audit_event=None,
) -> tuple[dict[str, Any], bool]:
    safe_tenant = str(tenant or "TDP").strip() or "TDP"
    safe_type = normalize_invoice_type(invoice_type)
    requested_source = normalize_source(source)
    expected_source = SOURCE_BY_INVOICE_TYPE[safe_type]
    # Earlier local builds sent `msmi` for both directions. Canonicalize that
    # one legacy output request to M-Invoice so an old cached page can never
    # route output invoices back through the wrong connector.
    if requested_source == "msmi" and safe_type == OUTPUT_INVOICE:
        safe_source = expected_source
    elif requested_source != expected_source:
        raise InvoiceWorkbenchError(
            "Hóa đơn đầu vào dùng mSMI; hóa đơn đầu ra dùng M-Invoice"
        )
    else:
        safe_source = requested_source
    safe_from, safe_to = validate_date_range(date_from, date_to)
    request_key = batch_request_key(safe_tenant, safe_source, safe_type, safe_from, safe_to)
    timestamp = now_iso()
    cursor = conn.execute(
        """INSERT OR IGNORE INTO invoice_sync_batches(
               request_key,tenant,source,invoice_type,date_from,date_to,status,created_at,updated_at
           ) VALUES(?,?,?,?,?,?,'prepared',?,?)""",
        (request_key, safe_tenant, safe_source, safe_type, safe_from, safe_to, timestamp, timestamp),
    )
    created = cursor.rowcount == 1
    row = conn.execute(
        "SELECT * FROM invoice_sync_batches WHERE request_key=?", (request_key,)
    ).fetchone()
    if row is None:  # pragma: no cover - SQLite invariant
        raise InvoiceWorkbenchError("Không tạo được phiên tải hóa đơn")
    if created and audit_event is not None:
        audit_event(
            conn,
            "invoice_sync.prepare",
            entity_type="invoice_sync_batch",
            entity_id=str(row["id"]),
            metadata={
                "source": safe_source,
                "invoice_type": safe_type,
                "date_from": safe_from,
                "date_to": safe_to,
                "request_key": request_key,
            },
        )
    return _batch_dict(row), created


def _automatic_input_status(conn, tenant):
    try:
        from .automatic_input_sync import status
    except ImportError:
        from automatic_input_sync import status
    return status(conn, tenant)


def list_sync_batches(
    conn,
    *,
    tenant: str,
    invoice_type: Any,
    date_from: Any,
    date_to: Any,
    status: Any = "all",
    limit: int = 50,
) -> dict[str, Any]:
    safe_type = normalize_invoice_type(invoice_type)
    safe_from, safe_to = validate_date_range(date_from, date_to)
    safe_status = str(status or "all").strip().casefold()
    if safe_status != "all" and safe_status not in ALLOWED_STATUSES:
        raise InvoiceWorkbenchError("Trạng thái lọc hóa đơn không hợp lệ")
    safe_limit = max(1, min(int(limit), 200))
    parameters: list[Any] = [str(tenant or "TDP").strip() or "TDP", safe_type, safe_to, safe_from]
    status_sql = ""
    if safe_status != "all":
        status_sql = " AND status=?"
        parameters.append(safe_status)
    parameters.append(safe_limit)
    rows = conn.execute(
        """SELECT * FROM invoice_sync_batches
           WHERE tenant=? AND invoice_type=? AND date_from<=? AND date_to>=?"""
        + status_sql
        + " ORDER BY id DESC LIMIT ?",
        parameters,
    ).fetchall()
    counts = {name: 0 for name in sorted(ALLOWED_STATUSES)}
    count_rows = conn.execute(
        """SELECT status,COUNT(*) count FROM invoice_sync_batches
           WHERE tenant=? AND invoice_type=? AND date_from<=? AND date_to>=?
           GROUP BY status""",
        parameters[:4],
    ).fetchall()
    for row in count_rows:
        counts[row["status"]] = row["count"]
    # Undated source stubs cannot pass any date filter. Keep their count
    # visible without pretending they belong to the selected period.
    undated_source_count = 0
    if safe_type == INPUT_INVOICE and conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='msmi_invoices'"
    ).fetchone():
        undated_source_count = conn.execute(
            """SELECT COUNT(*) FROM msmi_invoices WHERE tenant=? AND invoice_type=?
               AND COALESCE(invoice_date,'')='' AND sync_status='review_required'""",
            (parameters[0], INPUT_INVOICE),
        ).fetchone()[0]
    return {
        "undated_source_count": undated_source_count,
        "automatic_input_sync": _automatic_input_status(conn, parameters[0]) if safe_type == INPUT_INVOICE else None,
        "filters": {
            "invoice_type": safe_type,
            "direction": "input" if safe_type == INPUT_INVOICE else "output",
            "date_from": safe_from,
            "date_to": safe_to,
            "status": safe_status,
        },
        "supported_directions": [
            {
                "value": "input", "invoice_type": INPUT_INVOICE,
                "label": "Đầu vào", "source": "msmi", "source_label": "mSMI",
            },
            {
                "value": "output", "invoice_type": OUTPUT_INVOICE,
                "label": "Đầu ra", "source": "minvoice", "source_label": "M-Invoice",
            },
        ],
        "supported_statuses": ["all", *sorted(ALLOWED_STATUSES)],
        "counts": counts,
        "batches": [_batch_dict(row) for row in rows],
        "read_only_source": True,
    }


def register_invoice_workbench_routes(app, ctx) -> None:
    try:
        from invoice_line_groups import register_group_routes
    except ImportError:
        from .invoice_line_groups import register_group_routes
    register_group_routes(app,ctx)
    try:
        from .invoice_expenses import register_expense_routes
    except ImportError:
        from invoice_expenses import register_expense_routes
    register_expense_routes(app,ctx)
    try:
        from .invoice_output_adjustments import register_adjustment_routes
    except ImportError:
        from invoice_output_adjustments import register_adjustment_routes
    register_adjustment_routes(app,ctx)
    try:
        from .invoice_amount_support import register_amount_support_routes
    except ImportError:
        from invoice_amount_support import register_amount_support_routes
    register_amount_support_routes(app, ctx)
    db_factory = ctx["db"]
    now_iso = ctx["now_iso"]
    setting_get = ctx["setting_get"]
    audit_event = ctx.get("audit_event")
    create_msmi_client = ctx.get("create_msmi_client")
    create_minvoice_client = ctx.get("create_minvoice_client")

    @app.get("/api/invoice-workbench/output-archive")
    def api_output_archive():
        try:
            from .minvoice_account_archive import archive_html
        except ImportError:
            from minvoice_account_archive import archive_html
        with db_factory() as conn:
            return archive_html(conn), 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}

    def persist_sync_error(batch_id: int, error_code: str) -> None:
        """Persist only a count/code after the failed sync transaction rolls back.

        Source exceptions intentionally escape the database context so all
        partially imported invoices are rolled back.  That rollback would
        otherwise also erase the safe batch error marker written by the sync
        adapter.  Re-open a short transaction and store no remote payload,
        exception text, token or customer data.
        """
        try:
            with db_factory() as error_conn:
                timestamp = now_iso()
                error_conn.execute(
                    """UPDATE invoice_sync_batches
                       SET status='error',error_count=1,error_code=?,updated_at=?,completed_at=NULL
                       WHERE id=?""",
                    (error_code, timestamp, int(batch_id)),
                )
                batch_row = error_conn.execute(
                    "SELECT invoice_type,source FROM invoice_sync_batches WHERE id=?",
                    (int(batch_id),),
                ).fetchone()
                has_audit_log = error_conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
                ).fetchone()
                if batch_row is not None and has_audit_log:
                    direction = (
                        "input" if batch_row["invoice_type"] == INPUT_INVOICE else "output"
                    )
                    metadata = json.dumps(
                        {
                            "error_code": error_code,
                            "invoice_type": batch_row["invoice_type"],
                            "source": batch_row["source"],
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    error_conn.execute(
                        """INSERT INTO audit_log(
                               event_type,entity_type,entity_id,status,message,metadata_json,created_at
                           ) VALUES(?,'invoice_sync_batch',?,'error','',?,?)""",
                        (
                            f"invoice_{direction}.sync",
                            str(int(batch_id)),
                            metadata,
                            timestamp,
                        ),
                    )
        except Exception:
            # Never mask the original connector/validation response merely
            # because the diagnostic marker could not be stored.
            return

    def tenant_code(conn) -> str:
        return str(setting_get(conn, "tenant_code", "TDP") or "TDP")

    @app.route("/api/invoice-workbench/input-receipts", methods=["GET", "POST"])
    def api_input_receipts():
        try:
            from .invoice_receipt_bulk import preview_receipts, post_receipts, InvoiceReceiptError
            from .invoice_workbench_listing import invoice_range_payload
        except ImportError:
            from invoice_receipt_bulk import preview_receipts, post_receipts, InvoiceReceiptError
            from invoice_workbench_listing import invoice_range_payload
        try:
            with db_factory() as conn:
                if request.method == 'POST':
                    conn.execute('BEGIN IMMEDIATE')
                    body = request.get_json(silent=True)
                    result = post_receipts(conn, body.get('items') if isinstance(body, dict) else None, tenant_code(conn), now_iso)
                else:
                    conn.execute('BEGIN')
                    payload = invoice_range_payload(conn, tenant=tenant_code(conn), invoice_type='input',
                        date_from=request.args.get('from'), date_to=request.args.get('to'),
                        status=request.args.get('status', 'all'), line_filter=request.args.get('line_filter', 'all'),
                        scope=request.args.get('scope', 'period'))
                    wanted = request.args.get('id', type=int)
                    ids = [r['id'] for r in payload['items'] if r['workbench_status'] == 'ready' and (wanted is None or r['id'] == wanted)]
                    result = preview_receipts(conn, ids, tenant_code(conn), now_iso) if ids else {'items': [], 'blocked': []}
                    result['blocked'].extend({'id': r['id'], 'number': r['invoice_series'] + ' / ' + r['invoice_number'],
                        'reason': r.get('error_message') or ('Cần xác nhận lại phân loại chi phí do nguồn đã thay đổi.' if r.get('expense_review_count') else 'Còn dòng chưa đủ mã hoặc hệ số quy đổi.' if r['workbench_status'] == 'needs_mapping' else 'Cần kiểm tra hóa đơn trước khi nhập kho.')}
                        for r in payload['items'] if r['workbench_status'] in {'needs_mapping', 'error'}
                        and r.get('receipt_status') != 'posted' and (wanted is None or r['id'] == wanted))
                return jsonify({'ok': True, **result})
        except (InvoiceReceiptError, InvoiceWorkbenchError) as error:
            return jsonify({'ok': False, 'error': str(error), 'code': getattr(error, 'code', 'invalid')}), getattr(error, 'status', 400)

    @app.route("/api/invoice-workbench/output-postings", methods=["GET", "POST"])
    def api_output_postings():
        try:
            from .invoice_output_bulk import preview_outputs, post_outputs, InvoiceInventoryError
            from .invoice_workbench_listing import invoice_range_payload
        except ImportError:
            from invoice_output_bulk import preview_outputs, post_outputs, InvoiceInventoryError
            from invoice_workbench_listing import invoice_range_payload
        try:
            with db_factory() as conn:
                if request.method == 'POST':
                    body = request.get_json(silent=True)
                    body = body if isinstance(body, dict) else {}
                    conn.execute('BEGIN IMMEDIATE')
                    result = post_outputs(conn, body.get('items'), tenant_code(conn), now_iso, confirmed=body.get('confirmed'))
                else:
                    conn.execute('BEGIN')
                    payload = invoice_range_payload(conn, tenant=tenant_code(conn), invoice_type='output',
                        date_from=request.args.get('from'), date_to=request.args.get('to'),
                        status=request.args.get('status', 'all'), line_filter=request.args.get('line_filter', 'all'),
                        scope=request.args.get('scope', 'period'))
                    ids = [r['id'] for r in payload['items'] if r['workbench_status'] == 'ready']
                    result = preview_outputs(conn, ids, tenant_code(conn), now_iso) if ids else {'items': [], 'blocked': []}
                    result['blocked'].extend({'id': r['id'], 'number': r['invoice_series'] + ' / ' + r['invoice_number'],
                        'reason': r.get('error_message') or ('Còn dòng chưa đủ mã hoặc khác đơn vị kho.' if r['workbench_status'] == 'needs_mapping' else 'Cần đối chiếu hóa đơn nguồn trước khi ghi xuất kho.')}
                        for r in payload['items'] if r['workbench_status'] in {'needs_mapping', 'error'} and r.get('stock_status') not in {'posted', 'reversal_required'})
                return jsonify({'ok': True, **result})
        except (InvoiceInventoryError, InvoiceWorkbenchError) as error:
            return jsonify({'ok': False, 'error': str(error), 'code': getattr(error, 'code', 'invalid')}), getattr(error, 'status', 400)

    @app.post("/api/invoice-workbench/output-match-codes")
    def api_output_match_codes():
        try:
            from .invoice_output_mapping import match_output_catalog_codes
            from .invoice_mapping import InvoiceMappingError
        except ImportError:
            from invoice_output_mapping import match_output_catalog_codes
            from invoice_mapping import InvoiceMappingError
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "Dữ liệu yêu cầu không hợp lệ"}), 400
        try:
            start, end = validate_date_range(body.get("from"), body.get("to"))
            with db_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                result = match_output_catalog_codes(conn, tenant=tenant_code(conn),
                    date_from=start, date_to=end, now_iso=now_iso)
            return jsonify({"ok": True, **result})
        except (InvoiceWorkbenchError, InvoiceMappingError) as error:
            return jsonify({"ok": False, "error": str(error)}), getattr(error, "status", 400)

    @app.get("/api/invoice-workbench/invoices")
    @app.get("/api/invoice-workbench/invoices/export")
    @app.get("/api/invoice-workbench/output-register/export")
    def api_invoice_range_rows():
        from flask import send_file
        try:
            from invoice_workbench_listing import invoice_range_payload, range_workbook
        except ImportError:
            from .invoice_workbench_listing import invoice_range_payload, range_workbook
        try:
            full_output = request.path == '/api/invoice-workbench/output-register/export'
            with db_factory() as conn:
                if not conn.in_transaction:
                    # One read snapshot for invoice headers, detail rows and
                    # totals while another user may be syncing or mapping.
                    conn.execute("BEGIN")
                payload = invoice_range_payload(
                    conn, tenant=tenant_code(conn), invoice_type='output' if full_output else request.args.get("invoice_type", "input"),
                    date_from=request.args.get("from"), date_to=request.args.get("to"),
                    status='all' if full_output else request.args.get("status", "all"), line_filter='all' if full_output else request.args.get("line_filter", "all"),
                    scope='period' if full_output else request.args.get("scope", "period"),
                )
            if full_output:
                try:
                    from .invoice_output_register import output_sales_workbook
                except ImportError:
                    from invoice_output_register import output_sales_workbook
                return send_file(output_sales_workbook(payload), as_attachment=True,
                                 download_name=f"Dau_ra_M-Invoice_{payload['date_from']}_{payload['date_to']}.xlsx",
                                 mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            if request.path.endswith("/export"):
                return send_file(range_workbook(payload), as_attachment=True,
                                 download_name=f"Hoa_don_{payload['direction']}_{payload['date_from']}_{payload['date_to']}.xlsx",
                                 mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            return jsonify({"ok": True, **payload})
        except InvoiceWorkbenchError as error:
            return jsonify({"ok": False, "error": str(error)}), 400

    @app.get("/api/invoice-workbench")
    def api_invoice_workbench():
        try:
            with db_factory() as conn:
                payload = list_sync_batches(
                    conn,
                    tenant=tenant_code(conn),
                    invoice_type=request.args.get("invoice_type", "input"),
                    date_from=request.args.get("from"),
                    date_to=request.args.get("to"),
                    status=request.args.get("status", "all"),
                    limit=request.args.get("limit", 50, type=int),
                )
                return jsonify({"ok": True, **payload})
        except InvoiceWorkbenchError as error:
            return jsonify({"ok": False, "error": str(error)}), 400

    @app.post("/api/invoice-workbench/batches")
    def api_prepare_invoice_sync_batch():
        body = request.get_json(silent=True) or {}
        try:
            with db_factory() as conn:
                batch, created = prepare_sync_batch(
                    conn,
                    tenant=tenant_code(conn),
                    source=body.get("source") or (
                        "minvoice" if normalize_invoice_type(body.get("invoice_type")) == OUTPUT_INVOICE
                        else "msmi"
                    ),
                    invoice_type=body.get("invoice_type"),
                    date_from=body.get("date_from"),
                    date_to=body.get("date_to"),
                    now_iso=now_iso,
                    audit_event=audit_event,
                )
                return jsonify({"ok": True, "created": created, "batch": batch})
        except InvoiceWorkbenchError as error:
            return jsonify({"ok": False, "error": str(error)}), 400

    @app.post("/api/invoice-workbench/batches/<int:batch_id>/sync")
    def api_sync_invoice_batch(batch_id: int):
        # Import lazily to keep this shared workbench module independently
        # testable without loading the source-specific connector stack.
        try:
            from invoice_input_sync import InvoiceInputSyncError, MsmiError, sync_input_batch
            from invoice_output_sync import InvoiceOutputSyncError, sync_output_batch
            from minvoice_client import MinvoiceError
        except ImportError:  # pragma: no cover - package invocation
            from .invoice_input_sync import InvoiceInputSyncError, MsmiError, sync_input_batch
            from .invoice_output_sync import InvoiceOutputSyncError, sync_output_batch
            from .minvoice_client import MinvoiceError
        body = request.get_json(silent=True) or {}
        batch = None
        try:
            with db_factory() as conn:
                # Take the SQLite write lock before reading the cursor so two
                # clicks cannot resume the same batch from stale state.
                conn.execute("BEGIN IMMEDIATE")
                batch = conn.execute(
                    "SELECT invoice_type,source FROM invoice_sync_batches WHERE id=?", (batch_id,)
                ).fetchone()
                if batch is None:
                    raise InvoiceWorkbenchError("Không tìm thấy phiên tải hóa đơn")
                common = {
                    "max_pages": body.get("max_pages", 5),
                    "page_size": body.get("page_size", 199),
                }
                if batch["invoice_type"] == INPUT_INVOICE:
                    if batch["source"] != "msmi" or create_msmi_client is None:
                        raise InvoiceWorkbenchError("Connector mSMI đầu vào chưa được cấu hình")
                    result = sync_input_batch(
                        conn, create_msmi_client(), batch_id, now_iso, **common
                    )
                    try:
                        from automatic_invoice_mapping import apply_automatic_input_mappings
                    except ImportError:
                        from .automatic_invoice_mapping import apply_automatic_input_mappings
                    scope = conn.execute("SELECT tenant,date_from,date_to FROM invoice_sync_batches WHERE id=?", (batch_id,)).fetchone()
                    result["automatic_mapping"] = apply_automatic_input_mappings(
                        conn, tenant=scope["tenant"], date_from=scope["date_from"],
                        date_to=scope["date_to"], now_iso=now_iso,
                    )
                    updated = conn.execute("SELECT status,needs_mapping_count,ready_count,posted_count,error_count FROM invoice_sync_batches WHERE id=?", (batch_id,)).fetchone()
                    result.update(dict(updated))
                else:
                    if batch["source"] != "minvoice" or create_minvoice_client is None:
                        raise InvoiceWorkbenchError("Connector M-Invoice đầu ra chưa được cấu hình")
                    result = sync_output_batch(
                        conn,
                        create_minvoice_client(),
                        batch_id,
                        now_iso,
                        **common,
                    )
                return jsonify({"ok": True, **result})
        except (InvoiceWorkbenchError, InvoiceInputSyncError, InvoiceOutputSyncError) as error:
            persist_sync_error(batch_id, "sync_validation_error")
            return jsonify({"ok": False, "error": str(error), "read_only": True}), 400
        except (MsmiError, MinvoiceError) as error:
            persist_sync_error(
                batch_id,
                # Output normalization reuses strict numeric/date helpers that
                # raise MsmiError. Classify by the batch connector, not the
                # helper exception class, so an M-Invoice payload can never be
                # mislabeled as an mSMI source failure.
                "minvoice_source_error"
                if batch is not None and batch["source"] == "minvoice"
                else "msmi_source_error",
            )
            return jsonify({"ok": False, "error": str(error), "read_only": True}), 502
        except (TypeError, ValueError):
            persist_sync_error(batch_id, "invalid_sync_limits")
            return jsonify({
                "ok": False,
                "error": "Giới hạn trang đồng bộ không hợp lệ",
                "read_only": True,
            }), 400
        except Exception:
            persist_sync_error(batch_id, "sync_failed")
            return jsonify({
                "ok": False,
                "error": "Không đồng bộ được hóa đơn; phiên đã được hoàn tác an toàn",
                "read_only": True,
            }), 502

    @app.get("/api/invoice-workbench/batches/<int:batch_id>/invoices")
    def api_invoice_batch_rows(batch_id: int):
        try:
            from invoice_input_sync import InvoiceInputSyncError, input_invoice_payload
            from invoice_output_sync import InvoiceOutputSyncError, output_invoice_payload
        except ImportError:  # pragma: no cover - package invocation
            from .invoice_input_sync import InvoiceInputSyncError, input_invoice_payload
            from .invoice_output_sync import InvoiceOutputSyncError, output_invoice_payload
        try:
            with db_factory() as conn:
                batch = conn.execute(
                    "SELECT invoice_type FROM invoice_sync_batches WHERE id=?", (batch_id,)
                ).fetchone()
                if batch is None:
                    raise InvoiceWorkbenchError("Không tìm thấy phiên tải hóa đơn")
                payload = (
                    input_invoice_payload(conn, batch_id)
                    if batch["invoice_type"] == INPUT_INVOICE
                    else output_invoice_payload(conn, batch_id)
                )
                return jsonify({"ok": True, **payload})
        except (InvoiceWorkbenchError, InvoiceInputSyncError, InvoiceOutputSyncError) as error:
            return jsonify({"ok": False, "error": str(error)}), 404
