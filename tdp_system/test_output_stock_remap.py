import io
import json
import unittest
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from openpyxl import Workbook, load_workbook

from . import server
from .test_outgoing_readiness import OutgoingReadinessTests as Seed
from .output_stock_remap import export_workbook as export_new_workbook, preview_workbook, confirm_preview, RemapError
from .invoice_monthly_valuation import monthly_average_report
from .invoice_inventory import reverse_output_invoice
from .inventory_period_close import inventory_period_close_preview, close_inventory_period
from .outgoing_readiness import canonical_available_stock


def export_workbook(conn, start, end):
    """Build the previously shipped file from its unchanged saved snapshot.

    The original regression cases intentionally keep testing old customer files,
    including their metadata without any layout/version marker.
    """
    from .output_stock_remap import HEADERS, _excel_value
    downloaded = load_workbook(io.BytesIO(export_new_workbook(conn,start,end)))
    token = downloaded['_meta']['B1'].value; downloaded.close()
    snapshot = json.loads(conn.execute('SELECT payload FROM output_stock_excel_sessions WHERE token=?',(token,)).fetchone()[0])
    wb = Workbook(); ws=wb.active; ws.title='Doi ma xuat kho'; ws.append(HEADERS)
    for r in snapshot['rows']:
        ws.append([_excel_value(v) for v in r['cells']] + [r['product_code'],r['name']])
    meta=wb.create_sheet('_meta');meta.append(['token',token]);meta.sheet_state='veryHidden'
    data=io.BytesIO();wb.save(data);wb.close();return data.getvalue()


class OutputStockRemapTests(unittest.TestCase):
    setUpClass = classmethod(Seed.setUpClass.__func__)
    tearDownClass = classmethod(Seed.tearDownClass.__func__)

    def setUp(self):
        with server.db() as conn:
            conn.execute('DELETE FROM output_stock_remap_parts')
            conn.execute('DELETE FROM output_stock_remaps')
            conn.execute('DELETE FROM output_stock_excel_sessions')
            conn.execute('DELETE FROM inventory_period_closures')
            conn.execute('DELETE FROM invoice_inventory_ledger')
            conn.execute('DELETE FROM invoice_mapping_revisions')
            conn.execute('DELETE FROM invoice_line_mappings')
            conn.execute('DELETE FROM bk_import_lines')
            conn.execute('DELETE FROM bk_import_documents')
        Seed.setUp(self)
        with server.db() as conn:
            conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax) VALUES('REMAP-B','Hàng nhận','kg','8%')")
            conn.execute("INSERT OR REPLACE INTO products(code,name,unit,tax) VALUES('REMAP-C','Hoa cúng','kg','KKKNT')")
            Seed.add_opening(conn, 0)
            Seed.add_opening(conn, 10, product_code='REMAP-B')
            Seed.add_opening(conn, -3, product_code='REMAP-C')
            conn.execute("UPDATE inventory_transactions SET unit_cost=30 WHERE product_code='REMAP-B'")
            conn.execute("UPDATE inventory_transactions SET source_id='2026-08'")
            self.source_id = Seed.add_posted_source(conn, source='minvoice', number='REMAP-1')
            conn.execute('UPDATE outgoing_source_invoices SET raw_json=?,subtotal=80,tax_amount=6,total_amount=86 WHERE id=?',
                         (json.dumps({'_tdp_source_contract':'minvoice_portal_v1','details':[{'taxAmount':6}]}),self.source_id))
            self.line_id = conn.execute("""INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,
                source_item_name,source_unit,qty,unit_price,amount,tax_rate,product_code,mapping_status,stock_qty)
                VALUES(?,1,'SOURCE-A','Tên trên hóa đơn','kg',4,20,80,'8','HH-01','mapped',4)""",(self.source_id,)).lastrowid
            conn.execute('UPDATE invoice_inventory_ledger SET source_line_id=? WHERE source_invoice_id=?',(self.line_id,self.source_id))
            self.file = export_workbook(conn, '2026-08-01', '2026-08-31')

    def edited(self, code='REMAP-B', name='Hàng nhận', mutate=None):
        wb = load_workbook(io.BytesIO(self.file)); ws=wb['Doi ma xuat kho']
        ws['Q2']=code; ws['R2']=name
        if mutate: mutate(ws)
        data=io.BytesIO(); wb.save(data); wb.close(); return data.getvalue()

    def new_file(self, conn, mutate=None):
        # Compatibility with the A-B layout already downloaded by customers.
        from .output_stock_remap import NEW_HEADERS,NEW_COLUMN_ORDER,_excel_value
        wb=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31')))
        token=wb['_meta']['B1'].value
        snapshot=json.loads(conn.execute('SELECT payload FROM output_stock_excel_sessions WHERE token=?',(token,)).fetchone()[0])
        del wb['Doi ma xuat kho'];ws=wb.create_sheet('Doi ma xuat kho',0)
        for _ in range(3):ws.append(['Old instructions'])
        ws.append(NEW_HEADERS)
        for r in snapshot['rows']:
            values=[_excel_value(v) for v in r['cells']]+[r['product_code'],r['name']]
            ws.append([values[i] for i in NEW_COLUMN_ORDER])
        ws['A5']='REMAP-B';ws['B5']='Hàng nhận'
        if mutate: mutate(ws)
        data=io.BytesIO();wb.save(data);wb.close();return data.getvalue()

    def test_restored_layout_puts_editable_identity_right_and_imports_correct_line(self):
        with server.db() as conn:
            wb=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31')))
            ws=wb['Doi ma xuat kho']
            self.assertEqual(('Mã nội bộ mới','Tên nội bộ mới'),(ws['Q4'].value,ws['R4'].value))
            self.assertIn('1 dòng xuất / 1 mã hàng',ws['L1'].value)
            self.assertEqual('Lượng cần xử lý luân chuyển',ws['P4'].value)
            self.assertEqual(('HH-01','Hàng hóa 01','kg',4,4,'HH-01','Hàng hóa 01'),tuple(ws.cell(5,c).value for c in range(12,19)))
            self.assertEqual(('SOURCE-A','Tên trên hóa đơn',4,20,80,'8',6),tuple(ws[c+'5'].value for c in ('D','E','G','H','I','J','K')))
            self.assertIn('có thể trống',ws['D4'].comment.text)
            self.assertEqual(('L5','A4:R5'),(ws.freeze_panes,ws.auto_filter.ref))
            self.assertIsNone(ws.sheet_view.pane.xSplit)
            self.assertTrue(ws.column_dimensions['A'].hidden)
            self.assertFalse(ws['Q5'].protection.locked)
            self.assertTrue(ws['D5'].protection.locked)
            ws['Q5']='REMAP-B';ws['R5']='Hàng nhận'
            data=io.BytesIO();wb.save(data)
            wb.close()
            before=dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone())
            preview=preview_workbook(conn,data.getvalue())
            self.assertTrue(preview['can_confirm'],preview)
            self.assertEqual((5,self.line_id), (preview['changes'][0]['excel_row'],preview['changes'][0]['line_id']))
            confirm_preview(conn,preview['token'],'New layout test',server.now_iso())
            self.assertEqual({**before,'product_code':'REMAP-B'},dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone()))
            self.assertEqual(6,canonical_available_stock(conn)['REMAP-B']['canonical_qty'])

    def test_deficit_column_is_positive_protected_and_old_restored_file_still_imports(self):
        with server.db() as conn:
            conn.execute("UPDATE inventory_transactions SET qty_in=3.7 WHERE source_type='OPENING' AND product_code='HH-01'")
            book=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31')))
            ws=book['Doi ma xuat kho']
            self.assertAlmostEqual(0.3,ws['P5'].value)
            ws['Q5']='REMAP-B';ws['R5']='Hàng nhận'
            data=io.BytesIO();book.save(data)
            preview=preview_workbook(conn,data.getvalue())
            self.assertTrue(preview['can_confirm'],preview)
            self.assertAlmostEqual(0.3,preview['changes'][0]['qty'])
            ws['P5']=4
            data=io.BytesIO();book.save(data)
            with self.assertRaisesRegex(RemapError,'đã sửa cột gốc'):
                preview_workbook(conn,data.getvalue())
            # The restored Q-R template previously shipped with negative closing stock.
            from .output_stock_remap import HEADERS,_excel_value
            snapshot=json.loads(conn.execute('SELECT payload FROM output_stock_excel_sessions WHERE token=?',(book['_meta']['B1'].value,)).fetchone()[0])
            ws['P4']=HEADERS[15];ws['P5']=_excel_value(snapshot['rows'][0]['cells'][15])
            data=io.BytesIO();book.save(data);book.close()
            old_preview=preview_workbook(conn,data.getvalue())
            self.assertTrue(old_preview['can_confirm'],old_preview)
            self.assertAlmostEqual(0.3,old_preview['changes'][0]['qty'])

    def test_negative_summary_groups_lines_and_exposes_both_taxes_without_double_counting(self):
        with server.db() as conn:
            second=Seed.add_posted_source(conn,source='minvoice',number='SUMMARY-2',qty=2)
            conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',
                         (json.dumps({'_tdp_source_contract':'minvoice_portal_v1','details':[{'vatAmount':3.2}]}),second))
            line=conn.execute("""INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,
                source_item_name,source_unit,qty,unit_price,amount,tax_rate,product_code,mapping_status,stock_qty)
                VALUES(?,1,'SOURCE-A','Tên trên hóa đơn','kg',2,20,40,'8','HH-01','mapped',2)""",(second,)).lastrowid
            conn.execute('UPDATE invoice_inventory_ledger SET source_line_id=? WHERE source_invoice_id=?',(line,second))
            conn.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
            before=conn.execute('SELECT tax FROM products WHERE code=?',('HH-01',)).fetchone()[0]
            book=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31')))
            summary=book['Tổng hợp hàng âm'];rows=list(summary.iter_rows(min_row=3,values_only=True))
            match=[r for r in rows if r[0]=='HH-01']
            self.assertEqual(1,len(match));self.assertEqual(('KKKNT','8%'),match[0][2:4])
            self.assertEqual((-6,2),match[0][5:7])
            self.assertIn('khác thuế HĐ',match[0][7])
            opening_only=next(r for r in rows if r[0]=='REMAP-C')
            self.assertEqual((-3,0),opening_only[5:7]);self.assertIn('Không có dòng xuất',opening_only[8])
            self.assertEqual(2,book['Doi ma xuat kho'].max_row-4)
            self.assertTrue(all(r[15]==0 for r in book['Doi ma xuat kho'].iter_rows(min_row=5,values_only=True)))
            self.assertEqual(before,conn.execute('SELECT tax FROM products WHERE code=?',('HH-01',)).fetchone()[0])
            book.close()

    def test_focused_export_excludes_kkknt_and_positive_stock_and_keeps_other_lines_safe(self):
        with server.db() as conn:
            for code in ('REMAP-B','REMAP-C'):
                invoice=Seed.add_posted_source(conn,source='minvoice',number='SCOPE-'+code,qty=1,product_code=code)
                conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',
                    (json.dumps({'_tdp_source_contract':'minvoice_portal_v1','details':[{'taxAmount':0}]}),invoice))
                line=conn.execute("""INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,
                    source_item_name,source_unit,qty,unit_price,amount,tax_rate,product_code,mapping_status,stock_qty)
                    VALUES(?,1,?,'Other source','kg',1,20,20,'0',?,'mapped',1)""",(invoice,code,code)).lastrowid
                conn.execute('UPDATE invoice_inventory_ledger SET source_line_id=? WHERE source_invoice_id=?',(line,invoice))
            book=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31',scope='blocking')))
            ws=book['Doi ma xuat kho']
            self.assertEqual(5,ws.max_row);self.assertEqual('HH-01',ws['L5'].value)
            self.assertIn('1 dòng cần xử lý / 1 mã hàng',ws['L1'].value)
            ws['Q5']='REMAP-B';ws['R5']='Hàng nhận'
            data=io.BytesIO();book.save(data);book.close()
            preview=preview_workbook(conn,data.getvalue())
            self.assertTrue(preview['can_confirm'],preview)
            conn.execute("UPDATE products SET name='Changed outside exported rows' WHERE code='REMAP-C'")
            with self.assertRaises(RemapError): confirm_preview(conn,preview['token'],'Stale focused test',server.now_iso())
            conn.execute("UPDATE products SET name='Hoa cúng' WHERE code='REMAP-C'")
            confirm_preview(conn,preview['token'],'Focused test',server.now_iso())
            stocks=canonical_available_stock(conn)
            self.assertEqual((0,5,-4),tuple(stocks[c]['canonical_qty'] for c in ('HH-01','REMAP-B','REMAP-C')))
            self.assertEqual(1,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])
            # All stock blockers are resolved: no KKKNT rows leak into the next file.
            empty=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31',scope='blocking')))
            self.assertEqual(4,empty.active.max_row);self.assertIn('0 dòng cần xử lý',empty.active['L1'].value)
            empty.close()
            # Source changes outside the exported subset still invalidate preview.
            with self.assertRaises(RemapError):preview_workbook(conn,data.getvalue())

    def test_focused_file_rejects_deleted_or_added_rows_and_names_error_product(self):
        with server.db() as conn:
            for mutation in ('delete','duplicate','name'):
                book=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31',scope='blocking')))
                ws=book.active
                if mutation=='delete':ws.delete_rows(5)
                elif mutation=='duplicate':ws.append([c.value for c in ws[5]])
                else:ws['Q5']='REMAP-B';ws['R5']='Wrong name'
                data=io.BytesIO();book.save(data);book.close()
                if mutation=='name':
                    result=preview_workbook(conn,data.getvalue());self.assertFalse(result['can_confirm'])
                    for expected in ('Hàng số 5','HH-01','Hàng hóa 01','Tên đúng của mã REMAP-B: Hàng nhận'):
                        self.assertIn(expected,result['errors'][0])
                else:
                    with self.assertRaises(RemapError):preview_workbook(conn,data.getvalue())

    def test_api_export_defaults_to_non_kkknt_blockers_with_all_scope_available(self):
        with server.db() as conn:
            conn.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
        for query,expected_rows in (('',4),('&scope=all',5)):
            response=self.client.get('/api/inventory/output-remap/export?from=2026-08-01&to=2026-08-31'+query)
            self.assertEqual(200,response.status_code)
            book=load_workbook(io.BytesIO(response.data));self.assertEqual(expected_rows,book.active.max_row);book.close()

    def test_new_layout_rejects_source_identity_edits_and_keeps_missing_source_code_blank(self):
        with server.db() as conn:
            conn.execute("UPDATE outgoing_source_invoice_items SET source_item_code='' WHERE id=?",(self.line_id,))
            data=self.new_file(conn)
            wb=load_workbook(io.BytesIO(data));ws=wb['Doi ma xuat kho']
            self.assertIsNone(ws['J5'].value);self.assertEqual('HH-01',ws['C5'].value);wb.close()
            self.assertTrue(preview_workbook(conn,data)['can_confirm'])
            for column in 'CDEFGHIJKLMNOPQR':
                with self.subTest(column=column),self.assertRaises(RemapError):
                    preview_workbook(conn,self.new_file(conn,lambda ws:ws.__setitem__(column+'5','Changed')))
            with self.assertRaises(RemapError):
                preview_workbook(conn,self.new_file(conn,lambda ws:ws.__setitem__('A5','=1+1')))
            with self.assertRaises(RemapError):
                preview_workbook(conn,self.new_file(conn,lambda ws:ws.delete_rows(5)))
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])

    def test_round_trip_preserves_source_and_ledger_and_closes_with_negative_kkknt(self):
        with server.db() as conn:
            invoice = dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(self.source_id,)).fetchone())
            line = dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone())
            ledger = [dict(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger')]
            preview = preview_workbook(conn, self.edited())
            self.assertTrue(preview['can_confirm'],preview)
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])
            self.assertEqual(6,preview['changes'][0]['new_closing_after'])
            result = confirm_preview(conn,preview['token'],'Người kiểm thử',server.now_iso())
            self.assertEqual(1,result['changed_lines'])
            self.assertTrue(confirm_preview(conn,preview['token'],'Người kiểm thử',server.now_iso())['idempotent'])
            self.assertEqual(invoice,dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(self.source_id,)).fetchone()))
            after=dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone())
            self.assertEqual({**line,'product_code':'REMAP-B'},after)
            self.assertEqual(ledger,[dict(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger')])
            stock=canonical_available_stock(conn)
            self.assertEqual((0,6,-3),tuple(stock[c]['canonical_qty'] for c in ['HH-01','REMAP-B','REMAP-C']))
            close=inventory_period_close_preview(conn,'2026-08',today=date(2026,9,10))
            self.assertTrue(close['can_close'],close['issues'])
            self.assertEqual(1,close['kkknt_negative_count'])
            close_inventory_period(conn,'2026-08',expected_source_hash=close['source_hash'],expected_target_hash=close['target_hash'],timestamp=server.now_iso(),today=date(2026,9,10))
            report=monthly_average_report(conn,date_from='2026-09-01',date_to='2026-09-30',include_zero=True)
            flower=next(r for r in report['items'] if r['product_code']=='REMAP-C')
            self.assertEqual((-3,-30), (flower['opening_qty'],flower['opening_value']))

    def test_only_new_identity_columns_are_editable(self):
        for column in ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P']:
            with self.subTest(column=column),server.db() as conn:
                with self.assertRaises(RemapError): preview_workbook(conn,self.edited(mutate=lambda ws: ws.__setitem__(column+'2','Changed')))
                self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])

    def test_excel_numeric_round_trip_keeps_source_precision(self):
        with server.db() as conn:
            price = 20.123456789012345
            conn.execute('UPDATE outgoing_source_invoice_items SET unit_price=? WHERE id=?', (price,self.line_id))
            self.file = export_workbook(conn,'2026-08-01','2026-08-31')
            def excel_save(ws):
                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        if isinstance(cell.value,(int,float)) and not isinstance(cell.value,bool):
                            cell.value = float(format(cell.value,'.15g'))
            preview = preview_workbook(conn,self.edited(mutate=excel_save))
            self.assertTrue(preview['can_confirm'],preview)
            confirm_preview(conn,preview['token'],'Excel save test',server.now_iso())
            self.assertEqual(price,conn.execute('SELECT unit_price FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone()[0])
            self.file = export_workbook(conn,'2026-08-01','2026-08-31')
            with self.assertRaises(RemapError):
                preview_workbook(conn,self.edited(mutate=lambda ws:ws.__setitem__('H2',price+0.000001)))

    def test_future_receipt_cannot_hide_shortage_created_by_remap(self):
        with server.db() as conn:
            before = preview_workbook(conn,self.edited())
            self.assertTrue(before['can_confirm'])
            Seed.add_posted_source(conn,source='minvoice',number='FUTURE-OUT',
                invoice_date='2026-09-05',product_code='REMAP-B',qty=8)
            Seed.add_canonical_event(conn,10,'input','FUTURE-IN','2026-09-20',product_code='REMAP-B')
            self.file = export_workbook(conn,'2026-08-01','2026-08-31')
            preview = preview_workbook(conn,self.edited())
            self.assertFalse(preview['can_confirm'],preview)
            self.assertIn('REMAP-B',' '.join(preview['errors']))
            with self.assertRaises(RemapError):
                confirm_preview(conn,before['token'],'Future changed after preview',server.now_iso())
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])

    def test_concurrent_confirm_applies_once_and_rejects_other_stale_preview(self):
        with server.db() as conn:
            conn.execute("UPDATE inventory_transactions SET qty_in=3.7 WHERE source_type='OPENING' AND product_code='HH-01'")
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            first = preview_workbook(conn,self.edited())
            other = preview_workbook(conn,self.edited())
        barrier = Barrier(2)
        def confirm():
            with server.app.test_client() as client:
                barrier.wait(timeout=10)
                result = client.post('/api/inventory/output-remap/confirm',json={
                    'token':first['token'],'actor':'Concurrent test','confirmed':True})
                return result.status_code,result.get_json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _:confirm(),range(2)))
        self.assertEqual([200,200],[r[0] for r in results],results)
        self.assertEqual([False,True],sorted(r[1]['idempotent'] for r in results))
        stale = self.client.post('/api/inventory/output-remap/confirm',json={
            'token':other['token'],'actor':'Stale test','confirmed':True})
        self.assertEqual(409,stale.status_code,stale.get_json())
        with server.db() as conn:
            self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM audit_log WHERE event_type='inventory.output.remap'").fetchone()[0])
            self.assertEqual(9.7,canonical_available_stock(conn)['REMAP-B']['canonical_qty'])

    def test_fractional_deficit_split_preserves_invoice_and_reverses_after_month_close(self):
        with server.db() as conn:
            conn.execute("UPDATE inventory_transactions SET qty_in=3.7,unit_cost=20 WHERE source_type='OPENING' AND product_code='HH-01'")
            conn.execute("UPDATE products SET unit='Chai' WHERE code='REMAP-B'")
            mapping=conn.execute("""INSERT INTO invoice_line_mappings(tenant,source,invoice_type,scope_key,product_code,mapping_status,conversion_factor,confirmed_at,updated_at)
                VALUES('test','minvoice','OUTPUT_ELECTRONIC_INVOICE',?,'HH-01','confirmed',1,'test','test')""",(str(self.line_id),)).lastrowid
            revision=conn.execute("""INSERT INTO invoice_mapping_revisions(revision_key,mapping_id,product_code,source_unit,target_unit,conversion_factor,created_at)
                VALUES(?,?,'HH-01','kg','kg',1,'test')""",(str(self.line_id),mapping)).lastrowid
            conn.execute('UPDATE invoice_inventory_ledger SET mapping_revision_id=? WHERE source_line_id=?',(revision,self.line_id))
            before={table:[dict(r) for r in conn.execute('SELECT * FROM '+table+' ORDER BY id')] for table in
                    ('invoice_inventory_ledger','outgoing_source_invoices','outgoing_source_invoice_items')}
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            preview=preview_workbook(conn,self.edited())
            self.assertTrue(preview['can_confirm'],preview)
            change=preview['changes'][0]
            self.assertEqual((0.3,4,0,9.7),tuple(change[k] for k in ('qty','source_stock_qty','old_closing_after','new_closing_after')))
            confirm_preview(conn,preview['token'],'Partial test',server.now_iso())
            for table,values in before.items():self.assertEqual(values,[dict(r) for r in conn.execute('SELECT * FROM '+table+' ORDER BY id')])
            parts=[dict(r) for r in conn.execute("SELECT * FROM invoice_inventory_effective_ledger WHERE source_line_id=? AND event_type='POST'",(self.line_id,))]
            self.assertEqual({'HH-01':-3.7,'REMAP-B':-0.3},{r['product_code']:r['qty_delta'] for r in parts})
            self.assertEqual(2,len({r['event_key'] for r in parts}))
            book=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31')))
            exported=list(book.active.iter_rows(min_row=5,values_only=True));book.close()
            self.assertEqual(2,len(exported));self.assertTrue(all(r[6]==4 and r[8]==80 for r in exported))
            self.assertAlmostEqual(4,sum(r[14] for r in exported))
            close=inventory_period_close_preview(conn,'2026-08',today=date(2026,9,10))
            self.assertTrue(close['can_close'],close)
            close_inventory_period(conn,'2026-08',expected_source_hash=close['source_hash'],expected_target_hash=close['target_hash'],timestamp=server.now_iso(),today=date(2026,9,10))
            conn.execute("UPDATE outgoing_source_invoices SET stock_status='reversal_required',source_status_class='cancelled' WHERE id=?",(self.source_id,))
            reverse_output_invoice(conn,self.source_id,confirmed=True,note='partial reversal',now_iso=lambda:'2026-09-25T12:00:00')
            self.assertTrue(reverse_output_invoice(conn,self.source_id,confirmed=True,note='partial reversal',now_iso=lambda:'2026-09-25T12:00:00')['idempotent'])
            stock=canonical_available_stock(conn)
            self.assertEqual((3.7,10),(stock['HH-01']['canonical_qty'],stock['REMAP-B']['canonical_qty']))
            report=monthly_average_report(conn,date_from='2026-09-01',date_to='2026-09-30',include_zero=True)
            values={r['product_code']:r['closing_value'] for r in report['items']}
            self.assertEqual((74,300),(values['HH-01'],values['REMAP-B']))

    def _three_selected_rows(self, conn, deficit=64, target_stock=1110):
        conn.execute("UPDATE inventory_transactions SET qty_in=? WHERE source_type='OPENING' AND product_code='HH-01'",(1214-deficit,))
        conn.execute("UPDATE inventory_transactions SET qty_in=? WHERE source_type='OPENING' AND product_code='REMAP-B'",(target_stock,))
        conn.execute('UPDATE invoice_inventory_ledger SET qty_delta=-64 WHERE source_line_id=?',(self.line_id,))
        conn.execute('UPDATE outgoing_source_invoice_items SET qty=64,stock_qty=64 WHERE id=?',(self.line_id,))
        for index,qty in enumerate((350,800),2):
            invoice=Seed.add_posted_source(conn,source='minvoice',number='DEFICIT-'+str(index),qty=qty)
            conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',
                         (json.dumps({'_tdp_source_contract':'minvoice_portal_v1','details':[{'taxAmount':0}]}),invoice))
            line=conn.execute("""INSERT INTO outgoing_source_invoice_items(invoice_id,line_index,source_item_code,
                source_item_name,source_unit,qty,unit_price,amount,tax_rate,product_code,mapping_status,stock_qty)
                VALUES(?,1,'SRC','Original invoice','kg',?,20,?,'8','HH-01','mapped',?)""",(invoice,qty,qty*20,qty)).lastrowid
            conn.execute('UPDATE invoice_inventory_ledger SET source_line_id=? WHERE source_invoice_id=?',(line,invoice))
        self.file=export_workbook(conn,'2026-08-01','2026-08-31')
        def select(ws):
            for row in range(2,5):ws[f'Q{row}']='REMAP-B';ws[f'R{row}']='Hàng nhận'
        return self.edited(mutate=select)

    def test_repeated_rows_transfer_only_64_not_1214(self):
        with server.db() as conn:
            preview=preview_workbook(conn,self._three_selected_rows(conn))
            self.assertTrue(preview['can_confirm'],preview)
            self.assertEqual([64],[r['qty'] for r in preview['changes']])
            self.assertEqual(2,len(preview['skipped']))
            self.assertEqual(1046,preview['changes'][0]['new_closing_after'])
            confirm_preview(conn,preview['token'],'Only deficit',server.now_iso())
            self.assertEqual(0,canonical_available_stock(conn)['HH-01']['canonical_qty'])

    def test_deficit_spans_rows_once_and_partially_uses_last_required_row(self):
        with server.db() as conn:
            preview=preview_workbook(conn,self._three_selected_rows(conn,deficit=80))
            self.assertTrue(preview['can_confirm'],preview)
            self.assertEqual([64,16],[r['qty'] for r in preview['changes']])
            self.assertEqual(1,len(preview['skipped']))
            confirm_preview(conn,preview['token'],'Split deficit',server.now_iso())
            self.assertEqual(1030,canonical_available_stock(conn)['REMAP-B']['canonical_qty'])
            self.assertEqual(0,canonical_available_stock(conn)['HH-01']['canonical_qty'])

    def test_shortage_message_uses_deficit_quantity_and_identifies_selected_rows(self):
        with server.db() as conn:
            preview=preview_workbook(conn,self._three_selected_rows(conn,target_stock=50))
            self.assertFalse(preview['can_confirm'])
            error=preview['errors'][0]
            for expected in ('Hàng nhận','trước chuyển 50 kg','chuyển sang 64 kg','hàng Excel 2: 64','Còn thiếu 14 kg'):
                self.assertIn(expected,error)
            self.assertNotIn('1.214',error)

    def test_kkknt_changes_are_skipped_and_legacy_full_quantity_previews_rejected(self):
        with server.db() as conn:
            preview=preview_workbook(conn,self.edited())
            row=conn.execute('SELECT payload FROM output_stock_excel_sessions WHERE token=?',(preview['token'],)).fetchone()
            payload=json.loads(row[0]);payload.pop('mode')
            conn.execute('UPDATE output_stock_excel_sessions SET payload=? WHERE token=?',(json.dumps(payload),preview['token']))
            with self.assertRaisesRegex(RemapError,'Chọn lại file'):confirm_preview(conn,preview['token'],'Legacy preview',server.now_iso())
            conn.execute("UPDATE products SET tax='KKKNT' WHERE code='HH-01'")
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            preview=preview_workbook(conn,self.edited(name='Ignored choice'))
            self.assertEqual([],preview['changes']);self.assertIn('KKKNT',preview['skipped'][0]['reason'])

    def test_partial_write_failure_rolls_back_and_can_be_retried(self):
        with server.db() as conn:
            conn.execute("UPDATE inventory_transactions SET qty_in=3.7 WHERE source_type='OPENING' AND product_code='HH-01'")
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            preview=preview_workbook(conn,self.edited())
            conn.execute("CREATE TEMP TRIGGER fail_partial BEFORE INSERT ON output_stock_remap_parts WHEN NEW.product_code='REMAP-B' BEGIN SELECT RAISE(ABORT,'fixture'); END")
            with self.assertRaises(Exception):confirm_preview(conn,preview['token'],'Partial rollback',server.now_iso())
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remap_parts').fetchone()[0])
            self.assertEqual('HH-01',conn.execute('SELECT product_code FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone()[0])
            conn.execute('DROP TRIGGER fail_partial')
            self.assertEqual(1,confirm_preview(conn,preview['token'],'Partial retry',server.now_iso())['changed_lines'])

    def test_partial_component_can_be_reallocated_without_losing_remaining_quantity(self):
        from .output_stock_remap import init_schema,_snapshot,_source_hash
        with server.db() as conn:
            conn.execute("UPDATE inventory_transactions SET qty_in=3.7 WHERE source_type='OPENING' AND product_code='HH-01'")
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            preview=preview_workbook(conn,self.edited());confirm_preview(conn,preview['token'],'First partial',server.now_iso())
            conn.execute("UPDATE inventory_transactions SET qty_in=3.9 WHERE source_type='OPENING' AND product_code='HH-01'")
            conn.execute("UPDATE inventory_transactions SET qty_in=0.2 WHERE source_type='OPENING' AND product_code='REMAP-B'")
            book=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31',scope='blocking')))
            ws=book.active;self.assertEqual(5,ws.max_row);self.assertLess(ws['A5'].value,0)
            ws['Q5']='HH-01';ws['R5']='Hàng hóa 01'
            data=io.BytesIO();book.save(data);book.close()
            preview=preview_workbook(conn,data.getvalue());self.assertTrue(preview['can_confirm'],preview)
            self.assertEqual(0.1,preview['changes'][0]['qty'])
            confirm_preview(conn,preview['token'],'Second partial',server.now_iso())
            pieces={r['product_code']:r['qty_delta'] for r in conn.execute('SELECT * FROM invoice_inventory_effective_ledger WHERE source_line_id=?',(self.line_id,))}
            self.assertEqual({'HH-01':-3.8,'REMAP-B':-0.2},pieces)
            stock=canonical_available_stock(conn);self.assertAlmostEqual(0.1,stock['HH-01']['canonical_qty']);self.assertEqual(0,stock['REMAP-B']['canonical_qty'])
            before=_source_hash(_snapshot(conn,'2026-08-01','2026-08-31'))
            init_schema(conn)
            self.assertEqual(before,_source_hash(_snapshot(conn,'2026-08-01','2026-08-31')))

    def test_second_remap_returns_quantity_without_double_subtraction(self):
        with server.db() as conn:
            self.file = export_workbook(conn,'2026-08-01','2026-08-31')
            first = preview_workbook(conn,self.edited())
            confirm_preview(conn,first['token'],'First',server.now_iso())
            conn.execute("UPDATE inventory_transactions SET qty_in=0 WHERE source_type='OPENING' AND product_code='REMAP-B'")
            conn.execute("UPDATE inventory_transactions SET qty_in=10 WHERE source_type='OPENING' AND product_code='HH-01'")
            self.file = export_workbook(conn,'2026-08-01','2026-08-31')
            second = preview_workbook(conn,self.edited(code='HH-01',name='Hàng hóa 01'))
            self.assertTrue(second['can_confirm'],second)
            confirm_preview(conn,second['token'],'Second',server.now_iso())
            stock = canonical_available_stock(conn)
            self.assertEqual((6,0),(stock['HH-01']['canonical_qty'],stock['REMAP-B']['canonical_qty']))
            self.assertEqual(2,conn.execute('SELECT revision FROM output_stock_remaps').fetchone()[0])

    def test_selected_line_and_resync_preserve_other_line_and_source_report(self):
        from .invoice_output_sync import upsert_output_invoice
        from .test_invoice_output_sync import documented_minvoice_invoice
        remote = documented_minvoice_invoice(20)
        # Two source lines with the same inventory code: only the selected line
        # changes. Use the real source normalizer again after the internal edit.
        detail = remote['details'][0]
        detail.update(inv_itemCode='HH-01',inv_quantity=1,inv_unitPrice=20,
                      inv_TotalAmountWithoutVat=20,inv_vatAmount=1.6,inv_TotalAmount=21.6)
        remote['details'].append({**detail,'stt_rec0':'0002','inv_itemName':'Dòng nguồn thứ hai'})
        remote.update(tgtcthue=40,tgtthue=3.2,tgtttbso=43.2)
        options = dict(tenant='default',source='minvoice',now=server.now_iso(),
                       status_map={},status_fields=(),reference_fields=())
        with server.db() as conn:
            conn.execute("UPDATE products SET unit='Bịch' WHERE code='REMAP-B'")
            conn.execute("UPDATE inventory_transactions SET qty_in=5.5 WHERE source_type='OPENING' AND product_code='HH-01'")
            options['tenant'] = conn.execute("SELECT value FROM settings WHERE key='tenant_code'").fetchone()[0]
            invoice_id,_,_,review = upsert_output_invoice(conn,remote,**options)
            self.assertFalse(review)
            conn.execute("UPDATE outgoing_source_invoices SET stock_status='posted' WHERE id=?",(invoice_id,))
            raw=json.loads(conn.execute('SELECT raw_json FROM outgoing_source_invoices WHERE id=?',(invoice_id,)).fetchone()[0])
            raw['_tdp_source_contract']='minvoice_portal_v1'
            conn.execute('UPDATE outgoing_source_invoices SET raw_json=? WHERE id=?',(json.dumps(raw),invoice_id))
            lines = [dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice_id,))]
            for line in lines:
                conn.execute("UPDATE outgoing_source_invoice_items SET product_code='HH-01',stock_qty=1,mapping_status='mapped' WHERE id=?",(line['id'],))
                Seed.add_canonical_event(conn,-1,'output','MULTI-'+str(line['id']),'2026-08-20',
                    source_table='outgoing_source_invoices',source_id=invoice_id)
                conn.execute('UPDATE invoice_inventory_ledger SET source_line_id=?,source_line_index=? WHERE event_key=?',
                    (line['id'],line['line_index'],'MULTI-'+str(line['id'])))
            original = [dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice_id,))]
            self.file = export_workbook(conn,'2026-08-01','2026-08-31')
            def select_line(ws):
                ws['Q2']='HH-01';ws['R2']='Hàng hóa 01'
                ws['Q3']='REMAP-B';ws['R3']='Hàng nhận'
            preview = preview_workbook(conn,self.edited(mutate=select_line))
            self.assertTrue(preview['can_confirm'],preview)
            self.assertEqual(1,len(preview['changes']))
            confirm_preview(conn,preview['token'],'Selected line test',server.now_iso())
            invoice_id2,created,_,review = upsert_output_invoice(conn,remote,**options)
            self.assertEqual((invoice_id,False,False),(invoice_id2,created,review))
            after = [dict(r) for r in conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE invoice_id=? ORDER BY line_index',(invoice_id,))]
            self.assertEqual(original,after)
            self.assertEqual(9.5,canonical_available_stock(conn)['REMAP-B']['canonical_qty'])
        response = self.client.get('/api/invoice-valuation/export/output?from=2026-08-01&to=2026-08-31')
        self.assertEqual(200,response.status_code,response.get_json(silent=True))
        wb = load_workbook(io.BytesIO(response.data),data_only=True)
        rows = list(wb.active.values)
        changed = next(r for r in rows if len(r)>4 and r[4]=='Hàng kiểm thử')
        unchanged = next(r for r in rows if len(r)>4 and r[4]=='Dòng nguồn thứ hai')
        self.assertEqual(('Hàng kiểm thử','Kg',1,20,20),changed[4:9])
        self.assertEqual(('HH-01','Dòng nguồn thứ hai','Kg',1,20,20),unchanged[3:9])
        self.assertEqual((1.6,21.6),changed[11:13])
        wb.close()

    def test_cross_unit_remap_old_and_new_files_keep_quantity_and_invoice_unchanged(self):
        with server.db() as conn:
            conn.execute("UPDATE products SET unit='Bịch' WHERE code='REMAP-B'")
            before_header=dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(self.source_id,)).fetchone())
            before_line=dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone())
            before_ledger=[dict(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger ORDER BY id')]
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            for data in (self.edited(),self.new_file(conn)):
                preview=preview_workbook(conn,data)
                self.assertTrue(preview['can_confirm'],preview)
                change=preview['changes'][0]
                self.assertEqual((4,'kg','Bịch',0,6),tuple(change[k] for k in ('qty','old_unit','unit','old_closing_after','new_closing_after')))
            result=confirm_preview(conn,preview['token'],'Cross unit test',server.now_iso())
            self.assertEqual(1,result['changed_lines'])
            self.assertTrue(confirm_preview(conn,preview['token'],'Cross unit test',server.now_iso())['idempotent'])
            self.assertEqual(before_header,dict(conn.execute('SELECT * FROM outgoing_source_invoices WHERE id=?',(self.source_id,)).fetchone()))
            self.assertEqual({**before_line,'product_code':'REMAP-B'},dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone()))
            self.assertEqual(before_ledger,[dict(r) for r in conn.execute('SELECT * FROM invoice_inventory_ledger ORDER BY id')])
            book=load_workbook(io.BytesIO(export_new_workbook(conn,'2026-08-01','2026-08-31')))
            sheet=book['Doi ma xuat kho']
            self.assertEqual((4,'Bịch',0,'kg',4),tuple(sheet[c+'5'].value for c in ('O','N','P','F','G')))
            book.close()
            report=monthly_average_report(conn,date_from='2026-08-01',date_to='2026-08-31',include_zero=True)
            target=next(r for r in report['items'] if r['product_code']=='REMAP-B')
            self.assertEqual(('Bịch',6,180),(target['unit'],target['closing_qty'],target['closing_value']))
            # A second remap uses the current internal unit, never the invoice unit.
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            second=preview_workbook(conn,self.edited(code='REMAP-C',name='Hoa cúng'))
            self.assertFalse(second['can_confirm'],second)
            self.assertEqual([],second['changes'])
            stocks=canonical_available_stock(conn)
            self.assertEqual((0,6,-3),tuple(stocks[c]['canonical_qty'] for c in ('HH-01','REMAP-B','REMAP-C')))

    def test_cross_unit_still_checks_target_stock_and_catalog_changes(self):
        with server.db() as conn:
            conn.execute("UPDATE products SET unit='Bịch' WHERE code='REMAP-B'")
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            preview=preview_workbook(conn,self.edited())
            self.assertTrue(preview['can_confirm'],preview)
            conn.execute("UPDATE products SET unit='Chai' WHERE code='REMAP-B'")
            with self.assertRaises(RemapError): confirm_preview(conn,preview['token'],'Test',server.now_iso())
            conn.execute("UPDATE inventory_transactions SET qty_in=1 WHERE product_code='REMAP-B'")
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            preview=preview_workbook(conn,self.edited())
            self.assertFalse(preview['can_confirm']);self.assertIn('Còn thiếu 3',preview['errors'][0])

    def test_bad_code_name_formula_and_missing_row(self):
        with server.db() as conn:
            self.assertFalse(preview_workbook(conn,self.edited(code='NO-SUCH-CODE'))['can_confirm'])
            self.assertFalse(preview_workbook(conn,self.edited(name='Tên tự bịa'))['can_confirm'])
            with self.assertRaises(RemapError): preview_workbook(conn,self.edited(code='=1+1'))
            with self.assertRaises(RemapError): preview_workbook(conn,self.edited(mutate=lambda ws:ws.delete_rows(2)))

    def test_catalog_name_repair_requires_explicit_choice_and_keeps_stock_checks(self):
        with server.db() as conn:
            original=dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone())
            data=self.edited(name='Tên khách viết ngắn')
            blocked=preview_workbook(conn,data)
            self.assertFalse(blocked['can_confirm'])
            self.assertEqual('Hàng nhận',blocked['name_corrections'][0]['catalog_name'])
            fixed=preview_workbook(conn,data,use_catalog_names=True)
            self.assertTrue(fixed['can_confirm'],fixed)
            self.assertEqual('REMAP-B',fixed['changes'][0]['new_code'])
            self.assertEqual('Hàng nhận',fixed['changes'][0]['new_name'])
            self.assertEqual(original,dict(conn.execute('SELECT * FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone()))
            unknown=preview_workbook(conn,self.edited(code='NO-SUCH-CODE'),use_catalog_names=True)
            self.assertFalse(unknown['can_confirm'])
            self.assertEqual([],unknown['name_corrections'])
            conn.execute("UPDATE inventory_transactions SET qty_in=1 WHERE product_code='REMAP-B'")
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            shortage=preview_workbook(conn,self.edited(name='Tên viết tắt'),use_catalog_names=True)
            self.assertFalse(shortage['can_confirm'])
            self.assertIn('Còn thiếu 3',shortage['errors'][0])

    def test_target_shortage_stale_file_and_stale_preview_are_rejected(self):
        with server.db() as conn:
            p=preview_workbook(conn,self.edited()); self.assertTrue(p['can_confirm'])
            conn.execute("UPDATE inventory_transactions SET qty_in=1 WHERE product_code='REMAP-B'")
            with self.assertRaises(RemapError): confirm_preview(conn,p['token'],'Test',server.now_iso())
            with self.assertRaises(RemapError): preview_workbook(conn,self.edited())
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            p=preview_workbook(conn,self.edited()); self.assertFalse(p['can_confirm']); self.assertIn('Còn thiếu 3',p['errors'][0])

    def test_reversal_returns_stock_to_remapped_product(self):
        with server.db() as conn:
            conn.execute("UPDATE products SET unit='Bịch' WHERE code='REMAP-B'")
            mapping = conn.execute("""INSERT INTO invoice_line_mappings(tenant,source,invoice_type,scope_key,product_code,mapping_status,conversion_factor,confirmed_at,updated_at)
                VALUES('test','minvoice','OUTPUT_ELECTRONIC_INVOICE',?,'HH-01','confirmed',1,'test','test')""",(str(self.line_id),)).lastrowid
            revision = conn.execute("""INSERT INTO invoice_mapping_revisions(revision_key,mapping_id,product_code,source_unit,target_unit,conversion_factor,created_at)
                VALUES(?,?,'HH-01','kg','kg',1,'test')""",(str(self.line_id),mapping)).lastrowid
            conn.execute('UPDATE invoice_inventory_ledger SET mapping_revision_id=? WHERE source_line_id=?',(revision,self.line_id))
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            p=preview_workbook(conn,self.edited()); confirm_preview(conn,p['token'],'Test',server.now_iso())
            self.assertEqual(30,conn.execute("SELECT unit_cost FROM invoice_inventory_effective_ledger WHERE source_line_id=?",(self.line_id,)).fetchone()[0])
            close=inventory_period_close_preview(conn,'2026-08',today=date(2026,9,10))
            close_inventory_period(conn,'2026-08',expected_source_hash=close['source_hash'],expected_target_hash=close['target_hash'],timestamp=server.now_iso(),today=date(2026,9,10))
            conn.execute("UPDATE outgoing_source_invoices SET stock_status='reversal_required',source_status_class='cancelled' WHERE id=?",(self.source_id,))
            reverse_output_invoice(conn,self.source_id,confirmed=True,note='fixture',now_iso=lambda:'2026-09-25T12:00:00')
            stocks=canonical_available_stock(conn)
            self.assertEqual((0,10),tuple(stocks[c]['canonical_qty'] for c in ['HH-01','REMAP-B']))
            report=monthly_average_report(conn,date_from='2026-09-01',date_to='2026-09-30',include_zero=True)
            target=next(r for r in report['items'] if r['product_code']=='REMAP-B')
            self.assertEqual(('Bịch',10,300),(target['unit'],target['closing_qty'],target['closing_value']))

    def test_remapping_does_not_restore_local_issued_hold(self):
        with server.db() as conn:
            batch,orders=Seed.add_batch(conn,'2026-08-20',[{'qty':4}])
            Seed.add_local_issued_draft(conn,batch,orders[0],number='REMAP-1')
            self.file=export_workbook(conn,'2026-08-01','2026-08-31')
            p=preview_workbook(conn,self.edited()); confirm_preview(conn,p['token'],'Test',server.now_iso())
            self.assertEqual(0,canonical_available_stock(conn)['HH-01']['pending_sync_issued_qty'])

    def test_write_failure_rolls_back_every_change(self):
        with server.db() as conn:
            p=preview_workbook(conn,self.edited())
            conn.execute("CREATE TEMP TRIGGER fail_remap BEFORE UPDATE ON outgoing_source_invoice_items BEGIN SELECT RAISE(ABORT,'fixture'); END")
            with self.assertRaises(Exception): confirm_preview(conn,p['token'],'Test',server.now_iso())
            self.assertEqual(0,conn.execute('SELECT COUNT(*) FROM output_stock_remaps').fetchone()[0])
            self.assertEqual('HH-01',conn.execute('SELECT product_code FROM outgoing_source_invoice_items WHERE id=?',(self.line_id,)).fetchone()[0])

    def test_negative_kkknt_can_allocate_export_issue_and_recalculate(self):
        with server.db() as conn:
            batch,orders=Seed.add_batch(conn,'2026-08-20',[{'product_code':'REMAP-C','qty':100}])
            conn.execute("UPDATE orders SET tax='KKKNT' WHERE batch_id=?",(batch,))
        ready=self.client.get(f'/api/outgoing-invoices/readiness/{batch}').get_json()
        self.assertEqual([],ready['blocking_issues']); self.assertEqual(100,ready['invoiceable_qty'])
        self.assertEqual(1,len(ready['negative_stock_warnings']))
        for _ in range(2):
            created=self.client.post(f'/api/outgoing-invoices/draft/{batch}')
            self.assertEqual(200,created.status_code,created.get_json())
            self.assertEqual(0,created.get_json()['pending_qty'])
        exported=self.client.get(f'/api/export/invoices/{batch}')
        self.assertEqual(200,exported.status_code,exported.get_json(silent=True))
        draft=created.get_json()['drafts'][0]['id']
        with server.db() as conn:
            conn.execute("UPDATE outgoing_invoice_drafts SET buyer_name_snapshot='Buyer',buyer_tax_code_snapshot='0200000001',"
                         "buyer_address_snapshot='Address',company_name_snapshot='TDP',company_tax_code_snapshot='0100000001',"
                         "company_address_snapshot='Address',payment_requester_snapshot='Requester',"
                         "payment_bank_name_snapshot='Bank',payment_bank_account_snapshot='Account' WHERE batch_id=?", (batch,))
        issued=self.client.post(f'/api/outgoing-invoices/{draft}/confirm-issued',json={
            'confirmed':True,'invoice_number':'999001','invoice_series':'1C26TDP','invoice_date':'2026-08-20'})
        self.assertEqual(200,issued.status_code,issued.get_json())
        ready=self.client.get(f'/api/outgoing-invoices/readiness/{batch}').get_json()
        self.assertEqual((100,0),(ready['issued_qty'],ready['invoiceable_qty']))

    def test_zero_kct_unknown_and_mixed_tax_do_not_get_negative_exception(self):
        for tax in ['0%','KCT','INVALID','8%']:
            with self.subTest(tax=tax),server.db() as conn:
                conn.execute('UPDATE products SET tax=? WHERE code=?',(tax,'REMAP-C'))
                batch,_=Seed.add_batch(conn,'2026-08-20',[{'product_code':'REMAP-C','qty':1}])
                conn.execute('UPDATE orders SET tax=? WHERE batch_id=?',(tax,batch))
            ready=self.client.get(f'/api/outgoing-invoices/readiness/{batch}').get_json()
            self.assertEqual(1,len(ready['blocking_issues']))
            self.assertEqual(0,ready['invoiceable_qty'])
            self.assertNotEqual(200,self.client.post(f'/api/outgoing-invoices/draft/{batch}').status_code)
        with server.db() as conn:
            conn.execute("UPDATE products SET tax='KKKNT' WHERE code='REMAP-C'")
            conn.execute("UPDATE orders SET tax='0%' WHERE batch_id=?",(batch,))
        self.assertEqual(1,len(self.client.get(f'/api/outgoing-invoices/readiness/{batch}').get_json()['blocking_issues']))

    def test_kkknt_supplementary_purchase_register_does_not_require_nonnegative_stock(self):
        with server.db() as conn:
            conn.execute("INSERT OR REPLACE INTO suppliers(code,name) VALUES('BK-S1','Nhà cung cấp')")
            conn.execute("UPDATE products SET purchase_list=1,supplier='BK-S1',buy_price=10 WHERE code='REMAP-C'")
        template=self.client.get('/api/bk-import/template')
        wb=load_workbook(io.BytesIO(template.data)); ws=wb['BK_IMPORT']
        ws.append(['2026-08-31','','BK-FLOWER',1,'REMAP-C','Hoa cúng','kg',1,10,10,'BK-S1','Bổ sung mua vào'])
        data=io.BytesIO(); wb.save(data); wb.close()
        response=self.client.post('/api/bk-import/preview',data={'file':(io.BytesIO(data.getvalue()),'bk.xlsx')})
        self.assertEqual(200,response.status_code,response.get_json())
        preview=response.get_json()
        posted=self.client.post('/api/bk-import/confirm',json={'confirmed':True,'token':preview['token'],'previewId':preview['previewId']})
        self.assertEqual(200,posted.status_code,(posted.get_json(),preview))
        with server.db() as conn:
            self.assertEqual(-2,canonical_available_stock(conn)['REMAP-C']['canonical_qty'])
            report=monthly_average_report(conn,date_from='2026-08-01',date_to='2026-08-31',include_zero=True)
            self.assertEqual(-2,next(r for r in report['items'] if r['product_code']=='REMAP-C')['closing_qty'])


if __name__ == '__main__': unittest.main()
