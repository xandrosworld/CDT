"""Convert the application's styled Excel exports into one audited PDF bundle.

The Excel generators remain the source of truth for document content.  This
module only extracts their styled table regions and maps them to the neutral
``pdf_documents`` section format, avoiding a second set of business formulas.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from openpyxl import Workbook
from openpyxl.utils import get_column_letter


MAX_PDF_COLUMNS = 10


def _key(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", raw)
    return re.sub(r"[^a-z0-9]+", " ", "".join(char for char in text if unicodedata.category(char) != "Mn")).strip()


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _number(value: Any) -> float:
    """Convert an ordinary worksheet value without trying to execute formulas."""

    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        return float(int(value))
    return float(value)


def _supplier_purchase_value(
    worksheet, row_index: int, column: int, header_row: int,
    header_columns: Mapping[str, int]
) -> Any:
    """Resolve formulas in the canonical purchase sheet for PDF projection.

    The workbook is generated in memory and therefore has no cached values for
    Excel formulas yet.  PDF preparation must use the same simple business
    expressions instead of passing formula text to the numeric formatter.
    """

    value = worksheet.cell(row_index, column).value
    if not (isinstance(value, str) and value.startswith("=")):
        return value
    key = _key(worksheet.cell(header_row, column).value)
    actual_required = {"so luong", "hong", "them", "giam", "thieu"}
    if key not in {"sl thuc te", "thanh tien"} or not actual_required.issubset(header_columns):
        return value
    actual = (
        _number(worksheet.cell(row_index, header_columns["so luong"]).value)
        + _number(worksheet.cell(row_index, header_columns["them"]).value)
        - _number(worksheet.cell(row_index, header_columns["hong"]).value)
        - _number(worksheet.cell(row_index, header_columns["giam"]).value)
        - _number(worksheet.cell(row_index, header_columns["thieu"]).value)
    )
    if key == "sl thuc te":
        return actual
    if "gia mua" not in header_columns:
        return value
    return actual * _number(worksheet.cell(row_index, header_columns["gia mua"]).value)


def _header_row(worksheet, *, allow_wide: bool = False) -> tuple[int, int]:
    """Locate the first styled application table header and its last column."""

    for row_index in range(1, min(worksheet.max_row, 30) + 1):
        values = [_cell_text(worksheet.cell(row_index, column).value) for column in range(1, worksheet.max_column + 1)]
        last_column = max((index for index, value in enumerate(values, 1) if value), default=0)
        if last_column < 2:
            continue
        # The customer's canonical ``đặt hàng`` header deliberately uses
        # mostly regular-weight Cambria text.  Recognise that business schema
        # directly instead of requiring application-style coloured/bold cells.
        if allow_wide:
            keys = {_key(value) for value in values if value}
            required = {
                "ma hang", "ma bep", "ten hang", "so luong", "dvt", "ncc",
                "gia mua", "thanh tien",
            }
            if required.issubset(keys):
                return row_index, last_column
        colored = 0
        bold = 0
        for column in range(1, last_column + 1):
            cell = worksheet.cell(row_index, column)
            if cell.fill and cell.fill.fill_type == "solid":
                colored += 1
            if cell.font and cell.font.bold:
                bold += 1
        if colored >= max(2, last_column // 2) and bold >= max(2, last_column // 2):
            if last_column > MAX_PDF_COLUMNS and not allow_wide:
                raise ValueError(
                    f"Sheet {worksheet.title!r} có {last_column} cột; PDF chỉ hỗ trợ tối đa {MAX_PDF_COLUMNS} cột."
                )
            return row_index, last_column
    raise ValueError(f"Không tìm thấy hàng tiêu đề bảng trong sheet {worksheet.title!r}.")


def _column_format(label: str) -> tuple[str, str]:
    name = _key(label)
    if any(token in name for token in ("ngay", "date")):
        return "date", "center"
    if any(token in name for token in ("don gia", "thanh tien", "so tien", "doanh thu", "gia von", "loi nhuan", "phat sinh", "dieu chinh", "da thu", "da tra", "phai thu", "phai tra", "so du", "tong")):
        return "money", "right"
    if any(token in name for token in ("so luong", " sl", "sl ", "so dong")) or name in {"sl", "stt"}:
        return "number", "right" if name != "stt" else "center"
    return "text", "left"


def _column_weight(label: str) -> float:
    name = _key(label)
    if name == "stt":
        return 0.45
    if any(token in name for token in ("ten hang", "ghi chu", "noi dung", "nha thau", "nguoi ban", "dia chi")):
        return 2.6
    if any(token in name for token in ("ma hang", "cccd", "ngay", "bep", "ncc", "dvt")):
        return 1.2
    return 1.0


def _signature_block(document_type: str) -> list[dict[str, str]]:
    if document_type == "supplier_orders":
        return [
            {"title": "NGƯỜI LẬP", "hint": "Ký, ghi rõ họ tên"},
            {"title": "NHÀ CUNG CẤP", "hint": "Xác nhận"},
        ]
    if document_type == "deliveries":
        return [
            {"title": "TRỰC BAN", "hint": "Ký và ghi rõ họ tên"},
            {"title": "BẢO VỆ", "hint": "Ký và ghi rõ họ tên"},
            {"title": "NGƯỜI GIAO HÀNG", "hint": "Ký và ghi rõ họ tên"},
            {"title": "NGƯỜI NHẬN HÀNG", "hint": "Ký và ghi rõ họ tên"},
        ]
    if document_type == "purchases":
        return [
            {"title": "NGƯỜI BÁN", "hint": "Ký, ghi rõ họ tên"},
            {"title": "NGƯỜI MUA", "hint": "Ký, ghi rõ họ tên"},
        ]
    return []


def _delivery_header_row(worksheet) -> int | None:
    """Locate the approved delivery template without relying on fill colors."""

    required = {"stt", "ten hang", "sl", "dvt"}
    for row_index in range(1, min(worksheet.max_row, 15) + 1):
        keys = {
            _key(worksheet.cell(row_index, column).value)
            for column in range(1, worksheet.max_column + 1)
            if _key(worksheet.cell(row_index, column).value)
        }
        if required.issubset(keys):
            return row_index
    return None


def _delivery_section(worksheet, header_row: int) -> dict[str, Any]:
    """Project the customer's C:J delivery form into the safe PDF model."""

    source_columns = [
        column
        for column in range(1, worksheet.max_column + 1)
        if _cell_text(worksheet.cell(header_row, column).value)
        and not bool(worksheet.column_dimensions[get_column_letter(column)].hidden)
    ]
    if not source_columns or len(source_columns) > MAX_PDF_COLUMNS:
        raise ValueError(f"Sheet {worksheet.title!r} không xác định được các cột phiếu giao cần in.")
    headers = [_cell_text(worksheet.cell(header_row, column).value) for column in source_columns]
    columns = []
    for index, header in enumerate(headers, 1):
        value_format, alignment = _column_format(header)
        columns.append({
            "key": f"c{index}",
            "label": header,
            "width": _column_weight(header),
            "format": value_format,
            "align": alignment,
        })

    rows = []
    summary = []
    for row_index in range(header_row + 1, worksheet.max_row + 1):
        first_key = _key(worksheet.cell(row_index, source_columns[0]).value)
        if first_key.startswith("ngay ") and " thang " in f" {first_key} " and " nam " in f" {first_key} ":
            # Native Excel signature footer.  It belongs on the printed sheet,
            # but is not a delivery item in the generated PDF table.
            break
        if first_key in {"tong", "tong tien", "tong cong"}:
            total_value = worksheet.cell(row_index, 9).value
            if total_value not in (None, ""):
                summary.append({"label": "Tổng tiền", "value": total_value})
            break
        values = [worksheet.cell(row_index, column).value for column in source_columns]
        if all(value in (None, "") for value in values):
            continue
        rows.append({f"c{index}": value for index, value in enumerate(values, 1)})

    date_value = worksheet["C6"].value
    if hasattr(date_value, "strftime"):
        date_text = date_value.strftime("%d/%m/%Y")
    else:
        date_text = _cell_text(date_value)
    rendered_date = date_text if _key(date_text).startswith("ngay ") else (f"Ngày {date_text}" if date_text else "")
    subtitle_parts = [
        _cell_text(worksheet["C1"].value),
        _cell_text(worksheet["C7"].value),
        _cell_text(worksheet["C8"].value),
        _cell_text(worksheet["C9"].value),
        rendered_date,
    ]
    section = {
        "document_type": "deliveries",
        "title": _cell_text(worksheet["C4"].value) or worksheet.title,
        "subtitle": " · ".join(part for part in subtitle_parts if part),
        "columns": columns,
        "rows": rows,
        "notes": [f"Nguồn: {worksheet.title} · {len(rows)} dòng thực giao."],
        "signatures": _signature_block("deliveries"),
    }
    if summary:
        section["summary"] = summary
    return section


def _purchase_summary_header_rows(worksheet) -> tuple[int, int] | None:
    """Locate the two-row header of the approved purchase summary."""

    required = {
        "ten nguoi ban", "dia chi", "so cccd", "ten mat hang", "dvt",
        "so luong", "don gia", "tong gia thanh toan",
    }
    for row_index in range(2, min(worksheet.max_row, 15) + 1):
        keys = {
            _key(worksheet.cell(row_index, column).value)
            for column in range(1, min(worksheet.max_column, 10) + 1)
            if _key(worksheet.cell(row_index, column).value)
        }
        if required.issubset(keys):
            return row_index - 1, row_index
    return None


def _purchase_summary_section(
    worksheet, group_header_row: int, detail_header_row: int,
) -> dict[str, Any]:
    """Project ``bảng kê tổng`` without treating its numbering row as data."""

    header_cells = [
        worksheet.cell(group_header_row, 1),
        *[worksheet.cell(detail_header_row, column) for column in range(2, 10)],
        worksheet.cell(group_header_row, 10),
    ]
    headers = [_cell_text(cell.value) for cell in header_cells]
    columns = []
    for index, header in enumerate(headers, start=1):
        value_format, alignment = _column_format(header)
        columns.append({
            "key": f"c{index}",
            "label": header,
            "width": _column_weight(header),
            "format": value_format,
            "align": alignment,
        })

    rows = []
    summary = []
    for row_index in range(detail_header_row + 2, worksheet.max_row + 1):
        first_key = _key(worksheet.cell(row_index, 1).value)
        if first_key == "tong cong":
            summary = [
                {"label": "Tổng số lượng", "value": worksheet.cell(row_index, 7).value},
                {"label": "Tổng giá thanh toán", "value": worksheet.cell(row_index, 9).value},
            ]
            break
        values = [worksheet.cell(row_index, column).value for column in range(1, 11)]
        if all(value in (None, "") for value in values):
            continue
        rows.append({f"c{index}": value for index, value in enumerate(values, start=1)})

    return {
        "document_type": "purchases",
        "title": _cell_text(worksheet["A1"].value) or worksheet.title,
        "subtitle": _cell_text(worksheet["A2"].value),
        "columns": columns,
        "rows": rows,
        "summary": summary,
        "notes": [f"Nguồn: {worksheet.title} · {len(rows)} dòng mua/BK đã chốt."],
        "signatures": [
            {"title": "NGƯỜI LẬP BẢNG KÊ", "hint": "Ký, ghi rõ họ tên"},
            {"title": "ĐẠI DIỆN CÔNG TY", "hint": "Ký, đóng dấu"},
        ],
    }


def _receipt_header_row(worksheet) -> int | None:
    required = ["ten hang", "dvt", "don gia", "so luong", "thanh tien"]
    for row_index in range(2, min(worksheet.max_row, 20) + 1):
        if [
            _key(worksheet.cell(row_index, column).value)
            for column in range(3, 8)
        ] == required:
            return row_index
    return None


def _receipt_section(worksheet, header_row: int) -> dict[str, Any]:
    """Project one approved golden receipt, including its legal identity block."""

    headers = [
        _cell_text(worksheet.cell(header_row, column).value)
        for column in range(3, 8)
    ]
    columns = []
    for index, header in enumerate(headers, start=1):
        value_format, alignment = _column_format(header)
        columns.append({
            "key": f"c{index}",
            "label": header,
            "width": _column_weight(header),
            "format": value_format,
            "align": alignment,
        })

    rows = []
    summary = []
    total_row = None
    for row_index in range(header_row + 1, worksheet.max_row + 1):
        if _key(worksheet.cell(row_index, 3).value) == "tong":
            total_row = row_index
            summary = [
                {"label": "Tổng số lượng", "value": worksheet.cell(row_index, 6).value},
                {"label": "Tổng thành tiền", "value": worksheet.cell(row_index, 7).value},
            ]
            break
        values = [worksheet.cell(row_index, column).value for column in range(3, 8)]
        if all(value in (None, "") for value in values):
            continue
        rows.append({f"c{index}": value for index, value in enumerate(values, start=1)})
    if total_row is None:
        raise ValueError(f"Sheet {worksheet.title!r} thiếu dòng tổng biên nhận.")

    identity_notes = [
        _cell_text(worksheet["C5"].value),
        _cell_text(worksheet["C6"].value),
        _cell_text(worksheet["C7"].value),
        f"Người bán: {_cell_text(worksheet['D8'].value)}",
        f"Địa chỉ: {_cell_text(worksheet['D9'].value)}",
        f"Số CMT: {_cell_text(worksheet['D10'].value)}",
        f"Cấp ngày: {_cell_text(worksheet['D11'].value)}",
        f"Nơi cấp: {_cell_text(worksheet['D12'].value)}",
        _cell_text(worksheet.cell(total_row + 1, 3).value),
        _cell_text(worksheet.cell(total_row + 3, 3).value),
        _cell_text(worksheet.cell(total_row + 4, 3).value),
    ]
    return {
        "document_type": "purchase_receipt",
        # Keep the manifest title generic; legal identity remains inside the
        # official PDF body and is represented by a one-way input hash only.
        "title": _cell_text(worksheet["C3"].value) or "GIẤY BIÊN NHẬN",
        "subtitle": _cell_text(worksheet["C4"].value),
        "columns": columns,
        "rows": rows,
        "summary": summary,
        "notes": [value for value in identity_notes if value],
        "signatures": [
            {"title": "BÊN MUA HÀNG", "hint": "Ký, ghi rõ họ tên"},
            {"title": "BÊN BÁN HÀNG", "hint": "Ký, ghi rõ họ tên"},
        ],
    }


def _monthly_report_header_row(worksheet) -> int | None:
    expected = [
        "khach hang", "ma khach hang", "doanh so ban", "gia von",
        "loi nhuan gop", "tong thanh toan",
    ]
    for row_index in range(1, min(worksheet.max_row, 10) + 1):
        if [
            _key(worksheet.cell(row_index, column).value)
            for column in range(2, 8)
        ] == expected:
            return row_index
    return None


def _monthly_report_section(worksheet, header_row: int) -> dict[str, Any]:
    headers = [
        "Nhóm khách hàng",
        *[
            _cell_text(worksheet.cell(header_row, column).value)
            for column in range(2, 8)
        ],
    ]
    columns = []
    for index, header in enumerate(headers, start=1):
        value_format, alignment = _column_format(header)
        columns.append({
            "key": f"c{index}",
            "label": header,
            "width": _column_weight(header),
            "format": value_format,
            "align": alignment,
        })

    rows = []
    summary = []
    previous_group = ""
    for row_index in range(header_row + 1, worksheet.max_row + 1):
        values = [worksheet.cell(row_index, column).value for column in range(1, 8)]
        if _key(values[0]) == "tong thang":
            summary = [
                {"label": "Doanh số bán", "value": values[3]},
                {"label": "Giá vốn", "value": values[4]},
                {"label": "Lợi nhuận gộp", "value": values[5]},
                {"label": "Tổng thanh toán", "value": values[6]},
            ]
            break
        if all(value in (None, "") for value in values):
            continue
        if all(value in (None, "") for value in values[:3]):
            values[0] = f"TỔNG {previous_group}" if previous_group else "TỔNG NHÓM"
        else:
            previous_group = _cell_text(values[0]) or previous_group
        rows.append({f"c{index}": value for index, value in enumerate(values, start=1)})
    if not summary:
        raise ValueError(f"Sheet {worksheet.title!r} thiếu dòng TỔNG THÁNG.")
    return {
        "document_type": "report",
        "title": "BÁO CÁO TỔNG HỢP",
        "subtitle": "Theo nhóm khách hàng, nhà thầu và mã bếp",
        "columns": columns,
        "rows": rows,
        "summary": summary,
        "notes": [f"Nguồn: {worksheet.title} · {len(rows)} dòng dữ liệu và tổng nhóm."],
        "signatures": [],
    }


def workbook_sections(document_type: str, workbook: Workbook) -> list[dict[str, Any]]:
    """Return PDF sections for every sheet of one application workbook."""

    sections: list[dict[str, Any]] = []
    for worksheet in workbook.worksheets:
        supplier_order = document_type == "supplier_orders"
        if document_type == "deliveries":
            delivery_header = _delivery_header_row(worksheet)
            if delivery_header is not None:
                sections.append(_delivery_section(worksheet, delivery_header))
                continue
        if document_type == "purchases":
            purchase_headers = _purchase_summary_header_rows(worksheet)
            if purchase_headers is not None:
                sections.append(_purchase_summary_section(worksheet, *purchase_headers))
                continue
            receipt_header = _receipt_header_row(worksheet)
            if receipt_header is not None:
                sections.append(_receipt_section(worksheet, receipt_header))
                continue
        if document_type == "report":
            report_header = _monthly_report_header_row(worksheet)
            if report_header is not None:
                sections.append(_monthly_report_section(worksheet, report_header))
                continue
        # Supplier workbooks may be the legacy 13-column layout or the
        # customer's canonical purchase sheet with hidden identity columns.
        # Project either form to at most ten useful paper columns.
        if supplier_order and _key(worksheet.title) == "huong dan":
            continue
        header_row, last_column = _header_row(worksheet, allow_wide=supplier_order)
        canonical_supplier_order = supplier_order and last_column > MAX_PDF_COLUMNS
        source_columns = list(range(1, last_column + 1))
        if canonical_supplier_order:
            wanted = {
                "ma hang", "ma bep", "ngay", "ten hang", "so luong dat ncc",
                "so luong", "sl thuc te", "dvt", "ncc", "gia mua", "thanh tien", "ghi chu",
            }
            source_columns = [
                column for column in source_columns
                if _key(worksheet.cell(header_row, column).value) in wanted
            ]
            if not source_columns or len(source_columns) > MAX_PDF_COLUMNS:
                raise ValueError(
                    f"Sheet {worksheet.title!r} không xác định được các cột cần in."
                )
        headers = [_cell_text(worksheet.cell(header_row, column).value) for column in source_columns]
        if any(not header for header in headers):
            raise ValueError(f"Sheet {worksheet.title!r} có cột tiêu đề trống.")
        columns = []
        for index, header in enumerate(headers, 1):
            value_format, alignment = _column_format(header)
            columns.append(
                {
                    "key": f"c{index}",
                    "label": header,
                    "width": _column_weight(header),
                    "format": value_format,
                    "align": alignment,
                }
            )
        rows = []
        header_columns = {
            _key(worksheet.cell(header_row, column).value): column
            for column in range(1, last_column + 1)
            if _key(worksheet.cell(header_row, column).value)
        }
        for row_index in range(header_row + 1, worksheet.max_row + 1):
            values = [
                _supplier_purchase_value(
                    worksheet, row_index, column, header_row, header_columns
                )
                if canonical_supplier_order else worksheet.cell(row_index, column).value
                for column in source_columns
            ]
            if all(value in (None, "") for value in values):
                continue
            rows.append({f"c{index}": value for index, value in enumerate(values, 1)})
        # In the customer's canonical sheet row 1 contains hidden subtotal
        # formulas, not a document title.
        title = worksheet.title if canonical_supplier_order else (
            _cell_text(worksheet.cell(1, 1).value) or worksheet.title
        )
        subtitle_parts = [_cell_text(worksheet.cell(2, 1).value)]
        if header_row > 3:
            preface = " · ".join(
                _cell_text(worksheet.cell(row_index, column).value)
                for row_index in range(3, header_row)
                for column in range(1, last_column + 1)
                if worksheet.cell(row_index, column).value not in (None, "")
            )
            if preface:
                subtitle_parts.append(preface)
        section = {
            "document_type": document_type,
            "title": title,
            "subtitle": " · ".join(part for part in subtitle_parts if part),
            "columns": columns,
            "rows": rows,
            "notes": [f"Nguồn: {worksheet.title} · {len(rows)} dòng dữ liệu."],
            "signatures": _signature_block(document_type),
        }
        sections.append(section)
    return sections


def workbooks_to_sections(documents: Mapping[str, Workbook] | Sequence[tuple[str, Workbook]]) -> list[dict[str, Any]]:
    """Flatten multiple application workbooks into deterministic PDF sections."""

    items = documents.items() if isinstance(documents, Mapping) else documents
    sections: list[dict[str, Any]] = []
    for document_type, workbook in items:
        sections.extend(workbook_sections(str(document_type), workbook))
    if not sections:
        raise ValueError("Không có chứng từ để tạo PDF.")
    return sections


__all__ = ["workbook_sections", "workbooks_to_sections"]
