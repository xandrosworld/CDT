from __future__ import annotations

import unittest
from pathlib import Path


class UnifiedUiLanguageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        static_dir = Path(__file__).resolve().parent / "static"
        cls.script = (static_dir / "app.js").read_text(encoding="utf-8")
        cls.invoice_script = (static_dir / "invoice-workbench.js").read_text(encoding="utf-8")
        cls.page = (static_dir / "index.html").read_text(encoding="utf-8")
        cls.css = (static_dir / "real.css").read_text(encoding="utf-8")

    def test_navigation_and_business_boundaries_use_the_agreed_names(self):
        for marker in (
            "Báo cáo vật tư hàng hóa",
            "Kho thực tế",
            'data-view="reports"><span>↗</span> Báo cáo tổng hợp',
            'data-view="debts"><span>▤</span> Công nợ',
            "Bảng kê & hóa đơn",
            "Sao chép thành công toàn bộ ảnh của NCC mới ghi nhận đã đặt",
            ">Mở lại</button>",
            "Sổ phải thu vận hành chi tiết",
            "không phải đề nghị thanh toán/hóa đơn đỏ",
            "Bảng kê từ hóa đơn đỏ",
            "Được xuất và chưa được xuất theo nhà thầu",
        ):
            self.assertTrue(marker in self.page + self.script, marker)
        # The invoice-stock menu keeps its agreed name. Explanatory text may
        # distinguish it from the newly separate physical-stock module.
        self.assertNotIn('data-view="inventory"><span>▦</span> Kho hóa đơn', self.page)
        self.assertNotIn("Đánh dấu đã đặt", self.page + self.script)
        # Customer retired these modules on 05/09; keep the historical API, not menu entries.
        nav = self.page.split('<nav id="nav">')[1].split('</nav>')[0]
        for retired in ('kitchen', 'payroll', 'deliveries'):
            self.assertNotIn('data-view="' + retired + '"', nav)

    def test_debt_navigation_is_separate_and_summary_first(self):
        combined = self.page + self.script
        self.assertNotIn("Báo cáo & công nợ", combined)
        for marker in (
            'debtSection: ""',
            'debts: "Công nợ"',
            'data-action="open-debt-section"',
            'Công nợ phải thu (bếp)',
            'Công nợ phải thu (tổng)',
            'Công nợ phải trả',
            'data-action="back-debt-overview"',
            'if (section === "receivable-kitchen")',
            'if (section === "receivable-total")',
            'Chi tiết chỉ hiện trong mục đang chọn',
        ):
            self.assertIn(marker, combined)

    def test_invoice_and_meal_statuses_are_translated_before_rendering(self):
        for marker in (
            "function invoiceReceiptStatusText(value)",
            "Sẵn sàng tạo phiếu nhập",
            "Đã ghi nhập kho",
            "function invoiceStockStatusText(value)",
            "Sẵn sàng xác nhận xuất kho",
            "Cần hoàn tác xuất kho",
            "function invoiceSyncStatusText(value)",
            "Có lỗi · cần thử lại",
            "function mealPlanStatusText(value)",
            "Bản nháp",
            "invoice-issue-text",
            "hãy kiểm tra và tải tiếp",
        ):
            self.assertTrue(marker in self.script + self.invoice_script, marker)
        for raw_render in (
            "esc(invoice.receipt_status)",
            "esc(invoice.stock_status)",
            "esc(sync.last_status)",
            "esc(plan.status)",
            "Xác nhận reversal",
            "Đã tạo reversal",
            "đã post",
        ):
            self.assertNotIn(raw_render, self.script)

    def test_keyboard_flow_and_official_payment_documents_remain_explicit(self):
        for marker in (
            'event.target.closest(".invoice-mapping-input")',
            'event.target.closest(".unit-conversion-input, .invoice-draft-factor")',
            'event.target.closest(".quick-sell-price")',
            'event.target.closest(".payable-allocation-input")',
            'event.key === "Enter"',
            "Enter để lưu mã hoặc quy đổi",
            "Thông tin thanh toán mặc định",
            "Được khóa cùng hóa đơn và dùng để lập Đề nghị thanh toán chính thức theo nhà thầu",
            "Hồ sơ đề nghị thanh toán từ hóa đơn đỏ",
            "Tải Đề nghị thanh toán + bảng kê",
        ):
            self.assertTrue(marker in self.script + self.invoice_script, marker)
        self.assertNotIn("Đã lấy từ mẫu TĐP khách cung cấp", self.script)
        self.assertRegex(self.page, r'/static/app\.js\?v=\d+-\d+')

    def test_supplier_cards_keep_only_the_two_customer_requested_actions(self):
        self.assertIn('class="supplier-order-actions"', self.script)
        self.assertIn('data-action="copy-supplier-image"', self.script)
        self.assertIn('body: JSON.stringify({ status: "ordered"', self.script)
        supplier_card_source = self.script.split('function renderPurchases()', 1)[1].split('function supplierPresentation(', 1)[0]
        self.assertNotIn("download-supplier-image", supplier_card_source)
        self.assertNotIn("toggle-supplier-rule", supplier_card_source)
        self.assertNotIn('class="group-list"', supplier_card_source)
        self.assertIn("group.items.forEach(function (item, rowIndex)", self.script)
        self.assertIn('class="supplier-order-list fade-in"', self.script)

    def test_delivery_page_shows_workbook_without_forcing_download(self):
        self.assertIn('deliveries: "Phiếu giao hàng"', self.script)
        self.assertIn('id="deliveryDocumentPreview"', self.script)
        self.assertIn('window.TDPDocuments.open({kind:"deliveries"', self.script)
        self.assertIn("Tải toàn bộ Excel", self.script)
        self.assertNotIn('deliveries: "Phiếu giao theo bếp"', self.script)

    def test_bulk_order_column_headers_have_high_contrast(self):
        self.assertIn("Sửa nhanh toàn bộ đơn hàng", self.script)
        self.assertIn(
            ".bulk-grid thead th { position:sticky; top:0; z-index:2; "
            "background:#17324d; color:#fff; font-weight:800;",
            self.css,
        )
        self.assertRegex(self.page, r'/static/real\.css\?v=\d+-\d+')

    def test_home_has_exactly_the_four_customer_requested_actions(self):
        home = self.script.split("function renderHome()", 1)[1].split(
            "function renderOrders()", 1
        )[0]
        self.assertEqual(4, home.count('class="daily-action-card'))
        for marker in (
            "Tạo phiếu đặt hàng", "In đơn hàng", "Bảng kê và biên nhận", "Duyệt đơn",
            'id="homeFrom"', 'id="homeTo"', "phiếu theo bếp",
        ):
            self.assertIn(marker, home)
        self.assertNotIn("stats-grid", home)

    def test_quick_add_inherits_the_order_and_asks_only_three_business_fields(self):
        quick_add = self.script.split("function openQuickAddModal(id)", 1)[1].split(
            "function openPasteModal()", 1
        )[0]
        for field_call in (
            'field("Tên hàng", "product_name"',
            'field("Số lượng", "qty"',
            'field("Đơn vị tính", "unit"',
        ):
            self.assertIn(field_call, quick_add)
        for inherited_field in ("contractor", "kitchen", "work_date", "supplier", "buy_price", "sell_price"):
            self.assertNotIn(f'name="{inherited_field}"', quick_add)
        self.assertIn("Đang thêm vào", quick_add)

    def test_last_daily_workbook_becomes_standard_without_a_second_approval_click(self):
        for marker in (
            'payload.phase === "finalization"',
            "applyPendingOrderImport(confirmableSheets.map",
            'useAsLatest && imported.finalized',
            'api("/api/batches/" + imported.batch.id + "/approve"',
            "Đã dùng file cuối cùng làm bản chuẩn và tự chốt đơn",
        ):
            self.assertIn(marker, self.script)

    def test_printing_selects_all_or_individual_delivery_notes_by_kitchen(self):
        printing = self.script.split("function renderPrinting()", 1)[1].split(
            "function renderSettings()", 1
        )[0]
        for marker in (
            "Chọn tất cả hoặc từng bếp", "Chọn bếp cần in phiếu giao",
            "Bếp / ngày giao", "Tải file đã chọn",
        ):
            self.assertIn(marker, printing)
        self.assertIn("batch.delivery_notes", self.script)
        self.assertIn("delivery_selections", self.script)

    def test_large_modules_are_summary_first(self):
        for marker in (
            'quoteDetailsOpen: true', 'quoteHistoryOpen: false',
            'inventoryDetailsOpen: true', 'documentDetailsOpen: false',
            "Báo giá tổng", "Báo giá chi tiết", "tổng hợp theo nhà thầu và từng bếp trong tháng",
            "Tải đủ 4 file ZIP", "File đưa lên M-Invoice", "Bảng kê từ hóa đơn đỏ",
        ):
            self.assertIn(marker, self.script)

    def test_user_facing_language_avoids_demo_and_technical_labels(self):
        combined = self.page + self.script
        for marker in (
            "HỆ THỐNG QUẢN LÝ",
            "Dữ liệu lưu sau khi xác nhận",
            "Đặt hàng nhà cung cấp",
            "Không tìm thấy chức năng này",
            "Tải bản sao lưu dữ liệu",
            "Những việc phần mềm tự làm và không tự làm",
            "Bảo hiểm xã hội người lao động",
        ):
            self.assertIn(marker, combined)
        for technical_label in (
            "BẢN VẬN HÀNH THẬT",
            "TĐK–NXT / kho hóa đơn",
            "Xưởng cơm / PO",
            "Tải bản sao lưu SQLite",
            "Ranh giới tích hợp",
            "API M-Invoice hoạt động",
            "Khác ĐVT / cần quy đổi",
            "Lưu và tính cost",
        ):
            self.assertNotIn(technical_label, combined)

    def test_all_date_and_month_controls_use_unambiguous_vietnamese_display(self):
        for marker in (
            "function localizedTemporalText(value, kind)",
            "function parseLocalizedTemporal(value, kind)",
            "function enhanceLocalizedDateInputs(root)",
            'input[type="date"], input[type="month"]',
            'display.placeholder = kind === "month" ? "mm/yyyy" : "dd/mm/yyyy"',
            'enhanceLocalizedDateInputs(document)',
            "new MutationObserver(function ()",
            "Ngày làm việc (dd/mm/yyyy):",
            "Ngày hoàn tác bảng kê (dd/mm/yyyy):",
            "Nhập ngày hóa đơn dạng dd/mm/yyyy:",
        ):
            self.assertIn(marker, self.script)
        self.assertNotIn("Ngày làm việc (YYYY-MM-DD):", self.script)
        self.assertNotIn("Ngày hoàn tác BK (YYYY-MM-DD):", self.script)
        self.assertNotIn("Nhập ngày hóa đơn dạng YYYY-MM-DD:", self.script)


if __name__ == "__main__":
    unittest.main()
