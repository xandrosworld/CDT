"""Verify the settled Sep 3 purchase deductions on an isolated snapshot only."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--workbook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    source = args.snapshot.resolve(); database = out / 'copy.sqlite3'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    file_hash = hashlib.sha256(args.workbook.read_bytes()).hexdigest()
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as src, sqlite3.connect(database) as dst:
        src.backup(dst)
    os.environ.update(TDP_DATA_DIR=str(out), TDP_DB_PATH=str(database), TDP_EXPORT_DIR=str(out/'exports'),
        MSMI_API_BASE_URL='http://127.0.0.1:9', MSMI_API_TOKEN='offline-test',
        MINVOICE_API_BASE_URL='http://127.0.0.1:9', MINVOICE_USERNAME='offline-test', MINVOICE_PASSWORD='offline-test')
    from . import server
    from .purchase_money_adjustments import DEDUCTION_KIND, DEDUCTION_LABEL
    from .payable_export import payable_export_data, payable_workbook
    server.connector_config_paths = lambda: []
    server.init_database(sync_master=False)
    client = server.app.test_client()
    raw = args.workbook.read_bytes()
    def result(response):
        assert response.status_code == 200, (response.status_code, response.get_json())
        return response.get_json()
    def analyze():
        return result(client.post('/api/import/analyze', data={'continuous':'1',
            'file':(io.BytesIO(raw),args.workbook.name)}, content_type='multipart/form-data'))
    def confirm(analysis, sheets):
        return result(client.post('/api/import/confirm', json={'token':analysis['token'],
            'sheets':sheets, 'work_date':'2026-09-03', 'state_hash':analysis['stateHash']}))
    with server.db() as conn:
        old_orders = [tuple(r) for r in conn.execute('SELECT * FROM orders ORDER BY id')]
        assert not conn.execute("SELECT 1 FROM batches WHERE work_date='2026-09-03'").fetchone(), 'Use a snapshot before Sep 3 was imported'
    first = confirm(analyze(), ['03.09'])
    with server.db() as conn:
        batch = conn.execute("SELECT id FROM batches WHERE work_date='2026-09-03'").fetchone()[0]
    result(client.post(f'/api/batches/{batch}/approve'))
    protected_tables = ('orders','receivable_ledger_lines','invoice_inventory_ledger','inventory_transactions',
                        'physical_stock_openings','physical_stock_movements')
    def protected():
        with server.db() as conn:
            existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return {t:[tuple(r) for r in conn.execute('SELECT * FROM "'+t+'" ORDER BY rowid')]
                    for t in protected_tables if t in existing}
    before = protected()
    def purchase():
        preview = result(client.post('/api/purchase-orders/import/preview', data={
            'batch_id':str(batch), 'file':(io.BytesIO(raw),args.workbook.name)}, content_type='multipart/form-data'))
        assert preview['error_rows']==0, preview['issues']
        return result(client.post('/api/purchase-orders/import/confirm', json={'token':preview['token'],'confirmed':True}))
    purchased = purchase()
    assert before == protected(), 'Purchase import changed sales/receivables/stock'
    with server.db() as conn:
        rows = [dict(r) for r in conn.execute('SELECT * FROM purchase_workbook_lines WHERE batch_id=? ORDER BY source_row',(batch,))]
        deductions = [r for r in rows if r['line_kind']==DEDUCTION_KIND]
        assert len(rows)==273 and len(deductions)==2
        assert [r['source_row'] for r in deductions]==[157,158]
        assert sum(r['amount'] for r in deductions)==-207000
        assert all(r['actual_qty']==r['base_qty']==r['buy_price']==0 and r['order_id'] is None for r in deductions)
        assert all(r['supplier']=='phong' for r in deductions)
        rice = next(r for r in rows if r['source_row']==103)
        assert (rice['supplier'],rice['actual_qty'],rice['amount'])==('kho',.54,14040)
        goods = sum(r['amount'] for r in rows if r['supplier']=='phong' and r['line_kind']=='goods')
        net = conn.execute("SELECT SUM(amount) FROM payable_ledger_lines WHERE batch_id=? AND supplier_code='phong' AND status!='reversed'",(batch,)).fetchone()[0]
        assert net==goods-207000, (net,goods)
        data = payable_export_data(conn,date_from='2026-09-03',date_to='2026-09-03',supplier='phong',canonical_party_code=server.canonical_party_code)
        workbook = payable_workbook(data); workbook.save(out/'phong-payable.xlsx')
        sheet = workbook['Công nợ phải trả']
        assert sheet.max_column==14 and sheet.cell(sheet.max_row,14).value==net
        assert sum(r[13].value for r in sheet.iter_rows(min_row=4) if str(r[3].value).startswith(DEDUCTION_LABEL))==-207000
        workbook.close()
        revisions = conn.execute('SELECT COUNT(*) FROM payable_ledger_revisions').fetchone()[0]
    repeat = purchase()
    assert repeat['idempotent']
    assert before==protected()
    with server.db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM payable_ledger_revisions').fetchone()[0]==revisions
        assert [tuple(r) for r in conn.execute('SELECT * FROM orders ORDER BY id')][:len(old_orders)]==old_orders
        sales_count = conn.execute('SELECT COUNT(*) FROM orders WHERE batch_id=?',(batch,)).fetchone()[0]
        assert sales_count==352
        integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
        assert integrity=='ok'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    assert hashlib.sha256(args.workbook.read_bytes()).hexdigest()==file_hash
    report={'ok':True,'batch_id':batch,'sales_rows':sales_count,'purchase_rows':len(rows),'deduction_rows':2,
        'deduction_amount':207000,'phong_goods':goods,'phong_net':net,'old_orders_unchanged':len(old_orders),
        'protected_tables_unchanged':list(before),'repeat_no_extra_history':True,'source_snapshot_unchanged':True,
        'source_file_unchanged':True,'integrity':integrity}
    (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__': main()
