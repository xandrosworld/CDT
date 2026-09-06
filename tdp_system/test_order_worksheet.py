import json
import uuid
from unittest.mock import patch

from .test_order_price_override import OrderPriceOverrideTests
from . import server


class WorksheetTests(OrderPriceOverrideTests):
    def request_for(self, batch, ident, values):
        with server.db() as conn:
            row = next(item for item in server.batch_payload(conn, batch)['orders'] if item['id'] == ident)
        return {'batch_id': batch, 'request_id': str(uuid.uuid4()), 'actor': 'Operator', 'reason': 'Customer revision',
                'items': [{'id': ident, 'revision': row['worksheet_revision'], 'values': values}]}

    def send(self, body):
        return self.client.put('/api/orders/worksheet', json=body)

    def test_cell_save_updates_decimal_and_replay_does_not_duplicate_audit(self):
        batch, ident = self.create_order()
        body = self.request_for(batch, ident, {'qty': .855, 'note': 'Updated'})
        first = self.send(body)
        self.assertEqual(first.status_code, 200, first.json)
        self.assertEqual(first.json['orders'][0]['qty'], .855)
        with server.db() as conn:
            before = conn.execute("SELECT COUNT(*) FROM audit_log WHERE event_type='order.worksheet.edit'").fetchone()[0]
        second = self.send(body)
        self.assertTrue(second.json['idempotent'])
        with server.db() as conn:
            self.assertEqual(before, conn.execute("SELECT COUNT(*) FROM audit_log WHERE event_type='order.worksheet.edit'").fetchone()[0])

    def test_two_clients_stale_edit_preserves_new_value(self):
        batch, ident = self.create_order()
        stale = self.request_for(batch, ident, {'qty': 8})
        self.assertEqual(self.send(self.request_for(batch, ident, {'qty': 5})).status_code, 200)
        self.assertEqual(self.send(stale).status_code, 409)
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT qty FROM orders WHERE id=?', (ident,)).fetchone()[0], 5)

    def test_paste_price_and_quantity_atomic_with_price_history(self):
        batch, ident = self.create_order()
        result = self.send(self.request_for(batch, ident, {'sell_price': 15000, 'actual_delivered': 3}))
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['orders'][0]['revenue'], 45000)
        with server.db() as conn:
            history = conn.execute('SELECT * FROM order_sell_price_overrides WHERE order_id=?', (ident,)).fetchone()
            self.assertEqual(history['new_price'], 15000)
            self.assertEqual(history['actor'], 'Operator')

    def test_bad_second_row_rolls_back_first_and_no_receipt(self):
        batch, ident = self.create_order()
        second = self.add_order(batch)
        body = self.request_for(batch, ident, {'qty': 4})
        body['items'] += self.request_for(batch, second, {'qty': -1})['items']
        self.assertEqual(self.send(body).status_code, 400)
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT qty FROM orders WHERE id=?', (ident,)).fetchone()[0], 2)
            self.assertIsNone(conn.execute('SELECT * FROM worksheet_receipts WHERE request_id=?', (body['request_id'],)).fetchone())

    def test_audit_failure_rolls_back_everything(self):
        batch, ident = self.create_order()
        body = self.request_for(batch, ident, {'qty': 4, 'sell_price': 16000})
        with patch.object(server, 'audit_event', side_effect=RuntimeError('audit failed')):
            self.assertEqual(self.send(body).status_code, 500)
        with server.db() as conn:
            row = conn.execute('SELECT qty,sell_price FROM orders WHERE id=?', (ident,)).fetchone()
            self.assertEqual(tuple(row), (2, 12000))
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM order_sell_price_overrides').fetchone()[0], 0)

    def test_price_actor_required_and_derived_columns_rejected(self):
        batch, ident = self.create_order()
        body = self.request_for(batch, ident, {'sell_price': 14000})
        body['actor'] = ''
        self.assertEqual(self.send(body).status_code, 400)
        self.assertEqual(self.send(self.request_for(batch, ident, {'revenue': 2})).status_code, 400)

    def test_retry_key_cannot_save_different_payload(self):
        batch, ident = self.create_order()
        body = self.request_for(batch, ident, {'qty': 3})
        self.assertEqual(self.send(body).status_code, 200)
        body['items'][0]['values']['qty'] = 7
        self.assertEqual(self.send(body).status_code, 409)
