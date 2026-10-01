"""Read-only reprinting of posted purchase statements, independent of stock deficits."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import json


def period(start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first > last: raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Chọn đúng Từ ngày và Đến ngày để tìm bảng kê đã lưu.') from None
    return first.isoformat(), last.isoformat()


def documents(conn, start, end):
    start,end=period(start,end)
    rows=conn.execute('''SELECT d.id,d.filename,d.confirmed_at,MIN(l.document_date) date_from,
        MAX(l.document_date) date_to,COUNT(*) row_count,SUM(l.amount) amount_total
        FROM bk_import_documents d JOIN bk_import_lines l ON l.document_id=d.id
        WHERE d.status='posted' AND l.document_date BETWEEN ? AND ?
        GROUP BY d.id ORDER BY date_from,d.id''',(start,end))
    items=[dict(r) for r in rows]
    linked=set()
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='batch_bk_approvals'").fetchone():
        linked={r[0] for r in conn.execute('SELECT document_id FROM batch_bk_approvals')}
    for item in items:
        item['origin']='order' if item['id'] in linked else 'import'
        item['origin_label']='Bảng cũ từ duyệt đơn' if item['origin']=='order' else 'Bảng bổ sung / nhập Excel đã ghi kho'
    return items


def saved_rows(conn, start, end, ids):
    start,end=period(start,end)
    if not isinstance(ids,list) or not ids or len(ids)>500 or any(type(i)!=int or i<=0 for i in ids):
        raise ValueError('Chọn ít nhất một bảng kê đã lưu để xem hoặc in.')
    available={r['id'] for r in documents(conn,start,end)}
    if not set(ids)<=available:
        raise ValueError('Có bảng kê đã hoàn tác hoặc không thuộc kỳ đang chọn. Bấm Xem bảng kê đã lưu để cập nhật danh sách.')
    marks=','.join('?' for _ in set(ids))
    return [dict(r) for r in conn.execute(f'''SELECT l.* FROM bk_import_lines l
        JOIN bk_import_documents d ON d.id=l.document_id
        WHERE d.status='posted' AND l.document_id IN ({marks}) AND l.document_date BETWEEN ? AND ?
        ORDER BY l.document_date,l.document_id,l.id''',(*sorted(set(ids)),start,end))]


def workbook(conn, body, ctx):
    try:
        from .purchase_summary_export import build_purchase_summary_workbook, _key, _resolved_identity
        from .receipt_export import enrich_receipt_identity_rows, build_purchase_documents_workbook, ReceiptExportError, RECEIPT_MAX_DAILY_AMOUNT
    except ImportError:
        from purchase_summary_export import build_purchase_summary_workbook, _key, _resolved_identity
        from receipt_export import enrich_receipt_identity_rows, build_purchase_documents_workbook, ReceiptExportError, RECEIPT_MAX_DAILY_AMOUNT
    start,end=period(body.get('from'),body.get('to'))
    saved=saved_rows(conn,start,end,body.get('document_ids'))
    people=defaultdict(list)
    for p in conn.execute('SELECT * FROM people'):people[_key(p['name'])].append(dict(p))
    linked={r['document_id']:r['batch_id'] for r in conn.execute('SELECT document_id,batch_id FROM batch_bk_approvals')} if conn.execute("SELECT 1 FROM sqlite_master WHERE name='batch_bk_approvals'").fetchone() else {}
    rows=[];missing=set()
    for r in saved:
        batch_id=linked.get(r['document_id'])
        if batch_id is not None:
            canonical=conn.execute('SELECT 1 FROM purchase_workbook_lines WHERE batch_id=? LIMIT 1',(batch_id,)).fetchone()
            table='purchase_workbook_lines' if canonical else 'orders'
            source=conn.execute(f'SELECT * FROM {table} WHERE batch_id=? AND id=?',(batch_id,r['source_line'])).fetchone()
            if not source or source['product_code']!=r['product_code'] or source['work_date']!=r['document_date']:
                # Saved seller revisions are applied below when available.
                matches=people[_key(r['source_party'])]
            else:
                source=dict(source)
                order=conn.execute('SELECT * FROM orders WHERE batch_id=? AND id=?',(batch_id,source.get('order_id'))).fetchone() if canonical else source
                product=conn.execute('SELECT * FROM products WHERE code=?',(r['product_code'],)).fetchone()
                seller,identity,address,issues=_resolved_identity(dict(order) if order else None,dict(product) if product else None,people)
                matches=[] if issues else [dict(name=seller,cccd=identity,address=address)]
        else:
            matches=people[_key(r['source_party'])]
        if len(matches)!=1:
            missing.add(r['source_party'] or '(chưa có tên người bán)');continue
        p=matches[0]
        rows.append(dict(work_date=r['document_date'],seller=p['name'],cccd=p['cccd'],address=p['address'],
            product_name=r['product_name_snapshot'],unit=r['unit_snapshot'],quantity=r['qty'],buy_price=r['unit_cost'],
            amount=r['amount'],source_ref=r['source_line'],reference=r['source_reference'],supplier=r['source_party']))
    if missing:
        raise ValueError('Chưa xác định được hồ sơ Người bán: '+', '.join(sorted(missing))+'. Cần đối chiếu tên với danh mục người bán trước khi in. Có thể quay lại danh sách để chọn riêng bảng kê khác; các bảng kê đã lưu vẫn được giữ nguyên.')
    by_document=defaultdict(list)
    for row,source in zip(rows,saved):by_document[source['document_id']].append(row)
    # Document-only seller revisions are separate from the immutable stock rows.
    # Do not quietly print the original seller after a saved correction.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='purchase_seller_revisions'").fetchone():
        ids=sorted({r['document_id'] for r in saved})
        revisions=conn.execute('''SELECT s.*,a.document_id FROM purchase_seller_revisions s
            JOIN batch_bk_approvals a ON a.batch_id=s.batch_id
            WHERE s.revision=(SELECT MAX(t.revision) FROM purchase_seller_revisions t WHERE t.batch_id=s.batch_id)
            AND a.document_id IN (SELECT value FROM json_each(?))''',(json.dumps(ids),)).fetchall()
        def financial(items):
            sums=defaultdict(lambda:[Decimal(0),Decimal(0)])
            for r in items:
                key=(r['work_date'],_key(r['product_name']),_key(r['unit']))
                sums[key][0]+=Decimal(str(r['quantity']));sums[key][1]+=Decimal(str(r['amount']))
            return sums
        for revision in revisions:
            original=by_document[revision['document_id']]
            revised=[r for r in json.loads(revision['rows_json']) if start<=r['work_date']<=end]
            if financial(original)!=financial(revised):
                raise ValueError('Bảng kê đã có sửa người bán nhưng số lượng hoặc tiền không khớp bản đã lưu. Mở phần Cập nhật người bán / chọn hàng lập bảng kê để đối chiếu trước khi in.')
            # Apply by document only once; retain every other saved source row.
            by_document[revision['document_id']]=revised
    rows=sorted((row for group in by_document.values() for row in group),key=lambda r:r['work_date'])
    # The search month is not the date range of the selected printed purchases.
    kwargs=dict(template_path=ctx['MASTER_SOURCE'],date_from=min(r['work_date'] for r in rows),
                date_to=max(r['work_date'] for r in rows))
    if body.get('receipts'):
        rows=enrich_receipt_identity_rows(conn,rows)
        daily=defaultdict(Decimal);names={}
        for row in rows:
            key=(row['work_date'],row['cccd']);daily[key]+=Decimal(str(row['amount']));names[key]=row['seller']
        over=[(key,total) for key,total in daily.items() if total>RECEIPT_MAX_DAILY_AMOUNT]
        if over:
            detail='; '.join(f"{names[key]}, ngày {'/'.join(reversed(key[0].split('-')))}: {total:,.0f}đ" for key,total in over[:8])
            raise ReceiptExportError('Bảng kê tổng vẫn in được. Biên nhận cần đối chiếu vì tổng của cùng người bán trong ngày vượt 5.000.000đ: '+detail+
                (f'; còn {len(over)-8} trường hợp.' if len(over)>8 else '.')+
                ' Bấm Xem bảng kê tổng để in trước; kiểm tra chứng từ mua và người bán thực tế trước khi lập biên nhận. Không đổi ngày hoặc chia lại tiền để bỏ qua kiểm tra.',
                code='receipt_daily_limit_exceeded')
        book=build_purchase_documents_workbook(rows,**kwargs,
            buyer_name=ctx['setting_get'](conn,'purchase_receipt_buyer_name',''),
            buyer_title=ctx['setting_get'](conn,'purchase_receipt_buyer_title',''),
            company_name=ctx['setting_get'](conn,'company',''),company_address=ctx['setting_get'](conn,'company_address',''),
            location=ctx['setting_get'](conn,'purchase_receipt_location','Hải Phòng'))
    else:
        book=build_purchase_summary_workbook(rows,**kwargs)
    book._tdp_warnings=['In lại bảng kê đã ghi kho theo ngày mua đã lưu. Không nhập thêm kho. Thông tin định danh người bán lấy từ danh mục hiện tại; dùng bản sửa người bán đã lưu nếu có.']
    return book


def print_source_status(conn, body):
    """Describe provenance, never infer stock posting from order approval."""
    kind=body.get('kind')
    if kind=='saved-purchases':
        rows=saved_rows(conn,body.get('from'),body.get('to'),body.get('document_ids'))
        chosen=set(body.get('document_ids',[]))
        old=any(r['origin']=='order' and r['id'] in chosen for r in documents(conn,body.get('from'),body.get('to')))
        return dict(source='saved',title='Bảng đã ghi kho — in lại',
            message=('Có dữ liệu cũ đã ghi kho từ duyệt đơn; đây không phải xác nhận đã lập bảng bổ sung cho ngày này. ' if old else '')+'Đang in lại các dòng mua đã xác nhận nhập kho. Xem, tải và in không ghi thêm kho; không cần xác nhận nhập kho lần nữa.',
            from_date=min(r['document_date'] for r in rows),to_date=max(r['document_date'] for r in rows),items=[])
    if kind!='purchases':return None
    try:
        from .batch_bk_approval import linked_document
    except ImportError:
        from batch_bk_approval import linked_document
    items=[]
    for batch_id in sorted({int(s['batch_id']) for s in body['selections']}):
        batch=conn.execute('SELECT work_date FROM batches WHERE id=?',(batch_id,)).fetchone()
        doc=linked_document(conn,batch_id)
        posted=bool(doc and doc['status']=='posted')
        day=batch['work_date'];date_text='/'.join(reversed(day.split('-')))
        state='Đã có bảng kê liên kết ghi kho; mở Bảng đã ghi kho để in đúng dữ liệu đã lưu.' if posted else (
            'Bảng kê liên kết đã hoàn tác; bản xem này không xác nhận nhập kho.' if doc and doc['status']=='reversed' else
            'Chưa có bảng kê liên kết đã ghi kho. Không suy ra đã nhập kho từ trạng thái đơn đã duyệt.')
        items.append(dict(batch_id=batch_id,date=day,posted=posted,message=date_text+' · '+state))
    return dict(source='orders',title='Bản xem từ đơn hàng — không phải xác nhận nhập kho',
        message='Phần mềm dựng bảng kê và biên nhận từ dữ liệu đơn hàng. Có bản xem không có nghĩa đã mua hàng, đã trả tiền hoặc đã nhập kho. Xem, tải và in không làm hết hàng âm. Kiểm tra Bảng đã ghi kho trước; chỉ lập bổ sung khi xác định hàng thực mua chưa ghi kho.',
        from_date=min(i['date'] for i in items),to_date=max(i['date'] for i in items),items=items)
