"""Build a privacy-safe manifest for TDP golden/reference artifacts.

Only file/workbook topology is recorded. Cell values, document text, cached
external-link values and personally identifiable information are never copied
into the manifest.
"""

from __future__ import annotations

import hashlib
import io
import json
import posixpath
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = Path(__file__).resolve().parent / "golden_manifest.json"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_DOC_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_PACKAGE_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"x": MAIN_NS, "r": REL_DOC_NS, "pr": REL_PACKAGE_NS, "w": WORD_NS}


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    role: str
    candidates: tuple[Path, ...]


def _source_candidates(name: str) -> tuple[Path, ...]:
    return (ROOT / name, ROOT.parent / name, Path.home() / "Downloads" / name)


ARTIFACT_SPECS = (
    ArtifactSpec("em_thanh", "output_golden", _source_candidates("Em Thành.xlsx")),
    ArtifactSpec(
        "daily_order_2026_09_01",
        "input_contract",
        _source_candidates("Đơn hàng 01.09.2026.xlsx"),
    ),
    ArtifactSpec(
        "toyota_quote_2026_09",
        "output_golden",
        _source_candidates("BÁO GIÁ TOYOTA T09-2026.xlsx"),
    ),
    ArtifactSpec(
        "work_notes_2026_09_02",
        "requirements_reference",
        _source_candidates("Note công việc.docx"),
    ),
    ArtifactSpec(
        "payment_request_official_2026_09_03",
        "output_golden",
        _source_candidates("Đề nghị Thanh toán TĐP (T04.26).xlsx"),
    ),
    ArtifactSpec(
        "tax_kkknt",
        "output_golden",
        (ROOT / "bosung.30.8.26" / "thue 0.xlsx",),
    ),
    ArtifactSpec(
        "tax_vat_8",
        "output_golden",
        (ROOT / "bosung.30.8.26" / "thue 8.xlsx",),
    ),
    ArtifactSpec(
        "tax_vat_10",
        "output_golden",
        (ROOT / "bosung.30.8.26" / "thue 10.xlsx",),
    ),
    ArtifactSpec(
        "tax_vat_10_promotion",
        "output_golden",
        (ROOT / "bosung.30.8.26" / "thue 10 có khuyến mại.xlsx",),
    ),
    ArtifactSpec(
        "historical_payables",
        "historical_input",
        (ROOT / "bosung.30.8.26" / "Công nợ phải trả Thành Đạt Phát.xlsx",),
    ),
)


class GoldenManifestError(RuntimeError):
    """Raised when a required artifact is unavailable or malformed."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def resolve_artifact(spec: ArtifactSpec) -> Path:
    for candidate in spec.candidates:
        if candidate.is_file():
            return candidate.resolve()
    attempted = ", ".join(str(item) for item in spec.candidates)
    raise GoldenManifestError(f"Thiếu artifact {spec.artifact_id}; đã tìm: {attempted}")


def _xml(archive: zipfile.ZipFile, member: str) -> ET.Element:
    try:
        return ET.fromstring(archive.read(member))
    except (KeyError, ET.ParseError) as error:
        raise GoldenManifestError(f"Không đọc được cấu trúc OOXML: {member}") from error


def _relationship_targets(archive: zipfile.ZipFile, member: str) -> dict[str, tuple[str, str]]:
    root = _xml(archive, member)
    return {
        relationship.attrib["Id"]: (
            relationship.attrib.get("Target", ""),
            relationship.attrib.get("TargetMode", "Internal"),
        )
        for relationship in root.findall("pr:Relationship", NS)
    }


def _workbook_member(target: str) -> str:
    target = target.replace("\\", "/")
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return posixpath.normpath(target)
    return posixpath.normpath(posixpath.join("xl", target))


def _defined_print_metadata(workbook: ET.Element) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    defined_names = workbook.find("x:definedNames", NS)
    if defined_names is None:
        return result
    for item in defined_names.findall("x:definedName", NS):
        name = item.attrib.get("name", "")
        if name not in {"_xlnm.Print_Area", "_xlnm.Print_Titles"}:
            continue
        try:
            sheet_index = int(item.attrib["localSheetId"])
        except (KeyError, ValueError):
            continue
        key = "print_area" if name.endswith("Print_Area") else "print_titles"
        result.setdefault(sheet_index, {})[key] = item.text or ""
    return result


def _attributes(element: ET.Element | None, allowed: Iterable[str]) -> dict[str, str]:
    if element is None:
        return {}
    return {name: element.attrib[name] for name in allowed if name in element.attrib}


def inspect_xlsx(payload: bytes) -> dict[str, object]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as error:
        raise GoldenManifestError("File XLSX không phải gói OOXML hợp lệ") from error

    with archive:
        workbook = _xml(archive, "xl/workbook.xml")
        relationships = _relationship_targets(archive, "xl/_rels/workbook.xml.rels")
        print_metadata = _defined_print_metadata(workbook)
        sheets: list[dict[str, object]] = []

        sheet_root = workbook.find("x:sheets", NS)
        if sheet_root is None:
            raise GoldenManifestError("Workbook không có danh sách sheet")

        for index, sheet in enumerate(sheet_root.findall("x:sheet", NS)):
            relationship_id = sheet.attrib.get(f"{{{REL_DOC_NS}}}id", "")
            target, target_mode = relationships.get(relationship_id, ("", "Internal"))
            if not target or target_mode == "External":
                raise GoldenManifestError(
                    f"Không xác định được worksheet nội bộ cho sheet {sheet.attrib.get('name', index)}"
                )
            member = _workbook_member(target)
            worksheet = _xml(archive, member)
            dimension = worksheet.find("x:dimension", NS)
            merge_cells = worksheet.find("x:mergeCells", NS)
            merged_ranges = (
                [cell.attrib.get("ref", "") for cell in merge_cells.findall("x:mergeCell", NS)]
                if merge_cells is not None
                else []
            )
            formula_count = sum(1 for _ in worksheet.iter(f"{{{MAIN_NS}}}f"))
            page_setup = worksheet.find("x:pageSetup", NS)
            page_margins = worksheet.find("x:pageMargins", NS)
            sheet_view = worksheet.find("x:sheetViews/x:sheetView", NS)

            sheet_metadata: dict[str, object] = {
                "name": sheet.attrib.get("name", ""),
                "state": sheet.attrib.get("state", "visible"),
                "used_range": dimension.attrib.get("ref", "") if dimension is not None else "",
                "merged_ranges": merged_ranges,
                "formula_count": formula_count,
                "page_setup": _attributes(
                    page_setup,
                    ("paperSize", "orientation", "fitToWidth", "fitToHeight", "scale"),
                ),
                "page_margins": _attributes(
                    page_margins,
                    ("left", "right", "top", "bottom", "header", "footer"),
                ),
                "view": _attributes(sheet_view, ("showGridLines", "rightToLeft")),
            }
            sheet_metadata.update(print_metadata.get(index, {}))
            sheets.append(sheet_metadata)

        external_links = [
            name for name in archive.namelist() if name.startswith("xl/externalLinks/externalLink") and name.endswith(".xml")
        ]
        return {
            "kind": "xlsx",
            "sheet_count": len(sheets),
            "sheets": sheets,
            "external_link_count": len(external_links),
            "has_vba": "xl/vbaProject.bin" in archive.namelist(),
        }


def inspect_docx(payload: bytes) -> dict[str, object]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as error:
        raise GoldenManifestError("File DOCX không phải gói OOXML hợp lệ") from error

    with archive:
        document = _xml(archive, "word/document.xml")
        media = sorted(
            name for name in archive.namelist() if name.startswith("word/media/") and not name.endswith("/")
        )
        external_relationships = 0
        relationship_member = "word/_rels/document.xml.rels"
        if relationship_member in archive.namelist():
            relationships = _relationship_targets(archive, relationship_member)
            external_relationships = sum(1 for _, mode in relationships.values() if mode == "External")
        return {
            "kind": "docx",
            "paragraph_count": sum(1 for _ in document.iter(f"{{{WORD_NS}}}p")),
            "table_count": sum(1 for _ in document.iter(f"{{{WORD_NS}}}tbl")),
            "embedded_media_count": len(media),
            "embedded_media_extensions": sorted({Path(name).suffix.lower() for name in media}),
            "external_relationship_count": external_relationships,
        }


def inspect_artifact(spec: ArtifactSpec) -> dict[str, object]:
    path = resolve_artifact(spec)
    payload = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        topology = inspect_xlsx(payload)
    elif suffix == ".docx":
        topology = inspect_docx(payload)
    else:
        topology = {"kind": suffix.lstrip(".") or "binary"}
    return {
        "id": spec.artifact_id,
        "role": spec.role,
        "path": str(path),
        "size_bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "topology": topology,
    }


def build_manifest(specs: Iterable[ArtifactSpec] = ARTIFACT_SPECS) -> dict[str, object]:
    artifacts = [inspect_artifact(spec) for spec in specs]
    return {
        "schema_version": 1,
        "privacy": "metadata_only_no_cell_values_no_document_text",
        "artifacts": artifacts,
    }


def manifest_json(manifest: dict[str, object]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    try:
        rendered = manifest_json(build_manifest())
        OUTPUT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Golden manifest: {len(ARTIFACT_SPECS)} artifacts -> {OUTPUT_PATH}")
        return 0
    except (GoldenManifestError, OSError) as error:
        print(f"Golden manifest FAILED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
