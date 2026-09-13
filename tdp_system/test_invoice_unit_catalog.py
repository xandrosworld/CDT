import io,unittest,uuid
from openpyxl import Workbook
from . import server
from . import test_outgoing_readiness as support
from .outgoing_waiting import refresh_waiting
from .outgoing_readiness import validate_draft_export_stock,OutgoingReadinessError

class InvoiceUnitCatalogTests(unittest.TestCase):
    setUpClass=classmethod(support.OutgoingReadinessTests.setUpClass.__func__)
    tearDownClass=classmethod(support.OutgoingReadinessTests.tearDownClass.__func__)
    def setUp(self):
        support.OutgoingReadinessTests.setUp(self)
        with server.db() as conn:conn.execute('DELETE FROM outgoing_product_units')

    def row(self):
        return next(r for r in self.client.get('/api/catalog/worksheet').json['items'] if r['code']=='HH-01')

    def save(self,row,unit):
        return self.client.put('/api/catalog/worksheet',json={'request_id':str(uuid.uuid4()),'items':[{'id':row['id'],'revision':row['worksheet_revision'],'values':{'invoice_unit':unit}}]})

    def seed(self):
        with server.db() as conn:
            support.OutgoingReadinessTests.add_opening(conn,20)
            support.OutgoingReadinessTests.add_batch(conn,'2026-09-01',[{'qty':7}])
            refresh_waiting(conn,'2026-09-13')
            return conn.execute("SELECT id FROM outgoing_invoice_drafts WHERE status='draft'").fetchone()[0]

    def test_edit_invoice_unit_keeps_stock_and_draft_amounts_and_blocks_export(self):
        did=self.seed()
        with server.db() as conn:
            before={t:[tuple(r) for r in conn.execute('SELECT * FROM '+t)] for t in ['orders','inventory_transactions','outgoing_invoice_lines']}
        r=self.save(self.row(),'Gói');self.assertEqual(200,r.status_code,r.json)
        self.assertEqual('Gói',self.row()['invoice_unit']);self.assertEqual('kg',self.row()['unit'])
        with server.db() as conn:
            for t,rows in before.items():self.assertEqual(rows,[tuple(r) for r in conn.execute('SELECT * FROM '+t)])
            with self.assertRaises(OutgoingReadinessError) as error:validate_draft_export_stock(conn,did)
            self.assertIn('ĐVT hóa đơn',str(error.exception))
        payload=self.client.get('/api/outgoing-invoices/unissued?to=2026-09-13').json
        self.assertEqual(0,sum(r['ready_qty'] for r in payload['details']))
        self.assertTrue(all('quy đổi' in r['pending_reason'] for r in payload['details']))

    def test_clear_override_and_same_unit_restore_eligibility_without_relabel(self):
        did=self.seed()
        for unit in ['KG','']:
            self.assertEqual(200,self.save(self.row(),unit).status_code)
            with server.db() as conn:validate_draft_export_stock(conn,did)
            payload=self.client.get('/api/outgoing-invoices/unissued?to=2026-09-13').json
            self.assertEqual(7,sum(r['ready_qty'] for r in payload['details']))

    def test_stale_revision_and_invalid_unit_cannot_overwrite(self):
        old=self.row();self.assertEqual(200,self.save(old,'Gói').status_code)
        self.assertEqual(409,self.save(old,'Kg').status_code)
        self.assertEqual(400,self.save(self.row(),'x'*51).status_code)
        self.assertEqual('Gói',self.row()['invoice_unit'])

    def test_bundle_unit_is_not_silently_changed_to_set_unit(self):
        from .contract_modules import catalog_unit
        self.assertEqual('Bó',catalog_unit('Bo\u0301'))
        self.assertEqual('Bộ',catalog_unit('Bộ'))
        self.assertEqual(200,self.save(self.row(),'Bó').status_code)
        self.assertEqual('Bó',self.row()['invoice_unit'])

    def test_zero_opening_allows_unused_catalog_correction_without_rewriting_history(self):
        from .invoice_repairs import correct_unused_product_unit
        with server.db() as conn:
            support.OutgoingReadinessTests.add_opening(conn,0)
            conn.execute("UPDATE inventory_transactions SET unit_cost=0 WHERE product_code='HH-01'")
            history=[tuple(r) for r in conn.execute('SELECT * FROM inventory_transactions')]
            product=conn.execute("SELECT * FROM products WHERE code='HH-01'").fetchone()
            correct_unused_product_unit(conn,code='HH-01',expected_name=product['name'],expected_unit=product['unit'],unit='Gói',now='2026-09-13')
            self.assertEqual(history,[tuple(r) for r in conn.execute('SELECT * FROM inventory_transactions')])

    def test_excel_import_persists_invoice_unit_while_preserving_stock_unit(self):
        self.seed()
        w=Workbook();s=w.active;s.title='danh mục hh'
        s.append(['Mã hàng','Tên Thành Đạt Phát','Tên xuất hóa đơn','ĐVT thành đạt phát','ĐVT Xuất HĐ','Thuế'])
        s.append(['HH-01','Tên nội bộ','Tên hóa đơn','kg','Gói','0%'])
        buf=io.BytesIO();w.save(buf);w.close();buf.seek(0)
        p=self.client.post('/api/catalog/import/preview',data={'mode':'names_and_new','file':(buf,'catalog.xlsx')},content_type='multipart/form-data').json
        self.assertTrue(p['can_confirm']);self.assertTrue(p['rows'][0]['warnings'])
        r=self.client.post('/api/catalog/import/confirm',json={'token':p['token'],'confirmed':True})
        self.assertEqual(200,r.status_code,r.json);self.assertEqual('Gói',self.row()['invoice_unit']);self.assertEqual('kg',self.row()['unit'])

if __name__=='__main__':unittest.main()
