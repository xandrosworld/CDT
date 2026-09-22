import unittest
from .minvoice_precision import matches


class PrecisionTests(unittest.TestCase):
    def setUp(self):
        self.raw={'currencyId':'vnd','creationTime':'2026-09-21T22:00:00',
                  '_tdp_currency_precision':{'currency_id':'vnd','quantity':2,'price':2,'effective_at':'2026-07-31T18:00:00'}}

    def test_sender_six_decimals_then_provider_currency_rounding(self):
        self.assertTrue(matches(2.1,2.095999999999998,self.raw,'quantity'))
        self.assertTrue(matches(.06,.05499999999999949,self.raw,'quantity'))
        self.assertFalse(matches(2.11,2.096,self.raw,'quantity'))
        self.assertFalse(matches(float('nan'),2,self.raw,'quantity'))

    def test_no_precision_or_changed_currency_configuration_does_not_prove_rounding(self):
        self.assertFalse(matches(2.1,2.096,{},'quantity'))
        self.raw['_tdp_currency_precision']['effective_at']='2026-09-22T00:00:00'
        self.assertFalse(matches(2.1,2.096,self.raw,'quantity'))
        self.raw['_tdp_currency_precision']['effective_at']='2026-01-01T00:00:00'
        self.raw['currencyId']='other'
        self.assertFalse(matches(2.1,2.096,self.raw,'quantity'))
