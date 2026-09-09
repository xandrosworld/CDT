"""Synthetic approval fixtures. No customer data or external connectors."""
from .test_batch_bk_approval import BatchBKApprovalTests
from . import server
from waitress import serve

BatchBKApprovalTests.setUpClass()
case = BatchBKApprovalTests()
case.setUp()
good = case.batch
with server.db() as conn:
    case.batch = conn.execute("INSERT INTO batches(work_date,source_name,status,created_at) VALUES('2026-09-03','Đơn thiếu giá.xlsx','draft',?)", (server.now_iso(),)).lastrowid
    bad = case.batch
    oid = case.add_line(conn)
    conn.execute('UPDATE orders SET sell_price=0 WHERE id=?', (oid,))

@server.app.get('/fixture/bk-status')
def status():
    with server.db() as conn:
        return {'good': good, 'bad': bad,
                'lines': conn.execute('SELECT count(*) FROM invoice_inventory_ledger').fetchone()[0],
                'qty': conn.execute('SELECT coalesce(sum(qty_delta),0) FROM invoice_inventory_ledger').fetchone()[0]}

serve(server.app, host='127.0.0.1', port=18856, threads=4)
