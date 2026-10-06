import unittest
from unittest.mock import patch,MagicMock
from http.cookiejar import CookieJar
from http.client import RemoteDisconnected
from urllib.request import Request
from urllib.error import HTTPError
from .minvoice_read_pool import DetailReadPool


class DetailReadPoolTests(unittest.TestCase):
    def request(self,host='tenant.minvoice.net',method='GET'):
        return Request('https://'+host+'/api/api/app/invoice/abc/detail',method=method)

    @patch('tdp_system.minvoice_read_pool.HTTPSConnection')
    def test_reuses_connection_and_closes_at_end(self,constructor):
        response=constructor.return_value.getresponse.return_value
        response.status=200
        pool=DetailReadPool('tenant.minvoice.net',CookieJar())
        pool.open(self.request(),25);pool.open(self.request(),25)
        constructor.assert_called_once_with('tenant.minvoice.net',timeout=25)
        self.assertEqual(constructor.return_value.request.call_count,2)
        pool.close();constructor.return_value.close.assert_called_once()

    @patch('tdp_system.minvoice_read_pool.HTTPSConnection')
    def test_reconnects_once_for_closed_keepalive(self,constructor):
        first,second=MagicMock(),MagicMock();constructor.side_effect=[first,second]
        first.getresponse.side_effect=RemoteDisconnected();second.getresponse.return_value.status=200
        pool=DetailReadPool('tenant.minvoice.net',CookieJar());pool.open(self.request(),25)
        self.assertEqual(constructor.call_count,2);first.close.assert_called_once();pool.close()

    @patch('tdp_system.minvoice_read_pool.HTTPSConnection')
    def test_rejects_redirect_without_retry_and_cross_host_or_write(self,constructor):
        constructor.return_value.getresponse.return_value.status=302
        pool=DetailReadPool('tenant.minvoice.net',CookieJar())
        with self.assertRaises(HTTPError):pool.open(self.request(),25)
        self.assertEqual(constructor.call_count,1)
        for req in [self.request('other.minvoice.net'),self.request(method='POST')]:
            with self.assertRaises(ValueError):pool.open(req,25)
        self.assertEqual(constructor.call_count,1);pool.close()
