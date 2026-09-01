from __future__ import annotations

import unittest

try:
    from contract_modules import (
        invoice_delivery_statement_workbook,
        invoice_payment_request_document,
    )
except ImportError:  # pragma: no cover
    from .contract_modules import (
        invoice_delivery_statement_workbook,
        invoice_payment_request_document,
    )


class InvoicePaymentDocumentTests(unittest.TestCase):
    @staticmethod
    def drafts(total=216):
        return [{
            "id": 1,
            "issued_invoice_date": "2026-08-29",
            "issued_invoice_series": "1C26TDP",
            "issued_invoice_number": "00001234",
            "subtotal": 200,
            "tax_amount": 16,
            "total_amount": total,
        }]

    @staticmethod
    def lines():
        base = {
            "draft_id": 1,
            "work_date": "2026-08-29",
            "issued_invoice_date": "2026-08-29",
            "issued_invoice_series": "1C26TDP",
            "issued_invoice_number": "00001234",
            "kitchen": "POT",
            "product_code": "I000060",
            "product_name": "Hành tây",
            "unit": "Kg",
            "qty": 1,
            "unit_price": 100,
            "amount": 100,
            "tax": "8%",
        }
        return [dict(base), {**base, "product_code": "I000061", "product_name": "Hành khô"}]

    def test_docx_contains_invoice_identity_totals_and_repeating_header(self):
        document = invoice_payment_request_document(
            company="CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT",
            company_tax_code="0202265016",
            company_address="Hải Phòng",
            recipient="CÔNG TY QC BUYER",
            recipient_tax_code="0200000000",
            recipient_address="Địa chỉ QC",
            requester="VŨ THỊ THỤY",
            bank_name="Vietcombank",
            bank_account="1052787580",
            period_from="2026-08-01",
            period_to="2026-08-31",
            details=[{
                "invoice_date": "2026-08-29", "invoice_series": "1C26TDP",
                "invoice_number": "00001234", "subtotal": 200,
                "tax_amount": 16, "total_amount": 216,
            }],
        )
        text = "\n".join(
            [paragraph.text for paragraph in document.paragraphs]
            + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
        )
        for required in (
            "ĐỀ NGHỊ THANH TOÁN", "0202265016", "CÔNG TY QC BUYER",
            "0200000000", "1C26TDP / 00001234", "1052787580",
        ):
            self.assertIn(required, text)
        self.assertTrue(document.tables[1].rows[0]._tr.xpath("./w:trPr/w:tblHeader"))

    def test_delivery_statement_reconciles_and_blocks_mismatch(self):
        workbook = invoice_delivery_statement_workbook(self.lines(), self.drafts(), lambda _: 1.08)
        try:
            self.assertEqual(workbook.sheetnames, ["Bảng kê giao hàng", "Đối chiếu hóa đơn"])
            reconcile = workbook["Đối chiếu hóa đơn"]
            self.assertEqual(reconcile.cell(4, 10).value, 0)
        finally:
            workbook.close()
        with self.assertRaisesRegex(ValueError, "lệch bảng kê"):
            invoice_delivery_statement_workbook(self.lines(), self.drafts(total=218), lambda _: 1.08)


if __name__ == "__main__":
    unittest.main()
