"""Generate visual regression artifacts with synthetic data, never the live DB."""
from pathlib import Path
from .test_delivery_export import delivery_payload, GOLDEN
from .delivery_export import build_delivery_workbook
from .test_receipt_export import receipt_row
from .receipt_export import build_purchase_documents_workbook
from .test_quote_export import row, VERSION
from .quote_export import build_contractor_quote_workbook
from .test_invoice_payment_documents import InvoicePaymentDocumentTests as Payment
from .invoice_payment_documents import invoice_payment_request_workbook
from .invoice_delivery_statement import invoice_delivery_statement_workbook
from .document_preview import create_snapshot
from .excel_print_renderer import build_excel_pdf_bundle


def sample_books():
    deliveries = delivery_payload()
    deliveries[0]['items'][0]['product_name'] = 'Chả cá loại ngon (90-100 miếng/kg)'
    deliveries[0]['items'][0]['quantity'] = .855123
    deliveries[0]['items'][0]['sell_price'] = 26465.5
    deliveries[0]['items'][1]['unit'] = 'Cái'
    deliveries[1]['items'][0]['quantity'] = .855123
    purchases = [receipt_row(product_name='Chả cá loại ngon (90-100 miếng/kg)', quantity=.855123,
                 buy_price=1000, amount=855, source_ref=1),
                 receipt_row(product_name='Mặt hàng nguyên chiếc', unit='Cái', quantity=2, buy_price=1000, amount=2000, source_ref=2)]
    return [('Phieu_giao.xlsx', build_delivery_workbook(deliveries, work_date='2026-09-05', template_path=GOLDEN)),
            ('Bang_ke_bien_nhan.xlsx', build_purchase_documents_workbook(purchases, template_path=GOLDEN,
                 buyer_name='Người mua kiểm thử', buyer_title='Nhân viên thu mua', company_name='CÔNG TY KIỂM THỬ', company_address='Địa chỉ kiểm thử')),
            ('Bao_gia.xlsx', build_contractor_quote_workbook([row('A01','Chả cá loại ngon (90-100 miếng/kg) tên dài cần xuống dòng',26465.5)],
                 contractor='HATRAN',recipient='BẾP KIỂM THỬ',period='2026-09',version=VERSION)),
            ('De_nghi_thanh_toan.xlsx', invoice_payment_request_workbook(Payment.payment_scope())),
            ('Bang_ke_giao_nhan.xlsx', invoice_delivery_statement_workbook(Payment.lines(),Payment.drafts(),
                 contractor='NT-A',period_from='2026-08-01',period_to='2026-08-31'))]


if __name__ == '__main__':
    root=Path('D:/TDP_ROUND4/artifacts'); root.mkdir(parents=True,exist_ok=True)
    books=sample_books()
    try:
        snapshot=create_snapshot(root,books)
        sources=[]
        for name,book in books:
            path=root/name; book.save(path)
            sources.append({'path':path,'document_type':'round4','title':name})
        result=build_excel_pdf_bundle(sources,root/'Chung_tu_kiem_tra.pdf',paper='A4')
        print('PDF pages:',result['pages'],'Sheets:',snapshot['sheet_count'],flush=True)
        import fitz
        with fitz.open(root/'Chung_tu_kiem_tra.pdf') as doc:
            for i,page in enumerate(doc):
                page.get_pixmap(matrix=fitz.Matrix(1.25,1.25)).save(root/f'page-{i+1}.png')
    finally:
        for _,book in books: book.close()
