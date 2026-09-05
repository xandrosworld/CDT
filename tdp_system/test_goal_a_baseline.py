from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from .goal_a_baseline import (
        BaselineGuardError,
        assert_database_unchanged,
        require_source_database,
        sha256_file,
    )
except ImportError:  # pragma: no cover - direct file invocation
    from goal_a_baseline import (  # type: ignore
        BaselineGuardError,
        assert_database_unchanged,
        require_source_database,
        sha256_file,
    )


class GoalABaselineGuardTests(unittest.TestCase):
    def test_hash_is_stable_and_mutation_is_detected(self):
        with tempfile.TemporaryDirectory(prefix="tdp_baseline_guard_") as temp_name:
            database = Path(temp_name) / "source.sqlite3"
            database.write_bytes(b"safe baseline")
            expected = sha256_file(database)

            self.assertEqual(expected, require_source_database(database))
            assert_database_unchanged(database, expected, "fixture")

            database.write_bytes(b"unexpected mutation")
            with self.assertRaises(BaselineGuardError):
                assert_database_unchanged(database, expected, "fixture")

    def test_missing_or_empty_database_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tdp_baseline_guard_") as temp_name:
            missing = Path(temp_name) / "missing.sqlite3"
            with self.assertRaises(BaselineGuardError):
                require_source_database(missing)

            missing.touch()
            with self.assertRaises(BaselineGuardError):
                require_source_database(missing)


if __name__ == "__main__":
    unittest.main()
