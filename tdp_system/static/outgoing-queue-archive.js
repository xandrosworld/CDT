(function(){
 'use strict';
 window.TdpQueueArchive=async function(o){
  var d=document.createElement('dialog'),report=null,busy=false,endpoint='/api/outgoing-invoices/queue-archive';
  d.className='purchase-selection-dialog';
  d.innerHTML='<header><h2>Bỏ phần cũ khỏi chờ xuất và bảng tải</h2><button data-close class="btn btn-outline">Đóng</button></header><p><strong>'+o.esc((o.scope.contractor||'Tất cả nhà thầu đã tích')+' · '+o.scope.from+' → '+o.scope.to)+'</strong></p><p>Bỏ phần chưa xuất trong phạm vi trên, gồm cả hàng đang chờ và hàng đã chuyển sang Chưa xuất. Phần này sẽ không lặp lại trong bảng chờ, lựa chọn lập hóa đơn và file tải. Có thể khôi phục khi cần.</p><p>Giữ nguyên đơn gốc, công nợ, kho và hóa đơn đã ký. Đây không phải xác nhận đã xuất hóa đơn. Dòng mới vẫn hiện; dòng cũ đổi lượng đơn hoặc giá sẽ hiện lại để kiểm tra.</p><div data-report></div><p role="status" data-status></p><label style="display:flex;align-items:center;gap:10px"><input type="checkbox" style="width:auto;margin:0" data-confirm> Tôi xác nhận bỏ phần chưa xuất trong phạm vi trên.</label><footer><button class="btn btn-outline" data-preview>Xem lại</button><button class="btn btn-primary" data-hide disabled>Bỏ phần cũ</button></footer><div data-history></div>';
  document.body.appendChild(d);d.showModal();
  function controls(){d.querySelectorAll('button,input').forEach(function(e){e.disabled=busy;});d.querySelector('[data-hide]').disabled=busy||!report||!report.rows||!d.querySelector('[data-confirm]').checked;}
  async function request(action,id){return o.api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({},o.scope,{action:action,id:id,token:report&&report.token,confirmed:action==='restore'||d.querySelector('[data-confirm]').checked}))});}
  async function run(action,id){
   if(busy)return;busy=true;controls();
   try{
    var r=await request(action,id);
    if(action!=='preview'){
     d.querySelector('[data-status]').textContent=action==='hide'?'Đã bỏ phần cũ khỏi chờ xuất và bảng tải. Đơn gốc, công nợ, kho và hóa đơn đã ký giữ nguyên.'+((r.remote_drafts||[]).length?' Bản đã gửi M-Invoice vẫn được giữ để đối soát; thao tác này không xóa bản trên M-Invoice.':''):'Đã khôi phục. Chỉ phần thực tế còn chưa xuất trở lại; kiểm tra và chuẩn bị bản nháp mới khi cần.';
     r=await request('preview');
     if(o.onSaved)await o.onSaved();
    }
    report=r;d.querySelector('[data-confirm]').checked=false;
    d.querySelector('[data-report]').innerHTML='<h3>'+r.rows+' dòng chưa xuất trong phạm vi đã chọn</h3>'+r.summary.map(function(s){return '<p>'+o.esc(s.contractor)+' · '+s.rows+' dòng · '+Number(s.amount).toLocaleString('vi-VN')+' đ trước thuế</p>';}).join('')+((r.remote_drafts||[]).length?'<p><strong>Có '+r.remote_drafts.length+' bản đã gửi hoặc đang đối soát M-Invoice.</strong> Bỏ phần cũ không xóa các bản này trên M-Invoice và không tự gửi lại. Bản nháp chưa gửi sẽ được bỏ giữ hàng.</p>':'<p>Bản nháp chưa gửi liên quan sẽ được bỏ giữ hàng; khi khôi phục, hệ thống tính lại theo phần chưa xuất thực tế.</p>');
    d.querySelector('[data-history]').innerHTML='<h3>Các lần đã bỏ — có thể khôi phục</h3>'+r.history.map(function(h){return '<p>'+o.esc((h.contractor||'Tất cả nhà thầu đã tích')+' · '+h.date_from+' → '+h.date_to+' · '+h.created_at)+' <button class="btn btn-outline" data-restore="'+h.id+'">Khôi phục lần này</button></p>';}).join('');
   }catch(e){report=null;d.querySelector('[data-status]').textContent=e.message;d.querySelector('[data-preview]').focus();}finally{busy=false;controls();}
  }
  d.addEventListener('change',controls);
  d.addEventListener('click',function(e){if(e.target.closest('[data-close]'))d.close();if(e.target.closest('[data-preview]'))run('preview');if(e.target.closest('[data-hide]'))run('hide');var r=e.target.closest('[data-restore]');if(r&&window.confirm('Khôi phục phần chưa xuất của lần này vào bảng chờ và bảng tải?'))run('restore',Number(r.dataset.restore));});
  d.addEventListener('cancel',function(e){if(busy)e.preventDefault();});d.addEventListener('close',function(){d.remove();});await run('preview');
 };
})();
