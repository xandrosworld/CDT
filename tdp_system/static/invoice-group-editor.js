(function () {
  'use strict';
  window.TdpInvoiceGroupEditor = async function (ids, context) {
    const {api, esc, quantity, money, saved} = context;
    const post = (path, body) => api('/api/invoice-workbench/input-groups/' + path, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
    });
    const initial = await post('selection-preview', {item_ids:ids});
    const dialog = document.createElement('dialog');
    dialog.className = 'inventory-totals-dialog invoice-group-dialog';
    dialog.innerHTML = '<h3>Gộp ' + ids.length + ' dòng thành 1 dòng</h3><p>' + esc(initial.invoice_number) + '</p>' +
      '<label for="group-product-search">Mã hàng chung sau khi gộp</label>' +
      '<input id="group-product-search" class="input-date" autocomplete="off" placeholder="Tìm tên hoặc mã hàng">' +
      '<div class="group-product-results" aria-live="polite"></div><p class="group-product-selected"></p>' +
      '<div class="group-lines table-wrap"></div><div class="group-result" aria-live="polite">Chọn mã hàng để xem lượng và giá vốn sau gộp.</div>' +
      '<p class="code-note">Chỉ lưu mã và quy đổi cho các dòng đã chọn. Tổng tiền giữ nguyên, gồm cả hàng 0đ. Sau gộp hiện một dòng; có thể Tách lại. Chưa nhập kho.</p>' +
      '<p class="group-error" role="alert"></p><div class="compact-controls"><button type="button" class="btn btn-outline group-cancel">Hủy</button>' +
      '<button type="button" class="btn btn-primary group-confirm" disabled>Lưu và gộp</button></div>';
    const find = selector => dialog.querySelector(selector);
    let product=null, preview=null, busy=false, revision=0, searchRevision=0, timer;
    const confirm=find('.group-confirm'), search=find('#group-product-search');
    const fail=message=>{find('.group-error').textContent=message;};
    function factors() {
      return Object.fromEntries(Array.from(dialog.querySelectorAll('.group-factor')).map(e=>[e.dataset.id,e.value.trim().replace(',','.')]));
    }
    async function recalculate() {
      const version=++revision;
      preview=null;confirm.disabled=true;fail('');
      dialog.querySelectorAll('[data-converted]').forEach(e=>e.textContent='');
      if(!product)return;
      find('.group-result').textContent='Đang kiểm tra lượng và giá vốn…';
      try {
        const result=await post('selection-preview',{item_ids:ids,product_code:product.code,factors:factors()});
        if(version!==revision||!dialog.isConnected)return;
        if(result.source_token!==initial.source_token)throw Error('Dòng nguồn đã thay đổi. Đóng hộp và mở lại để kiểm tra dữ liệu mới.');
        preview=result;
        result.rows.forEach(r=>{const output=find('[data-converted="'+r.id+'"]');if(output)output.textContent=quantity(r.qty)+' '+r.source_unit+' → '+quantity(r.stock_qty)+' '+r.product_unit;});
        find('.group-result').innerHTML='<strong>Tổng lượng: '+quantity(result.qty)+' '+esc(result.unit)+'</strong><br>Tổng tiền chưa thuế: <strong>'+money(result.amount)+'</strong><br>Giá vốn sau gộp: <strong>'+money(result.unit_cost)+' / '+esc(result.unit)+'</strong>';
        confirm.disabled=false;
      } catch(e) {
        if(version!==revision||!dialog.isConnected)return;
        find('.group-result').textContent='Nhập đủ hệ số quy đổi để xem kết quả.';fail(e.message);
      }
    }
    function choose(p) {
      searchRevision++;product=p;search.value=p.code;
      find('.group-product-results').innerHTML='';
      find('.group-product-selected').textContent=p.code+' · '+p.name+' · Đơn vị kho: '+p.unit;
      find('.group-lines').innerHTML='<table><thead><tr><th>Dòng / Tên hàng nguồn</th><th>Lượng nguồn</th><th>Quy đổi sang '+esc(p.unit)+'</th><th>Tiền chưa thuế</th></tr></thead><tbody>'+initial.rows.map(r=>{
        const same=String(r.source_unit||'').trim().toLowerCase()===String(p.unit||'').trim().toLowerCase();
        const factor=r.product_code===p.code&&r.mapping_status==='mapped'&&r.conversion_factor>0?r.conversion_factor:same?1:'';
        return '<tr><td>'+esc(r.line_index)+' · '+esc(r.source_item_name)+'</td><td>'+quantity(r.qty)+' '+esc(r.source_unit)+'</td><td><label>1 '+esc(r.source_unit)+' = <input class="input-date group-factor" inputmode="decimal" data-id="'+r.id+'" value="'+esc(factor)+'" aria-label="Hệ số quy đổi dòng '+r.line_index+'"> '+esc(p.unit)+'</label><small data-converted="'+r.id+'"></small></td><td>'+money(r.amount)+'</td></tr>';
      }).join('')+'</tbody></table>';
      recalculate();
    }
    search.oninput=()=>{
      const version=++searchRevision;
      ++revision;preview=null;product=null;confirm.disabled=true;
      find('.group-product-selected').textContent='';find('.group-lines').innerHTML='';
      find('.group-result').textContent='Chọn mã hàng từ kết quả tìm kiếm.';
      clearTimeout(timer);
      const term=search.value.trim();
      find('.group-product-results').textContent=term.length<2?'Nhập ít nhất 2 ký tự.':'Đang tìm mã hàng…';
      if(term.length<2)return;
      timer=setTimeout(async()=>{
        try {
          const result=await api('/api/products/search?q='+encodeURIComponent(term));
          if(version!==searchRevision||!dialog.isConnected)return;
          const products=result.items||[];
          find('.group-product-results').innerHTML=products.length?products.map((p,i)=>'<button type="button" class="btn btn-outline" data-result="'+i+'">'+esc(p.code+' · '+p.name+' · '+p.unit)+'</button>').join(''):'Không tìm thấy mã. Hãy thử tên hoặc mã khác.';
          find('.group-product-results').querySelectorAll('button').forEach(b=>b.onclick=()=>choose(products[Number(b.dataset.result)]));
        } catch(e) {if(version===searchRevision&&dialog.isConnected)fail(e.message);}
      },180);
    };
    search.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();const options=Array.from(find('.group-product-results').querySelectorAll('button'));const exact=options.find(b=>b.textContent.startsWith(search.value.trim()+' · '));if(exact)exact.click();else if(options[0])options[0].focus();}};
    dialog.addEventListener('input',e=>{if(e.target.matches('.group-factor'))recalculate();});
    find('.group-cancel').onclick=()=>{if(!busy)dialog.close();};
    dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
    dialog.addEventListener('close',()=>{revision++;searchRevision++;clearTimeout(timer);dialog.remove();});
    confirm.onclick=async()=>{
      if(busy||!preview||!product)return;
      busy=true;const chosen=preview;
      dialog.querySelectorAll('input,button').forEach(e=>e.disabled=true);
      try {
        const result=await post('save-selection',{item_ids:ids,product_code:product.code,factors:factors(),token:chosen.token});
        dialog.close();await saved(result,chosen);
      } catch(e) {fail(e.message);}
      finally {busy=false;dialog.querySelectorAll('input,button').forEach(e=>e.disabled=false);confirm.disabled=!preview;}
    };
    document.body.appendChild(dialog);dialog.showModal();
    const codes=new Set(initial.rows.map(r=>r.product_code||''));
    if(codes.size===1&&!codes.has('')) {
      const row=initial.rows[0];choose({code:row.product_code,name:row.product_name,unit:row.product_unit});
    }
    search.focus();
  };
}());
