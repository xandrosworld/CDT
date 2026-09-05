"""Read real providers twice into a DB copy; never post inventory or issue invoices."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--direction', choices=['input', 'output', 'both'], default='both')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    target = output / 'copy.sqlite3'
    with closing(sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True)) as read, closing(sqlite3.connect(target)) as write:
        read.backup(write)
    cli = str(Path(os.environ['APPDATA'])/'npm/railway.cmd')
    fetched = subprocess.run([cli,'variables','--json'],capture_output=True,text=True,encoding='utf-8',check=True)
    variables = json.loads(fetched.stdout)
    os.environ.update({k:v for k,v in variables.items() if k.startswith(('MSMI_','MINVOICE_'))})
    os.environ.update(TDP_DB_PATH=str(target),TDP_DATA_DIR=str(output),TDP_EXPORT_DIR=str(output/'exports'))
    from . import server
    from .invoice_input_sync import sync_input_batch
    from .invoice_output_sync import sync_output_batch
    from .invoice_workbench import prepare_sync_batch
    from .invoice_payment_scope import issued_invoice_payment_scope, InvoicePaymentScopeError
    server.init_database(sync_master=False)
    report = {'runs':[]}
    with server.db() as conn:
        tenant = conn.execute('SELECT tenant FROM msmi_invoices LIMIT 1').fetchone()[0]
        for direction, source, factory, sync, table in [
            ('input','msmi',server.create_msmi_client,sync_input_batch,'msmi_invoices'),
            ('output','minvoice',server.create_minvoice_client,sync_output_batch,'outgoing_source_invoices'),
        ]:
            if args.direction not in ('both', direction):
                continue
            batch,_=prepare_sync_batch(conn,tenant=tenant,source=source,invoice_type=direction,
                                      date_from='2026-08-01',date_to='2026-08-31',now_iso=server.now_iso)
            client = factory()
            if getattr(client, 'is_test_environment', False) is True:
                report['runs'].append({'direction':direction,'blocked':'provider_test_environment'})
                print(json.dumps(report['runs'][-1]), flush=True)
                continue
            for attempt in (1,2):
                for segment in range(1, 21):
                    result=sync(conn,client,batch['id'],server.now_iso,max_pages=50,page_size=199)
                    conn.commit()
                    print(json.dumps({'direction':direction,'attempt':attempt,'segment':segment,
                                      'complete':result.get('complete'),'new':result.get('new_invoices'),
                                      'known':result.get('known_invoices'),'pages':result.get('pages')}),flush=True)
                    if result.get('complete') or result.get('status') == 'error': break
                count=conn.execute('SELECT COUNT(*) FROM '+table+" WHERE invoice_date BETWEEN '2026-08-01' AND '2026-08-31'").fetchone()[0]
                info={'direction':direction,'attempt':attempt,'count':count,
                      **{k:result.get(k) for k in ['complete','new_invoices','known_invoices','pages','status','error_count']}}
                report['runs'].append(info);print(json.dumps(info),flush=True)
                conn.commit()
        report['payment_scopes'] = []
        for profile in conn.execute('SELECT contractor FROM outgoing_buyer_profiles'):
            try:
                scope=issued_invoice_payment_scope(conn,profile[0],'2026-08-01','2026-08-31')
                report['payment_scopes'].append({'ok':True,'count':len(scope['invoices']),'total':scope['totals']['total_amount']})
            except InvoicePaymentScopeError as error:
                report['payment_scopes'].append({'ok':False,'code':error.code})
        first=conn.execute('SELECT raw_json FROM outgoing_source_invoices LIMIT 1').fetchone()
        report['output_raw_field_names']=sorted(json.loads(first[0])) if first else []
        report['stock_entries']=conn.execute('SELECT COUNT(*) FROM invoice_inventory_ledger').fetchone()[0]
    (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(output/'result.json'),'scopes':report['payment_scopes'],'stock_entries':report['stock_entries']}))


if __name__ == '__main__':main()
