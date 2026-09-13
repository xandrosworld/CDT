import io
import unittest
import zipfile
from unittest.mock import patch

from openpyxl import load_workbook

from . import server, test_outgoing_readiness as fixtures
from .outgoing_contractors import choices_payload, line_choices_payload
from .outgoing_readiness import canonical_available_stock, validate_draft_export_stock, OutgoingReadinessError
from .outgoing_unissued import issued_allocations, unissued_payload
from .outgoing_waiting import refresh_waiting


class OutgoingChoiceTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.OutgoingReadinessTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.OutgoingReadinessTests.tearDownClass.__func__)

    def setUp(self):
        fixtures.OutgoingReadinessTests.setUp(self)
        with server.db() as c:
            c.execute('DELETE FROM outgoing_contractor_choices')
            c.execute('DELETE FROM outgoing_order_choices')
            c.execute("INSERT OR IGNORE INTO contractors(code,name,price_group,pricing_mode) VALUES('NT-C','Nhà thầu C','NT-C','group')")
            fixtures.OutgoingReadinessTests.add_opening(c,100)
            self.batch,self.oids=fixtures.OutgoingReadinessTests.add_batch(c,'2026-09-01',[
                {'qty':3,'sell_price':20000}, {'qty':5,'contractor':'NT-B','sell_price':20000},
                {'qty':7,'contractor':'NT-C','sell_price':20000}, {'qty':2,'sell_price':20000}])

    def choices(self):
        response=self.client.get('/api/outgoing-invoices/contractor-choices')
        self.assertEqual(response.status_code,200)
        return {r['code']:r for r in response.get_json()['items']}

    def select_parties(self,changes):
        current=self.choices()
        return self.client.put('/api/outgoing-invoices/contractor-choices',json={'items':[
            {'code':code,'enabled':enabled,'token':current[code]['token']} for code,enabled in changes.items()]})

    def select_lines(self,changes):
        with server.db() as c:
            current={r['order_id']:r for r in line_choices_payload(c,'2026-09-13')}
        return self.client.put('/api/outgoing-invoices/line-choices',json={'items':[
            {'order_id':oid,'enabled':enabled,'token':current[oid]['token']} for oid,enabled in changes.items()]})

    def export(self,party='',path='/api/export/order-invoices'):
        return self.client.post(path,json={'contractor':party,'from':'2026-09-01','to':'2026-09-03'})

    def excel(self,response):
        self.assertEqual(response.status_code,200,response.get_json(silent=True))
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            return {name:list(load_workbook(io.BytesIO(z.read(name)),data_only=True).active.values)[1:]
                for name in z.namelist() if name.endswith('.xlsx')}

    def business_snapshot(self):
        with server.db() as c:
            tables=['orders','batches','products','receivable_ledger_lines','payable_ledger_lines',
                    'invoice_inventory_ledger','outgoing_source_invoices','outgoing_source_invoice_items']
            return {t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in tables}

    def test_get_is_read_only_and_defaults_to_enabled(self):
        with server.db() as c:before=c.serialize()
        data=self.choices()
        self.assertTrue(all(r['enabled'] for r in data.values()))
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_two_disabled_contractors_never_enter_zip_or_reservations(self):
        before=self.business_snapshot()
        r=self.select_parties({'NT-B':False,'NT-C':False})
        self.assertEqual(r.status_code,200,r.get_json())
        output=self.export();files=self.excel(output)
        self.assertEqual(len(files),1)
        self.assertIn('NT-A',next(iter(files)))
        self.assertEqual(next(iter(files.values()))[0][3],5)
        self.assertEqual(output.headers['X-Excluded-Contractors'],'2')
        self.assertEqual(self.business_snapshot(),before)
        with server.db() as c:
            self.assertEqual(canonical_available_stock(c)['HH-01']['reserved_qty'],5)
            self.assertEqual({r[0] for r in c.execute("SELECT contractor FROM outgoing_invoice_drafts WHERE status='draft'")},{'NT-A'})

    def test_disabled_explicit_export_and_catchup_reject_before_remote_sync(self):
        self.select_parties({'NT-A':False})
        with patch('tdp_system.outgoing_source_refresh.refresh_sources') as sync:
            for path in ['/api/export/order-invoices','/api/export/catch-up-invoices']:
                r=self.export('NT-A',path)
                self.assertEqual(r.status_code,409,r.get_json())
                self.assertIn('bỏ chọn',r.get_json()['error'])
            sync.assert_not_called()

    def test_cancel_only_editable_holds_and_legacy_zip_obeys_choice(self):
        self.excel(self.export())
        before=self.business_snapshot()
        result=self.select_parties({'NT-B':False,'NT-C':False})
        self.assertEqual(len(result.get_json()['released_draft_ids']),2)
        legacy=self.client.get(f'/api/export/invoices/{self.batch}')
        files=self.excel(legacy)
        self.assertEqual(len(files),1)
        self.assertIn('NT-A',next(iter(files)))
        self.assertEqual(self.business_snapshot(),before)
        with server.db() as c:
            refresh_waiting(c,server.now_iso())
            refresh_waiting(c,server.now_iso())
            self.assertEqual({r[0] for r in c.execute("SELECT contractor FROM outgoing_invoice_drafts WHERE status='draft'")},{'NT-A'})

    def test_protected_drafts_and_reservations_survive_contractor_exclusion(self):
        for status in ['saved','saving','unknown']:
            with self.subTest(status=status):
                self.setUp()
                self.excel(self.export('NT-A'))
                with server.db() as c:
                    c.execute("UPDATE outgoing_invoice_drafts SET minvoice_status=? WHERE contractor='NT-A' AND status='draft'",(status,))
                    draft=dict(c.execute("SELECT * FROM outgoing_invoice_drafts WHERE status='draft'").fetchone())
                    holds=[tuple(r) for r in c.execute("SELECT * FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT'")]
                r=self.select_parties({'NT-A':False})
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.get_json()['released_draft_ids'],[])
                with server.db() as c:
                    refresh_waiting(c,server.now_iso(),fill=False)
                    self.assertEqual(dict(c.execute('SELECT * FROM outgoing_invoice_drafts WHERE id=?',(draft['id'],)).fetchone()),draft)
                    self.assertEqual([tuple(r) for r in c.execute("SELECT * FROM inventory_transactions WHERE source_type='OUTGOING_DRAFT'")],holds)
                    with self.assertRaises(OutgoingReadinessError):validate_draft_export_stock(c,draft['id'])

    def test_bulk_stale_unknown_duplicate_or_invalid_choice_is_atomic(self):
        a=self.choices()['NT-A'];b=self.choices()['NT-B']
        good={'code':'NT-A','enabled':False,'token':a['token']}
        for bad in [{'code':'NT-B','enabled':False,'token':'stale'},
                    {'code':'missing','enabled':False,'token':''}, good,
                    {'code':'NT-B','enabled':'false','token':b['token']}]:
            with self.subTest(bad=bad):
                r=self.client.put('/api/outgoing-invoices/contractor-choices',json={'items':[good,bad]})
                self.assertEqual(r.status_code,409)
                self.assertTrue(self.choices()['NT-A']['enabled'])

    def test_old_tab_cannot_overwrite_saved_choice(self):
        old=self.choices()['NT-A']
        self.select_parties({'NT-A':False})
        r=self.client.put('/api/outgoing-invoices/contractor-choices',json={'items':[{'code':'NT-A','enabled':True,'token':old['token']}]})
        self.assertEqual(r.status_code,409)
        self.assertFalse(self.choices()['NT-A']['enabled'])

    def test_reenable_restores_eligibility_without_creating_sales(self):
        before=self.business_snapshot()
        self.select_parties({'NT-A':False})
        self.excel(self.export())
        self.select_parties({'NT-A':True})
        self.assertEqual(len(self.excel(self.export())),3)
        self.assertEqual(self.business_snapshot(),before)
        with server.db() as c:self.assertEqual(canonical_available_stock(c)['HH-01']['reserved_qty'],17)

    def test_unapproved_excluded_only_day_does_not_block_range(self):
        self.select_parties({'NT-B':False})
        with server.db() as c:
            bid,_=fixtures.OutgoingReadinessTests.add_batch(c,'2026-09-02',[{'contractor':'NT-B','qty':10}])
            c.execute("UPDATE batches SET status='draft' WHERE id=?",(bid,))
        self.assertEqual(len(self.excel(self.export())),2)

    def test_all_excluded_has_no_new_draft_or_file(self):
        self.select_parties({'NT-A':False,'NT-B':False,'NT-C':False})
        self.assertEqual(self.export().status_code,409)
        r=self.client.post(f'/api/outgoing-invoices/draft/{self.batch}')
        self.assertEqual(r.status_code,400,r.get_json())
        self.assertIn('không có nhà thầu',r.get_json()['error'])
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_invoice_drafts').fetchone()[0],0)

    def test_skip_line_splits_group_preserves_original_and_can_restore(self):
        before=self.business_snapshot()
        self.excel(self.export('NT-A'))
        result=self.select_lines({self.oids[0]:False})
        self.assertEqual(result.status_code,200,result.get_json())
        self.assertEqual(len(result.get_json()['released_draft_ids']),1)
        files=self.excel(self.export('NT-A'))
        self.assertEqual(next(iter(files.values()))[0][3],2)
        self.assertEqual(self.business_snapshot(),before)
        self.select_lines({self.oids[0]:True})
        self.assertEqual(next(iter(self.excel(self.export('NT-A')).values()))[0][3],5)

    def test_line_choice_is_persistent_but_history_retains_all_orders(self):
        self.select_lines({self.oids[0]:False})
        self.select_parties({'NT-B':False})
        result=self.client.get('/api/outgoing-invoices/unissued?to=2026-09-03').get_json()
        self.assertNotIn(self.oids[0],{r['order_id'] for r in result['details']})
        self.assertNotIn('NT-B',{r['contractor'] for r in result['details']})
        self.assertFalse(next(r for r in result['line_choices'] if r['order_id']==self.oids[0])['enabled'])
        with server.db() as c:
            self.assertEqual(len(unissued_payload(c,'2026-09-03')['details']),4)
            refresh_waiting(c,server.now_iso())
            active={r[0] for r in c.execute("SELECT a.order_id FROM outgoing_order_allocations a JOIN outgoing_invoice_drafts d ON d.id=a.draft_id WHERE d.status='draft'")}
            self.assertNotIn(self.oids[0],active)
            self.assertNotIn(self.oids[1],active)

    def test_signed_after_cutoff_still_subtracted_after_reenable(self):
        with server.db() as c:
            did=fixtures.OutgoingReadinessTests.add_local_issued_draft(c,self.batch,self.oids[0],number='SIGNED-TEST',qty=1,invoice_date='2026-09-04')
            before_issued=[tuple(r) for r in c.execute('SELECT * FROM outgoing_invoice_drafts WHERE id=?',(did,))]
            self.assertEqual(issued_allocations(c)[0][self.oids[0]],1)
        self.select_lines({self.oids[0]:False})
        self.select_parties({'NT-A':False})
        self.select_parties({'NT-A':True})
        self.select_lines({self.oids[0]:True})
        self.assertEqual(next(iter(self.excel(self.export('NT-A')).values()))[0][3],4)
        with server.db() as c:
            self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM outgoing_invoice_drafts WHERE id=?',(did,))],before_issued)
            self.assertEqual(issued_allocations(c)[0][self.oids[0]],1)

    def test_protected_line_selection_rejected(self):
        self.excel(self.export('NT-A'))
        with server.db() as c:c.execute("UPDATE outgoing_invoice_drafts SET minvoice_status='saved' WHERE status='draft'")
        result=self.select_lines({self.oids[0]:False})
        self.assertEqual(result.status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_order_choices').fetchone()[0],0)

    def test_stale_line_batch_changes_nothing(self):
        with server.db() as c:rows={r['order_id']:r for r in line_choices_payload(c,'2026-09-13')}
        with server.db() as c:c.execute('UPDATE orders SET actual_delivered=1 WHERE id=?',(self.oids[3],))
        r=self.client.put('/api/outgoing-invoices/line-choices',json={'items':[
            {'order_id':oid,'enabled':False,'token':rows[oid]['token']} for oid in [self.oids[0],self.oids[3]]]})
        self.assertEqual(r.status_code,409)
        with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_order_choices').fetchone()[0],0)

    def test_all_lines_excluded_draft_creation_and_export_reject(self):
        self.select_lines({oid:False for oid in self.oids})
        self.assertEqual(self.export().status_code,409)
        with server.db() as c:
            refresh_waiting(c,server.now_iso())
            self.assertEqual(c.execute("SELECT COUNT(*) FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0],0)

    def test_reenable_contractor_does_not_reenable_excluded_line(self):
        self.select_lines({self.oids[0]:False})
        self.select_parties({'NT-A':False})
        self.select_parties({'NT-A':True})
        self.assertEqual(next(iter(self.excel(self.export('NT-A')).values()))[0][3],2)


if __name__=='__main__':
    unittest.main()
