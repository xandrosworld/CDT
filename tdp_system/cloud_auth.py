"""Authenticated browser sessions for the hosted application."""
from __future__ import annotations

import hmac
import gzip
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from flask import jsonify, redirect, render_template_string, request, session
from werkzeug.security import check_password_hash

LOGIN = """<!doctype html><html lang="vi"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Đăng nhập · Thành Đạt Phát</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf3f5;color:#17324d;font:16px system-ui;
min-height:100vh;display:grid;place-items:center}main{background:white;padding:40px;
width:min(440px,92vw);border-radius:16px;box-shadow:0 12px 45px #17324d14}
h1{font-size:24px;margin:0 0 8px}p{line-height:1.6;color:#5e7083}label{display:block;margin:20px 0 7px}
input,button{font:inherit;width:100%;padding:12px;border:1px solid #b8c8ce;border-radius:7px}
button{background:#087f73;color:white;border:0;margin-top:24px;cursor:pointer}
.error{color:#a52b24}</style><main><h1>THÀNH ĐẠT PHÁT</h1><p>Đăng nhập hệ thống quản lý</p>
{% if error %}<p role="alert" class="error">{{ error }}</p>{% endif %}
<form method="post"><input type="hidden" name="csrf" value="{{ csrf }}">
<label for="username">Tên đăng nhập</label><input id="username" name="username" autocomplete="username" required>
<label for="password">Mật khẩu</label><input id="password" name="password" type="password" autocomplete="current-password" required>
<button type="submit">Đăng nhập</button></form></main></html>"""


def install_cloud_auth(app, *, username, password_hash, secret_key, secure=True):
    if not username or not password_hash.startswith(('scrypt:', 'pbkdf2:')) or len(secret_key) < 32:
        raise RuntimeError('Hosted mode requires a username, password hash and strong session secret')
    app.config.update(SECRET_KEY=secret_key, SESSION_COOKIE_NAME='tdp_session',
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=secure,
                      SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    attempts = defaultdict(deque)
    lock = threading.Lock()

    def guard():
        if request.path in ('/health', '/login'):
            return None
        if session.get('user') != username:
            if request.path.startswith('/api/'):
                return jsonify(ok=False, error='Vui lòng đăng nhập để tiếp tục.'), 401
            return redirect('/login')
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            # Browser fetch/form writes carry an Origin; script clients must set it too.
            if request.headers.get('Origin', '').rstrip('/') != request.host_url.rstrip('/'):
                return jsonify(ok=False, error='Yêu cầu không đúng nguồn đăng nhập.'), 403
        return None

    app.before_request_funcs.setdefault(None, []).insert(0, guard)

    @app.route('/login', methods=['GET', 'POST'])
    def cloud_login():
        error, status = '', 200
        csrf = session.setdefault('login_csrf', secrets.token_urlsafe(24))
        if request.method == 'POST':
            if not hmac.compare_digest(request.form.get('csrf', ''), csrf):
                return 'Phiên đăng nhập hết hạn. Hãy tải lại trang.', 403
            peer = request.remote_addr or 'unknown'
            now = time.monotonic()
            with lock:
                # Bound both memory and failed attempts; one process owns these counters.
                for key in list(attempts):
                    while attempts[key] and attempts[key][0] < now - 600:
                        attempts[key].popleft()
                    if not attempts[key]:
                        del attempts[key]
                if len(attempts) > 10000 or len(attempts[peer]) >= 10:
                    return render_template_string(LOGIN, csrf=csrf,
                        error='Đã thử quá nhiều lần. Vui lòng thử lại sau 10 phút.'), 429
                attempts[peer].append(now)
            valid_password = check_password_hash(password_hash, request.form.get('password', ''))
            if hmac.compare_digest(request.form.get('username', '').encode(), username.encode()) and valid_password:
                with lock:
                    attempts.pop(peer, None)
                session.clear()
                session['user'] = username
                session.permanent = True
                return redirect('/')
            error, status = 'Tên đăng nhập hoặc mật khẩu chưa đúng.', 401
        return render_template_string(LOGIN, csrf=csrf, error=error), status

    @app.post('/logout')
    def cloud_logout():
        session.clear()
        return redirect('/login')

    @app.after_request
    def cloud_headers(response):
        if request.path == '/' and response.status_code == 200 and response.mimetype == 'text/html':
            html = response.get_data(as_text=True)
            old = '<button class="user-chip" title="Hai người có thể cùng sử dụng">VT</button>'
            response.set_data(html.replace(old,
                '<form action="/logout" method="post"><button class="user-chip" type="submit">Đăng xuất</button></form>'))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'private, no-store'
        if secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if (response.status_code == 200 and request.accept_encodings['gzip'] > 0
                and not response.headers.get('Content-Encoding') and not response.headers.get('Content-Range')
                and response.mimetype in {'application/json', 'application/javascript', 'text/javascript', 'text/css', 'text/html'}):
            response.direct_passthrough = False
            payload = response.get_data()
            if len(payload) >= 1024:
                compressed = gzip.compress(payload, compresslevel=5)
                if len(compressed) < len(payload):
                    response.set_data(compressed)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.vary.add('Accept-Encoding')
                    response.headers.pop('ETag', None)
        return response
