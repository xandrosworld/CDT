window.TdpInputDiscount = async function({id,api,esc,onSaved}) {
  const dialog=document.createElement('dialog');dialog.className='inventory-totals-dialog input-discount-dialog';
  dialog.style.width='min(1280px,96vw)';dialog.style.maxWidth='96vw';dialog.style.padding='20px';
  dialog.innerHTML='<div class="inventory-totals-heading"><h3>Phân bổ chiết khấu vào giá nhập</h3><button class="icon-button" data-close aria-label="Đóng">×</button></div><div data-status role="status">Đang kiểm tra…</div><div data-body></div>';
  document.body.appendChild(dialog);dialog.showModal();
  let busy=false,model=null;
  const status=dialog.querySelector('[data-status]'),body=dialog.querySelector('[data-body]');
  const money=v=>Number(v||0).toLocaleString('vi-VN',{maximumFractionDigits:2});
  const endpoint='/api/invoice-workbench/input-discount/'+id;
  dialog.querySelector('[data-close]').onclick=()=>{if(!busy)dialog.close();};
  dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});dialog.addEventListener('close',()=>dialog.remove());
  function setBusy(value){busy=value;dialog.querySelectorAll('button,input').forEach(e=>e.disabled=value||e.hasAttribute('data-unavailable'));}
  function amounts(){return Array.from(body.querySelectorAll('[data-amount]')).map(e=>({item_id:Number(e.dataset.amount),discount:e.value}));}
  function recalc(){
    let total=0;
    for(const input of body.querySelectorAll('[data-amount]')){
      const row=model.lines.find(r=>r.item_id===Number(input.dataset.amount)),value=Number(input.value);
      total+=value;const net=row.amount-value;
      body.querySelector('[data-net="'+row.item_id+'"]').textContent=money(net);
      body.querySelector('[data-cost="'+row.item_id+'"]').textContent=row.stock_qty>0?money(net/row.stock_qty):'Chưa quy đổi';
    }
    body.querySelector('[data-total]').textContent='Đã phân bổ: '+money(total)+' đ · Còn lại: '+money(model.discount-total)+' đ';
  }
  function render(data){
    model=data;
    status.textContent=data.error|| (data.stale?'Nguồn hoặc mã/quy đổi đã đổi. Kiểm tra và lưu lại phân bổ.':data.saved?'Đã lưu phân bổ. Hóa đơn gốc giữ nguyên.':data.discount>0?'Chọn hàng được hưởng chiết khấu và kiểm tra số tiền trước khi lưu.':'Tiền dòng hàng đã khớp tổng chưa thuế; không trừ thêm chiết khấu.');
    body.innerHTML='<p>Hóa đơn <strong>'+esc(data.invoice_series+' / '+data.invoice_number)+'</strong></p><p>Tiền hàng trước chiết khấu: <strong>'+money(data.gross)+' đ</strong> · Cần phân bổ: <strong>'+money(data.discount)+' đ</strong> · Tổng chưa thuế sau chiết khấu: <strong>'+money(data.net)+' đ</strong></p>'+
      '<p>Chọn các mặt hàng được hưởng rồi bấm chia theo tiền hàng, hoặc nhập số tiền chiết khấu từng dòng. Hàng khuyến mại 0đ không nhận chiết khấu. Tổng phải khớp trước khi lưu. Chỉ thay đổi giá nhập kho; số lượng và hóa đơn gốc giữ nguyên.</p>'+
      (data.editable&&data.discount>0?'<button class="btn btn-outline" data-auto>Chia theo tiền hàng đã chọn</button>':'')+
      '<div class="table-wrap"><table><thead><tr><th>Hưởng CK</th><th>Dòng / Hàng hóa</th><th>Lượng hóa đơn</th><th>Tiền trước CK</th><th>Chiết khấu (đ)</th><th>Tiền nhập sau CK</th><th>Đơn giá kho sau CK</th></tr></thead><tbody>'+
      data.lines.map(r=>'<tr><td><input type="checkbox" data-selected="'+r.item_id+'" '+(r.amount>0?(r.discount>0?'checked':''):'disabled data-unavailable')+'></td><td>'+r.line_index+' · '+esc(r.product_code||'Chưa ghép mã')+'<br>'+esc(r.name)+'</td><td>'+money(r.source_qty)+' '+esc(r.source_unit)+'</td><td>'+money(r.amount)+'</td><td><input type="number" min="0" max="'+r.amount+'" step="0.01" style="width:130px" data-amount="'+r.item_id+'" value="'+r.discount+'" '+(!data.editable||r.amount===0?'readonly':'')+'></td><td data-net="'+r.item_id+'">'+money(r.net_amount)+'</td><td data-cost="'+r.item_id+'">'+(r.net_unit_cost==null?'Chưa quy đổi':money(r.net_unit_cost))+'</td></tr>').join('')+'</tbody></table></div><p data-total></p>'+
      (data.editable&&data.discount>0?'<form data-save><label>Người xác nhận <input name="actor" required maxlength="100"></label><button class="btn btn-primary">Lưu phân bổ chiết khấu</button></form>':'<p>Hóa đơn đã ghi kho hoặc không còn chiết khấu cần phân bổ.</p>');
    body.querySelectorAll('[data-amount]').forEach(e=>e.oninput=recalc);recalc();
    const auto=body.querySelector('[data-auto]');
    if(auto)auto.onclick=async()=>{
      const selected=Array.from(body.querySelectorAll('[data-selected]:checked')).map(e=>Number(e.dataset.selected));
      setBusy(true);
      try{render(await api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selected})}));}
      catch(e){status.textContent=e.message;}finally{setBusy(false);}
    };
    const form=body.querySelector('[data-save]');
    if(form)form.onsubmit=async e=>{
      e.preventDefault();if(busy)return;
      const payload={expected_token:model.token,actor:form.elements.actor.value,amounts:amounts()};setBusy(true);
      try{
        const saved=await api(endpoint,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        render(saved);status.textContent='Đã lưu phân bổ chiết khấu. Chưa ghi kho. Đóng bảng này, kiểm tra mã/quy đổi rồi bấm Nhập kho.';
        await onSaved();
      }catch(error){status.textContent=error.message;}finally{setBusy(false);}
    };
  }
  try{render(await api(endpoint));}catch(error){status.textContent=error.message;}
};
