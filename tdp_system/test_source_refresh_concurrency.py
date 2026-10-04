import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from . import outgoing_source_refresh as refresh


class SourceRefreshConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'sync.sqlite3'
        refresh._LAST_REFRESH=None

    def tearDown(self):
        refresh._LAST_REFRESH=None
        self.temp.cleanup()

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path)
        try:yield c
        finally:c.close()

    def run_refresh(self,end='2026-10-31'):
        return refresh.refresh_sources(self.db,lambda:None,lambda:'now','2026-10-01',end)

    def test_overlapping_requests_share_complete_result_but_later_click_reads_again(self):
        started=threading.Event();release=threading.Event()
        def read(*args):
            started.set();release.wait(5)
            return {'from':'2026-09-01','to':'2026-10-31','sync':{'complete':True}}
        with patch.object(refresh,'_refresh_sources',side_effect=read) as reader:
            with ThreadPoolExecutor(2) as pool:
                first=pool.submit(self.run_refresh);self.assertTrue(started.wait(2))
                second=pool.submit(self.run_refresh);time.sleep(.1);release.set()
                self.assertEqual(first.result(),second.result())
            self.assertEqual(reader.call_count,1)
            self.run_refresh();self.assertEqual(reader.call_count,2)

    def test_failed_or_narrow_result_is_not_reused(self):
        for failed in (True,False):
            refresh._LAST_REFRESH=None
            started=threading.Event();release=threading.Event();calls=[]
            def read(*args):
                calls.append(args[-1])
                if len(calls)==1:
                    started.set();release.wait(5)
                    if failed:raise ValueError('incomplete source')
                return {'from':args[-2],'to':args[-1]}
            with patch.object(refresh,'_refresh_sources',side_effect=read):
                with ThreadPoolExecutor(2) as pool:
                    first=pool.submit(self.run_refresh,'2026-10-04');self.assertTrue(started.wait(2))
                    second=pool.submit(self.run_refresh);time.sleep(.1);release.set()
                    if failed:
                        with self.assertRaises(ValueError):first.result()
                    else:first.result()
                    self.assertEqual(second.result()['to'],'2026-10-31')
                self.assertEqual(len(calls),2)

    def test_busy_response_is_retryable_and_does_not_start_another_sync(self):
        held=threading.Event();release=threading.Event()
        def hold():
            with refresh.REFRESH_LOCK:held.set();release.wait(5)
        t=threading.Thread(target=hold);t.start();self.assertTrue(held.wait(2))
        try:
            with patch.object(refresh,'REFRESH_WAIT_SECONDS',.01),patch.object(refresh,'_refresh_sources') as reader:
                with self.assertRaises(refresh.SourceRefreshBusy) as e:self.run_refresh()
                self.assertEqual(e.exception.code,'source_refresh_busy');reader.assert_not_called()
        finally:release.set();t.join()
