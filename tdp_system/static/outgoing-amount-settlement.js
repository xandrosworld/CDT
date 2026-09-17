(function () {
  'use strict';
  window.TdpAmountSettlement = async function (options) {
    var esc = options.esc, scope = options.scope, data = null, review = null, busy = false;
    var money = function (n) { return Number(n).toLocaleString('vi-VN', {maximumFractionDigits: 2}) + ' đ'; };
    var endpoint = '/api/outgoing-invoices/amount-settlement';
    var dialog = document.createElement('dialog'); dialog.className = 'purchase-selection-dialog';
    dialog.innerHTML = '<header><h2>Đối trừ hóa đơn đã ký theo tổng tiền</h2><button class="btn btn-outline" data-money="close">Đóng</button></header>' +
      '<p><strong>' + esc(scope.contractor) + ' · Ngày đơn ' + esc(scope.from) + ' → ' + esc(scope.to) + '</strong></p>' +
      '<p>Chọn các hóa đơn thực sự xuất cho kỳ đơn này, kể cả hóa đơn ký sau ngày đơn. Tổng so sánh gồm thuế, đến từng đồng. Khi xác nhận đủ tiền, kỳ đơn chuyển sang “Đã đối trừ theo tiền” và không được lập hóa đơn lần nữa; chi tiết mặt hàng vẫn được lưu để tra cứu.</p>' +
      '<p>Thao tác này không xác nhận khớp mặt hàng, không sửa doanh thu, công nợ hoặc lượng hàng đã ghi kho.</p>' +
      '<button class="btn btn-outline" data-money="sync">Cập nhật hóa đơn đã ký từ M-Invoice</button>' +
      '<p data-money-status role="status"></p><div data-money-history></div><div data-money-list></div><div data-money-review></div>' +
      '<footer><button class="btn btn-primary" data-money="preview">Kiểm tra tổng tiền đã chọn</button><button class="btn btn-primary" data-money="confirm" disabled>Xác nhận đã xuất đủ theo tiền</button></footer>';
    document.body.appendChild(dialog); dialog.showModal();
    var status = function (s, bad) { var e = dialog.querySelector('[data-money-status]'); e.textContent = s; e.classList.toggle('selection-error', !!bad); };
    function ids() { return Array.from(dialog.querySelectorAll('[name=invoice]:checked')).map(function (e) { return Number(e.value); }); }
    function invalidate() { review = null; dialog.querySelector('[data-money-review]').innerHTML = ''; dialog.querySelector('[data-money=confirm]').disabled = true; }
    function controls() {
      dialog.querySelectorAll('button,input').forEach(function (e) { e.disabled = busy; });
      var checked = dialog.querySelector('[name=confirmed]');
      dialog.querySelector('[data-money=confirm]').disabled = busy || !review || !review.can_confirm || !checked || !checked.checked;
    }
    async function load() {
      data = await options.api(endpoint + '?' + new URLSearchParams(scope)); invalidate();
      dialog.querySelector('[data-money-list]').innerHTML = '<h3>Doanh thu kỳ đơn, gồm thuế: ' + money(data.orders_total) + '</h3>' +
        '<p>Danh sách dưới đây gồm cả hóa đơn kỳ khác. Chỉ tích hóa đơn thuộc đúng kỳ đang đối trừ.</p>' + (data.unavailable_invoices||[]).map(function(r){return '<p class="selection-error">Chưa dùng được hóa đơn '+esc(r.number)+': '+esc(r.error)+'</p>';}).join('') + '<div class="selection-table"><table><thead><tr><th>Chọn</th><th>Hóa đơn</th><th>Ngày hóa đơn</th><th>Tiền trước thuế</th><th>Thuế</th><th>Tổng tiền</th></tr></thead><tbody>' +
        data.invoices.map(function (r) { return '<tr><td><input type="checkbox" name="invoice" value="' + r.id + '" aria-label="Chọn hóa đơn ' + esc(r.invoice_number) + '"></td><td>' + esc(r.invoice_series + ' / ' + r.invoice_number) + '</td><td>' + esc(r.invoice_date) + '</td><td>' + money(r.subtotal) + '</td><td>' + money(r.tax_amount) + '</td><td>' + money(r.total_amount) + '</td></tr>'; }).join('') + '</tbody></table></div>';
      dialog.querySelector('[data-money-history]').innerHTML = data.history.map(function (r) { return '<details><summary><strong>' + (r.needs_review ? 'Cần đối chiếu lại' : 'Đã đối trừ theo tiền') + ' #' + r.id + '</strong> · ' + esc(r.date_from + ' → ' + r.date_to) + ' · ' + money(r.amount) + '</summary><p>' + esc(r.invoices.map(function (i) { return i.invoice_series + '/' + i.invoice_number; }).join(', ')) + '</p><p>' + esc(r.actor + ': ' + r.reason) + '</p><label>Người mở lại<input name="revoke_actor_' + r.id + '" maxlength="120"></label><label>Lý do mở lại<input name="revoke_reason_' + r.id + '" maxlength="1000"></label><button class="btn btn-outline" data-money="revoke" data-id="' + r.id + '">Mở lại để đối chiếu</button></details>'; }).join('');
    }
    async function action(name, id) {
      if (busy) return;
      if (name === 'close') { dialog.close(); return; }
      busy = true; controls(); status('Đang kiểm tra…');
      try {
        if (name === 'load' || name === 'sync') {
          if (name === 'sync') await options.api('/api/outgoing-invoices/sync-issued', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(scope)});
          await load(); status('Chọn hóa đơn đã ký thuộc kỳ đơn rồi kiểm tra tổng tiền.');
        } else if (name === 'preview') {
          invalidate();
          review = await options.api(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.assign({},scope,{action:'preview',invoice_ids:ids()}))});
          dialog.querySelector('[data-money-review]').innerHTML = '<h3>Doanh thu: ' + money(review.orders_total) + ' − Đã ký: ' + money(review.signed_total) + ' = Còn thiếu: ' + money(review.remaining) + '</h3>' +
            '<p>Thuế trên đơn: ' + money(review.orders_tax) + ' · Thuế trên hóa đơn: ' + money(review.signed_tax) + '</p>' +
            (review.orders_tax !== review.signed_tax ? '<p class="selection-error">Tiền thuế đang khác nhau. Đối trừ tổng tiền không xác nhận thuế hoặc mặt hàng đã khớp; cần kiểm tra riêng phần chênh lệch này.</p>' : '') +
            review.conflicts.map(function (s) { return '<p class="selection-error">' + esc(s) + '</p>'; }).join('') +
            (review.can_confirm ? '<label>Người đối chiếu<input name="actor" maxlength="120"></label><label>Lý do / ghi chú<input name="reason" maxlength="1000" value="Đã đối chiếu hóa đơn đã ký đủ tổng tiền cho kỳ đơn này"></label><label><span><input type="checkbox" name="confirmed"> Tôi xác nhận các hóa đơn đã chọn thuộc kỳ đơn này và đã xuất đủ tổng tiền, dù chi tiết hàng có thể khác.</span></label>' : '<p class="selection-error">Chưa thể xác nhận. Cần khớp đúng tổng tiền và xử lý các thông tin đối chiếu bên trên.</p>');
          status('Đã kiểm tra tổng tiền. Chưa thay đổi phần chưa xuất.');
        } else if (name === 'confirm') {
          if (!review || !review.can_confirm || !dialog.querySelector('[name=confirmed]').checked) throw new Error('Kiểm tra và xác nhận trước.');
          var actor = dialog.querySelector('[name=actor]').value.trim(), reason = dialog.querySelector('[name=reason]').value.trim();
          if (!actor || !reason) throw new Error('Điền người đối chiếu và lý do.');
          status('Đang kiểm tra lại M-Invoice trước khi xác nhận. Không gửi hoặc ký thêm hóa đơn.');
          await options.api(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.assign({},scope,{action:'confirm',invoice_ids:ids(),token:review.token,actor:actor,reason:reason,confirmed:true}))});
          await load(); status('Đã chuyển kỳ đơn sang Đã đối trừ theo tiền. Doanh thu, công nợ và hàng đã ghi kho giữ nguyên.');
          if(options.onSaved)await options.onSaved();
        } else if (name === 'revoke') {
          await options.api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'revoke',id:Number(id),actor:dialog.querySelector('[name=revoke_actor_'+id+']').value,reason:dialog.querySelector('[name=revoke_reason_'+id+']').value})});
          await load(); status('Đã mở lại. Hệ thống đối chiếu theo hóa đơn hiện tại; lịch sử xác nhận vẫn được giữ.');
          if(options.onSaved)await options.onSaved();
        }
      } catch(error) { status(error.message,true); if(name==='confirm')invalidate(); }
      finally { busy=false;controls(); }
    }
    dialog.addEventListener('change',function(e){if(e.target.name==='invoice')invalidate();controls();});
    dialog.addEventListener('click',function(e){var b=e.target.closest('[data-money]');if(b)action(b.dataset.money,b.dataset.id);});
    dialog.addEventListener('cancel',function(e){if(busy)e.preventDefault();});
    dialog.addEventListener('close',function(){dialog.remove();});
    await action('load');
  };
})();
