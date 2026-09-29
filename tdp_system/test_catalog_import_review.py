import io
import unittest
import uuid

from openpyxl import Workbook
from . import server, contract_modules
from . import test_outgoing_readiness as support
from .invoice_identity_policy import CONFIRMED_DELIVERED_NAMES


class CatalogImportReviewTests(unittest.TestCase):
    setUpClass = classmethod(support.OutgoingReadinessTests.setUpClass.__func__)
    tearDownClass = classmethod(support.OutgoingReadinessTests.tearDownClass.__func__)

    def setUp(self):
        support.OutgoingReadinessTests.setUp(self)
        with contract_modules.CATALOG_IMPORT_LOCK:
            contract_modules.PENDING_CATALOG_IMPORTS.clear()
        self.units = ['Lễ', 'Cốc', 'Bộ', 'Đĩa']
        with server.db() as conn:
            for (code, name), unit in zip(CONFIRMED_DELIVERED_NAMES.items(), self.units):
                conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax) VALUES(?,?,?,'0.08')", (code, name, unit))
                conn.execute("INSERT OR REPLACE INTO outgoing_product_names VALUES(?,?, '2026-09-29')", (code, name))

    def preview(self, mode='full'):
        w = Workbook(); s = w.active; s.title = 'danh mục hh'
        s.append(['Mã hàng', 'Tên Thành Đạt Phát', 'Tên xuất hóa đơn', 'ĐVT Thành Đạt Phát', 'ĐVT Xuất HĐ', 'Thuế'])
        for code, name in CONFIRMED_DELIVERED_NAMES.items():
            s.append([code, name, 'Rau muống', 'Kg', 'Kg', '8%'])
        data = io.BytesIO(); w.save(data); w.close(); data.seek(0)
        r = self.client.post('/api/catalog/import/preview', data={'mode':mode, 'file':(data,'catalog.xlsx')})
        self.assertEqual(r.status_code, 200, r.json)
        return r.json

    def edits(self):
        return [{'source_row':i+2, 'values':{'invoice_name':name, 'invoice_unit':unit}}
                for i, ((code, name), unit) in enumerate(zip(CONFIRMED_DELIVERED_NAMES.items(), self.units))]

    def review(self, preview, edits=None, mode='names_and_new'):
        return self.client.post('/api/catalog/import/review', json={'token':preview['token'], 'mode':mode,
                                'edits':self.edits() if edits is None else edits})

    def test_repair_in_preview_preserves_internal_values_and_requires_confirmation(self):
        p = self.preview()
        self.assertFalse(p['can_confirm']); self.assertEqual(p['counts']['error'],4)
        with server.db() as conn: before = conn.serialize()
        result = self.review(p); self.assertEqual(result.status_code,200,result.json)
        fixed = result.json; self.assertTrue(fixed['can_confirm'],fixed)
        self.assertEqual(p['source_hash'], fixed['source_hash'])
        self.assertEqual(fixed['mode'],'names_and_new')
        self.assertEqual([r['unit'] for r in fixed['rows']], self.units)
        with server.db() as conn: self.assertEqual(before, conn.serialize())
        self.assertEqual(self.client.post('/api/catalog/import/confirm',json={'token':fixed['token']}).status_code,400)
        saved = self.client.post('/api/catalog/import/confirm',json={'token':fixed['token'],'confirmed':True})
        self.assertEqual(saved.status_code,200,saved.json)
        retry = self.client.post('/api/catalog/import/confirm',json={'token':fixed['token'],'confirmed':True})
        self.assertEqual(saved.json, retry.json)
        with server.db() as conn:
            for (code,name),unit in zip(CONFIRMED_DELIVERED_NAMES.items(),self.units):
                self.assertEqual(tuple(conn.execute('SELECT name,unit,tax FROM products WHERE code=?',(code,)).fetchone()),(name,unit,'0.08'))
                self.assertEqual(conn.execute('SELECT invoice_name FROM outgoing_product_names WHERE product_code=?',(code,)).fetchone()[0],name)
            self.assertIsNotNone(conn.execute("SELECT code FROM products WHERE code='HH-01'").fetchone())

    def test_retry_returns_same_review_and_old_preview_cannot_be_confirmed(self):
        p=self.preview(); first=self.review(p); retry=self.review(p)
        self.assertEqual(first.json,retry.json)
        self.assertEqual(self.client.post('/api/catalog/import/confirm',json={'token':p['token'],'confirmed':True}).status_code,409)

    def test_invalid_edit_keeps_original_file_and_preview(self):
        p=self.preview()
        for values in [{'unit':'=1+1'},{'product_code':'OTHER'},{'invoice_unit':'x'*51}]:
            self.assertEqual(self.review(p,[{'source_row':2,'values':values}]).status_code,400)
        self.assertTrue(self.review(p).json['can_confirm'])

    def test_new_only_can_switch_scope_without_uploading_file_again(self):
        p=self.preview('new_only'); self.assertEqual(p['counts']['new_products'],0)
        checked=self.review(p,edits=[],mode='names_and_new')
        self.assertEqual(checked.status_code,200); self.assertEqual(checked.json['counts']['error'],4)
        self.assertTrue(self.review(checked.json).json['can_confirm'])

    def test_worksheet_and_single_name_endpoint_reject_false_identity(self):
        rows=self.client.get('/api/catalog/worksheet').json['items']
        for code in CONFIRMED_DELIVERED_NAMES:
            row=next(r for r in rows if r['code']==code)
            response=self.client.put('/api/catalog/worksheet',json={'request_id':str(uuid.uuid4()),'items':[
                {'id':code,'revision':row['worksheet_revision'],'values':{'invoice_name':'Rau muống'}}]})
            self.assertEqual(response.status_code,400,response.json)
            response=self.client.put('/api/outgoing-product-names/'+code,json={'invoice_name':'Rau muống'})
            self.assertEqual(response.status_code,400,response.json)

    def test_existing_catalog_change_invalidates_confirmation(self):
        p=self.review(self.preview()).json
        with server.db() as conn: conn.execute("UPDATE products SET name='Changed' WHERE code='HH-01'")
        response=self.client.post('/api/catalog/import/confirm',json={'token':p['token'],'confirmed':True})
        self.assertEqual(response.status_code,409,response.json)
        # Recheck the retained upload against the new catalogue, without a file upload.
        retry=self.review(p,edits=[])
        self.assertEqual(retry.status_code,200,retry.json)
        self.assertTrue(retry.json['can_confirm'])

    def test_legacy_invalid_alias_blocks_output_without_rewriting_it(self):
        from .outgoing_line_policy import unit_issues
        from .outgoing_names import invoice_name
        with server.db() as conn:
            conn.execute("UPDATE outgoing_product_names SET invoice_name='Rau muống' WHERE product_code='N000006'")
            before=conn.serialize()
            issues=unit_issues(conn,[{'id':1,'product_code':'N000006','unit':'Lễ'}])
            self.assertIn('Cau, trầu',issues[1]['message'])
            with self.assertRaises(ValueError):invoice_name(conn,'N000006','Cau, trầu')
            self.assertEqual(before,conn.serialize())

    def test_separate_invoice_name_upload_cannot_bypass_identity_check(self):
        w=Workbook();s=w.active;s.title='Tên hóa đơn'
        s.append(['Mã hàng','Tên xuất hóa đơn']);s.append(['N000006','Rau muống'])
        data=io.BytesIO();w.save(data);w.close();data.seek(0)
        r=self.client.post('/api/mappings/import/preview',data={'mapping_type':'invoice_names','file':(data,'names.xlsx')})
        self.assertEqual(r.status_code,200,r.json)
        self.assertFalse(r.json['can_confirm'])
        self.assertIn('Cau, trầu',r.json['rows'][0]['errors'][0])

    def test_stale_draft_label_is_blocked_even_after_catalog_label_is_correct(self):
        from .outgoing_waiting import refresh_waiting
        from .outgoing_readiness import validate_draft_export_stock, OutgoingReadinessError
        with server.db() as conn:
            support.OutgoingReadinessTests.add_opening(conn,20)
            support.OutgoingReadinessTests.add_batch(conn,'2026-09-01',[{'qty':7}])
            refresh_waiting(conn,'2026-09-29')
            did=conn.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]
            conn.execute("UPDATE outgoing_invoice_lines SET product_code='N000006',product_name='Rau muống' WHERE draft_id=?",(did,))
            before=conn.serialize()
            with self.assertRaises(OutgoingReadinessError) as error:validate_draft_export_stock(conn,did)
            self.assertIn('Cau, trầu',str(error.exception))
            self.assertEqual(before,conn.serialize())


if __name__ == '__main__': unittest.main()
