import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from werkzeug.security import generate_password_hash
from .cloud_auth import install_cloud_auth
from .worksheet_assets import register
from .server import prevent_stale_application_assets


class WorksheetAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name) / 'worksheet-bundle'
        directory.mkdir()
        self.payload = b'/* worksheet fixture */' * 300
        self.name = 'worksheet-' + hashlib.sha256(self.payload).hexdigest()[:16] + '.js'
        (directory / self.name).write_bytes(self.payload)
        (directory / (self.name + '.gz')).write_bytes(gzip.compress(self.payload))
        (directory / 'worksheet.js').write_bytes(self.payload)
        (directory / 'manifest.json').write_text(json.dumps({'script': self.name, 'bytes': len(self.payload)}))
        self.app = Flask(__name__)
        register(self.app, self.tmp.name)
        self.app.after_request(prevent_stale_application_assets)
        install_cloud_auth(self.app, username='fixture', password_hash=generate_password_hash('fixture'), secret_key='x'*40, secure=False)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user'] = 'fixture'

    def test_precompressed_code_is_reusable_without_recompressing(self):
        with patch('tdp_system.cloud_auth.gzip.compress', side_effect=AssertionError('Must serve prebuilt gzip')):
            response = self.client.get('/static/worksheet-bundle/' + self.name, headers={'Accept-Encoding': 'gzip'})
            self.addCleanup(response.close)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Content-Encoding'], 'gzip')
            self.assertEqual(gzip.decompress(response.data), self.payload)
            self.assertIn('immutable', response.headers['Cache-Control'])
            self.assertIn('private', response.headers['Cache-Control'])
            self.assertIn('Accept-Encoding', response.headers['Vary'])
            self.assertNotIn('Pragma', response.headers)

    def test_identity_client_receives_original_code(self):
        response = self.client.get('/static/worksheet-bundle/' + self.name, headers={'Accept-Encoding':'identity'})
        self.addCleanup(response.close)
        self.assertEqual(response.data, self.payload)
        self.assertNotIn('Content-Encoding', response.headers)

    def test_manifest_and_unversioned_code_always_refresh(self):
        for name in ('manifest.json', 'worksheet.js'):
            with self.subTest(name=name):
                response = self.client.get('/static/worksheet-bundle/' + name)
                self.addCleanup(response.close)
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertNotIn('immutable', response.headers['Cache-Control'])

    def test_authentication_and_missing_asset_are_not_cacheable(self):
        missing = self.client.get('/static/worksheet-bundle/worksheet-1111111111111111.js')
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn('immutable', missing.headers['Cache-Control'])
        with self.client.session_transaction() as session:
            session.clear()
        denied = self.client.get('/static/worksheet-bundle/' + self.name)
        self.assertEqual(denied.status_code, 302)
        self.assertNotIn('immutable', denied.headers['Cache-Control'])
