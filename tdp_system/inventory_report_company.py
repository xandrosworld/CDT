"""Inventory report identity comes from company settings, never sample workbooks."""

DEFAULT_COMPANY = {
    'company': 'CÔNG TY TNHH THỰC PHẨM THÀNH ĐẠT PHÁT',
    'company_address': 'Số nhà 112 ngõ 366, Đường Hùng Vương, Phường Hồng Bàng, Thành phố Hải Phòng, Việt Nam',
    'company_tax_code': '0202265016',
}


def report_company(conn):
    settings = dict(conn.execute(
        "SELECT key,value FROM settings WHERE key IN ('company','company_address','company_tax_code')"
    ))
    return {key: str(settings.get(key) or value).strip() or value for key, value in DEFAULT_COMPANY.items()}


def write_company_header(sheet, model):
    info = dict(DEFAULT_COMPANY, **model.get('company_info', {}))
    for row, value in enumerate((info['company'], 'Địa chỉ: ' + info['company_address'], 'MST: ' + info['company_tax_code']), 1):
        cell = sheet.cell(row, 1)
        cell.value = value
        cell.data_type = 's'
