"""Read-only purchase-day suggestions for monthly supplementary schedules."""
from collections import defaultdict
try:
    from .purchase_summary_export import collect_purchase_summary_rows, PurchaseSummaryError
except ImportError:
    from purchase_summary_export import collect_purchase_summary_rows, PurchaseSummaryError


def purchase_sources(conn, start, end, codes):
    result=defaultdict(list); warnings=[]
    identities={r['cccd']:dict(r) for r in conn.execute('SELECT cccd,issue_date,issue_place FROM people')}
    for batch in conn.execute("SELECT * FROM batches WHERE status='approved' AND work_date BETWEEN ? AND ? ORDER BY work_date,id",(start,end)):
        batch=dict(batch)
        if conn.execute("SELECT 1 FROM batch_bk_approvals a JOIN bk_import_documents d ON d.id=a.document_id WHERE a.batch_id=? AND d.status='posted'",(batch['id'],)).fetchone():continue
        orders=[dict(r) for r in conn.execute('SELECT * FROM orders WHERE batch_id=?',(batch['id'],))]
        canonical=[dict(r) for r in conn.execute('SELECT * FROM purchase_workbook_lines WHERE batch_id=?',(batch['id'],))]
        table='purchase_workbook_lines' if canonical else 'orders'
        bykey={f"{batch['id']}:{table}:{r['id']}":r for r in canonical or orders}
        if not any(r['product_code'] in codes for r in bykey.values()):continue
        try: rows=collect_purchase_summary_rows(conn,batch,orders)
        except PurchaseSummaryError as exc:
            warnings.append(f"Ngày {batch['work_date']}: {exc}");continue
        for row in rows:
            source=bykey.get(':'.join(row['selection_key'].split(':')[:3]),{})
            code=source.get('product_code')
            if code not in codes or not start<=row['work_date']<=end:continue
            used=conn.execute("SELECT COALESCE(SUM(l.qty),0) FROM bk_import_lines l JOIN bk_import_documents d ON d.id=l.document_id WHERE d.status='posted' AND instr(l.note,?)>0",('[TDP-SOURCE:'+row['selection_key']+']',)).fetchone()[0]
            remaining=max(0,float(row['quantity'])-float(used))
            if remaining<=0.000001:continue
            result[code].append({'source_key':row['selection_key'],'document_date':row['work_date'],
                'source_party':row['seller'],'cccd':row['cccd'],'address':row['address'],
                'issue_date':identities.get(row['cccd'],{}).get('issue_date',''),
                'issue_place':identities.get(row['cccd'],{}).get('issue_place',''),
                'purchase_qty':remaining,'unit':row['unit'],'unit_cost':row['buy_price'],
                'source_description':f"Đơn ngày {batch['work_date']} · dòng {row['source_ref']}"})
    return result,warnings
