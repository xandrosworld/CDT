import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import cloud_server


class CloudStartupTests(unittest.TestCase):
    def test_bootstrap_serves_only_preparation_and_never_creates_database(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'tdp.sqlite3'
            with patch.dict(os.environ, TDP_DATA_DIR=root, TDP_DB_PATH=str(path), TDP_BOOTSTRAP='1'), \
                    patch('threading.Thread.start'), patch('waitress.serve') as serve:
                cloud_server.main()
                app = serve.call_args.args[0]
                client = app.test_client()
                self.assertEqual(client.get('/health').json, {'ok': True, 'database_ready': False, 'bootstrap': True})
                self.assertEqual(client.get('/').status_code, 503)
                self.assertEqual(client.get('/api/bootstrap').status_code, 404)
                self.assertFalse(path.exists())

    def test_normal_mode_refuses_missing_database(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, TDP_DATA_DIR=root, TDP_DB_PATH=str(Path(root)/'missing.sqlite3'), TDP_BOOTSTRAP='0'):
                with self.assertRaisesRegex(RuntimeError, 'Upload the verified database'):
                    cloud_server.main()
