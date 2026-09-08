/* A focused, explicit source recheck. Opening/closing never edits invoice data. */
(function () {
  'use strict';
  window.TdpInvoiceAmountReview = async function (id, context) {
    var esc = context.esc, money = context.money, report = null, saving = false, updated = false;
    var url = '/api/invoice-workbench/output/' + encodeURIComponent(id) + '/amount-review';
    var dialog = document.createElement('dialog');
    dialog.className = 'invoice-amount-dialog';
    dialog.setAttribute('aria-label', 'Kiểm tra tiền hóa đơn');
    dialog.innerHTML = '<header><h2>Kiểm tra tiền hóa đơn</h2><button type="button" class="btn btn-outline" data-close>Đóng</button></header>' +
      '<div class="amount-review-body"><div data-result aria-live="polite">Đang mở hóa đơn…</div><p class="invoice-amount-difference" data-error role="alert"></p></div>' +
      '<footer><button type="button" class="btn btn-primary" data-recheck>Kiểm tra lại M-Invoice</button>' +
      '<button type="button" class="btn btn-outline" data-download>Tải hồ sơ hỗ trợ</button>' +
      '<button type="button" class="btn btn-primary" data-apply disabled>Cập nhật hóa đơn</button></footer>';
    function controls(value) {
      dialog.querySelectorAll('button').forEach(function (button) { button.disabled = value; });
      dialog.querySelector('[data-close]').disabled = saving;
      dialog.querySelector('[data-apply]').disabled = value || !report || !report.can_apply;
      dialog.setAttribute('aria-busy', String(value));
    }
    async function requestJSON(path, options) {
      var response = await fetch(path, options), data;
      try { data = await response.json(); } catch (_) { throw new Error('Chưa kết nối được. Hãy thử lại.'); }
      if (!response.ok || !data.ok) throw new Error(data.error || 'Chưa kiểm tra được hóa đơn. Hãy thử lại.');
      return data;
    }
    function render() {
      var number = function (value) { return Number(value).toLocaleString('vi-VN', {maximumFractionDigits: 6}); };
      dialog.querySelector('[data-result]').innerHTML = '<h3>' + esc(report.series + ' / ' + report.number) + ' · ' + esc(report.date.split('-').reverse().join('/')) + '</h3>' +
        '<p>' + esc(report.buyer) + '</p><p><strong>' + (report.fresh ? 'Vừa kiểm tra lại từ M-Invoice.' : 'Dữ liệu đã tải về web.') + '</strong> ' + esc(report.message) + '</p>' +
        (report.status_note ? '<p class="invoice-amount-difference">' + esc(report.status_note) + '</p>' : '') +
        '<div class="amount-review-table"><table><thead><tr><th>Khoản tiền</th><th>Cộng chi tiết</th><th>Tổng hóa đơn</th><th>Chênh lệch</th></tr></thead><tbody>' +
        report.comparisons.map(function (c) { return '<tr><th>' + esc(c.label) + '</th><td>' + money(c.detail) + '</td><td>' + money(c.header) + '</td><td class="' + (Math.abs(c.difference) > 1 ? 'invoice-amount-difference' : '') + '">' + money(c.difference) + '</td></tr>'; }).join('') + '</tbody></table></div>' +
        (report.changes.length ? '<p><strong>So với lần tải trước:</strong> ' + report.changes.map(esc).join(' ') + '</p>' : '') +
        '<h3>' + report.lines.length + ' dòng hàng</h3><div class="amount-review-table amount-review-lines"><table><thead><tr><th>Dòng</th><th>Tên hàng</th><th>Lượng / ĐVT</th><th>Đơn giá</th><th>Tiền chưa thuế</th><th>Kiểm tra</th></tr></thead><tbody>' +
        report.lines.map(function (l) { return '<tr class="' + (l.note ? 'amount-line-check' : '') + '"><td>' + l.line + '</td><td>' + esc(l.name) + '</td><td>' + number(l.qty) + ' ' + esc(l.unit) + '</td><td>' + money(l.price) + '</td><td>' + money(l.amount) + '</td><td>' + esc([l.note, l.change].filter(Boolean).join(' ')) + '</td></tr>'; }).join('') + '</tbody></table></div>' +
        '<p class="amount-review-help">' + (report.can_apply ? 'Cập nhật sẽ lưu dữ liệu vừa kiểm tra vào web. Chưa ghi xuất kho.' : 'Chỉ cập nhật khi dữ liệu mới đã khớp tổng. Nếu vẫn lệch: tải hồ sơ hỗ trợ và gửi file đó, không cần chụp màn hình. Các hóa đơn khác đủ điều kiện vẫn làm tiếp được.') + '</p>';
    }
    async function load(fresh) {
      controls(true); dialog.querySelector('[data-error]').textContent = ''; dialog.querySelector('[data-error]').dataset.success = 'false';
      dialog.querySelector('[data-recheck]').textContent = fresh ? 'Đang kiểm tra M-Invoice…' : 'Đang mở…';
      try { report = await requestJSON(url + (fresh ? '?fresh=1' : '')); render(); }
      catch (error) {
        // A failed newer check must revoke any earlier apply offer.
        if (report) report.can_apply = false;
        else dialog.querySelector('[data-result]').textContent = 'Chưa mở được thông tin hóa đơn.';
        dialog.querySelector('[data-error]').textContent = error.message;
      }
      finally { controls(false); dialog.querySelector('[data-recheck]').textContent = 'Kiểm tra lại M-Invoice'; }
    }
    dialog.querySelector('[data-recheck]').onclick = function () { return load(true); };
    dialog.querySelector('[data-download]').onclick = async function () {
      controls(true); dialog.querySelector('[data-error]').textContent = ''; dialog.querySelector('[data-error]').dataset.success = 'false';
      try {
        var response = await fetch(url + '?download=1');
        if (!response.ok || !(response.headers.get('content-type') || '').includes('spreadsheetml')) throw new Error('Chưa tải được hồ sơ. Hãy thử lại.');
        var objectURL = URL.createObjectURL(await response.blob()), link = document.createElement('a');
        link.href = objectURL; link.download = 'Kiem-tra-hoa-don-' + (report ? report.number : id) + '.xlsx';
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(function () { URL.revokeObjectURL(objectURL); }, 30000);
        dialog.querySelector('[data-error]').dataset.success = 'true';
        dialog.querySelector('[data-error]').textContent = 'Đã tải hồ sơ. Gửi file này cho người hỗ trợ.';
      } catch (error) { dialog.querySelector('[data-error]').textContent = error.message; }
      finally { controls(false); }
    };
    dialog.querySelector('[data-apply]').onclick = async function () {
      if (!report || !report.can_apply) return;
      try { if (context.beforeApply) context.beforeApply(); }
      catch (error) { dialog.querySelector('[data-error]').dataset.success = 'false'; dialog.querySelector('[data-error]').textContent = error.message; return; }
      saving = true;
      controls(true); dialog.querySelector('[data-error]').textContent = ''; dialog.querySelector('[data-error]').dataset.success = 'false';
      try {
        var result = await requestJSON(url + '/apply', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({expected: report.expected, source_digest: report.source_digest})});
        updated = true;
        dialog.querySelector('[data-result]').innerHTML = '<h3>' + esc(result.message) + '</h3>';
        dialog.querySelector('footer').hidden = true;
        await context.refresh();
      } catch (error) { dialog.querySelector('[data-error]').textContent = error.message; report.can_apply = false; }
      finally { saving = false; controls(false); }
    };
    dialog.querySelector('[data-close]').onclick = function () { if (!saving) dialog.close(); };
    dialog.addEventListener('cancel', function (event) { if (saving) event.preventDefault(); });
    dialog.addEventListener('close', function () { dialog.remove(); if (context.closed) context.closed(updated); }, {once: true});
    document.body.appendChild(dialog); dialog.showModal();
    await load(false);
  };
}());
