"""Catalog invoice labels apply to editable drafts, never issued source records."""
import json


def invoice_name(conn, code, fallback):
    row=conn.execute('SELECT invoice_name FROM outgoing_product_names WHERE product_code=?',(code,)).fetchone()
    return str(row['invoice_name']).strip() if row and str(row['invoice_name'] or '').strip() else fallback


def refresh_editable_names(conn, timestamp, codes=None):
    """Caller owns the transaction; quantities, prices and reservations stay intact."""
    selected=set(codes) if codes is not None else None
    rows=conn.execute("""SELECT l.id,l.draft_id,l.product_code,l.product_name,
        COALESCE(NULLIF(TRIM(n.invoice_name),''),p.name) desired_name
        FROM outgoing_invoice_lines l JOIN outgoing_invoice_drafts d ON d.id=l.draft_id
        JOIN products p ON p.code=l.product_code
        LEFT JOIN outgoing_product_names n ON n.product_code=l.product_code
        WHERE d.status='draft' AND COALESCE(d.minvoice_status,'not_sent') NOT IN ('saved','saving','unknown')""").fetchall()
    changes=[]
    for row in rows:
        if selected is not None and row['product_code'] not in selected:continue
        if row['product_name']==row['desired_name']:continue
        conn.execute('UPDATE outgoing_invoice_lines SET product_name=? WHERE id=?',(row['desired_name'],row['id']))
        changes.append({'line_id':row['id'],'draft_id':row['draft_id'],'product_code':row['product_code'],
                        'before':row['product_name'],'after':row['desired_name']})
    if changes:
        conn.execute("""INSERT INTO audit_log(event_type,entity_type,entity_id,status,message,metadata_json,created_at)
          VALUES('outgoing.draft_names','catalog','','ok','',?,?)""",
          (json.dumps({'changes':changes,'quantities_and_money_unchanged':True},ensure_ascii=False),timestamp))
    return len(changes)
