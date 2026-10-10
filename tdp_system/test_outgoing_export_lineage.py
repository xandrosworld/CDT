import json
import unittest
from . import server, test_outgoing_source_scope as fixtures
from . import outgoing_export_receipts as receipts
from .outgoing_unissued import issued_allocations, warning_applies_to_order
from .outgoing_export_lineage import matches, catalog


class ExportLineageTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.Fixture.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.Fixture.tearDownClass.__func__)
    seed=fixtures.SourceScopeTests.seed
    add_opening=staticmethod(fixtures.Fixture.add_opening)
    add_batch=staticmethod(fixtures.Fixture.add_batch)

    def setUp(self):
        fixtures.SourceScopeTests.setUp(self)
        with server.db() as c:
            for table in ('outgoing_export_receipts','outgoing_source_item_reviews','outgoing_source_order_periods','outgoing_line_allocations','outgoing_waiting_settlements'):
                c.execute('DELETE FROM '+table)
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-A','Buyer','0101234567','Test','today')")
        self.seed(stock=100)

    def export(self, date='2026-10-01', qty=4):
        with server.db() as c:batch,oids=self.add_batch(c,date,[{'qty':qty}])
        response=self.client.post('/api/outgoing-invoices/draft/'+str(batch))
        self.assertEqual(response.status_code,200,response.json)
        with server.db() as c:
            draft=c.execute('SELECT * FROM outgoing_invoice_drafts WHERE batch_id=?',(batch,)).fetchone()
            token=receipts.create(c,[draft['id']],b'file','table.zip','2026-10-01T10:00:00')
            c.execute("UPDATE outgoing_export_receipts SET received_at='2026-10-01T10:00:01' WHERE token=?",(token,))
            return draft['id'],oids[0],token

    def source(self, number='883', qty=4, date='2026-10-07'):
        with server.db() as c:
            sid=fixtures.Fixture.add_posted_source(c,source='minvoice',number=number,qty=qty,invoice_date=date)
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='0101234567',subtotal=?,total_amount=? WHERE id=?",(qty*20,qty*20,sid))
            c.execute("INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,source_item_name,source_unit,qty,unit_price,amount,tax_rate,source_nature) VALUES(?,1,'HH-01','Name','kg',?,20,?,'0%','1')",(sid,qty,qty*20))
            return sid

    def test_download_only_does_not_issue_then_signed_source_uses_exact_order(self):
        did,oid,token=self.export()
        with server.db() as c:
            _,other=self.add_batch(c,'2026-10-01',[{'qty':4}])
            self.assertEqual(issued_allocations(c)[0],{})
        sid=self.source()
        with server.db() as c:
            before={t:list(map(tuple,c.execute('SELECT * FROM '+t))) for t in ('orders','invoice_inventory_ledger','outgoing_source_invoices')}
            q,w=issued_allocations(c)
            self.assertEqual(q,{oid:4});self.assertFalse(w)
            self.assertNotIn(other[0],q)
            self.assertEqual(issued_allocations(c),(q,w))
            for t,v in before.items():self.assertEqual(v,list(map(tuple,c.execute('SELECT * FROM '+t))))

    def test_frozen_file_survives_draft_edits_and_cancellation(self):
        did,oid,_=self.export();sid=self.source()
        with server.db() as c:
            c.execute("UPDATE outgoing_invoice_drafts SET status='cancelled' WHERE id=?",(did,))
            c.execute('UPDATE outgoing_invoice_lines SET qty=99,amount=1980 WHERE draft_id=?',(did,))
            self.assertEqual(issued_allocations(c),({oid:4},[]))

    def test_changed_original_order_holds_exact_rows_without_fifo_fallback(self):
        _,oid,_=self.export();sid=self.source()
        with server.db() as c:
            c.execute('UPDATE orders SET sell_price=21 WHERE id=?',(oid,))
            q,w=issued_allocations(c);self.assertFalse(q)
            self.assertEqual(w[0]['code'],'export_lineage_review')
            self.assertTrue(warning_applies_to_order(w[0],{'id':oid,'contractor':'NT-A','work_date':'2026-10-01'}))
            self.assertFalse(warning_applies_to_order(w[0],{'id':999,'contractor':'NT-A','work_date':'2026-10-01'}))

    def test_ambiguous_tables_never_choose_first_or_previous_month(self):
        self.export();self.export(date='2026-10-02');sid=self.source()
        with server.db() as c:
            q,w=issued_allocations(c);self.assertFalse(q)
            self.assertIn('nhiều bảng kê',w[0]['message'])

    def test_two_signed_invoices_cannot_consume_same_export_twice(self):
        self.export();self.source('883');self.source('884')
        with server.db() as c:
            q,w=issued_allocations(c);self.assertFalse(q)
            self.assertEqual(len(w),2)
            self.assertTrue(all(x['code']=='export_lineage_review' for x in w))

    def test_exact_export_reserved_before_earlier_unlinked_invoice_fifo(self):
        from .outgoing_source_scope import set_scope,review_token
        _,oid,_=self.export();early=self.source('882',qty=3,date='2026-10-06');late=self.source('883')
        with server.db() as c:
            source=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(early,)).fetchone()
            set_scope(c,early,{'token':review_token(source),'scope':'orders','contractor':'NT-A',
                'date_from':'2026-09-01','date_to':'2026-10-06','note':'Reviewed source'},server.now_iso())
            links={};q,w=issued_allocations(c,source_order_allocations=links)
            self.assertEqual(links[late],{oid:4});self.assertNotIn(oid,links[early]);self.assertFalse(w)

    def test_legacy_receipt_only_recovered_if_saved_hash_unchanged(self):
        did,oid,token=self.export();sid=self.source()
        with server.db() as c:
            row=c.execute('SELECT manifest FROM outgoing_export_receipts WHERE token=?',(token,)).fetchone()
            entries=json.loads(row[0]);del entries[0]['source_basis']
            c.execute('UPDATE outgoing_export_receipts SET manifest=? WHERE token=?',(json.dumps(entries),token))
            self.assertEqual(len(catalog(c)),1)
            source=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            self.assertEqual(matches(c,source,'NT-A'),[])
            c.execute('UPDATE outgoing_invoice_lines SET qty=99 WHERE draft_id=?',(did,))
            self.assertEqual(catalog(c),[])

    def test_changed_code_qty_or_buyer_is_not_exact_and_comparison_is_read_only(self):
        self.export();sid=self.source()
        with server.db() as c:
            s=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            self.assertEqual(len(matches(c,s,'NT-A')),1)
            c.execute("UPDATE outgoing_source_invoice_items SET source_item_code='OTHER' WHERE invoice_id=?",(sid,))
            self.assertEqual(matches(c,s,'NT-A'),[])
            c.execute("UPDATE outgoing_source_invoice_items SET source_item_code='HH-01',qty=3 WHERE invoice_id=?",(sid,))
            self.assertEqual(matches(c,s,'NT-A'),[])
            c.execute('UPDATE outgoing_source_invoice_items SET qty=4 WHERE invoice_id=?',(sid,))
            self.assertEqual(matches(c,{**dict(s),'buyer_tax_code':'other'},'NT-A'),[])
            before=c.serialize()
        response=self.client.get('/api/outgoing-invoices/source-scopes/'+str(sid)+'/comparison')
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(len(response.json['candidates']),1)
        with server.db() as c:self.assertEqual(c.serialize(),before)

    def test_changed_file_requires_source_instead_of_silent_previous_month_fifo(self):
        from .outgoing_source_scope import set_scope,review_token
        self.export();sid=self.source(qty=3)
        with server.db() as c:
            q,w=issued_allocations(c)
            self.assertFalse(q)
            self.assertEqual(w[0]['code'],'export_source_required')
            self.assertEqual(w[0]['invoice_id'],sid)
            source=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            with self.assertRaisesRegex(ValueError,'Từ ngày đơn'):
                set_scope(c,sid,{'token':review_token(source),'scope':'orders','contractor':'NT-A','note':'Unknown period'},server.now_iso())

    def test_wrong_buyer_never_silently_consumes_same_item_for_other_contractor(self):
        from .outgoing_export_lineage import comparison
        self.export();sid=self.source()
        with server.db() as c:
            self.add_batch(c,'2026-10-01',[{'qty':4,'contractor':'NT-B'}])
            c.execute("INSERT OR REPLACE INTO outgoing_buyer_profiles(contractor,legal_name,tax_code,address,updated_at) VALUES('NT-B','Other buyer','OTHER-TAX','Test','today')")
            c.execute("UPDATE outgoing_source_invoices SET buyer_tax_code='OTHER-TAX' WHERE id=?",(sid,))
            q,w=issued_allocations(c);self.assertFalse(q)
            self.assertEqual(w[0]['code'],'export_source_required')
            source=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            result=comparison(c,source,'NT-B')
            self.assertEqual(result['candidates'],[])
            self.assertEqual(result['other_buyers'][0]['contractor'],'NT-A')

    def test_review_survives_reinserted_source_rows_but_invalidates_business_change(self):
        from .outgoing_source_item_review import save_review, reviewed_items, fingerprint, upgrade_fingerprints
        from .outgoing_source_scope import set_scope,review_token
        _,oid,_=self.export();sid=self.source()
        with server.db() as c:
            source=c.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(sid,)).fetchone()
            set_scope(c,sid,{'token':review_token(source),'scope':'orders','contractor':'NT-A','date_from':'2026-10-01','date_to':'2026-10-02','note':'Customer confirmed'},server.now_iso())
            items=[{'source_code':'HH-01','order_ids':[oid]}]
            save_review(c,source,'NT-A','2026-10-01','2026-10-02',items,'Confirmed',server.now_iso())
            c.execute('UPDATE outgoing_source_item_reviews SET fingerprint=? WHERE invoice_id=?',(fingerprint(c,sid,items,legacy=True),sid))
            upgrade_fingerprints(c)
            self.assertTrue(c.execute('SELECT fingerprint FROM outgoing_source_item_reviews WHERE invoice_id=?',(sid,)).fetchone()[0].startswith('v2:'))
            c.execute('UPDATE outgoing_source_invoice_items SET id=id+10000 WHERE invoice_id=?',(sid,))
            self.assertFalse(reviewed_items(c,sid)[1])
            c.execute('UPDATE outgoing_source_invoice_items SET qty=3 WHERE invoice_id=?',(sid,))
            self.assertTrue(reviewed_items(c,sid)[1])
            upgrade_fingerprints(c);self.assertTrue(reviewed_items(c,sid)[1])
