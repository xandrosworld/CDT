"""Invoice-only scope for official contractor payment documents.

The customer supplied the approved payment-request workbook on 03/09/2026.
This module freezes and reconciles the financial/source scope before the
official request and delivery statement are rendered from literal values.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


SNAPSHOT_FIELDS = (
    "buyer_name_snapshot",
    "buyer_tax_code_snapshot",
    "buyer_address_snapshot",
    "company_name_snapshot",
    "company_tax_code_snapshot",
    "company_address_snapshot",
    "payment_requester_snapshot",
    "payment_bank_name_snapshot",
    "payment_bank_account_snapshot",
)


class InvoicePaymentScopeError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_invoice_payment_scope", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _strict_date(value: Any, label: str) -> str:
    text = _plain(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise InvoicePaymentScopeError(
            f"{label} phải đúng dạng YYYY-MM-DD", code="invalid_date_range", status=400,
        ) from None


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise InvoicePaymentScopeError(f"{label} không hợp lệ")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise InvoicePaymentScopeError(f"{label} không phải số hữu hạn") from None
    if not math.isfinite(result):
        raise InvoicePaymentScopeError(f"{label} không phải số hữu hạn")
    return result


def _vnd(*values: Any) -> int:
    try:
        result = Decimal("1")
        for value in values:
            result *= Decimal(str(value))
        return int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        raise InvoicePaymentScopeError("Không thể làm tròn số tiền hóa đơn") from None


def _tax_percent(value: Any) -> float:
    text = _plain(value).upper().replace(" ", "")
    if text in {"", "KKKNT", "KHÔNGKÊKHAI", "KHONGKEKHAI", "-2", "-2.0"}:
        return -2 if text else 0
    if text in {"KCT", "KHÔNGCHỊUTHUẾ", "KHONGCHIUTHUE", "-1", "-1.0"}:
        return -1
    if text.endswith("%"):
        text = text[:-1]
    try:
        result = float(text)
    except ValueError:
        raise InvoicePaymentScopeError("Dòng hóa đơn có thuế suất không hợp lệ") from None
    if 0 < abs(result) < 1:
        result *= 100
    if not math.isfinite(result) or result < 0 or result > 100:
        raise InvoicePaymentScopeError("Dòng hóa đơn có thuế suất không hợp lệ")
    return result


def _table_exists(conn, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,),
    ).fetchone())


def _source_match(conn, draft: dict[str, Any]) -> dict[str, Any] | None:
    if not _table_exists(conn, "outgoing_source_invoices"):
        return None
    rows = [dict(row) for row in conn.execute(
        """SELECT id,source,source_status_class,sync_status,stock_status,
                  invoice_series,invoice_number,invoice_date,subtotal,tax_amount,total_amount,
                  buyer_tax_code,buyer_name,relation_reference,error_message
             FROM outgoing_source_invoices
            WHERE source='minvoice'
              AND UPPER(TRIM(COALESCE(invoice_series,'')))=UPPER(TRIM(?))
              AND TRIM(COALESCE(invoice_number,''))=TRIM(?)
              AND TRIM(COALESCE(invoice_date,''))=TRIM(?)
            ORDER BY id""",
        (
            draft.get("issued_invoice_series") or "",
            draft.get("issued_invoice_number") or "",
            draft.get("issued_invoice_date") or "",
        ),
    )]
    if len(rows) > 1:
        raise InvoicePaymentScopeError(
            "Một định danh hóa đơn khớp nhiều bản nguồn; cần đối chiếu trước khi lập hồ sơ",
            code="invoice_source_identity_conflict",
        )
    return rows[0] if rows else None


def _verify_source(draft: dict[str, Any], source: dict[str, Any] | None) -> dict[str, Any]:
    if source is None:
        return {
            "verification_source": "local_issued_confirmation",
            "source_invoice_id": None,
            "source_status_class": "not_synced",
            "source_stock_status": "not_synced",
        }
    if source["source_status_class"] != "issued" or source["sync_status"] != "synced" or source[
        "stock_status"
    ] in {"blocked", "reversal_required", "reversed"}:
        raise InvoicePaymentScopeError(
            "Hóa đơn nguồn đã hủy/thay thế/điều chỉnh hoặc đang chờ đối chiếu; không được đưa vào đề nghị thanh toán",
            code="invoice_source_not_payable",
        )
    source_tax_code = _plain(source.get("buyer_tax_code")).upper()
    snapshot_tax_code = _plain(draft.get("buyer_tax_code_snapshot")).upper()
    if source_tax_code and snapshot_tax_code and source_tax_code != snapshot_tax_code:
        raise InvoicePaymentScopeError(
            "Mã số thuế bên mua trên hóa đơn nguồn lệch snapshot đã phát hành",
            code="invoice_source_buyer_mismatch",
        )
    local_totals = tuple(_vnd(draft[field]) for field in ("subtotal", "tax_amount", "total_amount"))
    source_totals = tuple(_vnd(source[field]) for field in ("subtotal", "tax_amount", "total_amount"))
    if any(abs(left - right) > 1 for left, right in zip(local_totals, source_totals)):
        raise InvoicePaymentScopeError(
            "Tổng hóa đơn xác nhận cục bộ lệch bản nguồn; cần đối chiếu trước khi lập hồ sơ",
            code="invoice_source_total_mismatch",
        )
    return {
        "verification_source": "synced_issued_source",
        "source_invoice_id": int(source["id"]),
        "source_status_class": source["source_status_class"],
        "source_stock_status": source["stock_status"],
    }


def _verify_lines(drafts: list[dict[str, Any]], lines: list[dict[str, Any]]) -> None:
    totals: dict[int, dict[str, int]] = {
        int(draft["id"]): {"subtotal": 0, "tax": 0, "total": 0} for draft in drafts
    }
    for line in lines:
        draft_id = int(line["draft_id"])
        if draft_id not in totals:
            raise InvoicePaymentScopeError("Dòng giao hàng không thuộc phạm vi hóa đơn đã khóa")
        qty = _number(line.get("qty"), "Số lượng hóa đơn")
        unit_price = _number(line.get("unit_price"), "Đơn giá hóa đơn")
        amount = _vnd(line.get("amount"))
        if qty <= 0 or unit_price < 0 or amount < 0 or _vnd(qty, unit_price) != amount:
            raise InvoicePaymentScopeError(
                "Dòng hóa đơn không thỏa Số lượng × Đơn giá = Thành tiền",
                code="invoice_line_amount_mismatch",
            )
        tax_percent = _tax_percent(line.get("tax"))
        tax_amount = 0 if tax_percent <= 0 else _vnd(amount, tax_percent / 100)
        totals[draft_id]["subtotal"] += amount
        totals[draft_id]["tax"] += tax_amount
        totals[draft_id]["total"] += amount + tax_amount
    mismatches = []
    for draft in drafts:
        calculated = totals[int(draft["id"])]
        expected = {
            "subtotal": _vnd(draft["subtotal"]),
            "tax": _vnd(draft["tax_amount"]),
            "total": _vnd(draft["total_amount"]),
        }
        if any(abs(calculated[key] - expected[key]) > 1 for key in expected):
            mismatches.append(_plain(draft.get("issued_invoice_number")) or str(draft["id"]))
    if mismatches:
        raise InvoicePaymentScopeError(
            "Tổng hóa đơn lệch chi tiết giao hàng: " + ", ".join(mismatches),
            code="invoice_delivery_total_mismatch",
        )


def _local_issued_payment_scope(
    conn,
    contractor: Any,
    date_from: Any,
    date_to: Any,
) -> dict[str, Any]:
    """Return a reconciled, invoice-only payment scope with explicit provenance."""
    safe_from = _strict_date(date_from, "Từ ngày")
    safe_to = _strict_date(date_to, "Đến ngày")
    if safe_from > safe_to:
        raise InvoicePaymentScopeError(
            "Từ ngày không được sau đến ngày", code="invalid_date_range", status=400,
        )
    party = _plain(contractor).upper()
    if not party:
        raise InvoicePaymentScopeError("Cần mã nhà thầu", code="contractor_required", status=400)
    drafts = [dict(row) for row in conn.execute(
        """SELECT * FROM outgoing_invoice_drafts
            WHERE UPPER(TRIM(contractor))=? AND status='issued'
              AND issued_invoice_date BETWEEN ? AND ?
            ORDER BY issued_invoice_date,issued_invoice_series,issued_invoice_number,id""",
        (party, safe_from, safe_to),
    )]
    if not drafts:
        raise InvoicePaymentScopeError(
            "Không có hóa đơn đã phát hành đủ số/ngày trong kỳ",
            code="issued_invoice_scope_empty",
            status=404,
        )
    for draft in drafts:
        if not _plain(draft.get("issued_invoice_number")) or not _plain(draft.get("issued_invoice_date")):
            raise InvoicePaymentScopeError(
                "Còn hóa đơn chưa ghi đủ số/ngày phát hành",
                code="issued_invoice_identity_incomplete",
            )
        missing = [field for field in SNAPSHOT_FIELDS if not _plain(draft.get(field))]
        if missing:
            raise InvoicePaymentScopeError(
                "Hóa đơn cũ chưa khóa đủ hồ sơ pháp lý/thanh toán; không dùng hồ sơ hiện tại ghi đè lịch sử",
                code="issued_invoice_snapshot_incomplete",
            )
    snapshot_keys = {
        tuple(_plain(draft.get(field)) for field in SNAPSHOT_FIELDS) for draft in drafts
    }
    if len(snapshot_keys) != 1:
        raise InvoicePaymentScopeError(
            "Các hóa đơn trong kỳ thuộc hồ sơ pháp lý/thanh toán khác nhau; hãy xuất tách kỳ",
            code="issued_invoice_snapshot_conflict",
        )

    draft_ids = [int(draft["id"]) for draft in drafts]
    placeholders = ",".join("?" for _ in draft_ids)
    lines = [dict(row) for row in conn.execute(
        f"""SELECT l.*,d.issued_invoice_number,d.issued_invoice_series,d.issued_invoice_date,
                    d.subtotal invoice_subtotal,d.tax_amount invoice_tax_amount,
                    d.total_amount invoice_total,b.work_date,o.kitchen
               FROM outgoing_order_allocations l
               JOIN outgoing_invoice_drafts d ON d.id=l.draft_id
               JOIN orders o ON o.id=l.order_id
               JOIN batches b ON b.id=o.batch_id
              WHERE l.draft_id IN ({placeholders})
              ORDER BY d.issued_invoice_date,d.id,b.work_date,l.id""",
        tuple(draft_ids),
    )]
    if not lines:
        raise InvoicePaymentScopeError(
            "Hóa đơn đã phát hành không còn dòng giao hàng để đối chiếu",
            code="issued_invoice_lines_missing",
        )
    invoice_lines = [dict(r) for r in conn.execute(
        f'SELECT * FROM outgoing_invoice_lines WHERE draft_id IN ({placeholders})',tuple(draft_ids))]
    _verify_lines(drafts, invoice_lines)

    invoices = []
    for draft in drafts:
        source = _source_match(conn, draft)
        provenance = _verify_source(draft, source)
        invoices.append({
            "draft_id": int(draft["id"]),
            "invoice_date": draft["issued_invoice_date"],
            "invoice_series": _plain(draft.get("issued_invoice_series")),
            "invoice_number": _plain(draft.get("issued_invoice_number")),
            "subtotal": _vnd(draft["subtotal"]),
            "tax_amount": _vnd(draft["tax_amount"]),
            "total_amount": _vnd(draft["total_amount"]),
            **provenance,
        })
    totals = {
        "subtotal": sum(item["subtotal"] for item in invoices),
        "tax_amount": sum(item["tax_amount"] for item in invoices),
        "total_amount": sum(item["total_amount"] for item in invoices),
    }
    if totals["total_amount"] <= 0:
        raise InvoicePaymentScopeError(
            "Tổng đề nghị từ hóa đơn phải lớn hơn 0",
            code="invoice_payment_total_not_positive",
        )
    scope_payload = {
        "contractor": party,
        "date_from": safe_from,
        "date_to": safe_to,
        "invoices": invoices,
        "line_fingerprint": [
            {
                "draft_id": int(line["draft_id"]),
                "order_id": int(line["order_id"]),
                "product_code": _plain(line.get("product_code")),
                "product_name": _plain(line.get("product_name")),
                "unit": _plain(line.get("unit")),
                "kitchen": _plain(line.get("kitchen")),
                "work_date": _plain(line.get("work_date")),
                "invoice_nature": _plain(line.get("invoice_nature")),
                "qty": round(_number(line.get("qty"), "Số lượng"), 9),
                "unit_price": _vnd(line.get("unit_price")),
                "amount": _vnd(line.get("amount")),
                "tax": _plain(line.get("tax")),
            }
            for line in lines
        ],
        "totals": totals,
    }
    frozen_snapshot = {field: drafts[0][field] for field in SNAPSHOT_FIELDS}
    scope_id = hashlib.sha256(json.dumps(
        {**scope_payload, "snapshot": frozen_snapshot},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest().upper()
    return {
        **scope_payload,
        "scope_id": scope_id,
        "drafts": drafts,
        "lines": lines,
        "snapshot": frozen_snapshot,
        "template_status": "official_customer_xlsx",
        "official_template_ready": True,
        "warning": (
            "Số liệu chỉ lấy từ hóa đơn đỏ đã phát hành và đã đối chiếu. "
            "Nếu phạm vi thay đổi sau khi xem trước, hệ thống sẽ chặn file cũ."
        ),
    }


def issued_invoice_payment_scope(conn, contractor, date_from, date_to):
    """Union local issued invoices and verified source invoices, once per identity.

    Source invoices have no invented delivery date, order or kitchen. Their
    payment pack uses an invoice statement and says why it is not delivery proof.
    """
    try:
        local = _local_issued_payment_scope(conn, contractor, date_from, date_to)
    except InvoicePaymentScopeError as exc:
        if exc.code != 'issued_invoice_scope_empty':
            raise
        local = None
    party = _plain(contractor).upper()
    safe_from, safe_to = _strict_date(date_from, 'Từ ngày'), _strict_date(date_to, 'Đến ngày')
    profile = conn.execute('SELECT * FROM outgoing_buyer_profiles WHERE UPPER(TRIM(contractor))=?', (party,)).fetchone()
    tax_code = _plain(dict(profile).get('tax_code')) if profile else ''
    sources = [dict(r) for r in conn.execute(
        "SELECT * FROM outgoing_source_invoices WHERE source='minvoice' "
        "AND UPPER(TRIM(buyer_tax_code))=? AND invoice_date BETWEEN ? AND ? ORDER BY invoice_date,id",
        (tax_code.upper(), safe_from, safe_to),
    )] if tax_code and _table_exists(conn, 'outgoing_source_invoices') else []
    matched_ids = {i['source_invoice_id'] for i in local['invoices'] if i.get('source_invoice_id')} if local else set()
    sources = [r for r in sources if r['id'] not in matched_ids]
    # Unissued source drafts do not create a payment obligation. A local invoice
    # claiming issued against a source draft was already rejected above.
    excluded_drafts = sum(r['source_status_class'] == 'draft' for r in sources)
    sources = [r for r in sources if r['source_status_class'] != 'draft']
    if not sources:
        if local:
            return local
        raise InvoicePaymentScopeError(
            'Không có hóa đơn VAT đã phát hành trong kỳ của nhà thầu. Hãy tải hóa đơn đầu ra '
            'và kiểm tra mã số thuế trong hồ sơ người mua.', code='issued_invoice_scope_empty', status=404)
    profiles = conn.execute('SELECT contractor FROM outgoing_buyer_profiles WHERE UPPER(TRIM(tax_code))=?',
                            (tax_code.upper(),)).fetchall()
    if len(profiles) != 1:
        raise InvoicePaymentScopeError('Mã số thuế thuộc nhiều nhà thầu; cần đối chiếu liên kết hóa đơn trước khi lập hồ sơ.',
                                       code='invoice_source_buyer_ambiguous')
    settings = {r['key']: r['value'] for r in conn.execute('SELECT key,value FROM settings')}
    invoices = list(local['invoices']) if local else []
    source_lines = []
    snapshot = dict(local['snapshot']) if local else None
    identities = {(i['invoice_series'].upper(), i['invoice_number'].lstrip('0') or '0', i['invoice_date'])
                  for i in invoices}
    for source in sources:
        # Do not silently drop an in-period cancellation/replacement/uncertain invoice.
        if source['source_status_class'] != 'issued' or source['sync_status'] != 'synced' or source['stock_status'] in {
            'blocked', 'reversal_required', 'reversed'
        } or source['relation_reference']:
            raise InvoicePaymentScopeError('Có hóa đơn nguồn bị hủy/thay thế/điều chỉnh hoặc cần đối chiếu trong kỳ; '
                                           'hãy kiểm tra trạng thái trước khi lập hồ sơ.', code='invoice_source_not_payable')
        if not _plain(source['invoice_number']) or not _plain(source['invoice_series']):
            raise InvoicePaymentScopeError('Hóa đơn nguồn thiếu số hoặc ký hiệu.', code='issued_invoice_identity_incomplete')
        identity = (source['invoice_series'].strip().upper(), source['invoice_number'].strip().lstrip('0') or '0', source['invoice_date'])
        if identity in identities:
            raise InvoicePaymentScopeError('Định danh hóa đơn bị trùng giữa các nguồn; cần đối chiếu.',
                                           code='invoice_source_identity_conflict')
        identities.add(identity)
        raw = json.loads(source['raw_json'])
        address = _plain(raw.get('inv_buyerAddressLine') or raw.get('inv_buyerAddress') or raw.get('buyerAddress') or raw.get('nmdchi'))
        if not address or not _plain(source['buyer_name']):
            raise InvoicePaymentScopeError('Hóa đơn nguồn thiếu tên hoặc địa chỉ người mua; tải lại chi tiết hóa đơn.',
                                           code='invoice_source_buyer_incomplete')
        source_snapshot = {
            'buyer_name_snapshot': _plain(source['buyer_name']), 'buyer_tax_code_snapshot': tax_code,
            'buyer_address_snapshot': address,
            **{field + '_snapshot': _plain(settings.get(field)) for field in (
                'company_tax_code', 'company_address', 'payment_requester', 'payment_bank_name', 'payment_bank_account')},
            'company_name_snapshot': _plain(settings.get('company')),
        }
        if any(not source_snapshot[field] for field in SNAPSHOT_FIELDS):
            raise InvoicePaymentScopeError('Cần điền đủ hồ sơ công ty và thông tin thanh toán trước khi lập đề nghị.',
                                           code='invoice_payment_settings_incomplete')
        if snapshot is not None and any(_plain(snapshot[f]) != source_snapshot[f] for f in SNAPSHOT_FIELDS):
            raise InvoicePaymentScopeError('Các hóa đơn có hồ sơ người mua hoặc thanh toán khác nhau; cần xuất tách kỳ.',
                                           code='issued_invoice_snapshot_conflict')
        snapshot = source_snapshot
        items = [dict(r) for r in conn.execute(
            'SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index', (source['id'],))]
        if not items or abs(sum(_number(r['amount'], 'Tiền dòng hóa đơn') for r in items) - source['subtotal']) > 1:
            raise InvoicePaymentScopeError('Thiếu chi tiết hoặc tiền chi tiết lệch tổng hóa đơn nguồn; tải lại và đối chiếu.',
                                           code='invoice_source_total_mismatch')
        if abs(_number(source['subtotal'], 'Trước thuế') + _number(source['tax_amount'], 'Thuế')
               - _number(source['total_amount'], 'Thanh toán')) > 1 or source['total_amount'] <= 0:
            raise InvoicePaymentScopeError('Tổng tiền hóa đơn nguồn không khớp trước thuế cộng thuế.',
                                           code='invoice_source_total_mismatch')
        invoices.append({
            'draft_id': None, 'invoice_date': source['invoice_date'], 'invoice_series': source['invoice_series'],
            'invoice_number': source['invoice_number'],
            **{k: _vnd(source[k]) for k in ('subtotal', 'tax_amount', 'total_amount')},
            'verification_source': 'synced_issued_source', 'source_invoice_id': source['id'],
            'source_status_class': source['source_status_class'], 'source_stock_status': source['stock_status'],
        })
        source_lines.extend({**item, 'invoice_date': source['invoice_date'], 'invoice_series': source['invoice_series'],
                             'invoice_number': source['invoice_number']} for item in items)
    invoices.sort(key=lambda i: (i['invoice_date'], i['invoice_series'], i['invoice_number']))
    result = {
        'contractor': party, 'date_from': safe_from, 'date_to': safe_to, 'invoices': invoices,
        'totals': {k: sum(i[k] for i in invoices) for k in ('subtotal', 'tax_amount', 'total_amount')},
        'snapshot': snapshot, 'drafts': local['drafts'] if local else [], 'lines': local['lines'] if local else [],
        'source_lines': source_lines, 'statement_kind': 'invoices',
        'excluded_draft_count': excluded_drafts,
        'template_status': 'official_customer_xlsx', 'official_template_ready': True,
        'warning': 'Số tiền lấy từ hóa đơn VAT đã phát hành. Thông tin nhận tiền là cấu hình tại lúc lập đề nghị. '
                   'Có hóa đơn chưa liên kết bếp/ngày giao: bảng kê theo ngày hóa đơn, không xác nhận lịch sử giao nhận.' +
                   (f' Đã loại {excluded_drafts} dự thảo chưa phát hành khỏi số tiền đề nghị.' if excluded_drafts else ''),
    }
    result['scope_id'] = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest().upper()
    return result


def public_payment_scope(scope: dict[str, Any]) -> dict[str, Any]:
    """Remove internal rendering rows while keeping the full proof summary."""
    return {
        key: value for key, value in scope.items()
        if key not in {"drafts", "lines", "snapshot", "line_fingerprint", "source_lines"}
    }


__all__ = [
    "InvoicePaymentScopeError",
    "SNAPSHOT_FIELDS",
    "issued_invoice_payment_scope",
    "public_payment_scope",
]
