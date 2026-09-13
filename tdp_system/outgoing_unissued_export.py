"""Same 13-column artwork as M-Invoice, with exact unissued order quantities.

This is a read-only reconciliation export. Invoiceable catch-up files must use
the ordinary stock-checked draft/allocation pipeline instead.
"""
import io
import zipfile
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

try:
    from .invoice_tax_export import build_invoice_workbook, _safe_name
    from .outgoing_unissued import unissued_workbook
except ImportError:
    from invoice_tax_export import build_invoice_workbook, _safe_name
    from outgoing_unissued import unissued_workbook


def unissued_template_zip(payload, template_dir, tax_percent):
    groups = defaultdict(dict)
    for row in payload['details']:
        qty = Decimal(str(row['unissued_qty'])).quantize(Decimal('.000001'), rounding=ROUND_HALF_UP)
        if qty <= 0:
            continue
        vat = tax_percent(row['tax'])
        price = Decimal(str(row['unit_price']))
        nature = str(row.get('invoice_nature') or '1')
        key = (row['product_code'], row['unit'].strip().casefold(), price, nature)
        lines = groups[(row['contractor'], vat)]
        item = lines.setdefault(key, {'contractor':row['contractor'], 'product_code':row['product_code'],
            'product_name':row['product_name'], 'unit':row['unit'], 'unit_price':price,
            'invoice_nature':nature, 'qty':Decimal(0)})
        item['qty'] += qty
    if not groups:
        raise ValueError('Không còn hàng chưa xuất hóa đơn trong phạm vi đã chọn.')
    output = io.BytesIO()
    count = 0
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        filenames = set()
        for (party, vat), group in sorted(groups.items()):
            lines = []
            for key, row in sorted(group.items()):
                amount = (row['qty'] * row['unit_price']).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                lines.append({**row, 'qty':float(row['qty']), 'unit_price':float(row['unit_price']), 'amount':float(amount)})
            book, _ = build_invoice_workbook(lines, vat_percent=vat, template_dir=template_dir)
            label = 'KKKNT' if vat == -2 else 'KCT' if vat == -1 else f'VAT{vat:g}'
            name = f"CHUA_XUAT_{_safe_name(party)}_{label}_DEN_{payload['asof']}.xlsx"
            if name.casefold() in filenames:
                raise ValueError('Tên file nhà thầu bị trùng; cần kiểm tra lại mã nhà thầu.')
            filenames.add(name.casefold()); archive.writestr(name, book); count += 1
        archive.writestr('DOI_CHIEU_CHI_TIET.xlsx', unissued_workbook(payload).getvalue())
        guide = [
            'BẢNG HÀNG CHƯA XUẤT HÓA ĐƠN – CÙNG MẪU 13 CỘT',
            f"Đơn đã duyệt đến hết {payload['asof']}. Nhà thầu: {payload['contractor'] or 'Tất cả'}.",
            'Các file CHUA_XUAT dùng để đối chiếu; gồm cả hàng thiếu đầu vào và phần lẻ chưa đủ xuất. Không dùng bộ đối chiếu này để nhập M-Invoice.',
            'Muốn xuất bù: bấm “Tải file xuất bù đủ điều kiện”. Web kiểm tra lại hóa đơn đã ký, đơn cũ và tồn kho rồi tạo bộ file đưa lên M-Invoice.',
            'Lượng chưa xuất = lượng thực giao của đơn đã duyệt sau trả hàng − lượng hóa đơn đã phát hành đã đối chiếu. Giữ nguyên phần lẻ trong bản đối chiếu.',
            'Cùng mã, đơn vị, giá bán, thuế và tính chất được cộng lượng. Khác giá giữ dòng riêng; không đổi giá bán trên đơn.',
            'Tải bảng hoặc xuất bù không duyệt lại đơn, không ghi thêm doanh thu hay công nợ. Tải file chưa tính là đã phát hành hóa đơn.',
            'Ngày chọn ở web là mốc đơn hàng. Ngày hóa đơn thực tế chọn khi phát hành trên M-Invoice.',
        ]
        if payload['warnings']:
            guide += ['CÒN HÓA ĐƠN CẦN ĐỐI CHIẾU – số chưa xuất có thể thay đổi sau khi xử lý:']
            guide += [w['message'] for w in payload['warnings']]
        archive.writestr('HUONG_DAN.txt', '\n'.join(guide).encode('utf-8-sig'))
    output.seek(0)
    return output, count
