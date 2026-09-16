"""Durable Vietnam-time input sync; all network I/O precedes DB writes."""
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

try:
    from .msmi_refresh import MsmiRefresh, RefreshError
    from .msmi_client import MsmiError
    from .contract_modules import as_date, first_value
    from .invoice_workbench import prepare_sync_batch
    from .invoice_input_sync import sync_input_batch, INPUT_INVOICE
except ImportError:
    from msmi_refresh import MsmiRefresh, RefreshError
    from msmi_client import MsmiError
    from contract_modules import as_date, first_value
    from invoice_workbench import prepare_sync_batch
    from invoice_input_sync import sync_input_batch, INPUT_INVOICE

VN = timezone(timedelta(hours=7))
SLOTS = ((2,30), (6,0))
LOOKBACK = 7
LEASE = timedelta(minutes=40)


def vn_now(): return datetime.now(VN)


def schedule(now):
    now = now.astimezone(VN)
    slots = [now.replace(hour=h,minute=m,second=0,microsecond=0)+timedelta(days=d)
             for d in (-1,0,1) for h,m in SLOTS]
    return max(t for t in slots if t <= now), min(t for t in slots if t > now)


def init_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS automatic_input_sync(
        tenant TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
        state TEXT NOT NULL DEFAULT 'waiting', owner TEXT NOT NULL DEFAULT '',
        lease_until TEXT, last_slot TEXT, last_attempt TEXT, last_success TEXT,
        next_attempt TEXT, failures INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT '', result_json TEXT NOT NULL DEFAULT '{}')''')


def status(conn, tenant, now=None):
    now = (now or vn_now()).astimezone(VN)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='automatic_input_sync'").fetchone():
        return {'enabled':False}
    row = conn.execute('SELECT * FROM automatic_input_sync WHERE tenant=?',(tenant,)).fetchone()
    if not row: return {'enabled':False}
    r = dict(row)
    result = json.loads(r.pop('result_json'))
    r.pop('owner')
    r.update(schedule='02:30 và 06:00 hằng ngày (giờ Việt Nam)', lookback_days=LOOKBACK,
             result=result, stock_changed=False)
    lease = datetime.fromisoformat(r['lease_until']) if r['lease_until'] else None
    due,_ = schedule(now)
    r['attention'] = bool(r['enabled'] and (r['state']=='error' or
        (r['state']=='running' and (not lease or lease <= now)) or
        (now > due+timedelta(minutes=45) and (not r['last_success'] or datetime.fromisoformat(r['last_success']) < due))))
    return r


def claim(db, tenant, now):
    owner = uuid.uuid4().hex
    slot,_ = schedule(now)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r = dict(c.execute('SELECT * FROM automatic_input_sync WHERE tenant=?',(tenant,)).fetchone())
        if not r['enabled']: return None
        if r['lease_until'] and datetime.fromisoformat(r['lease_until']) > now: return None
        if r['next_attempt'] and datetime.fromisoformat(r['next_attempt']) > now: return None
        c.execute('''UPDATE automatic_input_sync SET state='running',owner=?,lease_until=?,
                     last_attempt=?,last_slot=?,message='' WHERE tenant=?''',
                  (owner,(now+LEASE).isoformat(),now.isoformat(),slot.isoformat(),tenant))
    return owner


class Snapshot:
    def __init__(self, rows): self.rows=rows
    def list_invoices(self, *, page, size, **kwargs):
        part=self.rows[page*size:(page+1)*size]
        return {'items':part,'has_more':(page+1)*size<len(self.rows)}


def fetch_snapshot(client, start, end, tax_code, *, clock=time.monotonic):
    """Scan completely: mSMI ignores dates and may sort by update time."""
    deadline=clock()+600
    found={}
    for page in range(200):
        if clock() >= deadline: raise RefreshError('Chưa tải hết dữ liệu mSMI trong thời gian chờ; sẽ tự thử lại.')
        result=client.list_invoices(invoice_type=INPUT_INVOICE,page=page,size=199,from_date=start,to_date=end)
        for row in result['items']:
            if not isinstance(row,dict): raise RefreshError('mSMI trả dòng hóa đơn không hợp lệ.')
            date=as_date(first_value(row,'tdlap','nlap','invoiceDate','signedDate'))
            buyer=str(first_value(row,'nmmst','buyerTaxCode',default='')).strip()
            if buyer and buyer != tax_code: continue
            if date and not start <= date <= end: continue
            key=str(first_value(row,'_id','id','invoiceId',default=''))
            if not key: raise RefreshError('mSMI trả hóa đơn thiếu khóa định danh.')
            found[key]=row
        if not result['has_more']: return list(found.values())
    raise RefreshError('mSMI vượt giới hạn lượt tải; chưa xác nhận đủ dữ liệu.')


def run_due(db, tenant, client_factory, refresher_factory, tax_code, *, now_fn=vn_now):
    now=now_fn().astimezone(VN)
    owner=claim(db,tenant,now)
    if not owner: return {'skipped':True}
    start=(now.date()-timedelta(days=LOOKBACK)).isoformat()
    end=now.date().isoformat()
    result={}
    error=''
    try:
        source=refresher_factory().refresh(start,end)
        if not source.get('source_ready'): raise RefreshError('mSMI chưa xác nhận đồng bộ đủ chi tiết.')
        rows=fetch_snapshot(client_factory(),start,end,tax_code)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            lease=c.execute('SELECT owner,lease_until FROM automatic_input_sync WHERE tenant=?',(tenant,)).fetchone()
            if lease['owner'] != owner or datetime.fromisoformat(lease['lease_until']) <= now_fn():
                raise RefreshError('Lượt đồng bộ đã hết thời gian giữ chỗ; sẽ tự thử lại.')
            stamp=lambda:now_fn().astimezone(VN).strftime('%Y-%m-%d %H:%M:%S')
            batch,_=prepare_sync_batch(c,tenant=tenant,source='msmi',invoice_type='input',
                date_from=start,date_to=end,now_iso=stamp)
            # The complete in-memory snapshot has a different paging space.
            c.execute("UPDATE invoice_sync_batches SET source_cursor='{}' WHERE id=?",(batch['id'],))
            result=sync_input_batch(c,Snapshot(rows),batch['id'],stamp,max_pages=50,page_size=199)
            result.update(source, stock_changed=False)
            if not result['complete'] or result['review_required'] or result['error_count']:
                error='Còn hóa đơn thiếu hoặc sai dữ liệu nguồn; hệ thống sẽ tự thử lại. Xem phần Cần kiểm tra.'
            missing=c.execute('''SELECT COUNT(*) FROM msmi_invoices i WHERE tenant=? AND invoice_type=?
                AND invoice_date BETWEEN ? AND ? AND NOT EXISTS
                (SELECT 1 FROM msmi_invoice_items li WHERE li.invoice_id=i.id)''',(tenant,INPUT_INVOICE,start,end)).fetchone()[0]
            if missing: error='Còn hóa đơn chưa có dòng hàng; hệ thống sẽ tự đồng bộ bù chi tiết.'
    except (RefreshError,MsmiError) as exc:
        error=str(exc)
    except Exception:
        # Never expose payloads, account passwords, cookies or tax tokens.
        error='Đồng bộ tự động chưa hoàn tất; hệ thống sẽ thử lại. Cần kiểm tra nếu lỗi kéo dài.'
    finished=now_fn().astimezone(VN)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM automatic_input_sync WHERE tenant=?',(tenant,)).fetchone()
        if row['owner'] != owner: return {'superseded':True}
        failures=row['failures']+1 if error else 0
        _,next_slot=schedule(finished)
        retry=finished+timedelta(minutes=min(120,30*2**min(failures-1,2))) if error else next_slot
        next_attempt=min(retry,next_slot)
        result.update(date_from=start,date_to=end)
        c.execute('''UPDATE automatic_input_sync SET state=?,owner='',lease_until=NULL,
            last_success=?,next_attempt=?,failures=?,message=?,result_json=? WHERE tenant=?''',
            ('error' if error else 'success',row['last_success'] if error else finished.isoformat(),
             next_attempt.isoformat(),failures,error,json.dumps(result,ensure_ascii=False),tenant))
    return {'ok':not error,'error':error,'result':result}


def start_worker(server, *, interval=60):
    enabled=os.environ.get('TDP_AUTO_INPUT_SYNC','0')=='1'
    tax_code=os.environ.get('MSMI_SYNC_TAX_CODE','').strip()
    with server.db() as c:
        init_schema(c)
        tenant=server.setting_get(c,'tenant_code','TDP')
        c.execute('INSERT OR IGNORE INTO automatic_input_sync(tenant) VALUES(?)',(tenant,))
        c.execute('UPDATE automatic_input_sync SET enabled=? WHERE tenant=?',(int(enabled),tenant))
    stop=threading.Event()
    def loop():
        while not stop.wait(interval):
            try:
                run_due(server.db,tenant,server.create_msmi_client,
                    lambda:MsmiRefresh(os.environ.get('MSMI_USERNAME',''),os.environ.get('MSMI_PASSWORD',''),tax_code),tax_code)
            except Exception:
                print('Automatic input sync could not update its status; retrying.',flush=True)
    worker=threading.Thread(target=loop,name='tdp-auto-input-sync',daemon=True)
    worker.start()
    return stop,worker
