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


MAX_PDF_COLUMNS = 10


def _key(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(char for char in text if unicodedata.category(char) != "Mn")).strip()


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _header_row(worksheet) -> tuple[int, int]:
    """Locate the first styled application table header and its last column."""

    for row_index in range(1, min(worksheet.max_row, 30) + 1):
        values = [_cell_text(worksheet.cell(row_index, column).value) for column in range(1, worksheet.max_column + 1)]
        last_column = max((index for index, value in enumerate(values, 1) if value), default=0)
        if last_column < 2:
            continue
        colored = 0
        bold = 0
        for column in range(1, last_column + 1):
            cell = worksheet.cell(row_index, column)
            if cell.fill and cell.fill.fill_type == "solid":
                colored += 1
            if cell.font and cell.font.bold:
                bold += 1
        if colored >= max(2, last_column // 2) and bold >= max(2, last_column // 2):
            if last_column > MAX_PDF_COLUMNS:
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
            {"title": "NGƯỜI GIAO", "hint": "Ký, ghi rõ họ tên"},
            {"title": "NGƯỜI NHẬN", "hint": "Ký, ghi rõ họ tên"},
        ]
    if document_type == "purchases":
        return [
            {"title": "NGƯỜI BÁN", "hint": "Ký, ghi rõ họ tên"},
            {"title": "NGƯỜI MUA", "hint": "Ký, ghi rõ họ tên"},
        ]
    return []


def workbook_sections(document_type: str, workbook: Workbook) -> list[dict[str, Any]]:
    """Return PDF sections for every sheet of one application workbook."""

    sections: list[dict[str, Any]] = []
    for worksheet in workbook.worksheets:
        header_row, last_column = _header_row(worksheet)
        headers = [_cell_text(worksheet.cell(header_row, column).value) for column in range(1, last_column + 1)]
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
        for row_index in range(header_row + 1, worksheet.max_row + 1):
            values = [worksheet.cell(row_index, column).value for column in range(1, last_column + 1)]
            if all(value in (None, "") for value in values):
                continue
            rows.append({f"c{index}": value for index, value in enumerate(values, 1)})
        title = _cell_text(worksheet.cell(1, 1).value) or worksheet.title
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
