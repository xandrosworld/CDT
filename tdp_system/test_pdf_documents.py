"""Independent regression tests for the print-ready PDF engine."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, A5

from tdp_system.pdf_documents import (
    PdfDocumentError,
    build_pdf_bundle,
    verify_pdf,
    write_manifest,
)


class PdfDocumentsTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def _sections(row_count: int = 140) -> list[dict[str, object]]:
        rows = [
            {
                "stt": index,
                "code": f"MH{index:04d}",
                "name": (
                    "Cá & rau <đặc biệt> – dòng rất dài để kiểm tra xuống dòng "
                    f"và dấu tiếng Việt số {index}"
                ),
                "quantity": index / 3,
                "unit": "kg",
                "unit_price": 12_500 + index,
                "amount": (12_500 + index) * index / 3,
            }
            for index in range(1, row_count + 1)
        ]
        columns = [
            {"key": "stt", "label": "STT", "width": 0.45, "align": "center"},
            {"key": "code", "label": "Mã hàng", "width": 0.8},
            {"key": "name", "label": "Tên hàng", "width": 2.8},
            {
                "key": "quantity",
                "label": "Số lượng",
                "width": 0.8,
                "format": "number",
            },
            {"key": "unit", "label": "ĐVT", "width": 0.55, "align": "center"},
            {
                "key": "unit_price",
                "label": "Đơn giá",
                "width": 0.9,
                "format": "money",
            },
            {
                "key": "amount",
                "label": "Thành tiền",
                "width": 1.05,
                "format": "money",
            },
        ]
        return [
            {
                "document_type": "delivery",
                "title": "PHIẾU GIAO HÀNG – BẾP POT",
                "subtitle": "Ngày 31/08/2026 · dữ liệu đã duyệt",
                "columns": columns,
                "rows": rows,
                "notes": [
                    "Người nhận kiểm tra số lượng, tình trạng hàng trước khi ký.",
                    "Hàng đặc thù có thể chuyển sang tên xuất hóa đơn đã thống nhất.",
                ],
                "summary": [
                    {"label": "Tổng số dòng", "value": f"{row_count} dòng"},
                    {"label": "Tổng tiền", "value": "48.500.000 VNĐ"},
                ],
                "signatures": [
                    {"title": "NGƯỜI GIAO", "hint": "Ký, ghi rõ họ tên"},
                    {"title": "NGƯỜI NHẬN", "hint": "Ký, ghi rõ họ tên"},
                ],
            },
            {
                "document_type": "payment_request",
                "title": "ĐỀ NGHỊ THANH TOÁN",
                "subtitle": "Nhà cung cấp Hà Trân",
                "columns": columns,
                "rows": rows[:3],
                "signatures": ["NGƯỜI LẬP", "GIÁM ĐỐC"],
            },
            {
                "document_type": "empty_statement",
                "title": "BẢNG KÊ ĐỐI CHIẾU",
                "columns": columns,
                "rows": [],
                "notes": ["Không phát sinh dữ liệu trong kỳ."],
            },
        ]

    def test_unicode_multipage_a4_page_numbers_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tdp_pdf_test_") as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "bo_chung_tu.pdf"
            manifest = build_pdf_bundle(
                self._sections(),
                pdf_path,
                generated_at="2026-08-31 08:30:00",
            )

            self.assertTrue(pdf_path.is_file())
            self.assertTrue(manifest["ok"])
            self.assertEqual(manifest["section_count"], 3)
            self.assertEqual(manifest["row_count"], 143)
            self.assertGreaterEqual(manifest["pages"], 4)
            self.assertEqual(manifest["paper"], "A4")
            self.assertEqual(len(manifest["sha256"]), 64)
            self.assertEqual(len(manifest["input_sha256"]), 64)
            self.assertEqual(
                manifest["sha256"], hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            )

            reader = PdfReader(str(pdf_path))
            self.assertEqual(len(reader.pages), manifest["pages"])
            all_text: list[str] = []
            for page_number, page in enumerate(reader.pages, start=1):
                self.assertAlmostEqual(float(page.mediabox.width), A4[0], delta=1.0)
                self.assertAlmostEqual(float(page.mediabox.height), A4[1], delta=1.0)
                text = page.extract_text() or ""
                all_text.append(text)
                self.assertIn("CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT", text)
                self.assertIn(f"Trang {page_number} / {len(reader.pages)}", text)

            extracted = "\n".join(all_text)
            self.assertIn("PHIẾU GIAO HÀNG – BẾP POT", extracted)
            self.assertIn("ĐỀ NGHỊ THANH TOÁN", extracted)
            self.assertIn("BẢNG KÊ ĐỐI CHIẾU", extracted)
            self.assertIn("Cá & rau <đặc biệt>", extracted)
            self.assertIn("Không có dữ liệu", extracted)
            self.assertIn("NGƯỜI NHẬN", extracted)

            manifest_path = write_manifest(manifest, root / "bo_chung_tu.manifest.json")
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["sha256"], manifest["sha256"])
            self.assertEqual(saved["input_sha256"], manifest["input_sha256"])

    def test_failed_build_does_not_replace_existing_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tdp_pdf_atomic_") as temp_dir:
            target = Path(temp_dir) / "approved.pdf"
            original = b"APPROVED-PDF-MUST-SURVIVE"
            target.write_bytes(original)
            invalid = self._sections(row_count=1)
            invalid[0]["rows"][0]["amount"] = "không phải số"  # type: ignore[index]

            with self.assertRaisesRegex(PdfDocumentError, "Giá trị số không hợp lệ"):
                build_pdf_bundle(invalid, target)

            self.assertEqual(target.read_bytes(), original)
            leftovers = list(target.parent.glob(f".{target.name}.*.tmp"))
            self.assertEqual(leftovers, [])

    def test_a5_bundle_uses_a5_pages_and_verification_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tdp_pdf_a5_") as temp_dir:
            pdf_path = Path(temp_dir) / "chung_tu_khac_a5.pdf"
            manifest = build_pdf_bundle(
                self._sections(row_count=3)[1:],
                pdf_path,
                paper="A5",
                generated_at="2026-09-01 10:00:00",
            )

            self.assertEqual(manifest["paper"], "A5")
            verified = verify_pdf(pdf_path, paper="A5", minimum_pages=2)
            self.assertEqual(verified["paper"], "A5")
            for page in PdfReader(str(pdf_path)).pages:
                self.assertAlmostEqual(float(page.mediabox.width), A5[0], delta=1.0)
                self.assertAlmostEqual(float(page.mediabox.height), A5[1], delta=1.0)
            with self.assertRaisesRegex(PdfDocumentError, "không đúng khổ A4"):
                verify_pdf(pdf_path, paper="A4")

    def test_verify_rejects_corrupt_pdf_and_missing_required_text(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tdp_pdf_verify_") as temp_dir:
            root = Path(temp_dir)
            corrupt = root / "corrupt.pdf"
            corrupt.write_bytes(b"%PDF-1.4\nnot-a-real-pdf\n%%EOF")
            with self.assertRaises(PdfDocumentError):
                verify_pdf(corrupt)

            valid = root / "valid.pdf"
            build_pdf_bundle(self._sections(row_count=1)[:1], valid)
            with self.assertRaisesRegex(PdfDocumentError, "Thiếu nội dung bắt buộc"):
                verify_pdf(valid, required_texts=["NỘI DUNG KHÔNG HỀ TỒN TẠI"])

    def test_rejects_empty_missing_and_duplicate_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tdp_pdf_schema_") as temp_dir:
            output = Path(temp_dir) / "invalid.pdf"
            with self.assertRaisesRegex(PdfDocumentError, "ít nhất một chứng từ"):
                build_pdf_bundle([], output)

            missing_title = self._sections(row_count=1)[:1]
            missing_title[0]["title"] = ""
            with self.assertRaisesRegex(PdfDocumentError, "thiếu tiêu đề"):
                build_pdf_bundle(missing_title, output)

            duplicate_key = self._sections(row_count=1)[:1]
            duplicate_key[0]["columns"][1]["key"] = "stt"  # type: ignore[index]
            with self.assertRaisesRegex(PdfDocumentError, "trùng key cột"):
                build_pdf_bundle(duplicate_key, output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
