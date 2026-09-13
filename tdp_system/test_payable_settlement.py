import copy
from concurrent.futures import ThreadPoolExecutor

from . import server
from . import test_payable_payments as fixtures
from .payable_ledger import sync_payable_ledger


class PayableSettlementTests(fixtures.PayablePaymentTests):
    def snapshot(self, **changes):
        response = self.client.get('/api/debts/payables/settlement', query_string={
            'from':'2026-09-01', 'to':'2026-09-30', 'supplier':'S1', **changes})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json

    def plan(self, amount, **changes):
        snapshot = self.snapshot()
        body = {**snapshot, 'amount':amount, 'payment_date':'2026-09-30',
                'actor':'Người thử', 'request_id':'QUICK-PAY-00001', 'method':'Chuyển khoản', **changes}
        return self.client.post('/api/debts/payables/payments/preview', json=body)

    def test_quick_partial_full_replay_and_reversal_update_exact_balances(self):
        rows = self._ledger_lines([('A',100,'S1'),('B',200,'S1'),('OTHER',500,'S2')])
        with server.db() as conn:
            before = '\n'.join(conn.iterdump())
        preview = self.plan(150)
        self.assertEqual(preview.status_code, 200, preview.json)
        data = preview.json
        self.assertEqual((data['before_amount'],data['amount'],data['after_amount'],data['line_count']), (300,150,150,2))
        self.assertEqual([a['amount'] for a in data['payment']['allocations']], [100,50])
        with server.db() as conn:
            self.assertEqual('\n'.join(conn.iterdump()), before)
        paid = self.client.post('/api/debts/payables/payments',json=data['payment'])
        self.assertEqual(paid.status_code,201,paid.json)
        replay = self.client.post('/api/debts/payables/payments',json=data['payment'])
        self.assertTrue(replay.json['idempotent'])
        self.assertEqual(self.snapshot()['remaining_amount'],150)
        self.assertEqual(self.snapshot(supplier='S2')['remaining_amount'],500)
        debt = self.client.get('/api/debts?from=2026-09-01&to=2026-09-30').json['suppliers']['S1']
        self.assertEqual((debt['period_paid'],debt['closing']), (150,150))
        second = self.plan(150,request_id='QUICK-PAY-00002').json['payment']
        self.assertEqual(self.client.post('/api/debts/payables/payments',json=second).status_code,201)
        self.assertEqual(self.snapshot()['remaining_amount'],0)
        undo = self.client.post('/api/debts/payables/payments/'+str(paid.json['id'])+'/reverse',json={
            'actor':'Người thử','reason':'Hoàn tác kiểm thử','expected_revision':1})
        self.assertEqual(undo.status_code,200,undo.json)
        self.assertEqual(self.snapshot()['remaining_amount'],150)

    def test_quick_scope_dates_order_and_invalid_amounts(self):
        with server.db() as conn:
            batch=self._batch(conn)
            for key,day in [('NEW','2026-09-10'),('OLD','2026-09-01'),('OUTSIDE','2026-08-31')]:
                self._purchase(conn,batch,row_key=key,amount=100,work_date=day)
            sync_payable_ledger(conn,timestamp=server.now_iso())
        snap=self.snapshot()
        self.assertEqual((snap['line_count'],snap['remaining_amount']),(2,200))
        preview=self.plan(50,payment_date='2026-09-01')
        self.assertEqual(preview.status_code,200,preview.json)
        with server.db() as conn:
            row=conn.execute('SELECT product_name FROM payable_ledger_lines WHERE id=?',
                             (preview.json['payment']['allocations'][0]['ledger_line_id'],)).fetchone()
        self.assertEqual(row['product_name'],'Hàng OLD')
        self.assertEqual(self.plan(150,payment_date='2026-09-01').status_code,400)
        for value in (0,-1,201,1.5,True,'NaN'):
            self.assertEqual(self.plan(value).status_code,400,value)
        self.assertEqual(self.plan(10,actor='').status_code,400)
        for query in ({'supplier':''},{'from':'bad'},{'from':'2026-10-01'},{'supplier':'MISSING'}):
            result=self.client.get('/api/debts/payables/settlement',query_string={
                'from':'2026-09-01','to':'2026-09-30','supplier':'S1',**query})
            self.assertEqual(result.status_code,400,result.json)
        self.assertEqual(self.snapshot(supplier='S2')['remaining_amount'],0)

    def test_quick_tamper_stale_snapshot_and_competing_payment(self):
        self._ledger_lines([('A',100,'S1'),('B',200,'S1')])
        plan=self.plan(100).json['payment']
        tampered=copy.deepcopy(plan)
        with server.db() as conn:
            other=conn.execute('SELECT id FROM payable_ledger_lines ORDER BY id DESC').fetchone()[0]
        tampered['allocations'][0]['ledger_line_id']=other
        self.assertEqual(self.client.post('/api/debts/payables/payments',json=tampered).json['code'],'settlement_allocation_mismatch')
        def submit(index):
            with server.app.test_client() as client:
                return client.post('/api/debts/payables/payments',json={**plan,'request_id':f'QUICK-CONCURRENT-{index}'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(submit,range(2))),[201,409])
        self.assertEqual(self.snapshot()['remaining_amount'],200)
        self.assertEqual(self.client.post('/api/debts/payables/payments',json=plan).json['code'],'stale_settlement')

    def test_quick_detects_new_unselected_debt_and_rolls_back_failed_write(self):
        self._ledger_lines([('A',100,'S1'),('B',200,'S1')])
        plan=self.plan(150).json['payment']
        with server.db() as conn:
            conn.execute("CREATE TRIGGER fail_payable_allocation BEFORE INSERT ON payable_payment_allocations BEGIN SELECT RAISE(ABORT,'forced failure'); END")
        self.assertEqual(self.client.post('/api/debts/payables/payments',json=plan).status_code,500)
        self.assertEqual(self.snapshot()['remaining_amount'],300)
        with server.db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM payments').fetchone()[0],0)
            conn.execute('DROP TRIGGER fail_payable_allocation')
            batch=conn.execute('SELECT id FROM batches LIMIT 1').fetchone()[0]
            self._purchase(conn,batch,row_key='C',amount=50)
            sync_payable_ledger(conn,timestamp=server.now_iso())
        self.assertEqual(self.client.post('/api/debts/payables/payments',json=plan).json['code'],'stale_settlement')

    def test_quick_settlement_includes_more_than_500_lines(self):
        self._ledger_lines([(f'ROW-{i}',100,'S1') for i in range(805)])
        preview=self.plan(80500)
        self.assertEqual(preview.status_code,200,preview.json)
        self.assertEqual(preview.json['line_count'],805)
        result=self.client.post('/api/debts/payables/payments',json=preview.json['payment'])
        self.assertEqual(result.status_code,201,result.json)
        self.assertEqual(self.snapshot()['remaining_amount'],0)

    def test_case_only_supplier_variants_share_payment_ledger_export_and_account(self):
        with server.db() as conn:
            conn.execute("INSERT INTO suppliers(code,name) VALUES('s1','Tên viết thường')")
        self._ledger_lines([('A',100,'S1'),('B',200,'s1'),('OTHER',500,'S2')])
        self.assertEqual(self.snapshot()['remaining_amount'],300)
        self.assertEqual(self.snapshot(supplier='s1')['remaining_amount'],300)
        root='/api/debts/payables'
        for code in ('S1','s1'):
            rows=self.client.get(root+'/ledger?from=2026-09-01&to=2026-09-30&supplier='+code).json['rows']
            self.assertEqual(len(rows),2)
        plan=self.plan(150).json['payment']
        self.assertEqual(self.client.post(root+'/payments',json=plan).status_code,201)
        self.assertEqual(self.snapshot()['remaining_amount'],150)
        for code in ('S1','s1'):
            self.assertEqual(self.client.get(root+'/export?from=2026-09-01&to=2026-09-30&supplier='+code).status_code,200)
            history=self.client.get(root+'/payments?from=2026-09-01&to=2026-09-30&supplier='+code).json
            self.assertEqual(history['pagination']['total'],1)
        account=self.client.get('/api/debts?from=2026-09-01&to=2026-09-30').json['suppliers']
        self.assertEqual(account['S1']['closing'],150)
        self.assertNotIn('s1',account)
