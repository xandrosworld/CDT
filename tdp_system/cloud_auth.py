"""Authenticated browser sessions for the hosted application."""
from __future__ import annotations

import hmac
import gzip
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path

from flask import jsonify, redirect, render_template_string, request, session, send_from_directory
from werkzeug.security import check_password_hash

LOGIN_ASSETS = Path(__file__).with_name('login_assets')
LOGIN = (LOGIN_ASSETS / 'login.html').read_text(encoding='utf-8')
PUBLIC_LOGIN_ASSETS = frozenset({'login.css', 'login.js', 'harvest.webp', 'session.js'})
IDLE_SECONDS = 5 * 60 * 60


def install_cloud_auth(app, *, username, password_hash, secret_key, secure=True):
    if not username or not password_hash.startswith(('scrypt:', 'pbkdf2:')) or len(secret_key) < 32:
        raise RuntimeError('Hosted mode requires a username, password hash and strong session secret')
    app.config.update(SECRET_KEY=secret_key, TDP_CLOUD_ADMIN_USER=username, SESSION_COOKIE_NAME='tdp_session',
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=secure,
                      SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(days=30),
                      SESSION_REFRESH_EACH_REQUEST=False)
    attempts = defaultdict(deque)
    lock = threading.Lock()

    def guard():
        if request.path in ('/health', '/login') or (request.method in ('GET', 'HEAD') and request.path in {f'/login-assets/{name}' for name in PUBLIC_LOGIN_ASSETS}):
            return None
        if session.get('user') == username:
            # Background invoice polling must never count as customer activity.
            last_activity = session.get('last_activity')
            if last_activity is None:
                session['last_activity'] = time.time()  # Existing sessions at rollout.
            elif time.time() - last_activity >= IDLE_SECONDS:
                session.pop('user', None)
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

    @app.route('/api/session/activity', methods=['GET', 'POST'])
    def cloud_session_activity():
        if request.method == 'POST':
            session['last_activity'] = time.time()
        return jsonify(ok=True, remaining_seconds=max(0, IDLE_SECONDS - (time.time() - session['last_activity'])))

    @app.get('/login-assets/<name>')
    def cloud_login_asset(name):
        if name not in PUBLIC_LOGIN_ASSETS:
            return '', 404
        return send_from_directory(LOGIN_ASSETS, name)

    @app.route('/login', methods=['GET', 'POST'])
    def cloud_login():
        error, status = '', 200
        resume_mode = request.args.get('resume') == '1'
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
                        error='Đã thử quá nhiều lần. Vui lòng thử lại sau 10 phút.',
                        resume_mode=resume_mode,
                        entered_username=request.form.get('username', '')), 429
                attempts[peer].append(now)
            valid_password = check_password_hash(password_hash, request.form.get('password', ''))
            submitted_username = username if resume_mode else request.form.get('username', '')
            if hmac.compare_digest(submitted_username.encode(), username.encode()) and valid_password:
                with lock:
                    attempts.pop(peer, None)
                session.clear()
                session['user'] = username
                session['last_activity'] = time.time()
                session.permanent = True
                if request.args.get('resume') == '1':
                    return '<!doctype html><html lang="vi"><meta charset="utf-8"><p>Đã đăng nhập. Đang trở lại công việc…</p><script>window.parent.postMessage({type:"tdp-session-restored"},location.origin)</script></html>'
                return redirect('/')
            error, status = ('Mật khẩu chưa đúng.' if resume_mode else 'Tên đăng nhập hoặc mật khẩu chưa đúng.'), 401
        return render_template_string(LOGIN, csrf=csrf, error=error,
                                      resume_mode=resume_mode,
                                      entered_username=request.form.get('username', '')), status

    @app.post('/logout')
    def cloud_logout():
        session.clear()
        return redirect('/login')

    @app.after_request
    def cloud_headers(response):
        if request.path == '/' and response.status_code == 200 and response.mimetype == 'text/html':
            response.direct_passthrough = False
            html = response.get_data(as_text=True)
            old = '<button class="user-chip" title="Hai người có thể cùng sử dụng">VT</button>'
            html = html.replace(old,
                '<form action="/logout" method="post"><button class="user-chip" type="submit">Đăng xuất</button></form>')
            # Run ahead of application scripts without reloading the working page on expiry.
            script = '<script src="/login-assets/session.js?v=20261027"></script>'
            html = html.replace('</head>', script + '</head>') if '</head>' in html else script + html
            response.set_data(html)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        if not getattr(response, '_tdp_versioned_asset', False):
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
