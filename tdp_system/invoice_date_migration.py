"""Repair proven legacy UTC input dates without rewriting posted inventory.

Run after a pre-upgrade backup, or on the isolated release seed snapshot.
No connector calls, source re-import, or modifications to quantities/mappings.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

VIETNAM = timezone(timedelta(hours=7))
INPUT = "INPUT_ELECTRONIC_INVOICE"


def _tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _source_dates(raw_json):
    try:
        raw = json.loads(raw_json)
        if not isinstance(raw, dict):
            return None
        value = next((raw.get(key) for key in ("tdlap", "nlap", "invoiceDate", "signedDate")
                      if raw.get(key) not in (None, "")), None)
        if not isinstance(value, str):
            return None
        value = value.strip()
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.upper().endswith("Z") else value)
        # Only timezone-bearing source timestamps prove the UTC truncation bug.
        if parsed.tzinfo is None:
            return None
        return parsed.date().isoformat(), parsed.astimezone(VIETNAM).date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def repair_legacy_input_dates(conn, *, timestamp=None):
    """Atomic, repeatable repair; the caller owns the outer commit/rollback.

    Block ambiguous date changes and any document with a stock footprint.
    A dedicated history table keeps before/after evidence without raw payloads.
    """
    tables = _tables(conn)
    result = {"corrected": 0, "blocked": 0}
    if "msmi_invoices" not in tables:
        return result
    timestamp = timestamp or datetime.now(VIETNAM).isoformat(timespec="seconds")
    conn.execute("SAVEPOINT legacy_input_dates")
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS invoice_date_repairs (
            invoice_id INTEGER NOT NULL,
            old_date TEXT NOT NULL,
            new_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('corrected','blocked')),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(invoice_id,old_date,new_date)
        )""")
        posted_ids = set()
        if "invoice_inventory_ledger" in tables:
            posted_ids.update(row[0] for row in conn.execute(
                "SELECT DISTINCT source_invoice_id FROM invoice_inventory_ledger "
                "WHERE source_invoice_table='msmi_invoices'"))
        if "invoice_inventory_confirmations" in tables:
            posted_ids.update(row[0] for row in conn.execute(
                "SELECT DISTINCT source_invoice_id FROM invoice_inventory_confirmations "
                "WHERE source_invoice_table='msmi_invoices'"))
        legacy_sources = set()
        if "inventory_transactions" in tables:
            legacy_sources = {str(row[0]) for row in conn.execute(
                "SELECT DISTINCT source_id FROM inventory_transactions WHERE source_type='MSMI_INPUT'")}
        rows = conn.execute("""SELECT id,remote_id,invoice_date,receipt_status,raw_json
                               FROM msmi_invoices WHERE invoice_type=? ORDER BY id""", (INPUT,)).fetchall()
        for invoice_id, remote_id, old_date, receipt_status, raw_json in rows:
            old_date = str(old_date or "")
            dates = _source_dates(raw_json)
            if dates is None or old_date == dates[1]:
                continue
            source_date, new_date = dates
            status = "blocked"
            if old_date != source_date:
                reason = "Ngày đã lưu khác cả ngày timestamp và ngày Việt Nam; cần đối chiếu nguồn."
            elif (receipt_status not in {"pending_mapping", "ready", "not_inventory", "blocked"}
                  or invoice_id in posted_ids or str(remote_id) in legacy_sources):
                reason = "Hóa đơn đã ghi kho hoặc có dấu vết xử lý kho; cần đối chiếu ngày và kỳ kho trước khi sửa."
            else:
                status = "corrected"
                reason = "Sửa ngày UTC đã lưu theo timestamp nguồn và giờ Việt Nam."
                conn.execute("UPDATE msmi_invoices SET invoice_date=?,updated_at=? WHERE id=?",
                             (new_date, timestamp, invoice_id))
            previous = conn.execute("""SELECT status,reason FROM invoice_date_repairs
                                     WHERE invoice_id=? AND old_date=? AND new_date=?""",
                                    (invoice_id, old_date, new_date)).fetchone()
            if previous is None or tuple(previous) != (status, reason):
                conn.execute("""INSERT INTO invoice_date_repairs
                    (invoice_id,old_date,new_date,status,reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(invoice_id,old_date,new_date) DO UPDATE SET
                    status=excluded.status,reason=excluded.reason,updated_at=excluded.updated_at""",
                    (invoice_id, old_date, new_date, status, reason, timestamp, timestamp))
            if status == "blocked":
                message = f"[DATE_REPAIR] Ngày đang lưu {old_date}, ngày nguồn Việt Nam {new_date}. {reason}"
                # Keep all existing source errors, but do not append on every restart.
                current = conn.execute("SELECT sync_status,error_message FROM msmi_invoices WHERE id=?",
                                       (invoice_id,)).fetchone()
                old_message = str(current[1] or "")
                if message not in old_message:
                    conn.execute("UPDATE msmi_invoices SET sync_status='review_required',error_message=?,updated_at=? WHERE id=?",
                                 ("\n".join(filter(None, (old_message, message))), timestamp, invoice_id))
            result[status] += 1
        conn.execute("RELEASE SAVEPOINT legacy_input_dates")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT legacy_input_dates")
        conn.execute("RELEASE SAVEPOINT legacy_input_dates")
        raise
    return result


def input_date_repair_report(conn, *, tenant, date_from, date_to):
    """Read-only report, including blocked records on the OTHER side of a month boundary."""
    empty = {"corrected_count": 0, "blocked_count": 0, "items": []}
    if "invoice_date_repairs" not in _tables(conn):
        return empty
    rows = conn.execute("""SELECT r.invoice_id,r.old_date,r.new_date,r.status,r.reason,
                                  i.invoice_date,i.invoice_series,i.invoice_number,i.seller_name,
                                  i.raw_json
                           FROM invoice_date_repairs r JOIN msmi_invoices i ON i.id=r.invoice_id
                           WHERE i.tenant=? AND (r.old_date BETWEEN ? AND ? OR r.new_date BETWEEN ? AND ?)
                           ORDER BY r.new_date,r.invoice_id""",
                        (tenant, date_from, date_to, date_from, date_to)).fetchall()
    corrected = set()
    blocked = {}
    for invoice_id, old, new, status, reason, current, series, number, seller, raw in rows:
        if status == "corrected" and current == new:
            corrected.add(invoice_id)
        elif status == "blocked" and str(current or "") == old:
            source_dates = _source_dates(raw)
            if source_dates is None or source_dates[1] != new:
                continue  # A later source revision is no longer this repair candidate.
            blocked[invoice_id] = {"invoice_id": invoice_id, "invoice_series": series,
                                   "invoice_number": number, "seller_name": seller,
                                   "old_date": old, "new_date": new, "reason": reason}
    return {"corrected_count": len(corrected), "blocked_count": len(blocked),
            "items": list(blocked.values())}
