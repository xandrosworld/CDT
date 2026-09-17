import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock

from .automatic_output_sync import VN, init_schema, claim, status, run_due
from .outgoing_source_refresh import REFRESH_LOCK, SourceSnapshot


class AutomaticOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.sqlite3'
        self.now=datetime(2026,9,17,14,0,tzinfo=VN)
        with self.db() as c:
            init_schema(c)
            c.execute("INSERT INTO automatic_output_sync(tenant) VALUES('TDP')")
            c.execute('CREATE TABLE batches(work_date TEXT,status TEXT)')
            c.execute("INSERT INTO batches VALUES('2026-09-01','approved')")
        self.good={'sync':{'complete':True},'blocked':[],'waiting':{'warnings':[]}}

    def tearDown(self):
        self.temp.cleanup()

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=.1);c.row_factory=sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback();raise
        finally:
            c.close()

    def execute(self):
        return run_due(self.db,'TDP',lambda:None,lambda:'now',now_fn=lambda:self.now)

    def state(self):
        with self.db() as c:return status(c,'TDP',self.now)

    def test_five_minute_schedule_and_all_approved_order_history(self):
        with patch('tdp_system.automatic_output_sync.refresh_sources',return_value=self.good) as refresh:
            self.assertTrue(self.execute()['ok'])
            self.assertEqual(refresh.call_args.args[3:],('2026-09-01','2026-09-17'))
            self.assertTrue(self.execute()['skipped'])
            self.now+=timedelta(minutes=5)
            self.assertTrue(self.execute()['ok'])
            self.assertEqual(refresh.call_count,2)
        self.assertFalse(self.state()['attention'])

    def test_failure_retries_without_advancing_success_or_exposing_secrets(self):
        with patch('tdp_system.automatic_output_sync.refresh_sources',return_value=self.good):self.execute()
        before=self.state();self.now+=timedelta(minutes=5)
        with patch('tdp_system.automatic_output_sync.refresh_sources',side_effect=RuntimeError('secret-password-cookie')):
            self.assertFalse(self.execute()['ok'])
        s=self.state()
        self.assertEqual(s['last_checked'],before['last_checked'])
        self.assertEqual(s['last_success'],before['last_success'])
        self.assertEqual(s['next_attempt'],(self.now+timedelta(minutes=5)).isoformat())
        self.assertTrue(s['attention']);self.assertNotIn('secret-password',json.dumps(s))
        self.now+=timedelta(minutes=5)
        with patch('tdp_system.automatic_output_sync.refresh_sources',return_value=self.good):self.execute()
        self.assertFalse(self.state()['attention'])

    def test_stock_or_draft_blocker_is_not_reported_as_success(self):
        for result in [dict(self.good,blocked=[{'number':'808','error':'Cần đối chiếu kg'}]),
                       dict(self.good,waiting={'warnings':[{'contractor':'A','message':'Chưa khớp đơn'}]}),
                       dict(self.good,sync={'complete':True,'review_required':1})]:
            with self.subTest(result=result):
                with patch('tdp_system.automatic_output_sync.refresh_sources',return_value=result):
                    self.assertFalse(self.execute()['ok'])
                s=self.state();self.assertEqual('needs_review',s['state']);self.assertTrue(s['attention'])
                self.assertIsNone(s['last_success']);self.assertTrue(s['last_checked'])
                self.now+=timedelta(minutes=5)

    def test_restart_recovers_expired_claim_and_missed_schedule(self):
        first=claim(self.db,'TDP',self.now)
        self.assertIsNone(claim(self.db,'TDP',self.now+timedelta(minutes=1)))
        self.now+=timedelta(minutes=16)
        self.assertTrue(self.state()['attention'])
        self.assertNotEqual(first,claim(self.db,'TDP',self.now))

    def test_auto_does_not_queue_behind_foreground_refresh(self):
        held=threading.Event();release=threading.Event()
        def foreground():
            with REFRESH_LOCK:
                held.set();release.wait(5)
        worker=threading.Thread(target=foreground);worker.start()
        try:
            self.assertTrue(held.wait(2));self.assertTrue(self.execute()['skipped'])
            self.assertIsNone(self.state()['last_attempt'])
        finally:
            release.set();worker.join()

    def test_disabled_worker_never_contacts_provider(self):
        with self.db() as c:c.execute('UPDATE automatic_output_sync SET enabled=0')
        with patch('tdp_system.automatic_output_sync.refresh_sources') as refresh:
            self.assertTrue(self.execute()['skipped']);refresh.assert_not_called()

    def test_completed_but_stale_status_requires_attention(self):
        with patch('tdp_system.automatic_output_sync.refresh_sources',return_value=self.good):self.execute()
        self.now+=timedelta(minutes=11)
        self.assertTrue(self.state()['attention'])

    def test_changed_pagination_or_duplicate_invoice_never_counts_as_complete(self):
        for second in [{'data':[{'id':'A'}],'total':2},{'data':[{'id':'B'}],'total':3}]:
            client=Mock()
            client.get_invoice_series.return_value=[{'value':'1C26TDP'}]
            client.get_outgoing_invoices.side_effect=[{'data':[{'id':'A'}],'total':2},second]
            with self.assertRaises(ValueError):SourceSnapshot(client,'2026-09-01','2026-09-17')


if __name__=='__main__':unittest.main()
