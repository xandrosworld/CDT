import unittest
from unittest.mock import patch
from . import server,test_outgoing_source_scope as fixtures
from .outgoing_source_acceptance import preview,confirm,coverage
from .outgoing_unissued import issued_allocations


class SourceAcceptanceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.Fixture.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.Fixture.tearDownClass.__func__)
    seed=fixtures.SourceScopeTests.seed
    add_opening=staticmethod(fixtures.Fixture.add_opening)
    add_batch=staticmethod(fixtures.Fixture.add_batch)

    def setUp(self):
        fixtures.SourceScopeTests.setUp(self)
        with server.db() as c:
            for table in ('outgoing_source_acceptances','outgoing_source_item_reviews','outgoing_source_order_periods','outgoing_export_receipts'):
                c.execute('DELETE FROM '+table)
        self.seed(stock=50)
        with server.db() as c:
            c.execute("UPDATE orders SET tax='KKKNT'")
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Test','0101234567','Test','today')")
            c.execute("INSERT OR REPLACE INTO products(code,name,unit,tax) VALUES('OTHER','Changed item','kg','KKKNT')")
            self.sid=fixtures.Fixture.add_posted_source(c,source='minvoice',number='883',qty=7,invoice_date='2026-09-03')
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567',subtotal=200,total_amount=200 WHERE id=?",(self.sid,))
            c.execute('UPDATE invoice_inventory_ledger SET source_line_id=source_line_id+1 WHERE source_invoice_id=?',(self.sid,))
            fixtures.Fixture.add_canonical_event(c,-2,'output','acceptance-other',work_date='2026-09-03',source_table='outgoing_source_invoices',source_id=self.sid,product_code='OTHER')
            for index,code,qty,price in ((1,'HH-01',7,20),(2,'OTHER',2,30)):
                c.execute("INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,source_item_name,source_unit,qty,unit_price,amount,tax_rate,source_nature) VALUES(?,?,?,'Goods','kg',?,?,?,'-2','1')",(self.sid,index,code,qty,price,qty*price))

    def accept(self,c):
        report=preview(c,self.sid)
        body={'actor':'Customer confirmed via support','reason':'Keep invoice under this buyer; unmatched goods separate','confirmed':True,'token':report['token']}
        return confirm(c,self.sid,body,server.now_iso()),body

    def test_acceptance_only_removes_reviewed_hold_and_preserves_every_allocation(self):
        with server.db() as c:
            links={};before,w=issued_allocations(c,source_order_allocations=links)
            business={t:list(map(tuple,c.execute('SELECT * FROM '+t))) for t in ('orders','outgoing_source_invoices','outgoing_source_invoice_items','invoice_inventory_ledger','inventory_transactions')}
            self.assertEqual(len(w),1)
            result,body=self.accept(c)
            self.assertEqual(result['accepted']['allocated_order_rows'],2)
            self.assertEqual(result['accepted']['unmatched'][0]['qty'],2)
            later={};after,w=issued_allocations(c,source_order_allocations=later)
            self.assertEqual(after,before);self.assertEqual(links,later);self.assertEqual(w,[])
            self.assertTrue(confirm(c,self.sid,body,server.now_iso())['unchanged'])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_source_acceptances').fetchone()[0],1)
            for t,value in business.items():self.assertEqual(value,list(map(tuple,c.execute('SELECT * FROM '+t))))

    def test_new_orders_never_absorb_accepted_unmatched_quantity(self):
        with server.db() as c:
            before,_=issued_allocations(c);self.accept(c)
            _,oids=self.add_batch(c,'2026-09-02',[{'qty':2,'product_code':'OTHER'}])
            c.execute("UPDATE orders SET tax='KKKNT' WHERE id=?",(oids[0],))
            after,w=issued_allocations(c)
            self.assertEqual(after,before);self.assertEqual(w,[]);self.assertNotIn(oids[0],after)

    def test_sync_timestamps_do_not_invalidate_customer_confirmation(self):
        with server.db() as c:
            self.accept(c);before,_=issued_allocations(c)
            c.execute("UPDATE outgoing_source_invoices SET synced_at='later',updated_at='later' WHERE id=?",(self.sid,))
            c.execute('UPDATE outgoing_source_invoice_items SET id=id+10000 WHERE invoice_id=?',(self.sid,))
            self.assertTrue(coverage(c)[self.sid]['valid'])
            self.assertEqual(issued_allocations(c),(before,[]))

    def test_content_or_order_changes_invalidate_instead_of_hiding_errors(self):
        for sql in ("UPDATE outgoing_source_invoices SET total_amount=201 WHERE id=?",
                    "UPDATE outgoing_source_invoice_items SET qty=9 WHERE invoice_id=?",
                    "UPDATE outgoing_source_invoices SET source_status_class='replaced' WHERE id=?"):
            with self.subTest(sql=sql):
                self.setUp()
                with server.db() as c:
                    self.accept(c);c.execute(sql,(self.sid,))
                    self.assertFalse(coverage(c)[self.sid]['valid'])
                    q,w=issued_allocations(c);self.assertTrue(any(x.get('code')=='accepted_source_changed' for x in w))

    def test_preview_token_rechecks_allocations_and_requires_explicit_confirmation(self):
        with server.db() as c:
            p=preview(c,self.sid)
            body={'actor':'Test','reason':'Confirmed','token':p['token'],'confirmed':False}
            with self.assertRaises(ValueError):confirm(c,self.sid,body,server.now_iso())
            c.execute('UPDATE orders SET actual_delivered=actual_delivered+1')
            body['confirmed']=True
            with self.assertRaisesRegex(ValueError,'Dữ liệu vừa thay đổi'):confirm(c,self.sid,body,server.now_iso())
            self.assertEqual(c.execute('SELECT COUNT(*) FROM outgoing_source_acceptances').fetchone()[0],0)

    def test_vat_and_unposted_source_cannot_be_accepted(self):
        with server.db() as c:
            c.execute("UPDATE outgoing_source_invoice_items SET tax_rate='8' WHERE invoice_id=?",(self.sid,))
            with self.assertRaisesRegex(ValueError,'KKKNT'):preview(c,self.sid)
            c.execute("UPDATE outgoing_source_invoice_items SET tax_rate='-2' WHERE invoice_id=?",(self.sid,))
            c.execute("UPDATE outgoing_source_invoices SET stock_status='reversal_required' WHERE id=?",(self.sid,))
            with self.assertRaises(ValueError):preview(c,self.sid)

    def test_amount_settlement_requires_reopening_and_history_visible(self):
        from .outgoing_amount_settlement import preview as money_preview
        from .outgoing_source_scope import scope_report
        with server.db() as c:
            self.accept(c)
            r=money_preview(c,{'contractor':'NT-A','from':'2026-09-01','to':'2026-09-03','invoice_ids':[self.sid],'reviewed_kkknt':True})
            self.assertFalse(r['can_confirm']);self.assertIn('chênh lệch riêng',' '.join(r['conflicts']))
            row=next(x for x in scope_report(c,'2026-09-01','2026-09-30','NT-A',order_scope=True) if x['id']==self.sid)
            self.assertFalse(row['error']);self.assertTrue(row['acceptance']['valid'])

    def test_routes_revoke_restores_hold_and_keeps_audit(self):
        r=self.client.get(f'/api/outgoing-invoices/source-scopes/{self.sid}/acceptance')
        self.assertEqual(r.status_code,200,r.json)
        with patch('tdp_system.outgoing_source_refresh.refresh_sources',return_value={'ok':True}):
            r=self.client.post(f'/api/outgoing-invoices/source-scopes/{self.sid}/acceptance',json={'action':'confirm','actor':'Test','reason':'Confirmed by customer','confirmed':True,'token':r.json['token']})
        self.assertEqual(r.status_code,200,r.json)
        r=self.client.post(f'/api/outgoing-invoices/source-scopes/{self.sid}/acceptance',json={'action':'revoke','actor':'Test','reason':'Recheck source'})
        self.assertEqual(r.status_code,200,r.json)
        with server.db() as c:
            self.assertTrue(issued_allocations(c)[1]);self.assertEqual(len(coverage(c)),0)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM audit_log WHERE event_type LIKE 'outgoing.source.acceptance%'").fetchone()[0],2)
