"""Date-bounded, read-only mSMI ingestion for input-invoice workbench batches."""

from __future__ import annotations

import hashlib
import json
from typing import Any

try:
    from contract_modules import (
        MsmiError,
        as_date,
        first_value,
        mapping_key,
        normalize_invoice,
        product_name_candidates,
        quarantine_msmi_invoice,
        upsert_msmi_invoice,
    )
except ImportError:  # pragma: no cover - package invocation
    from .contract_modules import (
        MsmiError,
        as_date,
        first_value,
        mapping_key,
        normalize_invoice,
        product_name_candidates,
        quarantine_msmi_invoice,
        upsert_msmi_invoice,
    )

try:
    from invoice_mapping import apply_saved_mappings
except ImportError:  # pragma: no cover - package invocation
    from .invoice_mapping import apply_saved_mappings


INPUT_INVOICE = "INPUT_ELECTRONIC_INVOICE"


class InvoiceInputSyncError(ValueError):
    """A safe local validation/state error for an input sync batch."""


def input_invoice_payload(conn, batch_id: int | None = None, *, invoice_ids=None) -> dict[str, Any]:
    """Return only the sanitized mSMI invoices linked to one bounded batch."""
    safe_batch_id = None
    if invoice_ids is None:
        try:
            safe_batch_id = int(batch_id)
        except (TypeError, ValueError):
            raise InvoiceInputSyncError("Mã phiên tải hóa đơn không hợp lệ") from None
        batch = conn.execute(
            "SELECT source,invoice_type FROM invoice_sync_batches WHERE id=?", (safe_batch_id,)
        ).fetchone()
        if batch is None or batch["source"] != "msmi" or batch["invoice_type"] != INPUT_INVOICE:
            raise InvoiceInputSyncError("Không tìm thấy phiên hóa đơn đầu vào mSMI")
        invoice_ids = [row[0] for row in conn.execute(
            "SELECT invoice_id FROM invoice_sync_batch_invoices WHERE batch_id=?", (safe_batch_id,)
        )]
    invoices = [dict(row) for row in conn.execute(
        """SELECT i.id,i.invoice_type,i.seller_tax_code,i.seller_name,
                  i.invoice_number,i.invoice_series,i.invoice_date,i.subtotal,i.tax_amount,
                  i.total_amount,i.sync_status,i.receipt_status,i.error_message,i.synced_at,
                  COUNT(li.id) item_count,
                  SUM(CASE WHEN li.inventory_eligible=1 THEN 1 ELSE 0 END) inventory_item_count,
                  SUM(CASE WHEN li.inventory_eligible=1 AND li.mapping_status='mapped' THEN 1 ELSE 0 END) mapped_count
             FROM msmi_invoices i
             LEFT JOIN msmi_invoice_items li ON li.invoice_id=i.id
            WHERE i.id IN (SELECT value FROM json_each(?))
            GROUP BY i.id ORDER BY i.invoice_date DESC,i.id DESC""",
        (json.dumps([int(value) for value in invoice_ids]),),
    )]
    candidates = product_name_candidates(conn)
    suggestions = {key: rows[0] for key, rows in candidates.items() if len(rows) == 1}
    for invoice in invoices:
        invoice["mapped_count"] = int(invoice["mapped_count"] or 0)
        invoice["inventory_item_count"] = int(invoice["inventory_item_count"] or 0)
        invoice["items"] = [dict(row) for row in conn.execute(
            """SELECT li.id,li.line_index,li.source_item_code,li.source_item_name,li.source_unit,
                      li.qty,li.unit_price,li.amount,li.tax_rate,li.source_nature,
                      li.inventory_eligible,li.validation_note,li.product_code,li.mapping_status,
                      li.conversion_factor,li.stock_qty,li.stock_unit_price,
                      p.name product_name,p.unit product_unit
                 FROM msmi_invoice_items li LEFT JOIN products p ON p.code=li.product_code
                WHERE li.invoice_id=? ORDER BY li.line_index""",
            (invoice["id"],),
        )]
        for line in invoice["items"]:
            line["suggested_product_code"] = ""
            line["suggested_product_name"] = ""
            line["candidate_products"] = []
            if line["inventory_eligible"] and line["mapping_status"] != "mapped":
                name_key = mapping_key(line["source_item_name"])
                line["candidate_products"] = candidates.get(name_key, [])[:20]
                suggestion = suggestions.get(name_key)
                if suggestion:
                    line["suggested_product_code"] = suggestion["code"]
                    line["suggested_product_name"] = suggestion["name"]
        try:
            from .invoice_expenses import annotate_expenses
        except ImportError:
            from invoice_expenses import annotate_expenses
        annotate_expenses(conn,invoice)
        try:
            from .invoice_input_integrity import receipt_cost_warning
        except ImportError:
            from invoice_input_integrity import receipt_cost_warning
        invoice['cost_warning'] = receipt_cost_warning(conn, invoice['id'], invoice['items'])
    return {
        "batch_id": safe_batch_id,
        "invoice_type": INPUT_INVOICE,
        "source": "msmi",
        "items": invoices,
        "read_only": True,
    }


def _safe_cursor(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(str(raw or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _audit(conn, now_iso, status: str, *, batch_id: int, metadata: dict[str, Any]) -> None:
    """Write count-only evidence; source bodies and remote IDs are forbidden."""
    tables = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
        )
    }
    if "audit_log" not in tables:
        return
    conn.execute(
        """INSERT INTO audit_log(
               event_type,entity_type,entity_id,status,message,metadata_json,created_at
           ) VALUES('invoice_input.sync','invoice_sync_batch',?,?,?,?,?)""",
        (
            str(batch_id),
            status,
            "",
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            now_iso(),
        ),
    )


def _batch_counts(conn, batch_id: int) -> dict[str, int]:
    row = conn.execute(
        """SELECT COUNT(*) fetched_count,
                  COALESCE(SUM(CASE WHEN i.receipt_status='pending_mapping' THEN 1 ELSE 0 END),0)
                      needs_mapping_count,
                  COALESCE(SUM(CASE WHEN i.receipt_status='ready' THEN 1 ELSE 0 END),0)
                      ready_count,
                  COALESCE(SUM(CASE WHEN i.receipt_status='posted' THEN 1 ELSE 0 END),0)
                      posted_count,
                  COALESCE(SUM(CASE WHEN i.sync_status='review_required'
                                      OR i.receipt_status='blocked' THEN 1 ELSE 0 END),0)
                      error_count
           FROM invoice_sync_batch_invoices bi
           JOIN msmi_invoices i ON i.id=bi.invoice_id
           WHERE bi.batch_id=?""",
        (batch_id,),
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def _batch_source_hash(conn, batch_id: int) -> str:
    digest = hashlib.sha256()
    for row in conn.execute(
        """SELECT i.invoice_type,i.remote_id
           FROM invoice_sync_batch_invoices bi
           JOIN msmi_invoices i ON i.id=bi.invoice_id
           WHERE bi.batch_id=? ORDER BY i.invoice_type,i.remote_id""",
        (batch_id,),
    ):
        digest.update(str(row["invoice_type"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(row["remote_id"]).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def sync_input_batch(
    conn,
    client,
    batch_id: int,
    now_iso,
    *,
    max_pages: int = 5,
    page_size: int = 199,
) -> dict[str, Any]:
    """Fetch one fixed input-invoice range atomically and resume by stable ID.

    Page numbers are not durable cursors because newly arriving documents move
    older rows to later pages. The batch stores the oldest processed remote ID;
    a retry relocates that ID from page zero before advancing. Every remote call
    receives both inclusive date bounds.
    """
    try:
        safe_batch_id = int(batch_id)
    except (TypeError, ValueError):
        raise InvoiceInputSyncError("Mã phiên tải hóa đơn không hợp lệ") from None
    batch = conn.execute(
        "SELECT * FROM invoice_sync_batches WHERE id=?", (safe_batch_id,)
    ).fetchone()
    if batch is None:
        raise InvoiceInputSyncError("Không tìm thấy phiên tải hóa đơn")
    if batch["source"] != "msmi" or batch["invoice_type"] != INPUT_INVOICE:
        raise InvoiceInputSyncError("Phiên này không phải hóa đơn đầu vào mSMI")

    page_limit = max(1, min(int(max_pages), 50))
    safe_page_size = max(1, min(int(page_size), 200))
    date_from = str(batch["date_from"])
    date_to = str(batch["date_to"])
    tenant = str(batch["tenant"])
    cursor = _safe_cursor(batch["source_cursor"])
    anchor_id = str(cursor.get("anchor_remote_id") or "")
    anchor_date = str(cursor.get("anchor_date") or "")
    complete = bool(cursor.get("complete", False))
    reconcile_page = max(int(cursor.get("reconcile_next_page") or 1), 1)

    new_count = 0
    known_count = 0
    item_count = 0
    review_count = 0
    skipped_out_of_range = 0
    pages = 0
    progress_pages = 0
    savepoint = "invoice_input_batch_sync"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            "UPDATE invoice_sync_batches SET status='syncing',error_code='',updated_at=? WHERE id=?",
            (now_iso(), safe_batch_id),
        )

        def consume(remote: dict) -> dict[str, Any]:
            nonlocal new_count, known_count, item_count, review_count, skipped_out_of_range
            timestamp = now_iso()
            quarantined = False
            # Check the two cursor fields before validating money/items. Some
            # production mSMI tenants ignore the requested date parameters and
            # can return malformed invoices from another month. Those records
            # must neither be stored nor quarantined into the selected batch.
            remote_id = str(first_value(remote, "_id", "id", "invoiceId", default="")).strip()
            remote_invoice_date = as_date(
                first_value(remote, "tdlap", "nlap", "invoiceDate", "signedDate")
            )
            if remote_id and remote_invoice_date and not date_from <= remote_invoice_date <= date_to:
                skipped_out_of_range += 1
                return {
                    "remote_id": remote_id,
                    "invoice_date": remote_invoice_date,
                }
            try:
                normalized = normalize_invoice(remote, INPUT_INVOICE, timestamp)
                if not date_from <= normalized["invoice_date"] <= date_to:
                    # Production mSMI currently accepts the documented date
                    # parameters but can still return its unbounded newest
                    # page. Keep paging with the raw stable-ID cursor while
                    # refusing to persist or link any document outside this
                    # batch. This preserves the date boundary without making
                    # an older month impossible to download.
                    skipped_out_of_range += 1
                    return normalized
                invoice_id, created = upsert_msmi_invoice(
                    conn, remote, INPUT_INVOICE, tenant, timestamp
                )
            except InvoiceInputSyncError:
                raise
            except MsmiError as error:
                invoice_id, created, normalized = quarantine_msmi_invoice(
                    conn, remote, INPUT_INVOICE, tenant, timestamp, error
                )
                review_count += 1
                quarantined = True
            if not quarantined:
                apply_saved_mappings(conn, "input", invoice_id)
            conn.execute(
                """INSERT INTO invoice_sync_batch_invoices(batch_id,invoice_id,linked_at)
                   VALUES(?,?,?) ON CONFLICT(batch_id,invoice_id) DO NOTHING""",
                (safe_batch_id, invoice_id, timestamp),
            )
            if created:
                new_count += 1
            else:
                known_count += 1
            item_count += int(conn.execute(
                "SELECT COUNT(*) n FROM msmi_invoice_items WHERE invoice_id=?", (invoice_id,)
            ).fetchone()["n"])
            return normalized

        def fetch_page(page: int) -> dict[str, Any]:
            result = client.list_invoices(
                invoice_type=INPUT_INVOICE,
                page=page,
                size=safe_page_size,
                from_date=date_from,
                to_date=date_to,
            )
            if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                raise MsmiError("mSMI không trả danh sách hóa đơn đúng cấu trúc")
            return result

        if complete:
            # Re-read the newest page on every repeat, then rotate through older
            # pages. Upserts and batch links make this reconciliation idempotent.
            page_sequence = [0] + list(range(reconcile_page, reconcile_page + page_limit - 1))
            next_reconcile_page = reconcile_page
            for page in page_sequence:
                result = fetch_page(page)
                pages += 1
                remote_items = result["items"]
                if not remote_items:
                    if page > 0:
                        next_reconcile_page = 1
                    break
                for remote in remote_items:
                    if isinstance(remote, dict):
                        consume(remote)
                if page > 0:
                    next_reconcile_page = page + 1
                if not bool(result.get("has_more")):
                    next_reconcile_page = 1
                    break
            reconcile_page = next_reconcile_page
        else:
            locating_anchor = bool(anchor_id)
            page = 0
            while True:
                if page >= 5000:
                    raise MsmiError("Không tìm thấy mốc tiếp tục mSMI trong giới hạn an toàn")
                result = fetch_page(page)
                pages += 1
                remote_items = result["items"]
                if not remote_items:
                    complete = True
                    break
                page_made_progress = False
                for remote in remote_items:
                    if not isinstance(remote, dict):
                        continue
                    normalized = consume(remote)
                    if locating_anchor:
                        if normalized["remote_id"] == anchor_id:
                            locating_anchor = False
                        continue
                    anchor_id = normalized["remote_id"]
                    anchor_date = normalized["invoice_date"]
                    page_made_progress = True
                if locating_anchor:
                    if not bool(result.get("has_more")):
                        complete = True
                        break
                    page += 1
                    continue
                if page_made_progress:
                    progress_pages += 1
                if not bool(result.get("has_more")):
                    complete = True
                    break
                if progress_pages >= page_limit:
                    break
                page += 1

        cursor_payload = {
            "version": 1,
            "anchor_remote_id": anchor_id,
            "anchor_date": anchor_date,
            "complete": complete,
            "reconcile_next_page": reconcile_page,
        }
        counts = _batch_counts(conn, safe_batch_id)
        if not complete:
            status = "partial"
        elif counts["error_count"]:
            status = "quarantined"
        elif counts["needs_mapping_count"]:
            status = "needs_mapping"
        else:
            status = "ready"
        timestamp = now_iso()
        conn.execute(
            """UPDATE invoice_sync_batches SET
                   status=?,source_cursor=?,source_hash=?,fetched_count=?,
                   needs_mapping_count=?,ready_count=?,posted_count=?,error_count=?,
                   error_code='',updated_at=?,completed_at=?
               WHERE id=?""",
            (
                status,
                json.dumps(cursor_payload, separators=(",", ":"), sort_keys=True),
                _batch_source_hash(conn, safe_batch_id),
                counts["fetched_count"],
                counts["needs_mapping_count"],
                counts["ready_count"],
                counts["posted_count"],
                counts["error_count"],
                timestamp,
                timestamp if complete else None,
                safe_batch_id,
            ),
        )
        _audit(
            conn,
            now_iso,
            "ok",
            batch_id=safe_batch_id,
            metadata={
                "invoice_type": INPUT_INVOICE,
                "date_from": date_from,
                "date_to": date_to,
                "pages": pages,
                "new_invoices": new_count,
                "known_invoices": known_count,
                "invoice_items": item_count,
                "review_required": review_count,
                "skipped_out_of_range": skipped_out_of_range,
                "complete": complete,
            },
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return {
            "batch_id": safe_batch_id,
            "invoice_type": INPUT_INVOICE,
            "date_from": date_from,
            "date_to": date_to,
            "new_invoices": new_count,
            "known_invoices": known_count,
            "items": item_count,
            "pages": pages,
            "review_required": review_count,
            "skipped_out_of_range": skipped_out_of_range,
            "complete": complete,
            "more_history": not complete,
            "status": status,
            **counts,
            "read_only": True,
        }
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        error_code = "source_data_out_of_range" if isinstance(error, InvoiceInputSyncError) else (
            "msmi_source_error" if isinstance(error, MsmiError) else "sync_failed"
        )
        timestamp = now_iso()
        conn.execute(
            """UPDATE invoice_sync_batches SET status='error',error_count=1,error_code=?,
                      updated_at=?,completed_at=NULL WHERE id=?""",
            (error_code, timestamp, safe_batch_id),
        )
        _audit(
            conn,
            now_iso,
            "error",
            batch_id=safe_batch_id,
            metadata={
                "invoice_type": INPUT_INVOICE,
                "date_from": date_from,
                "date_to": date_to,
                "error_code": error_code,
            },
        )
        raise
