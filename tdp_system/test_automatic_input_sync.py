import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import Mock

from .automatic_input_sync import (VN,init_schema,schedule,claim,run_due,status,fetch_snapshot)
from .msmi_refresh import MsmiRefresh,RefreshError
from .test_invoice_input_sync import init_test_database,DateBoundedMsmi
from .test_msmi_sync import remote_invoice


class AutoInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.sqlite3'
        self.now=datetime(2026,9,16,2,30,tzinfo=VN)
        with self.db() as c:
            init_test_database(c);init_schema(c)
            c.execute("INSERT INTO automatic_input_sync(tenant,enabled) VALUES('TDP',1)")
        self.refresh=Mock();self.refresh.refresh.return_value={'source_ready':True,'repaired_details':0}
        self.factory=Mock(return_value=self.refresh)

    def tearDown(self):self.tmp.cleanup()

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row
        try:yield c;c.commit()
        finally:c.close()

    def execute(self,rows=()):
        return run_due(self.db,'TDP',lambda:DateBoundedMsmi(rows),self.factory,'0202265016',now_fn=lambda:self.now)

    def state(self):
        with self.db() as c:return status(c,'TDP',self.now)

    def test_vietnam_slots_month_year_boundary(self):
        for now,previous,next_ in [
            ('2026-09-16T02:29:59+07:00','2026-09-15T06:00:00+07:00','2026-09-16T02:30:00+07:00'),
            ('2027-01-01T02:30:00+07:00','2027-01-01T02:30:00+07:00','2027-01-01T06:00:00+07:00')]:
            self.assertEqual((previous,next_),tuple(t.isoformat() for t in schedule(datetime.fromisoformat(now))))

    def test_network_outside_write_transaction_and_two_workers_cannot_overlap(self):
        def refresh(*args):
            with self.db() as c:
                c.execute('BEGIN IMMEDIATE')
                self.assertEqual('running',status(c,'TDP',self.now)['state'])
            self.assertIsNone(claim(self.db,'TDP',self.now))
            return {'source_ready':True}
        self.refresh.refresh.side_effect=refresh
        self.assertTrue(self.execute()['ok'])
        self.assertEqual('2026-09-16T06:00:00+07:00',self.state()['next_attempt'])
        self.assertTrue(self.execute()['skipped'])

    def test_restart_recovers_expired_lease_and_catches_missed_schedule(self):
        first=claim(self.db,'TDP',self.now)
        self.assertIsNone(claim(self.db,'TDP',self.now+timedelta(minutes=10)))
        self.assertNotEqual(first,claim(self.db,'TDP',self.now+timedelta(minutes=41)))

    def test_healthy_catchup_is_running_without_false_stale_alarm(self):
        self.now=self.now.replace(hour=23)
        self.assertIsNotNone(claim(self.db,'TDP',self.now))
        self.assertFalse(self.state()['attention'])
        self.now+=timedelta(minutes=41)
        self.assertTrue(self.state()['attention'])

    def test_source_failure_retries_and_preserves_last_good_data(self):
        self.refresh.refresh.side_effect=RefreshError('mSMI chưa kết nối')
        self.assertFalse(self.execute()['ok'])
        s=self.state();self.assertTrue(s['attention']);self.assertIsNone(s['last_success'])
        self.assertEqual('2026-09-16T03:00:00+07:00',s['next_attempt'])
        self.assertTrue(self.execute()['skipped'])
        self.now+=timedelta(minutes=30);self.refresh.refresh.side_effect=None
        self.assertTrue(self.execute()['ok']);self.assertFalse(self.state()['attention'])

    def test_empty_source_stubs_are_not_success_and_later_details_recover_without_duplicates_or_stock(self):
        item=remote_invoice(20649);item.update(_id='recovered',tdlap='2026-09-15',nmmst='0202265016')
        stub={'_id':'recovered','type':'purchase','tthai':1}
        self.assertFalse(self.execute([stub])['ok'])
        self.now+=timedelta(minutes=30)
        self.assertTrue(self.execute([item])['ok'])
        self.now=self.now.replace(hour=6,minute=0)
        self.assertTrue(self.execute([item])['ok'])
        with self.db() as c:
            self.assertEqual(1,c.execute('SELECT COUNT(*) FROM msmi_invoices').fetchone()[0])
            self.assertEqual(0,c.execute('SELECT COUNT(*) FROM inventory_transactions').fetchone()[0])
            self.assertEqual(0,c.execute('SELECT COUNT(*) FROM orders').fetchone()[0])
            self.assertIsNone(c.execute("SELECT * FROM msmi_invoices WHERE sync_status='review_required'").fetchone())

    def test_unexpected_errors_do_not_leak_credentials_and_disabled_worker_does_not_connect(self):
        self.refresh.refresh.side_effect=RuntimeError('password=secret-private')
        self.execute();self.assertNotIn('secret-private',json.dumps(self.state()))
        with self.db() as c:c.execute('UPDATE automatic_input_sync SET enabled=0')
        self.refresh.reset_mock();self.assertTrue(self.execute()['skipped']);self.refresh.refresh.assert_not_called()

    def test_stale_status_warns_and_other_tenant_cannot_see_it(self):
        self.execute();self.now=self.now.replace(hour=7)
        self.assertTrue(self.state()['attention'])
        with self.db() as c:self.assertEqual({'enabled':False},status(c,'OTHER',self.now))

    def test_fetch_ignored_dates_deduplicates_and_excludes_other_buyer(self):
        good=remote_invoice(20649);good.update(_id='yes',tdlap='2026-09-15',nmmst='0202265016')
        old=deepcopy(good);old.update(_id='old',tdlap='2026-08-01')
        other=deepcopy(good);other.update(_id='other',nmmst='9999999999')
        class Client:
            def list_invoices(self,**kw):return {'items':[good,old,other,good],'has_more':False}
        rows=fetch_snapshot(Client(),'2026-09-09','2026-09-16','0202265016')
        self.assertEqual(['yes'],[r['_id'] for r in rows])


class RefreshTests(unittest.TestCase):
    def test_portal_refresh_runs_both_purchase_types_then_repairs_details_and_verifies(self):
        client=MsmiRefresh('login','private-password','0202265016')
        a={'_id':'abc123','username':'0202265016','password':'private-tax-password','token':'private-token',
           'user':'user123','sync_invoices_purchase':{'sync':True}}
        detail={'_id':'missing','type':'purchase','from':'query','key':'key',
                'keys':{'nbmst':'seller','khhdon':'C26TMA','shdon':20649,'khmshdon':1}}
        client.request=Mock(side_effect=[{}, {'items':[a]}, [], [], [detail], {}, []])
        result=client.refresh('2026-09-14','2026-09-16')
        self.assertEqual({'source_ready':True,'repaired_details':1},result)
        calls=client.request.call_args_list
        self.assertEqual(['purchase','purchase_sco'],[calls[n].args[1]['invoiceType'] for n in (2,3)])
        self.assertEqual('detail',calls[5].args[1]['crawlType'])
        self.assertEqual('2026-09-13T17:00:00.000Z',calls[4].kwargs['params']['from'])
        self.assertEqual('2026-09-16T16:59:59.999Z',calls[4].kwargs['params']['to'])
        self.assertNotIn('private',json.dumps(result))

    def test_wrong_account_or_unconfirmed_source_never_succeeds(self):
        client=MsmiRefresh('u','p','0202265016')
        client.request=Mock(side_effect=[{}, {'items':[]}])
        with self.assertRaises(RefreshError):client.refresh('2026-09-14','2026-09-16')
        self.assertEqual(2,client.request.call_count)
