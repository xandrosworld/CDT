"""Read connector for the tenant-cookie M-Invoice portal (.minvoice.net).

Contract checked against the portal's public InvoiceService / ServiceBase and
read-only responses. This is distinct from the legacy bearer-token API.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from http.cookiejar import Cookie, CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

try:
    from .minvoice_client import MinvoiceClient, MinvoiceError
    from .minvoice_portal_drafts import PortalDrafts
except ImportError:
    from minvoice_client import MinvoiceClient, MinvoiceError
    from minvoice_portal_drafts import PortalDrafts


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A login page or another host is not a successful JSON response.
        return None


def portal_date(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo:
            result = result.astimezone(timezone(timedelta(hours=7)))
        return result.date().isoformat()
    except (ValueError, TypeError):
        raise MinvoiceError("Portal M-Invoice trả ngày hóa đơn không hợp lệ") from None


def portal_status(remote):
    """Keep the portal's status enums separate: 5=adjusted, 6=replaced."""
    document, tax = remote.get("invoiceStatus"), remote.get("sendTaxStatus")
    raw = json.dumps({"invoiceStatus": document, "sendTaxStatus": tax}, sort_keys=True)
    status = "unknown"
    if type(document) is int and type(tax) is int:
        if document in {1, 2, 3, 5, 6}:
            status = {1: "cancelled", 2: "adjusted", 3: "replaced", 5: "adjusted", 6: "replaced"}[document]
        elif document == 0 and tax == 4:
            status = "issued"
        elif document == 0 and tax in {0, 1, 2, 3, 6}:
            status = "draft"
    return raw, status, "minvoice_portal.invoiceStatus+sendTaxStatus"


def portal_document_role(remote):
    """Preserve the distinction between a new related document and its original."""
    code = remote.get('invoiceStatus')
    if type(code) is not int:
        return 'unknown'
    return {0:'original',1:'cancelled',2:'adjustment',3:'replacement',
            5:'adjusted_original',6:'replaced_original'}.get(code,'unknown')


class MinvoicePortalClient(PortalDrafts, MinvoiceClient):
    def __init__(self, config, timeout=25):
        super().__init__(config, timeout)
        parsed = urlsplit(config.api_base_url)
        if (parsed.scheme != "https" or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or parsed.username or parsed.port
                or not re.fullmatch(r"\d{10}(?:-\d{3})?\.minvoice\.net", parsed.hostname or "")):
            raise MinvoiceError("Portal M-Invoice cần URL HTTPS dạng https://MST.minvoice.net, không kèm #/hoa-don")
        self.tax_code = parsed.hostname.split(".")[0]
        self._host = parsed.hostname
        self._cookies = CookieJar()
        self._can_create = False
        self._opener = build_opener(HTTPCookieProcessor(self._cookies), _NoRedirect())

    @property
    def supports_remote_drafts(self):
        return True

    def _portal_json(self, method, path, *, payload=None, params=None, allow_draft_write=False):
        draft_write = (method, path) == ('POST', 'app/invoice') and allow_draft_write is True
        if draft_write:
            self._guard_unsigned_payload(payload)
            if not self._can_create:
                raise MinvoiceError('Tài khoản M-Invoice chưa có quyền tạo hóa đơn.')
        elif method != "GET" and (method, path) != ("POST", "account/login"):
            raise MinvoiceError("Thao tác ghi portal chưa được xác nhận hoặc không được hỗ trợ")
        url = self.config.api_base_url.rstrip("/") + "/api/api/" + path
        if params:
            url += "?" + urlencode(params)
        headers = {"Accept": "application/json", "Origin": self.config.api_base_url,
                   "Referer": self.config.api_base_url + "/"}
        if draft_write:
            from urllib.parse import unquote
            for cookie in self._cookies:
                if cookie.name == 'XSRF-TOKEN':
                    headers['RequestVerificationToken'] = unquote(cookie.value)
                    headers['X-XSRF-TOKEN'] = unquote(cookie.value)
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            with self._opener.open(Request(url, data=body, headers=headers, method=method), timeout=self.timeout) as response:
                if "json" not in response.headers.get("Content-Type", "").lower():
                    raise MinvoiceError("Portal M-Invoice trả trang web thay vì dữ liệu; cần kiểm tra lại phiên đăng nhập")
                result = json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as error:
            raise MinvoiceError(f"Portal M-Invoice trả lỗi HTTP {error.code}") from None
        except (URLError, OSError):
            raise MinvoiceError("Không kết nối được portal M-Invoice") from None
        except (UnicodeDecodeError, ValueError):
            raise MinvoiceError("Portal M-Invoice trả dữ liệu không hợp lệ") from None
        if not isinstance(result, dict):
            raise MinvoiceError("Portal M-Invoice trả cấu trúc không hợp lệ")
        return result

    def _json(self, *args, **kwargs):
        # Never fall through to a legacy endpoint, including remote draft Save.
        raise MinvoiceError("Thao tác API cũ không dùng được với portal mới. Hãy tải file để nhập lên M-Invoice.")

    def login(self):
        self._token = ""
        self._can_create = False
        self._cookies.clear()
        tenant = self._portal_json("GET", "abp/multi-tenancy/tenants/by-name/" + self.tax_code)
        tenant_id = tenant.get("tenantId")
        if tenant.get("success") is not True or tenant.get("isActive") is not True or not isinstance(tenant_id, str):
            raise MinvoiceError("Không xác định được công ty trên portal M-Invoice")
        self._cookies.set_cookie(Cookie(0, "__tenant", tenant_id, None, False, self._host,
                                       True, False, "/", True, True, None, True, None, None, {}))
        result = self._portal_json("POST", "account/login", payload={
            "userNameOrEmailAddress": self.config.username, "password": self.config.password, "rememberMe": False,
        })
        if type(result.get("result")) is not int or result["result"] != 1:
            raise MinvoiceError("Portal M-Invoice từ chối đăng nhập vào công ty đã chọn")
        profile = self._portal_json("GET", "abp/application-configuration")
        if (profile.get("currentUser", {}).get("isAuthenticated") is not True
                or profile.get("currentTenant", {}).get("id") != tenant_id):
            raise MinvoiceError("Phiên đăng nhập M-Invoice chưa khớp công ty đã chọn")
        self._token = "cookie-session-verified"
        self._can_create = profile.get('auth', {}).get('grantedPolicies', {}).get('MInvoice.InvoiceManagement.Create') is True
        return True

    def profile_status(self):
        self._ensure_login()
        return {"authenticated": True, "credential_verified": True, "official_api": False,
                "connection_mode": "portal", "company_tax_code": self.tax_code,
                "test_environment": False, "test_environment_allowed": False,
                "draft_save_available": self._can_create}

    def outgoing_summary(self):
        result = super().outgoing_summary()
        result["official_api"] = False
        return result

    def get_invoice_series(self):
        self._ensure_login()
        rows, offset, total = [], 0, 1
        while offset < total:
            result = self._portal_json("GET", "app/register-invoice/using-list",
                                       params={"MaxResultCount": 100, "SkipCount": offset})
            items, total = self._page(result, offset)
            rows.extend({"value": i.get("symbolCode"), "invoiceYear": i.get("invoiceYear")} for i in items)
            offset += len(items)
            if offset > 10000:
                raise MinvoiceError("Danh sách ký hiệu M-Invoice vượt giới hạn kiểm tra")
        return rows

    @staticmethod
    def _page(result, offset):
        items, total = result.get("items"), result.get("totalCount")
        if (not isinstance(items, list) or any(not isinstance(i, dict) for i in items)
                or type(total) is not int or total < offset + len(items)
                or (not items and offset < total)):
            raise MinvoiceError("Portal M-Invoice trả phân trang không nhất quán")
        return items, total

    def get_outgoing_invoice(self, *, remote_id, series, number, invoice_date):
        """Read one known document; never search by number alone or write upstream."""
        if not isinstance(remote_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", remote_id):
            raise MinvoiceError("Không xác định được hóa đơn cần kiểm tra")
        self._ensure_login()
        detail = self._portal_json("GET", "app/invoice/" + quote(remote_id, safe="") + "/detail")
        if (detail.get("id") != remote_id or detail.get("sellerTaxCode") != self.tax_code
                or detail.get("invoiceSerial") != series
                or str(detail.get("invoiceNumber")) != str(number)
                or portal_date(detail.get("invoiceDate")) != portal_date(invoice_date)):
            raise MinvoiceError("Hóa đơn trả về khác công ty, ký hiệu, số hoặc ngày. Chưa cập nhật dữ liệu.")
        if not isinstance(detail.get("invoiceDetail"), list):
            raise MinvoiceError("M-Invoice chưa trả đủ chi tiết hóa đơn. Hãy thử lại.")
        return normalize_portal_document(detail)

    def get_issued_invoice_pdf(self, *, remote_id, series, number, invoice_date,
                               buyer_tax_code, subtotal, tax_amount, total_amount):
        """Download the provider's original PDF after checking the issued identity."""
        import io
        from pypdf import PdfReader
        if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", str(remote_id)):
            raise MinvoiceError('Hóa đơn chưa có định danh M-Invoice hợp lệ để tải PDF.')
        detail = self.get_outgoing_invoice(remote_id=remote_id, series=series,
                                          number=number, invoice_date=invoice_date)
        if (portal_status(detail)[1] != 'issued'
                or str(detail.get('buyerTaxCode') or '').strip() != str(buyer_tax_code).strip()):
            raise MinvoiceError('Trạng thái hoặc người mua của hóa đơn đã thay đổi; hãy tải lại hóa đơn đầu ra.')
        try:
            amounts = [('totalAmountWithoutVAT', subtotal), ('vatAmount', tax_amount), ('totalAmount', total_amount)]
            if any(not Decimal(str(detail[key])).is_finite()
                   or abs(Decimal(str(detail[key])) - Decimal(str(expected))) > Decimal('1')
                   for key, expected in amounts):
                raise ValueError()
        except (KeyError, ValueError, InvalidOperation):
            raise MinvoiceError('Số tiền hóa đơn đã thay đổi; hãy tải lại hóa đơn đầu ra trước khi lấy PDF.') from None
        # Spelling is from the tenant portal's InvoiceAppService API definition.
        url = self.config.api_base_url.rstrip('/') + '/api/api/app/invoice/' + remote_id + '/downloaf-pdf'
        try:
            with self._opener.open(Request(url, headers={
                'Accept': 'application/pdf', 'Referer': self.config.api_base_url + '/',
            }), timeout=self.timeout) as response:
                content = response.read(20 * 1024 * 1024 + 1)
                if len(content) > 20 * 1024 * 1024 or not content.startswith(b'%PDF-'):
                    raise MinvoiceError('M-Invoice chưa trả PDF hợp lệ hoặc file vượt 20 MB; hãy thử lại.')
        except HTTPError as error:
            raise MinvoiceError(f'Không tải được PDF từ M-Invoice (HTTP {error.code}); hãy thử lại.') from None
        except (URLError, OSError):
            raise MinvoiceError('Mất kết nối khi tải PDF hóa đơn; hãy thử lại.') from None
        try:
            pdf = PdfReader(io.BytesIO(content))
            if pdf.is_encrypted or not len(pdf.pages):
                raise ValueError()
        except Exception:
            raise MinvoiceError('PDF M-Invoice bị lỗi hoặc không đọc được; chưa tải hồ sơ thiếu.') from None
        return content

    def get_outgoing_invoices(self, start_date, end_date, series, start=0, count=300, include_details=True):
        self._ensure_login()
        start_date, end_date = portal_date(start_date), portal_date(end_date)
        if not series or start_date > end_date:
            raise MinvoiceError("Cần ký hiệu và khoảng ngày hóa đơn hợp lệ")
        offset = max(0, int(start))
        result = self._portal_json("GET", "app/invoice", params={
            "fromDate": start_date, "toDate": end_date, "invoiceSerial": series,
            "SkipCount": offset, "MaxResultCount": max(1, min(int(count), 100)),
            "Sorting": "invoiceDate", "SortType": "ASCEND",
        })
        rows, total = self._page(result, offset)
        output, seen = [], set()
        for row in rows:
            remote_id = row.get("id")
            if not isinstance(remote_id, str) or not re.fullmatch(r"[0-9a-fA-F-]{36}", remote_id) or remote_id in seen:
                raise MinvoiceError("Portal M-Invoice trả định danh trùng hoặc không hợp lệ")
            seen.add(remote_id)
            if include_details:
                detail = self._portal_json("GET", "app/invoice/" + quote(remote_id, safe="") + "/detail")
                if detail.get("id") != remote_id or any(detail.get(k) != row.get(k) for k in (
                        "invoiceSerial", "invoiceNumber", "invoiceDate", "totalAmountWithoutVAT", "vatAmount", "totalAmount",
                        "invoiceStatus", "sendTaxStatus")):
                    raise MinvoiceError("Hóa đơn M-Invoice thay đổi trong lúc đọc; hãy tải lại")
            else:
                detail = row
            if (detail.get("sellerTaxCode") != self.tax_code or detail.get("invoiceSerial") != series
                    or not start_date <= portal_date(detail.get("invoiceDate")) <= end_date):
                raise MinvoiceError("Portal M-Invoice trả hóa đơn khác công ty, ký hiệu hoặc khoảng ngày đã chọn")
            if include_details and not isinstance(detail.get("invoiceDetail"), list):
                raise MinvoiceError("Portal M-Invoice thiếu chi tiết hóa đơn")
            output.append(normalize_portal_document(detail))
        return {"ok": True, "code": "00", "data": output, "total": total}


def normalize_portal_document(detail):
    """Retain original fields and add explicit aliases for the shared pipeline."""
    result = dict(detail)
    result.update(_tdp_source_contract="minvoice_portal_v1", inv_invoiceSeries=detail.get("invoiceSerial"),
                  subtotal=detail.get("totalAmountWithoutVAT"), taxAmount=detail.get("vatAmount"),
                  inv_buyerLegalName=detail.get("buyerLegalName") or detail.get("buyerDisplayName"),
                  inv_buyerAddressLine=detail.get("buyerAddress"))
    result["details"] = [dict(line, inv_itemCode=line.get("productCode"), inv_itemName=line.get("productName"),
                              inv_unitCode=line.get("unitCode"), inv_TotalAmountWithoutVat=line.get("amountWithoutVAT"),
                              ma_thue=line.get("vatCode"), tchat=line.get("property"))
                         for line in detail.get("invoiceDetail", [])]
    return result


def portal_validation_error(remote):
    """A successful tax status cannot override inconsistent source amounts."""
    def number(value):
        if value is None or isinstance(value, bool):
            raise ValueError()
        n = Decimal(str(value))
        if not n.is_finite():
            raise ValueError()
        return n
    try:
        lines = remote["invoiceDetail"]
        if not isinstance(lines, list) or not lines:
            return "Portal chưa cung cấp đủ dòng chi tiết; cần đối chiếu nguồn"
        subtotal, tax, total = (number(remote[k]) for k in ("totalAmountWithoutVAT", "vatAmount", "totalAmount"))
        line_amount = sum(number(line["amountWithoutVAT"]) for line in lines)
        line_tax = sum(number(line["vatAmount"]) for line in lines)
        if abs(line_amount - subtotal) > 1 or abs(line_tax - tax) > 1 or abs(subtotal + tax - total) > 1:
            try:
                from .invoice_output_editing import PORTAL_TOTAL_MISMATCH
            except ImportError:
                from invoice_output_editing import PORTAL_TOTAL_MISMATCH
            return PORTAL_TOTAL_MISMATCH
        if any(type(line.get("property")) is not int or line["property"] not in {1, 2, 5} for line in lines):
            return "Hóa đơn có loại dòng chiết khấu/diễn giải hoặc chưa rõ; cần đối chiếu trước khi ghi kho"
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return "Portal trả số liệu chi tiết chưa đủ hoặc không hợp lệ; cần đối chiếu nguồn"
    return ""
