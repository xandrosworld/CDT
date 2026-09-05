/* One date-scoped table; row order and totals come from the same source as Excel. */
(function () {
  "use strict";
  window.TdpInvoiceWorkbench = function (state, format) {
    var esc = format.esc, num = format.num, money = format.money, dateVN = format.dateVN;
    var data = state.invoiceListing || {}, direction = state.invoiceDirection;
    var input = direction === "input", invoices = {}, totals = data.totals || {};
    (data.items || []).forEach(function (invoice) { invoices[invoice.id] = invoice; });
    var statusLabels = data.status_labels || {all:"Tất cả hóa đơn",needs_mapping:"Chưa ghép đủ mã / đơn vị",ready:"Sẵn sàng ghi kho",posted:"Đã ghi kho",error:"Cần kiểm tra",reversed:"Đã hoàn tác kho",not_inventory:"Không ghi kho"};
    var lineLabels = data.line_labels || {all:"Tất cả dòng",needs_attention:"Dòng cần xử lý",unmapped:"Chưa ghép mã",unit_review:"Cần quy đổi đơn vị",error:"Lỗi / bất thường",mapped:"Đã ghép mã"};
    function options(labels, selected) {
      return Object.keys(labels).map(function (value) {
        return '<option value="' + esc(value) + '"' + (value === selected ? ' selected' : '') + '>' + esc(labels[value]) + '</option>';
      }).join('');
    }
    function button(action, id, label, style) {
      return '<button type="button" class="btn btn-small ' + (style || 'btn-outline') + '" data-action="' + action + '" data-direction="' + direction + '" data-id="' + id + '">' + label + '</button>';
    }
    function mapping(item, invoice) {
      if (!item.id) return esc(item.issue);
      if (!item.inventory_eligible) return '<span class="muted">Không ghi kho · ' + esc(item.validation_note || 'Dịch vụ / điều chỉnh') + '</span>';
      if (item.mapping_status === 'mapped') return '<strong>' + esc(item.product_code) + '</strong><div>' + esc(item.product_name || '') + '</div><small>Lượng kho: ' + num(item.stock_qty == null ? item.qty : item.stock_qty) + ' ' + esc(item.product_unit || item.source_unit) + '</small>';
      // Posted or unsafe source records are immutable until the source is checked.
      if (invoice.sync_status !== 'synced' || invoice.receipt_status === 'posted' || ['posted','reversed','reversal_required'].indexOf(invoice.stock_status) >= 0 || (!input && invoice.source_status_class !== 'issued')) {
        return '<span class="tag tag-red">Cần kiểm tra nguồn hóa đơn</span>';
      }
      if (item.mapping_status === 'unit_review') return '<strong>' + esc(item.product_code) + '</strong><div class="unit-conversion-editor">1 ' + esc(item.source_unit || 'đơn vị nguồn') + ' = <input class="input-date unit-conversion-input" id="conversion_' + direction + '_' + item.id + '" type="number" min="0.000001" step="any" aria-label="Hệ số quy đổi dòng ' + item.line_index + '" data-direction="' + direction + '" data-id="' + item.id + '">' + esc(item.product_unit || 'đơn vị kho') + button('save-invoice-conversion', item.id, 'Lưu quy đổi') + '</div>';
      var candidates = item.candidate_products || [];
      var editor = candidates.length > 1 ? '<select class="input-date invoice-mapping-input" data-direction="' + direction + '" id="map_' + direction + '_' + item.id + '"><option value="">Chọn đúng mã hàng</option>' + candidates.map(function (p) { return '<option value="' + esc(p.code) + '">' + esc(p.code + ' · ' + p.name) + '</option>'; }).join('') + '</select>' :
        '<input class="input-date invoice-mapping-input" list="msmiProductOptions" data-direction="' + direction + '" data-source-name="' + esc(item.source_item_name) + '" id="map_' + direction + '_' + item.id + '" value="' + esc(item.suggested_product_code || '') + '" placeholder="Gõ mã rồi Enter" aria-label="Mã kho dòng ' + item.line_index + '">';
      return '<div class="compact-controls">' + editor + button('save-invoice-mapping', item.id, 'Ghi nhớ') + '</div>';
    }
    function actions(invoice) {
      var result = '<span class="tag">' + esc(statusLabels[invoice.workbench_status] || 'Cần kiểm tra') + '</span>';
      if (!input) result += '<small>' + esc({issued:'Đã phát hành hợp lệ',draft:'Nháp/chờ ký',unknown:'Chưa rõ trạng thái',cancelled:'Đã hủy · cần đối chiếu',replaced:'Đã thay thế · cần đối chiếu',adjusted:'Điều chỉnh · cần đối chiếu'}[invoice.source_status_class] || 'Chưa rõ trạng thái') + '</small>';
      var suggestions = input && invoice.workbench_status === 'needs_mapping' ? (invoice.items || []).filter(function (item) { return item.inventory_eligible && item.mapping_status !== 'mapped' && item.suggested_product_code; }).length : 0;
      if (suggestions) result += '<button class="btn btn-small btn-outline" data-action="apply-msmi-suggestions" data-id="' + invoice.id + '" data-count="' + suggestions + '">Xác nhận ' + suggestions + ' mã gợi ý</button>';
      if (invoice.workbench_status === 'ready') result += button(input ? 'create-msmi-receipt' : 'post-invoice-output', invoice.id, input ? 'Xác nhận nhập cả hóa đơn' : 'Xác nhận xuất cả hóa đơn', 'btn-primary');
      if (invoice.stock_status === 'reversal_required') result += button('reverse-invoice-output', invoice.id, 'Xác nhận hoàn tác xuất kho', 'btn-danger');
      if (invoice.receipt_status === 'posted' || ['posted','reversed','reversal_required'].indexOf(invoice.stock_status) >= 0) result += button('view-invoice-stock', invoice.id, 'Xem hàng đã ghi kho');
      return result;
    }
    var rows = (data.lines || []).map(function (item) {
      var invoice = invoices[item.invoice_id];
      return '<tr id="invoice-line-' + direction + '-' + (item.id || 'empty-' + invoice.id) + '" data-issue="' + (item.issue ? '1' : '0') + '" class="' + (item.issue ? 'invoice-row-issue' : '') + '"><td><strong>' + esc(invoice.invoice_series + ' / ' + invoice.invoice_number) + '</strong><div>' + dateVN(invoice.invoice_date) + '</div><small>' + esc(invoice.seller_name || invoice.buyer_name || '') + '</small></td><td>' + esc(item.line_index || '—') + '</td><td>' + esc(item.source_item_code || '—') + '</td><td>' + esc(item.source_item_name) + (item.issue ? '<div class="invoice-issue-text">' + esc(item.issue) + '</div>' : '') + '</td><td class="num-cell">' + num(item.qty) + ' ' + esc(item.source_unit || '') + '</td><td class="num-cell">' + money(item.amount) + '</td><td>' + mapping(item, invoice) + '</td><td><div class="invoice-row-actions">' + actions(invoice) + '</div></td></tr>';
    }).join('');
    var batchLabels = {prepared:'Đã chuẩn bị', syncing:'Đang tải', needs_mapping:'Chưa ghép mã',ready:'Sẵn sàng',posted:'Đã ghi kho',partial:'Còn phần cần xử lý',error:'Lỗi tải',quarantined:'Cần kiểm tra'};
    var batches = ((state.invoiceWorkbench || {}).batches || []).map(function (batch) {
      return '<tr><td>' + batch.id + '</td><td>' + dateVN(batch.date_from) + ' → ' + dateVN(batch.date_to) + '</td><td>' + esc(batchLabels[batch.status] || batch.status) + (batch.error_code ? ' · hãy kiểm tra và tải tiếp' : '') + '</td><td>' + num(batch.fetched_count) + '</td><td>' + (input && batch.fetched_count ? '<a href="/api/invoice-workbench/batches/' + batch.id + '/export-input-xlsx" class="btn btn-small btn-outline">Excel cả lần tải</a>' : '—') + '</td></tr>';
    }).join('');
    var qty = Object.keys(totals.qty_by_unit || {}).map(function (unit) { return num(totals.qty_by_unit[unit]) + ' ' + esc(unit); }).join(' · ') || '0';
    var query = '?invoice_type=' + direction + '&from=' + encodeURIComponent(state.invoiceFrom) + '&to=' + encodeURIComponent(state.invoiceTo) + '&status=' + encodeURIComponent(state.invoiceStatus) + '&line_filter=' + encodeURIComponent(state.invoiceLineFilter);
    var error = data.error || (state.invoiceWorkbench || {}).error;
    var dateRepair = data.date_repair || {};
    var dateRepairHtml = input && dateRepair.corrected_count ? '<div class="code-note">Đã cập nhật ngày Việt Nam từ nguồn cho ' + num(dateRepair.corrected_count) + ' hóa đơn liên quan kỳ này; giữ nguyên số tiền và ghép mã.</div>' : '';
    if (input && dateRepair.blocked_count) {
      dateRepairHtml += '<div class="warning-summary"><strong>Còn ' + num(dateRepair.blocked_count) + ' hóa đơn cần đối chiếu ngày.</strong> Các hóa đơn này có thể nằm ngoài bộ lọc theo ngày đang lưu. Sổ kho được giữ nguyên; cần kiểm tra trước khi tiếp tục ghi kho.<details><summary>Xem hóa đơn và ngày cần đối chiếu</summary><div class="table-wrap"><table><thead><tr><th>Hóa đơn / Bên bán</th><th>Ngày đang lưu</th><th>Ngày nguồn Việt Nam</th><th>Lý do</th></tr></thead><tbody>' + (dateRepair.items || []).map(function (item) {
        return '<tr><td>' + esc(item.invoice_series + ' / ' + item.invoice_number) + '<div>' + esc(item.seller_name) + '</div></td><td>' + dateVN(item.old_date) + '</td><td>' + dateVN(item.new_date) + '</td><td>' + esc(item.reason) + '</td></tr>';
      }).join('') + '</tbody></table></div></details></div>';
    }
    return '<div class="invoice-workbench"><div class="invoice-direction-tabs" role="tablist" aria-label="Loại hóa đơn">' + ['input','output'].map(function (d) {
      return '<button role="tab" aria-selected="' + (direction === d) + '" class="' + (direction === d ? 'active' : '') + '" data-action="set-invoice-direction" data-direction="' + d + '">Hóa đơn ' + (d === 'input' ? 'đầu vào' : 'đầu ra') + '</button>';
    }).join('') + '</div><div class="invoice-filter-grid"><div class="form-field"><label for="invoiceFrom">Từ ngày</label><input id="invoiceFrom" type="date" value="' + esc(state.invoiceFrom) + '"></div><div class="form-field"><label for="invoiceTo">Đến ngày</label><input id="invoiceTo" type="date" value="' + esc(state.invoiceTo) + '"></div><div class="form-field"><label for="invoiceStatus">Trạng thái hóa đơn</label><select id="invoiceStatus">' + options(statusLabels, state.invoiceStatus) + '</select></div><div class="form-field"><label for="invoiceLineFilter">Lọc dòng hàng</label><select id="invoiceLineFilter">' + options(lineLabels, state.invoiceLineFilter) + '</select></div><button class="btn btn-primary" data-action="prepare-invoice-sync">Tải/tiếp tục ' + (input ? 'đầu vào' : 'đầu ra') + '</button></div></div>' +
      (error ? '<div class="error-summary">' + esc(error) + '</div>' : '') +
      dateRepairHtml +
      (state.invoiceLastPosted && state.invoiceLastPosted.direction === direction ? '<div class="code-note invoice-post-result">Hóa đơn vừa xác nhận đã ghi kho. ' + button('view-invoice-stock', state.invoiceLastPosted.id, 'Xem hàng vừa ghi kho') + '</div>' : '') +
      '<div class="card invoice-lines-card"><div class="card-head"><div><h3>Hóa đơn trong khoảng ngày đã chọn</h3><p id="invoice-list-count">Đang xem ' + num(totals.invoice_count) + ' / ' + num((data.counts || {}).all) + ' hóa đơn · ' + num(totals.line_count) + ' dòng hàng · ' + num(totals.issue_count) + ' dòng cần xử lý</p></div><div class="compact-controls"><button class="btn btn-outline" data-action="jump-invoice-issue"' + (!totals.issue_count ? ' disabled' : '') + '>Đến dòng cần sửa đầu tiên</button>' + (!error ? '<a class="btn btn-outline" href="/api/invoice-workbench/invoices/export' + query + '">Excel đúng bộ lọc</a>' : '') + '</div></div>' +
      '<div class="code-note">Dòng cần xử lý nằm trên cùng. Nhấn Tab để chuyển ô, Enter để lưu mã hoặc quy đổi. Đổi bộ lọc chỉ xem dữ liệu đã tải, không gọi nguồn hóa đơn và không ghi kho.</div>' +
      '<div class="table-wrap invoice-lines-scroll"><table><thead><tr><th>Hóa đơn / Đối tác</th><th>Dòng</th><th>Mã nguồn</th><th>Tên hàng / Cần xử lý</th><th>Số lượng nguồn</th><th>Tiền dòng<br>(chưa thuế)</th><th>Ghép mã / Quy đổi</th><th>Thao tác cả hóa đơn</th></tr></thead><tbody>' + (rows || '<tr><td colspan="8" class="empty">' + (error ? 'Chưa đọc được dữ liệu. Kiểm tra thông báo phía trên.' : (data.counts || {}).all ? 'Không có dòng phù hợp. Chọn Tất cả hóa đơn / Tất cả dòng để xem lại.' : 'Không có hóa đơn đã tải trong khoảng ngày này. Chọn đúng ngày hoặc bấm Tải/tiếp tục.') + '</td></tr>') + '</tbody><tfoot><tr class="table-total-row"><td colspan="4">TỔNG CÁC DÒNG ĐANG LỌC</td><td>' + qty + '</td><td class="num-cell">' + money(totals.line_amount) + '</td><td colspan="2">Lượng cộng riêng theo từng đơn vị</td></tr></tfoot></table></div>' +
      '<div class="code-note invoice-total-note"><strong>Tổng thanh toán các hóa đơn có dòng đang lọc: ' + money(totals.invoice_amount) + '</strong> (mỗi hóa đơn tính một lần, gồm thuế; khác với tổng tiền dòng khi lọc bớt hàng).</div></div>' +
      '<div class="code-note">Chỉ tải dữ liệu về; không ký, phát hành, sửa hoặc hủy hóa đơn trên mSMI/M-Invoice. Phải ghép đủ mã, đơn vị và xác nhận mới ghi kho hóa đơn. Hóa đơn đầu ra không hợp lệ bị chặn để đối chiếu.</div>' +
      '<details class="card invoice-batch-card"><summary>Lịch sử các lần tải liên quan (' + num(((state.invoiceWorkbench || {}).batches || []).length) + ' lần gần nhất)</summary><div class="table-wrap invoice-lines-scroll"><table><thead><tr><th>Lần tải</th><th>Khoảng ngày của lần tải</th><th>Trạng thái lần tải</th><th>Số HĐ trong lần tải</th><th>Excel</th></tr></thead><tbody>' + (batches || '<tr><td colspan="5">Chưa có lần tải liên quan.</td></tr>') + '</tbody></table></div><div class="code-note">Các lần tải có thể trùng hóa đơn. Không cộng số lượng giữa các lần tải; bảng phía trên đã loại trùng.</div></details><datalist id="msmiProductOptions"></datalist>';
  };
}());
