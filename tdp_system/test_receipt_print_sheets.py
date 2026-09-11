import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen.canvas import Canvas
from .excel_print_renderer import _merge_pdfs, ReceiptPrintError


class ReceiptPrintSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def source(self, name, pages, label, horizontal=False):
        path = self.root / (label + '.pdf')
        canvas = Canvas(str(path), pagesize=landscape(A4) if horizontal else A4)
        for i in range(pages):
            canvas.drawString(40, 100, f'{label} - page {i+1} - amount 123456')
            canvas.showPage()
        canvas.save()
        return {'sheet':name, 'path':path, 'pages':pages}

    def check(self, sources, duplex):
        originals = {s['path']:s['path'].read_bytes() for s in sources}
        target = self.root / 'result.pdf'
        layout = _merge_pdfs(sources, target, paper='A4', duplex=duplex)
        reader = PdfReader(target)
        self.assertEqual(len(reader.pages),layout['total_pages'])
        for number in layout['blank_pages']:
            self.assertFalse((reader.pages[number-1].extract_text() or '').strip())
        for item in layout['sections']:
            if item['receipt']:
                self.assertEqual(item['start_page'],item['end_page'])
                if duplex:
                    self.assertEqual(item['start_page'] % 2,1)
                    self.assertIn(item['end_page']+1,layout['blank_pages'])
        for p, data in originals.items():self.assertEqual(p.read_bytes(),data)
        self.assertEqual(reader.trailer['/Root']['/ViewerPreferences']['/Duplex'], '/DuplexFlipLongEdge' if duplex else '/Simplex')
        return layout,reader

    def test_odd_and_even_summary_pages_then_five_receipts(self):
        for summary_pages in (1,2,3,4):
            with self.subTest(summary_pages=summary_pages):
                sources=[self.source('bảng kê tổng',summary_pages,'SUMMARY',True)]
                sources += [self.source('biên nhận' if i==1 else f'biên nhận {i:02d}',1,f'PERSON_{i}') for i in range(1,6)]
                layout,reader=self.check(sources,True)
                self.assertEqual(len(reader.pages),summary_pages+(summary_pages%2)+10)
                for i in range(summary_pages):self.assertIn('SUMMARY',reader.pages[i].extract_text())
                full=''.join(p.extract_text() for p in reader.pages)
                for i in range(1,6):self.assertEqual(full.count(f'PERSON_{i}'),1)

    def test_only_selected_receipts_still_get_individual_sheets(self):
        layout,reader=self.check([self.source('biên nhận 02',1,'PERSON_2'),self.source('biên nhận 05',1,'PERSON_5')],True)
        self.assertEqual(layout['blank_pages'],[2,4])
        self.assertEqual(len(reader.pages),4)

    def test_single_sided_print_has_no_extra_blank_sheets(self):
        layout,reader=self.check([self.source('bảng kê tổng',3,'SUMMARY',True),self.source('biên nhận',1,'PERSON_1'),self.source('biên nhận 02',1,'PERSON_2')],False)
        self.assertEqual(len(reader.pages),5)
        self.assertEqual(layout['blank_pages'],[])

    def test_summary_alone_and_other_documents_are_not_padded(self):
        layout,reader=self.check([self.source('bảng kê tổng',3,'SUMMARY',True),self.source('Báo cáo',1,'REPORT')],True)
        self.assertEqual(len(reader.pages),4)
        self.assertEqual(layout['blank_pages'],[])

    def test_receipt_back_cannot_be_used_by_next_workbook(self):
        layout,reader=self.check([self.source('biên nhận',1,'PERSON_1'),self.source('bảng kê tổng',1,'SUMMARY',True),self.source('biên nhận 02',1,'PERSON_2')],True)
        self.assertEqual([r['start_page'] for r in layout['sections']],[1,3,5])
        self.assertEqual(layout['blank_pages'],[2,4,6])

    def test_receipt_spanning_multiple_pages_is_blocked_in_both_modes(self):
        for duplex in (False,True):
            with self.subTest(duplex=duplex), self.assertRaises(ReceiptPrintError):
                self.check([self.source('biên nhận 02',2,'TOO_LONG')],duplex)
