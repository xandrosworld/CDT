window.TdpInputConversionRepair = async function({invoice,api,esc,onSaved}) {
  const lines=invoice.items.filter(r=>r.inventory_eligible&&r.stock_qty>0);
  const dialog=document.createElement('dialog');dialog.className='inventory-totals-dialog input-conversion-repair-dialog';
  dialog.style.width='min(1100px,96vw)';dialog.style.maxWidth='96vw';dialog.style.padding='20px';
  const money=v=>Number(v||0).toLocaleString('vi-VN',{maximumFractionDigits:2});
  const qty=v=>Number(v||0).toLocaleString('vi-VN',{maximumFractionDigits:6});
  dialog.innerHTML='<div class="inventory-totals-heading"><h3>Sửa quy đổi đã nhập kho</h3><button data-close class="icon-button" aria-label="Đóng">×</button></div>'+
    '<p>Hóa đơn <strong>'+esc(invoice.invoice_series+' / '+invoice.invoice_number)+'</strong> · '+esc(invoice.invoice_date)+'</p>'+
    '<p>Sửa lượng nhập và giá nhập theo quy cách thực tế. Tiền hàng, thuế và nội dung hóa đơn gốc giữ nguyên. Báo cáo tồn và giá vốn được tính lại từ lượng đã sửa.</p>'+
    '<label>Chọn dòng cần sửa <select data-line>'+lines.map(r=>'<option value="'+r.id+'">Dòng '+r.line_index+' · '+esc(r.source_item_name)+' · '+qty(r.qty)+' '+esc(r.source_unit)+'</option>').join('')+'</select></label>'+
    '<p data-rule></p><div data-status role="status">Đang kiểm tra…</div><div data-preview></div>'+
    '<form data-form><p><label>Người xác nhận <input name="actor" required maxlength="100"></label></p><p><label>Lý do sửa <input name="reason" required maxlength="500" style="width:80%"></label></p>'+
    '<p><label><input type="checkbox" name="remember" checked> Nhớ quy đổi cho dòng mới cùng tên hàng, đơn vị và nhà cung cấp. Không sửa các hóa đơn cũ khác.</label></p>'+
    '<button class="btn btn-primary" data-confirm disabled>Xác nhận sửa lượng và giá nhập</button></form><div data-history></div>';
  document.body.appendChild(dialog);dialog.showModal();let busy=false,model=null;
  const find=s=>dialog.querySelector(s),status=find('[data-status]'),selection=find('[data-line]');
  function close(){if(!busy)dialog.close();}
  find('[data-close]').onclick=close;dialog.onclose=()=>dialog.remove();dialog.oncancel=e=>{if(busy)e.preventDefault();};
  function lock(v){busy=v;dialog.querySelectorAll('input,button,select').forEach(e=>e.disabled=v);find('[data-confirm]').disabled=v||!model?.changed;}
  function render(p){
    model=p;find('[data-rule]').innerHTML='1 '+esc(p.source_unit)+' = <input data-factor type="number" min="0.000001" step="any" value="'+p.factor+'" style="width:120px"> '+esc(p.unit)+' <button class="btn btn-outline" data-check>Kiểm tra thay đổi</button>';
    find('[data-factor]').oninput=()=>{model=null;find('[data-confirm]').disabled=true;status.textContent='Bấm Kiểm tra thay đổi để xem lượng và giá mới trước khi xác nhận.';};
    find('[data-check]').onclick=()=>load(find('[data-factor]').value);
    find('[data-preview]').innerHTML='<h4>'+esc(p.name)+'</h4><table style="width:100%"><thead><tr><th>Nội dung</th><th>Trước khi sửa</th><th>Sau khi sửa</th></tr></thead><tbody>'+
      '<tr><td>Lượng nhập</td><td>'+qty(p.old_qty)+' '+esc(p.unit)+'</td><td><strong>'+qty(p.qty)+' '+esc(p.unit)+'</strong></td></tr>'+
      '<tr><td>Đơn giá nhập</td><td>'+money(p.old_unit_cost)+' đ/'+esc(p.unit)+'</td><td>'+money(p.unit_cost)+' đ/'+esc(p.unit)+'</td></tr>'+
      '<tr><td>Tiền nhập giữ nguyên</td><td>'+money(p.amount)+' đ</td><td>'+money(p.amount)+' đ</td></tr>'+
      '<tr><td>Tồn cuối tháng '+esc(p.date.slice(0,7))+'</td><td>'+qty(p.before.closing_qty)+' '+esc(p.unit)+'</td><td>'+qty(p.after.closing_qty)+' '+esc(p.unit)+'</td></tr>'+
      '<tr><td>Giá vốn xuất trong tháng</td><td>'+money(p.before.output_value)+' đ</td><td>'+money(p.after.output_value)+' đ</td></tr></tbody></table>'+
      (p.after.closing_qty<0?'<p class="warning-summary">Sau khi sửa, mã này còn tồn âm '+qty(p.after.closing_qty)+' '+esc(p.unit)+'. Cần đối chiếu nhập/xuất thực tế.</p>':'');
    find('[data-history]').innerHTML=(p.history||[]).length?'<h4>Lịch sử sửa quy đổi</h4>'+p.history.map(h=>'<p>'+esc(h.created_at)+' · '+esc(h.actor)+' · '+qty(h.before)+' → '+qty(h.after)+' '+esc(p.unit)+' · '+esc(h.reason)+'</p>').join(''):'';
    status.textContent=p.changed?'Kiểm tra lượng và giá mới, nhập lý do rồi xác nhận. Chưa ghi thay đổi.':'Nhập hệ số đúng rồi bấm Kiểm tra thay đổi.';
  }
  async function load(factor){
    if(busy)return;lock(true);model=null;
    try{render(await api('/api/invoice-workbench/input-conversion-repair/'+selection.value,factor==null?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({factor})}));}
    catch(e){status.textContent=e.message;find('[data-preview]').innerHTML='';}finally{lock(false);}
  }
  selection.onchange=()=>load();
  find('[data-form]').onsubmit=async e=>{
    e.preventDefault();if(busy||!model?.changed)return;
    const form=find('[data-form]'),payload={confirmed:true,token:model.token,factor:model.factor,actor:form.elements.actor.value,reason:form.elements.reason.value,remember:form.elements.remember.checked};
    lock(true);
    try{
      const result=await api('/api/invoice-workbench/input-conversion-repair/'+selection.value,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      render({...result,changed:false});status.textContent='Đã sửa thành công: '+qty(result.old_qty)+' → '+qty(result.qty)+' '+result.unit+'. Tiền nhập giữ nguyên '+money(result.amount)+' đ. Không cần nhập kho lại.';
      await onSaved();
    }catch(error){status.textContent=error.message;}finally{lock(false);}
  };
  await load();
};

