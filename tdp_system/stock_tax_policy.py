"""Customer-approved negative-stock exception, exclusively for KKKNT items."""

def is_kkknt(value):
    return str(value if value is not None else '').strip().upper().replace(' ', '') in {
        'KKKNT', 'KHÔNGKÊKHAI', 'KHONGKEKHAI', '-2', '-2.0',
    }


def kkknt_codes(conn):
    if 'tax' not in {r['name'] for r in conn.execute('PRAGMA table_info(products)')}:
        return set()
    return {r['code'] for r in conn.execute('SELECT code,tax FROM products') if is_kkknt(r['tax'])}


def exempt_order_codes(conn, orders):
    """A mixed-tax product must not exempt its taxable lines or holds."""
    codes = kkknt_codes(conn)
    for row in orders:
        if not is_kkknt(row['tax']):
            codes.discard(row['product_code'])
    return codes
