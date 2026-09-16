import unittest
from .purchase_rounding import rounded_purchase_amounts


class PurchaseRoundingTests(unittest.TestCase):
    def rows(self, values):
        from decimal import Decimal, ROUND_HALF_UP
        return [dict(actual_qty=1, buy_price=v, amount=int(Decimal(str(v)).quantize(Decimal(1), rounding=ROUND_HALF_UP)), source_row=i+3) for i,v in enumerate(values)]

    def test_round_total_once_and_stable_under_reordering(self):
        rows=self.rows([10.5,20.5,30.666666666667])
        self.assertEqual(rounded_purchase_amounts(rows),[10,21,31])
        self.assertEqual(rounded_purchase_amounts(rows[::-1]),[31,21,10])
        self.assertEqual([r['amount'] for r in rows],[11,21,31])

    def test_negative_returns_half_and_binary_noise(self):
        self.assertEqual(rounded_purchase_amounts(self.rows([-10.5,-20.5])),[-10,-21])
        self.assertEqual(rounded_purchase_amounts(self.rows([10.49999999999999])),[11])
        self.assertEqual(rounded_purchase_amounts(self.rows([10.5])),[11])
        self.assertEqual(rounded_purchase_amounts([]),[])

    def test_preserve_direct_deductions_and_integer_amounts(self):
        rows=self.rows([10.5,20.5]);rows.append(dict(actual_qty=0,buy_price=0,amount=-10,source_row=5))
        self.assertEqual(rounded_purchase_amounts(rows),[10,21,-10])
        self.assertEqual(rounded_purchase_amounts([dict(actual_qty=0,buy_price=0,amount=-1)]),[-1])
