"""Durable polling of signed M-Invoice sources; never creates or signs invoices."""
import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

try:
    from .outgoing_source_refresh import refresh_sources, REFRESH_LOCK
except ImportError:
    from outgoing_source_refresh import refresh_sources, REFRESH_LOCK

VN = timezone(timedelta(hours=7))
INTERVAL = timedelta(minutes=5)
LEASE = timedelta(minutes=15)


def vn_now():
    return datetime.now(VN)


def init_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS automatic_output_sync(
        tenant TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
        state TEXT NOT NULL DEFAULT 'waiting', owner TEXT NOT NULL DEFAULT '',
        lease_until TEXT, last_attempt TEXT, last_checked TEXT, last_success TEXT,
        next_attempt TEXT, failures INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT '', issues_json TEXT NOT NULL DEFAULT '[]')''')


def status(conn, tenant, now=None):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='automatic_output_sync'").fetchone():
        return {'enabled': False, 'message': 'Đồng bộ tự động chưa được bật.'}
    row = conn.execute('SELECT * FROM automatic_output_sync WHERE tenant=?', (tenant,)).fetchone()
    if not row:
        return {'enabled': False, 'message': 'Đồng bộ tự động chưa được bật.'}
    r = dict(row); r.pop('owner')
    r['issues'] = json.loads(r.pop('issues_json'))
    now = now or vn_now()
    stale = not r['last_checked'] or now - datetime.fromisoformat(r['last_checked']) > timedelta(minutes=10)
    overdue = bool(r['lease_until'] and datetime.fromisoformat(r['lease_until']) <= now)
    r.update(interval_minutes=5, attention=bool(r['enabled'] and (stale or overdue or r['state'] in ('error','needs_review'))))
    return r


def claim(db, tenant, now):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r = c.execute('SELECT * FROM automatic_output_sync WHERE tenant=?', (tenant,)).fetchone()
        if not r or not r['enabled']:
            return None
        if r['lease_until'] and datetime.fromisoformat(r['lease_until']) > now:
            return None
        if r['next_attempt'] and datetime.fromisoformat(r['next_attempt']) > now:
            return None
        owner = uuid.uuid4().hex
        c.execute("""UPDATE automatic_output_sync SET state='running',owner=?,lease_until=?,last_attempt=?
                     WHERE tenant=?""", (owner,(now+LEASE).isoformat(),now.isoformat(),tenant))
        return owner


def run_due(db, tenant, client_factory, now_iso, *, now_fn=vn_now):
    # A foreground download and the background poll share one source refresh.
    # Do not let scheduled work queue behind an already active foreground job.
    if not REFRESH_LOCK.acquire(blocking=False):
        return {'skipped': True}
    try:
        owner = claim(db,tenant,now_fn())
        if not owner:
            return {'skipped': True}
        result = {}; issues = []; error = ''; checked = False
        try:
            with db() as c:
                first = c.execute("SELECT MIN(work_date) FROM batches WHERE status='approved'").fetchone()[0]
            if first:
                result = refresh_sources(db,client_factory,now_iso,first,now_fn().astimezone(VN).date().isoformat())
                issues = result.get('blocked',[]) + result.get('waiting',{}).get('warnings',[])
                if any(result.get('sync',{}).get(k) for k in ('error_count','review_required')):
                    issues.append({'message':'Có hóa đơn nguồn cần kiểm tra; xem Hóa đơn đầu ra.'})
            checked = True
        except Exception:
            # Provider exceptions may include URLs/payloads: never expose them here.
            error = 'Chưa cập nhật đủ hóa đơn đã ký. Hệ thống tự thử lại sau 5 phút; chưa dùng số cũ để xuất tiếp.'
        finished = now_fn()
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM automatic_output_sync WHERE tenant=?',(tenant,)).fetchone()
            if row['owner'] != owner:
                return {'superseded': True}
            state = 'error' if error else 'needs_review' if issues else 'success'
            message = error or (f'Còn {len(issues)} vấn đề cần đối chiếu hóa đơn đã ký.' if issues else 'Đã cập nhật và đối chiếu hóa đơn đã ký.')
            c.execute('''UPDATE automatic_output_sync SET state=?,owner='',lease_until=NULL,
                last_checked=?,last_success=?,next_attempt=?,failures=?,message=?,issues_json=? WHERE tenant=?''',
                (state,finished.isoformat() if checked else row['last_checked'],
                 finished.isoformat() if state=='success' else row['last_success'],
                 (finished+INTERVAL).isoformat(),row['failures']+1 if error else 0,message,
                 json.dumps(issues[:100],ensure_ascii=False),tenant))
        return {'ok':not error and not issues,'state':state,'result':result}
    finally:
        REFRESH_LOCK.release()


def start_worker(server, *, interval=30):
    with server.db() as c:
        init_schema(c)
        tenant = server.setting_get(c,'tenant_code','TDP')
        c.execute('INSERT OR IGNORE INTO automatic_output_sync(tenant) VALUES(?)',(tenant,))
        c.execute('UPDATE automatic_output_sync SET enabled=? WHERE tenant=?',
                  (int(os.environ.get('TDP_AUTO_OUTPUT_SYNC','1')=='1'),tenant))
    stop = threading.Event()
    def loop():
        while not stop.wait(interval):
            try:
                run_due(server.db,tenant,server.create_minvoice_client,server.now_iso)
            except Exception:
                print('Automatic output sync could not update status; retrying.',flush=True)
    worker = threading.Thread(target=loop,name='tdp-auto-output-sync',daemon=True)
    worker.start()
    return stop,worker
