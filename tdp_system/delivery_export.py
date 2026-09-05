"""Template-preserving delivery-note export.

The approved delivery note is the ``đơn hàng đi giao`` sheet in
``Em Thành.xlsx``.  This module clones that sheet for every kitchen, removes
all example business values, and writes only the current delivery literals.
The template's photographed signature footer is replaced with native Excel
cells so the customer can edit the wording and print it sharply.
"""

from __future__ import annotations

import math
import re
from copy import copy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.pagebreak import Break, RowBreak

try:
    from document_totals import quantity_cell
    from document_preview import white_print_style
except ImportError:
    from .document_totals import quantity_cell
    from .document_preview import white_print_style

try:
    from template_workbook import (
        TemplateWorkbookError,
        assert_workbook_safe,
        clone_template_workbook,
        write_literal,
    )
except ImportError:  # pragma: no cover - package import path
    from .template_workbook import (
        TemplateWorkbookError,
        assert_workbook_safe,
        clone_template_workbook,
        write_literal,
    )


DELIVERY_TEMPLATE_SHEET = "đơn hàng đi giao"
EM_THANH_SHA256 = "66808CD910F63F4D543A72CC51DDAEBA1C60B147E0457FEAFC5BAD65EAD26AD3"

# Proven unique by both the approved T.chiếu row and the transferred database.
# Requiring the exact pair makes a stale flag or a kitchen name containing
# "Nhựa" fail closed instead of exposing selling prices on the wrong note.
PRICE_VISIBLE_KITCHEN = "NHUAHP"
PRICE_VISIBLE_CONTRACTOR = "NHUAHAIPHONG"

SOURCE_TABLE_HEADER_ROW = 8
SOURCE_TABLE_FIRST_ROW = 9
TABLE_HEADER_ROW = 10
TABLE_FIRST_ROW = 11
GOLDEN_LAST_ITEM_ROW = 26
GOLDEN_TOTAL_ROW = 27
GOLDEN_SIGNATURE_FROM_ROW = 27  # zero-based drawing anchor: Excel row 28
SIGNATURE_PRINT_ROWS = 8
SIGNATURE_DATE_TEXT = "Ngày ..... tháng ..... năm ........"
SIGNATURE_TITLES_TEXT = (
    "Trực ban\u2003\u2003\u2003\u2003\u2003Bảo vệ\u2003\u2003\u2003\u2003\u2003"
    "Người giao hàng\u2003\u2003\u2003\u2003\u2003Người nhận hàng"
)
SIGNATURE_HINTS_TEXT = (
    # The four titles have different visual widths. Use matching inter-group
    # spacing (plus a small trailing pad) so every hint is centred below its
    # own title in the fixed Arial footer, instead of the whole hint line
    # bunching toward the middle of the page.
    "(Ký và ghi rõ họ tên)\u2003\u2003\u2003\u2003(Ký và ghi rõ họ tên)"
    "\u2003\u2003\u2003\u2003\u2003\u2003\u2003(Ký và ghi rõ họ tên)"
    "\u2003\u2003\u2003\u2003\u2003\u2003\u2003\u2003\u2003\u2003\u2003"
    "(Ký và ghi rõ họ tên)\u2003\u2003"
)
DELIVERY_MAX_ITEMS_PER_PAGE = 20

INVALID_SHEET_CHARACTER = re.compile(r"[\\/*?:\[\]]")


class DeliveryExportError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_delivery", status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


def delivery_prices_visible(kitchen: Any, contractor: Any) -> bool:
    """Return true only for the source-backed Nhựa kitchen/contractor pair."""

    return (
        str(kitchen or "").strip().upper() == PRICE_VISIBLE_KITCHEN
        and str(contractor or "").strip().upper() == PRICE_VISIBLE_CONTRACTOR
    )


def _finite_number(value: Any, label: str) -> int | float:
    if isinstance(value, bool):
        raise DeliveryExportError(f"{label} phải là số hữu hạn")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise DeliveryExportError(f"{label} phải là số hữu hạn") from error
    if not math.isfinite(number):
        raise DeliveryExportError(f"{label} phải là số hữu hạn")
    return int(number) if number.is_integer() else number


def _amount(quantity: int | float, price: int | float) -> int | float:
    try:
        value = Decimal(str(quantity)) * Decimal(str(price))
    except (InvalidOperation, ValueError) as error:  # defensive; inputs are finite
        raise DeliveryExportError("Không tính được thành tiền") from error
    # Match order_totals: round each line to VND before summing the document.
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _work_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise DeliveryExportError("Ngày giao hàng không hợp lệ", code="invalid_work_date")


def _unique_sheet_title(raw: Any, used: set[str]) -> str:
    base = INVALID_SHEET_CHARACTER.sub("-", str(raw or "").strip()) or "CHUA_XAC_DINH"
    base = base[:31]
    candidate = base
    suffix = 2
    while candidate.casefold() in used:
        tail = f"-{suffix}"
        candidate = base[: 31 - len(tail)] + tail
        suffix += 1
    used.add(candidate.casefold())
    return candidate


def _style_snapshot(sheet: Any, row: int, start_column: int = 1, end_column: int = 11) -> dict[str, Any]:
    cells = []
    for column in range(start_column, end_column + 1):
        cell = sheet.cell(row, column)
        cells.append({
            "style": copy(cell._style),
            "number_format": cell.number_format,
            "alignment": copy(cell.alignment),
            "protection": copy(cell.protection),
        })
    dimension = sheet.row_dimensions[row]
    return {
        "cells": cells,
        "start_column": start_column,
        "height": dimension.height,
        "hidden": dimension.hidden,
        "outlineLevel": dimension.outlineLevel,
        "collapsed": dimension.collapsed,
        "thickTop": dimension.thickTop,
        "thickBot": dimension.thickBot,
    }


def _apply_style_snapshot(sheet: Any, row: int, snapshot: Mapping[str, Any]) -> None:
    dimension = sheet.row_dimensions[row]
    for attribute in ("height", "hidden", "outlineLevel", "collapsed", "thickTop", "thickBot"):
        setattr(dimension, attribute, snapshot[attribute])
    start_column = int(snapshot["start_column"])
    for offset, source in enumerate(snapshot["cells"]):
        cell = sheet.cell(row, start_column + offset)
        cell._style = copy(source["style"])
        cell.number_format = source["number_format"]
        cell.alignment = copy(source["alignment"])
        cell.protection = copy(source["protection"])
        cell.comment = None
        cell._hyperlink = None


def _cell_style_snapshot(cell: Any) -> dict[str, Any]:
    return {
        "style": copy(cell._style),
        "number_format": cell.number_format,
        "alignment": copy(cell.alignment),
        "protection": copy(cell.protection),
    }


def _apply_cell_style(cell: Any, snapshot: Mapping[str, Any]) -> None:
    cell._style = copy(snapshot["style"])
    cell.number_format = snapshot["number_format"]
    cell.alignment = copy(snapshot["alignment"])
    cell.protection = copy(snapshot["protection"])
    cell.comment = None
    cell._hyperlink = None


def _clear_golden_business_values(sheet: Any, through_row: int) -> None:
    for row in range(TABLE_FIRST_ROW, max(39, through_row) + 1):
        for column in range(2, 12):
            cell = sheet.cell(row, column)
            cell.value = None
            cell.comment = None
            cell._hyperlink = None
    # H5 is the displayed date; K5 was the golden's hidden date input.
    sheet["H5"].value = None
    sheet["K5"].value = None


def _write_signature_cells(sheet: Any, closing_row: int, blank_style: Any) -> None:
    """Write the four-signature footer as editable Excel cells, never an image."""

    first_row = closing_row + 1
    last_row = closing_row + SIGNATURE_PRINT_ROWS
    for merged_range in list(sheet.merged_cells.ranges):
        if merged_range.max_row >= first_row and merged_range.min_row <= last_row:
            sheet.unmerge_cells(str(merged_range))

    for row in range(first_row, last_row + 1):
        dimension = sheet.row_dimensions[row]
        dimension.height = 15
        dimension.hidden = False
        dimension.outlineLevel = 0
        dimension.collapsed = False
        dimension.thickTop = False
        dimension.thickBot = False
        for column in range(3, 11):
            cell = sheet.cell(row, column)
            cell.value = None
            cell._style = copy(blank_style)
            cell.comment = None
            cell._hyperlink = None

    # Keep the same visual footprint as the customer's photographed footer.
    # The long merged rows also work on sheets where the price columns H:I are
    # hidden; all four signature positions remain visible and printable.
    row_heights = (20, 26, 18, 20, 20, 20, 20, 20)
    for offset, height in enumerate(row_heights):
        sheet.row_dimensions[first_row + offset].height = height

    top_side = Side(style="medium", color="000000")
    for column in range(3, 11):
        cell = sheet.cell(first_row, column)
        cell.border = Border(top=top_side)

    for row in range(first_row, first_row + 3):
        sheet.merge_cells(start_row=row, start_column=3, end_row=row, end_column=10)

    date_cell = sheet.cell(first_row, 3)
    write_literal(sheet, date_cell.coordinate, SIGNATURE_DATE_TEXT)
    date_cell.font = Font(name="Arial", size=11, italic=True, color="000000")
    date_cell.alignment = Alignment(horizontal="right", vertical="center", shrink_to_fit=True)
    date_cell.border = Border(top=top_side)

    title_cell = sheet.cell(first_row + 1, 3)
    write_literal(sheet, title_cell.coordinate, SIGNATURE_TITLES_TEXT)
    title_cell.font = Font(name="Arial", size=12, bold=True, color="000000")
    title_cell.alignment = Alignment(horizontal="center", vertical="center", shrink_to_fit=True)

    hint_cell = sheet.cell(first_row + 2, 3)
    write_literal(sheet, hint_cell.coordinate, SIGNATURE_HINTS_TEXT)
    hint_cell.font = Font(name="Arial", size=8, italic=True, color="000000")
    hint_cell.alignment = Alignment(horizontal="center", vertical="center", shrink_to_fit=True)


def _page_chunks(item_count: int) -> list[int]:
    """Split long notes into balanced pages instead of one full and one sparse page."""

    page_count = max(1, math.ceil(item_count / DELIVERY_MAX_ITEMS_PER_PAGE))
    base, remainder = divmod(item_count, page_count)
    return [base + (1 if index < remainder else 0) for index in range(page_count)]


def _delivery_base_row_height(item_count: int, chunks: Sequence[int]) -> float:
    if len(chunks) == 1:
        return max(23.0, min(32.0, 460.0 / max(1, item_count)))
    # Roughly 500 points of item rows per page leaves room for the first-page
    # identity block and the last-page four-signature block.
    return max(26.0, min(38.0, 500.0 / max(chunks)))


def _style_delivery_print_layout(sheet: Any, *, records: Sequence[Mapping[str, Any]]) -> None:
    """Apply the customer's readable, full-width black-and-white print layout."""

    # Remove the source workbook's conditional highlights. They are useful
    # while preparing data, but must never colour a customer delivery note.
    sheet.conditional_formatting._cf_rules.clear()

    top_styles = {
        "C1": (13, True), "C2": (13, True), "C3": (13, True),
        "C4": (20, False), "C5": (14, False), "C6": (14, True),
        "C7": (14, False), "C8": (14, False), "C9": (14, False),
    }
    for coordinate, (size, bold) in top_styles.items():
        font = copy(sheet[coordinate].font)
        font.name = "Arial"
        font.sz = size
        font.bold = bold
        font.charset = None
        font.scheme = None
        font.family = 2
        font.color = "FF000000"
        sheet[coordinate].font = font
        alignment = copy(sheet[coordinate].alignment)
        alignment.vertical = "center"
        sheet[coordinate].alignment = alignment
    for coordinate in ("C6",):
        if str(sheet[coordinate].value or "").startswith("Ngày "):
            font = copy(sheet[coordinate].font)
            font.name = "Arial"
            font.sz = 14
            font.bold = True
            font.charset = None
            font.scheme = None
            font.family = 2
            font.color = "FF000000"
            sheet[coordinate].font = font
    sheet.row_dimensions[1].height = 21
    sheet.row_dimensions[2].height = 36
    sheet.row_dimensions[3].height = 21
    sheet.row_dimensions[4].height = 29
    sheet.row_dimensions[5].height = 23
    sheet.row_dimensions[6].height = 23
    sheet.row_dimensions[7].height = 24
    sheet.row_dimensions[8].height = 24
    sheet.row_dimensions[9].height = 24
    sheet.row_dimensions[TABLE_HEADER_ROW].height = 25

    white_fill = PatternFill(fill_type="solid", fgColor="FFFFFF")
    for column in "CDEFGHIJ":
        cell = sheet[f"{column}{TABLE_HEADER_ROW}"]
        font = copy(cell.font)
        font.name = "Arial"
        font.sz = 14
        font.bold = True
        font.charset = None
        font.scheme = None
        font.family = 2
        font.color = "FF000000"
        cell.font = font
        cell.fill = white_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    chunks = _page_chunks(len(records))
    base_height = _delivery_base_row_height(len(records), chunks)
    for offset, record in enumerate(records):
        row = TABLE_FIRST_ROW + offset
        product_name = str(record.get("product_name") or record.get("product_code") or "").strip()
        # Excel/LibreOffice wrap on word boundaries, so a Vietnamese item name
        # can occupy two lines before a raw character-count estimate predicts
        # it. Reserve 24pt for every displayed line so the lower line never
        # touches the bottom border in the printed/PDF version.
        line_count = max(1, math.ceil(len(product_name) / 28))
        sheet.row_dimensions[row].height = max(base_height, 24.0 * line_count)
        for column in "CDEFGHIJ":
            cell = sheet[f"{column}{row}"]
            cell.fill = white_fill
            font = copy(cell.font)
            font.name = "Arial"
            font.sz = 16 if column in "DE" else 15 if column == "F" else 13
            font.bold = False
            font.charset = None
            font.scheme = None
            font.family = 2
            font.color = "FF000000"
            cell.font = font
            alignment = copy(cell.alignment)
            alignment.vertical = "center"
            alignment.wrap_text = column in "DJ"
            if column == "D":
                alignment.horizontal = "left"
            elif column in "CEFHI":
                alignment.horizontal = "center"
            cell.alignment = alignment

    total_row = TABLE_FIRST_ROW + len(records)
    if str(sheet[f"C{total_row}"].value or "").strip():
        sheet.row_dimensions[total_row].height = 27
        for column in "CDEFGHIJ":
            cell = sheet[f"{column}{total_row}"]
            cell.fill = white_fill
            font = copy(cell.font)
            font.name = "Arial"
            font.sz = 14
            font.bold = True
            font.charset = None
            font.scheme = None
            font.family = 2
            font.color = "FF000000"
            cell.font = font
            alignment = copy(cell.alignment)
            alignment.vertical = "center"
            cell.alignment = alignment

    # Use the complete printable width while keeping item and quantity adjacent.
    sheet.column_dimensions["C"].width = 6
    sheet.column_dimensions["D"].width = 43
    sheet.column_dimensions["E"].width = 12
    sheet.column_dimensions["F"].width = 10
    sheet.column_dimensions["J"].width = 24

    sheet.row_breaks = RowBreak()
    cumulative = 0
    for chunk in chunks[:-1]:
        cumulative += chunk
        sheet.row_breaks.append(Break(id=TABLE_FIRST_ROW + cumulative - 1))
    sheet.print_title_rows = f"{TABLE_HEADER_ROW}:{TABLE_HEADER_ROW}"
    sheet.print_options.horizontalCentered = True
    sheet.print_options.verticalCentered = False
    sheet.page_margins = PageMargins(
        left=0.25, right=0.25, top=0.3, bottom=0.3, header=0.1, footer=0.1,
    )


def _prepare_sheet(
    sheet: Any,
    delivery: Mapping[str, Any],
    work_date: datetime,
    item_style: Mapping[str, Any],
    item_heights: Sequence[float | None],
    total_style: Mapping[str, Any],
    blank_style: Any,
    date_style: Mapping[str, Any],
) -> None:
    kitchen = str(delivery.get("kitchen") or "").strip().upper()
    contractor = str(delivery.get("contractor") or "").strip().upper()
    recipient = str(delivery.get("recipient") or kitchen).strip()
    address = str(delivery.get("address") or "").strip()
    records = list(delivery.get("items") or [])
    if not records:
        raise DeliveryExportError(f"Bếp {kitchen or '(trống)'} không có dòng thực giao")

    # The customer-approved header uses separate centred rows for the subtitle
    # and date, followed by buyer, address and payment method. The transferred
    # golden placed subtitle and date side-by-side, so add two native rows and
    # move the original table down without altering the locked source file.
    if "C27:H27" in {str(value) for value in sheet.merged_cells.ranges}:
        sheet.unmerge_cells("C27:H27")
    sheet.insert_rows(6, amount=2)

    show_price = delivery_prices_visible(kitchen, contractor)
    last_item_row = TABLE_FIRST_ROW + len(records) - 1
    total_row = last_item_row + 1
    closing_row = total_row

    _clear_golden_business_values(sheet, closing_row)

    # Rows 1-9 are prose fields in the customer's approved form, not table
    # rows. In
    # the original workbook their text merely overflowed through adjacent
    # blank cells.  That is fragile once the price columns are hidden: Excel
    # stops painting the overflow at the hidden columns and the printed
    # address loses its final words.  Merge the same printable span and shrink
    # only when necessary so both priced and non-priced variants retain the
    # complete legal name/address on paper.
    existing_merges = {str(value) for value in sheet.merged_cells.ranges}
    for merged_range in ("C5:F5", "H5:I5"):
        if merged_range in existing_merges:
            sheet.unmerge_cells(merged_range)
    for merged_range in (
        "C1:J1", "C2:J2", "C3:J3", "C5:J5", "C6:J6",
        "C7:J7", "C8:J8", "C9:J9",
    ):
        if merged_range not in {str(value) for value in sheet.merged_cells.ranges}:
            sheet.merge_cells(merged_range)
    write_literal(sheet, "C5", "(Kiêm phiếu xuất kho)")
    _apply_cell_style(sheet["C6"], date_style)
    write_literal(sheet, "C6", work_date.strftime("Ngày %d tháng %m năm %Y"))
    write_literal(sheet, "C7", f"Đơn vị mua hàng: {recipient}")
    write_literal(sheet, "C8", f"Địa chỉ giao hàng: {address}" if address else "Địa chỉ giao hàng:")
    payment_method = str(delivery.get("payment_method") or "TM/CK").strip()
    write_literal(sheet, "C9", f"Hình thức thanh toán: {payment_method}")
    for coordinate in ("C1", "C2", "C3", "C7", "C8", "C9"):
        prose_alignment = copy(sheet[coordinate].alignment)
        prose_alignment.horizontal = "left"
        prose_alignment.vertical = "center"
        prose_alignment.shrinkToFit = coordinate != "C2"
        prose_alignment.wrap_text = coordinate == "C2"
        sheet[coordinate].alignment = prose_alignment
    for coordinate in ("C4", "C5", "C6"):
        centered = copy(sheet[coordinate].alignment)
        centered.horizontal = "center"
        centered.vertical = "center"
        centered.shrinkToFit = True
        centered.wrap_text = False
        sheet[coordinate].alignment = centered

    write_literal(sheet, f"C{TABLE_HEADER_ROW}", "STT")
    write_literal(sheet, f"D{TABLE_HEADER_ROW}", "Tên hàng")
    write_literal(sheet, f"E{TABLE_HEADER_ROW}", "SL")
    write_literal(sheet, f"F{TABLE_HEADER_ROW}", "ĐVT")
    write_literal(sheet, f"G{TABLE_HEADER_ROW}", None)
    write_literal(sheet, f"H{TABLE_HEADER_ROW}", "Đơn giá" if show_price else None)
    write_literal(sheet, f"I{TABLE_HEADER_ROW}", "Thành tiền" if show_price else None)
    write_literal(sheet, f"J{TABLE_HEADER_ROW}", "GC")

    total = Decimal("0")
    for offset, record in enumerate(records):
        row = TABLE_FIRST_ROW + offset
        _apply_style_snapshot(sheet, row, item_style)
        sheet.row_dimensions[row].height = item_heights[min(offset, len(item_heights) - 1)]
        quantity = _finite_number(record.get("quantity"), f"Số lượng dòng {offset + 1}")
        if quantity <= 0:
            raise DeliveryExportError(f"Số lượng dòng {offset + 1} phải lớn hơn 0")
        write_literal(sheet, f"C{row}", offset + 1)
        product_name = str(record.get("product_name") or record.get("product_code") or "").strip()
        write_literal(sheet, f"D{row}", product_name)
        write_literal(sheet, f"E{row}", quantity)
        sheet[f"E{row}"].number_format = "#,##0.######"
        write_literal(sheet, f"F{row}", record.get("unit") or "")
        write_literal(sheet, f"G{row}", None)  # never export the hidden purchase price
        if show_price:
            price = _finite_number(record.get("sell_price", 0), f"Đơn giá dòng {offset + 1}")
            if price < 0:
                raise DeliveryExportError(f"Đơn giá dòng {offset + 1} không được âm")
            amount = _amount(quantity, price)
            total += Decimal(str(amount))
            write_literal(sheet, f"H{row}", price)
            write_literal(sheet, f"I{row}", amount)
            sheet[f"H{row}"].number_format = "#,##0"
            sheet[f"I{row}"].number_format = "#,##0"
        else:
            write_literal(sheet, f"H{row}", None)
            write_literal(sheet, f"I{row}", None)
        write_literal(sheet, f"J{row}", record.get("note") or "")
        # All values in an item row share one visual baseline.  The golden
        # amount/sequence/note cells otherwise inherit bottom alignment while
        # quantity and price are centered, which makes one row look staggered.
        for column in "CDEFGHIJ":
            cell = sheet[f"{column}{row}"]
            alignment = copy(cell.alignment)
            alignment.vertical = "center"
            cell.alignment = alignment
        # The picking team works at night: keep the item and its quantity close
        # together and larger, while retaining the customer's regular-weight
        # typography.  "Larger" must not be interpreted as bold.
        for coordinate, font_size in (
            (f"D{row}", 20),
            (f"E{row}", 20),
            (f"F{row}", 18),
        ):
            font = copy(sheet[coordinate].font)
            font.sz = font_size
            font.bold = False
            sheet[coordinate].font = font
            alignment = copy(sheet[coordinate].alignment)
            alignment.vertical = "center"
            sheet[coordinate].alignment = alignment
        name_alignment = copy(sheet[f"D{row}"].alignment)
        name_alignment.horizontal = "left"
        name_alignment.wrap_text = True
        sheet[f"D{row}"].alignment = name_alignment
        quantity_alignment = copy(sheet[f"E{row}"].alignment)
        quantity_alignment.horizontal = "center"
        sheet[f"E{row}"].alignment = quantity_alignment
        unit_alignment = copy(sheet[f"F{row}"].alignment)
        unit_alignment.horizontal = "center"
        sheet[f"F{row}"].alignment = unit_alignment
        # At 20pt in the compact 36-character column, Vietnamese item names
        # can wrap at roughly 18 characters once word boundaries are applied.
        # Reserve the full wrapped height so no line can overlap the next item.
        name_lines = max(1, math.ceil(len(product_name) / 18))
        sheet.row_dimensions[row].height = max(
            sheet.row_dimensions[row].height or 0,
            28 if name_lines == 1 else 23 * name_lines,
        )
        # The approved sample has 18pt operational text.  Its blank GC cells
        # used a smaller font, so raise only that dynamic field to a readable
        # minimum without changing the surrounding golden layout.
        if sheet[f"J{row}"].font.sz is None or sheet[f"J{row}"].font.sz < 14:
            font = copy(sheet[f"J{row}"].font)
            font.sz = 14
            sheet[f"J{row}"].font = font
        if record.get("note"):
            note_alignment = copy(sheet[f"J{row}"].alignment)
            note_alignment.wrap_text = True
            note_alignment.vertical = "center"
            sheet[f"J{row}"].alignment = note_alignment
            sheet.row_dimensions[row].height = max(sheet.row_dimensions[row].height or 0, 32)

    _apply_style_snapshot(sheet, total_row, total_style)
    sheet.merge_cells(start_row=total_row, start_column=3, end_row=total_row, end_column=4)
    write_literal(sheet, f"C{total_row}", "TỔNG CỘNG")
    # The visible E:F cells are shared by priced and price-hidden notes.
    sheet.merge_cells(start_row=total_row, start_column=5, end_row=total_row, end_column=6)
    qty = quantity_cell(records, "quantity")
    if not isinstance(qty, str):
        qty = f"{qty:,.6f}".rstrip('0').rstrip('.') + ' ' + str(records[0].get('unit') or '')
    write_literal(sheet, f"E{total_row}", qty)
    sheet[f"E{total_row}"].alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    if show_price:
        write_literal(sheet, f"I{total_row}", int(total) if total == total.to_integral_value() else float(total))
        sheet[f"I{total_row}"].number_format = "#,##0"
        write_literal(sheet, f"J{total_row}", None)

    _write_signature_cells(sheet, closing_row, blank_style)

    # Column G was a hidden purchase-price helper in the customer's source.
    # It stays hidden and empty.  Price columns are both hidden and empty for
    # every non-Nhựa sheet so unhiding them cannot reveal a selling price.
    sheet.column_dimensions["G"].hidden = True
    sheet.column_dimensions["H"].hidden = not show_price
    sheet.column_dimensions["I"].hidden = not show_price
    # Final customer-facing typography, full-width columns and page balance.
    _style_delivery_print_layout(sheet, records=records)
    sheet.row_dimensions[total_row].height = max(30, 20 * math.ceil(len(qty) / 20))
    sheet.auto_filter.ref = f"C{TABLE_HEADER_ROW}:J{last_item_row}"
    # The source print area stopped at the total even though its approved
    # four-signature artwork is anchored immediately below it.  Include the
    # complete signature block and fit the width to one A4 page; height remains
    # unlimited so unusually long kitchen notes paginate instead of shrinking
    # operational text to an unreadable size.
    sheet.print_area = f"C1:J{closing_row + SIGNATURE_PRINT_ROWS}"
    sheet.page_setup.paperSize = "9"
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.scale = None
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.freeze_panes = None


def build_delivery_workbook(
    deliveries: Iterable[Mapping[str, Any]],
    *,
    work_date: Any,
    template_path: str | Path,
    expected_sha256: str = EM_THANH_SHA256,
) -> Any:
    """Build one approved delivery-note sheet per kitchen."""

    payload = list(deliveries)
    if not payload:
        raise DeliveryExportError("Không có dòng thực giao để lập phiếu", code="no_delivery_rows")
    parsed_date = _work_date(work_date)
    try:
        cloned = clone_template_workbook(
            template_path,
            sheet_names=[DELIVERY_TEMPLATE_SHEET],
            expected_sha256=expected_sha256,
        )
    except TemplateWorkbookError as error:
        raise DeliveryExportError(
            f"Không thể dùng mẫu phiếu giao đã khóa: {error}",
            code="delivery_template_error",
            status=500,
        ) from error

    workbook = cloned.workbook
    source = workbook[DELIVERY_TEMPLATE_SHEET]
    # The golden still contains the customer's photographed footer.  It is a
    # reference only: generated workbooks must contain native text, not images.
    source._images = []
    item_style = _style_snapshot(source, SOURCE_TABLE_FIRST_ROW)
    item_heights = [
        source.row_dimensions[row].height
        for row in range(SOURCE_TABLE_FIRST_ROW, GOLDEN_LAST_ITEM_ROW + 1)
    ]
    total_style = _style_snapshot(source, GOLDEN_TOTAL_ROW)
    blank_style = copy(source["A36"]._style)
    date_style = _cell_style_snapshot(source["H5"])

    sheets = [source]
    for _ in payload[1:]:
        copied = workbook.copy_worksheet(source)
        # WorksheetCopy intentionally does not copy drawings.
        copied._images = []
        sheets.append(copied)

    used_titles: set[str] = set()
    try:
        for sheet, delivery in zip(sheets, payload):
            sheet.title = _unique_sheet_title(delivery.get("kitchen"), used_titles)
            _prepare_sheet(
                sheet,
                delivery,
                parsed_date,
                item_style,
                item_heights,
                total_style,
                blank_style,
                date_style,
            )
        workbook.active = 0
        for index, sheet in enumerate(workbook.worksheets):
            sheet.sheet_view.tabSelected = index == 0
        assert_workbook_safe(workbook)
        white_print_style(workbook)
        return workbook
    except Exception:
        workbook.close()
        raise


__all__ = [
    "DELIVERY_TEMPLATE_SHEET",
    "DeliveryExportError",
    "EM_THANH_SHA256",
    "PRICE_VISIBLE_CONTRACTOR",
    "PRICE_VISIBLE_KITCHEN",
    "build_delivery_workbook",
    "delivery_prices_visible",
]
