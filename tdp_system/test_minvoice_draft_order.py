import copy
import unittest
from unittest.mock import Mock

from .minvoice_client import MinvoiceError, MinvoiceOutcomeUnknown
from .minvoice_portal_drafts import ordered_draft_lines
from .test_minvoice_portal import client, document


class PortalDraftOrderTests(unittest.TestCase):
    def setUp(self):
        self.client = client()
        self.client._ensure_login = Mock()
        self.payload = document()
        self.payload.update(orderNumber='TDP-AAAAAAAAAAAA-' + 'B' * 32,
                            keyApi='TDP-AAAAAAAAAAAA-' + 'B' * 32,
                            invoiceNumber=None, invoiceStatus=0, sendTaxStatus=0,
                            buyerDisplayName='Buyer', buyerAddress='Address',
                            invoiceDate='2026-09-16')
        line = self.payload['invoiceDetail'][0]
        # Same product twice must stay two distinct lines with their own qty.
        self.payload['invoiceDetail'] = [dict(line, ordinalNumber='1'),
                                        dict(line, ordinalNumber='2', quantity=3)]
        self.remote = copy.deepcopy(self.payload)
        self.remote.update(keyApi=None, sendTaxStatus=1)
        self.remote['invoiceDetail'].reverse()

    def test_save_accepts_same_lines_returned_in_different_array_order(self):
        self.client.portal_draft_payload = Mock(return_value=self.payload)
        self.client.get_invoice_info = Mock(return_value={'found': False})
        self.client._portal_json = Mock(side_effect=[{'id': self.remote['id']}, self.remote])
        result = self.client.create_draft({}, dry_run=False, confirm_remote_write=True)
        self.assertTrue(result['ok'])
        self.assertEqual(['POST', 'GET'], [c.args[0] for c in self.client._portal_json.call_args_list])

    def test_reconciliation_orders_only_by_complete_unique_ordinal(self):
        self.client._portal_json = Mock(side_effect=[
            {'items': [self.remote], 'totalCount': 1}, self.remote])
        result = self.client.get_invoice_info(key_api=self.payload['keyApi'])
        self.assertEqual([2, 3], [r['quantity'] for r in result['data']['details']])
        self.assertEqual(['GET', 'GET'], [c.args[0] for c in self.client._portal_json.call_args_list])

    def test_real_line_change_still_blocks_saved_confirmation(self):
        self.remote['invoiceDetail'][0]['quantity'] = 4
        self.client.portal_draft_payload = Mock(return_value=self.payload)
        self.client.get_invoice_info = Mock(return_value={'found': False})
        self.client._portal_json = Mock(side_effect=[{'id': self.remote['id']}, self.remote])
        with self.assertRaises(MinvoiceOutcomeUnknown):
            self.client.create_draft({}, dry_run=False, confirm_remote_write=True)

    def test_duplicate_missing_and_invalid_ordinals_are_not_guessed(self):
        for positions in [('1', '1'), ('1', None), ('1', '3'), ('0', '1'), ('1', True)]:
            with self.subTest(positions=positions), self.assertRaises(MinvoiceError):
                ordered_draft_lines([{'ordinalNumber': p} for p in positions])
        legacy = [{'productCode': 'Z'}, {'productCode': 'A'}]
        self.assertEqual(legacy, ordered_draft_lines(legacy))


if __name__ == '__main__':
    unittest.main()
