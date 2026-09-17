(function () {
  'use strict';
  window.TdpPurchaseDocumentSelection = async function (options) {
    var esc = options.esc, data = null, busy = false, dirty = false, sellerPreview = null;
    var money = function (n) { return Number(n).toLocaleString('vi-VN', {maximumFractionDigits: 2}) + ' đ'; };
    var dialog = document.createElement('dialog');
    dialog.className = 'purchase-selection-dialog';
    dialog.innerHTML = '<header><div><h2>Chọn hàng lập bảng kê / phần chờ</h2><p>1. Xem ngày mua → 2. Chọn hàng, nhập lượng lập → 3. Lưu lựa chọn.</p></div><button class="btn btn-outline" data-select-action="close">Đóng</button></header>' +
      '<p>Hạn mức lựa chọn: <strong>5.000.000đ / người bán / ngày</strong>, cộng chung các đơn cùng ngày. Người bán vượt hạn mức chưa được chọn sẵn.</p>' +
      '<p>Phần chưa chọn hiện riêng <strong>Chờ bổ sung chứng từ</strong>. Tiền mua, công nợ và hàng đã ghi kho giữ nguyên.</p>' +
      '<section class="pending-queue"><h3>Phần chờ các ngày đến hôm nay</h3><p>Tự nhớ phần còn lại theo ngày mua gốc, kể cả ngoài khoảng ngày bên dưới. Sang ngày mới không đổi ngày mua và không cấp thêm hạn mức. Phần đã chọn là lựa chọn đang lưu, chưa phải xác nhận đã in.</p><button class="btn btn-outline" data-select-action="pending-refresh">Cập nhật phần chờ</button><p class="pending-message" role="status">Đang kiểm tra các ngày…</p><div class="pending-days"></div><button class="btn btn-outline" data-select-action="pending-more" hidden>Xem tiếp các ngày còn lại</button></section>' +
      '<div class="selection-controls"><label>Từ ngày<input name="from" type="date" value="' + esc(options.from || '') + '"></label><label>Đến ngày<input name="to" type="date" value="' + esc(options.to || '') + '"></label><button class="btn btn-outline" data-select-action="load">Xem ngày mua</button></div>' +
      '<details class="seller-update"><summary><strong>Cập nhật người bán từ Excel</strong></summary><p>Dùng khi đơn đã ghi kho và chị sửa người bán hoặc tách lượng giữa người bán. Chọn cùng một ngày ở hai ô trên. Tiền mua, kho và công nợ giữ nguyên; số tiền bảng kê dùng giá mua BK đã ghi kho.</p><input name="seller_file" type="file" accept=".xlsx" aria-label="File đơn đã sửa người bán"><button class="btn btn-outline" data-select-action="seller-preview">Xem trước thay đổi</button><div class="seller-preview"></div></details>' +
      '<p class="selection-message" role="status"></p><div class="selection-days"></div>' +
      '<footer><label>Người lưu<input name="actor" maxlength="120" placeholder="Tên người chọn hàng"></label><label>Lý do thay bản đã lưu<input name="reason" maxlength="500" placeholder="Bắt buộc khi đổi lựa chọn cũ"></label><button class="btn btn-primary" data-select-action="save" disabled>Lưu lựa chọn</button></footer>' +
      '<p class="muted">Mỗi ngày chỉ có một lựa chọn đang dùng. Lưu lại thay thế bản trước; không tạo thêm một hạn mức mới. Bản Excel kèm tổng mua cả ngày và phần chờ.</p>';
    document.body.appendChild(dialog);
    dialog.showModal();
    var field = function (name) { return dialog.querySelector('[name="' + name + '"]'); };
    var message = function (text, error) { var el = dialog.querySelector('.selection-message'); el.textContent = text; el.classList.toggle('selection-error', !!error); };
    var pendingEntries = [], pendingAfter = null, pendingPages = 0;
    async function loadPending(more) {
      if (more && !pendingAfter) return;
      var status = dialog.querySelector('.pending-message');
      status.textContent = 'Đang cập nhật phần chờ…';
      status.classList.remove('selection-error');
      var pages = more ? 1 : Math.max(1, pendingPages), entries = more ? pendingEntries.slice() : [], cursor = more ? pendingAfter : null;
      try {
        var result, loaded = 0;
        for (var i = 0; i < pages; i++) {
          result = await options.api('/api/purchase-document-selection/pending' + (cursor ? '?after=' + encodeURIComponent(cursor) : ''));
          loaded++;
          entries = entries.concat(result.entries); cursor = result.next_after;
          if (!cursor) break;
        }
        pendingEntries = entries; pendingAfter = cursor; pendingPages = more ? pendingPages + loaded : loaded;
        var openDates = Array.from(dialog.querySelectorAll('.pending-days details[open]')).map(function (el) { return el.dataset.pendingDay; });
        dialog.querySelector('.pending-days').innerHTML = entries.map(function (day) {
          return '<details data-pending-day="' + esc(day.date) + '" ' + (day.status === 'needs_review' || openDates.indexOf(day.date) >= 0 ? 'open' : '') + '><summary><strong>Ngày mua ' + esc(day.date.split('-').reverse().join('/')) + '</strong> · ' + (day.status === 'needs_review' ? 'Cần đối chiếu nguồn' : money(day.pending) + ' · ' + (day.revision ? 'Lựa chọn đã lưu, bản ' + day.revision : 'Chưa lưu lựa chọn')) + '</summary>' +
            (day.error ? '<p class="selection-error">' + esc(day.error) + '</p>' : day.groups.map(function (group) {
              return '<p><strong>' + esc(group.seller) + '</strong> · Chờ: ' + money(group.pending) + ' · Còn có thể chọn trong ngày gốc: ' + money(group.remaining_capacity) + '</p><ul>' + group.rows.map(function (r) { return '<li>' + esc(r.product_name) + ': ' + esc(r.quantity) + ' ' + esc(r.unit) + ' · ' + money(r.amount) + ' · ' + esc(r.kitchen || '') + ' · Dòng ' + esc(r.source_ref) + '</li>'; }).join('') + '</ul>';
            }).join('')) + '<button class="btn btn-outline" data-select-action="pending-open" data-pending-date="' + esc(day.date) + '">Mở ngày mua này để xử lý</button></details>';
        }).join('');
        status.textContent = 'Đã cập nhật đến ' + result.through.split('-').reverse().join('/') + '. ' + (cursor ? 'Chưa xem hết các ngày: bấm Xem tiếp bên dưới.' : entries.length ? 'Đã kiểm tra hết các ngày có nguồn. Phần cần đối chiếu chưa được coi là đã xử lý.' : 'Không có phần chờ từ các lựa chọn hiện tại.');
        dialog.querySelector('[data-select-action="pending-more"]').hidden = !cursor;
      } catch (error) {
        status.textContent = 'Chưa cập nhật được phần chờ: ' + error.message + '. Danh sách đang hiện có thể đã cũ; bấm Cập nhật để thử lại.';
        status.classList.add('selection-error');
      }
    }
    function part(row) {
      var qty = Number(row.selected_quantity);
      return qty === Number(row.quantity) ? Number(row.amount) : Math.round((Number(row.amount) * qty / Number(row.quantity) + Number.EPSILON) * 100) / 100;
    }
    function updateTotals() {
      dialog.querySelector('footer').hidden = !!sellerPreview;
      dialog.querySelector('.selection-days').hidden = !!sellerPreview;
      var valid = !!(data && data.days.length) && data.from === field('from').value && data.to === field('to').value;
      if (data) data.days.forEach(function (day, di) {
        if (day.stale) valid = false;
        day.groups.forEach(function (group, gi) {
          var rows = day.rows.filter(function (r) { return r.cccd === group.identity; });
          var good = rows.every(function (r) { var q = Number(r.selected_quantity); return r.selected_quantity !== '' && Number.isFinite(q) && q >= 0 && q <= Number(r.quantity) && Math.abs(q * 1e6 - Math.round(q * 1e6)) < 0.00001; });
          var selected = rows.reduce(function (s, r) { return s + part(r); }, 0);
          var exceeded = selected > data.limit + 0.000001;
          var el = dialog.querySelector('[data-group="' + di + '-' + gi + '"]');
          el.textContent = 'Tổng mua: ' + money(group.total) + ' · Đã chọn: ' + money(selected) + ' · Chờ bổ sung: ' + money(group.total - selected) + (!good ? ' · Số lượng không hợp lệ' : exceeded ? ' · Vượt hạn mức — giảm lượng chọn' : '');
          el.classList.toggle('selection-error', !good || exceeded);
          if (!good || exceeded) valid = false;
        });
      });
      dialog.querySelector('[data-select-action="save"]').disabled = busy || !valid;
      var confirmButton = dialog.querySelector('[data-select-action="seller-confirm"]');
      if (confirmButton) confirmButton.disabled = busy || !sellerPreview || !field('seller_confirmed').checked || sellerPreview.date !== field('from').value || sellerPreview.date !== field('to').value;
    }
    function render() {
      dialog.querySelector('.selection-days').innerHTML = data.days.map(function (day, di) {
        return '<section><h3>Ngày ' + esc(day.date.split('-').reverse().join('/')) + ' · ' + (day.revision ? 'Bản đã lưu ' + day.revision : 'Chưa lưu lựa chọn') + '</h3>' +
          (day.stale ? '<p class="selection-error">Nguồn đã thay đổi sau khi lưu. Cần đối chiếu bảng kê đã lập trước khi thay lựa chọn.</p>' : '') +
          day.groups.map(function (group, gi) {
            return '<details ' + (group.total > data.limit ? 'open' : '') + '><summary><strong>' + esc(group.seller) + '</strong><span data-group="' + di + '-' + gi + '"></span></summary><div class="selection-table"><table><thead><tr><th>Chọn</th><th>Hàng / nguồn</th><th>ĐVT</th><th>Lượng mua</th><th>Lượng lập bảng kê</th><th>Tiền mua BK</th></tr></thead><tbody>' +
              day.rows.map(function (r, ri) {
                if (r.cccd !== group.identity) return '';
                return '<tr data-day="' + di + '" data-line="' + ri + '"><td><input type="checkbox" data-select-field="checked" ' + (Number(r.selected_quantity) > 0 ? 'checked' : '') + ' aria-label="Chọn ' + esc(r.product_name) + '"></td><td>' + esc(r.product_name) + '<small>' + esc(r.kitchen || '') + ' · Dòng ' + esc(r.source_ref) + '</small></td><td>' + esc(r.unit) + '</td><td>' + esc(r.quantity) + '</td><td><input type="number" min="0" max="' + esc(r.quantity) + '" step="0.000001" data-select-field="quantity" value="' + esc(r.selected_quantity) + '" aria-label="Lượng lập ' + esc(r.product_name) + '"></td><td>' + money(r.amount) + '</td></tr>';
              }).join('') + '</tbody></table></div></details>';
          }).join('') + '</section>';
      }).join('') || '<p>Không có hàng lập bảng kê của đơn đã duyệt trong khoảng ngày này.</p>';
      updateTotals();
    }
    async function action(name, pendingDate) {
      if (name === 'close') {
        if (!busy && (!dirty || window.confirm('Lựa chọn chưa lưu. Đóng và bỏ thay đổi?'))) dialog.close();
        return;
      }
      if (busy) return;
      if (name === 'pending-open') {
        if (dirty && !window.confirm('Mở ngày khác sẽ bỏ lựa chọn chưa lưu. Tiếp tục?')) return;
        field('from').value = pendingDate; field('to').value = pendingDate;
        sellerPreview = null; dialog.querySelector('.seller-preview').innerHTML = '';
        dirty = false; name = 'load';
      }
      if ((name === 'seller-preview' || name === 'seller-confirm') && dirty) { message('Lưu lựa chọn hàng đang sửa trước khi cập nhật người bán.', true); return; }
      if (name === 'load' && dirty && !window.confirm('Xem lại sẽ bỏ lựa chọn chưa lưu. Tiếp tục?')) return;
      busy = true;
      dialog.querySelectorAll('button,input').forEach(function (el) { el.disabled = true; });
      try {
        if (name === 'load') {
          data = await options.api('/api/purchase-document-selection?from=' + encodeURIComponent(field('from').value) + '&to=' + encodeURIComponent(field('to').value));
          dirty = false; render(); message('Chọn hàng hoặc nhập lượng cần lập. Nhập 0 để để lại toàn bộ dòng chờ bổ sung.');
        } else if (name === 'pending-refresh' || name === 'pending-more') {
          await loadPending(name === 'pending-more');
        } else if (name === 'seller-preview') {
          sellerPreview = null;
          dialog.querySelector('.seller-preview').innerHTML = '';
          if (!field('from').value || field('from').value !== field('to').value) throw new Error('Chọn cùng một ngày ở Từ ngày và Đến ngày để cập nhật file của ngày đó.');
          if (!field('seller_file').files.length) throw new Error('Chọn file Excel đã sửa người bán.');
          var upload = new FormData(); upload.append('date', field('from').value); upload.append('file', field('seller_file').files[0]);
          var preview = await options.api('/api/purchase-sellers/preview', {method: 'POST', body: upload});
          if (preview.unchanged) { message('Người bán trong file đã khớp bản đang dùng. Không cần lưu lại.'); return; }
          sellerPreview = preview;
          function parts(rows) { return rows.map(function (r) { return esc(r.seller) + ': ' + esc(r.quantity) + ' · ' + money(r.amount); }).join('<br>'); }
          dialog.querySelector('.seller-preview').innerHTML = '<h3>Thay đổi ngày ' + esc(preview.date) + '</h3><div class="selection-table"><table><thead><tr><th>Hàng / bếp</th><th>Đang dùng</th><th>Theo file mới</th></tr></thead><tbody>' + preview.changes.map(function (r) { return '<tr><td>' + esc(r.product_name) + '<br>' + esc(r.kitchen) + '</td><td>' + parts(r.before) + '</td><td>' + parts(r.after) + '</td></tr>'; }).join('') + '</tbody></table></div><h4>Tổng tiền BK cả ngày sau cập nhật</h4><ul>' + preview.groups.map(function (g) { return '<li>' + esc(g.seller) + ': ' + money(g.amount) + (g.over_limit ? ' — vượt hạn mức, cần chọn phần lập bảng kê' : '') + '</li>'; }).join('') + '</ul><p>Tổng tiền mua BK giữ nguyên: <strong>' + money(preview.total) + '</strong>. Bản cũ được lưu lịch sử. Nếu đã in bảng kê cũ, kiểm tra và thay bằng bản mới.</p><label class="seller-confirmation"><input name="seller_confirmed" type="checkbox"> Tôi đã đối chiếu: người bán và lượng hàng trong file đúng giao dịch thực tế.</label><div class="selection-controls"><label>Người lưu<input name="seller_actor" maxlength="120" placeholder="Tên người đối chiếu"></label><label>Lý do cập nhật<input name="seller_reason" maxlength="500" placeholder="Ghi lý do sửa người bán"></label></div><button class="btn btn-primary" data-select-action="seller-confirm" disabled>Lưu người bán theo file</button>';
          message('Đã đọc file. Kiểm tra thay đổi trước khi xác nhận lưu.');
        } else if (name === 'seller-confirm') {
          if (!sellerPreview || !field('seller_confirmed').checked) throw new Error('Kiểm tra và xác nhận người bán trước khi lưu.');
          if (!field('seller_actor').value.trim() || !field('seller_reason').value.trim()) throw new Error('Điền Người lưu và Lý do cập nhật ngay dưới phần xem trước.');
          await options.api('/api/purchase-sellers/confirm', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: sellerPreview.token, confirmed: true, actor: field('seller_actor').value, reason: field('seller_reason').value})});
          sellerPreview = null; dialog.querySelector('.seller-preview').innerHTML = ''; field('seller_file').value = '';
          data = await options.api('/api/purchase-document-selection?from=' + encodeURIComponent(field('from').value) + '&to=' + encodeURIComponent(field('to').value));
          dirty = false; render();
          message('Đã cập nhật người bán, giữ nguyên tiền mua, kho và công nợ. Kiểm tra lượng được chọn bên dưới; nếu đã có lựa chọn cũ, các dòng đổi người bán đang để 0 để chị chọn và lưu lại.');
          if (options.onSaved) options.onSaved();
          await loadPending(false);
        } else if (name === 'save') {
          if (!field('actor').value.trim()) throw new Error('Điền tên người lưu trước khi lưu lựa chọn.');
          data = await options.api('/api/purchase-document-selection', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
            from: data.from, to: data.to, state_hash: data.state_hash, actor: field('actor').value, reason: field('reason').value,
            days: data.days.map(function (day) { var quantities = {}; day.rows.forEach(function (r) { quantities[r.selection_key] = r.selected_quantity; }); return {date: day.date, quantities: quantities}; })
          })});
          dirty = false; field('reason').value = ''; render();
          message('Đã lưu. Đóng cửa sổ này, bấm Xem phần đã chọn hoặc Tải file đã chọn để lấy bảng kê và danh sách chờ bổ sung.');
          if (options.onSaved) options.onSaved();
          await loadPending(false);
        }
      } catch (error) { message(error.message, true); }
      finally {
        if (name === 'load') await loadPending(false);
        busy = false; dialog.querySelectorAll('button,input').forEach(function (el) { el.disabled = false; }); updateTotals();
      }
    }
    dialog.addEventListener('input', function (event) {
      if (['from', 'to', 'seller_file'].indexOf(event.target.name) >= 0) { sellerPreview = null; dialog.querySelector('.seller-preview').innerHTML = ''; }
      var tr = event.target.closest('tr[data-line]');
      if (tr) {
        var row = data.days[Number(tr.dataset.day)].rows[Number(tr.dataset.line)];
        row.selected_quantity = event.target.dataset.selectField === 'checked' ? (event.target.checked ? String(row.quantity) : '0') : event.target.value;
        tr.querySelector('[data-select-field="quantity"]').value = row.selected_quantity;
        tr.querySelector('[data-select-field="checked"]').checked = Number(row.selected_quantity) > 0;
        dirty = true; message('Lựa chọn đã thay đổi, chưa lưu.');
      }
      updateTotals();
    });
    dialog.addEventListener('click', function (event) { var button = event.target.closest('[data-select-action]'); if (button) action(button.dataset.selectAction, button.dataset.pendingDate); });
    dialog.addEventListener('cancel', function (event) { event.preventDefault(); action('close'); });
    var refreshTimer = window.setInterval(function () { if (dialog.open && !busy && !dirty && !sellerPreview && !document.hidden) action('pending-refresh'); }, 60000);
    dialog.addEventListener('close', function () { window.clearInterval(refreshTimer); dialog.remove(); });
    await action('load');
  };
})();
