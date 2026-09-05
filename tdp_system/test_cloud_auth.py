import re
import unittest

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
