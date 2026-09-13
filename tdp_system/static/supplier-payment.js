(function(root) {
  'use strict';
  var current=null, pendingKey='tdp.pendingSupplierPayment';
  function dateVN(value){return String(value||'').split('-').reverse().join('/');}
  function stored() { try { return JSON.parse(sessionStorage.getItem(pendingKey)||'null'); } catch(_) { return null; } }
  function mount(host, options) {
    if(!host)return;
    var scope={supplier:options.supplier,from:options.dateFrom,to:options.dateTo};
    var key=JSON.stringify(scope), recovery=stored();
    if(current && (current.key===key || current.saving || current.uncertain)) {
      var reload=current.key===key && options.dataVersion!==current.options.dataVersion && !current.loading && !current.saving && !current.uncertain;
      current.options=options;host.appendChild(current.element);if(reload)current.reload?.();return;
    }
    if(recovery){scope=recovery.scope;key=JSON.stringify(scope);}
    var esc=options.esc, money=options.money;
    var box=document.createElement('div');box.className='card supplier-payment-card';
    var job={key:key,scope:scope,element:box,options:options,snapshot:null,plan:recovery?.plan||null,
      saving:false,uncertain:!!recovery,loading:false,serial:0};current=job;
    host.appendChild(box);
    if(!scope.supplier){box.innerHTML='<div class="card-head"><div><h3>Ghi nhận trả tiền NCC</h3><p>Chọn một nhà cung cấp ở bộ lọc phía trên để xem số còn nợ và nhập tiền trả lần này.</p></div></div>';return;}
    box.innerHTML='<div class="card-head"><div><h3>Ghi nhận trả tiền NCC · '+esc(scope.supplier)+'</h3><p>Các dòng còn nợ từ '+esc(dateVN(scope.from))+' đến '+esc(dateVN(scope.to))+'. Trừ nợ từ ngày cũ đến mới.</p></div></div><div class="card-body">'+
      '<form id="supplierPaymentForm"><fieldset><div class="supplier-payment-amounts">'+
      '<div><label for="supplierPaymentDue">Còn phải trả trong kỳ</label><strong id="supplierPaymentDue">Đang tải…</strong><small data-quick-count></small></div>'+
      '<div><label for="supplierPaymentAmount">Số tiền trả lần này (đ)</label><input id="supplierPaymentAmount" name="amount" type="number" min="1" step="1" required placeholder="Nhập số tiền đã trả"><button type="button" class="btn btn-small btn-outline" data-quick-all>Trả hết số còn nợ</button></div>'+
      '<div><label>Sau lần trả này còn</label><strong id="supplierPaymentRemaining">—</strong></div></div><div class="payment-grid">'+
      '<div class="form-field"><label>Người ghi nhận<input name="actor" maxlength="120" required></label></div>'+
      '<div class="form-field"><label>Ngày thanh toán<input name="payment_date" type="date" value="'+esc(scope.to)+'" required></label></div>'+
      '<div class="form-field"><label>Phương thức<select name="method"><option>Chuyển khoản</option><option>Tiền mặt</option><option>Bù trừ</option><option>Khác</option></select></label></div>'+
      '<div class="form-field"><label>Mã tham chiếu<input name="reference_code" maxlength="200" placeholder="UNC / mã ngân hàng"></label></div>'+
      '<div class="form-field span-2"><label>Nội dung<input name="note" maxlength="1000" placeholder="Nội dung thanh toán"></label></div></div>'+
      '<p data-quick-date-hint hidden>Ngày thanh toán ngoài kỳ đang xem. Khoản trả xuất hiện ở bảng tổng trong kỳ có ngày thanh toán này.</p><div class="compact-controls"><button class="btn btn-primary" type="submit">Ghi nhận thanh toán NCC</button><button type="button" class="btn btn-outline" data-quick-refresh>Cập nhật số còn nợ</button></div></fieldset></form>'+
      '<p class="supplier-payment-status" role="status"></p><button type="button" class="btn btn-outline" data-quick-retry hidden>Kiểm tra / gửi lại khoản vừa ghi nhận</button></div>';
    var form=box.querySelector('form'), fields=form.querySelector('fieldset'), amount=form.elements.amount;
    var status=box.querySelector('[role=status]'), retry=box.querySelector('[data-quick-retry]');
    function say(message,error){status.textContent=message;status.classList.toggle('danger-text',!!error);}
    function refreshAmounts(){
      var available=job.snapshot?.remaining_amount, value=Number(amount.value);
      box.querySelector('#supplierPaymentDue').textContent=available==null?'—':money(available);
      box.querySelector('[data-quick-count]').textContent=job.snapshot?job.snapshot.line_count+' dòng còn nợ':'';
      box.querySelector('#supplierPaymentRemaining').textContent=available==null?'—':
        !amount.value?money(available):Number.isInteger(value)&&value>0&&value<=available?money(available-value):'Số tiền chưa hợp lệ';
      amount.max=available==null?'':String(available);
      box.querySelector('[data-quick-all]').disabled=!available;
      form.querySelector('[type=submit]').disabled=!available || job.loading || job.uncertain;
    }
    async function load(){
      if(job.saving||job.uncertain)return;
      var serial=++job.serial;job.loading=true;fields.disabled=true;say('Đang cập nhật số còn nợ…');
      try{
        var data=await job.options.api('/api/debts/payables/settlement?'+new URLSearchParams(scope));
        if(serial!==job.serial)return;job.snapshot=data;refreshAmounts();say(data.line_count?'Chỉ ghi nhận khi NCC đã được thanh toán.':'Không còn dòng nợ cần trả trong kỳ này.');
      }catch(error){job.snapshot=null;refreshAmounts();say(error.message,true);}
      finally{job.loading=false;fields.disabled=job.uncertain;refreshAmounts();}
    }
    job.reload=load;
    function remember(plan){sessionStorage.setItem(pendingKey,JSON.stringify({scope:scope,plan:plan}));}
    function forget(){var pending=stored();if(pending?.plan?.payment.request_id===job.plan?.payment.request_id)sessionStorage.removeItem(pendingKey);}
    function review(plan){
      var dialog=document.createElement('dialog');dialog.className='supplier-payment-confirm';
      dialog.setAttribute('aria-label','Xác nhận khoản trả NCC');
      dialog.innerHTML='<h2>Xác nhận trả tiền · '+esc(plan.payment.party_code)+'</h2><p>Ngày thanh toán: '+esc(dateVN(plan.payment.payment_date))+'</p>'+
        '<dl><div><dt>Còn phải trả trước lần này</dt><dd>'+money(plan.before_amount)+'</dd></div><div><dt>Ghi nhận đã trả</dt><dd>'+money(plan.amount)+'</dd></div><div><dt>Sau lần trả này còn</dt><dd>'+money(plan.after_amount)+'</dd></div></dl>'+
        '<p>Trừ vào '+plan.line_count+' dòng còn nợ trong kỳ đã chọn, từ ngày cũ đến mới.</p><p role="status"></p><div class="compact-controls"><button type="button" class="btn btn-outline" data-cancel>Quay lại</button><button type="button" class="btn btn-primary" data-confirm>Xác nhận ghi nhận</button></div>';
      var message=dialog.querySelector('[role=status]'), confirm=dialog.querySelector('[data-confirm]');
      function close(){if(job.saving)return;dialog.close();dialog.remove();}
      dialog.querySelector('[data-cancel]').onclick=close;dialog.addEventListener('cancel',function(e){e.preventDefault();close();});
      confirm.onclick=async function(){
        if(job.saving)return;
        // Persist the exact request before the first write; retries/reloads reuse it.
        try{remember(plan);}catch(error){message.textContent='Chưa lưu được mã chống gửi trùng trên trình duyệt. Không gửi thanh toán; kiểm tra bộ nhớ trình duyệt rồi thử lại.';return;}
        job.plan=plan;job.saving=true;fields.disabled=true;confirm.disabled=true;message.textContent='Đang ghi nhận…';
        var result;
        try{
          result=await job.options.api('/api/debts/payables/payments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(plan.payment)});
        }catch(error){
          job.saving=false;confirm.disabled=false;
          job.uncertain=!error.status||error.status>=500;
          if(job.uncertain){
            message.textContent='Chưa xác định được kết quả. Bấm xác nhận lại để kiểm tra/gửi lại cùng khoản, hệ thống không ghi trùng.';
            say(message.textContent,true);retry.hidden=false;
          }else{
            forget();job.plan=null;close();await load();say(error.message,true);
          }
          return;
        }
        forget();job.saving=false;job.uncertain=false;retry.hidden=true;job.plan=null;amount.value='';close();
        say('Đã ghi nhận '+money(result.amount)+' cho '+result.supplier.code+'.');
        await load();
        // A refresh failure must never turn a successful payment into an uncertain write.
        try{await job.options.onSaved('Đã ghi nhận '+money(result.amount)+' cho '+result.supplier.code+'; đã cập nhật công nợ.');}
        catch(error){say('Khoản trả đã lưu. Tải lại công nợ để xem số mới.',true);}
      };
      document.body.appendChild(dialog);dialog.showModal();
    }
    form.addEventListener('submit',async function(event){
      event.preventDefault();event.stopPropagation();if(job.loading||job.saving||job.uncertain||!job.snapshot)return;
      job.loading=true;fields.disabled=true;
      try{
        var values={};Array.from(form.elements).forEach(function(el){if(el.name)values[el.name]=el.value;});
        var plan=await job.options.api('/api/debts/payables/payments/preview',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify(Object.assign(values,scope,{amount:Number(amount.value),snapshot_hash:job.snapshot.snapshot_hash,request_id:'PAY-NCC-'+crypto.randomUUID()}))});
        if(current!==job || !box.isConnected)return;
        review(plan);
      }catch(error){say(error.message,true);}
      finally{job.loading=false;fields.disabled=false;refreshAmounts();}
    });
    amount.addEventListener('input',refreshAmounts);
    form.elements.payment_date.addEventListener('change',function(){box.querySelector('[data-quick-date-hint]').hidden=this.value>=scope.from&&this.value<=scope.to;});
    box.querySelector('[data-quick-all]').onclick=function(){if(job.snapshot){amount.value=job.snapshot.remaining_amount;refreshAmounts();}};
    box.querySelector('[data-quick-refresh]').onclick=load;
    retry.onclick=function(){if(job.plan)review(job.plan);};
    if(recovery){
      Object.entries(recovery.plan.payment).forEach(function(entry){if(form.elements[entry[0]])form.elements[entry[0]].value=entry[1];});
      job.snapshot={remaining_amount:recovery.plan.before_amount,line_count:recovery.plan.line_count};fields.disabled=true;
      refreshAmounts();retry.hidden=false;say('Khoản trả trước chưa xác định được kết quả. Bấm Kiểm tra / gửi lại để đối chiếu cùng khoản, không ghi trùng.',true);
    }else load();
  }
  root.TdpSupplierPayment={mount:mount};
})(window);
