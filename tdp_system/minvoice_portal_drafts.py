"""Unsigned portal creation using the provider's ABP API contract.

Verified against GET /api/api/abp/api-definition and the portal InvoiceService
on 2026-09-14. POST app/invoice is separate from sign/send-tax endpoints.
No generic write method, signing, replacement, deletion or email is exposed.
"""
import re
from urllib.parse import quote

try:
    from .minvoice_client import MinvoiceError, MinvoiceOutcomeUnknown
except ImportError:
    from minvoice_client import MinvoiceError, MinvoiceOutcomeUnknown


class PortalDrafts:
    @staticmethod
    def _guard_unsigned_payload(p):
        if (not isinstance(p, dict) or p.get('invoiceStatus') != 0 or p.get('sendTaxStatus') != 0
                or p.get('invoiceNumber') is not None or p.get('sendEmail') is not False
                or not re.fullmatch(r'TDP-[A-Z0-9]{12}-[A-Z0-9]{32}', str(p.get('keyApi', '')))
                or p.get('orderNumber') != p.get('keyApi') or not p.get('invoiceDetail')
                or any(p.get(k) for k in ('invoiceId', 'relatedInvoiceId', 'relatedInvoiceIds',
                                         'relatedInvoiceListId', 'taxAuthorityCode', 'dateSign', 'userSign'))):
            raise MinvoiceError('Chỉ gửi bản nháp mới, chưa ký, có khóa chống trùng của bảng kê đã kiểm tra.')

    def _catalog(self, path):
        rows, offset, total = [], 0, 1
        while offset < total:
            page = self._portal_json('GET', path, params={'MaxResultCount': 100, 'SkipCount': offset})
            items, total = self._page(page, offset)
            rows.extend(items); offset += len(items)
            if total > 10000:
                raise MinvoiceError('Danh mục portal vượt giới hạn đối chiếu.')
        return rows

    @staticmethod
    def _one(rows, field, value, label):
        found = [r for r in rows if str(r.get(field, '')).strip().casefold() == str(value).strip().casefold()]
        if len(found) != 1 or not found[0].get('id'):
            raise MinvoiceError('Chưa xác định duy nhất '+label+' trên M-Invoice.')
        return found[0]

    def portal_draft_payload(self, draft):
        n = self._normalize_draft(draft)
        if n['currency'] != 'VND' or n['discount_total']:
            raise MinvoiceError('Bảng kê gửi trực tiếp dùng VND và các dòng chưa chiết khấu.')
        self._ensure_login()
        if not self._can_create:
            raise MinvoiceError('Tài khoản M-Invoice chưa có quyền tạo hóa đơn.')
        register = self._one(self._catalog('app/register-invoice/using-list'), 'symbolCode', n['series'], 'ký hiệu')
        if int(register.get('invoiceYear') or 0) % 100 != int(n['invoice_date'][:4]) % 100:
            raise MinvoiceError('Ký hiệu không đúng năm hóa đơn.')
        if register.get('typeCompany') not in (None, 0):
            raise MinvoiceError('Mẫu hóa đơn đặc thù cần lập trên portal; hãy dùng file Excel.')
        company = self._one(self._catalog('app/tenant-company'), 'taxCode', self.tax_code, 'công ty bán')
        if not company.get('name') or not company.get('address'):
            raise MinvoiceError('Thông tin công ty bán trên M-Invoice chưa đầy đủ.')
        currency = self._one(self._catalog('app/currency'), 'code', n['currency'], 'tiền tệ')
        payment = self._one(self._catalog('app/payment-type'), 'name', n['payment_method'], 'hình thức thanh toán')
        taxes = self._catalog('app/tax')
        lines = []
        for i, line in enumerate(n['lines'], 1):
            if line['tchat'] not in (1, 2):
                raise MinvoiceError('Gửi bảng kê chỉ hỗ trợ dòng hàng bán và khuyến mại.')
            tax = self._one(taxes, 'code', line['ma_thue'], 'thuế suất')
            lines.append({
                'ordinalNumber': str(i), 'property': line['tchat'], 'isShowOrder': True,
                'productCode': line['inv_itemCode'], 'productName': line['inv_itemName'],
                'unitCode': line['inv_unitCode'], 'quantity': line['inv_quantity'],
                'unitPrice': line['inv_unitPrice'], 'amount': line['inv_TotalAmountWithoutVat'],
                'amountWithoutVAT': line['inv_TotalAmountWithoutVat'], 'vatAmount': line['inv_vatAmount'],
                'totalAmount': line['inv_TotalAmount'], 'discountAmount': 0, 'discountRate': 0,
                'taxId': tax['id'], 'vatCode': tax['code'], 'vatName': tax['name'], 'vatRate': tax['taxValue'],
            })
        buyer = n['buyer']
        try:
            from .invoice_payment_documents import number_to_vietnamese
        except ImportError:
            from invoice_payment_documents import number_to_vietnamese
        payload = {
            'registerInvoiceId': register['id'], 'invoiceSerial': n['series'],
            'invoiceDate': n['invoice_date'], 'invoiceStatus': 0, 'sendTaxStatus': 0,
            'invoiceNumber': None, 'sendEmail': False, 'signOnly': False,
            'currencyId': currency['id'], 'currencyCode': n['currency'], 'exchangeRate': self._json_number(n['exchange_rate']),
            'paymenType': payment['id'], 'paymentMethod': payment['name'],
            'tenantCompanyId': company['id'], 'sellerTaxCode': company['taxCode'],
            'sellerLegalName': company['name'], 'sellerAddress': company['address'],
            'buyerLegalName': buyer['legal_name'], 'buyerDisplayName': buyer['display_name'],
            'buyerTaxCode': buyer['tax_code'], 'buyerAddress': buyer['address'], 'buyerEmail': buyer['email'],
            'totalAmountWithoutVAT': self._json_number(n['subtotal']), 'vatAmount': self._json_number(n['tax_amount']),
            'totalAmount': self._json_number(n['total_amount']), 'totalDiscountAmount': 0,
            'totalAmountToWord': number_to_vietnamese(n['total_amount']),
            'keyApi': n['key_api'], 'orderNumber': n['key_api'], 'invoiceNote': n['order_number'],
            'isPaymented': False, 'paidAmount': 0, 'invoiceDetail': lines,
        }
        self._guard_unsigned_payload(payload)
        return payload

    def get_invoice_info(self, *, key_api):
        if not re.fullmatch(r'TDP-[A-Z0-9]{12}-[A-Z0-9]{32}', str(key_api)):
            raise MinvoiceError('Khóa đối soát bản nháp không hợp lệ.')
        self._ensure_login()
        rows, offset, total = [], 0, 1
        while offset < total:
            page = self._portal_json('GET', 'app/invoice', params={
                'OrderNumber': key_api, 'SkipCount': offset, 'MaxResultCount': 100})
            items, total = self._page(page, offset)
            rows.extend(items); offset += len(items)
            if total > 1000:raise MinvoiceError('Không thu hẹp được bản nháp cần đối soát.')
        exact = [r for r in rows if r.get('orderNumber') == key_api]
        if len(exact) > 1:raise MinvoiceError('Có nhiều bản nháp trùng khóa; cần đối chiếu trên M-Invoice.')
        if not exact:
            if rows:raise MinvoiceError('Portal trả sai khóa đối soát; chưa thể xác nhận bản nháp chưa tồn tại.')
            return {'found': False, 'data': None}
        remote_id = exact[0].get('id')
        if not re.fullmatch(r'[0-9a-fA-F-]{36}', str(remote_id)):
            raise MinvoiceError('Portal trả định danh bản nháp không hợp lệ.')
        detail = self._portal_json('GET', 'app/invoice/'+quote(remote_id, safe='')+'/detail')
        if (detail.get('id') != remote_id or detail.get('sellerTaxCode') != self.tax_code
                or detail.get('keyApi') not in (None, '', key_api) or detail.get('orderNumber') != key_api
                or not isinstance(detail.get('invoiceDetail'), list)):
            raise MinvoiceError('Bản nháp trả về không khớp công ty hoặc khóa đối soát.')
        try:
            from .minvoice_portal import normalize_portal_document
        except ImportError:
            from minvoice_portal import normalize_portal_document
        return {'found': True, 'data': normalize_portal_document(detail)}

    def create_draft(self, draft, *, dry_run=True, confirm_remote_write=False):
        if not dry_run and confirm_remote_write is not True:
            raise MinvoiceError('Cần xác nhận trước khi gửi bản nháp lên M-Invoice.')
        payload = self.portal_draft_payload(draft)
        if dry_run:
            return {'ok': True, 'dry_run': True, 'remote_write': False, 'endpoint': '/api/api/app/invoice',
                    'payload': {'data': [payload]}, 'requires_user_sign_and_issue': True}
        prior = self.get_invoice_info(key_api=payload['keyApi'])
        if prior['found']:
            # The route performs the full amount/line reconciliation on a retry.
            raise MinvoiceOutcomeUnknown('Bản nháp đã tồn tại; đối soát khóa trước khi gửi tiếp.')
        try:
            result = self._portal_json('POST', 'app/invoice', payload=payload, allow_draft_write=True)
            remote_id = result.get('id')
            if not re.fullmatch(r'[0-9a-fA-F-]{36}', str(remote_id)):
                raise ValueError('Missing draft id')
            detail = self._portal_json('GET', 'app/invoice/'+quote(remote_id, safe='')+'/detail')
            fields = ('id', 'orderNumber', 'sellerTaxCode', 'invoiceSerial', 'invoiceStatus',
                      'buyerTaxCode','buyerLegalName','buyerDisplayName','buyerAddress',
                      'totalAmountWithoutVAT', 'vatAmount', 'totalAmount')
            expected = {**payload, 'id': remote_id}
            try:from .minvoice_portal import portal_date
            except ImportError:from minvoice_portal import portal_date
            # Current portal normalizes a new draft to tax status 1 (chờ ký),
            # and keeps our reference in orderNumber while keyApi is null.
            if (any(detail.get(k) != expected[k] for k in fields)
                    or detail.get('keyApi') not in (None, '', payload['keyApi'])
                    or portal_date(detail.get('invoiceDate')) != payload['invoiceDate']
                    or type(detail.get('sendTaxStatus')) is not int or detail['sendTaxStatus'] not in (0,1)
                    or detail.get('invoiceNumber') is not None or detail.get('dateSign') or detail.get('taxAuthorityCode')):
                raise ValueError('Saved draft needs reconciliation')
            for key in ('productCode', 'productName', 'unitCode', 'quantity', 'unitPrice', 'amountWithoutVAT', 'vatCode', 'property'):
                if [r.get(key) for r in detail.get('invoiceDetail', [])] != [r.get(key) for r in payload['invoiceDetail']]:
                    raise ValueError('Saved draft lines changed')
        except Exception as exc:
            raise MinvoiceOutcomeUnknown('Chưa xác nhận kết quả gửi bản nháp. Cần đối soát trước khi thử lại.') from exc
        return {'ok': True, 'dry_run': False, 'remote_write': True, 'data': detail,
                'requires_user_sign_and_issue': True}
