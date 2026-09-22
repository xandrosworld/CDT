"""Refresh purchase lists and missing details through the mSMI portal flow.

This is separate from OpenAPI listing: listing alone cannot repair empty
source stubs. No invoice issue, cancellation, tax-login or stock operations.
Portal contract observed in mSMI's own browser client, September 2026.
"""
import http.cookiejar
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError, URLError

BASE = 'https://qlhd.minvoice.com.vn/api/'
VN = timezone(timedelta(hours=7))


class RefreshError(RuntimeError):
    pass


class MsmiRefresh:
    def __init__(self, username, password, tax_code, *, opener=None, clock=time.monotonic):
        self.username, self.password, self.tax_code = username, password, tax_code
        self.opener = opener or build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.clock = clock
        self.deadline = clock() + 900

    def request(self, path, body=None, params=None):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise RefreshError('mSMI chưa hoàn tất trong thời gian chờ; sẽ tự thử lại.')
        url = BASE + path
        if params:
            url += '?' + urlencode(params)
        req = Request(url, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type':'application/json', 'Accept':'application/json',
                               'Origin':'https://qlhd.minvoice.com.vn'})
        try:
            with self.opener.open(req, timeout=min(200, remaining)) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code in (401, 403):
                raise RefreshError('Không đăng nhập được mSMI hoặc kết nối thuế đã hết hạn; cần kiểm tra tài khoản.') from None
            raise RefreshError(f'mSMI chưa đồng bộ được (HTTP {error.code}); sẽ tự thử lại.') from None
        except (URLError, OSError, ValueError):
            raise RefreshError('mSMI chưa phản hồi hợp lệ; sẽ tự thử lại.') from None

    def refresh(self, start, end):
        first, last = (datetime.strptime(d, '%Y-%m-%d').replace(tzinfo=VN) for d in (start,end))
        if not self.username or not self.password or not self.tax_code:
            raise RefreshError('Chưa cấu hình đủ tài khoản mSMI và mã số thuế cho đồng bộ tự động.')
        if not 0 <= (last-first).days <= 30:
            raise RefreshError('Khoảng đồng bộ mSMI phải nằm trong 31 ngày.')
        self.request('users/login', {'username':self.username, 'password':self.password})
        result = self.request('external_accounts', params={'lazyLoadEvent':json.dumps({'filters':{
            'visible':{'value':True,'matchMode':'equals'},
            'type':{'value':'hoadondientu-gov','matchMode':'equals'}}})})
        accounts = result.get('items',[]) if isinstance(result,dict) else []
        matches = [a for a in accounts if a.get('username') == self.tax_code]
        if len(matches) != 1:
            raise RefreshError('Hồ sơ thuế mSMI chưa kết nối hoặc không khớp mã số thuế đã cấu hình.')
        if not matches[0].get('token'):
            raise RefreshError('Kết nối thuế trên mSMI đã hết phiên. Mở mSMI, chọn hồ sơ thuế '+self.tax_code+
                ', đăng nhập lại kết nối thuế, rồi quay lại bấm “Tải/tiếp tục đầu vào”. Hóa đơn đã tải và dữ liệu nhập kho vẫn được giữ nguyên.')
        a = matches[0]
        if not a.get('sync_invoices_purchase',{}).get('sync'):
            raise RefreshError('Hồ sơ mSMI chưa bật đồng bộ hóa đơn mua vào.')
        account = str(a['_id'])
        if not account.isalnum():
            raise RefreshError('Mã hồ sơ mSMI không hợp lệ.')
        user = a.get('user')
        if isinstance(user,dict): user = user.get('_id')
        common = dict(user=user, account=account, username=a['username'],
                      password=a.get('password'), token=a['token'],
                      taxCodeCrawl=(a.get('profile') or {}).get('groupId') or a['username'],
                      fromDate=first.strftime('%d/%m/%YT00:00:00'),
                      toDate=last.strftime('%d/%m/%YT23:59:59'))
        session = uuid.uuid4().hex[:24]
        for kind in ('purchase','purchase_sco'):
            response = self.request('crawl-api/build-request', dict(common,
                crawlType='excel', invoiceType=kind, trigger_id=session, manualSessionId=session,
                nbmst=None, khhdon=None, shdon=None, khmshdon=None))
            # The portal returns an array of received headers. Never mistake
            # an HTTP-200 error object or legacy request recipe for completion.
            if not isinstance(response,list):
                raise RefreshError('mSMI chưa xác nhận tải xong danh sách hóa đơn; sẽ tự thử lại.')
        utc_text = lambda value: value.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        params = {'from':utc_text(first), 'to':utc_text(last+timedelta(days=1,microseconds=-1000)), 'type':'detail'}
        path = f'invoices/account/{account}/type/purchase/sync'
        missing = self.request(path, params=params)
        if not isinstance(missing,list):
            raise RefreshError('mSMI chưa trả được danh sách hóa đơn thiếu chi tiết.')
        repaired = 0
        for item in missing:
            if item.get('type') != 'purchase':
                raise RefreshError('mSMI trả hóa đơn không thuộc đầu vào; đã dừng đồng bộ.')
            keys = item.get('keys') or {}
            if not all(keys.get(k) is not None for k in ('nbmst','khhdon','shdon','khmshdon')):
                raise RefreshError('mSMI thiếu định danh để tải chi tiết; sẽ tự thử lại.')
            source = item.get('from','query')
            kind = 'purchase' if source == 'query' else 'purchase_sco'
            self.request('crawl-api/build-request', dict(common, crawlType='detail',
                invoiceType=kind, nbmst=keys['nbmst'], khhdon=keys['khhdon'],
                shdon=str(keys['shdon']), khmshdon=str(keys['khmshdon']), invoiceKey=item.get('key')))
            repaired += 1
        remaining = self.request(path, params=params)
        if not isinstance(remaining,list) or remaining:
            raise RefreshError('mSMI vẫn còn hóa đơn thiếu chi tiết; sẽ tự thử lại.')
        return {'source_ready':True,'repaired_details':repaired}
