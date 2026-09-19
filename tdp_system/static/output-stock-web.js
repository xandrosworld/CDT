/* Direct correction of stock identities; posting requires a reviewed confirmation. */
window.TdpOutputStockWeb = function (options) {
  const {api, esc, from, to} = options;
  const dialog = document.createElement('dialog');
  dialog.className = 'inventory-totals-dialog output-stock-web';
  dialog.setAttribute('aria-label', 'Xử lý hàng âm');
  dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Xử lý hàng âm</h3><button class="btn btn-outline" data-close>Đóng</button></div>' +
    '<p>Kỳ ' + esc(from) + ' → ' + esc(to) + '. Chọn đúng mặt hàng để xem nguyên nhân và xử lý ngay tại đây.</p>' +
    '<div class="form-actions"><button class="btn btn-outline" data-reload>Cập nhật số liệu</button><button class="btn btn-outline" data-excel>Cách khác: sửa bằng Excel</button></div>' +
    '<div data-status role="status"></div><div data-issues role="alert"></div>' +
    '<div data-list></div><div data-editor></div><div data-preview></div>';
  document.body.appendChild(dialog); dialog.showModal();
  let data, activeCode = options.code || '', busy = false, preview = null;
  const el = selector => dialog.querySelector(selector);
  const qty = value => Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits:6});
  const field = name => el('[name="' + name + '"]');
  const post = body => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  function focus(name) {
    if (name === 'dates') { dialog.close(); options.onDates(); return; }
    if (name === 'reload') { el('[data-reload]').focus(); return; }
    if (name === 'period') { el('[data-period]')?.click(); return; }
    if (name === 'supplement') { el('[data-supplement]')?.click(); return; }
    const target = field(name); if (target) { target.scrollIntoView({block:'center'}); target.focus(); }
  }
  function issues(items) {
    el('[data-issues]').innerHTML = items.map((item, i) => '<p class="error-summary">' + esc(item.message) +
      ' <button type="button" class="btn btn-outline" data-fix="' + i + '">' +
      esc(item.field === 'reload' ? 'Cập nhật số liệu' : item.field === 'dates' ? 'Sửa khoảng ngày' : item.field === 'period' ? 'Mở kỳ kho' : 'Sửa tại đây') + '</button></p>').join('');
    el('[data-issues]').querySelectorAll('[data-fix]').forEach(button => button.onclick = () => {
      const target = items[Number(button.dataset.fix)].field;
      if (target === 'reload') load(true); else focus(target);
    });
    if (items.length) el('[data-issues]').scrollIntoView({block:'nearest'});
  }
  function working(value) {
    busy = value;
    dialog.querySelectorAll('button,input,select').forEach(control => { control.disabled = value; });
    if (!value && el('[data-confirm]')) el('[data-confirm]').disabled = !field('confirmed').checked;
  }
  function invalidate() { preview = null; el('[data-preview]').innerHTML = ''; issues([]); }
  function renderList() {
    el('[data-list]').innerHTML = '<div class="table-wrap"><table><thead><tr><th>Mã / tên hàng</th><th>Tồn cuối kỳ</th><th>Xử lý</th></tr></thead><tbody>' +
      data.items.map(item => '<tr><td>' + esc(item.product_code + ' · ' + item.product_name) + '</td><td>' + qty(item.closing_qty) + ' ' + esc(item.unit) + '</td><td><button class="btn btn-primary" data-item="' + esc(item.product_code) + '">Xem nguyên nhân và xử lý</button></td></tr>').join('') +
      (!data.items.length ? '<tr><td colspan="3">Không có hàng âm trong kỳ đã chọn.</td></tr>' : '') + '</tbody></table></div>';
    el('[data-list]').querySelectorAll('[data-item]').forEach(button => button.onclick = () => {
      activeCode = button.dataset.item; renderEditor();
    });
  }
  function renderEditor(saved) {
    invalidate();
    const item = data.items.find(row => row.product_code === activeCode);
    if (!item) { el('[data-editor]').innerHTML = activeCode ? '<p>' + esc(activeCode) + ': không còn âm trong kỳ đã chọn.</p>' : ''; return; }
    const unit = esc(item.unit);
    el('[data-editor]').innerHTML = '<section class="card"><h3>' + esc(item.product_code + ' · ' + item.product_name) + '</h3>' +
      '<div class="stock-cause-totals">' + [['Tồn đầu kỳ',item.opening_qty],['Nhập trong kỳ',item.input_qty],['Xuất trong kỳ',item.output_qty],['Tồn cuối kỳ',item.closing_qty]].map(pair => '<div><span>' + pair[0] + '</span><strong>' + qty(pair[1]) + ' ' + unit + '</strong></div>').join('') + '</div>' +
      (item.reversal_qty ? '<p>Hoàn tác trong kỳ: ' + qty(item.reversal_qty) + ' ' + unit + '.</p>' : '') +
      '<p>Cần đối chiếu ' + qty(-item.closing_qty) + ' ' + unit + '. Nếu hàng thực mua chưa ghi kho, kiểm tra đầu vào. Nếu dòng xuất đang trừ nhầm mã, chọn đúng mặt hàng thực tế đã xuất bên dưới.</p>' +
      '<div class="form-actions"><button class="btn btn-outline" data-input>Kiểm tra hóa đơn đầu vào</button>' +
      (item.supplementary_allowed ? '<button class="btn btn-primary" data-supplement>Lập bảng kê bổ sung cho mặt hàng này</button>' : '') + '</div>' +
      (data.blocked_reason ? '<p class="error-summary">' + esc(data.blocked_reason) + '</p><button class="btn btn-outline" data-period>Mở kỳ kho</button>' : '') +
      (!data.blocked_reason && !item.supplementary_allowed && item.sources.length ? '<form data-edit novalidate><h4>Sửa mã của dòng xuất bị trừ nhầm</h4>' +
        '<label>Dòng xuất cần sửa<select name="ledger_id">' + item.sources.map(row => '<option value="' + row.ledger_id + '">' + esc(row.date + ' · HĐ ' + row.invoice + ' · ' + row.source_name + ' · ' + qty(row.qty) + ' ' + item.unit) + '</option>').join('') + '</select></label>' +
        '<label>Mặt hàng thực tế đã xuất<input name="new_code" list="stock-web-products" placeholder="Gõ mã hoặc tên để chọn trong danh mục" autocomplete="off"></label>' +
        '<datalist id="stock-web-products">' + data.catalog.filter(p => p.code !== item.product_code && p.unit.trim().toLocaleLowerCase() === item.unit.trim().toLocaleLowerCase()).map(p => '<option value="' + esc(p.code) + '">' + esc(p.name + ' · Tồn cuối kỳ: ' + qty(p.closing_qty) + ' ' + p.unit) + '</option>').join('') + '</datalist><p data-target></p>' +
        '<label>Số lượng sửa (' + unit + ')<input name="qty" type="number" step="any" min="0" value="' + Math.min(-item.closing_qty, item.sources[0].qty) + '"></label>' +
        '<p>Chỉ sửa phần bị trừ nhầm, tối đa bằng phần còn âm và lượng của dòng xuất đã chọn. Mặt hàng nhận phải đúng hàng thực tế đã xuất, cùng đơn vị tính.</p><button class="btn btn-primary" type="submit">Xem trước thay đổi tồn kho</button></form>' :
        (!item.supplementary_allowed && !data.blocked_reason ? '<p>Không có dòng hóa đơn đã ký, đã ghi kho có thể sửa mã trong kỳ này. Kiểm tra đầu vào hoặc đối chiếu tồn đầu kỳ; không tự cộng kho để xóa âm.</p>' : '')) + '</section>';
    el('[data-input]').onclick = async () => {
      working(true);
      try { await options.onInput(activeCode); dialog.close(); }
      catch (error) { issues([{field:'reload', message:error.message}]); }
      finally { working(false); }
    };
    if (el('[data-supplement]')) el('[data-supplement]').onclick = () => options.onSupplement(activeCode, () => load(true));
    if (el('[data-period]')) el('[data-period]').onclick = () => options.onPeriod();
    if (el('[data-edit]')) {
      if (saved) ['ledger_id','new_code','qty'].forEach(key => { if (saved[key] != null) field(key).value = saved[key]; });
      const targetInfo = () => {
        const target = data.catalog.find(p => p.code === field('new_code').value.trim());
        el('[data-target]').textContent = target ? target.name + ' · Tồn cuối kỳ: ' + qty(target.closing_qty) + ' ' + target.unit : '';
      };
      targetInfo(); field('new_code').addEventListener('input', targetInfo);
      field('ledger_id').onchange = () => {
        const source = item.sources.find(r => String(r.ledger_id) === field('ledger_id').value);
        if (source) field('qty').value = Math.min(-item.closing_qty, source.qty);
        invalidate();
      };
      el('[data-edit]').onsubmit = check;
      requestAnimationFrame(() => focus(saved ? 'new_code' : 'ledger_id'));
    } else el('[data-editor]').scrollIntoView({block:'nearest'});
  }
  function values() {
    return field('ledger_id') ? {ledger_id:Number(field('ledger_id').value), new_code:field('new_code').value.trim(), qty:field('qty').value} : null;
  }
  async function check(event) {
    event.preventDefault(); if (busy) return;
    invalidate(); working(true); el('[data-status]').textContent = 'Đang kiểm tra thay đổi. Kho chưa được ghi nhận…';
    try {
      preview = await api('/api/inventory/output-remap/web-preview', post({from,to,version:data.version,product_code:activeCode,...values()}));
      issues(preview.issues);
      if (!preview.can_confirm) { el('[data-status]').textContent = 'Chưa ghi nhận. Bấm Sửa tại đây ở thông báo để sửa, không cần nhập lại.'; return; }
      const c = preview.changes[0];
      el('[data-preview]').innerHTML = '<section class="card"><h3>Xem trước · Kho chưa thay đổi</h3><p>Chuyển ' + qty(c.qty) + ' ' + esc(c.unit) + ' từ mã bị trừ nhầm sang mặt hàng thực tế đã xuất.</p>' +
        '<table><thead><tr><th>Mặt hàng</th><th>Tồn cuối kỳ sau khi sửa</th></tr></thead><tbody><tr><td>' + esc(c.old_code + ' · ' + c.old_name) + '</td><td>' + qty(c.old_closing_after) + ' ' + esc(c.old_unit) + '</td></tr><tr><td>' + esc(c.new_code + ' · ' + c.new_name) + '</td><td>' + qty(c.new_closing_after) + ' ' + esc(c.unit) + '</td></tr></tbody></table>' +
        '<p>Thông tin trên hóa đơn đã ký giữ nguyên. Thay đổi này chỉ sửa mã hàng trừ kho nội bộ.</p>' +
        '<form data-confirm-form novalidate><label>Người xác nhận<input name="actor" maxlength="100" autocomplete="name"></label>' +
        '<label><input name="confirmed" type="checkbox"> Tôi đã đối chiếu đúng mặt hàng thực tế đã xuất và số lượng sửa.</label>' +
        '<button class="btn btn-primary" data-confirm disabled>Xác nhận sửa và cập nhật kho</button></form></section>';
      el('[data-status]').textContent = 'Kiểm tra tồn sau khi sửa rồi xác nhận ở dưới.';
      el('[data-confirm-form]').onsubmit = confirm;
      field('confirmed').onchange = () => { el('[data-confirm]').disabled = !field('confirmed').checked; };
      el('[data-preview]').scrollIntoView({block:'start'});
    } catch (error) { el('[data-status]').textContent = 'Chưa ghi nhận.'; issues([{field:'reload',message:error.message}]); }
    finally { working(false); }
  }
  async function confirm(event) {
    event.preventDefault(); if (busy || !preview || !field('confirmed').checked) return;
    const actor = field('actor').value.trim();
    if (!actor) { issues([{field:'actor', message:'Điền Người xác nhận trước khi cập nhật kho.'}]); focus('actor'); return; }
    working(true);
    try {
      await api('/api/inventory/output-remap/confirm', post({token:preview.token, actor, confirmed:true}));
      invalidate(); el('[data-editor]').innerHTML = '';
      el('[data-status]').textContent = 'Đã cập nhật kho. Hàng hết âm được bỏ khỏi danh sách; hàng còn âm hiển thị số còn thiếu.';
      await options.onApplied(); await load(false, true);
    } catch (error) { issues([{field:'reload', message:error.message}]); }
    finally { working(false); }
  }
  async function load(preserve = true, afterSave = false) {
    if (busy && !afterSave) return;
    const saved = preserve ? values() : null;
    working(true);
    try {
      const result = await api('/api/inventory/output-remap/shortages?' + new URLSearchParams({from,to}));
      if (!dialog.isConnected) return;
      data = result; renderList(); renderEditor(saved);
      if (!afterSave) el('[data-status]').textContent = data.items.length + ' mặt hàng còn âm. Cập nhật số liệu không thay đổi kho.';
    } catch (error) { issues([{field:/Từ ngày|Đến ngày|ngày đầu|ngày cuối/.test(error.message) ? 'dates' : 'reload',message:error.message}]); }
    finally { working(false); }
  }
  el('[data-close]').onclick = () => { if (!busy) dialog.close(); };
  el('[data-reload]').onclick = () => load(true);
  el('[data-excel]').onclick = () => options.onExcel(() => load(true));
  dialog.addEventListener('input', event => { if (event.target.closest('[data-edit]')) invalidate(); });
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  dialog.addEventListener('close', () => dialog.remove());
  load();
};
