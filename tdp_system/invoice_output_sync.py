"""Read-only M-Invoice output ingestion with a fail-closed status contract.

The built-in mapping follows the published M-Invoice API v1.0.9 states and the
field names verified from the deployed ``GetInvoices`` response. Anything not
covered by that contract is persisted for review but remains blocked from
inventory. This module never calls an M-Invoice write endpoint.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

try:
    from contract_modules import (
        MsmiError,
        as_date,
        first_value,
        invoice_details,
        msmi_number,
    )
except ImportError:  # pragma: no cover - package invocation
    from .contract_modules import (
        MsmiError,
        as_date,
        first_value,
        invoice_details,
        msmi_number,
    )

try:
    from invoice_mapping import apply_saved_mappings
except ImportError:  # pragma: no cover - package invocation
    from .invoice_mapping import apply_saved_mappings

try:
    from minvoice_client import MinvoiceError
except ImportError:  # pragma: no cover - package invocation
    from .minvoice_client import MinvoiceError


OUTPUT_INVOICE = "OUTPUT_ELECTRONIC_INVOICE"
MINVOICE_SOURCE = "minvoice"
CANONICAL_STATUSES = {"issued", "draft", "unknown", "cancelled", "replaced", "adjusted"}


class InvoiceOutputSyncError(ValueError):
    """A safe validation/state error for output sync."""


def normalize_status_map(value: Any) -> dict[str, str]:
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, json.JSONDecodeError):
            raise InvoiceOutputSyncError("Cấu hình ánh xạ trạng thái đầu ra không phải JSON hợp lệ") from None
    if not isinstance(value, dict):
        raise InvoiceOutputSyncError("Cấu hình ánh xạ trạng thái đầu ra phải là object")
    output: dict[str, str] = {}
    for raw, canonical in value.items():
        raw_key = str(raw or "").strip().casefold()
        canonical_value = str(canonical or "").strip().casefold()
        if not raw_key or canonical_value not in CANONICAL_STATUSES:
            raise InvoiceOutputSyncError("Ánh xạ trạng thái đầu ra chứa giá trị chưa được cho phép")
        output[raw_key] = canonical_value
    return output


def normalize_field_names(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except (ValueError, json.JSONDecodeError):
                raise InvoiceOutputSyncError("Cấu hình trường trạng thái đầu ra không hợp lệ") from None
        else:
            value = [part.strip() for part in stripped.split(",")]
    if not isinstance(value, (list, tuple)):
        raise InvoiceOutputSyncError("Cấu hình trường trạng thái đầu ra phải là danh sách")
    fields = tuple(str(item or "").strip() for item in value if str(item or "").strip())
    if any(not field.replace("_", "").isalnum() for field in fields):
        raise InvoiceOutputSyncError("Tên trường trạng thái đầu ra không hợp lệ")
    return fields


def _identity(remote: dict, invoice_date: str = "") -> dict[str, str]:
    remote_id = str(first_value(
        remote, "id", "hoadon68_id", "_id", "invoiceId", "inv_invoiceAuth_id", default="",
    ) or "").strip()
    number = str(first_value(
        remote, "shdon", "inv_invoiceNumber", "soHoaDon", "invoiceNumber", default="",
    ) or "").strip()
    series = str(first_value(
        remote, "inv_invoiceSeries", "khhdon", "khmshdon", "series", "invoiceSeries", default="",
    ) or "").strip()
    if not invoice_date:
        invoice_date = as_date(first_value(
            remote, "inv_invoiceIssuedDate", "tdlap", "nlap", "invoiceDate", "signedDate",
        ))
    business_source = "\0".join((series, number, invoice_date)) if all((series, number, invoice_date)) else ""
    business_key = hashlib.sha256(business_source.encode("utf-8")).hexdigest() if business_source else ""
    identity_source = "remote\0" + remote_id if remote_id else "business\0" + business_key
    if not remote_id and not business_key:
        raise MsmiError("Hóa đơn đầu ra thiếu cả remote ID và khóa nghiệp vụ ký hiệu/số/ngày")
    return {
        "remote_id": remote_id,
        "invoice_number": number,
        "invoice_series": series,
        "invoice_date": invoice_date,
        "business_key": business_key,
        "identity_key": hashlib.sha256(identity_source.encode("utf-8")).hexdigest(),
    }


def _source_status(
    remote: dict,
    status_map: dict[str, str],
    status_fields: Iterable[str],
) -> tuple[str, str, str]:
    for field in status_fields:
        if field in remote and remote[field] not in (None, ""):
            raw = str(remote[field]).strip()
            return raw, status_map.get(raw.casefold(), "unknown"), field
    return "", "unknown", ""


def _fold_status(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().casefold())
    return " ".join(
        "".join(character for character in text if unicodedata.category(character) != "Mn")
        .replace("đ", "d")
        .split()
    )


def _status_code(value: Any, labels: dict[str, int]) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        numeric = Decimal(str(value).strip())
        if numeric.is_finite() and numeric == numeric.to_integral_value():
            return int(numeric)
    except (InvalidOperation, TypeError, ValueError):
        pass
    return labels.get(_fold_status(value))


def minvoice_source_status(remote: dict) -> tuple[str, str, str]:
    """Map documented M-Invoice states without guessing unknown values.

    M-Invoice API v1.0.9 documents ``is_tthdon`` as invoice relation/state
    (0 original, 1 cancelled, 2/6 adjusted, 3/5 replaced) and ``tthai`` as
    the tax-authority lifecycle.  The deployed GetInvoices response exposes
    the numeric tax state as ``trang_thai`` and a display label in ``tthai``.
    Only an original invoice at the final success state may enter the stock
    mapping queue; every missing or undocumented combination fails closed.
    """
    if remote.get("_tdp_source_contract") == "minvoice_portal_v1":
        try:
            from .minvoice_portal import portal_status
        except ImportError:
            from minvoice_portal import portal_status
        return portal_status(remote)
    document_labels = {
        "goc": 0,
        "huy": 1,
        "dieu chinh": 2,
        "thay the": 3,
        "giai trinh": 4,
        "bi thay the": 5,
        "bi dieu chinh": 6,
    }
    tax_labels = {
        "cho duyet": 0,
        "cho ky": 1,
        "da ky": 2,
        "da gui": 4,  # Live GetInvoices label paired with documented success code 4.
        "thanh cong": 4,
        "co loi": 5,
        "tu choi": 6,
    }
    document_raw = first_value(remote, "is_tthdon", default=None)
    tax_raw = first_value(remote, "trang_thai", default=None)
    if tax_raw in (None, ""):
        tax_raw = first_value(remote, "tthai", default=None)
    document_code = _status_code(document_raw, document_labels)
    tax_code = _status_code(tax_raw, tax_labels)
    raw = json.dumps(
        {"invoice_state": document_raw, "tax_state": tax_raw},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if document_code == 1:
        canonical = "cancelled"
    elif document_code in {2, 6}:
        canonical = "adjusted"
    elif document_code in {3, 5}:
        canonical = "replaced"
    elif document_code == 0 and tax_code == 4:
        canonical = "issued"
    elif document_code == 0 and tax_code in {0, 1, 2, 3}:
        canonical = "draft"
    else:
        canonical = "unknown"
    return raw, canonical, "is_tthdon+trang_thai/tthai"


def resolved_source_status(
    remote: dict,
    status_map: dict[str, str],
    status_fields: Iterable[str],
) -> tuple[str, str, str]:
    # Explicit mappings remain available for deterministic fixtures and a
    # future documented provider version. Production M-Invoice needs no local
    # secret/configuration knob for its published status contract.
    fields = tuple(status_fields)
    if status_map and fields:
        return _source_status(remote, status_map, fields)
    return minvoice_source_status(remote)


def _reference(remote: dict, reference_fields: Iterable[str]) -> str:
    for field in reference_fields:
        if field in remote and remote[field] not in (None, ""):
            return str(remote[field]).strip()
    return ""


def normalize_output_invoice(
    remote: dict,
    *,
    status_map: dict[str, str],
    status_fields: Iterable[str],
    reference_fields: Iterable[str],
    now: str,
) -> dict[str, Any]:
    invoice_date = as_date(first_value(
        remote, "inv_invoiceIssuedDate", "tdlap", "nlap", "invoiceDate", "signedDate",
    ))
    if not invoice_date:
        raise MsmiError("Hóa đơn đầu ra thiếu ngày lập hợp lệ")
    identity = _identity(remote, invoice_date)
    subtotal = msmi_number(first_value(remote, "tgtcthue", "subtotal", "totalBeforeTax"), "Tiền trước thuế")
    tax_amount = msmi_number(first_value(remote, "tgtthue", "taxAmount", "totalTax"), "Tiền thuế")
    total_amount = msmi_number(first_value(remote, "tgtttbso", "tgtttbchu", "totalAmount", "total"), "Tổng tiền")
    source_raw, source_class, source_field = resolved_source_status(remote, status_map, status_fields)
    portal_adjustment = (remote.get("_tdp_source_contract") == "minvoice_portal_v1"
                         and source_class in {"adjusted", "replaced", "cancelled"})
    if (subtotal < 0 or tax_amount < 0 or total_amount < 0) and not portal_adjustment:
        raise MsmiError("Hóa đơn đầu ra có tổng tiền âm; cần đối chiếu thủ công")
    if total_amount <= 0 and remote.get("_tdp_source_contract") != "minvoice_portal_v1":
        total_amount = subtotal + tax_amount
    source_raw, source_class, source_field = resolved_source_status(
        remote, status_map, status_fields,
    )
    validation_error = ""
    if remote.get("_tdp_source_contract") == "minvoice_portal_v1":
        try:
            from .minvoice_portal import portal_validation_error
        except ImportError:
            from minvoice_portal import portal_validation_error
        validation_error = portal_validation_error(remote)
    try:
        raw_json = json.dumps(remote, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise MsmiError("Hóa đơn đầu ra chứa dữ liệu JSON không hợp lệ") from None
    return {
        **identity,
        "buyer_tax_code": str(first_value(
            remote, "inv_buyerTaxCode", "mstNmua", "nmstmua", "buyerTaxCode", "buyerTaxId", default=""
        ) or ""),
        "buyer_name": str(first_value(
            remote, "inv_buyerLegalName", "inv_buyerDisplayName", "tnmua",
            "tenNmua", "nmten", "buyerName", default="",
        ) or ""),
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_amount": total_amount,
        "source_status_raw": source_raw,
        "source_status_class": source_class,
        "source_status_field": source_field,
        "validation_error": validation_error,
        "relation_reference": _reference(remote, reference_fields),
        "raw_json": raw_json,
        "synced_at": now,
        "cursor_id": identity["remote_id"] or identity["identity_key"],
    }


def normalize_output_item(remote_item: dict, line_index: int, *, portal_adjustment=False) -> dict[str, Any]:
    """Normalize either documented M-Invoice detail names or legacy aliases."""
    qty = msmi_number(
        first_value(remote_item, "inv_quantity", "sluong", "quantity", "qty"),
        f"Số lượng dòng {line_index}",
    )
    unit_price = msmi_number(
        first_value(remote_item, "inv_unitPrice", "dgia", "unitPrice", "price"),
        f"Đơn giá dòng {line_index}",
    )
    amount = msmi_number(
        first_value(
            remote_item,
            "inv_TotalAmountWithoutVat",
            "inv_Amount",
            "thtien",
            "amount",
            "total",
        ),
        f"Thành tiền dòng {line_index}",
    )
    nature = str(first_value(remote_item, "tchat", "nature", "itemNature", "type")).strip()
    financial_adjustment = amount < 0 and qty == 0 and unit_price == 0
    if not portal_adjustment and (qty < 0 or unit_price < 0 or (amount < 0 and not financial_adjustment)):
        raise MsmiError(
            f"Dòng {line_index} M-Invoice có số lượng, đơn giá hoặc thành tiền âm; "
            "cần đối chiếu thủ công"
        )
    inventory_eligible = not portal_adjustment and not financial_adjustment and qty > 0 and (unit_price > 0 or amount == 0)
    if portal_adjustment:
        validation_note = "Giữ lượng/tiền điều chỉnh nguồn để đối chiếu; không tự ghi kho"
    elif financial_adjustment:
        validation_note = (
            "Không ghi kho: dòng chiết khấu/điều chỉnh tài chính âm, "
            "được giữ nguyên để đối chiếu tổng hóa đơn"
        )
    elif inventory_eligible:
        validation_note = ""
    else:
        validation_note = (
            "Không ghi kho: dòng nguồn không có số lượng/đơn giá dương; "
            "vẫn giữ nguyên để đối chiếu hóa đơn"
        )
    return {
        "line_index": line_index,
        "source_item_code": str(first_value(
            remote_item, "inv_itemCode", "ma", "mhhhoa", "itemCode", "code",
        )),
        "source_item_name": str(first_value(
            remote_item, "inv_itemName", "ten", "tenhh", "itemName", "name",
        )),
        "source_unit": str(first_value(
            remote_item, "inv_unitCode", "dvtinh", "dvt", "unit",
        )),
        "qty": qty,
        "unit_price": unit_price,
        "amount": amount,
        "tax_rate": str(first_value(remote_item, "ma_thue", "tsuat", "taxRate", "tax")),
        "source_nature": nature,
        "inventory_eligible": 1 if inventory_eligible else 0,
        "validation_note": validation_note,
    }


def _event(
    conn,
    invoice_id: int,
    identity_key: str,
    previous: str,
    current: str,
    reference: str,
    now: str,
) -> None:
    if previous == current:
        return
    event_type = "status_transition" if previous else "source_status_observed"
    event_key = hashlib.sha256(
        "\0".join((str(invoice_id), identity_key, event_type, previous, current, reference)).encode("utf-8")
    ).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO outgoing_source_events(
               event_key,invoice_id,event_type,previous_status_class,current_status_class,
               relation_reference,created_at
           ) VALUES(?,?,?,?,?,?,?)""",
        (event_key, invoice_id, event_type, previous, current, reference, now),
    )


def _business_signature(header: dict[str, Any], items: list[dict[str, Any]]) -> str:
    return json.dumps({
        "header": {
            key: header.get(key, "") for key in (
                "buyer_tax_code", "buyer_name", "invoice_number", "invoice_series", "invoice_date",
                "subtotal", "tax_amount", "total_amount",
            )
        },
        "items": [{
            key: item.get(key, "") for key in (
                "line_index", "source_item_code", "source_item_name", "source_unit", "qty",
                "unit_price", "amount", "tax_rate", "source_nature", "inventory_eligible",
            )
        } for item in items],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def quarantine_output_invoice(
    conn,
    remote: dict,
    *,
    tenant: str,
    source: str,
    now: str,
    error: Exception,
    status_map: dict[str, str],
    status_fields: Iterable[str],
    reference_fields: Iterable[str],
) -> tuple[int, bool, dict[str, Any]]:
    identity = _identity(remote)
    source_raw, source_class, source_field = resolved_source_status(
        remote, status_map, status_fields,
    )
    try:
        raw_json = json.dumps(remote, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise MsmiError("Hóa đơn đầu ra lỗi dữ liệu và JSON không thể cách ly an toàn") from None
    existing = conn.execute(
        "SELECT * FROM outgoing_source_invoices WHERE tenant=? AND source=? AND identity_key=?",
        (tenant, source, identity["identity_key"]),
    ).fetchone()
    timestamp = now
    message = "Dữ liệu nguồn đầu ra cần đối chiếu thủ công: " + str(error)[:180]
    if existing and existing["stock_status"] in {"posted", "reversal_required", "reversed"}:
        frozen_status = (
            "reversed" if existing["stock_status"] == "reversed" else "reversal_required"
        )
        conn.execute(
            """UPDATE outgoing_source_invoices SET sync_status='reconcile_required',
                      source_status_raw=?,source_status_class=?,source_status_field=?,
                      stock_status=?,error_message=?,synced_at=?,updated_at=? WHERE id=?""",
            (
                source_raw, source_class, source_field, frozen_status, message,
                timestamp, timestamp, existing["id"],
            ),
        )
        return existing["id"], False, {**identity, "cursor_id": identity["remote_id"] or identity["identity_key"]}
    if existing:
        invoice_id = existing["id"]
        conn.execute("DELETE FROM outgoing_source_invoice_items WHERE invoice_id=?", (invoice_id,))
        conn.execute(
            """UPDATE outgoing_source_invoices SET source_status_raw=?,source_status_class=?,
                      source_status_field=?,sync_status='review_required',stock_status='blocked',
                      raw_json=?,error_message=?,synced_at=?,updated_at=? WHERE id=?""",
            (source_raw, source_class, source_field, raw_json, message, timestamp, timestamp, invoice_id),
        )
        created = False
    else:
        cursor = conn.execute(
            """INSERT INTO outgoing_source_invoices(
                   tenant,source,identity_key,remote_id,business_key,buyer_tax_code,buyer_name,
                   invoice_number,invoice_series,invoice_date,source_status_raw,source_status_class,
                   source_status_field,sync_status,stock_status,raw_json,error_message,
                   synced_at,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'review_required','blocked',?,?,?,?,?)""",
            (
                tenant, source, identity["identity_key"], identity["remote_id"], identity["business_key"],
                str(first_value(
                    remote, "inv_buyerTaxCode", "mstNmua", "nmstmua", "buyerTaxCode", default="",
                ) or ""),
                str(first_value(
                    remote, "inv_buyerLegalName", "inv_buyerDisplayName", "tnmua",
                    "tenNmua", "nmten", "buyerName", default="",
                ) or ""),
                identity["invoice_number"], identity["invoice_series"], identity["invoice_date"],
                source_raw, source_class, source_field, raw_json, message, timestamp, timestamp, timestamp,
            ),
        )
        invoice_id = cursor.lastrowid
        created = True
    _event(
        conn, invoice_id, identity["identity_key"],
        str(existing["source_status_class"] or "") if existing else "",
        source_class, "", timestamp,
    )
    return invoice_id, created, {**identity, "cursor_id": identity["remote_id"] or identity["identity_key"]}


def upsert_output_invoice(
    conn,
    remote: dict,
    *,
    tenant: str,
    source: str = MINVOICE_SOURCE,
    now: str,
    status_map: dict[str, str],
    status_fields: Iterable[str],
    reference_fields: Iterable[str],
) -> tuple[int, bool, dict[str, Any], bool]:
    try:
        data = normalize_output_invoice(
            remote,
            status_map=status_map,
            status_fields=status_fields,
            reference_fields=reference_fields,
            now=now,
        )
        normalized_items = [
            normalize_output_item(item if isinstance(item, dict) else {}, index,
                                  portal_adjustment=(remote.get("_tdp_source_contract") == "minvoice_portal_v1"
                                                     and data["source_status_class"] in {"adjusted", "replaced", "cancelled"}))
            for index, item in enumerate(invoice_details(remote), start=1)
        ]
    except MsmiError as error:
        invoice_id, created, data = quarantine_output_invoice(
            conn,
            remote,
            tenant=tenant,
            source=source,
            now=now,
            error=error,
            status_map=status_map,
            status_fields=status_fields,
            reference_fields=reference_fields,
        )
        return invoice_id, created, data, True

    existing = conn.execute(
        "SELECT * FROM outgoing_source_invoices WHERE tenant=? AND source=? AND identity_key=?",
        (tenant, source, data["identity_key"]),
    ).fetchone()
    if not existing and data["business_key"]:
        business_match = conn.execute(
            """SELECT * FROM outgoing_source_invoices
               WHERE tenant=? AND source=? AND business_key=?""",
            (tenant, source, data["business_key"]),
        ).fetchone()
        if business_match:
            message = "Khóa remote của cùng ký hiệu/số/ngày đã thay đổi; cần đối chiếu nguồn"
            conn.execute(
                """UPDATE outgoing_source_invoices SET sync_status='review_required',
                          stock_status=CASE
                              WHEN stock_status='reversed' THEN 'reversed'
                              WHEN stock_status IN ('posted','reversal_required') THEN 'reversal_required'
                              ELSE 'blocked' END,
                          error_message=?,updated_at=?,synced_at=? WHERE id=?""",
                (message, now, now, business_match["id"]),
            )
            _event(
                conn, business_match["id"], business_match["identity_key"],
                business_match["source_status_class"], "unknown", "identity_conflict", now,
            )
            return business_match["id"], False, data, True

    previous_class = str(existing["source_status_class"] or "") if existing else ""
    if existing and existing["stock_status"] in {"posted", "reversal_required", "reversed"}:
        stored_items = [dict(row) for row in conn.execute(
            "SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index",
            (existing["id"],),
        )]
        changed = _business_signature(dict(existing), stored_items) != _business_signature(data, normalized_items)
        already_reversed = existing["stock_status"] == "reversed"
        try:
            from .invoice_output_editing import PORTAL_TOTAL_MISMATCH, output_amount_review
        except ImportError:
            from invoice_output_editing import PORTAL_TOTAL_MISMATCH, output_amount_review
        unchanged_amount_warning = (not changed and existing['stock_status'] == 'posted'
            and data.get('validation_error') == PORTAL_TOTAL_MISMATCH
            and output_amount_review(existing) is not None)
        requires_reconcile = (already_reversed or changed or data["source_status_class"] != "issued"
                              or bool(data.get("validation_error")) and not unchanged_amount_warning)
        next_stock_status = (
            "reversed" if already_reversed
            else "reversal_required" if requires_reconcile
            else "posted"
        )
        conn.execute(
            """UPDATE outgoing_source_invoices SET source_status_raw=?,source_status_class=?,
                      source_status_field=?,relation_reference=?,
                      sync_status=?,stock_status=?,error_message=?,synced_at=?,updated_at=?
               WHERE id=?""",
            (
                data["source_status_raw"], data["source_status_class"], data["source_status_field"],
                data["relation_reference"],
                "reconcile_required" if requires_reconcile else "review_required" if unchanged_amount_warning else "synced",
                next_stock_status,
                "Nguồn thay đổi sau khi đã ghi kho; cần hoàn tác xuất kho và đối chiếu" if requires_reconcile else PORTAL_TOTAL_MISMATCH if unchanged_amount_warning else "",
                now, now, existing["id"],
            ),
        )
        _event(
            conn, existing["id"], data["identity_key"], previous_class,
            data["source_status_class"], data["relation_reference"], now,
        )
        return existing["id"], False, data, requires_reconcile

    if existing:
        invoice_id = existing["id"]
        conn.execute("DELETE FROM outgoing_source_invoice_items WHERE invoice_id=?", (invoice_id,))
        created = False
    else:
        invoice_id = conn.execute(
            """INSERT INTO outgoing_source_invoices(
               tenant,source,identity_key,remote_id,business_key,synced_at,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?)""",
            (tenant, source, data["identity_key"], data["remote_id"], data["business_key"], now, now, now),
        ).lastrowid
        created = True

    inventory_items = 0
    for item in normalized_items:
        inventory_items += int(bool(item["inventory_eligible"]))
        conn.execute(
            """INSERT INTO outgoing_source_invoice_items(
                   invoice_id,line_index,source_item_code,source_item_name,source_unit,qty,
                   unit_price,amount,tax_rate,source_nature,inventory_eligible,validation_note,
                   product_code,mapping_status
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                invoice_id, item["line_index"], item["source_item_code"], item["source_item_name"],
                item["source_unit"], item["qty"], item["unit_price"], item["amount"],
                item["tax_rate"], item["source_nature"], item["inventory_eligible"],
                item["validation_note"], "",
                "unmapped" if item["inventory_eligible"] else "not_inventory",
            ),
        )
    status_class = data["source_status_class"]
    if data.get("validation_error"):
        sync_status, stock_status, error_message = "review_required", "blocked", data["validation_error"]
    elif status_class == "issued":
        sync_status = "synced"
        stock_status = "pending_mapping" if inventory_items else "not_inventory"
        error_message = ""
    elif status_class in {"cancelled", "replaced", "adjusted"}:
        sync_status = "reconcile_required"
        # A relation/cancellation first observed before any POST has nothing to
        # reverse. Keep it blocked. Only the frozen-posted branch above may
        # promote an already-posted invoice to reversal_required.
        stock_status = "blocked"
        error_message = "Trạng thái nguồn yêu cầu đối chiếu; hóa đơn này chưa được ghi xuất kho"
    else:
        sync_status = "review_required"
        stock_status = "blocked"
        error_message = "Trạng thái nguồn chưa chứng minh hóa đơn đã phát hành hợp lệ"
    conn.execute(
        """UPDATE outgoing_source_invoices SET
               remote_id=?,business_key=?,buyer_tax_code=?,buyer_name=?,invoice_number=?,
               invoice_series=?,invoice_date=?,subtotal=?,tax_amount=?,total_amount=?,
               source_status_raw=?,source_status_class=?,source_status_field=?,relation_reference=?,
               sync_status=?,stock_status=?,raw_json=?,error_message=?,synced_at=?,updated_at=?
           WHERE id=?""",
        (
            data["remote_id"], data["business_key"], data["buyer_tax_code"], data["buyer_name"],
            data["invoice_number"], data["invoice_series"], data["invoice_date"], data["subtotal"],
            data["tax_amount"], data["total_amount"], data["source_status_raw"],
            data["source_status_class"], data["source_status_field"], data["relation_reference"],
            sync_status, stock_status, data["raw_json"], error_message, now, now, invoice_id,
        ),
    )
    _event(
        conn, invoice_id, data["identity_key"], previous_class,
        status_class, data["relation_reference"], now,
    )
    return invoice_id, created, data, sync_status != "synced"


def _counts(conn, batch_id: int) -> dict[str, int]:
    row = conn.execute(
        """SELECT COUNT(*) fetched_count,
                  COALESCE(SUM(CASE WHEN i.stock_status='pending_mapping' THEN 1 ELSE 0 END),0)
                      needs_mapping_count,
                  COALESCE(SUM(CASE WHEN i.stock_status='ready' THEN 1 ELSE 0 END),0) ready_count,
                  COALESCE(SUM(CASE WHEN i.stock_status='posted' THEN 1 ELSE 0 END),0) posted_count,
                  COALESCE(SUM(CASE WHEN i.sync_status!='synced'
                                      OR i.stock_status IN ('blocked','reversal_required') THEN 1 ELSE 0 END),0)
                      error_count
           FROM invoice_sync_batch_output_invoices bi
           JOIN outgoing_source_invoices i ON i.id=bi.invoice_id
           WHERE bi.batch_id=?""",
        (batch_id,),
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def _source_hash(conn, batch_id: int) -> str:
    digest = hashlib.sha256()
    for row in conn.execute(
        """SELECT i.identity_key FROM invoice_sync_batch_output_invoices bi
           JOIN outgoing_source_invoices i ON i.id=bi.invoice_id
           WHERE bi.batch_id=? ORDER BY i.identity_key""",
        (batch_id,),
    ):
        digest.update(row["identity_key"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _audit(conn, now_iso, status: str, batch_id: int, metadata: dict[str, Any]) -> None:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone():
        return
    conn.execute(
        """INSERT INTO audit_log(
               event_type,entity_type,entity_id,status,message,metadata_json,created_at
           ) VALUES('invoice_output.sync','invoice_sync_batch',?,?,?,?,?)""",
        (
            str(batch_id), status, "",
            json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            now_iso(),
        ),
    )


def _minvoice_series_codes(client, date_from: str, date_to: str) -> list[str]:
    series_rows = client.get_invoice_series()
    if not isinstance(series_rows, list):
        raise MinvoiceError("M-Invoice không trả danh sách ký hiệu đúng cấu trúc")
    first_year = datetime.strptime(date_from, "%Y-%m-%d").year
    last_year = datetime.strptime(date_to, "%Y-%m-%d").year
    accepted_years = {year for year in range(first_year, last_year + 1)}
    codes: set[str] = set()
    for row in series_rows:
        if not isinstance(row, dict):
            continue
        raw_year = row.get("invoiceYear")
        if raw_year not in (None, ""):
            try:
                year = int(raw_year)
            except (TypeError, ValueError):
                continue
            if year < 100:
                year += 2000
            if year not in accepted_years:
                continue
        code = str(row.get("value") or row.get("khhdon") or "").strip()
        if code:
            codes.add(code)
    return sorted(codes, key=lambda item: (item.casefold(), item))


def _series_signature(codes: list[str]) -> str:
    return hashlib.sha256("\n".join(codes).encode("utf-8")).hexdigest()


def _minvoice_page(
    client,
    *,
    date_from: str,
    date_to: str,
    series: str,
    offset: int,
    size: int,
) -> tuple[list[dict], int]:
    result = client.get_outgoing_invoices(
        date_from,
        date_to,
        series,
        start=offset,
        count=size,
        include_details=True,
    )
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        raise MinvoiceError("M-Invoice không trả danh sách hóa đơn đầu ra đúng cấu trúc")
    items = result["data"]
    if any(not isinstance(item, dict) for item in items):
        raise MinvoiceError("M-Invoice trả một dòng hóa đơn đầu ra không đúng cấu trúc")
    raw_total = result.get("total", offset + len(items))
    if isinstance(raw_total, bool):
        raise MinvoiceError("M-Invoice trả tổng số hóa đơn không hợp lệ")
    try:
        total = int(raw_total)
    except (TypeError, ValueError):
        raise MinvoiceError("M-Invoice trả tổng số hóa đơn không hợp lệ") from None
    if total < 0 or total < offset + len(items):
        raise MinvoiceError("M-Invoice trả phân trang hóa đơn không nhất quán")
    if not items and offset < total:
        raise MinvoiceError("M-Invoice trả trang rỗng trước khi hết danh sách hóa đơn")
    return items, total


def sync_output_batch(
    conn,
    client,
    batch_id: int,
    now_iso,
    *,
    status_map: Any = None,
    status_fields: Any = None,
    reference_fields: Any = None,
    max_pages: int = 10,
    page_size: int = 199,
) -> dict[str, Any]:
    try:
        safe_batch_id = int(batch_id)
    except (TypeError, ValueError):
        raise InvoiceOutputSyncError("Mã phiên tải hóa đơn không hợp lệ") from None
    batch = conn.execute("SELECT * FROM invoice_sync_batches WHERE id=?", (safe_batch_id,)).fetchone()
    if batch is None:
        raise InvoiceOutputSyncError("Không tìm thấy phiên tải hóa đơn")
    if batch["source"] != MINVOICE_SOURCE or batch["invoice_type"] != OUTPUT_INVOICE:
        raise InvoiceOutputSyncError("Phiên này không phải hóa đơn đầu ra M-Invoice")
    active_connection = conn.execute("SELECT value FROM settings WHERE key='minvoice_active_connection'").fetchone()
    portal_client = getattr(getattr(client, "config", None), "api_mode", "legacy") == "portal"
    if active_connection and active_connection[0] == "portal" and not portal_client:
        raise InvoiceOutputSyncError("Đang chuyển sang tài khoản portal công ty; kết nối cũ không được tải thêm dữ liệu")
    if portal_client and conn.execute("""SELECT 1 FROM outgoing_source_invoices WHERE source='minvoice'
             AND COALESCE(json_extract(raw_json,'$._tdp_source_contract'),'')!='minvoice_portal_v1' LIMIT 1""").fetchone():
        raise InvoiceOutputSyncError("Cần đối chiếu và lưu dữ liệu tài khoản cũ vào lịch sử riêng trước khi tải từ portal mới")
    if (getattr(client, 'is_test_environment', False) is True
            and getattr(getattr(client, 'config', None), 'allow_test_environment', False) is not True):
        raise InvoiceOutputSyncError('M-Invoice đang dùng máy chủ kiểm thử. Hãy cấu hình URL và tài khoản '
                                     'chính thức của Thành Đạt Phát trước khi tải hóa đơn đầu ra.')
    safe_map = normalize_status_map(status_map)
    safe_fields = normalize_field_names(status_fields)
    safe_reference_fields = normalize_field_names(reference_fields)
    if not safe_reference_fields:
        safe_reference_fields = (
            "relatedInvoiceNumber",
            "inv_originalId",
            "relatedInvoiceSerial",
            "relatedInvoiceListNumber",
        )
    page_limit = max(1, min(int(max_pages), 50))
    safe_page_size = max(1, min(int(page_size), 300))
    date_from, date_to, tenant = batch["date_from"], batch["date_to"], batch["tenant"]
    series_codes = _minvoice_series_codes(client, date_from, date_to)
    signature = _series_signature(series_codes)
    try:
        cursor = json.loads(batch["source_cursor"] or "{}")
        if not isinstance(cursor, dict):
            cursor = {}
    except (ValueError, json.JSONDecodeError):
        cursor = {}
    if cursor.get("version") != 2 or cursor.get("series_signature") != signature:
        cursor = {}
    history_complete = bool(cursor.get("history_complete", cursor.get("complete", False)))
    complete = False if history_complete else bool(cursor.get("complete", False))
    series_index = max(int(cursor.get("series_index") or 0), 0)
    series_offset = max(int(cursor.get("series_offset") or 0), 0)
    if series_index >= len(series_codes):
        series_index = 0
        series_offset = 0
    reconciliation = history_complete
    new_count = known_count = item_count = review_count = pages = 0
    savepoint = "invoice_output_batch_sync"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        conn.execute(
            "UPDATE invoice_sync_batches SET status='syncing',error_code='',updated_at=? WHERE id=?",
            (now_iso(), safe_batch_id),
        )

        def consume(remote: dict) -> dict[str, Any]:
            nonlocal new_count, known_count, item_count, review_count
            invoice_id, created, normalized, review = upsert_output_invoice(
                conn,
                remote,
                tenant=tenant,
                source=MINVOICE_SOURCE,
                now=now_iso(),
                status_map=safe_map,
                status_fields=safe_fields,
                reference_fields=safe_reference_fields,
            )
            apply_saved_mappings(conn, "output", invoice_id)
            try:
                from .invoice_output_mapping import match_output_catalog_codes
            except ImportError:
                from invoice_output_mapping import match_output_catalog_codes
            match_output_catalog_codes(conn, tenant=tenant, invoice_id=invoice_id, now_iso=now_iso)
            invoice_date = str(normalized.get("invoice_date") or "")
            if invoice_date and not date_from <= invoice_date <= date_to:
                raise InvoiceOutputSyncError(
                    "Nguồn M-Invoice trả hóa đơn đầu ra ngoài khoảng ngày đã chọn; phiên đã dừng an toàn"
                )
            conn.execute(
                """INSERT INTO invoice_sync_batch_output_invoices(batch_id,invoice_id,linked_at)
                   VALUES(?,?,?) ON CONFLICT(batch_id,invoice_id) DO NOTHING""",
                (safe_batch_id, invoice_id, now_iso()),
            )
            new_count += int(created)
            known_count += int(not created)
            review_count += int(review)
            item_count += int(conn.execute(
                "SELECT COUNT(*) n FROM outgoing_source_invoice_items WHERE invoice_id=?", (invoice_id,)
            ).fetchone()["n"])
            return normalized

        while series_codes and pages < page_limit:
            code = series_codes[series_index]
            page_items, total = _minvoice_page(
                client,
                date_from=date_from,
                date_to=date_to,
                series=code,
                offset=series_offset,
                size=safe_page_size,
            )
            pages += 1
            for remote in page_items:
                consume(remote)
            next_offset = series_offset + len(page_items)
            if next_offset < total:
                series_offset = next_offset
                continue
            series_index += 1
            series_offset = 0
            if series_index < len(series_codes):
                continue
            # Initial history has now covered every series. Later calls cycle
            # through the same deterministic series list to detect cancelled,
            # replaced or adjusted invoices without creating duplicate rows.
            complete = True
            history_complete = True
            series_index = 0
            reconciliation = True
            break

        if not series_codes:
            complete = True
            history_complete = True
            series_index = 0
            series_offset = 0

        counts = _counts(conn, safe_batch_id)
        if not complete:
            status = "partial"
        elif counts["error_count"]:
            status = "quarantined"
        elif counts["needs_mapping_count"]:
            status = "needs_mapping"
        else:
            status = "ready"
        timestamp = now_iso()
        cursor_payload = json.dumps({
            "version": 2,
            "provider": MINVOICE_SOURCE,
            "series_signature": signature,
            "series_index": series_index,
            "series_offset": series_offset,
            "complete": complete,
            "history_complete": history_complete,
        }, sort_keys=True, separators=(",", ":"))
        conn.execute(
            """UPDATE invoice_sync_batches SET status=?,source_cursor=?,source_hash=?,
                      fetched_count=?,needs_mapping_count=?,ready_count=?,posted_count=?,error_count=?,
                      error_code='',updated_at=?,completed_at=? WHERE id=?""",
            (
                status, cursor_payload, _source_hash(conn, safe_batch_id), counts["fetched_count"],
                counts["needs_mapping_count"], counts["ready_count"], counts["posted_count"],
                counts["error_count"], timestamp, timestamp if complete else None, safe_batch_id,
            ),
        )
        _audit(conn, now_iso, "ok", safe_batch_id, {
            "invoice_type": OUTPUT_INVOICE,
            "source": MINVOICE_SOURCE,
            "date_from": date_from,
            "date_to": date_to,
            "pages": pages,
            "series_count": len(series_codes),
            "new_invoices": new_count,
            "known_invoices": known_count,
            "invoice_items": item_count,
            "review_required": review_count,
            "complete": complete,
            "status_contract": "minvoice_portal_v1" if portal_client else "minvoice_api_v1.0.9",
            "reconciliation": reconciliation,
        })
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return {
            "batch_id": safe_batch_id,
            "invoice_type": OUTPUT_INVOICE,
            "source": MINVOICE_SOURCE,
            "date_from": date_from,
            "date_to": date_to,
            "new_invoices": new_count,
            "known_invoices": known_count,
            "items": item_count,
            "pages": pages,
            "review_required": review_count,
            "complete": complete,
            "more_history": not complete,
            "status": status,
            "status_mapping_configured": True,
            "status_contract": "minvoice_portal_v1" if portal_client else "minvoice_api_v1.0.9",
            "series_count": len(series_codes),
            "reconciliation": reconciliation,
            **counts,
            "read_only": True,
        }
    except Exception as error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        error_code = "source_data_out_of_range" if isinstance(error, InvoiceOutputSyncError) else (
            "minvoice_source_error" if isinstance(error, (MsmiError, MinvoiceError)) else "sync_failed"
        )
        conn.execute(
            """UPDATE invoice_sync_batches SET status='error',error_count=1,error_code=?,
                      updated_at=?,completed_at=NULL WHERE id=?""",
            (error_code, now_iso(), safe_batch_id),
        )
        _audit(conn, now_iso, "error", safe_batch_id, {
            "invoice_type": OUTPUT_INVOICE,
            "source": MINVOICE_SOURCE,
            "date_from": date_from,
            "date_to": date_to,
            "error_code": error_code,
        })
        raise


def output_invoice_payload(conn, batch_id: int | None = None, *, invoice_ids=None) -> dict[str, Any]:
    if invoice_ids is None:
        batch = conn.execute("SELECT * FROM invoice_sync_batches WHERE id=?", (int(batch_id),)).fetchone()
        if (
            batch is None
            or batch["invoice_type"] != OUTPUT_INVOICE
            or batch["source"] != MINVOICE_SOURCE
        ):
            raise InvoiceOutputSyncError("Không tìm thấy phiên hóa đơn đầu ra")
        invoice_ids = [row[0] for row in conn.execute(
            "SELECT invoice_id FROM invoice_sync_batch_output_invoices WHERE batch_id=?", (int(batch_id),)
        )]
    rows = conn.execute(
        """SELECT i.* FROM outgoing_source_invoices i
           WHERE i.id IN (SELECT value FROM json_each(?))
           ORDER BY i.invoice_date DESC,i.invoice_series,i.invoice_number,i.id""",
        (json.dumps([int(value) for value in invoice_ids]),),
    ).fetchall()
    try:
        from .invoice_output_adjustments import adjustment_reviews, annotate_adjustment
        from .minvoice_portal import portal_document_role
    except ImportError:
        from invoice_output_adjustments import adjustment_reviews, annotate_adjustment
        from minvoice_portal import portal_document_role
    adjustments = {tenant:adjustment_reviews(conn,tenant) for tenant in {r['tenant'] for r in rows}}
    items = []
    for row in rows:
        invoice = dict(row)
        try:
            from .invoice_output_editing import output_mapping_allowed, output_amount_review
        except ImportError:
            from invoice_output_editing import output_mapping_allowed, output_amount_review
        invoice['can_edit_mapping'] = output_mapping_allowed(invoice)
        invoice['quantity_policy'] = 'source_quantity'
        invoice['amount_review'] = output_amount_review(invoice)
        try:
            raw = json.loads(invoice['raw_json'])
            invoice['source_document_role'] = portal_document_role(raw) if raw.get('_tdp_source_contract') == 'minvoice_portal_v1' else ''
        except (TypeError,ValueError,AttributeError):
            invoice['source_document_role'] = ''
        for key in ("identity_key", "remote_id", "business_key", "raw_json"):
            invoice.pop(key, None)
        invoice["items"] = [dict(item) for item in conn.execute(
            """SELECT li.id,li.line_index,li.source_item_code,li.source_item_name,li.source_unit,
                      li.qty,li.unit_price,li.amount,li.tax_rate,li.source_nature,
                      li.inventory_eligible,li.validation_note,li.product_code,li.mapping_status,
                      li.conversion_factor,li.stock_qty,li.stock_unit_price,
                      p.name product_name,p.unit product_unit
               FROM outgoing_source_invoice_items li LEFT JOIN products p ON p.code=li.product_code
               WHERE li.invoice_id=? ORDER BY li.line_index""",
            (row["id"],),
        )]
        try:
            from .invoice_product_identity import output_identity_warning
        except ImportError:
            from invoice_product_identity import output_identity_warning
        if invoice['stock_status'] not in {'posted', 'reversed', 'reversal_required'}:
            for item in invoice['items']:
                item['identity_warning'] = output_identity_warning(conn, item['id'])
            if any(item['identity_warning'] for item in invoice['items']) and invoice['stock_status'] == 'ready':
                invoice['stock_status'] = 'pending_mapping'
        annotate_adjustment(invoice,adjustments[row['tenant']].get(row['id']))
        items.append(invoice)
    return {
        "batch_id": int(batch_id) if batch_id is not None else None,
        "invoice_type": OUTPUT_INVOICE,
        "items": items,
        "read_only": True,
    }
