import unittest
from unittest.mock import patch
from . import server
from .outgoing_source_scope import review_token,set_scope
from .test_outgoing_unissued import UnissuedTests
from .test_outgoing_readiness import OutgoingReadinessTests as Fixture


class SourceScopeTests(unittest.TestCase):
    setUpClass=classmethod(Fixture.setUpClass.__func__)
    tearDownClass=classmethod(Fixture.tearDownClass.__func__)
    add_opening=staticmethod(Fixture.add_opening)
    add_batch=staticmethod(Fixture.add_batch)
    seed=UnissuedTests.seed
    request=UnissuedTests.request
    report=UnissuedTests.report

    def setUp(self):
        with server.db() as c:
            c.execute('DELETE FROM output_stock_remaps')
            c.execute('DELETE FROM invoice_inventory_ledger')
            c.execute('DELETE FROM invoice_mapping_revisions')
            c.execute('DELETE FROM invoice_line_mappings')
            c.execute('DELETE FROM invoice_sync_batch_output_invoices')
        Fixture.setUp(self)
        with server.db() as c:
            c.execute('DELETE FROM outgoing_source_order_scopes')
            c.execute('DELETE FROM outgoing_buyer_profiles')
            c.execute("DELETE FROM settings WHERE key='minvoice_active_connection'")

    def source(self,qty=3,code='HH-01'):
        with server.db() as c:
            return Fixture.add_posted_source(c,source='minvoice',qty=qty,product_code=code,invoice_date='2026-09-03',number='789')

    def assign(self,sid,scope='orders',party='NT-A'):
        with server.db() as c:
            row=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            return set_scope(c,sid,{'token':review_token(row),'scope':scope,'contractor':party,'note':'Đối chiếu nguồn đơn'},server.now_iso())

    def test_outside_sale_keeps_stock_issue_without_deducting_orders(self):
        self.seed(stock=20);sid=self.source()
        self.assertFalse(self.report()['reconciliation_complete'])
        with server.db() as c:before=[tuple(r) for r in c.execute('SELECT * FROM invoice_inventory_ledger')]
        self.assign(sid,'outside')
        self.assertTrue(self.report()['reconciliation_complete'])
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],10)
        with server.db() as c:self.assertEqual(before,[tuple(r) for r in c.execute('SELECT * FROM invoice_inventory_ledger')])

    def test_manual_invoice_link_settles_orders_and_repeat_is_not_double_counted(self):
        self.seed(stock=20);sid=self.source();self.assign(sid)
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],7)
        self.assign(sid)
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],7)
        with server.db() as c:
            c.execute("UPDATE outgoing_source_invoices SET buyer_name='Người mua đã thay đổi' WHERE id=?",(sid,))
        self.assertFalse(self.report()['reconciliation_complete'])
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],10)

    def test_full_external_issue_does_not_leave_a_float_dust_draft(self):
        from .outgoing_waiting import refresh_waiting
        self.seed(stock=20);self.assertEqual(self.request().status_code,200)
        sid=self.source(qty=9.999999999999998);self.assign(sid)
        with server.db() as c:
            result=refresh_waiting(c,server.now_iso(),fill=False)
            self.assertEqual(result['warnings'],[])
            self.assertEqual(c.execute("SELECT COUNT(*) FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT' AND status='reserved'").fetchone()[0],0)

    def test_stale_review_or_missing_contractor_cannot_be_saved(self):
        self.seed();sid=self.source()
        response=self.client.put('/api/outgoing-invoices/source-scopes/'+str(sid),json={'token':'old','scope':'outside','note':'Test'})
        self.assertEqual(response.status_code,409)
        with self.assertRaises(ValueError):self.assign(sid,'orders','NOT-A-CONTRACTOR')

    def test_review_waits_for_source_writer_then_rechecks_identity(self):
        import threading
        self.seed();sid=self.source()
        with server.db() as c:
            token=review_token(c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone())
        locked=threading.Event();release=threading.Event();failures=[]
        def writer():
            try:
                with server.db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    c.execute("UPDATE outgoing_source_invoices SET buyer_name='Người mua mới' WHERE id=?",(sid,))
                    locked.set()
                    if not release.wait(5):raise AssertionError('Writer not released')
            except Exception as exc:failures.append(exc);locked.set()
        thread=threading.Thread(target=writer);thread.start()
        self.assertTrue(locked.wait(5))
        timer=threading.Timer(.15,release.set);timer.start()
        try:
            response=self.client.put('/api/outgoing-invoices/source-scopes/'+str(sid),json={'token':token,'scope':'outside','note':'Nguồn vừa thay đổi'})
        finally:
            release.set();thread.join(5);timer.cancel()
        self.assertEqual(failures,[])
        self.assertEqual(response.status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_source_order_scopes').fetchone()[0],0)

    def test_unmatched_issued_code_blocks_another_export(self):
        self.seed(stock=20)
        with server.db() as c:c.execute("INSERT OR REPLACE INTO products(code,name,unit) VALUES('OTHER','Mã khác','kg')")
        sid=self.source(code='OTHER');self.assign(sid)
        report=self.report();self.assertFalse(report['reconciliation_complete'])
        self.assertIn('OTHER',str(report['warnings']))
        self.assertEqual(self.request().status_code,409)

    def test_known_other_contractor_conflict_does_not_block_selected_export(self):
        self.seed(stock=30)
        with server.db() as c:
            self.add_batch(c,'2026-09-02',[{'qty':4,'contractor':'NT-B'}])
            c.execute("INSERT OR REPLACE INTO products(code,name,unit) VALUES('OTHER','Mã khác','kg')")
        sid=self.source(code='OTHER');self.assign(sid,party='NT-B')
        self.assertEqual(self.request(contractor='NT-B').status_code,409)
        all_response=self.request(contractor='')
        self.assertEqual(all_response.status_code,200,all_response.get_json(silent=True))
        self.assertEqual(all_response.headers['X-Blocked-Contractors'],'1')
        response=self.request(contractor='NT-A')
        self.assertEqual(response.status_code,200,response.get_json(silent=True))
        self.assertEqual(response.headers['X-Invoice-Files'],'1')
        with server.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM outgoing_invoice_drafts WHERE contractor='NT-B'").fetchone()[0],0)

    def test_unknown_buyer_still_requires_reconciliation_for_selected_export(self):
        self.seed(stock=30);self.source()
        self.assertEqual(self.request(contractor='NT-A').status_code,409)

    def test_verified_buyer_profile_resolves_future_invoices(self):
        self.seed(stock=30);sid=self.source()
        self.assertEqual(self.request().status_code,409)
        with server.db() as c:
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0200168673' WHERE id=?",(sid,))
            tax=c.execute('SELECT buyer_tax_code FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()[0]
            c.execute("INSERT INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Khách hàng',?,'Test',?)",(tax,server.now_iso()))
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],7)
        self.assertEqual(self.request().status_code,200)
        self.assertEqual(self.request().status_code,200)
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],7)

    def test_effective_stock_identity_is_used_after_a_reviewed_remap(self):
        self.seed(stock=20)
        with server.db() as c:c.execute("INSERT OR REPLACE INTO products(code,name,unit) VALUES('OTHER','Mã khác','kg')")
        sid=self.source(code='OTHER');self.assign(sid)
        with server.db() as c:
            lid=c.execute("SELECT id FROM invoice_inventory_ledger WHERE source_invoice_id=? AND direction='output'",(sid,)).fetchone()[0]
            c.execute("INSERT INTO output_stock_remaps(ledger_id,product_code,revision,updated_at,unit_cost) VALUES(?,'HH-01',1,?,10)",(lid,server.now_iso()))
        report=self.report();self.assertTrue(report['reconciliation_complete'])
        self.assertEqual(report['rows'][0]['unissued_qty'],7)

    def test_connected_export_cannot_skip_failed_source_refresh(self):
        self.seed(stock=20)
        with server.db() as c:c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('minvoice_active_connection','portal')")
        try:
            with patch('tdp_system.outgoing_source_refresh.refresh_sources',side_effect=ValueError('M-Invoice không phản hồi')):
                response=self.request()
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.get_json()['code'],'issued_sync_required')
            with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)
        finally:
            with server.db() as c:c.execute("DELETE FROM settings WHERE key='minvoice_active_connection'")

    def test_connected_export_refreshes_even_on_repeat_download(self):
        self.seed(stock=20)
        with server.db() as c:c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('minvoice_active_connection','portal')")
        try:
            with patch('tdp_system.outgoing_source_refresh.refresh_sources',return_value={}) as sync:
                self.assertEqual(self.request().status_code,200)
                self.assertEqual(self.request().status_code,200)
                self.assertEqual(sync.call_count,2)
        finally:
            with server.db() as c:c.execute("DELETE FROM settings WHERE key='minvoice_active_connection'")

    def test_real_sync_pipeline_posts_once_and_removes_signed_quantity_from_waiting(self):
        from .test_invoice_output_sync import documented_minvoice_invoice,OutputFixtureMsmi
        from .outgoing_source_refresh import refresh_sources
        self.seed(stock=20);self.assertEqual(self.request().status_code,200)
        with server.db() as c:
            c.execute("INSERT INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Khách hàng kiểm thử','0209999999','Test',?)",(server.now_iso(),))
        remote=documented_minvoice_invoice(1);remote['inv_invoiceIssuedDate']='2026-09-10'
        remote['details'][0]['inv_itemCode']='HH-01';remote['details'][0]['inv_itemName']='Hàng hóa 01'
        client=OutputFixtureMsmi([remote])
        first=refresh_sources(server.db,lambda:client,server.now_iso,'2026-09-01','2026-09-11')
        self.assertEqual(first['blocked'],[])
        self.assertEqual(len(first['posted']),1)
        report=self.report();self.assertTrue(report['reconciliation_complete'],report['warnings'])
        self.assertEqual(report['rows'][0]['issued_qty'],2)
        self.assertEqual(report['rows'][0]['drafted_qty'],8)
        with server.db() as c:
            ledger=[tuple(r) for r in c.execute('SELECT * FROM invoice_inventory_ledger')]
        second=refresh_sources(server.db,lambda:client,server.now_iso,'2026-09-01','2026-09-11')
        self.assertEqual(second['posted'],[])
        self.assertEqual(self.report()['rows'][0]['unissued_qty'],8)
        with server.db() as c:self.assertEqual(ledger,[tuple(r) for r in c.execute('SELECT * FROM invoice_inventory_ledger')])
