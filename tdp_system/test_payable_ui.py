from __future__ import annotations

import unittest
from pathlib import Path


class PayableUiStaticContractTests(unittest.TestCase):
    def test_ui_uses_explicit_allocation_reversal_and_persisted_filters(self):
        static_dir = Path(__file__).resolve().parent / "static"
        script = (static_dir / "app.js").read_text(encoding="utf-8")
        page = (static_dir / "index.html").read_text(encoding="utf-8")
        css = (static_dir / "real.css").read_text(encoding="utf-8")
        for required in (
            'id="payablePaymentForm"',
            'class="payable-line-select"',
            'class="payable-allocation-input"',
            '"/api/debts/payables/payments"',
            '"/reverse"',
            'expected_revision',
            'tdp.payableFilters',
            'esc(state.debtTo || todayIso)',
            'id="receiptForm"',
            'Excel phải trả nhà cung cấp',
            'state.payableLedger === null && !state.payableLoading && !state.payableError',
            'statCard("Tổng số lượng", esc(quantityGroups(summary.filtered_quantities_by_unit))',
            'TỔNG THEO BỘ LỌC',
        ):
            self.assertIn(required, script)
        self.assertNotIn('<option value="payment">Trả nhà cung cấp</option>', script)
        self.assertIn("payable-line-select:disabled", css)
        self.assertIn("payable-payment-form", css)
        self.assertIn("/static/app.js?v=20260907-9", page)
        self.assertIn("/static/real.css?v=20260907-9", page)


if __name__ == "__main__":
    unittest.main()
