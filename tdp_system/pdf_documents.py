"""Print-ready PDF generation for Thành Đạt Phát operational documents.

The module intentionally has no Flask or database dependency.  Callers pass plain
Python data, receive one A4 PDF containing one or more document sections, and can
store the returned manifest in the application audit log.

Expected section shape::

    {
        "document_type": "deliveries",
        "title": "PHIẾU GIAO HÀNG",
        "subtitle": "Bếp POT - Ngày 31/08/2026",
        "columns": [
            {"key": "index", "label": "STT", "width": 0.7, "align": "center"},
            {"key": "name", "label": "Tên hàng", "width": 3.5},
            {"key": "qty", "label": "SL", "width": 1, "format": "number"},
        ],
        "rows": [{"index": 1, "name": "Cà chua", "qty": 2.5}],
        "notes": ["Người nhận kiểm tra số lượng trước khi ký."],
        "signatures": [
            {"title": "NGƯỜI GIAO", "hint": "Ký, ghi rõ họ tên"},
            {"title": "NGƯỜI NHẬN", "hint": "Ký, ghi rõ họ tên"},
        ],
    }

Column ``width`` values are relative weights, not physical units.  Supported
formats are ``text``, ``number``, ``money``, ``percent`` and ``date``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from xml.sax.saxutils import escape

try:
    from pypdf import PdfReader
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import (
        KeepTogether,
        LongTable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:  # pragma: no cover - exercised by deployment checks.
    raise RuntimeError(
        "Chức năng PDF cần reportlab và pypdf; hãy cài đúng requirements trước khi chạy."
    ) from exc


PDF_FORMAT_VERSION = "1"
PAPER_NAME = "A4"
PAPER_SIZE = A4
MAX_SECTIONS = 100
MAX_ROWS_PER_SECTION = 50_000

NAVY = colors.HexColor("#17324D")
TEAL = colors.HexColor("#087F73")
PALE = colors.HexColor("#F5F8FB")
GRAY = colors.HexColor("#5E7083")
LIGHT_BORDER = colors.HexColor("#CBD5E1")


class PdfDocumentError(ValueError):
    """Raised when source data or the generated PDF fails validation."""


def _font_candidates() -> list[tuple[Path, Path]]:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = [
        (windows / "arial.ttf", windows / "arialbd.ttf"),
        (windows / "calibri.ttf", windows / "calibrib.ttf"),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/Library/Fonts/Arial Unicode.ttf"),
            Path("/Library/Fonts/Arial Bold.ttf"),
        ),
    ]
    return candidates


def register_unicode_fonts(
    regular_path: str | os.PathLike[str] | None = None,
    bold_path: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """Register and return a Unicode font pair suitable for Vietnamese text."""

    if regular_path or bold_path:
        if not regular_path or not bold_path:
            raise PdfDocumentError("Cần cung cấp đủ font thường và font đậm.")
        candidates = [(Path(regular_path), Path(bold_path))]
    else:
        candidates = _font_candidates()

    selected: tuple[Path, Path] | None = None
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            selected = (regular.resolve(), bold.resolve())
            break
    if selected is None:
        raise PdfDocumentError(
            "Không tìm thấy cặp font Unicode. Hãy cấu hình Arial hoặc DejaVu Sans."
        )

    regular, bold = selected
    fingerprint = hashlib.sha256(f"{regular}|{bold}".encode("utf-8")).hexdigest()[:10]
    regular_name = f"TDPUnicode-{fingerprint}"
    bold_name = f"TDPUnicodeBold-{fingerprint}"
    registered = set(pdfmetrics.getRegisteredFontNames())
    if regular_name not in registered:
        pdfmetrics.registerFont(TTFont(regular_name, str(regular)))
    if bold_name not in registered:
        pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
    pdfmetrics.registerFontFamily(
        regular_name,
        normal=regular_name,
        bold=bold_name,
        italic=regular_name,
        boldItalic=bold_name,
    )
    return {
        "regular_name": regular_name,
        "bold_name": bold_name,
        "regular_path": str(regular),
        "bold_path": str(bold),
    }


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain(item) for item in value]
    return str(value)


def _source_hash(sections: Sequence[Mapping[str, Any]]) -> str:
    raw = json.dumps(_plain(sections), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_text(value: Any) -> str:
    return escape(str(value if value is not None else "")).replace("\n", "<br/>")


def _text_key(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value or "")).split())


def _as_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError as exc:
        raise PdfDocumentError(f"Giá trị số không hợp lệ: {value!r}") from exc


def _format_number(value: Any, decimals: int | None = None) -> str:
    number = _as_number(value)
    if decimals is None:
        decimals = 0 if number.is_integer() else min(3, max(1, len(f"{number:.3f}".rstrip("0").split(".")[-1])))
    rendered = f"{number:,.{decimals}f}"
    return rendered.replace(",", "_").replace(".", ",").replace("_", ".")


def _format_value(value: Any, column: Mapping[str, Any]) -> str:
    kind = str(column.get("format") or "text").lower()
    if value in (None, ""):
        return ""
    if kind == "money":
        return _format_number(value, 0)
    if kind == "number":
        decimals = column.get("decimals")
        return _format_number(value, int(decimals) if decimals is not None else None)
    if kind == "percent":
        return f"{_format_number(_as_number(value) * 100, 2)}%"
    if kind == "date":
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        text = str(value).strip()
        for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, pattern).strftime("%d/%m/%Y")
            except ValueError:
                continue
        return text
    return str(value)


def _validate_sections(sections: Sequence[Mapping[str, Any]]) -> None:
    if not sections:
        raise PdfDocumentError("Bộ PDF phải có ít nhất một chứng từ.")
    if len(sections) > MAX_SECTIONS:
        raise PdfDocumentError(f"Một bộ PDF chỉ hỗ trợ tối đa {MAX_SECTIONS} chứng từ.")
    for section_index, section in enumerate(sections, start=1):
        title = str(section.get("title") or "").strip()
        columns = section.get("columns")
        rows = section.get("rows", [])
        if not title:
            raise PdfDocumentError(f"Chứng từ {section_index} thiếu tiêu đề.")
        if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)) or not columns:
            raise PdfDocumentError(f"Chứng từ {title!r} chưa có định nghĩa cột.")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise PdfDocumentError(f"Dữ liệu của chứng từ {title!r} phải là danh sách.")
        if len(rows) > MAX_ROWS_PER_SECTION:
            raise PdfDocumentError(
                f"Chứng từ {title!r} vượt quá {MAX_ROWS_PER_SECTION:,} dòng."
            )
        seen_keys: set[str] = set()
        for column in columns:
            if not isinstance(column, Mapping):
                raise PdfDocumentError(f"Định nghĩa cột của {title!r} không hợp lệ.")
            key = str(column.get("key") or "").strip()
            label = str(column.get("label") or "").strip()
            if not key or not label:
                raise PdfDocumentError(f"Một cột của {title!r} thiếu key hoặc label.")
            if key in seen_keys:
                raise PdfDocumentError(f"Chứng từ {title!r} bị trùng key cột {key!r}.")
            seen_keys.add(key)


class _NumberedCanvas(Canvas):
    """Canvas that adds stable company header and page X/Y footer."""

    def __init__(
        self,
        *args: Any,
        company: str,
        font_name: str,
        bold_font_name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []
        self._company = company
        self._font_name = font_name
        self._bold_font_name = bold_font_name

    def showPage(self) -> None:  # noqa: N802 - ReportLab public API name.
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header_footer(page_count)
            super().showPage()
        super().save()

    def _draw_header_footer(self, page_count: int) -> None:
        width, height = PAPER_SIZE
        self.saveState()
        self.setStrokeColor(NAVY)
        self.setLineWidth(0.5)
        self.line(18 * mm, height - 12 * mm, width - 18 * mm, height - 12 * mm)
        self.setFont(self._bold_font_name, 7.5)
        self.setFillColor(NAVY)
        self.drawString(18 * mm, height - 10 * mm, self._company[:100])
        self.setStrokeColor(LIGHT_BORDER)
        self.line(18 * mm, 12 * mm, width - 18 * mm, 12 * mm)
        self.setFont(self._font_name, 7.5)
        self.setFillColor(GRAY)
        self.drawString(18 * mm, 8.5 * mm, "Chứng từ tạo từ hệ thống Thành Đạt Phát")
        self.drawRightString(
            width - 18 * mm,
            8.5 * mm,
            f"Trang {self._pageNumber} / {page_count}",
        )
        self.restoreState()


def _styles(fonts: Mapping[str, str]) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    regular = fonts["regular_name"]
    bold = fonts["bold_name"]
    return {
        "title": ParagraphStyle(
            "TDPTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=15,
            leading=18,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "subtitle": ParagraphStyle(
            "TDPSubtitle",
            parent=base["Normal"],
            fontName=regular,
            fontSize=9,
            leading=12,
            textColor=GRAY,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "header": ParagraphStyle(
            "TDPHeader",
            parent=base["Normal"],
            fontName=bold,
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "left": ParagraphStyle(
            "TDPCellLeft",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8,
            leading=10,
            textColor=colors.black,
            alignment=TA_LEFT,
        ),
        "center": ParagraphStyle(
            "TDPCellCenter",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8,
            leading=10,
            textColor=colors.black,
            alignment=TA_CENTER,
        ),
        "right": ParagraphStyle(
            "TDPCellRight",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8,
            leading=10,
            textColor=colors.black,
            alignment=TA_RIGHT,
        ),
        "note": ParagraphStyle(
            "TDPNote",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8.5,
            leading=11,
            textColor=GRAY,
            leftIndent=2 * mm,
            bulletIndent=0,
            spaceAfter=1.5 * mm,
        ),
        "signature": ParagraphStyle(
            "TDPSignature",
            parent=base["Normal"],
            fontName=bold,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
        ),
        "signature_hint": ParagraphStyle(
            "TDPSignatureHint",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8,
            leading=10,
            textColor=GRAY,
            alignment=TA_CENTER,
        ),
    }


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    if isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
        return row[index] if index < len(row) else ""
    raise PdfDocumentError("Mỗi dòng chứng từ phải là object hoặc danh sách giá trị.")


def _section_story(
    section: Mapping[str, Any],
    styles: Mapping[str, ParagraphStyle],
    available_width: float,
) -> list[Any]:
    title = str(section["title"]).strip()
    subtitle = str(section.get("subtitle") or "").strip()
    columns = list(section["columns"])
    rows = list(section.get("rows", []))
    story: list[Any] = [Paragraph(_safe_text(title), styles["title"])]
    if subtitle:
        story.append(Paragraph(_safe_text(subtitle), styles["subtitle"]))

    weights = []
    for column in columns:
        try:
            weight = float(column.get("width", 1))
        except (TypeError, ValueError) as exc:
            raise PdfDocumentError(f"Cột {column.get('key')!r} có độ rộng không hợp lệ.") from exc
        if weight <= 0:
            raise PdfDocumentError(f"Cột {column.get('key')!r} phải có độ rộng dương.")
        weights.append(weight)
    total_weight = sum(weights)
    column_widths = [available_width * weight / total_weight for weight in weights]

    table_data: list[list[Any]] = [
        [Paragraph(_safe_text(column["label"]), styles["header"]) for column in columns]
    ]
    if rows:
        for row in rows:
            values = []
            for index, column in enumerate(columns):
                value = _row_value(row, str(column["key"]), index)
                formatted = _format_value(value, column)
                align = str(column.get("align") or "").lower()
                if not align:
                    align = "right" if str(column.get("format") or "text").lower() in {
                        "money",
                        "number",
                        "percent",
                    } else "left"
                if align not in {"left", "center", "right"}:
                    raise PdfDocumentError(
                        f"Cột {column.get('key')!r} có căn lề không hợp lệ: {align!r}."
                    )
                values.append(Paragraph(_safe_text(formatted), styles[align]))
            table_data.append(values)
    else:
        table_data.append(
            [Paragraph("Không có dữ liệu", styles["center"])]
            + [Paragraph("", styles["left"]) for _ in columns[1:]]
        )

    table = LongTable(
        table_data,
        colWidths=column_widths,
        repeatRows=1,
        hAlign="LEFT",
        splitByRow=1,
    )
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("GRID", (0, 0), (-1, -1), 0.35, LIGHT_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for row_index in range(2, len(table_data), 2):
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), PALE))
    if not rows and len(columns) > 1:
        commands.append(("SPAN", (0, 1), (-1, 1)))
    table.setStyle(TableStyle(commands))
    story.extend([table, Spacer(1, 3 * mm)])

    for note in section.get("notes") or []:
        story.append(Paragraph(f"• {_safe_text(note)}", styles["note"]))

    closing_block: list[Any] = []
    summary = section.get("summary") or []
    if isinstance(summary, Mapping):
        summary = list(summary.items())
    if summary:
        summary_rows = []
        for item in summary:
            if isinstance(item, Mapping):
                label, value = item.get("label", ""), item.get("value", "")
            elif (
                isinstance(item, Sequence)
                and not isinstance(item, (str, bytes, bytearray))
                and len(item) >= 2
            ):
                label, value = item[0], item[1]
            else:
                raise PdfDocumentError(f"Dòng tổng hợp của {title!r} không hợp lệ.")
            summary_rows.append(
                [Paragraph(_safe_text(label), styles["signature"]), Paragraph(_safe_text(value), styles["right"])]
            )
        summary_table = Table(summary_rows, colWidths=[available_width * 0.72, available_width * 0.28])
        summary_table.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 0.8, NAVY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        closing_block.extend([Spacer(1, 2 * mm), summary_table])

    signatures = list(section.get("signatures") or [])
    if signatures:
        signature_cells = []
        for item in signatures:
            if isinstance(item, Mapping):
                signature_title = item.get("title", "")
                hint = item.get("hint", "Ký, ghi rõ họ tên")
            else:
                signature_title = item
                hint = "Ký, ghi rõ họ tên"
            signature_cells.append(
                [
                    Paragraph(_safe_text(signature_title), styles["signature"]),
                    Paragraph(f"({_safe_text(hint)})", styles["signature_hint"]),
                    Spacer(1, 22 * mm),
                ]
            )
        signature_table = Table(
            [signature_cells],
            colWidths=[available_width / len(signature_cells)] * len(signature_cells),
        )
        signature_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ]))
        closing_block.extend([Spacer(1, 7 * mm), signature_table])
    if closing_block:
        # A total without its approval signatures is ambiguous on paper.  Move the
        # compact closing block as one unit when the current page has no room.
        story.append(KeepTogether(closing_block))
    return story


def verify_pdf(
    path: str | os.PathLike[str],
    *,
    required_texts: Iterable[str] = (),
    minimum_pages: int = 1,
) -> dict[str, Any]:
    """Perform structural, A4, Unicode-text and completeness checks."""

    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise PdfDocumentError(f"Không tìm thấy PDF: {pdf_path}")
    data = pdf_path.read_bytes()
    errors: list[str] = []
    if not data.startswith(b"%PDF-"):
        errors.append("Thiếu chữ ký đầu file PDF")
    if b"%%EOF" not in data[-2048:]:
        errors.append("Thiếu dấu kết thúc PDF")
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # pypdf provides detailed parser errors.
        raise PdfDocumentError(f"PDF không đọc được: {exc}") from exc
    if reader.is_encrypted:
        errors.append("PDF bị mã hóa")
    page_count = len(reader.pages)
    if page_count < minimum_pages:
        errors.append(f"PDF chỉ có {page_count} trang, tối thiểu cần {minimum_pages}")
    expected_width, expected_height = PAPER_SIZE
    page_sizes = []
    extracted = []
    for index, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        page_sizes.append([round(width, 2), round(height, 2)])
        if abs(width - expected_width) > 1 or abs(height - expected_height) > 1:
            errors.append(f"Trang {index} không đúng khổ A4 dọc")
        extracted.append(page.extract_text() or "")
    full_text = _text_key("\n".join(extracted))
    missing_texts = [text for text in required_texts if _text_key(text) not in full_text]
    if missing_texts:
        errors.append("Thiếu nội dung bắt buộc: " + ", ".join(repr(text) for text in missing_texts))
    result = {
        "ok": not errors,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "pages": page_count,
        "paper": PAPER_NAME,
        "page_sizes_points": page_sizes,
        "missing_required_texts": missing_texts,
        "errors": errors,
    }
    if errors:
        raise PdfDocumentError("; ".join(errors))
    return result


def build_pdf_bundle(
    sections: Sequence[Mapping[str, Any]],
    output_path: str | os.PathLike[str],
    *,
    company: str = "CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT",
    document_title: str = "Bộ chứng từ Thành Đạt Phát",
    subject: str = "Chứng từ vận hành đã duyệt",
    author: str = "Hệ thống Thành Đạt Phát",
    generated_at: str | None = None,
    regular_font_path: str | os.PathLike[str] | None = None,
    bold_font_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Build and verify one print-ready A4 PDF containing all ``sections``.

    The output is written atomically: a failed build/verification never replaces an
    existing valid target.  The returned manifest is safe to persist in audit logs.
    """

    _validate_sections(sections)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    fonts = register_unicode_fonts(regular_font_path, bold_font_path)
    styles = _styles(fonts)
    left_margin = 16 * mm
    right_margin = 16 * mm
    # Leave a dedicated band for the repeated company header.  LongTable starts
    # directly at the frame top on continuation pages, so 22 mm prevents it from
    # colliding with the 10-12 mm header line/text.
    top_margin = 22 * mm
    bottom_margin = 18 * mm
    available_width = PAPER_SIZE[0] - left_margin - right_margin
    generated_at = generated_at or datetime.now().replace(microsecond=0).isoformat(sep=" ")

    document = SimpleDocTemplate(
        str(temp),
        pagesize=PAPER_SIZE,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=document_title,
        subject=subject,
        author=author,
        creator="TDP PDF engine",
        producer="ReportLab",
        pageCompression=1,
    )
    story: list[Any] = []
    for index, section in enumerate(sections):
        if index:
            story.append(PageBreak())
        story.extend(_section_story(section, styles, available_width))

    canvas_factory = partial(
        _NumberedCanvas,
        company=company,
        font_name=fonts["regular_name"],
        bold_font_name=fonts["bold_name"],
    )
    try:
        document.build(story, canvasmaker=canvas_factory)
        required = [str(section["title"]).strip() for section in sections]
        verification = verify_pdf(temp, required_texts=required, minimum_pages=len(sections))
        os.replace(temp, target)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    section_manifest = [
        {
            "document_type": str(section.get("document_type") or "document"),
            "title": str(section["title"]).strip(),
            "rows": len(section.get("rows") or []),
        }
        for section in sections
    ]
    return {
        "ok": True,
        "format_version": PDF_FORMAT_VERSION,
        "file_name": target.name,
        "sha256": verification["sha256"],
        "bytes": verification["bytes"],
        "pages": verification["pages"],
        "paper": PAPER_NAME,
        "orientation": "portrait",
        "generated_at": generated_at,
        "input_sha256": _source_hash(sections),
        "section_count": len(sections),
        "row_count": sum(item["rows"] for item in section_manifest),
        "sections": section_manifest,
        "font_regular": fonts["regular_path"],
        "font_bold": fonts["bold_path"],
        "verification": verification,
    }


def write_manifest(manifest: Mapping[str, Any], path: str | os.PathLike[str]) -> Path:
    """Write a manifest atomically as UTF-8 JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temp.write_text(
        json.dumps(_plain(manifest), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, target)
    return target


__all__ = [
    "PDF_FORMAT_VERSION",
    "PAPER_NAME",
    "PdfDocumentError",
    "build_pdf_bundle",
    "register_unicode_fonts",
    "verify_pdf",
    "write_manifest",
]
