"""Identity and scaling regressions for importing a large order history."""
import unittest
from .receivable_ledger import _index_source_identities, _source_identity, _source_key

class IdentityIndexTests(unittest.TestCase):
    def test_reused_id_keeps_generation_and_latest_revision(self):
        rows = {
            'new': dict(id=9, source_table='orders', source_id=7, source_key='new', status='active'),
            'old': dict(id=2, source_table='orders', source_id=7, source_key='old', status='reversed', reversal_reason='source_removed'),
            'other': dict(id=99, source_table='other', source_id=7, source_key='other', status='active'),
        }
        index = _index_source_identities(rows)
        self.assertEqual(_source_identity(7,index), ('new',rows['new']))
        rows['new'].update(status='reversed',reversal_reason='source_removed')
        self.assertEqual(_source_identity(7,index), (_source_key(7,3),None))
        self.assertEqual(_source_identity(8,index), (_source_key(8),None))
        rows['new']['reversal_reason']='batch_not_approved'
        self.assertEqual(_source_identity(7,index), ('new',rows['new']))

    def test_large_history_is_read_once_for_all_lookups(self):
        class Ledger(dict):
            visits=0
            def values(self):
                for row in super().values():
                    self.visits+=1
                    yield row
        ledger=Ledger({str(i):dict(id=i,source_id=i,source_table='orders',source_key=str(i),status='active') for i in range(15000)})
        index=_index_source_identities(ledger)
        for i in range(15000):self.assertEqual(_source_identity(i,index)[0],str(i))
        self.assertEqual(ledger.visits,15000)
