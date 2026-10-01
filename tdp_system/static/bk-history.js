(function(root){
  'use strict';
  root.TdpBkHistory=async function(options){
    var host=document.getElementById(options.hostId),esc=options.esc;
    if(!host)return;
    host.classList.add('bk-history-container');
    var serial=String(Date.now())+Math.random();host.dataset.historySerial=serial;
    var current=function(){return host.isConnected&&host.dataset.historySerial===serial;};
    host.innerHTML='<p role="status">Đang tìm bảng kê đã lưu theo ngày mua…</p>';
    try{
      var data=await options.api('/api/bk-import/history?from='+encodeURIComponent(options.from)+'&to='+encodeURIComponent(options.to));
      if(!current())return;
      var items=data.items||[],previewId=options.hostId+'-preview';
      items.sort(function(a,b){return (a.origin==='order'?0:1)-(b.origin==='order'?0:1)||a.date_from.localeCompare(b.date_from)||a.id-b.id;});
      host.innerHTML='<section class="card bk-saved-history"><div class="card-head"><div><h3>Bảng kê đã lưu · '+esc(options.from.split('-').reverse().join('/'))+' – '+esc(options.to.split('-').reverse().join('/'))+'</h3><p>1. Chọn bảng kê → 2. Xem bảng kê tổng → 3. In phiếu đã chọn hoặc Tải PDF đã chọn.</p></div></div><div class="card-body">'+
        '<p>Chỉ lấy các dòng mua đã ghi kho trong kỳ này. In lại không nhập thêm kho; không cần tìm hoặc nạp lại file Excel cũ.</p>'+
        (items.length?'<p><strong>'+items.length+' bảng kê đã lưu</strong>. Đã tích sẵn tất cả; bỏ tích bảng không cần in.</p><div class="table-wrap"><table><thead><tr><th>Chọn</th><th>Bảng kê đã lưu</th><th>Ngày mua</th><th>Dòng trong kỳ</th><th>Thành tiền trong kỳ</th></tr></thead><tbody>'+items.map(function(r){return '<tr><td><input type="checkbox" data-history-id="'+r.id+'" aria-label="Chọn bảng kê '+r.id+'" checked></td><td>#'+r.id+' · '+esc(r.filename)+'</td><td>'+esc(r.date_from.split('-').reverse().join('/'))+' – '+esc(r.date_to.split('-').reverse().join('/'))+'</td><td>'+r.row_count+'</td><td>'+Number(r.amount_total).toLocaleString('vi-VN')+' đ</td></tr>';}).join('')+'</tbody></table></div><div class="bk-history-actions"><button class="btn btn-primary" data-history="summary">Xem bảng kê tổng</button><button class="btn btn-outline" data-history="receipts">Xem biên nhận</button><span class="bk-history-count" role="status"></span></div>':'<p role="status">Kỳ này chưa có bảng kê đã ghi kho. Kiểm tra lại tháng cần in; nếu chưa lập bảng kê, dùng Lập bảng kê bổ sung từ tồn âm và kiểm tra thông tin mua thực tế.</p>')+
        '<div class="bk-history-error" role="alert" hidden></div></div></section><div id="'+previewId+'"></div>';
      if(items.length){
        var tbody=host.querySelector('tbody'),previousOrigin=null;
        items.forEach(function(item,index){
          var row=host.querySelector('[data-history-id="'+item.id+'"]').closest('tr');
          if(item.origin!==previousOrigin){
            var group=document.createElement('tr'),cell=document.createElement('th');cell.colSpan=5;
            cell.style.color='#173c4a';cell.style.backgroundColor='#dcefeb';cell.style.textAlign='left';
            cell.textContent=item.origin_label+' · '+items.filter(function(r){return r.origin===item.origin;}).length+' bảng';
            group.appendChild(cell);tbody.insertBefore(group,row);previousOrigin=item.origin;
          }
          var note=document.createElement('div');note.className='muted';note.textContent='Đã xác nhận ghi kho: '+item.confirmed_at;
          row.children[1].appendChild(note);
        });
        var actions=host.querySelector('.bk-history-actions');
        actions.querySelector('[data-history=receipts]').textContent='Xem bảng kê và biên nhận';
        var selection=document.createElement('div');selection.className='bk-history-actions';
        selection.innerHTML='<button class="btn btn-outline" data-history="all">Chọn tất cả bảng kê</button><button class="btn btn-outline" data-history="none">Bỏ chọn tất cả</button><span>Có thể chọn nhiều ngày để in cùng một lần. Ngày trên bản in theo các dòng mua đã chọn.</span>';
        host.querySelector('.table-wrap').before(selection);
      }
      var explanation=document.createElement('div');explanation.className='document-note tag-warn';
      explanation.innerHTML='<strong>Đây là lịch sử để in lại, không phải danh sách hàng còn âm.</strong><p>Bảng cũ từ duyệt đơn đã được lưu theo quy trình trước đây. Bảng bổ sung / nhập Excel là các bảng đã xác nhận ghi kho riêng. Có các bảng này không có nghĩa đã đủ hàng mua hoặc đã hết tồn âm. Không lập lại các dòng đã ghi kho.</p>';
      if(options.onSupplement){
        var supplement=document.createElement('button');supplement.className='btn btn-primary';supplement.dataset.historySupplement='';
        supplement.textContent='Lập bảng kê bổ sung từ tồn âm';supplement.onclick=options.onSupplement;explanation.appendChild(supplement);
      }
      host.querySelector('.card-body').prepend(explanation);
      function selected(){return Array.from(host.querySelectorAll('[data-history-id]:checked')).map(function(el){return Number(el.dataset.historyId);});}
      document.getElementById(previewId).classList.add('bk-history-preview');
      function counts(){var ids=selected(),count=host.querySelector('.bk-history-count');if(count)count.textContent='Đã chọn '+ids.length+'/'+items.length+' bảng kê · '+items.filter(function(r){return ids.includes(r.id);}).reduce(function(t,r){return t+Number(r.amount_total);},0).toLocaleString('vi-VN')+' đ';}
      host.onchange=function(e){if(e.target.matches('[data-history-id]'))counts();};counts();
      host.onclick=async function(e){
        var button=e.target.closest('[data-history]');if(!button)return;
        if(['all','none'].includes(button.dataset.history)){
          host.querySelectorAll('[data-history-id]').forEach(function(el){el.checked=button.dataset.history==='all';});counts();return;
        }
        var ids=selected(),error=host.querySelector('.bk-history-error');
        if(!ids.length){error.hidden=false;error.textContent='Chọn ít nhất một bảng kê trong danh sách phía trên.';var input=host.querySelector('[data-history-id]');input.scrollIntoView({block:'center'});input.focus();return;}
        error.hidden=true;
        host.querySelectorAll('[data-history]').forEach(function(b){b.disabled=true;});
        try{
          await root.TDPDocuments.open({kind:'saved-purchases',from:options.from,to:options.to,document_ids:ids,receipts:button.dataset.history==='receipts'},previewId);
          if(current()){var preview=document.getElementById(previewId);preview.scrollIntoView({block:'start'});}
        }finally{if(current())host.querySelectorAll('[data-history]').forEach(function(b){b.disabled=false;});}
      };
      host.scrollIntoView({block:'start'});
    }catch(error){
      if(!current())return;
      host.innerHTML='<p role="alert">'+esc(error.message)+'</p><button class="btn btn-outline" data-history-retry>Thử lại danh sách bảng kê</button>';
      host.querySelector('[data-history-retry]').onclick=function(){root.TdpBkHistory(options);};
    }
  };
}(window));
