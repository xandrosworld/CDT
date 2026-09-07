/* Edit saved mappings while keeping the original invoice and stock untouched. */
(function () {
  'use strict';
  window.TdpInvoiceReviewEditor = async function (initial, context) {
    const {api, esc, quantity, money, dateVN, changed} = context;
    if (document.querySelector('.invoice-review-dialog')) return;
    const dialog = document.createElement('dialog');
    dialog.className = 'inventory-totals-dialog invoice-receipt-summary-dialog invoice-review-dialog';
    dialog.setAttribute('aria-label', 'Kiểm tra lượng & tiền');
    dialog.innerHTML = '<div class="inventory-totals-heading"><div><h3>Kiểm tra lượng & tiền</h3><p>' +
      esc(initial.invoice_series + ' / ' + initial.invoice_number) + ' · ' + dateVN(initial.invoice_date) +
      '</p></div><button type="button" class="icon-button review-close" aria-label="Đóng kiểm tra">×</button></div>' +
      '<div class="review-toolbar"><button type="button" class="btn btn-outline review-group" disabled>Gộp 0 dòng đã chọn</button>' +
      '<span class="review-status" role="status">Đang tải đủ các dòng…</span></div>' +
      '<p class="review-error" role="alert"></p><div class="review-content"></div>' +
      '<p class="code-note review-footer">Lưu từng dòng hoặc Lưu và gộp để cập nhật. Khớp xong các hóa đơn rồi dùng nút Nhập kho chung trên bảng.</p>';
    document.body.appendChild(dialog); dialog.showModal();
    const find = s => dialog.querySelector(s);
    let invoice = initial, lines = [], warnings = [], groups = new Map(), drafts = new Map(), busy = false, revision = 0;
    const selected = new Set();
    const editable = () => invoice.sync_status === 'synced' && !invoice.error_message && !['posted','blocked','reversed'].includes(invoice.receipt_status);
    const snapshot = line => Object.fromEntries(['product_code','mapping_status','conversion_factor','source_unit','qty','amount'].map(k => [k,line[k]]));
    const error = message => { find('.review-error').textContent = message; };
    const lineFor = id => lines.find(r => String(r.id) === String(id));
    const rowFor = id => find('[data-review-line="' + id + '"]');
    function draftFor(line) {
      if (!drafts.has(line.id)) drafts.set(line.id, {
        code: line.product_code || '', product: line.product_code ? {code:line.product_code,name:line.product_name,unit:line.product_unit} : null,
        factor: line.mapping_status === 'mapped' ? String(line.conversion_factor) : '',
        factorProduct: line.product_code || '', manual: false, expected:snapshot(line)
      });
      return drafts.get(line.id);
    }
    function groupButton() {
      const button = find('.review-group');
      button.textContent = 'Gộp ' + selected.size + ' dòng đã chọn';
      button.disabled = busy || !editable() || selected.size < 2 || selected.size > 100;
    }
    function lock(value) {
      busy = value;
      dialog.querySelectorAll('input,button').forEach(e => { e.disabled = value; });
      groupButton();
    }
    function conversion(row, line, draft) {
      const factor = Number(String(draft.factor).trim().replace(',', '.'));
      row.querySelector('.review-unit').textContent = draft.product ? draft.product.unit : 'đơn vị kho';
      row.querySelector('.review-product-label').textContent = draft.product ? draft.product.name : '';
      row.querySelector('.review-converted').textContent = draft.product && Number.isFinite(factor) && factor > 0
        ? quantity(line.qty * factor) + ' ' + draft.product.unit : 'Chọn mã và nhập hệ số quy đổi';
    }
    function render() {
      ++revision;
      const allowed = editable(), summary = invoice.receipt_summary || {items:[],pending_lines:0};
      find('.review-content').innerHTML = (!allowed ? '<p class="warning-summary">' + esc(invoice.error_message || 'Hóa đơn đã ghi kho hoặc nguồn cần kiểm tra. Chỉ xem các dòng và tổng đã lưu.') + '</p>' : '') +
        warnings.map(g=>'<p class="warning-summary">' + esc(g.message) + (allowed ? ' <button type="button" class="btn btn-small btn-outline review-split" data-group="' + g.id + '">Bỏ nhóm cũ</button>' : '') + '</p>').join('') +
        '<p class="review-caption">Đủ ' + lines.length + ' dòng gốc · Tổng tiền dòng chưa thuế: <strong>' + money(lines.reduce((sum,r)=>sum+Number(r.amount || 0),0)) + '</strong></p>' +
        '<div class="review-lines-scroll"><table class="review-lines"><thead><tr><th>Chọn</th><th>Dòng / Tên hàng</th><th>Lượng nguồn</th><th>Đơn giá</th><th>Tiền chưa thuế</th><th>Mã hàng / Quy đổi</th></tr></thead><tbody>' + lines.map(line => {
          const group = groups.get(line.id), canEdit = allowed && line.inventory_eligible && !line.is_expense && !group;
          const issue = line.issue || '';
          const draft = drafts.get(line.id);
          const product = draft ? draft.product : line.product_code ? {code:line.product_code,name:line.product_name,unit:line.product_unit} : null;
          const code = draft ? draft.code : line.product_code || '';
          const factor = draft ? draft.factor : line.mapping_status === 'mapped' ? line.conversion_factor : '';
          const editor = canEdit ? '<div class="review-editor"><input class="review-code" autocomplete="off" placeholder="Tìm mã / tên" aria-label="Mã kho dòng ' + line.line_index + '" value="' + esc(code) + '">' +
            '<div class="review-results" aria-live="polite" hidden></div><small class="review-product-label">' + esc(product ? product.name : '') + '</small>' +
            '<div class="review-factor-controls"><label>1 ' + esc(line.source_unit) + ' = <input class="review-factor" inputmode="decimal" placeholder="Quy đổi" aria-label="Hệ số quy đổi dòng ' + line.line_index + '" value="' + esc(factor) + '"> <span class="review-unit">' + esc(product ? product.unit : 'đơn vị kho') + '</span></label>' +
            '<button type="button" class="btn btn-small btn-outline review-save">Lưu</button><button type="button" class="btn btn-small btn-outline review-reset"' + (!draft ? ' hidden' : '') + '>Bỏ sửa</button></div>' +
            '<small class="review-converted">' + (line.mapping_status === 'mapped' ? quantity(line.stock_qty) + ' ' + esc(line.product_unit) : 'Chọn mã và nhập hệ số quy đổi') + '</small></div>' :
            line.is_expense ? '<span>Chi phí · không nhập kho</span>' : '<strong>' + esc(line.product_code || '—') + '</strong><div>' + esc(line.product_name || '') + '</div>' +
            (line.mapping_status === 'mapped' ? '<small>' + quantity(line.stock_qty) + ' ' + esc(line.product_unit) + '</small>' : '') +
            (group ? '<div class="review-group-info">Nhóm dòng ' + esc(group.line_index) + (allowed ? ' <button type="button" class="btn btn-small btn-outline review-split" data-group="' + group.group_id + '">Tách nhóm</button>' : '') + '</div>' : !line.inventory_eligible ? '<small>Không nhập kho</small>' : '');
          return '<tr data-review-line="' + line.id + '" class="' + (issue ? 'invoice-row-issue' : '') + '"><td>' + (canEdit ? '<input type="checkbox" class="review-select" aria-label="Chọn dòng ' + line.line_index + ' để gộp"' + (selected.has(line.id) ? ' checked' : '') + '>' : '—') +
            '</td><td><strong>Dòng ' + line.line_index + '</strong><div>' + esc(line.source_item_name) + '</div><small>' + esc(line.source_item_code || '') + '</small>' + (issue ? '<div class="invoice-issue-text">' + esc(issue) + '</div>' : '') + '</td><td class="num-cell">' + quantity(line.qty) + ' ' + esc(line.source_unit) +
            '</td><td class="num-cell">' + money(line.unit_price) + '</td><td class="num-cell">' + money(line.amount) + '</td><td>' + editor + '</td></tr>';
        }).join('') + '</tbody></table></div>' +
        '<h4 class="review-caption">Tổng nhập theo mã đã lưu</h4>' + (summary.pending_lines ? '<p class="warning-summary">Còn ' + summary.pending_lines + ' dòng chưa đủ mã/quy đổi. Tổng dưới đây chưa gồm các dòng này.</p>' : '') +
        '<div class="review-summary-scroll"><table class="review-summary"><thead><tr><th>Mã / Tên hàng</th><th>ĐVT</th><th>Tổng lượng nhập</th><th>Lượng hàng 0đ</th><th>Tiền chưa thuế</th><th>Giá nhập bình quân</th></tr></thead><tbody>' + summary.items.map(r =>
          '<tr><td><strong>' + esc(r.product_code) + '</strong><div>' + esc(r.product_name) + '</div></td><td>' + esc(r.unit) + '</td><td>' + quantity(r.qty) + '</td><td>' + quantity(r.zero_amount_qty) + '</td><td>' + money(r.amount) + '</td><td>' + money(r.average_unit_cost) + '</td></tr>'
        ).join('') + (!summary.items.length ? '<tr><td colspan="6">Chưa có dòng đủ mã và quy đổi để cộng.</td></tr>' : '') + '</tbody></table></div>';
      drafts.forEach((draft,id) => { const row=rowFor(id); if(row?.querySelector('.review-editor')) conversion(row,lineFor(id),draft); });
      groupButton();
    }
    async function reload(message) {
      const date = encodeURIComponent(initial.invoice_date);
      const data = await api('/api/invoice-workbench/invoices?invoice_type=input&from=' + date + '&to=' + date + '&status=all&line_filter=all');
      if (!dialog.isConnected) return;
      const fresh = (data.items || []).find(r => r.id === initial.id);
      if (!fresh) throw Error('Không còn tìm thấy hóa đơn trong ngày này. Đóng và tải lại bảng để kiểm tra.');
      invoice = fresh;
      const all = new Map((data.lines || []).filter(r=>r.invoice_id===invoice.id).map(r=>[r.id,r]));
      warnings = (data.group_warnings || []).filter(g=>g.invoice_id===invoice.id);
      groups = new Map();
      all.forEach(r => { if(r.group_id) r.group_members.forEach(member=>groups.set(member.id,r)); });
      lines = invoice.items.map(r => ({...r,issue:groups.has(r.id) ? groups.get(r.id).issue : all.get(r.id)?.issue || ''}));
      selected.forEach(id => { const r=lineFor(id); if(!r || groups.has(id) || !r.inventory_eligible || r.is_expense) selected.delete(id); });
      render();
      find('.review-status').textContent = message || 'Sửa mã, quy đổi hoặc chọn các dòng để gộp.';
    }
    async function refreshSaved(message) {
      try { await reload(message); await changed(); }
      catch(e) { throw Error('Đã lưu thay đổi nhưng chưa tải lại được. Đóng và mở lại Kiểm tra để xem dữ liệu mới. ' + e.message); }
    }
    function close() {
      if (busy) return;
      if (drafts.size && !window.confirm('Còn dòng đang sửa chưa lưu. Bỏ phần chưa lưu và đóng? Các dòng đã Lưu vẫn được giữ.')) return;
      dialog.close();
    }
    find('.review-close').onclick = close;
    dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
    dialog.addEventListener('close',()=>{++revision;dialog.remove();});
    dialog.addEventListener('change',e=>{
      if (!e.target.matches('.review-select') || busy) return;
      const id=Number(e.target.closest('[data-review-line]').dataset.reviewLine);
      if(e.target.checked)selected.add(id);else selected.delete(id);
      groupButton();
    });
    dialog.addEventListener('input',async e=>{
      if (!e.target.matches('.review-code,.review-factor') || busy) return;
      const row=e.target.closest('[data-review-line]'),line=lineFor(row.dataset.reviewLine),draft=draftFor(line);
      row.querySelector('.review-reset').hidden=false;
      if(e.target.matches('.review-factor')) {
        draft.factor=e.target.value;draft.manual=true;conversion(row,line,draft);return;
      }
      draft.code=e.target.value;draft.product=null;
      const results=row.querySelector('.review-results'),version=++revision,term=draft.code.trim();
      conversion(row,line,draft);
      results.hidden=false;results.textContent=term.length<2?'Nhập ít nhất 2 ký tự.':'Đang tìm mã hàng…';
      if(term.length<2)return;
      try {
        const result=await api('/api/products/search?q='+encodeURIComponent(term));
        if(version!==revision || !row.isConnected)return;
        results.innerHTML=(result.items || []).map((p,i)=>'<button type="button" class="btn btn-small btn-outline" data-review-product="'+i+'">'+esc(p.code+' · '+p.name+' · '+p.unit)+'</button>').join('') || 'Không tìm thấy mã hàng.';
        results.querySelectorAll('button').forEach(button=>button.onclick=()=>{
          const p=result.items[Number(button.dataset.reviewProduct)];
          const keep=draft.manual && (!draft.factorProduct || draft.factorProduct===p.code);
          const same=String(line.source_unit||'').trim().toLowerCase()===String(p.unit||'').trim().toLowerCase();
          if(!keep) {draft.factor=line.product_code===p.code && line.mapping_status==='mapped'?String(line.conversion_factor):same?'1':'';draft.manual=false;}
          draft.product=p;draft.code=p.code;draft.factorProduct=p.code;
          row.querySelector('.review-code').value=p.code;row.querySelector('.review-factor').value=draft.factor;
          results.hidden=true;conversion(row,line,draft);row.querySelector('.review-factor').focus();
        });
      }catch(e){if(version===revision && row.isConnected)results.textContent=e.message;}
    });
    dialog.addEventListener('keydown',e=>{
      const row=e.target.closest('[data-review-line]');
      if(!row)return;
      if(e.key==='Escape' && e.target.matches('input')) {
        const results=row.querySelector('.review-results');
        if(results && !results.hidden){e.preventDefault();e.stopPropagation();++revision;results.hidden=true;return;}
        if(drafts.has(Number(row.dataset.reviewLine))){e.preventDefault();e.stopPropagation();drafts.delete(Number(row.dataset.reviewLine));render();rowFor(row.dataset.reviewLine)?.querySelector('.review-code')?.focus();}
      }
      if(e.key==='Enter' && e.target.matches('.review-factor')){e.preventDefault();row.querySelector('.review-save').click();}
      if(e.key==='Enter' && e.target.matches('.review-code')) {
        e.preventDefault();
        const results=row.querySelector('.review-results');
        if(!results.hidden)results.querySelector('button')?.focus();else row.querySelector('.review-factor').focus();
      }
    });
    dialog.addEventListener('click',async e=>{
      const button=e.target.closest('button');
      if(!button || busy)return;
      const row=button.closest('[data-review-line]'),line=row && lineFor(row.dataset.reviewLine);
      if(button.matches('.review-reset')){drafts.delete(line.id);render();rowFor(line.id).querySelector('.review-code').focus();return;}
      if(!button.matches('.review-save,.review-group,.review-split'))return;
      error('');
      if(!editable()){error('Hóa đơn không còn cho phép chỉnh sửa.');return;}
      if(!button.matches('.review-save') && drafts.size){error('Lưu hoặc Bỏ sửa các dòng đang sửa trước khi gộp/tách nhóm.');return;}
      lock(true);
      try {
        if(button.matches('.review-save')) {
          const draft=draftFor(line),factor=Number(String(draft.factor).trim().replace(',','.'));
          if(!draft.product || draft.code.trim()!==draft.product.code)throw Error('Chọn mã hàng trong danh sách gợi ý trước khi lưu.');
          if(!Number.isFinite(factor) || factor<=0 || factor>1000000000)throw Error('Hệ số quy đổi phải lớn hơn 0 và không quá 1.000.000.000.');
          const endpoint=draft.product.code===draft.expected.product_code?'conversion':'mapping';
          await api('/api/invoice-workbench/items/input/'+line.id+'/'+endpoint,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_code:draft.product.code,conversion_factor:factor,expected:draft.expected})});
          drafts.delete(line.id);
          await refreshSaved('Đã lưu dòng '+line.line_index+'. Tổng nhập đã cập nhật; chưa nhập kho.');
          rowFor(line.id)?.querySelector('.review-code')?.focus();
        } else if(button.matches('.review-split')) {
          await api('/api/invoice-workbench/input-groups/'+button.dataset.group+'/split',{method:'POST'});
          await refreshSaved('Đã tách nhóm. Có thể sửa mã/quy đổi từng dòng hoặc chọn gộp lại.');
        } else {
          await window.TdpInvoiceGroupEditor(Array.from(selected),{api,esc,quantity,money,saved:async()=>{
            lock(true);
            try { selected.clear();await refreshSaved('Đã gộp các dòng đã chọn. Chưa nhập kho.'); }
            catch(e){error('Đã lưu nhóm nhưng chưa tải lại được: '+e.message);}
            finally{lock(false);}
          }});
        }
      }catch(e){error(e.message);}
      finally{lock(false);}
    });
    lock(true);
    try{await reload();}catch(e){error(e.message);find('.review-status').textContent='Chưa tải được chi tiết. Đóng và mở lại để thử lại.';}
    finally{lock(false);find('.review-close').focus();}
  };
}());
