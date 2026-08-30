from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MinvoiceError(RuntimeError):
    """A sanitized M-Invoice connection error safe to return to the local UI."""


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

    @classmethod
    def from_env_files(cls, paths: list[Path]) -> "MinvoiceConfig":
        values: dict[str, str] = {}
        for path in paths:
            values.update(_read_env_file(path))
        required = {
            "MINVOICE_API_BASE_URL": values.get("MINVOICE_API_BASE_URL", ""),
            "MINVOICE_USERNAME": values.get("MINVOICE_USERNAME", ""),
            "MINVOICE_PASSWORD": values.get("MINVOICE_PASSWORD", ""),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise MinvoiceError("Thiếu cấu hình M-Invoice trong .env: " + ", ".join(missing))
        return cls(
            api_base_url=required["MINVOICE_API_BASE_URL"].rstrip("/"),
            username=required["MINVOICE_USERNAME"],
            password=required["MINVOICE_PASSWORD"],
            unit_code=values.get("MINVOICE_UNIT_CODE", "VP") or "VP",
        )


class MinvoiceClient:
    """Read-only client for the documented M-Invoice 2.0 API."""

    def __init__(self, config: MinvoiceConfig, timeout: int = 25):
        self.config = config
        self.timeout = timeout
        self._token = ""

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
        except URLError:
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
        return {"authenticated": True, "credential_verified": True, "official_api": True}

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

