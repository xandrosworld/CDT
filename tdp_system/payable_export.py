"""Auditable supplier-payable Excel export.

The customer's historical workbook establishes the useful business column
order, but it also contains stale print areas, a freeze pane at row 9969 and a
formula in the ``Thành tiền`` header.  This exporter therefore keeps the
grounded order while writing static ledger values and deterministic print
settings.  Current balances always come from ``payable_ledger_lines``;
payment and allocation history is retained instead of being flattened away.
"""

from __future__ import annotations

try:
    from .document_preview import white_print_style
except ImportError:
    from document_preview import white_print_style

try:
    from document_totals import quantity_totals, quantity_text, quantity_cell
except ImportError:
    from .document_totals import quantity_totals, quantity_text, quantity_cell

import io
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable

from flask import jsonify, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins


STATUS_LABELS = {
    "open": "Chưa trả",
    "partially_paid": "Trả một phần",
    "paid": "Đã trả",
    "reversed": "Đã đảo",
    "posted": "Đã ghi nhận",
}
SOURCE_LABELS = {
    "current_purchase": "Bảng đặt hàng chuẩn",
    "current_order": "Đơn vận hành",
    "historical_import": "File công nợ lịch sử",
}
FORBIDDEN_SHEET_CHARACTERS = re.compile(r"[\\/*?:\[\]]")
FORBIDDEN_FILENAME_CHARACTERS = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")


class PayableExportError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_payable_export", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _strict_date(value: Any, label: str) -> str:
    text = _clean(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise PayableExportError(f"{label} phải là ngày YYYY-MM-DD hợp lệ") from None


def _vnd(value: Any) -> int:
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        raise PayableExportError(
            "Dữ liệu tiền trong sổ phải trả không hợp lệ",
            code="invalid_payable_export_money",
            status=500,
        ) from None
    if not number.is_finite():
        raise PayableExportError(
            "Dữ liệu tiền trong sổ phải trả không hữu hạn",
            code="invalid_payable_export_money",
            status=500,
        )
    return int(number.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _number(value: Any) -> float:
    try:
        number = Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0
    return float(number) if number.is_finite() else 0.0


def _excel_date(value: str) -> date | str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return _clean(value)


def _display_date(value: Any) -> str:
    parsed = _excel_date(str(value or ""))
    return parsed.strftime("%d/%m/%Y") if isinstance(parsed, date) else str(parsed)


def _display_datetime(value: Any) -> str:
    text = _clean(value)
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.strftime("%d/%m/%Y %H:%M:%S" if "%H" in pattern else "%d/%m/%Y")
        except ValueError:
            pass
    return text


def _table_columns(conn, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _chunks(values: list[int], size: int = 800):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _source_details(conn, lines: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    """Fetch adjustment columns in batches; ledger remains the money authority."""
    requested: dict[str, list[int]] = defaultdict(list)
    for line in lines:
        source_table = _clean(line.get("source_table"))
        source_id = int(line.get("source_id") or 0)
        if source_table in {
            "purchase_workbook_lines", "historical_payable_lines",
            "purchase_order_lines", "orders",
        } and source_id:
            requested[source_table].append(source_id)

    result: dict[tuple[str, int], dict[str, Any]] = {}
    for table, raw_ids in requested.items():
        columns = _table_columns(conn, table)
        ids = sorted(set(raw_ids))
        if table == "purchase_workbook_lines":
            wanted = [
                "id", "base_qty", "damaged_qty", "added_qty", "reduced_qty",
                "missing_qty", "actual_qty", "note",
            ]
        elif table == "historical_payable_lines":
            wanted = [
                "id", "qty", "damaged_qty", "added_qty", "reduced_qty",
                "missing_qty", "actual_qty", "note",
            ]
        elif table == "purchase_order_lines":
            wanted = ["id", "order_qty", "note"]
        else:
            wanted = [
                "id", "actual_received", "damaged_qty", "supplier_return_qty", "note",
            ]
        selected = [name for name in wanted if name in columns]
        if "id" not in selected:
            continue
        for group in _chunks(ids):
            placeholders = ",".join("?" for _ in group)
            for row in conn.execute(
                f"SELECT {','.join(selected)} FROM {table} WHERE id IN ({placeholders})",
                group,
            ):
                item = dict(row)
                source_id = int(item.pop("id"))
                if "qty" in item:
                    item["base_qty"] = item.pop("qty")
                if "order_qty" in item:
                    item["base_qty"] = item.pop("order_qty")
                if "actual_received" in item:
                    item["base_qty"] = item.pop("actual_received")
                if table == "orders" and "supplier_return_qty" in item:
                    item["reduced_qty"] = item.pop("supplier_return_qty")
                result[(table, source_id)] = item
    return result


def _safe_supplier_code(
    conn, supplier: Any, canonical_party_code: Callable[[Any, str, str], str],
) -> str:
    requested = _clean(supplier)
    if not requested:
        return ""
    try:
        return canonical_party_code(conn, "supplier", requested)
    except ValueError as error:
        raise PayableExportError(str(error), code="invalid_supplier") from None


def payable_export_data(
    conn, *, date_from: Any, date_to: Any, supplier: Any,
    canonical_party_code: Callable[[Any, str, str], str],
    statuses: Any = None,
) -> dict[str, Any]:
    """Return one read-snapshot used by every sheet in the workbook."""
    safe_from = _strict_date(date_from, "Từ ngày")
    safe_to = _strict_date(date_to, "Đến ngày")
    if safe_from > safe_to:
        raise PayableExportError(
            "Từ ngày không được lớn hơn Đến ngày", code="invalid_period",
        )
    supplier_code = _safe_supplier_code(conn, supplier, canonical_party_code)
    allowed = {"open", "partially_paid", "paid", "reversed"}
    selected_statuses = allowed - {"reversed"} if not statuses else (
        allowed if statuses == "all" else set(str(statuses).split(","))
    )
    if not selected_statuses or not selected_statuses <= allowed:
        raise PayableExportError("Trạng thái phải trả không hợp lệ", code="invalid_status", status=400)
    supplier_clause = " AND l.supplier_code=?" if supplier_code else ""
    params: list[Any] = [safe_from, safe_to]
    if supplier_code:
        params.append(supplier_code)
    lines = [dict(row) for row in conn.execute(
        f"""SELECT l.*,COALESCE(s.name,'') supplier_name
              FROM payable_ledger_lines l
              LEFT JOIN suppliers s ON s.code=l.supplier_code
             WHERE l.work_date>=? AND l.work_date<=?{supplier_clause}
             ORDER BY l.supplier_code,l.work_date,l.kitchen,l.product_name,l.id""",
        params,
    )]
    details = _source_details(conn, lines)
    for line in lines:
        source_detail = details.get((line["source_table"], int(line["source_id"])), {})
        line["base_qty"] = _number(source_detail.get("base_qty", line["actual_qty"]))
        line["damaged_qty"] = source_detail.get("damaged_qty")
        line["added_qty"] = source_detail.get("added_qty")
        line["reduced_qty"] = source_detail.get("reduced_qty")
        line["missing_qty"] = source_detail.get("missing_qty")
        line["note"] = _clean(source_detail.get("note"))
        line["amount"] = _vnd(line["amount"])
        line["paid_amount"] = _vnd(line["paid_amount"])
        line["remaining_amount"] = (
            0 if line["status"] == "reversed"
            else line["amount"] - line["paid_amount"]
        )
        invalid_allocation = (
            line["paid_amount"] < 0
            or (line["amount"] <= 0 and line["paid_amount"] > 0)
            or (line["amount"] > 0 and line["paid_amount"] > line["amount"])
        )
        if invalid_allocation:
            raise PayableExportError(
                f"Dòng nợ {line['id']} có số đã trả vượt thành tiền",
                code="payable_export_overpayment",
                status=409,
            )

    payment_supplier_clause = " AND p.party_code=?" if supplier_code else ""
    payment_params: list[Any] = [safe_from, safe_to]
    if supplier_code:
        payment_params.append(supplier_code)
    payments = [dict(row) for row in conn.execute(
        f"""SELECT p.*,COALESCE(s.name,'') supplier_name,
                    COUNT(a.id) allocation_count,
                    COALESCE(SUM(CASE WHEN a.status='posted' THEN a.amount ELSE 0 END),0)
                        posted_allocation_amount
              FROM payments p
              LEFT JOIN suppliers s ON s.code=p.party_code
              LEFT JOIN payable_payment_allocations a ON a.payment_id=p.id
             WHERE p.kind='payment' AND p.party_type='supplier'
               AND p.payment_date>=? AND p.payment_date<=?{payment_supplier_clause}
             GROUP BY p.id
             ORDER BY p.payment_date,p.id""",
        payment_params,
    )]
    for payment in payments:
        payment["amount"] = _vnd(payment["amount"])
        payment["posted_allocation_amount"] = _vnd(payment["posted_allocation_amount"])

    allocation_params: list[Any] = [safe_from, safe_to]
    allocation_supplier_clause = " AND l.supplier_code=?" if supplier_code else ""
    if supplier_code:
        allocation_params.append(supplier_code)
    allocations = [dict(row) for row in conn.execute(
        f"""SELECT a.*,p.payment_date,p.party_code supplier_code,
                    p.method,p.reference_code,p.note payment_note,
                    p.status payment_status,l.work_date,l.kitchen,l.product_name,
                    l.amount line_amount,l.status line_status
              FROM payable_payment_allocations a
              JOIN payments p ON p.id=a.payment_id
              JOIN payable_ledger_lines l ON l.id=a.ledger_line_id
             WHERE l.work_date>=? AND l.work_date<=?{allocation_supplier_clause}
             ORDER BY l.supplier_code,p.payment_date,p.id,a.id""",
        allocation_params,
    )]
    for allocation in allocations:
        allocation["amount"] = _vnd(allocation["amount"])
        allocation["line_amount"] = _vnd(allocation["line_amount"])

    posted_by_line: dict[int, int] = defaultdict(int)
    for allocation in allocations:
        if allocation["status"] == "posted":
            posted_by_line[int(allocation["ledger_line_id"])] += allocation["amount"]
    for line in lines:
        allocated = posted_by_line.get(int(line["id"]), 0)
        if allocated != line["paid_amount"]:
            raise PayableExportError(
                f"Dòng nợ {line['id']} lệch giữa sổ và phân bổ thanh toán; đã dừng xuất file",
                code="payable_export_allocation_mismatch",
                status=409,
            )

    supplier_info: dict[str, dict[str, Any]] = {}
    for line in lines:
        code = _clean(line["supplier_code"])
        supplier_info.setdefault(code, {
            "code": code,
            "name": _clean(line["supplier_name"]) or _clean(line["supplier_snapshot"]) or code,
        })
    for payment in payments:
        code = _clean(payment["party_code"])
        supplier_info.setdefault(code, {
            "code": code,
            "name": _clean(payment["supplier_name"]) or code,
        })

    summaries = []
    for code in sorted(supplier_info, key=lambda value: value.casefold()):
        supplier_lines = [line for line in lines if _clean(line["supplier_code"]) == code]
        active = [line for line in supplier_lines if line["status"] != "reversed"]
        reversed_lines = [line for line in supplier_lines if line["status"] == "reversed"]
        supplier_payments = [payment for payment in payments if _clean(payment["party_code"]) == code]
        summary = {
            **supplier_info[code],
            "active_line_count": len(active),
            "reversed_line_count": len(reversed_lines),
            "charge_amount": sum(line["amount"] for line in active),
            "paid_amount": sum(line["paid_amount"] for line in active),
            "remaining_amount": sum(line["remaining_amount"] for line in active),
            "reversed_amount": sum(line["amount"] for line in reversed_lines),
            "reversed_paid_amount": sum(line["paid_amount"] for line in reversed_lines),
            "payment_count": len(supplier_payments),
            "posted_payment_amount": sum(
                item["amount"] for item in supplier_payments if item["status"] == "posted"
            ),
            "reversed_payment_amount": sum(
                item["amount"] for item in supplier_payments if item["status"] == "reversed"
            ),
        }
        if summary["charge_amount"] != summary["paid_amount"] + summary["remaining_amount"]:
            raise PayableExportError(
                f"Công nợ nhà cung cấp {code} không đối soát",
                code="payable_export_reconciliation_failed",
                status=409,
            )
        summaries.append(summary)

    total_fields = (
        "active_line_count", "reversed_line_count", "charge_amount", "paid_amount",
        "remaining_amount", "reversed_amount", "reversed_paid_amount", "payment_count",
        "posted_payment_amount", "reversed_payment_amount",
    )
    totals = {field: sum(item[field] for item in summaries) for field in total_fields}
    return {
        "statuses": sorted(selected_statuses),
        "date_from": safe_from,
        "date_to": safe_to,
        "supplier": supplier_code or None,
        "lines": lines,
        "payments": payments,
        "allocations": allocations,
        "suppliers": summaries,
        "totals": totals,
    }


THIN_GRAY = Side(style="thin", color="000000")
TABLE_BORDER = Border(left=THIN_GRAY, right=THIN_GRAY, top=THIN_GRAY, bottom=THIN_GRAY)
TITLE_FILL = PatternFill(fill_type=None)
HEADER_FILL = PatternFill(fill_type=None)
TOTAL_FILL = PatternFill(fill_type=None)
REVERSED_FILL = PatternFill("solid", fgColor="FEE2E2")


def _style_sheet(
    ws, *, title: str, subtitle: str, headers: list[str], widths: list[float],
    money_columns: tuple[int, ...] = (), quantity_columns: tuple[int, ...] = (),
    date_columns: tuple[int, ...] = (), total_row: int | None = None,
    print_end_column: int | None = None,
) -> None:
    end_col = len(headers)
    ws.insert_rows(1, 2)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=end_col)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end_col)
    ws.cell(1, 1, title)
    ws.cell(2, 1, subtitle)
    ws.cell(1, 1).font = Font(name="Times New Roman", size=16, bold=True)
    ws.cell(1, 1).fill = TITLE_FILL
    ws.cell(1, 1).alignment = Alignment(horizontal="center", vertical="center")
    ws.cell(2, 1).font = Font(name="Times New Roman", size=11, italic=True)
    ws.cell(2, 1).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 30
    ws.row_dimensions[3].height = 34
    for cell in ws[3]:
        cell.font = Font(name="Times New Roman", size=11, bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = TABLE_BORDER
    for row in ws.iter_rows(min_row=4, max_col=end_col):
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
            cell.font = Font(name="Times New Roman", size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = TABLE_BORDER
    for column in money_columns:
        for row in range(4, ws.max_row + 1):
            ws.cell(row, column).number_format = "#,##0"
    for column in quantity_columns:
        for row in range(4, ws.max_row + 1):
            ws.cell(row, column).number_format = "#,##0.###"
    for column in date_columns:
        for row in range(4, ws.max_row + 1):
            ws.cell(row, column).number_format = "dd/mm/yyyy"
    if total_row:
        for cell in ws[total_row]:
            cell.font = Font(name="Times New Roman", size=11, bold=True)
            cell.fill = TOTAL_FILL
            cell.border = TABLE_BORDER
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:{get_column_letter(end_col)}{max(ws.max_row, 3)}"
    ws.print_title_rows = "3:3"
    printable_end = print_end_column or end_col
    ws.print_area = f"A1:{get_column_letter(printable_end)}{max(ws.max_row, 3)}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.scale = None
    ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.5, bottom=0.5, header=0.2, footer=0.2)
    ws.print_options.horizontalCentered = True
    ws.oddFooter.center.text = "Trang &P / &N"
    ws.sheet_view.showGridLines = False


def _sheet_name(code: str, used: set[str]) -> str:
    cleaned = FORBIDDEN_SHEET_CHARACTERS.sub("-", _clean(code)).strip(" '") or "KHÔNG MÃ"
    base = f"NCC {cleaned}"
    candidate = base[:31]
    serial = 2
    while candidate.casefold() in used:
        suffix = f" ({serial})"
        candidate = base[:31 - len(suffix)] + suffix
        serial += 1
    used.add(candidate.casefold())
    return candidate


def _filename_token(value: Any) -> str:
    token = FORBIDDEN_FILENAME_CHARACTERS.sub("_", _clean(value)).strip(" .")
    return token[:60] or "NCC"


PAYABLE_HEADERS = [
    "Tháng", "Tên bếp", "Ngày, tháng", "Tên hàng", "Số lượng", "ĐVT", "NCC",
    "Giá mua", "Hỏng", "Thêm", "Giảm", "Thiếu", "SL thực tế", "Thành tiền",
]


def payable_workbook(data: dict[str, Any]) -> Workbook:
    period = f"Từ {_display_date(data['date_from'])} đến {_display_date(data['date_to'])}"
    workbook = Workbook()
    workbook.properties.creator = "Thành Đạt Phát"
    selected = set(data.get("statuses") or ("open", "partially_paid", "paid"))
    lines = [line for line in data["lines"] if line["status"] in selected]
    fields = ("base_qty", "damaged_qty", "added_qty", "reduced_qty", "missing_qty", "actual_qty")

    def detail_sheet(ws, items, title):
        ws.append(PAYABLE_HEADERS)
        for line in items:
            work_date = _excel_date(line["work_date"])
            ws.append([
                work_date.strftime("%m/%Y") if isinstance(work_date, date) else "",
                line["kitchen"], work_date, line["product_name"], _number(line["base_qty"]),
                line["unit"], line["supplier_code"], line["buy_price"],
                *[_number(line[f]) for f in fields[1:]], _vnd(line["amount"]),
            ])
        data_end = ws.max_row + 2
        sums = {f: quantity_cell(items, f) for f in fields}
        amount = sum(_vnd(line["amount"]) for line in items)
        ws.append(["TỔNG", "", "", "", sums["base_qty"], "", "", "",
                   *[sums[f] for f in fields[1:]], amount])
        total_row = ws.max_row + 2
        note = " · Có dòng đã đảo: tiền dòng để tra cứu, không phải số còn nợ." if any(
            line["status"] == "reversed" for line in items) else ""
        _style_sheet(
            ws, title=title,
            subtitle=f"{period} · Lượng {quantity_text(quantity_totals(items, 'actual_qty'))} · Tổng tiền {amount:,} VND{note}",
            headers=PAYABLE_HEADERS,
            widths=[10, 15, 13, 34, 18, 9, 14, 15, 18, 18, 18, 18, 20, 17],
            money_columns=(8, 14), quantity_columns=(5, 9, 10, 11, 12, 13),
            date_columns=(3,), total_row=total_row, print_end_column=14,
        )
        ws.auto_filter.ref = f"A3:N{data_end}"
        for row_number, line in enumerate(items, 4):
            if line["status"] == "reversed":
                for cell in ws[row_number]:
                    cell.fill = REVERSED_FILL
        for cell in ws[total_row]:
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.row_dimensions[total_row].height = max(32, 18 * len(quantity_totals(items, "actual_qty")))
        for row_number in range(4, ws.max_row + 1):
            for column in (5, 9, 10, 11, 12, 13):
                ws.cell(row_number, column).number_format = "#,##0.######"

    ws = workbook.active
    ws.title = "Công nợ phải trả"
    detail_sheet(ws, lines, "CÔNG NỢ PHẢI TRẢ")
    if not data["supplier"]:
        ws = workbook.create_sheet("Tổng NCC")
        headers = ["NCC", "Tên NCC", "Tổng lượng theo ĐVT", "Thành tiền", "Đã trả", "Còn trả"]
        ws.append(headers)
        used = {name.casefold() for name in workbook.sheetnames}
        for code in sorted({line["supplier_code"] for line in lines}):
            items = [line for line in lines if line["supplier_code"] == code]
            active = [line for line in items if line["status"] != "reversed"]
            ws.append([code, items[0].get("supplier_name") or code,
                       quantity_text(quantity_totals(active, "actual_qty")),
                       sum(line["amount"] for line in active),
                       sum(line["paid_amount"] for line in active),
                       sum(line["remaining_amount"] for line in active)])
            detail_sheet(workbook.create_sheet(_sheet_name(code, used)), items, f"CÔNG NỢ PHẢI TRẢ – {code}")
        active = [line for line in lines if line["status"] != "reversed"]
        ws.append(["TỔNG", "", quantity_text(quantity_totals(active, "actual_qty")),
                   sum(line["amount"] for line in active), sum(line["paid_amount"] for line in active),
                   sum(line["remaining_amount"] for line in active)])
        _style_sheet(ws, title="TỔNG CÔNG NỢ THEO NCC", subtitle=period + " · Theo bộ lọc; không cộng dòng đã đảo.",
                     headers=headers, widths=[16, 35, 35, 22, 22, 22],
                     money_columns=(4, 5, 6), total_row=ws.max_row + 2)
    workbook.active = 0
    return workbook


def register_payable_export_routes(app, ctx: dict[str, Any]) -> None:
    db_factory: Callable = ctx["db"]
    canonical_party_code: Callable = ctx["canonical_party_code"]

    @app.get("/api/debts/payables/export")
    def api_export_payables():
        today = date.today()
        try:
            with db_factory() as conn:
                conn.execute("BEGIN")
                data = payable_export_data(
                    conn,
                    date_from=request.args.get("from") or today.replace(day=1).isoformat(),
                    date_to=request.args.get("to") or today.isoformat(),
                    supplier=request.args.get("supplier") or "",
                    statuses=request.args.get("status"),
                    canonical_party_code=canonical_party_code,
                )
                workbook = payable_workbook(data)
            stream = io.BytesIO()
            white_print_style(workbook).save(stream)
            workbook.close()
            stream.seek(0)
            suffix = f"_{_filename_token(data['supplier'])}" if data["supplier"] else ""
            return send_file(
                stream,
                as_attachment=True,
                download_name=(
                    f"Cong_no_phai_tra{suffix}_{data['date_from']}_{data['date_to']}.xlsx"
                ),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except PayableExportError as error:
            return jsonify({"ok": False, "error": str(error), "code": error.code}), error.status
