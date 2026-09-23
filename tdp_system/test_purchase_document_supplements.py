import json
from unittest.mock import patch

from . import purchase_document_selection as selection
from . import purchase_document_supplements as supplements
from .test_purchase_document_selection import PurchaseDocumentSelectionTests


class PurchaseDocumentSupplementTests(PurchaseDocumentSelectionTests):
    def supplement_body(self):
        state = supplements.queue(self.conn, '2026-09-01', '2026-09-30')
        return {**state, 'dates': ['2026-09-14'], 'reference': 'BS-09-01', 'actor': 'Kiểm thử',
                'request_id': 'test-request-1', 'confirmed': True}

    def make(self, body=None):
        return supplements.create(self.conn, body or self.supplement_body(), '2026-09-30', self.audit)

    def test_saved_remainder_filed_once_keeps_dates_money_and_original_selection(self):
        self.save(self.body({'1': '10', '2': '5'}))
        before = {table: list(self.conn.execute('SELECT * FROM '+table)) for table in
                  ('batches', 'purchase_document_selections', 'purchase_document_selection_history')}
        request = self.supplement_body()
        result = self.make(request)
        self.assertEqual(result['id'], self.make(request)['id'])
        self.assertTrue(self.make(request)['unchanged'])
        self.assertEqual(1, self.conn.execute('SELECT COUNT(*) FROM purchase_document_supplements').fetchone()[0])
        record = supplements.get_record(self.conn, result['id'])
        row = json.loads(record['rows_json'])[0]
        self.assertEqual(('2026-09-14', 5, 1500000), (row['work_date'], row['quantity'], row['amount']))
        self.assertEqual(before, {table: list(self.conn.execute('SELECT * FROM '+table)) for table in before})
        self.assertEqual([], selection.pending_queue(self.conn, '2026-09-30')['entries'])
        state = supplements.queue(self.conn, '2026-09-01', '2026-09-30')
        self.assertEqual([], state['entries'])
        self.assertEqual(1500000, state['history'][0]['amount'])
        selected, pending, plan = selection.export_scope(self.conn, {'id': 2, 'work_date': '2026-09-14', 'status': 'approved'}, self.rows)
        self.assertEqual(5, selected[0]['quantity'])
        self.assertEqual([], pending)
        from openpyxl import Workbook
        book = selection.annotate_workbook(Workbook(), plan, pending)
        self.assertEqual(0, book['Đối chiếu lựa chọn']['E2'].value)
        self.assertEqual(1500000, book['Đối chiếu lựa chọn']['F2'].value)
        book.close()

    def test_unsaved_choices_cannot_be_filed(self):
        state = supplements.queue(self.conn, '2026-09-01', '2026-09-30')
        self.assertEqual('needs_selection', state['entries'][0]['status'])
        with self.assertRaisesRegex(ValueError, 'chưa lưu'):
            self.make()

    def test_concurrent_old_queue_cannot_file_duplicates(self):
        self.save(self.body({'1': '10'}))
        request = self.supplement_body()
        self.make(request)
        request.update(request_id='other-tab', reference='BS-09-02')
        with self.assertRaisesRegex(ValueError, 'vừa thay đổi'):
            self.make(request)

    def test_cancel_returns_pending_and_allows_selection_change(self):
        self.save(self.body({'1': '10'}))
        record = self.make()
        edit = self.body({'2': '10'}); edit['reason'] = 'Đổi lựa chọn'
        with self.assertRaisesRegex(ValueError, 'đã lập bảng kê bổ sung'):
            self.save(edit)
        supplements.cancel(self.conn, record['id'], {'actor': 'Kiểm thử', 'reason': 'Sửa bản in', 'confirmed': True}, '2026-10-01', self.audit)
        state = supplements.queue(self.conn, '2026-09-01', '2026-09-30')
        self.assertEqual(3000000, state['entries'][0]['pending'])
        self.assertEqual('cancelled', state['history'][0]['status'])
        self.save(edit)

    def test_changed_source_remains_visible_for_review(self):
        self.save(self.body({'1': '10'})); self.make()
        self.rows[1]['amount'] += 100
        entry = supplements.queue(self.conn, '2026-09-01', '2026-09-30')['entries'][0]
        self.assertEqual('needs_review', entry['status'])

    def test_required_fields_and_confirmation(self):
        self.save(self.body({'1': '10'}))
        for field, value in [('actor', ''), ('reference', ''), ('confirmed', False), ('dates', [])]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.make({**self.supplement_body(), field: value})

    def test_month_filter_export_literals_and_no_identity_in_queue(self):
        self.save(self.body({'1': '10'}))
        state = supplements.queue(self.conn, '2026-09-01', '2026-09-30')
        self.assertNotIn('cccd', json.dumps(state))
        self.assertFalse(supplements.queue(self.conn, '2026-09-15', '2026-09-30')['entries'])
        record = self.make()
        book = supplements.workbook(supplements.get_record(self.conn, record['id']))
        self.assertEqual(1, len(book.sheetnames))
        self.assertEqual('2026-09-14', book.active['A5'].value)
        self.assertEqual(3000000, book.active['G5'].value)
        self.assertFalse(any(c.data_type == 'f' for row in book.active for c in row))
        book.close()

    def test_multi_day_document_keeps_separate_purchase_dates(self):
        self.conn.execute("INSERT INTO batches VALUES(3,'2026-09-15','approved')")
        def source(conn, work_date):
            rows = [{**r, 'work_date': work_date, 'selection_key': work_date+'-'+str(i)} for i, r in enumerate(self.rows)]
            return rows, selection.digest(rows)
        with patch.object(selection, 'day_source', side_effect=source):
            state = selection.scope(self.conn, '2026-09-14', '2026-09-15')
            selection.save(self.conn, {**state, 'actor':'Test', 'days':[{'date': d['date'], 'quantities':{}} for d in state['days']]}, '2026-09-30', self.audit)
            body = self.supplement_body(); body['dates'] = ['2026-09-14', '2026-09-15']
            record = supplements.get_record(self.conn, self.make(body)['id'])
            rows = json.loads(record['rows_json'])
            self.assertEqual({'2026-09-14', '2026-09-15'}, {r['work_date'] for r in rows})
            self.assertEqual(12000000, sum(r['amount'] for r in rows))
            self.assertFalse(supplements.queue(self.conn, '2026-09-01', '2026-09-30')['entries'])
