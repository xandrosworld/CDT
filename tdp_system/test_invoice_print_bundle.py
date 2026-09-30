import io
import unittest

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from .invoice_print_bundle import combined_invoice_pdf

A4 = (595.275591, 841.889764)


def fixture_pdf(number, pages=1, size=A4):
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=size)
    for page in range(pages):
        canvas.drawString(20, size[1]-30, f'INVOICE {number} PAGE {page+1}')
        canvas.drawString(20, 20, f'END {number} PAGE {page+1}')
        canvas.showPage()
    canvas.save()
    return stream.getvalue()


class InvoicePrintBundleTests(unittest.TestCase):
    def test_each_invoice_starts_on_front_with_unchanged_source_pages(self):
        files = [(f'{number}.pdf', fixture_pdf(number, pages))
                 for number, pages in [(853,1),(854,3),(855,2),(856,1)]]
        content, count = combined_invoice_pdf(files, layout='invoice-per-sheet')
        reader = PdfReader(io.BytesIO(content))
        self.assertEqual(9, count)
        for offset, (_, original) in zip((0,2,6,8), files):
            self.assertEqual(0, offset % 2)
            for index, source in enumerate(PdfReader(io.BytesIO(original)).pages):
                side = reader.pages[offset+index]
                self.assertEqual(source.get_contents().get_data(), side.get_contents().get_data())
                self.assertEqual(source.mediabox, side.mediabox)
                self.assertEqual(source.extract_text(), side.extract_text())
        self.assertEqual('', reader.pages[1].extract_text())
        self.assertEqual('', reader.pages[5].extract_text())
        prefs = reader.trailer['/Root']['/ViewerPreferences']
        self.assertEqual('/DuplexFlipLongEdge', prefs['/Duplex'])

    def test_single_page_invoices_do_not_share_a_sheet(self):
        content, count = combined_invoice_pdf([(str(n), fixture_pdf(n)) for n in (1,2,3)], 'invoice-per-sheet')
        self.assertEqual(5, count)
        reader = PdfReader(io.BytesIO(content))
        self.assertIn('INVOICE 2', reader.pages[2].extract_text())
        self.assertIn('INVOICE 3', reader.pages[4].extract_text())

    def test_rotated_landscape_page_keeps_all_text(self):
        source = PdfReader(io.BytesIO(fixture_pdf(853, size=(842,595))))
        source.pages[0].rotate(90)
        writer = PdfWriter(); writer.add_page(source.pages[0])
        stream = io.BytesIO(); writer.write(stream)
        content, count = combined_invoice_pdf([('853',stream.getvalue())], 'invoice-per-sheet')
        page = PdfReader(io.BytesIO(content)).pages[0]
        self.assertEqual(1, count)
        self.assertIn('END 853 PAGE 1', page.extract_text())
        self.assertEqual(90, page.rotation)

    def test_original_pages_option_and_invalid_input(self):
        content, count = combined_invoice_pdf([('853',fixture_pdf(853,3))], 'pages')
        self.assertEqual(3, count)
        self.assertEqual(3, len(PdfReader(io.BytesIO(content)).pages))
        with self.assertRaises(ValueError):
            combined_invoice_pdf([('bad',b'not pdf')], 'invoice-per-sheet')
        with self.assertRaises(ValueError):
            combined_invoice_pdf([], 'invoice-per-sheet')
        with self.assertRaises(ValueError):
            combined_invoice_pdf([], 'unknown')


if __name__ == '__main__':
    unittest.main()
