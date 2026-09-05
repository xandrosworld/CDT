from __future__ import annotations

import unittest
from pathlib import Path


class PayrollUiContractTests(unittest.TestCase):
    def test_retired_modules_leave_navigation_but_keep_legacy_implementation(self):
        root = Path(__file__).resolve().parent.parent
        page = (root / "tdp_system" / "static" / "index.html").read_text(encoding="utf-8")
        script = (root / "tdp_system" / "static" / "app.js").read_text(encoding="utf-8")
        styles = (root / "tdp_system" / "static" / "real.css").read_text(encoding="utf-8")
        server = (root / "tdp_system" / "contract_modules.py").read_text(encoding="utf-8")
        # README-new-2 section 2.1 retires these menus while preserving history.
        nav = page.split('<nav id="nav">')[1].split('</nav>')[0]
        self.assertNotIn('data-view="kitchen"', nav)
        self.assertNotIn('data-view="payroll"', nav)
        self.assertNotIn("Suất ăn & đặt hàng bếp", nav)
        self.assertNotIn("Chấm công & lương", nav)
        self.assertIn('data-view="physical"', nav)
        self.assertIn('/static/app.js?v=', page)
        for marker in (
            "function renderPayroll()", 'id="staffForm"', 'id="attendanceForm"',
            'id="payrollAdjustmentForm"', "Nạp file chấm công",
            "/api/attendance/import/preview", "/api/attendance/import/confirm",
            "/api/export/payroll?month=", "staff-form-actions",
        ):
            self.assertIn(marker, script)
        for marker in (".staff-form-actions .btn", "min-width:150px", "white-space:nowrap"):
            self.assertIn(marker, styles)
        for marker in (
            '@app.post("/api/staff")', '@app.post("/api/attendance")',
            '@app.post("/api/attendance/import/preview")',
            '@app.post("/api/attendance/import/confirm")',
            '@app.put("/api/payroll-adjustments/<employee_code>/<month>")',
            '@app.get("/api/payroll")', '@app.get("/api/export/payroll")',
        ):
            self.assertIn(marker, server)


if __name__ == "__main__":
    unittest.main()
