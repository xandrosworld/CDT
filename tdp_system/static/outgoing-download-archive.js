(function(){
 'use strict';
 window.TdpDownloadArchive=async function(o){
  var d=document.createElement('dialog'),report=null,busy=false;
  d.className='purchase-selection-dialog';
  d.innerHTML='<header><h2>Ẩn phần cũ khỏi bảng tải</h2><button data-close class="btn btn-outline">Đóng</button></header><p>'+o.esc((o.scope.contractor||'Tất cả nhà thầu đã tích')+' · '+o.scope.from+' → '+o.scope.to)+'</p><p>Chỉ ẩn khỏi file “Tải toàn bộ chưa ký”. Không đánh dấu đã xuất, không đổi đơn gốc, công nợ, tồn kho hoặc phần chờ xuất. Dòng mới vẫn được tải; dòng cũ thay đổi lượng đơn hoặc giá sẽ hiện lại để kiểm tra.</p><div data-report></div><p role="status" data-status></p><label><input type="checkbox" data-confirm> Tôi xác nhận ẩn các dòng trong phạm vi trên khỏi bảng tải lần sau.</label><footer><button class="btn btn-outline" data-preview>Xem lại</button><button class="btn btn-primary" data-hide disabled>Ẩn phần cũ khỏi bảng tải</button></footer><div data-history></div>';
  document.body.appendChild(d);d.showModal();
  function controls(){d.querySelectorAll('button,input').forEach(function(e){e.disabled=busy;});d.querySelector('[data-hide]').disabled=busy||!report||!report.rows||!d.querySelector('[data-confirm]').checked;}
  async function run(action,id){
   if(busy)return;busy=true;controls();
   try{
    var r=await o.api('/api/outgoing-invoices/download-archive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({},o.scope,{action:action,id:id,token:report&&report.token,confirmed:action==='restore'||d.querySelector('[data-confirm]').checked}))});
    if(action!=='preview'){
     d.querySelector('[data-status]').textContent=action==='hide'?'Đã ẩn phần cũ khỏi bảng tải. Đơn gốc, công nợ, tồn kho và trạng thái hóa đơn giữ nguyên.':'Đã khôi phục phần đã ẩn vào bảng tải.';
     r=await o.api('/api/outgoing-invoices/download-archive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({},o.scope,{action:'preview'}))});
    }
    report=r;d.querySelector('[data-confirm]').checked=false;
    d.querySelector('[data-report]').innerHTML='<h3>'+r.rows+' dòng đang có trong bảng tải</h3>'+r.summary.map(function(s){return '<p>'+o.esc(s.contractor)+' · '+s.rows+' dòng · '+Number(s.amount).toLocaleString('vi-VN')+' đ trước thuế</p>';}).join('');
    d.querySelector('[data-history]').innerHTML='<h3>Các lần đã ẩn — có thể khôi phục</h3>'+r.history.map(function(h){return '<p>'+o.esc((h.contractor||'Tất cả nhà thầu đã tích')+' · '+h.date_from+' → '+h.date_to+' · '+h.created_at)+' <button class="btn btn-outline" data-restore="'+h.id+'">Khôi phục lần ẩn này</button></p>';}).join('');
   }catch(e){report=null;d.querySelector('[data-status]').textContent=e.message;}finally{busy=false;controls();}
  }
  d.addEventListener('change',controls);
  d.addEventListener('click',function(e){if(e.target.closest('[data-close]'))d.close();if(e.target.closest('[data-preview]'))run('preview');if(e.target.closest('[data-hide]'))run('hide');var r=e.target.closest('[data-restore]');if(r&&window.confirm('Khôi phục các dòng của lần ẩn này vào bảng tải?'))run('restore',Number(r.dataset.restore));});
  d.addEventListener('cancel',function(e){if(busy)e.preventDefault();});d.addEventListener('close',function(){d.remove();});await run('preview');
 };
})();
