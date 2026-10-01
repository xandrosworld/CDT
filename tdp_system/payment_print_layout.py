"""Readable A4 geometry for the two customer payment forms."""
from copy import copy
from openpyxl.worksheet.page import PageMargins


def readable_payment_layout(sheet, *, statement=False):
    # Keep the customer's columns, merges and content, but do not shrink the
    # oversized source spreadsheet to fit A4. Long forms paginate downwards.
    widths = (5, 22, 6, 8, 11, 13, 9, 12, 14) if statement else (2, 6, 14, 12, 19, 16, 21, 2)
    for index, width in enumerate(widths):
        sheet.column_dimensions[chr(65 + index)].width = width
    sheet.page_margins = PageMargins(left=.25, right=.25, top=.4, bottom=.4, header=.15, footer=.15)
    for row in sheet:
        for cell in row:
            if cell.value is None:
                continue
            font = copy(cell.font)
            font.sz = max(14, font.sz or 14)
            cell.font = font
            alignment = copy(cell.alignment)
            alignment.shrinkToFit = False
            alignment.wrapText = True
            cell.alignment = alignment
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.orientation = 'portrait'
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.page_setup.scale = None
    sheet.print_options.horizontalCentered = True


def keep_payment_footer(sheet, total_row, last_row):
    """Explicit page breaks keep final items, totals and signatures together."""
    from openpyxl.worksheet.pagebreak import Break
    landscape = sheet.page_setup.orientation == 'landscape'
    budget = (595 if landscape else 842) - 72 * (sheet.page_margins.top + sheet.page_margins.bottom) - 35
    height = lambda r: sheet.row_dimensions[r].height or 15
    heading = height(10)
    used = sum(height(r) for r in range(1,11))
    tail = max(11,total_row-2)
    for row in range(11,tail):
        if used + height(row) > budget:
            sheet.row_breaks.append(Break(id=row-1));used=heading
        used += height(row)
    remaining=sum(height(r) for r in range(tail,last_row+1))
    if used+remaining > budget and tail>11:
        sheet.row_breaks.append(Break(id=tail-1))
