from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class QuoteUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        cls.index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "static" / "real.css").read_text(encoding="utf-8")

    def test_separate_period_quote_upload_is_validated_then_saved_as_latest(self):
        self.assertIn('id="quoteWorkbookInput"', self.index)
        self.assertIn('id="quotePeriod" type="month"', self.app_js)
        self.assertIn('data-action="choose-quote-workbook"', self.app_js)
        self.assertIn('"/api/quotes/import/preview"', self.app_js)
        self.assertIn('"/api/quotes/import/confirm"', self.app_js)
        self.assertIn('state_hash: preview.stateHash', self.app_js)
        self.assertIn("preview.canConfirm", self.app_js)
        self.assertIn("preview.conflicts", self.app_js)
        self.assertIn("await confirmQuoteImport(null)", self.app_js)
        self.assertIn("Đã lưu báo giá mới nhất kỳ", self.app_js)

    def test_ui_uses_period_and_header_provenance_and_keeps_zero_visible(self):
        self.assertIn('"&period=" + encodeURIComponent(state.quotePeriod)', self.app_js)
        self.assertIn("excelColumnName(item.sourceColumn)", self.app_js)
        self.assertIn('item.price_state === "zero"', self.app_js)
        self.assertIn("0 · giữ để xác nhận", self.app_js)
        self.assertIn("Dòng X/rỗng đã loại", self.app_js)
        self.assertIn("hệ thống không tự chọn giữa các dòng cùng mã", self.app_js)
        self.assertIn("Phải nạp báo giá đúng kỳ trước khi xuất", self.app_js)
        self.assertIn("Boolean(meta.version)", self.app_js)
        self.assertIn("Boolean(meta.dailySource)", self.app_js)
        self.assertIn("Kính gửi:", self.app_js)
        self.assertIn("Phải chọn đơn hàng có giá theo ngày", self.app_js)
        self.assertIn('api("/api/quotes/versions?period="', self.app_js)
        self.assertIn('href="/api/export/quotes/all', self.app_js)
        self.assertIn("Tải Excel ", self.app_js)
        self.assertIn("Tải báo giá tổng (.zip)", self.app_js)
        self.assertIn("Các lần báo giá đã lưu", self.app_js)
        self.assertIn("Mỗi nhà thầu là một file Excel riêng, không lẫn giá.", self.app_js)
        self.assertIn('"&version_id=" + version.id', self.app_js)
        self.assertIn(".quote-import-preview", self.css)
        self.assertIn('quoteDetailsOpen: true', self.app_js)
        self.assertIn('quoteHistoryOpen: false', self.app_js)
        self.assertRegex(self.index, r'/static/app\.js\?v=\d+-\d+')


if __name__ == "__main__":
    unittest.main()
