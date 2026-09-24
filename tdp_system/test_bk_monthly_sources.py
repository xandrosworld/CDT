import io
import unittest
from . import server,bk_draft,bk_supplement
from .test_order_approval_without_bk import OrderApprovalWithoutBKTests as Fixture


class MonthlySourcesTests(unittest.TestCase):
    setUpClass=classmethod(Fixture.setUpClass.__func__)
    tearDownClass=classmethod(Fixture.tearDownClass.__func__)
    add_line=Fixture.add_line

    def setUp(self):
        Fixture.setUp(self)
        with server.db() as c:
            c.execute("UPDATE people SET issue_date='01/01/2020',issue_place='Test place'")
            c.execute("UPDATE batches SET status='approved'")
            c.execute("UPDATE products SET tax='KKKNT'")
            c.execute("INSERT INTO inventory_transactions(txn_date,product_code,qty_in,qty_out,unit_cost,source_type,source_id,created_at,updated_at) VALUES('2026-09-01','BK-P1',0,5,100,'OPENING','2026-09','now','now')")
            self.batch=c.execute("INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-09-04','second.xlsx','approved','now')").lastrowid
            oid=self.add_line(c,qty=3)
            c.execute("UPDATE orders SET work_date='2026-09-04' WHERE id=?",(oid,))

    def body(self,reference='MONTH-1'):
        with server.db() as c:
            sources=bk_draft.shortage_rows(c,'2026-09-01','2026-09-30')['items'][0]['purchase_sources']
        return {'from':'2026-09-01','to':'2026-09-30','reference':reference,'rows':[
            {'document_date':r['document_date'],'product_code':'BK-P1','qty':r['purchase_qty'],'unit_cost':111,'source_party':'Người bán BK','note':'[TDP-SOURCE:'+r['source_key']+']'}
            for r in sources]}

    def test_sources_preserve_purchase_dates_identity_and_readonly(self):
        with server.db() as c:
            before=c.serialize()
            data=bk_draft.shortage_rows(c,'2026-09-01','2026-09-30')
            self.assertEqual(before,c.serialize())
        item=data['items'][0]
        self.assertEqual(item['suggested_qty'],5)
        self.assertEqual([s['document_date'] for s in item['purchase_sources']],['2026-09-03','2026-09-04'])
        self.assertTrue(all(s['source_party']=='Người bán BK' and s['cccd']=='123456789' and s['address'] for s in item['purchase_sources']))

    def test_seller_catalog_and_print_use_selected_person_identity(self):
        with server.db() as c:
            c.execute("INSERT INTO people(name,cccd,address,issue_date,issue_place) VALUES('Người bán khác','987654321','Địa chỉ mới','02/02/2020','Nơi cấp mới')")
        response=self.client.get('/api/bk-import/draft/sellers')
        self.assertEqual(response.status_code,200)
        person=next(p for p in response.json['items'] if p['name']=='Người bán khác')
        self.assertEqual(person['cccd'],'987654321')
        self.assertEqual(person['address'],'Địa chỉ mới')
        with server.db() as c:
            before=c.serialize()
            rows=bk_supplement.receipt_rows(c,{'rows':[{'sourceParty':'Người bán khác','documentDate':'2026-09-03','productName':'Hàng BK','unit':'kg','qty':1,'unitCost':111,'amount':111,'sourceLine':1,'sourceReference':'TEST'}]})
            self.assertEqual(rows[0]['cccd'],'987654321')
            self.assertEqual(rows[0]['address'],'Địa chỉ mới')
            self.assertEqual(before,c.serialize())

    def test_multiday_excel_roundtrip_post_repeated_and_deficit_recheck(self):
        body=self.body()
        response=self.client.post('/api/bk-import/draft/excel',json=body)
        self.assertEqual(response.status_code,200)
        imported=self.client.post('/api/bk-import/draft/file',data={'file':(io.BytesIO(response.data),'month.xlsx')})
        self.assertEqual(imported.status_code,200,imported.json)
        self.assertEqual([r['document_date'] for r in imported.json['rows']],['2026-09-03','2026-09-04'])
        with server.db() as c:
            p=bk_supplement.prepare(c,response.data,body['from'],body['to'])
            saved=bk_supplement.post(c,p,'Reviewer',server.now_iso(),server.audit_event)
            self.assertEqual(saved['newInventoryLines'],2)
            self.assertTrue(bk_supplement.post(c,p,'Reviewer',server.now_iso(),server.audit_event)['idempotent'])
        again=self.client.post('/api/bk-import/draft/excel',json={**body,'reference':'MONTH-2'})
        with server.db() as c:
            with self.assertRaisesRegex(ValueError,'Nguồn mua đã bổ sung|vượt lượng còn thiếu'):
                bk_supplement.prepare(c,again.data,body['from'],body['to'])
            self.assertEqual(bk_draft.shortage_rows(c,body['from'],body['to'])['items'],[])

    def test_over_limit_reports_seller_and_day_before_printing(self):
        body=self.body();body['rows'][0]['unit_cost']=3000000
        response=self.client.post('/api/bk-import/draft/excel',json=body)
        with server.db() as c:
            with self.assertRaisesRegex(ValueError,'Người bán BK, ngày 2026-09-03'):
                bk_supplement.prepare(c,response.data,body['from'],body['to'])

    def test_partial_source_is_reduced_and_cannot_be_reused_under_new_reference(self):
        body=self.body();body['rows']=body['rows'][:1];body['rows'][0]['qty']=1
        response=self.client.post('/api/bk-import/draft/excel',json=body)
        with server.db() as c:
            p=bk_supplement.prepare(c,response.data,body['from'],body['to'])
            bk_supplement.post(c,p,'Reviewer',server.now_iso(),server.audit_event)
            remaining=bk_draft.shortage_rows(c,body['from'],body['to'])['items'][0]
            self.assertEqual(remaining['suggested_qty'],4)
            self.assertEqual([r['purchase_qty'] for r in remaining['purchase_sources']],[1,3])
        body['reference']='DIFFERENT';body['rows'][0]['qty']=2
        response=self.client.post('/api/bk-import/draft/excel',json=body)
        with server.db() as c:
            with self.assertRaisesRegex(ValueError,'Nguồn mua đã bổ sung'):
                bk_supplement.prepare(c,response.data,body['from'],body['to'])

    def test_historical_posted_seller_is_visible_without_suggesting_duplicate_input(self):
        from . import batch_bk_approval
        with server.db() as c:
            p=batch_bk_approval.prepare(c,self.batch)
            batch_bk_approval.approve(c,self.batch,{'source_hash':p['sourceHash'],'confirm_bk':True},server.now_iso(),server.audit_event)
            item=bk_draft.shortage_rows(c,'2026-09-01','2026-09-30')['items'][0]
            history=[r for r in item['purchase_sources'] if r['already_posted']]
            self.assertEqual(len(history),1)
            self.assertEqual(history[0]['source_party'],'Người bán BK')
            self.assertEqual(history[0]['purchase_qty'],0)
            self.assertEqual(history[0]['posted_qty'],3)
