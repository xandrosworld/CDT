"""Per-page HTTPS keep-alive connections for read-only invoice details."""
from http.client import HTTPSConnection, HTTPException
from threading import local, Lock
from urllib.error import HTTPError
from urllib.parse import urlsplit


class DetailReadPool:
    def __init__(self, host, cookies):
        self.host=host
        self.cookies=cookies
        self.local=local()
        self.lock=Lock()
        self.connections=[]

    def open(self, request, timeout):
        url=urlsplit(request.full_url)
        if (request.get_method()!='GET' or url.scheme!='https' or url.netloc!=self.host
                or not url.path.startswith('/api/api/app/invoice/') or not url.path.endswith('/detail')
                or url.query or request.data is not None):
            raise ValueError('Read pool accepts only same-host invoice detail GET requests')
        self.cookies.add_cookie_header(request)
        for attempt in range(2):
            conn=getattr(self.local,'connection',None)
            if conn is None:
                conn=HTTPSConnection(self.host,timeout=timeout)
                self.local.connection=conn
                with self.lock:self.connections.append(conn)
            try:
                conn.request('GET',url.path,headers=dict(request.header_items()))
                response=conn.getresponse()
                if response.status>=300:
                    # Never follow a redirect or retry provider HTTP errors.
                    error=HTTPError(request.full_url,response.status,response.reason,response.headers,None)
                    response.close();conn.close();self.local.connection=None
                    raise error
                self.cookies.extract_cookies(response,request)
                return response
            except HTTPError:
                raise
            except (OSError,HTTPException):
                conn.close();self.local.connection=None
                if attempt:raise

    def close(self):
        for conn in self.connections:conn.close()
