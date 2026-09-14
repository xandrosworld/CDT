(function () {
  'use strict';
  var esc = function (v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); };
  var number = function (v) { return Number(v).toLocaleString('vi-VN', {maximumFractionDigits: 6}); };
  var date = function (v) { return String(v || '').replace(/^(\d{4})-(\d{2})-(\d{2})$/, '$3/$2/$1'); };

  function open(options) {
    if (document.querySelector('.invoice-unit-dialog')) return;
    var dialog = document.createElement('dialog'), busy = false, rows = [], weights = [];
    var selected = Number(options.orderId) || 0;
    dialog.className = 'inventory-totals-dialog invoice-unit-dialog';
    dialog.setAttribute('aria-labelledby', 'invoiceUnitTitle');
    dialog.innerHTML = '<div class="inventory-totals-heading"><h3 id="invoiceUnitTitle">Sửa ĐVT / nhập kg thực tế</h3><button type="button" class="icon-button" data-close aria-label="Đóng">×</button></div>' +
      '<p>' + esc(options.scope.contractor || 'Tất cả nhà thầu đã chọn') + ' · ' + esc(date(options.scope.from)) + ' → ' + esc(date(options.scope.to)) + '</p>' +
      '<div data-unit-body></div><p data-unit-status role="status"></p><div class="compact-controls"><button type="button" class="btn btn-outline" data-reload>Tải lại dữ liệu dòng</button></div>';
    var body = dialog.querySelector('[data-unit-body]'), status = dialog.querySelector('[data-unit-status]');
    function lock(value) {
      busy = value;
      dialog.querySelectorAll('input,select,button').forEach(function (e) { e.disabled = value; });
    }
    function currentWeight() { return weights.find(function (r) { return r.order_id === selected; }); }
    function render() {
      var row = rows.find(function (r) { return r.order_id === selected; }), weight = currentWeight();
      if (!row) { body.innerHTML = '<p>Không còn dòng đang chọn trong phạm vi này. Kiểm tra nhà thầu, ngày hoặc dòng đã bỏ chọn trên bảng kê.</p>'; return; }
      body.innerHTML = '<label class="invoice-unit-row-picker">Dòng hàng cần sửa<select data-unit-row>' + rows.map(function (r) {
        return '<option value="' + r.order_id + '"' + (r.order_id === selected ? ' selected' : '') + '>' + esc(date(r.date) + ' · ' + r.contractor + ' · ' + r.kitchen + ' · ' + r.product_code + ' · ' + r.invoice_name + ' · dòng ' + r.order_id) + '</option>';
      }).join('') + '</select></label><h4>' + esc(row.product_code + ' · ' + row.invoice_name) + '</h4>' +
        '<p>Chưa xuất: <strong>' + number(weight ? weight.remaining_qty : row.qty) + ' ' + esc(row.unit) + '</strong> · ĐVT hóa đơn: <strong>' + esc(weight ? weight.invoice_unit : row.invoice_unit) + '</strong>' +
        (weight ? ' · ĐVT kho: ' + esc(weight.stock_unit) : '') + '</p>' +
        '<button type="button" class="btn btn-outline" data-catalog>Sửa ĐVT trong danh mục</button>' +
        '<p class="muted">ĐVT trong danh mục dùng cho những lần lập hóa đơn sau. Đổi chữ Túi/Gói thành Kg chưa tự đổi số lượng.</p>';
      if (weight && weight.review_kind === 'actual_kg' && weight.editable) {
        body.innerHTML += '<form data-weight-form><p>Nhập <strong>tổng kg thực tế của phần chưa xuất trên dòng này</strong>. Phần mềm tính giá/kg, giữ thành tiền <strong>' + number(weight.amount) + ' đ</strong>.</p>' +
          '<label>Tổng kg thực tế<input name="actual_kg" type="number" min="0.000001" max="999999.999999" step="0.000001" inputmode="decimal" required value="' + (weight.actual_kg == null ? '' : esc(weight.actual_kg)) + '" placeholder="Nhập số kg đã xác nhận"></label>' +
          '<p>Đơn giá: <strong data-price>' + (weight.price_per_kg == null ? 'Chưa nhập kg' : number(weight.price_per_kg) + ' đ/kg') + '</strong></p>' +
          '<label>Căn cứ số kg<input name="note" maxlength="500" required value="' + esc(weight.note) + '" placeholder="Ví dụ: đã cân / khách xác nhận"></label>' +
          '<label class="invoice-unit-confirm"><input type="checkbox" name="confirmed" required> Tôi xác nhận số kg của phần chưa xuất trên dòng này.</label>' +
          '<button type="submit" class="btn btn-primary">' + (weight.confirmed ? 'Cập nhật kg thực tế' : 'Lưu kg thực tế') + '</button>' +
          '<p class="muted">Lưu kg chưa gửi hóa đơn, chưa trừ kho. Sau khi lưu, kiểm tra và chuẩn bị lại bảng kê.</p></form>';
      } else if (weight) {
        body.innerHTML += '<p class="code-note">' + esc(weight.reason) + '</p>' + (weight.batch_id ? '<button type="button" class="btn btn-outline" data-order>Mở dòng đơn gốc</button>' : '');
        if (weight.review_kind === 'unit_mismatch') body.innerHTML += '<p>Đối chiếu đơn gốc và danh mục để sửa đúng đơn vị. Dòng này chưa đủ căn cứ để nhập kg.</p>';
      } else {
        body.innerHTML += '<p>Dòng này hiện không cần nhập kg riêng. Nếu muốn xuất theo Kg, kiểm tra và sửa ĐVT xuất hóa đơn trong danh mục trước.</p>';
      }
    }
    async function reload() {
      lock(true); status.textContent = 'Đang lấy số chưa xuất và ĐVT hiện tại…';
      try {
        var query = '?' + new URLSearchParams(options.scope).toString();
        var data = await Promise.all([options.api('/api/outgoing-invoices/actual-weights' + query), options.api('/api/outgoing-invoices/unissued' + query)]);
        if (!dialog.isConnected) return;
        weights = data[0].rows;
        rows = data[1].line_choices.filter(function (r) { return r.enabled && (!options.code || r.product_code === options.code); });
        if (!rows.some(function (r) { return r.order_id === selected; })) {
          var first = rows.find(function (r) { return weights.some(function (w) { return w.order_id === r.order_id && w.editable; }); }) || rows[0];
          selected = first ? first.order_id : 0;
        }
        status.textContent = ''; render();
      } catch (error) { body.innerHTML = ''; status.textContent = error.message + ' Bấm “Tải lại dữ liệu dòng” để thử lại.'; }
      finally { if (dialog.isConnected) lock(false); }
    }
    dialog.addEventListener('cancel', function (event) { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', function () { dialog.remove(); });
    dialog.addEventListener('change', function (event) { if (event.target.matches('[data-unit-row]')) { selected = Number(event.target.value); status.textContent = ''; render(); } });
    dialog.addEventListener('input', function (event) {
      if (event.target.name !== 'actual_kg') return;
      var kg = Number(event.target.value), weight = currentWeight();
      dialog.querySelector('[data-price]').textContent = Number.isFinite(kg) && kg > 0 ? number(weight.amount / kg) + ' đ/kg' : 'Chưa nhập kg';
    });
    dialog.addEventListener('click', async function (event) {
      if (busy) return;
      if (event.target.closest('[data-close]')) dialog.close();
      if (event.target.closest('[data-reload]')) await reload();
      var row = rows.find(function (r) { return r.order_id === selected; }), weight = currentWeight();
      if (row && event.target.closest('[data-catalog]')) { dialog.close(); await options.onCatalog(row.product_code, selected); }
      if (weight && event.target.closest('[data-order]')) { dialog.close(); await options.onOrder(weight); }
    });
    dialog.addEventListener('submit', async function (event) {
      if (!event.target.matches('[data-weight-form]')) return;
      event.preventDefault(); if (busy) return;
      var weight = currentWeight(), values = new FormData(event.target);
      lock(true); status.textContent = 'Đang lưu kg thực tế…';
      var saved = false;
      try {
        await options.api('/api/outgoing-invoices/actual-weights/' + selected, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:weight.token, actual_kg:values.get('actual_kg'), note:values.get('note'), confirmed_actual_weight:values.get('confirmed') === 'on'})});
        saved = true;
        await options.onSaved();
        await reload();
        status.textContent = 'Đã lưu kg thực tế, giữ nguyên thành tiền. Đóng cửa sổ để kiểm tra và chuẩn bị lại bảng kê.';
      } catch (error) { status.textContent = (saved ? 'Kg đã được lưu. ' : 'Chưa lưu kg. ') + error.message + ' Bấm “Tải lại dữ liệu dòng” trước khi sửa tiếp.'; }
      finally { if (dialog.isConnected) lock(false); }
    });
    document.body.appendChild(dialog); dialog.showModal(); reload();
  }
  window.TDPInvoiceUnitEditor = {open:open};
})();
