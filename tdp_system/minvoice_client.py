from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.client import HTTPException
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class MinvoiceError(RuntimeError):
    """A sanitized M-Invoice connection error safe to return to the local UI."""


class MinvoiceOutcomeUnknown(MinvoiceError):
    """The Save request may have reached M-Invoice and must be reconciled."""


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass(frozen=True)
class MinvoiceConfig:
    api_base_url: str
    username: str
    password: str
    unit_code: str = "VP"
    allow_test_environment: bool = False
    api_mode: str = "legacy"

    @classmethod
    def from_env_files(cls, paths: list[Path]) -> "MinvoiceConfig":
        values: dict[str, str] = {}
        for path in paths:
            values.update(_read_env_file(path))
        values.update({key: value for key, value in os.environ.items() if key.startswith('MINVOICE_')})
        required = {
            "MINVOICE_API_BASE_URL": values.get("MINVOICE_API_BASE_URL", ""),
            "MINVOICE_USERNAME": values.get("MINVOICE_USERNAME", ""),
            "MINVOICE_PASSWORD": values.get("MINVOICE_PASSWORD", ""),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise MinvoiceError("Thiếu cấu hình kết nối M-Invoice: " + ", ".join(missing))
        return cls(
            api_base_url=required["MINVOICE_API_BASE_URL"].rstrip("/"),
            username=required["MINVOICE_USERNAME"],
            password=required["MINVOICE_PASSWORD"],
            unit_code=values.get("MINVOICE_UNIT_CODE", "VP") or "VP",
            allow_test_environment=values.get("MINVOICE_ALLOW_TEST_ENVIRONMENT", "").strip().lower() in {"1", "true", "yes"},
            api_mode=values.get("MINVOICE_API_MODE", "legacy").strip().lower() or "legacy",
        )


class MinvoiceClient:
    """M-Invoice 2.0 client with explicit safeguards around remote writes.

    Reading series/invoices is always available. Creating a remote invoice is
    deliberately opt-in twice: ``create_draft`` defaults to ``dry_run=True``
    and also requires ``confirm_remote_write=True`` before it can call the
    documented ``InvoiceApi78/Save`` endpoint. This client never signs or
    issues an invoice.
    """

    DRAFT_SAVE_PATH = "InvoiceApi78/Save"
    INVOICE_INFO_PATH = "InvoiceApi78/GetInfoInvoice"
    _TAX_CODES = {"0", "5", "8", "10", "-1", "-2"}
    _SIX_PLACES = Decimal("0.000001")

    def __init__(self, config: MinvoiceConfig, timeout: int = 25):
        if config.api_mode not in {"legacy", "portal"}:
            raise MinvoiceError("MINVOICE_API_MODE phải là legacy hoặc portal")
        self.config = config
        self.timeout = timeout
        self._token = ""

    @property
    def supports_remote_drafts(self):
        return True

    def _json(self, method: str, path: str, payload=None, params=None, authenticated=False):
        url = self.config.api_base_url + "/api/" + path.lstrip("/")
        if params:
            url += "?" + urlencode(params)
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            self._ensure_login()
            headers["Authorization"] = "Bearer " + self._token
        try:
            with urlopen(Request(url, data=body, headers=headers, method=method), timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as error:
            raise MinvoiceError(f"M-Invoice trả lỗi HTTP {error.code}") from None
        except (URLError, OSError, HTTPException):
            raise MinvoiceError("Không kết nối được máy chủ M-Invoice") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MinvoiceError("M-Invoice trả dữ liệu không đúng định dạng") from None

    def login(self):
        result = self._json("POST", "Account/Login", {
            "username": self.config.username,
            "password": self.config.password,
            # The test API rejects these credentials if ma_dvcs is omitted,
            # although the current document labels this field as optional.
            "ma_dvcs": self.config.unit_code,
        })
        token = str(result.get("token") or "")
        if not (result.get("ok") and result.get("code") == "00" and token):
            raise MinvoiceError("M-Invoice API từ chối tài khoản, mật khẩu hoặc mã đơn vị")
        self._token = token
        return True

    def _ensure_login(self):
        if not self._token:
            self.login()

    def profile_status(self) -> dict:
        self._ensure_login()
        return {"authenticated": True, "credential_verified": True, "official_api": True,
                "test_environment": self.is_test_environment,
                "test_environment_allowed": self.config.allow_test_environment,
                "draft_save_available": not self.is_test_environment or self.config.allow_test_environment}

    @property
    def is_test_environment(self) -> bool:
        return (urlsplit(self.config.api_base_url).hostname or '').lower() == '0106026495-999.minvoice.site'

    def assert_business_environment(self) -> None:
        if self.is_test_environment and not self.config.allow_test_environment:
            raise MinvoiceError('M-Invoice đang dùng máy chủ kiểm thử. Cần cấu hình URL và tài khoản chính thức '
                                'của Thành Đạt Phát trước khi tải hóa đơn đầu ra hoặc lưu nháp nghiệp vụ.')

    def get_invoice_series(self) -> list[dict]:
        result = self._json("GET", "Invoice68/GetTypeInvoiceSeries", authenticated=True)
        if not result.get("ok") or result.get("code") != "00":
            raise MinvoiceError("Không đọc được danh sách ký hiệu hóa đơn M-Invoice")
        return result.get("data") or []

    def outgoing_summary(self) -> dict:
        series = self.get_invoice_series()
        current_year = date.today().year % 100
        current = [item for item in series if int(item.get("invoiceYear") or 0) == current_year]
        return {
            "available": True,
            "official_api": True,
            "series_count": len(series),
            "current_year_series_count": len(current),
        }

    def get_outgoing_invoices(
        self, start_date: str, end_date: str, series: str,
        start: int = 0, count: int = 300, include_details: bool = True,
    ) -> dict:
        if not series:
            raise MinvoiceError("Cần chọn ký hiệu hóa đơn")
        count = max(1, min(int(count), 300))
        result = self._json("POST", "InvoiceApi78/GetInvoices", {
            "tuNgay": start_date,
            "denngay": end_date,
            "khieu": series,
            "start": max(0, int(start)),
            "count": count,
            "coChiTiet": bool(include_details),
        }, authenticated=True)
        if not result.get("ok") or result.get("code") != "00":
            raise MinvoiceError("Không đọc được danh sách hóa đơn đầu ra M-Invoice")
        return result

    def get_invoice_info(self, *, key_api: str) -> dict:
        """Look up one invoice by the client idempotency key without writing.

        M-Invoice returns code ``29404`` when no matching invoice exists.  The
        raw invoice is intentionally kept inside the client/route boundary so
        callers can reconcile state without logging buyer or line details.
        """
        key = self._text(
            key_api, field="khóa chống trùng key_api", required=True, max_length=100,
        )
        result = self._json(
            "GET", self.INVOICE_INFO_PATH,
            params={"keyApi": key}, authenticated=True,
        )
        if str(result.get("code") or "") == "29404":
            return {"found": False, "key_api": key, "data": None, "read_only": True}
        if result.get("code") != "00" or result.get("ok") is False:
            raise MinvoiceError("Không đối soát được hóa đơn M-Invoice theo key_api")
        data = result.get("data")
        return {
            "found": data not in (None, "", [], {}),
            "key_api": key,
            "data": data,
            "read_only": True,
        }

    @staticmethod
    def _text(value, *, field: str, required: bool = False, max_length: int | None = None) -> str:
        text = str(value or "").strip()
        if required and not text:
            raise MinvoiceError(f"Thiếu {field}")
        if max_length is not None and len(text) > max_length:
            raise MinvoiceError(f"{field} dài quá {max_length} ký tự")
        return text

    @classmethod
    def _decimal(cls, value, *, field: str, minimum: Decimal | None = None) -> Decimal:
        if isinstance(value, bool):
            raise MinvoiceError(f"{field} không đúng định dạng số")
        try:
            number = Decimal(str(value).strip().replace(",", ""))
        except (InvalidOperation, AttributeError, ValueError):
            raise MinvoiceError(f"{field} không đúng định dạng số") from None
        if not number.is_finite():
            raise MinvoiceError(f"{field} không đúng định dạng số")
        if minimum is not None and number < minimum:
            raise MinvoiceError(f"{field} phải lớn hơn hoặc bằng {minimum}")
        return number.quantize(cls._SIX_PLACES, rounding=ROUND_HALF_UP)

    @classmethod
    def _json_number(cls, value: Decimal):
        value = value.quantize(cls._SIX_PLACES, rounding=ROUND_HALF_UP)
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    @classmethod
    def _tax_code(cls, value) -> str:
        if value is None or str(value).strip() == "":
            raise MinvoiceError("Thiếu thuế suất của dòng hàng")
        raw = str(value).strip().upper().replace(" ", "")
        aliases = {
            "KCT": "-1",
            "KHÔNGCHỊUTHUẾ": "-1",
            "KHONGCHIUTHUE": "-1",
            "KKKNT": "-2",
            "KHÔNGKÊKHAI": "-2",
            "KHONGKEKHAI": "-2",
        }
        if raw in aliases:
            return aliases[raw]
        raw = raw.rstrip("%").replace(",", ".")
        try:
            numeric = Decimal(raw)
        except InvalidOperation:
            raise MinvoiceError("Thuế suất chỉ nhận 0%, 5%, 8%, 10%, KCT hoặc KKKNT") from None
        if Decimal("0") < numeric < Decimal("1"):
            numeric *= 100
        code = str(int(numeric)) if numeric == numeric.to_integral_value() else format(numeric.normalize(), "f")
        if code not in cls._TAX_CODES:
            raise MinvoiceError("Thuế suất chỉ nhận 0%, 5%, 8%, 10%, KCT hoặc KKKNT")
        return code

    @staticmethod
    def _first(mapping: dict, *keys, default=None):
        for key in keys:
            if key in mapping and mapping[key] is not None:
                return mapping[key]
        return default

    @classmethod
    def _normalize_draft(cls, draft: dict) -> dict:
        if not isinstance(draft, dict):
            raise MinvoiceError("Dữ liệu dự thảo hóa đơn phải là một đối tượng")

        invoice_date = cls._text(
            cls._first(draft, "invoice_date", "inv_invoiceIssuedDate"),
            field="ngày hóa đơn", required=True,
        )
        try:
            parsed_date = datetime.strptime(invoice_date, "%Y-%m-%d").date()
        except ValueError:
            raise MinvoiceError("Ngày hóa đơn phải theo định dạng YYYY-MM-DD") from None

        series = cls._text(
            cls._first(draft, "series", "inv_invoiceSeries"),
            field="ký hiệu hóa đơn", required=True, max_length=8,
        )
        if not re.fullmatch(r"1[A-Z0-9]{6}", series.upper()):
            raise MinvoiceError("Ký hiệu phải là ký hiệu hóa đơn GTGT 7 ký tự bắt đầu bằng 1")
        series = series.upper()

        currency = cls._text(
            cls._first(draft, "currency", "inv_currencyCode", default="VND"),
            field="đơn vị tiền tệ", required=True, max_length=3,
        ).upper()
        if currency not in {"VND", "USD"}:
            raise MinvoiceError("Đơn vị tiền tệ chỉ nhận VND hoặc USD")
        exchange_rate = cls._decimal(
            cls._first(draft, "exchange_rate", "inv_exchangeRate", default=1),
            field="tỷ giá", minimum=Decimal("0.000001"),
        )
        if currency == "VND" and exchange_rate != Decimal("1.000000"):
            raise MinvoiceError("Hóa đơn VND phải có tỷ giá bằng 1")

        key_api = cls._text(
            cls._first(draft, "key_api", "keyApi"),
            field="khóa chống trùng key_api", required=True, max_length=100,
        )
        payment_method = cls._text(
            cls._first(draft, "payment_method", "inv_paymentMethodName", default="TM/CK"),
            field="hình thức thanh toán", required=True, max_length=50,
        )
        order_number = cls._text(
            cls._first(draft, "order_number", "so_benh_an"),
            field="số đơn hàng", max_length=50,
        )

        buyer = draft.get("buyer") or {}
        if not isinstance(buyer, dict):
            raise MinvoiceError("Thông tin người mua không đúng định dạng")
        display_name = cls._text(
            cls._first(buyer, "display_name", "name", default=cls._first(draft, "inv_buyerDisplayName")),
            field="tên người mua", max_length=100,
        )
        legal_name = cls._text(
            cls._first(buyer, "legal_name", "company_name", default=cls._first(draft, "inv_buyerLegalName")),
            field="tên đơn vị mua", max_length=400,
        )
        tax_code = cls._text(
            cls._first(buyer, "tax_code", default=cls._first(draft, "inv_buyerTaxCode")),
            field="mã số thuế người mua", max_length=14,
        )
        address = cls._text(
            cls._first(buyer, "address", default=cls._first(draft, "inv_buyerAddressLine")),
            field="địa chỉ người mua", required=True, max_length=400,
        )
        if legal_name or tax_code:
            if not legal_name or not tax_code:
                raise MinvoiceError("Người mua là đơn vị phải có đủ tên đơn vị và mã số thuế")
            if not re.fullmatch(r"\d{10}(?:-\d{3})?", tax_code):
                raise MinvoiceError("Mã số thuế người mua phải gồm 10 số hoặc 10 số-3 số")
        elif not display_name:
            raise MinvoiceError("Người mua cá nhân phải có tên người mua")

        email = cls._text(
            cls._first(buyer, "email", default=cls._first(draft, "inv_buyerEmail")),
            field="email người mua", max_length=50,
        )
        bank_account = cls._text(
            cls._first(buyer, "bank_account", default=cls._first(draft, "inv_buyerBankAccount")),
            field="tài khoản ngân hàng người mua", max_length=30,
        )
        bank_name = cls._text(
            cls._first(buyer, "bank_name", default=cls._first(draft, "inv_buyerBankName")),
            field="ngân hàng người mua", max_length=400,
        )

        lines = cls._first(draft, "lines", "items")
        buyer_tax_code = tax_code
        if not isinstance(lines, list) or not lines:
            raise MinvoiceError("Hóa đơn phải có ít nhất một dòng hàng")
        if len(lines) > 9999:
            raise MinvoiceError("Hóa đơn không được vượt quá 9.999 dòng hàng")

        normalized_lines = []
        subtotal = Decimal("0")
        tax_amount = Decimal("0")
        total_amount = Decimal("0")
        discount_total = Decimal("0")
        tolerance = Decimal("1") if currency == "VND" else Decimal("0.01")
        money_quantum = Decimal("1") if currency == "VND" else cls._SIX_PLACES

        for index, source in enumerate(lines, 1):
            if not isinstance(source, dict):
                raise MinvoiceError(f"Dòng hàng {index} không đúng định dạng")
            try:
                tchat = int(cls._first(source, "tchat", default=1))
            except (TypeError, ValueError):
                raise MinvoiceError(f"Tính chất dòng hàng {index} không hợp lệ") from None
            if tchat not in {1, 2, 4}:
                raise MinvoiceError(
                    f"Dòng hàng {index}: client an toàn chỉ hỗ trợ hàng hóa, khuyến mại hoặc diễn giải"
                )
            name = cls._text(
                cls._first(source, "name", "product_name", "inv_itemName"),
                field=f"tên hàng dòng {index}", required=True, max_length=500,
            )
            code = cls._text(
                cls._first(source, "code", "product_code", "inv_itemCode"),
                field=f"mã hàng dòng {index}", max_length=50,
            )
            unit = cls._text(
                cls._first(source, "unit", "inv_unitCode"),
                field=f"đơn vị tính dòng {index}", max_length=50,
            )

            if tchat == 4:
                normalized_lines.append({
                    "tchat": 4,
                    "stt_rec0": f"{index:04d}",
                    "inv_itemName": name,
                    "inv_discountPercentage": 0,
                    "inv_discountAmount": 0,
                    "inv_TotalAmountWithoutVat": 0,
                    "inv_vatAmount": 0,
                    "inv_TotalAmount": 0,
                })
                continue

            quantity = cls._decimal(
                cls._first(source, "quantity", "qty", "inv_quantity"),
                field=f"số lượng dòng {index}", minimum=Decimal("0.000001"),
            )
            unit_price = cls._decimal(
                cls._first(source, "unit_price", "inv_unitPrice"),
                field=f"đơn giá dòng {index}", minimum=Decimal("0"),
            )
            discount_percentage = cls._decimal(
                cls._first(source, "discount_percentage", "inv_discountPercentage", default=0),
                field=f"tỷ lệ chiết khấu dòng {index}", minimum=Decimal("0"),
            )
            if discount_percentage > Decimal("100"):
                raise MinvoiceError(f"Tỷ lệ chiết khấu dòng {index} không được vượt quá 100%")
            gross = (quantity * unit_price).quantize(money_quantum, rounding=ROUND_HALF_UP)
            supplied_discount = cls._first(source, "discount_amount", "inv_discountAmount")
            calculated_discount = (
                gross * discount_percentage / Decimal("100")
            ).quantize(money_quantum, rounding=ROUND_HALF_UP)
            if supplied_discount is None:
                discount_amount = calculated_discount
            else:
                discount_amount = cls._decimal(
                    supplied_discount,
                    field=f"tiền chiết khấu dòng {index}", minimum=Decimal("0"),
                )
                if discount_percentage and abs(discount_amount - calculated_discount) > tolerance:
                    raise MinvoiceError(f"Tiền chiết khấu dòng {index} không khớp tỷ lệ chiết khấu")
            if discount_amount > gross:
                raise MinvoiceError(f"Tiền chiết khấu dòng {index} lớn hơn tiền hàng")
            discount_amount = discount_amount.quantize(money_quantum, rounding=ROUND_HALF_UP)

            before_tax = (gross - discount_amount).quantize(money_quantum, rounding=ROUND_HALF_UP)
            tax_code = cls._tax_code(cls._first(source, "tax", "tax_rate", "ma_thue"))
            if int(tax_code) >= 0:
                vat = (before_tax * Decimal(tax_code) / Decimal("100")).quantize(
                    money_quantum, rounding=ROUND_HALF_UP
                )
            else:
                vat = Decimal("0")
            line_total = (before_tax + vat).quantize(money_quantum, rounding=ROUND_HALF_UP)

            supplied_checks = (
                (("amount_without_tax", "inv_TotalAmountWithoutVat"), before_tax, "tiền trước thuế"),
                (("vat_amount", "inv_vatAmount"), vat, "tiền thuế"),
                (("total_amount", "inv_TotalAmount"), line_total, "tổng tiền"),
            )
            for aliases, expected, label in supplied_checks:
                supplied = cls._first(source, *aliases)
                if supplied is None:
                    continue
                actual = cls._decimal(supplied, field=f"{label} dòng {index}")
                if abs(actual - expected) > tolerance:
                    raise MinvoiceError(f"{label.capitalize()} dòng {index} không khớp số lượng, đơn giá và thuế")

            normalized_line = {
                "tchat": tchat,
                "stt_rec0": f"{index:04d}",
                "inv_itemCode": code,
                "inv_itemName": name,
                "inv_unitCode": unit,
                "inv_quantity": cls._json_number(quantity),
                "inv_unitPrice": cls._json_number(unit_price),
                "inv_discountPercentage": cls._json_number(discount_percentage),
                "inv_discountAmount": cls._json_number(discount_amount),
                "inv_TotalAmountWithoutVat": cls._json_number(before_tax),
                "ma_thue": tax_code,
                "inv_vatAmount": cls._json_number(vat),
                "inv_TotalAmount": cls._json_number(line_total),
                "inv_promotion": tchat == 2,
            }
            normalized_lines.append(normalized_line)
            subtotal += before_tax
            tax_amount += vat
            total_amount += line_total
            discount_total += discount_amount

        subtotal = subtotal.quantize(money_quantum, rounding=ROUND_HALF_UP)
        tax_amount = tax_amount.quantize(money_quantum, rounding=ROUND_HALF_UP)
        total_amount = total_amount.quantize(money_quantum, rounding=ROUND_HALF_UP)
        discount_total = discount_total.quantize(money_quantum, rounding=ROUND_HALF_UP)
        header_checks = (
            (("subtotal", "inv_TotalAmountWithoutVat"), subtotal, "tổng tiền trước thuế"),
            (("tax_amount", "inv_vatAmount"), tax_amount, "tổng tiền thuế"),
            (("total_amount", "inv_TotalAmount"), total_amount, "tổng tiền thanh toán"),
        )
        for aliases, expected, label in header_checks:
            supplied = cls._first(draft, *aliases)
            if supplied is None:
                continue
            actual = cls._decimal(supplied, field=label)
            if abs(actual - expected) > tolerance:
                raise MinvoiceError(f"{label.capitalize()} không khớp chi tiết hóa đơn")

        return {
            "invoice_date": parsed_date.isoformat(),
            "series": series,
            "currency": currency,
            "exchange_rate": exchange_rate,
            "payment_method": payment_method,
            "order_number": order_number,
            "key_api": key_api,
            "buyer": {
                "display_name": display_name,
                "legal_name": legal_name,
                "tax_code": buyer_tax_code,
                "address": address,
                "email": email,
                "bank_account": bank_account,
                "bank_name": bank_name,
            },
            "lines": normalized_lines,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "discount_total": discount_total,
        }

    def validate_draft(self, draft: dict) -> dict:
        """Validate locally and return calculated totals without any network call."""
        normalized = self._normalize_draft(draft)
        return {
            "valid": True,
            "remote_write": False,
            "series": normalized["series"],
            "invoice_date": normalized["invoice_date"],
            "key_api": normalized["key_api"],
            "line_count": len(normalized["lines"]),
            "subtotal": self._json_number(normalized["subtotal"]),
            "tax_amount": self._json_number(normalized["tax_amount"]),
            "total_amount": self._json_number(normalized["total_amount"]),
        }

    def build_draft_payload(self, draft: dict) -> dict:
        """Build the documented ``InvoiceApi78/Save`` payload locally."""
        normalized = self._normalize_draft(draft)
        buyer = normalized["buyer"]
        invoice = {
            "inv_invoiceSeries": normalized["series"],
            "inv_invoiceIssuedDate": normalized["invoice_date"],
            "inv_currencyCode": normalized["currency"],
            "inv_exchangeRate": self._json_number(normalized["exchange_rate"]),
            "inv_paymentMethodName": normalized["payment_method"],
            "inv_buyerDisplayName": buyer["display_name"],
            "inv_buyerLegalName": buyer["legal_name"],
            "inv_buyerTaxCode": buyer["tax_code"],
            "inv_buyerAddressLine": buyer["address"],
            "inv_buyerEmail": buyer["email"],
            "inv_buyerBankAccount": buyer["bank_account"],
            "inv_buyerBankName": buyer["bank_name"],
            "inv_discountAmount": self._json_number(normalized["discount_total"]),
            "inv_TotalAmountWithoutVat": self._json_number(normalized["subtotal"]),
            "inv_vatAmount": self._json_number(normalized["tax_amount"]),
            "inv_TotalAmount": self._json_number(normalized["total_amount"]),
            "key_api": normalized["key_api"],
            "details": [{"data": normalized["lines"]}],
        }
        if normalized["order_number"]:
            invoice["so_benh_an"] = normalized["order_number"]
        return {"editmode": 1, "data": [invoice]}

    def _assert_series_available(self, series: str, invoice_date: str) -> None:
        available = self.get_invoice_series()
        selected = next(
            (
                item for item in available
                if str(item.get("value") or item.get("khhdon") or "").upper() == series.upper()
            ),
            None,
        )
        if not selected:
            raise MinvoiceError("Ký hiệu hóa đơn không có trong tài khoản M-Invoice")
        invoice_year = int(invoice_date[:4]) % 100
        configured_year = selected.get("invoiceYear")
        if configured_year not in (None, "") and int(configured_year) != invoice_year:
            raise MinvoiceError("Ký hiệu M-Invoice không đúng năm của ngày hóa đơn")

    def create_draft(
        self,
        draft: dict,
        *,
        dry_run: bool = True,
        confirm_remote_write: bool = False,
    ) -> dict:
        """Prepare or create one *unsigned* M-Invoice invoice in ``Chờ ký``.

        The default is a local-only dry run. A real request requires both
        ``dry_run=False`` and ``confirm_remote_write=True``. Even then this
        method only calls ``InvoiceApi78/Save``; it never calls ``Sign`` or
        ``SaveSign`` and therefore cannot sign, issue or submit to the tax
        authority.
        """
        payload = self.build_draft_payload(draft)
        invoice = payload["data"][0]
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "remote_write": False,
                "endpoint": "/api/" + self.DRAFT_SAVE_PATH,
                "payload": payload,
                "requires_user_sign_and_issue": True,
            }
        if not confirm_remote_write:
            raise MinvoiceError("Cần xác nhận rõ trước khi lưu dự thảo lên M-Invoice")
        self.assert_business_environment()
        self._assert_series_available(invoice["inv_invoiceSeries"], invoice["inv_invoiceIssuedDate"])
        try:
            result = self._json("POST", self.DRAFT_SAVE_PATH, payload, authenticated=True)
        except MinvoiceError as exc:
            raise MinvoiceOutcomeUnknown(
                "Chưa xác định M-Invoice đã nhận bản nháp hay chưa; cần đối soát key_api trước khi thử lại"
            ) from exc
        except Exception as exc:
            # A timeout/reset can surface from response.read() as an OSError or
            # HTTPException depending on the Python/SSL stack.  Once POST has
            # started, every unexpected transport/parse failure is ambiguous:
            # never let the caller retry it without a key_api reconciliation.
            raise MinvoiceOutcomeUnknown(
                "Chưa xác định M-Invoice đã nhận bản nháp hay chưa; cần đối soát key_api trước khi thử lại"
            ) from exc
        if not isinstance(result, dict):
            raise MinvoiceOutcomeUnknown(
                "Chưa xác định M-Invoice đã nhận bản nháp hay chưa; cần đối soát key_api trước khi thử lại"
            )
        if result.get("code") != "00" or result.get("ok") is False:
            raise MinvoiceError("M-Invoice không lưu được hóa đơn chờ ký")
        return {
            "ok": True,
            "dry_run": False,
            "remote_write": True,
            "requires_user_sign_and_issue": True,
            "data": result.get("data"),
            "message": result.get("message") or "Thành công",
        }
