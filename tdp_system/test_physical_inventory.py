import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import server
from .physical_inventory import physical_stock_payload
from . import test_order_import_idempotence as import_fixtures


def seed_round2(conn):
    conn.execute("INSERT OR REPLACE INTO contractors(code,name,price_group) VALUES('C1','Nhà thầu thử','C1')")
    conn.execute("INSERT OR REPLACE INTO kitchens(code,name,contractor) VALUES('K1','Bếp thử','C1')")
    conn.execute("INSERT OR REPLACE INTO suppliers(code,name) VALUES('S1','Nhà cung cấp thử')")
    for code, name, unit in [('P1','Cà rốt','kg'), ('P2','Trứng','cái')]:
        conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax,supplier,buy_price) VALUES(?,?,?,'0','S1',1000)", (code,name,unit))
    return conn.execute("INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-09-05','Round 2 thử nghiệm','draft',?)", (server.now_iso(),)).lastrowid


class PhysicalStockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = server.DB_PATH, server.DATA_DIR, server.MASTER_SOURCE
        server.DATA_DIR = Path(self.temp.name)
        server.DB_PATH = Path(self.temp.name) / 'test.sqlite3'
        server.MASTER_SOURCE = Path(self.temp.name) / 'disabled.xlsx'
        server.init_database()
        self.client = server.app.test_client()
        with server.db() as conn:
            self.batch = seed_round2(conn)

    def tearDown(self):
        server.DB_PATH, server.DATA_DIR, server.MASTER_SOURCE = self.original
        self.temp.cleanup()

    def opening(self, code='P1', qty=10, **kwargs):
        result = self.client.post('/api/physical-stock/opening', json={
            'product_code':code, 'work_date':'2026-09-05','qty':qty,'unit_cost':1000,
            'actor':'Người thử','reason':'Kiểm đếm đầu ngày','revision':0, **kwargs})
        self.assertEqual(result.status_code, 200, result.json)

    def order(self, **kwargs):
        result = self.client.post('/api/orders', json={
            'batch_id':self.batch,'kitchen':'K1','contractor':'C1','product_code':'P1',
            'qty':4,'actual_received':0,'actual_delivered':0,'sell_price':1200, **kwargs})
        self.assertEqual(result.status_code, 200, result.json)
        return result.json['orders'][-1]

    def stock(self, code='P1'):
        payload = self.client.get('/api/physical-stock').json
        return next(i for i in payload['items'] if i['product_code'] == code)

    def update(self, row, **kwargs):
        result = self.client.put('/api/orders/' + str(row['id']), json=kwargs)
        self.assertEqual(result.status_code, 200, result.json)
        return next(i for i in result.json['orders'] if i['id'] == row['id'])

    def settle(self, row, stage='delivered'):
        result = self.client.put('/api/physical-stock/orders/' + str(row['id']), json={'stage':stage,'revision':row['physical_revision']})
        self.assertEqual(result.status_code, 200, result.json)
        return next(i for i in result.json['orders'] if i['id'] == row['id'])

    def test_uninitialized_is_unknown_not_false_zero(self):
        self.order()
        item = self.stock()
        self.assertIsNone(item['balance_qty'])
        self.assertEqual(item['status'],'uninitialized')
        self.assertEqual(item['committed_qty'],4)

    def test_place_edit_repeat_deliver_edit_return_and_delete(self):
        self.opening()
        row = self.order()
        self.assertEqual(self.stock()['balance_qty'],6)
        row = self.update(row, qty=5)
        self.assertEqual(self.stock()['balance_qty'],5)
        self.update(row, qty=5)
        self.assertEqual(self.stock()['balance_qty'],5)
        row = self.update(row, actual_delivered=3)
        self.assertEqual(self.stock()['balance_qty'],5, 'Unconfirmed delivery must not remove pending order claim')
        row = self.settle(row)
        self.assertEqual(self.stock()['balance_qty'],7)
        row = self.settle(row)
        self.assertEqual(self.stock()['balance_qty'],7)
        row = self.update(row, actual_delivered=2, customer_return_qty=.5)
        self.assertEqual(self.stock()['balance_qty'],8.5)
        self.assertEqual(self.client.delete('/api/orders/' + str(row['id'])).status_code,200)
        self.assertEqual(self.stock()['balance_qty'],10)
        with server.db() as conn:
            self.assertGreater(conn.execute('SELECT COUNT(*) FROM physical_order_history').fetchone()[0],3)

    def test_stale_settlement_cannot_override_changed_order(self):
        row = self.order()
        self.update(row, actual_delivered=1)
        result = self.client.put('/api/physical-stock/orders/' + str(row['id']), json={'stage':'delivered','revision':row['physical_revision']})
        self.assertEqual(result.status_code,409)

    def test_independent_codes_units_and_tiny_quantities(self):
        self.opening()
        self.opening('P2',qty=20)
        self.order(qty=.000001)
        self.order(product_code='P2',qty=2)
        self.assertAlmostEqual(self.stock()['balance_qty'],9.999999)
        self.assertEqual(self.stock('P2')['balance_qty'],18)
        totals = self.client.get('/api/physical-stock').json['totals']['qty_by_unit']
        self.assertEqual(set(totals),{'kg','cái'})

    def test_future_delivery_is_reserved_immediately_old_orders_excluded(self):
        self.opening()
        for day in ('2026-09-04','2026-09-09'):
            batch = self.client.post('/api/batches',json={'work_date':day}).json['batch']['id']
            self.order(batch_id=batch,qty=3)
        self.assertEqual(self.stock()['balance_qty'],7)

    def test_movement_retry_conflict_opening_revision_and_history(self):
        self.opening()
        body = {'product_code':'P1','work_date':'2026-09-05','qty':2.5,'unit_cost':1000,
                'actor':'A','reason':'Hàng đã về','request_key':'receipt-1'}
        for _ in range(2):
            self.assertEqual(self.client.post('/api/physical-stock/movement',json=body).status_code,200)
        self.assertEqual(self.stock()['balance_qty'],12.5)
        self.assertEqual(self.client.post('/api/physical-stock/movement',json={**body,'qty':3}).status_code,409)
        revision = self.stock()['opening']['id']
        self.opening(qty=11, revision=revision)
        self.assertEqual(self.stock()['balance_qty'],13.5)
        self.assertEqual(self.client.post('/api/physical-stock/movement',json={**body,'qty':-2.5,'request_key':'correction-1','reason':'Hoàn tác nhập nhầm'}).status_code,200)
        self.assertEqual(self.stock()['balance_qty'],11)
        self.assertEqual(len(self.client.get('/api/physical-stock').json['movements']),2)

    def test_no_invoice_or_supplier_purchase_side_effect(self):
        self.opening()
        self.order()
        with server.db() as conn:
            before = [tuple(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger')]
            conn.execute("INSERT INTO inventory_transactions(txn_date,product_code,qty_in,source_type,source_id,created_at,updated_at) VALUES('2026-09-05','P1',999,'OPENING','other','now','now')")
        self.assertEqual(self.stock()['balance_qty'],6)
        needs = self.client.get('/api/supplier-needs/' + str(self.batch)).json
        response = self.client.put(f'/api/supplier-order-status/{self.batch}/s1',json={'status':'ordered','revision':0,'plan_hash':needs['plan_hash']})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.stock()['balance_qty'],6)
        with server.db() as conn:
            self.assertEqual(before,[tuple(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger')])

    def test_supplier_changes_reopen_and_stale_plan_rejected(self):
        row = self.order()
        original = self.client.get('/api/supplier-needs/' + str(self.batch)).json
        self.update(row,qty=5)
        response = self.client.put(f'/api/supplier-order-status/{self.batch}/s1',json={'status':'ordered','revision':0,'plan_hash':original['plan_hash']})
        self.assertEqual(response.status_code,409)
        self.client.put(f'/api/supplier-order-status/{self.batch}/s1',json={'status':'ordered','revision':0})
        self.update(row,qty=6)
        supplier = self.client.get('/api/supplier-needs/' + str(self.batch)).json['checklist'][0]
        self.assertEqual((supplier['status'],supplier['revision']),('reopened',2))

    def test_bad_units_unmapped_rows_and_negative_inputs_visible(self):
        self.opening()
        self.order(unit='thùng')
        self.order(product_code='UNKNOWN', product_name='Hàng chưa ghép')
        self.assertEqual(len(self.client.get('/api/physical-stock').json['issues']),2)
        self.assertEqual(self.stock()['status'], 'review')
        self.assertIsNone(self.stock()['balance_qty'])
        result = self.client.post('/api/physical-stock/movement',json={
            'product_code':'P1','work_date':'2026-09-05','qty':'NaN','unit_cost':1,
            'actor':'A','reason':'Test','request_key':'bad'})
        self.assertEqual(result.status_code,400)

    def test_two_receipt_retries_and_two_opening_editors_are_serialized(self):
        self.opening()
        body = {'product_code':'P1','work_date':'2026-09-05','qty':2,'unit_cost':1000,
                'actor':'A','reason':'Nhập có thật','request_key':'same-receipt'}
        def receipt(_):
            with server.app.test_client() as client:
                return client.post('/api/physical-stock/movement',json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(receipt,range(2))),[200,200])
        self.assertEqual(self.stock()['balance_qty'],12)
        revision = self.stock()['opening']['id']
        def edit(qty):
            with server.app.test_client() as client:
                return client.post('/api/physical-stock/opening',json={**body,'qty':qty,'revision':revision}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(edit,[11,12])),[200,409])

    def test_reinit_preserves_customer_stock_and_does_not_replay_claims(self):
        self.opening()
        self.order()
        before = self.stock()
        server.init_database()
        self.assertEqual(self.stock(),before)

    def test_filter_amount_rounding_and_no_writes_on_read(self):
        self.opening(qty=1, unit_cost=26465.5)
        self.order(qty=2)
        self.assertEqual(self.stock()['estimated_amount'],-26466)
        with server.db() as conn:
            before = conn.total_changes
            data = physical_stock_payload(conn,search='Cà rốt',status='short')
            self.assertEqual(data['totals']['rows'],1)
            self.assertEqual(conn.total_changes,before)

    def test_bulk_edit_failure_rolls_back_physical_claims(self):
        self.opening()
        row = self.order(qty=2)
        result = self.client.put('/api/orders/bulk-update',json={'batch_id':self.batch,'items':[{'id':row['id'],'qty':7},{'id':999999,'qty':3}]})
        self.assertEqual(result.status_code,409)
        self.assertEqual(self.stock()['balance_qty'],8)
        result = self.client.put('/api/orders/bulk-update',json={'batch_id':self.batch,'items':[{'id':row['id'],'qty':7}]})
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(self.stock()['balance_qty'],3)

    def test_reimport_replaces_not_duplicate_and_bad_file_keeps_previous(self):
        self.opening(work_date='2026-08-29')
        def upload(payload):
            analysis = self.client.post('/api/import/analyze',data={'file':(io.BytesIO(payload),'orders.xlsx')},content_type='multipart/form-data')
            if 'token' not in analysis.json:
                return analysis
            token = analysis.json['token']
            return self.client.post('/api/import/confirm',json={'token':token,'sheets':['29.08'],'work_date':'2026-08-29'})
        payload = import_fixtures.OrderImportIdempotenceTests.workbook_bytes(qty=2)
        first = upload(payload)
        self.assertEqual(first.status_code,200,first.json)
        self.assertEqual(self.stock()['balance_qty'],8)
        self.assertTrue(upload(payload).json['idempotent'])
        changed = upload(import_fixtures.OrderImportIdempotenceTests.workbook_bytes(qty=3))
        self.assertEqual(changed.status_code,200,changed.json)
        self.assertEqual(changed.json['batch']['id'],first.json['batch']['id'])
        self.assertEqual(self.stock()['balance_qty'],7)
        self.assertEqual(upload(payload).status_code,409, 'Superseded file cannot silently restore old orders')
        bad = upload(import_fixtures.OrderImportIdempotenceTests.workbook_bytes(qty=-3))
        self.assertEqual(bad.status_code,400,bad.json)
        self.assertEqual(self.stock()['balance_qty'],7)


if __name__ == '__main__':
    unittest.main()
