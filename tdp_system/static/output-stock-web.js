/* Direct correction of stock identities; posting requires a reviewed confirmation. */
window.TdpOutputStockWeb = function (options) {
  const {api, esc, from, to} = options;
  const dialog = document.createElement('dialog');
  dialog.className = 'inventory-totals-dialog output-stock-web';
  dialog.setAttribute('aria-label', 'Xử lý hàng âm');
  dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Xử lý hàng âm</h3><button class="btn btn-outline" data-close>Đóng</button></div>' +
    '<p>Kỳ ' + esc(from) + ' → ' + esc(to) + '. Chọn đúng mặt hàng để xem nguyên nhân và xử lý ngay tại đây.</p>' +
    '<div class="form-actions"><button class="btn btn-outline" data-reload>Cập nhật số liệu</button><button class="btn btn-outline" data-excel>Cách khác: sửa bằng Excel</button></div>' +
    '<p>Đã làm trước đây: xem <b>Điều chỉnh đã lưu</b> bên dưới trước khi nhập lại. Nếu mới sửa file Excel, bấm <b>Cách khác: sửa bằng Excel</b> để tải lên chính file đã sửa và kiểm tra trước khi xác nhận.</p>' +
    '<div data-status role="status"></div><div data-issues role="alert"></div><div data-history></div>' +
    '<div data-list></div><div data-editor></div><div data-preview></div>';
  document.body.appendChild(dialog); dialog.showModal();
  let data, activeCode = options.code || '', busy = false, preview = null;
  // Keep unfinished entries for this tab/period; never restore posting consent.
  const draftKey = 'tdp-stock-correction-drafts:' + from + ':' + to;
  let drafts = {};
  try { drafts = JSON.parse(sessionStorage.getItem(draftKey) || '{}') || {}; } catch (_) {}
  function persistDrafts() { try { sessionStorage.setItem(draftKey, JSON.stringify(drafts)); } catch (_) {} }
  function remember() { const current = values(); if (current && activeCode) { drafts[activeCode] = current; persistDrafts(); } }
  const el = selector => dialog.querySelector(selector);
  const qty = value => Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits:6});
  const field = name => el('[name="' + name + '"]');
  const post = body => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  function focus(name) {
    if (name === 'dates') { dialog.close(); options.onDates(); return; }
    if (name === 'reload') { el('[data-reload]').focus(); return; }
    if (name === 'period') { el('[data-period]')?.click(); return; }
    if (name === 'supplement') { el('[data-supplement]')?.click(); return; }
    if (name === 'availability') { const box = el('[data-availability]'); if (box) { box.scrollIntoView({block:'center'}); box.focus(); } return; }
    const target = field(name); if (target) { target.scrollIntoView({block:'center'}); target.focus(); }
  }
  function issues(items) {
    dialog.querySelectorAll('[data-issues],[data-edit-issues],[data-confirm-issues]').forEach(box => { box.innerHTML = ''; });
    dialog.querySelectorAll('[aria-invalid]').forEach(control => control.removeAttribute('aria-invalid'));
    const box = (items.some(item => item.field === 'actor' || item.field === 'confirmed') ? el('[data-confirm-issues]') : el('[data-edit-issues]')) || el('[data-issues]');
    box.innerHTML = items.map((item, i) => '<p class="error-summary">' + esc(item.message) +
      ' <button type="button" class="btn btn-outline" data-fix="' + i + '">' +
      esc(item.field === 'availability' ? 'Xem tồn và dự thảo' : item.field === 'reload' ? 'Cập nhật số liệu' : item.field === 'dates' ? 'Sửa khoảng ngày' : item.field === 'period' ? 'Mở kỳ kho' : 'Sửa tại đây') + '</button></p>').join('');
    items.forEach(item => field(item.field)?.setAttribute('aria-invalid', 'true'));
    box.querySelectorAll('[data-fix]').forEach(button => button.onclick = () => {
      const target = items[Number(button.dataset.fix)].field;
      if (target === 'reload') load(true); else focus(target);
    });
    if (items.length) box.scrollIntoView({block:'nearest'});
  }
  function working(value) {
    busy = value;
    dialog.querySelectorAll('button,input,select').forEach(control => { control.disabled = value; });
    if (!value && el('[data-confirm]')) el('[data-confirm]').disabled = !field('confirmed').checked;
    if (!value && el('[data-release-confirm]')) el('[data-release-confirm]').disabled = !field('release_confirmed').checked;
  }
  function invalidate() { preview = null; el('[data-preview]').innerHTML = ''; el('[data-availability]')?.remove(); issues([]); }
  function renderAvailability(info) {
    if (!info) return;
    const box = document.createElement('section'); box.className = 'card'; box.dataset.availability = ''; box.tabIndex = -1;
    const unit = esc(info.unit);
    box.innerHTML = '<h4>Tồn có thể dùng để sửa · ' + esc(info.product_code) + '</h4><p>Tồn cuối kỳ: <b>' + qty(info.closing_qty) + ' ' + unit + '</b>. Dự thảo đang giữ: <b>' + qty(info.reserved_qty) + ' ' + unit + '</b>.</p>' +
      '<details class="stock-hold-calculation"><summary>Chi tiết cách tính tồn</summary><p>Tồn thấp nhất từ cuối kỳ trở đi: ' + qty(info.minimum_qty) + ' ' + unit + '. Hóa đơn đã ghi nhận phát hành, chờ đối chiếu vào sổ kho: ' + qty(info.pending_qty) + ' ' + unit + '.</p></details>' +
      '<p><b>Có thể dùng để sửa tối đa: ' + qty(info.available_qty) + ' ' + unit + '</b> (đồng thời không vượt phần còn âm và lượng của Dòng xuất cần sửa).</p>' +
      (info.holds_enforced === false ? '<p>Mặt hàng KKKNT áp dụng quy tắc riêng: phần sửa này chỉ giới hạn theo tồn cuối kỳ, không trừ lượng dự thảo đang giữ.</p>' : '') +
      (info.holds || []).map(hold => '<section class="stock-hold-action" data-hold="' + hold.id + '"><h4>Dự thảo #' + hold.id + ' · ' + esc(hold.contractor) + '</h4>' +
        '<p>Ngày ' + esc(hold.invoice_date) + ' · Đang giữ <b>' + qty(hold.qty) + ' ' + unit + '</b> của mặt hàng <b>' + esc(info.product_code) + '</b>.</p>' +
        (hold.can_cancel ? '<p><b>Bước tiếp theo:</b> Nếu dự thảo chưa phát hành và không còn dùng mặt hàng này, bấm nút dưới để xem trước. Các mặt hàng khác được giữ lại.</p><button type="button" class="btn btn-primary" data-release-hold="' + hold.id + '">Bỏ riêng mặt hàng này</button><p class="stock-hold-help">Bấm nút chỉ mở bước xem trước, chưa thay đổi dự thảo hoặc kho.</p>' : '<p>Dự thảo đã gửi hoặc đang đối chiếu với M-Invoice; cần xử lý tại phần hóa đơn, không thể bỏ mặt hàng tại đây.</p>') +
        '<details><summary>Xem toàn bộ ' + hold.line_count + ' dòng của dự thảo và cách hủy toàn bộ</summary>' +
        '<div class="table-wrap"><table><thead><tr><th>Mã / tên hàng</th><th>Số lượng</th></tr></thead><tbody>' + hold.lines.map(line => '<tr><td>' + esc(line.product_code + ' · ' + line.product_name) + '</td><td>' + qty(line.qty) + ' ' + esc(line.unit) + '</td></tr>').join('') + '</tbody></table></div>' +
        (hold.can_cancel ? '<p>Chỉ hủy toàn bộ nếu không còn dùng tất cả ' + hold.line_count + ' dòng. File cũ không được tiếp tục dùng để phát hành.</p><button type="button" class="btn btn-outline" data-cancel-hold="' + hold.id + '">Hủy dự thảo #' + hold.id + ' không còn dùng…</button>' : '') + '</details></section>').join('') + '<div data-release-review></div>';
    el('[data-edit]').insertBefore(box, el('[data-edit] .stock-save-actions'));
    box.querySelectorAll('[data-release-hold]').forEach(button => button.onclick = async () => {
      if (busy) return;
      working(true);
      const review = el('[data-release-review]');
      try {
        const plan = await api('/api/inventory/output-remap/release-product/preview', post({draft_id:Number(button.dataset.releaseHold),product_code:info.product_code}));
        const rows = list => list.map(line => '<tr><td>' + esc(line.product_code + ' · ' + line.product_name) + '</td><td>' + qty(line.qty) + ' ' + esc(line.unit) + '</td></tr>').join('');
        review.innerHTML = '<section class="card" tabindex="-1"><h4>Xem trước: bỏ riêng ' + esc(plan.product_code) + ' khỏi dự thảo #' + plan.draft_id + '</h4>' +
          '<p><b>Chưa thay đổi dữ liệu.</b> Bỏ các dòng sau và giải phóng lượng đang giữ:</p><table><thead><tr><th>Mặt hàng bỏ khỏi dự thảo</th><th>Số lượng</th></tr></thead><tbody>' + rows(plan.removed) + '</tbody></table>' +
          '<details><summary>Giữ lại ' + plan.kept.length + ' dòng khác · Bấm để đối chiếu</summary><div class="table-wrap"><table><thead><tr><th>Mặt hàng giữ lại</th><th>Số lượng</th></tr></thead><tbody>' + rows(plan.kept) + '</tbody></table></div></details>' +
          '<p>Dự thảo cũ được lưu trong lịch sử. ' + (plan.kept.length ? 'Các dòng giữ lại được chuyển sang dự thảo mới, giữ nguyên số lượng, đơn giá, ngày và liên kết đơn gốc. ' : '') +
          'Không dùng lại file đã tải của dự thảo cũ; cần kiểm tra và tải file mới nếu tiếp tục lập hóa đơn.</p>' +
          '<p>Thao tác này không xác nhận đã xuất hóa đơn hay đã thanh toán. Đơn gốc vẫn còn; lần lập dự thảo tiếp theo có thể chọn lại mặt hàng này theo tồn khả dụng. Sửa mã xuất kho cần kiểm tra và xác nhận riêng.</p>' +
          '<label>Người xác nhận<input name="release_actor" maxlength="100" autocomplete="name"></label>' +
          '<label><input type="checkbox" name="release_confirmed"> Tôi xác nhận dự thảo này chưa phát hành trên M-Invoice, không còn dùng các dòng mặt hàng nêu trên và không dùng lại file cũ.</label>' +
          '<p data-release-error role="alert"></p><div class="form-actions"><button type="button" class="btn btn-primary" data-release-confirm disabled>Xác nhận bỏ riêng mặt hàng này</button><button type="button" class="btn btn-outline" data-release-back>Quay lại, chưa thay đổi</button></div></section>';
        field('release_confirmed').onchange = () => { el('[data-release-confirm]').disabled = !field('release_confirmed').checked; };
        el('[data-release-back]').onclick = () => { review.innerHTML = ''; button.focus(); };
        el('[data-release-confirm]').onclick = async () => {
          if (busy || !field('release_confirmed').checked) return;
          const actor = field('release_actor').value.trim();
          if (!actor) { el('[data-release-error]').textContent = 'Điền Người xác nhận trước khi bỏ mặt hàng khỏi dự thảo.'; field('release_actor').focus(); return; }
          remember(); working(true);
          try {
            const result = await api('/api/inventory/output-remap/release-product/confirm', post({token:plan.token,actor,confirmed:true}));
            invalidate(); working(false); await load(true);
            el('[data-status]').textContent = 'Đã bỏ riêng ' + result.product_code + ' khỏi dự thảo #' + result.draft_id + ', giải phóng ' + qty(result.released_qty) + ' ' + info.unit + '. ' +
              (result.replacement_draft_id ? 'Đã giữ ' + result.kept_lines + ' dòng khác trong dự thảo #' + result.replacement_draft_id + '. ' : '') +
              'Mã hàng và Số lượng sửa vẫn còn. Bấm 1. Kiểm tra trước khi lưu để tiếp tục sửa kho; chưa sửa số liệu kho.';
            focus('new_code');
          } catch (error) { el('[data-release-error]').textContent = error.message; el('[data-release-error]').scrollIntoView({block:'center'}); }
          finally { working(false); }
        };
        review.firstElementChild.scrollIntoView({block:'center'}); review.firstElementChild.focus();
      } catch (error) { review.textContent = error.message; review.scrollIntoView({block:'center'}); }
      finally { working(false); }
    });
    box.querySelectorAll('[data-cancel-hold]').forEach(button => button.onclick = async () => {
      if (busy) return;
      const id = Number(button.dataset.cancelHold), hold = info.holds.find(row => row.id === id);
      if (!window.confirm('Chỉ tiếp tục nếu dự thảo #' + id + ' của ' + hold.contractor + ' chưa phát hành trên M-Invoice và không còn sử dụng.\n\nHủy toàn bộ ' + hold.line_count + ' dòng và nhả tồn đang giữ? Không tiếp tục dùng file đã tải của dự thảo này.\n\nSửa mã xuất kho vẫn cần kiểm tra và xác nhận riêng.')) return;
      remember(); working(true);
      try {
        await api('/api/outgoing-invoices/' + id + '/cancel', post({confirmed:true}));
        invalidate(); working(false); await load(true);
        el('[data-status]').textContent = 'Đã hủy dự thảo #' + id + ' và nhả tồn đang giữ. Mã hàng và Số lượng sửa đã giữ lại; bấm 1. Kiểm tra trước khi lưu để tiếp tục. Chưa sửa mã xuất kho.';
      } catch (error) { issues([{field:'availability',message:error.message}]); }
      finally { working(false); }
    });
  }
  function renderHistory() {
    const history = data.history || [];
    el('[data-history]').innerHTML = '<details class="card"><summary><b>Điều chỉnh đã lưu: ' + history.length + ' dòng</b> · Bấm xem phần đã xác nhận trên web hoặc từ Excel</summary>' +
      '<p>Lịch sử các lần xác nhận có kỳ xử lý giao với khoảng ngày đang xem. Không nhập lại các lần đã lưu. Tồn kho hiện tại được tính ở bảng bên dưới.</p>' +
      (history.length ? '<div class="table-wrap"><table><thead><tr><th>Đã lưu lúc / Người xác nhận</th><th>Mã bị trừ nhầm</th><th>Mặt hàng thực tế đã xuất</th><th>Số lượng sửa</th><th>Cách lưu / Kỳ xử lý</th></tr></thead><tbody>' + history.map(row => '<tr><td>' + esc(row.saved_at + ' · ' + row.actor) + '</td><td>' + esc(row.old_code + ' · ' + row.old_name) + '</td><td>' + esc(row.new_code + ' · ' + row.new_name) + '</td><td>' + qty(row.qty) + ' ' + esc(row.unit) + '</td><td>' + esc((row.origin === 'web' ? 'Trên web' : 'Excel') + ' · ' + row.from_date + ' → ' + row.to_date) + '</td></tr>').join('') + '</tbody></table></div>' : '<p>Chưa tìm thấy lần xác nhận sửa mã nào trong kỳ này. Nếu chị đã sửa trong Excel nhưng chưa tải lên và xác nhận, mở Cách khác: sửa bằng Excel. Có thể đổi khoảng ngày để kiểm tra kỳ khác.</p>') + '</details>';
    const others = data.other_history || [];
    if (others.length) {
      const latest = others[0];
      el('[data-history]').innerHTML += '<details class="card" data-other-history><summary><b>Còn ' + others.length + ' dòng điều chỉnh đã lưu ở kỳ khác</b> · Bấm xem phần đã làm trước đây</summary>' +
        '<p>Lần lưu gần nhất ở kỳ khác: ' + esc(latest.saved_at + ' · ' + latest.actor + ' · Kỳ ' + latest.from_date + ' → ' + latest.to_date) + '. Các dòng dưới đây là lịch sử đã xác nhận, không cần nhập lại cho kỳ hiện tại.</p>' +
        '<div class="table-wrap"><table><thead><tr><th>Đã lưu lúc / Kỳ xử lý</th><th>Mã bị trừ nhầm</th><th>Mặt hàng thực tế đã xuất</th><th>Số lượng sửa</th><th>Người xác nhận / Cách lưu</th></tr></thead><tbody>' + others.map(row => '<tr><td>' + esc(row.saved_at + ' · ' + row.from_date + ' → ' + row.to_date) + '</td><td>' + esc(row.old_code + ' · ' + row.old_name) + '</td><td>' + esc(row.new_code + ' · ' + row.new_name) + '</td><td>' + qty(row.qty) + ' ' + esc(row.unit) + '</td><td>' + esc(row.actor + ' · ' + (row.origin === 'web' ? 'Trên web' : 'Excel')) + '</td></tr>').join('') + '</tbody></table></div></details>';
    }
  }
  function renderList() {
    el('[data-list]').innerHTML = '<div class="table-wrap"><table><thead><tr><th>Mã / tên hàng</th><th>Tồn cuối kỳ</th><th>Xử lý</th></tr></thead><tbody>' +
      data.items.map(item => '<tr><td>' + esc(item.product_code + ' · ' + item.product_name) + '</td><td>' + qty(item.closing_qty) + ' ' + esc(item.unit) + '</td><td><button class="btn btn-primary" data-item="' + esc(item.product_code) + '">Xem nguyên nhân và xử lý</button></td></tr>').join('') +
      (!data.items.length ? '<tr><td colspan="3">Không có hàng âm trong kỳ đã chọn.</td></tr>' : '') + '</tbody></table></div>';
    el('[data-list]').querySelectorAll('[data-item]').forEach(button => button.onclick = () => {
      remember(); activeCode = button.dataset.item; renderEditor(drafts[activeCode]);
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
      (!data.blocked_reason && !item.supplementary_allowed && item.sources.length ? '<form data-edit novalidate><h4>Sửa mã của dòng xuất bị trừ nhầm</h4><p class="stock-save-help"><b>Chưa lưu vào kho.</b> Điền thông tin → bấm <b>1. Kiểm tra trước khi lưu</b> → đối chiếu và bấm <b>2. Lưu và cập nhật kho</b> ở bước tiếp theo.</p>' +
        '<label>Dòng xuất cần sửa<select name="ledger_id">' + item.sources.map(row => '<option value="' + row.ledger_id + '">' + esc(row.date + ' · HĐ ' + row.invoice + ' · ' + row.source_name + ' · ' + qty(row.qty) + ' ' + item.unit) + '</option>').join('') + '</select></label>' +
        '<p>Điền hàng xuất sang vào ô <b>Mặt hàng thực tế đã xuất</b>: chọn đúng hàng đã giao thực tế để sửa mã bị trừ nhầm.</p>' +
        '<label>Mặt hàng thực tế đã xuất<input name="new_code" list="stock-web-products" placeholder="Gõ mã hoặc tên để chọn trong danh mục" autocomplete="off"></label>' +
        '<datalist id="stock-web-products">' + data.catalog.filter(p => p.code !== item.product_code && p.unit.trim().toLocaleLowerCase() === item.unit.trim().toLocaleLowerCase()).map(p => '<option value="' + esc(p.code) + '">' + esc(p.name + ' · Tồn cuối kỳ: ' + qty(p.closing_qty) + ' ' + p.unit) + '</option>').join('') + '</datalist><p data-target></p>' +
        '<label>Số lượng sửa (' + unit + ')<input name="qty" type="number" step="any" min="0" value="' + Math.min(-item.closing_qty, item.sources[0].qty) + '"></label>' +
        '<p>Chỉ sửa phần bị trừ nhầm, tối đa bằng phần còn âm và lượng của dòng xuất đã chọn. Mặt hàng nhận phải đúng hàng thực tế đã xuất, cùng đơn vị tính.</p><div data-edit-issues role="alert"></div><div class="stock-save-actions"><button class="btn btn-primary" type="submit">1. Kiểm tra trước khi lưu</button><span>Kiểm tra xong sẽ hiện bước 2 để lưu. Kho chưa thay đổi.</span></div></form>' :
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
      if (saved) {
        ['ledger_id','new_code','qty'].forEach(key => { if (saved[key] != null) field(key).value = saved[key]; });
        const notice = document.createElement('p');
        notice.textContent = 'Đã giữ phần đang nhập trong tab này, chưa lưu vào kho. Chị tiếp tục điền và bấm 1. Kiểm tra trước khi lưu.';
        el('[data-edit]').prepend(notice);
      }
      const targetInfo = () => {
        const target = data.catalog.find(p => p.code === field('new_code').value.trim());
        el('[data-target]').textContent = target ? target.name + ' · Tồn cuối kỳ: ' + qty(target.closing_qty) + ' ' + target.unit + '. Chưa trừ dự thảo đang giữ; bấm 1. Kiểm tra trước khi lưu để xem lượng có thể dùng.' : '';
      };
      targetInfo(); field('new_code').addEventListener('input', targetInfo);
      field('ledger_id').onchange = () => {
        const source = item.sources.find(r => String(r.ledger_id) === field('ledger_id').value);
        if (source) field('qty').value = Math.min(-item.closing_qty, source.qty);
        invalidate(); remember();
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
    invalidate();
    const entered = values(), missing = [];
    if (!entered.ledger_id) missing.push({field:'ledger_id',message:'Chọn Dòng xuất cần sửa trước khi lưu.'});
    if (!entered.new_code) missing.push({field:'new_code',message:'Chưa chọn Mặt hàng thực tế đã xuất. Gõ mã hoặc tên và chọn một mặt hàng trong danh mục.'});
    if (!Number.isFinite(Number(entered.qty)) || Number(entered.qty) <= 0) missing.push({field:'qty',message:'Số lượng sửa phải lớn hơn 0. Nhập số lượng thực tế cần sửa rồi kiểm tra lại.'});
    if (missing.length) { issues(missing); focus(missing[0].field); return; }
    let nextField = null;
    working(true); el('[data-status]').textContent = 'Đang kiểm tra trước khi lưu. Kho chưa thay đổi…';
    try {
      preview = await api('/api/inventory/output-remap/web-preview', post({from,to,version:data.version,product_code:activeCode,...values()}));
      renderAvailability(preview.availability);
      issues(preview.issues);
      if (!preview.can_confirm) { nextField = preview.issues[0]?.field; el('[data-status]').textContent = 'Chưa lưu vào kho. Xem hướng dẫn xử lý ngay dưới thông báo; thông tin đang nhập được giữ lại.'; return; }
      const c = preview.changes[0];
      el('[data-preview]').innerHTML = '<section class="card"><h3>Bước 2 · Đối chiếu và lưu vào kho</h3><p><b>Kiểm tra hợp lệ, chưa lưu.</b> Điền Người xác nhận, tích ô đã đối chiếu rồi bấm <b>2. Lưu và cập nhật kho</b>.</p><p>Chuyển ' + qty(c.qty) + ' ' + esc(c.unit) + ' từ mã bị trừ nhầm sang mặt hàng thực tế đã xuất.</p>' +
        '<table><thead><tr><th>Mặt hàng</th><th>Tồn cuối kỳ sau khi sửa</th></tr></thead><tbody><tr><td>' + esc(c.old_code + ' · ' + c.old_name) + '</td><td>' + qty(c.old_closing_after) + ' ' + esc(c.old_unit) + '</td></tr><tr><td>' + esc(c.new_code + ' · ' + c.new_name) + '</td><td>' + qty(c.new_closing_after) + ' ' + esc(c.unit) + '</td></tr></tbody></table>' +
        '<p>Thông tin trên hóa đơn đã ký giữ nguyên. Thay đổi này chỉ sửa mã hàng trừ kho nội bộ.</p>' +
        '<form data-confirm-form novalidate><label>Người xác nhận<input name="actor" maxlength="100" autocomplete="name"></label>' +
        '<label><input name="confirmed" type="checkbox"> Tôi đã đối chiếu đúng mặt hàng thực tế đã xuất và số lượng sửa.</label>' +
        '<div data-confirm-issues role="alert"></div><p>Tích ô đã đối chiếu để bật nút 2. Lưu và cập nhật kho.</p><button class="btn btn-primary" data-confirm disabled>2. Lưu và cập nhật kho</button></form></section>';
      el('[data-status]').textContent = 'Kiểm tra tồn sau khi sửa rồi xác nhận ở dưới.';
      el('[data-confirm-form]').onsubmit = confirm;
      field('confirmed').onchange = () => { el('[data-confirm]').disabled = !field('confirmed').checked; };
      el('[data-preview]').scrollIntoView({block:'start'});
    } catch (error) { el('[data-status]').textContent = 'Chưa ghi nhận.'; issues([{field:'reload',message:error.message}]); }
    finally { working(false); if (nextField) focus(nextField); }
  }
  async function confirm(event) {
    event.preventDefault(); if (busy || !preview || !field('confirmed').checked) return;
    const actor = field('actor').value.trim();
    if (!actor) { issues([{field:'actor', message:'Điền Người xác nhận trước khi cập nhật kho.'}]); focus('actor'); return; }
    working(true);
    try {
      await api('/api/inventory/output-remap/confirm', post({token:preview.token, actor, confirmed:true}));
      delete drafts[activeCode]; persistDrafts();
      invalidate(); el('[data-editor]').innerHTML = '';
      el('[data-status]').textContent = 'Đã lưu và cập nhật kho. Chị có thể xem lại trong Điều chỉnh đã lưu; không cần nhập lại lần sửa này.';
      await options.onApplied(); await load(false, true);
      el('[data-status]').scrollIntoView({block:'center'});
    } catch (error) { issues([{field:'reload', message:error.message}]); }
    finally { working(false); }
  }
  async function load(preserve = true, afterSave = false) {
    if (busy && !afterSave) return;
    if (preserve) remember();
    const saved = preserve ? drafts[activeCode] : null;
    working(true);
    try {
      const result = await api('/api/inventory/output-remap/shortages?' + new URLSearchParams({from,to}));
      if (!dialog.isConnected) return;
      data = result; renderHistory(); renderList(); renderEditor(saved);
      if (!afterSave) el('[data-status]').textContent = data.items.length + ' mặt hàng còn âm. Cập nhật số liệu không thay đổi kho.';
    } catch (error) { issues([{field:/Từ ngày|Đến ngày|ngày đầu|ngày cuối/.test(error.message) ? 'dates' : 'reload',message:error.message}]); }
    finally { working(false); }
  }
  el('[data-close]').onclick = () => { if (!busy) dialog.close(); };
  el('[data-reload]').onclick = () => load(true);
  el('[data-excel]').onclick = () => options.onExcel(() => load(true));
  dialog.addEventListener('input', event => { if (event.target.matches('[name=ledger_id],[name=new_code],[name=qty]')) { invalidate(); remember(); } });
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  dialog.addEventListener('close', () => { remember(); dialog.remove(); });
  load();
};
