import io
import json
import unittest
from openpyxl import load_workbook
from . import server, contract_modules as cm
from . import test_supplier_plan_source as fixtures
from .payable_ledger import sync_payable_ledger, pending_purchase_sheets
from .payable_export import payable_export_data


class PayablePurchaseSheetTests(fixtures.SupplierPlanSourceTests):
    def approve_for_payable(self, bid):
        with server.db() as conn:
            conn.execute("UPDATE batches SET status='approved' WHERE id=?", (bid,))
            sync_payable_ledger(conn, timestamp=server.now_iso())

    def active(self):
        with server.db() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM payable_ledger_lines WHERE status!='reversed'")]

    def test_approved_day_uses_purchase_quantity_price_and_adjustments_not_sales(self):
        w=load_workbook(io.BytesIO(self.file(7, 9000)));s=w['đặt hàng']
        s.cell(3,9,1);s.cell(3,10,2);s.cell(3,13,8);s.cell(3,14,72000)
        stream=io.BytesIO();w.save(stream);w.close()
        bid=self.daily(stream.getvalue())
        with server.db() as conn:
            protected=[tuple(r)for r in conn.execute('SELECT * FROM orders')]
        self.approve_for_payable(bid)
        row=self.active()[0]
        self.assertEqual((row['source_table'],row['actual_qty'],row['buy_price'],row['amount']), ('supplier_plan_sources',8,9000,72000))
        with server.db() as conn:
            self.assertEqual([tuple(r)for r in conn.execute('SELECT * FROM orders')],protected)
            repeat=sync_payable_ledger(conn,timestamp=server.now_iso())
            self.assertEqual(repeat['inserted']+repeat['updated']+repeat['reversed'],0)
            data=payable_export_data(conn,date_from='2026-09-01',date_to='2026-09-01',supplier='',canonical_party_code=lambda conn,kind,code: code)
            line=next(x for x in data['lines']if x['status']!='reversed')
            self.assertEqual((line['base_qty'],line['damaged_qty'],line['added_qty'],line['amount']),(7,1,2,72000))

    def test_no_sales_fallback_and_unpriced_sheet_shows_pending(self):
        bid=self.daily(self.file())
        self.approve_for_payable(bid)
        self.assertEqual(self.active(),[])
        with server.db() as conn:
            pending=pending_purchase_sheets(conn,'2026-09-01','2026-09-01')
            self.assertIn('Chưa có giá mua',str(pending))
            conn.execute('DELETE FROM supplier_plan_sources')
            sync_payable_ledger(conn,timestamp=server.now_iso())
            self.assertEqual(len(pending_purchase_sheets(conn,'2026-09-01','2026-09-01')),1)
        self.assertEqual(self.active(),[])

    def test_correcting_priced_sheet_updates_only_payable_and_keeps_revisions(self):
        bid=self.daily(self.file(7,9000));self.approve_for_payable(bid)
        before=self.protected();old=self.active()[0]
        self.confirm(self.preview(bid,self.file(8,11000)))
        row=self.active()[0]
        self.assertEqual((row['id'],row['revision'],row['amount']),(old['id'],old['revision']+1,88000))
        after=self.protected()
        for table in before:
            if not table.startswith('payable_'):self.assertEqual(before[table],after[table],table)

    def test_paid_sheet_correction_is_rejected_and_rolled_back(self):
        bid=self.daily(self.file(7,9000));self.approve_for_payable(bid)
        with server.db() as conn:
            conn.execute("UPDATE payable_ledger_lines SET paid_amount=1000,status='partially_paid' WHERE status='open'")
            before=tuple(conn.execute('SELECT * FROM supplier_plan_sources').fetchone())
        self.confirm(self.preview(bid,self.file(8,9000)),status=409)
        with server.db() as conn:
            self.assertEqual(tuple(conn.execute('SELECT * FROM supplier_plan_sources').fetchone()),before)
        self.assertEqual(self.active()[0]['amount'],63000)

    def test_confirmed_purchase_uses_sheet_price_even_with_existing_quote(self):
        bid=self.daily(self.file(7,9000))
        preview=self.preview(bid,self.file(7,9000),plan=False)
        self.assertEqual(preview['total_amount'],63000)
        self.confirm(preview)
        with server.db() as conn:
            conn.execute("UPDATE purchase_workbook_lines SET price_source='Bảng báo giá',buy_price=10000,amount=70000")
        preview=self.preview(bid,self.file(7,11000),plan=False)
        self.assertEqual(preview['total_amount'],77000)
        self.confirm(preview)
        with server.db() as conn:
            self.assertEqual(tuple(conn.execute('SELECT buy_price,amount,price_source FROM purchase_workbook_lines').fetchone()),(11000,77000,'Sheet đặt hàng chuẩn'))

    def test_paid_sheet_cannot_be_replaced_by_another_source_table(self):
        bid=self.daily(self.file(7,9000));self.approve_for_payable(bid)
        with server.db() as conn:
            conn.execute("UPDATE payable_ledger_lines SET paid_amount=1000,status='partially_paid' WHERE status='open'")
        before=self.protected()
        self.confirm(self.preview(bid,self.file(7,9000),plan=False),status=409)
        self.assertEqual(self.protected(),before)
        self.assertEqual(self.active()[0]['source_table'],'supplier_plan_sources')


if __name__=='__main__':unittest.main()
