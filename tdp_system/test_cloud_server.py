import os
import tempfile
import sqlite3
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import patch

from . import cloud_server


class CloudStartupTests(unittest.TestCase):
    def test_only_authenticated_cloud_admin_can_download_remote_backup(self):
        from . import server
        with tempfile.TemporaryDirectory() as root:
            database = Path(root) / 'working.sqlite3'
            with closing(sqlite3.connect(database)) as conn:
                conn.execute('CREATE TABLE evidence(value TEXT)')
                conn.execute("INSERT INTO evidence VALUES('preserve')")
                conn.commit()
            with patch.object(server, 'DB_PATH', database), patch.object(server, 'DATA_DIR', Path(root)), \
                    patch.dict(server.app.config, SECRET_KEY='test-session-secret', TDP_CLOUD_ADMIN_USER='admin'):
                client = server.app.test_client()
                kwargs = {'environ_overrides': {'REMOTE_ADDR': '203.0.113.9'}}
                self.assertEqual(client.get('/api/backup', **kwargs).status_code, 403)
                with client.session_transaction() as session:
                    session['user'] = 'different-user'
                self.assertEqual(client.get('/api/backup', **kwargs).status_code, 403)
                with client.session_transaction() as session:
                    session['user'] = 'admin'
                response = client.get('/api/backup', **kwargs)
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.data.startswith(b'SQLite format 3'))
                finally:
                    response.close()

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
