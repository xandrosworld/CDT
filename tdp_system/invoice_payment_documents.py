"""Official contractor payment-request workbook based on the approved sample.

The customer workbook establishes the visible six-column invoice table and
the legal/payment wording.  It also contains stale sheets, external VnTools
formulas and fixed blank rows, so this renderer writes reconciled literal
values, spells the amount natively and paginates dynamically.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins


class InvoicePaymentDocumentError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_invoice_payment_document", status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ").strip())


def _excel_text(value: Any) -> str:
    text = _plain(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def _strict_date(value: Any, label: str) -> date:
    text = _plain(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise InvoicePaymentDocumentError(
            f"{label} phải là ngày YYYY-MM-DD hợp lệ", code="invalid_payment_document_date",
        ) from None


def _vnd(value: Any, label: str = "Số tiền") -> int:
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise InvoicePaymentDocumentError(f"{label} không hợp lệ") from None
    if not number.is_finite():
        raise InvoicePaymentDocumentError(f"{label} không hữu hạn")
    return int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


VIET_DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")


def number_to_vietnamese(value: Any) -> str:
    number = _vnd(value)
    if number < 0:
        raise InvoicePaymentDocumentError("Tổng đề nghị thanh toán không được âm")
    if number == 0:
        return "Không đồng"

    def three_digits(group: int, full: bool = False) -> str:
        hundred, remainder = divmod(group, 100)
        ten, unit = divmod(remainder, 10)
        words: list[str] = []
        if hundred or full:
            words.extend((VIET_DIGITS[hundred], "trăm"))
        if ten > 1:
            words.extend((VIET_DIGITS[ten], "mươi"))
            if unit == 1:
                words.append("mốt")
            elif unit == 5:
                words.append("lăm")
            elif unit:
                words.append(VIET_DIGITS[unit])
        elif ten == 1:
            words.append("mười")
            if unit == 5:
                words.append("lăm")
            elif unit:
                words.append(VIET_DIGITS[unit])
        elif unit:
            if hundred or full:
                words.append("lẻ")
            words.append(VIET_DIGITS[unit])
        return " ".join(words)

    groups: list[int] = []
    while number:
        groups.append(number % 1000)
        number //= 1000
    units = ("", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ")
    if len(groups) > len(units):
        raise InvoicePaymentDocumentError("Tổng đề nghị thanh toán vượt giới hạn đọc bằng chữ")
    words: list[str] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            continue
        words.append(three_digits(group, full=bool(words) and group < 100))
        if units[index]:
            words.append(units[index])
    result = " ".join(words).strip()
    return result[:1].upper() + result[1:] + " đồng"


THIN = Side(style="thin", color="000000")
TABLE_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _font(*, size: float = 12, bold: bool = False, italic: bool = False, color: str = "000000") -> Font:
    return Font(name="Times New Roman", size=size, bold=bold, italic=italic, color=color)


def _merge_write(
    ws, cell_range: str, value: Any, *, size: float = 12, bold: bool = False,
    italic: bool = False, color: str = "000000", horizontal: str = "left",
    vertical: str = "center", wrap: bool = True,
) -> None:
    ws.merge_cells(cell_range)
    cell = ws[cell_range.split(":", 1)[0]]
    text = _plain(value)
    # openpyxl only marks leading '=' as a formula.  Keep ordinary legal
    # punctuation such as dashed separators and '- Như trên' visually clean.
    cell.value = "'" + text if text.startswith("=") else text
    cell.font = _font(size=size, bold=bold, italic=italic, color=color)
    cell.alignment = Alignment(horizontal=horizontal, vertical=vertical, wrap_text=wrap)


def _validated_scope(scope: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    invoices = list(scope.get("invoices") or [])
    snapshot = dict(scope.get("snapshot") or {})
    totals = dict(scope.get("totals") or {})
    if not invoices:
        raise InvoicePaymentDocumentError("Không có hóa đơn đã phát hành để lập đề nghị")
    required_snapshot = (
        "buyer_name_snapshot", "buyer_tax_code_snapshot", "buyer_address_snapshot",
        "company_name_snapshot", "company_tax_code_snapshot", "company_address_snapshot",
        "payment_bank_name_snapshot", "payment_bank_account_snapshot",
    )
    missing = [name for name in required_snapshot if not _plain(snapshot.get(name))]
    if missing:
        raise InvoicePaymentDocumentError("Thiếu hồ sơ pháp lý hoặc thanh toán đã khóa cùng hóa đơn")
    computed = {
        "subtotal": sum(_vnd(item.get("subtotal")) for item in invoices),
        "tax_amount": sum(_vnd(item.get("tax_amount")) for item in invoices),
        "total_amount": sum(_vnd(item.get("total_amount")) for item in invoices),
    }
    expected = {key: _vnd(totals.get(key)) for key in computed}
    if computed != expected or expected["total_amount"] <= 0:
        raise InvoicePaymentDocumentError(
            "Tổng đề nghị thanh toán không khớp phạm vi hóa đơn",
            code="payment_document_total_mismatch",
        )
    identities: set[tuple[str, str, str]] = set()
    for item in invoices:
        invoice_date = _strict_date(item.get("invoice_date"), "Ngày hóa đơn").isoformat()
        number = _plain(item.get("invoice_number"))
        series = _plain(item.get("invoice_series")).upper()
        if not number:
            raise InvoicePaymentDocumentError("Hóa đơn thiếu số hóa đơn")
        identity = (invoice_date, series, number)
        if identity in identities:
            raise InvoicePaymentDocumentError(
                "Phạm vi có hóa đơn bị lặp", code="payment_document_duplicate_invoice",
            )
        identities.add(identity)
    return invoices, snapshot, expected


def invoice_payment_request_workbook(
    scope: dict[str, Any], *, issue_date: Any | None = None,
    request_number: Any = "……/CV/ĐNTT", contract_no: Any = "", contract_date: Any = "",
) -> Workbook:
    """Create one official, print-ready payment request for one contractor."""
    invoices, snapshot, totals = _validated_scope(scope)
    period_from = _strict_date(scope.get("date_from"), "Từ ngày")
    period_to = _strict_date(scope.get("date_to"), "Đến ngày")
    if period_from > period_to:
        raise InvoicePaymentDocumentError("Từ ngày không được lớn hơn Đến ngày")
    issued_on = _strict_date(issue_date or period_to.isoformat(), "Ngày lập")
    safe_contract_date = None
    if _plain(contract_date):
        safe_contract_date = _strict_date(contract_date, "Ngày hợp đồng")
    safe_contract_no = _plain(contract_no)

    workbook = Workbook()
    workbook.properties.title = (
        f"Đề nghị thanh toán {_plain(scope.get('contractor'))} "
        f"{period_from.isoformat()} - {period_to.isoformat()}"
    )
    workbook.properties.subject = "Đề nghị thanh toán từ hóa đơn đỏ đã phát hành"
    workbook.properties.creator = "Thành Đạt Phát"
    workbook.calculation.fullCalcOnLoad = False
    workbook.calculation.forceFullCalc = False
    workbook.calculation.calcMode = "manual"
    ws = workbook.active
    ws.title = "Đề nghị thanh toán"
    ws.sheet_view.showGridLines = False
    widths = (8, 16, 14, 19, 18, 21)
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width

    _merge_write(ws, "A1:C1", snapshot["company_name_snapshot"].upper(), size=12, bold=True, horizontal="center")
    _merge_write(ws, "D1:F1", "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", size=12, bold=True, horizontal="center")
    _merge_write(ws, "A2:C2", request_number, size=12, horizontal="center")
    _merge_write(ws, "D2:F2", "Độc lập – Tự do – Hạnh phúc", size=12, bold=True, horizontal="center")
    _merge_write(ws, "A3:C3", "V/v: Đề nghị thanh toán", size=12, italic=True, horizontal="center")
    _merge_write(ws, "D3:F3", "----------------", size=12, horizontal="center")
    ws.row_dimensions[1].height = 34
    ws.row_dimensions[2].height = 22
    ws.row_dimensions[3].height = 22
    _merge_write(
        ws, "D4:F4",
        f"Hải Phòng, ngày {issued_on.day:02d} tháng {issued_on.month:02d} năm {issued_on.year}",
        size=12, italic=True, color="FF0000", horizontal="center",
    )
    _merge_write(ws, "A6:F6", "ĐỀ NGHỊ THANH TOÁN", size=16, bold=True, horizontal="center")
    _merge_write(
        ws, "A7:F7", f"Kính gửi: {snapshot['buyer_name_snapshot'].upper()}",
        size=12, bold=True, horizontal="center",
    )
    if safe_contract_no:
        contract_text = f"Căn cứ vào hợp đồng mua bán số: {safe_contract_no}"
        if safe_contract_date:
            contract_text += (
                f" ngày {safe_contract_date.day:02d} tháng {safe_contract_date.month:02d} "
                f"năm {safe_contract_date.year}"
            )
        contract_text += (
            f" giữa {snapshot['buyer_name_snapshot']} và {snapshot['company_name_snapshot']}."
        )
    else:
        contract_text = (
            f"Căn cứ hàng hóa đã cung cấp giữa {snapshot['buyer_name_snapshot']} "
            f"và {snapshot['company_name_snapshot']}."
        )
    _merge_write(ws, "A9:F9", contract_text, size=12, color="FF0000", horizontal="left")
    ws.row_dimensions[9].height = 34
    narrative = (
        f"Thời gian từ ngày {period_from.strftime('%d/%m/%Y')} – {period_to.strftime('%d/%m/%Y')} "
        f"chúng tôi đã cung cấp hàng hóa cho {snapshot['buyer_name_snapshot']}, dựa theo số lượng "
        "bàn giao chúng tôi đã xuất hóa đơn như sau:"
    )
    _merge_write(ws, "A11:F12", narrative, size=12, horizontal="left", vertical="top")
    ws.row_dimensions[11].height = 24
    ws.row_dimensions[12].height = 24

    header_row = 14
    headers = (
        "STT", "Ngày hóa đơn", "Số hóa đơn", "Tổng tiền trước thuế",
        "Tổng tiền thuế", "Tổng tiền thanh toán",
    )
    for column, value in enumerate(headers, 1):
        cell = ws.cell(header_row, column, value)
        cell.font = _font(size=11, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = TABLE_BORDER
    ws.row_dimensions[header_row].height = 36
    for index, item in enumerate(invoices, start=1):
        row = header_row + index
        invoice_date = _strict_date(item.get("invoice_date"), "Ngày hóa đơn")
        values = (
            index, invoice_date, _excel_text(item.get("invoice_number")),
            _vnd(item.get("subtotal")), _vnd(item.get("tax_amount")),
            _vnd(item.get("total_amount")),
        )
        for column, value in enumerate(values, 1):
            cell = ws.cell(row, column, value)
            cell.font = _font(size=11)
            cell.border = TABLE_BORDER
            cell.alignment = Alignment(
                horizontal="right" if column >= 4 else "center", vertical="center",
            )
        ws.cell(row, 2).number_format = "dd/mm/yyyy"
        for column in (4, 5, 6):
            ws.cell(row, column).number_format = '#,##0;[Red]-#,##0;"-"'
        ws.row_dimensions[row].height = 22

    total_row = header_row + len(invoices) + 1
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=3)
    ws.cell(total_row, 1, "Tổng cộng")
    ws.cell(total_row, 1).font = _font(size=11, bold=True)
    ws.cell(total_row, 1).alignment = Alignment(horizontal="center", vertical="center")
    for column, key in zip((4, 5, 6), ("subtotal", "tax_amount", "total_amount")):
        ws.cell(total_row, column, totals[key])
        ws.cell(total_row, column).number_format = '#,##0;[Red]-#,##0;"-"'
    for column in range(1, 7):
        ws.cell(total_row, column).border = TABLE_BORDER
        ws.cell(total_row, column).font = _font(size=11, bold=True)
    ws.row_dimensions[total_row].height = 24

    words_row = total_row + 2
    _merge_write(
        ws, f"A{words_row}:F{words_row}",
        "Bằng chữ:    " + number_to_vietnamese(totals["total_amount"]) + "./.",
        size=11, bold=True, italic=True,
    )
    payment_rows = (
        "Vậy kính mong quý Công ty thanh toán cho chúng tôi bằng chuyển khoản theo thông tin tài khoản sau:",
        f"Tên tài khoản: {snapshot['company_name_snapshot'].upper()}",
        f"Số tài khoản: {snapshot['payment_bank_account_snapshot']}  Tại {snapshot['payment_bank_name_snapshot']}",
        "Rất mong nhận được sự hợp tác từ quý công ty!",
        "Trân trọng cảm ơn!",
    )
    for offset, text in enumerate(payment_rows, start=2):
        row = words_row + offset
        _merge_write(ws, f"A{row}:F{row}", text, size=11, bold=offset in (3, 4))
        ws.row_dimensions[row].height = 20

    signature_row = words_row + 8
    _merge_write(ws, f"A{signature_row}:C{signature_row}", "Nơi nhận", size=11, italic=True, horizontal="center")
    _merge_write(ws, f"D{signature_row}:F{signature_row}", "ĐẠI DIỆN CÔNG TY", size=11, bold=True, horizontal="center")
    _merge_write(ws, f"A{signature_row + 1}:C{signature_row + 2}", "- Như trên;\n- Lưu VP;", size=11, italic=True, horizontal="center", vertical="top")
    _merge_write(ws, f"D{signature_row + 1}:F{signature_row + 2}", "(Ký, họ tên, đóng dấu)", size=11, italic=True, horizontal="center", vertical="top")

    ws.print_area = f"A1:F{signature_row + 7}"
    ws.print_title_rows = f"{header_row}:{header_row}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.scale = None
    ws.page_margins = PageMargins(left=0.55, right=0.45, top=0.45, bottom=0.45, header=0.15, footer=0.15)
    ws.print_options.horizontalCentered = True
    ws.oddFooter.center.text = "Trang &P / &N"

    proof = workbook.create_sheet("Đối chiếu hóa đơn")
    proof.append([
        "Ngày HĐ", "Ký hiệu", "Số HĐ", "Trước thuế", "Thuế", "Tổng",
        "Nguồn xác minh", "ID nguồn", "ID draft",
    ])
    for item in invoices:
        proof.append([
            _strict_date(item.get("invoice_date"), "Ngày hóa đơn"),
            _excel_text(item.get("invoice_series")), _excel_text(item.get("invoice_number")),
            _vnd(item.get("subtotal")), _vnd(item.get("tax_amount")),
            _vnd(item.get("total_amount")), _excel_text(item.get("verification_source")),
            item.get("source_invoice_id") or "", item.get("draft_id") or "",
        ])
    proof.append(["TỔNG", "", "", totals["subtotal"], totals["tax_amount"], totals["total_amount"], "", "", ""])
    for cell in proof[1]:
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17324D")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in proof.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial", size=9, bold=cell.row == proof.max_row)
            cell.border = TABLE_BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    for column in (4, 5, 6):
        for row in range(2, proof.max_row + 1):
            proof.cell(row, column).number_format = "#,##0"
    for column, width in enumerate((14, 15, 15, 17, 15, 18, 24, 14, 12), start=1):
        proof.column_dimensions[get_column_letter(column)].width = width
    proof.freeze_panes = "A2"
    proof.auto_filter.ref = f"A1:I{proof.max_row - 1}"
    proof.sheet_state = "hidden"
    return workbook


__all__ = [
    "InvoicePaymentDocumentError", "invoice_payment_request_workbook",
    "number_to_vietnamese",
]
