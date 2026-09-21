"""Authorized negative-stock rules: KKKNT and explicit BK orders."""
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
    """Return codes whose scoped rows all allow negative stock; mixed tax rows stay guarded."""
    names={r['code']:r['name'] for r in conn.execute('SELECT code,name FROM products')}
    allowed=set();blocked=set()
    for row in orders:
        code=row['product_code']
        name=row['product_name'] if 'product_name' in row.keys() else names.get(code,'')
        marked='purchase_list' in row.keys() and str(row['purchase_list']).strip() in {'1','True'}
        (allowed if is_kkknt(row['tax']) or marked or has_bk_name(name) else blocked).add(code)
    return allowed-blocked
