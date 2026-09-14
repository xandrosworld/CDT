import json
import subprocess
import unittest
from pathlib import Path
from . import server, test_outgoing_review as fixture
from .outgoing_export_diagnostics import empty_export_diagnostic


class EmptyExportTests(unittest.TestCase):
    setUpClass=classmethod(fixture.InvoiceReviewTests.setUpClass.__func__)
    tearDownClass=classmethod(fixture.InvoiceReviewTests.tearDownClass.__func__)
    setUp=fixture.InvoiceReviewTests.setUp

    def body(self, period=None):
        period=period or self.period
        data=self.client.get('/api/outgoing-invoices/unissued',query_string=period).json
        return {**period,'scope':'approved_range','invoice_date':'2026-09-14','review_confirmed':True,
                'review_rows':[{'order_id':r['order_id'],'token':r['token']} for r in data['line_choices']]}

    def saved(self):
        with server.db() as c:
            return {t:[tuple(r) for r in c.execute('SELECT * FROM '+t)] for t in
                    ('orders','batches','inventory_transactions','outgoing_invoice_drafts','outgoing_invoice_lines',
                     'invoice_inventory_ledger','receivable_ledger_lines','payable_ledger_lines')}

    def test_empty_prepare_is_explained_without_creating_or_sending_anything(self):
        with server.db() as c:c.execute("UPDATE inventory_transactions SET qty_in=0 WHERE source_type='OPENING'")
        before=self.saved();body=self.body()
        r=self.client.post('/api/outgoing-invoices/prepare',json=body)
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['outcome'],'no_eligible_quantity')
        self.assertEqual(r.json['items'],[]);self.assertFalse(r.json['remote_write'])
        d=r.json['diagnostic'];self.assertEqual(d['unissued_rows'],2)
        self.assertEqual([(g['code'],g['count']) for g in d['groups']],[('stock_shortage',2)])
        self.assertEqual(d['scope'],self.period)
        self.assertEqual(self.saved(),before)
        exported=self.client.post('/api/export/order-invoices',json=body)
        self.assertEqual(exported.status_code,409)
        self.assertEqual(exported.json['code'],'no_invoiceable_orders')
        self.assertEqual(exported.json['diagnostic'],d)
        downloaded=self.client.get(d['download_url']);self.assertEqual(downloaded.status_code,200)
        self.assertEqual(self.saved(),before)

    def test_rounding_and_unit_mismatches_are_not_all_called_stock_shortages(self):
        with server.db() as c:
            c.execute('UPDATE orders SET actual_delivered=.02 WHERE id=?',(self.ids[0],))
            c.execute('UPDATE orders SET actual_delivered=.03 WHERE id=?',(self.ids[1],))
        r=self.client.post('/api/outgoing-invoices/prepare',json=self.body())
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual([(g['code'],g['count']) for g in r.json['diagnostic']['groups']],[('rounding',2)])
        with server.db() as c:c.execute("UPDATE orders SET unit='Gói' WHERE id IN (?,?)",self.ids[:2])
        before=self.saved()
        r=self.client.post('/api/outgoing-invoices/prepare',json=self.body())
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual([(g['code'],g['count']) for g in r.json['diagnostic']['groups']],[('unit_review',2)])
        self.assertEqual(self.saved(),before)

    def test_other_contractor_reservations_are_explained_and_preserved(self):
        with server.db() as c:c.execute('UPDATE orders SET actual_delivered=100 WHERE id=?',(self.ids[2],))
        other={**self.period,'contractor':'NT-B'}
        r=self.client.post('/api/outgoing-invoices/prepare',json=self.body(other))
        self.assertEqual(r.status_code,200,r.json);self.assertTrue(r.json['items'])
        before=self.saved()
        r=self.client.post('/api/outgoing-invoices/prepare',json=self.body())
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['diagnostic']['rows'][0]['stock_reserved_qty'],100)
        self.assertEqual(self.saved(),before)

    def test_diagnostic_is_read_only_and_respects_removed_rows_and_dates(self):
        with server.db() as c:
            c.execute("INSERT INTO outgoing_order_choices VALUES(?,0,'test','now')",(self.ids[0],))
            c.execute('PRAGMA query_only=ON')
            before=c.total_changes
            d=empty_export_diagnostic(c,self.period)
            self.assertEqual(c.total_changes,before)
        self.assertEqual(d['unissued_rows'],1);self.assertEqual(d['excluded_rows'],1)
        self.assertTrue(all(r['contractor']=='NT-A' and r['first_date']=='2026-09-05' for r in d['rows']))

    def test_source_review_only_shows_selected_party_and_starts_collapsed(self):
        script=r'''
const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('tdp_system/static/app.js','utf8');
const part=source.slice(source.indexOf('  function sourceScopeReviewHtml()'),source.indexOf('  function conversionIssue('));
const render=new Function('state','pendingScope','esc',part+'return sourceScopeReviewHtml();');
const rows=['ATV','TOYOTA','EXCLUDED',''].map((c,i)=>({contractor:c,number:'INVOICE-'+i,buyer:c||'OUTSIDE',scope:c?'orders':'outside',stock_status:'posted',id:i}));
const state={outgoingSourceReview:rows,invoiceContractorChoices:{items:[{code:'ATV',enabled:true},{code:'TOYOTA',enabled:true},{code:'EXCLUDED',enabled:false}]},data:{master:{contractors:[]}}};
let html=render(state,()=>({contractor:'ATV'}),String);
assert(html.includes('INVOICE-0'));assert(!html.includes('INVOICE-1'));assert(!html.includes('INVOICE-2'));assert(!html.includes('INVOICE-3'));assert(!html.includes('<details open'));
html=render(state,()=>({contractor:''}),String);assert(html.includes('INVOICE-1'));assert(!html.includes('INVOICE-2'));assert(!html.includes('INVOICE-3'));
console.log(JSON.stringify({ok:true}));'''
        result=subprocess.check_output(['node','-e',script],cwd=Path(__file__).resolve().parent.parent,text=True,encoding='utf-8')
        self.assertTrue(json.loads(result)['ok'])


if __name__=='__main__':unittest.main()
