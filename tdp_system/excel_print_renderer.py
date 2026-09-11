"""Render operational Excel workbooks to PDF without redrawing customer forms.

The customer's Excel sheets are the print artwork.  Converting them into a
generic table destroys legal headings, merged cells, signatures and page
geometry.  This module therefore asks the installed Microsoft Excel to export
each visible worksheet, then merges the resulting PDFs in workbook/sheet order.

The import of pywin32 is deliberately lazy so ordinary application startup and
non-Windows unit tests do not require a running Excel installation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import DictionaryObject, NameObject
from reportlab.lib.pagesizes import A4, A5


EXCEL_PAPER_SIZES = {"A4": 9, "A5": 11}
PDF_PAPER_SIZES = {"A4": A4, "A5": A5}
FORMAT_VERSION = "tdp-excel-artwork-pdf-v4"


class ExcelPrintError(RuntimeError):
    """Raised when an exact-form Excel print bundle cannot be produced."""


class ReceiptPrintError(ExcelPrintError):
    code = 'receipt_requires_one_page'


def is_receipt_sheet(name: str) -> bool:
    return bool(re.fullmatch(r'biên nhận(?:\s+\d+)?', str(name).strip().casefold()))


def _clean_source(source: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(source.get("path") or "").resolve()
    document_type = str(source.get("document_type") or "document").strip()
    if not path.is_file():
        raise ExcelPrintError(f"Không tìm thấy file Excel cần in: {path.name or 'không rõ tên'}")
    if path.suffix.casefold() not in {".xlsx", ".xlsm"}:
        raise ExcelPrintError(f"File cần in không phải Excel hợp lệ: {path.name}")
    return {
        "path": path,
        "document_type": document_type,
        "title": str(source.get("title") or document_type).strip(),
    }


def _input_sha256(sources: Sequence[Mapping[str, Any]], paper: str, duplex: bool = False) -> str:
    digest = hashlib.sha256()
    digest.update(FORMAT_VERSION.encode("ascii"))
    digest.update(paper.encode("ascii"))
    digest.update(b'duplex' if duplex else b'simplex')
    for source in sources:
        metadata = {
            "document_type": source["document_type"],
            "title": source["title"],
            "file_name": source["path"].name,
        }
        digest.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        with source["path"].open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _page_size_matches(width: float, height: float, paper: str, tolerance: float = 3.0) -> bool:
    expected_width, expected_height = PDF_PAPER_SIZES[paper]
    portrait = abs(width - expected_width) <= tolerance and abs(height - expected_height) <= tolerance
    landscape = abs(width - expected_height) <= tolerance and abs(height - expected_width) <= tolerance
    return portrait or landscape


def _raw_pdf_page_count(path: Path) -> int:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ExcelPrintError("Microsoft Excel đã tạo một file PDF không đọc được") from exc
    if reader.is_encrypted or not reader.pages:
        raise ExcelPrintError("Microsoft Excel đã tạo một file PDF trống hoặc bị mã hóa")
    return len(reader.pages)


def verify_excel_pdf(
    path: str | os.PathLike[str],
    *,
    paper: str,
    minimum_pages: int = 1,
) -> dict[str, Any]:
    """Verify a PDF while accepting both portrait and landscape pages."""

    paper_name = str(paper or "").strip().upper()
    if paper_name not in PDF_PAPER_SIZES:
        raise ExcelPrintError("Chứng từ chỉ hỗ trợ khổ A4 hoặc A5")
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise ExcelPrintError("Excel không tạo được file PDF")
    payload = pdf_path.read_bytes()
    if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-2048:]:
        raise ExcelPrintError("File Excel xuất ra không phải PDF hoàn chỉnh")
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise ExcelPrintError(f"Không đọc được PDF do Excel tạo: {type(exc).__name__}") from exc
    if reader.is_encrypted:
        raise ExcelPrintError("PDF do Excel tạo đang bị mã hóa")
    if len(reader.pages) < minimum_pages:
        raise ExcelPrintError(
            f"PDF chỉ có {len(reader.pages)} trang, tối thiểu cần {minimum_pages} trang"
        )
    page_sizes: list[list[float]] = []
    orientations: list[str] = []
    for index, page in enumerate(reader.pages, 1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        page_sizes.append([round(width, 2), round(height, 2)])
        orientations.append("landscape" if width > height else "portrait")
        if not _page_size_matches(width, height, paper_name):
            raise ExcelPrintError(
                f"Trang {index} không đúng khổ {paper_name} "
                f"({width:.2f} x {height:.2f} point)"
            )
    return {
        "ok": True,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "pages": len(reader.pages),
        "paper": paper_name,
        "page_sizes_points": page_sizes,
        "orientations": orientations,
    }


def _export_libreoffice_sheets(sources, *, paper, render_dir):
    """Render preserved workbook artwork on Linux using isolated Calc profiles."""
    from openpyxl import load_workbook
    executable = shutil.which('libreoffice') or shutil.which('soffice')
    if not executable:
        raise ExcelPrintError('Máy chủ chưa cài bộ chuyển PDF LibreOffice')
    rendered = []
    profile = render_dir / 'lo-profile'
    for source_index, source in enumerate(sources, 1):
        probe = load_workbook(source['path'], read_only=False, data_only=False)
        names = [sheet.title for sheet in probe if sheet.sheet_state == 'visible']
        probe.close()
        for sheet_index, name in enumerate(names, 1):
            workbook = load_workbook(source['path'], read_only=False, data_only=False)
            try:
                selected = workbook[name]
                for sheet in workbook:
                    sheet.sheet_state = 'visible' if sheet.title == name else 'hidden'
                    sheet.sheet_view.tabSelected = sheet.title == name
                    if sheet.title != name:
                        # Calc exports hidden XLSX sheets that retain print ranges.
                        # Keep formula dependencies, but remove their print definitions
                        # only in this disposable rendering copy.
                        sheet.print_area = None
                workbook.active = workbook.index(selected)
                selected.page_setup.paperSize = str(EXCEL_PAPER_SIZES[paper])
                selected.page_setup.fitToWidth = 1
                selected.sheet_properties.pageSetUpPr.fitToPage = True
                path = render_dir / f'{source_index:02d}_{sheet_index:03d}.xlsx'
                workbook.save(path)
            finally:
                workbook.close()
            try:
                result = subprocess.run([executable, '-env:UserInstallation=' + profile.as_uri(),
                    '--headless', '--nologo', '--nodefault', '--norestore', '--convert-to',
                    'pdf:calc_pdf_Export:{"SinglePageSheets":{"type":"boolean","value":"false"}}',
                    '--outdir', str(render_dir), str(path)],
                    capture_output=True, timeout=120)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ExcelPrintError('Chưa chuyển được PDF trên máy chủ; hãy thử lại.') from exc
            pdf_path = path.with_suffix('.pdf')
            if result.returncode or not pdf_path.is_file():
                raise ExcelPrintError('Bộ chuyển PDF không tạo được chứng từ. File Excel vẫn có thể tải.')
            rendered.append({'path': pdf_path, 'document_type': source['document_type'],
                'title': source['title'], 'workbook': source['path'].name, 'sheet': name,
                'pages': _raw_pdf_page_count(pdf_path)})
    if not rendered:
        raise ExcelPrintError('Không có trang Excel hiển thị để tạo PDF')
    return rendered


def _export_visible_sheets(
    sources: Sequence[Mapping[str, Any]],
    *,
    paper: str,
    render_dir: Path,
) -> list[dict[str, Any]]:
    if os.name != "nt":
        return _export_libreoffice_sheets(sources, paper=paper, render_dir=render_dir)
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise ExcelPrintError("Máy đang thiếu thành phần kết nối Microsoft Excel") from exc

    pythoncom.CoInitialize()
    excel = None
    rendered: list[dict[str, Any]] = []
    try:
        try:
            excel = win32com.client.DispatchEx("Excel.Application")
        except Exception as exc:
            raise ExcelPrintError(
                "Không mở được Microsoft Excel để tạo bản in đúng mẫu khách"
            ) from exc
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AskToUpdateLinks = False
        excel.EnableEvents = False
        excel.AutomationSecurity = 3

        for source_index, source in enumerate(sources, 1):
            workbook = None
            try:
                workbook = excel.Workbooks.Open(
                    Filename=str(source["path"]),
                    UpdateLinks=0,
                    ReadOnly=True,
                    AddToMru=False,
                    IgnoreReadOnlyRecommended=True,
                    Notify=False,
                )
                for sheet_index in range(1, workbook.Worksheets.Count + 1):
                    worksheet = workbook.Worksheets(sheet_index)
                    # xlSheetVisible is -1.  Hidden control/evidence sheets must
                    # never leak into the customer's printed bundle.
                    if int(worksheet.Visible) != -1:
                        continue
                    try:
                        page_setup = worksheet.PageSetup
                        page_setup.PaperSize = EXCEL_PAPER_SIZES[paper]
                        page_setup.Zoom = False
                        page_setup.FitToPagesWide = 1
                        # Keep each sheet's own FitToPagesTall.  Receipts use one
                        # page; long listings deliberately paginate vertically.
                    except Exception as exc:
                        raise ExcelPrintError(
                            f"Không đặt được khổ {paper} cho trang {worksheet.Name}"
                        ) from exc
                    pdf_path = render_dir / f"{source_index:02d}_{sheet_index:03d}.pdf"
                    try:
                        worksheet.ExportAsFixedFormat(
                            Type=0,
                            Filename=str(pdf_path),
                            Quality=0,
                            IncludeDocProperties=False,
                            IgnorePrintAreas=False,
                            OpenAfterPublish=False,
                        )
                    except Exception as exc:
                        raise ExcelPrintError(
                            f"Microsoft Excel không xuất được trang {worksheet.Name}"
                        ) from exc
                    rendered.append({
                        "path": pdf_path,
                        "document_type": source["document_type"],
                        "title": source["title"],
                        "workbook": source["path"].name,
                        "sheet": str(worksheet.Name),
                        "pages": _raw_pdf_page_count(pdf_path),
                    })
            finally:
                if workbook is not None:
                    workbook.Close(SaveChanges=False)
        if not rendered:
            raise ExcelPrintError("Không có trang Excel hiển thị để tạo PDF")
        return rendered
    finally:
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _merge_pdfs(rendered: Sequence[Mapping[str, Any]], target: Path, *, paper: str, duplex: bool = False) -> dict:
    """Merge and normalize pages to real A4/A5 dimensions without distortion.

    Excel's PDF exporter may follow the Windows default printer's Letter media
    even after ``PageSetup.PaperSize`` is A4.  Place the original page on a
    correctly sized blank page, preserving aspect ratio and centering it.  This
    keeps the exact sheet artwork while guaranteeing the approved paper size.
    """

    writer = PdfWriter()
    layout, blank_pages = [], []
    binding_landscape = None
    def blank_back():
        previous = writer.pages[-1]
        writer.add_blank_page(width=float(previous.mediabox.width), height=float(previous.mediabox.height))
        blank_pages.append(len(writer.pages))
    try:
        for item in rendered:
            reader = PdfReader(str(item["path"]))
            receipt = is_receipt_sheet(item.get('sheet', ''))
            if receipt and len(reader.pages) != 1:
                raise ReceiptPrintError(f"Biên nhận {item.get('sheet')} đang có {len(reader.pages)} trang. Cần dàn về một trang trước khi in để mỗi người có một tờ riêng.")
            if duplex and receipt and len(writer.pages) % 2:
                blank_back()
            start_page = len(writer.pages) + 1
            for page in reader.pages:
                source_width = float(page.mediabox.width)
                source_height = float(page.mediabox.height)
                if not receipt and binding_landscape is None:
                    binding_landscape = source_width > source_height
                base_width, base_height = PDF_PAPER_SIZES[paper]
                if source_width > source_height:
                    target_width, target_height = base_height, base_width
                else:
                    target_width, target_height = base_width, base_height
                scale = min(target_width / source_width, target_height / source_height)
                offset_x = (target_width - source_width * scale) / 2
                offset_y = (target_height - source_height * scale) / 2
                output_page = writer.add_blank_page(width=target_width, height=target_height)
                output_page.merge_transformed_page(
                    page,
                    Transformation().scale(scale).translate(offset_x, offset_y),
                )
            layout.append({'sheet':item.get('sheet',''), 'start_page':start_page,
                           'end_page':len(writer.pages), 'receipt':receipt})
            if duplex and receipt:
                blank_back()
        if binding_landscape is None and writer.pages:
            binding_landscape = writer.pages[0].mediabox.width > writer.pages[0].mediabox.height
        edge = '/DuplexFlipShortEdge' if binding_landscape else '/DuplexFlipLongEdge'
        writer._root_object[NameObject('/ViewerPreferences')] = DictionaryObject({
            NameObject('/Duplex'): NameObject(edge if duplex else '/Simplex')})
        with target.open("wb") as handle:
            writer.write(handle)
        return {'sections':layout, 'blank_pages':blank_pages, 'total_pages':len(writer.pages)}
    finally:
        writer.close()


def build_excel_pdf_bundle(
    sources: Sequence[Mapping[str, Any]],
    output_path: str | os.PathLike[str],
    *,
    paper: str,
    generated_at: str | None = None,
    duplex: bool = False,
) -> dict[str, Any]:
    """Export and merge visible Excel sheets while preserving their artwork."""

    paper_name = str(paper or "").strip().upper()
    if paper_name not in EXCEL_PAPER_SIZES:
        raise ExcelPrintError("Chứng từ chỉ hỗ trợ khổ A4 hoặc A5")
    normalized = [_clean_source(source) for source in sources]
    if not normalized:
        raise ExcelPrintError("Không có file Excel để tạo bộ in")

    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    render_dir = Path(tempfile.mkdtemp(prefix="tdp_excel_print_", dir=target.parent))
    temp_target = render_dir / "merged.pdf"
    try:
        rendered = _export_visible_sheets(normalized, paper=paper_name, render_dir=render_dir)
        layout = _merge_pdfs(rendered, temp_target, paper=paper_name, duplex=duplex)
        verification = verify_excel_pdf(
            temp_target,
            paper=paper_name,
            minimum_pages=layout['total_pages'],
        )
        os.replace(temp_target, target)
    except ExcelPrintError:
        raise
    except Exception as exc:
        raise ExcelPrintError(f"Không tạo được bộ PDF đúng mẫu: {type(exc).__name__}") from exc
    finally:
        shutil.rmtree(render_dir, ignore_errors=True)

    sections = [
        {
            "document_type": item["document_type"],
            "title": item["title"],
            "workbook": item["workbook"],
            "sheet": item["sheet"],
            "pages": item["pages"],
        }
        for item in rendered
    ]
    document_types = list(dict.fromkeys(item["document_type"] for item in sections))
    return {
        "ok": True,
        "format_version": FORMAT_VERSION,
        "file_name": target.name,
        "sha256": verification["sha256"],
        "bytes": verification["bytes"],
        "pages": verification["pages"],
        "paper": paper_name,
        "orientation": "mixed",
        "duplex": duplex,
        "page_layout": layout,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "input_sha256": _input_sha256(normalized, paper_name, duplex),
        "section_count": len(sections),
        "document_count": len(document_types),
        "sections": sections,
        "verification": verification,
    }


__all__ = [
    "ExcelPrintError",
    "build_excel_pdf_bundle",
    "verify_excel_pdf",
]
