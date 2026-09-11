"""Tax classification and the separate, explicit BK exception for order exports."""
import re


def has_bk_name(value):
    return bool(re.search(r'(?<!\w)BK(?!\w)', str(value or ''), re.IGNORECASE))

def is_kkknt(value):
    return str(value if value is not None else '').strip().upper().replace(' ', '') in {
        'KKKNT', 'KHÔNGKÊKHAI', 'KHONGKEKHAI', '-2', '-2.0',
    }


def kkknt_codes(conn):
    if 'tax' not in {r['name'] for r in conn.execute('PRAGMA table_info(products)')}:
        return set()
    return {r['code'] for r in conn.execute('SELECT code,tax FROM products') if is_kkknt(r['tax'])}


def exempt_order_codes(conn, orders):
    """Only rows explicitly named BK may exceed stock; tax is not permission."""
    names={r['code']:r['name'] for r in conn.execute('SELECT code,name FROM products')}
    allowed=set();blocked=set()
    for row in orders:
        code=row['product_code']
        name=row['product_name'] if 'product_name' in row.keys() else names.get(code,'')
        (allowed if has_bk_name(name) else blocked).add(code)
    return allowed-blocked
