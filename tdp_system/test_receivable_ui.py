from __future__ import annotations

import unittest
from pathlib import Path


class ReceivableUiStaticContractTests(unittest.TestCase):
    def test_ui_filters_operational_receivables_and_keeps_vat_boundary_visible(self):
        static_dir = Path(__file__).resolve().parent / "static"
        script = (static_dir / "app.js").read_text(encoding="utf-8")
        page = (static_dir / "index.html").read_text(encoding="utf-8")
        css = (static_dir / "real.css").read_text(encoding="utf-8")
        for required in (
            'id="receivableFilterForm"',
            'id="receivableContractor"',
            'id="receivableKitchen"',
            'id="receivableStatus"',
            'id="receivableExportSelected"',
            '"/api/debts/receivables/ledger?"',
            '"/api/debts/receivables/ledger/"',
            '"/api/debts/receivables/export?from="',
            'data-action="toggle-receivable-history"',
            'tdp.receivableFilters',
            'Sổ phải thu vận hành chi tiết',
            'không phải đề nghị thanh toán/hóa đơn đỏ',
            'Excel toàn bộ bếp',
            'ZIP phải thu mọi nhà thầu',
            'state.receivableLedger === null && !state.receivableLoading && !state.receivableError',
        ):
            self.assertIn(required, script)
        for required in (
            ".receivable-filter-grid", ".receivable-ledger-table",
            ".receivable-line-reversed", ".receivable-revision-panel",
        ):
            self.assertIn(required, css)
        self.assertRegex(page, r'/static/app\.js\?v=\d{8}-\d+')
        self.assertRegex(page, r'/static/real\.css\?v=\d{8}-\d+')


if __name__ == "__main__":
    unittest.main()
