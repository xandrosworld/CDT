/* Excel changes apply only to internal inventory identities. */
window.TdpOutputStockRemap = function (options) {
  const {api, downloadFile, esc, from, to, onApplied} = options;
  const dialog = document.createElement('dialog');
  dialog.className = 'inventory-totals-dialog output-remap-dialog';
  let preview = null, busy = false;
  dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Xuất · Đổi mã hàng nội bộ qua Excel</h3><button class="icon-button" data-remap-close aria-label="Đóng">×</button></div>' +
    '<p>Kỳ ' + esc(from) + ' → ' + esc(to) + '. File gồm các dòng xuất đã ghi kho trong kỳ. Tải Excel, sửa hai cột màu vàng theo danh mục rồi tải lên để xem trước.</p>' +
    '<p>Tên hàng, lượng, tiền và thuế trên hóa đơn đã xuất được giữ nguyên. Mỗi dòng chuyển toàn bộ lượng trừ kho sang mã mới cùng đơn vị.</p>' +
    '<div class="form-actions"><button class="btn btn-primary" data-remap-download>1. Tải Excel đổi mã nội bộ</button>' +
    '<label class="btn btn-outline">2. Chọn Excel đã sửa<input data-remap-file type="file" accept=".xlsx" style="display:block"></label></div>' +
    '<div class="warning-summary">KKKNT được lập bảng kê bổ sung và chuyển nguyên tồn âm sang tháng sau. Hàng KCT, 0% và có thuế vẫn cần xử lý tồn âm.</div>' +
    '<div data-remap-message role="status"></div><div data-remap-preview></div>';
  document.body.appendChild(dialog); dialog.showModal();
  const message = dialog.querySelector('[data-remap-message]');
  const panel = dialog.querySelector('[data-remap-preview]');
  function setBusy(value) {
    busy = value;
    dialog.querySelectorAll('button,input').forEach(el => { el.disabled = value; });
  }
  dialog.addEventListener('cancel', e => { if (busy) e.preventDefault(); });
  dialog.addEventListener('close', () => dialog.remove());
  dialog.querySelector('[data-remap-close]').onclick = () => { if (!busy) dialog.close(); };
  dialog.querySelector('[data-remap-download]').onclick = async () => {
    setBusy(true); message.textContent = 'Đang tạo Excel…';
    try {
      await downloadFile('/api/inventory/output-remap/export?from=' + encodeURIComponent(from) + '&to=' + encodeURIComponent(to));
      message.textContent = 'Đã tải Excel. Sửa mã và tên ở hai cột vàng, giữ nguyên các cột khác.';
    } catch (error) { message.textContent = error.message; }
    finally { setBusy(false); }
  };
  dialog.querySelector('[data-remap-file]').onchange = async e => {
    const file = e.target.files[0]; if (!file) return;
    preview = null; panel.innerHTML = ''; setBusy(true); message.textContent = 'Đang kiểm tra file và tính lại tồn…';
    const data = new FormData(); data.append('file', file);
    try {
      preview = await api('/api/inventory/output-remap/preview', {method:'POST', body:data});
      message.textContent = preview.errors.length ? preview.errors.join('\n') : 'File hợp lệ. Kiểm tra các dòng đổi mã trước khi xác nhận.';
      panel.innerHTML = '<div class="table-wrap"><table><thead><tr><th>Dòng Excel</th><th>Mã cũ</th><th>Mã mới</th><th>Tên nội bộ mới</th><th>Lượng chuyển</th><th>Tồn mã cũ sau</th><th>Tồn mã mới sau</th></tr></thead><tbody>' +
        preview.changes.map(c => '<tr><td>' + c.excel_row + '</td><td>' + esc(c.old_code) + '</td><td>' + esc(c.new_code) + '</td><td>' + esc(c.new_name) + '</td><td>' + c.qty + ' ' + esc(c.unit) + '</td><td>' + (c.old_closing_after ?? '—') + '</td><td>' + (c.new_closing_after ?? '—') + '</td></tr>').join('') + '</tbody></table></div>' +
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
