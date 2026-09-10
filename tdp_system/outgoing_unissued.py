"""Cumulative approved demand less issued invoices; downloads are never issues."""
from collections import defaultdict
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill


def _identity(r,local=False):
    return (str(r['issued_invoice_series'] if local else r['invoice_series']).strip().upper(),
            str(r['issued_invoice_number'] if local else r['invoice_number']).strip(),
            str((r['issued_invoice_date'] or r['invoice_date']) if local else r['invoice_date']).strip())


def issued_allocations(conn,asof='9999-12-31'):
    """Prefer explicit order links; otherwise allocate mapped M-Invoice FIFO once."""
    orders=[dict(r) for r in conn.execute("SELECT o.* FROM orders o JOIN batches b ON b.id=o.batch_id WHERE b.status='approved' AND o.work_date<=? ORDER BY o.work_date,o.id",(asof,))]
    quantities=defaultdict(float);warnings=[];linked=set()
    sources=[dict(r) for r in conn.execute("SELECT * FROM outgoing_source_invoices WHERE source='minvoice' AND invoice_date<=? ORDER BY invoice_date,id",(asof,))]
    by_identity=defaultdict(list)
    for s in sources:by_identity[_identity(s)].append(s)
    for d in conn.execute("SELECT * FROM outgoing_invoice_drafts WHERE status='issued' AND COALESCE(issued_invoice_date,invoice_date)<=?",(asof,)):
        matching=by_identity.get(_identity(d,True),[])
        if matching and any(s['source_status_class'] in ('cancelled','replaced','adjusted') for s in matching):
            warnings.append({'contractor':d['contractor'],'message':'Hóa đơn '+str(d['issued_invoice_number'])+' đã thay đổi trạng thái trên M-Invoice; cần đối chiếu.'})
            linked.update(s['id'] for s in matching);continue
        # A confirmed local issue carries exact order lineage. Same invoice is not counted again.
        if matching:
            local=defaultdict(float)
            for r in conn.execute('SELECT product_code,qty FROM outgoing_order_allocations WHERE draft_id=?',(d['id'],)):
                local[r['product_code']]+=r['qty']
            for s in matching:
                posted={r['product_code']:r['qty'] for r in conn.execute("""SELECT product_code,-SUM(qty_delta) qty FROM invoice_inventory_ledger
                    WHERE direction='output' AND status='posted' AND source_invoice_table='outgoing_source_invoices'
                    AND source_invoice_id=? GROUP BY product_code""",(s['id'],))}
                if s['source_status_class']!='issued' or s['sync_status']!='synced' or set(local)!=set(posted) or any(abs(q-posted.get(code,0))>1e-8 for code,q in local.items()):
                    warnings.append({'contractor':d['contractor'],'message':'Hóa đơn '+str(d['issued_invoice_number'])+' chưa khớp trạng thái/lượng giữa xác nhận và M-Invoice; số chưa xuất cần đối chiếu.'})
        linked.update(s['id'] for s in matching)
        for r in conn.execute('SELECT order_id,qty FROM outgoing_order_allocations WHERE draft_id=?',(d['id'],)):quantities[r['order_id']]+=r['qty']
    profiles=defaultdict(list)
    for r in conn.execute("SELECT contractor,tax_code FROM outgoing_buyer_profiles WHERE TRIM(COALESCE(tax_code,''))!=''"):
        profiles[r['tax_code'].strip().upper()].append(r['contractor'])
    indexed=defaultdict(list)
    for o in orders:indexed[(o['contractor'],o['product_code'],o['unit'].strip().casefold())].append(o)
    earliest=min((o['work_date'] for o in orders),default=asof)
    seen=set()
    for s in sources:
        if s['id'] in linked or s['invoice_date']<earliest or s['source_status_class'] in ('draft','cancelled','replaced'):continue
        parties=profiles.get(s['buyer_tax_code'].strip().upper(),[])
        if len(parties)!=1:
            if s['source_status_class']=='issued':warnings.append({'contractor':'','message':'Hóa đơn '+s['invoice_number']+' chưa ghép duy nhất với nhà thầu; chưa trừ vào bảng cộng dồn.'})
            continue
        party=parties[0]
        if not any(o['contractor']==party and o['work_date']<=s['invoice_date'] for o in orders):continue
        identity=_identity(s)
        if identity in seen:
            warnings.append({'contractor':party,'message':'Hóa đơn '+s['invoice_number']+' trùng định danh nguồn; cần đối chiếu.'});continue
        seen.add(identity)
        if s['source_status_class']!='issued' or s['sync_status']!='synced' or s['stock_status'] not in ('posted','not_inventory'):
            warnings.append({'contractor':party,'message':'Hóa đơn '+s['invoice_number']+' chưa đủ đối chiếu mã/lượng để trừ khỏi đơn.'});continue
        # The posted stock ledger already includes reviewed conversions and reversals.
        lines=conn.execute("""SELECT il.product_code,p.unit,-SUM(il.qty_delta) qty FROM invoice_inventory_ledger il
            JOIN products p ON p.code=il.product_code WHERE il.direction='output' AND il.status='posted'
            AND il.source_invoice_table='outgoing_source_invoices' AND il.source_invoice_id=? GROUP BY il.product_code,p.unit""",(s['id'],)).fetchall()
        for line in lines:
            remaining=max(float(line['qty']),0)
            candidates=indexed.get((party,line['product_code'],line['unit'].strip().casefold()),[])
            for o in candidates:
                if o['work_date']>s['invoice_date']:continue
                need=max(o['actual_delivered']-o['customer_return_qty']-quantities[o['id']],0)
                take=min(need,remaining);quantities[o['id']]+=take;remaining-=take
                if remaining<=1e-8:break
    return dict(quantities),warnings


def unissued_payload(conn,asof,contractor=''):
    # The cutoff selects order dates. An invoice issued later can settle those orders.
    issued,warnings=issued_allocations(conn)
    orders=[dict(r) for r in conn.execute("""SELECT o.* FROM orders o JOIN batches b ON b.id=o.batch_id
        WHERE b.status='approved' AND o.work_date<=? AND (?='' OR o.contractor=?) ORDER BY o.work_date,o.id""",(asof,contractor,contractor))]
    drafted={r['order_id']:r['qty'] for r in conn.execute("SELECT l.order_id,SUM(l.qty) qty FROM outgoing_order_allocations l JOIN outgoing_invoice_drafts d ON d.id=l.draft_id WHERE d.status='draft' GROUP BY l.order_id")}
    grouped={};details=[]
    for o in orders:
        q=max(o['actual_delivered']-o['customer_return_qty'],0)
        if q<=1e-8:continue
        done=issued.get(o['id'],0);left=max(q-done,0)
        r={'order_id':o['id'],'work_date':o['work_date'],'contractor':o['contractor'],'product_code':o['product_code'],
           'product_name':o['product_name'],'unit':o['unit'],'approved_qty':q,'issued_qty':done,'drafted_qty':drafted.get(o['id'],0),'unissued_qty':left,'unit_price':o['sell_price']}
        details.append(r)
        key=(o['contractor'],o['product_code'],o['unit'].strip().casefold())
        g=grouped.setdefault(key,{**r,'approved_qty':0,'issued_qty':0,'drafted_qty':0,'unissued_qty':0,'first_date':o['work_date'],'last_date':o['work_date']})
        for field in ('approved_qty','issued_qty','drafted_qty','unissued_qty'):g[field]+=r[field]
        g['last_date']=o['work_date']
    rows=[r for r in grouped.values() if r['unissued_qty']>1e-8]
    rows.sort(key=lambda r:(r['contractor'],r['product_name'],r['product_code']))
    totals=defaultdict(lambda:defaultdict(float))
    for r in grouped.values():
        for field in ('approved_qty','issued_qty','drafted_qty','unissued_qty'):totals[r['unit'].strip().casefold()][field]+=r[field]
    warnings=[w for w in warnings if not contractor or not w['contractor'] or w['contractor']==contractor]
    return {'asof':asof,'contractor':contractor,'rows':rows,'details':[r for r in details if r['unissued_qty']>1e-8],
            'totals_by_unit':dict(totals),'source_order_rows':len(details),'unissued_order_rows':sum(r['unissued_qty']>1e-8 for r in details),
            'warnings':warnings,'reconciliation_complete':not warnings,
            'policy':'Cộng dồn đơn đã duyệt đến ngày chọn, trừ lượng hóa đơn đã phát hành được đồng bộ hoặc xác nhận đến hiện tại, kể cả hóa đơn phát hành sau ngày đơn. Tải file và tạo nháp không làm giảm lượng chưa xuất.'}


def unissued_workbook(payload):
    w=Workbook();s=w.active;s.title='Chua xuat cong don'
    headers=['Nhà thầu','Mã hàng','Tên hàng','ĐVT','Ngày đơn đầu','Ngày đơn cuối','Lượng đã duyệt','Đã phát hành','Đang nháp (chưa phát hành)','Chưa xuất hóa đơn']
    s.append(headers)
    for r in payload['rows']:s.append([r[k] for k in ('contractor','product_code','product_name','unit','first_date','last_date','approved_qty','issued_qty','drafted_qty','unissued_qty')])
    s=w.create_sheet('Chi tiet theo ngay');s.append(['Dòng đơn','Ngày đơn','Nhà thầu','Mã','Tên','ĐVT','Đã duyệt','Đã phát hành','Đang nháp','Chưa xuất','Giá trên đơn'])
    for r in payload['details']:s.append([r[k] for k in ('order_id','work_date','contractor','product_code','product_name','unit','approved_qty','issued_qty','drafted_qty','unissued_qty','unit_price')])
    note=w.create_sheet('Ghi chu');note.append(['Cộng dồn đến ngày',payload['asof']]);note.append(['Cách tính',payload['policy']])
    note.append(['Đối chiếu M-Invoice','Nếu đã ký bên ngoài, đồng bộ hóa đơn hoặc xác nhận đúng số hóa đơn đã phát hành trước khi lập tiếp.'])
    for warning in payload['warnings']:note.append(['Cần đối chiếu',warning['message']])
    for s in w:
        s.freeze_panes='A2';s.auto_filter.ref=s.dimensions
        for cell in s[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='163247')
        for col in s.columns:s.column_dimensions[col[0].column_letter].width=min(55,max(16,max(len(str(c.value or '')) for c in col)+2))
    output=BytesIO();w.save(output);output.seek(0);return output
