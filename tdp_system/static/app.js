(function () {
  "use strict";

  function currentWorkDate() {
    var parts = {};
    new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).forEach(function(part) { parts[part.type] = part.value; });
    return parts.year + '-' + parts.month + '-' + parts.day;
  }
  var todayIso = currentWorkDate();
  var storedInvoiceFilters = {};
  var storedPayableFilters = {};
  var storedReceivableFilters = {};
  try {
    storedInvoiceFilters = JSON.parse(window.localStorage.getItem("tdp.invoiceWorkbenchFilters") || "{}");
  } catch (ignore) {
    storedInvoiceFilters = {};
  }
  try {
    storedPayableFilters = JSON.parse(window.localStorage.getItem("tdp.payableFilters") || "{}");
  } catch (ignore) {
    storedPayableFilters = {};
  }
  try {
    storedReceivableFilters = JSON.parse(window.localStorage.getItem("tdp.receivableFilters") || "{}");
  } catch (ignore) {
    storedReceivableFilters = {};
  }

  var state = {
    view: "home",
    data: null,
    batchId: null,
    editingId: null,
    orderFilter: "",
    orderIssueFilter: "all",
    orderImportMessage: "",
    physicalStock: null,
    physicalStockSerial: 0,
    physicalSearch: "",
    physicalStatus: "all",
    physicalEntry: null,
    inventoryDataToolsOpen: false,
    quickAddContext: null,
    homeFrom: "",
    homeTo: "",
    priceOverrideActor: "",
    priceOverrideReason: "",
    quoteContractor: "HATRAN",
    quotePeriod: todayIso.slice(0, 7),
    quoteItems: null,
    quoteMode: "group",
    quoteMeta: null,
    quoteVersions: null,
    quoteImportPreview: null,
    quoteDetailsOpen: true,
    quoteHistoryOpen: false,
    modalMode: "order",
    pendingImport: null,
    mappingImportType: "",
    mappingPreview: null,
    catalogImportPreview: null,
    catalogQuery: '',
    catalogOffset: 0,
    catalogItems: [],
    catalogRequest: 0,
    kitchenImportPreview: null,
    kitchenMealCountOverrides: {},
    xcomPaymentPreview: null,
    xcomPaymentRequest: null,
    mealAttendancePreview: null,
    mealAttendancePeriodOverride: "",
    attendanceImportPreview: null,
    openingImportPreview: null,
    bkImportPreview: null,
    bkDocuments: null,
    inventoryValuation: null,
    inventoryValuationRequestSerial: 0,
    inventoryTrace: null,
    inventoryTraceRequestSerial: 0,
    inventoryMonthClose: null,
    inventoryCloseActor: "",
    inventoryMonthCloseRequestSerial: 0,
    inventoryFrom: todayIso.slice(0, 7) + "-01",
    inventoryTo: todayIso,
    inventoryDetailsOpen: true,
    payablesImportPreview: null,
    minvoiceStatus: null,
    operations: null,
    invoiceWorkbench: null,
    invoiceListing: null,
    legacyInvoiceMappingPreview: null,
    invoiceLastPosted: null,
    invoiceWorkbenchRequestSerial: 0,
    invoiceInputRows: [],
    invoiceOutputRows: [],
    invoiceDirection: storedInvoiceFilters.direction === "output" ? "output" : "input",
    invoiceFrom: storedInvoiceFilters.date_from || todayIso.slice(0, 7) + "-01",
    invoiceTo: storedInvoiceFilters.date_to || todayIso,
    invoiceStatus: ["all", "needs_mapping", "ready", "posted", "error", "reversed", "not_inventory"].indexOf(storedInvoiceFilters.status) >= 0 ? storedInvoiceFilters.status : "all",
    invoiceLineFilter: storedInvoiceFilters.line_filter || "all",
    invoicePending: storedInvoiceFilters.scope_version === 2 && storedInvoiceFilters.pending === true,
    supplierNeeds: null,
    purchaseOrderPreview: null,
    deliveryDetailsOpen: false,
    debtSection: "",
    debtPeriod: null,
    debtLoading: false,
    debtFrom: storedPayableFilters.date_from || storedReceivableFilters.date_from || "",
    debtTo: storedPayableFilters.date_to || storedReceivableFilters.date_to || "",
    receivableContractor: storedReceivableFilters.contractor || "",
    receivableKitchen: storedReceivableFilters.kitchen || "",
    receivableStatus: storedReceivableFilters.status || "active",
    receivableLedger: null,
    receivableLoading: false,
    receivableError: "",
    receivableRequestSerial: 0,
    receivableExpanded: {},
    receivableRevisions: {},
    payableSupplier: storedPayableFilters.supplier || "",
    payableStatus: storedPayableFilters.status || "outstanding",
    payableLedger: null,
    payablePayments: null,
    payableLoading: false,
    payableError: "",
    payableSelected: {},
    payableRequestSerial: 0,
    outgoingInvoices: null,
    outgoingShortages: [],
    outgoingReadiness: null,
    outgoingReadinessLoading: false,
    outgoingSubstitutionActions: null,
    outgoingSubstitutionLoading: false,
    outgoingSubstitutionPreview: null,
    outgoingSubstitutionRequest: null,
    outgoingSubstitutionDraft: null,
    invoicePaymentScope: null,
    paymentFilters: null,
    documentDetailsOpen: false,
    outgoingPeriodShortages: null,
    outgoingShortageFrom: todayIso.slice(0, 7) + "-01",
    outgoingShortageTo: todayIso,
    outgoingShortageContractor: "",
    outgoingShortageLoading: false,
    opsDate: todayIso,
    opsMonth: todayIso.slice(0, 7),
    reportPeriod: "",
    reportData: null, reportLoading: false, reportError: "", reportSerial: 0,
    debtSerial: 0, debtError: "", receiptHistory: [], receivableOffset: 0, payableOffset: 0, payableHistoryOffset: 0,
    printingFrom: "",
    printingCustomer: "",
    printingRows: null,
    printingListKey: "",
    printingListSerial: 0,
    printingListLoading: false,
    printingListError: "",
    printingTo: "",
    printingDocument: "deliveries",
    printingSelected: {},
    printingRangeKey: "",
    busy: false
  };

  var titles = {
    home: "Công việc hằng ngày",
    orders: "Nhập và sửa đơn",
    purchases: "Đặt hàng nhà cung cấp",
    physical: "Kho thực tế · hàng còn và thiếu",
    deliveries: "Phiếu giao hàng",
    quotes: "Báo giá",
    reports: "Báo cáo tổng hợp",
    debts: "Công nợ",
    documents: "Bảng kê, biên nhận và hóa đơn",
    inventory: "Báo cáo vật tư hàng hóa",
    msmi: "Hóa đơn đầu vào + đầu ra",
    kitchen: "Suất ăn và đặt hàng bếp",
    payroll: "Chấm công và tính lương",
    printing: "In giấy tờ",
    settings: "Danh mục và sao lưu"
  };

  var content = document.getElementById("content");
  var pageTitle = document.getElementById("pageTitle");
  var sidebar = document.getElementById("sidebar");
  var toast = document.getElementById("toast");
  var batchSelect = document.getElementById("batchSelect");
  var excelInput = document.getElementById("excelInput");
  var attendanceInput = document.getElementById("attendanceInput");
  var mappingFileInput = document.getElementById("mappingFileInput");
  var catalogWorkbookInput = document.getElementById("catalogWorkbookInput");
  var kitchenWorkbookInput = document.getElementById("kitchenWorkbookInput");
  var mealAttendanceInput = document.getElementById("mealAttendanceInput");
  var openingWorkbookInput = document.getElementById("openingWorkbookInput");
  var bkWorkbookInput = document.getElementById("bkWorkbookInput");
  var payablesWorkbookInput = document.getElementById("payablesWorkbookInput");
  var purchaseOrderInput = document.getElementById("purchaseOrderInput");
  var quoteWorkbookInput = document.getElementById("quoteWorkbookInput");
  var backdrop = document.getElementById("modalBackdrop");
  var orderForm = document.getElementById("orderForm");
  var toastTimer;
  var msmiProductSearchTimer;
  var msmiProductSearchVersion = 0;
  var msmiProductSearchInput = null;

  function closeMsmiProductOptions() {
    clearTimeout(msmiProductSearchTimer);
    ++msmiProductSearchVersion;
    var list = document.getElementById("msmiProductOptions");
    if (list) { list.hidden = true; list.innerHTML = ""; }
    if (msmiProductSearchInput) {
      msmiProductSearchInput.setAttribute("aria-expanded", "false");
      msmiProductSearchInput.removeAttribute("aria-activedescendant");
    }
    msmiProductSearchInput = null;
  }

  function showMsmiProductOptions(input, list) {
    msmiProductSearchInput = input;
    input.removeAttribute("aria-activedescendant");
    var box = input.getBoundingClientRect();
    var below = innerHeight - box.bottom - 12, above = box.top - 12;
    var height = Math.min(300, Math.max(below, above));
    var width = Math.min(480, innerWidth - 24);
    list.style.width = width + "px";
    list.style.maxHeight = height + "px";
    list.style.left = Math.max(12, Math.min(box.left, innerWidth - width - 12)) + "px";
    list.style.top = below >= Math.min(300, above) ? (box.bottom + 4) + "px" : "auto";
    list.style.bottom = list.style.top === "auto" ? (innerHeight - box.top + 4) + "px" : "auto";
    list.hidden = false;
    list.scrollTop = 0;
    input.setAttribute("aria-expanded", "true");
  }

  function chooseMsmiProductOption(option) {
    var input = msmiProductSearchInput;
    if (!input || !input.isConnected) return;
    var editingCell = input.closest('.invoice-mapping-cell');
    if (!editingCell.mappingExpected) editingCell.mappingExpected = invoiceMappingExpected(input.dataset.id);
    input.value = option.dataset.productCode;
    input.dataset.selectedCode = option.dataset.productCode;
    var cell = input.closest('.invoice-mapping-cell');
    var line = invoiceEditingLine(input.dataset.id);
    if (cell && line) {
      cell.dataset.editingId = input.dataset.id;
      refreshInvoiceDraftConversion(cell, line, {
        code: option.dataset.productCode, name: option.dataset.productName, unit: option.dataset.productUnit
      });
      input.title = option.dataset.productCode + ' · ' + option.dataset.productName + ' · ' + option.dataset.productUnit + '. Esc để bỏ sửa.';
    }
    closeMsmiProductOptions();
    // Choosing a suggestion previews the conversion; saving remains explicit.
  }

  function refreshInvoiceDraftConversion(cell, line, product) {
    var selectedProduct = cell.querySelector('.invoice-selected-product');
    if (selectedProduct && product) selectedProduct.textContent = 'Mã đang chọn: ' + product.code + ' · ' + product.name + ' · ' + product.unit;
    var progress = cell.querySelector('.invoice-mapping-state');
    if (progress) progress.textContent = product ? 'Đang chọn mã · bấm Lưu.' : 'Chọn mã trong danh mục rồi Lưu.';
    var identityReview = cell.querySelector('.invoice-identity-review');
    if (identityReview) identityReview.hidden = !product || product.code !== line.product_code;
    var conversion = cell.querySelector('.invoice-draft-conversion');
    if (!conversion) return;
    var field = cell.querySelector('.invoice-draft-factor');
    var draft = field?.dataset.userEntered === 'true' ? {value:field.value,product:field.dataset.factorProduct || ''} : null;
    // Keep a factor entered before choosing a code, or when reselecting the same
    // code. A different product must get its own conversion/default.
    if (product && draft?.product && draft.product !== product.code) draft = null;
    var html = window.TdpInvoiceDraftConversion(line,product,draft);
    if (conversion.innerHTML !== html) conversion.innerHTML = html;
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function n(value) { return Number(value || 0); }
  function money(value) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n(value)) + " đ";
  }
  function num(value) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(n(value));
  }
  function stockQty(value) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 6 }).format(n(value));
  }
  function stockMoney(value) {
    // Intl rounds ties away from zero, including negative credit/adjustment rows.
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n(value)) + " đ";
  }
  function stockQuantitySummary(items, field) {
    var units = {};
    items.forEach(function (item) { var unit = (item.unit || "Không có ĐVT").trim().toLocaleLowerCase("vi-VN"); units[unit] = (units[unit] || 0) + n(item[field]); });
    return Object.keys(units).filter(function (unit) { return Math.abs(units[unit]) > 0.0000005; }).map(function (unit) { return stockQty(units[unit]) + " " + unit; }).join(" · ") || "0";
  }
  function inventoryUnits(items) {
    var groups = Object.create(null);
    items.forEach(function(item) {
      var unit = (item.unit || "Không có ĐVT").trim().toLocaleLowerCase("vi-VN");
      if (!groups[unit]) groups[unit] = {unit:unit, opening_qty:0, input_qty:0, output_qty:0, closing_qty:0};
      ["opening_qty","input_qty","output_qty","closing_qty"].forEach(function(field) { groups[unit][field] += n(item[field]); });
    });
    return Object.keys(groups).sort(function(a,b) { return a.localeCompare(b,"vi-VN"); }).map(function(unit) { return groups[unit]; });
  }
  function compactInventoryQuantity(items, field) {
    var groups = inventoryUnits(items).filter(function(row) { return Math.abs(row[field]) > 0.0000005; });
    if (!groups.length) return "0";
    var label = groups.length === 1 ? stockQty(groups[0][field]) + " " + groups[0].unit : groups.length + " ĐVT";
    return '<button type="button" class="inventory-total-button" data-action="view-inventory-unit-totals" title="Xem tổng lượng theo từng đơn vị">' + esc(label) + ' <span aria-hidden="true">↗</span></button>';
  }
  function showInventoryUnitTotals() {
    var groups = inventoryUnits((state.inventoryValuation || {}).items || []);
    var dialog = document.createElement("dialog");
    dialog.className = "inventory-totals-dialog";
    dialog.setAttribute("aria-labelledby", "inventoryTotalsTitle");
    dialog.innerHTML = '<div class="inventory-totals-heading"><div><h3 id="inventoryTotalsTitle">Tổng lượng theo đơn vị</h3><p>' + dateVN(state.inventoryFrom) + ' → ' + dateVN(state.inventoryTo) + '</p></div><button type="button" class="icon-button" aria-label="Đóng tổng lượng">×</button></div>' +
      '<div class="inventory-totals-body"><table><thead><tr><th>ĐVT</th><th>Tồn đầu</th><th>Nhập</th><th>Xuất</th><th>Tồn cuối</th></tr></thead><tbody>' + groups.map(function(row) {
        return '<tr><th scope="row">' + esc(row.unit) + '</th>' + ["opening_qty","input_qty","output_qty","closing_qty"].map(function(field) { return '<td class="num-cell">' + stockQty(row[field]) + '</td>'; }).join("") + '</tr>';
      }).join("") + '</tbody></table></div>';
    dialog.querySelector("button").onclick = function() { dialog.close(); };
    dialog.addEventListener("close", function() { dialog.remove(); });
    document.body.appendChild(dialog);
    dialog.showModal();
  }
  function showInvoiceUnitTotals() {
    var groups = (state.invoiceListing && state.invoiceListing.totals || {}).qty_by_unit || {};
    var dialog = document.createElement('dialog');
    dialog.className = 'inventory-totals-dialog invoice-unit-totals-dialog';
    dialog.setAttribute('aria-label', 'Tổng lượng dòng hóa đơn theo đơn vị');
    dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Tổng lượng dòng đang lọc theo ĐVT</h3><button type="button" class="icon-button" aria-label="Đóng tổng lượng">×</button></div><div class="inventory-totals-body"><table><thead><tr><th>ĐVT</th><th>Tổng lượng</th></tr></thead><tbody>' + Object.keys(groups).map(function(unit) {
      return '<tr><th scope="row">' + esc(unit) + '</th><td>' + stockQty(groups[unit]) + '</td></tr>';
    }).join('') + '</tbody></table></div>';
    dialog.querySelector('button').onclick = function() { dialog.close(); };
    dialog.addEventListener('close', function() { dialog.remove(); });
    document.body.appendChild(dialog); dialog.showModal();
  }
  function confirmInvoiceProductIdentity(review, warning) {
    return new Promise(function(resolve) {
      var dialog = document.createElement('dialog');
      dialog.className = 'invoice-identity-dialog';
      dialog.setAttribute('aria-labelledby', 'invoice-identity-title');
      dialog.setAttribute('aria-describedby', 'invoice-identity-effect');
      dialog.innerHTML = '<h3 id="invoice-identity-title">Kiểm tra mã hàng đầu ra</h3>' +
        (review ? '<dl><div><dt>Tên trên hóa đơn</dt><dd>' + esc(review.source_name) + '<small>Đơn vị: ' + esc(review.source_unit) + '</small></dd></div>' +
        '<div><dt>Mã kho đang chọn</dt><dd><strong>' + esc(review.product_code) + '</strong> · ' + esc(review.product_name) + '<small>Đơn vị: ' + esc(review.product_unit) + '</small></dd></div></dl>' : '<p>' + esc(warning) + '</p>') +
        '<p><strong>Hai tên trên có đúng là cùng một mặt hàng không?</strong></p>' +
        '<p id="invoice-identity-effect">Nếu khác mặt hàng, hãy chọn mã khác. Chỉ xác nhận khi đúng cùng mặt hàng. Lưu mã giữ nguyên số lượng, tiền hóa đơn và chưa xuất kho.</p>' +
        '<div class="invoice-identity-dialog-actions"><button type="button" class="btn btn-outline" data-identity-cancel autofocus>Chọn mã khác</button><button type="button" class="btn btn-primary" data-identity-confirm>Đúng cùng mặt hàng · Lưu mã</button></div>';
      dialog.querySelector('[data-identity-cancel]').onclick = function() { dialog.close('cancel'); };
      dialog.querySelector('[data-identity-confirm]').onclick = function() { dialog.close('confirm'); };
      dialog.addEventListener('close', function() { var confirmed = dialog.returnValue === 'confirm'; dialog.remove(); resolve(confirmed); }, {once:true});
      document.body.appendChild(dialog); dialog.showModal();
      dialog.querySelector('[data-identity-cancel]').focus();
    });
  }
  async function showStockCause(button) {
    if (document.querySelector('.stock-cause-dialog[open]')) return;
    var batchId = state.batchId, code = button.dataset.code, saving = false;
    var dialog = document.createElement('dialog');
    dialog.className = 'inventory-totals-dialog stock-cause-dialog';
    dialog.setAttribute('aria-labelledby', 'stock-cause-title');
    dialog.innerHTML = '<div class="inventory-totals-heading"><h3 id="stock-cause-title">Kiểm tra tồn · ' + esc(code) + '</h3></div><div class="stock-cause-body" aria-live="polite">Đang tải lịch sử mặt hàng…</div><div class="stock-cause-actions"><button type="button" class="btn btn-outline">Quay lại</button></div>';
    dialog.querySelector('.stock-cause-actions button').onclick = function() { if (!saving) dialog.close(); };
    var recheck = document.createElement('button'); recheck.type = 'button'; recheck.className = 'btn btn-outline'; recheck.textContent = 'Kiểm tra lại';
    recheck.onclick = async function() { if (saving) return; await fetchOutgoingReadiness(); await loadTrace(); };
    dialog.querySelector('.stock-cause-actions').appendChild(recheck);
    dialog.addEventListener('cancel', function(event) { if (saving) event.preventDefault(); });
    dialog.addEventListener('close', function() { dialog.remove(); if (button.isConnected) button.focus({preventScroll:true}); }, {once:true});
    document.body.appendChild(dialog); dialog.showModal();
    var body = dialog.querySelector('.stock-cause-body');
    async function loadTrace() {
      dialog.querySelector('[data-edit-opening]')?.remove();
      body.textContent = 'Đang tải lịch sử mặt hàng…';
      try {
        var trace = await api('/api/outgoing-invoices/readiness/' + batchId + '/stock/' + encodeURIComponent(code));
        if (!dialog.open || !dialog.isConnected) return;
        var unit = esc(trace.unit), quantity = function(value) { return stockQty(value) + ' ' + unit; };
        dialog.querySelector('h3').textContent = trace.product_name + ' · ' + trace.product_code;
        var totals = [['Tồn đầu kỳ',trace.opening_qty],['Nhập',trace.input_qty],['Xuất',trace.output_qty],['Tồn trên sổ',trace.closing_qty]];
        var holds = [];
        if (n(trace.reserved_qty)) holds.push('Đang giữ cho dự thảo: <strong>' + quantity(trace.reserved_qty) + '</strong>');
        if (n(trace.pending_sync_issued_qty)) holds.push('Đã phát hành, chờ ghi kho: <strong>' + quantity(trace.pending_sync_issued_qty) + '</strong>');
        body.innerHTML = '<p class="' + (n(trace.available_qty) < 0 ? 'error-summary' : 'ok-summary') + '"><strong>' + (n(trace.available_qty) < 0 ? 'Đang âm ' + quantity(-trace.available_qty) : 'Còn có thể lập ' + quantity(trace.available_qty)) + '</strong></p>' +
          (trace.negative_opening_only ? '<p>Âm ngay từ tồn đầu kỳ. Chưa có dòng nhập/xuất sau đó. Kiểm tra số tồn trong nguồn bên dưới.</p>' : '') +
          '<div class="stock-cause-totals">' + totals.map(function(t) { return '<div><span>' + t[0] + '</span><strong>' + quantity(t[1]) + '</strong></div>'; }).join('') + '</div>' +
          (n(trace.reversal_qty) ? '<p>Hoàn tác: ' + quantity(trace.reversal_qty) + '</p>' : '') +
          (holds.length ? '<p>' + holds.join(' · ') + '</p>' : '') +
          '<h4>Nguồn tính tồn' + (trace.opening_date ? ' từ ' + dateVN(trace.opening_date) : '') + '</h4><div class="stock-cause-scroll"><table><thead><tr><th>Ngày</th><th>Nguồn</th><th>Tăng / giảm</th><th>Tồn sau dòng</th></tr></thead><tbody>' +
          (trace.events || []).map(function(row) { return '<tr><td>' + dateVN(row.date) + '</td><td><strong>' + esc(row.label) + '</strong><div>' + esc(row.reference) + '</div></td><td class="num-cell">' + quantity(row.qty_delta) + '</td><td class="num-cell">' + quantity(row.balance_qty) + '</td></tr>'; }).join('') +
          (!(trace.events || []).length ? '<tr><td colspan="4">Chưa có tồn đầu hoặc dòng nhập/xuất đã ghi sổ.</td></tr>' : '') + '</tbody></table></div>';
        body.insertAdjacentHTML('beforeend', '<div class="stock-source-actions"><p>Đối chiếu nguồn trước khi sửa. Chỉ sửa tồn đầu khi số đầu kỳ sai; nếu dòng nhập/xuất sai, mở đúng hóa đơn bên dưới.</p>' +
          (trace.events || []).filter(function(row) { return row.can_open_invoice; }).map(function(row, index) {
            return '<button type="button" class="btn btn-outline" data-stock-source="' + index + '">Mở ' + esc(row.label.toLowerCase()) + ' · ' + esc(row.reference) + '</button>';
          }).join('') + '</div>');
        var sourceRows = (trace.events || []).filter(function(row) { return row.can_open_invoice; });
        body.querySelectorAll('[data-stock-source]').forEach(function(link) {
          link.onclick = async function() {
            var row = sourceRows[Number(link.dataset.stockSource)];
            link.disabled = true;
            state.stockResolutionReturn = batchId;
            state.invoiceDirection = row.direction;
            state.invoiceFrom = row.invoice_date || row.date; state.invoiceTo = state.invoiceFrom;
            state.invoiceStatus = 'all'; state.invoiceLineFilter = 'all'; state.invoicePending = false;
            await loadInvoiceWorkbench(true);
            if (state.invoiceListing?.error) { link.disabled = false; showToast(state.invoiceListing.error, true); return; }
            if (!state.operations) await loadOperations(true);
            dialog.close(); navigate('msmi');
            var target = invoiceVirtual?.reveal(row.line_id) || document.getElementById('invoice-line-' + row.direction + '-' + row.line_id);
            if (target) { target.classList.add('invoice-just-saved'); target.scrollIntoView({block:'center'}); }
            showToast('Đã mở ngày hóa đơn ' + row.reference + '. Đối chiếu mã ' + code + '.');
          };
        });
        var inputLink = document.createElement('button'); inputLink.type = 'button'; inputLink.className = 'btn btn-outline';
        inputLink.textContent = 'Kiểm tra hóa đơn đầu vào';
        inputLink.onclick = async function() {
          inputLink.disabled = true; state.stockResolutionReturn = batchId;
          state.invoiceDirection = 'input'; state.invoiceFrom = trace.opening_date || currentWorkDate().slice(0,7) + '-01';
          state.invoiceTo = todayIso; state.invoiceStatus = 'all'; state.invoiceLineFilter = 'all'; state.invoicePending = false;
          await loadInvoiceWorkbench(true);
          if (!state.operations) await loadOperations(true);
          dialog.close(); navigate('msmi');
        };
        body.querySelector('.stock-source-actions').appendChild(inputLink);
        if (trace.opening_editor) {
          var edit = document.createElement('button'); edit.type = 'button'; edit.className = 'btn btn-primary';
          edit.dataset.editOpening = '1'; edit.textContent = 'Sửa tồn đầu';
          dialog.querySelector('.stock-cause-actions').appendChild(edit);
          edit.onclick = function() {
            if (dialog.querySelector('.stock-opening-form')) return;
            edit.disabled = true;
            var editor = trace.opening_editor, form = document.createElement('form');
            form.className = 'stock-opening-form';
            form.innerHTML = '<h4>Sửa tồn đầu tháng ' + esc(editor.period.slice(5) + '/' + editor.period.slice(0,4)) + '</h4><p>' + esc(trace.product_name) + ' · ' + esc(code) + '</p>' +
              '<label>Số tồn đúng đã đối chiếu (' + unit + ')<input name="qty" type="number" step="any" required value="' + esc(editor.qty) + '"></label><p class="stock-opening-error" role="alert"></p>' +
              '<div class="form-actions"><button type="button" class="btn btn-outline" data-cancel-edit>Hủy sửa</button><button type="submit" class="btn btn-primary">Lưu tồn đầu</button></div>';
            form.querySelector('p').insertAdjacentHTML('afterend', '<p>Chỉ nhập số tồn đầu đã đối chiếu với nguồn. Không cộng bù để làm hết âm. Lịch sử nhập/xuất giữ nguyên.</p>');
            body.appendChild(form); form.scrollIntoView({block:'nearest'}); form.querySelector('input').focus(); form.querySelector('input').select();
            form.querySelector('[data-cancel-edit]').onclick = function() { form.remove(); edit.disabled = false; edit.focus(); };
            form.onsubmit = async function(event) {
              event.preventDefault(); if (saving) return;
              var qty = Number(form.elements.qty.value); if (!Number.isFinite(qty)) return;
              saving = true; dialog.querySelectorAll('button,input').forEach(function(el) { el.disabled = true; });
              try {
                await api('/api/inventory/opening', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
                  period:editor.period,expected_opening:editor.expected,items:[{product_code:code,qty:qty}]
                })});
              } catch(error) {
                form.querySelector('[role=alert]').textContent = error.message;
                saving = false; dialog.querySelectorAll('button,input').forEach(function(el) { el.disabled = false; }); edit.disabled = true; return;
              }
              saving = false; dialog.querySelectorAll('button,input').forEach(function(el) { el.disabled = false; });
              state.inventoryValuation = null; state.inventoryMonthClose = null; state.outgoingReadiness = null;
              await fetchOutgoingReadiness(); await loadTrace(); showToast('Đã lưu tồn đầu kỳ.');
            };
          };
        }
      } catch(error) {
        if (!dialog.open || !dialog.isConnected) return;
        body.innerHTML = '<p class="error-summary">' + esc(error.message) + '</p><button class="btn btn-outline" type="button">Thử lại</button>';
        body.querySelector('button').onclick = loadTrace;
      }
    }
    await loadTrace();
  }
  function recordIssuedInvoice(draft) {
    return new Promise(function(resolve) {
      var dialog = document.createElement('dialog'), busy = false, result = null;
      dialog.className = 'invoice-identity-dialog invoice-issue-dialog';
      dialog.setAttribute('aria-labelledby','invoice-issue-title');
      dialog.innerHTML = '<h3 id="invoice-issue-title">Ghi nhận hóa đơn đã phát hành</h3><p><strong>' + esc(draft.contractor) + ' · Lượt ' + esc(draft.round_no || 1) + ' · ' + esc(draft.tax_label || '') + '</strong><br>Tổng tiền: ' + money(draft.total_amount) + '</p>' +
        '<form><p>Nhập đúng thông tin đã phát hành trên M-Invoice.</p><div class="payment-grid">' +
        '<label>Ký hiệu hóa đơn<input name="invoice_series" required maxlength="50" value="' + esc(draft.minvoice_series || '') + '" placeholder="VD: 1C26TYY"></label>' +
        '<label>Số hóa đơn<input name="invoice_number" required inputmode="numeric" pattern="[0-9]{1,20}" maxlength="20"></label>' +
        '<label>Ngày hóa đơn<input name="invoice_date" type="date" required value="' + esc(currentWorkDate()) + '"></label></div>' +
        '<p class="invoice-issue-error" role="alert"></p><div class="invoice-identity-dialog-actions"><button type="button" class="btn btn-outline" data-issue-cancel>Quay lại</button><button type="submit" class="btn btn-primary">Lưu số hóa đơn</button></div></form>';
      dialog.querySelector('[data-issue-cancel]').onclick = function() { if (!busy) dialog.close(); };
      dialog.addEventListener('cancel', function(event) { if (busy) event.preventDefault(); });
      dialog.addEventListener('close', function() { dialog.remove(); resolve(result); }, {once:true});
      dialog.querySelector('form').onsubmit = async function(event) {
        event.preventDefault(); if (busy) return;
        var body = Object.fromEntries(new FormData(event.target).entries()); body.confirmed = true;
        busy = true; dialog.querySelectorAll('button,input').forEach(function(el) { el.disabled = true; });
        try {
          result = await api('/api/outgoing-invoices/' + draft.id + '/confirm-issued', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
          busy = false; dialog.close();
        } catch (error) {
          dialog.querySelector('.invoice-issue-error').textContent = error.message;
          busy = false; dialog.querySelectorAll('button,input').forEach(function(el) { el.disabled = false; });
        }
      };
      document.body.appendChild(dialog); dialog.showModal(); dialog.querySelector('input').focus();
    });
  }
  function confirmOutputTaxAdjustment(review) {
    return new Promise(function(resolve) {
      var dialog = document.createElement('dialog');
      dialog.className = 'invoice-identity-dialog invoice-tax-adjustment-dialog';
      dialog.setAttribute('aria-labelledby','invoice-tax-adjustment-title');
      dialog.innerHTML = '<h3 id="invoice-tax-adjustment-title">Đối chiếu cặp hóa đơn điều chỉnh</h3>' +
        review.documents.map(function(doc) {
          return '<section><h4>' + esc(doc.invoice_series + ' / ' + doc.invoice_number) + '</h4><p>Điều chỉnh cho hóa đơn ' + esc(doc.reference_series + ' / ' + doc.reference_number) + '</p>' +
            doc.lines.map(function(line) { return '<p><strong>' + esc(line.product_code + ' · ' + line.product_name) + '</strong><br>' + stockQty(line.qty) + ' ' + esc(line.unit) + ' · Tiền trước thuế: ' + stockMoney(line.amount) + '</p>'; }).join('') +
            '<p>Tiền thuế: <strong>' + stockMoney(doc.tax) + '</strong></p>' + (doc.source_note ? '<p>Lý do trên hóa đơn: ' + esc(doc.source_note) + '</p>' : '') + '</section>';
        }).join('') + '<p><strong>Cộng hai hóa đơn: lượng thay đổi 0, tiền trước thuế thay đổi 0 đ.</strong><br>Thuế thay đổi: <strong>' + stockMoney(review.tax_difference) + '</strong>.</p>' +
        '<label class="invoice-tax-adjustment-check"><input type="checkbox" data-tax-only-check> Tôi xác nhận cặp này chỉ sửa thuế, không giao thêm hoặc nhận trả hàng.</label>' +
        '<p>Xác nhận sẽ đánh dấu cả hai hóa đơn đã đối chiếu. Giữ nguyên hóa đơn và số tiền, không tạo nhập/xuất kho.</p>' +
        '<div class="invoice-identity-dialog-actions"><button type="button" class="btn btn-outline" data-tax-cancel>Để kiểm tra lại</button><button type="button" class="btn btn-primary" data-tax-confirm disabled>Xác nhận đã đối chiếu</button></div>';
      dialog.querySelector('[data-tax-only-check]').onchange = function(event) { dialog.querySelector('[data-tax-confirm]').disabled = !event.target.checked; };
      dialog.querySelector('[data-tax-cancel]').onclick = function() { dialog.close('cancel'); };
      dialog.querySelector('[data-tax-confirm]').onclick = function() { if (dialog.querySelector('[data-tax-only-check]').checked) dialog.close('confirm'); };
      dialog.addEventListener('close',function() { var confirmed = dialog.returnValue === 'confirm';dialog.remove();resolve(confirmed); },{once:true});
      document.body.appendChild(dialog);dialog.showModal();dialog.querySelector('[data-tax-cancel]').focus();
    });
  }
  function confirmInvoiceExpense(invoice, line, expense) {
    return new Promise(function(resolve) {
      var rows = line ? [line] : (invoice.items || []).filter(function(r) { return expense ? r.inventory_eligible || r.is_expense : r.is_expense; });
      var dialog = document.createElement('dialog');
      dialog.className = 'invoice-expense-confirm';
      dialog.setAttribute('aria-labelledby','invoice-expense-confirm-title');
      dialog.setAttribute('aria-describedby','invoice-expense-confirm-effect');
      dialog.innerHTML = '<h3 id="invoice-expense-confirm-title">' + (expense ? 'Chuyển sang chi phí không nhập kho?' : 'Chuyển lại thành hàng hóa?') + '</h3>' +
        '<p><strong>' + esc(invoice.invoice_series + ' / ' + invoice.invoice_number) + '</strong> · ' + dateVN(invoice.invoice_date) + '<br>' + esc(invoice.seller_name || '') + '</p>' +
        '<p><strong>' + (line ? 'Chỉ dòng ' + line.line_index : 'Cả hóa đơn · ' + rows.length + ' dòng trong danh sách') + '</strong></p>' +
        '<div class="invoice-expense-confirm-lines"><table><thead><tr><th>Mặt hàng</th><th>Lượng</th><th>Tiền chưa thuế</th></tr></thead><tbody>' + rows.map(function(r) {
          return '<tr><td>' + esc(r.source_item_name) + (r.product_code ? '<small>' + esc(r.product_code) + '</small>' : '') + '</td><td>' + stockQty(r.qty) + ' ' + esc(r.source_unit || '') + '</td><td>' + stockMoney(r.amount) + '</td></tr>';
        }).join('') + '</tbody></table></div>' +
        '<p id="invoice-expense-confirm-effect">' + (expense ? 'Các dòng này sẽ không được đưa vào lần nhập kho. Hóa đơn và số tiền vẫn được giữ nguyên. Nếu đang gộp, nhóm liên quan sẽ được tách.' : 'Các dòng này sẽ cần mã hàng và quy đổi hợp lệ trước khi nhập kho. Xác nhận phân loại chưa ghi kho.') + '</p>' +
        '<div class="invoice-expense-confirm-actions"><button type="button" class="btn btn-outline" data-expense-cancel autofocus>Hủy, giữ nguyên</button><button type="button" class="btn btn-primary" data-expense-confirm>' + (expense ? 'Xác nhận là chi phí' : 'Xác nhận là hàng hóa') + '</button></div>';
      dialog.querySelector('[data-expense-cancel]').onclick = function() { dialog.close('cancel'); };
      dialog.querySelector('[data-expense-confirm]').onclick = function() { dialog.close('confirm'); };
      dialog.addEventListener('close',function() { var confirmed = dialog.returnValue === 'confirm'; dialog.remove(); resolve(confirmed); },{once:true});
      document.body.appendChild(dialog); dialog.showModal();
      dialog.querySelector('[data-expense-cancel]').focus();
    });
  }
  function showInvoiceReceiptSummary(id) {
    if (content.querySelector('.invoice-mapping-cell[data-editing-id]')) {
      showToast('Hãy Lưu hoặc nhấn Esc để bỏ phần đang sửa trên bảng trước khi mở Kiểm tra.', true);
      return;
    }
    var invoice = ((state.invoiceListing || {}).items || []).find(function(row) { return String(row.id) === String(id); });
    if (!invoice || !invoice.receipt_summary) return;
    return window.TdpInvoiceReviewEditor(invoice, {
      api: api, esc: esc, quantity: stockQty, money: stockMoney, dateVN: dateVN,
      changed: async function() {
        state.operations = null;
        await loadInvoiceWorkbench(true); render();
      }
    });
  }
  function dateVN(value) {
    if (!value) return "";
    var parts = String(value).slice(0, 10).split("-");
    return parts.length === 3 ? parts[2] + "/" + parts[1] + "/" + parts[0] : value;
  }
  function dateTimeVN(value) {
    var raw = String(value || "").trim();
    if (!raw) return "";
    var time = raw.match(/[T ](\d{2}:\d{2})/);
    return dateVN(raw) + (time ? " lúc " + time[1] : "");
  }
  function localizedTemporalText(value, kind) {
    var raw = String(value || "").trim();
    var match = kind === "month"
      ? raw.match(/^(\d{4})-(\d{2})$/)
      : raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return raw;
    return kind === "month"
      ? match[2] + "/" + match[1]
      : match[3] + "/" + match[2] + "/" + match[1];
  }
  function parseLocalizedTemporal(value, kind) {
    var raw = String(value || "").trim();
    if (!raw) return "";
    var match;
    if (kind === "month") {
      match = raw.match(/^(\d{1,2})[\/.-](\d{4})$/);
      if (match) raw = match[2] + "-" + String(match[1]).padStart(2, "0");
      match = raw.match(/^(\d{4})-(\d{2})$/);
      if (!match || Number(match[2]) < 1 || Number(match[2]) > 12) return null;
      return match[1] + "-" + match[2];
    }
    match = raw.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})$/);
    if (match) {
      raw = match[3] + "-" + String(match[2]).padStart(2, "0") + "-" + String(match[1]).padStart(2, "0");
    }
    match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return null;
    var year = Number(match[1]);
    var month = Number(match[2]);
    var day = Number(match[3]);
    var checked = new Date(Date.UTC(year, month - 1, day));
    if (checked.getUTCFullYear() !== year || checked.getUTCMonth() !== month - 1 || checked.getUTCDate() !== day) return null;
    return match[1] + "-" + match[2] + "-" + match[3];
  }
  function enhanceLocalizedDateInputs(root) {
    (root || document).querySelectorAll('input[type="date"], input[type="month"]').forEach(function (nativeInput) {
      if (nativeInput.dataset.localizedDate === "1") return;
      nativeInput.dataset.localizedDate = "1";
      var kind = nativeInput.type;
      var committedValue = nativeInput.value;
      var fieldLabel = nativeInput.getAttribute("aria-label") || Array.from(nativeInput.labels || []).map(function (label) { return label.textContent.trim(); }).join(' ') || (kind === 'month' ? 'Tháng' : 'Ngày');
      var wrapper = document.createElement("span");
      wrapper.className = "localized-date-control";
      var display = document.createElement("input");
      display.type = "text";
      display.className = "localized-date-display";
      display.placeholder = kind === "month" ? "mm/yyyy" : "dd/mm/yyyy";
      display.inputMode = "numeric";
      display.autocomplete = "off";
      display.required = nativeInput.required;
      display.disabled = nativeInput.disabled;
      display.readOnly = nativeInput.readOnly;
      display.setAttribute("aria-label", fieldLabel);
      display.value = localizedTemporalText(nativeInput.value, kind);
      nativeInput.parentNode.insertBefore(wrapper, nativeInput);
      wrapper.appendChild(display);
      wrapper.appendChild(nativeInput);
      nativeInput.classList.add("localized-date-native");
      nativeInput.tabIndex = -1;
      var icon = document.createElement("button");
      icon.type = "button";
      icon.className = "localized-date-icon";
      icon.setAttribute("aria-label", (kind === 'month' ? 'Mở lịch tháng: ' : 'Mở lịch: ') + fieldLabel);
      icon.disabled = nativeInput.disabled || nativeInput.readOnly;
      icon.textContent = "▦";
      wrapper.appendChild(icon);
      if (typeof nativeInput.showPicker === 'function') {
        // Keep the text field from blurring/re-rendering before the click arrives.
        icon.addEventListener('pointerdown', function (event) { event.preventDefault(); });
        icon.addEventListener('click', function () {
          if (!nativeInput.disabled && !nativeInput.readOnly) nativeInput.showPicker();
        });
      } else {
        // Older browsers use the native picker, with its full hit area over the icon.
        wrapper.classList.add('native-picker-fallback');
        icon.tabIndex = -1;
        nativeInput.tabIndex = 0;
        nativeInput.setAttribute('aria-label', fieldLabel);
      }

      function syncFromDisplay(reportInvalid) {
        var parsed = parseLocalizedTemporal(display.value, kind);
        var message = kind === "month" ? "Nhập tháng theo dạng mm/yyyy" : "Nhập ngày theo dạng dd/mm/yyyy";
        if (parsed === null) {
          nativeInput.value = "";
          display.setCustomValidity(reportInvalid ? message : "");
          if (reportInvalid) display.reportValidity();
          return;
        }
        display.setCustomValidity("");
        var changed = committedValue !== parsed;
        nativeInput.value = parsed;
        display.value = localizedTemporalText(parsed, kind);
        if (changed) nativeInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
      display.addEventListener("input", function () {
        display.setCustomValidity("");
        var parsed = parseLocalizedTemporal(display.value, kind);
        if (parsed !== null) nativeInput.value = parsed;
      });
      display.addEventListener("change", function () { syncFromDisplay(true); });
      display.addEventListener("blur", function () { syncFromDisplay(Boolean(display.value)); });
      nativeInput.addEventListener("input", function () {
        display.value = localizedTemporalText(nativeInput.value, kind);
        display.setCustomValidity("");
      });
      nativeInput.addEventListener("change", function () {
        committedValue = nativeInput.value;
        display.value = localizedTemporalText(nativeInput.value, kind);
        display.setCustomValidity("");
      });
      if (nativeInput.form) {
        nativeInput.form.addEventListener("reset", function () {
          setTimeout(function () { committedValue = nativeInput.value; display.value = localizedTemporalText(nativeInput.value, kind); }, 0);
        });
      }
    });
  }
  function payableStatusText(value) {
    return ({
      open: "Chưa trả",
      partially_paid: "Trả một phần",
      paid: "Đã trả",
      reversed: "Đã đảo",
      posted: "Đã ghi nhận"
    })[value] || value || "—";
  }
  function payableStatusClass(value) {
    if (value === "paid" || value === "posted") return "tag-ok";
    if (value === "partially_paid") return "tag-warn";
    if (value === "reversed") return "tag-red";
    return "";
  }
  function receivableStatusText(value) {
    return ({ active: "Hiệu lực", reversed: "Đã hoàn tác" })[value] || value || "—";
  }
  function receivableRevisionText(value) {
    return ({
      insert: "Khởi tạo", update: "Cập nhật", reverse: "Hoàn tác", reactivate: "Kích hoạt lại"
    })[value] || value || "—";
  }
  function invoiceReceiptStatusText(value) {
    return ({
      pending_mapping: "Chưa ghép đủ mã",
      ready: "Sẵn sàng tạo phiếu nhập",
      posted: "Đã ghi nhập kho",
      blocked: "Đang bị chặn · cần kiểm tra",
      not_inventory: "Không có dòng nhập kho"
    })[value] || "Chưa rõ trạng thái nhập kho";
  }
  function invoiceStockStatusText(value) {
    return ({
      blocked: "Đang bị chặn · cần kiểm tra",
      pending_mapping: "Chưa ghép đủ mã",
      ready: "Sẵn sàng xác nhận xuất kho",
      not_inventory: "Không có dòng ảnh hưởng kho",
      posted: "Đã ghi xuất kho",
      reversal_required: "Cần hoàn tác xuất kho",
      reversed: "Đã hoàn tác xuất kho"
    })[value] || "Chưa rõ trạng thái xuất kho";
  }
  function invoiceSyncStatusText(value) {
    return ({ ok: "Thành công", error: "Có lỗi · cần thử lại" })[value] || "Chưa rõ trạng thái đồng bộ";
  }
  function mealPlanStatusText(value) {
    return ({ draft: "Bản nháp", approved: "Đã duyệt" })[value] || "Chưa rõ trạng thái kế hoạch";
  }
  function persistPayableFilters() {
    try {
      window.localStorage.setItem("tdp.payableFilters", JSON.stringify({
        date_from: state.debtFrom,
        date_to: state.debtTo,
        supplier: state.payableSupplier,
        status: state.payableStatus
      }));
    } catch (ignore) {}
  }
  function persistReceivableFilters() {
    try {
      window.localStorage.setItem("tdp.receivableFilters", JSON.stringify({
        date_from: state.debtFrom,
        date_to: state.debtTo,
        contractor: state.receivableContractor,
        kitchen: state.receivableKitchen,
        status: state.receivableStatus
      }));
    } catch (ignore) {}
  }
  function taxText(value) {
    var code = String(value == null ? '' : value).trim().toUpperCase();
    if (code === "KKKNT" || code === "KCT") return code;
    if (!code) return 'Chưa có thuế';
    var rate = Number(code.replace(/%$/, ''));
    if (!Number.isFinite(rate)) return 'Thuế chưa hợp lệ';
    if (rate === -2) return 'KKKNT';
    if (rate === -1) return 'KCT';
    if (!code.endsWith('%') && rate > 0 && rate < 1) rate *= 100;
    return [0,5,8,10].includes(rate) ? rate + '%' : 'Thuế chưa hợp lệ';
  }
  function html(parts) { return parts.join(""); }

  function showToast(message, error) {
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.toggle("toast-error", Boolean(error));
    toast.classList.add("show");
    toastTimer = setTimeout(function () { toast.classList.remove("show"); }, error ? 4300 : 2800);
  }

  function friendlyErrorMessage(message, status) {
    var text = String(message || "").trim();
    if ((status === 404 && !text) || /requested URL was not found/i.test(text)) {
      return "Không tìm thấy chức năng này. Hãy tải lại trang; nếu vẫn còn lỗi, liên hệ người hỗ trợ.";
    }
    if (/failed to fetch|networkerror|network request failed/i.test(text)) {
      return "Không kết nối được với phần mềm. Hãy kiểm tra cửa sổ chạy hệ thống rồi thử lại.";
    }
    return text || "Có lỗi khi xử lý. Hãy thử lại.";
  }

  async function api(url, options) {
    var response;
    try {
      response = await fetch(url, options || {});
    } catch (error) {
      throw new Error(friendlyErrorMessage(error && error.message));
    }
    var type = response.headers.get("content-type") || "";
    var payload = type.indexOf("application/json") >= 0 ? await response.json() : null;
    if (!response.ok || (payload && payload.ok === false)) {
      var error = new Error(friendlyErrorMessage(payload && payload.error, response.status));
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  async function downloadFile(url, options) {
    var response;
    try {
      response = await fetch(url, options || {});
    } catch (error) {
      throw new Error(friendlyErrorMessage(error && error.message));
    }
    if (!response.ok) {
      var type = response.headers.get("content-type") || "";
      var payload = type.indexOf("application/json") >= 0 ? await response.json() : null;
      throw new Error(friendlyErrorMessage(payload && payload.error, response.status));
    }
    var disposition = response.headers.get("content-disposition") || "";
    var encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    var plainName = disposition.match(/filename="?([^";]+)"?/i);
    var filename = encodedName ? decodeURIComponent(encodedName[1]) : plainName ? plainName[1] : "chung-tu";
    var blobUrl = URL.createObjectURL(await response.blob());
    var anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(function () { URL.revokeObjectURL(blobUrl); }, 1000);
    return {filename:filename, invoiceFiles:Number(response.headers.get('X-Invoice-Files') || 0), pendingLines:Number(response.headers.get('X-Pending-Order-Lines') || 0)};
  }

  function setBusy(value, message) {
    state.busy = value;
    if (value) {
      content.innerHTML = '<div class="loading-panel"><div class="spinner"></div><strong>' +
        esc(message || "Đang xử lý…") + "</strong></div>";
    }
  }

  async function loadData(batchId, silent) {
    if (batchId === undefined) batchId = state.batchId;
    if (!silent) setBusy(true, "Đang nạp dữ liệu vận hành…");
    try {
      var suffix = batchId ? "?batch_id=" + batchId : "";
      state.data = await api("/api/bootstrap" + suffix);
      state.outgoingReadinessSerial = (state.outgoingReadinessSerial || 0) + 1;
      state.outgoingInvoicesSerial = (state.outgoingInvoicesSerial || 0) + 1;
      state.outgoingReadiness = null; state.outgoingReadinessLoading = false;
      state.outgoingInvoices = null; state.outgoingInvoicesLoading = false;
      state.outgoingPeriodShortages = null;
      state.printingListSerial++;
      state.printingRows = null;
      state.printingListLoading = false;
      state.printingRangeKey = "";
      state.batchId = state.data.batch ? state.data.batch.id : null;
      var anchorDate = state.data.batch
        ? state.data.batch.work_date
        : state.data.batches && state.data.batches.length
          ? state.data.batches[0].work_date
          : todayIso;
      if (!state.homeFrom || !state.homeTo) state.homeFrom = state.homeTo = anchorDate;
      if (!state.printingFrom || !state.printingTo) state.printingFrom = state.printingTo = anchorDate;
      if (!state.reportPeriod) state.reportPeriod = String(anchorDate).slice(0, 7);
      state.reportSerial++; state.reportData = null; state.reportLoading = false; state.reportError = "";
      state.supplierNeeds = null;
      state.purchaseOrderPreview = null;
      invalidateDebtPeriod();
      invalidateReceivableWorkspace(true);
      invalidatePayableWorkspace(true);
      state.busy = false;
      renderBatchSelect();
      render();
    } catch (error) {
      state.busy = false;
      content.innerHTML = '<div class="card"><div class="empty"><h3>Không nạp được dữ liệu</h3><p>' +
        esc(error.message) + '</p><button class="btn btn-primary" data-action="reload">Thử lại</button></div></div>';
    }
  }

  async function loadOperations(silent) {
    if (!silent) content.innerHTML = '<div class="loading-panel"><div class="spinner"></div><strong>Đang nạp dữ liệu module…</strong></div>';
    try {
      state.operations = await api("/api/operations/bootstrap?as_of=" + encodeURIComponent(state.opsDate) +
        "&active_only=1&month=" + encodeURIComponent(state.opsMonth) + "&date=" + encodeURIComponent(state.opsDate));
      if (state.view === "msmi") await loadInvoiceWorkbench(true);
      render();
    } catch (error) {
      content.innerHTML = '<div class="card"><div class="empty"><h3>Không nạp được module</h3><p>' +
        esc(error.message) + '</p><button class="btn btn-primary" data-action="reload-operations">Thử lại</button></div></div>';
    }
  }

  async function loadInventoryValuation(silent) {
    var requestSerial = ++state.inventoryValuationRequestSerial;
    if (!silent) content.innerHTML = '<div class="loading-panel"><div class="spinner"></div><strong>Đang mở báo cáo vật tư hàng hóa…</strong></div>';
    try {
      var valuationResult = await api("/api/invoice-valuation?from=" +
        encodeURIComponent(state.inventoryFrom) + "&to=" + encodeURIComponent(state.inventoryTo));
      if (requestSerial !== state.inventoryValuationRequestSerial) return;
      state.inventoryValuation = valuationResult;
      if (!silent) render();
    } catch (error) {
      if (requestSerial !== state.inventoryValuationRequestSerial) return;
      state.inventoryValuation = { error: error.message, items: [] };
      if (!silent) render();
    }
  }

  async function loadInventoryMonthClose(silent) {
    var period = state.inventoryClosePeriod || (state.inventoryFrom || state.opsMonth || todayIso).slice(0, 7);
    var requestSerial = ++state.inventoryMonthCloseRequestSerial;
    try {
      var result = await api(
        "/api/inventory/month-close/preview?period=" + encodeURIComponent(period)
      );
      if (requestSerial !== state.inventoryMonthCloseRequestSerial) return;
      state.inventoryMonthClose = result;
      if (!silent && state.view === "inventory") renderInventoryCloseDialog();
    } catch (error) {
      if (requestSerial !== state.inventoryMonthCloseRequestSerial) return;
      state.inventoryMonthClose = { error: error.message, period: period, issues: [] };
      if (!silent && state.view === "inventory") renderInventoryCloseDialog();
    }
  }

  async function refreshInventoryMonthWorkspace(message) {
    state.inventoryValuation = null;
    state.inventoryMonthClose = null;
    await Promise.all([loadInventoryValuation(true), loadInventoryMonthClose(true)]);
    renderInventory();
    renderInventoryCloseDialog();
    if (message) showToast(message);
  }

  async function closeInventoryMonth(button) {
    var actorInput = document.getElementById("inventoryCloseActor");
    var actor = actorInput ? actorInput.value.trim() : state.inventoryCloseActor;
    if (!actor) { showToast("Nhập tên người xác nhận trước khi chốt tháng", true); if (actorInput) actorInput.focus(); return; }
    state.inventoryCloseActor = actor;
    var preview = state.inventoryMonthClose;
    var period = button.dataset.period;
    var periodLabel = button.dataset.periodLabel;
    var nextPeriodLabel = button.dataset.nextPeriodLabel;
    var sourceHash = button.dataset.sourceHash;
    var targetHash = button.dataset.targetHash;
    if (!period || !sourceHash || !targetHash) return;
    var question = "Chốt kho tháng " + periodLabel + " và chuyển toàn bộ tồn cuối " +
      "sang tồn đầu tháng " + nextPeriodLabel + "?\n\n" +
      "Hệ thống sẽ thay dữ liệu tồn đầu tháng sau, không cộng chồng.";
    if (preview && (preview.unposted_input_count || preview.unposted_output_count)) {
      question += "\n\nLưu ý: còn " + num(preview.unposted_input_count) + " hóa đơn đầu vào và " + num(preview.unposted_output_count) + " hóa đơn đầu ra chưa ghi kho. Chốt tháng chỉ lấy số liệu ĐÃ GHI KHO, không tự ghi các hóa đơn còn lại.";
    }
    if (!window.confirm(question)) return;
    state.inventoryCloseBusy = true;
    document.querySelectorAll('.inventory-close-dialog button,.inventory-close-dialog input').forEach(function(el) { el.disabled = true; });
    var label = button.textContent;
    try {
      button.disabled = true;
      button.textContent = "Đang chốt và kiểm tra…";
      var result = await api("/api/inventory/month-close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          period: period,
          source_hash: sourceHash,
          target_hash: targetHash,
          actor: actor,
          confirmed: true
        })
      });
      await refreshInventoryMonthWorkspace(
        result.idempotent
          ? "Tháng này đã được chốt đúng số liệu, hệ thống không cộng lại"
          : "Đã chốt tháng " + periodLabel + " và chuyển tồn sang tháng " + nextPeriodLabel
      );
    } catch (error) {
      button.disabled = false;
      button.textContent = label;
      showToast(error.message, true);
      await loadInventoryMonthClose(true);
      renderInventory();
    } finally {
      state.inventoryCloseBusy = false;
      renderInventoryCloseDialog();
    }
  }

  async function reopenInventoryMonth(button) {
    var actorInput = document.getElementById("inventoryCloseActor");
    var actor = actorInput ? actorInput.value.trim() : state.inventoryCloseActor;
    if (!actor) { showToast("Nhập tên người xác nhận trước khi mở lại tháng", true); if (actorInput) actorInput.focus(); return; }
    state.inventoryCloseActor = actor;
    var period = button.dataset.period;
    var periodLabel = button.dataset.periodLabel;
    var nextPeriodLabel = button.dataset.nextPeriodLabel;
    if (!period) return;
    var question = "Mở lại tháng " + periodLabel + " để sửa số liệu?\n\n" +
      "Tồn đầu tháng " + nextPeriodLabel + " sẽ được bỏ tạm thời. " +
      "Sau khi sửa xong, hãy chốt tháng này lại.";
    if (!window.confirm(question)) return;
    state.inventoryCloseBusy = true;
    document.querySelectorAll('.inventory-close-dialog button,.inventory-close-dialog input').forEach(function(el) { el.disabled = true; });
    var label = button.textContent;
    try {
      button.disabled = true;
      button.textContent = "Đang mở lại tháng…";
      await api("/api/inventory/month-close/reopen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period: period, confirmed: true, actor: actor })
      });
      await refreshInventoryMonthWorkspace(
        "Đã mở lại tháng " + periodLabel + " · sửa xong hãy chốt lại"
      );
    } catch (error) {
      button.disabled = false;
      button.textContent = label;
      showToast(error.message, true);
      await loadInventoryMonthClose(true);
      renderInventory();
    } finally {
      state.inventoryCloseBusy = false;
      renderInventoryCloseDialog();
    }
  }

  async function loadBkDocuments(silent) {
    try {
      var result = await api("/api/bk-import/documents?limit=50");
      state.bkDocuments = result.items || [];
      if (!silent && state.view === "inventory") renderInventory();
    } catch (error) {
      state.bkDocuments = [];
      if (!silent) showToast(error.message, true);
    }
  }

  function persistInvoiceWorkbenchFilters() {
    try {
      window.localStorage.setItem("tdp.invoiceWorkbenchFilters", JSON.stringify({
        direction: state.invoiceDirection,
        date_from: state.invoiceFrom,
        date_to: state.invoiceTo,
        status: state.invoiceStatus,
        line_filter: state.invoiceLineFilter,
        pending: state.invoicePending,
        scope_version: 2
      }));
    } catch (ignore) {
      // The workbench remains usable when browser storage is disabled.
    }
  }

  async function loadInvoiceWorkbench(silent) {
    var requestSerial = ++state.invoiceWorkbenchRequestSerial;
    var direction = state.invoiceDirection;
    var query = "?invoice_type=" + encodeURIComponent(direction) + "&from=" + encodeURIComponent(state.invoiceFrom) + "&to=" + encodeURIComponent(state.invoiceTo);
    if (!silent) content.innerHTML = '<div class="loading-panel"><div class="spinner"></div><strong>Đang nạp bàn làm việc hóa đơn…</strong></div>';
    try {
      var results = await Promise.all([
        api("/api/invoice-workbench" + query),
        api("/api/invoice-workbench/invoices" + query + "&status=" + encodeURIComponent(state.invoiceStatus) + "&line_filter=" + encodeURIComponent(state.invoiceLineFilter) + (state.invoicePending ? '&scope=pending' : ''))
      ]);
      if (requestSerial !== state.invoiceWorkbenchRequestSerial) return;
      state.invoiceWorkbench = results[0];
      state.invoiceListing = results[1];
      state.invoiceInputRows = direction === "input" ? results[1].items : [];
      state.invoiceOutputRows = direction === "output" ? results[1].items : [];
      if (!silent) render();
    } catch (error) {
      if (requestSerial !== state.invoiceWorkbenchRequestSerial) return;
      state.invoiceWorkbench = { error: error.message, batches: [], counts: {} };
      state.invoiceListing = {error:error.message, items:[], lines:[]};
      state.invoiceInputRows = [];
      state.invoiceOutputRows = [];
      if (!silent) render();
    }
  }

  async function prepareInvoiceSyncBatch(button) {
    var originalLabel = button.textContent;
    try {
      button.disabled = true;
      button.textContent = "Đang chuẩn bị…";
      var result = await api("/api/invoice-workbench/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: state.invoiceDirection === "input" ? "msmi" : "minvoice",
          invoice_type: state.invoiceDirection,
          date_from: state.invoiceFrom,
          date_to: state.invoiceTo
        })
      });
      button.textContent = state.invoiceDirection === "input" ? "Đang tải đầu vào…" : "Đang tải đầu ra…";
      var synced = await api("/api/invoice-workbench/batches/" + result.batch.id + "/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_pages: state.invoiceDirection === "input" ? 5 : 10, page_size: 199 })
      });
      if (state.invoiceDirection === "input") {
        state.operations = null;
        await Promise.all([loadOperations(true), loadInvoiceWorkbench(true)]);
        render();
        showToast("Đầu vào: " + synced.new_invoices + " hóa đơn mới, " + synced.known_invoices +
          " hóa đơn đã có · tự ghép " + ((synced.automatic_mapping || {}).mapped_lines_in_period || 0) +
          " dòng trùng khớp" + (synced.more_history ? " · bấm tiếp để tải phần còn lại" : ""));
      } else {
        await loadInvoiceWorkbench(true);
        render();
        showToast("Đầu ra: " + synced.new_invoices + " hóa đơn mới, " + synced.known_invoices +
          " hóa đơn đã có" + (synced.more_history ? " · còn dữ liệu, bấm tiếp để tải hết đúng khoảng ngày" : "") +
          (!synced.status_mapping_configured ? " · chưa đọc được trạng thái, cần người dùng kiểm tra" : ""));
      }
    } catch (error) {
      showToast(error.message, true);
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  function renderBatchSelect() {
    var batches = state.data && state.data.batches ? state.data.batches : [];
    if (batches.length) {
      batchSelect.innerHTML = batches.map(function (batch) {
        return '<option value="' + batch.id + '"' + (batch.id === state.batchId ? " selected" : "") + ">" +
          dateVN(batch.work_date) + " · " + esc(batch.source_name) + " · " +
          (batch.status === "approved" ? "Đã duyệt" : "Nháp") + "</option>";
      }).join("");
    } else {
      batchSelect.innerHTML = '<option value="">Chưa có đơn hàng</option>';
    }
    batchSelect.disabled = !batches.length;
  }

  function navigate(view) {
    // Legacy data stays in the database; retired modules have no daily screen.
    if (view === "kitchen" || view === "payroll") view = "home";
    if (view === "debts" && state.view !== "debts") state.debtSection = "";
    state.view = view;
    document.querySelectorAll(".nav-item").forEach(function (button) {
      button.classList.toggle("active", button.dataset.view === view);
    });
    pageTitle.textContent = titles[view] || "Vận hành";
    sidebar.classList.remove("open");
    window.scrollTo(0, 0);
    if (view === "physical") { loadPhysicalStock(); return; }
    if (["msmi", "printing"].indexOf(view) >= 0 && !state.operations) {
      loadOperations();
      return;
    }
    if (view === "msmi" && !state.invoiceWorkbench) {
      loadInvoiceWorkbench();
      return;
    }
    render();
  }

  function statCard(label, value, sub, icon) {
    return '<div class="stat-card"><div class="stat-head"><span class="label">' + esc(label) +
      '</span><div class="stat-icon">' + icon + '</div></div><span class="value">' + esc(value) +
      '</span><div class="sub">' + esc(sub) + "</div></div>";
  }

  function mappingPreviewHtml(mappingType) {
    var preview = state.mappingPreview;
    if (!preview || preview.mapping_type !== mappingType) return "";
    var statusNames = { "new": "Thêm mới", "update": "Cập nhật", "unchanged": "Không đổi", "duplicate": "Dòng trùng", "error": "Lỗi" };
    var visibleRows = preview.rows.slice(0, 200).map(function (item) {
      var messages = item.errors.concat(item.warnings);
      var tagClass = item.errors.length ? "tag-red" : item.status === "new" ? "tag-ok" : "tag-warn";
      return '<tr class="' + (item.errors.length ? 'row-error' : item.warnings.length ? 'row-warning' : '') + '"><td>' + item.source_row + '</td><td><strong>' + esc(item.resolved_code || item.source_code) +
        '</strong><div class="muted">' + esc(item.resolved_name || item.source_name) + '</div></td><td>' +
        esc(item.current_value || "—") + '</td><td><strong>' + esc(item.target_value || "—") +
        '</strong></td><td><span class="tag ' + tagClass + '">' + esc(statusNames[item.status] || item.status) +
        '</span><div class="muted">' + esc(messages.join(" · ")) + '</div></td></tr>';
    }).join("");
    var count = preview.counts;
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Xem trước file ', esc(preview.filename),
      '</h3><p>Trang Excel ', esc(preview.sheet), ' · dòng tiêu đề ', preview.header_row,
      ' · dữ liệu chỉ được ghi sau khi xác nhận</p></div><button class="btn btn-small btn-outline" data-action="cancel-mapping-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.total, ' dòng · ', count.new, ' thêm · ', count.update,
      ' sửa · ', count.unchanged, ' không đổi · ', count.duplicate, ' trùng · ', count.error, ' lỗi</div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Dòng</th><th>Mã / tên đã ghép</th><th>Đang lưu</th><th>Sẽ lưu</th><th>Kiểm tra</th></tr></thead><tbody>',
      visibleRows, '</tbody></table></div>',
      preview.rows.length > 200 ? '<div class="card-body muted">Chỉ hiển thị 200 dòng đầu; toàn bộ file vẫn được kiểm tra.</div>' : '',
      '<div class="card-body"><div class="form-actions"><button class="btn btn-primary" data-action="confirm-mapping-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận nhập dữ liệu</button></div>',
      preview.can_confirm ? '' : '<div class="code-note"><strong>Chưa thể nhập:</strong> sửa hết dòng lỗi trong Excel rồi chọn lại file.</div>',
      '</div></div>'
    ]);
  }

  function catalogImportPreviewHtml() {
    var preview = state.catalogImportPreview;
    if (!preview) return "";
    var statusNames = { "new": "Thêm mới", "update": "Cập nhật", "unchanged": "Không đổi", "duplicate": "Dòng trùng", "error": "Lỗi" };
    var visibleRows = preview.rows.slice(0, 200).map(function (item) {
      var messages = item.errors.concat(item.warnings);
      var status = item.errors.length ? "error" : item.product_status;
      var tagClass = status === "error" ? "tag-red" : status === "new" ? "tag-ok" : "tag-warn";
      return '<tr class="' + (item.errors.length ? 'row-error' : item.warnings.length ? 'row-warning' : '') + '"><td>' + item.source_row + '</td><td><strong>' + esc(item.product_code) +
        '</strong><div class="muted">' + esc(item.product_group || "—") + '</div></td><td><strong>' +
        esc(item.product_name) + '</strong><div class="muted">' + esc(item.unit) + ' · ' +
        esc(taxText(item.tax)) + '</div></td><td>' + esc(item.invoice_name || "—") +
        '</td><td><span class="tag ' + tagClass + '">' + esc(statusNames[status] || status) +
        '</span><div class="muted">' + esc(messages.join(" · ")) + '</div></td></tr>';
    }).join("");
    var count = preview.counts;
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Xem trước danh mục ', esc(preview.filename),
      '</h3><p>Trang Excel ', esc(preview.sheet), ' · dòng tiêu đề ', preview.header_row,
      ' · chỉ ghi sau khi người dùng xác nhận</p></div><button class="btn btn-small btn-outline" data-action="cancel-catalog-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.unique_products, ' mã · ', count.new_products,
      ' mã mới · ', count.update_products, ' cập nhật · ', count.retained_products,
      ' mã cũ được giữ · ', count.new_names, ' tên hóa đơn mới · ', count.error, ' lỗi</div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Dòng</th><th>Mã / nhóm</th><th>Tên TĐP</th><th>Tên xuất hóa đơn</th><th>Kiểm tra</th></tr></thead><tbody>',
      visibleRows, '</tbody></table></div>',
      preview.rows.length > 200 ? '<div class="card-body muted">Hiển thị 200 dòng đầu; toàn bộ file vẫn được kiểm tra và nhập.</div>' : '',
      '<div class="card-body"><div class="code-note"><strong>Nguyên tắc:</strong> giữ nguyên giá mua, nhà cung cấp và các nhóm giá đang có; không xóa mã cũ. Tên xuất hóa đơn được dùng đúng theo file khách đã xác nhận.</div>',
      '<div class="form-actions"><button class="btn btn-primary" data-action="confirm-catalog-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận cập nhật danh mục</button></div>',
      preview.can_confirm ? '' : '<div class="code-note"><strong>Chưa thể nhập:</strong> sửa hết dòng lỗi rồi chọn lại file.</div>',
      '</div></div>'
    ]);
  }

  function kitchenImportReady() {
    var preview = state.kitchenImportPreview;
    if (!preview) return false;
    if (preview.can_confirm) return true;
    if (!preview.can_confirm_with_overrides) return false;
    return preview.plans.every(function (plan) {
      if (!plan.errors.length) return true;
      if (!plan.override_only || !plan.needs_meal_count) return false;
      var value = Number(state.kitchenMealCountOverrides[plan.plan_key]);
      return Number.isFinite(value) && Number.isInteger(value) && value > 0;
    });
  }

  function kitchenImportPreviewHtml() {
    var preview = state.kitchenImportPreview;
    if (!preview) return "";
    var planRows = preview.plans.map(function (plan) {
      var messages = plan.errors.concat(plan.warnings);
      var servingText = plan.menu_count > 1
        ? num(plan.meal_count) + ' suất tổng · ' + plan.menu_count + ' thực đơn × ' + num(plan.servings_per_menu) + ' suất'
        : num(plan.meal_count) + ' suất';
      var overrideValue = state.kitchenMealCountOverrides[plan.plan_key] || "";
      var overrideHtml = plan.needs_meal_count
        ? '<div class="form-field" style="margin-top:8px"><label>Số suất đã chốt (bắt buộc)</label>' +
          '<input type="number" min="1" step="1" inputmode="numeric" required ' +
          'data-kitchen-meal-override="' + esc(plan.plan_key) + '" value="' + esc(overrideValue) + '" ' +
          'placeholder="Nhập tổng số suất của nhóm này"></div>'
        : '';
      var tagClass = plan.errors.length ? (plan.override_only ? 'tag-warn' : 'tag-red') : 'tag-ok';
      return '<div class="group-line"><div><strong>' + esc(plan.kitchen) + ' → XCOM ' +
        esc(plan.xcom_code) + '</strong><span>' + dateVN(plan.work_date) + ' · ' + esc(plan.shift) + ' · ' + servingText +
        ' · dòng ' + plan.source_row_start + '–' + plan.source_row_end + ' · ' +
        plan.items.length + ' nguyên liệu</span><span>' + esc(plan.menu_name || "Chưa ghi tên món") +
        '</span></div><div><span class="tag ' + tagClass + '">' +
        (plan.status === "update" ? "Cập nhật" : "Thêm mới") + '</span><div class="muted">' +
        esc(messages.join(" · ")) + '</div>' + overrideHtml + '</div></div>';
    }).join("");
    var count = preview.counts;
    var ready = kitchenImportReady();
    var missingCount = preview.plans.filter(function (plan) { return plan.needs_meal_count; }).length;
    var dateLabel = preview.weekly ? 'Tuần bắt đầu Thứ Hai ' : 'Ngày ';
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Xem trước file ',
      esc(preview.filename), '</h3><p>', dateLabel, dateVN(preview.work_date),
      ' · chỉ ghi dữ liệu sau khi xác nhận</p></div><button class="btn btn-small btn-outline" data-action="cancel-kitchen-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.plans, ' nhóm bếp/ca · ', count.items,
      ' nguyên liệu · ', count.new, ' thêm · ', count.update, ' cập nhật · ', count.errors,
      ' nhóm lỗi · ', count.warnings, ' nhóm cần lưu ý',
      missingCount ? ' · ' + missingCount + ' nhóm phải nhập số suất' : '',
      '</div><div class="group-list" style="margin-top:16px">',
      planRows, '</div><div class="form-actions"><button class="btn btn-primary" data-action="confirm-kitchen-import" ',
      ready ? '' : 'disabled', '>Xác nhận nạp file xưởng cơm</button></div>',
      ready ? '<div class="code-note"><strong>Kiểm soát:</strong> mỗi trang Excel T2–CN được ghi đúng ngày trong tuần; phần mềm ưu tiên số lượng đã chốt trong file và không tạo trùng khi nạp lại.</div>' :
        (preview.can_confirm_with_overrides
          ? '<div class="code-note"><strong>Cần nhập số suất:</strong> điền số nguyên lớn hơn 0 cho tất cả nhóm file đang để trống; nút xác nhận sẽ tự mở.</div>'
          : '<div class="code-note"><strong>Chưa thể nhập:</strong> file còn lỗi mã hàng/tên hàng; xem thông báo đỏ và sửa đúng file trước khi chọn lại.</div>'),
      '</div></div>'
    ]);
  }

  function mealAttendancePreviewHtml() {
    var preview = state.mealAttendancePreview;
    if (!preview) return "";
    var visibleRows = preview.rows.slice(0, 200).map(function (item) {
      var messages = item.errors.concat(item.warnings);
      var tagClass = item.errors.length ? "tag-red" : item.warnings.length ? "tag-warn" : "tag-ok";
      var statusText = item.status === "new" ? "Thêm" : item.status === "update" ? "Cập nhật" : "Không đổi";
      return '<tr class="' + (item.errors.length ? 'row-error' : item.warnings.length ? 'row-warning' : '') + '"><td>' + dateVN(item.work_date) + '</td><td><strong>' + esc(item.kitchen) +
        '</strong></td><td>' + esc(item.shift) + '</td><td class="num-cell"><strong>' +
        num(item.actual_count) + '</strong></td><td class="num-cell">' +
        (item.ordered_count ? num(item.ordered_count) : "—") + '</td><td><span class="tag ' +
        tagClass + '">' + statusText + '</span><div class="muted">' + esc(messages.join(" · ")) +
        '</div></td></tr>';
    }).join("");
    var count = preview.counts;
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Xem trước chấm suất ăn</h3><p>File ',
      esc(preview.filename), ' · kỳ ', esc(preview.periods.join(", ")),
      ' · số ăn thực tế lưu riêng, không thay số suất đã đặt cho bếp</p></div><button class="btn btn-small btn-outline" data-action="cancel-meal-attendance-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.items, ' dòng ngày/bếp/ca · ', count.dates,
      ' ngày · ', count.kitchens, ' bếp · ', count.new, ' thêm · ', count.update, ' cập nhật · ',
      count.unchanged, ' không đổi · ', count.error, ' lỗi · Tổng thực ăn ', num(preview.totals.actual),
      ' suất</div></div><div class="table-wrap"><table><thead><tr><th>Ngày</th><th>Bếp</th><th>Ca</th><th>Thực ăn</th><th>Số đặt</th><th>Kiểm tra</th></tr></thead><tbody>',
      visibleRows, '</tbody></table></div>',
      preview.rows.length > 200 ? '<div class="card-body muted">Hiển thị 200 dòng đầu; toàn bộ file vẫn được kiểm tra.</div>' : '',
      '<div class="card-body"><div class="form-actions"><button class="btn btn-primary" data-action="confirm-meal-attendance-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận nạp chấm suất</button></div>',
      preview.can_confirm ? '<div class="code-note"><strong>Kiểm soát:</strong> nạp lại cùng tháng sẽ cập nhật/thay thế đúng dữ liệu tháng, không cộng trùng.</div>' :
        '<div class="code-note"><strong>Chưa thể nhập:</strong> sửa dòng âm hoặc cấu trúc lỗi rồi chọn lại file.</div>',
      '</div></div>'
    ]);
  }

  function attendanceImportPreviewHtml() {
    var preview = state.attendanceImportPreview;
    if (!preview) return "";
    var count = preview.counts;
    var warningRows = (preview.warnings || []).slice(0, 30).map(function (message) {
      return '<div class="group-line"><div><strong>Cần lưu ý</strong><span>' + esc(message) +
        '</span></div><span class="tag tag-warn">Cảnh báo</span></div>';
    }).join("");
    return html([
      '<div class="card" style="margin:0 0 18px"><div class="card-head"><div><h3>Xem trước chấm công ',
      esc(preview.month), '</h3><p>File ', esc(preview.filename),
      ' · chưa ghi dữ liệu cho đến khi xác nhận</p></div><button class="btn btn-small btn-outline" data-action="cancel-attendance-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.staff, ' nhân sự · ',
      count.attendance_entries, ' ngày công · ', count.payroll_overrides, ' khoản lương chốt · ',
      count.labor_cost_entries, ' dòng chi phí bếp · ', count.warnings, ' cảnh báo</div>',
      warningRows ? '<div class="group-list" style="margin-top:16px">' + warningRows + '</div>' : '',
      '<div class="form-actions"><button class="btn btn-primary" data-action="confirm-attendance-import">Xác nhận thay dữ liệu nhập file của kỳ ',
      esc(preview.month), '</button></div>',
      '<div class="code-note"><strong>Kiểm soát:</strong> nạp lại file sửa/đổi tên sẽ thay đúng ảnh chụp của kỳ; các dòng chấm công và khoản lương đã sửa tay được giữ nguyên.</div>',
      '</div></div>'
    ]);
  }

  function openingImportPreviewHtml() {
    var preview = state.openingImportPreview;
    if (!preview) return "";
    var count = preview.counts;
    var visibleRows = preview.rows.slice(0, 200).map(function (item) {
      var messages = item.errors.concat(item.warnings);
      var statusText = item.errors.length ? "Lỗi" : item.status === "update" ? "Cập nhật" : "Thêm tồn";
      if (item.create_product) statusText += " + mã mới";
      var tagClass = item.errors.length ? "tag-red" : item.warnings.length ? "tag-warn" : "tag-ok";
      return '<tr class="' + (item.errors.length ? 'row-error' : item.warnings.length ? 'row-warning' : '') + '"><td><strong>' + esc(item.product_code || "—") + '</strong><div class="muted">' +
        esc(item.product_name) + '</div></td><td>' + esc(item.source_rows.join(", ")) +
        '<div class="muted">' + esc(item.warehouse_codes.join(", ") || "Không có mã kho") +
        '</div></td><td class="num-cell"><strong>' + num(item.qty) + '</strong> ' + esc(item.unit) +
        '</td><td class="num-cell">' + money(item.unit_cost) + '</td><td class="num-cell"><strong>' +
        money(item.amount) + '</strong></td><td><span class="tag ' + tagClass + '">' +
        esc(statusText) + '</span><div class="muted">' + esc(messages.join(" · ")) + '</div></td></tr>';
    }).join("");
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Xem trước tồn đầu kỳ ',
      esc(preview.period), '</h3><p>File ', esc(preview.filename), ' · trang Excel ', esc(preview.sheet),
      ' · chỉ ghi dữ liệu sau khi xác nhận</p></div><button class="btn btn-small btn-outline" data-action="cancel-opening-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.source_rows, ' dòng nguồn → ', count.items,
      ' mã TĐP · ', count.new_products, ' mã mới · ', count.negative, ' mã tồn âm · ', count.warning,
      ' mã cần lưu ý · ', count.error, ' lỗi · Tổng số lượng ', num(preview.totals.qty),
      ' · Tổng tiền ', money(preview.totals.amount), '</div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Mã / tên TĐP</th><th>Dòng / mã kho</th><th>Tồn</th><th>Đơn giá vốn</th><th>Giá trị</th><th>Kiểm tra</th></tr></thead><tbody>',
      visibleRows, '</tbody></table></div>',
      preview.rows.length > 200 ? '<div class="card-body muted">Hiển thị 200 mã cần xem đầu tiên; toàn bộ file vẫn được kiểm tra và gộp.</div>' : '',
      '<div class="card-body"><div class="form-actions"><button class="btn btn-primary" data-action="confirm-opening-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận nạp tồn đầu kỳ</button></div>',
      preview.can_confirm ? '<div class="code-note"><strong>Kiểm soát:</strong> mã trùng được cộng theo Mã TĐP; số âm và Thành tiền sổ sách được giữ nguyên. Mã mới được thêm vào danh mục nhưng chưa có nhà cung cấp mặc định.</div>' :
        '<div class="code-note"><strong>Chưa thể nhập:</strong> sửa các dòng lỗi trong Excel rồi chọn lại file.</div>',
      '</div></div>'
    ]);
  }

  function bkImportPreviewHtml() {
    var preview = state.bkImportPreview;
    if (!preview) return "";
    var count = preview.counts || {};
    var visibleRows = (preview.rows || []).slice(0, 200).map(function (item) {
      var messages = (item.errors || []).concat(item.warnings || []);
      var tagClass = item.errors.length ? "tag-red" : item.warnings.length ? "tag-warn" : "tag-ok";
      var statusText = item.errors.length ? "Lỗi" : "Sẵn sàng nhập";
      return '<tr class="' + (item.errors.length ? 'row-error' : item.warnings.length ? 'row-warning' : '') + '"><td>' + item.sourceRow + '</td><td>' + dateVN(item.documentDate) +
        '<div class="muted">' + esc(item.sourceType) + ' · ' + esc(item.sourceReference) +
        ' · dòng ' + num(item.sourceLine) + '</div></td><td><strong>' + esc(item.productCode || "—") +
        '</strong><div class="muted">' + esc(item.productName) + '</div></td><td class="num-cell">' +
        num(item.qty) + ' ' + esc(item.unit) + '</td><td class="num-cell">' + money(item.unitCost) +
        '</td><td class="num-cell"><strong>' + money(item.amount) + '</strong></td><td><span class="tag ' +
        tagClass + '">' + esc(statusText) + '</span><div class="muted">' +
        esc(messages.join(" · ")) + '</div></td></tr>';
    }).join("");
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Kiểm tra bảng kê trước khi nhập kho</h3><p>File ',
      esc(preview.filename),
      '</p></div><button class="btn btn-small btn-outline" data-action="cancel-bk-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', num(count.sourceRows), ' dòng · ',
      num(count.readyRows), ' sẵn sàng · ', num(count.errorRows), ' lỗi · ',
      num(count.duplicateGroups), ' nhóm trùng · Tổng số lượng ', num(preview.totals && preview.totals.qty),
      ' · Tổng tiền ', money(preview.totals && preview.totals.amount), '</div>',
      '<div class="code-note"><strong>Nguồn dữ liệu:</strong> ', esc(preview.policy),
      ' File này chưa làm thay đổi kho; nếu chọn lại đúng file, phần mềm sẽ không cộng hàng hai lần.</div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Dòng</th><th>Nguồn</th><th>Mã / tên hàng</th><th>Số lượng</th><th>Giá vốn</th><th>Thành tiền</th><th>Kiểm tra</th></tr></thead><tbody>',
      visibleRows, '</tbody></table></div>',
      '<div class="card-body"><div class="form-actions"><button class="btn btn-primary" data-action="confirm-bk-import" ',
      preview.canConfirm ? '' : 'disabled', '>', preview.alreadyPosted ? 'Xem lại lần nhập trước' : 'Xác nhận nhập bảng kê vào kho',
      '</button></div>',
      preview.canConfirm ? '<div class="code-note"><strong>Sau khi xác nhận:</strong> các dòng được cộng một lần vào sổ vật tư hàng hóa. Muốn hủy phải dùng nút Hoàn tác và ghi rõ lý do.</div>' :
        '<div class="code-note"><strong>Chưa thể nhập:</strong> sửa toàn bộ dòng lỗi trong Excel rồi chọn lại file.</div>',
      '</div></div>'
    ]);
  }

  function bkDocumentsHtml() {
    var items = state.bkDocuments || [];
    if (!items.length) return "";
    var rows = items.map(function (item) {
      var isPosted = item.status === "posted";
      return '<tr><td><strong>#' + num(item.id) + '</strong><div class="muted">' +
        esc(item.filename) + '</div></td><td>' + num(item.rowCount) + '</td><td class="num-cell">' +
        num(item.qtyTotal) + '</td><td class="num-cell">' + money(item.amountTotal) +
        '</td><td><span class="tag ' + (isPosted ? 'tag-ok' : 'tag-warn') + '">' +
        (isPosted ? 'Đã nhập kho' : 'Đã hoàn tác') + '</span><div class="muted">' +
        esc(isPosted ? item.confirmedAt : (item.reversalDate || item.reversedAt || "")) +
        (item.reversalReason ? ' · ' + esc(item.reversalReason) : '') + '</div></td><td>' +
        (isPosted ? '<button class="btn btn-small btn-outline" data-action="reverse-bk-import" data-document-id="' +
          item.id + '">Hoàn tác bảng kê</button>' : '—') + '</td></tr>';
    }).join("");
    return '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Lịch sử nhập bảng kê</h3>' +
      '<p>Lịch sử luôn được giữ lại. Khi hoàn tác, phần mềm ghi một dòng điều chỉnh ngược thay vì xóa dữ liệu cũ.</p></div></div>' +
      '<div class="table-wrap"><table><thead><tr><th>File bảng kê</th><th>Dòng</th><th>Tổng số lượng</th>' +
      '<th>Tổng tiền</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>' + rows +
      '</tbody></table></div></div>';
  }

  function payablesImportPreviewHtml() {
    var preview = state.payablesImportPreview;
    if (!preview) return "";
    var count = preview.counts;
    var issueRows = preview.issues || [];
    var previewRows = issueRows.length ? issueRows : (preview.rows || []);
    var visibleRows = previewRows.slice(0, 120).map(function (item) {
      var messages = item.errors.concat(item.warnings);
      var tagClass = item.errors.length ? "tag-red" : item.warnings.length ? "tag-warn" : "tag-ok";
      return '<tr class="' + (item.errors.length ? 'row-error' : item.warnings.length ? 'row-warning' : '') + '"><td>' + item.source_row + '</td><td>' + dateVN(item.purchase_date) +
        '</td><td><strong>' + esc(item.supplier || "—") + '</strong><div class="muted">' +
        esc(item.kitchen) + '</div></td><td>' + esc(item.item_name) + '</td><td class="num-cell">' +
        num(item.actual_qty) + ' ' + esc(item.unit) + '</td><td class="num-cell"><strong>' +
        money(item.amount) + '</strong></td><td><span class="tag ' + tagClass + '">' +
        (item.status === "skip" ? "Bỏ qua" : item.errors.length ? "Lỗi" : "Sẵn sàng") +
        '</span><div class="muted">' + esc(messages.join(" · ")) + '</div></td></tr>';
    }).join("");
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Xem trước công nợ phải trả</h3><p>File ',
      esc(preview.filename), ' · trang Excel ', esc(preview.sheet),
      ' · khi xác nhận sẽ thay TOÀN BỘ lịch sử công nợ phải trả hiện có</p></div><button class="btn btn-small btn-outline" data-action="cancel-payables-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.total, ' dòng · ', count.ready,
      ' sẵn sàng · ', count.suppliers, ' nhà cung cấp · ', count.skipped, ' bỏ qua · ', count.errors,
      ' lỗi · Tổng số lượng ', num(preview.totals.actual_qty),
      ' · Tổng tiền ', money(preview.totals.amount), '</div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Dòng</th><th>Ngày</th><th>Nhà cung cấp / bếp</th><th>Hàng</th><th>Thực tế</th><th>Thành tiền</th><th>Kiểm tra</th></tr></thead><tbody>',
      visibleRows, '</tbody></table></div>',
      preview.preview_truncated ? '<div class="card-body muted">Ưu tiên hiển thị các dòng bỏ qua/cảnh báo/lỗi; toàn bộ file vẫn được kiểm tra trước khi nhập.</div>' : '',
      '<div class="card-body"><div class="form-actions"><button class="btn btn-primary" data-action="confirm-payables-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận thay toàn bộ lịch sử công nợ</button></div>',
      preview.can_confirm ? '<div class="code-note"><strong>Phạm vi thay thế:</strong> file này là ảnh chụp tổng hợp có thẩm quyền; hệ thống xóa ảnh chụp công nợ lịch sử cũ rồi ghi đúng dữ liệu đang xem trước, không cộng lặp.</div>' :
        '<div class="code-note"><strong>Chưa thể nhập:</strong> cần ít nhất một dòng hợp lệ và không được còn dòng phát sinh thiếu ngày, nhà cung cấp hoặc giá mua.</div>',
      '</div></div>'
    ]);
  }

  function emptyBatch(title, description) {
    return '<div class="card fade-in"><div class="empty"><div class="empty-icon">▤</div><h3>' +
      esc(title) + "</h3><p>" + esc(description) +
      '</p><div class="empty-actions"><button class="btn btn-primary" data-action="choose-excel">Nạp file Excel</button>' +
      '<button class="btn btn-outline" data-action="new-batch">Tạo đơn nhập tay</button></div></div></div>';
  }

  function exportUrl(kind) {
    return state.batchId ? "/api/export/" + kind + "/" + state.batchId : "#";
  }

  function batchesInRange(fromDate, toDate) {
    return (state.data && state.data.batches || []).filter(function (batch) {
      return (!fromDate || batch.work_date >= fromDate) && (!toDate || batch.work_date <= toDate);
    });
  }

  function printingSelectionRows() { return state.printingRows || []; }

  async function loadPrintingRows() {
    var key = [state.printingDocument,state.printingFrom,state.printingTo,state.printingCustomer].join("|");
    if (state.printingListLoading && state.printingListKey === key) return;
    var serial = ++state.printingListSerial;
    state.printingListKey = key;
    state.printingListLoading = true;
    state.printingListError = "";
    state.printingRows = null;
    try {
      var data = await api("/api/documents/list?kind=" + encodeURIComponent(state.printingDocument) +
        "&from=" + encodeURIComponent(state.printingFrom) + "&to=" + encodeURIComponent(state.printingTo) +
        "&customer=" + encodeURIComponent(state.printingCustomer));
      if (serial !== state.printingListSerial) return;
      state.printingRows = data.rows;
    } catch (error) {
      if (serial !== state.printingListSerial) return;
      state.printingRows = []; state.printingListError = error.message;
    } finally {
      if (serial === state.printingListSerial) {
        state.printingListLoading = false;
        if (state.view === "printing") renderPrinting();
      }
    }
  }

  function renderHome() {
    var d = state.data;
    var batches = batchesInRange(state.homeFrom, state.homeTo);
    var orderCount = batches.reduce(function (total, batch) { return total + n(batch.order_count); }, 0);
    var lineCount = batches.reduce(function (total, batch) { return total + n(batch.line_count); }, 0);
    var s = d.summary.totals;
    var hasBatch = Boolean(d.batch);
    var errorCount = hasBatch ? n(s.errors) : 0;
    var warningCount = hasBatch ? n(s.warnings) : 0;
    var approved = hasBatch && d.batch.status === "approved";
    var currentText = hasBatch
      ? "Đơn đang chọn: " + dateVN(d.batch.work_date) + " · " + d.orders.length + " dòng"
      : "Chưa có đơn hàng được chọn";
    var reviewText = !hasBatch
      ? "Chưa có đơn để hoàn thiện"
      : approved
        ? "Đã duyệt · doanh thu " + money(s.revenue) + " · lợi nhuận " + money(s.profit)
        : errorCount
          ? errorCount + " dòng còn thiếu hoặc sai dữ liệu"
          : warningCount
            ? warningCount + " dòng cần xem lại trước khi duyệt"
            : "Đã đủ dữ liệu để duyệt";
    content.innerHTML = html([
      '<div class="daily-range card fade-in"><div><span class="daily-range-label">Chọn thời gian cần làm việc</span>',
      '<strong>', esc(currentText), '</strong></div><div class="compact-controls">',
      '<label>Từ ngày <input id="homeFrom" class="input-date" type="date" value="', esc(state.homeFrom), '"></label>',
      '<label>Đến ngày <input id="homeTo" class="input-date" type="date" value="', esc(state.homeTo), '"></label>',
      '</div></div>',
      '<div class="daily-action-grid fade-in">',
      '<section class="daily-action-card"><div class="daily-action-number">1</div><div><h3>Tạo phiếu đặt hàng</h3>',
      '<p>Nhập file Excel. File hợp lệ tải sau cùng là file đang dùng.</p>',
      '<strong class="daily-action-total">', num(orderCount), ' phiếu theo bếp · ', num(lineCount), ' dòng</strong></div>',
      '<button class="btn btn-primary" data-action="choose-excel">Chọn file Excel</button></section>',
      '<section class="daily-action-card"><div class="daily-action-number">2</div><div><h3>In đơn hàng</h3>',
      '<p>Chọn in tất cả hoặc chọn từng đơn trong khoảng ngày.</p></div>',
      '<div class="form-actions"><button class="btn btn-outline" data-view="deliveries" ', hasBatch ? '' : 'disabled', '>Xem phiếu giao</button>',
      '<button class="btn btn-primary" data-action="open-print-workspace" data-document="deliveries" ', hasBatch ? '' : 'disabled', '>Chọn đơn để in</button></div></section>',
      '<section class="daily-action-card"><div class="daily-action-number">3</div><div><h3>Bảng kê và biên nhận</h3>',
      '<p>Xem ngay trên phần mềm, chọn phiếu cần in hoặc tải Excel.</p></div>',
      '<button class="btn btn-primary" data-action="open-print-workspace" data-document="purchases" ', hasBatch ? '' : 'disabled', '>Xem bảng kê và biên nhận</button></section>',
      '<section class="daily-action-card ', errorCount ? 'has-error' : approved ? 'is-done' : '', '"><div class="daily-action-number">4</div><div><h3>Duyệt đơn</h3>',
      '<p>', esc(reviewText), '</p></div>',
      '<button class="btn ', errorCount ? 'btn-outline' : 'btn-primary', '" data-view="orders" ', hasBatch ? '' : 'disabled', '>',
      approved ? 'Xem đơn đã duyệt' : errorCount ? 'Sửa các dòng đang thiếu' : 'Kiểm tra và duyệt', '</button></section>',
      '</div>',
      batches.length
        ? '<div class="daily-range-result">Trong khoảng đã chọn có <strong>' + batches.length + ' ngày dữ liệu</strong> và <strong>' + orderCount + ' phiếu theo bếp</strong>.</div>'
        : '<div class="daily-range-result is-empty">Khoảng ngày đã chọn chưa có đơn hàng.</div>'
    ]);
  }

  function renderOrders() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có đơn hàng", "Chọn file Excel đơn hàng đã hoàn thiện hoặc tạo đơn mới để nhập tay.");
      return;
    }
    // Keep all row nodes so filtering does not lose unsaved price edits.
    var orders = d.orders.slice().sort(function (a, b) {
      return Number(Boolean(b.errors.length)) - Number(Boolean(a.errors.length)) || a.id - b.id;
    });
    var approved = d.batch.status === "approved";
    var visibleTotals = orders.reduce(function (result, item) {
      result.ordered += n(item.qty);
      result.received += Math.max(n(item.actual_received) - n(item.damaged_qty) - n(item.supplier_return_qty), 0);
      result.delivered += Math.max(n(item.actual_delivered) - n(item.customer_return_qty), 0);
      result.cost += n(item.cost);
      result.revenue += n(item.revenue);
      result.total += n(item.total);
      return result;
    }, { ordered: 0, received: 0, delivered: 0, cost: 0, revenue: 0, total: 0 });
    var rows = orders.map(function (item, index) {
      var warnings = item.warnings || [];
      var errors = item.errors.length
        ? '<div class="errors">' + item.errors.map(esc).join("<br>") + "</div>"
        : warnings.length
          ? '<div class="warnings">' + warnings.map(esc).join("<br>") + "</div>"
          : '<span class="tag tag-ok">Đủ dữ liệu</span>';
      return html([
        '<tr data-order-row="', item.id, '" class="', item.errors.length ? "row-error" : warnings.length ? "row-warning" : "", '"><td>', index + 1, "</td><td><strong>",
        esc(item.kitchen), '</strong><div class="muted">', esc(item.contractor), "</div></td><td>",
        esc(item.product_code), '</td><td class="name-cell"><strong>', esc(item.product_name),
        item.invoice_nature === "2" ? ' <span class="tag tag-warn">Khuyến mại</span>' : '',
        '</strong><div class="muted">', esc(item.note), '</div></td><td class="num-cell">', stockQty(item.qty),
        '</td><td class="num-cell">', stockQty(item.actual_received), '<div class="muted">Hỏng/trả ',
        stockQty(n(item.damaged_qty) + n(item.supplier_return_qty)), ' · ròng ', stockQty(Math.max(n(item.actual_received) - n(item.damaged_qty) - n(item.supplier_return_qty), 0)),
        '</div></td><td class="num-cell">', stockQty(item.actual_delivered), '<div class="muted">Khách trả ', stockQty(item.customer_return_qty),
        ' · ròng ', stockQty(Math.max(n(item.actual_delivered) - n(item.customer_return_qty), 0)), '</div>',
        "</td><td>", esc(item.unit), "</td><td>", esc(item.supplier), '</td><td class="num-cell">',
        stockMoney(item.buy_price), '</td><td class="num-cell"><input class="quick-sell-price" type="number" min="0" step="1" value="',
        esc(item.sell_price), '" data-order-id="', item.id, '" data-original="', esc(item.sell_price),
        '" data-revision="', item.sell_price_revision || 1, '" aria-label="Giá bán ', esc(item.product_name), '" ',
        approved ? "disabled" : "", '>', item.sell_price_source === "manual_override"
          ? '<div><span class="tag tag-warn">Giá sửa tay · lần ' + (item.sell_price_revision || 1) + "</span></div>" : "",
        '</td><td><span class="tag tag-tax">', taxText(item.tax), '</span></td><td class="',
        item.profit < 0 ? "profit-negative" : "profit-positive", ' num-cell">', stockMoney(item.profit),
        "</td><td>", errors, '</td><td><div class="table-actions"><button class="icon-button" data-action="quick-add-order" data-id="',
        item.id, '" title="Thêm hàng vào đúng đơn này">＋</button><button class="icon-button" data-action="edit-order" data-id="',
        item.id, '" title="Sửa chi tiết">✎</button><button class="icon-button danger" data-action="delete-order" data-id="',
        item.id, '" title="Xóa">×</button><button class="btn btn-small btn-outline" data-action="settle-physical-order" data-id="',
        item.id, '">', item.physical_stage === "delivered" ? "Đã giao · mở lại" : "Chốt lượng đã giao", '</button></div></td></tr>'
      ]);
    }).join("");
    content.innerHTML = html([
      '<div class="import-zone round2-import fade-in"><div><strong>Nguồn: ', esc(d.batch.source_name),
      "</strong><p>Ngày làm việc ", dateVN(d.batch.work_date), " · Dữ liệu tự lưu ngay sau mỗi lần sửa</p></div>",
      '<div class="compact-controls"><button class="btn btn-outline" data-view="physical">Xem kho thực tế</button><button class="btn btn-outline" data-view="deliveries">Xem phiếu giao</button><button class="btn btn-outline" data-action="choose-excel">Chọn file đơn hàng khác</button>',
      '<button class="btn btn-outline" data-action="paste-orders">Dán nhiều dòng</button><button class="btn btn-outline" data-action="bulk-edit-orders">Sửa nhanh cả bảng</button><button class="btn btn-primary" data-action="approve-batch" ',
      approved || d.summary.totals.errors ? "disabled" : "", ">", approved ? "✓ Đã duyệt" : "Duyệt đơn hàng", "</button></div></div>",
      '<div class="toolbar round2-toolbar fade-in"><div class="toolbar-left"><div class="',
      d.summary.totals.errors ? "error-summary" : d.summary.totals.warnings ? "warning-summary" : "ok-summary", '">',
      d.summary.totals.errors
        ? "Còn " + d.summary.totals.errors + " dòng lỗi — bấm bút chì để sửa"
        : d.summary.totals.warnings
          ? d.summary.totals.warnings + " cảnh báo cần xác nhận · Không chặn duyệt"
          : "✓ " + d.orders.length + " dòng đã đủ mã, giá, nhà cung cấp và thuế",
      '</div><button class="btn btn-outline" data-action="first-order-error">Tới lỗi đầu tiên</button><select class="select" id="orderIssueFilter" aria-label="Lọc kiểm tra đơn">',
      [['all','Tất cả dòng'],['error','Chỉ lỗi chặn duyệt'],['warning','Chỉ cảnh báo (không chặn)'],['valid','Đủ dữ liệu']].map(function (entry) {
        return '<option value="' + entry[0] + '"' + (state.orderIssueFilter === entry[0] ? ' selected' : '') + '>' + entry[1] + '</option>';
      }).join(''), '</select></div><div class="toolbar-right"><input class="input-date" id="priceOverrideActor" value="',
      esc(state.priceOverrideActor), '" placeholder="Người sửa giá"><input class="input-date" id="priceOverrideReason" value="',
      esc(state.priceOverrideReason), '" placeholder="Lý do sửa giá"><button class="btn btn-outline" data-action="save-price-overrides" ',
      approved ? "disabled" : "", '>Lưu giá đã đổi</button><input class="input-date search-input" id="orderSearch" value="',
      esc(state.orderFilter), '" placeholder="Tìm mã, tên hàng, bếp, nhà cung cấp…"></div></div>',
      state.orderImportMessage ? '<div class="code-note">' + esc(state.orderImportMessage) + '</div>' : '',
      '<div class="totals-strip fade-in" id="orderVisibleTotals"><div><span>Tổng số đặt</span><strong>', stockQty(visibleTotals.ordered),
      '</strong></div><div><span>Tổng thực nhận</span><strong>', stockQty(visibleTotals.received),
      '</strong></div><div><span>Tổng thực giao</span><strong>', stockQty(visibleTotals.delivered),
      '</strong></div><div><span>Tổng tiền mua</span><strong>', stockMoney(visibleTotals.cost),
      '</strong></div><div><span>Tổng tiền bán</span><strong>', stockMoney(visibleTotals.total), '</strong></div></div>',
      '<div class="card fade-in"><div class="card-head"><div><h3>Đơn hàng đã kiểm tra</h3>',
      '<p>Lưu đơn là trừ kho thực tế theo số đặt, kể cả chưa giao. Chốt lượng đã giao để chuyển sang số giao ròng, không trừ lần hai.</p></div><span class="tag ',
      approved ? "tag-ok" : "tag-warn", '">', approved ? "Đã duyệt" : "Bản nháp", "</span></div>",
      '<div class="table-wrap round2-table" id="orderTable"><table><thead><tr><th>STT</th><th>Bếp / Nhà thầu</th><th>Mã hàng</th><th>Tên hàng</th>',
      "<th>Số đặt</th><th>Thực nhận</th><th>Thực giao</th><th>Đơn vị</th><th>Nhà cung cấp</th><th>Giá mua</th><th>Giá bán</th>",
      "<th>Thuế</th><th>Lợi nhuận</th><th>Kiểm tra</th><th></th></tr></thead><tbody>",
      rows || '<tr><td colspan="15"><div class="empty">Không có dòng phù hợp</div></td></tr>',
      '</tbody></table></div><div id="orderNoMatches" class="empty" hidden>Không có dòng phù hợp</div></div>'
    ]);
    applyOrderFilter();
  }

  function applyOrderFilter() {
    var search = state.orderFilter.trim().toLowerCase();
    var visible = (state.data.orders || []).filter(function (item) {
      var error = Boolean(item.errors.length), warning = Boolean((item.warnings || []).length);
      var match = [item.product_code, item.product_name, item.kitchen, item.contractor, item.supplier].join(' ').toLowerCase().indexOf(search) >= 0;
      return match && (state.orderIssueFilter === 'all' || state.orderIssueFilter === 'error' && error || state.orderIssueFilter === 'warning' && !error && warning || state.orderIssueFilter === 'valid' && !error && !warning);
    });
    var ids = new Set(visible.map(function (item) { return String(item.id); }));
    content.querySelectorAll('[data-order-row]').forEach(function (row) { row.hidden = !ids.has(row.dataset.orderRow); });
    var totals = document.getElementById('orderVisibleTotals');
    if (totals) totals.innerHTML = '<div><span>Số dòng đang xem</span><strong>' + visible.length + ' / ' + state.data.orders.length + '</strong></div>' +
      [['Tổng số đặt', stockQuantitySummary(visible, 'qty')],
       ['Tổng giao ròng', stockQuantitySummary(visible.map(function (item) { return { unit: item.unit, qty: Math.max(n(item.actual_delivered) - n(item.customer_return_qty), 0) }; }), 'qty')],
       ['Tổng tiền mua', stockMoney(visible.reduce(function (sum, item) { return sum + n(item.cost); }, 0))],
       ['Tổng tiền bán', stockMoney(visible.reduce(function (sum, item) { return sum + n(item.total); }, 0))]].map(function (pair) {
        return '<div><span>' + pair[0] + '</span><strong>' + esc(pair[1]) + '</strong></div>';
      }).join('');
    var empty = document.getElementById('orderNoMatches');
    if (empty) empty.hidden = visible.length > 0;
  }

  function groupBy(list, key) {
    return list.reduce(function (acc, item) {
      var value = typeof key === "function" ? key(item) : item[key];
      value = value || "CHƯA XÁC ĐỊNH";
      if (!acc[value]) acc[value] = [];
      acc[value].push(item);
      return acc;
    }, {});
  }

  async function fetchSupplierNeeds() {
    var requestedBatch = state.batchId;
    try {
      var result = await api("/api/supplier-needs/" + requestedBatch);
      if (requestedBatch !== state.batchId) return;
      state.supplierNeeds = result;
      if (state.view === "purchases") renderPurchases();
    } catch (error) { showToast(error.message, true); }
  }

  function purchaseOrderPreviewHtml() {
    var preview = state.purchaseOrderPreview;
    if (!preview) return "";
    var needsByOrder = {};
    ((state.supplierNeeds && state.supplierNeeds.rows) || []).forEach(function (item) {
      if (item.order_id != null) needsByOrder[String(item.order_id)] = item;
    });
    var issueRows = Array.isArray(preview.issues) ? preview.issues : [];
    var visibleRows = issueRows.length ? issueRows : (preview.items || preview.rows || []);
    var rows = visibleRows.map(function (item) {
      var source = needsByOrder[String(item.order_id)] || {};
      var errors = Array.isArray(item.errors) ? item.errors : [];
      var warnings = Array.isArray(item.warnings) ? item.warnings : [];
      var canonical = item.format === "customer_canonical";
      return '<tr class="' + (errors.length ? 'row-error' : warnings.length ? 'row-warning' : '') + '"><td>' +
        esc(item.source_sheet || "—") + '<div class="muted">Dòng ' + esc(item.source_row || "—") +
        '</div></td><td><strong>' + esc(item.product_name || source.product_name || "—") +
        '</strong><div class="muted">' + (item.line_kind === 'replacement_deduction' ? esc(item.note) + ' · ' + money(item.amount) : esc(item.product_code || source.product_code || "—")) +
        ' · ' + esc(item.kitchen || source.kitchen || "—") + '</div></td><td class="num-cell">' +
        num(canonical ? item.base_qty : (item.demand_qty == null ? source.demand_qty : item.demand_qty)) +
        ' ' + esc(item.unit || source.unit || "") + '</td><td class="num-cell">' +
        (canonical ? [item.damaged_qty, item.added_qty, item.reduced_qty, item.missing_qty].map(num).join(" / ") : num(item.physical_stock_used)) +
        '</td><td class="num-cell"><strong>' + num(canonical ? item.actual_qty : item.order_qty) +
        '</strong></td><td><strong>' + esc(item.supplier || "—") +
        '</strong></td><td class="num-cell">' + money(item.buy_price) + '</td><td>' +
        (errors.length ? '<span class="tag tag-red">Cần sửa</span><div class="errors">' +
          esc(errors.join(" · ")) + '</div>' : warnings.length ? '<span class="tag tag-warn">Cần bổ sung</span><div class="warnings">' +
          esc(warnings.join(" · ")) + '</div>' : '<span class="tag tag-ok">Sẵn sàng</span>') + '</td></tr>';
    }).join("");
    var totalRows = n(preview.count == null ? (preview.items || preview.rows || []).length : preview.count);
    var errorRows = n(preview.error_rows == null ? (preview.counts && preview.counts.error) : preview.error_rows);
    var warningRows = n(preview.warning_rows);
    return html([
      '<div class="card purchase-preview fade-in"><div class="card-head"><div><h3>Kiểm tra file trước khi ghi</h3><p>',
      esc(preview.filename || "File đặt nhà cung cấp đã chỉnh"), ' · chưa thay đổi dữ liệu cho đến khi bấm xác nhận</p></div>',
      '<button class="btn btn-small btn-outline" data-action="cancel-purchase-order-import">Bỏ file này</button></div>',
      '<div class="card-body"><div class="status-bar">', totalRows, ' dòng · Đặt nhà cung cấp ', num(preview.total_qty),
      ' · Thành tiền ', money(preview.total_amount), ' · ', errorRows, ' dòng lỗi · ', warningRows, ' cảnh báo</div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Vị trí</th><th>Hàng / bếp</th><th>Số lượng</th>',
      '<th>Hỏng / thêm / giảm / thiếu</th><th>Số thực tế</th><th>Nhà cung cấp</th><th>Giá mua</th><th>Kiểm tra</th></tr></thead><tbody>',
      rows || '<tr><td colspan="8"><div class="empty">File không có dòng để nhập.</div></td></tr>',
      '</tbody></table></div>',
      issueRows.length ? '<div class="card-body muted">Đang ưu tiên hiện toàn bộ dòng lỗi/cảnh báo; các dòng hợp lệ vẫn được kiểm tra.</div>' : '',
      '<div class="card-body"><div class="simple-warning"><strong>Trước khi xác nhận:</strong> SL thực tế = Số lượng + Thêm − Hỏng − Giảm − Thiếu; Thành tiền được làm tròn VND từ SL thực tế × Giá mua. Mua ngoài có lượng dương bắt buộc có giá mua; Kho được phép giá 0. Đơn khách và giá bán không bị thay đổi.</div>',
      '<div class="form-actions"><button class="btn btn-primary" data-action="confirm-purchase-order-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận nạp file đặt nhà cung cấp</button></div>',
      preview.can_confirm ? '' : '<div class="code-note"><strong>Chưa thể nạp:</strong> mở Excel sửa các dòng màu đỏ, lưu file rồi chọn lại.</div>',
      '</div></div>'
    ]);
  }

  function renderPurchases() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có dữ liệu đặt hàng", "Nạp đơn để hệ thống tự gộp số lượng theo nhà cung cấp.");
      return;
    }
    if (!state.supplierNeeds) {
      content.innerHTML = '<div class="loading-panel"><div class="spinner"></div><strong>Đang nạp kế hoạch đặt nhà cung cấp…</strong></div>';
      setTimeout(fetchSupplierNeeds, 0);
      return;
    }
    var needs = state.supplierNeeds;
    var checklistCounts = needs.checklist_counts || { pending: 0, reopened: 0, ordered: 0 };
    var checklistOpen = n(checklistCounts.pending) + n(checklistCounts.reopened);
    var cards = (needs.checklist || []).map(function (supplier) {
      var groupIndex = needs.groups.findIndex(function (group) { return group.supplier_key === supplier.supplier_key; });
      var group = supplierPresentation(needs.groups[groupIndex]);
      var supplier = group.supplier, items = group.items;
      var rawLineCount = group.raw_line_count == null ? items.length : group.raw_line_count;
      var orderStatus = group.order_status || "pending";
      var statusText = orderStatus === "ordered" ? "Đã đặt" : orderStatus === "reopened" ? "Cần đặt lại" : "Chưa đặt";
      var statusClass = orderStatus === "ordered" ? "tag-ok" : orderStatus === "reopened" ? "tag-warn" : "tag-red";
      var reopenControl = orderStatus === "ordered"
        ? '<button class="btn btn-small btn-link" data-action="set-supplier-order-status" data-supplier-key="' +
          esc(group.supplier_key || supplier) + '" data-status="reopened" data-revision="' +
          n(group.order_status_revision) + '">Mở lại</button>'
        : '';
      return '<div class="group-card supplier-order-card is-' + orderStatus + '" data-supplier-key="' +
        esc(group.supplier_key || supplier) + '" data-order-status="' + orderStatus + '"><div class="group-title supplier-order-title"><div class="supplier-order-summary"><strong>Nhà cung cấp ' + esc(supplier.toUpperCase()) +
        "</strong><span>" + esc(group.kitchen) + " · " + rawLineCount + " dòng gốc · " + items.length +
        ' dòng gửi</span></div><div class="supplier-order-actions"><span class="tag ' + statusClass + '">' + statusText +
        '</span><button class="btn btn-small btn-primary" data-action="copy-supplier-image" data-group-index="' +
        groupIndex + '">Sao chép ảnh</button>' + reopenControl + '</div></div><div class="group-total"><span>Tổng đặt nhà cung cấp</span><strong>' +
        esc(stockQuantitySummary(items, 'order_qty')) + (group.total_amount != null ? " · " + stockMoney(group.total_amount) : "") + '</strong></div>' +
        '<details class="supplier-lines"><summary>Xem ' + items.length + ' dòng đặt hàng</summary><div class="table-wrap round2-table"><table><thead><tr><th>Bếp</th><th>Hàng</th><th>SL đặt</th><th>ĐVT</th><th>Giá mua</th><th>Thành tiền</th><th>Ghi chú</th></tr></thead><tbody>' +
        items.map(function (item) { return '<tr><td>' + esc(item.kitchen) + '</td><td>' + esc(item.product_name) + '</td><td>' + stockQty(item.order_qty) + '</td><td>' + esc(item.unit) + '</td><td>' + (item.mixed_buy_prices ? 'Nhiều giá' : stockMoney(item.buy_price)) + '</td><td>' + stockMoney(item.amount) + '</td><td>' + esc(item.note) + '</td></tr>'; }).join('') +
        '</tbody></table></div></details></div>';
    }).join("");
    content.innerHTML = '<div class="supplier-order-overview fade-in"><div><strong>' + checklistOpen +
      ' nhà cung cấp chưa đặt</strong><span>' + n(checklistCounts.ordered) + ' đã đặt · tổng ' +
      (needs.checklist || []).length + ' nhà cung cấp</span></div><small>Sao chép thành công toàn bộ ảnh của NCC mới ghi nhận đã đặt.</small></div>' +
      '<div class="supplier-order-list fade-in">' +
      (cards || '<div class="card"><div class="empty">Tồn hiện có đã đáp ứng toàn bộ nhu cầu.</div></div>') + "</div>";
    content.innerHTML += '<details class="operation-details fade-in"><summary>Chỉnh số lượng và giá mua bằng Excel</summary><div class="operation-details-body">' +
      '<div class="compact-controls"><button class="btn btn-outline" data-action="download-document" data-url="' +
      exportUrl("suppliers") + '">Tải file để chỉnh</button><button class="btn btn-primary" data-action="choose-purchase-order-file">Chọn file đã chỉnh</button></div>' +
      purchaseOrderPreviewHtml() +
      '<div class="code-note" style="margin-top:14px">File Excel chỉ cập nhật phần mua và công nợ phải trả; không làm thay đổi đơn khách.</div>' +
      '</div></details>';
    if ((needs.money_adjustments || []).length) {
      content.innerHTML += '<div class="card purchase-money-adjustments"><div class="card-head"><h3>Trừ tiền mua hộ do hàng hỏng</h3></div><div class="card-body"><p>Các khoản này trừ vào công nợ phải trả khi đơn được duyệt. Doanh thu và số lượng hàng giữ nguyên.</p><div class="table-wrap"><table><thead><tr><th>NCC</th><th>Bếp</th><th>Nội dung</th><th>Khoản trừ</th></tr></thead><tbody>' +
        needs.money_adjustments.map(function (item) { return '<tr><td>' + esc(item.supplier) + '</td><td>' + esc(item.kitchen) + '</td><td>' + esc(item.product_name) + '</td><td class="num-cell">' + money(item.amount) + '</td></tr>'; }).join('') +
        '</tbody><tfoot><tr><td colspan="3">Tổng khoản trừ</td><td class="num-cell">' + money(needs.money_adjustments.reduce(function (total, item) { return total + n(item.amount); }, 0)) + '</td></tr></tfoot></table></div></div></div>';
    }
  }

  function supplierPresentation(group) {
    var related = state.supplierNeeds.groups.filter(function (item) { return item.supplier_key === group.supplier_key; });
    return Object.assign({}, group, {
      kitchen: related.length > 1 ? 'Nhiều bếp · giữ từng dòng theo quy tắc NCC' : group.kitchen,
      items: related.reduce(function (rows, item) { return rows.concat(item.items); }, []),
      raw_line_count: related.reduce(function (sum, item) { return sum + item.raw_line_count; }, 0),
      total_amount: related.reduce(function (sum, item) { return sum + n(item.total_amount); }, 0)
    });
  }

  async function loadPhysicalStock() {
    var serial = ++state.physicalStockSerial;
    state.physicalStock = null;
    if (state.view === 'physical') content.innerHTML = '<div class="loading-panel">Đang đọc kho thực tế…</div>';
    try {
      var payload = await api('/api/physical-stock?search=' + encodeURIComponent(state.physicalSearch) + '&status=' + state.physicalStatus);
      if (serial !== state.physicalStockSerial) return;
      state.physicalStock = payload;
      if (state.view === 'physical') renderPhysicalStock();
    } catch (error) {
      if (serial !== state.physicalStockSerial) return;
      if (state.view === 'physical') content.innerHTML = '<div class="code-note">' + esc(error.message) + '<button class="btn" data-action="reload-physical">Thử lại</button></div>';
    }
  }

  function renderPhysicalStock() {
    var data = state.physicalStock;
    if (!data) { loadPhysicalStock(); return; }
    var labels = { available: 'Còn hàng', empty: 'Hết hàng', short: 'Thiếu hàng', uninitialized: 'Chưa khai tồn đầu', review: 'Cần đối chiếu' };
    var entry = state.physicalEntry;
    var form = entry ? '<div class="card card-body"><h3>' + (entry.kind === 'opening' ? 'Khai/sửa tồn đầu ngày' : 'Nhập/điều chỉnh thực tế') + ' · ' + esc(entry.item.product_name) + '</h3>' +
      '<p>Tồn đầu là lượng có trước các đơn của ngày bắt đầu. Chỉ nhập số đã kiểm đếm; đơn mua NCC/hóa đơn không tự tăng kho này. Điều chỉnh giảm dùng số âm, luôn ghi rõ lý do.</p>' +
      '<form id="physicalStockForm" class="payment-grid"><label>Ngày<input class="input-date" type="date" name="work_date" value="' + esc(entry.kind === 'opening' && entry.item.opening ? entry.item.opening.start_date : todayIso) + '" required></label>' +
      '<label>Số lượng (' + esc(entry.item.unit) + ')<input type="number" name="qty" step="any" ' + (entry.kind === 'opening' ? 'min="0" ' : '') + 'value="' + (entry.kind === 'opening' ? entry.item.opening_qty : '') + '" required></label>' +
      '<label>Giá nhập tham khảo<input type="number" min="0" step="any" name="unit_cost" value="' + esc(entry.item.unit_cost) + '" required></label>' +
      '<label>Người thực hiện<input name="actor" required maxlength="100"></label><label>Nội dung/lý do<input name="reason" required maxlength="500"></label>' +
      '<button class="btn btn-primary" type="submit">Lưu kho thực tế</button><button class="btn btn-outline" type="button" data-action="cancel-physical-entry">Đóng</button></form></div>' : '';
    content.innerHTML = '<div class="code-note">' + esc(data.note) + ' Đơn hẹn ngày sau cũng trừ ngay. <strong>Chưa khai tồn đầu thì chưa kết luận hàng còn/hết.</strong></div>' +
      '<form id="physicalFilterForm" class="toolbar"><input class="input-date" name="search" value="' + esc(state.physicalSearch) + '" placeholder="Tìm mã hoặc tên hàng"><select class="select" name="status">' +
      [['all','Tất cả'],['available','Còn hàng'],['empty','Hết hàng'],['short','Thiếu hàng'],['uninitialized','Chưa khai tồn đầu'],['review','Cần đối chiếu']].map(function (pair) { return '<option value="' + pair[0] + '"' + (state.physicalStatus === pair[0] ? ' selected' : '') + '>' + pair[1] + '</option>'; }).join('') + '</select><button class="btn btn-primary">Xem / Làm mới</button></form>' +
      '<div class="totals-strip"><div><span>Số mã</span><strong>' + data.totals.rows + '</strong></div><div><span>Tổng tồn theo ĐVT</span><strong>' + esc(stockQuantitySummary(data.items, 'balance_qty')) + '</strong></div><div><span>Giá trị tồn ước tính</span><strong>' + stockMoney(data.totals.estimated_amount) + '</strong></div><div><span>Chưa khai tồn</span><strong>' + data.totals.uninitialized + '</strong></div></div>' +
      (data.issues.length ? '<details class="code-note"><summary>Có ' + data.issues.length + ' dòng cần đối chiếu mã/ĐVT/lượng; số tồn chưa đầy đủ</summary>' + data.issues.map(function (item) { return '<p>' + esc(item.product_code || 'Chưa có mã') + (item.order_id ? ' · đơn #' + item.order_id : '') + ': ' + esc(item.error) + '</p>'; }).join('') + '</details>' : '') +
      form + '<div class="card"><div class="table-wrap round2-table"><table><thead><tr><th>Mã / Hàng</th><th>ĐVT</th><th>Tồn đầu</th><th>Nhập/điều chỉnh</th><th>Đã trừ theo đơn</th><th>Còn lại</th><th>Tiền ước tính</th><th>Trạng thái</th><th></th></tr></thead><tbody>' +
      data.items.map(function (item) {
        return '<tr class="' + (item.status === 'short' ? 'row-error' : '') + '"><td><strong>' + esc(item.product_name) + '</strong><div class="muted">' + esc(item.product_code) + '</div><details><summary>Đơn đã trừ (' + item.orders.length + ')</summary>' +
          item.orders.map(function (order) { return '<p>' + dateVN(order.work_date) + ' · ' + esc(order.kitchen) + ' · ' + stockQty(order.qty) + ' ' + esc(item.unit) + ' <button class="btn btn-small" data-action="physical-source-order" data-batch="' + order.batch_id + '" data-id="' + order.order_id + '">Mở đơn #' + order.order_id + '</button></p>'; }).join('') + '</details></td><td>' + esc(item.unit) + '</td><td>' +
          stockQty(item.opening_qty) + (item.opening ? '<div class="muted">Từ ' + dateVN(item.opening.start_date) + '</div>' : '') + '</td><td>' + stockQty(item.received_qty) + '</td><td>' + stockQty(item.committed_qty) + '</td><td>' + (item.balance_qty == null ? '—' : stockQty(item.balance_qty)) + '</td><td>' + (item.estimated_amount == null ? '—' : stockMoney(item.estimated_amount)) + '</td><td>' + labels[item.status] + '</td><td><button class="btn btn-small" data-action="physical-entry" data-kind="opening" data-code="' + esc(item.product_code) + '">Tồn đầu</button> <button class="btn btn-small" data-action="physical-entry" data-kind="movement" data-code="' + esc(item.product_code) + '">Nhập/điều chỉnh</button></td></tr>';
      }).join('') + '</tbody></table></div></div>' +
      '<details class="operation-details"><summary>Lịch sử nhập/điều chỉnh thực tế</summary><div class="table-wrap round2-table"><table><thead><tr><th>Ngày</th><th>Mã hàng</th><th>Lượng</th><th>ĐVT</th><th>Người lưu</th><th>Nội dung</th></tr></thead><tbody>' +
      data.movements.slice().reverse().map(function (item) { return '<tr><td>' + dateVN(item.work_date) + '</td><td>' + esc(item.product_code) + '</td><td>' + stockQty(item.qty) + '</td><td>' + esc(item.unit) + '</td><td>' + esc(item.actor) + '</td><td>' + esc(item.reason) + '</td></tr>'; }).join('') + '</tbody></table></div></details>';
  }

  function renderDeliveries() {
    var d = state.data;
    if (!d.batch) { content.innerHTML = emptyBatch("Chưa có dữ liệu giao hàng", "Nạp đơn trước khi xem phiếu."); return; }
    var batch = d.batches.find(function(b) { return b.id === state.batchId; }) || d.batch;
    var notes = batch.delivery_notes || [];
    content.innerHTML = '<div class="card"><div class="card-head"><div><h3>Phiếu giao ngày ' + dateVN(d.batch.work_date) + '</h3><p>Chọn từng bếp ở bên dưới để xem, tải Excel hoặc in; phiếu ẩn giá vẫn giữ ẩn giá.</p></div><a class="btn btn-outline" href="' + exportUrl("deliveries") + '">Tải toàn bộ Excel</a></div></div><div id="deliveryDocumentPreview"></div>';
    if (!notes.length) {
      document.getElementById("deliveryDocumentPreview").innerHTML = '<div class="empty">Chưa có hàng thực giao để lập phiếu.</div>';
      return;
    }
    window.TDPDocuments.open({kind:"deliveries", selections:notes.map(function(note) { return {batch_id:state.batchId, kitchen:note.code}; })}, "deliveryDocumentPreview");
  }

  async function fetchQuote() {
    try {
      var url = "/api/quotes?contractor=" + encodeURIComponent(state.quoteContractor) +
        "&period=" + encodeURIComponent(state.quotePeriod);
      if (state.batchId) url += "&batch_id=" + state.batchId;
      var results = await Promise.all([
        api(url),
        api("/api/quotes/versions?period=" + encodeURIComponent(state.quotePeriod))
      ]);
      var payload = results[0];
      state.quoteItems = payload.items;
      state.quoteMode = payload.mode;
      state.quoteMeta = payload;
      state.quoteVersions = results[1].items || [];
      if (state.view === "quotes") renderQuotes();
    } catch (error) {
      showToast(error.message, true);
    }
  }

  function excelColumnName(column) {
    var value = Number(column) || 0;
    var output = "";
    while (value > 0) {
      value -= 1;
      output = String.fromCharCode(65 + value % 26) + output;
      value = Math.floor(value / 26);
    }
    return output || "?";
  }

  function quoteImportPreviewHtml() {
    var preview = state.quoteImportPreview;
    if (!preview) return "";
    var counts = preview.counts || {};
    var mappings = (preview.priceColumns || []).map(function (item) {
      return '<span class="tag tag-ok">' + esc(item.sourceHeader) + " · cột " +
        esc(excelColumnName(item.sourceColumn)) + " → " + esc(item.priceGroup) + "</span>";
    }).join(" ");
    var conflicts = (preview.conflicts || []).map(function (item) {
      return '<tr><td><strong>' + esc(item.productCode) + "</strong></td><td>" +
        esc(item.priceGroup) + "</td><td>" + esc((item.sourceRows || []).join(", ")) +
        "</td><td>" + esc((item.reasons || []).join("; ")) + "</td></tr>";
    }).join("");
    var conflictTable = conflicts
      ? '<div class="code-note danger-note"><strong>Phải sửa file rồi xem trước lại:</strong> hệ thống không tự chọn giữa các dòng cùng mã.</div>' +
        '<div class="table-wrap"><table><thead><tr><th>Mã hàng</th><th>Nhóm giá</th><th>Dòng nguồn</th><th>Xung đột</th></tr></thead><tbody>' +
        conflicts + "</tbody></table></div>"
      : '<div class="status-bar">✓ Không có mã lặp xung đột; mã lặp cùng dữ liệu sẽ chỉ hiện một dòng.</div>';
    return html([
      '<div class="card quote-import-preview fade-in"><div class="card-head"><div><p class="eyebrow">KIỂM TRA FILE BÁO GIÁ</p><h3>Kỳ ',
      esc(preview.effectivePeriod), " · phiên bản dự kiến ", preview.proposedVersion,
      '</h3><p>Trang Excel ', esc(preview.sheet), " · ", counts.products || 0,
      " dòng dữ liệu · ", counts.price_groups || 0, " nhóm giá</p></div>",
      '<span class="tag ', preview.canConfirm ? "tag-ok" : "tag-red", '">',
      preview.canConfirm ? "File hợp lệ" : "Đang bị chặn", "</span></div>",
      '<div class="code-note"><strong>Các cột giá đã nhận:</strong> ', mappings, "</div>",
      '<div class="summary-grid compact-summary"><div><span>Mã lặp</span><strong>', counts.duplicate_codes || 0,
      '</strong></div><div><span>Gộp an toàn</span><strong>', counts.safe_duplicate_codes || 0,
      '</strong></div><div><span>Mã xung đột</span><strong>', counts.conflict_codes || 0,
      '</strong></div><div><span>Xung đột nhóm</span><strong>', counts.conflicts || 0, "</strong></div></div>",
      conflictTable,
      '<div class="toolbar"><button class="btn btn-light" data-action="cancel-quote-import">Bỏ file này</button>',
      preview.canConfirm ? '<button class="btn btn-primary" data-action="confirm-quote-import">Lưu lại file này</button>' : "",
      "</div></div>"
    ]);
  }

  function renderQuotes() {
    var d = state.data;
    var contractors = d.master.contractors || [];
    if (!contractors.some(function (item) { return item.code === state.quoteContractor; }) && contractors.length) {
      state.quoteContractor = contractors[0].code;
    }
    if (state.quoteItems === null) {
      content.innerHTML = '<div class="loading-panel"><div class="spinner"></div><strong>Đang nạp bảng giá…</strong></div>';
      setTimeout(fetchQuote, 0);
      return;
    }
    var meta = state.quoteMeta || {};
    var outputCount = Number(meta.outputCount || 0);
    var statusCount = Number(meta.statusCount || 0);
    var excludedCount = Number(meta.excludedCount || 0);
    var rows = state.quoteItems.map(function (item, index) {
      var price = item.price_state === "numeric"
        ? "<strong>" + money(item.sell_price) + "</strong>"
        : item.price_state === "zero"
          ? '<span class="tag tag-warn">0 · giữ để xác nhận</span>'
          : '<span class="tag tag-warn">' + esc(item.status || "Chưa có giá") + "</span>";
      return "<tr><td>" + (index + 1) + "</td><td>" + esc(item.product_code) +
        '</td><td class="name-cell">' + esc(item.product_name) + "</td><td>" + esc(item.unit) +
        '</td><td><span class="tag tag-tax">' + taxText(item.tax) + '</span></td><td class="num-cell">' +
        price + "</td><td>" + esc((item.source_rows || [item.source_row]).join(", ")) + "</td></tr>";
    }).join("");
    var options = contractors.map(function (item) {
      return '<option value="' + esc(item.code) + '"' + (item.code === state.quoteContractor ? " selected" : "") +
        ">" + esc(item.code) + (item.pricing_mode === "daily" ? " · giá theo ngày" : "") + "</option>";
    }).join("");
    var note = state.quoteMode === "daily"
      ? "GIANHAPTAY/YLKHAN không dùng bảng giá nhà thầu: báo giá lấy từ giá nhập của đơn hàng theo ngày."
      : "Giá lấy đúng cột của nhóm nhà thầu trong bản mới nhất đã lưu; X/rỗng không xuất, giá 0 vẫn giữ rõ để người dùng quyết định.";
    var versionText = state.quoteMode === "daily"
      ? meta.dailySource
        ? "Đơn hàng số " + meta.dailySource.batch_id + " · ngày " + dateVN(meta.dailySource.work_date)
        : "Chưa chọn đơn hàng có giá theo ngày"
      : meta.version
        ? "Phiên bản " + meta.version.version_no + " · nhóm " + (meta.price_group || state.quoteContractor)
        : "Chưa có bảng giá của kỳ này · đang xem danh mục giá cũ";
    var exportQuery = state.quoteMode === "daily" && meta.dailySource
      ? "?batch_id=" + meta.dailySource.batch_id
      : "?period=" + encodeURIComponent(state.quotePeriod);
    var canExportQuote = state.quoteMode === "daily" ? Boolean(meta.dailySource) : Boolean(meta.version);
    var exportControl = canExportQuote
      ? '<a class="btn btn-primary" href="/api/export/quote/' + encodeURIComponent(state.quoteContractor) +
        exportQuery + '">Tải báo giá ' + esc(state.quoteContractor) + "</a>"
      : '<button class="btn btn-primary" type="button" disabled title="' +
        (state.quoteMode === "daily" ? "Phải chọn đơn hàng có giá theo ngày" : "Phải nạp báo giá đúng kỳ trước khi xuất") + '">' +
        (state.quoteMode === "daily" ? "Chưa thể xuất · cần chọn đơn hàng" : "Chưa thể xuất · cần bảng giá kỳ này") + "</button>";
    if (canExportQuote) exportControl += '<button class="btn btn-outline" data-action="preview-quote">Xem bản gửi khách / In</button>';
    var versions = state.quoteVersions || [];
    var latestVersion = versions.length ? versions[0] : null;
    var selectedBatch = d.batch || null;
    var bundleQuery = latestVersion
      ? "?period=" + encodeURIComponent(state.quotePeriod) + "&version_id=" + latestVersion.id
      : "";
    if (latestVersion && selectedBatch && String(selectedBatch.work_date || "").slice(0, 7) === state.quotePeriod) {
      bundleQuery += "&batch_id=" + selectedBatch.id;
    }
    var bundleControl = latestVersion
      ? '<a class="btn btn-primary" href="/api/export/quotes/all' + bundleQuery + '">Tải báo giá tổng (.zip)</a>'
      : '<button class="btn btn-primary" type="button" disabled>Chưa có báo giá tháng này</button>';
    if (latestVersion) bundleControl += '<button class="btn btn-outline" data-action="preview-all-quotes">Xem báo giá tổng / In</button>';
    var historyRows = versions.map(function (version) {
      var historyQuery = "?period=" + encodeURIComponent(state.quotePeriod) + "&version_id=" + version.id;
      var contractorDownload = state.quoteMode === "daily"
        ? ""
        : '<a class="btn btn-small btn-outline" href="/api/export/quote/' +
          encodeURIComponent(state.quoteContractor) + historyQuery + '">Tải Excel ' +
          esc(state.quoteContractor) + "</a>";
      return '<tr><td><strong>Phiên bản ' + version.version_no + '</strong></td><td>' +
        esc(dateTimeVN(version.confirmed_at || version.created_at || "")) + '</td><td>' +
        esc(version.source_name || "Không có tên file") + '</td><td><div class="table-actions">' +
        contractorDownload + '<a class="btn btn-small btn-outline" href="/api/export/quotes/all' +
        historyQuery + '">Tải tất cả bản này (.zip)</a></div></td></tr>';
    }).join("");
    var historyCard = '<div class="card fade-in" style="margin-top:18px"><div class="card-head"><div>' +
      '<h3>Các lần báo giá đã lưu</h3><p>Chọn đúng lần cần gửi lại. Mỗi nhà thầu là một file Excel riêng, không lẫn giá.</p>' +
      '</div><span class="tag tag-ok">' + versions.length + ' phiên bản</span></div>' +
      (historyRows
        ? '<div class="table-wrap"><table><thead><tr><th>Lần lưu</th><th>Thời điểm lưu</th><th>File nguồn</th><th>Tải file</th></tr></thead><tbody>' + historyRows + '</tbody></table></div>'
        : '<div class="empty">Chưa có báo giá đã lưu cho kỳ này.</div>') + '</div>';
    var activeConflicts = (meta.conflicts || []).map(function (item) {
      return esc(item.product_code) + " (dòng " + esc((item.source_rows || []).join(", ")) + ")";
    }).join("; ");
    var latestText = latestVersion
      ? "Bản mới nhất: lần " + latestVersion.version_no + " · " + dateTimeVN(latestVersion.confirmed_at || latestVersion.created_at)
      : "Chưa có báo giá đã lưu trong tháng";
    var detailPanel = state.quoteDetailsOpen ? html([
      '<div class="card fade-in quote-detail-panel"><div class="card-head"><div><h3>Chi tiết báo giá ',
      esc(state.quoteContractor), " · tháng ", esc(meta.period || state.quotePeriod), "</h3><p>Kính gửi: ",
      esc(meta.recipient || state.quoteContractor), " · ", esc(versionText),
      '</p></div><button class="btn btn-small btn-outline" data-action="toggle-quote-details">Ẩn chi tiết</button></div>',
      '<div class="compact-summary"><div><span>Dòng được xuất</span><strong>', outputCount,
      '</strong></div><div><span>Trạng thái chữ</span><strong>', statusCount,
      '</strong></div><div><span>Dòng X/rỗng đã loại</span><strong>', excludedCount,
      '</strong></div></div><div class="code-note"><strong>Quy tắc:</strong> ', esc(note), '</div>',
      '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Mã hàng</th><th>Tên hàng</th><th>Đơn vị</th><th>Thuế</th><th>Giá / Trạng thái</th><th>Dòng trong file</th></tr></thead><tbody>',
      rows, '</tbody></table></div></div>'
    ]) : "";
    content.innerHTML = html([
      '<div class="quote-topline fade-in"><label><strong>Tháng báo giá</strong><input class="input" id="quotePeriod" type="month" value="',
      esc(state.quotePeriod), '"></label><button class="btn btn-outline" data-action="choose-quote-workbook">Nạp báo giá tháng mới</button>',
      '<span>', esc(latestText), '</span></div>',
      quoteImportPreviewHtml(),
      activeConflicts ? '<div class="code-note danger-note"><strong>Chưa thể xuất:</strong> mã đang xung đột ' + activeConflicts + "</div>" : "",
      '<div class="quote-choice-grid fade-in"><section class="quote-choice-card"><div class="quote-choice-icon">TỔNG</div>',
      '<div><h3>Báo giá tổng</h3><p>Tải bản mới nhất của tháng; mỗi nhà thầu là một file Excel riêng.</p></div>',
      '<div class="quote-choice-actions">', bundleControl, '</div></section>',
      '<section class="quote-choice-card"><div class="quote-choice-icon">CT</div><div><h3>Báo giá chi tiết</h3>',
      '<p>Chọn đúng nhà thầu cần gửi.</p><label>Nhà thầu<select class="select" id="quoteContractor">', options,
      '</select></label></div><div class="quote-choice-actions">', exportControl,
      '<button class="btn btn-outline" data-action="toggle-quote-details">', state.quoteDetailsOpen ? 'Ẩn bảng chi tiết' : 'Xem bảng chi tiết',
      '</button></div></section></div>',
      '<div class="secondary-action-row"><button class="btn btn-outline" data-action="toggle-quote-history">',
      state.quoteHistoryOpen ? 'Ẩn các lần báo giá cũ' : 'Xem các lần báo giá đã lưu', '</button></div>',
      state.quoteHistoryOpen ? historyCard : "",
      detailPanel
    ]);
    content.insertAdjacentHTML("beforeend", '<div id="quotePreview"></div>');
  }

  async function previewQuoteWorkbook(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("effective_period", state.quotePeriod);
      form.append("file", file);
      state.quoteImportPreview = await api("/api/quotes/import/preview", { method: "POST", body: form });
      if (state.quoteImportPreview.canConfirm) {
        await confirmQuoteImport(null);
      } else {
        renderQuotes();
        showToast("Báo giá có mã trùng xung đột · chưa ghi dữ liệu", true);
      }
    } catch (error) {
      state.quoteImportPreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmQuoteImport(button) {
    var preview = state.quoteImportPreview;
    if (!preview || !preview.canConfirm) return;
    try {
      if (button) {
        button.disabled = true;
        button.textContent = "Đang lưu file mới nhất…";
      }
      var result = await api("/api/quotes/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: preview.token, confirmed: true, state_hash: preview.stateHash
        })
      });
      state.quoteImportPreview = null;
      state.quoteItems = null;
      state.quoteMeta = null;
      await fetchQuote();
      showToast("Đã lưu báo giá mới nhất kỳ " + result.effectivePeriod + " · lần " + result.versionNo);
    } catch (error) {
      if (button) {
        button.disabled = false;
        button.textContent = "Lưu lại file này";
      }
      renderQuotes();
      showToast(error.message, true);
    }
  }

  function receivableExportUrl() {
    var url = "/api/debts/receivables/export?from=" + encodeURIComponent(state.debtFrom) +
      "&to=" + encodeURIComponent(state.debtTo);
    if (state.receivableContractor) {
      url += "&contractor=" + encodeURIComponent(state.receivableContractor);
    }
    return url;
  }

  function receivableHistoryRows(item) {
    var key = String(item.id);
    if (!state.receivableExpanded[key]) return "";
    var history = state.receivableRevisions[key];
    var body;
    if (history === "loading" || !history) {
      body = '<div class="loading-inline compact-loading"><div class="spinner"></div><strong>Đang nạp lịch sử dòng…</strong></div>';
    } else if (history.error) {
      body = '<div class="error-summary">' + esc(history.error) + '</div>';
    } else {
      var revisions = (history.revisions || []).map(function (revision) {
        return '<li><strong>Lần thay đổi ' + revision.revision + ' · ' +
          esc(receivableRevisionText(revision.change_kind)) + '</strong><span>' +
          dateVN(revision.work_date) + ' · giao ròng ' + num(revision.delivered_qty) + ' ' +
          esc(revision.unit || item.unit) + ' · ' + money(revision.amount) + ' · ' +
          esc(receivableStatusText(revision.status)) +
          (revision.reversal_reason ? ' · ' + esc(revision.reversal_reason) : '') +
          '</span></li>';
      }).join("");
      body = '<div class="receivable-revision-panel"><strong>Nguồn ' +
        esc(history.source_ref || item.source.ref) + '</strong><ol>' +
        (revisions || '<li>Chưa có lịch sử.</li>') + '</ol></div>';
    }
    return '<tr class="receivable-history-row"><td colspan="15">' + body + '</td></tr>';
  }

  function receivableWorkspaceHtml() {
    if (state.receivableError) {
      return '<div class="card receivable-workspace"><div class="card-body"><div class="error-summary">' +
        esc(state.receivableError) + '</div><div class="form-actions"><button class="btn btn-outline" data-action="refresh-receivables">Tải lại sổ phải thu</button></div></div></div>';
    }
    if (!state.receivableLedger) {
      return '<div class="card receivable-workspace"><div class="card-body"><div class="loading-inline"><div class="spinner"></div><strong>Đang nạp sổ phải thu vận hành…</strong></div></div></div>';
    }
    var ledger = state.receivableLedger;
    var summary = ledger.summary || {};
    var statusCounts = summary.status_counts || {};
    var rows = (ledger.rows || []).map(function (item) {
      var key = String(item.id);
      var expanded = Boolean(state.receivableExpanded[key]);
      var statusClass = item.status === "active" ? "tag-ok" : "tag-red";
      return '<tr class="receivable-line-' + esc(item.status) + '"><td>' + dateVN(item.work_date) +
        '</td><td><strong>' + esc(item.contractor.code) + '</strong><div class="muted">' +
        esc(item.contractor.name) + '</div></td><td><strong>' + esc(item.kitchen.code || "—") +
        '</strong><div class="muted">' + esc(item.kitchen.name) + '</div></td><td><strong>' +
        esc(item.product_name) + '</strong><div class="muted">' + esc(item.product_code || "Không có mã") +
        '</div></td><td class="num-cell">' + stockQty(item.ordered_qty) + '</td><td class="num-cell">' +
        stockQty(item.actual_delivered) + '</td><td class="num-cell">' + stockQty(item.customer_return_qty) +
        '</td><td class="num-cell"><strong>' + stockQty(item.delivered_qty) + '</strong></td><td>' +
        esc(item.unit) + '</td><td class="num-cell">' + money(item.sell_price) +
        '</td><td class="num-cell">' + money(item.subtotal) + '</td><td class="num-cell">' +
        (n(item.tax_percent) ? num(item.tax_percent) + "% · " : "") + money(item.tax_amount) +
        '</td><td class="num-cell"><strong>' + money(item.amount) + '</strong></td><td><span class="tag ' +
        statusClass + '">' + esc(receivableStatusText(item.status)) + '</span>' +
        (item.reversal_reason ? '<div class="muted">' + esc(item.reversal_reason) + '</div>' : '') +
        '</td><td><div class="muted">Mã dòng ' + item.id + ' · lần sửa ' + item.ledger_revision +
        '</div><button class="btn btn-small btn-outline" data-action="toggle-receivable-history" data-id="' +
        item.id + '" aria-expanded="' + (expanded ? "true" : "false") + '">' +
        (expanded ? "Ẩn lịch sử" : "Xem lịch sử") + '</button></td></tr>' + receivableHistoryRows(item);
    }).join("");
    var pagination = ledger.pagination || {};
    var truncated = ledgerPager("receivable", ledger.pagination);
    var account = null;
    if (state.receivableContractor && state.debtPeriod && state.debtPeriod.contractors) {
      account = state.debtPeriod.contractors[state.receivableContractor] || {
        opening: 0, period_charge: 0, period_adjustment: 0, period_paid: 0, closing: 0
      };
    }
    var reconciliation = account
      ? '<div class="code-note receivable-reconcile"><strong>Đối soát tài khoản ' +
        esc(state.receivableContractor) + ':</strong> đầu kỳ ' + money(account.opening) +
        ' + phát sinh ' + money(account.period_charge) + ' + điều chỉnh ' +
        money(account.period_adjustment) + ' − đã thu ' + money(account.period_paid) +
        ' = còn thu <strong>' + money(account.closing) + '</strong>.' +
        (state.receivableKitchen ? ' Bộ lọc bếp chỉ thu hẹp bảng chi tiết; số dư tài khoản vẫn gồm toàn bộ bếp của nhà thầu.' : '') + '</div>'
      : '<div class="code-note receivable-reconcile"><strong>Đối soát:</strong> chọn một nhà thầu để xem công thức đầu kỳ + phát sinh + điều chỉnh − đã thu = còn thu.</div>';
    return html([
      '<div class="receivable-workspace fade-in">',
      '<div class="stats-grid receivable-stats">',
      statCard("Tổng số lượng", esc(quantityGroups(summary.filtered_quantities_by_unit)), "Theo bộ lọc đang chọn", "∑"),
      statCard("Tiền trước thuế", stockMoney(summary.filtered_subtotal), "Theo bộ lọc đang chọn", "↗"),
      statCard("Thuế vận hành", stockMoney(summary.filtered_tax_amount), "Không đọc tổng hóa đơn đỏ", "%"),
      statCard("Tổng tiền", stockMoney(summary.filtered_amount), "Dòng đã đảo chỉ để tra cứu", "₫"),
      '</div>', reconciliation, truncated,
      '<div class="card"><div class="card-head"><div><h3>Sổ phải thu vận hành chi tiết</h3>',
      '<p>Nguồn duy nhất: lượng thực giao ròng đã duyệt × giá bán giao dịch + thuế; không phải đề nghị thanh toán/hóa đơn đỏ</p></div><span class="tag">',
      num(pagination.returned || 0), ' dòng đang hiển thị</span></div>',
      '<div class="table-wrap round3-table receivable-ledger-table"><table><thead><tr><th>Ngày</th><th>Nhà thầu</th><th>Bếp</th><th>Hàng</th><th>Số đặt</th><th>Thực giao</th><th>Khách trả</th><th>Giao ròng</th><th>Đơn vị</th><th>Giá bán giao dịch</th><th>Trước thuế</th><th>Thuế</th><th>Phải thu vận hành</th><th>Trạng thái</th><th>Nguồn / lịch sử</th></tr></thead><tbody>',
      rows || '<tr><td colspan="15"><div class="empty">Không có dòng phải thu theo bộ lọc này.</div></td></tr>',
      '</tbody><tfoot><tr class="table-total-row"><td colspan="4">TỔNG THEO BỘ LỌC</td><td colspan="3"></td><td class="num-cell">',
      esc(quantityGroups(summary.filtered_quantities_by_unit)), '</td><td colspan="2"></td><td class="num-cell">',
      money(summary.filtered_subtotal), '</td><td class="num-cell">', money(summary.filtered_tax_amount),
      '</td><td class="num-cell">', money(summary.filtered_amount), '</td><td colspan="2"></td></tr></tfoot></table></div></div></div>'
    ]);
  }

  function payableSelectionState() {
    var entries = Object.entries(state.payableSelected || {}).map(function (entry) {
      return Object.assign({ id: Number(entry[0]) }, entry[1]);
    });
    var suppliers = Array.from(new Set(entries.map(function (item) { return item.supplier; }).filter(Boolean)));
    var total = entries.reduce(function (sum, item) { return sum + n(item.amount); }, 0);
    var invalid = entries.some(function (item) {
      var amount = Number(item.amount);
      return !Number.isInteger(amount) || amount <= 0 || amount > n(item.remaining);
    });
    return {
      entries: entries,
      suppliers: suppliers,
      total: total,
      ready: entries.length > 0 && suppliers.length === 1 && !invalid,
      invalid: invalid
    };
  }

  function updatePayableSelectionSummary() {
    var selection = payableSelectionState();
    var count = document.getElementById("payableSelectedCount");
    var supplier = document.getElementById("payableSelectedSupplier");
    var total = document.getElementById("payablePaymentTotal");
    var hint = document.getElementById("payableSelectionHint");
    var submit = document.getElementById("payablePaymentSubmit");
    if (count) count.textContent = selection.entries.length + " dòng";
    if (supplier) supplier.value = selection.suppliers.length === 1 ? selection.suppliers[0] : "";
    if (total) total.value = selection.total ? Math.round(selection.total) : "";
    if (submit) submit.disabled = !selection.ready;
    if (hint) {
      hint.textContent = !selection.entries.length
        ? "Chọn dòng rồi tự nhập số tiền phân bổ cho từng dòng."
        : selection.suppliers.length > 1
          ? "Một giao dịch chỉ được chọn các dòng của cùng một nhà cung cấp."
          : selection.invalid
            ? "Mỗi số phân bổ phải là số tiền nguyên đồng, lớn hơn 0 và không vượt số còn phải trả."
            : "Sẵn sàng ghi nhận " + money(selection.total) + " cho " + selection.suppliers[0] + ".";
      hint.classList.toggle("danger-text", selection.entries.length > 0 && !selection.ready);
    }
  }

  function payableExportUrl() {
    var url = "/api/debts/payables/export?from=" + encodeURIComponent(state.debtFrom) +
      "&to=" + encodeURIComponent(state.debtTo);
    if (state.payableSupplier) url += "&supplier=" + encodeURIComponent(state.payableSupplier);
    url += "&status=" + encodeURIComponent(state.payableStatus === "outstanding" ? "open,partially_paid" : state.payableStatus);
    return url;
  }

  function payableWorkspaceHtml() {
    if (state.payableError) {
      return '<div class="card payable-workspace"><div class="card-body"><div class="error-summary">' +
        esc(state.payableError) + '</div><div class="form-actions"><button class="btn btn-outline" data-action="refresh-payables">Tải lại sổ phải trả</button></div></div></div>';
    }
    if (!state.payableLedger || !state.payablePayments) {
      return '<div class="card payable-workspace"><div class="card-body"><div class="loading-inline"><div class="spinner"></div><strong>Đang nạp sổ phải trả chi tiết và lịch sử thanh toán…</strong></div></div></div>';
    }
    var ledger = state.payableLedger;
    var history = state.payablePayments;
    var summary = ledger.summary || {};
    var statusCounts = summary.status_counts || {};
    var selection = payableSelectionState();
    var lineRows = (ledger.rows || []).map(function (item) {
      var key = String(item.id);
      var selected = state.payableSelected[key];
      var canPay = (item.status === "open" || item.status === "partially_paid") && n(item.remaining_amount) > 0;
      return '<tr class="payable-line-' + esc(item.status) + '"><td class="payable-select-cell"><input type="checkbox" class="payable-line-select" aria-label="Chọn dòng nợ ' +
        esc(item.id) + ' của ' + esc(item.supplier.code) + '" data-id="' + item.id + '" data-supplier="' +
        esc(item.supplier.code) + '" data-revision="' + item.ledger_revision + '" data-remaining="' +
        n(item.remaining_amount) + '" ' + (selected ? "checked" : "") + (canPay ? "" : " disabled") + '></td><td>' +
        dateVN(item.work_date) + '</td><td><strong>' + esc(item.supplier.code) + '</strong><div class="muted">' +
        esc(item.supplier.name) + '</div></td><td>' + esc(item.kitchen || "—") + '</td><td><strong>' +
        esc(item.product_name || "—") + '</strong><div class="muted">' + esc(item.product_code || "Không có mã") +
        '</div></td><td class="num-cell">' + stockQty(item.actual_qty) + ' ' + esc(item.unit) +
        '</td><td class="num-cell">' + money(item.buy_price) + '</td><td class="num-cell"><strong>' +
        money(item.amount) + '</strong></td><td class="num-cell">' + money(item.paid_amount) +
        '</td><td class="num-cell"><strong>' + money(item.remaining_amount) + '</strong></td><td><span class="tag ' +
        payableStatusClass(item.status) + '">' + esc(payableStatusText(item.status)) +
        '</span><div class="muted">Lần sửa ' + item.ledger_revision + '</div></td><td><input class="payable-allocation-input" inputmode="numeric" type="number" min="1" max="' +
        n(item.remaining_amount) + '" step="1" aria-label="Số tiền phân bổ dòng ' + item.id + '" data-id="' +
        item.id + '" value="' + esc(selected ? selected.amount : "") + '" ' + (selected ? "" : "disabled") +
        ' placeholder="Tự nhập"></td></tr>';
    }).join("");
    var historyRows = (history.payments || []).map(function (item) {
      var allocations = (item.allocations || []).map(function (allocation) {
        return '<li>#' + allocation.ledger_line_id + ' · ' + dateVN(allocation.line.work_date) + ' · ' +
          esc(allocation.line.product_name) + ' · <strong>' + money(allocation.amount) + '</strong></li>';
      }).join("");
      var reverse = item.status === "posted"
        ? '<button class="btn btn-small btn-danger" data-action="reverse-payable-payment" data-id="' + item.id +
          '" data-revision="' + item.revision + '" data-supplier="' + esc(item.supplier.code) +
          '" data-amount="' + item.amount + '">Hoàn tác</button>'
        : '<span class="muted">' + esc(item.reversal_reason || "Đã hoàn tác") + " · " + esc(item.reversed_by || "") + '</span>';
      return '<tr class="payable-payment-' + esc(item.status) + '"><td>' + dateVN(item.payment_date) +
        '</td><td><strong>#' + item.id + ' · ' + esc(item.supplier.code) + '</strong><div class="muted">' +
        esc(item.supplier.name) + '</div></td><td class="num-cell"><strong>' + money(item.amount) +
        '</strong></td><td>' + esc(item.method || "—") + '<div class="muted">' +
        esc(item.reference_code || "Không có mã tham chiếu") + '</div></td><td>' + esc(item.note || "—") +
        '<div class="muted">' + esc(item.created_by || "Bản cũ chưa ghi người thao tác") + '</div>' +
        '</td><td><span class="tag ' + payableStatusClass(item.status) + '">' +
        esc(payableStatusText(item.status)) + '</span><div class="muted">Lần sửa ' + item.revision +
        '</div></td><td><details><summary>' + (item.allocations || []).length +
        ' dòng</summary><ul class="payable-allocation-list">' + allocations + '</ul></details></td><td>' + reverse + '</td></tr>';
    }).join("");
    var truncated = ledgerPager("payable", ledger.pagination);
    return html([
      '<div class="payable-workspace fade-in">',
      '<div class="stats-grid payable-stats">',
      statCard("Tổng số lượng", esc(quantityGroups(summary.filtered_quantities_by_unit)), "Theo bộ lọc đang chọn", "∑"),
      statCard("Tổng tiền", stockMoney(summary.filtered_amount), "Theo bộ lọc; dòng đã đảo chỉ tra cứu", "₫"),
      statCard("Đã phân bổ", stockMoney(summary.filtered_paid_amount), "Theo các dòng đang lọc", "✓"),
      statCard("Còn phải trả", stockMoney(summary.filtered_remaining_amount), "Theo các dòng đang lọc", "₫"),
      '</div>', truncated,
      '<div class="card"><div class="card-head"><div><h3>Sổ phải trả chi tiết</h3><p>Chọn rõ dòng nợ; hệ thống không tự chọn dòng cũ nhất và không tự chia tiền</p></div><span class="tag">',
      num((ledger.pagination || {}).returned || 0), ' dòng đang hiển thị</span></div>',
      '<div class="table-wrap round3-table payable-ledger-table"><table><thead><tr><th>Chọn</th><th>Ngày</th><th>Nhà cung cấp</th><th>Bếp</th><th>Hàng</th><th>Số thực tế</th><th>Giá mua</th><th>Thành tiền</th><th>Đã trả</th><th>Còn trả</th><th>Trạng thái</th><th>Phân bổ lần này</th></tr></thead><tbody>',
      lineRows || '<tr><td colspan="12"><div class="empty">Không có dòng nợ theo bộ lọc này.</div></td></tr>',
      '</tbody><tfoot><tr class="table-total-row"><td colspan="5">TỔNG THEO BỘ LỌC</td><td class="num-cell">',
      esc(quantityGroups(summary.filtered_quantities_by_unit)), '</td><td></td><td class="num-cell">', money(summary.filtered_amount),
      '</td><td class="num-cell">', money(summary.filtered_paid_amount), '</td><td class="num-cell">',
      money(summary.filtered_remaining_amount), '</td><td colspan="2"></td></tr></tfoot></table></div></div>',
      '<div class="card payable-payment-card"><div class="card-head"><div><h3>Ghi nhận đã trả</h3><p>Một giao dịch chỉ gồm các dòng cùng nhà cung cấp; tổng tiền bằng đúng tổng phân bổ</p></div><span id="payableSelectedCount" class="tag">',
      selection.entries.length, ' dòng</span></div><div class="card-body">',
      '<div id="payableSelectionHint" class="code-note ', selection.entries.length && !selection.ready ? 'danger-text' : '', '">',
      !selection.entries.length ? 'Chọn dòng rồi tự nhập số tiền phân bổ cho từng dòng.' :
        selection.suppliers.length > 1 ? 'Một giao dịch chỉ được chọn các dòng của cùng một nhà cung cấp.' :
        selection.invalid ? 'Mỗi khoản phân bổ phải là số tiền nguyên đồng, lớn hơn 0 và không vượt số còn phải trả.' :
        'Sẵn sàng ghi nhận ' + money(selection.total) + ' cho ' + esc(selection.suppliers[0]) + '.',
      '</div><form id="payablePaymentForm" class="payment-grid payable-payment-form" style="margin-top:14px">',
      '<div class="form-field"><label>Người ghi nhận</label><input name="actor" maxlength="120" required></div>',
      '<div class="form-field"><label>Ngày thanh toán</label><input name="payment_date" type="date" value="', esc(state.debtTo || todayIso), '" required></div>',
      '<div class="form-field"><label>Nhà cung cấp đã chọn</label><input id="payableSelectedSupplier" value="', selection.suppliers.length === 1 ? esc(selection.suppliers[0]) : '', '" readonly placeholder="Chưa chọn"></div>',
      '<div class="form-field"><label>Tổng phân bổ</label><input id="payablePaymentTotal" value="', selection.total || '', '" readonly placeholder="0"></div>',
      '<div class="form-field"><label>Phương thức</label><select name="method"><option>Chuyển khoản</option><option>Tiền mặt</option><option>Bù trừ</option><option value="Khác">Khác</option></select></div>',
      '<div class="form-field"><label>Mã tham chiếu</label><input name="reference_code" placeholder="UNC / mã ngân hàng"></div>',
      '<div class="form-field span-2"><label>Nội dung</label><input name="note" placeholder="Nội dung thanh toán"></div>',
      '<button id="payablePaymentSubmit" class="btn btn-primary" type="submit" ', selection.ready ? '' : 'disabled', '>Ghi nhận thanh toán</button></form></div></div>',
      '<div class="card payable-history-card"><div class="card-head"><div><h3>Lịch sử trả nhà cung cấp</h3><p>Giữ cả giao dịch và phân bổ đã hoàn tác; không dùng xóa</p></div></div>',
      ledgerPager("payable-history", history.pagination),
      '<div class="table-wrap"><table><thead><tr><th>Ngày</th><th>Giao dịch / nhà cung cấp</th><th>Số tiền</th><th>Phương thức / tham chiếu</th><th>Nội dung</th><th>Trạng thái</th><th>Phân bổ</th><th>Thao tác</th></tr></thead><tbody>',
      historyRows || '<tr><td colspan="8"><div class="empty">Chưa có giao dịch trả nhà cung cấp trong kỳ.</div></td></tr>',
      '</tbody></table></div></div></div>'
    ]);
  }

  function quantityGroups(items) {
    return (items || []).map(function (item) { return stockQty(item.quantity) + " " + item.unit; }).join(" · ") || "0";
  }

  function ledgerPager(kind, page) {
    page = page || {};
    var offset = n(page.offset), limit = n(page.limit) || 5000;
    return '<div class="ledger-pager"><span>' + (page.total ? offset + 1 : 0) + '–' + (offset + n(page.returned)) + ' / ' + n(page.total) +
      ' dòng · Tổng phía dưới tính toàn bộ bộ lọc</span><button class="btn btn-outline" data-action="ledger-page" data-kind="' + kind +
      '" data-offset="' + Math.max(0, offset - limit) + '"' + (offset ? '' : ' disabled') + '>Trang trước</button><button class="btn btn-outline" data-action="ledger-page" data-kind="' +
      kind + '" data-offset="' + (offset + limit) + '"' + (offset + n(page.returned) < n(page.total) ? '' : ' disabled') + '>Trang sau</button></div>';
  }

  async function fetchMonthlyReport() {
    var serial = ++state.reportSerial, period = state.reportPeriod;
    state.reportLoading = true; state.reportError = ""; state.reportData = null;
    if (state.view === "reports") renderReports();
    try {
      var data = await api("/api/reports/monthly?period=" + encodeURIComponent(period));
      if (serial === state.reportSerial) state.reportData = data;
    } catch (error) {
      if (serial === state.reportSerial) state.reportError = error.message;
    } finally {
      if (serial === state.reportSerial) {
        state.reportLoading = false;
        if (state.view === "reports") renderReports();
      }
    }
  }

  function renderReports() {
    if (!state.reportData && !state.reportLoading && !state.reportError) setTimeout(fetchMonthlyReport, 0);
    var data = state.reportData;
    var rows = data ? data.rows.map(function (row) {
      var total = String(row[0] || "").indexOf("TỔNG") === 0;
      return '<tr class="' + (total ? 'table-total-row' : '') + '">' + row.map(function (value, index) {
        return '<td' + (index >= 3 ? ' class="num-cell"' : '') + '>' + (index >= 3 ? stockMoney(value) : esc(value || "")) + '</td>';
      }).join("") + '</tr>';
    }).join("") : "";
    content.innerHTML = '<div class="toolbar"><label>Tháng cần xem <input id="reportPeriod" type="month" value="' + esc(state.reportPeriod) +
      '"></label><button class="btn btn-outline" data-action="refresh-monthly-report">Tải lại</button>' +
      (data ? '<a class="btn btn-primary" href="/api/reports/monthly/export?period=' + encodeURIComponent(state.reportPeriod) + '">Tải báo cáo tổng hợp</a>' : '') +
      '</div><div class="code-note">Báo cáo tổng hợp theo nhà thầu và từng bếp trong tháng, chỉ cộng đơn đã duyệt. Bếp chưa phát sinh vẫn hiện; không lấy khoản thu/chi hay hóa đơn đỏ.' +
      (data && data.draft_count ? ' Còn ' + data.draft_count + ' phiên chưa duyệt, chưa cộng vào báo cáo.' : '') + '</div>' +
      (state.reportError ? '<div class="error-summary">' + esc(state.reportError) + '</div>' : '') +
      (state.reportLoading ? '<div class="loading-inline">Đang nạp báo cáo…</div>' : '') +
      (data ? '<div class="card"><div class="table-wrap round3-table" id="monthlyReportTable"><table><thead><tr>' +
        data.headers.map(function (h) { return '<th>' + esc(h) + '</th>'; }).join("") + '</tr></thead><tbody>' + rows + '</tbody></table></div></div>' : '');
  }

  function debtMenuCard(section, title, description, icon) {
    return '<button type="button" class="debt-menu-card" data-action="open-debt-section" data-section="' +
      esc(section) + '"><span class="debt-menu-icon">' + esc(icon) + '</span><span><strong>' +
      esc(title) + '</strong><small>' + esc(description) + '</small></span><b>›</b></button>';
  }

  function renderDebts() {
    var d = state.data;
    if (!state.debtFrom || !state.debtTo) {
      var anchorDate = d.batch ? d.batch.work_date : todayIso;
      state.debtFrom = anchorDate.slice(0, 7) + "-01";
      state.debtTo = anchorDate;
      persistPayableFilters();
      persistReceivableFilters();
    }
    var sectionTitles = {
      "receivable-kitchen": "Công nợ phải thu theo bếp",
      "receivable-total": "Công nợ phải thu tổng hợp",
      payable: "Công nợ phải trả nhà cung cấp"
    };
    var section = state.debtSection;
    pageTitle.textContent = sectionTitles[section] || titles.debts;
    if (!sectionTitles[section]) {
      content.innerHTML = html([
        '<div class="card debt-menu-shell fade-in"><div class="card-head"><div><h3>Chọn nội dung cần xem</h3>',
        '<p>Chỉ hiện phần tổng quan. Bấm vào từng mục để xem số liệu và thao tác chi tiết.</p></div></div>',
        '<div class="card-body"><div class="debt-menu-grid">',
        debtMenuCard("receivable-kitchen", "Công nợ phải thu (bếp)", "Xem chi tiết từng bếp, từng mặt hàng", "▦"),
        debtMenuCard("receivable-total", "Công nợ phải thu (tổng)", "Xem tổng theo nhà thầu và ghi nhận đã thu", "₫"),
        debtMenuCard("payable", "Công nợ phải trả", "Xem và thanh toán cho nhà cung cấp", "⇄"),
        '</div></div></div>'
      ]);
      return;
    }
    if (state.debtPeriod === null && !state.debtLoading && !state.debtError) setTimeout(fetchDebtPeriod, 0);
    // A failed request deliberately leaves the workspace empty so its error
    // panel and explicit retry button remain visible.  Do not immediately
    // schedule the same request from renderDebts(), otherwise a missing or
    // temporarily unavailable backend route creates an endless render/fetch
    // loop that makes the whole report screen flicker.
    if (section === "receivable-kitchen" && state.receivableLedger === null && !state.receivableLoading && !state.receivableError) {
      setTimeout(fetchReceivableWorkspace, 0);
    }
    if (section === "payable" && state.payableLedger === null && !state.payableLoading && !state.payableError) {
      setTimeout(fetchPayableWorkspace, 0);
    }
    var s = d.summary;
    var contractorDebt = state.debtPeriod ? state.debtPeriod.contractors : {};
    var supplierDebt = state.debtPeriod ? state.debtPeriod.suppliers : {};
    if (state.payableSupplier) {
      var accountSupplier = state.payableLedger && state.payableLedger.supplier || state.payableSupplier;
      supplierDebt = Object.fromEntries(Object.entries(supplierDebt).filter(function (entry) { return entry[0] === accountSupplier; }));
    }
    var knownSupplier = false;
    var supplierOptions = '<option value="">Tất cả nhà cung cấp</option>' + (d.master.suppliers || []).map(function (item) {
      if (item.code === state.payableSupplier) knownSupplier = true;
      return '<option value="' + esc(item.code) + '"' + (item.code === state.payableSupplier ? " selected" : "") + '>' +
        esc(item.code) + (item.name && item.name !== item.code ? " · " + esc(item.name) : "") + '</option>';
    }).join("");
    if (state.payableSupplier && !knownSupplier) {
      supplierOptions += '<option value="' + esc(state.payableSupplier) + '" selected>' + esc(state.payableSupplier) + '</option>';
    }
    var knownContractor = false;
    var contractorOptions = '<option value="">Tất cả nhà thầu</option>' + (d.master.contractors || []).map(function (item) {
      if (item.code === state.receivableContractor) knownContractor = true;
      return '<option value="' + esc(item.code) + '"' + (item.code === state.receivableContractor ? " selected" : "") + '>' +
        esc(item.code) + (item.name && item.name !== item.code ? " · " + esc(item.name) : "") + '</option>';
    }).join("");
    if (state.receivableContractor && !knownContractor) {
      contractorOptions += '<option value="' + esc(state.receivableContractor) + '" selected>' + esc(state.receivableContractor) + '</option>';
    }
    var knownKitchen = false;
    var kitchenOptions = '<option value="">Tất cả bếp</option>' + (d.master.kitchens || []).filter(function (item) {
      return !state.receivableContractor || item.contractor === state.receivableContractor;
    }).map(function (item) {
      if (item.code === state.receivableKitchen) knownKitchen = true;
      return '<option value="' + esc(item.code) + '"' + (item.code === state.receivableKitchen ? " selected" : "") + '>' +
        esc(item.code) + (item.name && item.name !== item.code ? " · " + esc(item.name) : "") + '</option>';
    }).join("");
    if (state.receivableKitchen && !knownKitchen) {
      kitchenOptions += '<option value="' + esc(state.receivableKitchen) + '" selected>' + esc(state.receivableKitchen) + '</option>';
    }
    var receivableStatuses = [
      ["active", "Dòng hiệu lực"], ["reversed", "Dòng đã hoàn tác"], ["all", "Tất cả trạng thái"]
    ].map(function (item) {
      return '<option value="' + item[0] + '"' + (state.receivableStatus === item[0] ? " selected" : "") + '>' + item[1] + '</option>';
    }).join("");
    var payableStatuses = [
      ["outstanding", "Còn phải trả"], ["open", "Chưa trả"],
      ["partially_paid", "Trả một phần"], ["paid", "Đã trả đủ"],
      ["reversed", "Đã đảo"], ["all", "Tất cả trạng thái"]
    ].map(function (item) {
      return '<option value="' + item[0] + '"' + (state.payableStatus === item[0] ? " selected" : "") + '>' + item[1] + '</option>';
    }).join("");
    var contractorRows = Object.entries(contractorDebt).map(function (entry) {
      var name = entry[0], item = entry[1];
      return "<tr><td><strong>" + esc(name) + '</strong></td><td class="num-cell">' + money(item.opening) +
        '</td><td class="num-cell">' + money(item.period_charge == null ? item.total : item.period_charge) +
        '</td><td class="num-cell">' + money(item.period_adjustment || 0) +
        '</td><td class="num-cell">' + money(item.period_paid == null ? item.paid : item.period_paid) +
        '</td><td class="num-cell"><strong>' + money(item.closing == null ? item.balance : item.closing) + "</strong></td></tr>";
    }).join("");
    var supplierRows = Object.entries(supplierDebt).map(function (entry) {
      var name = entry[0], item = entry[1];
      return "<tr><td><strong>" + esc(name) + '</strong></td><td class="num-cell">' + money(item.opening) +
        '</td><td class="num-cell">' + money(item.period_charge == null ? item.cost : item.period_charge) +
        '</td><td class="num-cell">' + money(item.period_adjustment || 0) +
        '</td><td class="num-cell">' + money(item.period_paid == null ? item.paid : item.period_paid) +
        '</td><td class="num-cell"><strong>' + money(item.closing == null ? item.balance : item.closing) + "</strong></td></tr>";
    }).join("");
    var paymentRows = (state.receiptHistory || []).map(function (item) {
      return '<tr><td>' + dateVN(item.payment_date) + '</td><td>' + (item.status === "reversed" ? "Đã hoàn tác" : "Đã thu") +
        '</td><td>' + esc(item.party_code) + '</td><td class="num-cell">' + stockMoney(item.amount) + '</td><td>' +
        esc(item.note || "") + '<div class="muted">' + esc(item.created_by || "Bản cũ chưa ghi người thao tác") +
        '</div></td><td>' + (item.status === "reversed" ? esc(item.reversal_reason) + ' · ' + esc(item.reversed_by) :
        '<button class="btn btn-small btn-danger" data-action="reverse-receipt" data-id="' + item.id + '" data-revision="' + item.revision + '">Hoàn tác</button>') + '</td></tr>';
    }).join("");
    function accountTotalRows(accounts) {
      return '<tfoot><tr class="table-total-row"><td>TỔNG</td>' + ["opening", "period_charge", "period_adjustment", "period_paid", "closing"].map(function (field) {
        return '<td class="num-cell">' + stockMoney(Object.values(accounts).reduce(function (sum, item) { return sum + n(item[field]); }, 0)) + '</td>';
      }).join("") + '</tr></tfoot>';
    }
    var debtNotice = state.debtError ? '<div class="error-summary">' + esc(state.debtError) + '<button class="btn btn-outline" data-action="refresh-debt-period">Tải lại tổng công nợ</button></div>' :
      (!state.debtPeriod ? '<div class="loading-inline">Đang nạp tổng công nợ đúng kỳ…</div>' : '');
    var detailHeader = debtNotice + '<div class="debt-detail-head fade-in"><button type="button" class="btn btn-outline" data-action="back-debt-overview">← Danh mục công nợ</button>' +
      '<div><strong>' + esc(sectionTitles[section]) + '</strong><span>Chi tiết chỉ hiện trong mục đang chọn</span></div></div>';
    var periodToolbarStart = '<div class="toolbar fade-in debt-period-toolbar"><form id="debtPeriodForm" class="debt-period-grid' + (section === "payable" ? ' debt-period-grid-payable' : '') + '">' +
      '<div class="form-field"><label for="payableFrom">Từ ngày</label><input id="payableFrom" name="from" type="date" value="' + esc(state.debtFrom) + '" required></div>' +
      '<div class="form-field"><label for="payableTo">Đến ngày</label><input id="payableTo" name="to" type="date" value="' + esc(state.debtTo) + '" required></div>';
    var periodToolbar = periodToolbarStart + (section === "payable"
      ? '<div class="form-field"><label for="payableSupplier">Nhà cung cấp</label><select id="payableSupplier" name="supplier">' + supplierOptions + '</select></div>' +
        '<div class="form-field"><label for="payableStatus">Trạng thái</label><select id="payableStatus" name="status">' + payableStatuses + '</select></div>'
      : '') + '<button class="btn btn-outline" type="submit">Xem công nợ</button></form></div>';
    var receivableFilter = '<div class="toolbar fade-in receivable-toolbar"><form id="receivableFilterForm" class="receivable-filter-grid">' +
      '<div class="form-field"><label for="receivableContractor">Nhà thầu</label><select id="receivableContractor" name="contractor">' + contractorOptions + '</select></div>' +
      '<div class="form-field"><label for="receivableKitchen">Bếp</label><select id="receivableKitchen" name="kitchen">' + kitchenOptions + '</select></div>' +
      '<div class="form-field"><label for="receivableStatus">Trạng thái</label><select id="receivableStatus" name="status">' + receivableStatuses + '</select></div>' +
      '<button class="btn btn-outline" type="submit">Lọc danh sách</button></form><div class="compact-controls">' +
      (state.receivableContractor
        ? '<a id="receivableExportSelected" class="btn btn-primary" href="' + esc(receivableExportUrl()) + '">Excel toàn bộ bếp · ' + esc(state.receivableContractor) + '</a><a class="btn btn-outline" href="/api/debts/receivables/export?from=' + encodeURIComponent(state.debtFrom) + '&to=' + encodeURIComponent(state.debtTo) + '">ZIP mọi nhà thầu</a>'
        : '<a id="receivableExportSelected" class="btn btn-primary" href="' + esc(receivableExportUrl()) + '">ZIP phải thu mọi nhà thầu</a>') +
      '<a class="btn btn-outline" id="receivableFilteredExport" href="/api/debts/receivables/lines/export?from=' + encodeURIComponent(state.debtFrom) +
      '&to=' + encodeURIComponent(state.debtTo) + '&contractor=' + encodeURIComponent(state.receivableContractor) + '&kitchen=' + encodeURIComponent(state.receivableKitchen) +
      '&status=' + encodeURIComponent(state.receivableStatus) + '">Excel theo bộ lọc</a></div></div>';
    var partyType = section === "payable" ? "supplier" : "contractor";
    var partyLabel = partyType === "supplier" ? "nhà cung cấp" : "nhà thầu";
    var adminTools = '<details class="debt-extra-tools"><summary>Số dư đầu kỳ và điều chỉnh</summary><div class="debt-extra-grid">' +
      '<div class="card"><div class="card-head"><div><h3>Nhập số dư đầu kỳ</h3><p>Dùng khi bắt đầu theo dõi công nợ trên hệ thống</p></div></div>' +
      '<div class="card-body"><form id="balanceForm" class="payment-grid"><input name="party_type" type="hidden" value="' + partyType + '">' +
      '<div class="form-field"><label>Ngày bắt đầu áp dụng</label><input name="as_of_date" type="date" value="' + esc(state.debtFrom) + '" required></div>' +
      '<div class="form-field"><label>Mã ' + partyLabel + '</label><input name="party_code" required></div>' +
      '<div class="form-field"><label>Số dư đầu kỳ</label><input name="opening" type="number" required></div>' +
      '<button class="btn btn-outline" type="submit">Lưu số dư</button></form></div></div>' +
      '<div class="card"><div class="card-head"><div><h3>Điều chỉnh công nợ</h3><p>Số dương để tăng, số âm để giảm</p></div></div><div class="card-body">' +
      '<form id="debtAdjustmentForm" class="payment-grid"><input name="party_type" type="hidden" value="' + partyType + '">' +
      '<div class="form-field"><label>Ngày</label><input name="adjustment_date" type="date" value="' + esc(state.debtTo) + '" required></div>' +
      '<div class="form-field"><label>Mã ' + partyLabel + '</label><input name="party_code" required></div>' +
      '<div class="form-field"><label>Số điều chỉnh (+/−)</label><input name="amount" type="number" required></div>' +
      '<div class="form-field span-2"><label>Lý do</label><input name="note" required></div>' +
      '<button class="btn btn-outline" type="submit">Lưu điều chỉnh</button></form></div></div></div></details>';

    if (section === "receivable-kitchen") {
      content.innerHTML = html([
        detailHeader, periodToolbar, receivableFilter,
        '<div class="code-note operational-receivable-note"><strong>Cách tính:</strong> số thực giao sau điều chỉnh × giá bán tại thời điểm giao; không phải đề nghị thanh toán hay hóa đơn đỏ.</div>',
        receivableWorkspaceHtml()
      ]);
      return;
    }

    if (section === "receivable-total") {
      content.innerHTML = html([
        detailHeader, periodToolbar,
        '<div class="toolbar fade-in debt-download-toolbar"><div class="compact-controls"><a class="btn btn-outline" href="/api/export/debts?from=', encodeURIComponent(state.debtFrom), '&to=', encodeURIComponent(state.debtTo), '">Tải Excel thu/chi</a><a class="btn btn-primary" href="/api/debts/receivables/export?from=', encodeURIComponent(state.debtFrom), '&to=', encodeURIComponent(state.debtTo), '">Tải công nợ phải thu (ZIP)</a></div></div>',
        '<div class="card"><div class="card-head"><div><h3>Tổng công nợ phải thu</h3><p>Đầu kỳ + phát sinh + điều chỉnh − đã thu</p></div></div>',
        '<div class="table-wrap round3-table"><table><thead><tr><th>Nhà thầu</th><th>Đầu kỳ</th><th>Phát sinh</th><th>Điều chỉnh</th><th>Đã thu</th><th>Còn thu</th></tr></thead><tbody>',
        contractorRows || '<tr><td colspan="6"><div class="empty">Chưa có công nợ phải thu trong kỳ.</div></td></tr>', '</tbody>', accountTotalRows(contractorDebt), '</table></div></div>',
        '<div class="card"><div class="card-head"><div><h3>Ghi nhận khách hàng đã thanh toán</h3><p>Lưu số tiền đã nhận từ nhà thầu</p></div></div><div class="card-body"><form id="receiptForm" class="payment-grid">',
        '<div class="form-field"><label>Người ghi nhận</label><input name="actor" maxlength="120" required></div>',
        '<div class="form-field"><label>Ngày nhận tiền</label><input name="payment_date" type="date" value="', currentWorkDate(), '" required></div>',
        '<input name="kind" type="hidden" value="receipt"><div class="form-field"><label>Mã nhà thầu</label><input name="party_code" placeholder="VD: HATRAN" required></div>',
        '<div class="form-field"><label>Số tiền</label><input name="amount" type="number" min="1" step="1" required></div>',
        '<div class="form-field"><label>Nội dung</label><input name="note" placeholder="Ví dụ: Chuyển khoản"></div>',
        '<button class="btn btn-primary" type="submit">Lưu khoản đã thu</button></form></div></div>',
        '<div class="card"><div class="card-head"><div><h3>Lịch sử thu khách hàng</h3><p>Các khoản tiền đã ghi nhận trong kỳ</p></div></div>',
        '<div class="table-wrap round3-table"><table><thead><tr><th>Ngày</th><th>Loại</th><th>Đối tượng</th><th>Số tiền</th><th>Nội dung</th><th></th></tr></thead><tbody>',
        paymentRows || '<tr><td colspan="6"><div class="empty">Chưa ghi nhận khoản thu</div></td></tr>', '</tbody></table></div></div>',
        adminTools
      ]);
      return;
    }

    content.innerHTML = html([
      detailHeader, periodToolbar,
      '<div class="toolbar fade-in debt-download-toolbar"><div class="compact-controls"><button class="btn btn-outline" data-action="choose-payables-workbook">Nạp file công nợ cũ</button><a class="btn btn-primary" href="', esc(payableExportUrl()), '">Excel phải trả nhà cung cấp</a></div></div>',
      payablesImportPreviewHtml(), payableWorkspaceHtml(),
      '<div class="card"><div class="card-head"><div><h3>Tổng công nợ phải trả</h3><p>Toàn bộ tài khoản trong kỳ (không theo bộ lọc trạng thái dòng): đầu kỳ + thực nhận + điều chỉnh − đã trả</p></div></div>',
      '<div class="table-wrap round3-table"><table><thead><tr><th>Nhà cung cấp</th><th>Đầu kỳ</th><th>Phát sinh</th><th>Điều chỉnh</th><th>Đã trả</th><th>Còn trả</th></tr></thead><tbody>',
      supplierRows || '<tr><td colspan="6"><div class="empty">Chưa có công nợ phải trả trong kỳ.</div></td></tr>', '</tbody>', accountTotalRows(supplierDebt), '</table></div></div>',
      adminTools
    ]);
  }

  function documentCard(icon, title, text, href, button) {
    return '<div class="document-card"><div class="doc-icon">' + icon + "</div><h4>" + esc(title) +
      "</h4><p>" + esc(text) + '</p><button type="button" class="btn btn-outline" data-action="download-document" data-url="' +
      esc(href) + '">' + esc(button) + "</button></div>";
  }

  function readinessQuantity(rows, field) {
    var units = {};
    (rows || []).forEach(function(row) {
      var unit = row.unit || 'Chưa có ĐVT';
      units[unit] = (units[unit] || 0) + n(row[field]);
    });
    return Object.keys(units).filter(function(unit) { return Math.abs(units[unit]) > 1e-9; }).map(function(unit) {
      return stockQty(units[unit]) + ' ' + esc(unit);
    }).join(' · ') || '0';
  }
  function outgoingReadinessHtml() {
    var readiness = state.outgoingReadiness;
    if (readiness === null) {
      return '<div class="card fade-in invoice-readiness"><div class="card-body"><div class="loading-inline"><div class="spinner"></div><strong>Đang đối chiếu tồn vật tư hàng hóa…</strong></div></div></div>';
    }
    if (readiness.error) {
      return '<div class="card fade-in invoice-readiness"><div class="card-body"><div class="error-summary">Chưa tính được khả năng xuất: ' +
        esc(readiness.error) + '</div><div class="form-actions"><button class="btn btn-outline" data-action="refresh-outgoing-readiness">Thử lại</button><button class="btn btn-outline" data-view="orders">Mở đơn để kiểm tra mã hàng</button><button class="btn btn-outline" data-view="inventory">Đối chiếu tồn kho</button></div></div></div>';
    }
    var rows = (readiness.rows || []).map(function (item) {
      var status = n(item.pending_qty) > 0
        ? '<span class="tag tag-warn">Còn chờ</span>'
        : n(item.invoiceable_qty) > 0
          ? '<span class="tag tag-ok">' + (item.negative_stock_allowed ? 'KKKNT · được phép âm' : 'Đủ lượng') + '</span>'
          : n(item.drafted_qty) > 0
            ? '<span class="tag">Đang giữ trong dự thảo</span>'
            : '<span class="tag tag-ok">Đã phát hành</span>';
      if (item.pending_reason) status += '<div class="muted">' + esc(item.pending_reason) + '</div>';
      return '<tr><td><strong>' + esc(item.contractor || "—") + '</strong><div class="muted">Bếp ' +
        esc(item.kitchen || "—") + '</div></td><td><strong>' + esc(item.product_name || "—") +
        '</strong><div class="muted">' + esc(item.product_code || "—") + '</div></td><td class="num-cell">' +
        num(item.demand_qty) + ' ' + esc(item.unit || "") + '</td><td class="num-cell">' +
        num(item.drafted_qty) + '</td><td class="num-cell">' +
        num(item.issued_qty) + '</td><td class="num-cell invoice-ready-qty">' +
        num(item.invoiceable_qty) + '<div class="muted">' + money(item.invoiceable_value) + '</div></td><td class="num-cell invoice-wait-qty">' +
        num(item.pending_qty) + '<div class="muted">' + money(item.pending_value) + '</div></td><td>' + status + '</td></tr>';
    }).join("");
    var contractorRows = (readiness.contractors || []).map(function (item) {
      var group = (readiness.rows || []).filter(function(row) { return row.contractor === item.contractor; });
      return '<tr><td><strong>' + esc(item.contractor) + '</strong></td><td class="num-cell">' +
        readinessQuantity(group,'demand_qty') + '</td><td class="num-cell">' + readinessQuantity(group,'drafted_qty') +
        '</td><td class="num-cell">' + readinessQuantity(group,'issued_qty') +
        '</td><td class="num-cell invoice-ready-qty">' + readinessQuantity(group,'invoiceable_qty') + '<div class="muted">' + money(item.invoiceable_value) + '</div>' +
        '</td><td class="num-cell invoice-wait-qty">' + readinessQuantity(group,'pending_qty') + '<div class="muted">' + money(item.pending_value) + '</div></td></tr>';
    }).join("");
    var allReady = n(readiness.pending_qty) <= 0;
    var stockBlocks = readiness.blocking_issues || [];
    var orderIssues = readiness.order_issues || [];
    var approved = state.data?.batch?.status === 'approved';
    return html([
      '<div class="card fade-in invoice-readiness"><div class="card-head"><div><h3>Lượng có thể lập thêm theo tồn kho</h3>',
      '<p>Phần đủ tồn và phần còn thiếu đầu vào. Tổng hàng chưa phát hành xem tại bảng cộng dồn phía trên.</p></div>',
      '<button class="btn btn-small btn-outline" data-action="refresh-outgoing-readiness">Kiểm tra lại</button></div>',
      '<div class="card-body">',
      !approved ? '<div class="warning-summary">Đơn chưa duyệt. <button class="btn btn-outline" data-view="orders">Mở đơn để sửa / duyệt</button></div>' : '',
      (readiness.negative_stock_warnings || []).length ? '<div class="warning-summary">KKKNT vẫn được lập bảng kê dù tồn âm: ' + readiness.negative_stock_warnings.map(function(r) { return esc(r.product_code) + ' (' + stockQty(r.qty) + ' ' + esc(r.unit) + ')'; }).join(' · ') + '. Số âm vẫn được theo dõi và chuyển sang tháng sau.</div>' : '',
      orderIssues.length ? '<div class="error-summary" id="invoice-order-issues"><strong>Còn ' + orderIssues.length + ' dòng đơn cần sửa trước khi lập hóa đơn.</strong>' + orderIssues.map(function(item) {
        return '<div class="stock-block-row"><span><strong>' + esc(item.product_name || item.product_code) + '</strong> · ' + esc(item.product_code) + ' · Bếp ' + esc(item.kitchen) + (item.source_row ? ' · Dòng Excel ' + esc(item.source_row) : '') + '<br>' + (item.messages || []).map(esc).join('<br>') + '</span><button class="btn btn-outline" data-action="resolve-invoice-order" data-id="' + item.order_id + '">Sửa dòng này</button></div>';
      }).join('') + '</div>' : '',
      '<div class="readiness-totals"><div><span>Tổng cần lập</span><strong>', readinessQuantity(readiness.rows,'demand_qty'),
      '</strong></div><div><span>Đã dự thảo</span><strong>', readinessQuantity(readiness.rows,'drafted_qty'),
      '</strong></div><div><span>Đã phát hành</span><strong>', readinessQuantity(readiness.rows,'issued_qty'),
      '</strong></div><div class="', stockBlocks.length || orderIssues.length || !approved ? 'waiting' : 'ready', '"><span>Phần đủ lượng</span><strong>', readinessQuantity(readiness.rows,'invoiceable_qty'),
      '</strong><span>', money(readiness.invoiceable_value), '</span></div><div class="waiting"><span>Phần còn thiếu tồn</span><strong>', readinessQuantity(readiness.rows,'pending_qty'),
      '</strong><span>', money(readiness.pending_value), '</span></div></div>',
      stockBlocks.length
        ? '<div class="error-summary" id="outgoing-stock-blocks" style="margin-top:14px"><strong>Chưa tạo được file: ' + stockBlocks.length + ' mã tồn âm.</strong><p>Mở từng mã, đối chiếu tồn đầu và nhập/xuất, sửa đúng nguồn rồi bấm Kiểm tra lại.</p>' + stockBlocks.map(function(r) { return '<div class="stock-block-row"><span>' + esc(r.product_name || r.product_code) + ' (' + esc(r.product_code) + ') đang âm <strong>' + stockQty(-r.qty) + ' ' + esc(r.unit || '') + '</strong>. Cần kiểm tra trước khi tạo file.</span><button class="btn btn-outline" data-action="show-stock-cause" data-code="' + esc(r.product_code) + '">Xử lý ' + esc(r.product_code) + '</button></div>'; }).join('') + '</div>'
        : allReady
        ? '<div class="ok-summary" style="margin-top:14px">Toàn bộ phần còn lại đủ điều kiện về tồn; hàng KKKNT được phép âm.</div>'
        : '<div class="warning-summary" style="margin-top:14px">' + (approved ? 'Có thể tạo dự thảo cho phần đủ lượng.' : 'Duyệt đơn trước khi tạo dự thảo cho phần đủ lượng.') + ' Phần còn thiếu giữ lại để lập tiếp.</div>',
      '</div><div class="table-wrap"><table><thead><tr><th>Nhà thầu</th><th>Tổng cần</th><th>Đã dự thảo</th><th>Đã phát hành</th><th>Có thể lập</th><th>Còn thiếu</th></tr></thead><tbody>',
      contractorRows || '<tr><td colspan="6"><div class="empty">Không có nhà thầu cần lập hóa đơn trong đơn hàng này.</div></td></tr>',
      '</tbody></table></div><details class="readiness-line-details"><summary>Xem chi tiết từng mặt hàng</summary><div class="table-wrap"><table><thead><tr><th>Nhà thầu / bếp</th><th>Mặt hàng</th><th>Khách đã chốt</th>',
      '<th>Đã dự thảo</th><th>Đã phát hành</th><th>Phần đủ lượng</th><th>Còn chờ đầu vào</th><th>Trạng thái</th></tr></thead><tbody>',
      rows || '<tr><td colspan="8"><div class="empty">Không có dòng cần lập hóa đơn trong đơn hàng này.</div></td></tr>',
      '</tbody></table></div></details></div>'
    ]);
  }

  function outgoingPeriodShortagesHtml(contractors) {
    var payload = state.outgoingPeriodShortages;
    contractors = Array.from(new Set(contractors.concat(
      payload && !payload.error ? (payload.contractors || []).map(function (item) {
        return item.contractor;
      }) : []
    ))).filter(Boolean).sort();
    var options = '<option value="">Tất cả nhà thầu</option>' + contractors.map(function (code) {
      return '<option value="' + esc(code) + '" ' +
        (code === state.outgoingShortageContractor ? 'selected' : '') + '>' + esc(code) + '</option>';
    }).join("");
    var rows = payload && !payload.error ? (payload.shortages || []).map(function (item) {
      return '<tr><td><strong>' + esc(item.contractor) + '</strong></td><td><strong>' +
        esc(item.product_code) + '</strong><div class="muted">' + esc(item.product_name) +
        '</div></td><td>' + esc(item.work_dates || "—") + '</td><td class="num-cell">' +
        num(item.demand_qty) + '</td><td class="num-cell">' + num(item.drafted_qty) +
        '</td><td class="num-cell">' + num(item.issued_qty) +
        '</td><td class="num-cell">' + num(item.invoiceable_qty) +
        '</td><td class="num-cell invoice-wait-qty"><strong>' + num(item.pending_qty) +
        '</strong></td><td class="num-cell">' + money(item.pending_value) + '</td></tr>';
    }).join("") : "";
    var result = payload && payload.error
      ? '<div class="error-summary" style="margin-top:14px">' + esc(payload.error) + '</div>'
      : payload
        ? html([
          '<div class="readiness-totals" style="margin-top:14px"><div><span>Tổng cần</span><strong>', num(payload.demand_qty),
          '</strong></div><div><span>Đã dự thảo</span><strong>', num(payload.drafted_qty),
          '</strong></div><div><span>Đã phát hành</span><strong>', num(payload.issued_qty),
          '</strong></div><div class="ready"><span>Có thể lập</span><strong>', num(payload.invoiceable_qty),
          '</strong></div><div class="waiting"><span>Còn thiếu</span><strong>', num(payload.pending_qty),
          '</strong></div></div><div class="table-wrap" style="margin-top:14px"><table><thead><tr><th>Nhà thầu</th><th>Mã hàng</th><th>Ngày nguồn</th><th>Tổng cần</th><th>Đã dự thảo</th><th>Đã phát hành</th><th>Có thể lập</th><th>Còn thiếu</th><th>Giá trị thiếu</th></tr></thead><tbody>',
          rows || '<tr><td colspan="9"><div class="empty">Không còn mã hàng thiếu trong kỳ đã chọn.</div></td></tr>',
          '</tbody></table></div>'
        ])
        : '<div class="muted" style="margin-top:12px">Chọn kỳ rồi bấm Xem danh sách để đối chiếu trước khi chuyển yêu cầu cuối tháng.</div>';
    return html([
      '<div class="card fade-in" style="margin-top:18px"><div class="card-head"><div><h3>Danh sách còn thiếu theo kỳ</h3>',
      '<p>Tách theo nhà thầu và mã hàng; file Excel chỉ lấy phần còn thiếu sau khi trừ dự thảo, hóa đơn đã phát hành và tồn vật tư đã ghi nhận.</p></div></div>',
      '<div class="card-body"><div class="payment-grid"><div class="form-field"><label>Từ ngày</label><input id="outgoingShortageFrom" type="date" value="',
      esc(state.outgoingShortageFrom), '"></div><div class="form-field"><label>Đến ngày</label><input id="outgoingShortageTo" type="date" value="',
      esc(state.outgoingShortageTo), '"></div><div class="form-field"><label>Nhà thầu</label><select id="outgoingShortageContractor">',
      options, '</select></div><div class="form-actions"><button class="btn btn-outline" data-action="load-outgoing-shortages" ',
      state.outgoingShortageLoading ? 'disabled' : '', '>', state.outgoingShortageLoading ? 'Đang tính…' : 'Xem danh sách',
      '</button><button class="btn btn-primary" data-action="download-outgoing-shortages">Tải Excel phần còn thiếu</button></div></div>',
      result, '</div></div>'
    ]);
  }

  function outgoingSubstitutionHtml() {
    var readiness = state.outgoingReadiness;
    var draft = state.outgoingSubstitutionDraft || {};
    var missingRows = readiness && !readiness.error ? (readiness.rows || []).filter(function (item) {
      return n(item.pending_qty) > 0;
    }) : [];
    var orderOptions = '<option value="">Chọn đúng dòng còn thiếu…</option>' + missingRows.map(function (item) {
      var selected = String(draft.order_id || "") === String(item.order_id) ? " selected" : "";
      return '<option value="' + item.order_id + '"' + selected + '>' + esc(item.contractor || "—") +
        ' · ' + esc(item.product_code || "—") + ' · ' + esc(item.product_name || "—") +
        ' · thiếu ' + num(item.pending_qty) + ' ' + esc(item.unit || "") + '</option>';
    }).join("");
    var preview = state.outgoingSubstitutionPreview;
    var previewHtml = "";
    if (preview && preview.error) {
      previewHtml = '<div id="outgoingSubstitutionPreviewResult" class="error-summary" style="margin-top:14px">' +
        esc(preview.error) + '</div>';
    } else if (preview) {
      var source = preview.price_source === "approved_override"
        ? "Giá riêng đã duyệt"
        : "Báo giá kỳ " + esc(preview.price_period || "—") +
          (preview.quote_version_no ? " · phiên bản " + num(preview.quote_version_no) : "");
      previewHtml = html([
        '<div id="outgoingSubstitutionPreviewResult" class="', preview.can_confirm ? 'ok-summary' : 'warning-summary',
        '" style="margin-top:14px"><strong>Xem trước — chưa ghi:</strong> ',
        esc(preview.original_product_code), ' → <strong>', esc(preview.substitute_product_code), '</strong> · ',
        num(preview.qty), ' ', esc(preview.unit), ' · đơn giá ', money(preview.unit_price),
        ' · thành tiền ', money(preview.amount), ' · thuế ', esc(preview.tax),
        '<div class="muted">', source, ' · tồn mã thay thế trước khi giữ: ', num(preview.substitute_available),
        ' · ', esc(preview.price_message || ""), '</div>',
        preview.can_confirm
          ? '<div class="form-actions" style="margin-top:10px"><button class="btn btn-primary" data-action="confirm-outgoing-substitution">Xác nhận đúng mã thay thế này</button></div>'
          : '<div class="muted" style="margin-top:8px">Chưa thể xác nhận. Nếu dùng giá riêng, hãy nhập giá, ghi lý do, đánh dấu đã được duyệt rồi kiểm tra lại.</div>',
        '</div><div id="outgoingSubstitutionStale" class="warning-summary" style="margin-top:10px" hidden>Dữ liệu đã thay đổi sau lần kiểm tra. Hãy bấm “Xem trước” lại trước khi xác nhận.</div>'
      ]);
    }
    var actions = state.outgoingSubstitutionActions;
    var historyRows = (actions || []).map(function (item) {
      var active = item.status === "active";
      var editable = active && item.draft_status === "draft" &&
        ["saved", "saving", "unknown"].indexOf(item.minvoice_status || "not_sent") < 0;
      var statusText = !active ? "Đã hoàn tác" : editable ? "Đang áp dụng" : "Đã khóa/phát hành";
      var statusClass = !active ? "tag-red" : editable ? "tag-warn" : "tag-ok";
      var priceSource = item.price_source === "approved_override"
        ? "Giá riêng đã duyệt"
        : "Báo giá " + esc(item.price_period || "—");
      return '<tr><td><strong>' + esc(item.original_product_code) + ' → ' +
        esc(item.substitute_product_code) + '</strong><div class="muted">' + esc(item.contractor) +
        '</div></td><td class="num-cell">' + num(item.qty) + ' ' + esc(item.unit) +
        '</td><td class="num-cell">' + money(item.unit_price) + '<div class="muted">' + priceSource +
        '</div></td><td class="num-cell"><strong>' + money(n(item.qty) * n(item.unit_price)) +
        '</strong></td><td>' + esc(item.actor) + '<div class="muted">' + esc(item.reason) +
        '</div></td><td><span class="tag ' + statusClass + '">' + statusText + '</span></td><td>' +
        (editable ? '<button class="btn btn-small btn-outline" data-action="reverse-outgoing-substitution" data-id="' +
          item.id + '">Hoàn tác</button>' : '') + '</td></tr>';
    }).join("");
    var historyTotals = (actions || []).filter(function (item) {
      return item.status === "active";
    }).reduce(function (result, item) {
      result.qty += n(item.qty);
      result.amount += n(item.qty) * n(item.unit_price);
      return result;
    }, { qty: 0, amount: 0 });
    var hasMissing = missingRows.length > 0;
    return html([
      '<div class="card fade-in" style="margin-top:18px"><div class="card-head"><div><h3>Luân chuyển / mặt hàng thay thế có xác nhận</h3>',
      '<p>Chỉ chọn từ dòng đang thiếu. Hệ thống không tự quyết định mã thay thế và không lấy giá vốn làm giá bán.</p></div>',
      '<span class="tag tag-warn">Kiểm tra → xác nhận → lưu lịch sử</span></div><div class="card-body">',
      '<div class="simple-warning"><strong>Quy tắc:</strong> người dùng tự nhập mã thay thế; đơn vị tính phải khớp; giá lấy từ báo giá đúng kỳ/nhà thầu hoặc giá riêng đã được duyệt. Dòng đơn gốc luôn được giữ nguyên.</div>',
      '<form id="outgoingSubstitutionForm" class="payment-grid" style="margin-top:14px">',
      '<div class="form-field span-2"><label>Dòng đang thiếu</label><select id="outgoingSubstitutionOrder" name="order_id" required ', hasMissing ? '' : 'disabled', '>',
      orderOptions, '</select></div>',
      '<div class="form-field"><label>Mã hàng thay thế (tự chọn)</label><input name="substitute_product_code" value="',
      esc(draft.substitute_product_code || ""), '" placeholder="Nhập đúng mã TĐP" required></div>',
      '<div class="form-field"><label>Số lượng thay thế</label><input name="qty" type="number" min="0.000001" step="any" value="',
      esc(draft.qty || ""), '" required></div>',
      '<div class="form-field"><label>Người xác nhận</label><input name="actor" value="', esc(draft.actor || ""), '" required></div>',
      '<div class="form-field span-2"><label>Lý do thay thế</label><input name="reason" value="', esc(draft.reason || ""), '" required></div>',
      '<div class="form-field"><label>Giá bán riêng (nếu có)</label><input name="override_price" type="number" min="1" step="1" value="',
      esc(draft.override_price || ""), '" placeholder="Để trống để lấy báo giá kỳ"></div>',
      '<div class="form-field span-2"><label>Lý do dùng giá riêng</label><input name="override_reason" value="',
      esc(draft.override_reason || ""), '" placeholder="Bắt buộc nếu nhập giá riêng"></div>',
      '<label class="check-line"><input name="approve_price_override" type="checkbox" ',
      draft.approve_price_override ? 'checked' : '', '> Tôi xác nhận giá riêng đã được người có thẩm quyền duyệt</label>',
      '<div class="form-actions"><button class="btn btn-outline" type="submit" ', state.outgoingSubstitutionLoading || !hasMissing ? 'disabled' : '', '>',
      state.outgoingSubstitutionLoading ? 'Đang kiểm tra…' : 'Xem trước, chưa ghi', '</button></div></form>',
      hasMissing ? '' : '<div class="muted" style="margin-top:12px">Đơn hàng này hiện không có dòng nào còn thiếu để chọn thay thế.</div>',
      previewHtml,
      '</div><div class="card-head"><div><h4>Lịch sử lựa chọn trong đơn hàng</h4><p>Giữ cả lựa chọn đã hoàn tác; không sửa lại lịch sử đơn gốc.</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Gốc → thay thế</th><th>Số lượng</th><th>Giá bán</th><th>Thành tiền</th><th>Xác nhận / lý do</th><th>Trạng thái</th><th></th></tr></thead><tbody>',
      historyRows || '<tr><td colspan="7"><div class="empty">' +
        (actions === null ? 'Đang nạp lịch sử…' : 'Chưa có lựa chọn thay thế trong đơn hàng này.') +
        '</div></td></tr>',
      '</tbody><tfoot><tr class="table-total-row"><td>TỔNG ĐANG ÁP DỤNG</td><td class="num-cell">',
      num(historyTotals.qty), '</td><td></td><td class="num-cell">', money(historyTotals.amount),
      '</td><td colspan="3"></td></tr></tfoot></table></div></div>'
    ]);
  }

  function invoicePaymentScopeHtml() {
    var scope = state.invoicePaymentScope;
    if (!scope) return "";
    if (scope.error) {
      return '<div class="card fade-in" style="margin-top:18px"><div class="card-body"><div class="error-summary">' +
        esc(scope.error) + '</div></div></div>';
    }
    var invoices = (scope.invoices || []).map(function (item) {
      var sourceText = item.verification_source === "synced_issued_source"
        ? "Đã khớp nguồn đồng bộ"
        : "Đã xác nhận phát hành trên phần mềm";
      return '<tr><td>' + dateVN(item.invoice_date) + '</td><td><strong>' +
        esc(item.invoice_series || "—") + ' / ' + esc(item.invoice_number) +
        '</strong></td><td class="num-cell">' + money(item.subtotal) +
        '</td><td class="num-cell">' + money(item.tax_amount) +
        '</td><td class="num-cell"><strong>' + money(item.total_amount) +
        '</strong></td><td><span class="tag tag-ok">' + sourceText + '</span></td></tr>';
    }).join("");
    var downloadUrl = "/api/export/invoice-payment-bundle/" + encodeURIComponent(scope.contractor) +
      "?from=" + encodeURIComponent(scope.date_from) + "&to=" + encodeURIComponent(scope.date_to) +
      "&scope_id=" + encodeURIComponent(scope.scope_id || "");
    var statementUrl = "/api/outgoing-invoices/delivery-statement/" + encodeURIComponent(scope.contractor) +
      "?from=" + encodeURIComponent(scope.date_from) + "&to=" + encodeURIComponent(scope.date_to) +
      "&scope_id=" + encodeURIComponent(scope.scope_id || "");
    return html([
      '<div class="card fade-in" style="margin-top:18px"><div class="card-head"><div><h3>Hồ sơ đề nghị thanh toán từ hóa đơn đỏ</h3>',
      '<p>Nhà thầu ', esc(scope.contractor), ' · ', dateVN(scope.date_from), ' – ', dateVN(scope.date_to),
      '</p></div><span class="tag tag-ok">Mẫu chính thức</span></div>',
      '<div class="card-body"><div class="code-note"><strong>Đã đối chiếu:</strong> ',
      esc(scope.warning), '</div>',
      '<div class="readiness-totals" style="margin-top:14px"><div><span>Số hóa đơn đỏ</span><strong>',
      num((scope.invoices || []).length), '</strong></div><div><span>Trước thuế</span><strong>',
      money(scope.totals && scope.totals.subtotal), '</strong></div><div><span>Tiền thuế</span><strong>',
      money(scope.totals && scope.totals.tax_amount), '</strong></div><div class="ready"><span>Tổng kiểm soát</span><strong>',
      money(scope.totals && scope.totals.total_amount), '</strong></div></div>',
      '<div class="form-actions" style="margin-top:14px"><button class="btn btn-primary" data-action="download-invoice-delivery-statement" data-url="',
      esc(statementUrl), '">', scope.statement_kind === 'invoices' ? 'Tải bảng kê hóa đơn VAT' : 'Tải Bảng tổng hợp giao nhận', '</button><button class="btn btn-outline" data-action="download-invoice-payment-control" data-url="',
      esc(downloadUrl), '">Tải Đề nghị thanh toán + bảng kê</button><button class="btn btn-outline" data-action="preview-payment-documents">Xem chứng từ / In</button></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Ngày HĐ</th><th>Ký hiệu / số HĐ</th><th>Trước thuế</th><th>Thuế</th><th>Tổng</th><th>Nguồn xác minh</th></tr></thead><tbody>',
      invoices, '</tbody></table></div></div>'
    ]);
  }

  function orderInvoiceExportHtml() {
    var selectedDay = (state.data.batch && state.data.batch.work_date) || currentWorkDate();
    var filters = state.orderInvoiceFilters || {from:selectedDay,to:selectedDay,contractor:''};
    var result = state.orderInvoiceExportResult;
    return '<section class="card"><div class="card-head"><div><h3>Bảng kê từ đơn hàng để đưa lên M-Invoice</h3>' +
      '<p>Đơn đã duyệt → Bảng kê theo tồn kho → Chị chủ động quyết định xuất hóa đơn.</p></div></div>' +
      '<div class="card-body"><form id="orderInvoiceExportForm" class="document-contractor-form">' +
      '<label>Nhà thầu<select name="contractor" required><option value="">Chọn nhà thầu cần xuất</option><option value="*"'+(filters.contractor==='*'?' selected':'')+'>Tất cả nhà thầu</option>' + state.data.master.contractors.map(function(item) {
        return '<option value="'+esc(item.code)+'"'+(filters.contractor===item.code?' selected':'')+'>'+esc(item.code+' · '+item.name)+'</option>';
      }).join('') + '</select></label><label>Từ ngày<input name="from" type="date" required value="'+esc(filters.from)+'"></label>' +
      '<label>Đến ngày<input name="to" type="date" required value="'+esc(filters.to)+'"></label>' +
      '<button type="submit" value="sync" class="btn btn-outline">Cập nhật hóa đơn đã ký</button>' +
      '<button type="submit" value="export" class="btn btn-primary">Tải bảng kê để up M-Invoice</button></form>' +
      '<p>Trước mỗi lần tải bảng kê, hệ thống cập nhật hóa đơn đã ký từ M-Invoice để trừ phần đã xuất. Nếu còn hóa đơn chưa khớp nhà thầu hoặc mã hàng, cần đối chiếu trước khi tải tiếp.</p>' +
      '<p>Hàng thông thường chỉ lấy lượng đủ tồn, không âm kho; phần thiếu giữ lại. KKKNT giữ ngoại lệ đã thống nhất.</p>' +
      '<p>Xuất theo ngày: chọn cùng ngày bắt đầu và kết thúc. Xuất theo tháng: chọn khoảng ngày trong tháng. Chỉ lấy nhà thầu và ngày chị chọn; tải file chưa tính là đã phát hành.</p>' +
      '<p>Một ZIP, mỗi nhà thầu một file cho từng nhóm thuế. Cùng mã và cùng giá bán cộng lượng; khác giá giữ dòng riêng để đối chiếu. Kg lấy một chữ số thập phân, phần lẻ giữ lại.</p>' +
      (result ? '<div class="code-note" role="status">'+esc(result)+'</div>' : '') + sourceScopeReviewHtml() + '</div></section>';
  }

  function sourceScopeReviewHtml() {
    if(!state.outgoingSourceReview) return '';
    return '<details open><summary>Hóa đơn đã ký vừa đối chiếu · '+state.outgoingSourceReview.length+' hóa đơn</summary>'+state.outgoingSourceReview.map(function(r){
      var status=r.scope==='outside'?'Đơn riêng · không trừ đơn đã duyệt':r.scope==='orders'?'Trừ đơn của '+r.contractor:'Chưa xác định đơn liên quan';
      return '<div class="code-note"><strong>'+esc(r.number)+' · '+esc(r.buyer)+'</strong><p>'+esc(status)+' · '+(r.stock_status==='posted'?'Đã ghi xuất kho':'Cần kiểm tra mã hàng / ghi xuất kho')+'</p>'+
        (r.error?'<p class="error-summary">'+esc(r.error)+'</p>':'')+
        '<details><summary>'+(r.scope==='unresolved'?'Chọn đơn liên quan':'Sửa phạm vi đối chiếu')+'</summary><form class="source-order-scope document-contractor-form" data-id="'+r.id+'" data-token="'+esc(r.token)+'">'+
        '<label>Hóa đơn này thuộc<select name="choice" required><option value="">Chọn đúng nguồn đơn</option><option value="outside"'+(r.scope==='outside'?' selected':'')+'>Đơn riêng, chưa đưa vào phần mềm</option>'+state.data.master.contractors.map(function(c){return '<option value="'+esc(c.code)+'"'+(r.scope==='orders'&&r.contractor===c.code?' selected':'')+'>Đơn đã duyệt · '+esc(c.code)+'</option>';}).join('')+'</select></label>'+
        '<label>Lý do xác nhận<input name="note" required placeholder="Đối chiếu theo đơn / hóa đơn nào"></label><button type="submit" class="btn btn-outline">Lưu đối chiếu</button></form></details></div>';
    }).join('')+'</details>';
  }

  function unissuedHtml() {
    var f=state.unissuedFilters || {to:currentWorkDate(),contractor:''}, d=state.unissued;
    var rows=d && d.rows || [];
    return '<section class="card"><div class="card-head"><div><h3>Hàng chưa xuất hóa đơn · cộng dồn</h3><p>Đơn đã duyệt − lượng đã phát hành. Tải bảng kê và tạo nháp không làm giảm số chưa xuất.</p></div></div><div class="card-body">'+
      '<p>Phần đủ điều kiện được giữ chờ, không cấp lại cho đơn mới. Chị chọn nhà thầu và ngày xuất ở phía trên; chưa phát hành thì vẫn cộng dồn.</p><form id="unissuedForm" class="document-contractor-form"><label>Nhà thầu<select name="contractor"><option value="">Tất cả nhà thầu</option>'+state.data.master.contractors.map(function(r){return '<option value="'+esc(r.code)+'"'+(f.contractor===r.code?' selected':'')+'>'+esc(r.code)+'</option>';}).join('')+'</select></label>'+
      '<label>Cộng dồn đến ngày<input type="date" name="to" required value="'+esc(f.to)+'"></label><button class="btn btn-outline" type="submit" value="view">Cập nhật phần chờ xuất</button><button class="btn btn-primary" type="submit" value="excel">Tải bảng chưa xuất</button></form>'+
      (d ? '<p class="code-note" role="status">Đến '+esc(dateVN(d.asof))+' · '+rows.length+' mã còn chưa xuất · '+d.unissued_order_rows+' dòng đơn nguồn. Phần đã nháp vẫn nằm trong số chưa xuất.</p>'+ (d.warnings||[]).map(function(w){return '<div class="warning-summary">'+esc(w.message)+'</div>';}).join('') : '<p>Chọn ngày để xem số chưa xuất cộng dồn từ các đơn đã duyệt.</p>')+
      (d?'<p class="code-note">'+esc(d.policy)+' Hóa đơn đã ký bên ngoài cần được tải về ở Hóa đơn đầu ra hoặc ghi nhận số hóa đơn đã phát hành, rồi bấm Xem / cập nhật.</p>':'')+
      (state.unissuedError?'<div class="error-summary">'+esc(state.unissuedError)+'</div>':'')+'</div>'+
      (d?'<div class="table-wrap" style="max-height:380px;overflow:auto"><table><thead><tr><th>Nhà thầu</th><th>Mã / Tên hàng</th><th>ĐVT</th><th>Đã duyệt</th><th>Đã phát hành</th><th>Tổng chưa xuất</th><th>Đủ điều kiện · giữ chờ xuất</th><th>Chưa đủ / chờ cộng lẻ</th></tr></thead><tbody>'+rows.map(function(r){return '<tr><td>'+esc(r.contractor)+'</td><td>'+esc(r.product_code)+' · '+esc(r.product_name)+'</td><td>'+esc(r.unit)+'</td><td>'+stockQty(r.approved_qty)+'</td><td>'+stockQty(r.issued_qty)+'</td><td>'+stockQty(r.unissued_qty)+'</td><td><strong>'+stockQty(r.ready_qty)+'</strong></td><td>'+stockQty(r.waiting_qty)+'</td></tr>';}).join('')+'</tbody></table></div>':'')+'</section>';
  }

  function paymentRequestFormHtml() {
    var d = state.data;
    if (!state.paymentFilters) {
      var day = (d.batch && d.batch.work_date) || currentWorkDate();
      state.paymentFilters = {from: day.slice(0, 7) + '-01', to: day, contractor: ''};
    }
    var filters = state.paymentFilters;
    var contractors = (d.master.contractors || []);
    return '<form id="paymentRequestForm" class="document-contractor-form">' +
      '<label>Nhà thầu<select name="contractor" class="select" required>' +
      '<option value="">Chọn nhà thầu</option>' + contractors.map(function (item) {
        return '<option value="' + esc(item.code) + '"' + (item.code === filters.contractor ? ' selected' : '') + '>' + esc(item.code + ' · ' + item.name) + '</option>';
      }).join('') + '</select></label>' +
      '<label>Từ ngày<input name="from" type="date" value="' + esc(filters.from) + '" required></label>' +
      '<label>Đến ngày<input name="to" type="date" value="' + esc(filters.to) + '" required></label>' +
      '<button class="btn btn-primary" type="submit">Xem và tải bảng kê</button></form>' + buyerProfileFormHtml();
  }

  function buyerProfileFormHtml() {
    var contractor = state.paymentFilters && state.paymentFilters.contractor;
    if (!contractor) return '<p class="muted">Chọn nhà thầu để kiểm tra hồ sơ người mua và mã số thuế liên kết hóa đơn VAT.</p>';
    var draft = (state.buyerEdits || {})[contractor];
    var buyer = draft || (state.buyerProfiles || {})[contractor] || {};
    return '<details' + (draft ? ' open' : '') + '><summary>Hồ sơ người mua · ' + esc(contractor) + '</summary>' +
      '<form id="buyerProfileForm" class="document-contractor-form" data-contractor="' + esc(contractor) + '">' +
      [['legal_name', 'Tên pháp lý'], ['tax_code', 'Mã số thuế'], ['address', 'Địa chỉ'],
       ['display_name', 'Tên người mua'], ['email', 'Email']].map(function (field) {
        return '<label>' + field[1] + '<input name="' + field[0] + '" value="' + esc(buyer[field[0]] || '') + '"' +
          (field[0] === 'address' ? ' required' : '') + '></label>';
      }).join('') + '<button type="submit" class="btn btn-outline">Lưu hồ sơ người mua</button></form></details>';
  }

  function renderDocuments() {
    var d = state.data;
    if (state.outgoingInvoices === null) setTimeout(fetchOutgoingInvoices, 0);
    if (!d.batch) {
      content.innerHTML = '<section class="card"><div class="card-body"><h3>File đưa lên M-Invoice</h3><p>Chọn đơn hàng ở thanh trên để tạo file Excel. Nếu chưa có đơn, vào Nhập &amp; sửa đơn để nạp và duyệt trước.</p><button class="btn btn-outline" data-view="orders">Mở Nhập &amp; sửa đơn</button></div></section><section class="card"><div class="card-body"><h3>Hồ sơ thanh toán từ hóa đơn VAT</h3>' +
        paymentRequestFormHtml() + '</div></section>' + invoicePaymentScopeHtml() + '<div id="paymentDocumentPreview"></div>';
      return;
    }
    if (state.outgoingReadiness === null && !state.outgoingReadinessLoading) setTimeout(fetchOutgoingReadiness, 0);
    if (state.documentDetailsOpen && state.outgoingSubstitutionActions === null && !state.outgoingSubstitutionLoading) {
      setTimeout(fetchOutgoingSubstitutions, 0);
    }
    var shortageContractors = Array.from(new Set(d.orders.map(function (item) {
      return (item.contractor || "").trim();
    }).filter(Boolean))).sort();
    var currentInvoices = (state.outgoingInvoices || []).filter(function (item) {
      return item.batch_id === state.batchId || (item.source_batch_ids || []).includes(state.batchId);
    });
    var outgoingRows = currentInvoices.map(function (item) {
      var statusText = item.status === "issued" ? "Đã phát hành" : item.status === "cancelled" ? "Đã hủy" : item.draft_kind === 'waiting' ? 'Giữ chờ xuất · chưa lập file' : "Dự thảo";
      var statusClass = item.status === "issued" ? "tag-ok" : item.status === "cancelled" ? "tag-red" : "tag-warn";
      if (item.minvoice_status === "saved" && item.status === "draft") {
        statusText = "Đã lưu M-Invoice · chờ ký";
        statusClass = "tag-ok";
      }
      var actions = item.status === "draft"
        ? '<div class="compact-controls"><button class="btn btn-small btn-primary" data-action="confirm-outgoing-issued" data-id="' +
          item.id + '">Ghi nhận hóa đơn đã phát hành</button><button class="btn btn-small btn-outline" data-action="cancel-outgoing-draft" data-id="' +
          item.id + '">Hủy & nhả tồn</button></div>'
        : item.status === "issued" && item.issued_invoice_date && item.issued_invoice_number
          ? '<button type="button" class="btn btn-small btn-outline" data-action="download-invoice-payment-control" data-url="/api/export/invoice-payment-bundle/' +
             encodeURIComponent(item.contractor) + '?from=' + encodeURIComponent(item.issued_invoice_date) +
             '&to=' + encodeURIComponent(item.issued_invoice_date) + '">Tải hồ sơ thanh toán</button>'
          : "";
      return '<tr><td><strong>' + esc(item.contractor) + '</strong><div>Lượt ' + esc(item.round_no || 1) + ' · ' + esc(item.tax_label || '') + '</div><button class="btn btn-small btn-outline" data-action="edit-invoice-buyer" data-contractor="' + esc(item.contractor) + '">Hồ sơ người mua</button></td><td>' + dateVN(item.invoice_date) +
        '</td><td class="num-cell">' + money(item.subtotal) + '</td><td class="num-cell">' + money(item.tax_amount) +
        '</td><td class="num-cell"><strong>' + money(item.total_amount) + '</strong></td><td><span class="tag ' +
        statusClass + '">' + statusText + '</span>' +
        (item.status === "issued" ? '<div class="muted">' + esc(item.issued_invoice_series || "") + ' ' +
          esc(item.issued_invoice_number || "") + ' · ' + dateVN(item.issued_invoice_date || item.invoice_date) + '</div>' : '') +
        '</td><td>' + actions + '</td></tr>';
    }).join("");
    var minvoiceForms = ((state.data && state.data.minvoice_draft_available === false) ? [] : (state.outgoingInvoices || [])).filter(function (item) {
      return (item.batch_id === state.batchId || (item.source_batch_ids || []).includes(state.batchId)) && item.status === "draft";
    }).map(function (item) {
      var buyer = item.buyer || {};
      return '<form class="minvoiceDraftForm card-body" data-id="' + item.id + '" data-contractor="' +
        esc(item.contractor) + '"><div class="card-head"><div><h4>' + esc(item.contractor) +
        ' · ' + money(item.total_amount) + '</h4><p>' +
        (item.minvoice_status === "saved" ? 'Đã lưu chờ ký · mã ' + esc(item.minvoice_remote_id || "—") :
          'Kiểm tra tại máy trước; chỉ nút Lưu nháp mới ghi lên M-Invoice') +
        '</p></div></div><div class="payment-grid"><div class="form-field"><label>Ký hiệu hóa đơn</label><input name="series" required value="' +
        esc(item.minvoice_series || "") + '" placeholder="VD: 1C26TDP"></div>' +
        '<div class="form-field"><label>Tên người mua</label><input name="display_name" value="' + esc(buyer.display_name || "") + '"></div>' +
        '<div class="form-field span-2"><label>Tên đầy đủ của công ty mua</label><input name="legal_name" value="' + esc(buyer.legal_name || "") + '"></div>' +
        '<div class="form-field"><label>Mã số thuế</label><input name="tax_code" value="' + esc(buyer.tax_code || "") + '"></div>' +
        '<div class="form-field span-2"><label>Địa chỉ</label><input name="address" required value="' + esc(buyer.address || "") + '"></div>' +
        '<div class="form-field"><label>Email</label><input name="email" type="email" value="' + esc(buyer.email || "") + '"></div>' +
        '<div class="form-actions"><button class="btn btn-outline" type="submit" name="minvoice_action" value="dry">Kiểm tra dữ liệu</button>' +
        (item.minvoice_status === "saved" ? '' : '<button class="btn btn-primary" type="submit" name="minvoice_action" value="save">Lưu nháp chờ ký</button>') +
        '</div></div></form>';
    }).join("");
    var shortagePanel = state.outgoingShortages.length ? html([
      '<div class="card fade-in" style="margin-top:18px"><div class="card-head"><div><h3>Thiếu tồn vật tư hàng hóa: ',
      state.outgoingShortages.length, ' mã hàng</h3><p>Cần bổ sung hóa đơn đầu vào hoặc tồn đầu trước khi tạo dự thảo; hệ thống không xuất âm kho.</p></div>',
      '<button class="btn btn-small btn-outline" data-view="inventory">Mở báo cáo vật tư hàng hóa</button></div>',
      '<div class="table-wrap"><table><thead><tr><th>Mã hàng</th><th>Tên hàng</th><th>Tồn dùng được</th><th>Cần bổ sung</th></tr></thead><tbody>',
      state.outgoingShortages.map(function (item) {
        return '<tr><td><strong>' + esc(item.product_code) + '</strong></td><td>' + esc(item.product_name) +
          '</td><td class="num-cell">' + num(item.available) + '</td><td class="num-cell"><strong>' +
          num(item.required) + '</strong></td></tr>';
      }).join(""), '</tbody></table></div></div>'
    ]) : "";
    var activeDrafts = currentInvoices.filter(function (item) { return item.status === "draft" && !['saved','saving','unknown'].includes(item.minvoice_status); });
    var creationBlocked = !state.outgoingReadiness || !!state.outgoingReadiness.error || (state.outgoingReadiness.blocking_issues || []).length > 0 || (state.outgoingReadiness.order_issues || []).length > 0 || n(state.outgoingReadiness.invoiceable_qty) <= 0;
    var invoiceFileAction = state.outgoingInvoices === null
      ? '<button class="btn btn-primary" disabled>Đang kiểm tra…</button>'
      : d.batch.status !== "approved"
        ? '<button class="btn btn-primary" disabled>Cần duyệt đơn trước</button><button class="btn btn-outline" data-view="orders">Mở đơn để sửa / duyệt</button>'
        : activeDrafts.length
          ? '<button class="btn btn-primary" data-action="download-document" data-url="' + exportUrl("invoices") + '">Tải ZIP hóa đơn</button><button class="btn btn-outline" data-action="create-outgoing-drafts">Tính lại dự thảo</button>'
          : '<button class="btn btn-primary" data-action="create-outgoing-drafts"' + (creationBlocked ? ' disabled' : '') + '>Tạo file tải hóa đơn</button>';
    var invalidOrderCount = d.orders.filter(function(row) { return row.errors && row.errors.length; }).length;
    if (invalidOrderCount) invoiceFileAction += '<p class="invoice-issue-error">Còn ' + invalidOrderCount + ' dòng đơn cần sửa trước khi duyệt.</p>';
    var outgoingTable = currentInvoices.length ? html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Dự thảo hóa đơn đầu ra</h3>',
      '<p>Mỗi lượt và nhóm thuế tương ứng một file. Nhập số hóa đơn sau khi phát hành trên M-Invoice.</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Nhà thầu</th><th>Ngày</th><th>Trước thuế</th><th>Thuế</th><th>Tổng</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>',
      outgoingRows || '<tr><td colspan="7"><div class="empty">' + (state.outgoingInvoices === null ? 'Đang kiểm tra…' : 'Chưa có dự thảo đầu ra.') + '</div></td></tr>',
      '</tbody></table></div></div>'
    ]) : '';
    var detailsHtml = state.documentDetailsOpen ? html([
      '<div class="document-detail-panel fade-in">', shortagePanel,
      outgoingSubstitutionHtml(), outgoingPeriodShortagesHtml(shortageContractors),
      minvoiceForms ? '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Lưu bản nháp M-Invoice</h3><p>Kiểm tra thông tin người mua trước khi lưu nháp chờ ký.</p></div></div>' + minvoiceForms + '</div>' : '',
      '</div>'
    ]) : '';
    content.innerHTML = html([
      orderInvoiceExportHtml(),
      unissuedHtml(),
      outgoingReadinessHtml(),
      state.outgoingActionError && state.outgoingActionError.batchId === state.batchId ? '<div class="error-summary" role="alert">' + esc(state.outgoingActionError.message) + '<div class="form-actions"><button class="btn btn-outline" data-action="refresh-outgoing-readiness">Kiểm tra lại</button><button class="btn btn-outline" data-view="orders">Mở đơn để kiểm tra</button></div></div>' : '',
      '<div class="document-primary-grid fade-in"><section class="document-primary-card"><div class="document-primary-icon">13</div>',
      '<div><h3>File đưa lên M-Invoice</h3><p>Tải ZIP về máy, giải nén rồi nhập file Excel vào M-Invoice để kiểm tra, ký và phát hành.</p></div><div class="document-primary-action">',
      invoiceFileAction, '</div></section>',
      '<section class="document-primary-card"><div class="document-primary-icon">KÊ</div><div><details><summary>Bảng kê từ hóa đơn đỏ · sau khi phát hành</summary>',
      '<p>Chọn nhà thầu để lấy đúng các hóa đơn Thành Đạt Phát đã phát hành.</p>',
      paymentRequestFormHtml(), '</details></div></section></div>',
      outgoingTable, invoicePaymentScopeHtml(),
      '<div id="paymentDocumentPreview"></div>',
      '<div class="card"><div class="card-head"><div><h3>Bảng kê mua hàng và biên nhận</h3><p>Xem đúng hồ sơ người bán; thiếu hoặc trùng CCCD vẫn bị chặn.</p></div><button class="btn btn-outline" data-action="preview-purchase-documents">Xem bảng kê / biên nhận</button></div><div id="purchaseDocumentPreview"></div></div>',
      '<div class="secondary-action-row"><button class="btn btn-outline" data-action="toggle-document-details">',
      state.documentDetailsOpen ? 'Ẩn xử lý chi tiết' : 'Xử lý chi tiết hóa đơn', '</button></div>',
      detailsHtml
    ]);
  }

  function renderInventoryCloseDialog() {
    if (!state.inventoryCloseOpen) return;
    var dialog = document.querySelector('.inventory-close-dialog');
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.className = 'inventory-totals-dialog inventory-close-dialog';
      dialog.setAttribute('aria-label', 'Chuyển tồn sang tháng sau');
      dialog.addEventListener('cancel', function(event) { if (state.inventoryCloseBusy) event.preventDefault(); });
      dialog.addEventListener('close', function() { state.inventoryCloseOpen = false; ++state.inventoryMonthCloseRequestSerial; dialog.remove(); });
      document.body.appendChild(dialog); dialog.showModal();
    }
    var close = state.inventoryMonthClose;
    dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Chuyển tồn sang tháng sau</h3><button class="icon-button close-period-dialog" aria-label="Đóng">×</button></div>' +
      '<label class="inventory-close-period">Tháng cần chuyển <input id="inventoryClosePeriod" type="month" value="' + esc(state.inventoryClosePeriod) + '"></label>' +
      '<p>Chuyển tồn cuối tháng đã ghi kho thành tồn đầu tháng kế tiếp. Hóa đơn còn chờ có thể ghi kho hàng loạt ngay bên dưới.</p>' + inventoryMonthCloseHtml(close) +
      (close && !close.error && (close.unposted_input_count || close.unposted_output_count) ? '<div class="compact-controls">' +
        (close.unposted_input_count ? '<button class="btn btn-primary" data-bulk-direction="input">Ghi kho đầu vào hàng loạt</button><button class="btn btn-outline" data-pending-direction="input">Xem đầu vào còn chờ</button>' : '') +
        (close.unposted_output_count ? '<button class="btn btn-primary" data-bulk-direction="output">Ghi kho đầu ra hàng loạt</button><button class="btn btn-outline" data-pending-direction="output">Xem đầu ra còn chờ</button>' : '') + '</div>' : '') +
      (close && close.problem_items && close.problem_items.length ? '<div class="form-actions"><button class="btn btn-primary" data-close-remap>Xuất · Sửa mã nội bộ bằng Excel</button><button class="btn btn-outline" data-close-bk>Bảng kê mua vào bổ sung</button></div><div class="table-wrap"><table><thead><tr><th>Mã cần kiểm tra</th><th>Tên hàng</th><th>ĐVT</th><th>Tồn cuối</th><th>Giá trị tồn cuối</th><th>Xử lý</th></tr></thead><tbody>' + close.problem_items.map(function(item) {
        return '<tr class="invoice-row-issue"><td>' + esc(item.product_code) + '</td><td>' + esc(item.product_name) + '</td><td>' + esc(item.unit) + '</td><td>' + stockQty(item.closing_qty) + '</td><td>' + stockMoney(item.closing_value) + '</td><td>' + (item.negative_stock_allowed ? 'KKKNT · được chuyển tồn âm' : 'Đối chiếu tồn đầu hoặc sửa mã xuất') + '</td></tr>';
      }).join('') + '</tbody></table></div>' : '');
    dialog.querySelector('.close-period-dialog').onclick = function() { if (!state.inventoryCloseBusy) dialog.close(); };
    var remapButton = dialog.querySelector('[data-close-remap]');
    if (remapButton) remapButton.onclick = function() { dialog.close(); openOutputStockRemap(close.date_from, close.date_to); };
    var bkButton = dialog.querySelector('[data-close-bk]');
    if (bkButton) bkButton.onclick = function() { dialog.close(); state.inventoryDataToolsOpen = true; navigate('inventory'); document.getElementById('inventoryDataTools')?.scrollIntoView(); };
    dialog.querySelector('#inventoryClosePeriod').onchange = async function(event) {
      if (state.inventoryCloseBusy || !/^\d{4}-\d{2}$/.test(event.target.value)) return;
      state.inventoryClosePeriod = event.target.value; state.inventoryMonthClose = null;
      renderInventoryCloseDialog(); await loadInventoryMonthClose();
    };
    dialog.querySelectorAll('[data-action]').forEach(function(button) { button.onclick = async function() {
      if (state.inventoryCloseBusy) return;
      if (button.dataset.action === 'close-inventory-month') await closeInventoryMonth(button);
      if (button.dataset.action === 'reopen-inventory-month') await reopenInventoryMonth(button);
      if (button.dataset.action === 'reload-inventory-close') { state.inventoryMonthClose = null; renderInventoryCloseDialog(); await loadInventoryMonthClose(); }
    }; });
    dialog.querySelectorAll('[data-pending-direction]').forEach(function(button) { button.onclick = function() {
      state.invoiceDirection = button.dataset.pendingDirection; state.invoiceFrom = close.date_from; state.invoiceTo = close.date_to;
      state.invoiceStatus = 'all'; state.invoiceLineFilter = 'all'; state.invoicePending = true;
      state.invoiceWorkbench = null; state.invoiceListing = null; persistInvoiceWorkbenchFilters(); dialog.close(); navigate('msmi');
    }; });
    dialog.querySelectorAll('[data-bulk-direction]').forEach(function(button) { button.onclick = async function() {
      if (state.inventoryCloseBusy) return;
      var direction = button.dataset.bulkDirection;
      var query = '?from=' + encodeURIComponent(close.date_from) + '&to=' + encodeURIComponent(close.date_to) + '&status=all&line_filter=all';
      await window.TdpReceiptReview({direction:direction, api:api, query:query, esc:esc, money:stockMoney, qty:stockQty, date:dateVN,
        onPosted:async function(result) {
          state.inventoryValuation = null; state.inventoryMonthClose = null; state.outgoingReadiness = null;
          state.invoiceWorkbench = null; state.invoiceListing = null;
          await loadInventoryMonthClose();
          showToast('Đã ghi kho ' + result.posted_count + ' hóa đơn. Đã tính lại tồn cuối tháng.');
        }});
    }; });
    if (state.inventoryCloseBusy) dialog.querySelectorAll('button,input').forEach(function(el) { el.disabled = true; });
  }

  function inventoryMonthCloseHtml(close) {
    if (!close) {
      return '<div class="inventory-month-close"><div><strong>Đang kiểm tra trạng thái chốt tháng…</strong></div></div>';
    }
    if (close.error) {
      return '<div class="inventory-month-close inventory-month-close-error"><div><strong>Chưa kiểm tra được việc chốt tháng</strong>' +
        '<p>' + esc(close.error) + '</p></div><button class="btn btn-outline" data-action="reload-inventory-close">Thử lại</button></div>';
    }
    var statusLabel = {
      not_closed: "Chưa chốt",
      closed: "Đã chốt",
      reopened: "Đang làm lại",
      needs_reclose: "Cần chốt lại"
    }[close.status] || "Chưa chốt";
    var statusClass = close.status === "closed" ? "tag-ok" : "tag-warn";
    var issueHtml = (close.issues || []).length
      ? '<div class="inventory-close-warning">' + (close.issues || []).map(function (item) {
          return '<span>• ' + esc(item) + '</span>';
        }).join("") + '</div>'
      : '';
    var replacementWarning = close.has_existing_next_opening && close.status !== "closed"
      ? '<p class="inventory-close-note">Tồn đầu tháng ' + esc(close.next_period_label) +
        ' đang có dữ liệu. Khi xác nhận, hệ thống sẽ thay bằng đúng tồn cuối tháng ' +
        esc(close.period_label) + ' và không cộng chồng.</p>' : '';
    var movementWarning = close.next_movement_count
      ? '<p class="inventory-close-note">Tháng ' + esc(close.next_period_label) + ' đã có ' +
        stockQty(close.next_movement_count) + ' phát sinh. Hệ thống sẽ kiểm tra lại để không bị âm kho.</p>' : '';
    var unpostedWarning = close.unposted_input_count || close.unposted_output_count
      ? '<p class="inventory-close-note">Còn ' + stockQty(close.unposted_input_count) + ' hóa đơn đầu vào và ' + stockQty(close.unposted_output_count) + ' hóa đơn đầu ra chưa ghi kho. Chốt tháng chỉ chuyển số liệu đã ghi kho; không tự ghi các hóa đơn còn lại.</p>' : '';
    var action = '';
    if (close.can_close) {
      action = '<button class="btn btn-primary" data-action="close-inventory-month" data-period="' +
        esc(close.period) + '" data-period-label="' + esc(close.period_label) +
        '" data-next-period-label="' + esc(close.next_period_label) + '" data-source-hash="' +
        esc(close.source_hash) + '" data-target-hash="' + esc(close.target_hash) + '">Chốt tháng ' +
        esc(close.period_label) + ' và chuyển sang ' + esc(close.next_period_label) + '</button>';
    }
    if (close.can_reopen) {
      action += '<button class="btn btn-outline" data-action="reopen-inventory-month" data-period="' +
        esc(close.period) + '" data-period-label="' + esc(close.period_label) +
        '" data-next-period-label="' + esc(close.next_period_label) + '">Mở lại tháng ' +
        esc(close.period_label) + '</button>';
    }
    var history = (close.history || []).map(function (entry) { return '<tr><td>' + esc(entry.created_at) + '</td><td>' + (entry.action === "close" ? "Chốt và chuyển tồn" : "Mở lại tháng") + '</td><td>' + esc(entry.actor || "Chưa ghi tên (lịch sử cũ)") + '</td></tr>'; }).join("");
    return '<div class="inventory-month-close"><div class="inventory-close-main"><div class="inventory-close-title">' +
      '<div><span class="eyebrow">CHỐT KHO THEO THÁNG</span><h3>Tháng ' + esc(close.period_label) +
      ' → tồn đầu tháng ' + esc(close.next_period_label) + '</h3></div><span class="tag ' + statusClass + '">' +
      esc(statusLabel) + '</span></div><div class="inventory-close-totals"><span><small>Số mặt hàng</small><strong>' +
      stockQty(close.nonzero_item_count) + '</strong></span><span><small>Tổng lượng tồn cuối</small><strong>' +
      esc(Object.keys(close.qty_by_unit || {}).map(function (unit) { return stockQty(close.qty_by_unit[unit]) + " " + unit; }).join(" · ") || stockQty(close.total_qty)) + '</strong></span><span><small>Tổng giá trị tồn cuối</small><strong>' +
      stockMoney(close.total_value) + '</strong></span></div>' + (close.kkknt_negative_count ? '<p class="warning-summary">Có ' + close.kkknt_negative_count + ' mã KKKNT âm: được chuyển nguyên số âm sang tháng sau; có thể lập bảng kê mua vào bổ sung.</p>' : '') + replacementWarning + movementWarning + unpostedWarning + issueHtml +
      '</div><div class="inventory-close-action">' + (action ? '<label>Người xác nhận<input id="inventoryCloseActor" class="input-date" type="text" maxlength="100" placeholder="Nhập họ tên" value="' + esc(state.inventoryCloseActor) + '"></label>' : '') + action + '</div></div>' +
      '<details class="inventory-close-history"><summary>Lịch sử chốt / mở tháng (50 lần gần nhất)</summary><div class="table-wrap"><table><thead><tr><th>Thời gian</th><th>Thao tác</th><th>Người xác nhận</th></tr></thead><tbody>' + (history || '<tr><td colspan="3">Chưa có lịch sử chốt tháng này.</td></tr>') + '</tbody></table></div><small>Tên do người thao tác nhập khi xác nhận; không phải tài khoản đăng nhập riêng.</small></details>';
  }

  async function openInvoiceStock(direction, id) {
    var serial = ++state.inventoryTraceRequestSerial;
    var trace = await api("/api/invoice-inventory/source/" + encodeURIComponent(direction) + "/" + encodeURIComponent(id));
    if (serial !== state.inventoryTraceRequestSerial) return;
    state.inventoryTrace = trace;
    var invoiceDate = trace.invoice.invoice_date;
    state.inventoryFrom = invoiceDate.slice(0, 7) + "-01";
    var nextMonth = new Date(Number(invoiceDate.slice(0,4)), Number(invoiceDate.slice(5,7)), 0);
    state.inventoryTo = invoiceDate.slice(0, 7) + "-" + String(nextMonth.getDate()).padStart(2, "0");
    if (serial !== state.inventoryTraceRequestSerial) return;
    navigate("inventory");
    var panel = document.getElementById("invoice-stock-trace");
    if (panel) panel.scrollIntoView({block:"start"});
  }

  function inventoryTraceHtml() {
    var trace = state.inventoryTrace;
    if (!trace) return "";
    var invoice = trace.invoice, quantities = {}, amount = 0;
    var rows = trace.events.map(function (event) {
      var unit = event.product_unit || "Không có ĐVT";
      quantities[unit] = (quantities[unit] || 0) + n(event.qty_delta);
      var value = n(event.qty_delta) * n(event.unit_cost);
      amount += value;
      return '<tr><td>' + dateVN(event.txn_date) + '</td><td>' + esc(event.event_type === "REVERSAL" ? "Hoàn tác" : trace.direction === "input" ? "Nhập kho" : "Xuất kho") + '</td><td>' + event.source_line_index + '</td><td><strong>' + esc(event.product_code) + '</strong></td><td>' + esc(event.product_name) + '</td><td>' + esc(unit) + '</td><td class="num-cell">' + stockQty(event.qty_delta) + '</td><td class="num-cell">' + stockMoney(event.unit_cost) + '</td><td class="num-cell">' + stockMoney(value) + '</td></tr>';
    }).join("");
    var qty = Object.keys(quantities).map(function (unit) { return stockQty(quantities[unit]) + " " + esc(unit); }).join(" · ") || "0";
    return '<div class="card invoice-stock-trace" id="invoice-stock-trace"><div class="card-head"><div><h3>Hàng đã ghi kho của hóa đơn ' + esc(invoice.invoice_series + " / " + invoice.invoice_number) + '</h3><p>' + dateVN(invoice.invoice_date) + ' · ' + esc(invoice.partner_name) + '</p></div><div class="compact-controls"><button class="btn btn-outline" data-action="back-invoice-workbench">Quay lại hóa đơn</button><button class="btn btn-outline" data-action="clear-invoice-stock">Bỏ chọn hóa đơn</button></div></div><div class="code-note">Đây là lịch sử đúng hóa đơn đã chọn, không phải tổng nhập cả tháng. Dấu + tăng kho, dấu − giảm kho. Giá trị là giá vốn lưu khi ghi sổ; báo cáo tháng bên dưới tính lại giá bình quân theo toàn bộ phát sinh.</div><div class="table-wrap invoice-lines-scroll"><table><thead><tr><th>Ngày kho</th><th>Thao tác</th><th>Dòng HĐ</th><th>Mã kho</th><th>Tên hàng</th><th>ĐVT</th><th>Tăng / giảm lượng</th><th>Giá vốn lúc ghi sổ</th><th>Tăng / giảm giá trị</th></tr></thead><tbody>' + (rows || '<tr><td colspan="9">Hóa đơn này chưa có bút toán ghi kho.</td></tr>') + '</tbody><tfoot><tr class="table-total-row"><td colspan="6">TỔNG THAY ĐỔI CỦA HÓA ĐƠN</td><td>' + qty + '</td><td></td><td class="num-cell">' + stockMoney(amount) + '</td></tr></tfoot></table></div></div>';
  }

  function renderInventory() {
    if (state.inventoryDataToolsOpen && state.bkDocuments == null) {
      state.bkDocuments = [];
      loadBkDocuments();
    }
    var valid = state.inventoryFrom && state.inventoryTo && state.inventoryFrom <= state.inventoryTo;
    var exportQuery = "?from=" + encodeURIComponent(state.inventoryFrom) + "&to=" + encodeURIComponent(state.inventoryTo);
    content.innerHTML = inventoryTraceHtml() + html([
      '<div class="card inventory-primary-card"><div class="inventory-primary-range"><div><h3>Báo cáo vật tư hàng hóa</h3>',
      '<p>NXT và Tồn trong kỳ dùng giá bình quân cả tháng theo từng mã, giữ T/Suất. Tồn trong kỳ là báo cáo tồn cuối tháng riêng; Xuất theo doanh thu M-Invoice. Chọn trọn một tháng để xem các báo cáo tồn và tải bộ ZIP.</p></div><div class="compact-controls">',
      '<button class="btn btn-primary" data-action="open-inventory-close">Chuyển tồn sang tháng sau</button>',
      '<label>Từ ngày <input id="inventoryFrom" class="input-date" type="date" value="', esc(state.inventoryFrom), '"></label>',
      '<label>Đến ngày <input id="inventoryTo" class="input-date" type="date" value="', esc(state.inventoryTo), '"></label>',
      '</div></div><div class="inventory-export-grid">',
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/invoice-valuation/export', exportQuery, '"', valid ? '' : ' disabled', '>Tải 5 báo cáo ZIP</button>',
      [['opening','Tồn đầu kỳ'],['input','Nhập'],['output','Xuất · giá bán hóa đơn'],['nxt','Nhập – xuất – tồn'],['closing','Tồn trong kỳ']].map(function(item) {
        return '<button class="btn ' + (item[0] === 'output' ? 'btn-primary' : 'btn-outline') + '" data-action="preview-inventory-report" data-kind="' + item[0] + '"' + (valid ? '' : ' disabled') + '>' + item[1] + '</button>';
      }).join(''),
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/invoice-valuation/export/closing', exportQuery, '"', valid ? '' : ' disabled', '>Tải Excel tồn trong kỳ</button>',
      '<button class="btn btn-primary" data-action="open-output-stock-remap"', valid ? '' : ' disabled', '>Xuất · Đổi mã nội bộ qua Excel</button>',
      '</div>', valid ? '' : '<p class="error-summary">Chọn đủ ngày; Từ ngày không được lớn hơn Đến ngày.</p>', '</div>',
      inventoryDataToolsHtml()
    ]);
    var dataTools = document.getElementById('inventoryDataTools');
    dataTools.ontoggle = function() {
      state.inventoryDataToolsOpen = dataTools.open;
      if (dataTools.open && state.bkDocuments == null) { state.bkDocuments=[]; loadBkDocuments(); }
    };
  }

  function inventoryDataToolsHtml() {
    return html([
      '<details id="inventoryDataTools" class="card inventory-data-tools"', state.inventoryDataToolsOpen || state.openingImportPreview || state.bkImportPreview ? ' open' : '', '>',
      '<summary class="card-head">Nhập tồn đầu, bảng kê mua vào và lịch sử</summary><div class="card-body">',
      '<h3>Nhập tồn đầu kỳ</h3><p>Chọn đúng kỳ cần nhập. Có thể nhập từng mã hoặc nạp Excel; hệ thống kiểm tra trước khi ghi.</p>',
      '<form id="openingForm" class="payment-grid"><div class="form-field"><label>Kỳ<input name="period" type="month" value="', esc(state.opsMonth), '" required></label></div>',
      '<div class="form-field"><label>Mã hàng<input name="product_code" required></label></div>',
      '<div class="form-field"><label>Số lượng<input name="qty" type="number" step="any" required></label></div>',
      '<div class="form-field"><label>Đơn giá vốn<input name="unit_cost" type="number" step="any" min="0"></label></div>',
      '<button class="btn btn-primary" type="submit">Lưu tồn đầu</button>',
      '<button class="btn btn-outline" type="button" data-action="choose-opening-workbook">Nạp Excel tồn đầu kỳ</button></form>',
      openingImportPreviewHtml(),
      '<h3>Bảng kê mua vào không có hóa đơn</h3><p>Tải mẫu, điền dữ liệu rồi chọn file để kiểm tra trước khi xác nhận nhập kho.</p><div class="form-actions">',
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/bk-import/template">Tải mẫu trắng</button>',
      state.batchId ? '<button class="btn btn-outline" data-action="download-document" data-url="/api/bk-import/template?batch_id=' + encodeURIComponent(state.batchId) + '">Tải theo đơn đang chọn</button>' : '',
      '<button class="btn btn-primary" data-action="choose-bk-workbook">Chọn file bảng kê đã sửa</button>',
      '<button class="btn btn-outline" data-action="reload-bk-documents">Tải lại lịch sử bảng kê</button></div>',
      bkImportPreviewHtml(), bkDocumentsHtml(),
      '<details><summary>Điều chỉnh dùng nội bộ</summary><p>Điều chỉnh này có lịch sử, không dùng để mở khóa xuất hóa đơn.</p>',
      '<form id="inventoryAdjustmentForm" class="payment-grid"><div class="form-field"><label>Ngày<input name="txn_date" type="date" value="',esc(state.opsDate),'" required></label></div>',
      '<div class="form-field"><label>Mã hàng<input name="product_code" required></label></div>',
      '<div class="form-field"><label>Số lượng (+ tăng / − giảm)<input name="qty" type="number" step="any" required></label></div>',
      '<div class="form-field"><label>Lý do<input name="note" required></label></div><button class="btn btn-outline" type="submit">Ghi điều chỉnh</button></form></details>',
      '</div></details>'
    ]);
  }

  var inventoryPreviewSerial = 0;
  function openOutputStockRemap(from, to) {
    window.TdpOutputStockRemap({api:api, downloadFile:downloadFile, esc:esc, from:from, to:to, onApplied:async function() {
      state.inventoryValuation = null; state.inventoryMonthClose = null;
      state.invoiceWorkbench = null; state.invoiceListing = null;
      await loadData();
    }});
  }

  async function previewInventoryReport(button) {
    var serial = ++inventoryPreviewSerial, from = state.inventoryFrom, to = state.inventoryTo;
    if (!from || !to || from > to) { showToast('Khoảng ngày chưa hợp lệ.', true); return; }
    var label = button.textContent, kind = button.dataset.kind;
    button.disabled = true; button.textContent = 'Đang mở…';
    try {
      var result = await api('/api/invoice-valuation/preview/' + encodeURIComponent(kind) + '?from=' + encodeURIComponent(from) + '&to=' + encodeURIComponent(to));
      if (serial !== inventoryPreviewSerial || state.view !== 'inventory' || state.inventoryFrom !== from || state.inventoryTo !== to || !button.isConnected) return;
      await window.TDPWorksheet.open({title:label + ' · ' + dateVN(from) + ' → ' + dateVN(to), editable:false, workbookData:result.workbook});
    } catch(error) {
      if (serial === inventoryPreviewSerial && state.view === 'inventory' && button.isConnected) showToast(error.message, true);
    } finally {
      if (button.isConnected) { button.disabled=false; button.textContent=label; }
    }
  }

  var invoiceVirtual = null;
  function invoiceCheckedRows() {
    return invoiceVirtual ? invoiceVirtual.checked() : Array.from(content.querySelectorAll('.invoice-group-select:checked'));
  }
  function invoicePendingEdit() {
    if (invoiceVirtual) return invoiceVirtual.nodes().map(function(r){return r.querySelector('.invoice-mapping-cell[data-editing-id]');}).find(Boolean);
    return content.querySelector('.invoice-mapping-cell[data-editing-id]');
  }
  function renderMsmi() {
    if (!state.invoiceWorkbench || !state.invoiceListing) { loadInvoiceWorkbench(); return; }
    invoiceVirtual?.dispose();
    content.innerHTML = (state.stockResolutionReturn ? '<div class="warning-summary">Đang đối chiếu nguồn tồn cho phiên đơn. <button class="btn btn-primary" data-action="return-stock-resolution">Quay lại bảng kê · Kiểm tra lại</button></div>' : '') + window.TdpInvoiceWorkbench(state, {esc:esc, num:stockQty, money:stockMoney, dateVN:dateVN});
    invoiceVirtual = window.TdpInvoiceVirtualTable(content.querySelector('.invoice-lines-card .invoice-lines-scroll'), state.invoiceListing.lines || [], window.TdpInvoiceRenderRow);
  }

  async function loadMsmiProductOptions(input) {
    var productList = document.getElementById("msmiProductOptions");
    if (!productList || !input || !input.isConnected || document.activeElement !== input) return;
    var version = ++msmiProductSearchVersion;
    var value = input.value;
    var term = input.value.trim() || input.dataset.sourceName || "";
    productList.innerHTML = "";
    function currentSearch() {
      return version === msmiProductSearchVersion && input.isConnected &&
        document.activeElement === input && input.value === value &&
        document.getElementById("msmiProductOptions") === productList;
    }
    if (term.length < 2) return;
    try {
      var result = await api("/api/products/search?q=" + encodeURIComponent(term));
      if (!currentSearch()) return;
      productList.innerHTML = (result.items || []).map(function (product, index) {
        var label = product.code + " · " + product.name;
        if (product.unit) label += " · " + product.unit;
        if (product.invoice_name && product.invoice_name !== product.name) label += " · Tên trên hóa đơn: " + product.invoice_name;
        return '<button type="button" tabindex="-1" role="option" aria-selected="false" id="invoice-product-option-' + index + '" data-product-code="' + esc(product.code) + '" data-product-name="' + esc(product.name) + '" data-product-unit="' + esc(product.unit) + '">' + esc(label) + '</button>';
      }).join("");
      if (!(result.items || []).length) productList.innerHTML = '<div class="invoice-product-hint">Không tìm thấy mã. Hãy thử tên hoặc mã khác.</div>';
      else productList.innerHTML += '<div class="invoice-product-hint">Chọn mã bằng chuột hoặc ↑ ↓ rồi Enter. Sau đó Enter/Ghi nhớ để lưu. Tìm cụ thể hơn nếu chưa thấy mã cần chọn.</div>';
      showMsmiProductOptions(input, productList);
    } catch (error) {
      if (currentSearch()) showToast(error.message, true);
    }
  }

  function mealPaymentDocumentTypeText(value) {
    if (value === "MEAL_SIMPLE") return "Đề nghị thanh toán (Word)";
    if (value === "MEAL_BOT_BUNDLE") return "Bộ chứng từ thanh toán BOT (Excel)";
    return value || "Chưa chọn loại chứng từ";
  }

  function renderKitchen() {
    var o = state.operations;
    if (!o) { loadOperations(); return; }
    var attendanceTotals = o.meal_attendance_totals || { actual: 0, ordered: 0, rows: 0, kitchens: 0 };
    var attendanceRows = (o.meal_attendance || []).slice(0, 240).map(function (item) {
      var difference = item.ordered_count ? item.actual_count - item.ordered_count : null;
      return '<tr><td>' + dateVN(item.work_date) + '</td><td><strong>' + esc(item.kitchen) +
        '</strong></td><td>' + esc(item.shift) + '</td><td class="num-cell"><strong>' +
        num(item.actual_count) + '</strong></td><td class="num-cell">' +
        (item.ordered_count ? num(item.ordered_count) : "—") + '</td><td class="num-cell">' +
        (difference === null ? "—" : num(difference)) + '</td></tr>';
    }).join("");
    var poApproved = o.meal_plans.length && o.meal_plans.every(function (plan) {
      return plan.status === "approved";
    });
    var cards = o.meal_plans.map(function (plan) {
      var lines = plan.items.map(function (item) {
        return '<div class="group-line"><div><strong>' + esc(item.product_name) + '</strong><span>' +
          esc(item.dish_name) + ' · ' + esc(item.price_source) + '</span></div><strong>' +
          num(item.required_qty) + ' ' + esc(item.unit) + ' · ' + money(item.cost) + '</strong></div>';
      }).join("");
      return '<div class="group-card"><div class="group-title"><div><strong>' + esc(plan.kitchen) +
        ' · ' + esc(plan.shift) + '</strong><span>' + num(plan.meal_count) + ' suất tổng' +
        (plan.menu_count > 1 ? ' · ' + plan.menu_count + ' thực đơn × ' + num(plan.servings_per_menu) : '') + ' · XCOM ' +
        esc(plan.mapped_unit || "CHƯA GHÉP") + '</span></div><span class="tag ' +
        (plan.status === "approved" ? "tag-ok" : plan.warnings.length ? "tag-red" : "tag-warn") + '">' +
        esc(mealPlanStatusText(plan.status)) + '</span></div><div class="group-list">' + lines +
        '</div><div class="group-total"><span>Doanh thu ' + money(plan.revenue) + ' · Tổng chi/suất ' + money(plan.cost_per_meal) +
        '</span><strong>LN ' + money(plan.profit) + '</strong></div>' +
        (plan.warnings.length ? '<div class="code-note"><strong>Cần kiểm tra:</strong> ' + esc(plan.warnings.join(' · ')) + '</div>' : '') +
        (plan.status !== "approved" ? '<button class="btn btn-small btn-primary" data-action="approve-meal-plan" data-id="' + plan.id + '">Duyệt kế hoạch</button>' : '') + '</div>';
    }).join("");
    var unitRows = o.kitchen_units.map(function (item) {
      return '<div class="group-line"><div><strong>' + esc(item.kitchen_code) +
        '</strong></div><strong>' + esc(item.unit_code) + '</strong></div>';
    }).join("");
    var paymentProfiles = o.xcom_payment_profiles || [];
    var paymentProfileOptions = paymentProfiles.map(function (profile) {
      return '<option value="' + esc(profile.profile_code) + '">' + esc(profile.profile_code) +
        ' · ' + esc(profile.display_name || profile.recipient_name || profile.document_type) + '</option>';
    }).join("");
    var paymentDocumentRequest = state.xcomPaymentRequest || {
      profile_code: paymentProfiles.length ? paymentProfiles[0].profile_code : "",
      date_from: state.opsMonth + "-01",
      date_to: state.opsDate,
      issue_date: currentWorkDate()
    };
    var paymentDocumentProfileOptions = paymentProfiles.map(function (profile) {
      return '<option value="' + esc(profile.profile_code) + '"' +
        (profile.profile_code === paymentDocumentRequest.profile_code ? ' selected' : '') + '>' +
        esc(profile.profile_code) + ' · ' + esc(profile.display_name || profile.recipient_name || profile.document_type) +
        '</option>';
    }).join("");
    var paymentProfileRows = paymentProfiles.map(function (profile) {
      var scopes = (profile.scopes || []).map(function (scope) {
        var scopeLabel = scope.scope_type === "KITCHEN" ? "Bếp" : "Xưởng cơm";
        return '<span class="tag">' + scopeLabel + ' ' + esc(scope.scope_code) +
          ' <button type="button" class="icon-button danger" title="Bỏ nơi áp dụng" data-action="delete-xcom-payment-scope" data-scope-type="' +
          esc(scope.scope_type) + '" data-scope-code="' + esc(scope.scope_code) + '">×</button></span>';
      }).join(" ");
      var tariffs = (profile.tariffs || []).map(function (tariff) {
        return '<span class="tag tag-ok">' + esc(tariff.period) + ' · ' + esc(tariff.shift) + ' · ' +
          money(tariff.unit_price) + ' <button type="button" class="icon-button danger" title="Xóa giá kỳ" data-action="delete-xcom-meal-tariff" data-profile="' +
          esc(profile.profile_code) + '" data-period="' + esc(tariff.period) + '" data-shift="' +
          esc(tariff.shift) + '">×</button></span>';
      }).join(" ");
      return '<div class="group-line"><div><strong>' + esc(profile.profile_code) + ' · ' +
        esc(profile.display_name || profile.recipient_name) + '</strong><span>' + esc(mealPaymentDocumentTypeText(profile.document_type)) +
        ' · Thuế GTGT ' + esc(profile.vat_rate) + '% · ' + esc(profile.bank_name || "Chưa có ngân hàng") +
        '</span><div class="compact-controls" style="margin-top:6px">' +
        (scopes || '<span class="tag tag-red">Chưa chọn nơi áp dụng</span>') + '</div><div class="compact-controls" style="margin-top:6px">' +
        (tariffs || '<span class="tag tag-red">Chưa có giá đúng kỳ</span>') +
        '</div></div><button type="button" class="icon-button danger" title="Xóa hồ sơ" data-action="delete-xcom-payment-profile" data-profile="' +
        esc(profile.profile_code) + '">×</button></div>';
    }).join("");
    var paymentPreview = state.xcomPaymentPreview && state.xcomPaymentPreview.summary;
    var paymentPreviewHtml = paymentPreview ? '<div class="code-note" style="margin-top:12px"><strong>Đối chiếu trước khi tải:</strong> ' +
      num(paymentPreview.actual_count) + ' suất thực tế · trước thuế ' + money(paymentPreview.subtotal) +
      ' · thuế GTGT ' + money(paymentPreview.vat_amount) + ' · tổng ' + money(paymentPreview.total) +
      ' · loại ' + esc(mealPaymentDocumentTypeText(paymentPreview.document_type)) + '<br><span class="muted">Chỉ tải được một lần; hết hạn lúc ' +
      esc((state.xcomPaymentPreview.expires_at || "").replace("T", " ")) + '.</span></div>' : '';
    var xcomPaymentModuleHtml = html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Hồ sơ và chứng từ thanh toán suất ăn</h3><p>Chỉ tính suất thực tế; đơn giá bắt buộc đúng kỳ. Phần mềm không tự điền mã số thuế, người ký hoặc tài khoản.</p></div></div><div class="card-body">',
      '<details><summary><strong>Tạo/cập nhật hồ sơ đầy đủ</strong></summary><form id="xcomPaymentProfileForm" class="payment-grid" style="margin-top:12px">',
      '<div class="form-field"><label>Mã hồ sơ</label><input name="profile_code" placeholder="BOT" required></div>',
      '<div class="form-field"><label>Tên hiển thị</label><input name="display_name" placeholder="BOT Cầu Bạch Đằng"></div>',
      '<div class="form-field"><label>Loại chứng từ</label><select name="document_type"><option value="MEAL_SIMPLE">Đề nghị thanh toán (Word)</option><option value="MEAL_BOT_BUNDLE">Bộ chứng từ thanh toán BOT (Excel)</option></select></div>',
      '<div class="form-field"><label>Thuế GTGT (%)</label><input name="vat_rate" type="number" min="0" max="100" step="0.01" value="0" required></div>',
      '<div class="form-field span-2"><label>Đơn vị đề nghị / bên bán</label><input name="issuer_name" required></div>',
      '<div class="form-field"><label>Mã số thuế bên bán</label><input name="issuer_tax_code"></div><div class="form-field span-2"><label>Địa chỉ bên bán</label><input name="issuer_address"></div>',
      '<div class="form-field span-2"><label>Đơn vị nhận / bên mua</label><input name="recipient_name" required></div>',
      '<div class="form-field"><label>Mã số thuế bên mua</label><input name="recipient_tax_code"></div><div class="form-field span-2"><label>Địa chỉ bên mua</label><input name="recipient_address"></div>',
      '<div class="form-field"><label>Số hợp đồng</label><input name="contract_no"></div><div class="form-field"><label>Ngày hợp đồng</label><input name="contract_date" type="date"></div>',
      '<div class="form-field span-2"><label>Đơn vị thụ hưởng</label><input name="beneficiary_name" required></div>',
      '<div class="form-field"><label>Số tài khoản</label><input name="bank_account" required></div><div class="form-field span-2"><label>Ngân hàng</label><input name="bank_name" required></div>',
      '<div class="form-field"><label>Người đề nghị</label><input name="requester" required></div>',
      '<div class="form-field"><label>Người ký bên bán</label><input name="seller_signer_name"></div><div class="form-field"><label>Chức vụ bên bán</label><input name="seller_signer_title"></div>',
      '<div class="form-field"><label>Người ký bên mua</label><input name="buyer_signer_name"></div><div class="form-field"><label>Chức vụ bên mua</label><input name="buyer_signer_title"></div>',
      '<button class="btn btn-primary" type="submit">Lưu hồ sơ</button></form></details>',
      '<div class="section-grid" style="margin-top:14px"><form id="xcomPaymentScopeForm" class="payment-grid"><div class="form-field"><label>Hồ sơ</label><select name="profile_code" required>', paymentProfileOptions, '</select></div>',
      '<div class="form-field"><label>Áp dụng cho</label><select name="scope_type"><option value="XCOM">Xưởng cơm</option><option value="KITCHEN">Bếp riêng</option></select></div><div class="form-field"><label>Mã xưởng cơm / bếp</label><input name="scope_code" required></div><button class="btn btn-outline" type="submit">Lưu nơi áp dụng</button></form>',
      '<form id="xcomMealTariffForm" class="payment-grid"><div class="form-field"><label>Hồ sơ</label><select name="profile_code" required>', paymentProfileOptions, '</select></div><div class="form-field"><label>Kỳ giá</label><input name="period" type="month" value="', esc(state.opsMonth), '" required></div>',
      '<div class="form-field"><label>Ca ăn</label><select name="shift"><option>Sáng</option><option>Trưa</option><option>Chiều</option><option>Đêm</option><option>Tổng</option></select></div><div class="form-field"><label>Đơn giá/suất</label><input name="unit_price" type="number" min="1" step="1" required></div><button class="btn btn-outline" type="submit">Lưu giá kỳ</button></form></div>',
      '<div class="group-list" style="margin-top:14px">', paymentProfileRows || '<div class="muted">Chưa có hồ sơ thanh toán suất ăn.</div>', '</div>',
      '<form id="xcomPaymentDocumentForm" class="payment-grid" style="margin-top:16px"><div class="form-field"><label>Hồ sơ</label><select name="profile_code" required>', paymentDocumentProfileOptions, '</select></div>',
      '<div class="form-field"><label>Từ ngày</label><input name="date_from" type="date" value="', esc(paymentDocumentRequest.date_from), '" required></div><div class="form-field"><label>Đến ngày</label><input name="date_to" type="date" value="', esc(paymentDocumentRequest.date_to), '" required></div><div class="form-field"><label>Ngày lập</label><input name="issue_date" type="date" value="', esc(paymentDocumentRequest.issue_date), '" required></div>',
      '<button class="btn btn-outline" type="button" data-action="preview-xcom-payment">Kiểm tra số liệu</button><button class="btn btn-primary" type="submit"',
      paymentPreview ? '' : ' disabled', '>Tải chứng từ đã kiểm tra</button></form>', paymentPreviewHtml,
      '</div></div>'
    ]);
    content.innerHTML = html([
      '<div class="toolbar fade-in"><div><div class="status-bar">Cách làm thường ngày: chọn ngày → nạp file định mức và đặt hàng → kiểm tra → xác nhận → duyệt kế hoạch → tải đơn đặt bếp</div><div class="muted">Chỉ nhập tay khi không có file. Số suất ăn thực tế được lưu riêng để đối chiếu và không làm đổi số suất đã đặt ban đầu.</div></div>',
      '<div class="compact-controls"><label class="muted">Ngày / Thứ Hai đầu tuần</label><input id="kitchenDate" type="date" value="', esc(state.opsDate), '"><button class="btn btn-outline" data-action="choose-kitchen-workbook">Nạp file định mức và đặt hàng</button><label class="muted">Tháng chấm suất</label><input id="mealAttendancePeriod" type="month" value="', esc(state.mealAttendancePeriodOverride), '"><button class="btn btn-outline" data-action="choose-meal-attendance">Nạp chấm suất tháng</button><a class="btn btn-primary" href="/api/kitchen/po?date=', encodeURIComponent(state.opsDate), '">',
      poApproved ? 'Tải đơn đặt bếp đã duyệt' : 'Tải đơn đặt bếp nháp', '</a></div></div>',
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Nhập tay kế hoạch bếp/ca</h3><p>Chỉ dùng khi không có file định mức và đặt hàng để nạp</p></div></div><div class="card-body">',
      '<form id="mealPlanForm"><div class="payment-grid kitchen-manual-grid"><div class="form-field"><label>Ngày</label><input name="work_date" type="date" value="', esc(state.opsDate), '" required></div>',
      '<div class="form-field"><label>Mã bếp</label><input name="kitchen" placeholder="POT" required></div>',
      '<div class="form-field"><label>Ca</label><input name="shift" placeholder="Sáng / trưa / chiều" required></div>',
      '<div class="form-field"><label>Tổng số suất cần nấu</label><input name="meal_count" type="number" min="1" required></div>',
      '<div class="form-field"><label>Có bao nhiêu thực đơn</label><input name="menu_count" type="number" min="1" value="1"></div>',
      '<div class="form-field"><label>Số suất của mỗi thực đơn</label><input name="servings_per_menu" type="number" min="0"></div>',
      '<div class="form-field"><label>Đơn giá suất ăn</label><input name="meal_price" type="number" min="0"></div>',
      '<div class="form-field"><label>Chi phí khác</label><input name="other_cost" type="number" min="0"></div></div>',
      '<div class="form-field"><label>Nguyên liệu (dán từ Excel)</label><div class="field-help">Mỗi dòng gồm 5 cột theo thứ tự: Mã hàng · Định lượng cho 1 suất · Tên món · Đơn vị · Nhà cung cấp. Hãy sao chép các ô trong Excel rồi dán vào đây; không tự gõ dấu |.</div><textarea name="items" style="min-height:180px" placeholder="I000060&#9;0.08&#9;Canh rau&#9;kg&#9;HATRAN" required></textarea></div>',
      '<div class="form-actions"><button class="btn btn-primary" type="submit">Lưu và tính chi phí</button></div></form></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Ghép bếp vào XCOM (xưởng cơm)</h3><p>Nạp danh sách một lần; chỉ nhập tay khi cần sửa riêng một bếp</p></div></div><div class="card-body"><form id="kitchenUnitForm" class="kitchen-side-form">',
      '<div class="form-field"><label>Mã bếp</label><input name="kitchen_code" required></div><div class="form-field"><label>Mã XCOM</label><input name="unit_code" required></div>',
      '<div class="form-actions"><button class="btn btn-outline" type="submit">Lưu bếp này</button><button class="btn btn-primary" type="button" data-action="choose-mapping-file" data-mapping-type="kitchen_units">Nạp danh sách bếp → XCOM</button></div></form>',
      '<div class="group-list" style="margin-top:16px">', unitRows || '<div class="muted">Chưa ghép bếp nào vào XCOM.</div>', '</div>',
      '<div class="code-note" style="margin-top:18px"><strong>Giá HATRAN theo kỳ:</strong> giá được khóa theo tháng khi nhập file. Chỉ dùng ô dưới đây khi cần sửa một mã theo báo giá HATRAN đã chốt.</div>',
      '<form id="datedPriceForm" class="kitchen-side-form price-form" style="margin-top:12px"><div class="form-field"><label>Tháng áp dụng</label><input name="period" type="month" value="', esc(state.opsMonth), '" required></div>',
      '<div class="form-field"><label>Mã hàng</label><input name="product_code" required></div><div class="form-field price-value-field"><label>Giá HATRAN đã chốt</label><input name="price_value" type="number" min="1" step="1" required></div>',
      '<div class="form-actions"><button class="btn btn-outline" type="submit">Lưu giá tháng này</button></div></form></div></div></div>',
      xcomPaymentModuleHtml,
      mappingPreviewHtml("kitchen_units"),
      kitchenImportPreviewHtml(),
      mealAttendancePreviewHtml(),
      '<div class="group-grid" style="margin-top:18px">', cards || '<div class="card"><div class="empty">Ngày này chưa có kế hoạch xưởng cơm.</div></div>', '</div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Chấm suất ăn thực tế ', esc(state.opsMonth),
      '</h3><p>', attendanceTotals.kitchens, ' bếp · ', attendanceTotals.rows, ' dòng ngày/bếp/ca · tổng ',
      num(attendanceTotals.actual), ' suất thực ăn</p></div></div><div class="table-wrap"><table><thead><tr><th>Ngày</th><th>Bếp</th><th>Ca</th><th>Thực ăn</th><th>Số đặt</th><th>Chênh lệch</th></tr></thead><tbody>',
      attendanceRows || '<tr><td colspan="6"><div class="empty">Chưa nạp file chấm suất ăn tháng này.</div></td></tr>',
      '</tbody></table></div>', (o.meal_attendance || []).length > 240 ? '<div class="card-body muted">Đang hiển thị 240 dòng đầu của kỳ.</div>' : '', '</div>'
    ]);
  }

  function renderPayroll() {
    var o = state.operations;
    if (!o) { loadOperations(); return; }
    var rows = o.payroll.map(function (item, index) {
      return '<tr><td>' + (index + 1) + '</td><td><strong>' + esc(item.full_name) + '</strong><div class="muted">' +
        esc(item.employee_code) + ' · ' + esc(item.kitchen) + '</div></td><td>' + esc(item.role_name) +
        '</td><td class="num-cell">' + num(item.normal_hours) + '</td><td class="num-cell">' +
        num(item.overtime_hours) + '</td><td class="num-cell">' + num(item.sunday_hours) +
        '</td><td class="num-cell">' + num(item.night_hours) + '</td><td class="num-cell">' +
        num(item.holiday_hours) + '</td><td class="num-cell">' + money(n(item.allowance) + n(item.responsibility)) +
        '</td><td class="num-cell">' + money(item.gross_salary) + '</td><td class="num-cell">' +
        money(item.bhxh_employee) + '</td><td class="num-cell">' + money(n(item.advance) + n(item.probation_deduction)) +
        '</td><td class="num-cell"><strong>' + money(item.net_salary) + '</strong></td></tr>';
    }).join("");
    var laborRows = o.labor_costs.slice(0, 120).map(function (item) {
      return '<tr><td>' + dateVN(item.work_date) + '</td><td>' + esc(item.kitchen) +
        '</td><td class="num-cell">' + money(item.amount) + '</td></tr>';
    }).join("");
    content.innerHTML = html([
      '<div class="toolbar fade-in"><div class="status-bar">Công thường · tăng ca 150% · Chủ nhật 200% · đêm 130% · lễ 300% · phụ cấp · bảo hiểm xã hội · tạm ứng</div>',
      '<div class="compact-controls"><input id="payrollMonth" type="month" value="', esc(state.opsMonth), '"><a class="btn btn-outline" href="/api/export/payroll?month=', encodeURIComponent(state.opsMonth), '">Tải bảng lương</a><button class="btn btn-primary" data-action="choose-attendance">Nạp file chấm công</button></div></div>',
      attendanceImportPreviewHtml(),
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Thêm/cập nhật nhân sự</h3><p>Mỗi nhân sự dùng một mã riêng</p></div></div><div class="card-body">',
      '<form id="staffForm" class="payment-grid"><div class="form-field"><label>Mã</label><input name="employee_code" required></div>',
      '<div class="form-field"><label>Họ tên</label><input name="full_name" required></div><div class="form-field"><label>Chức vụ</label><input name="role_name"></div>',
      '<div class="form-field"><label>Bếp</label><input name="kitchen"></div><div class="form-field"><label>Lương cơ bản</label><input name="base_salary" type="number" min="0"></div>',
      '<div class="form-field"><label>Ngày chuẩn/tháng</label><input name="standard_days" type="number" min="1" value="26"></div><div class="form-field"><label>Giờ chuẩn/ngày</label><input name="standard_hours" type="number" min="1" value="8"></div>',
      '<div class="form-field"><label>Tỷ lệ bảo hiểm xã hội của người lao động</label><input name="bhxh_employee_rate" type="number" min="0" step="0.001" value="0"></div><div class="form-field"><label>Tỷ lệ bảo hiểm xã hội của công ty</label><input name="bhxh_company_rate" type="number" min="0" step="0.001" value="0"></div>',
      '<div class="form-actions staff-form-actions"><button class="btn btn-outline" type="submit">Lưu nhân sự</button></div></form></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Chi phí lao động theo bếp</h3><p>Đọc từ trang chấm công chợ trong file Excel</p></div></div><div class="table-wrap"><table><thead><tr><th>Ngày</th><th>Bếp</th><th>Chi phí</th></tr></thead><tbody>',
      laborRows || '<tr><td colspan="3"><div class="empty">Chưa nạp file chấm công tháng này.</div></td></tr>',
      '</tbody></table></div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Chấm/sửa công một ngày</h3><p>Dùng khi cần bổ sung phát sinh sau khi nạp Excel</p></div></div><div class="card-body"><form id="attendanceForm" class="payment-grid">',
      '<div class="form-field"><label>Mã nhân sự</label><input name="employee_code" required></div><div class="form-field"><label>Ngày</label><input name="work_date" type="date" value="', esc(state.opsDate), '" required></div>',
      '<div class="form-field"><label>Giờ thường</label><input name="normal_hours" type="number" min="0" step="0.5"></div><div class="form-field"><label>Tăng ca</label><input name="overtime_hours" type="number" min="0" step="0.5"></div>',
      '<div class="form-field"><label>Chủ nhật</label><input name="sunday_hours" type="number" min="0" step="0.5"></div><div class="form-field"><label>Ca đêm</label><input name="night_hours" type="number" min="0" step="0.5"></div>',
      '<div class="form-field"><label>Ngày lễ</label><input name="holiday_hours" type="number" min="0" step="0.5"></div><div class="form-field span-2"><label>Ghi chú</label><input name="note"></div>',
      '<button class="btn btn-outline" type="submit">Lưu chấm công</button></form></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Khoản lương theo tháng</h3><p>Phụ cấp, trách nhiệm, bảo hiểm xã hội, tạm ứng, thử việc hoặc chốt thực lĩnh theo file hiện tại</p></div></div><div class="card-body"><form id="payrollAdjustmentForm" class="payment-grid">',
      '<div class="form-field"><label>Mã nhân sự</label><input name="employee_code" required></div><div class="form-field"><label>Tháng</label><input name="month" type="month" value="', esc(state.opsMonth), '" required></div>',
      '<div class="form-field"><label>Phụ cấp</label><input name="allowance" type="number" value="0"></div><div class="form-field"><label>Trách nhiệm</label><input name="responsibility" type="number" value="0"></div>',
      '<div class="form-field"><label>Tạm ứng</label><input name="advance" type="number" value="0"></div><div class="form-field"><label>Khấu trừ thử việc</label><input name="probation_deduction" type="number" value="0"></div>',
      '<div class="form-field"><label>Bảo hiểm xã hội người lao động</label><input name="bhxh_employee_amount" type="number" value="0"></div><div class="form-field"><label>Bảo hiểm xã hội công ty</label><input name="bhxh_company_amount" type="number" value="0"></div>',
      '<div class="form-field"><label>Tổng lương chốt</label><input name="gross_override" type="number" value="0"></div><div class="form-field"><label>Thực lĩnh chốt</label><input name="net_override" type="number" value="0"></div>',
      '<div class="form-field"><label><input name="use_override" type="checkbox"> Dùng số chốt thay công thức</label></div><div class="form-field span-2"><label>Ghi chú</label><input name="note"></div>',
      '<button class="btn btn-primary" type="submit">Lưu khoản lương</button></form></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Bảng lương ', esc(state.opsMonth),
      '</h3><p>Tính từ dữ liệu chấm công đã kiểm tra; các khoản điều chỉnh lưu riêng theo tháng</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Nhân sự</th><th>Chức vụ</th><th>Giờ thường</th><th>Tăng ca</th><th>Chủ nhật</th><th>Ca đêm</th><th>Ngày lễ</th><th>Phụ cấp + trách nhiệm</th><th>Tổng lương</th><th>Bảo hiểm xã hội người lao động</th><th>Tạm ứng + thử việc</th><th>Thực lĩnh</th></tr></thead><tbody>',
      rows || '<tr><td colspan="13"><div class="empty">Chưa có nhân sự/chấm công.</div></td></tr>',
      '</tbody></table></div></div>'
    ]);
  }

  function renderPrinting() {
    var o = state.operations;
    if (!o) { loadOperations(); return; }
    var directPrinting = o.printer.supported && !state.data.hosted;
    var listKey = [state.printingDocument,state.printingFrom,state.printingTo,state.printingCustomer].join("|");
    if (state.printingListKey !== listKey || state.printingRows === null) {
      loadPrintingRows();
      content.innerHTML = '<div class="loading-panel">Đang đọc danh sách phiếu theo khoảng ngày…</div>';
      return;
    }
    var selectionRows = printingSelectionRows();
    var rangeKey = state.printingDocument + "|" + state.printingFrom + "|" + state.printingTo + "|" + state.printingCustomer;
    if (state.printingRangeKey !== rangeKey) {
      state.printingRangeKey = rangeKey;
      state.printingSelected = {};
      selectionRows.forEach(function (item) { state.printingSelected[item.key] = true; });
    }
    var selectedCount = selectionRows.filter(function (item) {
      return Boolean(state.printingSelected[item.key]);
    }).length;
    var documentChoices = [
      ["deliveries", "Đơn hàng đi giao", "Chọn tất cả hoặc từng bếp", "GIAO"],
      ["suppliers", "Đơn đặt nhà cung cấp", "File Excel đặt hàng", "ĐẶT"],
      ["purchases", "Bảng kê và biên nhận", "File Excel có thể sửa thêm", "KÊ"],
      ["report", "Báo cáo tổng hợp", "Đúng mẫu tổng hợp theo tháng", "BC"]
    ].map(function (choice) {
      return '<label class="print-type-card ' + (state.printingDocument === choice[0] ? 'is-selected' : '') + '">' +
        '<input type="radio" name="printDocument" class="print-document-choice" value="' + choice[0] + '" ' +
        (state.printingDocument === choice[0] ? 'checked' : '') + '><span class="print-type-icon">' + choice[3] +
        '</span><span><strong>' + choice[1] + '</strong><small>' + choice[2] + '</small></span></label>';
    }).join("");
    var batchRows = selectionRows.map(function (item) {
      var batch = item.batch;
      var status = batch.status === "approved"
        ? '<span class="tag tag-ok">Đã duyệt</span>'
        : n(batch.error_count)
          ? '<span class="tag tag-red">Còn ' + n(batch.error_count) + ' dòng lỗi</span>'
          : '<span class="tag tag-warn">Chưa duyệt</span>';
      return '<tr><td><label class="print-batch-check"><input type="checkbox" class="print-batch-select" data-id="' +
        esc(item.key) + '" ' + (state.printingSelected[item.key] ? 'checked' : '') + '><span></span></label></td><td><strong>' +
        esc(item.title) + '</strong><div class="muted">' + esc(item.subtitle) +
        '</div></td><td class="num-cell">' + num(item.line_count) + ' dòng hàng</td><td>' + status + '</td><td><button class="btn btn-small btn-outline" data-action="preview-print-row" data-key="' + esc(item.key) + '">Xem trước</button></td></tr>';
    }).join("");
    var jobs = o.print_jobs.filter(function (item) { return !state.batchId || item.batch_id === state.batchId; });
    var rows = jobs.map(function (item) {
      var documentLabels = {
        delivery_pdf: "Phiếu giao hàng", other_pdf: "Chứng từ khác", pdf_bundle: "Bộ PDF cũ"
      };
      var statusLabels = {
        prepared: "Chờ duyệt", approved: "Đã duyệt", submitting: "Đang gửi đến máy in",
        submitted: "Máy in đã nhận lệnh", submission_unknown: "Chưa xác nhận máy in đã nhận",
        printed: "Đã gửi hàng đợi (bản cũ)", error: "Lỗi", stale: "Đã hủy do sửa nguồn"
      };
      return '<tr><td>' + esc(documentLabels[item.document_type] || item.document_type) +
        '</td><td><strong>' + esc(item.paper || "") + '</strong></td><td><span class="tag ' +
        (["submitted", "printed"].indexOf(item.status) >= 0 ? "tag-ok" :
          ["error", "submission_unknown"].indexOf(item.status) >= 0 ? "tag-red" : "tag-warn") + '">' +
        esc(statusLabels[item.status] || item.status) + '</span></td><td>' + num(item.page_count || 0) +
        '</td><td>' + esc(item.approved_at || "") + '</td><td>' +
        esc(item.submitted_at || item.printed_at || "") + '</td><td>' + esc(item.error_message || "") + '</td></tr>';
    }).join("");
    var installedPrinters = (o.printer.installed || []).slice();
    if (o.printer.name && installedPrinters.indexOf(o.printer.name) < 0) installedPrinters.unshift(o.printer.name);
    var printerOptions = '<option value="">Máy mặc định Windows' +
      (o.printer.default ? ' · ' + esc(o.printer.default) : '') + '</option>' +
      installedPrinters.map(function (name) {
        return '<option value="' + esc(name) + '"' + (name === o.printer.name ? ' selected' : '') + '>' + esc(name) + '</option>';
      }).join("");
    var pdfLinks = state.batchId ? jobs.filter(function (item) {
      return ["delivery_pdf", "other_pdf", "pdf_bundle"].indexOf(item.document_type) >= 0 &&
        ["stale", "cancelled"].indexOf(item.status) < 0;
    }).map(function (item) {
      var label = item.document_type === "delivery_pdf" ? "Xem phiếu giao A4" :
        item.document_type === "other_pdf" ? "Xem chứng từ " + (item.paper || "") : "Xem PDF cũ";
      return '<a class="btn btn-outline" href="/api/print/pdf/' + state.batchId + '/' +
        encodeURIComponent(item.document_type) + '">' + esc(label) + '</a>';
    }).join("") : "";
    var canInvalidate = jobs.some(function (item) {
      return ["prepared", "approved", "error"].indexOf(item.status) >= 0;
    });
    content.innerHTML = html([
      '<div class="print-type-grid fade-in">', documentChoices, '</div>',
      '<div class="card print-selection-card fade-in"><div class="card-head"><div><h3>',
      state.printingDocument === "deliveries" ? 'Chọn bếp cần in phiếu giao' : 'Chọn ngày cần lấy giấy tờ', '</h3>',
      '<p>Chọn phiếu, xem ngay tại đây hoặc in phần đã chọn. Bảng kê/biên nhận có thể chọn tiếp từng sheet trong bản xem.</p></div>',
      '<span class="tag tag-ok" id="printingSelectedCount">Đang lọc ', selectionRows.length, ' · Đã chọn ', selectedCount,
      state.printingDocument === "deliveries" ? ' phiếu giao' : ' ngày', '</span></div>',
      '<div class="card-body"><div class="print-range-controls"><label>Từ ngày <input id="printingFrom" type="date" value="',
      esc(state.printingFrom), '"></label><label>Đến ngày <input id="printingTo" type="date" value="', esc(state.printingTo), '"></label>',
      '<button class="btn btn-outline" data-action="select-all-print-batches">Chọn tất cả</button>',
      '<button class="btn btn-outline" data-action="clear-print-batches">Bỏ chọn tất cả</button>',
      '<button class="btn btn-outline" data-action="preview-selected-documents" ', selectedCount ? '' : 'disabled', '>Xem phần đã chọn</button>',
      '<button class="btn btn-primary" data-action="print-selected-documents" ', selectedCount ? '' : 'disabled', '>In phần đã chọn</button>',
      '<button class="btn btn-outline" data-action="download-selected-documents" ', selectedCount ? '' : 'disabled', '>Tải file đã chọn</button>',
      state.printingDocument === "purchases" ? '<button class="btn btn-primary" data-action="download-approved-input-bk" ' + (selectedCount ? '' : 'disabled') + '>Tải bảng kê đầu vào</button>' : '',
      '</div>',
      state.printingDocument === "purchases" ? '<p class="muted">Tải bảng kê đầu vào: gộp các ngày đã chọn vào một file Excel, theo lượng và giá đã ghi nhập kho khi duyệt đơn.</p>' : '',
      state.printingDocument === 'deliveries' ? '<label class="print-customer-filter">Khách hàng / bếp <select id="printingCustomer"><option value="">Tất cả bếp</option>' + state.data.master.kitchens.map(function(k) { return '<option value="' + esc(k.code) + '" ' + (state.printingCustomer === k.code ? 'selected' : '') + '>' + esc(k.name || k.code) + '</option>'; }).join('') + '</select></label>' : '', '</div>',
      '<div class="table-wrap print-batch-table"><table><thead><tr><th>Chọn</th><th>',
      state.printingDocument === "deliveries" ? 'Bếp / ngày giao' : 'Ngày / file đơn',
      '</th><th>Số dòng</th><th>Trạng thái</th><th>Xem</th></tr></thead><tbody>',
      batchRows || '<tr><td colspan="5"><div class="empty">' + esc(state.printingListError || 'Khoảng ngày này chưa có giấy tờ phù hợp.') + '</div></td></tr>',
      '</tbody></table></div></div><div id="printingPreview"></div>',
      '<details class="operation-details fade-in"><summary>', directPrinting ? 'In trực tiếp trọn bộ của ngày đang chọn' : 'Cách in trên máy tính và lịch sử in', '</summary><div class="operation-details-body">',
      directPrinting ? html([
      '<div class="toolbar"><div class="status-bar">Dùng khi muốn gửi thẳng bộ giấy của đơn đang chọn sang máy in</div><div class="compact-controls">',
      '<button class="btn btn-outline" data-action="prepare-print" ', state.batchId ? '' : 'disabled', '>1. Tạo bản xem trước</button>',
      '<button class="btn btn-outline" data-action="approve-print" ', state.batchId ? '' : 'disabled', '>2. Xác nhận bộ giấy</button>',
      pdfLinks,
      '<button class="btn btn-outline" data-action="invalidate-print" ', canInvalidate ? '' : 'disabled', '>Bỏ bộ cũ</button>',
      '<button class="btn btn-primary" data-action="run-print" ', state.batchId ? '' : 'disabled', '>3. Gửi sang máy in</button></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Máy in</h3><p>Phiếu giao dùng A4; giấy tờ khác có thể chọn A5 hoặc A4</p></div></div><div class="card-body">',
      '<form id="printSettingsForm" class="payment-grid"><div class="form-field span-2"><label>Máy in Windows</label><select name="printer_name">', printerOptions, '</select></div>',
      '<div class="form-field"><label>Số bản</label><input name="copies" type="number" min="1" max="10" value="', esc(o.printer.copies), '"></div>',
      '<div class="form-field"><label>Phiếu giao</label><input value="A4 · cố định" disabled></div>',
      '<div class="form-field"><label>Giấy tờ khác</label><select name="other_paper">',
      '<option value="A5" ', (o.printer.other_paper || o.printer.paper) === "A5" ? 'selected' : '', '>A5</option>',
      '<option value="A4" ', (o.printer.other_paper || o.printer.paper) === "A4" ? 'selected' : '', '>A4</option></select></div>',
      '<button class="btn btn-outline" type="submit">Lưu</button></form></div></div>'
      ]) : '<div class="code-note">Chọn phiếu ở danh sách phía trên rồi bấm <strong>In phần đã chọn</strong>. Bản PDF mở ngay tại màn này; chọn máy in và số bản trong hộp thoại in của trình duyệt. Nếu trình duyệt chưa mở hộp thoại in, dùng nút in trên bản PDF hoặc tải PDF về để in.</div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Lịch sử gửi in</h3><p>Đơn hàng đang chọn</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Giấy tờ</th><th>Khổ</th><th>Trạng thái</th><th>Trang</th><th>Xác nhận lúc</th><th>Gửi in lúc</th><th>Lỗi</th></tr></thead><tbody>',
      rows || '<tr><td colspan="7"><div class="empty">Chưa có lần in nào.</div></td></tr>',
      '</tbody></table></div></div></div></details>'
    ]);
  }

  async function loadBackupStatus() {
    var target = document.getElementById("automaticBackupStatus");
    if (!target) return;
    try {
      var result = await api("/api/backup/status");
      if (!target.isConnected || document.getElementById("automaticBackupStatus") !== target) return;
      var last = result.last_success ? new Date(result.last_success).toLocaleString("vi-VN") : "Chưa có bản sao tự động thành công";
      target.textContent = "Sao lưu gần nhất: " + last + ". " + (result.error || result.warning || (result.last_success ? "Bản sao đã được kiểm tra an toàn." : "Hệ thống sẽ sao lưu khi có dữ liệu."));
      target.setAttribute("role", result.error || result.warning ? "alert" : "status");
      target.classList.toggle("tag-red", Boolean(result.error || result.warning));
    } catch (error) {
      if (target.isConnected) { target.textContent = "Không đọc được tình trạng sao lưu. " + error.message; target.setAttribute("role", "alert"); }
    }
  }
  setInterval(function () { if (state.view === "settings") loadBackupStatus(); }, 60000);

  async function loadCatalogProducts() {
    var table = document.getElementById('catalogProducts');
    if (!table) return;
    var serial = ++state.catalogRequest;
    table.textContent = 'Đang tải danh mục…';
    try {
      var data = await api('/api/catalog/products?q=' + encodeURIComponent(state.catalogQuery) + '&all=1');
      if (serial !== state.catalogRequest || table !== document.getElementById('catalogProducts')) return;
      state.catalogItems = data.items;
      state.catalogOffset = data.offset;
      table.innerHTML = '<p class="catalog-count">Tìm trên toàn bộ ' + stockQty(data.catalog_total) + ' mã · ' + data.total + ' kết quả · cuộn trong bảng để xem tiếp</p><div class="table-wrap catalog-products-scroll"><table><thead><tr><th>Mã hàng</th><th>Tên hàng</th><th>ĐVT</th><th>Thuế</th><th>Tên trên hóa đơn</th><th></th></tr></thead><tbody>' + data.items.map(function(item) {
        return '<tr><td>' + esc(item.code) + '</td><td>' + esc(item.name) + '</td><td>' + esc(item.unit) + '</td><td>' + esc(taxText(item.tax)) + '</td><td>' + esc(item.invoice_name || item.name) + '</td><td><button class="btn btn-small btn-outline" data-action="edit-catalog-product" data-code="' + esc(item.code) + '">Sửa</button></td></tr>';
      }).join('') + (!data.items.length ? '<tr><td colspan="6">Không tìm thấy mã hàng.</td></tr>' : '') + '</tbody></table></div>';
    } catch (error) { if (serial === state.catalogRequest) table.textContent = error.message; }
  }

  async function openCatalogWorksheet() {
    if (!window.TDPWorksheet || window.TDPWorksheet.isOpen()) return;
    try {
      var data = await api('/api/catalog/worksheet');
      var saved = false;
      await window.TDPWorksheet.open({kind:'catalog', title:'Danh mục hàng hóa · ' + data.total + ' mã', editable:true, rows:data.items,
        columns:[
          {key:'code',title:'Mã hàng',width:150,editable:false},
          {key:'name',title:'Tên hàng',width:360,editable:true},
          {key:'unit',title:'ĐVT',width:90,editable:true},
          {key:'tax',title:'Thuế',width:110,editable:true},
          {key:'invoice_name',title:'Tên trên hóa đơn (trống = dùng tên hàng)',width:360,editable:true}
        ],
        onSaved:function(){ saved = true; },
        onClose:async function(){
          if (saved) {
            state.catalogImportPreview=null; state.invoiceWorkbench=null; state.invoiceListing=null;
            state.catalogItems=[];
            var catalog = document.getElementById('catalogProducts');
            if (catalog) catalog.textContent='Đang cập nhật danh mục đã lưu…';
            try { await loadData(state.batchId,true); } catch(error){ showToast('Đã lưu danh mục. Tải lại trang để cập nhật các màn khác.',true); }
          } else await loadCatalogProducts();
        }
      });
    } catch(error) { showToast(error.message,true); }
  }

  function openCatalogProductDialog(product) {
    if (document.querySelector('.catalog-product-dialog')) return;
    var dialog = document.createElement('dialog');
    dialog.className = 'inventory-totals-dialog catalog-product-dialog';
    dialog.setAttribute('aria-labelledby', 'catalog-product-title');
    dialog.innerHTML = '<form><div class="inventory-totals-heading"><h3 id="catalog-product-title">Thêm mã hàng</h3><button type="button" class="icon-button catalog-product-cancel" aria-label="Đóng">×</button></div>' +
      '<div class="catalog-product-fields"><div class="form-field"><label for="newProductCode">Mã hàng</label><input id="newProductCode" name="code" maxlength="64" required autocomplete="off" placeholder="Ví dụ: H000003"></div>' +
      '<div class="form-field"><label for="newProductName">Tên hàng</label><input id="newProductName" name="name" maxlength="255" required placeholder="Ví dụ: Đậu phụ chiên"></div>' +
      '<div class="form-field"><label for="newProductUnit">Đơn vị tính</label><input id="newProductUnit" name="unit" maxlength="50" required list="newProductUnits" placeholder="Ví dụ: Cái"><datalist id="newProductUnits"><option value="Cái"><option value="Kg"><option value="Can"><option value="Gói"><option value="Hộp"><option value="Thùng"><option value="Chai"><option value="Lít"><option value="Ream"></datalist></div>' +
      '<div class="form-field"><label for="newProductTax">Thuế</label><select id="newProductTax" name="tax" required><option value="">Chọn thuế</option><option value="KKKNT">KKKNT · Không kê khai</option><option value="KCT">KCT · Không chịu thuế</option><option value="0">0%</option><option value="0.05">5%</option><option value="0.08">8%</option><option value="0.1">10%</option></select></div>' +
      '<div class="form-field catalog-invoice-name"><label for="newProductInvoiceName">Tên trên hóa đơn (không bắt buộc)</label><input id="newProductInvoiceName" name="invoice_name" maxlength="255" placeholder="Bỏ trống để dùng tên hàng"></div>' +
      '<p class="catalog-product-error" role="alert"></p></div><div class="catalog-product-footer"><button type="button" class="btn btn-outline catalog-product-cancel">Hủy</button><button type="submit" class="btn btn-primary">Lưu mã hàng</button></div></form>';
    if (product) {
      dialog.querySelector('h3').textContent = 'Sửa mã hàng';
      ['code','name','unit','invoice_name'].forEach(function(key) { dialog.querySelector('[name="' + key + '"]').value = product[key] || ''; });
      dialog.querySelector('[name="tax"]').value = product.tax == null || product.tax === '' ? '' : ['KKKNT','KCT'].includes(product.tax) ? product.tax : String(Number(product.tax));
      dialog.querySelector('[name="code"]').readOnly = true;
    }
    var busy = false;
    dialog.querySelector('form').addEventListener('input', function() {
      dialog.querySelector('.catalog-product-error').textContent = '';
    });
    dialog.querySelector('form').addEventListener('invalid', function() {
      dialog.querySelector('.catalog-product-error').textContent = 'Chưa lưu. Cần nhập đủ Mã hàng, Tên hàng, Đơn vị tính và chọn Thuế.';
    }, true);
    dialog.querySelectorAll('.catalog-product-cancel').forEach(function(button) { button.onclick = function() { if (!busy) dialog.close(); }; });
    dialog.addEventListener('cancel', function(event) { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', function() { dialog.remove(); });
    dialog.querySelector('form').onsubmit = async function(event) {
      event.preventDefault();
      if (busy) return;
      var payload = Object.fromEntries(new FormData(event.target).entries());
      if (product) {
        payload.expected = {};
        ['name','unit','tax','invoice_name','catalog_updated_at'].forEach(function(key) { payload.expected[key] = product[key]; });
      }
      busy = true;
      var submit = dialog.querySelector('[type="submit"]');
      dialog.querySelectorAll('button,input,select').forEach(function(field) { field.disabled = true; });
      submit.textContent = 'Đang lưu…';
      dialog.querySelector('.catalog-product-error').textContent = '';
      var created;
      try {
        created = await api('/api/catalog/products', {method:product ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      } catch (error) {
        busy = false;
        dialog.querySelectorAll('button,input,select').forEach(function(field) { field.disabled = false; });
        submit.textContent = 'Lưu mã hàng';
        dialog.querySelector('.catalog-product-error').textContent = error.message;
        dialog.querySelector('[name="code"]').focus();
        return;
      }
      busy = false; dialog.close();
      state.catalogImportPreview = null;
      state.invoiceWorkbench = null; state.invoiceListing = null;
      state.catalogQuery = created.product.code; state.catalogOffset = 0;
      try { await loadData(state.batchId, true); }
      catch (error) { showToast('Đã lưu mã ' + created.product.code + '. Tải lại trang để cập nhật danh mục.', true); return; }
      showToast('Đã lưu mã ' + created.product.code + ' · ' + created.product.name + ' · ' + created.product.unit);
    };
    document.body.appendChild(dialog); dialog.showModal();
    dialog.querySelector('[name="code"]').focus();
  }

  function renderSettings() {
    var d = state.data;
    var backupLocation = d.hosted
      ? '<strong>Dữ liệu được lưu trên hệ thống trực tuyến.</strong> Đăng nhập cùng địa chỉ web trên máy tính khác để tiếp tục làm việc.'
      : '<strong>Dữ liệu lưu tại máy chạy hệ thống.</strong> Máy thứ hai cùng mạng Wi-Fi hoặc mạng nội bộ có thể dùng chung khi máy chính đang mở.';
    var backupSchedule = d.hosted
      ? 'Hệ thống tự sao lưu mỗi 30 phút khi dịch vụ đang chạy, kể cả khi đã đóng trình duyệt; giữ bản mới nhất của 14 ngày có sao lưu.'
      : 'Tự sao lưu mỗi 30 phút khi phần mềm đang mở, giữ bản mới nhất của 14 ngày có sao lưu.';
    var synced = d.master.settings.master_synced_at || "Chưa đồng bộ";
    var m = state.minvoiceStatus;
    var minvoiceTitle = m && m.connected ? "Đã kết nối M-Invoice" : "Kiểm tra kết nối M-Invoice";
    if (m && m.test_environment) minvoiceTitle = 'M-Invoice · máy chủ kiểm thử';
    var minvoiceText = m && m.connected
      ? "M-Invoice đang hoạt động · " + num(m.outgoing.series_count) + " ký hiệu. Có thể lưu nháp chờ ký; không tự ký/phát hành."
      : "Kiểm tra kết nối an toàn; lưu nháp cần xác nhận riêng và không bao giờ tự ký/phát hành.";
    if (m && m.connected && m.draft_save_available === false) minvoiceText = "Đã kết nối portal công ty · " + num(m.outgoing.series_count) + " ký hiệu. Tải hóa đơn đã có; lập hóa đơn bằng file Excel nhập trên M-Invoice.";
    if (m && m.warning) minvoiceText = m.warning;
    var minvoiceCard = '<div class="card fade-in" style="margin-bottom:18px"><div class="card-head"><div><h3>' +
      esc(minvoiceTitle) + '</h3><p>' + esc(minvoiceText) + '</p></div><button class="btn btn-primary" data-action="check-minvoice">' +
      (m && m.connected ? "Kiểm tra lại" : "Kiểm tra ngay") + '</button></div></div>';
    content.innerHTML = html([
      minvoiceCard,
      '<div class="stats-grid fade-in">',
      statCard("Mã hàng", num(d.master.product_count), "Danh mục sản phẩm", "▤"),
      statCard("Bếp", num(d.master.kitchens.length), "Có nhà thầu và địa chỉ", "⌂"),
      statCard("Nhà cung cấp", num(d.master.suppliers.length), "Danh mục đặt hàng", "⇄"),
      statCard("Nhóm nhà thầu", num(d.master.contractors.length), "Giá nhóm / giá theo ngày", "₫"),
      "</div>",
      '<div class="card"><div class="card-head"><div><h3>Danh mục hàng hóa</h3><p>Thêm từng mã hoặc nạp nhiều mã từ Excel. Tên trên hóa đơn để trống sẽ dùng tên hàng.</p></div></div><div class="card-body">',
      '<div class="form-actions"><button class="btn btn-primary" data-action="add-catalog-product">Thêm mã hàng</button><button class="btn btn-outline" data-action="choose-catalog-workbook">Nạp từ Excel</button></div>',
      '<p class="code-note">Chọn file Em Thành.xlsx hoặc danh mục có các cột Mã hàng, Tên hàng, ĐVT, Thuế. Xem trước các thay đổi rồi xác nhận.</p>',
      '<form id="catalogSearchForm" class="catalog-search"><input class="input-date" name="q" aria-label="Tìm mã hoặc tên hàng" placeholder="Tìm toàn bộ mã hoặc tên hàng (có / không dấu)" value="',esc(state.catalogQuery),'"><button class="btn btn-outline" type="submit">Tìm</button></form><div id="catalogProducts"></div>',
      '<details class="code-note"><summary>Nạp dữ liệu khác</summary><div class="form-actions"><button class="btn btn-outline" data-action="choose-mapping-file" data-mapping-type="invoice_names">Nạp riêng tên hóa đơn từ Excel</button><button class="btn btn-outline" data-action="sync-master">Đọc lại bản Em Thành trên hệ thống</button></div><p>Bản Em Thành trên hệ thống được nạp lần cuối: ',esc(synced),'. Muốn dùng file vừa sửa trên máy, chọn Nạp từ Excel phía trên.</p></details></div></div>',
      catalogImportPreviewHtml(), mappingPreviewHtml("invoice_names"),
      '<div class="section-grid">',
      '<div class="card"><div class="card-head"><div><h3>Sao lưu dữ liệu</h3><p>Tải toàn bộ đơn, công nợ và thanh toán về máy</p></div></div>',
      '<div class="card-body"><div class="code-note">', backupLocation, '</div>',
      '<p>', backupSchedule, ' Trước nâng cấp luôn tạo bản sao riêng. Bấm Lưu/Xác nhận để ghi thay đổi; với bảng Excel, chờ trạng thái Đã lưu. Ô đang gõ chưa xác nhận chưa được lưu.</p>',
      '<div id="automaticBackupStatus" class="code-note" role="status">Đang kiểm tra lần sao lưu gần nhất…</div>',
      '<p>Nên tải thêm một bản sang ổ khác trước khi chuyển máy. Sao lưu trên cùng ổ không bảo vệ được khi ổ đĩa hỏng.</p>',
      '<div class="form-actions"><a class="btn btn-primary" href="/api/backup">Tải bản sao lưu dữ liệu</a></div></div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Thông tin thanh toán mặc định</h3><p>Được khóa cùng hóa đơn và dùng để lập Đề nghị thanh toán chính thức theo nhà thầu</p></div></div><div class="card-body">',
      '<form id="documentSettingsForm" class="payment-grid"><div class="form-field span-2"><label>Người đại diện / đề nghị</label><input name="payment_requester" required value="', esc(d.master.settings.payment_requester || ""), '"></div>',
      '<div class="form-field"><label>Số tài khoản nhận tiền</label><input name="payment_bank_account" inputmode="numeric" required value="', esc(d.master.settings.payment_bank_account || ""), '"></div>',
      '<div class="form-field span-2"><label>Ngân hàng</label><input name="payment_bank_name" required value="', esc(d.master.settings.payment_bank_name || ""), '"></div>',
      '<button class="btn btn-primary" type="submit">Lưu thông tin</button></form>',
      '<div class="code-note" style="margin-top:14px"><strong>Kiểm soát:</strong> thiếu một trong ba thông tin sẽ chặn việc khóa hóa đơn và tạo hồ sơ thanh toán chính thức.</div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Những việc phần mềm tự làm và không tự làm</h3><p>Giới hạn an toàn</p></div></div>',
      '<div class="card-body"><div class="flow">',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>Đơn hàng và dữ liệu</strong><span>Có thể nhập, sửa, lưu, tính và xuất file</span></div></div>',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>mSMI và M-Invoice an toàn</strong><span>Đầu vào chỉ tải thêm hóa đơn chưa có; đầu ra tạo bản nháp để người dùng kiểm tra và phát hành</span></div></div>',
      '<div class="flow-step"><div class="num">!</div><div><strong>Không tự gửi Zalo, ký hoặc phát hành</strong><span>Các thao tác gửi ra ngoài luôn chờ người dùng duyệt</span></div></div>',
      "</div></div></div>"
    ]);
    loadCatalogProducts();
  }

  function render() {
    if (state.busy || !state.data) return;
    var views = {
      home: renderHome,
      orders: renderOrders,
      physical: renderPhysicalStock,
      purchases: renderPurchases,
      deliveries: renderDeliveries,
      quotes: renderQuotes,
      reports: renderReports,
      debts: renderDebts,
      documents: renderDocuments,
      inventory: renderInventory,
      msmi: renderMsmi,
      printing: renderPrinting,
      settings: renderSettings
    };
    (views[state.view] || renderHome)();
    if (state.view === "settings") loadBackupStatus();
  }

  function optionList(items, selected, valueKey, labelKey) {
    return '<option value="">-- Chọn --</option>' + items.map(function (item) {
      var value = item[valueKey];
      var label = item[labelKey] || value;
      return '<option value="' + esc(value) + '"' + (String(value) === String(selected || "") ? " selected" : "") +
        ">" + esc(label) + "</option>";
    }).join("");
  }

  function field(label, name, value, type, extra, span) {
    type = type || "text";
    extra = extra || "";
    span = span || "";
    return '<div class="form-field ' + span + '"><label for="f_' + name + '">' + esc(label) +
      '</label><input id="f_' + name + '" name="' + name + '" type="' + type + '" value="' +
      esc(value) + '" ' + extra + "></div>";
  }

  function setOrderModalWide(wide) {
    orderForm.className = "modal-body" + (wide ? " bulk-order-form" : "");
    var modal = orderForm.closest(".modal");
    if (modal) modal.classList.toggle("modal-wide", Boolean(wide));
  }

  function openOrderModal(id) {
    var d = state.data;
    var item = id ? d.orders.find(function (row) { return row.id === Number(id); }) : null;
    item = item || {
      work_date: d.batch ? d.batch.work_date : currentWorkDate(),
      contractor: "", kitchen: "", product_code: "", product_name: "", qty: 0,
      actual_received: 0, actual_delivered: 0, unit: "", supplier: "",
      damaged_qty: 0, supplier_return_qty: 0, customer_return_qty: 0,
      buy_price: 0, sell_price: 0, tax: "KKKNT", invoice_nature: "1", purchase_list: 0,
      seller: "", cccd: "", note: ""
    };
    state.editingId = id ? Number(id) : null;
    state.modalMode = "order";
    setOrderModalWide(false);
    document.getElementById("modalTitle").textContent = id ? "Sửa dòng đơn hàng" : "Thêm dòng đơn hàng";
    var contractorOptions = optionList(d.master.contractors, item.contractor, "code", "code");
    var kitchenOptions = optionList(d.master.kitchens, item.kitchen, "code", "code");
    var supplierOptions = optionList(d.master.suppliers, item.supplier, "code", "name");
    var rawOrderTax = String(item.tax == null ? '' : item.tax).trim().toUpperCase();
    var knownOrderTax = ['KKKNT','KCT'].includes(rawOrderTax) || (rawOrderTax !== '' && [0,0.05,0.08,0.1].includes(Number(rawOrderTax)));
    orderForm.innerHTML = html([
      '<div class="form-grid">',
      field("Ngày", "work_date", item.work_date, "date", "required"),
      '<div class="form-field"><label>Nhà thầu</label><select name="contractor">', contractorOptions, "</select></div>",
      '<div class="form-field"><label>Mã bếp</label><select name="kitchen" required>', kitchenOptions, "</select></div>",
      '<div class="form-field"><label>Nhà cung cấp</label><select name="supplier">', supplierOptions, "</select></div>",
      field("Mã hàng", "product_code", item.product_code, "text", 'placeholder="Nhập mã để tự dò"', ""),
      field("Tên hàng", "product_name", item.product_name, "text", "required", "span-2"),
      field("Đơn vị tính", "unit", item.unit, "text", "required"),
      field("Số lượng đặt", "qty", item.qty, "number", 'step="any" min="0" required'),
      field("Số thực nhận", "actual_received", item.actual_received, "number", 'step="any" min="0" required'),
      field("Số thực giao", "actual_delivered", item.actual_delivered, "number", 'step="any" min="0" required'),
      field("Hàng hỏng", "damaged_qty", item.damaged_qty, "number", 'step="any" min="0"'),
      field("Trả nhà cung cấp", "supplier_return_qty", item.supplier_return_qty, "number", 'step="any" min="0"'),
      field("Khách trả", "customer_return_qty", item.customer_return_qty, "number", 'step="any" min="0"'),
      field("Giá mua", "buy_price", item.buy_price, "number", 'step="1" min="0" required'),
      field("Giá bán", "sell_price", item.sell_price, "number", state.editingId
        ? 'step="1" min="0" readonly title="Sửa giá trên bảng để lưu lịch sử thay đổi"'
        : 'step="1" min="0" required'),
      '<div class="form-field"><label>Thuế</label><select name="tax" required>',
      !knownOrderTax ? '<option value="" selected disabled>Thuế chưa hợp lệ — cần chọn</option>' : '',
      '<option value="KKKNT"',
      String(item.tax).toUpperCase() === "KKKNT" ? " selected" : "",
      '>KKKNT</option><option value="KCT"', String(item.tax).toUpperCase() === "KCT" ? " selected" : "",
      '>KCT</option><option value="0"', knownOrderTax && String(item.tax).toUpperCase() !== "KCT" && String(item.tax).toUpperCase() !== "KKKNT" && n(item.tax) === 0 ? " selected" : "",
      '>0%</option><option value="0.05"', n(item.tax) === 0.05 ? " selected" : "",
      '>5%</option><option value="0.08"', n(item.tax) === 0.08 ? " selected" : "",
      '>8%</option><option value="0.10"', n(item.tax) === 0.10 ? " selected" : "",
      ">10%</option></select></div>",
      '<div class="form-field"><label>Tính chất hóa đơn</label><select name="invoice_nature"><option value="1"',
      String(item.invoice_nature || "1") === "1" ? " selected" : "",
      '>1 · Hàng hóa</option><option value="2"', String(item.invoice_nature) === "2" ? " selected" : "",
      '>2 · Khuyến mại (giá bán 0)</option></select></div>',
      field("Người bán bảng kê", "seller", item.seller, "text", 'list="eligibleSellerList"'),
      '<datalist id="eligibleSellerList">', (state.data.master.eligible_sellers || []).map(function (name) { return '<option value="' + esc(name) + '"></option>'; }).join(''), '</datalist>',
      '<div class="form-field span-4 muted">Đoàn Văn Giang đã được khách xác nhận và được chọn lập bảng kê/biên nhận. Nguyễn Văn Toại vẫn bị loại khỏi chứng từ mới; dữ liệu lịch sử, kho và công nợ được giữ nguyên.</div>',
      field("CCCD", "cccd", item.cccd),
      '<div class="form-field"><label>Hàng bảng kê</label><label class="check-line"><input type="checkbox" name="purchase_list" value="1" ',
      item.purchase_list ? "checked" : "", "> Có lập bảng kê</label></div>",
      '<div class="form-field span-4"><label>Ghi chú đặt hàng / giao hàng</label><textarea name="note">',
      esc(item.note), "</textarea></div>",
      '<div class="form-actions"><button type="button" class="btn btn-outline" data-action="close-modal">Hủy</button>',
      '<button type="submit" class="btn btn-primary">Lưu và kiểm tra lại</button></div></div>'
    ]);
    backdrop.hidden = false;
    setTimeout(function () {
      var element = document.getElementById("f_product_code");
      if (element) element.focus();
    }, 50);
  }

  function openQuickAddModal(id) {
    var d = state.data;
    var context = d && d.orders.find(function (row) { return row.id === Number(id); });
    if (!context) {
      showToast("Không tìm thấy đơn cần thêm hàng", true);
      return;
    }
    state.editingId = null;
    state.quickAddContext = context;
    state.modalMode = "quick-add";
    setOrderModalWide(false);
    document.getElementById("modalTitle").textContent = "Thêm hàng vào đơn " + context.kitchen;
    orderForm.innerHTML = html([
      '<div class="quick-add-context"><span>Đang thêm vào</span><strong>', esc(context.kitchen),
      '</strong><small>', esc(context.contractor || ""), ' · Ngày ', dateVN(context.work_date), '</small></div>',
      '<div class="form-grid quick-add-grid">',
      field("Tên hàng", "product_name", "", "text", 'required autocomplete="off"', "span-2"),
      field("Số lượng", "qty", "", "number", 'step="any" min="0.01" required'),
      field("Đơn vị tính", "unit", "", "text", "required"),
      '<div class="form-actions"><button type="button" class="btn btn-outline" data-action="close-modal">Hủy</button>',
      '<button type="submit" class="btn btn-primary">Thêm vào đơn này</button></div></div>'
    ]);
    backdrop.hidden = false;
    setTimeout(function () {
      var element = document.getElementById("f_product_name");
      if (element) element.focus();
    }, 50);
  }

  function openPasteModal() {
    state.editingId = null;
    state.modalMode = "paste";
    setOrderModalWide(false);
    document.getElementById("modalTitle").textContent = "Dán nhiều dòng từ Excel";
    orderForm.innerHTML = html([
      '<div class="form-grid"><div class="form-field span-4"><div class="code-note"><strong>Cách nhanh nhất:</strong> sao chép vùng Excel có hàng tiêu đề rồi dán vào đây. Phần mềm nhận các cột Mã bếp, Mã hàng/Tên hàng, Số lượng, Nhà cung cấp, Giá mua, Giá bán, Thuế, Ghi chú.<br><br>Nếu không có tiêu đề, dùng thứ tự: Mã bếp → Tên hàng → Số lượng → Nhà cung cấp → Giá mua → Giá bán → Thuế → Ghi chú.</div></div>',
      '<div class="form-field span-4"><label>Dữ liệu sao chép từ Excel</label><textarea name="text" id="pasteText" style="min-height:280px" placeholder="POT&#9;Hành tây&#9;5&#9;kho&#9;14000&#9;16000&#9;KKKNT"></textarea></div>',
      '<div class="form-actions"><button type="button" class="btn btn-outline" data-action="close-modal">Hủy</button>',
      '<button type="submit" class="btn btn-primary">Thêm tất cả và kiểm tra</button></div></div>'
    ]);
    backdrop.hidden = false;
    setTimeout(function () {
      var element = document.getElementById("pasteText");
      if (element) element.focus();
    }, 50);
  }

  function openBulkOrderModal() {
    var data = state.data;
    if (!data || !data.batch || !data.orders.length) return;
    state.editingId = null;
    state.modalMode = "bulk-edit";
    setOrderModalWide(true);
    document.getElementById("modalTitle").textContent = "Sửa nhanh toàn bộ đơn hàng";
    var numericFields = [
      ["qty", "SL đặt"], ["actual_received", "Thực nhận"], ["damaged_qty", "Hỏng"],
      ["supplier_return_qty", "Trả nhà cung cấp"], ["actual_delivered", "Thực giao"],
      ["customer_return_qty", "Khách trả"], ["buy_price", "Giá mua"]
    ];
    function numericInput(item, pair) {
      return '<td><input class="bulk-cell bulk-number" type="number" min="0" step="any" data-bulk-field="' +
        pair[0] + '" value="' + esc(item[pair[0]]) + '" aria-label="' + esc(pair[1]) + '"></td>';
    }
    function taxOptions(item) {
      var raw = String(item.tax || "").toUpperCase();
      var values = [["KKKNT", "KKKNT"], ["KCT", "KCT"], ["0", "0%"], ["0.05", "5%"], ["0.08", "8%"], ["0.10", "10%"]];
      return values.map(function (entry) {
        var selected = raw === entry[0] || (raw !== "KKKNT" && raw !== "KCT" && Math.abs(n(item.tax) - n(entry[0])) < 0.000001);
        return '<option value="' + entry[0] + '"' + (selected ? " selected" : "") + '>' + entry[1] + '</option>';
      }).join("");
    }
    var ordered = data.orders.slice().sort(function (a, b) {
      return Number(Boolean(b.errors && b.errors.length)) - Number(Boolean(a.errors && a.errors.length)) || a.id - b.id;
    });
    var rows = ordered.map(function (item, index) {
      var issue = item.errors && item.errors.length ? item.errors.join(" · ")
        : item.warnings && item.warnings.length ? item.warnings.join(" · ") : "Đủ dữ liệu";
      return '<tr data-bulk-order-id="' + item.id + '" class="' +
        (item.errors && item.errors.length ? "row-error" : item.warnings && item.warnings.length ? "row-warning" : "") +
        '"><td>' + (index + 1) + '<div class="muted">#' + item.id + '</div></td><td><strong>' + esc(item.kitchen) +
        '</strong><div class="muted">' + esc(item.contractor) + '</div></td><td class="bulk-product"><strong>' +
        esc(item.product_code) + '</strong><div>' + esc(item.product_name) + '</div><small>' + esc(issue) + '</small></td>' +
        numericFields.map(function (pair) { return numericInput(item, pair); }).join("") +
        '<td><input class="bulk-cell" data-bulk-field="supplier" list="bulkSupplierList" value="' + esc(item.supplier) + '"></td>' +
        '<td><select class="bulk-cell" data-bulk-field="tax">' + taxOptions(item) + '</select></td>' +
        '<td><select class="bulk-cell" data-bulk-field="invoice_nature"><option value="1"' +
        (String(item.invoice_nature || "1") === "1" ? " selected" : "") + '>1 · Hàng</option><option value="2"' +
        (String(item.invoice_nature) === "2" ? " selected" : "") + '>2 · KM</option></select></td>' +
        '<td><input type="checkbox" data-bulk-field="purchase_list"' + (item.purchase_list ? " checked" : "") + '></td></tr>';
    }).join("");
    var supplierOptions = (data.master.suppliers || []).map(function (supplier) {
      return '<option value="' + esc(supplier.code) + '">' + esc(supplier.name || supplier.code) + '</option>';
    }).join("");
    orderForm.innerHTML = '<div class="code-note"><strong>Lưu một lần cho cả bảng:</strong> hệ thống kiểm tra lại mã, giá, thuế, khuyến mại, hàng hỏng và trả lại trong cùng một giao dịch. Dòng lỗi được đưa lên đầu.</div>' +
      '<datalist id="bulkSupplierList">' + supplierOptions + '</datalist><div class="bulk-grid-wrap"><table class="bulk-grid"><thead><tr>' +
      '<th>STT</th><th>Bếp</th><th>Mã / Tên / Kiểm tra</th>' + numericFields.map(function (pair) { return '<th>' + esc(pair[1]) + '</th>'; }).join("") +
      '<th>Nhà cung cấp</th><th>Thuế</th><th>Tính chất</th><th>Bảng kê</th></tr></thead><tbody>' + rows + '</tbody></table></div>' +
      '<div class="form-actions"><button type="button" class="btn btn-outline" data-action="close-modal">Hủy</button>' +
      '<button type="submit" class="btn btn-primary">Lưu cả bảng và kiểm tra lại</button></div>';
    backdrop.hidden = false;
  }

  function openImportModal(payload) {
    state.editingId = null;
    state.modalMode = "import";
    setOrderModalWide(false);
    state.pendingImport = payload;
    document.getElementById("modalTitle").textContent = payload.phase === "finalization"
      ? "File cuối ngày còn phần cần kiểm tra" : "Chọn trang Excel của đơn hàng";
    function dateToken(value) {
      var match = String(value || "").match(/(?:^|\D)(\d{1,2})[.\-_/](\d{1,2})(?:\D|$)/);
      return match ? Number(match[1]) + "." + Number(match[2]) : "";
    }
    var fileDate = dateToken(payload.filename);
    var dateMatched = fileDate ? payload.sheets.filter(function (sheet) {
      return dateToken(sheet.name) === fileDate;
    }) : [];
    var preferred = payload.sheets.filter(function (sheet) {
      return sheet.name.toLowerCase().indexOf("đơn hàng") >= 0;
    });
    var useDateMatched = dateMatched.length > 0;
    var usePreferred = !useDateMatched && preferred.length > 0;
    var sheetCards = payload.sheets.map(function (sheet) {
      var checked = payload.strictDaily
        ? Boolean(sheet.confirmAvailable)
        : (useDateMatched
        ? dateToken(sheet.name) === fileDate
        : (usePreferred ? sheet.name.toLowerCase().indexOf("đơn hàng") >= 0 : true));
      var disabled = payload.strictDaily && !sheet.confirmAvailable;
      var role = sheet.scope === "customer_orders"
        ? "Bán/giao · đơn khách, doanh thu, phải thu"
        : sheet.scope === "purchase_orders"
          ? (sheet.confirmAvailable ? "Mua/phải trả · không sửa đơn khách" : "Mua/phải trả · chưa thể chốt")
          : "Trang đơn hàng";
      var diff = sheet.diff || null;
      var diffText = diff ? " · thay đổi: +" + Number(diff.added || 0) + " thêm · " +
        Number(diff.updated || 0) + " sửa · " + Number(diff.unchanged || 0) +
        " giữ nguyên · " + Number(diff.removed || 0) + " bỏ · " +
        Number(diff.conflicts || 0) + " xung đột" : "";
      var issues = payload.strictDaily
        ? " · " + Number(sheet.errorRows || 0) + " dòng lỗi · " +
          Number(sheet.warningRows || 0) + " dòng cảnh báo · " + role + diffText
        : "";
      return '<label class="sheet-choice"><input type="checkbox" name="sheets" value="' + esc(sheet.name) + '" ' +
        (checked ? "checked " : "") + (disabled ? "disabled " : "") + '><span><strong>' +
        esc(sheet.name) + "</strong><small>" + sheet.rows + " dòng nhận diện · hàng tiêu đề " +
        sheet.headerRow + issues + "</small></span></label>";
    }).join("");
    var fallback = state.data && state.data.batch
      ? state.data.batch.work_date : currentWorkDate();
    if (payload.strictDaily && payload.detectedWorkDate) {
      fallback = payload.detectedWorkDate;
    } else if (fileDate) {
      var parts = fileDate.split(".");
      fallback = new Date().getFullYear() + "-" + String(parts[1]).padStart(2, "0") + "-" + String(parts[0]).padStart(2, "0");
    }
    var referenceNote = payload.strictDaily && payload.ignoredSheets && payload.ignoredSheets.length
      ? '<div class="form-field span-4"><div class="code-note"><strong>Các trang tham chiếu không nhập ở bước này:</strong> ' +
        payload.ignoredSheets.map(function (item) { return esc(item.name); }).join(", ") +
        '. Các trang CCCD, BÁO GIÁ và gộp đơn được bảo vệ; dữ liệu danh mục khác chỉ thay đổi ở màn hình riêng sau khi xem và xác nhận.</div></div>'
      : "";
    orderForm.innerHTML = html([
      '<div class="form-grid"><div class="form-field span-4"><div class="code-note"><strong>File: ',
      esc(payload.filename), "</strong><br>",
      payload.phase === "finalization"
        ? "File chưa thể tự lưu vì còn phần lỗi. Chỉ những phần đã kiểm tra đạt mới được chọn; phần mua không sửa đơn khách, doanh thu hay phải thu."
        : "Chỉ các trang Excel được chọn mới đi vào đơn hàng. File hợp lệ mới cùng ngày và đúng phạm vi sheet cũ sẽ thay toàn bộ dòng phiên đó, kể cả dòng sửa/thêm tay. Ngày và sheet khác, danh mục và lịch sử bản cũ được giữ; phần đã liên kết chứng từ sẽ bị chặn để đối chiếu.",
      "</div></div>",
      referenceNote,
      '<div class="form-field span-4"><label>Trang Excel cần nhập</label><div class="sheet-list">', sheetCards, "</div></div>",
      field("Ngày làm việc dự phòng", "work_date", fallback, "date", "required", "span-2"),
      '<div class="form-actions"><button type="button" class="btn btn-outline" data-action="close-modal">Hủy</button>',
      '<button type="submit" class="btn btn-primary">',
      payload.phase === "finalization" ? "Dùng các phần đạt làm bản mới nhất" : "Nhập các trang đã chọn",
      "</button></div></div>"
    ]);
    backdrop.hidden = false;
  }

  function closeModal() {
    if (state.modalMode === "import" && state.pendingImport && state.pendingImport.token) {
      var token = state.pendingImport.token;
      state.pendingImport = null;
      fetch("/api/import/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token }),
        keepalive: true
      }).catch(function () {});
    }
    backdrop.hidden = true;
    state.editingId = null;
    state.quickAddContext = null;
    setOrderModalWide(false);
  }

  async function applyPendingOrderImport(sheets, workDate, useAsLatest) {
    var pending = state.pendingImport;
    if (!pending || !pending.token) return;
    try {
      setBusy(true, useAsLatest
        ? "Đang kiểm tra và lưu file cuối cùng làm bản chuẩn…"
        : "Đang nhập, đối chiếu danh mục và kiểm tra giá…");
      var imported = await api("/api/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: pending.token,
          work_date: workDate,
          sheets: sheets,
          state_hash: pending.stateHash || ""
        })
      });
      state.orderImportMessage = imported.replacement ? imported.replacement.message + ' ' + imported.replacement.replaced_rows + ' dòng cũ → ' + imported.replacement.new_rows + ' dòng mới.' :
        imported.idempotent ? 'File này đã được nạp; giữ bản hiện tại, không tạo thêm dòng hoặc trừ kho lần nữa.' :
        'Đã cập nhật phạm vi vừa chọn. Các ngày khác, danh mục và phần mua/bán không chọn được giữ nguyên.';
      state.pendingImport = null;
      closeModal();
      var automaticallyApproved = false;
      var approvalWarning = "";
      if (!pending.continuous && useAsLatest && imported.finalized && imported.batch.status !== "approved" &&
          n(imported.summary && imported.summary.totals && imported.summary.totals.errors) === 0) {
        try {
          var approvalResult = await confirmBatchApproval(imported.batch.id);
          if (approvalResult) { imported = approvalResult; automaticallyApproved = true; }
          else approvalWarning = "Đơn chưa duyệt. Kiểm tra bảng kê rồi bấm Duyệt đơn.";
        } catch (approvalError) {
          approvalWarning = approvalError.message;
        }
      }
      state.batchId = imported.batch.id;
      state.view = "orders";
      await loadData(state.batchId, true);
      var message = useAsLatest
        ? (automaticallyApproved
          ? "Đã dùng file cuối cùng làm bản chuẩn và tự chốt đơn"
          : "Đã dùng file cuối cùng làm bản mới nhất" + (approvalWarning ? " · chưa tự chốt: " + approvalWarning : ""))
        : imported.selectedScopes
          ? "Đã chốt " + imported.selectedScopes.map(function (scope) {
            return scope === "customer_orders" ? "Bán/giao" : "Mua/phải trả";
          }).join(" + ")
          : "Đã nhập " + imported.orders.length + " dòng · " + imported.summary.totals.errors +
            " lỗi · " + (imported.summary.totals.warnings || 0) + " cảnh báo";
      showToast(message, Boolean(approvalWarning));
      if (pending.continuous) openOrderWorksheet();
      return true;
    } catch (error) {
      state.busy = false;
      render();
      showToast(error.message, true);
      return false;
    }
  }

  async function importExcel(file) {
    if (!file) return;
    setBusy(true, "Đang nhận diện các trang Excel trong " + file.name + "…");
    try {
      var form = new FormData();
      form.append("file", file);
      form.append("continuous", "1");
      var payload = await api("/api/import/analyze", { method: "POST", body: form });
      payload.continuous = true;
      state.busy = false;
      render();
      if (payload.strictDaily && payload.phase !== "finalization") {
        var initialSheets = (payload.sheets || []).filter(function (sheet) {
          return sheet.scope === "customer_orders" && sheet.confirmAvailable;
        });
        if (initialSheets.length === 1 && payload.detectedWorkDate) {
          state.pendingImport = payload;
          await applyPendingOrderImport([initialSheets[0].name], payload.detectedWorkDate, false);
          return;
        }
      }
      if (payload.strictDaily && payload.phase === "finalization") {
        var scopedSheets = (payload.sheets || []).filter(function (sheet) {
          return sheet.scope === "customer_orders" || sheet.scope === "purchase_orders";
        });
        var confirmableSheets = scopedSheets.filter(function (sheet) {
          return Boolean(sheet.confirmAvailable);
        });
        if (scopedSheets.length && confirmableSheets.length === scopedSheets.length) {
          state.pendingImport = payload;
          await applyPendingOrderImport(confirmableSheets.map(function (sheet) {
            return sheet.name;
          }), payload.detectedWorkDate, true);
          return;
        }
      }
      openImportModal(payload);
    } catch (error) {
      state.busy = false;
      render();
      showToast(error.message, true);
    }
  }

  async function newBatch() {
    var workDateText = window.prompt("Ngày làm việc (dd/mm/yyyy):", dateVN(currentWorkDate()));
    if (!workDateText) return;
    var workDate = parseLocalizedTemporal(workDateText, "date");
    if (!workDate) { showToast("Ngày làm việc chưa đúng dạng dd/mm/yyyy", true); return; }
    try {
      var payload = await api("/api/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ work_date: workDate })
      });
      state.batchId = payload.batch.id;
      state.view = "orders";
      await loadData(state.batchId);
      openOrderModal(null);
    } catch (error) { showToast(error.message, true); }
  }

  async function saveOrder(event) {
    event.preventDefault();
    var form = new FormData(orderForm);
    if (state.modalMode === "import") {
      var sheets = form.getAll("sheets");
      if (!sheets.length) {
        showToast(state.pendingImport && state.pendingImport.phase === "finalization"
          ? "Cần chọn rõ ít nhất một phạm vi bán/giao hoặc mua/phải trả"
          : "Cần chọn ít nhất một trang Excel", true);
        return;
      }
      var imported = await applyPendingOrderImport(sheets, form.get("work_date"),
        state.pendingImport && state.pendingImport.phase === "finalization");
      if (!imported) backdrop.hidden = false;
      return;
    }
    if (state.modalMode === "paste") {
      try {
        var bulk = await api("/api/orders/bulk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ batch_id: state.batchId, text: form.get("text") })
        });
        closeModal();
        await loadData(bulk.batch.id, true);
        showToast("Đã thêm " + bulk.inserted + " dòng và tự kiểm tra");
      } catch (error) { showToast(error.message, true); }
      return;
    }
    if (state.modalMode === "bulk-edit") {
      var numeric = new Set(["qty", "actual_received", "damaged_qty", "supplier_return_qty",
        "actual_delivered", "customer_return_qty", "buy_price", "sell_price"]);
      var items = Array.from(orderForm.querySelectorAll("[data-bulk-order-id]")).map(function (row) {
        var item = { id: Number(row.dataset.bulkOrderId) };
        row.querySelectorAll("[data-bulk-field]").forEach(function (input) {
          var key = input.dataset.bulkField;
          item[key] = input.type === "checkbox" ? (input.checked ? 1 : 0) : (numeric.has(key) ? n(input.value) : input.value);
        });
        return item;
      });
      try {
        if (event.submitter) event.submitter.disabled = true;
        var updated = await api("/api/orders/bulk-update", {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ batch_id: state.batchId, items: items })
        });
        closeModal();
        await loadData(updated.batch.id, true);
        showToast("Đã cập nhật " + updated.updated + " dòng · còn " + updated.error_rows + " lỗi · " + updated.warning_rows + " cảnh báo");
      } catch (error) {
        if (event.submitter) event.submitter.disabled = false;
        showToast(error.message, true);
      }
      return;
    }
    if (state.modalMode === "quick-add") {
      var context = state.quickAddContext;
      if (!context) {
        showToast("Đơn gốc không còn tồn tại; hãy mở lại đơn rồi thử lại", true);
        return;
      }
      try {
        if (event.submitter) event.submitter.disabled = true;
        var quickPayload = await api("/api/orders", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            batch_id: state.batchId,
            work_date: context.work_date,
            contractor: context.contractor,
            kitchen: context.kitchen,
            product_name: form.get("product_name"),
            qty: n(form.get("qty")),
            unit: form.get("unit")
          })
        });
        closeModal();
        await loadData(quickPayload.batch.id, true);
        showToast("Đã thêm hàng vào đúng đơn " + context.kitchen + " và kiểm tra lại dữ liệu");
      } catch (error) {
        if (event.submitter) event.submitter.disabled = false;
        showToast(error.message, true);
      }
      return;
    }
    var body = Object.fromEntries(form.entries());
    ["qty", "actual_received", "actual_delivered", "damaged_qty", "supplier_return_qty", "customer_return_qty", "buy_price", "sell_price"].forEach(function (key) {
      body[key] = n(body[key]);
    });
    body.purchase_list = form.has("purchase_list") ? 1 : 0;
    body.batch_id = state.batchId;
    try {
      var url = state.editingId ? "/api/orders/" + state.editingId : "/api/orders";
      var method = state.editingId ? "PUT" : "POST";
      var payload = await api(url, {
        method: method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      closeModal();
      await loadData(payload.batch.id, true);
      showToast("Đã lưu dòng đơn và kiểm tra lại");
    } catch (error) { showToast(error.message, true); }
  }

  async function deleteOrder(id) {
    if (!window.confirm("Xóa dòng đơn này?")) return;
    try {
      var payload = await api("/api/orders/" + id, { method: "DELETE" });
      await loadData(payload.batch.id, true);
      showToast("Đã xóa dòng đơn");
    } catch (error) { showToast(error.message, true); }
  }

  async function saveSellPriceOverrides(inputList) {
    var inputs = Array.from(inputList || content.querySelectorAll(".quick-sell-price"));
    var changed = inputs.filter(function (input) {
      return Math.abs(Number(input.value) - Number(input.dataset.original)) > 0.000001;
    });
    if (!changed.length) {
      showToast("Chưa có giá bán nào thay đổi", true);
      return;
    }
    var actorInput = document.getElementById("priceOverrideActor");
    var reasonInput = document.getElementById("priceOverrideReason");
    var actor = actorInput ? actorInput.value.trim() : "";
    var reason = reasonInput ? reasonInput.value.trim() : "";
    if (!actor) {
      showToast("Cần ghi người thực hiện trước khi lưu giá", true);
      if (actorInput) actorInput.focus();
      return;
    }
    if (!reason) {
      showToast("Cần ghi lý do thay đổi giá", true);
      if (reasonInput) reasonInput.focus();
      return;
    }
    try {
      var payload = await api("/api/orders/sell-price-overrides", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          batch_id: state.batchId,
          actor: actor,
          reason: reason,
          items: changed.map(function (input) {
            return {
              id: Number(input.dataset.orderId),
              sell_price: Number(input.value),
              expected_revision: Number(input.dataset.revision || 1)
            };
          })
        })
      });
      state.priceOverrideActor = actor;
      state.priceOverrideReason = "";
      await loadData(payload.batch.id, true);
      showToast("Đã lưu giá sửa tay cho " + payload.updated + " dòng và lưu lịch sử thay đổi");
    } catch (error) {
      showToast(error.message, true);
    }
  }

  async function confirmBatchApproval(batchId) {
      var preview = await api("/api/batches/" + batchId + "/approval-preview");
      if (!preview.canApprove) {
        var dialog = document.createElement('dialog');
        dialog.className = 'inventory-totals-dialog batch-bk-approval-dialog';
        dialog.setAttribute('aria-label', 'Bảng kê cần kiểm tra');
        dialog.innerHTML = '<div class="inventory-totals-heading"><h3>Bảng kê cần kiểm tra</h3><button type="button" class="icon-button" aria-label="Đóng">×</button></div><p>Sửa các dòng dưới đây rồi duyệt lại. Đơn và kho chưa thay đổi.</p><div class="inventory-totals-body"><table><thead><tr><th>Dòng</th><th>Mặt hàng</th><th>Cần sửa</th><th></th></tr></thead><tbody>' +
          (preview.issues || []).map(function (r) { return '<tr><td>' + esc(r.row) + '</td><td>' + esc(r.code) + ' · ' + esc(r.name || '') + '</td><td>' + esc((r.errors || []).join('; ')) + '</td><td>' + (r.orderId ? '<button type="button" class="btn btn-outline" data-bk-edit="' + esc(r.orderId) + '">Sửa dòng</button>' : '') + '</td></tr>'; }).join('') + '</tbody></table></div>';
        dialog.querySelector('button').onclick = function () { dialog.close(); };
        dialog.querySelectorAll('[data-bk-edit]').forEach(function (button) { button.onclick = function () { dialog.close(); openOrderModal(Number(button.getAttribute('data-bk-edit'))); }; });
        dialog.addEventListener('close', function () { dialog.remove(); });
        document.body.appendChild(dialog); dialog.showModal();
        return null;
      }
      var text = preview.alreadyPosted ? "Đơn đã có bảng kê nhập kho. Kiểm tra lại trạng thái duyệt?" :
        preview.rowCount ? "Duyệt đơn và ghi nhập kho " + preview.rowCount + " dòng bảng kê, " + money(preview.amount) + "?\nSố lượng dùng theo thực nhận trong đơn. Giá bảng kê bằng " + preview.ratePercent + "% giá bán." : "Duyệt đơn hàng này? Không có dòng bảng kê cần nhập kho.";
      if (preview.excludedRows) text += "\n" + preview.excludedRows + " dòng thuộc người bán đã loại khỏi bảng kê.";
      if ((preview.overlaps || []).length) text += "\n\nCác mã đã nhập kho cùng ngày từ hóa đơn hoặc bảng kê: " + Array.from(new Set(preview.overlaps.map(function (r) { return r.code; }))).join(', ') + ".\nChỉ đồng ý nếu đây là lần mua riêng, chưa nằm trong phần đã nhập kho.";
      if (!window.confirm(text)) return null;
      return api("/api/batches/" + batchId + "/approve", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_hash: preview.sourceHash, confirm_bk: true, confirm_separate_purchases: Boolean((preview.overlaps || []).length) }) });
  }

  async function approveBatch() {
    if (!state.batchId) return;
    try {
      var batchId = state.batchId;
      var approved = await confirmBatchApproval(batchId);
      if (!approved) return;
      await loadData(batchId, true);
      showToast(approved.bk && approved.bk.inventoryLines ? "Đã duyệt đơn và ghi bảng kê vào kho" : "Đã duyệt đơn hàng");
    } catch (error) { showToast(error.message, true); }
  }

  function supplierImageFilename(group) {
    var supplier = String(group.supplier || "NCC").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^A-Za-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "") || "NCC";
    return "Don_dat_hang_" + supplier + "_" + state.data.batch.work_date + ".png";
  }

  function downloadBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function canvasTextLines(context, value, maxWidth, maxLines) {
    var words = String(value || "").split(/\s+/).filter(Boolean);
    var lines = [];
    var current = "";
    words.forEach(function (word) {
      var candidate = current ? current + " " + word : word;
      if (current && context.measureText(candidate).width > maxWidth) {
        lines.push(current);
        current = word;
      } else current = candidate;
    });
    if (current) lines.push(current);
    if (!lines.length) lines.push("");
    if (lines.length > maxLines) {
      lines = lines.slice(0, maxLines);
      while (context.measureText(lines[maxLines - 1] + "…").width > maxWidth && lines[maxLines - 1].length) {
        lines[maxLines - 1] = lines[maxLines - 1].slice(0, -1);
      }
      lines[maxLines - 1] += "…";
    }
    return lines;
  }

  function supplierOrderImageBlob(group) {
    return new Promise(function (resolve, reject) {
      var scale = 2;
      var logicalWidth = 1400;
      var left = 30;
      var tableTop = 110;
      var headerHeight = 58;
      var rowHeight = 76;
      var logicalHeight = tableTop + headerHeight + group.items.length * rowHeight + 30;
      scale = Math.min(scale, 30000 / logicalHeight);
      var canvas = document.createElement("canvas");
      canvas.width = logicalWidth * scale;
      canvas.height = logicalHeight * scale;
      var ctx = canvas.getContext("2d");
      if (!ctx) { reject(new Error("Trình duyệt không tạo được ảnh")); return; }
      ctx.scale(scale, scale);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, logicalWidth, logicalHeight);
      ctx.textBaseline = "middle";

      ctx.fillStyle = "#17324d";
      ctx.font = "bold 30px Arial, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("ĐƠN ĐẶT HÀNG – NHÀ CUNG CẤP " + String(group.supplier || "").toUpperCase() + " – " +
        dateVN(state.data.batch.work_date), logicalWidth / 2, 45);

      var imageContract = (state.supplierNeeds && state.supplierNeeds.image_contract) || {};
      var imageColumns = imageContract.columns || [
        { key: "kitchen", label: "Mã bếp" }, { key: "work_date", label: "Ngày" },
        { key: "product_name", label: "Tên hàng" }, { key: "order_qty", label: "Số lượng" },
        { key: "unit", label: "Đơn vị" }, { key: "supplier", label: "Nhà cung cấp" },
        { key: "note", label: "Ghi chú" }
      ];
      var widthByKey = { kitchen: 140, work_date: 150, product_name: 360, order_qty: 140,
        unit: 80, supplier: 140, note: 320 };
      var widths = imageColumns.map(function (column) { return widthByKey[column.key] || 140; });
      var headers = imageColumns.map(function (column) { return column.label; });
      var tableWidth = widths.reduce(function (sum, value) { return sum + value; }, 0);
      var x = left;
      ctx.fillStyle = "#087f73";
      ctx.fillRect(left, tableTop, tableWidth, headerHeight);
      ctx.font = "bold 21px Arial, sans-serif";
      ctx.fillStyle = "#ffffff";
      headers.forEach(function (label, index) {
        ctx.textAlign = "center";
        ctx.fillText(label, x + widths[index] / 2, tableTop + headerHeight / 2);
        x += widths[index];
      });

      group.items.forEach(function (item, rowIndex) {
        var y = tableTop + headerHeight + rowIndex * rowHeight;
        ctx.fillStyle = rowIndex % 2 ? "#f4f8fb" : "#ffffff";
        ctx.fillRect(left, y, tableWidth, rowHeight);
        var rowData = {
          kitchen: item.kitchen,
          work_date: dateVN(item.work_date || state.data.batch.work_date),
          product_name: item.product_name,
          order_qty: stockQty(item.order_qty == null ? item.required_qty : item.order_qty),
          unit: item.unit,
          supplier: item.supplier || group.supplier,
          note: item.note || ""
        };
        var values = imageColumns.map(function (column) { return rowData[column.key] || ""; });
        x = left;
        values.forEach(function (value, colIndex) {
          var columnKey = imageColumns[colIndex].key;
          ctx.fillStyle = "#172b3e";
          ctx.font = (columnKey === "order_qty" ? "bold " : "") + "20px Arial, sans-serif";
          if (columnKey === "product_name" || columnKey === "note") {
            ctx.textAlign = "left";
            var lines = canvasTextLines(ctx, value, widths[colIndex] - 24, 3);
            var lineGap = 23;
            var firstY = y + rowHeight / 2 - (lines.length - 1) * lineGap / 2;
            lines.forEach(function (line, lineIndex) {
              ctx.fillText(line, x + 12, firstY + lineIndex * lineGap);
            });
          } else if (columnKey === "order_qty") {
            ctx.textAlign = "right";
            ctx.fillText(value, x + widths[colIndex] - 14, y + rowHeight / 2);
          } else {
            ctx.textAlign = "center";
            ctx.fillText(value, x + widths[colIndex] / 2, y + rowHeight / 2);
          }
          x += widths[colIndex];
        });
      });

      ctx.strokeStyle = "#9fb0bf";
      ctx.lineWidth = 1;
      var bottom = tableTop + headerHeight + group.items.length * rowHeight;
      x = left;
      ctx.beginPath();
      ctx.rect(left, tableTop, tableWidth, bottom - tableTop);
      widths.forEach(function (width) { x += width; ctx.moveTo(x, tableTop); ctx.lineTo(x, bottom); });
      for (var row = 0; row <= group.items.length; row += 1) {
        var rowY = tableTop + headerHeight + row * rowHeight;
        ctx.moveTo(left, rowY); ctx.lineTo(left + tableWidth, rowY);
      }
      ctx.stroke();
      canvas.toBlob(function (blob) {
        if (blob) resolve(blob); else reject(new Error("Không tạo được file ảnh PNG"));
      }, "image/png");
    });
  }

  async function handleSupplierImage(groupIndex, downloadOnly) {
    var group = state.supplierNeeds && state.supplierNeeds.groups[Number(groupIndex)];
    if (!group) { showToast("Không tìm thấy nhóm đơn nhà cung cấp", true); return; }
    var requestedBatch = state.batchId;
    group = supplierPresentation(group);
    var planHash = state.supplierNeeds.plan_hash;
    try {
      var blob = await supplierOrderImageBlob(group);
      var filename = supplierImageFilename(group);
      if (downloadOnly) {
        downloadBlob(blob, filename);
        showToast("Đã tải ảnh đơn đặt hàng");
        return;
      }
      var imageMessage = "";
      var copied = false;
      if (!navigator.clipboard || !window.ClipboardItem || !window.isSecureContext) {
        downloadBlob(blob, filename);
        imageMessage = "Trình duyệt đã tải ảnh PNG để gửi Zalo";
      } else {
        try {
          await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
          copied = true;
          imageMessage = "Đã sao chép ảnh · mở Zalo và bấm Ctrl+V để gửi";
        } catch (clipboardError) {
          downloadBlob(blob, filename);
          imageMessage = "Đã tải ảnh PNG để gửi Zalo";
        }
      }
      if (!copied) { showToast(imageMessage + ' · chưa đánh dấu Đã đặt vì chưa sao chép thành công', true); return; }
      if (group.order_status !== "ordered") {
        await api("/api/supplier-order-status/" + requestedBatch + "/" +
          encodeURIComponent(group.supplier_key || group.supplier), {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "ordered", revision: n(group.order_status_revision), plan_hash: planHash })
          });
        if (requestedBatch === state.batchId) {
          state.supplierNeeds = null;
          await fetchSupplierNeeds();
        }
      }
      showToast(imageMessage + " · đã tự ghi nhận Đã đặt");
    } catch (error) {
      showToast(error.message || "Không tạo được ảnh đơn đặt hàng", true);
    }
  }

  function invalidateReceivableWorkspace(clearHistory) {
    state.receivableRequestSerial += 1;
    state.receivableLoading = false;
    state.receivableLedger = null;
    state.receivableError = "";
    if (clearHistory) {
      state.receivableExpanded = {};
      state.receivableRevisions = {};
    }
  }

  async function toggleReceivableHistory(button) {
    var key = String(button.dataset.id);
    if (state.receivableExpanded[key]) {
      delete state.receivableExpanded[key];
      renderDebts();
      return;
    }
    state.receivableExpanded[key] = true;
    if (state.receivableRevisions[key] && state.receivableRevisions[key] !== "loading") {
      renderDebts();
      return;
    }
    var requestSerial = state.receivableRequestSerial;
    state.receivableRevisions[key] = "loading";
    renderDebts();
    try {
      var history = await api("/api/debts/receivables/ledger/" + encodeURIComponent(key) + "/revisions");
      if (requestSerial !== state.receivableRequestSerial) return;
      state.receivableRevisions[key] = history;
    } catch (error) {
      if (requestSerial !== state.receivableRequestSerial) return;
      state.receivableRevisions[key] = { error: error.message };
    }
    if (state.view === "debts") renderDebts();
  }

  function invalidatePayableWorkspace(clearSelection) {
    state.payableRequestSerial += 1;
    state.payableLoading = false;
    state.payableLedger = null;
    state.payablePayments = null;
    state.payableError = "";
    if (clearSelection) state.payableSelected = {};
  }

  async function savePayment(formElement) {
    if (formElement.dataset.saving) return;
    var body = Object.fromEntries(new FormData(formElement).entries());
    body.amount = Number(body.amount); body.party_type = "contractor";
    if (!formElement.dataset.requestId) formElement.dataset.requestId = payableRequestId();
    body.request_id = formElement.dataset.requestId;
    var button = formElement.querySelector('[type="submit"]');
    formElement.dataset.saving = "1"; if (button) button.disabled = true;
    try {
      await api("/api/payments", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
      formElement.reset(); delete formElement.dataset.requestId;
      invalidateDebtPeriod(); await fetchDebtPeriod();
      showToast("Đã ghi nhận khoản thu khách hàng");
    } catch (error) { showToast(error.message, true); }
    finally { delete formElement.dataset.saving; if (button) button.disabled = false; }
  }

  function payableRequestId() {
    var random = window.crypto && window.crypto.randomUUID
      ? window.crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
    return "PAY-UI-" + Date.now() + "-" + random;
  }

  async function refreshPayablesAfterMutation(message) {
    invalidateDebtPeriod();
    invalidatePayableWorkspace(true);
    await Promise.all([fetchDebtPeriod(), fetchPayableWorkspace()]);
    if (message) showToast(message);
  }

  async function savePayablePayment(formElement, submitButton) {
    var selection = payableSelectionState();
    if (!selection.ready) {
      updatePayableSelectionSummary();
      showToast("Kiểm tra nhà cung cấp và số tiền phân bổ của từng dòng", true);
      return;
    }
    var form = Object.fromEntries(new FormData(formElement).entries());
    var body = {
      request_id: formElement.dataset.requestId || (formElement.dataset.requestId = payableRequestId()),
      actor: form.actor || "",
      payment_date: form.payment_date,
      party_code: selection.suppliers[0],
      amount: selection.total,
      method: form.method || "",
      reference_code: form.reference_code || "",
      note: form.note || "",
      allocations: selection.entries.map(function (item) {
        return {
          ledger_line_id: item.id,
          amount: Number(item.amount),
          expected_revision: Number(item.revision)
        };
      })
    };
    if (!window.confirm(
      "Ghi nhận trả " + money(body.amount) + " cho " + body.party_code +
      " vào " + body.allocations.length + " dòng đã chọn?"
    )) return;
    var originalLabel = submitButton ? submitButton.textContent : "Ghi nhận thanh toán";
    try {
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Đang ghi nhận…";
      }
      await api("/api/debts/payables/payments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      await refreshPayablesAfterMutation(
        "Đã ghi nhận " + money(body.amount) + " cho " + body.party_code +
        " vào " + body.allocations.length + " dòng"
      );
    } catch (error) {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalLabel;
      }
      if (error.status === 409) {
        invalidatePayableWorkspace(true);
        await fetchPayableWorkspace();
      }
      showToast(error.message, true);
    }
  }

  async function reversePayablePayment(button) {
    var actor = window.prompt("Tên người hoàn tác (bắt buộc):", "");
    if (!actor || !actor.trim()) return;
    var reason = window.prompt(
      "Lý do hoàn tác giao dịch #" + button.dataset.id + " (bắt buộc):", ""
    );
    if (reason === null) return;
    reason = reason.trim();
    if (!reason) {
      showToast("Phải nhập lý do hoàn tác", true);
      return;
    }
    if (!window.confirm(
      "Hoàn tác khoản trả " + money(button.dataset.amount) + " cho " +
      button.dataset.supplier + "? Các dòng nợ sẽ được tính lại."
    )) return;
    var originalLabel = button.textContent;
    try {
      button.disabled = true;
      button.textContent = "Đang hoàn tác…";
      await api("/api/debts/payables/payments/" + button.dataset.id + "/reverse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_revision: Number(button.dataset.revision),
          reason: reason,
          actor: actor.trim()
        })
      });
      await refreshPayablesAfterMutation("Đã hoàn tác giao dịch và trả lại số còn nợ cho các dòng");
    } catch (error) {
      button.disabled = false;
      button.textContent = originalLabel;
      if (error.status === 409) {
        invalidatePayableWorkspace(true);
        await fetchPayableWorkspace();
      }
      showToast(error.message, true);
    }
  }

  async function saveBalance(formElement) {
    var body = Object.fromEntries(new FormData(formElement).entries());
    body.opening = n(body.opening);
    try {
      await api("/api/balances", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
      invalidateDebtPeriod();
      await loadData(state.batchId, true);
      showToast("Đã cập nhật số dư đầu kỳ");
    } catch (error) { showToast(error.message, true); }
  }

  function invalidateDebtPeriod() {
    state.debtSerial++; state.debtLoading = false; state.debtPeriod = null;
    state.debtError = ""; state.receiptHistory = [];
  }

  async function fetchDebtPeriod() {
    if (!state.debtFrom || !state.debtTo || state.debtLoading) return;
    var serial = ++state.debtSerial;
    var query = "from=" + encodeURIComponent(state.debtFrom) + "&to=" + encodeURIComponent(state.debtTo);
    state.debtLoading = true; state.debtError = "";
    try {
      var result = await api("/api/debts?" + query);
      if (serial !== state.debtSerial) return;
      state.debtPeriod = result; state.receiptHistory = result.receipts || [];
    } catch (error) {
      if (serial !== state.debtSerial) return;
      state.debtPeriod = null; state.receiptHistory = []; state.debtError = error.message;
    } finally {
      if (serial === state.debtSerial) {
        state.debtLoading = false;
        if (state.view === "debts") renderDebts();
      }
    }
  }

  async function fetchReceivableWorkspace() {
    if (!state.debtFrom || !state.debtTo || state.receivableLoading) return;
    var requestSerial = ++state.receivableRequestSerial;
    var query = "from=" + encodeURIComponent(state.debtFrom) +
      "&to=" + encodeURIComponent(state.debtTo) +
      "&status=" + encodeURIComponent(state.receivableStatus || "active") + "&limit=5000&offset=" + state.receivableOffset;
    if (state.receivableContractor) {
      query += "&contractor=" + encodeURIComponent(state.receivableContractor);
    }
    if (state.receivableKitchen) {
      query += "&kitchen=" + encodeURIComponent(state.receivableKitchen);
    }
    state.receivableLoading = true;
    state.receivableError = "";
    try {
      var ledger = await api("/api/debts/receivables/ledger?" + query);
      if (requestSerial !== state.receivableRequestSerial) return;
      state.receivableLedger = ledger;
    } catch (error) {
      if (requestSerial !== state.receivableRequestSerial) return;
      state.receivableError = error.message;
      state.receivableLedger = null;
    } finally {
      if (requestSerial === state.receivableRequestSerial) {
        state.receivableLoading = false;
        if (state.view === "debts") renderDebts();
      }
    }
  }

  async function fetchPayableWorkspace() {
    if (!state.debtFrom || !state.debtTo || state.payableLoading) return;
    var requestSerial = ++state.payableRequestSerial;
    var dateFrom = state.debtFrom;
    var dateTo = state.debtTo;
    var supplier = state.payableSupplier;
    var status = state.payableStatus === "outstanding" ? "open,partially_paid" : state.payableStatus;
    var query = "from=" + encodeURIComponent(dateFrom) + "&to=" + encodeURIComponent(dateTo) +
      "&status=" + encodeURIComponent(status || "outstanding") + "&limit=5000&offset=" + state.payableOffset;
    if (supplier) query += "&supplier=" + encodeURIComponent(supplier);
    state.payableLoading = true;
    state.payableError = "";
    try {
      var results = await Promise.all([
        api("/api/debts/payables/ledger?" + query),
        api("/api/debts/payables/payments?from=" + encodeURIComponent(dateFrom) +
          "&to=" + encodeURIComponent(dateTo) + "&status=all&limit=5000&offset=" + state.payableHistoryOffset +
          (supplier ? "&supplier=" + encodeURIComponent(supplier) : ""))
      ]);
      if (requestSerial !== state.payableRequestSerial) return;
      state.payableLedger = results[0];
      state.payablePayments = results[1];
      var currentRows = {};
      (state.payableLedger.rows || []).forEach(function (item) { currentRows[item.id] = item; });
      Object.keys(state.payableSelected).forEach(function (id) {
        var row = currentRows[id];
        if (!row || (row.status !== "open" && row.status !== "partially_paid") || n(row.remaining_amount) <= 0) {
          delete state.payableSelected[id];
        }
      });
    } catch (error) {
      if (requestSerial !== state.payableRequestSerial) return;
      state.payableError = error.message;
      state.payableLedger = null;
      state.payablePayments = null;
    } finally {
      if (requestSerial === state.payableRequestSerial) {
        state.payableLoading = false;
        if (state.view === "debts") renderDebts();
      }
    }
  }

  async function fetchOutgoingInvoices() {
    if (state.outgoingInvoicesLoading) return;
    state.outgoingInvoicesLoading = true;
    var outgoingBatchId = state.batchId;
    var serial = state.outgoingInvoicesSerial = (state.outgoingInvoicesSerial || 0) + 1;
    try {
      var payload = await api('/api/outgoing-invoices' + (outgoingBatchId ? '?batch_id=' + encodeURIComponent(outgoingBatchId) : ''));
      if (outgoingBatchId !== state.batchId || serial !== state.outgoingInvoicesSerial) return;
      state.outgoingInvoices = payload.items || [];
      state.buyerProfiles = payload.buyer_profiles || {};
      if (state.view === "documents") renderDocuments();
    } catch (error) { showToast(error.message, true); }
    finally {
      if (serial === state.outgoingInvoicesSerial) {
        state.outgoingInvoicesLoading = false;
        if (outgoingBatchId !== state.batchId && state.view === 'documents') setTimeout(fetchOutgoingInvoices, 0);
      }
    }
  }

  async function fetchOutgoingReadiness() {
    if (!state.batchId || state.outgoingReadinessLoading) return;
    state.outgoingReadinessLoading = true;
    var batchId = state.batchId;
    var serial = state.outgoingReadinessSerial = (state.outgoingReadinessSerial || 0) + 1;
    try {
      var payload = await api("/api/outgoing-invoices/readiness/" + batchId);
      if (serial !== state.outgoingReadinessSerial || batchId !== state.batchId) return;
      state.outgoingReadiness = payload;
    } catch (error) {
      if (serial !== state.outgoingReadinessSerial || batchId !== state.batchId) return;
      state.outgoingReadiness = { error: error.message, rows: [], demand_qty: 0,
        allocated_qty: 0, invoiceable_qty: 0, pending_qty: 0 };
      showToast(error.message, true);
    } finally {
      if (serial === state.outgoingReadinessSerial) {
        state.outgoingReadinessLoading = false;
        if (batchId !== state.batchId) state.outgoingReadiness = null;
        if (state.view === "documents") renderDocuments();
      }
    }
  }

  async function fetchOutgoingSubstitutions() {
    if (!state.batchId || state.outgoingSubstitutionLoading) return;
    state.outgoingSubstitutionLoading = true;
    try {
      var payload = await api("/api/outgoing-substitutions?batch_id=" + encodeURIComponent(state.batchId));
      state.outgoingSubstitutionActions = payload.items || [];
    } catch (error) {
      state.outgoingSubstitutionActions = [];
      showToast(error.message, true);
    } finally {
      state.outgoingSubstitutionLoading = false;
      if (state.view === "documents") renderDocuments();
    }
  }

  function outgoingSubstitutionFormBody(form) {
    form = form || document.getElementById("outgoingSubstitutionForm");
    if (!form) return null;
    var data = new FormData(form);
    var overrideText = String(data.get("override_price") || "").trim();
    return {
      batch_id: state.batchId,
      order_id: Number(data.get("order_id") || 0),
      substitute_product_code: String(data.get("substitute_product_code") || "").trim().toUpperCase(),
      qty: Number(data.get("qty")),
      actor: String(data.get("actor") || "").trim(),
      reason: String(data.get("reason") || "").trim(),
      override_price: overrideText === "" ? "" : Number(overrideText),
      override_reason: String(data.get("override_reason") || "").trim(),
      approve_price_override: data.has("approve_price_override")
    };
  }

  function sameOutgoingSubstitutionRequest(left, right) {
    return Boolean(left && right && JSON.stringify(left) === JSON.stringify(right));
  }

  async function fetchOutgoingPeriodShortages() {
    if (state.outgoingShortageLoading) return;
    state.outgoingShortageLoading = true;
    try {
      var query = "from=" + encodeURIComponent(state.outgoingShortageFrom) +
        "&to=" + encodeURIComponent(state.outgoingShortageTo) +
        "&contractor=" + encodeURIComponent(state.outgoingShortageContractor);
      state.outgoingPeriodShortages = await api("/api/outgoing-invoices/shortages?" + query);
    } catch (error) {
      state.outgoingPeriodShortages = { error: error.message, shortages: [] };
      showToast(error.message, true);
    } finally {
      state.outgoingShortageLoading = false;
      if (state.view === "documents") renderDocuments();
    }
  }

  async function checkMinvoice(button) {
    try {
      button.disabled = true;
      button.textContent = "Đang kiểm tra…";
      state.minvoiceStatus = await api("/api/minvoice/status");
      renderSettings();
      showToast(state.minvoiceStatus.warning || (state.minvoiceStatus.draft_save_available === false ? "Đã kết nối portal công ty · có thể tải hóa đơn" : "M-Invoice đã kết nối · có thể lưu nháp chờ ký · " + num(state.minvoiceStatus.outgoing.series_count) + " ký hiệu"), !!state.minvoiceStatus.warning);
    } catch (error) {
      button.disabled = false;
      button.textContent = "Kiểm tra lại";
      showToast(error.message, true);
    }
  }

  async function reverseReceipt(button) {
    var reason = window.prompt("Lý do hoàn tác khoản thu (bắt buộc):", "");
    if (!reason || !reason.trim()) return;
    var actor = window.prompt("Tên người hoàn tác (bắt buộc):", "");
    if (!actor || !actor.trim()) return;
    if (!window.confirm("Hoàn tác khoản thu này? Giao dịch và lý do vẫn được giữ trong lịch sử.")) return;
    button.disabled = true;
    try {
      await api("/api/debts/receipts/" + button.dataset.id + "/reverse", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({reason: reason.trim(), actor: actor.trim(), expected_revision: Number(button.dataset.revision)})
      });
      invalidateDebtPeriod(); await fetchDebtPeriod();
      showToast("Đã hoàn tác, vẫn giữ lịch sử khoản thu");
    } catch (error) { showToast(error.message, true); button.disabled = false; }
  }

  async function refreshOperations(message) {
    state.operations = null;
    state.inventoryValuation = null;
    state.bkDocuments = null;
    await loadOperations(true);
    if (message) showToast(message);
  }

  async function importAttendance(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("file", file);
      form.append("period", state.opsMonth);
      state.attendanceImportPreview = await api("/api/attendance/import/preview", {
        method: "POST", body: form
      });
      renderPayroll();
      showToast("Đã kiểm tra file chấm công · xem tóm tắt rồi xác nhận nhập");
    } catch (error) {
      state.attendanceImportPreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmAttendanceImport(button) {
    var preview = state.attendanceImportPreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi chấm công…";
      var result = await api("/api/attendance/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      state.attendanceImportPreview = null;
      if (result.month) state.opsMonth = result.month;
      await refreshOperations("Đã nạp " + result.attendance_entries + " ngày công, " +
        result.payroll_overrides + " khoản lương và " + result.labor_cost_entries + " dòng chi phí bếp");
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nạp chấm công";
      showToast(error.message, true);
    }
  }

  async function previewMappingFile(file) {
    if (!file || !state.mappingImportType) return;
    try {
      var form = new FormData();
      form.append("mapping_type", state.mappingImportType);
      form.append("file", file);
      state.mappingPreview = await api("/api/mappings/import/preview", { method: "POST", body: form });
      if (state.mappingImportType === "kitchen_units") renderKitchen();
      else renderSettings();
      showToast("Đã kiểm tra file · xem kỹ rồi xác nhận nhập");
    } catch (error) {
      state.mappingPreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmMappingImport(button) {
    var preview = state.mappingPreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi dữ liệu…";
      var result = await api("/api/mappings/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      var mappingType = preview.mapping_type;
      state.mappingPreview = null;
      state.mappingImportType = "";
      if (mappingType === "kitchen_units") {
        await refreshOperations("Đã nhập " + result.processed + " bếp → XCOM");
      } else {
        await loadData(state.batchId, true);
        showToast("Đã nhập " + result.processed + " tên xuất hóa đơn");
      }
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nhập dữ liệu";
      showToast(error.message, true);
    }
  }

  async function previewCatalogWorkbook(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("file", file);
      state.catalogImportPreview = await api("/api/catalog/import/preview", { method: "POST", body: form });
      renderSettings();
      showToast("Đã kiểm tra danh mục · xem kỹ rồi xác nhận cập nhật");
    } catch (error) {
      state.catalogImportPreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmCatalogImport(button) {
    var preview = state.catalogImportPreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang cập nhật danh mục…";
      var result = await api("/api/catalog/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      state.catalogImportPreview = null;
      await loadData(state.batchId, true);
      showToast("Đã cập nhật " + result.processed + " mã và tên xuất hóa đơn");
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận cập nhật danh mục";
      showToast(error.message, true);
    }
  }

  async function previewKitchenWorkbook(file) {
    if (!file) return;
    state.kitchenMealCountOverrides = {};
    try {
      var form = new FormData();
      form.append("work_date", state.opsDate);
      form.append("file", file);
      state.kitchenImportPreview = await api("/api/kitchen/import/preview", { method: "POST", body: form });
      renderKitchen();
      showToast("Đã kiểm tra file xưởng cơm · xem kỹ rồi xác nhận nhập");
    } catch (error) {
      state.kitchenImportPreview = null;
      state.kitchenMealCountOverrides = {};
      showToast(error.message, true);
    }
  }

  async function confirmKitchenImport(button) {
    var preview = state.kitchenImportPreview;
    if (!preview || !kitchenImportReady()) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi dữ liệu…";
      var result = await api("/api/kitchen/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: preview.token,
          confirmed: true,
          meal_count_overrides: state.kitchenMealCountOverrides
        })
      });
      state.kitchenImportPreview = null;
      state.kitchenMealCountOverrides = {};
      await refreshOperations("Đã nạp " + (result.inserted + result.updated) + " nhóm xưởng cơm và " + result.items + " nguyên liệu");
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nạp file xưởng cơm";
      showToast(error.message, true);
    }
  }

  async function previewMealAttendance(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("file", file);
      if (state.mealAttendancePeriodOverride) form.append("period", state.mealAttendancePeriodOverride);
      state.mealAttendancePreview = await api("/api/kitchen/attendance/import/preview", {
        method: "POST", body: form
      });
      renderKitchen();
      showToast("Đã kiểm tra file chấm suất ăn · xem kỹ rồi xác nhận nhập");
    } catch (error) {
      state.mealAttendancePreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmMealAttendance(button) {
    var preview = state.mealAttendancePreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi chấm suất…";
      var result = await api("/api/kitchen/attendance/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      state.mealAttendancePreview = null;
      if (result.periods.length) {
        state.opsMonth = result.periods[0];
        state.opsDate = result.periods[0] + "-01";
      }
      await refreshOperations("Đã nạp " + result.processed + " dòng chấm suất · thêm " +
        result.inserted + " · cập nhật " + result.updated + " · không đổi " + result.unchanged);
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nạp chấm suất";
      showToast(error.message, true);
    }
  }

  async function previewOpeningWorkbook(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("period", state.opsMonth);
      form.append("file", file);
      state.openingImportPreview = await api("/api/inventory/opening/import/preview", {
        method: "POST", body: form
      });
      renderInventory();
      showToast("Đã kiểm tra và gộp file tồn đầu kỳ · xem kỹ rồi xác nhận nhập");
    } catch (error) {
      state.openingImportPreview = null;
      showToast(error.message, true);
    }
  }

  async function previewBkWorkbook(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("file", file);
      state.bkImportPreview = await api("/api/bk-import/preview", {
        method: "POST", body: form
      });
      renderInventory();
      showToast("Đã kiểm tra file bảng kê · xem kỹ rồi xác nhận nhập kho");
    } catch (error) {
      state.bkImportPreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmBkImport(button) {
    var preview = state.bkImportPreview;
    if (!preview || !preview.canConfirm) return;
    if (!window.confirm(
      "Xác nhận cộng " + num(preview.totals && preview.totals.qty) +
      " đơn vị hàng trong bảng kê vào sổ kho?"
    )) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi bảng kê vào kho…";
      var result = await api("/api/bk-import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: preview.token, previewId: preview.previewId, confirmed: true
        })
      });
      state.bkImportPreview = null;
      await refreshOperations(
        result.idempotent
          ? "Bảng kê này đã có trong sổ · không cộng lặp"
          : "Đã nhập " + num(result.newInventoryLines) + " dòng bảng kê vào sổ kho"
      );
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nhập bảng kê vào kho";
      showToast(error.message, true);
    }
  }

  async function reverseBkImport(button) {
    var documentId = button.dataset.documentId;
    var reversalDateText = window.prompt("Ngày hoàn tác bảng kê (dd/mm/yyyy):", dateVN(state.opsDate || todayIso));
    if (reversalDateText === null) return;
    var reversalDate = parseLocalizedTemporal(reversalDateText, "date");
    if (!reversalDate) { showToast("Ngày hoàn tác bảng kê chưa đúng dạng dd/mm/yyyy", true); return; }
    var reason = window.prompt("Lý do hoàn tác bảng kê (bắt buộc):", "");
    if (reason === null || !reason.trim()) {
      showToast("Phải nhập lý do hoàn tác bảng kê", true);
      return;
    }
    if (!window.confirm("Hoàn tác bảng kê số " + documentId + "? Phần mềm sẽ kiểm tra để kho không bị âm.")) return;
    try {
      button.disabled = true;
      button.textContent = "Đang kiểm tra…";
      var result = await api("/api/bk-import/documents/" + encodeURIComponent(documentId) + "/reversal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirmed: true, reversalDate: reversalDate, reason: reason.trim()
        })
      });
      await refreshOperations(
        result.idempotent ? "Bảng kê này đã được hoàn tác trước đó" :
          "Đã hoàn tác " + num(result.newReversalLines) + " dòng bảng kê"
      );
    } catch (error) {
      button.disabled = false;
      button.textContent = "Hoàn tác bảng kê";
      showToast(error.message, true);
    }
  }

  async function confirmOpeningImport(button) {
    var preview = state.openingImportPreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi tồn đầu kỳ…";
      var result = await api("/api/inventory/opening/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      state.openingImportPreview = null;
      state.opsMonth = result.period;
      state.opsDate = result.period + "-01";
      await refreshOperations("Đã nạp " + result.processed + " mã tồn đầu kỳ · thêm " +
        result.inserted_products + " mã hàng mới");
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nạp tồn đầu kỳ";
      showToast(error.message, true);
    }
  }

  async function previewPayablesWorkbook(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("file", file);
      state.payablesImportPreview = await api("/api/debts/payables/import/preview", {
        method: "POST", body: form
      });
      renderDebts();
      showToast("Đã kiểm tra toàn bộ file công nợ phải trả · xem rồi xác nhận nhập");
    } catch (error) {
      state.payablesImportPreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmPayablesImport(button) {
    var preview = state.payablesImportPreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi công nợ…";
      var result = await api("/api/debts/payables/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      state.payablesImportPreview = null;
      invalidateDebtPeriod();
      invalidatePayableWorkspace(true);
      await Promise.all([fetchDebtPeriod(), fetchPayableWorkspace()]);
      showToast("Đã nạp " + result.inserted + " dòng công nợ phải trả · không cộng trùng file cũ");
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nạp công nợ phải trả";
      showToast(error.message, true);
    }
  }

  async function previewPurchaseOrderFile(file) {
    if (!file || !state.batchId) return;
    try {
      var form = new FormData();
      form.append("file", file);
      form.append("batch_id", state.batchId);
      state.purchaseOrderPreview = await api("/api/purchase-orders/import/preview", {
        method: "POST", body: form
      });
      renderPurchases();
      showToast("Đã kiểm tra file đặt nhà cung cấp · xem lại số lượng và giá rồi xác nhận");
    } catch (error) {
      state.purchaseOrderPreview = null;
      renderPurchases();
      showToast(error.message, true);
    }
  }

  async function confirmPurchaseOrderImport(button) {
    var preview = state.purchaseOrderPreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi đơn đặt nhà cung cấp…";
      var result = await api("/api/purchase-orders/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      state.purchaseOrderPreview = null;
      state.supplierNeeds = null;
      invalidateDebtPeriod();
      await loadData(state.batchId, true);
      await fetchSupplierNeeds();
      if (state.debtFrom && state.debtTo) await fetchDebtPeriod();
      var processed = result.processed == null ? (result.count == null ? "" : result.count) : result.processed;
      showToast("Đã nạp " + (processed === "" ? "file" : processed + " dòng") + " đặt nhà cung cấp · công nợ phải trả đã tính lại");
    } catch (error) {
      button.disabled = false;
      button.textContent = "Xác nhận nạp file đặt nhà cung cấp";
      showToast(error.message, true);
    }
  }

  async function jsonWrite(url, method, body, success) {
    try {
      var result = await api(url, { method: method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      var warnings = Array.isArray(result.warnings) ? result.warnings.filter(Boolean) : [];
      var message = success;
      if (warnings.length) message += " · Cần xử lý: " + warnings.join("; ");
      await refreshOperations(message);
    } catch (error) { showToast(error.message, true); }
  }

  document.getElementById("nav").addEventListener("click", function (event) {
    var button = event.target.closest("[data-view]");
    if (button) navigate(button.dataset.view);
  });
  document.getElementById("menuButton").addEventListener("click", function () {
    sidebar.classList.toggle("open");
  });
  batchSelect.addEventListener("change", function () {
    state.batchId = Number(batchSelect.value) || null;
    state.quoteItems = null;
    state.supplierNeeds = null;
    state.purchaseOrderPreview = null;
    state.operations = null;
    invalidateDebtPeriod();
    state.debtLoading = false;
    invalidateReceivableWorkspace(true);
    invalidatePayableWorkspace(true);
    state.outgoingInvoices = null;
    state.outgoingShortages = [];
    state.outgoingReadiness = null;
    state.outgoingReadinessLoading = false;
    state.outgoingSubstitutionActions = null;
    state.outgoingSubstitutionLoading = false;
    state.outgoingSubstitutionPreview = null;
    state.outgoingSubstitutionRequest = null;
    state.outgoingSubstitutionDraft = null;
    state.invoicePaymentScope = null;
    state.outgoingPeriodShortages = null;
    state.outgoingShortageLoading = false;
    loadData(state.batchId);
  });
  excelInput.addEventListener("change", function () {
    var file = excelInput.files[0];
    excelInput.value = "";
    importExcel(file);
  });
  attendanceInput.addEventListener("change", function () {
    var file = attendanceInput.files[0];
    attendanceInput.value = "";
    importAttendance(file);
  });
  mappingFileInput.addEventListener("change", function () {
    var file = mappingFileInput.files[0];
    mappingFileInput.value = "";
    previewMappingFile(file);
  });
  catalogWorkbookInput.addEventListener("change", function () {
    var file = catalogWorkbookInput.files[0];
    catalogWorkbookInput.value = "";
    previewCatalogWorkbook(file);
  });
  kitchenWorkbookInput.addEventListener("change", function () {
    var file = kitchenWorkbookInput.files[0];
    kitchenWorkbookInput.value = "";
    previewKitchenWorkbook(file);
  });
  mealAttendanceInput.addEventListener("change", function () {
    var file = mealAttendanceInput.files[0];
    mealAttendanceInput.value = "";
    previewMealAttendance(file);
  });
  openingWorkbookInput.addEventListener("change", function () {
    var file = openingWorkbookInput.files[0];
    openingWorkbookInput.value = "";
    previewOpeningWorkbook(file);
  });
  bkWorkbookInput.addEventListener("change", function () {
    var file = bkWorkbookInput.files[0];
    bkWorkbookInput.value = "";
    previewBkWorkbook(file);
  });
  payablesWorkbookInput.addEventListener("change", function () {
    var file = payablesWorkbookInput.files[0];
    payablesWorkbookInput.value = "";
    previewPayablesWorkbook(file);
  });
  purchaseOrderInput.addEventListener("change", function () {
    var file = purchaseOrderInput.files[0];
    purchaseOrderInput.value = "";
    previewPurchaseOrderFile(file);
  });
  quoteWorkbookInput.addEventListener("change", function () {
    var file = quoteWorkbookInput.files[0];
    quoteWorkbookInput.value = "";
    previewQuoteWorkbook(file);
  });
  orderForm.addEventListener("submit", saveOrder);
  backdrop.addEventListener("click", function (event) {
    if (event.target === backdrop) closeModal();
  });

  content.addEventListener("submit", async function (event) {
    if (event.target.id === 'physicalFilterForm') {
      event.preventDefault();
      var filters = new FormData(event.target);
      state.physicalSearch = filters.get('search') || '';
      state.physicalStatus = filters.get('status') || 'all';
      state.physicalEntry = null;
      await loadPhysicalStock();
      return;
    }
    if (event.target.id === 'physicalStockForm') {
      event.preventDefault();
      var entry = state.physicalEntry;
      if (!entry || !window.confirm('Lưu thay đổi này vào kho thực tế? Kho hóa đơn không thay đổi.')) return;
      var physicalBody = Object.fromEntries(new FormData(event.target).entries());
      physicalBody.product_code = entry.item.product_code;
      physicalBody.revision = entry.item.opening ? entry.item.opening.id : 0;
      physicalBody.request_key = entry.requestKey;
      try {
        if (event.submitter) event.submitter.disabled = true;
        await api('/api/physical-stock/' + entry.kind, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(physicalBody) });
        state.physicalEntry = null;
        await loadPhysicalStock();
        showToast('Đã lưu kho thực tế');
      } catch (error) { showToast(error.message, true); if (event.submitter) event.submitter.disabled = false; }
      return;
    }
    if (event.target.id === "outgoingSubstitutionForm") {
      event.preventDefault();
      var substitutionBody = outgoingSubstitutionFormBody(event.target);
      state.outgoingSubstitutionDraft = substitutionBody;
      if (!substitutionBody.order_id || !substitutionBody.substitute_product_code ||
          !Number.isFinite(substitutionBody.qty) || substitutionBody.qty <= 0 ||
          !substitutionBody.actor || !substitutionBody.reason) {
        showToast("Cần chọn dòng thiếu, nhập mã, số lượng, người xác nhận và lý do", true);
        return;
      }
      state.outgoingSubstitutionLoading = true;
      state.outgoingSubstitutionPreview = null;
      try {
        var substitutionPreview = await api("/api/outgoing-substitutions/preview", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(substitutionBody)
        });
        state.outgoingSubstitutionRequest = substitutionBody;
        state.outgoingSubstitutionPreview = substitutionPreview;
        showToast(substitutionPreview.can_confirm
          ? "Đã kiểm tra tồn và giá · cần xác nhận lần cuối"
          : "Chưa đủ điều kiện xác nhận · xem cảnh báo bên dưới", !substitutionPreview.can_confirm);
      } catch (error) {
        state.outgoingSubstitutionRequest = null;
        state.outgoingSubstitutionPreview = { error: error.message };
        showToast(error.message, true);
      } finally {
        state.outgoingSubstitutionLoading = false;
        renderDocuments();
      }
      return;
    }
    if (event.target.classList.contains("minvoiceDraftForm")) {
      event.preventDefault();
      var minvoiceForm = event.target;
      var minvoiceBody = Object.fromEntries(new FormData(minvoiceForm).entries());
      var minvoiceAction = event.submitter && event.submitter.value === "save" ? "save" : "dry";
      var contractor = minvoiceForm.dataset.contractor;
      var draftId = minvoiceForm.dataset.id;
      if (minvoiceAction === "save" && !window.confirm(
        "Lưu bản nháp này lên M-Invoice ở trạng thái chờ ký? Hệ thống sẽ không ký hoặc phát hành."
      )) return;
      try {
        if (event.submitter) event.submitter.disabled = true;
        await api("/api/outgoing-buyers/" + encodeURIComponent(contractor), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            display_name: minvoiceBody.display_name,
            legal_name: minvoiceBody.legal_name,
            tax_code: minvoiceBody.tax_code,
            address: minvoiceBody.address,
            email: minvoiceBody.email
          })
        });
        var minvoiceResult = await api("/api/minvoice/drafts/" + draftId, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            series: minvoiceBody.series,
            dry_run: minvoiceAction !== "save",
            confirm_remote_write: minvoiceAction === "save"
          })
        });
        state.outgoingInvoices = null;
        state.outgoingSubstitutionActions = null;
        await Promise.all([fetchOutgoingInvoices(), fetchOutgoingSubstitutions()]);
        if (minvoiceAction === "save") {
          showToast("Đã lưu nháp M-Invoice · vẫn chưa ký/phát hành");
        } else {
          var previewInvoice = minvoiceResult.payload && minvoiceResult.payload.data && minvoiceResult.payload.data[0];
          showToast("Dữ liệu M-Invoice hợp lệ · tổng " + money(previewInvoice ? previewInvoice.inv_TotalAmount : 0));
        }
      } catch (error) {
        if (event.submitter) event.submitter.disabled = false;
        showToast(error.message, true);
      }
    }
    if (event.target.id === "debtPeriodForm") {
      event.preventDefault();
      var debtRange = Object.fromEntries(new FormData(event.target).entries());
      state.receivableOffset = 0; state.payableOffset = 0; state.payableHistoryOffset = 0;
      state.debtFrom = debtRange.from;
      state.debtTo = debtRange.to;
      if (Object.prototype.hasOwnProperty.call(debtRange, "supplier")) {
        state.payableSupplier = debtRange.supplier || "";
      }
      if (Object.prototype.hasOwnProperty.call(debtRange, "status")) {
        state.payableStatus = debtRange.status || "outstanding";
      }
      state.payableSelected = {};
      persistPayableFilters();
      persistReceivableFilters();
      invalidateDebtPeriod();
      invalidateReceivableWorkspace(true);
      invalidatePayableWorkspace(true);
      var debtLoaders = [fetchDebtPeriod()];
      if (state.debtSection === "receivable-kitchen") debtLoaders.push(fetchReceivableWorkspace());
      if (state.debtSection === "payable") debtLoaders.push(fetchPayableWorkspace());
      await Promise.all(debtLoaders);
    }
    if (event.target.id === "receivableFilterForm") {
      event.preventDefault();
      var receivableFilter = Object.fromEntries(new FormData(event.target).entries());
      state.receivableOffset = 0;
      var selectedKitchen = receivableFilter.kitchen || "";
      var kitchenMeta = (state.data.master.kitchens || []).find(function (item) {
        return item.code === selectedKitchen;
      });
      state.receivableContractor = receivableFilter.contractor || "";
      state.receivableKitchen = state.receivableContractor && kitchenMeta &&
        kitchenMeta.contractor !== state.receivableContractor ? "" : selectedKitchen;
      state.receivableStatus = receivableFilter.status || "active";
      persistReceivableFilters();
      invalidateReceivableWorkspace(true);
      await fetchReceivableWorkspace();
    }
    if (event.target.id === "debtAdjustmentForm") {
      event.preventDefault();
      var debtAdjustment = Object.fromEntries(new FormData(event.target).entries());
      debtAdjustment.amount = n(debtAdjustment.amount);
      try {
        await api("/api/debt-adjustments", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(debtAdjustment)
        });
    invalidateDebtPeriod();
        await loadData(state.batchId, true);
        showToast("Đã lưu điều chỉnh công nợ");
      } catch (error) { showToast(error.message, true); }
    }
    if (event.target.id === "receiptForm") {
      event.preventDefault();
      savePayment(event.target);
    }
    if (event.target.id === "payablePaymentForm") {
      event.preventDefault();
      await savePayablePayment(event.target, event.submitter);
    }
    if (event.target.id === "balanceForm") {
      event.preventDefault();
      saveBalance(event.target);
    }
    if (event.target.id === "openingForm") {
      event.preventDefault();
      var opening = Object.fromEntries(new FormData(event.target).entries());
      state.opsMonth = opening.period;
      state.opsDate = opening.period + '-01';
      jsonWrite("/api/inventory/opening", "POST", { period: opening.period, items: [{
        product_code: opening.product_code, qty: n(opening.qty), unit_cost: n(opening.unit_cost)
      }] }, "Đã lưu tồn đầu kỳ");
    }
    if (event.target.id === "inventoryAdjustmentForm") {
      event.preventDefault();
      var adjustment = Object.fromEntries(new FormData(event.target).entries());
      adjustment.qty = n(adjustment.qty);
      jsonWrite("/api/inventory/adjustments", "POST", adjustment, "Đã ghi điều chỉnh kho");
    }
    if (event.target.id === "kitchenUnitForm") {
      event.preventDefault();
      var unit = Object.fromEntries(new FormData(event.target).entries());
      jsonWrite("/api/kitchen-units/" + encodeURIComponent(unit.kitchen_code), "PUT", { xcom_code: unit.unit_code }, "Đã ghép bếp vào XCOM");
    }
    if (event.target.id === "xcomPaymentProfileForm") {
      event.preventDefault();
      var xcomProfile = Object.fromEntries(new FormData(event.target).entries());
      xcomProfile.vat_rate = n(xcomProfile.vat_rate);
      state.xcomPaymentPreview = null;
      state.xcomPaymentRequest = null;
      await jsonWrite(
        "/api/kitchen/payment-profiles/" + encodeURIComponent(xcomProfile.profile_code),
        "PUT", xcomProfile, "Đã lưu hồ sơ thanh toán suất ăn"
      );
    }
    if (event.target.id === "xcomPaymentScopeForm") {
      event.preventDefault();
      var xcomScope = Object.fromEntries(new FormData(event.target).entries());
      state.xcomPaymentPreview = null;
      state.xcomPaymentRequest = null;
      await jsonWrite(
        "/api/kitchen/payment-profiles/" + encodeURIComponent(xcomScope.profile_code) +
        "/scopes/" + encodeURIComponent(xcomScope.scope_type) + "/" + encodeURIComponent(xcomScope.scope_code),
        "PUT", {}, "Đã gán bếp/XCOM vào hồ sơ thanh toán"
      );
    }
    if (event.target.id === "xcomMealTariffForm") {
      event.preventDefault();
      var xcomTariff = Object.fromEntries(new FormData(event.target).entries());
      state.xcomPaymentPreview = null;
      state.xcomPaymentRequest = null;
      await jsonWrite(
        "/api/kitchen/payment-profiles/" + encodeURIComponent(xcomTariff.profile_code) +
        "/tariffs/" + encodeURIComponent(xcomTariff.period) + "/" + encodeURIComponent(xcomTariff.shift),
        "PUT", { unit_price: n(xcomTariff.unit_price) }, "Đã lưu đơn giá suất ăn đúng kỳ"
      );
    }
    if (event.target.id === "xcomPaymentDocumentForm") {
      event.preventDefault();
      var xcomDocument = Object.fromEntries(new FormData(event.target).entries());
      var checkedPayment = state.xcomPaymentPreview;
      var checkedSummary = checkedPayment && checkedPayment.summary;
      if (!checkedPayment || !checkedPayment.preview_token || !checkedSummary ||
          checkedSummary.profile_code !== xcomDocument.profile_code ||
          checkedSummary.date_from !== xcomDocument.date_from ||
          checkedSummary.date_to !== xcomDocument.date_to ||
          checkedPayment.issue_date !== xcomDocument.issue_date) {
        showToast("Cần bấm Kiểm tra số liệu trước khi tải chứng từ", true);
        return;
      }
      try {
        await downloadFile("/api/kitchen/payment-documents/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            profile_code: xcomDocument.profile_code,
            date_from: xcomDocument.date_from,
            date_to: xcomDocument.date_to,
            issue_date: xcomDocument.issue_date,
            preview_token: checkedPayment.preview_token
          })
        });
        state.xcomPaymentPreview = null;
        state.xcomPaymentRequest = null;
        showToast("Đã tải chứng từ từ số liệu vừa kiểm tra");
        renderKitchen();
      } catch (error) {
        state.xcomPaymentPreview = null;
        state.xcomPaymentRequest = null;
        showToast(error.message, true);
      }
    }
    if (event.target.id === "mealPlanForm") {
      event.preventDefault();
      var plan = Object.fromEntries(new FormData(event.target).entries());
      plan.meal_count = n(plan.meal_count);
      plan.menu_count = n(plan.menu_count) || 1;
      plan.servings_per_menu = n(plan.servings_per_menu);
      plan.meal_price = n(plan.meal_price);
      plan.other_cost = n(plan.other_cost);
      var itemLines = String(plan.items || "").split(/\r?\n/).filter(function (line) { return line.trim(); });
      var invalidLine = itemLines.findIndex(function (line) {
        var cells = line.split("\t");
        return cells.length < 2 || !cells[0].trim() || n(cells[1]) <= 0;
      });
      if (!itemLines.length) {
        showToast("Cần dán ít nhất một dòng nguyên liệu từ Excel", true);
        return;
      }
      if (invalidLine >= 0) {
        showToast("Dòng nguyên liệu " + (invalidLine + 1) + " chưa đúng. Hãy sao chép các cột trong Excel rồi dán lại", true);
        return;
      }
      plan.items = itemLines.map(function (line) {
        var cells = line.split("\t");
        return { product_code: cells[0] || "", norm_qty: n(cells[1]), dish_name: cells[2] || "",
          unit: cells[3] || "", supplier: cells[4] || "" };
      });
      state.opsDate = plan.work_date;
      jsonWrite("/api/kitchen/plans", "POST", plan, "Đã lưu kế hoạch và tính chi phí");
    }
    if (event.target.id === "datedPriceForm") {
      event.preventDefault();
      var datedPrice = Object.fromEntries(new FormData(event.target).entries());
      datedPrice.price_value = n(datedPrice.price_value);
      datedPrice.price_group = "HATRAN";
      state.opsMonth = datedPrice.period;
      jsonWrite("/api/dated-prices/" + encodeURIComponent(datedPrice.product_code), "PUT", datedPrice, "Đã khóa giá HATRAN theo kỳ");
    }
    if (event.target.id === "staffForm") {
      event.preventDefault();
      var staff = Object.fromEntries(new FormData(event.target).entries());
      staff.base_salary = n(staff.base_salary);
      staff.standard_days = n(staff.standard_days) || 26;
      staff.standard_hours = n(staff.standard_hours) || 8;
      staff.bhxh_employee_rate = n(staff.bhxh_employee_rate);
      staff.bhxh_company_rate = n(staff.bhxh_company_rate);
      jsonWrite("/api/staff", "POST", staff, "Đã lưu nhân sự");
    }
    if (event.target.id === "attendanceForm") {
      event.preventDefault();
      var attendance = Object.fromEntries(new FormData(event.target).entries());
      ["normal_hours", "overtime_hours", "sunday_hours", "night_hours", "holiday_hours"].forEach(function (key) {
        attendance[key] = n(attendance[key]);
      });
      state.opsDate = attendance.work_date;
      state.opsMonth = state.opsDate.slice(0, 7);
      jsonWrite("/api/attendance", "POST", attendance, "Đã lưu chấm công trong ngày");
    }
    if (event.target.id === "payrollAdjustmentForm") {
      event.preventDefault();
      var payrollAdjustment = Object.fromEntries(new FormData(event.target).entries());
      ["allowance", "responsibility", "advance", "probation_deduction", "bhxh_employee_amount",
        "bhxh_company_amount", "gross_override", "net_override"].forEach(function (key) {
        payrollAdjustment[key] = n(payrollAdjustment[key]);
      });
      payrollAdjustment.use_override = new FormData(event.target).has("use_override");
      state.opsMonth = payrollAdjustment.month;
      jsonWrite("/api/payroll-adjustments/" + encodeURIComponent(payrollAdjustment.employee_code) + "/" +
        encodeURIComponent(payrollAdjustment.month), "PUT", payrollAdjustment, "Đã lưu khoản lương tháng");
    }
    if (event.target.id === "printSettingsForm") {
      event.preventDefault();
      var printSettings = Object.fromEntries(new FormData(event.target).entries());
      printSettings.copies = n(printSettings.copies);
      jsonWrite("/api/print/settings", "PUT", printSettings, "Đã lưu cấu hình in");
    }
    if (event.target.id === "buyerProfileForm") {
      event.preventDefault();
      var buyerContractor = event.target.dataset.contractor;
      var buyerBody = Object.fromEntries(new FormData(event.target).entries());
      try {
        await api('/api/outgoing-buyers/' + encodeURIComponent(buyerContractor), {
          method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(buyerBody)
        });
        state.invoicePaymentScope = null;
        if (state.buyerEdits) delete state.buyerEdits[buyerContractor];
        await fetchOutgoingInvoices();
        showToast('Đã lưu hồ sơ người mua');
      } catch (error) { showToast(error.message, true); }
    }
    if (event.target.id === "orderInvoiceExportForm") {
      event.preventDefault();
      var selectedOrderScope = Object.fromEntries(new FormData(event.target).entries());
      state.orderInvoiceFilters = selectedOrderScope;
      var orderExportButton = event.submitter || event.target.querySelector('button[type=submit]');
      orderExportButton.disabled = true;
      orderExportButton.textContent = 'Đang kiểm tra tồn và tạo file…';
      try {
        if(event.submitter && event.submitter.value==='sync') {
          orderExportButton.textContent='Đang cập nhật hóa đơn đã ký…';
          var syncedSource=await api('/api/outgoing-invoices/sync-issued',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selectedOrderScope)});
          state.outgoingSourceReview=syncedSource.sources;
          state.orderInvoiceExportResult='Đã cập nhật hóa đơn ký đến '+dateVN(syncedSource.to)+'. '+(syncedSource.waiting.warnings.length?'Còn hóa đơn cần đối chiếu bên dưới; chưa xuất lại phần cũ.':'Đã đối chiếu phần đã phát hành với đơn đã duyệt.');
          state.unissuedFilters={to:selectedOrderScope.to,contractor:selectedOrderScope.contractor==='*'?'':selectedOrderScope.contractor};
          state.unissued=await api('/api/outgoing-invoices/unissued?'+new URLSearchParams(state.unissuedFilters).toString());
          return;
        }
        var exported = await downloadFile('/api/export/order-invoices', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(selectedOrderScope)});
        state.orderInvoiceExportResult = 'Đã tải '+exported.invoiceFiles+' file Excel để up M-Invoice. '+(exported.pendingLines ? 'Còn '+exported.pendingLines+' dòng chưa phân bổ vào file này.' : 'Đã phân bổ lượng được chọn vào file.')+' Tải file chưa tính là đã xuất; xem bảng chưa xuất cộng dồn bên dưới.';
        showToast('Đã tải bảng kê từ đơn hàng để up M-Invoice');
        state.outgoingInvoices = null; state.outgoingReadiness = null; state.outgoingPeriodShortages = null;
        await Promise.all([fetchOutgoingInvoices(),fetchOutgoingReadiness()]);
        if(state.unissued && state.unissuedFilters) {
          state.unissued=await api('/api/outgoing-invoices/unissued?'+new URLSearchParams(state.unissuedFilters).toString());
        }
      } catch(error) {
        state.orderInvoiceExportResult = error.message;
        try {state.outgoingSourceReview=(await api('/api/outgoing-invoices/source-scopes?from='+encodeURIComponent(selectedOrderScope.from)+'&to='+encodeURIComponent(currentWorkDate()))).items;} catch(_) {}
        showToast(error.message,true);
      } finally { renderDocuments(); }
      return;
    }
    if(event.target.classList.contains('source-order-scope')) {
      event.preventDefault();
      var sourceForm=event.target,choice=new FormData(sourceForm).get('choice');
      var scopeButton=event.submitter;scopeButton.disabled=true;
      try {
        await api('/api/outgoing-invoices/source-scopes/'+sourceForm.dataset.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:sourceForm.dataset.token,scope:choice==='outside'?'outside':'orders',contractor:choice==='outside'?'':choice,note:new FormData(sourceForm).get('note')})});
        var sourceDates=state.orderInvoiceFilters;
        state.outgoingSourceReview=(await api('/api/outgoing-invoices/source-scopes?from='+encodeURIComponent(sourceDates.from)+'&to='+encodeURIComponent(currentWorkDate()))).items;
        state.unissuedFilters={to:sourceDates.to,contractor:sourceDates.contractor==='*'?'':sourceDates.contractor};
        state.unissued=await api('/api/outgoing-invoices/unissued/refresh?'+new URLSearchParams(state.unissuedFilters).toString(),{method:'POST'});
        showToast('Đã lưu phạm vi đối chiếu hóa đơn');
      } catch(error) {showToast(error.message,true);} finally {renderDocuments();}
      return;
    }
    if (event.target.id === 'unissuedForm') {
      event.preventDefault();
      var f=Object.fromEntries(new FormData(event.target).entries());state.unissuedFilters=f;
      var params='?to='+encodeURIComponent(f.to)+'&contractor='+encodeURIComponent(f.contractor);
      try {
        state.unissuedError='';
        state.unissued=await api('/api/outgoing-invoices/unissued/refresh'+params,{method:'POST'});
        if(event.submitter && event.submitter.value==='excel') await downloadFile('/api/outgoing-invoices/unissued.xlsx'+params);
      } catch(error) {state.unissuedError=error.message;showToast(error.message,true);}
      renderDocuments();return;
    }
    if (event.target.id === "paymentRequestForm") {
      event.preventDefault();
      var paymentRequest = Object.fromEntries(new FormData(event.target).entries());
      state.paymentFilters = paymentRequest;
      var from = paymentRequest.from;
      var paymentButton = event.submitter || event.target.querySelector('button[type="submit"]');
      var paymentLabel = paymentButton ? paymentButton.textContent : "";
      try {
        if (!paymentRequest.contractor) throw new Error("Chưa có hóa đơn đã phát hành trong kỳ này");
        if (paymentButton) {
          paymentButton.disabled = true;
          paymentButton.textContent = "Đang đối chiếu hóa đơn…";
        }
        state.invoicePaymentScope = await api(
          "/api/outgoing-invoices/payment-scope/" + encodeURIComponent(paymentRequest.contractor) +
          "?from=" + encodeURIComponent(from) + "&to=" + encodeURIComponent(paymentRequest.to)
        );
        renderDocuments();
        showToast("Đã đối chiếu phạm vi hóa đơn đỏ · sẵn sàng tải hồ sơ chính thức");
      } catch (error) {
        state.invoicePaymentScope = { error: error.message };
        renderDocuments();
        showToast(error.message, true);
      } finally {
        if (paymentButton) {
          paymentButton.disabled = false;
          paymentButton.textContent = paymentLabel;
        }
      }
    }
    if (event.target.id === "documentSettingsForm") {
      event.preventDefault();
      var documentSettings = Object.fromEntries(new FormData(event.target).entries());
      try {
        await api("/api/document-settings", {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(documentSettings)
        });
        await loadData(state.batchId, true);
        showToast("Đã lưu thông tin đề nghị thanh toán");
      } catch (error) { showToast(error.message, true); }
    }
    if (event.target.id === "catalogSearchForm") {
      event.preventDefault();
      state.catalogQuery = new FormData(event.target).get('q').trim(); state.catalogOffset = 0;
      await loadCatalogProducts();
    }

  });

  content.addEventListener("input", function (event) {
    if (event.target.form && event.target.form.id === 'orderInvoiceExportForm') state.orderInvoiceFilters=Object.fromEntries(new FormData(event.target.form).entries());
    if (event.target.form && event.target.form.id === 'unissuedForm') state.unissuedFilters=Object.fromEntries(new FormData(event.target.form).entries());
    if (event.target.matches('.unit-conversion-input, .invoice-draft-factor')) {
      var editingCell = event.target.closest('.invoice-mapping-cell');
      if (!editingCell.mappingExpected) editingCell.mappingExpected = invoiceMappingExpected(event.target.dataset.id);
      editingCell.dataset.editingId = event.target.dataset.id;
      if (event.target.matches('.invoice-draft-factor')) {
        event.target.dataset.userEntered = 'true';
        event.target.dataset.factorProduct = event.target.dataset.productCode || '';
      }
      var previewLine = invoiceEditingLine(event.target.dataset.id);
      var previewBox = event.target.closest('.invoice-mapping-cell')?.querySelector('.invoice-conversion-preview');
      var previewFactor = Number(event.target.value.replace(',', '.'));
      if (previewLine && previewBox) previewBox.textContent = Number.isFinite(previewFactor) && previewFactor > 0 && previewFactor <= 1000000000
        ? event.target.matches('.invoice-draft-factor') && !event.target.dataset.productCode
          ? 'Đã nhập hệ số. Chọn mã hàng để kiểm tra đơn vị kho trước khi Lưu.'
          : stockQty(previewLine.qty) + ' ' + previewLine.source_unit + ' → ' + stockQty(previewLine.qty * previewFactor) + ' ' + (event.target.dataset.unit || previewLine.product_unit)
        : 'Nhập hệ số lớn hơn 0 trong giới hạn cho phép';
      if (previewBox) event.target.title = previewBox.textContent + '. Esc để bỏ sửa.';
      return;
    }

    if (event.target.form && event.target.form.id === 'buyerProfileForm') {
      state.buyerEdits = state.buyerEdits || {};
      state.buyerEdits[event.target.form.dataset.contractor] = Object.fromEntries(new FormData(event.target.form).entries());
      return;
    }
    if (event.target.form && event.target.form.id === 'paymentRequestForm') {
      state.paymentFilters = Object.fromEntries(new FormData(event.target.form).entries());
    }
    if (event.target.closest && event.target.closest("#outgoingSubstitutionForm")) {
      state.outgoingSubstitutionDraft = outgoingSubstitutionFormBody(event.target.form);
      if (state.outgoingSubstitutionPreview && !sameOutgoingSubstitutionRequest(
          state.outgoingSubstitutionDraft, state.outgoingSubstitutionRequest)) {
        var staleNotice = document.getElementById("outgoingSubstitutionStale");
        var substitutionConfirm = content.querySelector('[data-action="confirm-outgoing-substitution"]');
        if (staleNotice) staleNotice.hidden = false;
        if (substitutionConfirm) substitutionConfirm.disabled = true;
      }
      return;
    }
    if (event.target.matches(".payable-allocation-input")) {
      var selectedLine = state.payableSelected[event.target.dataset.id];
      if (selectedLine) selectedLine.amount = event.target.value;
      updatePayableSelectionSummary();
      return;
    }
    if (event.target.id === "orderSearch") {
      state.orderFilter = event.target.value;
      applyOrderFilter();
    }
    if (event.target.matches("[data-kitchen-meal-override]")) {
      var planKey = event.target.dataset.kitchenMealOverride;
      state.kitchenMealCountOverrides[planKey] = event.target.value;
      var confirmButton = content.querySelector('[data-action="confirm-kitchen-import"]');
      if (confirmButton) confirmButton.disabled = !kitchenImportReady();
    }
    if (event.target.closest && event.target.closest("#xcomPaymentDocumentForm") && state.xcomPaymentPreview) {
      state.xcomPaymentPreview = null;
      var paymentDownload = event.target.form && event.target.form.querySelector('button[type="submit"]');
      if (paymentDownload) paymentDownload.disabled = true;
    }
  });

  content.addEventListener("change", function (event) {
    if (event.target.form && event.target.form.id === 'orderInvoiceExportForm') state.orderInvoiceFilters=Object.fromEntries(new FormData(event.target.form).entries());
    if (event.target.form && event.target.form.id === 'unissuedForm') state.unissuedFilters=Object.fromEntries(new FormData(event.target.form).entries());
    if (event.target.matches('.invoice-group-select')) {
      var checked = invoiceCheckedRows();
      if (checked.some(function(e) { return e.dataset.invoiceId !== event.target.dataset.invoiceId; })) {
        event.target.checked = false; showToast('Chỉ chọn các dòng trong cùng một hóa đơn để gộp.', true); return;
      }
      var selectedGroups = checked.length;
      var groupButton = content.querySelector('[data-action="preview-invoice-group"]');
      if (groupButton) { groupButton.disabled = selectedGroups < 2; groupButton.textContent = 'Gộp ' + selectedGroups + ' dòng đã chọn'; }
      return;
    }
    if (event.target.form && event.target.form.id === 'buyerProfileForm') {
      state.buyerEdits = state.buyerEdits || {};
      state.buyerEdits[event.target.form.dataset.contractor] = Object.fromEntries(new FormData(event.target.form).entries());
      return;
    }
    if (event.target.form && event.target.form.id === 'paymentRequestForm') {
      state.paymentFilters = Object.fromEntries(new FormData(event.target.form).entries());
      state.invoicePaymentScope = null;
      renderDocuments();
      return;
    }
    if (event.target.id === 'orderIssueFilter') { state.orderIssueFilter = event.target.value; applyOrderFilter(); }
    if (event.target.id === "homeFrom" || event.target.id === "homeTo") {
      if (event.target.id === "homeFrom") state.homeFrom = event.target.value;
      if (event.target.id === "homeTo") state.homeTo = event.target.value;
      if (!state.homeFrom || !state.homeTo || state.homeFrom > state.homeTo) {
        showToast("Từ ngày phải nhỏ hơn hoặc bằng Đến ngày", true);
        return;
      }
      renderHome();
      return;
    }
    if (event.target.id === "printingCustomer") { state.printingCustomer = event.target.value; renderPrinting(); return; }
    if (event.target.id === "printingFrom" || event.target.id === "printingTo") {
      if (event.target.id === "printingFrom") state.printingFrom = event.target.value;
      if (event.target.id === "printingTo") state.printingTo = event.target.value;
      if (!state.printingFrom || !state.printingTo || state.printingFrom > state.printingTo) {
        showToast("Từ ngày phải nhỏ hơn hoặc bằng Đến ngày", true);
        return;
      }
      state.printingRangeKey = "";
      renderPrinting();
      return;
    }
    if (event.target.matches(".print-document-choice")) {
      state.printingDocument = event.target.value;
      renderPrinting();
      return;
    }
    if (event.target.matches(".print-batch-select")) {
      state.printingSelected[event.target.dataset.id] = event.target.checked;
      renderPrinting();
      return;
    }
    if (event.target.id === "receivableContractor") {
      // Stage the filters until “Lọc danh sách”. A background reload here
      // used to erase a kitchen selection made while its response arrived.
      var requestedContractor = event.target.value || "";
      var kitchenSelect = document.getElementById("receivableKitchen");
      if (kitchenSelect) kitchenSelect.innerHTML = '<option value="">Tất cả bếp</option>' +
        (state.data.master.kitchens || []).filter(function (item) {
          return !requestedContractor || item.contractor === requestedContractor;
        }).map(function (item) {
          return '<option value="' + esc(item.code) + '">' + esc(item.code) + ' · ' + esc(item.name || item.code) + '</option>';
        }).join("");
      return;
    }
    if (event.target.matches(".payable-line-select")) {
      var payableId = event.target.dataset.id;
      if (event.target.checked) {
        state.payableSelected[payableId] = {
          supplier: event.target.dataset.supplier,
          revision: Number(event.target.dataset.revision),
          remaining: Number(event.target.dataset.remaining),
          amount: ""
        };
      } else {
        delete state.payableSelected[payableId];
      }
      renderDebts();
      if (event.target.checked) {
        var allocationInput = content.querySelector('.payable-allocation-input[data-id="' + payableId + '"]');
        if (allocationInput) allocationInput.focus();
      }
      return;
    }
    if (["invoiceFrom", "invoiceTo", "invoiceStatus", "invoiceLineFilter"].indexOf(event.target.id) >= 0) {
      if (event.target.id === "invoiceFrom") { state.invoiceFrom = event.target.value; state.invoicePending = false; state.legacyInvoiceMappingPreview = null; }
      if (event.target.id === "invoiceTo") { state.invoiceTo = event.target.value; state.invoicePending = false; state.legacyInvoiceMappingPreview = null; }
      if (event.target.id === "invoiceStatus") {
        state.invoiceStatus = event.target.value;
        if (['posted','reversed','not_inventory'].includes(state.invoiceStatus)) state.invoicePending = false;
      }
      if (event.target.id === "invoiceLineFilter") state.invoiceLineFilter = event.target.value;
      persistInvoiceWorkbenchFilters();
      state.invoiceWorkbench = null;
      loadInvoiceWorkbench();
      return;
    }
    if (event.target.id === "quoteContractor") {
      state.quoteContractor = event.target.value;
      state.quoteItems = null;
      state.quoteMeta = null;
      renderQuotes();
      return;
    }
    if (event.target.id === "quotePeriod") {
      state.quotePeriod = event.target.value || todayIso.slice(0, 7);
      state.quoteImportPreview = null;
      state.quoteItems = null;
      state.quoteMeta = null;
      state.quoteVersions = null;
      renderQuotes();
      return;
    }
    if (event.target.id === "reportPeriod") {
      state.reportPeriod = event.target.value || todayIso.slice(0, 7);
      fetchMonthlyReport();
      return;
    }
    if (event.target.id === "inventoryFrom" || event.target.id === "inventoryTo") {
      if (event.target.id === "inventoryFrom") state.inventoryFrom = event.target.value;
      if (event.target.id === "inventoryTo") state.inventoryTo = event.target.value;
      ++inventoryPreviewSerial;
      renderInventory();
      return;
    }
    if (event.target.id === "kitchenDate") {
      state.opsDate = event.target.value;
      state.opsMonth = state.opsDate.slice(0, 7);
      state.kitchenImportPreview = null;
      state.kitchenMealCountOverrides = {};
      state.mealAttendancePreview = null;
      state.xcomPaymentPreview = null;
      state.xcomPaymentRequest = null;
      state.operations = null;
      loadOperations();
    }
    if (event.target.id === "payrollMonth") {
      state.opsMonth = event.target.value;
      state.attendanceImportPreview = null;
      state.operations = null;
      loadOperations();
    }
    if (event.target.id === "mealAttendancePeriod") {
      state.mealAttendancePeriodOverride = event.target.value;
      state.mealAttendancePreview = null;
    }
  });

  content.addEventListener("focusin", function (event) {
    var input = event.target.closest(".invoice-mapping-input");
    if (input) {
      closeMsmiProductOptions();
      loadMsmiProductOptions(input);
    }
  });

  content.addEventListener("pointerdown", function (event) {
    if (event.target.closest('#msmiProductOptions [data-product-code]')) event.preventDefault();
  });
  content.addEventListener("focusout", function (event) {
    if (event.target.closest('.invoice-mapping-input')) closeMsmiProductOptions();
  });
  content.addEventListener("click", function (event) {
    var option = event.target.closest('#msmiProductOptions [data-product-code]');
    if (option) chooseMsmiProductOption(option);
  });
  document.addEventListener("scroll", function (event) {
    var list = document.getElementById("msmiProductOptions");
    if (list && !list.hidden && !list.contains(event.target)) closeMsmiProductOptions();
  }, true);
  window.addEventListener("resize", function () {
    var list = document.getElementById("msmiProductOptions");
    if (list && !list.hidden) closeMsmiProductOptions();
  });

  content.addEventListener("input", function (event) {
    if (event.target.id === "priceOverrideActor") {
      state.priceOverrideActor = event.target.value;
      return;
    }
    if (event.target.id === "priceOverrideReason") {
      state.priceOverrideReason = event.target.value;
      return;
    }
    var quickPrice = event.target.closest(".quick-sell-price");
    if (quickPrice) {
      quickPrice.classList.toggle(
        "price-changed",
        Math.abs(Number(quickPrice.value) - Number(quickPrice.dataset.original)) > 0.000001
      );
      return;
    }
    var input = event.target.closest(".invoice-mapping-input");
    if (!input) return;
    delete input.dataset.selectedCode;
    var draftCell = input.closest('.invoice-mapping-cell');
    var draftLine = invoiceEditingLine(input.dataset.id);
    if (draftCell && draftLine) {
      refreshInvoiceDraftConversion(draftCell,draftLine,null);
      if (!draftCell.mappingExpected) draftCell.mappingExpected = invoiceMappingExpected(input.dataset.id);
      draftCell.dataset.editingId = input.dataset.id;
    }
    closeMsmiProductOptions();
    msmiProductSearchTimer = setTimeout(function () { loadMsmiProductOptions(input); }, 220);
  });

  content.addEventListener("keydown", function (event) {
    if (event.isComposing || event.keyCode === 229) return;
    var payableAllocation = event.target.closest(".payable-allocation-input");
    if (payableAllocation && event.key === "Enter") {
      event.preventDefault();
      var allocationInputs = Array.from(content.querySelectorAll(".payable-allocation-input:not(:disabled)"));
      var currentAllocation = allocationInputs.indexOf(payableAllocation);
      var nextAllocation = allocationInputs[currentAllocation + 1];
      if (nextAllocation) nextAllocation.focus();
      else {
        var paymentDate = content.querySelector('#payablePaymentForm [name="payment_date"]');
        if (paymentDate) paymentDate.focus();
      }
      return;
    }
    var quickPrice = event.target.closest(".quick-sell-price");
    if (quickPrice && event.key === "Enter") {
      event.preventDefault();
      saveSellPriceOverrides([quickPrice]);
      return;
    }
    var conversionInput = event.target.closest(".unit-conversion-input, .invoice-draft-factor");
    if (conversionInput && event.key === "Enter") {
      event.preventDefault();
      if (conversionInput.matches('.invoice-draft-factor')) {
        conversionInput.closest('.invoice-mapping-cell').querySelector('[data-action="save-invoice-mapping"]').click();
        return;
      }
      var conversionButton = content.querySelector('[data-action="save-invoice-conversion"][data-direction="' +
        conversionInput.dataset.direction + '"][data-id="' + conversionInput.dataset.id + '"]');
      if (conversionButton) conversionButton.click();
      return;
    }
    var input = event.target.closest(".invoice-mapping-input");
    if (input && !event.isComposing) {
      var list = document.getElementById("msmiProductOptions");
      if (list && !list.hidden && msmiProductSearchInput === input) {
        var options = Array.from(list.querySelectorAll('[data-product-code]'));
        var selected = list.querySelector('[aria-selected="true"]');
        if (event.key === "Escape") {
          event.preventDefault(); event.stopPropagation(); closeMsmiProductOptions(); return;
        }
        if ((event.key === "ArrowDown" || event.key === "ArrowUp") && options.length) {
          event.preventDefault();
          var index = selected ? options.indexOf(selected) + (event.key === "ArrowDown" ? 1 : -1) : (event.key === "ArrowDown" ? 0 : options.length - 1);
          index = (index + options.length) % options.length;
          options.forEach(function (option, i) { option.setAttribute("aria-selected", i === index ? "true" : "false"); });
          input.setAttribute("aria-activedescendant", options[index].id);
          options[index].scrollIntoView({block:"nearest"}); return;
        }
        if (event.key === "Enter" && selected) {
          event.preventDefault(); chooseMsmiProductOption(selected); return;
        }
      }
    }
    if (event.isComposing) return;
    if (event.key === 'Escape') {
      var cancelCell = event.target.closest('.invoice-mapping-cell');
      var cancelField = cancelCell?.querySelector('.invoice-mapping-input');
      if (cancelField) {
        event.preventDefault(); event.stopPropagation(); closeMsmiProductOptions();
        var originalLine = invoiceEditingLine(cancelField.dataset.id);
        var originalInvoice = (state.invoiceListing?.items || []).find(function(r) { return r.id === originalLine?.invoice_id; });
        if (originalLine && originalInvoice) {
          delete cancelCell.mappingExpected;
          delete cancelCell.dataset.editingId;
          cancelCell.innerHTML = window.TdpInvoiceMappingCell(originalLine, originalInvoice);
        }
      }
      return;
    }
    if (!input || event.key !== "Enter") return;
    event.preventDefault();
    var direction = input.dataset.direction || state.invoiceDirection;
    var itemId = input.id.replace("map_" + direction + "_", "");
    var button = content.querySelector('[data-action="save-invoice-mapping"][data-direction="' +
      direction + '"][data-id="' + itemId + '"]');
    if (button) button.click();
  });

  function invoiceEditingLine(id) {
    return (state.invoiceListing?.lines || []).find(function(r) { return String(r.id) === String(id); });
  }
  function invoiceMappingExpected(id) {
    var row = invoiceEditingLine(id);
    if (!row) throw new Error('Dòng đang xem đã thay đổi. Hãy mở lại bảng.');
    var draft = document.getElementById('map_' + state.invoiceDirection + '_' + id)?.closest('.invoice-mapping-cell');
    if (draft?.mappingExpected) return draft.mappingExpected;
    var expected = {};
    ['product_code', 'mapping_status', 'conversion_factor', 'source_unit', 'qty', 'amount'].forEach(function(k) { expected[k] = row[k]; });
    return expected;
  }
  async function refreshSavedInvoiceMapping(direction, savedId) {
    var scope = [state.invoiceDirection,state.invoiceFrom,state.invoiceTo,state.invoiceStatus,state.invoiceLineFilter,state.invoicePending].join('|');
    var previousListing=state.invoiceListing, previousWorkbench=state.invoiceWorkbench;
    var oldLines = state.invoiceListing.lines || [], order = new Map(oldLines.map(function(r,i) { return [r.id,i]; }));
    await loadInvoiceWorkbench(true);
    if (state.view !== 'msmi' || scope !== [state.invoiceDirection,state.invoiceFrom,state.invoiceTo,state.invoiceStatus,state.invoiceLineFilter,state.invoicePending].join('|')) return;
    if (state.invoiceListing.error) {
      state.invoiceListing=previousListing;state.invoiceWorkbench=previousWorkbench;
      throw new Error('Đã lưu mã nhưng chưa tải lại được bảng. Phần đang gõ được giữ lại; hãy tải lại khi kết nối ổn định.');
    }
    // Capture immediately before rendering: the user may type or scroll while saving.
    var scroll = content.querySelector('.invoice-lines-card .invoice-lines-scroll');
    var top = scroll?.scrollTop || 0, left = scroll?.scrollLeft || 0;
    var viewport = invoiceVirtual?.snapshot(), focused=document.activeElement;
    var caret=focused?.selectionStart, caretEnd=focused?.selectionEnd;
    var nodes = invoiceVirtual ? invoiceVirtual.nodes() : Array.from(scroll?.querySelectorAll('tbody tr') || []);
    var scrollBox=scroll?.getBoundingClientRect(), anchor=focused?.closest?.('tr');
    function visibleAnchor(row){if(!row?.isConnected||!scroll?.contains(row))return false;var box=row.getBoundingClientRect();return box.bottom>scrollBox.top+48&&box.top<scrollBox.bottom;}
    if(!visibleAnchor(anchor)) anchor=nodes.find(visibleAnchor);
    var anchorId=anchor?.id, anchorOffset=anchor ? anchor.getBoundingClientRect().top-scrollBox.top : 0;
    var drafts = nodes.map(function(r) { return r.querySelector('.invoice-mapping-cell[data-editing-id]'); }).filter(function(c) { return c && c.dataset.editingId !== String(savedId); });
    var choices = invoiceCheckedRows().map(function(e) { return e.dataset.id; });
    // Server totals/status stay fresh; keep the rows in place during this edit session.
    state.invoiceListing.lines.sort(function(a,b) { return (order.get(a.id) ?? 1e12) - (order.get(b.id) ?? 1e12); });
    render();
    if (invoiceVirtual) invoiceVirtual.restore(top,left,drafts,choices,viewport);
    else {
      drafts.forEach(function(cell) { var row=document.getElementById('invoice-line-'+direction+'-'+cell.dataset.editingId); var target=row?.querySelector('.invoice-mapping-cell'); if(target) target.replaceWith(cell); });
      choices.forEach(function(id) { var box=document.querySelector('.invoice-group-select[data-id="'+id+'"]'); if(box) box.checked=true; });
      scroll=content.querySelector('.invoice-lines-card .invoice-lines-scroll');if(scroll){scroll.scrollTop=top;scroll.scrollLeft=left;}
    }
    var groupButton=content.querySelector('[data-action="preview-invoice-group"]');
    var chosen=invoiceCheckedRows().length;
    if(groupButton){groupButton.disabled=chosen<2;groupButton.textContent='Gộp '+chosen+' dòng đã chọn';}
    scroll=content.querySelector('.invoice-lines-card .invoice-lines-scroll');
    var restoredAnchor=anchorId&&document.getElementById(anchorId);
    if(scroll&&restoredAnchor) scroll.scrollTop+=restoredAnchor.getBoundingClientRect().top-scroll.getBoundingClientRect().top-anchorOffset;
    if(focused?.isConnected){focused.focus({preventScroll:true});if(caret!=null)try{focused.setSelectionRange(caret,caretEnd);}catch(ignore){}}
  }
  async function revealSavedInvoiceLine(direction, id, needsConversion) {
    if (state.invoiceDirection !== direction) return;
    var row = document.getElementById('invoice-line-' + direction + '-' + id);
    if (!row) return;
    row.classList.add('invoice-just-saved');
    // Saving keeps the current working position. Only explicit navigation scrolls.
  }
  content.addEventListener("click", async function (event) {
    var viewButton = event.target.closest("[data-view]");
    if (viewButton) { navigate(viewButton.dataset.view); return; }
    var button = event.target.closest("[data-action]");
    if (!button) return;
    var action = button.dataset.action;
    if (action === 'review-invoice-amount') {
      await window.TdpInvoiceAmountReview(button.dataset.id, {esc: esc, money: money,
        beforeApply: function () {
          var nodes = invoiceVirtual ? invoiceVirtual.nodes() : Array.from(content.querySelectorAll('tr'));
          if (nodes.some(function (row) { return row.querySelector('.invoice-mapping-cell[data-editing-id]'); })) {
            throw new Error('Còn mã hàng đang gõ chưa lưu. Đóng bảng này, Lưu hoặc nhấn Esc để bỏ phần đang sửa, rồi kiểm tra lại.');
          }
        },
        refresh: async function () {
          var scroll = content.querySelector('.invoice-lines-scroll');
          var top = scroll?.scrollTop || 0, left = scroll?.scrollLeft || 0;
          await loadInvoiceWorkbench(true); render();
          scroll = content.querySelector('.invoice-lines-scroll');
          if (scroll) { scroll.scrollTop = top; scroll.scrollLeft = left; }
        }});
      return;
    }
    if (action === 'preview-inventory-report') { await previewInventoryReport(button); return; }
    if (action === 'open-output-stock-remap') { openOutputStockRemap(state.inventoryFrom, state.inventoryTo); return; }
    if (action === 'show-all-output-invoices') {
      state.invoiceDirection = 'output'; state.invoiceStatus = 'all';
      state.invoiceLineFilter = 'all'; state.invoicePending = false;
      persistInvoiceWorkbenchFilters();
      await loadInvoiceWorkbench(true); render();
      return;
    }
    if (action === 'filter-invoice-issues') {
      state.invoiceLineFilter = state.invoiceLineFilter === 'needs_attention' ? 'all' : 'needs_attention';
      persistInvoiceWorkbenchFilters();
      await loadInvoiceWorkbench(true); render();
      return;
    }
    if (action === "jump-invoice-issue") {
      var firstIssue = (state.invoiceListing?.lines || []).find(function(r) { return r.issue; });
      if (firstIssue && invoiceVirtual) invoiceVirtual.reveal(firstIssue.id == null ? 'empty-'+firstIssue.invoice_id : firstIssue.id);
      var issueRow = document.querySelector('.invoice-lines-card tr[data-issue="1"]');
      if (issueRow) {
        issueRow.scrollIntoView({block:"center", inline:"nearest"});
        var editor = issueRow.querySelector('.invoice-mapping-input:not([disabled]), .invoice-draft-factor:not([disabled]), input[id^="conversion_"]:not([disabled])') ||
          issueRow.querySelector('input:not([type="checkbox"]):not([disabled]),select:not([disabled]),button:not([disabled])');
        if (editor) { editor.focus(); editor.scrollIntoView({block:"center", inline:"center"}); }
      }
      return;
    }
    if (action === 'reload-physical') { await loadPhysicalStock(); return; }
    if (action === 'cancel-physical-entry') { state.physicalEntry = null; renderPhysicalStock(); return; }
    if (action === 'physical-entry') {
      var selected = state.physicalStock.items.find(function (item) { return item.product_code === button.dataset.code; });
      if (!selected) return;
      state.physicalEntry = { kind: button.dataset.kind, item: selected, requestKey: window.crypto.randomUUID() };
      renderPhysicalStock();
      document.getElementById('physicalStockForm').scrollIntoView({ block: 'center' });
      return;
    }
    if (action === 'physical-source-order') {
      state.orderFilter = ''; state.orderIssueFilter = 'all';
      state.view = 'orders';
      await loadData(Number(button.dataset.batch), true);
      navigate('orders');
      var sourceRow = content.querySelector('[data-order-row="' + Number(button.dataset.id) + '"]');
      if (sourceRow) sourceRow.scrollIntoView({ block: 'center' });
      return;
    }
    if (action === "view-invoice-stock") {
      button.disabled = true;
      try { await openInvoiceStock(button.dataset.direction, button.dataset.id); }
      catch (error) { showToast(error.message, true); }
      finally { button.disabled = false; }
      return;
    }
    if (action === "back-invoice-workbench") {
      navigate("msmi");
      return;
    }
    if (action === "clear-invoice-stock") {
      state.inventoryTraceRequestSerial++;
      state.inventoryTrace = null;
      renderInventory();
      return;
    }
    if (action === "open-print-workspace") {
      state.printingRows = null; state.printingListLoading = false;
      state.printingDocument = button.dataset.document || "deliveries";
      state.printingFrom = state.homeFrom;
      state.printingTo = state.homeTo;
      state.printingSelected = {};
      navigate("printing");
      return;
    }
    if (action === "quick-add-order") {
      openQuickAddModal(button.dataset.id);
      return;
    }
    if (action === "select-all-print-batches") {
      printingSelectionRows().forEach(function (item) {
        state.printingSelected[item.key] = true;
      });
      renderPrinting();
      return;
    }
    if (action === "clear-print-batches") {
      state.printingSelected = {};
      renderPrinting();
      return;
    }
    if (action === "preview-selected-documents" || action === "print-selected-documents" || action === "preview-print-row") {
      var previewRows = printingSelectionRows().filter(function (item) {
        return action === "preview-print-row" ? item.key === button.dataset.key : Boolean(state.printingSelected[item.key]);
      });
      if (!previewRows.length) { showToast("Hãy chọn ít nhất một phiếu", true); return; }
      await window.TDPDocuments.open({kind:state.printingDocument, selections:previewRows.map(function(item) {
        return {batch_id:item.batch_id, kitchen:item.kitchen || ""};
      })}, "printingPreview", action === "print-selected-documents");
      return;
    }
    if (action === "preview-all-quotes") {
      var latest = (state.quoteVersions || [])[0];
      await window.TDPDocuments.open({kind:"quotes", period:state.quotePeriod, version_id:latest ? latest.id : null,
        batch_id:state.data.batch && state.data.batch.work_date.slice(0,7) === state.quotePeriod ? state.batchId : null}, "quotePreview");
      return;
    }
    if (action === "preview-quote") {
      await window.TDPDocuments.open({kind:"quote", contractor:state.quoteContractor, period:state.quotePeriod,
        batch_id:state.quoteMode === "daily" && state.quoteMeta.dailySource ? state.quoteMeta.dailySource.batch_id : null,
        version_id:state.quoteMeta.version ? state.quoteMeta.version.id : null}, "quotePreview");
      return;
    }
    if (action === "preview-payment-documents") {
      var scope = state.invoicePaymentScope;
      if (!scope || scope.error) return;
      await window.TDPDocuments.open({kind:"payment", contractor:scope.contractor, from:scope.date_from, to:scope.date_to, scope_id:scope.scope_id}, "paymentDocumentPreview");
      return;
    }
    if (action === "preview-purchase-documents") {
      await window.TDPDocuments.open({kind:"purchases", selections:[{batch_id:state.batchId}]}, "purchaseDocumentPreview");
      return;
    }
    if (action === "download-selected-documents" || action === "download-approved-input-bk") {
      var inputBKDownload = action === "download-approved-input-bk";
      var selectedPrintRows = printingSelectionRows().filter(function (item) {
        return Boolean(state.printingSelected[item.key]);
      });
      var selectedIds = selectedPrintRows.map(function (item) { return item.batch_id; }).filter(function (id, index, list) {
        return list.indexOf(id) === index;
      });
      if (!selectedIds.length) {
        showToast("Hãy chọn ít nhất một giấy tờ cần in", true);
        return;
      }
      var printLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang tạo file…";
        await downloadFile(inputBKDownload ? "/api/bk-import/export-approved" : "/api/export/selected-documents", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            batch_ids: selectedIds,
            documents: [state.printingDocument],
            delivery_selections: state.printingDocument === "deliveries" ? selectedPrintRows.map(function (item) {
              return { batch_id: item.batch_id, kitchen: item.kitchen };
            }) : []
          })
        });
        showToast(inputBKDownload ? "Đã tải bảng kê đầu vào của các ngày đã chọn. Hàng đã ghi kho, không cần nhập lại." : "Đã tải giấy tờ đã chọn · mở file Excel rồi bấm Ctrl+P để in");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = printLabel;
      }
      return;
    }
    if (action === "open-debt-section") {
      state.debtSection = button.dataset.section || "";
      renderDebts();
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    if (action === "back-debt-overview") {
      state.debtSection = "";
      pageTitle.textContent = titles.debts;
      renderDebts();
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    if (action === "toggle-delivery-details") {
      state.deliveryDetailsOpen = !state.deliveryDetailsOpen;
      renderDeliveries();
      return;
    }
    if (action === "toggle-quote-details") {
      state.quoteDetailsOpen = !state.quoteDetailsOpen;
      renderQuotes();
      return;
    }
    if (action === "toggle-quote-history") {
      state.quoteHistoryOpen = !state.quoteHistoryOpen;
      renderQuotes();
      return;
    }
    if (action === "toggle-inventory-details") {
      state.inventoryDetailsOpen = !state.inventoryDetailsOpen;
      renderInventory();
      return;
    }
    if (action === "reload-inventory-close") {
      state.inventoryMonthClose = null;
      renderInventory();
      await loadInventoryMonthClose();
      return;
    }
    if (action === "close-inventory-month") {
      await closeInventoryMonth(button);
      return;
    }
    if (action === "reopen-inventory-month") {
      await reopenInventoryMonth(button);
      return;
    }
    if (action === 'open-minvoice-files') { navigate('documents'); return; }
    if (action === 'resolve-invoice-order') {
      state.orderFilter = ''; state.orderIssueFilter = 'all'; navigate('orders');
      var orderRow = content.querySelector('[data-order-row="' + button.dataset.id + '"]');
      if (orderRow) orderRow.scrollIntoView({block:'center'});
      openOrderModal(button.dataset.id); return;
    }
    if (action === 'return-stock-resolution') {
      state.stockResolutionReturn = null; state.outgoingReadiness = null; state.outgoingInvoices = null;
      navigate('documents'); await Promise.all([fetchOutgoingReadiness(), fetchOutgoingInvoices()]); return;
    }
    if (action === 'show-stock-cause') { await showStockCause(button); return; }
    if (action === 'edit-invoice-buyer') {
      state.paymentFilters = Object.assign({}, state.paymentFilters, {contractor:button.dataset.contractor});
      renderDocuments();
      var buyerForm = document.getElementById('buyerProfileForm');
      if (buyerForm) { buyerForm.closest('details').open = true; buyerForm.scrollIntoView({block:'center'}); buyerForm.querySelector('input').focus({preventScroll:true}); }
      return;
    }
    if (action === 'open-inventory-close') {
      if (!state.inventoryClosePeriod) {
        var chosen = (state.inventoryFrom || todayIso).slice(0,7);
        var current = todayIso.slice(0,7);
        var previous = new Date(Number(current.slice(0,4)), Number(current.slice(5,7)) - 1, 0);
        state.inventoryClosePeriod = chosen < current ? chosen : previous.getFullYear() + '-' + String(previous.getMonth()+1).padStart(2,'0');
      }
      state.inventoryCloseOpen = true; state.inventoryMonthClose = null; renderInventoryCloseDialog();
      await loadInventoryMonthClose(); return;
    }
    if (action === "toggle-document-details") {
      state.documentDetailsOpen = !state.documentDetailsOpen;
      renderDocuments();
      return;
    }
    if (action === "save-price-overrides") {
      await saveSellPriceOverrides();
      return;
    }
    if (action === "choose-quote-workbook") {
      state.quoteImportPreview = null;
      quoteWorkbookInput.click();
      return;
    }
    if (action === "cancel-quote-import") {
      state.quoteImportPreview = null;
      renderQuotes();
      return;
    }
    if (action === "confirm-quote-import") {
      await confirmQuoteImport(button);
      return;
    }
    if (action === "toggle-pending-invoices") {
      state.invoicePending = !state.invoicePending;
      state.invoiceStatus = 'all'; state.invoiceLineFilter = 'all';
      persistInvoiceWorkbenchFilters();
      await loadInvoiceWorkbench();
      return;
    }
    if (action === "set-invoice-direction") {
      state.invoiceDirection = button.dataset.direction === "output" ? "output" : "input";
      state.legacyInvoiceMappingPreview = null;
      persistInvoiceWorkbenchFilters();
      state.invoiceWorkbench = null;
      loadInvoiceWorkbench();
      return;
    }
    if (action === "prepare-invoice-sync") {
      state.legacyInvoiceMappingPreview = null;
      await prepareInvoiceSyncBatch(button);
      return;
    }
    if (action === "reload") loadData();
    if (action === "reload-operations") { state.operations = null; loadOperations(); }
    if (action === "refresh-payables") {
      invalidatePayableWorkspace(true);
      await fetchPayableWorkspace();
      return;
    }
    if (action === "refresh-receivables") {
      invalidateReceivableWorkspace(false);
      await fetchReceivableWorkspace();
      return;
    }
    if (action === "toggle-receivable-history") {
      await toggleReceivableHistory(button);
      return;
    }
    if (action === "reverse-payable-payment") {
      await reversePayablePayment(button);
      return;
    }
    if (action === "choose-excel") excelInput.click();
    if (action === "choose-attendance") {
      state.attendanceImportPreview = null;
      attendanceInput.click();
    }
    if (action === "choose-mapping-file") {
      state.mappingImportType = button.dataset.mappingType || "";
      state.mappingPreview = null;
      mappingFileInput.click();
    }
    if (action === "edit-catalog-product") { openCatalogProductDialog(state.catalogItems.find(function(item) { return item.code === button.dataset.code; })); return; }
    if (action === "catalog-previous" || action === "catalog-next") { state.catalogOffset = Math.max(0, state.catalogOffset + (action === 'catalog-next' ? 50 : -50)); await loadCatalogProducts(); return; }
    if (action === "add-catalog-product") { openCatalogProductDialog(); return; }
    if (action === "choose-catalog-workbook") {
      state.catalogImportPreview = null;
      catalogWorkbookInput.click();
    }
    if (action === "choose-kitchen-workbook") {
      state.kitchenImportPreview = null;
      state.kitchenMealCountOverrides = {};
      kitchenWorkbookInput.click();
    }
    if (action === "choose-meal-attendance") {
      state.mealAttendancePreview = null;
      mealAttendanceInput.click();
    }
    if (action === "preview-xcom-payment") {
      var xcomPaymentForm = document.getElementById("xcomPaymentDocumentForm");
      if (!xcomPaymentForm || !xcomPaymentForm.reportValidity()) return;
      var xcomPaymentBody = Object.fromEntries(new FormData(xcomPaymentForm).entries());
      try {
        state.xcomPaymentPreview = await api("/api/kitchen/payment-documents/preview", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(xcomPaymentBody)
        });
        state.xcomPaymentRequest = xcomPaymentBody;
        renderKitchen();
        showToast("Đã đối chiếu suất thực tế và đơn giá đúng kỳ");
      } catch (error) {
        state.xcomPaymentPreview = null;
        state.xcomPaymentRequest = null;
        showToast(error.message, true);
      }
    }
    if (action === "delete-xcom-payment-profile") {
      if (!window.confirm("Xóa hồ sơ thanh toán và toàn bộ phạm vi/đơn giá của hồ sơ này?")) return;
      state.xcomPaymentPreview = null;
      state.xcomPaymentRequest = null;
      await jsonWrite(
        "/api/kitchen/payment-profiles/" + encodeURIComponent(button.dataset.profile),
        "DELETE", { confirmed: true }, "Đã xóa hồ sơ thanh toán"
      );
    }
    if (action === "delete-xcom-payment-scope") {
      if (!window.confirm("Bỏ bếp/XCOM này khỏi hồ sơ thanh toán?")) return;
      state.xcomPaymentPreview = null;
      state.xcomPaymentRequest = null;
      await jsonWrite(
        "/api/kitchen/payment-scopes/" + encodeURIComponent(button.dataset.scopeType) +
        "/" + encodeURIComponent(button.dataset.scopeCode),
        "DELETE", { confirmed: true }, "Đã bỏ phạm vi hồ sơ thanh toán"
      );
    }
    if (action === "delete-xcom-meal-tariff") {
      if (!window.confirm("Xóa đơn giá suất ăn của đúng kỳ/ca này?")) return;
      state.xcomPaymentPreview = null;
      state.xcomPaymentRequest = null;
      await jsonWrite(
        "/api/kitchen/payment-profiles/" + encodeURIComponent(button.dataset.profile) +
        "/tariffs/" + encodeURIComponent(button.dataset.period) + "/" + encodeURIComponent(button.dataset.shift),
        "DELETE", { confirmed: true }, "Đã xóa đơn giá suất ăn"
      );
    }
    if (action === "choose-opening-workbook") {
      var openingPeriod = document.querySelector('#openingForm [name="period"]');
      if (openingPeriod && openingPeriod.value) state.opsMonth = openingPeriod.value;
      state.openingImportPreview = null;
      openingWorkbookInput.click();
    }
    if (action === "choose-bk-workbook") {
      state.bkImportPreview = null;
      bkWorkbookInput.click();
    }
    if (action === 'reload-bk-documents') await loadBkDocuments();
    if (action === "choose-payables-workbook") {
      state.payablesImportPreview = null;
      payablesWorkbookInput.click();
    }
    if (action === "choose-purchase-order-file") {
      state.purchaseOrderPreview = null;
      purchaseOrderInput.click();
    }
    if (action === "cancel-purchase-order-import") {
      state.purchaseOrderPreview = null;
      renderPurchases();
    }
    if (action === "confirm-purchase-order-import") await confirmPurchaseOrderImport(button);
    if (action === "cancel-payables-import") {
      state.payablesImportPreview = null;
      renderDebts();
    }
    if (action === "confirm-payables-import") await confirmPayablesImport(button);
    if (action === "cancel-opening-import") {
      state.openingImportPreview = null;
      renderInventory();
    }
    if (action === "cancel-bk-import") {
      state.bkImportPreview = null;
      renderInventory();
    }
    if (action === "confirm-bk-import") await confirmBkImport(button);
    if (action === "reverse-bk-import") await reverseBkImport(button);
    if (action === "confirm-opening-import") await confirmOpeningImport(button);
    if (action === "cancel-kitchen-import") {
      state.kitchenImportPreview = null;
      state.kitchenMealCountOverrides = {};
      renderKitchen();
    }
    if (action === "confirm-kitchen-import") await confirmKitchenImport(button);
    if (action === "cancel-meal-attendance-import") {
      state.mealAttendancePreview = null;
      renderKitchen();
    }
    if (action === "confirm-meal-attendance-import") await confirmMealAttendance(button);
    if (action === "cancel-attendance-import") {
      state.attendanceImportPreview = null;
      renderPayroll();
    }
    if (action === "confirm-attendance-import") await confirmAttendanceImport(button);
    if (action === "cancel-mapping-import") {
      var cancelledType = state.mappingPreview && state.mappingPreview.mapping_type;
      state.mappingPreview = null;
      state.mappingImportType = "";
      if (cancelledType === "kitchen_units") renderKitchen(); else renderSettings();
    }
    if (action === "confirm-mapping-import") await confirmMappingImport(button);
    if (action === "cancel-catalog-import") {
      state.catalogImportPreview = null;
      renderSettings();
    }
    if (action === "confirm-catalog-import") await confirmCatalogImport(button);
    if (action === "new-batch") newBatch();
    if (action === "paste-orders") openPasteModal();
    if (action === "bulk-edit-orders") openBulkOrderModal();
    if (action === 'first-order-error') {
      state.orderFilter = '';
      state.orderIssueFilter = 'error';
      document.getElementById('orderSearch').value = '';
      document.getElementById('orderIssueFilter').value = 'error';
      applyOrderFilter();
      var firstError = content.querySelector('[data-order-row].row-error');
      if (firstError) {
        firstError.scrollIntoView({ block: 'center', inline: 'start' });
        firstError.querySelector('[data-action="edit-order"]').focus({ preventScroll: true });
      } else showToast('Không còn lỗi chặn duyệt');
    }
    if (action === 'settle-physical-order') {
      var row = state.data.orders.find(function (item) { return String(item.id) === button.dataset.id; });
      var stage = row.physical_stage === 'delivered' ? 'ordered' : 'delivered';
      if (!window.confirm(stage === 'delivered'
        ? 'Chốt đã giao ' + stockQty(row.actual_delivered) + ' ' + row.unit + ', khách trả ' + stockQty(row.customer_return_qty) + '? Kho chuyển từ lượng đặt sang lượng giao ròng, không trừ thêm lần nữa.'
        : 'Mở lại: kho tính theo số đặt ' + stockQty(row.qty) + ' ' + row.unit + '?')) return;
      try {
        button.disabled = true;
        await api('/api/physical-stock/orders/' + row.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stage: stage, revision: row.physical_revision }) });
        await loadData(state.batchId, true);
        showToast('Đã cập nhật kho thực tế theo lượng đã xác nhận');
      } catch (error) { showToast(error.message, true); button.disabled = false; }
    }
    if (action === "add-order") openOrderModal(null);
    if (action === "edit-order") openOrderModal(button.dataset.id);
    if (action === "delete-order") deleteOrder(button.dataset.id);
    if (action === "approve-batch") approveBatch();
    if (action === "copy-supplier-image" || action === "download-supplier-image") {
      var imageLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang tạo ảnh…";
        await handleSupplierImage(button.dataset.groupIndex, action === "download-supplier-image");
      } finally {
        button.disabled = false;
        button.textContent = imageLabel;
      }
    }
    if (action === "set-supplier-order-status") {
      var targetStatus = button.dataset.status;
      var supplierKey = button.dataset.supplierKey;
      var statusLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang cập nhật…";
        await api("/api/supplier-order-status/" + state.batchId + "/" + encodeURIComponent(supplierKey), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: targetStatus, revision: n(button.dataset.revision) })
        });
        state.supplierNeeds = null;
        await fetchSupplierNeeds();
        showToast(targetStatus === "ordered" ? "Đã đánh dấu nhà cung cấp đã đặt" : "Đã mở lại nhà cung cấp · cần đặt lại");
      } catch (error) {
        button.disabled = false;
        button.textContent = statusLabel;
        showToast(error.message, true);
      }
    }
    if (action === "toggle-supplier-rule") {
      try {
        await api("/api/supplier-rules/" + encodeURIComponent(button.dataset.supplier), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ combine_kitchens: button.dataset.combine === "1" })
        });
        state.supplierNeeds = null;
        await fetchSupplierNeeds();
        showToast(button.dataset.combine === "1" ? "Đã gộp đơn nhà cung cấp qua nhiều bếp" : "Đã tách đơn nhà cung cấp theo từng bếp");
      } catch (error) { showToast(error.message, true); }
    }
    if (action === "reverse-receipt") reverseReceipt(button);
    if (action === "refresh-monthly-report") fetchMonthlyReport();
    if (action === "refresh-debt-period") fetchDebtPeriod();
    if (action === "ledger-page") {
      var pageOffset = Math.max(0, Number(button.dataset.offset) || 0);
      if (button.dataset.kind === "receivable") {
        state.receivableOffset = pageOffset;
        invalidateReceivableWorkspace(true); fetchReceivableWorkspace();
      } else if (button.dataset.kind === "payable-history") {
        state.payableHistoryOffset = pageOffset;
        invalidatePayableWorkspace(true); fetchPayableWorkspace();
      } else {
        state.payableOffset = pageOffset;
        invalidatePayableWorkspace(true); fetchPayableWorkspace();
      }
    }
    if (action === "check-minvoice") checkMinvoice(button);
    if (action === "refresh-outgoing-readiness") {
      state.outgoingActionError = null;
      state.outgoingReadiness = null;
      renderDocuments();
      await fetchOutgoingReadiness();
    }
    if (action === "confirm-outgoing-substitution") {
      var currentSubstitution = outgoingSubstitutionFormBody();
      var activePreview = state.outgoingSubstitutionPreview;
      if (!activePreview || !activePreview.can_confirm ||
          !sameOutgoingSubstitutionRequest(currentSubstitution, state.outgoingSubstitutionRequest)) {
        showToast("Dữ liệu đã đổi hoặc chưa đủ điều kiện; cần xem trước lại", true);
        return;
      }
      if (!window.confirm(
        "Xác nhận thay " + activePreview.original_product_code + " bằng " +
        activePreview.substitute_product_code + " · " + activePreview.qty + " " +
        activePreview.unit + " với đơn giá " + money(activePreview.unit_price) + "?"
      )) return;
      try {
        button.disabled = true;
        button.textContent = "Đang ghi xác nhận…";
        var confirmedSubstitution = await api("/api/outgoing-substitutions/confirm", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(Object.assign({}, state.outgoingSubstitutionRequest, {
            preview_id: activePreview.preview_id,
            confirmed: true
          }))
        });
        state.outgoingSubstitutionPreview = null;
        state.outgoingSubstitutionRequest = null;
        state.outgoingSubstitutionDraft = null;
        state.outgoingSubstitutionActions = null;
        state.outgoingInvoices = null;
        state.outgoingReadiness = null;
        state.outgoingPeriodShortages = null;
        await Promise.all([
          fetchOutgoingSubstitutions(), fetchOutgoingInvoices(), fetchOutgoingReadiness()
        ]);
        showToast(confirmedSubstitution.idempotent
          ? "Lựa chọn này đã được ghi trước đó · không tạo trùng"
          : "Đã ghi mặt hàng thay thế, giữ tồn và lưu lịch sử thay đổi");
      } catch (error) {
        button.disabled = false;
        button.textContent = "Xác nhận đúng mã thay thế này";
        showToast(error.message, true);
      }
      return;
    }
    if (action === "reverse-outgoing-substitution") {
      if (!window.confirm("Hoàn tác lựa chọn thay thế này và nhả phần tồn đang giữ? Lịch sử vẫn được giữ.")) return;
      var reversalActor = window.prompt("Người thực hiện hoàn tác (bắt buộc):", "") || "";
      if (!reversalActor.trim()) { showToast("Cần nhập người thực hiện hoàn tác", true); return; }
      var reversalReason = window.prompt("Lý do hoàn tác (bắt buộc):", "") || "";
      if (!reversalReason.trim()) { showToast("Cần nhập lý do hoàn tác", true); return; }
      try {
        button.disabled = true;
        button.textContent = "Đang hoàn tác…";
        await api("/api/outgoing-substitutions/" + button.dataset.id + "/reverse", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            confirmed: true, actor: reversalActor.trim(), reason: reversalReason.trim()
          })
        });
        state.outgoingSubstitutionPreview = null;
        state.outgoingSubstitutionRequest = null;
        state.outgoingSubstitutionActions = null;
        state.outgoingInvoices = null;
        state.outgoingReadiness = null;
        state.outgoingPeriodShortages = null;
        await Promise.all([
          fetchOutgoingSubstitutions(), fetchOutgoingInvoices(), fetchOutgoingReadiness()
        ]);
        showToast("Đã hoàn tác, trả lại số lượng tồn và giữ nguyên lịch sử thay đổi");
      } catch (error) {
        button.disabled = false;
        button.textContent = "Hoàn tác";
        showToast(error.message, true);
      }
      return;
    }
    if (action === "load-outgoing-shortages") {
      var shortageFrom = document.getElementById("outgoingShortageFrom");
      var shortageTo = document.getElementById("outgoingShortageTo");
      var shortageContractor = document.getElementById("outgoingShortageContractor");
      state.outgoingShortageFrom = shortageFrom ? shortageFrom.value : state.outgoingShortageFrom;
      state.outgoingShortageTo = shortageTo ? shortageTo.value : state.outgoingShortageTo;
      state.outgoingShortageContractor = shortageContractor ? shortageContractor.value : "";
      await fetchOutgoingPeriodShortages();
    }
    if (['edit-invoice-mapping', 'edit-invoice-conversion', 'cancel-invoice-mapping-edit'].includes(action)) {
      var editLine = invoiceEditingLine(button.dataset.id);
      var editInvoice = (state.invoiceListing?.items || []).find(function(r) { return r.id === editLine?.invoice_id; });
      if (!editLine || !editInvoice) return;
      var editCell = button.closest('.invoice-mapping-cell');
      if (action === 'cancel-invoice-mapping-edit') {delete editCell.dataset.editingId;delete editCell.mappingExpected;}
      else editCell.dataset.editingId = button.dataset.id;
      editCell.innerHTML = window.TdpInvoiceMappingCell(editLine, editInvoice,
        action === 'edit-invoice-mapping' ? 'code' : action === 'edit-invoice-conversion' ? 'conversion' : '');
      var editField = editCell.querySelector('input');
      if (editField) { editField.focus(); editField.select(); }
      return;
    }
    if (['save-invoice-mapping', 'review-invoice-identity', 'review-output-adjustment', 'save-invoice-conversion', 'create-msmi-receipt', 'review-input-receipts', 'review-output-postings', 'post-invoice-output', 'preview-invoice-group','split-invoice-group'].includes(action)) {
      var pendingEdit = invoicePendingEdit();
      var savingThisEdit = action.startsWith('save-invoice-') || action === 'review-invoice-identity';
      if (pendingEdit && !savingThisEdit) {
        showToast('Đang sửa mã/quy đổi. Hãy Lưu hoặc nhấn Esc để bỏ sửa trước.', true);
        return;
      }
    }
    if (action === 'repair-input-conversion') {
      var repairInvoice = (state.invoiceListing.items || []).find(r => String(r.id) === String(button.dataset.id));
      if (repairInvoice) await window.TdpInputConversionRepair({invoice:repairInvoice,api:api,esc:esc,onSaved:async function(){
        state.inventoryValuation=null;state.inventoryMonthClose=null;state.outgoingReadiness=null;
        state.outgoingPeriodShortages=null;await loadInvoiceWorkbench(true);render();
      }});
      return;
    }
    if (action === 'allocate-input-discount') {
      if (invoicePendingEdit()) { showToast('Lưu mã/quy đổi đang sửa trước khi phân bổ chiết khấu.',true); return; }
      await window.TdpInputDiscount({id:Number(button.dataset.id),api:api,esc:esc,onSaved:async function(){ await loadInvoiceWorkbench(true); render(); }});
      return;
    }
    if (['invoice-expense-all','invoice-expense-undo','invoice-expense-line','invoice-expense-line-undo'].includes(action)) {
      if (invoicePendingEdit()) {
        showToast('Hãy Lưu hoặc nhấn Esc để bỏ sửa mã trước khi phân loại.',true); return;
      }
      var expenseLine = action.includes('-line') ? invoiceEditingLine(button.dataset.id) : null;
      if (action.includes('-line') && !expenseLine) { showToast('Dòng đã thay đổi; hãy tải lại bảng trước khi phân loại.',true); return; }
      var expenseInvoiceId = expenseLine ? expenseLine.invoice_id : Number(button.dataset.id);
      var expenseInvoice = (state.invoiceListing?.items || []).find(function(r) { return r.id === expenseInvoiceId; });
      if (!expenseInvoice) return;
      var expenseLabel = button.textContent;
      try {
        button.disabled = true;
        if (!await confirmInvoiceExpense(expenseInvoice,expenseLine,!action.endsWith('-undo'))) return;
        button.textContent = 'Đang lưu…';
        await api('/api/invoice-workbench/input-invoices/' + expenseInvoiceId + '/expense', {
          method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
            confirmed:true,expense:!action.endsWith('-undo'),item_ids:expenseLine ? [expenseLine.id] : null,expected:expenseInvoice.expense_token
          })
        });
        await loadInvoiceWorkbench(true); render();
        showToast(action.endsWith('-undo') ? 'Đã bỏ phân loại chi phí. Kiểm tra mã/quy đổi trước khi nhập kho.' : 'Đã đánh dấu chi phí không nhập kho. Giữ nguyên hóa đơn và số tiền.');
      } catch(error) { showToast(error.message,true); }
      finally { button.disabled=false; button.textContent=expenseLabel; }
      return;
    }
    if (action === 'preview-invoice-group') {
      var groupIds = invoiceCheckedRows().map(function(e) { return Number(e.dataset.id); });
      try {
        button.disabled = true;
        await window.TdpInvoiceGroupEditor(groupIds, {
          api: api, esc: esc, quantity: stockQty, money: stockMoney,
          saved: async function(result, preview) {
            state.invoiceStatus = 'all'; state.invoiceLineFilter = 'all'; persistInvoiceWorkbenchFilters();
            await loadInvoiceWorkbench(true); render();
            var mergedRow = document.getElementById('invoice-line-input-' + groupIds[0]);
            if (mergedRow) mergedRow.scrollIntoView({block:'center',inline:'nearest'});
            showToast('Đã gộp thành 1 dòng · ' + stockQty(preview.qty) + ' ' + preview.unit + '. Chưa nhập kho.');
          }
        });
      } catch(e) { showToast(e.message,true); }
      finally { button.disabled=false; }
      return;
    }
    if (action === 'split-invoice-group') {
      try {
        button.disabled=true;
        await api('/api/invoice-workbench/input-groups/'+button.dataset.id+'/split',{method:'POST'});
        await loadInvoiceWorkbench(true);render();showToast('Đã hiện lại các dòng riêng. Lượng, tiền và sổ kho giữ nguyên.');
      } catch(e) { showToast(e.message,true);button.disabled=false; }
      return;
    }
    if (action === "save-invoice-mapping" || action === "review-invoice-identity") {
      var mappingDirection = button.dataset.direction || state.invoiceDirection;
      var mappingInput = document.getElementById("map_" + mappingDirection + "_" + button.dataset.id);
      if (!mappingInput || !mappingInput.value.trim()) { showToast("Cần nhập mã hàng TĐP", true); return; }
      if (mappingInput.dataset.selectedCode !== mappingInput.value.trim()) {
        showToast(mappingDirection === 'input' ? 'Chọn mã trong danh sách gợi ý rồi nhập quy đổi và Lưu.' : 'Chọn mã trong danh sách gợi ý rồi Lưu.', true);
        mappingInput.focus();
        return;
      }
      try {
        button.disabled = true;
        var mappingBody = { product_code: mappingInput.value.trim(), expected: invoiceMappingExpected(button.dataset.id) };
        var draftFactor = button.closest('.invoice-mapping-cell').querySelector('.invoice-draft-factor');
        if (mappingDirection === 'input' && draftFactor && mappingInput.dataset.selectedCode === mappingBody.product_code) {
          var factorValue = Number(draftFactor.value.trim().replace(',', '.'));
          if (!Number.isFinite(factorValue) || factorValue <= 0 || factorValue > 1000000000) {
            draftFactor.focus();
            throw new Error(mappingDirection === 'output' ? 'Mã đã chọn nhưng chưa đủ quy đổi. Nhập số ' + draftFactor.dataset.unit + ' tương ứng với 1 ' + invoiceEditingLine(button.dataset.id).source_unit + ', rồi Lưu.' : 'Nhập hệ số quy đổi lớn hơn 0 trong giới hạn cho phép trước khi lưu.');
          }
          mappingBody.conversion_factor = factorValue;
        }
        var conversionOnly = mappingDirection === 'input' && mappingBody.product_code === mappingBody.expected.product_code && mappingBody.conversion_factor != null;
        var savingFields=Array.from(button.closest('.invoice-mapping-cell').querySelectorAll('input'));
        savingFields.forEach(function(field){field.disabled=true;});
        var mappingUrl = "/api/invoice-workbench/items/" + mappingDirection + "/" + button.dataset.id + (conversionOnly ? "/conversion" : "/mapping");
        var saveChosenMapping = function () { return api(mappingUrl, {method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(mappingBody)}); };
        var mappingResult;
        try { mappingResult = await saveChosenMapping(); }
        catch (identityError) {
          if (identityError.payload?.code !== 'product_identity_confirmation_required') throw identityError;
          if (!await confirmInvoiceProductIdentity(identityError.payload.identity_review, identityError.message)) {
            mappingInput.disabled = false;
            mappingInput.focus({preventScroll:true}); mappingInput.select();
            throw new Error('Chưa xác nhận mã. Hãy chọn đúng mặt hàng trong danh mục rồi Lưu.');
          }
          mappingBody.confirm_identity = true;
          if (identityError.payload.identity_review) mappingBody.expected_identity = identityError.payload.identity_review.key;
          mappingResult = await saveChosenMapping();
        }
        state.operations = null;
        await refreshSavedInvoiceMapping(mappingDirection, button.dataset.id);
        await revealSavedInvoiceLine(mappingDirection, button.dataset.id, mappingResult.requires_unit_conversion);
        var savedInvoice = (state.invoiceListing?.items || []).find(function(r) { return r.id === invoiceEditingLine(button.dataset.id)?.invoice_id; });
        showToast(mappingDirection === 'output' ? 'Đã khớp mã. Giữ nguyên số lượng hóa đơn.' + (savedInvoice?.amount_review ? ' HĐ ' + savedInvoice.invoice_number + ' chờ đối chiếu tiền; xem cảnh báo phía trên bảng.' : '') : mappingResult.requires_unit_conversion
          ? "Đã nhớ mã nhưng đơn vị tính khác nhau — cần nhập quy đổi trước khi ghi kho"
          : "Đã ghép mã và ghi nhớ đúng loại hóa đơn, đúng đối tác");
      } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
      } finally {
        (savingFields || []).forEach(function(field){field.disabled=false;});
      }
      return;
    }
    if (action === "save-invoice-conversion") {
      var conversionDirection = button.dataset.direction || state.invoiceDirection;
      var conversionInput = document.getElementById("conversion_" + conversionDirection + "_" + button.dataset.id);
      var conversionFactor = conversionInput ? Number(conversionInput.value) : 0;
      if (!Number.isFinite(conversionFactor) || conversionFactor <= 0) {
        showToast("Hệ số quy đổi phải là số lớn hơn 0", true);
        return;
      }
      try {
        button.disabled = true;
        var conversionResult = await api("/api/invoice-workbench/items/" + conversionDirection + "/" +
          button.dataset.id + "/conversion", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ conversion_factor: conversionFactor, expected: invoiceMappingExpected(button.dataset.id) })
        });
        state.operations = null;
        await refreshSavedInvoiceMapping(conversionDirection, button.dataset.id);
        await revealSavedInvoiceLine(conversionDirection, button.dataset.id, false);
        showToast("Đã lưu: 1 " + conversionResult.source_unit + " = " + conversionResult.conversion_factor +
          " " + conversionResult.target_unit + " · số lượng vào kho " + conversionResult.stock_qty);
      } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
      }
      return;
    }
    if (action === "post-invoice-output") {
      if (!window.confirm("Xác nhận đây là hóa đơn đã phát hành hợp lệ và trừ kho theo các dòng đã ghép mã?")) return;
      try {
        button.disabled = true;
        var postResult = await api("/api/invoice-workbench/output/" + button.dataset.id + "/post", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true })
        });
        state.inventoryValuation = null;
        await loadInvoiceWorkbench(true);
        state.invoiceLastPosted = {direction:"output", id:button.dataset.id};
        render();
        showToast("Đã xuất kho " + postResult.inventory_lines + " dòng hóa đơn · có lưu lịch sử và chống trùng");
      } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
      }
      return;
    }
    if (action === "reverse-invoice-output") {
      if (!window.confirm("Xác nhận hoàn tác xuất kho? Bút toán xuất cũ sẽ được giữ nguyên và hệ thống thêm bút toán đảo.")) return;
      try {
        button.disabled = true;
        var reverseResult = await api("/api/invoice-workbench/output/" + button.dataset.id + "/reversal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true, note: "Xác nhận hoàn tác xuất kho từ bàn làm việc hóa đơn" })
        });
        state.inventoryValuation = null;
        await loadInvoiceWorkbench(true);
        render();
        showToast("Đã hoàn tác xuất kho " + reverseResult.reversal_lines + " dòng · không xóa lịch sử cũ");
      } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
      }
      return;
    }
    if (action === "match-output-catalog-codes") {
      if (document.querySelector('.invoice-mapping-cell[data-editing-id]')) {
        showToast('Hãy Lưu hoặc nhấn Esc để bỏ sửa dòng đang mở trước.', true); return;
      }
      var matchLabel = button.textContent;
      try {
        button.disabled = true; button.textContent = 'Đang khớp mã…';
        var matched = await api('/api/invoice-workbench/output-match-codes', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({from:state.invoiceFrom,to:state.invoiceTo})
        });
        await loadInvoiceWorkbench(true); render();
        showToast('Đã khớp ' + matched.matched_lines + ' dòng. Giữ nguyên số lượng hóa đơn. Chưa xuất kho.');
      } catch (error) {
        showToast(error.message, true); button.disabled = false; button.textContent = matchLabel;
      }
      return;
    }
    if (action === "preview-msmi-legacy-mappings" || action === "apply-msmi-safe-suggestions") {
      var autoFrom = state.invoiceFrom, autoTo = state.invoiceTo;
      var autoOptions = {method: "POST"};
      if (action === "preview-msmi-legacy-mappings") {
        var autoFile = document.getElementById("legacyInvoiceMappingFile");
        if (!autoFile?.files?.[0]) { showToast("Hãy chọn bảng kê nhập .xlsx hoặc .xlsm", true); return; }
        var autoForm = new FormData();
        autoForm.append("file", autoFile.files[0]);
        autoForm.append("from", autoFrom);
        autoForm.append("to", autoTo);
        autoOptions.body = autoForm;
      } else {
        autoOptions.headers = {"Content-Type": "application/json"};
        autoOptions.body = JSON.stringify({from: autoFrom, to: autoTo});
      }
      var autoLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang tự ghép mã…";
        var autoResult = await api("/api/msmi/auto-mappings", autoOptions);
        state.legacyInvoiceMappingPreview = null;
        await loadInvoiceWorkbench(true);
        render();
        showToast("Đã tự ghép " + autoResult.mapped_lines_in_period + " dòng trong kỳ " + dateVN(autoFrom) + " → " + dateVN(autoTo) + ". Dòng còn cần xử lý nằm trên cùng; " + autoResult.ready_invoices_in_period + " hóa đơn đủ mã, chờ nhập kho.");
      } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
        button.textContent = autoLabel;
      }
      return;
    }
    if (action === "download-outgoing-shortages") {
      var exportFrom = document.getElementById("outgoingShortageFrom");
      var exportTo = document.getElementById("outgoingShortageTo");
      var exportContractor = document.getElementById("outgoingShortageContractor");
      state.outgoingShortageFrom = exportFrom ? exportFrom.value : state.outgoingShortageFrom;
      state.outgoingShortageTo = exportTo ? exportTo.value : state.outgoingShortageTo;
      state.outgoingShortageContractor = exportContractor ? exportContractor.value : "";
      var exportQuery = "from=" + encodeURIComponent(state.outgoingShortageFrom) +
        "&to=" + encodeURIComponent(state.outgoingShortageTo) +
        "&contractor=" + encodeURIComponent(state.outgoingShortageContractor);
      var exportLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang tạo file…";
        await downloadFile("/api/outgoing-invoices/shortages/export?" + exportQuery);
        showToast("Đã tải danh sách còn thiếu theo kỳ");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = exportLabel;
      }
    }
    if (action === "download-invoice-payment-control") {
      var controlLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang tạo hồ sơ…";
        await downloadFile(button.dataset.url);
        showToast("Đã tải Đề nghị thanh toán và Bảng tổng hợp giao nhận");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = controlLabel;
      }
      return;
    }
    if (action === "download-invoice-delivery-statement") {
      var statementLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang tạo bảng kê…";
        await downloadFile(button.dataset.url);
        showToast("Đã tải bảng kê giao hàng đối chiếu theo hóa đơn đỏ");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = statementLabel;
      }
      return;
    }
    if (action === "download-document") {
      var originalLabel = button.textContent;
      try {
        button.disabled = true;
        button.textContent = "Đang tải…";
        await downloadFile(button.dataset.url);
        showToast("Đã tải file về máy");
      } catch (error) {
        if (state.view === 'documents' && (button.dataset.url || '').indexOf('/api/export/invoices/') === 0) {
          state.outgoingActionError = {batchId:state.batchId, message:error.message};
          await fetchOutgoingReadiness();
        }
        showToast(error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = originalLabel;
      }
    }
    if (action === "view-invoice-receipt-summary") { showInvoiceReceiptSummary(button.dataset.id); return; }
    if (action === 'review-output-adjustment') {
      try {
        button.disabled = true;
        var adjustmentInvoice = (state.invoiceListing?.items || []).find(function(r) { return String(r.id) === button.dataset.id; });
        var adjustment = adjustmentInvoice?.adjustment_review;
        if (!adjustment || adjustment.confirmed) return;
        if (!await confirmOutputTaxAdjustment(adjustment)) return;
        await api('/api/invoice-workbench/output-adjustments/' + adjustmentInvoice.id + '/confirm-tax', {
          method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed:true,expected:adjustment.token})
        });
        await refreshSavedInvoiceMapping('output','');
        showToast('Đã đối chiếu cả hai hóa đơn điều chỉnh thuế. Không thay đổi kho.');
      } catch (error) { showToast(error.message,true); }
      finally { button.disabled = false; }
      return;
    }
    if (action === 'review-output-postings') {
      var outputQuery = '?from=' + encodeURIComponent(state.invoiceListing.date_from) + '&to=' + encodeURIComponent(state.invoiceListing.date_to) + '&status=' + encodeURIComponent(state.invoiceStatus) + '&line_filter=' + encodeURIComponent(state.invoiceLineFilter);
      if (state.invoiceListing.scope === 'pending') outputQuery += '&scope=pending';
      await window.TdpReceiptReview({direction:'output', api:api, query:outputQuery, esc:esc, money:stockMoney, qty:stockQty, date:dateVN,
        onPosted:async function(result, rows) {
          state.inventoryValuation = null; state.inventoryMonthClose = null; state.outgoingReadiness = null;
          state.invoiceLastPosted = {direction:'output', id:rows[0].id};
          state.invoiceStatus = 'all'; state.invoiceLineFilter = 'all';
          persistInvoiceWorkbenchFilters(); await loadInvoiceWorkbench(true); render();
          showToast('Đã ghi xuất kho ' + result.posted_count + ' hóa đơn' + (result.already_posted_count ? ' · ' + result.already_posted_count + ' hóa đơn đã ghi trước đó' : '') + '. Hóa đơn chưa đủ điều kiện vẫn được giữ lại.');
        }});
      return;
    }
    if (action === "create-msmi-receipt" || action === "review-input-receipts") {
      var receiptQuery = '?from=' + encodeURIComponent(state.invoiceListing.date_from) + '&to=' + encodeURIComponent(state.invoiceListing.date_to) + '&status=' + encodeURIComponent(state.invoiceStatus) + '&line_filter=' + encodeURIComponent(state.invoiceLineFilter);
      if (state.invoiceListing.scope === 'pending') receiptQuery += '&scope=pending';
      if (action === "create-msmi-receipt") receiptQuery += '&id=' + encodeURIComponent(button.dataset.id);
      await window.TdpReceiptReview({api:api, query:receiptQuery, esc:esc, money:stockMoney, qty:stockQty, date:dateVN,
        onPosted: async function(result, rows) {
          state.inventoryValuation = null; state.inventoryMonthClose = null;
          state.outgoingReadiness = null; state.outgoingPeriodShortages = null;
          state.invoiceLastPosted = {direction:'input', id:rows[0].id};
          state.invoiceLastPostedGroup = rows;
          state.invoiceStatus = 'all'; state.invoiceLineFilter = 'all';
          persistInvoiceWorkbenchFilters();
          try { await loadInvoiceWorkbench(true); render(); }
          catch(error) { showToast('Đã nhập kho. Chưa tải lại được bảng; hãy tải lại trang.', true); return; }
          showToast('Đã nhập ' + result.posted_count + ' hóa đơn' + (result.already_posted_count ? ' · ' + result.already_posted_count + ' hóa đơn đã nhập trước đó' : '') + '. Phần chưa đủ điều kiện tiếp tục chờ.');
        }});
      return;
    }
    if (action === "create-outgoing-drafts") {
      try {
        button.disabled = true;
        state.outgoingActionError = null;
        var drafts = await api("/api/outgoing-invoices/draft/" + state.batchId, { method: "POST" });
        state.outgoingShortages = [];
        state.outgoingInvoices = null;
        state.outgoingReadiness = null;
        state.outgoingPeriodShortages = null;
        await Promise.all([fetchOutgoingInvoices(), fetchOutgoingReadiness()]);
        showToast("Đã tạo " + drafts.drafts.length + " dự thảo · chưa ký/phát hành");
      } catch (error) {
        state.outgoingShortages = error.payload && Array.isArray(error.payload.shortages)
          ? error.payload.shortages : [];
        if (state.outgoingShortages.length) {
          state.documentDetailsOpen = true;
          state.outgoingReadiness = null;
          await fetchOutgoingReadiness();
          renderDocuments();
          showToast("Thiếu tồn vật tư cho " + state.outgoingShortages.length + " mã · xem danh sách bên dưới", true);
        } else {
          state.outgoingActionError = {batchId:state.batchId, message:error.message};
          await fetchOutgoingReadiness(); showToast(error.message, true);
        }
      }
    }
    if (action === "confirm-outgoing-issued") {
      try {
        var issueDraft = (state.outgoingInvoices || []).find(function(item) { return String(item.id) === button.dataset.id; });
        if (!issueDraft || !await recordIssuedInvoice(issueDraft)) return;
        state.outgoingInvoices = null;
        state.outgoingSubstitutionActions = null;
        state.operations = null;
        state.outgoingReadiness = null;
        state.outgoingPeriodShortages = null;
        state.invoicePaymentScope = null;
        await Promise.all([fetchOutgoingInvoices(), fetchOutgoingReadiness(), fetchOutgoingSubstitutions()]);
        showToast("Đã ghi nhận hóa đơn phát hành · hàng trong kho vẫn được giữ để chờ đối soát M-Invoice");
      } catch (error) { showToast(error.message, true); }
    }
    if (action === "cancel-outgoing-draft") {
      if (!window.confirm("Hủy dự thảo này và nhả phần tồn đang giữ?")) return;
      try {
        await api("/api/outgoing-invoices/" + button.dataset.id + "/cancel", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true })
        });
        state.outgoingInvoices = null;
        state.outgoingSubstitutionActions = null;
        state.operations = null;
        state.outgoingReadiness = null;
        state.outgoingPeriodShortages = null;
        await Promise.all([fetchOutgoingInvoices(), fetchOutgoingReadiness(), fetchOutgoingSubstitutions()]);
        showToast("Đã hủy dự thảo và nhả tồn khả dụng");
      } catch (error) { showToast(error.message, true); }
    }
    if (action === "approve-meal-plan") {
      jsonWrite("/api/kitchen/plans/" + button.dataset.id + "/approve", "POST", {}, "Đã duyệt kế hoạch xưởng cơm");
    }
    if (action === "prepare-print") {
      jsonWrite("/api/print/prepare/" + state.batchId, "POST", {}, "Đã chuẩn bị bộ chứng từ; cần duyệt trước khi in");
    }
    if (action === "approve-print") {
      if (!window.confirm("Duyệt phiếu giao A4 và bộ chứng từ khác theo khổ đã chọn để sẵn sàng in?")) return;
      jsonWrite("/api/print/approve/" + state.batchId, "POST", {}, "Đã duyệt bộ chứng từ in");
    }
    if (action === "run-print") {
      if (!window.confirm("Gửi phiếu giao A4 và chứng từ khác theo khổ đã chọn sang máy in Windows? Sau đó cần kiểm tra giấy ra thực tế.")) return;
      jsonWrite("/api/print/run/" + state.batchId, "POST", { dry_run: false }, "Đã gửi bộ chứng từ sang máy in");
    }
    if (action === "invalidate-print") {
      if (!window.confirm("Hủy bộ PDF in cũ để sửa lại dữ liệu nguồn? Bộ đã gửi sang máy in sẽ không thể hủy.")) return;
      jsonWrite("/api/print/invalidate/" + state.batchId, "POST", { confirmed: true }, "Đã hủy bộ in cũ; có thể sửa dữ liệu nguồn");
    }
    if (action === "sync-master") {
      try {
        button.disabled = true;
        await api("/api/master/sync", { method: "POST" });
        await loadData(state.batchId, true);
        showToast("Đã đồng bộ lại danh mục từ Em Thành.xlsx");
      } catch (error) { showToast(error.message, true); button.disabled = false; }
    }
  });

  document.body.addEventListener("click", function (event) {
    var button = event.target.closest('[data-action="close-modal"]');
    if (button) closeModal();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !backdrop.hidden) closeModal();
  });

  enhanceLocalizedDateInputs(document);
  new MutationObserver(function (records) {
    if (records.some(function(r) { return !r.target.closest?.('.invoice-mapping-cell, #msmiProductOptions, .invoice-lines-card tbody'); })) enhanceLocalizedDateInputs(document);
  }).observe(document.body, { childList: true, subtree: true });

  function openOrderWorksheet() {
    if (!window.TDPWorksheet || !state.data || !state.data.batch) return;
    var editable = state.data.batch.status !== 'approved';
    var definitions = [
      ['kitchen','Bếp',120], ['product_code','Mã hàng',120], ['product_name','Tên hàng',230],
      ['qty','SL đặt',95,1], ['unit','ĐVT',70], ['supplier','NCC',110],
      ['actual_received','SL nhận',100,1], ['damaged_qty','Hỏng',90,1], ['supplier_return_qty','Trả NCC',95,1],
      ['actual_delivered','SL giao',100,1], ['customer_return_qty','Khách trả',100,1],
      ['buy_price','Giá mua',110,1,1], ['sell_price','Giá bán',110,1,1], ['tax','Thuế',85],
      ['invoice_nature','Tính chất (1/2)',115], ['note','Ghi chú',220],
      ['cost','Tiền mua',130,1,1,1], ['revenue','Tiền bán',130,1,1,1],
      ['errors','Lỗi cần sửa',320,0,0,1], ['warnings','Cảnh báo',280,0,0,1]
    ];
    window.TDPWorksheet.open({ title: 'Đơn ngày ' + dateVN(state.data.batch.work_date),
      batchId: state.data.batch.id, editable: editable,
      rows: state.data.orders.slice().sort(function(a,b) { return Number(!!b.errors.length) - Number(!!a.errors.length) || a.id-b.id; }),
      columns: definitions.map(function(d) { return { key:d[0], title:d[1], width:d[2], numeric:!!d[3], money:!!d[4], editable:!d[5] }; }),
      onSaved: function(payload) { state.data.batch=payload.batch; state.data.orders=payload.orders; state.data.summary=payload.summary; },
      onClose: function() { loadData(state.batchId, true); },
      onImport: function() { excelInput.click(); }
    });
  }

  function openTableWorksheet(table) {
    if (table.closest('.invoice-lines-card')) { openInvoiceMappingFullscreen(); return; }
    if (!window.TDPWorksheet) return;
    if (table.closest('.inventory-nxt-scroll') && state.inventoryValuation) {
      var nxtFields=[['product_code','Mã hàng',120],['product_name','Tên hàng',230],['unit','ĐVT',70],
        ['opening_qty','Tồn đầu',105,1],['opening_value','Giá trị đầu',130,1,1],
        ['input_qty','Nhập',105,1],['input_value','Giá trị nhập',130,1,1],
        ['output_qty','Xuất',105,1],['output_value','Giá trị xuất',130,1,1],
        ['closing_qty','Tồn cuối',105,1],['closing_value','Giá trị tồn',130,1,1],
        ['average_unit_cost','Giá bình quân',135,1,1],['valuation_status','Đối chiếu',170]];
      window.TDPWorksheet.open({title:'Nhập – xuất – tồn · '+dateVN(state.inventoryFrom)+' → '+dateVN(state.inventoryTo),editable:false,
        rows:(state.inventoryValuation.items||[]).map(function(row){return Object.assign({},row,{valuation_status:row.valuation_status==='ok'?'Khớp':'Cần kiểm tra'});}),columns:nxtFields.map(function(d){return {key:d[0],title:d[1],width:d[2],numeric:!!d[3],money:!!d[4]};})});
      return;
    }
    // Expand merged cells into sheet coordinates, including multi-level headers.
    var matrix=[], issueRows=[], maxColumns=0;
    Array.from(table.rows).filter(function(row) { return !row.hidden && getComputedStyle(row).display !== 'none'; }).forEach(function(row,r) {
      matrix[r]=matrix[r]||[]; var c=0;
      // Invoice data-issue denotes a blocking source/mapping validation failure.
      // Warning/status badge colors alone are not row errors.
      issueRows[r]=row.dataset.error==='1' || row.dataset.issue==='1' || !!row.querySelector('.field-error') || row.matches('.row-error,.has-error');
      Array.from(row.cells).forEach(function(cell) {
        while(matrix[r][c] !== undefined) c++;
        var input=cell.querySelector('input,select');
        var value=input ? input.value : cell.innerText.trim();
        matrix[r][c]=value;
        for(var y=0;y<cell.rowSpan;y++) for(var x=0;x<cell.colSpan;x++) {
          matrix[r+y]=matrix[r+y]||[];
          if(y||x) matrix[r+y][c+x]='';
        }
        c+=cell.colSpan;
      });
      maxColumns=Math.max(maxColumns,c,matrix[r].length);
    });
    if(!matrix.length) return;
    var headings=matrix.shift(); issueRows.shift();
    var title=document.getElementById('pageTitle');
    window.TDPWorksheet.open({ title:((table.caption && table.caption.innerText) || (title && title.innerText) || 'Bảng dữ liệu')+' · phần đang hiển thị', editable:false,
      columns:Array.from({length:maxColumns},function(_,c) { return { key:'c'+c,title:headings[c]||String.fromCharCode(65+c),width:c===1?230:150 }; }),
      rows:matrix.map(function(row,r) { var obj={worksheet_error:issueRows[r]}; row.forEach(function(value,c) { obj['c'+c]=value; }); return obj; }) });
  }

  var invoiceMappingFullscreen = false;
  var invoiceMappingPreviousOverflow = '';
  function closeInvoiceMappingFullscreen() {
    closeMsmiProductOptions();
    invoiceMappingFullscreen = false;
    content.classList.remove('invoice-mapping-fullscreen');
    document.body.style.overflow = invoiceMappingPreviousOverflow;
    var bar = content.querySelector('.invoice-mapping-fullscreen-bar');
    // Search and its reopen button are moved into the fullscreen bar. Keep
    // those live controls when removing the bar, including any typed query.
    if (bar && mappingSearch && bar.contains(mappingSearch.element)) {
      var card = bar.closest('.invoice-lines-card');
      card.insertBefore(mappingSearch.element, card.querySelector('.invoice-lines-scroll'));
    }
    if (bar) bar.remove();
  }
  function syncInvoiceMappingFullscreen() {
    if (!invoiceMappingFullscreen) return;
    var card = content.querySelector('.invoice-lines-card');
    if (!card) {
      // A slow filter refresh temporarily replaces the card with its loader.
      if (state.view !== 'msmi') closeInvoiceMappingFullscreen();
      return;
    }
    if (card.querySelector('.invoice-mapping-fullscreen-bar')) return;
    var bar = document.createElement('div'); bar.className = 'invoice-mapping-fullscreen-bar';
    var help = document.createElement('span');
    help.textContent = state.invoiceDirection === 'input' ? 'Hóa đơn đầu vào · Ghép mã / Quy đổi' : 'Hóa đơn đầu ra · Ghép mã';
    var close = document.createElement('button'); close.type = 'button'; close.className = 'btn btn-outline';
    close.textContent = 'Đóng toàn màn hình'; close.onclick = closeInvoiceMappingFullscreen;
    bar.appendChild(help); bar.appendChild(close); card.insertBefore(bar, card.firstChild);
  }
  function openInvoiceMappingFullscreen() {
    if (!invoiceMappingFullscreen) invoiceMappingPreviousOverflow = document.body.style.overflow;
    invoiceMappingFullscreen = true;
    content.classList.add('invoice-mapping-fullscreen');
    document.body.style.overflow = 'hidden';
    syncInvoiceMappingFullscreen();
  }
  document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && invoiceMappingFullscreen && backdrop.hidden && !document.querySelector('dialog[open]')) closeInvoiceMappingFullscreen();
  });
  var sheetEnhanceTimer;
  var mappingSearch = null;
  function enhanceMappingSearch() {
    var card = content.querySelector('.invoice-lines-card');
    if (mappingSearch && (!card || !card.contains(mappingSearch.element))) {
      mappingSearch.dispose(); mappingSearch = null;
    }
    if (!card) return;
    var fullscreenBar = card.querySelector('.invoice-mapping-fullscreen-bar');
    if (mappingSearch) {
      if (fullscreenBar && mappingSearch.element.parentNode !== fullscreenBar) fullscreenBar.insertBefore(mappingSearch.element, fullscreenBar.lastChild);
      return;
    }
    var selectedCell = null;
    mappingSearch = window.TDPTableSearch({
      scope: 'Trong các dòng đúng bộ lọc ngày / trạng thái',
      active: function () { return !window.TDPWorksheet?.isOpen() && backdrop.hidden && !document.querySelector('dialog[open]'); },
      cells: function () {
        if (invoiceVirtual) {
          var invoices = new Map((state.invoiceListing.items || []).map(r=>[r.id,r]));
          return state.invoiceListing.lines.map(function(r) { var inv=invoices.get(r.invoice_id)||{};
            var id=r.id==null?'empty-'+r.invoice_id:r.id;
            return {key:String(id),id:id,values:[r.source_item_name,r.product_code,r.product_name,r.source_item_code,r.source_unit,r.product_unit,r.qty,stockQty(r.qty),r.amount,stockMoney(r.amount),inv.invoice_number,inv.invoice_series,inv.seller_name,inv.buyer_name,dateVN(inv.invoice_date)]}; });
        }
        var cells = [];
        card.querySelectorAll('.invoice-lines-scroll tbody tr').forEach(function (row, r) {
          Array.from(row.cells).slice(0, state.invoiceDirection === 'input' ? -1 : undefined).forEach(function (cell, c) {
            var copy = cell.cloneNode(true);
            copy.querySelectorAll('button,input,select').forEach(function (el) { el.remove(); });
            var values = [copy.textContent];
            cell.querySelectorAll('input').forEach(function (el) { values.push(el.value); });
            cells.push({ key: r + ':' + c, element: cell, values: values });
          });
        });
        return cells;
      },
      clear: function () { if (selectedCell) selectedCell.classList.remove('tdp-search-hit'); selectedCell = null; },
      select: function (hit) {
        selectedCell = invoiceVirtual ? invoiceVirtual.reveal(hit.id)?.cells[state.invoiceDirection === 'input' ? 4 : 3] : hit.element;
        if (!selectedCell) return;
        selectedCell.classList.add('tdp-search-hit');
        var scroll = card.querySelector('.invoice-lines-scroll');
        var head = scroll.querySelector('thead').getBoundingClientRect().height;
        scroll.scrollTop += selectedCell.getBoundingClientRect().top - scroll.getBoundingClientRect().top - head - 12;
        if (selectedCell.cellIndex > 0) {
          var left = selectedCell.parentNode.cells[0].getBoundingClientRect().width;
          scroll.scrollLeft += selectedCell.getBoundingClientRect().left - scroll.getBoundingClientRect().left - left - 12;
        }
      }
    });
    if (fullscreenBar) fullscreenBar.insertBefore(mappingSearch.element, fullscreenBar.lastChild);
    else card.insertBefore(mappingSearch.element, card.querySelector('.invoice-lines-scroll'));
  }
  function addWorksheetButtons() {
    syncInvoiceMappingFullscreen();
    enhanceMappingSearch();
    content.querySelectorAll('table').forEach(function(table) {
      if(table.closest('.inventory-nxt-scroll, .invoice-amount-reviews')) return;
      if(table.dataset.worksheetReady) return;
      table.dataset.worksheetReady='1';
      var wrap=table.closest('.table-wrap,.invoice-lines-scroll')||table;
      var button=document.createElement('button'); button.type='button'; button.className='tdp-open-sheet';
      var isOrders=Boolean(table.closest('#orderTable'));
      var isCatalog=Boolean(table.closest('#catalogProducts'));
      var isMapping=Boolean(table.closest('.invoice-lines-card'));
      button.textContent=isCatalog?'Mở bảng Excel toàn màn hình · sửa toàn bộ danh mục':isMapping?(state.invoiceDirection === 'input' ? 'Ghép mã / Quy đổi' : 'Ghép mã') + ' · toàn màn hình':isOrders?'Mở bảng Excel · tự lưu':'Xem bảng Excel toàn màn hình · chỉ xem';
      button.onclick=function(){if(isCatalog) openCatalogWorksheet(); else if(isOrders) openOrderWorksheet(); else openTableWorksheet(table);};
      var head = wrap.parentNode.querySelector(':scope > .card-head');
      if (isMapping && mappingSearch) mappingSearch.element.appendChild(button);
      else if (head) head.appendChild(button);
      else wrap.parentNode.insertBefore(button,wrap);
    });
  }
  new MutationObserver(function(records) { if(records.every(function(r) { return r.target.closest?.('.invoice-mapping-cell, #msmiProductOptions, .invoice-lines-card tbody'); })) return; clearTimeout(sheetEnhanceTimer); sheetEnhanceTimer=setTimeout(addWorksheetButtons,50); })
    .observe(content,{childList:true,subtree:true});
  content.addEventListener('click',function(event) {
    if(event.target.closest('[data-action="view-invoice-unit-totals"]')) { showInvoiceUnitTotals(); return; }
    if(event.target.closest('[data-action="view-inventory-unit-totals"]')) { showInventoryUnitTotals(); return; }
    if(event.target.closest('[data-action="view-inventory-worksheet"]')) { openTableWorksheet(content.querySelector('.inventory-nxt-scroll table')); return; }
    var button=event.target.closest('[data-action="bulk-edit-orders"]');
    if(button && window.TDPWorksheet) {event.preventDefault();event.stopImmediatePropagation();openOrderWorksheet();}
  },true);
  loadData(null);
})();
