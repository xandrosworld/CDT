(function () {
  'use strict';
  window.TdpPurchaseDocumentSupplements = function (options) {
    var esc = options.esc, data = null, busy = false, requestId = null, focusTarget = null;
    var dialog = document.createElement('dialog'); dialog.className = 'purchase-selection-dialog purchase-supplement-dialog';
    var today = options.to || new Date().toLocaleDateString('en-CA');
    var start = (options.from || today).slice(0, 7) + '-01';
    function money(value) { return Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits: 2}) + ' đ'; }
    function dateText(value) { return value.split('-').reverse().join('/'); }
    dialog.innerHTML = '<header><div><h2>Chờ lập bảng kê bổ sung</h2><p>Phần chưa chọn sau khi Lưu lựa chọn tự hiện tại đây, theo ngày mua và người bán. Cuối tháng chọn nhiều ngày để lập một lượt.</p></div><button class="btn btn-outline" data-supplement="close">Đóng</button></header>' +
      '<p>Giữ nguyên ngày mua, tiền mua, công nợ và kho. Bảng kê bổ sung này ghi lại phần chờ; không tạo thêm giao dịch mua hoặc biên nhận thanh toán.</p>' +
      '<div class="selection-controls"><label>Từ ngày<input name="from" type="date" value="'+esc(start)+'"></label><label>Đến ngày<input name="to" type="date" value="'+esc(today)+'"></label><button class="btn btn-outline" data-supplement="load">Xem phần chờ</button></div>' +
      '<p class="supplement-message" role="status"></p><div class="supplement-days"></div>' +
      '<div class="selection-controls"><button class="btn btn-outline" data-supplement="all">Chọn tất cả ngày còn chờ</button><button class="btn btn-outline" data-supplement="none">Bỏ chọn</button></div><p class="supplement-total"></p>' +
      '<div class="selection-controls"><label>Số bảng kê bổ sung<input name="reference" maxlength="100"></label><label>Người lập<input name="actor" maxlength="120"></label></div>' +
      '<label><input name="confirmed" type="checkbox"> Tôi đã kiểm tra các ngày và phần chờ được chọn để lập bảng kê bổ sung.</label>' +
      '<div class="selection-controls"><button class="btn btn-primary" data-supplement="create">Lập bảng kê bổ sung</button></div>' +
      '<h3>Đã lập</h3><p>Tải hoặc in lại từ đây không tạo thêm bảng kê. Nếu cần sửa, hủy bản đã lập trước; bản hủy vẫn lưu trong lịch sử.</p><div class="supplement-history"></div>';
    document.body.appendChild(dialog); dialog.showModal();
    function field(name) { return dialog.querySelector('[name="'+name+'"]'); }
    function message(text, error) { var el=dialog.querySelector('.supplement-message'); el.textContent=text; el.classList.toggle('selection-error', !!error); }
    function focus(el) { if (busy) { focusTarget=el; return; } if (el) { el.scrollIntoView({block:'center'}); el.focus(); } }
    function dates() { return Array.from(dialog.querySelectorAll('[data-supplement-date]:checked')).map(function(el){return el.dataset.supplementDate;}); }
    function totals() {
      var chosen=dates(), entries=data ? data.entries : [];
      dialog.querySelector('.supplement-total').textContent=chosen.length+' ngày đã chọn · '+money(entries.reduce(function(total,day){return total+(chosen.indexOf(day.date)>=0 ? day.pending : 0);},0));
      dialog.querySelector('[data-supplement="create"]').disabled=busy || !chosen.length;
    }
    function render() {
      dialog.querySelector('.supplement-days').innerHTML=data.entries.map(function(day){
        return '<section><h3>'+(day.status==='saved' ? '<input type="checkbox" data-supplement-date="'+esc(day.date)+'" aria-label="Chọn ngày '+esc(dateText(day.date))+'"> ' : '')+'Ngày mua '+esc(dateText(day.date))+' · '+(day.status==='needs_review' ? 'Cần đối chiếu' : money(day.pending))+'</h3>'+
          (day.error ? '<p class="selection-error">'+esc(day.error)+'</p>' : '')+
          (day.status==='needs_selection' ? '<p>Lưu lựa chọn của ngày này trước để xác định phần chuyển sang bảng kê bổ sung.</p>' : '')+
          (day.groups || []).map(function(group){return '<details open><summary><strong>'+esc(group.seller)+'</strong> · '+money(group.pending)+'</summary><div class="selection-table"><table><thead><tr><th>Hàng / dòng nguồn</th><th>Bếp</th><th>ĐVT</th><th>Lượng còn chờ</th><th>Giá mua BK</th><th>Thành tiền</th></tr></thead><tbody>'+group.rows.map(function(row){return '<tr><td>'+esc(row.product_name)+'<small>Dòng '+esc(row.source_ref)+'</small></td><td>'+esc(row.kitchen)+'</td><td>'+esc(row.unit)+'</td><td>'+esc(row.quantity)+'</td><td>'+money(row.buy_price)+'</td><td>'+money(row.amount)+'</td></tr>';}).join('')+'</tbody></table></div></details>';}).join('')+
          '<button class="btn btn-outline" data-supplement="selection" data-day="'+esc(day.date)+'">Mở lựa chọn ngày '+esc(dateText(day.date))+'</button></section>';
      }).join('') || '<p>Không còn phần chờ trong khoảng ngày này. Xem các bảng kê đã lập bên dưới.</p>';
      dialog.querySelector('.supplement-history').innerHTML=data.history.map(function(record){
        var base='/api/purchase-document-supplements/'+record.id;
        return '<section data-record="'+record.id+'"><h4>'+esc(record.reference)+' · '+money(record.amount)+' · '+(record.status==='active'?'Đã lập':'Đã hủy')+'</h4><p>Ngày mua: '+record.dates.map(dateText).map(esc).join(', ')+' · Người lập: '+esc(record.actor)+'</p><div class="selection-controls"><a class="btn btn-primary" href="'+base+'/excel">Tải Excel</a><a class="btn btn-outline" href="'+base+'/print" target="_blank" rel="noopener">Xem / In bảng kê</a></div>'+
          (record.status==='active' ? '<details><summary>Hủy bảng kê này để sửa</summary><label>Lý do hủy<input name="cancel_reason_'+record.id+'" maxlength="500"></label><label><input name="cancel_confirmed_'+record.id+'" type="checkbox"> Tôi xác nhận hủy bảng kê này và đưa phần hàng về chờ.</label><button class="btn btn-outline" data-supplement="cancel" data-id="'+record.id+'">Hủy bảng kê bổ sung</button></details>' : '<p>Lý do hủy: '+esc(record.cancel_reason)+'</p>')+'</section>';
      }).join('') || '<p>Chưa có bảng kê bổ sung đã lập trong khoảng ngày này.</p>';
      totals();
    }
    async function load() {
      var selected=dates();
      data=await options.api('/api/purchase-document-supplements?from='+encodeURIComponent(field('from').value)+'&to='+encodeURIComponent(field('to').value));
      render();
      dialog.querySelectorAll('[data-supplement-date]').forEach(function(el){el.checked=selected.indexOf(el.dataset.supplementDate)>=0;});
      field('confirmed').checked=false; totals();
    }
    async function act(action, button) {
      if(busy)return;
      if(action==='close'){dialog.close();return;}
      if(action==='all'||action==='none'){dialog.querySelectorAll('[data-supplement-date]').forEach(function(el){el.checked=action==='all';});field('confirmed').checked=false;totals();return;}
      if(action==='selection'){
        await window.TdpPurchaseDocumentSelection({api:options.api,esc:esc,from:button.dataset.day,to:button.dataset.day,onClosed:function(){act('load');}});return;
      }
      busy=true;dialog.querySelectorAll('button').forEach(function(el){el.disabled=true;});
      try {
        if(action==='load'){await load();message('Phần chờ đã cập nhật. Chọn các ngày cần lập bảng kê bổ sung.');}
        if(action==='create'){
          if(!data || data.from!==field('from').value || data.to!==field('to').value){focus(dialog.querySelector('[data-supplement="load"]'));throw new Error('Khoảng ngày đã đổi. Bấm Xem phần chờ trước khi lập.');}
          if(!field('reference').value.trim()){focus(field('reference'));throw new Error('Điền Số bảng kê bổ sung.');}
          if(!field('actor').value.trim()){focus(field('actor'));throw new Error('Điền Người lập.');}
          if(!field('confirmed').checked){focus(field('confirmed'));throw new Error('Tích xác nhận đã kiểm tra các ngày và phần chờ được chọn.');}
          requestId=requestId || crypto.randomUUID();
          var result=await options.api('/api/purchase-document-supplements',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({from:data.from,to:data.to,state_hash:data.state_hash,dates:dates(),actor:field('actor').value,reference:field('reference').value,confirmed:true,request_id:requestId})});
          requestId=null;if(options.onSaved)options.onSaved();await load();message('Đã lập bảng kê bổ sung. Bấm Tải Excel hoặc Xem / In bảng kê ở bản vừa lập bên dưới.');
          focus(dialog.querySelector('[data-record="'+result.id+'"] a'));
        }
        if(action==='cancel'){
          var id=button.dataset.id;
          if(!field('actor').value.trim()){focus(field('actor'));throw new Error('Điền Người lập để ghi nhận người hủy.');}
          if(!field('cancel_reason_'+id).value.trim()){focus(field('cancel_reason_'+id));throw new Error('Điền Lý do hủy.');}
          if(!field('cancel_confirmed_'+id).checked){focus(field('cancel_confirmed_'+id));throw new Error('Tích xác nhận hủy bảng kê này và đưa phần hàng về chờ.');}
          await options.api('/api/purchase-document-supplements/'+id+'/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor:field('actor').value,reason:field('cancel_reason_'+id).value,confirmed:true})});
          if(options.onSaved)options.onSaved();await load();message('Đã hủy bảng kê. Phần hàng trở lại chờ; bản hủy vẫn lưu để đối chiếu.');
        }
      }catch(error){message(error.message,true);}
      finally{busy=false;dialog.querySelectorAll('button').forEach(function(el){el.disabled=false;});totals();if(focusTarget){focus(focusTarget);focusTarget=null;}}
    }
    dialog.addEventListener('click',function(event){var button=event.target.closest('[data-supplement]');if(button)act(button.dataset.supplement,button);});
    dialog.addEventListener('input',function(event){requestId=null;if(event.target.name!=='confirmed')field('confirmed').checked=false;totals();});
    dialog.addEventListener('cancel',function(event){if(busy)event.preventDefault();});
    dialog.addEventListener('close',function(){dialog.remove();if(options.onClosed)options.onClosed();});
    act('load');
  };
})();
