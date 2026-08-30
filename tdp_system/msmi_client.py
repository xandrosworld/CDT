from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MsmiError(RuntimeError):
    """A sanitized mSMI error that never includes credentials or invoice data."""


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
class MsmiConfig:
    api_base_url: str
    api_token: str

    @classmethod
    def from_env_files(cls, paths: list[Path]) -> "MsmiConfig":
        values: dict[str, str] = {}
        for path in paths:
            values.update(_read_env_file(path))
        base = values.get("MSMI_API_BASE_URL", "").rstrip("/")
        token = values.get("MSMI_API_TOKEN", "")
        missing = []
        if not base:
            missing.append("MSMI_API_BASE_URL")
        if not token:
            missing.append("MSMI_API_TOKEN")
        if missing:
            raise MsmiError("Thiếu cấu hình mSMI trong .env: " + ", ".join(missing))
        return cls(api_base_url=base, api_token=token)


class MsmiClient:
    """Read-only mSMI OpenAPI client used only for listing invoice data."""

    def __init__(self, config: MsmiConfig, timeout: int = 35):
        self.config = config
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = self.config.api_base_url + "/" + path.lstrip("/")
        if params:
            url += "?" + urlencode({key: value for key, value in params.items() if value not in (None, "")})
        request = Request(url, headers={"Accept": "application/json", "apiToken": self.config.api_token})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as error:
            raise MsmiError(f"mSMI trả lỗi HTTP {error.code}") from None
        except (URLError, OSError):
            raise MsmiError("Không kết nối được máy chủ mSMI") from None
        except TimeoutError:
            raise MsmiError("mSMI phản hồi quá thời gian chờ") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MsmiError("mSMI trả dữ liệu không đúng định dạng") from None
        if not isinstance(payload, dict):
            raise MsmiError("mSMI trả dữ liệu không đúng cấu trúc")
        return payload

    def list_invoices(
        self,
        invoice_type: str = "INPUT_ELECTRONIC_INVOICE",
        page: int = 0,
        size: int = 200,
        from_date: str = "",
        to_date: str = "",
    ) -> dict:
        if invoice_type not in {"INPUT_ELECTRONIC_INVOICE", "OUTPUT_ELECTRONIC_INVOICE"}:
            raise MsmiError("Loại hóa đơn mSMI không hợp lệ")
        params = {
            "invoiceType": invoice_type,
            "page": max(0, int(page)),
            "size": max(1, min(int(size), 200)),
        }
        # These optional names follow mSMI OpenAPI v1.1.1. Omitting them keeps
        # compatibility with tenants that do not enable a date filter.
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        payload = self._get("api/qlhd-api/invoices", params)
        invoices = payload.get("listInvoice")
        if invoices is None:
            invoices = payload.get("data", {}).get("listInvoice") if isinstance(payload.get("data"), dict) else None
        if invoices is None or not isinstance(invoices, list):
            raise MsmiError("mSMI không trả danh sách hóa đơn")
        return {
            "items": invoices,
            "page": int(page),
            "size": int(params["size"]),
            "has_more": len(invoices) >= int(params["size"]),
        }

    def status(self) -> dict:
        result = self.list_invoices(size=1)
        return {
            "connected": True,
            "read_only": True,
            "official_api": True,
            "sample_count": len(result["items"]),
        }
