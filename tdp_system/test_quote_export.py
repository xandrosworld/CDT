from __future__ import annotations

import unittest

try:
    from .quote_export import (
        QuoteExportError,
        build_contractor_quote_workbook,
        build_toyota_quote_workbook,
        contractor_quote_filename,
        quote_recipient,
    )
except ImportError:  # pragma: no cover - direct file invocation
    from quote_export import (
        QuoteExportError,
        build_contractor_quote_workbook,
        build_toyota_quote_workbook,
        contractor_quote_filename,
        quote_recipient,
    )


VERSION = {"version_no": 2, "source_hash": "A" * 64}


def row(code, name, price, tax="8%", *, state="numeric", exportable=True):
    return {
        "product_code": code,
        "product_name": name,
        "unit": "Kg",
        "tax": tax,
        "sell_price": price,
        "price_state": state,
        "exportable": exportable,
    }


class ToyotaQuoteExportTests(unittest.TestCase):
    def test_golden_shape_groups_code_sort_zero_and_source_trace(self):
        workbook = build_toyota_quote_workbook([
            row("P000016", "Nước lau sàn", 0, state="zero"),
            row("A000010", "Thịt mã mười", 120_000, "KKKNT"),
            row("B000003", "Cánh gà", 80_000, 0.1),
            row("A000002", "Thịt mã hai", 110_000, 0.08),
            row("A000099", "Không xuất", None, state="excluded", exportable=False),
        ], period="2026-09", version=VERSION)
        try:
            self.assertEqual(workbook.sheetnames, ["all"])
            sheet = workbook["all"]
            self.assertEqual(sheet["A1"].value, "CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT")
            self.assertEqual(sheet["A5"].value, "BẢNG BÁO GIÁ THÁNG 09 - NĂM 2026")
            self.assertEqual(sheet["A6"].value, "KÍNH GỬI: CÔNG TY TNHH TOYOTA NANKAI HẢI PHÒNG")
            self.assertEqual(
                [sheet.cell(8, column).value for column in range(1, 7)],
                ["STT", "MÃ", "TÊN THÀNH ĐẠT PHÁT", "ĐVT", "Giá chưa VAT", "Thuế"],
            )
            self.assertEqual(sheet.print_title_rows, "$8:$8")
            self.assertEqual(sheet.page_setup.orientation, "landscape")
            self.assertEqual(str(sheet.page_setup.paperSize), "9")
            self.assertEqual(sheet.page_setup.scale, 87)
            self.assertEqual(sheet.column_dimensions["C"].width, 42.825)
            self.assertIsNone(sheet["A8"].fill.patternType)

            group_rows = [
                cell.row for cell in sheet["C"]
                if cell.value in {"THỊT HEO", "GIA CẦM", "CHẤT TẨY RỬA-GIẤY CÁC LOẠI"}
            ]
            self.assertEqual(group_rows, [9, 12, 14])
            for group_row in group_rows:
                self.assertIsNone(sheet.cell(group_row, 3).fill.patternType)
                self.assertTrue(sheet.cell(group_row, 3).font.bold)
            product_rows = [
                row_number for row_number in range(9, sheet.max_row + 1)
                if sheet.cell(row_number, 2).value
            ]
            self.assertEqual(
                [sheet.cell(row_number, 2).value for row_number in product_rows],
                ["A000002", "A000010", "B000003", "P000016"],
            )
            self.assertEqual(
                [sheet.cell(row_number, 1).value for row_number in product_rows],
                [1, 2, 3, 4],
            )
            zero_row = product_rows[-1]
            self.assertEqual(sheet.cell(zero_row, 5).value, 0)
            self.assertEqual('#,##0', sheet.cell(zero_row, 5).number_format)
            self.assertEqual(sheet.cell(product_rows[0], 6).value, 0.08)
            self.assertEqual(sheet.cell(product_rows[0], 6).number_format, "0%")
            self.assertEqual(sheet.cell(product_rows[1], 6).value, "KKKNT")
            note_row = next(cell.row for cell in sheet["A"] if cell.value == "Báo giá trên chưa bao gồm VAT!")
            self.assertIsNone(sheet.cell(note_row, 4).value)
            self.assertIn("TOYOTA · kỳ 2026-09 · phiên bản 2", workbook.properties.subject)
            self.assertIn("A" * 64, workbook.properties.keywords)
            self.assertFalse(str(sheet.print_area))
            self.assertEqual(sheet.max_row, note_row + 3)
            self.assertFalse(workbook._external_links)
            self.assertFalse(any(
                cell.data_type == "f"
                for worksheet in workbook.worksheets
                for cells in worksheet.iter_rows()
                for cell in cells
            ))
        finally:
            workbook.close()

    def test_fail_closed_for_unconfirmed_duplicate_formula_and_bad_prices(self):
        with self.assertRaisesRegex(QuoteExportError, "chưa có phiên bản"):
            build_toyota_quote_workbook([], period="2026-09", version=None)
        with self.assertRaisesRegex(QuoteExportError, "nhiều hơn một dòng"):
            build_toyota_quote_workbook([
                row("A000001", "Một", 1), row("a000001", "Hai", 2),
            ], period="2026-09", version=VERSION)
        with self.assertRaisesRegex(QuoteExportError, "không được là công thức"):
            build_toyota_quote_workbook([
                row("A000001", "=HYPERLINK(\"bad\")", 1),
            ], period="2026-09", version=VERSION)
        for bad_price in (float("nan"), float("inf"), -1):
            with self.subTest(bad_price=bad_price):
                with self.assertRaises(QuoteExportError):
                    build_toyota_quote_workbook([
                        row("A000001", "Một", bad_price),
                    ], period="2026-09", version=VERSION)

    def test_contractor_neutral_shape_recipient_and_period_trace(self):
        expected = {
            "ATV": "CÔNG TY CỔ PHẦN SUẤT ĂN CÔNG NGHIỆP ATV",
            "HATRAN": "HÀ TRÂN",
            "NHUAHAIPHONG": "CÔNG TY CỔ PHẦN NHỰA VÀ CƠ KHÍ HẢI PHÒNG",
        }
        for index, (contractor, recipient) in enumerate(expected.items(), 1):
            with self.subTest(contractor=contractor):
                workbook = build_contractor_quote_workbook(
                    [row("A000001", "Một", index * 10_000)],
                    contractor=contractor,
                    recipient=quote_recipient(contractor),
                    period="2026-09",
                    version=VERSION,
                )
                try:
                    sheet = workbook["all"]
                    self.assertEqual(sheet["A6"].value, f"KÍNH GỬI: {recipient}")
                    self.assertEqual(sheet["B10"].value, "A000001")
                    self.assertEqual(sheet["E10"].value, index * 10_000)
                    note_row = next(
                        cell.row for cell in sheet["A"]
                        if cell.value == "Báo giá trên chưa bao gồm VAT!"
                    )
                    self.assertIsNone(sheet.cell(note_row, 4).value)
                    self.assertIn(
                        f"{contractor} · kỳ 2026-09 · phiên bản 2",
                        workbook.properties.subject,
                    )
                    self.assertEqual(
                        contractor_quote_filename(
                            contractor, period="2026-09", version_no=2,
                        ),
                        f"BAO_GIA_{contractor}_T09-2026_V2.xlsx",
                    )
                finally:
                    workbook.close()

    def test_daily_source_uses_same_shape_and_cannot_mix_with_period_version(self):
        source = {"batch_id": 17, "work_date": "2026-09-03", "source_name": "don-ngay.xlsx"}
        workbook = build_contractor_quote_workbook(
            [row("P000001", "Nước", 0, state="zero")],
            contractor="YLKHAN",
            recipient=quote_recipient("YLKHAN"),
            daily_source=source,
        )
        try:
            sheet = workbook["all"]
            self.assertEqual(sheet["A5"].value, "BẢNG BÁO GIÁ NGÀY 03/09/2026")
            self.assertEqual(sheet["A6"].value, "KÍNH GỬI: BẾP YLKHAN")
            self.assertEqual(sheet["E10"].value, 0)
            note_row = next(
                cell.row for cell in sheet["A"]
                if cell.value == "Báo giá trên chưa bao gồm VAT!"
            )
            self.assertIsNone(sheet.cell(note_row, 4).value)
            self.assertIn("YLKHAN · ngày 03/09/2026 · phiên đơn 17", workbook.properties.subject)
            self.assertEqual(
                contractor_quote_filename("YLKHAN", daily_source=source),
                "BAO_GIA_YLKHAN_2026-09-03_PHIEN_17.xlsx",
            )
        finally:
            workbook.close()
        with self.assertRaisesRegex(QuoteExportError, "đồng thời"):
            build_contractor_quote_workbook(
                [row("P000001", "Nước", 1)], contractor="YLKHAN",
                recipient="BẾP YLKHAN", period="2026-09", version=VERSION,
                daily_source=source,
            )


if __name__ == "__main__":
    unittest.main()
