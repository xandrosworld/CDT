(function () {
  'use strict';
  window.TdpPayableRepair = function (options) {
    var esc = options.esc, money = options.money, preview = null, busy = false, serial = 0;
    var dialog = document.createElement('dialog');
    dialog.className = 'payable-repair-dialog';
    dialog.setAttribute('aria-label', 'Sửa file Đặt hàng ngày ' + options.dateText);
    dialog.innerHTML = '<div class="repair-heading"><h2>Sửa file Đặt hàng ngày ' + esc(options.dateText) + '</h2><button type="button" class="btn btn-outline" data-close>Đóng</button></div>' +
      '<section data-instructions><h3>1. Sửa giá trong Excel rồi lưu file</h3><p>Mở file đơn hàng ngày ' + esc(options.dateText) + ', chọn sheet <b>Đặt hàng</b>. Điền giá mua đúng vào cột <b>Đơn giá</b> ở các dòng dưới đây, rồi nhấn <b>Ctrl + S</b>.</p>' +
      '<ul>' + (options.issues || []).map(function (issue) {
        var row = /^(Dòng \d+) · [^·]+ · (.*?):/.exec(issue);
        return '<li>' + esc(row ? row[1] + ' — ' + row[2] : issue) + '</li>';
      }).join('') + '</ul></section>' +
      '<section data-upload><h3>2. Chọn file vừa lưu</h3><label class="btn btn-primary repair-file-label">Chọn file Excel đã sửa<input type="file" accept=".xlsx" aria-label="Chọn file Excel đã sửa"></label><p data-filename></p></section>' +
      '<div data-preview></div><p role="status" aria-live="polite"></p>' +
      '<div class="repair-actions"><button type="button" class="btn btn-primary" data-save disabled>Lưu và cập nhật công nợ</button><button type="button" class="btn btn-outline" data-done hidden>Xem công nợ</button></div>' +
      '<p class="muted" data-note>Chỉ cập nhật Đặt hàng của ngày này. Đơn bán, phải thu và kho giữ nguyên.</p>';
    document.body.appendChild(dialog); dialog.showModal();
    var input = dialog.querySelector('input'), save = dialog.querySelector('[data-save]');
    var message = dialog.querySelector('[role=status]'), target = dialog.querySelector('[data-preview]');
    function say(text, error) { message.textContent = text; message.classList.toggle('danger-text', !!error); }
    function close() { if (busy) return; serial++; dialog.close(); dialog.remove(); }
    dialog.querySelector('[data-close]').onclick = close;
    dialog.querySelector('[data-done]').onclick = close;
    dialog.addEventListener('cancel', function (e) { e.preventDefault(); close(); });
    function cell(item) {
      var messages = (item.errors || []).concat(item.warnings || []);
      if (!messages.every(function (text) { return text.startsWith('Chưa có giá mua') || text === 'Giá mua không phải là số'; })) return 'Dòng ' + item.source_row;
      var column = (item._issue_columns || {}).buy_price, letters = '';
      while (column > 0) { column--; letters = String.fromCharCode(65 + column % 26) + letters; column = Math.floor(column / 26); }
      return letters ? letters + item.source_row : 'Dòng ' + item.source_row;
    }
    function problem(item) {
      var messages = (item.errors || []).concat(item.warnings || []);
      return messages.length && messages.every(function (text) { return text.startsWith('Chưa có giá mua') || text === 'Giá mua không phải là số'; })
        ? 'Nhập giá mua đúng, lớn hơn 0.' : messages.join('; ');
    }
    input.onchange = async function () {
      var file = input.files[0]; input.value = ''; if (!file || busy) return;
      var current = ++serial; preview = null; save.disabled = true; target.innerHTML = '';
      dialog.querySelector('[data-filename]').textContent = file.name;
      say('Đang kiểm tra file…');
      try {
        var form = new FormData(); form.append('file', file); form.append('batch_id', options.batchId); form.append('plan_only', '1');
        var result = await options.api('/api/purchase-orders/import/preview', { method: 'POST', body: form });
        if (current !== serial || !dialog.isConnected) return;
        if (result.batch_id !== options.batchId) throw new Error('Ngày nhận file không khớp. Đóng bảng này và chọn lại đúng ngày.');
        dialog.querySelector('[data-instructions]').hidden = true;
        var ready = result.can_confirm && !result.error_rows && !result.warning_rows;
        if (!ready) {
          target.innerHTML = '<h3>File vẫn còn chỗ cần sửa</h3><p>Với lỗi giá mua: mở Excel, bấm ô địa chỉ ở góc trái trên bảng, gõ địa chỉ ô dưới đây rồi Enter. Nhập giá đúng, nhấn Ctrl + S rồi chọn lại file. Nếu chọn nhầm ngày, chọn lại file đúng ngày.</p>' +
            '<div class="repair-table"><table><thead><tr><th>Ô trong Excel</th><th>Hàng</th><th>Cần sửa</th></tr></thead><tbody>' +
            (result.issues || []).map(function (item) { return '<tr><td><b>' + esc(cell(item)) + '</b></td><td>' + esc(item.product_name) + '</td><td>' + esc(problem(item)) + '</td></tr>'; }).join('') + '</tbody></table></div>';
          say('Chưa lưu. Sửa các ô được báo rồi bấm Chọn file Excel đã sửa lần nữa.', true);
          return;
        }
        preview = result;
        target.innerHTML = '<h3>3. Kiểm tra tổng tiền rồi bấm Lưu</h3><div class="repair-total"><span>Ngày ' + esc(options.dateText) + ' · ' + result.count + ' dòng Đặt hàng</span><strong>' + money(result.total_amount) + '</strong></div>';
        say('File đã đủ dữ liệu. Chưa thay đổi công nợ cho đến khi bấm Lưu.'); save.disabled = false;
      } catch (error) { if (current === serial) say(error.message, true); }
    };
    save.onclick = async function () {
      if (!preview || busy) return;
      busy = true; input.disabled = true; save.disabled = true; save.textContent = 'Đang cập nhật…'; say('Đang lưu file…');
      dialog.querySelector('[data-close]').disabled = true;
      try {
        var result = await options.api('/api/purchase-orders/import/confirm', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: preview.token, confirmed: true }) });
        preview = null;
        var ledger = await options.api('/api/debts/payables/ledger?' + new URLSearchParams({ from: options.date, to: options.date, status: 'open,partially_paid,paid', limit: '20000' }));
        var pending = (ledger.pending_purchase_sheets || []).find(function (item) { return item.batch_id === options.batchId; });
        dialog.querySelector('[data-instructions]').hidden = true; dialog.querySelector('[data-upload]').hidden = true; save.hidden = true;
        dialog.querySelector('[data-done]').hidden = false;
        dialog.querySelector('[data-done]').disabled = true;
        if (pending) {
          target.innerHTML = '<h3>Đã lưu file, nhưng công nợ ngày này vẫn chưa đủ</h3><ul>' + pending.issues.map(function (item) { return '<li>' + esc(item) + '</li>'; }).join('') + '</ul>';
          say('Xem công nợ để kiểm tra phần còn cần bổ sung.', true);
        } else {
          target.innerHTML = '<h3>Đã cập nhật xong ngày ' + esc(options.dateText) + '</h3><div class="repair-total"><span>Phát sinh phải trả của ngày này</span><strong>' + money(ledger.summary.filtered_amount) + '</strong></div>';
          say(result.idempotent ? 'File này đã được lưu trước đó. Công nợ không cộng thêm lần nữa.' : 'Đã lưu thành công. Bấm Xem công nợ để quay lại bảng tổng.');
        }
        await options.onSaved();
      } catch (error) {
        preview = null;
        say(error.message + ' — Kiểm tra lại công nợ. Nếu cần thử lại, chọn lại file; nạp lại cùng dữ liệu không cộng trùng.', true);
      } finally {
        busy = false; input.disabled = false; save.textContent = 'Lưu và cập nhật công nợ';
        dialog.querySelector('[data-close]').disabled = false; dialog.querySelector('[data-done]').disabled = false;
      }
    };
  };
})();
