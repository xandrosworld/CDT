"""Railway entrypoint: one process, persistent data, authenticated HTTP."""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

PROXY_OPTIONS = {
    'trusted_proxy': '*',
    'trusted_proxy_count': 1,
    'trusted_proxy_headers': {'x-forwarded-for', 'x-forwarded-proto'},
}


def main():
    if hasattr(time, 'tzset'):
        time.tzset()
    data = Path(os.environ['TDP_DATA_DIR']).resolve()
    data.mkdir(parents=True, exist_ok=True)
    database = Path(os.environ['TDP_DB_PATH']).resolve()
    if not database.is_relative_to(data):
        raise RuntimeError('Database must reside on the persistent data volume')
    if os.environ.get('TDP_BOOTSTRAP') == '1' and not (data / '.bootstrap-ready').exists():
        # Railway file transfer needs a running container. This temporary service
        # exposes no business routes and never initializes an empty customer DB.
        from flask import Flask, jsonify
        from waitress import serve
        bootstrap = Flask('tdp_bootstrap')
        bootstrap.add_url_rule('/health', endpoint='health', view_func=lambda: jsonify(ok=True, database_ready=False, bootstrap=True))
        bootstrap.add_url_rule('/', endpoint='preparing', view_func=lambda: ('Đang chuẩn bị dữ liệu. Vui lòng quay lại sau.', 503))
        def await_upload():
            while not (data / '.bootstrap-ready').exists():
                time.sleep(2)
            os.execv(sys.executable, [sys.executable, '-m', 'tdp_system.cloud_server'])
        threading.Thread(target=await_upload, daemon=True).start()
        serve(bootstrap, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')), threads=2)
        return
    # Refuse an empty deployment instead of silently replacing missing customer data.
    if not database.is_file() or database.stat().st_size == 0:
        raise RuntimeError('Upload the verified database to the volume before starting the service')
    root = Path(__file__).resolve().parent.parent
    assets = data / 'assets'
    # Only office/reference assets may be linked into the runtime; never executable code.
    for source in assets.rglob('*') if assets.exists() else []:
        if not source.is_file() or source.suffix.lower() not in {'.xlsx', '.xlsm', '.docx', '.json'}:
            continue
        relative = source.relative_to(assets)
        target = root / relative
        if not target.parent.resolve().is_relative_to(root):
            raise RuntimeError('Asset destination escaped application directory')
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to(source)

    try:
        from . import server
        from .cloud_auth import install_cloud_auth
    except ImportError:
        import server
        from cloud_auth import install_cloud_auth
    from waitress import serve

    # Configure Waitress itself: it otherwise strips proxy headers before Flask.
    # The service is reachable publicly only through Railway's immediate proxy.
    install_cloud_auth(server.app, username=os.environ.get('TDP_ADMIN_USER', ''),
        password_hash=os.environ.get('TDP_ADMIN_PASSWORD_HASH', ''),
        secret_key=os.environ.get('TDP_SESSION_SECRET', ''))
    domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
    hosts = set(filter(None, os.environ.get('TDP_TRUSTED_HOSTS', '').split(',')))
    hosts.update(filter(None, [domain, 'healthcheck.railway.app']))
    os.environ['TDP_TRUSTED_HOSTS'] = ','.join(sorted(hosts))
    # The imported DB already owns its master catalog. File mtime changes on upload
    # must not re-import the original workbook over later catalog edits.
    server.MASTER_SOURCE = data / '.no_automatic_master_import.xlsx'
    server.init_database()
    stop, worker = server.start_backup_worker(server.auto_backup)
    print('TDP hosted application ready; persistent database initialized', flush=True)
    try:
        serve(server.app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')),
              threads=4, **PROXY_OPTIONS)
    finally:
        stop.set()
        worker.join(timeout=2)


if __name__ == '__main__':
    main()
