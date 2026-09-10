/* Excel changes apply only to internal inventory identities. */
window.TdpOutputStockRemap = function (options) {
  const {api, downloadFile, esc, from, to, onApplied} = options;
  const dialog = document.createElement('dialog');
  dialog.className = 'inventory-totals-dialog output-remap-dialog';
  let preview = null, busy = false;
  const quantity = value => value == null ? '—' : Number(value).toLocaleString('vi-VN', {maximumFractionDigits:6});
  dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Xuất · Đổi mã hàng nội bộ qua Excel</h3><button class="icon-button" data-remap-close aria-label="Đóng">×</button></div>' +
    '<p>Kỳ ' + esc(from) + ' → ' + esc(to) + '. File mặc định chỉ gồm các dòng xuất của hàng âm cần xử lý, <strong>bỏ qua KKKNT</strong>. Số dòng và số mã ghi ngay đầu bảng Excel.</p>' +
    '<p>Thông tin hàng cũ ở cột L–P. Sửa <strong>hai cột vàng Q–R bên phải: Mã nội bộ mới và Tên nội bộ mới</strong>, sao chép đúng cặp mã + tên từ sheet Danh muc ma hang. Thông tin hóa đơn gốc vẫn đầy đủ ở bên trái. <strong>File đã sửa trước đây vẫn tải lên được</strong>, kể cả mẫu có hai cột vàng A–B.</p>' +
    '<p><strong>Chỉ chuyển đúng phần tồn âm của mỗi mã một lần.</strong> Ví dụ: âm 64 Gói thì tổng chuyển chỉ 64; âm 0,3 Kg chỉ chuyển 0,3. Các dòng được chọn xử lý từ trên xuống, dừng khi đủ phần âm. Phần chuyển dùng đơn vị mã mới; phần xuất còn lại vẫn trừ mã cũ. Hóa đơn gốc giữ nguyên.</p>' +
    '<label>Phạm vi tải <select data-remap-scope><option value="blocking">Chỉ hàng âm cần xử lý (bỏ qua KKKNT)</option><option value="all">Toàn bộ dòng xuất để tra cứu</option></select></label>' +
    '<div class="form-actions"><button class="btn btn-primary" data-remap-download>1. Tải Excel đổi mã nội bộ</button>' +
    '<label class="btn btn-outline">2. Chọn Excel đã sửa<input data-remap-file type="file" accept=".xlsx" style="display:block"></label></div>' +
    '<div class="warning-summary">KKKNT được lập bảng kê bổ sung và chuyển nguyên tồn âm sang tháng sau. Hàng KCT, 0% và có thuế vẫn cần xử lý tồn âm.</div>' +
    '<div data-remap-message role="status"></div><div data-remap-preview></div>';
  document.body.appendChild(dialog); dialog.showModal();
  const message = dialog.querySelector('[data-remap-message]');
  const panel = dialog.querySelector('[data-remap-preview]');
  function setBusy(value) {
    busy = value;
    dialog.querySelectorAll('button,input,select').forEach(el => { el.disabled = value; });
  }
  dialog.addEventListener('cancel', e => { if (busy) e.preventDefault(); });
  dialog.addEventListener('close', () => dialog.remove());
  dialog.querySelector('[data-remap-close]').onclick = () => { if (!busy) dialog.close(); };
  dialog.querySelector('[data-remap-download]').onclick = async () => {
    setBusy(true); message.textContent = 'Đang tạo Excel…';
    try {
      await downloadFile('/api/inventory/output-remap/export?from=' + encodeURIComponent(from) + '&to=' + encodeURIComponent(to) + '&scope=' + dialog.querySelector('[data-remap-scope]').value);
      message.textContent = 'Đã tải Excel. Sửa hai cột vàng Q–R bên phải, lưu file rồi chọn lại ở bước 2.';
    } catch (error) { message.textContent = error.message; }
    finally { setBusy(false); }
  };
  dialog.querySelector('[data-remap-file]').onchange = async e => {
    const file = e.target.files[0]; if (!file) return;
    preview = null; panel.innerHTML = ''; setBusy(true); message.textContent = 'Đang kiểm tra file và tính lại tồn…';
    const data = new FormData(); data.append('file', file);
    try {
      preview = await api('/api/inventory/output-remap/preview', {method:'POST', body:data});
      message.innerHTML = preview.errors.length ? '<strong>Chưa ghi nhận: còn ' + preview.errors.length + ' vấn đề cần sửa.</strong><ul>' + preview.errors.map(error => '<li>' + esc(error) + '</li>').join('') + '</ul><p>Sửa trên file vừa tải lên, lưu rồi chọn lại file ở bước 2. Không cần tải file mới.</p>' : 'Chưa ghi nhận. File hợp lệ; kiểm tra lượng xử lý âm bên dưới rồi bấm xác nhận.';
      if (preview.skipped?.length) message.innerHTML += '<p>Bỏ qua ' + preview.skipped.length + ' dòng đã chọn vì thuộc KKKNT, không âm hoặc đã đủ lượng xử lý âm.</p>';
      panel.innerHTML = '<div class="table-wrap"><table><thead><tr><th>Hàng số trong Excel</th><th>Chuyển trừ kho</th><th>Lượng cần xử lý luân chuyển</th><th>Tồn hàng cũ sau chuyển</th><th>Tồn hàng nhận sau chuyển</th></tr></thead><tbody>' +
        preview.changes.map(c => '<tr><td>' + c.excel_row + '</td><td>Từ <strong>' + esc(c.old_code) + ' · ' + esc(c.old_name) + '</strong><br>→ Sang <strong>' + esc(c.new_code) + ' · ' + esc(c.new_name) + '</strong></td><td>' + quantity(c.qty) + ' ' + esc(c.old_unit ?? c.unit) + ' → ' + quantity(c.qty) + ' ' + esc(c.unit) + '</td><td>' + quantity(c.old_closing_after) + ' ' + esc(c.old_unit ?? c.unit) + '</td><td>' + quantity(c.new_closing_after) + ' ' + esc(c.unit) + '</td></tr>').join('') + '</tbody></table></div>' +
        (preview.can_confirm ? '<form data-remap-confirm><label>Người xác nhận <input name="actor" maxlength="100" required></label><button class="btn btn-primary" type="submit">3. Xác nhận đổi mã nội bộ</button></form>' : '');
      const form = panel.querySelector('form');
      if (form) form.onsubmit = async event => {
        event.preventDefault(); if (busy) return;
        const actor = form.elements.actor.value.trim(); if (!actor) return;
        setBusy(true); message.textContent = 'Đang lưu và tính lại tồn…';
        try {
          const result = await api('/api/inventory/output-remap/confirm', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:preview.token, actor, confirmed:true})});
          panel.innerHTML = '';
          message.textContent = 'Đã đổi ' + result.changed_lines + ' dòng nội bộ và tính lại tồn. Hóa đơn gốc giữ nguyên.';
          await onApplied();
        } catch (error) { message.textContent = error.message; }
        finally { setBusy(false); }
      };
    } catch (error) { message.textContent = error.message; }
    finally { setBusy(false); e.target.value = ''; }
  };
};
