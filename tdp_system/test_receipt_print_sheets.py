import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen.canvas import Canvas
from .excel_print_renderer import _merge_pdfs, ReceiptPrintError, build_excel_pdf_bundle


class ReceiptPrintSheetTests(unittest.TestCase):
    def test_auto_receipt_print_uses_duplex_only_when_a_receipt_needs_two_pages(self):
        source = self.root / 'receipts.xlsx'
        book = Workbook();book.active.title = 'biên nhận'
        book.create_sheet('biên nhận 02');book.save(source);book.close()
        before = source.read_bytes()
        for count in (1, 2):
            rendered = [self.source('biên nhận', count, 'FIRST'), self.source('biên nhận 02', 1, 'SECOND')]
            for item in rendered:item.update(document_type='selected', title=item['sheet'], workbook=source.name)
            with patch('tdp_system.excel_print_renderer._export_visible_sheets', return_value=rendered):
                report = build_excel_pdf_bundle([{'path':source, 'document_type':'selected'}],
                                                self.root / 'auto.pdf', paper='A5', duplex='auto')
            self.assertEqual(report['duplex'], count == 2)
            self.assertEqual(report['pages'], 2 if count == 1 else 4)
            self.assertEqual(report['page_layout']['blank_pages'], [] if count == 1 else [4])
            self.assertEqual(source.read_bytes(), before)
            for page in PdfReader(self.root / 'auto.pdf').pages:
                self.assertAlmostEqual(float(page.mediabox.width), 148 * 72 / 25.4, places=2)
                self.assertAlmostEqual(float(page.mediabox.height), 210 * 72 / 25.4, places=2)

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

    def check(self, sources, duplex, edge='/DuplexFlipShortEdge'):
        originals = {s['path']:s['path'].read_bytes() for s in sources}
        target = self.root / 'result.pdf'
        layout = _merge_pdfs(sources, target, paper='A4', duplex=duplex)
        reader = PdfReader(target)
        self.assertEqual(len(reader.pages),layout['total_pages'])
        for number in layout['blank_pages']:
            self.assertFalse((reader.pages[number-1].extract_text() or '').strip())
        for item in layout['sections']:
            if item['receipt']:
                self.assertLessEqual(item['end_page'] - item['start_page'], 1 if duplex else 0)
                if duplex:
                    self.assertEqual(item['start_page'] % 2,1)
                    self.assertEqual((item['start_page']-1)//2, (item['end_page']-1)//2)
                    if item['end_page'] % 2:
                        self.assertIn(item['end_page']+1,layout['blank_pages'])
        for p, data in originals.items():self.assertEqual(p.read_bytes(),data)
        self.assertEqual(reader.trailer['/Root']['/ViewerPreferences']['/Duplex'], edge if duplex else '/Simplex')
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
        layout,reader=self.check([self.source('biên nhận 02',1,'PERSON_2'),self.source('biên nhận 05',1,'PERSON_5')],True,'/DuplexFlipLongEdge')
        self.assertEqual(layout['blank_pages'],[2,4])
        self.assertEqual(len(reader.pages),4)

    def test_single_sided_print_has_no_extra_blank_sheets(self):
        layout,reader=self.check([self.source('bảng kê tổng',3,'SUMMARY',True),self.source('biên nhận',1,'PERSON_1'),self.source('biên nhận 02',1,'PERSON_2')],False)
        self.assertEqual(len(reader.pages),5)
        self.assertEqual(layout['blank_pages'],[])

    def test_portrait_duplex_uses_long_edge_without_rotating_back(self):
        _,reader=self.check([self.source('Báo cáo',2,'PORTRAIT')],True,'/DuplexFlipLongEdge')
        self.assertTrue(all(p.rotation==0 for p in reader.pages))
        self.assertIn('page 2',reader.pages[1].extract_text())

    def test_landscape_duplex_uses_short_edge_without_rotating_back(self):
        _,reader=self.check([self.source('bảng kê tổng',2,'LANDSCAPE',True)],True)
        self.assertTrue(all(p.rotation==0 for p in reader.pages))
        self.assertIn('page 2',reader.pages[1].extract_text())

    def test_summary_alone_and_other_documents_are_not_padded(self):
        layout,reader=self.check([self.source('bảng kê tổng',3,'SUMMARY',True),self.source('Báo cáo',1,'REPORT')],True)
        self.assertEqual(len(reader.pages),4)
        self.assertEqual(layout['blank_pages'],[])

    def test_receipt_back_cannot_be_used_by_next_workbook(self):
        layout,reader=self.check([self.source('biên nhận',1,'PERSON_1'),self.source('bảng kê tổng',1,'SUMMARY',True),self.source('biên nhận 02',1,'PERSON_2')],True)
        self.assertEqual([r['start_page'] for r in layout['sections']],[1,3,5])
        self.assertEqual(layout['blank_pages'],[2,4,6])

    def test_two_page_receipt_uses_both_sides_of_one_sheet(self):
        sources = [self.source('biên nhận',2,'PERSON_1'), self.source('biên nhận 02',1,'PERSON_2'),
                   self.source('biên nhận 03',2,'PERSON_3')]
        layout, reader = self.check(sources, True, '/DuplexFlipLongEdge')
        self.assertEqual([(r['start_page'],r['end_page']) for r in layout['sections']],[(1,2),(3,3),(5,6)])
        self.assertEqual(layout['blank_pages'],[4])
        self.assertEqual(len(reader.pages),6)
        for number, label in ((1,'PERSON_1'),(2,'PERSON_1'),(3,'PERSON_2'),(5,'PERSON_3'),(6,'PERSON_3')):
            self.assertIn(label, reader.pages[number-1].extract_text())

    def test_two_page_receipt_after_odd_summary_and_before_next_workbook(self):
        sources = [self.source('bảng kê tổng',3,'SUMMARY',True),self.source('biên nhận',2,'PERSON_1'),
                   self.source('bảng kê tổng',1,'NEXT_SUMMARY',True),self.source('biên nhận 02',1,'PERSON_2')]
        layout, reader = self.check(sources, True)
        self.assertEqual([(r['start_page'],r['end_page']) for r in layout['sections']],[(1,3),(5,6),(7,7),(9,9)])
        self.assertEqual(layout['blank_pages'],[4,8,10])
        self.assertEqual([p.rotation for p in reader.pages], [0,0,0,0,0,180,0,0,0,0])

    def test_receipt_before_landscape_summary_uses_same_binding(self):
        layout, reader = self.check([self.source('biên nhận',2,'PERSON_1'),
                                    self.source('bảng kê tổng',2,'SUMMARY',True)], True)
        self.assertEqual(layout['blank_pages'], [])
        self.assertEqual([p.rotation for p in reader.pages], [0,180,0,0])

    def test_two_page_receipt_simplex_requires_duplex(self):
        with self.assertRaisesRegex(ReceiptPrintError, 'Hai mặt'):
            self.check([self.source('biên nhận 02',2,'TWO_PAGES')],False)

    def test_receipt_longer_than_one_physical_sheet_is_blocked(self):
        for duplex in (False,True):
            with self.subTest(duplex=duplex), self.assertRaises(ReceiptPrintError):
                self.check([self.source('biên nhận 02',3,'TOO_LONG')],duplex)
