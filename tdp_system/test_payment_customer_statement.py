from copy import deepcopy, copy
import unittest
from .test_invoice_payment_documents import InvoicePaymentDocumentTests as Fixtures
from .payment_customer_statement import customer_statement
from .invoice_payment_documents import InvoicePaymentDocumentError, invoice_payment_request_workbook
from .document_preview import white_print_style, sheet_preview


class CustomerStatementTests(unittest.TestCase):
    def test_both_payment_forms_keep_readable_fonts_and_allow_more_pages(self):
        scope=self.scope()
        for build in (customer_statement, invoice_payment_request_workbook):
            ws=build(scope).active
            self.assertEqual(0,ws.page_setup.fitToHeight)
            self.assertLess(sum(d.width for d in ws.column_dimensions.values()),140)
            for row in ws:
                for cell in row:
                    if cell.value is not None:
                        self.assertGreaterEqual(cell.font.sz,14)
                        self.assertFalse(cell.alignment.shrinkToFit)
        ws=customer_statement(scope).active
        self.assertIn('Bằng chữ:',ws['A14'].value)
        self.assertIn('A14:I14',str(ws.merged_cells))

    def scope(self):
        scope=Fixtures.payment_scope()
        scope['lines']=Fixtures.lines()
        return scope

    def test_nine_columns_and_new_contractor_without_special_mapping(self):
        scope=self.scope();scope['contractor']='NEW-CONTRACTOR'
        scope['snapshot']['buyer_name_snapshot']='NHÀ THẦU MỚI'
        before=deepcopy(scope);book=customer_statement(scope);sheet=book.active
        self.assertEqual(['STT','Tên hàng','ĐVT','Số lượng','Đơn giá','Thành tiền','Thuế suất','Tiền thuế','Thanh toán'],
                         [sheet.cell(10,c).value.strip() for c in range(1,10)])
        self.assertEqual(9,sheet.max_column)
        self.assertEqual('Khách hàng: NHÀ THẦU MỚI',sheet['A7'].value)
        self.assertEqual((200,16,216),tuple(sheet[f'{c}13'].value for c in ('F','H','I')))
        self.assertEqual(before,scope)
        font=copy(sheet['A5'].font);white_print_style(book)
        self.assertEqual(font,copy(sheet['A5'].font))
        self.assertIn('NHÀ THẦU MỚI',sheet_preview(sheet)['html'])

    def test_group_same_item_but_keep_different_prices(self):
        scope=self.scope();scope['lines'][1]['product_name']=scope['lines'][0]['product_name']
        book=customer_statement(scope)
        self.assertEqual(2,book.active['D11'].value)
        self.assertEqual(216,book.active['I11'].value)
        scope['lines'][1].update(qty=2,unit_price=50)
        book=customer_statement(scope)
        self.assertEqual((100,50),(book.active['E11'].value,book.active['E12'].value))

    def test_local_ratio_tax_matches_issued_invoice_tax_validation(self):
        for rate in ('8%', '8', 8, '0.08', .08):
            with self.subTest(rate=rate):
                scope=self.scope()
                for line in scope['lines']:line['tax']=rate
                ws=customer_statement(scope).active
                self.assertEqual('8%',ws['G11'].value)
                self.assertEqual(8,ws['H11'].value)
                self.assertEqual(216,ws['I13'].value)

    def test_source_vat_amount_is_used_and_mismatch_does_not_create_balancing_values(self):
        scope=self.scope();scope['lines'][0]['line_tax_amount']=6
        with self.assertRaisesRegex(InvoicePaymentDocumentError,'chưa khớp'):
            customer_statement(scope)
        scope['lines'][0]['line_tax_amount']=7;scope['lines'][1]['line_tax_amount']=9
        book=customer_statement(scope)
        self.assertEqual((7,9),(book.active['H11'].value,book.active['H12'].value))

    def test_many_items_expand_before_totals_and_signature(self):
        scope=self.scope();base=scope['lines'][0]
        scope['lines']=[dict(base,product_name=f'Mặt hàng {i}') for i in range(120)]
        scope['totals']=dict(subtotal=12000,tax_amount=960,total_amount=12960)
        scope['invoices'][0].update(scope['totals'])
        ws=customer_statement(scope).active
        self.assertEqual(12960,ws['I131'].value)
        self.assertIn('ĐẠI DIỆN',ws['A134'].value)
        self.assertEqual(0,ws.page_setup.fitToHeight)
        self.assertFalse(any(c.data_type=='f' for row in ws for c in row))

    def test_provider_fractional_vat_rounds_at_invoice_total_without_allocation(self):
        scope=self.scope();scope['lines'][0]['line_tax_amount']=7.79
        before=deepcopy(scope)
        book=customer_statement(scope)
        self.assertEqual(7.79,book.active['H11'].value)
        self.assertEqual(16,book.active['H13'].value)
        self.assertEqual(before,scope)
