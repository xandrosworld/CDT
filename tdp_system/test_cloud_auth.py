import re
import gzip
import io
import unittest
from unittest.mock import patch

from flask import Flask
from werkzeug.security import generate_password_hash

from .cloud_auth import install_cloud_auth


class CloudAuthTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True
        self.app.add_url_rule('/api/private', view_func=lambda: {'secret': 'test-data'}, methods=['GET', 'POST'])
        install_cloud_auth(self.app, username='admin',
            password_hash=generate_password_hash('fixture-password'), secret_key='s'*40, secure=False)
        self.client = self.app.test_client()

    def login(self, password='fixture-password'):
        page = self.client.get('/login')
        token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        return self.client.post('/login', data={'csrf': token, 'username': 'admin', 'password': password})

    def test_anonymous_and_wrong_password_cannot_read_data(self):
        self.assertEqual(self.client.get('/api/private').status_code, 401)
        self.assertEqual(self.login('wrong').status_code, 401)
        self.assertEqual(self.client.get('/api/private').status_code, 401)

    def test_login_csrf_cookie_and_cross_origin_writes(self):
        self.assertEqual(self.client.post('/login', data={'username': 'admin', 'password': 'fixture-password'}).status_code, 403)
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertEqual(self.client.get('/api/private').status_code, 200)
        for headers in ({}, {'Origin': 'https://attacker.invalid'}):
            self.assertEqual(self.client.post('/api/private', headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/api/private', headers={'Origin': 'http://localhost'}).status_code, 200)
        self.client.post('/logout', headers={'Origin': 'http://localhost'})
        self.assertEqual(self.client.get('/api/private').status_code, 401)

    def test_failed_logins_are_limited(self):
        for _ in range(10):
            self.assertEqual(self.login('wrong').status_code, 401)
        self.assertEqual(self.login().status_code, 429)

    def test_missing_cloud_credentials_fail_closed(self):
        with self.assertRaises(RuntimeError):
            install_cloud_auth(Flask('unsafe'), username='', password_hash='', secret_key='')

    def test_login_assets_are_public_without_exposing_other_files(self):
        for name in ('login.css', 'login.js', 'harvest.webp'):
            with self.client.get('/login-assets/' + name) as response:
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/login-assets/login.html').status_code, 302)
        self.assertEqual(self.client.get('/api/private').status_code, 401)

    def test_failed_login_preserves_and_escapes_username(self):
        page = self.client.get('/login')
        token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        response = self.client.post('/login', data={'csrf': token,
            'username': '<script>alert(1)</script>', 'password': 'wrong'})
        self.assertEqual(response.status_code, 401)
        self.assertIn('&lt;script&gt;', response.text)
        self.assertNotIn('<script>alert(1)</script>', response.text)

    def test_idle_expiry_and_activity_heartbeat(self):
        self.login()
        with self.client.session_transaction() as state:
            start = state['last_activity']
        with patch('tdp_system.cloud_auth.time.time', return_value=start + 17900):
            self.assertEqual(self.client.get('/api/private').status_code, 200)
        with self.client.session_transaction() as state:
            self.assertEqual(state['last_activity'], start)
        with patch('tdp_system.cloud_auth.time.time', return_value=start + 18001):
            self.assertEqual(self.client.post('/api/private', headers={'Origin':'http://localhost'}).status_code, 401)
        self.login()
        with self.client.session_transaction() as state:
            state['last_activity'] -= 17000
        response = self.client.post('/api/session/activity', headers={'Origin':'http://localhost'})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json['remaining_seconds'], 17990)

    def test_resume_login_stays_in_frame_and_keeps_csrf_protection(self):
        page = self.client.get('/login?resume=1')
        token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        response = self.client.post('/login?resume=1', data={'csrf':token,'username':'admin','password':'fixture-password'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('tdp-session-restored', response.text)
        self.assertEqual(self.client.post('/api/session/activity').status_code, 403)

    def test_text_compression_preserves_payload(self):
        self.app.add_url_rule('/large', endpoint='large', view_func=lambda: {'items': ['fixture-value']*500})
        self.login()
        response = self.client.get('/large', headers={'Accept-Encoding': 'gzip'})
        self.assertEqual(response.headers['Content-Encoding'], 'gzip')
        self.assertIn(b'fixture-value', gzip.decompress(response.data))
        self.assertIn('Accept-Encoding', response.headers['Vary'])

    def test_railway_https_survives_waitress_proxy_processing(self):
        from waitress.proxy_headers import proxy_headers_middleware
        from .cloud_server import PROXY_OPTIONS
        self.app.wsgi_app = proxy_headers_middleware(self.app.wsgi_app, **PROXY_OPTIONS)
        headers = {'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '203.0.113.9'}
        page = self.client.get('/login', headers=headers)
        token = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        result = self.client.post('/login', headers=headers,
            data={'csrf': token, 'username': 'admin', 'password': 'fixture-password'})
        self.assertEqual(result.status_code, 302)
        result = self.client.post('/api/private', headers={**headers, 'Origin': 'https://localhost'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.post('/api/private', headers={**headers, 'Origin':'https://bad.invalid'}).status_code, 403)

    def test_streamed_index_still_loads_with_logout_and_compression(self):
        from flask import send_file
        html = '<html><button class="user-chip" title="Hai người có thể cùng sử dụng">VT</button>' + 'x'*2000 + '</html>'
        self.app.add_url_rule('/', endpoint='index', view_func=lambda: send_file(io.BytesIO(html.encode()), mimetype='text/html'))
        self.login()
        response = self.client.get('/', headers={'Accept-Encoding':'gzip'})
        self.assertEqual(response.status_code, 200)
        result = gzip.decompress(response.data).decode()
        self.assertIn('action="/logout"', result)
        self.assertNotIn('>VT</button>', result)
