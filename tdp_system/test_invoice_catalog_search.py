"""Search outside ambiguous invoice suggestions without changing automatic mapping."""
import sqlite3
import subprocess
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from .test_invoice_workbench_listing import seed_round1
from .test_invoice_input_sync import init_test_database
from .invoice_workbench_listing import invoice_range_payload


class InvoiceCatalogSearchTests(unittest.TestCase):
    def node(self, script):
        subprocess.run(['node', '-e', script], check=True,
                       cwd=Path(__file__).resolve().parent.parent)

    def test_ambiguous_rows_use_catalog_search_but_unsafe_rows_remain_locked(self):
        self.node(r"""
        const assert=require('node:assert/strict');global.window={};
        require('./tdp_system/static/invoice-workbench.js');
        const fmt={esc:x=>String(x??''),num:String,money:String,dateVN:String};
        const line={id:7,invoice_id:1,line_index:1,inventory_eligible:1,mapping_status:'unmapped',
          candidate_products:[{code:'A',name:'Cha lua'},{code:'B',name:'Cha lua'}],suggested_product_code:'A'};
        for(const direction of ['input','output']) {
          const invoice={id:1,sync_status:'synced',source_status_class:'issued'};
          const state={invoiceDirection:direction,invoiceListing:{items:[invoice],lines:[line]}};
          let html=window.TdpInvoiceWorkbench(state,fmt);
          assert.match(html, /<input[^>]+class="[^"]*invoice-mapping-input/);
          assert.match(html, /id="map_(input|output)_7" value=""/);
          assert.ok(!html.includes('<select class="input-date invoice-mapping-input"'));
          for(const fields of [{sync_status:'review_required'}, {receipt_status:'posted'},
                               {stock_status:'posted'}, {stock_status:'reversal_required'},
                               ...(direction==='output'?[{source_status_class:'draft'}]:[])]) {
            state.invoiceListing.items=[{...invoice,...fields}];
            html=window.TdpInvoiceWorkbench(state,fmt);
            assert.ok(!html.includes('id="map_'+direction+'_7"'));
          }
        }
        """)

    def test_search_finds_third_catalog_code_without_auto_selecting_it(self):
        from . import server
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        init_test_database(conn)
        ids = seed_round1(conn)
        conn.executemany('INSERT INTO products(code,name,unit) VALUES(?,?,?)', [
            ('F000005', 'Chả lụa heo loại 1', 'kg'),
            ('F000006', 'Chả lụa heo TH', 'kg'),
            ('F000009', 'Chả lụa heo', 'kg')])
        conn.executemany("INSERT INTO outgoing_product_names(product_code,invoice_name,updated_at) VALUES(?,?,'2026-09-06 00:00:00')",
                         [('F000005', 'Chả lụa'), ('F000006', 'Chả lụa')])
        conn.execute('UPDATE msmi_invoice_items SET source_item_name=? WHERE id=?', ('Chả lụa', ids['line_b']))
        before = conn.total_changes
        payload = invoice_range_payload(conn, tenant='TDP', invoice_type='input',
                                        date_from='2026-08-01', date_to='2026-08-31')
        line = next(x for x in payload['lines'] if x['id'] == ids['line_b'])
        self.assertEqual({'F000005','F000006'}, {x['code'] for x in line['candidate_products']})
        self.assertFalse(line['product_code'])
        @contextmanager
        def db():
            yield conn
        with patch.object(server, 'db', db):
            for term in ['Chả lụa', 'cha lua', 'F000009']:
                result = server.app.test_client().get('/api/products/search', query_string={'q':term})
                self.assertEqual(200, result.status_code)
                self.assertIn('F000009', [x['code'] for x in result.json['items']])
        self.assertEqual(before, conn.total_changes)

    def test_late_search_cannot_replace_new_query_or_another_row(self):
        self.node(r"""
        const assert=require('node:assert/strict'), fs=require('node:fs');
        const source=fs.readFileSync('tdp_system/static/app.js','utf8');
        const functionSource=source.slice(source.indexOf('  async function loadMsmiProductOptions('),
                                         source.indexOf('  function mealPaymentDocumentTypeText('));
        let msmiProductSearchVersion=0, list={innerHTML:''}, pending=[], errors=[];
        const document={activeElement:null,getElementById:()=>list};
        const api=()=>new Promise((resolve,reject)=>pending.push({resolve,reject}));
        const esc=String,showToast=e=>errors.push(e);
        const showMsmiProductOptions=()=>{};
        eval(functionSource);
        const input={value:'old',dataset:{},isConnected:true};document.activeElement=input;
        (async()=>{
          const old=loadMsmiProductOptions(input);input.value='new';
          const latest=loadMsmiProductOptions(input);
          pending[1].resolve({items:[{code:'NEW',name:'New'}]});await latest;
          pending[0].resolve({items:[{code:'OLD',name:'Old'}]});await old;
          assert.ok(list.innerHTML.includes('NEW'));assert.ok(!list.innerHTML.includes('OLD'));
          input.value='before-edit';const editing=loadMsmiProductOptions(input);
          input.value='after-edit';pending[2].resolve({items:[{code:'STALE'}]});await editing;
          assert.equal(list.innerHTML,'');
          const moving=loadMsmiProductOptions(input);
          const other={value:'other',dataset:{},isConnected:true};document.activeElement=other;
          const next=loadMsmiProductOptions(other);
          pending[4].resolve({items:[{code:'OTHER',name:'Other'}]});await next;
          pending[3].reject(Error('Old row failed'));await moving;
          assert.ok(list.innerHTML.includes('OTHER'));assert.equal(errors.length,0);
          other.value='reload';const reload=loadMsmiProductOptions(other);list={innerHTML:''};
          pending[5].resolve({items:[{code:'DETACHED'}]});await reload;assert.equal(list.innerHTML,'');
          other.value='x';await loadMsmiProductOptions(other);assert.equal(pending.length,6);
        })().catch(e=>{console.error(e);process.exitCode=1;});
        """)


if __name__ == '__main__':
    unittest.main()
