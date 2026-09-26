(function () {
  'use strict';
  window.TdpAmountSettlement = async function (options) {
    var esc = options.esc, scope = options.scope, data = null, review = null, busy = false, focusAfter = '', entered = {};
    var money = function (n) { return Number(n).toLocaleString('vi-VN', {maximumFractionDigits: 2}) + ' đ'; };
    var endpoint = '/api/outgoing-invoices/amount-settlement';
    var dialog = document.createElement('dialog'); dialog.className = 'purchase-selection-dialog';
    dialog.innerHTML = '<header><h2>Đối chiếu hóa đơn đã ký theo tổng tiền</h2><button class="btn btn-outline" data-money="close">Đóng</button></header>' +
      '<p><strong>' + esc(scope.contractor) + ' · Ngày đơn ' + esc(scope.from) + ' → ' + esc(scope.to) + '</strong></p>' +
      '<p>Chọn các hóa đơn thực sự xuất cho khoảng ngày đơn này, kể cả hóa đơn ký sau ngày đơn. Tổng so sánh gồm thuế. Nếu mới xuất một phần, bấm “Lưu tiến độ — còn chưa xuất”; phần còn lại tiếp tục theo dõi theo khoảng ngày, không bắt buộc xuất bù cho hết doanh thu.</p>' +
      '<p>Lưu tiến độ chỉ nhớ các hóa đơn đang đối chiếu và số tiền còn lại, chưa trừ thêm số lượng mặt hàng. Chỉ dùng “Xác nhận đã xuất đủ theo tiền” khi đã khớp đủ tiền và muốn khép toàn bộ kỳ đơn.</p>' +
      '<p>Thao tác này không xác nhận khớp mặt hàng, không sửa doanh thu, công nợ hoặc lượng hàng đã ghi kho.</p>' +
      '<button class="btn btn-outline" data-money="sync">Cập nhật hóa đơn đã ký từ M-Invoice</button>' +
      '<p data-money-status role="status"></p><div data-money-unsigned></div><div data-money-progress></div><div data-money-history></div><div data-money-list></div><div data-money-review></div>' +
      '<footer><button class="btn btn-primary" data-money="preview">Kiểm tra tổng tiền đã chọn</button><button class="btn btn-primary" data-money="save_progress" hidden disabled>Lưu tiến độ — còn chưa xuất</button><button class="btn btn-primary" data-money="confirm" disabled>Xác nhận đã xuất đủ theo tiền</button></footer>';
    document.body.appendChild(dialog); dialog.showModal();
    var status = function (s, bad) { var e = dialog.querySelector('[data-money-status]'); e.textContent = s; e.classList.toggle('selection-error', !!bad); };
    function ids() { return Array.from(dialog.querySelectorAll('[name=invoice]:checked')).map(function (e) { return Number(e.value); }); }
    function remember() {
      ['actor','reason'].forEach(function(name){var e=dialog.querySelector('[name='+name+']');if(e)entered[name]=e.value;});
    }
    function invalidate() { remember(); review = null; dialog.querySelector('[data-money-review]').innerHTML = ''; dialog.querySelector('[data-money=confirm]').disabled = true; }
    function controls() {
      dialog.querySelectorAll('button,input').forEach(function (e) { e.disabled = busy; });
      var checked = dialog.querySelector('[name=confirmed]');
      dialog.querySelector('[data-money=confirm]').disabled = busy || !review || !review.can_confirm || !checked || !checked.checked;
      dialog.querySelector('[data-money=confirm]').hidden = !!review && !review.can_confirm;
      dialog.querySelector('[data-money=save_progress]').hidden = !review || !review.can_save_progress;
      dialog.querySelector('[data-money=save_progress]').disabled = busy || !review || !review.can_save_progress;
    }
    async function load() {
      var selected=data?ids():null;
      data = await options.api(endpoint + '?' + new URLSearchParams(scope)); invalidate();
      var saved=data.progress, completed=data.history.some(function(r){return !r.needs_review&&r.date_from===scope.from&&r.date_to===scope.to;});
      if(selected===null)selected=saved?saved.invoice_ids:[];
      if(saved){if(entered.actor===undefined)entered.actor=saved.actor;if(entered.reason===undefined)entered.reason=saved.reason;}
      dialog.querySelector('[data-money-unsigned]').innerHTML = (data.unsigned_invoices||[]).length ? '<details open><summary><strong>Bản nháp chưa tính vào tiền đã xuất</strong></summary><p>Các bản dưới đây chưa được đồng bộ ở trạng thái đã ký. Sau khi ký trên M-Invoice, bấm Cập nhật hóa đơn đã ký từ M-Invoice ở trên.</p><ul>'+(data.unsigned_invoices||[]).map(function(r){return '<li>Ngày '+esc(r.invoice_date)+' · Trước thuế '+money(r.subtotal)+' · Gồm thuế '+money(r.total_amount)+' · Đồng bộ '+esc(r.synced_at)+'</li>';}).join('')+'</ul></details>' : '';
      dialog.querySelector('[data-money-progress]').innerHTML = saved&&!completed?'<p><strong>Tiến độ đã lưu · '+esc(saved.from+' → '+saved.to)+'</strong><br>Tiền hóa đơn đã chọn: '+money(saved.signed_total)+' · Còn chưa xuất theo tiền: '+money(saved.remaining)+'. Chưa khép kỳ đơn.</p>'+(saved.needs_review?'<p class="selection-error">'+esc(saved.message)+' <button class="btn btn-outline" data-money="preview">Kiểm tra tổng tiền đã chọn</button></p>':''):'';
      dialog.querySelector('[data-money-list]').innerHTML = '<h3>Doanh thu kỳ đơn, gồm thuế: ' + money(data.orders_total) + '</h3>' +
        '<p>Danh sách dưới đây gồm cả hóa đơn kỳ khác. Chỉ tích hóa đơn thuộc đúng kỳ đang đối trừ.</p>' + (data.unavailable_invoices||[]).map(function(r){return '<p class="selection-error">Chưa dùng được hóa đơn '+esc(r.number)+': '+esc(r.error)+'</p>';}).join('') + '<div class="selection-table"><table><thead><tr><th>Chọn</th><th>Hóa đơn</th><th>Ngày hóa đơn</th><th>Tiền trước thuế</th><th>Thuế</th><th>Tổng tiền</th></tr></thead><tbody>' +
        data.invoices.map(function (r) { return '<tr><td><input type="checkbox" name="invoice" value="' + r.id + '" aria-label="Chọn hóa đơn ' + esc(r.invoice_number) + '"></td><td>' + esc(r.invoice_series + ' / ' + r.invoice_number) + '</td><td>' + esc(r.invoice_date) + '</td><td>' + money(r.subtotal) + '</td><td>' + money(r.tax_amount) + '</td><td>' + money(r.total_amount) + '</td></tr>'; }).join('') + '</tbody></table></div>';
      dialog.querySelectorAll('[name=invoice]').forEach(function(e){e.checked=selected.indexOf(Number(e.value))!==-1;});
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
          dialog.querySelector('[data-money-review]').innerHTML = '<h3>Doanh thu trong khoảng ngày: ' + money(review.orders_total) + ' − Tiền hóa đơn đã chọn: ' + money(review.signed_total) + ' = Chênh lệch: ' + money(review.remaining) + '</h3>' +
            '<p>Thuế trên đơn: ' + money(review.orders_tax) + ' · Thuế trên hóa đơn: ' + money(review.signed_tax) + '</p>' +
            ((review.price_differences||[]).length?'<details open><summary><strong>Giá trên hóa đơn đã ký khác đơn gốc trong kỳ</strong></summary><p>Các dòng dưới đây đã có liên kết với đơn gốc. Kiểm tra chứng từ trước khi xử lý chênh lệch; phần mềm giữ nguyên giá và công nợ.</p><ul>'+review.price_differences.map(function(r){return '<li>HĐ '+esc(r.invoice_number)+' · Đơn ngày '+esc(r.work_date)+' · '+esc(r.product_name)+' ('+esc(r.product_code)+'): '+esc(r.qty)+' × (giá hóa đơn '+money(r.invoice_price)+' − giá đơn '+money(r.order_price)+') = '+money(r.difference)+'</li>';}).join('')+'</ul></details>':'')+
            (review.remaining===0 && review.orders_tax !== review.signed_tax ? '<p class="selection-error">Tiền thuế đang khác nhau. Đối trừ tổng tiền không xác nhận thuế hoặc mặt hàng đã khớp; cần kiểm tra riêng phần chênh lệch này.</p>' : '') +
            review.conflicts.map(function (s) { return '<p class="selection-error">' + esc(s) + '</p>'; }).join('') +
            (review.can_confirm||review.can_save_progress ?
              (review.can_save_progress?'<p>Còn '+money(review.remaining)+' chưa xuất theo tiền. Chị có thể lưu tiến độ và tiếp tục làm phần khác; không cần xuất bù để khép kỳ đơn.</p>':'')+
              '<label>Người đối chiếu<input name="actor" maxlength="120" value="'+esc(entered.actor||'')+'"></label><label>Lý do / ghi chú<input name="reason" maxlength="1000" value="'+esc(entered.reason===undefined?(review.can_save_progress?'Đã kiểm tra phần hóa đơn đã ký; phần còn lại tiếp tục theo dõi':'Đã đối chiếu hóa đơn đã ký đủ tổng tiền cho kỳ đơn này'):entered.reason)+'"></label>'+(review.can_confirm?'<label><span><input type="checkbox" name="confirmed"> Tôi xác nhận các hóa đơn đã chọn thuộc kỳ đơn này và đã xuất đủ tổng tiền, dù chi tiết hàng có thể khác.</span></label>':'') : '<p class="selection-error">'+(!review.invoice_ids.length?'Chọn hóa đơn đã ký ở danh sách phía trên rồi bấm Kiểm tra tổng tiền đã chọn.':review.remaining<0?'Tiền hóa đơn đã chọn lớn hơn doanh thu trong khoảng ngày. Kiểm tra lại hóa đơn đã chọn hoặc khoảng ngày đơn.':'Kiểm tra các thông tin đối chiếu bên trên trước khi lưu.')+'</p><button class="btn btn-outline" data-money="choose">Đến danh sách hóa đơn</button>');
          status('Đã kiểm tra tổng tiền. Chưa thay đổi phần chưa xuất.');
        } else if (name === 'confirm' || name === 'save_progress') {
          if (!review || !(name==='confirm'?review.can_confirm:review.can_save_progress) || (name==='confirm'&&!dialog.querySelector('[name=confirmed]').checked)) throw new Error('Kiểm tra và xác nhận trước.');
          var actor = dialog.querySelector('[name=actor]').value.trim(), reason = dialog.querySelector('[name=reason]').value.trim();
          if (!actor || !reason) {focusAfter=!actor?'actor':'reason';throw new Error(!actor?'Điền Người đối chiếu để lưu.':'Điền Lý do / ghi chú để lưu.');}
          status(name==='confirm'?'Đang kiểm tra lại M-Invoice trước khi xác nhận. Không gửi hoặc ký thêm hóa đơn.':'Đang lưu tiến độ đối chiếu.');
          await options.api(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.assign({},scope,{action:name,invoice_ids:ids(),token:review.token,actor:actor,reason:reason,confirmed:name==='confirm'}))});
          await load(); status(name==='confirm'?'Đã chuyển kỳ đơn sang Đã đối trừ theo tiền. Doanh thu, công nợ và hàng đã ghi kho giữ nguyên.':'Đã lưu tiến độ. Phần còn lại vẫn chưa xuất; doanh thu, công nợ và lượng hàng giữ nguyên.');
          if(options.onSaved)await options.onSaved();
        } else if (name === 'choose') {
          focusAfter='invoice';
        } else if (name === 'revoke') {
          await options.api(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'revoke',id:Number(id),actor:dialog.querySelector('[name=revoke_actor_'+id+']').value,reason:dialog.querySelector('[name=revoke_reason_'+id+']').value})});
          await load(); status('Đã mở lại. Hệ thống đối chiếu theo hóa đơn hiện tại; lịch sử xác nhận vẫn được giữ.');
          if(options.onSaved)await options.onSaved();
        }
      } catch(error) { status(error.message,true); if((name==='confirm'||name==='save_progress')&&!focusAfter){review=null;focusAfter='preview';} }
      finally { busy=false;controls();if(focusAfter){var target=dialog.querySelector(focusAfter==='preview'?'[data-money=preview]':'[name='+focusAfter+']');if(target){target.scrollIntoView({block:'center'});target.focus();}focusAfter='';} }
    }
    dialog.addEventListener('change',function(e){if(e.target.name==='invoice')invalidate();controls();});
    dialog.addEventListener('click',function(e){var b=e.target.closest('[data-money]');if(b)action(b.dataset.money,b.dataset.id);});
    dialog.addEventListener('cancel',function(e){if(busy)e.preventDefault();});
    dialog.addEventListener('close',function(){dialog.remove();});
    await action('load');
  };
})();
