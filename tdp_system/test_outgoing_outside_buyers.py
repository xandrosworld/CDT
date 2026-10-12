import unittest
from unittest.mock import patch
from . import server
from .test_outgoing_source_scope import SourceScopeTests as Base
from .test_invoice_output_sync import output_invoice, STATUS_MAP
from .invoice_output_sync import upsert_output_invoice
from .outgoing_source_scope import review_token, resolve_scope
from .outgoing_outside_buyers import rules, forget, apply_remembered


class OutsideBuyerTests(unittest.TestCase):
    setUpClass=classmethod(Base.setUpClass.__func__)
    tearDownClass=classmethod(Base.tearDownClass.__func__)
    add_opening=staticmethod(Base.add_opening)
    add_batch=staticmethod(Base.add_batch)
    seed=Base.seed
    report=Base.report

    def setUp(self):
        Base.setUp(self)
        with server.db() as c:
            c.execute("DELETE FROM settings WHERE key LIKE 'outgoing.outside_buyer.%'")
        self.seed(stock=100)

    def sync(self, number, name='Vũ Thị Vân', tax='', status='FIXTURE_ISSUED', tenant='default'):
        remote=output_invoice(number,status=status)
        remote.update(mstNmua=tax,tenNmua=name)
        with server.db() as c:
            sid,_,_,_=upsert_output_invoice(c,remote,tenant=tenant,now=server.now_iso(),
                status_map={k.casefold():v for k,v in STATUS_MAP.items()},status_fields=['fixtureStatus'],reference_fields=[])
        return sid

    def remember(self,sid):
        with server.db() as c:
            source=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            token=review_token(source)
        response=self.client.put('/api/outgoing-invoices/source-scopes/'+str(sid),json={
            'token':token,'scope':'outside','note':'Khách xác nhận bán ngoài','remember_outside':True})
        self.assertEqual(response.status_code,200,response.json)

    def scope(self,sid):
        with server.db() as c:
            row=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            return resolve_scope(c,row,{})

    def test_future_sync_remembers_without_stock_or_order_mutation_and_repeat_is_idempotent(self):
        sid=self.sync(1);self.remember(sid)
        with server.db() as c:
            before={t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in ['orders','invoice_inventory_ledger','inventory_transactions']}
        new=self.sync(2);self.assertEqual(self.scope(new),(None,''))
        self.assertEqual(self.sync(2),new)
        with server.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM audit_log WHERE event_type='outgoing.outside_buyer' AND message='apply'").fetchone()[0],1)
            for t,rows in before.items():self.assertEqual(rows,[tuple(r) for r in c.execute('SELECT * FROM '+t)])
            self.assertEqual(c.execute('SELECT stock_status FROM outgoing_source_invoices WHERE id=?',(new,)).fetchone()[0],'pending_mapping')

    def test_forget_only_changes_future_invoices(self):
        sid=self.sync(1);self.remember(sid);new=self.sync(2)
        r=self.client.delete('/api/outgoing-invoices/outside-buyers/'+str(sid));self.assertEqual(r.status_code,200)
        self.assertEqual(self.scope(new),(None,''))
        later=self.sync(3);self.assertTrue(self.scope(later)[1])

    def test_does_not_reclassify_existing_invoice(self):
        old=self.sync(1);sid=self.sync(2);self.remember(sid);self.sync(1)
        self.assertTrue(self.scope(old)[1])

    def test_different_name_tax_or_tenant_does_not_match(self):
        self.remember(self.sync(1))
        for n,kwargs in [(2,{'name':'Người khác'}),(3,{'tax':'123456'}),(4,{'tenant':'other'})]:
            self.assertTrue(self.scope(self.sync(n,**kwargs))[1])
        self.assertEqual(self.scope(self.sync(5,name=' VŨ   THỊ VÂN ')),(None,''))

    def test_draft_waits_for_issued_status(self):
        self.remember(self.sync(1));sid=self.sync(2,status='FIXTURE_DRAFT')
        self.assertTrue(self.scope(sid)[1]);self.sync(2)
        self.assertEqual(self.scope(sid),(None,''))

    def test_conflicting_export_requires_review(self):
        from .outgoing_export_lineage import signature
        self.remember(self.sync(1))
        with patch('tdp_system.outgoing_outside_buyers.apply_remembered',return_value=False):sid=self.sync(2)
        with server.db() as c:
            sig=signature(list(c.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=?',(sid,))),True)
            with patch('tdp_system.outgoing_export_lineage.catalog',return_value=[{'created_at':'2000','signature':sig}]):
                self.assertFalse(apply_remembered(c,sid,server.now_iso()))
        self.assertTrue(self.scope(sid)[1])

    def test_known_contractor_cannot_be_remembered(self):
        sid=self.sync(1,name='Nhà thầu A')
        with server.db() as c:token=review_token(c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone())
        r=self.client.put('/api/outgoing-invoices/source-scopes/'+str(sid),json={'token':token,'scope':'outside','note':'Test','remember_outside':True})
        self.assertEqual(r.status_code,409)
        with server.db() as c:self.assertEqual(rules(c),[])

    def test_new_contractor_profile_overrides_remembered_default(self):
        self.remember(self.sync(1))
        with server.db() as c:
            c.execute("INSERT INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Vũ Thị Vân','','','now')")
        self.assertTrue(self.scope(self.sync(2))[1])

    def test_explicit_or_stale_source_decision_is_never_overwritten(self):
        self.remember(self.sync(1));sid=self.sync(2)
        with server.db() as c:
            c.execute("UPDATE outgoing_source_order_scopes SET identity_snapshot='stale' WHERE invoice_id=?",(sid,))
            self.assertFalse(apply_remembered(c,sid,server.now_iso()))
        self.assertTrue(self.scope(sid)[1])

    def test_linked_local_invoice_is_not_classified_outside(self):
        from .test_outgoing_readiness import OutgoingReadinessTests as Fixture
        self.remember(self.sync(1))
        with patch('tdp_system.outgoing_outside_buyers.apply_remembered',return_value=False):sid=self.sync(2)
        with server.db() as c:
            row=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            order=c.execute('SELECT * FROM orders LIMIT 1').fetchone()
            Fixture.add_local_issued_draft(c,order['batch_id'],order['id'],number=row['invoice_number'],series=row['invoice_series'],invoice_date=row['invoice_date'])
            self.assertFalse(apply_remembered(c,sid,server.now_iso()))
        self.assertTrue(self.scope(sid)[1])

    def test_cancelled_and_replaced_sources_stay_unclassified(self):
        self.remember(self.sync(1))
        for n,status in [(2,'FIXTURE_CANCELLED'),(3,'FIXTURE_REPLACED')]:
            self.assertTrue(self.scope(self.sync(n,status=status))[1])
    def test_outside_invoices_remain_accessible_for_customer_correction(self):
        sid=self.sync(1);self.remember(sid)
        with server.db() as c:
            row=c.execute('SELECT invoice_date FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
        r=self.client.get('/api/outgoing-invoices/source-scopes',query_string={'from':row[0],'to':row[0],'contractor':'NT-A','order_scope':'1'})
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(next(x['scope'] for x in r.json['items'] if x['id']==sid),'outside')
        self.assertEqual(len(r.json['outside_buyers']),1)
