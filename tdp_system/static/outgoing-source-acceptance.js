(function(){
  'use strict';
  window.TdpSourceAcceptance=async function(options){
    var esc=options.esc,report=null,busy=false,entered={actor:'',reason:''};
    var endpoint='/api/outgoing-invoices/source-scopes/'+options.invoiceId+'/acceptance';
    var d=document.createElement('dialog');d.className='purchase-selection-dialog';
    d.innerHTML='<header><h2>Giữ hóa đơn cho nhà thầu — chênh lệch riêng</h2><button class="btn btn-outline" data-act="close">Đóng</button></header><p role="status"></p><div data-body></div><footer><button class="btn btn-outline" data-act="load">Kiểm tra lại</button><button class="btn btn-primary" data-act="confirm" disabled>Xác nhận giữ hóa đơn</button><button class="btn btn-outline" data-act="revoke" hidden>Mở lại để đối chiếu</button></footer>';
    document.body.appendChild(d);d.showModal();
    function status(message){d.querySelector('[role=status]').textContent=message;}
    function remember(){['actor','reason'].forEach(function(n){var e=d.querySelector('[name='+n+']');if(e)entered[n]=e.value;});}
    function controls(){d.querySelectorAll('button,input').forEach(function(e){e.disabled=busy;});var accepted=report&&report.accepted;
      d.querySelector('[data-act=confirm]').hidden=!!accepted;
      d.querySelector('[data-act=confirm]').disabled=busy||!report||!report.can_confirm||!d.querySelector('[name=confirmed]:checked');
      d.querySelector('[data-act=revoke]').hidden=!accepted;
    }
    async function load(){
      remember();report=await options.api(endpoint);var a=report.accepted;
      var unmatched=a?a.unmatched:report.unmatched;
      var orders=a?a.orders:report.orders;
      d.querySelector('[data-body]').innerHTML=(a?'<p><strong>'+esc(a.message)+'</strong></p><p>'+esc(a.actor+' · '+a.created_at)+': '+esc(a.reason)+'</p>':'<p><strong>Hóa đơn '+esc(report.number)+' · '+esc(report.contractor)+' · '+Number(report.total_amount).toLocaleString('vi-VN')+' đ</strong></p>')+
        '<p>Giữ nguyên '+(a?a.allocated_order_rows:report.allocated_order_rows)+' dòng đơn hiện đã đối trừ. Phần chưa khớp được lưu riêng và không tự trừ vào đơn khác, kể cả khi tải thêm đơn hoặc đồng bộ lại.</p>'+
        '<p>Không đánh dấu toàn bộ kỳ đơn là đã xuất. Các đơn còn lại vẫn ở phần chưa xuất; hóa đơn đã ký, công nợ và lượng hàng đã ghi kho giữ nguyên.</p>'+
        '<details><summary>Xem các dòng đang được đối trừ · '+orders.length+' dòng</summary><p>Đây là phần đối trừ hiện có được giữ nguyên, không phải xác nhận mới rằng toàn bộ kỳ đơn đã xuất hết.</p><div class="selection-table"><table><thead><tr><th>Ngày đơn</th><th>Mã hàng</th><th>Lượng đang đối trừ</th></tr></thead><tbody>'+orders.map(function(r){return '<tr><td>'+esc(r.work_date)+'</td><td>'+esc(r.product_code)+'</td><td>'+Number(r.allocated_qty).toLocaleString('vi-VN',{maximumFractionDigits:8})+' '+esc(r.unit)+'</td></tr>';}).join('')+'</tbody></table></div></details>'+
        '<details open><summary>Phần chênh lệch giữ riêng · '+unmatched.length+' thông tin</summary><ul>'+unmatched.map(function(r){return '<li>'+esc(r.qty==null?r.message:r.product_code+' · '+Number(r.qty).toLocaleString('vi-VN',{maximumFractionDigits:8})+' '+r.unit)+'</li>';}).join('')+'</ul></details>'+
        '<label>Người xác nhận<input name="actor" maxlength="120" value="'+esc(entered.actor)+'"></label><label>Lý do xác nhận<input name="reason" maxlength="1500" value="'+esc(entered.reason)+'"></label>'+
        (a?'':'<label><input type="checkbox" name="confirmed"> Tôi xác nhận giữ hóa đơn cho '+esc(report.contractor)+' dù mặt hàng chưa khớp; giữ nguyên phần đối trừ hiện có, giữ riêng chênh lệch và không trừ thêm đơn chưa xác định.</label>');
      status(a?'Đã có xác nhận được lưu. Chỉ mở lại khi cần thay đổi cách đối chiếu.':'Kiểm tra phần chênh lệch rồi xác nhận. Chưa thay đổi dữ liệu.');
    }
    async function act(name){if(busy)return;if(name==='close'){d.close();return;}remember();busy=true;controls();var focus='';
      try{
        if(name==='load'){await load();}
        else{
          if(!entered.actor.trim()||!entered.reason.trim()){focus=!entered.actor.trim()?'actor':'reason';throw new Error(focus==='actor'?'Điền Người xác nhận.':'Điền Lý do xác nhận.');}
          if(name==='confirm'&&(!report||!report.can_confirm||!d.querySelector('[name=confirmed]:checked')))throw new Error('Tích xác nhận giữ hóa đơn trước khi lưu.');
          status(name==='confirm'?'Đang cập nhật và kiểm tra lại hóa đơn trước khi lưu…':'Đang mở lại xác nhận…');
          await options.api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:name,token:report.token,actor:entered.actor.trim(),reason:entered.reason.trim(),confirmed:name==='confirm'})});
          await load();if(options.onSaved)await options.onSaved();
          status(name==='confirm'?'Đã giữ hóa đơn cho nhà thầu; chênh lệch đã lưu riêng, không trừ thêm đơn.':'Đã mở lại để đối chiếu theo dữ liệu hiện tại.');
        }
      }catch(e){status(e.message);if(name==='confirm'&&!focus){report=null;focus='load';}}
      finally{busy=false;controls();if(focus){var el=d.querySelector(focus==='load'?'[data-act=load]':'[name='+focus+']');el.scrollIntoView({block:'center'});el.focus();}}
    }
    d.addEventListener('click',function(e){var b=e.target.closest('[data-act]');if(b)act(b.dataset.act);});
    d.addEventListener('change',controls);d.addEventListener('cancel',function(e){if(busy)e.preventDefault();});
    d.addEventListener('close',function(){d.remove();});await act('load');
  };
})();
