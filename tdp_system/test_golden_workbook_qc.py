from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from PIL import Image

try:
    from .golden_workbook_qc import (
        WorkbookQCError,
        WorkbookQCReport,
        _assert_sheet_safe,
        compare_workbooks,
        image_difference_ratio,
    )
except ImportError:  # pragma: no cover - direct file invocation
    from golden_workbook_qc import (  # type: ignore
        WorkbookQCError,
        WorkbookQCReport,
        _assert_sheet_safe,
        compare_workbooks,
        image_difference_ratio,
    )


def save_fixture(path: Path, *, bad: bool) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "QC"
    sheet.append(["Mã hàng", "Số lượng"] if not bad else ["Số lượng", "Mã hàng"])
    sheet.append(["A", 2])
    sheet.append(["TỔNG", 2 if not bad else 3])
    sheet.print_area = "A1:B3" if not bad else "A1:B2"
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.paperSize = "9"
    workbook.save(path)
    workbook.close()


class GoldenWorkbookQCTests(unittest.TestCase):
    def test_data_topology_and_total_differences_are_detected_without_values_in_report(self):
        with tempfile.TemporaryDirectory(prefix="tdp_golden_qc_") as temp_name:
            directory = Path(temp_name)
            golden = directory / "golden.xlsx"
            candidate = directory / "candidate.xlsx"
            save_fixture(golden, bad=False)
            save_fixture(candidate, bad=True)

            report = compare_workbooks(golden, candidate)
            rendered = json.dumps(report.as_dict(), ensure_ascii=False)

            self.assertFalse(report.layers["data"]["ok"])
            self.assertFalse(report.layers["topology"]["ok"])
            self.assertTrue(any(issue["location"] == "A1" for issue in report.issues if issue["layer"] == "data"))
            self.assertTrue(any(issue["location"] == "B3" for issue in report.issues if issue["layer"] == "data"))
            self.assertTrue(any(issue["kind"] == "print_area" for issue in report.issues))
            self.assertNotIn("Mã hàng", rendered)
            self.assertNotIn("Số lượng", rendered)

    def test_image_difference_ratio_detects_visual_change(self):
        with tempfile.TemporaryDirectory(prefix="tdp_visual_qc_") as temp_name:
            first = Path(temp_name) / "first.png"
            second = Path(temp_name) / "second.png"
            Image.new("RGB", (20, 20), "white").save(first)
            changed = Image.new("RGB", (20, 20), "white")
            for x in range(5):
                for y in range(5):
                    changed.putpixel((x, y), (0, 0, 0))
            changed.save(second)
            self.assertEqual(0.0, image_difference_ratio(first, first))
            self.assertGreater(image_difference_ratio(first, second), 0.0)

    def test_sensitive_identity_sheet_is_never_rendered(self):
        for name in ("CCCD", "C.M.T", "cmnd"):
            with self.assertRaises(WorkbookQCError):
                _assert_sheet_safe(name)

    def test_report_requires_visual_layer_before_overall_pass(self):
        report = WorkbookQCReport("golden.xlsx", "candidate.xlsx")
        self.assertFalse(report.ok)
        report.layers["visual"].update({"ok": True, "status": "compared"})
        self.assertTrue(report.ok)


if __name__ == "__main__":
    unittest.main()
