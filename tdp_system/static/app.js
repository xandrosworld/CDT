(function () {
  "use strict";

  var todayIso = new Date().toISOString().slice(0, 10);
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
    invoiceLastPosted: null,
    invoiceWorkbenchRequestSerial: 0,
    invoiceInputRows: [],
    invoiceOutputRows: [],
    invoiceDirection: storedInvoiceFilters.direction === "output" ? "output" : "input",
    invoiceFrom: storedInvoiceFilters.date_from || todayIso.slice(0, 7) + "-01",
    invoiceTo: storedInvoiceFilters.date_to || todayIso,
    invoiceStatus: ["all", "needs_mapping", "ready", "posted", "error", "reversed", "not_inventory"].indexOf(storedInvoiceFilters.status) >= 0 ? storedInvoiceFilters.status : "all",
    invoiceLineFilter: storedInvoiceFilters.line_filter || "all",
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
    documentDetailsOpen: false,
    outgoingPeriodShortages: null,
    outgoingShortageFrom: todayIso.slice(0, 7) + "-01",
    outgoingShortageTo: todayIso,
    outgoingShortageContractor: "",
    outgoingShortageLoading: false,
    opsDate: new Date().toISOString().slice(0, 10),
    opsMonth: new Date().toISOString().slice(0, 7),
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
      var wrapper = document.createElement("span");
      wrapper.className = "localized-date-control";
      var display = document.createElement("input");
      display.type = "text";
      display.className = "localized-date-display";
      display.placeholder = kind === "month" ? "mm/yyyy" : "dd/mm/yyyy";
      display.inputMode = "numeric";
      display.autocomplete = "off";
      display.required = nativeInput.required;
      display.setAttribute("aria-label", nativeInput.getAttribute("aria-label") || display.placeholder);
      display.value = localizedTemporalText(nativeInput.value, kind);
      nativeInput.parentNode.insertBefore(wrapper, nativeInput);
      wrapper.appendChild(display);
      wrapper.appendChild(nativeInput);
      nativeInput.classList.add("localized-date-native");
      nativeInput.tabIndex = -1;
      var icon = document.createElement("span");
      icon.className = "localized-date-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = "▦";
      wrapper.appendChild(icon);

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
        var changed = nativeInput.value !== parsed;
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
        display.value = localizedTemporalText(nativeInput.value, kind);
        display.setCustomValidity("");
      });
      if (nativeInput.form) {
        nativeInput.form.addEventListener("reset", function () {
          setTimeout(function () { display.value = localizedTemporalText(nativeInput.value, kind); }, 0);
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
    var code = String(value).toUpperCase();
    if (code === "KKKNT" || code === "KCT") return code;
    return Math.round(n(value) * 100) + "%";
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
    if (status === 404 || /requested URL was not found/i.test(text)) {
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
      if (state.view === "inventory") await Promise.all([
        loadInventoryValuation(true), loadInventoryMonthClose(true), loadBkDocuments(true)
      ]);
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
    var period = (state.inventoryFrom || state.opsMonth || todayIso).slice(0, 7);
    var requestSerial = ++state.inventoryMonthCloseRequestSerial;
    try {
      var result = await api(
        "/api/inventory/month-close/preview?period=" + encodeURIComponent(period)
      );
      if (requestSerial !== state.inventoryMonthCloseRequestSerial) return;
      state.inventoryMonthClose = result;
      if (!silent && state.view === "inventory") renderInventory();
    } catch (error) {
      if (requestSerial !== state.inventoryMonthCloseRequestSerial) return;
      state.inventoryMonthClose = { error: error.message, period: period, issues: [] };
      if (!silent && state.view === "inventory") renderInventory();
    }
  }

  async function refreshInventoryMonthWorkspace(message) {
    state.inventoryValuation = null;
    state.inventoryMonthClose = null;
    await Promise.all([loadInventoryValuation(true), loadInventoryMonthClose(true)]);
    renderInventory();
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
        line_filter: state.invoiceLineFilter
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
        api("/api/invoice-workbench/invoices" + query + "&status=" + encodeURIComponent(state.invoiceStatus) + "&line_filter=" + encodeURIComponent(state.invoiceLineFilter))
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
          " hóa đơn đã có" + (synced.more_history ? " · bấm tiếp để tải phần còn lại" : ""));
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
    if (["inventory", "msmi", "printing"].indexOf(view) >= 0 && !state.operations) {
      loadOperations();
      return;
    }
    if (view === "inventory" && !state.inventoryValuation) {
      loadInventoryValuation();
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
      return '<tr><td>' + item.source_row + '</td><td><strong>' + esc(item.resolved_code || item.source_code) +
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
      return '<tr><td>' + item.source_row + '</td><td><strong>' + esc(item.product_code) +
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
      return '<tr><td>' + dateVN(item.work_date) + '</td><td><strong>' + esc(item.kitchen) +
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
      return '<tr><td><strong>' + esc(item.product_code || "—") + '</strong><div class="muted">' +
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
      return '<tr><td>' + item.sourceRow + '</td><td>' + dateVN(item.documentDate) +
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
      return '<tr><td>' + item.source_row + '</td><td>' + dateVN(item.purchase_date) +
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
        '</strong><div class="muted">' + esc(item.product_code || source.product_code || "Mã dòng " + item.order_id) +
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
        '<div class="form-field"><label>Ngày nhận tiền</label><input name="payment_date" type="date" value="', new Date().toISOString().slice(0, 10), '" required></div>',
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

  function outgoingReadinessHtml() {
    var readiness = state.outgoingReadiness;
    if (readiness === null) {
      return '<div class="card fade-in invoice-readiness"><div class="card-body"><div class="loading-inline"><div class="spinner"></div><strong>Đang đối chiếu tồn vật tư hàng hóa…</strong></div></div></div>';
    }
    if (readiness.error) {
      return '<div class="card fade-in invoice-readiness"><div class="card-body"><div class="error-summary">Chưa tính được khả năng xuất: ' +
        esc(readiness.error) + '</div><div class="form-actions"><button class="btn btn-outline" data-action="refresh-outgoing-readiness">Thử lại</button></div></div></div>';
    }
    var rows = (readiness.rows || []).map(function (item) {
      var status = n(item.pending_qty) > 0
        ? '<span class="tag tag-warn">Còn chờ</span>'
        : n(item.invoiceable_qty) > 0
          ? '<span class="tag tag-ok">Lập được</span>'
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
      return '<tr><td><strong>' + esc(item.contractor) + '</strong></td><td class="num-cell">' +
        num(item.demand_qty) + '</td><td class="num-cell">' + num(item.drafted_qty) +
        '</td><td class="num-cell">' + num(item.issued_qty) +
        '</td><td class="num-cell invoice-ready-qty">' + num(item.invoiceable_qty) + '<div class="muted">' + money(item.invoiceable_value) + '</div>' +
        '</td><td class="num-cell invoice-wait-qty">' + num(item.pending_qty) + '<div class="muted">' + money(item.pending_value) + '</div></td></tr>';
    }).join("");
    var allReady = n(readiness.pending_qty) <= 0;
    return html([
      '<div class="card fade-in invoice-readiness"><div class="card-head"><div><h3>Được xuất và chưa được xuất theo nhà thầu</h3>',
      '<p>Xem số tổng trước; chỉ mở chi tiết mặt hàng khi cần kiểm tra.</p></div>',
      '<button class="btn btn-small btn-outline" data-action="refresh-outgoing-readiness">Tính lại</button></div>',
      '<div class="card-body"><div class="readiness-totals"><div><span>Tổng cần lập</span><strong>', num(readiness.demand_qty),
      '</strong></div><div><span>Đã dự thảo</span><strong>', num(readiness.drafted_qty),
      '</strong></div><div><span>Đã phát hành</span><strong>', num(readiness.issued_qty),
      '</strong></div><div class="ready"><span>Có thể lập bây giờ</span><strong>', num(readiness.invoiceable_qty),
      '</strong><span>', money(readiness.invoiceable_value), '</span></div><div class="waiting"><span>Còn chờ hóa đơn đầu vào</span><strong>', num(readiness.pending_qty),
      '</strong><span>', money(readiness.pending_value), '</span></div></div>',
      allReady
        ? '<div class="ok-summary" style="margin-top:14px">Đã đủ đầu vào cho toàn bộ phần còn lại.</div>'
        : '<div class="warning-summary" style="margin-top:14px">Có thể lập phần màu xanh trước. Phần còn chờ sẽ giữ lại để tính tiếp khi có hóa đơn đầu vào.</div>',
      '</div><div class="table-wrap"><table><thead><tr><th>Nhà thầu</th><th>Tổng cần</th><th>Đã dự thảo</th><th>Đã phát hành</th><th>Có thể lập</th><th>Còn thiếu</th></tr></thead><tbody>',
      contractorRows || '<tr><td colspan="6"><div class="empty">Không có nhà thầu cần lập hóa đơn trong đơn hàng này.</div></td></tr>',
      '</tbody></table></div><details class="readiness-line-details"><summary>Xem chi tiết từng mặt hàng</summary><div class="table-wrap"><table><thead><tr><th>Nhà thầu / bếp</th><th>Mặt hàng</th><th>Khách đã chốt</th>',
      '<th>Đã dự thảo</th><th>Đã phát hành</th><th>Có thể lập bây giờ</th><th>Còn chờ đầu vào</th><th>Trạng thái</th></tr></thead><tbody>',
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
      esc(statementUrl), '">Tải Bảng tổng hợp giao nhận</button><button class="btn btn-outline" data-action="download-invoice-payment-control" data-url="',
      esc(downloadUrl), '">Tải Đề nghị thanh toán + bảng kê</button><button class="btn btn-outline" data-action="preview-payment-documents">Xem chứng từ / In</button></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Ngày HĐ</th><th>Ký hiệu / số HĐ</th><th>Trước thuế</th><th>Thuế</th><th>Tổng</th><th>Nguồn xác minh</th></tr></thead><tbody>',
      invoices, '</tbody></table></div></div>'
    ]);
  }

  function renderDocuments() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có dữ liệu chứng từ", "Nạp và hoàn thiện đơn trước khi tạo bảng kê, biên nhận và file hóa đơn.");
      return;
    }
    if (state.outgoingInvoices === null) setTimeout(fetchOutgoingInvoices, 0);
    if (state.outgoingReadiness === null && !state.outgoingReadinessLoading) setTimeout(fetchOutgoingReadiness, 0);
    if (state.documentDetailsOpen && state.outgoingSubstitutionActions === null && !state.outgoingSubstitutionLoading) {
      setTimeout(fetchOutgoingSubstitutions, 0);
    }
    var paymentPeriodFrom = d.batch.work_date.slice(0, 7) + "-01";
    var issuedContractors = Array.from(new Set((state.outgoingInvoices || []).filter(function (item) {
      var issuedDate = item.issued_invoice_date || "";
      return item.status === "issued" && issuedDate >= paymentPeriodFrom && issuedDate <= d.batch.work_date;
    }).map(function (item) { return item.contractor; }))).sort();
    var contractorOptions = issuedContractors.length
      ? issuedContractors.map(function (code) {
        return '<option value="' + esc(code) + '">' + esc(code) + '</option>';
      }).join("")
      : '<option value="">' + (state.outgoingInvoices === null
        ? 'Đang kiểm tra hóa đơn…' : 'Chưa có hóa đơn đã phát hành trong kỳ') + '</option>';
    var shortageContractors = Array.from(new Set(d.orders.map(function (item) {
      return (item.contractor || "").trim();
    }).filter(Boolean))).sort();
    var currentInvoices = (state.outgoingInvoices || []).filter(function (item) {
      return item.batch_id === state.batchId;
    });
    var outgoingRows = currentInvoices.map(function (item) {
      var statusText = item.status === "issued" ? "Đã phát hành" : item.status === "cancelled" ? "Đã hủy" : "Dự thảo";
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
      return '<tr><td><strong>' + esc(item.contractor) + '</strong></td><td>' + dateVN(item.invoice_date) +
        '</td><td class="num-cell">' + money(item.subtotal) + '</td><td class="num-cell">' + money(item.tax_amount) +
        '</td><td class="num-cell"><strong>' + money(item.total_amount) + '</strong></td><td><span class="tag ' +
        statusClass + '">' + statusText + '</span>' +
        (item.status === "issued" ? '<div class="muted">' + esc(item.issued_invoice_series || "") + ' ' +
          esc(item.issued_invoice_number || "") + ' · ' + dateVN(item.issued_invoice_date || item.invoice_date) + '</div>' : '') +
        '</td><td>' + actions + '</td></tr>';
    }).join("");
    var minvoiceForms = (state.outgoingInvoices || []).filter(function (item) {
      return item.batch_id === state.batchId && item.status === "draft";
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
    var activeDrafts = currentInvoices.filter(function (item) { return item.status === "draft"; });
    var invoiceFileAction = state.outgoingInvoices === null
      ? '<button class="btn btn-primary" disabled>Đang kiểm tra…</button>'
      : d.batch.status !== "approved"
        ? '<button class="btn btn-primary" disabled>Cần duyệt đơn trước</button>'
        : activeDrafts.length
          ? '<a class="btn btn-primary" href="' + exportUrl("invoices") + '">Tải ZIP vòng này</a>'
          : '<button class="btn btn-primary" data-action="create-outgoing-drafts">Tạo file tải hóa đơn</button>';
    var detailsHtml = state.documentDetailsOpen ? html([
      '<div class="document-detail-panel fade-in">', shortagePanel,
      outgoingSubstitutionHtml(), outgoingPeriodShortagesHtml(shortageContractors),
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Dự thảo hóa đơn đầu ra</h3>',
      '<p>Chỉ ghi nhận phát hành sau khi người dùng đã kiểm tra trên M-Invoice.</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Nhà thầu</th><th>Ngày</th><th>Trước thuế</th><th>Thuế</th><th>Tổng</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>',
      outgoingRows || '<tr><td colspan="7"><div class="empty">' + (state.outgoingInvoices === null ? 'Đang kiểm tra…' : 'Chưa có dự thảo đầu ra.') + '</div></td></tr>',
      '</tbody></table></div></div>',
      minvoiceForms ? '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Lưu bản nháp M-Invoice</h3><p>Kiểm tra thông tin người mua trước khi lưu nháp chờ ký.</p></div></div>' + minvoiceForms + '</div>' : '',
      '</div>'
    ]) : '';
    content.innerHTML = html([
      outgoingReadinessHtml(),
      '<div class="document-primary-grid fade-in"><section class="document-primary-card"><div class="document-primary-icon">13</div>',
      '<div><h3>File tải hóa đơn</h3><p>File 13 cột, tách riêng từng nhà thầu và nhóm thuế.</p></div><div class="document-primary-action">',
      invoiceFileAction, '</div></section>',
      '<section class="document-primary-card"><div class="document-primary-icon">KÊ</div><div><h3>Bảng kê từ hóa đơn đỏ</h3>',
      '<p>Chọn nhà thầu để lấy đúng các hóa đơn Thành Đạt Phát đã phát hành.</p>',
      '<form id="paymentRequestForm" class="document-contractor-form"><select name="contractor" class="select">', contractorOptions,
      '</select><button class="btn btn-primary" type="submit" ', issuedContractors.length ? '' : 'disabled',
      '>Xem và tải bảng kê</button></form></div></section></div>',
      invoicePaymentScopeHtml(),
      '<div id="paymentDocumentPreview"></div>',
      '<div class="card"><div class="card-head"><div><h3>Bảng kê mua hàng và biên nhận</h3><p>Xem đúng hồ sơ người bán; thiếu hoặc trùng CCCD vẫn bị chặn.</p></div><button class="btn btn-outline" data-action="preview-purchase-documents">Xem bảng kê / biên nhận</button></div><div id="purchaseDocumentPreview"></div></div>',
      '<div class="secondary-action-row"><button class="btn btn-outline" data-action="toggle-document-details">',
      state.documentDetailsOpen ? 'Ẩn xử lý chi tiết' : 'Xử lý chi tiết hóa đơn', '</button></div>',
      detailsHtml
    ]);
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
      stockMoney(close.total_value) + '</strong></span></div>' + replacementWarning + movementWarning + unpostedWarning + issueHtml +
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
    state.inventoryDetailsOpen = true;
    await Promise.all([loadInventoryValuation(true), loadInventoryMonthClose(true)]);
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
    var o = state.operations;
    if (!o) { loadOperations(); return; }
    var valuation = state.inventoryValuation;
    if (!valuation) { loadInventoryValuation(); return; }
    var items = valuation.items || [];
    var totals = items.reduce(function (result, item) {
      ["opening_qty", "opening_value", "input_qty", "input_value", "output_qty",
        "output_value", "closing_qty", "closing_value"].forEach(function (field) {
        result[field] += n(item[field]);
      });
      return result;
    }, {
      opening_qty: 0, opening_value: 0, input_qty: 0, input_value: 0,
      output_qty: 0, output_value: 0, closing_qty: 0, closing_value: 0
    });
    var rows = items.map(function (item, index) {
      var status = item.valuation_status === "ok"
        ? '<span class="tag tag-ok">Khớp</span>'
        : '<span class="tag tag-warn">Cần kiểm tra</span>';
      return '<tr><td>' + (index + 1) + '</td><td><strong>' + esc(item.product_code) +
        '</strong></td><td>' + esc(item.product_name) + '</td><td>' + esc(item.unit) +
        '</td><td class="num-cell">' + stockQty(item.opening_qty) + '</td><td class="num-cell">' +
        stockMoney(item.opening_value) + '</td><td class="num-cell">' + stockQty(item.input_qty) +
        '</td><td class="num-cell">' + stockMoney(item.input_value) + '</td><td class="num-cell">' +
        stockQty(item.output_qty) + '</td><td class="num-cell">' + stockMoney(item.output_value) +
        '</td><td class="num-cell"><strong>' + stockQty(item.closing_qty) + '</strong></td><td class="num-cell"><strong>' +
        stockMoney(item.closing_value) + '</strong></td><td class="num-cell">' +
        stockMoney(item.average_unit_cost) + '</td><td>' + status + '</td></tr>';
    }).join("");
    var exportQuery = "?from=" + encodeURIComponent(state.inventoryFrom) +
      "&to=" + encodeURIComponent(state.inventoryTo);
    var errorPanel = valuation.error
      ? '<div class="code-note"><strong>Chưa dựng được sổ kỳ này:</strong> ' + esc(valuation.error) + '</div>'
      : '';
    var detailsHtml = state.inventoryDetailsOpen ? html([
      '<div class="inventory-detail-panel fade-in">',
      '<div class="toolbar"><div class="toolbar-left"><div><strong>Bảng kê mua vào không có hóa đơn</strong>',
      '<div class="muted">Tải mẫu, sửa dữ liệu rồi chọn lại file để kiểm tra.</div></div></div><div class="compact-controls">',
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/bk-import/template">Tải mẫu trắng</button>',
      state.batchId ? '<button class="btn btn-outline" data-action="download-document" data-url="/api/bk-import/template?batch_id=' + encodeURIComponent(state.batchId) + '">Tải theo đơn đang chọn</button>' : '',
      '<button class="btn btn-primary" data-action="choose-bk-workbook">Chọn file đã sửa</button></div></div>',
      errorPanel,
      '<div class="stats-grid">',
      statCard("Mặt hàng phát sinh", stockQty(items.length), dateVN(state.inventoryFrom) + " → " + dateVN(state.inventoryTo), "▦"),
      statCard("Tổng lượng tồn cuối", stockQuantitySummary(items, "closing_qty"), "Cộng riêng từng ĐVT · Tồn đầu + Nhập − Xuất", "∑"),
      statCard("Giá trị tồn đầu", stockMoney(totals.opening_value), "Kỳ tồn: " + esc(valuation.opening_period || "chưa có"), "Σ"),
      statCard("Nhập / Xuất", stockMoney(totals.input_value) + " / " + stockMoney(totals.output_value), "Theo sổ vật tư", "⇄"),
      statCard("Giá trị tồn cuối", stockMoney(totals.closing_value), "Tồn đầu + Nhập − Xuất", "✓"),
      '</div><div class="section-grid"><div class="card"><div class="card-head"><div><h3>Nhập tồn đầu kỳ</h3><p>Có thể nhập từng mã hoặc nạp Excel</p></div></div><div class="card-body">',
      '<form id="openingForm" class="payment-grid"><div class="form-field"><label>Kỳ</label><input name="period" type="month" value="', esc(state.opsMonth), '" required></div>',
      '<div class="form-field"><label>Mã hàng</label><input name="product_code" required></div>',
      '<div class="form-field"><label>Số lượng</label><input name="qty" type="number" step="0.01" required></div>',
      '<div class="form-field"><label>Đơn giá vốn</label><input name="unit_cost" type="number" min="0"></div>',
      '<button class="btn btn-primary" type="submit">Lưu tồn đầu</button>',
      '<button class="btn btn-outline" type="button" data-action="choose-opening-workbook">Nạp Excel tồn đầu kỳ</button></form></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Điều chỉnh dùng nội bộ</h3><p>Có lưu lịch sử, không thay đổi báo cáo hóa đơn</p></div></div><div class="card-body">',
      '<form id="inventoryAdjustmentForm" class="payment-grid"><div class="form-field"><label>Ngày</label><input name="txn_date" type="date" value="', esc(state.opsDate), '" required></div>',
      '<div class="form-field"><label>Mã hàng</label><input name="product_code" required></div>',
      '<div class="form-field"><label>Số lượng (+ tăng / − giảm)</label><input name="qty" type="number" step="0.01" required></div>',
      '<div class="form-field"><label>Lý do</label><input name="note" required></div>',
      '<button class="btn btn-outline" type="submit">Ghi điều chỉnh</button></form></div></div></div>',
      openingImportPreviewHtml(), bkImportPreviewHtml(), bkDocumentsHtml(),
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Chi tiết Nhập – Xuất – Tồn</h3><p>',
      dateVN(state.inventoryFrom), ' → ', dateVN(state.inventoryTo), '</p></div></div>',
      '<div class="table-wrap invoice-lines-scroll"><table><thead><tr><th>STT</th><th>Mã</th><th>Tên hàng</th><th>Đơn vị</th><th>Tồn đầu kỳ</th><th>Giá trị đầu kỳ</th><th>Số nhập</th><th>Giá trị nhập</th><th>Số xuất</th><th>Giá trị xuất</th><th>Tồn cuối</th><th>Giá trị tồn cuối</th><th>Giá bình quân</th><th>Đối chiếu</th></tr></thead><tbody>',
      rows || '<tr><td colspan="14"><div class="empty">Kỳ này chưa có tồn đầu hoặc phát sinh đã ghi sổ.</div></td></tr>',
      '</tbody><tfoot><tr class="table-total-row"><td colspan="4">TỔNG</td><td class="num-cell">',
      esc(stockQuantitySummary(items, "opening_qty")), '</td><td class="num-cell">', stockMoney(totals.opening_value),
      '</td><td class="num-cell">', esc(stockQuantitySummary(items, "input_qty")), '</td><td class="num-cell">',
      stockMoney(totals.input_value), '</td><td class="num-cell">', esc(stockQuantitySummary(items, "output_qty")),
      '</td><td class="num-cell">', stockMoney(totals.output_value), '</td><td class="num-cell">',
      esc(stockQuantitySummary(items, "closing_qty")), '</td><td class="num-cell">', stockMoney(totals.closing_value),
      '</td><td colspan="2"></td></tr></tfoot></table></div></div></div>'
    ]) : '';
    content.innerHTML = html([
      inventoryTraceHtml(),
      '<div class="card inventory-primary-card fade-in"><div class="inventory-primary-range"><div><h3>Báo cáo vật tư hàng hóa</h3>',
      '<p>Sổ kho hóa đơn · xem bảng nhập – xuất – tồn bên dưới hoặc tải Excel theo cùng khoảng ngày.</p></div><div class="compact-controls">',
      '<label>Từ ngày <input id="inventoryFrom" class="input-date" type="date" value="', esc(state.inventoryFrom), '"></label>',
      '<label>Đến ngày <input id="inventoryTo" class="input-date" type="date" value="', esc(state.inventoryTo), '"></label>',
      '</div></div><div class="inventory-export-grid">',
      '<button class="btn btn-primary" data-action="download-document" data-url="/api/invoice-valuation/export', exportQuery, '">Tải đủ 4 file ZIP</button>',
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/invoice-valuation/export/opening', exportQuery, '">Tồn đầu kỳ</button>',
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/invoice-valuation/export/input', exportQuery, '">Nhập</button>',
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/invoice-valuation/export/output', exportQuery, '">Xuất</button>',
      '<button class="btn btn-outline" data-action="download-document" data-url="/api/invoice-valuation/export/nxt', exportQuery, '">Nhập – xuất – tồn</button>',
      '</div>', inventoryMonthCloseHtml(state.inventoryMonthClose),
      '<div class="inventory-detail-toggle"><button class="btn btn-outline" data-action="toggle-inventory-details">',
      state.inventoryDetailsOpen ? 'Ẩn chi tiết' : 'Xem chi tiết và nhập dữ liệu', '</button></div></div>',
      detailsHtml
    ]);
  }

  function renderMsmi() {
    if (!state.invoiceWorkbench || !state.invoiceListing) { loadInvoiceWorkbench(); return; }
    content.innerHTML = window.TdpInvoiceWorkbench(state, {esc:esc, num:stockQty, money:stockMoney, dateVN:dateVN});
  }

  async function loadMsmiProductOptions(input) {
    var productList = document.getElementById("msmiProductOptions");
    if (!productList || !input) return;
    var term = input.value.trim() || input.dataset.sourceName || "";
    if (term.length < 2) return;
    try {
      var result = await api("/api/products/search?q=" + encodeURIComponent(term));
      productList.innerHTML = (result.items || []).map(function (product) {
        var label = product.code + " · " + product.name;
        if (product.invoice_name && product.invoice_name !== product.name) label += " · Tên trên hóa đơn: " + product.invoice_name;
        return '<option value="' + esc(product.code) + '" label="' + esc(label) + '"></option>';
      }).join("");
    } catch (error) {
      showToast(error.message, true);
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
      issue_date: new Date().toISOString().slice(0, 10)
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
      '<button class="btn btn-outline" data-action="download-selected-documents" ', selectedCount ? '' : 'disabled', '>Tải file đã chọn</button></div>',
      state.printingDocument === 'deliveries' ? '<label class="print-customer-filter">Khách hàng / bếp <select id="printingCustomer"><option value="">Tất cả bếp</option>' + state.data.master.kitchens.map(function(k) { return '<option value="' + esc(k.code) + '" ' + (state.printingCustomer === k.code ? 'selected' : '') + '>' + esc(k.name || k.code) + '</option>'; }).join('') + '</select></label>' : '', '</div>',
      '<div class="table-wrap print-batch-table"><table><thead><tr><th>Chọn</th><th>',
      state.printingDocument === "deliveries" ? 'Bếp / ngày giao' : 'Ngày / file đơn',
      '</th><th>Số dòng</th><th>Trạng thái</th><th>Xem</th></tr></thead><tbody>',
      batchRows || '<tr><td colspan="5"><div class="empty">' + esc(state.printingListError || 'Khoảng ngày này chưa có giấy tờ phù hợp.') + '</div></td></tr>',
      '</tbody></table></div></div><div id="printingPreview"></div>',
      '<details class="operation-details fade-in"><summary>In trực tiếp trọn bộ của ngày đang chọn</summary><div class="operation-details-body">',
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
      '<button class="btn btn-outline" type="submit">Lưu</button></form></div></div>',
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

  function renderSettings() {
    var d = state.data;
    var synced = d.master.settings.master_synced_at || "Chưa đồng bộ";
    var m = state.minvoiceStatus;
    var minvoiceTitle = m && m.connected ? "Đã kết nối M-Invoice" : "Kiểm tra kết nối M-Invoice";
    var minvoiceText = m && m.connected
      ? "M-Invoice đang hoạt động · " + num(m.outgoing.series_count) + " ký hiệu. Có thể lưu nháp chờ ký; không tự ký/phát hành."
      : "Kiểm tra kết nối an toàn; lưu nháp cần xác nhận riêng và không bao giờ tự ký/phát hành.";
    var minvoiceCard = '<div class="card fade-in" style="margin-bottom:18px"><div class="card-head"><div><h3>' +
      esc(minvoiceTitle) + '</h3><p>' + esc(minvoiceText) + '</p></div><button class="btn btn-primary" data-action="check-minvoice">' +
      (m && m.connected ? "Kiểm tra lại" : "Kiểm tra ngay") + '</button></div></div>';
    var outgoingRows = (d.master.outgoing_names || []).map(function (item) {
      return '<div class="group-line"><div><strong>' + esc(item.product_code) + '</strong><span>' +
        esc(item.source_name) + '</span></div><strong>' + esc(item.invoice_name) + '</strong></div>';
    }).join("");
    content.innerHTML = html([
      minvoiceCard,
      '<div class="stats-grid fade-in">',
      statCard("Mã hàng", num(d.master.product_count), "Danh mục sản phẩm", "▤"),
      statCard("Bếp", num(d.master.kitchens.length), "Có nhà thầu và địa chỉ", "⌂"),
      statCard("Nhà cung cấp", num(d.master.suppliers.length), "Danh mục đặt hàng", "⇄"),
      statCard("Nhóm nhà thầu", num(d.master.contractors.length), "Giá nhóm / giá theo ngày", "₫"),
      "</div>",
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Đồng bộ danh mục</h3>',
      '<p>Nguồn: Em Thành.xlsx · Lần cuối ', esc(synced), '</p></div></div><div class="card-body">',
      '<div class="code-note"><strong>Đang áp dụng:</strong> HATRAN, ATV, SUPPY… dùng đúng nhóm giá. GIANHAPTAY và YLKHAN là giá theo ngày, không ăn theo nhà thầu nào.</div>',
      '<div class="form-actions"><button class="btn btn-outline" data-action="sync-master">Đồng bộ lại từ Em Thành.xlsx</button>',
      '<button class="btn btn-primary" data-action="choose-catalog-workbook">Nạp danh mục khách chốt</button></div></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Sao lưu dữ liệu</h3><p>Tải toàn bộ đơn, công nợ và thanh toán về máy</p></div></div>',
      '<div class="card-body"><div class="code-note"><strong>Dữ liệu lưu tại máy chạy hệ thống.</strong> Máy thứ hai cùng mạng Wi-Fi hoặc mạng nội bộ có thể dùng chung khi máy chính đang mở.</div>',
      '<p>Tự sao lưu mỗi 30 phút khi phần mềm đang mở, giữ bản mới nhất của 14 ngày có sao lưu. Trước nâng cấp luôn tạo bản sao riêng. Bấm Lưu/Xác nhận để ghi thay đổi; ô đang gõ chưa xác nhận chưa được lưu.</p>',
      '<div id="automaticBackupStatus" class="code-note" role="status">Đang kiểm tra lần sao lưu gần nhất…</div>',
      '<p>Nên tải thêm một bản sang ổ khác trước khi chuyển máy. Sao lưu trên cùng ổ không bảo vệ được khi ổ đĩa hỏng.</p>',
      '<div class="form-actions"><a class="btn btn-primary" href="/api/backup">Tải bản sao lưu dữ liệu</a></div></div></div></div>',
      catalogImportPreviewHtml(),
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Thông tin thanh toán mặc định</h3><p>Được khóa cùng hóa đơn và dùng để lập Đề nghị thanh toán chính thức theo nhà thầu</p></div></div><div class="card-body">',
      '<form id="documentSettingsForm" class="payment-grid"><div class="form-field span-2"><label>Người đại diện / đề nghị</label><input name="payment_requester" required value="', esc(d.master.settings.payment_requester || ""), '"></div>',
      '<div class="form-field"><label>Số tài khoản nhận tiền</label><input name="payment_bank_account" inputmode="numeric" required value="', esc(d.master.settings.payment_bank_account || ""), '"></div>',
      '<div class="form-field span-2"><label>Ngân hàng</label><input name="payment_bank_name" required value="', esc(d.master.settings.payment_bank_name || ""), '"></div>',
      '<button class="btn btn-primary" type="submit">Lưu thông tin</button></form>',
      '<div class="code-note" style="margin-top:14px"><strong>Kiểm soát:</strong> thiếu một trong ba thông tin sẽ chặn việc khóa hóa đơn và tạo hồ sơ thanh toán chính thức.</div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Tên xuất hóa đơn</h3><p>Ghi nhớ tên đầu ra chuẩn theo mã hàng; nếu chưa khai báo sẽ dùng tên danh mục TĐP</p></div></div><div class="card-body">',
      '<form id="outgoingNameForm" class="payment-grid"><div class="form-field"><label>Mã hàng</label><input name="product_code" required></div>',
      '<div class="form-field span-2"><label>Tên xuất hóa đơn</label><input name="invoice_name" required></div><button class="btn btn-outline" type="submit">Lưu tên đầu ra</button>',
      '<button class="btn btn-primary" type="button" data-action="choose-mapping-file" data-mapping-type="invoice_names">Nạp danh sách từ Excel</button></form>',
      '<div class="status-bar" style="margin-top:16px">Đã lưu ', num(d.master.outgoing_name_count || 0), ' tên đầu ra</div>',
      '<div class="group-list" style="margin-top:12px">', outgoingRows || '<div class="muted">Chưa có tên đầu ra riêng; hệ thống đang dùng tên danh mục TĐP.</div>', '</div></div></div>',
      mappingPreviewHtml("invoice_names"),
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Những việc phần mềm tự làm và không tự làm</h3><p>Giới hạn an toàn</p></div></div>',
      '<div class="card-body"><div class="flow">',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>Đơn hàng và dữ liệu</strong><span>Có thể nhập, sửa, lưu, tính và xuất file</span></div></div>',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>mSMI và M-Invoice an toàn</strong><span>Đầu vào chỉ tải thêm hóa đơn chưa có; đầu ra tạo bản nháp để người dùng kiểm tra và phát hành</span></div></div>',
      '<div class="flow-step"><div class="num">!</div><div><strong>Không tự gửi Zalo, ký hoặc phát hành</strong><span>Các thao tác gửi ra ngoài luôn chờ người dùng duyệt</span></div></div>',
      "</div></div></div>"
    ]);
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
      work_date: d.batch ? d.batch.work_date : new Date().toISOString().slice(0, 10),
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
      '<div class="form-field"><label>Thuế</label><select name="tax"><option value="KKKNT"',
      String(item.tax).toUpperCase() === "KKKNT" ? " selected" : "",
      '>KKKNT</option><option value="KCT"', String(item.tax).toUpperCase() === "KCT" ? " selected" : "",
      '>KCT</option><option value="0"', String(item.tax).toUpperCase() !== "KCT" && String(item.tax).toUpperCase() !== "KKKNT" && n(item.tax) === 0 ? " selected" : "",
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
      '<div class="form-field span-4 muted">Đoàn Văn Giang và Nguyễn Văn Toại đã bị loại khỏi bảng kê/biên nhận mới. Dòng lịch sử vẫn được giữ, không xóa kho hay công nợ.</div>',
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
      ? state.data.batch.work_date : new Date().toISOString().slice(0, 10);
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
      if (useAsLatest && imported.finalized && imported.batch.status !== "approved" &&
          n(imported.summary && imported.summary.totals && imported.summary.totals.errors) === 0) {
        try {
          imported = await api("/api/batches/" + imported.batch.id + "/approve", { method: "POST" });
          automaticallyApproved = true;
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
      var payload = await api("/api/import/analyze", { method: "POST", body: form });
      state.busy = false;
      render();
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
    var workDateText = window.prompt("Ngày làm việc (dd/mm/yyyy):", dateVN(new Date().toISOString().slice(0, 10)));
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

  async function approveBatch() {
    if (!state.batchId || !window.confirm("Duyệt đơn hàng này để chốt số liệu đầu ra?")) return;
    try {
      await api("/api/batches/" + state.batchId + "/approve", { method: "POST" });
      await loadData(state.batchId, true);
      showToast("Đã duyệt đơn hàng · Các đầu ra đã sẵn sàng");
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
    try {
      var payload = await api("/api/outgoing-invoices");
      state.outgoingInvoices = payload.items || [];
      if (state.view === "documents") renderDocuments();
    } catch (error) { showToast(error.message, true); }
  }

  async function fetchOutgoingReadiness() {
    if (!state.batchId || state.outgoingReadinessLoading) return;
    state.outgoingReadinessLoading = true;
    try {
      state.outgoingReadiness = await api("/api/outgoing-invoices/readiness/" + state.batchId);
    } catch (error) {
      state.outgoingReadiness = { error: error.message, rows: [], demand_qty: 0,
        allocated_qty: 0, invoiceable_qty: 0, pending_qty: 0 };
      showToast(error.message, true);
    } finally {
      state.outgoingReadinessLoading = false;
      if (state.view === "documents") renderDocuments();
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
      showToast("M-Invoice đã kết nối · có thể lưu nháp chờ ký · " + num(state.minvoiceStatus.outgoing.series_count) + " ký hiệu");
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
    if (event.target.id === "paymentRequestForm") {
      event.preventDefault();
      var paymentRequest = Object.fromEntries(new FormData(event.target).entries());
      var from = state.data.batch.work_date.slice(0, 7) + "-01";
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
          "?from=" + encodeURIComponent(from) + "&to=" + encodeURIComponent(state.data.batch.work_date)
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
    if (event.target.id === "outgoingNameForm") {
      event.preventDefault();
      var outgoingName = Object.fromEntries(new FormData(event.target).entries());
      try {
        await api("/api/outgoing-product-names/" + encodeURIComponent(outgoingName.product_code), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ invoice_name: outgoingName.invoice_name })
        });
        event.target.reset();
        await loadData(state.batchId, true);
        showToast("Đã ghi nhớ tên xuất hóa đơn");
      } catch (error) { showToast(error.message, true); }
    }
  });

  content.addEventListener("input", function (event) {
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
      if (event.target.id === "invoiceFrom") state.invoiceFrom = event.target.value;
      if (event.target.id === "invoiceTo") state.invoiceTo = event.target.value;
      if (event.target.id === "invoiceStatus") state.invoiceStatus = event.target.value;
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
      if (!state.inventoryFrom || !state.inventoryTo || state.inventoryFrom > state.inventoryTo) {
        state.inventoryValuation = { error: "Từ ngày không được lớn hơn Đến ngày", items: [] };
        renderInventory();
        return;
      }
      state.opsMonth = state.inventoryFrom.slice(0, 7);
      state.opsDate = state.inventoryTo;
      state.inventoryValuation = null;
      state.inventoryMonthClose = null;
      Promise.all([loadInventoryValuation(true), loadInventoryMonthClose(true)]).then(function () {
        renderInventory();
      });
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
    if (input) loadMsmiProductOptions(input);
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
    clearTimeout(msmiProductSearchTimer);
    msmiProductSearchTimer = setTimeout(function () { loadMsmiProductOptions(input); }, 220);
  });

  content.addEventListener("keydown", function (event) {
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
    var conversionInput = event.target.closest(".unit-conversion-input");
    if (conversionInput && event.key === "Enter") {
      event.preventDefault();
      var conversionButton = content.querySelector('[data-action="save-invoice-conversion"][data-direction="' +
        conversionInput.dataset.direction + '"][data-id="' + conversionInput.dataset.id + '"]');
      if (conversionButton) conversionButton.click();
      return;
    }
    var input = event.target.closest(".invoice-mapping-input");
    if (!input || event.key !== "Enter") return;
    event.preventDefault();
    var direction = input.dataset.direction || state.invoiceDirection;
    var itemId = input.id.replace("map_" + direction + "_", "");
    var button = content.querySelector('[data-action="save-invoice-mapping"][data-direction="' +
      direction + '"][data-id="' + itemId + '"]');
    if (button) button.click();
  });

  content.addEventListener("click", async function (event) {
    var viewButton = event.target.closest("[data-view]");
    if (viewButton) { navigate(viewButton.dataset.view); return; }
    var button = event.target.closest("[data-action]");
    if (!button) return;
    var action = button.dataset.action;
    if (action === "jump-invoice-issue") {
      var issueRow = document.querySelector('.invoice-lines-card tr[data-issue="1"]');
      if (issueRow) {
        issueRow.scrollIntoView({block:"center", inline:"nearest"});
        var editor = issueRow.querySelector("input,select,button");
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
    if (action === "download-selected-documents") {
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
        await downloadFile("/api/export/selected-documents", {
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
        showToast("Đã tải giấy tờ đã chọn · mở file Excel rồi bấm Ctrl+P để in");
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
    if (action === "set-invoice-direction") {
      state.invoiceDirection = button.dataset.direction === "output" ? "output" : "input";
      persistInvoiceWorkbenchFilters();
      state.invoiceWorkbench = null;
      loadInvoiceWorkbench();
      return;
    }
    if (action === "prepare-invoice-sync") {
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
    if (action === "save-invoice-mapping") {
      var mappingDirection = button.dataset.direction || state.invoiceDirection;
      var mappingInput = document.getElementById("map_" + mappingDirection + "_" + button.dataset.id);
      if (!mappingInput || !mappingInput.value.trim()) { showToast("Cần nhập mã hàng TĐP", true); return; }
      try {
        button.disabled = true;
        var mappingResult = await api("/api/invoice-workbench/items/" + mappingDirection + "/" +
          button.dataset.id + "/mapping", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ product_code: mappingInput.value.trim() })
        });
        if (mappingDirection === "input") {
          state.operations = null;
          await loadOperations(true);
        } else {
          await loadInvoiceWorkbench(true);
          render();
        }
        showToast(mappingResult.requires_unit_conversion
          ? "Đã nhớ mã nhưng đơn vị tính khác nhau — cần nhập quy đổi trước khi ghi kho"
          : "Đã ghép mã và ghi nhớ đúng loại hóa đơn, đúng đối tác");
      } catch (error) {
        showToast(error.message, true);
        button.disabled = false;
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
          body: JSON.stringify({ conversion_factor: conversionFactor })
        });
        if (conversionDirection === "input") {
          state.operations = null;
          await loadOperations(true);
        } else {
          await loadInvoiceWorkbench(true);
          render();
        }
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
    if (action === "apply-msmi-suggestions") {
      var suggestionCount = Number(button.dataset.count || 0);
      if (!window.confirm("Xác nhận " + suggestionCount + " mã có tên khớp duy nhất trong danh mục TĐP?")) return;
      jsonWrite("/api/msmi/invoices/" + button.dataset.id + "/suggested-mappings", "POST", {}, "Đã xác nhận các mã gợi ý");
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
        showToast(error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = originalLabel;
      }
    }
    if (action === "create-msmi-receipt") {
      if (!window.confirm("Tạo phiếu nhập kho từ hóa đơn này? Phần mềm sẽ không tạo lại nếu hóa đơn đã được nhập trước đó.")) return;
      try {
        button.disabled = true;
        await api("/api/msmi/invoices/" + button.dataset.id + "/receipt", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"});
        state.inventoryValuation = null;
        state.inventoryMonthClose = null;
        state.outgoingReadiness = null;
        state.outgoingPeriodShortages = null;
        state.invoiceLastPosted = {direction:"input", id:button.dataset.id};
        await loadInvoiceWorkbench(true);
        render();
        showToast("Đã nhập kho. Bấm Xem hàng đã ghi kho tại hóa đơn để kiểm tra đúng các dòng vừa nhập.");
      } catch (error) { showToast(error.message, true); button.disabled = false; }
      return;
    }
    if (action === "create-outgoing-drafts") {
      try {
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
        } else showToast(error.message, true);
      }
    }
    if (action === "confirm-outgoing-issued") {
      if (!window.confirm("Thao tác này chỉ ghi nhận số, ký hiệu và ngày hóa đơn; hàng trong kho vẫn được giữ để chờ đối soát. Muốn trừ kho, hãy tải hóa đơn tại phần Đầu ra M-Invoice, ghép mã rồi bấm “Xác nhận trừ kho theo hóa đơn”. Tiếp tục?")) return;
      var issuedNumber = window.prompt("Nhập số hóa đơn đã phát hành (bắt buộc):", "");
      if (!issuedNumber || !issuedNumber.trim()) { showToast("Cần nhập số hóa đơn đã phát hành", true); return; }
      var issuedSeries = window.prompt("Nhập ký hiệu hóa đơn (nếu có):", "") || "";
      var issuedDateText = window.prompt("Nhập ngày hóa đơn dạng dd/mm/yyyy:", dateVN(state.opsDate || ""));
      var issuedDate = parseLocalizedTemporal(issuedDateText, "date");
      if (!issuedDate) { showToast("Ngày hóa đơn chưa đúng dạng dd/mm/yyyy", true); return; }
      try {
        await api("/api/outgoing-invoices/" + button.dataset.id + "/confirm-issued", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true, invoice_number: issuedNumber.trim(),
            invoice_series: issuedSeries.trim(), invoice_date: issuedDate })
        });
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
  new MutationObserver(function () {
    enhanceLocalizedDateInputs(document);
  }).observe(document.body, { childList: true, subtree: true });

  loadData(null);
})();
