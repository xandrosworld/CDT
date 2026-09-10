/* Excel changes apply only to internal inventory identities. */
window.TdpOutputStockRemap = function (options) {
  const {api, downloadFile, esc, from, to, onApplied} = options;
  const dialog = document.createElement('dialog');
  dialog.className = 'inventory-totals-dialog output-remap-dialog';
  let preview = null, busy = false;
  const quantity = value => value == null ? '—' : Number(value).toLocaleString('vi-VN', {maximumFractionDigits:6});
  dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Xuất · Đổi mã hàng nội bộ qua Excel</h3><button class="icon-button" data-remap-close aria-label="Đóng">×</button></div>' +
    '<p>Kỳ ' + esc(from) + ' → ' + esc(to) + '. Tải Excel, sửa <strong>hai cột vàng A–B ở đầu bảng: Mã hàng muốn chuyển sang và Tên hàng muốn chuyển sang</strong>, rồi tải lên để xem trước. Sao chép đúng cặp mã + tên từ sheet Danh muc ma hang.</p>' +
    '<p>Cột C–G là hàng đang trừ kho và tồn để đối chiếu. Thông tin hóa đơn gốc nằm bên phải; mã nguồn có thể trống, còn mã nội bộ đang trừ kho nằm ở cột C. <strong>File mẫu cũ vẫn tải lên được</strong> bằng hai cột vàng Mã nội bộ mới và Tên nội bộ mới.</p>' +
    '<p><strong>So với báo cáo tồn:</strong> mở sheet <strong>Tổng hợp hàng âm</strong>, mỗi mã một dòng, và lọc <strong>Thuế danh mục</strong>. File đổi mã giữ từng dòng hóa đơn nên một mã có thể lặp nhiều lần. Không cộng lặp cột Tồn cuối kỳ. Thuế hóa đơn được trình bày riêng để đối chiếu.</p>' +
    '<p><strong>Giữ số lượng, trừ theo đơn vị của mã mới.</strong> Ví dụ: 35 Hộp chuyển sang mã có đơn vị Bịch thì trừ 35 Bịch. Tên hàng, đơn vị, lượng, tiền và thuế trên hóa đơn đã xuất được giữ nguyên.</p>' +
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
      message.textContent = 'Đã tải Excel. Chỉ sửa hai cột vàng A–B ở đầu bảng, lấy cặp mã + tên từ sheet Danh muc ma hang.';
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
      panel.innerHTML = '<div class="table-wrap"><table><thead><tr><th>Dòng Excel</th><th>Chuyển trừ kho</th><th>Lượng chuyển</th><th>Tồn hàng cũ sau chuyển</th><th>Tồn hàng nhận sau chuyển</th></tr></thead><tbody>' +
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
