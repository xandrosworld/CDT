(function () {
  'use strict';
  window.TdpReceiptReview = async function (opts) {
    if (document.querySelector('.receipt-review-dialog[open]')) return;
    const e = opts.esc, money = opts.money, qty = opts.qty;
    const output = opts.direction === 'output', verb = output ? 'xuất' : 'nhập';
    const endpoint = '/api/invoice-workbench/' + (output ? 'output-postings' : 'input-receipts');
    const dialog = document.createElement('dialog');
    dialog.className = 'inventory-totals-dialog receipt-review-dialog';
    dialog.setAttribute('aria-label', 'Kiểm tra trước khi ' + verb + ' kho');
    dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Kiểm tra trước khi ' + verb + ' kho</h3><button type="button" class="icon-button receipt-close" aria-label="Đóng">×</button></div><div class="receipt-review-body" aria-live="polite">Đang kiểm tra hóa đơn…</div>';
    let busy = false;
    const close = () => { if (!busy) { dialog.close(); dialog.remove(); } };
    dialog.querySelector('.receipt-close').onclick = close;
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', () => dialog.remove());
    document.body.appendChild(dialog); dialog.showModal();
    const body = dialog.querySelector('.receipt-review-body');
    try {
      const result = await opts.api(endpoint + opts.query);
      if (!dialog.open) return;
      const items = result.items || [];
      body.innerHTML = '<p>' + (output ? 'Ghi xuất kho trên web theo hóa đơn đã phát hành. Kiểm tra đủ tồn theo ngày cho cả nhóm; hóa đơn chưa đủ điều kiện giữ lại trong Còn chưa xuất. Thao tác này không gửi hoặc phát hành hóa đơn trên M-Invoice.' : 'Nhập một lần các hóa đơn đủ điều kiện đã chọn bên dưới. Hóa đơn còn dòng lỗi được giữ lại cả hóa đơn trong Còn chưa nhập để xử lý tiếp.') + '</p>' +
        '<p class="receipt-selection-total" role="status"></p>' +
        '<details class="receipt-selection-details"' + (items.length === 1 ? ' open' : '') + '><summary>Xem chi tiết / Bỏ chọn hóa đơn</summary>' +
        '<label class="receipt-select-all"><input type="checkbox" checked> Chọn tất cả</label><div class="table-wrap"><table><thead><tr><th>Chọn</th><th>Hóa đơn / Ngày / ' + (output ? 'Khách hàng' : 'NCC') + '</th><th>Dòng ' + verb + '</th><th>Tiền hàng (chưa thuế)</th></tr></thead><tbody>' +
        items.map((r,i) => '<tr><td><input class="receipt-choice" type="checkbox" checked value="'+i+'" aria-label="Chọn hóa đơn '+e(r.number)+'"></td><td><strong>'+e(r.number)+'</strong><div>'+e(opts.date(r.date))+'</div>'+e(r.seller)+'</td><td>'+r.line_count+'</td><td class="num-cell">'+money(r.amount)+'</td></tr>').join('') +
        '</tbody></table></div></details><details class="receipt-quantity-details"'+(items.length === 1 ? ' open' : '')+'><summary>Xem tổng lượng theo đơn vị</summary><p class="receipt-quantity-total"></p></details>' +
        ((result.blocked || []).length ? '<details open><summary>'+result.blocked.length+' hóa đơn chưa thể '+verb+'</summary><ul>'+result.blocked.map(r=>'<li>'+e(r.number)+': '+e(r.reason)+'</li>').join('')+'</ul></details>' : '') +
        '<p class="receipt-review-error" role="alert"></p><div class="receipt-review-footer"><button type="button" class="btn btn-outline receipt-cancel">Quay lại</button><button type="button" class="btn btn-primary receipt-confirm">Xác nhận '+verb+' kho</button></div>';
      const confirm = body.querySelector('.receipt-confirm');
      const choices = [...body.querySelectorAll('.receipt-choice')];
      const all = body.querySelector('.receipt-select-all input');
      const selected = () => choices.filter(c=>c.checked).map(c=>items[Number(c.value)]);
      function update() {
        const rows = selected(), units = {};
        rows.forEach(r=>Object.entries(r.qty_by_unit).forEach(([u,q])=>units[u]=(units[u]||0)+q));
        body.querySelector('.receipt-selection-total').textContent = rows.length+' hóa đơn · '+rows.reduce((n,r)=>n+r.line_count,0)+' dòng '+verb+' · Tiền hàng (chưa thuế): '+money(rows.reduce((n,r)=>n+r.amount,0));
        body.querySelector('.receipt-quantity-total').textContent = Object.entries(units).map(([u,q])=>qty(q)+' '+u).join(' · ') || 'Chưa chọn hóa đơn.';
        confirm.disabled = !rows.length;
        all.checked = !!rows.length && rows.length === items.length;
        all.indeterminate = !!rows.length && rows.length !== items.length;
      }
      choices.forEach(c=>c.onchange=update);
      all.onchange=()=>{choices.forEach(c=>c.checked=all.checked);update();};
      body.querySelector('.receipt-cancel').onclick=close;
      confirm.onclick=async()=>{
        if (busy || !selected().length) return;
        const rows = selected(); busy=true;
        dialog.querySelectorAll('button,input').forEach(c=>c.disabled=true);
        confirm.textContent='Đang '+verb+' kho…';
        try {
          const posted=await opts.api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true,items:rows.map(r=>({id:r.id,token:r.token}))})});
          busy=false; close();
          await opts.onPosted(posted, rows);
        } catch(error) {
          busy=false;
          dialog.querySelectorAll('button,input').forEach(c=>c.disabled=false);
          confirm.textContent='Thử xác nhận lại';
          body.querySelector('.receipt-review-error').textContent=error.message+' Nếu mất kết nối, có thể thử lại cùng lựa chọn; hệ thống không ghi trùng.';
          update();
        }
      };
      update();
      body.querySelector('.receipt-cancel').focus();
    } catch(error) {
      body.textContent=error.message;
    }
  };
}());
