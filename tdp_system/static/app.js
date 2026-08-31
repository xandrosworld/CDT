(function () {
  "use strict";

  var state = {
    view: "home",
    data: null,
    batchId: null,
    editingId: null,
    orderFilter: "",
    quoteContractor: "HATRAN",
    quoteItems: null,
    quoteMode: "group",
    modalMode: "order",
    pendingImport: null,
    mappingImportType: "",
    mappingPreview: null,
    kitchenImportPreview: null,
    mealAttendancePreview: null,
    openingImportPreview: null,
    minvoiceStatus: null,
    operations: null,
    supplierNeeds: null,
    debtPeriod: null,
    debtLoading: false,
    debtFrom: "",
    debtTo: "",
    outgoingInvoices: null,
    opsDate: new Date().toISOString().slice(0, 10),
    opsMonth: new Date().toISOString().slice(0, 7),
    busy: false
  };

  var titles = {
    home: "Tổng quan hôm nay",
    orders: "Nhập và kiểm tra đơn",
    purchases: "Đặt hàng nhà cung cấp",
    deliveries: "Phiếu giao theo bếp",
    quotes: "Báo giá theo nhà thầu",
    reports: "Báo cáo và công nợ",
    documents: "Bảng kê, biên nhận và hóa đơn",
    inventory: "Kho hóa đơn / sổ sách",
    msmi: "Hóa đơn đầu vào mSMI",
    kitchen: "Xưởng cơm, menu và PO",
    payroll: "Chấm công và tính lương",
    printing: "Duyệt và in hàng loạt",
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
  var kitchenWorkbookInput = document.getElementById("kitchenWorkbookInput");
  var mealAttendanceInput = document.getElementById("mealAttendanceInput");
  var openingWorkbookInput = document.getElementById("openingWorkbookInput");
  var backdrop = document.getElementById("modalBackdrop");
  var orderForm = document.getElementById("orderForm");
  var toastTimer;

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function n(value) { return Number(value || 0); }
  function money(value) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(Math.round(n(value))) + " đ";
  }
  function num(value) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(n(value));
  }
  function dateVN(value) {
    if (!value) return "";
    var parts = String(value).slice(0, 10).split("-");
    return parts.length === 3 ? parts[2] + "/" + parts[1] + "/" + parts[0] : value;
  }
  function taxText(value) {
    return String(value).toUpperCase() === "KKKNT" ? "KKKNT" : Math.round(n(value) * 100) + "%";
  }
  function html(parts) { return parts.join(""); }

  function showToast(message, error) {
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.toggle("toast-error", Boolean(error));
    toast.classList.add("show");
    toastTimer = setTimeout(function () { toast.classList.remove("show"); }, error ? 4300 : 2800);
  }

  async function api(url, options) {
    var response = await fetch(url, options || {});
    var type = response.headers.get("content-type") || "";
    var payload = type.indexOf("application/json") >= 0 ? await response.json() : null;
    if (!response.ok || (payload && payload.ok === false)) {
      throw new Error(payload && payload.error ? payload.error : "Lỗi máy chủ (" + response.status + ")");
    }
    return payload;
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
      state.batchId = state.data.batch ? state.data.batch.id : null;
      state.supplierNeeds = null;
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
        "&month=" + encodeURIComponent(state.opsMonth) + "&date=" + encodeURIComponent(state.opsDate));
      render();
    } catch (error) {
      content.innerHTML = '<div class="card"><div class="empty"><h3>Không nạp được module</h3><p>' +
        esc(error.message) + '</p><button class="btn btn-primary" data-action="reload-operations">Thử lại</button></div></div>';
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
      batchSelect.innerHTML = '<option value="">Chưa có phiên đơn</option>';
    }
    batchSelect.disabled = !batches.length;
  }

  function navigate(view) {
    state.view = view;
    document.querySelectorAll(".nav-item").forEach(function (button) {
      button.classList.toggle("active", button.dataset.view === view);
    });
    pageTitle.textContent = titles[view] || "Vận hành";
    sidebar.classList.remove("open");
    window.scrollTo(0, 0);
    if (["inventory", "msmi", "kitchen", "payroll", "printing"].indexOf(view) >= 0 && !state.operations) {
      loadOperations();
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
      '</h3><p>Sheet ', esc(preview.sheet), ' · tiêu đề dòng ', preview.header_row,
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

  function kitchenImportPreviewHtml() {
    var preview = state.kitchenImportPreview;
    if (!preview) return "";
    var planRows = preview.plans.map(function (plan) {
      var messages = plan.errors.concat(plan.warnings);
      var servingText = plan.menu_count > 1
        ? num(plan.meal_count) + ' suất tổng · ' + plan.menu_count + ' thực đơn × ' + num(plan.servings_per_menu) + ' suất'
        : num(plan.meal_count) + ' suất';
      return '<div class="group-line"><div><strong>' + esc(plan.kitchen) + ' → XCOM ' +
        esc(plan.xcom_code) + '</strong><span>' + esc(plan.shift) + ' · ' + servingText +
        ' · dòng ' + plan.source_row_start + '–' + plan.source_row_end + ' · ' +
        plan.items.length + ' nguyên liệu</span><span>' + esc(plan.menu_name || "Chưa ghi tên món") +
        '</span></div><div><span class="tag ' + (plan.errors.length ? 'tag-red' : 'tag-ok') + '">' +
        (plan.status === "update" ? "Cập nhật" : "Thêm mới") + '</span><div class="muted">' +
        esc(messages.join(" · ")) + '</div></div></div>';
    }).join("");
    var count = preview.counts;
    return html([
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Xem trước file ',
      esc(preview.filename), '</h3><p>Ngày ', dateVN(preview.work_date),
      ' · chỉ ghi dữ liệu sau khi xác nhận</p></div><button class="btn btn-small btn-outline" data-action="cancel-kitchen-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.plans, ' nhóm bếp/ca · ', count.items,
      ' nguyên liệu · ', count.new, ' thêm · ', count.update, ' cập nhật · ', count.errors,
      ' nhóm lỗi · ', count.warnings, ' nhóm cần lưu ý</div><div class="group-list" style="margin-top:16px">',
      planRows, '</div><div class="form-actions"><button class="btn btn-primary" data-action="confirm-kitchen-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận nạp file xưởng cơm</button></div>',
      preview.can_confirm ? '<div class="code-note"><strong>Kiểm soát:</strong> file có cảnh báo vẫn được nhập; hệ thống ưu tiên số lượng cần đã chốt trong file và không tạo trùng khi nạp lại.</div>' :
        '<div class="code-note"><strong>Chưa thể nhập:</strong> bổ sung các mã hàng còn thiếu trong danh mục rồi chọn lại file.</div>',
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
      ' · số ăn thực tế lưu riêng, không thay số suất đặt dùng cho PO</p></div><button class="btn btn-small btn-outline" data-action="cancel-meal-attendance-import">Bỏ file</button></div>',
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
      esc(preview.period), '</h3><p>File ', esc(preview.filename), ' · sheet ', esc(preview.sheet),
      ' · chỉ ghi dữ liệu sau khi xác nhận</p></div><button class="btn btn-small btn-outline" data-action="cancel-opening-import">Bỏ file</button></div>',
      '<div class="card-body"><div class="status-bar">', count.source_rows, ' dòng nguồn → ', count.items,
      ' mã TĐP · ', count.new_products, ' mã mới · ', count.negative, ' mã tồn âm · ', count.warning,
      ' mã cần lưu ý · ', count.error, ' lỗi · Tổng giá trị ', money(preview.totals.amount), '</div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Mã / tên TĐP</th><th>Dòng / mã kho</th><th>Tồn</th><th>Đơn giá vốn</th><th>Giá trị</th><th>Kiểm tra</th></tr></thead><tbody>',
      visibleRows, '</tbody></table></div>',
      preview.rows.length > 200 ? '<div class="card-body muted">Hiển thị 200 mã cần xem đầu tiên; toàn bộ file vẫn được kiểm tra và gộp.</div>' : '',
      '<div class="card-body"><div class="form-actions"><button class="btn btn-primary" data-action="confirm-opening-import" ',
      preview.can_confirm ? '' : 'disabled', '>Xác nhận nạp tồn đầu kỳ</button></div>',
      preview.can_confirm ? '<div class="code-note"><strong>Kiểm soát:</strong> mã trùng được cộng theo Mã TĐP; số âm và Thành tiền sổ sách được giữ nguyên. Mã mới được thêm vào danh mục nhưng chưa có NCC mặc định.</div>' :
        '<div class="code-note"><strong>Chưa thể nhập:</strong> sửa các dòng lỗi trong Excel rồi chọn lại file.</div>',
      '</div></div>'
    ]);
  }

  function emptyBatch(title, description) {
    return '<div class="card fade-in"><div class="empty"><div class="empty-icon">▤</div><h3>' +
      esc(title) + "</h3><p>" + esc(description) +
      '</p><div class="empty-actions"><button class="btn btn-primary" data-action="choose-excel">Nạp file Excel</button>' +
      '<button class="btn btn-outline" data-action="new-batch">Tạo phiên nhập tay</button></div></div></div>';
  }

  function exportUrl(kind) {
    return state.batchId ? "/api/export/" + kind + "/" + state.batchId : "#";
  }

  function renderHome() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = html([
        '<div class="hero fade-in"><div class="hero-copy"><div class="demo-badge">NHẬP MỘT LẦN – TOÀN BỘ QUY TRÌNH DÙNG CHUNG DỮ LIỆU</div>',
        "<h2>Bắt đầu từ file đơn hàng đã kiểm tra</h2><p>Hệ thống tự đối chiếu mã hàng, bếp, nhà thầu, NCC, giá, thuế và tạo các đầu ra liên quan.</p>",
        '<div class="hero-actions"><button class="btn btn-light" data-action="choose-excel">Nạp file Excel thật <span>→</span></button>',
        '<button class="btn btn-outline hero-outline" data-action="new-batch">Nhập tay</button></div></div></div>',
        '<div class="stats-grid">',
        statCard("Danh mục hàng", num(d.master.product_count), "Đã đồng bộ từ file tổng", "▤"),
        statCard("Bếp giao hàng", num(d.master.kitchens.length), "Tự nhận nhà thầu", "⌂"),
        statCard("Nhà cung cấp", num(d.master.suppliers.length), "Tự gộp đơn đặt hàng", "⇄"),
        statCard("Nhóm giá", num(d.master.contractors.length), "Có giá nhóm và giá theo ngày", "₫"),
        "</div>"
      ]);
      return;
    }
    var s = d.summary.totals;
    var errorCount = s.errors;
    var warningCount = s.warnings || 0;
    var approved = d.batch.status === "approved";
    content.innerHTML = html([
      '<div class="hero fade-in"><div class="hero-copy"><div class="demo-badge">',
      approved ? "PHIÊN ĐƠN ĐÃ DUYỆT" : "PHIÊN ĐƠN ĐANG XỬ LÝ", " · ", dateVN(d.batch.work_date),
      "</div><h2>", esc(d.batch.source_name), "</h2><p>", d.orders.length,
      " dòng đơn đang dùng chung cho đặt hàng, giao hàng, doanh thu, công nợ và chứng từ.</p>",
      '<div class="hero-actions"><button class="btn btn-light" data-view="orders">Mở đơn hàng <span>→</span></button>',
      '<button class="btn btn-outline hero-outline" data-action="choose-excel">Nạp phiên mới</button></div></div></div>',
      '<div class="stats-grid">',
      statCard("Dòng đơn", num(d.orders.length), errorCount ? errorCount + " dòng lỗi" : warningCount ? warningCount + " dòng cảnh báo" : "Đã đủ dữ liệu", "▤"),
      statCard("Doanh thu chưa VAT", money(s.revenue), "Theo số thực giao", "₫"),
      statCard("Giá vốn", money(s.cost), "Theo số thực nhận", "↓"),
      statCard("Lợi nhuận gộp", money(s.profit), s.cost ? (s.profit / s.cost * 100).toFixed(1) + "% trên giá vốn" : "Chưa có giá vốn", "↗"),
      "</div>",
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Trạng thái phiên đơn</h3>',
      '<p>Tất cả đầu ra bám theo trạng thái hiện tại</p></div><span class="tag ',
      approved ? "tag-ok" : errorCount ? "tag-red" : warningCount ? "tag-warn" : "tag-ok", '">',
      approved ? "Đã duyệt" : errorCount ? "Còn lỗi" : warningCount ? "Có cảnh báo" : "Sẵn sàng duyệt", "</span></div>",
      '<div class="card-body"><div class="flow"><div class="flow-step done"><div class="num">✓</div><div><strong>Đã nạp đơn</strong><span>',
      d.orders.length, " dòng từ ", esc(d.batch.source_name), '</span></div></div><div class="flow-step ',
      !errorCount ? "done" : "", '"><div class="num">', !errorCount ? "✓" : "2",
      "</div><div><strong>Kiểm tra dữ liệu</strong><span>",
      errorCount ? errorCount + " dòng cần sửa" : warningCount ? warningCount + " dòng cần xác nhận nhưng vẫn có thể duyệt" : "Mã, giá, NCC và thuế đã đủ",
      '</span></div></div><div class="flow-step ', approved ? "done" : "", '"><div class="num">',
      approved ? "✓" : "3", "</div><div><strong>Duyệt đơn</strong><span>",
      approved ? "Đã khóa số liệu đầu ra" : "Khóa số liệu đầu ra chính thức",
      "</span></div></div></div></div></div>",
      '<div class="card"><div class="card-head"><div><h3>Truy cập nhanh</h3><p>File xuất luôn sinh từ dữ liệu đang thấy</p></div></div>',
      '<div class="card-body"><div class="quick-grid">',
      '<button class="quick-card" data-view="purchases"><strong>Đặt hàng NCC</strong><span>Tự gộp theo NCC</span></button>',
      '<button class="quick-card" data-view="deliveries"><strong>Phiếu giao</strong><span>Tách theo từng bếp</span></button>',
      '<button class="quick-card" data-view="reports"><strong>Công nợ</strong><span>Đầu kỳ + phát sinh − thanh toán</span></button>',
      '<button class="quick-card" data-view="documents"><strong>Hóa đơn</strong><span>Đúng mẫu 11 cột</span></button>',
      "</div></div></div></div>"
    ]);
  }

  function renderOrders() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có phiên đơn", "Nạp file Excel đơn hoàn thiện hoặc tạo phiên mới để nhập tay.");
      return;
    }
    var search = state.orderFilter.toLowerCase();
    var orders = d.orders.filter(function (item) {
      if (!search) return true;
      return [item.product_code, item.product_name, item.kitchen, item.contractor, item.supplier].some(function (value) {
        return String(value || "").toLowerCase().indexOf(search) >= 0;
      });
    });
    var rows = orders.map(function (item, index) {
      var warnings = item.warnings || [];
      var errors = item.errors.length
        ? '<div class="errors">' + item.errors.map(esc).join("<br>") + "</div>"
        : warnings.length
          ? '<div class="warnings">' + warnings.map(esc).join("<br>") + "</div>"
          : '<span class="tag tag-ok">Đủ dữ liệu</span>';
      return html([
        '<tr class="', item.errors.length ? "row-error" : warnings.length ? "row-warning" : "", '"><td>', index + 1, "</td><td><strong>",
        esc(item.kitchen), '</strong><div class="muted">', esc(item.contractor), "</div></td><td>",
        esc(item.product_code), '</td><td class="name-cell"><strong>', esc(item.product_name),
        '</strong><div class="muted">', esc(item.note), '</div></td><td class="num-cell">', num(item.qty),
        '</td><td class="num-cell">', num(item.actual_received), '<div class="muted">Hỏng/trả ',
        num(n(item.damaged_qty) + n(item.supplier_return_qty)), ' · ròng ', num(Math.max(n(item.actual_received) - n(item.damaged_qty) - n(item.supplier_return_qty), 0)),
        '</div></td><td class="num-cell">', num(item.actual_delivered), '<div class="muted">Khách trả ', num(item.customer_return_qty),
        ' · ròng ', num(Math.max(n(item.actual_delivered) - n(item.customer_return_qty), 0)), '</div>',
        "</td><td>", esc(item.unit), "</td><td>", esc(item.supplier), '</td><td class="num-cell">',
        money(item.buy_price), '</td><td class="num-cell">', money(item.sell_price),
        '</td><td><span class="tag tag-tax">', taxText(item.tax), '</span></td><td class="',
        item.profit < 0 ? "profit-negative" : "profit-positive", ' num-cell">', money(item.profit),
        "</td><td>", errors, '</td><td><div class="table-actions"><button class="icon-button" data-action="edit-order" data-id="',
        item.id, '" title="Sửa">✎</button><button class="icon-button danger" data-action="delete-order" data-id="',
        item.id, '" title="Xóa">×</button></div></td></tr>'
      ]);
    }).join("");
    var approved = d.batch.status === "approved";
    content.innerHTML = html([
      '<div class="import-zone fade-in"><div><strong>Nguồn: ', esc(d.batch.source_name),
      "</strong><p>Ngày làm việc ", dateVN(d.batch.work_date), " · Dữ liệu tự lưu ngay sau mỗi lần sửa</p></div>",
      '<div class="compact-controls"><button class="btn btn-outline" data-action="choose-excel">Nạp phiên Excel mới</button>',
      '<button class="btn btn-outline" data-action="paste-orders">Dán nhiều dòng</button><button class="btn btn-outline" data-action="add-order">+ Thêm dòng</button><button class="btn btn-primary" data-action="approve-batch" ',
      approved || d.summary.totals.errors ? "disabled" : "", ">", approved ? "✓ Đã duyệt" : "Duyệt phiên đơn", "</button></div></div>",
      '<div class="toolbar fade-in"><div class="toolbar-left"><div class="',
      d.summary.totals.errors ? "error-summary" : d.summary.totals.warnings ? "warning-summary" : "ok-summary", '">',
      d.summary.totals.errors
        ? "Còn " + d.summary.totals.errors + " dòng lỗi — bấm bút chì để sửa"
        : d.summary.totals.warnings
          ? d.summary.totals.warnings + " cảnh báo cần xác nhận · Không chặn duyệt"
          : "✓ " + d.orders.length + " dòng đã đủ mã, giá, NCC và thuế",
      '</div></div><div class="toolbar-right"><input class="input-date search-input" id="orderSearch" value="',
      esc(state.orderFilter), '" placeholder="Tìm mã, tên hàng, bếp, NCC…"></div></div>',
      '<div class="card fade-in"><div class="card-head"><div><h3>Đơn hàng đã chuẩn hóa</h3>',
      '<p>SL đặt → đặt NCC · Thực nhận → giá vốn · Thực giao → doanh thu/hóa đơn</p></div><span class="tag ',
      approved ? "tag-ok" : "tag-warn", '">', approved ? "Đã duyệt" : "Bản nháp", "</span></div>",
      '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Bếp / Nhà thầu</th><th>Mã hàng</th><th>Tên hàng</th>',
      "<th>SL đặt</th><th>Thực nhận</th><th>Thực giao</th><th>ĐVT</th><th>NCC</th><th>Giá mua</th><th>Giá bán</th>",
      "<th>Thuế</th><th>Lợi nhuận</th><th>Kiểm tra</th><th></th></tr></thead><tbody>",
      rows || '<tr><td colspan="15"><div class="empty">Không có dòng phù hợp</div></td></tr>',
      "</tbody></table></div></div>"
    ]);
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
    try {
      state.supplierNeeds = await api("/api/supplier-needs/" + state.batchId);
      if (state.view === "purchases") renderPurchases();
    } catch (error) { showToast(error.message, true); }
  }

  function renderPurchases() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có dữ liệu đặt hàng", "Nạp đơn để hệ thống tự gộp số lượng theo nhà cung cấp.");
      return;
    }
    if (!state.supplierNeeds) {
      content.innerHTML = '<div class="loading-panel"><div class="spinner"></div><strong>Đang trừ tồn khả dụng và tách NCC…</strong></div>';
      setTimeout(fetchSupplierNeeds, 0);
      return;
    }
    var needs = state.supplierNeeds;
    var cards = needs.groups.map(function (group, groupIndex) {
      var supplier = group.supplier, items = group.items;
      var lines = items.map(function (item) {
        return '<div class="group-line"><div><strong>' + esc(item.product_name) + "</strong><span>" +
          esc(item.product_code) + " · " + esc(item.kitchen) + " · KH đặt " + num(item.customer_qty) +
          (item.stock_used ? " · trừ tồn " + num(item.stock_used) : "") +
          "</span></div><strong>" + num(item.required_qty) + " " + esc(item.unit) + "</strong></div>";
      }).join("");
      return '<div class="group-card"><div class="group-title"><div><strong>NCC ' + esc(supplier.toUpperCase()) +
        "</strong><span>" + esc(group.kitchen) + " · " + items.length +
        ' dòng</span></div><div class="compact-controls"><button class="btn btn-small btn-outline" data-action="toggle-supplier-rule" data-supplier="' +
        esc(supplier) + '" data-combine="' + (group.combine_kitchens ? "0" : "1") + '">' +
        (group.combine_kitchens ? "Tách theo bếp" : "Gộp NCC này") +
        '</button><button class="btn btn-small btn-outline" data-action="copy-supplier-need" data-group-index="' +
        groupIndex + '">Sao chép gửi Zalo</button></div></div><div class="group-list">' + lines +
        '</div><div class="group-total"><span>Tổng cần mua sau trừ tồn</span><strong>' +
        num(group.total_qty) + "</strong></div></div>";
    }).join("");
    content.innerHTML = '<div class="code-note fade-in"><strong>Công thức:</strong> max(lượng khách đặt − tồn khả dụng, 0). ' +
      'Đơn NCC không dùng toàn bộ lượng khách đặt.</div><div class="toolbar fade-in"><div class="status-bar">KH đặt ' +
      num(needs.ordered_qty) + " · Cần mua " + num(needs.required_qty) + " · " + needs.groups.length +
      ' nhóm NCC/bếp</div><a class="btn btn-primary" href="' + exportUrl("suppliers") +
      '">Tải Excel đặt hàng</a></div><div class="group-grid fade-in">' +
      (cards || '<div class="card"><div class="empty">Tồn hiện có đã đáp ứng toàn bộ nhu cầu.</div></div>') + "</div>";
  }

  function renderDeliveries() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có dữ liệu giao hàng", "Nạp đơn để hệ thống tự tách phiếu theo từng bếp.");
      return;
    }
    var groups = groupBy(d.orders, "kitchen");
    var kitchenMeta = Object.fromEntries(d.master.kitchens.map(function (item) { return [item.code, item]; }));
    var cards = Object.entries(groups).map(function (entry) {
      var kitchen = entry[0], items = entry[1];
      var meta = kitchenMeta[kitchen] || { name: kitchen, address: "" };
      var lines = items.map(function (item) {
        return '<div class="group-line"><div><strong>' + esc(item.product_name) + "</strong><span>" +
          esc(item.product_code) + (item.note ? " · " + esc(item.note) : "") + "</span></div><strong>" +
          num(item.actual_delivered) + " " + esc(item.unit) + "</strong></div>";
      }).join("");
      return '<div class="group-card"><div class="group-title"><div><strong>' + esc(meta.name || kitchen) +
        "</strong><span>" + esc(meta.address || "") + '</span></div><span class="tag ' +
        (meta.show_price ? "tag-warn" : "tag-ok") + '">' + (meta.show_price ? "Có hiển thị giá" : "Ẩn giá") +
        '</span></div><div class="group-list">' + lines + '</div><div class="group-total"><span>' +
        items.length + " dòng · Theo số thực giao</span><strong>" + esc(kitchen) + "</strong></div></div>";
    }).join("");
    content.innerHTML = '<div class="toolbar fade-in"><div class="status-bar">✓ Đã tách thành ' +
      Object.keys(groups).length + ' phiếu giao · Dùng số thực giao</div><a class="btn btn-primary" href="' +
      exportUrl("deliveries") + '">Tải toàn bộ phiếu giao</a></div><div class="group-grid fade-in">' + cards + "</div>";
  }

  async function fetchQuote() {
    try {
      var url = "/api/quotes?contractor=" + encodeURIComponent(state.quoteContractor);
      if (state.batchId) url += "&batch_id=" + state.batchId;
      var payload = await api(url);
      state.quoteItems = payload.items;
      state.quoteMode = payload.mode;
      if (state.view === "quotes") renderQuotes();
    } catch (error) {
      showToast(error.message, true);
    }
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
    var output = state.quoteItems.filter(function (item) { return n(item.sell_price) > 0; });
    var pending = state.quoteItems.length - output.length;
    var rows = state.quoteItems.slice(0, 1200).map(function (item, index) {
      var price = n(item.sell_price) > 0
        ? "<strong>" + money(item.sell_price) + "</strong>"
        : '<span class="tag tag-warn">' + esc(item.status || "Chưa có giá") + "</span>";
      return "<tr><td>" + (index + 1) + "</td><td>" + esc(item.product_code) +
        '</td><td class="name-cell">' + esc(item.product_name) + "</td><td>" + esc(item.unit) +
        '</td><td><span class="tag tag-tax">' + taxText(item.tax) + '</span></td><td class="num-cell">' +
        price + "</td></tr>";
    }).join("");
    var options = contractors.map(function (item) {
      return '<option value="' + esc(item.code) + '"' + (item.code === state.quoteContractor ? " selected" : "") +
        ">" + esc(item.code) + (item.pricing_mode === "daily" ? " · giá theo ngày" : "") + "</option>";
    }).join("");
    var note = state.quoteMode === "daily"
      ? "GIANHAPTAY/YLKHAN không ăn theo bảng giá nhà thầu nào: báo giá lấy từ giá nhập theo ngày trong phiên đơn."
      : "Giá lấy đúng cột nhóm nhà thầu trong bảng giá tổng; dòng X/rỗng không xuất.";
    content.innerHTML = html([
      '<div class="toolbar fade-in"><div class="toolbar-left"><label><strong>Nhà thầu:</strong> <select class="select" id="quoteContractor">',
      options, '</select></label><div class="status-bar">', output.length, " dòng có giá · ", pending, " dòng chưa xuất</div></div>",
      '<a class="btn btn-primary" href="/api/export/quote/', encodeURIComponent(state.quoteContractor),
      state.batchId ? "?batch_id=" + state.batchId : "", '">Xuất báo giá ', esc(state.quoteContractor), "</a></div>",
      '<div class="code-note fade-in"><strong>Quy tắc giá:</strong> ', esc(note), "</div>",
      '<div class="card fade-in" style="margin-top:18px"><div class="card-head"><div><h3>Bảng giá ',
      esc(state.quoteContractor), "</h3><p>", state.quoteMode === "daily" ? "Giá theo ngày" : "Giá theo nhóm cấu hình",
      '</p></div><span class="tag ', state.quoteMode === "daily" ? "tag-warn" : "tag-ok", '">',
      state.quoteMode === "daily" ? "Nhập từng ngày" : "Theo bảng tổng", "</span></div>",
      '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Mã hàng</th><th>Tên hàng</th><th>ĐVT</th><th>Thuế</th><th>Giá / Trạng thái</th></tr></thead><tbody>',
      rows, "</tbody></table></div></div>"
    ]);
  }

  function renderReports() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có dữ liệu báo cáo", "Nạp đơn để tính doanh thu, giá vốn, lợi nhuận và công nợ.");
      return;
    }
    if (!state.debtFrom || !state.debtTo) {
      state.debtFrom = d.batch.work_date.slice(0, 7) + "-01";
      state.debtTo = d.batch.work_date;
    }
    if (state.debtPeriod === null) setTimeout(fetchDebtPeriod, 0);
    var s = d.summary;
    var contractorDebt = state.debtPeriod ? state.debtPeriod.contractors : s.contractors;
    var supplierDebt = state.debtPeriod ? state.debtPeriod.suppliers : s.suppliers;
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
    var paymentRows = (d.payments || []).map(function (item) {
      return "<tr><td>" + dateVN(item.payment_date) + "</td><td>" +
        (item.kind === "receipt" ? "Thu khách hàng" : "Trả nhà cung cấp") + "</td><td><strong>" +
        esc(item.party_code) + '</strong></td><td class="num-cell">' + money(item.amount) + "</td><td>" +
        esc(item.note) + '</td><td><button class="icon-button danger" data-action="delete-payment" data-id="' +
        item.id + '">×</button></td></tr>';
    }).join("");
    content.innerHTML = html([
      '<div class="toolbar fade-in"><form id="debtPeriodForm" class="compact-controls"><strong>Kỳ công nợ</strong><input class="input-date" name="from" type="date" value="', esc(state.debtFrom), '" required><span>đến</span><input class="input-date" name="to" type="date" value="', esc(state.debtTo), '" required><button class="btn btn-outline" type="submit">Xem kỳ</button></form>',
      '<div class="compact-controls"><a class="btn btn-outline" href="', exportUrl("report"), '">Báo cáo ngày</a>',
      '<a class="btn btn-primary" href="/api/export/debts?from=', encodeURIComponent(state.debtFrom),
      '&to=', encodeURIComponent(state.debtTo), '">Tải công nợ kỳ</a></div></div>',
      '<div class="stats-grid fade-in">',
      statCard("Doanh thu chưa VAT", money(s.totals.revenue), "Theo số thực giao", "₫"),
      statCard("Giá vốn", money(s.totals.cost), "Theo số thực nhận", "↓"),
      statCard("Lợi nhuận gộp", money(s.totals.profit), s.totals.cost ? (s.totals.profit / s.totals.cost * 100).toFixed(1) + "% trên giá vốn" : "0%", "↗"),
      statCard("Tổng thanh toán", money(s.totals.total), "Đã gồm thuế", "✓"),
      "</div>",
      '<div class="card"><div class="card-head"><div><h3>Ghi nhận thu / chi</h3><p>Công nợ cập nhật ngay sau khi lưu</p></div></div>',
      '<div class="card-body"><form id="paymentForm" class="payment-grid">',
      '<div class="form-field"><label>Ngày</label><input name="payment_date" type="date" value="', new Date().toISOString().slice(0, 10), '" required></div>',
      '<div class="form-field"><label>Loại</label><select name="kind"><option value="receipt">Thu khách hàng</option><option value="payment">Trả nhà cung cấp</option></select></div>',
      '<div class="form-field"><label>Mã nhà thầu / NCC</label><input name="party_code" placeholder="VD: HATRAN" required></div>',
      '<div class="form-field"><label>Số tiền</label><input name="amount" type="number" min="0" required></div>',
      '<div class="form-field"><label>Nội dung</label><input name="note" placeholder="Chuyển khoản…"></div>',
      '<button class="btn btn-primary" type="submit">Lưu thanh toán</button></form></div></div>',
      '<div class="section-grid" style="margin-top:18px"><div class="card"><div class="card-head"><div><h3>Công nợ phải thu</h3><p>Đầu kỳ + phát sinh + điều chỉnh − đã thu</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Nhà thầu</th><th>Đầu kỳ</th><th>Phát sinh</th><th>Điều chỉnh</th><th>Đã thu</th><th>Còn thu</th></tr></thead><tbody>',
      contractorRows, "</tbody></table></div></div>",
      '<div class="card"><div class="card-head"><div><h3>Công nợ phải trả</h3><p>Đầu kỳ + giá vốn thực nhận + điều chỉnh − đã trả</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>NCC</th><th>Đầu kỳ</th><th>Phát sinh</th><th>Điều chỉnh</th><th>Đã trả</th><th>Còn trả</th></tr></thead><tbody>',
      supplierRows, "</tbody></table></div></div></div>",
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Nhập số dư đầu kỳ</h3><p>Có thể cập nhật lại khi bắt đầu sử dụng</p></div></div>',
      '<div class="card-body"><form id="balanceForm" class="payment-grid">',
      '<div class="form-field"><label>Nhóm</label><select name="party_type"><option value="contractor">Nhà thầu phải thu</option><option value="supplier">NCC phải trả</option></select></div>',
      '<div class="form-field span-2"><label>Mã nhà thầu / NCC</label><input name="party_code" required></div>',
      '<div class="form-field"><label>Số dư đầu kỳ</label><input name="opening" type="number" required></div>',
      '<button class="btn btn-outline" type="submit">Lưu số dư</button></form></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Điều chỉnh công nợ</h3><p>Dùng số dương để tăng, số âm để giảm; lưu riêng trong lịch sử kỳ</p></div></div><div class="card-body"><form id="debtAdjustmentForm" class="payment-grid">',
      '<div class="form-field"><label>Ngày</label><input name="adjustment_date" type="date" value="', esc(state.debtTo), '" required></div>',
      '<div class="form-field"><label>Nhóm</label><select name="party_type"><option value="contractor">Phải thu</option><option value="supplier">Phải trả</option></select></div>',
      '<div class="form-field"><label>Mã nhà thầu / NCC</label><input name="party_code" required></div>',
      '<div class="form-field"><label>Số điều chỉnh (+/−)</label><input name="amount" type="number" required></div>',
      '<div class="form-field span-2"><label>Lý do</label><input name="note" required></div>',
      '<button class="btn btn-outline" type="submit">Lưu điều chỉnh</button></form></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Lịch sử thanh toán</h3><p>100 giao dịch gần nhất</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Ngày</th><th>Loại</th><th>Đối tượng</th><th>Số tiền</th><th>Nội dung</th><th></th></tr></thead><tbody>',
      paymentRows || '<tr><td colspan="6"><div class="empty">Chưa ghi nhận thanh toán</div></td></tr>',
      "</tbody></table></div></div>"
    ]);
  }

  function documentCard(icon, title, text, href, button) {
    return '<div class="document-card"><div class="doc-icon">' + icon + "</div><h4>" + esc(title) +
      "</h4><p>" + esc(text) + '</p><a class="btn btn-outline" href="' + href + '">' + esc(button) + "</a></div>";
  }

  function renderDocuments() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có dữ liệu chứng từ", "Nạp và hoàn thiện đơn trước khi tạo bảng kê, biên nhận và file hóa đơn.");
      return;
    }
    var purchaseCount = d.orders.filter(function (item) { return item.purchase_list; }).length;
    var contractorOptions = (d.master.contractors || []).map(function (item) {
      return '<option value="' + esc(item.code) + '">' + esc(item.code) + '</option>';
    }).join("");
    if (state.outgoingInvoices === null) setTimeout(fetchOutgoingInvoices, 0);
    var outgoingRows = (state.outgoingInvoices || []).filter(function (item) {
      return item.batch_id === state.batchId;
    }).map(function (item) {
      var statusText = item.status === "issued" ? "Đã phát hành" : item.status === "cancelled" ? "Đã hủy" : "Dự thảo";
      var statusClass = item.status === "issued" ? "tag-ok" : item.status === "cancelled" ? "tag-red" : "tag-warn";
      var actions = item.status === "draft"
        ? '<div class="compact-controls"><button class="btn btn-small btn-primary" data-action="confirm-outgoing-issued" data-id="' +
          item.id + '">Xác nhận đã ký/phát hành</button><button class="btn btn-small btn-outline" data-action="cancel-outgoing-draft" data-id="' +
          item.id + '">Hủy & nhả tồn</button></div>'
        : "";
      return '<tr><td><strong>' + esc(item.contractor) + '</strong></td><td>' + dateVN(item.invoice_date) +
        '</td><td class="num-cell">' + money(item.subtotal) + '</td><td class="num-cell">' + money(item.tax_amount) +
        '</td><td class="num-cell"><strong>' + money(item.total_amount) + '</strong></td><td><span class="tag ' +
        statusClass + '">' + statusText + '</span></td><td>' + actions + '</td></tr>';
    }).join("");
    content.innerHTML = html([
      '<div class="code-note fade-in"><strong>Luồng hóa đơn đúng:</strong> hệ thống sinh file 11 cột theo mẫu khách gửi → tải lên phần mềm trung gian kiểm tra tồn → phần mềm trung gian mới đẩy sang M-Invoice.</div>',
      '<div class="toolbar fade-in"><div class="toolbar-left"><button class="btn btn-primary" data-action="create-outgoing-drafts">Kiểm tra tồn & tạo dự thảo đầu ra</button>',
      '<span class="muted">Chỉ tạo bản nháp; người dùng tự kiểm tra, ký và phát hành</span></div>',
      '<form id="paymentRequestForm" class="compact-controls"><select name="contractor" class="select">', contractorOptions,
      '</select><button class="btn btn-outline" type="submit">Đề nghị thanh toán</button></form></div>',
      '<div class="card fade-in" style="margin-top:18px"><div class="card-head"><div><h3>Đầu ra từ phiên ', dateVN(d.batch.work_date),
      "</h3><p>Mỗi lần tải, file được sinh mới từ dữ liệu hiện tại — không dùng file dựng sẵn</p></div>",
      '<span class="tag tag-ok">', d.orders.length, " dòng nguồn</span></div>",
      '<div class="card-body"><div class="document-grid">',
      documentCard("NCC", "Đơn đặt hàng", "Tách nhiều sheet theo nhà cung cấp", exportUrl("suppliers"), "Tải Excel"),
      documentCard("GH", "Phiếu giao", "Tách sheet theo bếp, đúng quy tắc ẩn/hiện giá", exportUrl("deliveries"), "Tải Excel"),
      documentCard("BK", "Bảng kê & biên nhận", purchaseCount + " dòng bảng kê, tự gộp theo người bán", exportUrl("purchases"), "Tải Excel"),
      documentCard("11", "File tải hóa đơn", "ZIP tách nhà thầu và thuế, đúng 11 cột", exportUrl("invoices"), "Tải ZIP"),
      documentCard("BC", "Báo cáo công nợ", "Doanh thu, giá vốn, đầu kỳ và thanh toán", exportUrl("report"), "Tải Excel"),
      "</div></div></div>",
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Dự thảo hóa đơn đầu ra</h3><p>Tạo dự thảo chỉ giữ tồn khả dụng; chỉ ghi xuất kho sau khi người dùng xác nhận đã ký/phát hành bên ngoài</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Nhà thầu</th><th>Ngày</th><th>Trước thuế</th><th>Thuế</th><th>Tổng</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>',
      outgoingRows || '<tr><td colspan="7"><div class="empty">' + (state.outgoingInvoices === null ? 'Đang nạp trạng thái dự thảo…' : 'Phiên này chưa có dự thảo đầu ra.') + '</div></td></tr>',
      '</tbody></table></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Điểm kiểm soát trước khi tải hóa đơn</h3>',
      '<p>Hệ thống không tự nhận là đã phát hành hóa đơn</p></div></div><div class="card-body"><div class="flow">',
      '<div class="flow-step ', d.summary.totals.errors ? "" : "done", '"><div class="num">1</div><div><strong>Đơn đủ dữ liệu</strong><span>',
      d.summary.totals.errors ? d.summary.totals.errors + " dòng còn lỗi" : "Mã, bếp, giá và thuế đã đủ", "</span></div></div>",
      '<div class="flow-step done"><div class="num">2</div><div><strong>Tách đúng nhóm thuế</strong><span>8% và KKKNT không trộn file</span></div></div>',
      '<div class="flow-step"><div class="num">3</div><div><strong>Kiểm tra tồn ở phần mềm trung gian</strong><span>Thao tác ngoài hệ thống này</span></div></div>',
      "</div></div></div>"
    ]);
  }

  function renderInventory() {
    var o = state.operations;
    if (!o) { loadOperations(); return; }
    var rows = o.inventory.map(function (item, index) {
      return '<tr><td>' + (index + 1) + '</td><td><strong>' + esc(item.product_code) +
        '</strong></td><td>' + esc(item.product_name) + '</td><td>' + esc(item.unit) +
        '</td><td class="num-cell">' + num(item.accounting_qty) + '</td><td class="num-cell"><strong>' +
        num(item.available_qty) + '</strong></td></tr>';
    }).join("");
    content.innerHTML = html([
      '<div class="code-note fade-in"><strong>Kho sổ sách:</strong> tồn đầu kỳ + hóa đơn đầu vào + bảng kê BK − hóa đơn đầu ra đã xác nhận phát hành. Dự thảo đầu ra chỉ giữ tồn khả dụng.</div>',
      '<div class="stats-grid fade-in">',
      statCard("Mặt hàng có tồn", num(o.inventory_totals.products), "Tính đến " + dateVN(o.inventory_as_of), "▦"),
      statCard("Tồn sổ sách", num(o.inventory_totals.accounting_qty), "Chứng từ đã ghi sổ", "Σ"),
      statCard("Tồn khả dụng", num(o.inventory_totals.available_qty), "Đã trừ phần giữ cho dự thảo", "✓"),
      statCard("Nguyên tắc", "Sổ sách", "Không trộn kho thực tế", "i"),
      '</div>',
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Nhập tồn đầu kỳ</h3><p>Mỗi lần lưu cùng kỳ + mã sẽ cập nhật, không tạo trùng</p></div></div><div class="card-body">',
      '<form id="openingForm" class="payment-grid"><div class="form-field"><label>Kỳ</label><input name="period" type="month" value="', esc(state.opsMonth), '" required></div>',
      '<div class="form-field"><label>Mã hàng</label><input name="product_code" required></div>',
      '<div class="form-field"><label>Số lượng</label><input name="qty" type="number" step="0.01" required></div>',
      '<div class="form-field"><label>Đơn giá vốn</label><input name="unit_cost" type="number" min="0"></div>',
      '<button class="btn btn-primary" type="submit">Lưu tồn đầu</button>',
      '<button class="btn btn-outline" type="button" data-action="choose-opening-workbook">Nạp Excel tồn đầu kỳ</button></form></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Điều chỉnh kho</h3><p>Mọi điều chỉnh đều có audit</p></div></div><div class="card-body">',
      '<form id="inventoryAdjustmentForm" class="payment-grid"><div class="form-field"><label>Ngày</label><input name="txn_date" type="date" value="', esc(state.opsDate), '" required></div>',
      '<div class="form-field"><label>Mã hàng</label><input name="product_code" required></div>',
      '<div class="form-field"><label>SL (+ tăng / − giảm)</label><input name="qty" type="number" step="0.01" required></div>',
      '<div class="form-field"><label>Lý do</label><input name="note" required></div>',
      '<button class="btn btn-outline" type="submit">Ghi điều chỉnh</button></form></div></div></div>',
      openingImportPreviewHtml(),
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Chi tiết tồn</h3><p>',
      dateVN(o.inventory_as_of), '</p></div><input id="inventoryDate" type="date" value="', esc(state.opsDate), '"></div>',
      '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Mã</th><th>Tên hàng</th><th>ĐVT</th><th>Tồn sổ sách</th><th>Tồn khả dụng</th></tr></thead><tbody>',
      rows || '<tr><td colspan="6"><div class="empty">Chưa có tồn đầu, hóa đơn đầu vào hoặc bảng kê đã duyệt.</div></td></tr>',
      '</tbody></table></div></div>'
    ]);
  }

  function renderMsmi() {
    var o = state.operations;
    if (!o) { loadOperations(); return; }
    var sync = o.msmi.state.length ? o.msmi.state[0] : null;
    var cards = o.msmi.invoices.map(function (invoice) {
      var itemRows = invoice.items.map(function (item) {
        var mapping = item.mapping_status === "mapped"
          ? '<span class="tag tag-ok">' + esc(item.product_code) + ' · ' + esc(item.product_name || "Đã ghép") + '</span>'
          : '<div class="compact-controls"><input class="input-date" id="map_' + item.id + '" placeholder="Mã hàng TĐP"><button class="btn btn-small btn-outline" data-action="save-msmi-mapping" data-id="' + item.id + '">Ghi nhớ</button></div>';
        return '<tr><td>' + item.line_index + '</td><td>' + esc(item.source_item_code) + '</td><td>' +
          esc(item.source_item_name) + '</td><td>' + num(item.qty) + ' ' + esc(item.source_unit) +
          '</td><td class="num-cell">' + money(item.amount) + '</td><td>' + mapping + '</td></tr>';
      }).join("");
      return '<div class="card" style="margin-bottom:18px"><div class="card-head"><div><h3>' +
        esc(invoice.seller_name || invoice.seller_tax_code || "Người bán") + '</h3><p>' +
        dateVN(invoice.invoice_date) + ' · ' + esc(invoice.invoice_series) + ' ' + esc(invoice.invoice_number) +
        ' · ' + invoice.mapped_count + '/' + invoice.item_count + ' dòng đã ghép</p></div><div class="compact-controls"><span class="tag ' +
        (invoice.receipt_status === "posted" ? "tag-ok" : invoice.receipt_status === "ready" ? "tag-warn" : "tag-red") + '">' +
        esc(invoice.receipt_status) + '</span>' + (invoice.receipt_status === "ready" ? '<button class="btn btn-small btn-primary" data-action="create-msmi-receipt" data-id="' + invoice.id + '">Tạo phiếu nhập</button>' : '') +
        '</div></div><div class="table-wrap"><table><thead><tr><th>Dòng</th><th>Mã nguồn</th><th>Tên hàng nguồn</th><th>SL</th><th>Thành tiền</th><th>Ghép mã TĐP</th></tr></thead><tbody>' +
        itemRows + '</tbody></table></div></div>';
    }).join("");
    content.innerHTML = html([
      '<div class="toolbar fade-in"><div><div class="status-bar">mSMI chỉ đọc · đồng bộ tăng dần · không tạo phiếu nhập trùng</div><div class="muted">',
      sync ? 'Lần cuối ' + esc(sync.last_synced_at) + ' · ' + esc(sync.last_status) : 'Chưa đồng bộ trong phần mềm',
      '</div></div><button class="btn btn-primary" data-action="sync-msmi">Đồng bộ hóa đơn mới</button></div>',
      '<div class="code-note"><strong>Kiểm soát:</strong> phải ghép đủ mã hàng rồi người dùng mới bấm tạo phiếu nhập. Mapping được nhớ theo tenant + người bán + mã/tên hàng nguồn.</div>',
      '<div style="margin-top:18px">', cards || '<div class="card"><div class="empty">Chưa có hóa đơn đầu vào trong database. Bấm đồng bộ khi API mSMI sẵn sàng.</div></div>', '</div>'
    ]);
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
        esc(plan.status) + '</span></div><div class="group-list">' + lines +
        '</div><div class="group-total"><span>Doanh thu ' + money(plan.revenue) + ' · Tổng chi/suất ' + money(plan.cost_per_meal) +
        '</span><strong>LN ' + money(plan.profit) + '</strong></div>' +
        (plan.warnings.length ? '<div class="code-note"><strong>Cần kiểm tra:</strong> ' + esc(plan.warnings.join(' · ')) + '</div>' : '') +
        (plan.status !== "approved" ? '<button class="btn btn-small btn-primary" data-action="approve-meal-plan" data-id="' + plan.id + '">Duyệt kế hoạch</button>' : '') + '</div>';
    }).join("");
    var unitRows = o.kitchen_units.map(function (item) {
      return '<div class="group-line"><div><strong>' + esc(item.kitchen_code) +
        '</strong></div><strong>' + esc(item.unit_code) + '</strong></div>';
    }).join("");
    content.innerHTML = html([
      '<div class="toolbar fade-in"><div><div class="status-bar">Menu → suất đặt → định lượng → nguyên liệu → giá HATRAN đúng kỳ → XCOM → PO</div><div class="muted">Chấm suất thực tế lưu riêng để đối chiếu; không tự đổi số suất đặt ban đầu của PO.</div></div>',
      '<div class="compact-controls"><input id="kitchenDate" type="date" value="', esc(state.opsDate), '"><button class="btn btn-outline" data-action="choose-kitchen-workbook">Nạp định mức/PO</button><button class="btn btn-outline" data-action="choose-meal-attendance">Nạp chấm suất tháng</button><a class="btn btn-primary" href="/api/kitchen/po?date=', encodeURIComponent(state.opsDate), '">',
      poApproved ? 'Tải PO đã duyệt' : 'Tải PO nháp', '</a></div></div>',
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Tạo kế hoạch bếp/ca</h3><p>Mỗi dòng nguyên liệu: mã | định lượng/suất | món | ĐVT | NCC | giá tùy chọn</p></div></div><div class="card-body">',
      '<form id="mealPlanForm"><div class="payment-grid"><div class="form-field"><label>Ngày</label><input name="work_date" type="date" value="', esc(state.opsDate), '" required></div>',
      '<div class="form-field"><label>Mã bếp</label><input name="kitchen" placeholder="POT" required></div>',
      '<div class="form-field"><label>Ca</label><input name="shift" placeholder="Sáng / trưa / chiều" required></div>',
      '<div class="form-field"><label>Tổng số suất</label><input name="meal_count" type="number" min="1" required></div>',
      '<div class="form-field"><label>Số thực đơn</label><input name="menu_count" type="number" min="1" value="1"></div>',
      '<div class="form-field"><label>Suất/thực đơn</label><input name="servings_per_menu" type="number" min="0"></div>',
      '<div class="form-field"><label>Đơn giá suất ăn</label><input name="meal_price" type="number" min="0"></div>',
      '<div class="form-field"><label>Chi phí khác</label><input name="other_cost" type="number" min="0"></div></div>',
      '<div class="form-field"><label>Nguyên liệu</label><textarea name="items" style="min-height:180px" placeholder="I000060&#9;0.08&#9;Canh rau&#9;kg&#9;kho&#9;16000"></textarea></div>',
      '<div class="form-actions"><button class="btn btn-primary" type="submit">Lưu và tính cost</button></div></form></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Ghép bếp vào XCOM (xưởng cơm)</h3><p>Chỉ cần làm một lần, có thể sửa</p></div></div><div class="card-body"><form id="kitchenUnitForm" class="payment-grid">',
      '<div class="form-field"><label>Mã bếp</label><input name="kitchen_code" required></div><div class="form-field"><label>Mã XCOM</label><input name="unit_code" required></div>',
      '<button class="btn btn-outline" type="submit">Lưu mapping</button><button class="btn btn-primary" type="button" data-action="choose-mapping-file" data-mapping-type="kitchen_units">Nạp danh sách bếp → XCOM</button></form>',
      '<div class="group-list" style="margin-top:16px">', unitRows || '<div class="muted">Chưa ghép bếp nào vào XCOM.</div>', '</div></div></div></div>',
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
      '<div class="toolbar fade-in"><div class="status-bar">Công thường · tăng ca 150% · Chủ nhật 200% · đêm 130% · lễ 300% · phụ cấp · BHXH · tạm ứng</div>',
      '<div class="compact-controls"><input id="payrollMonth" type="month" value="', esc(state.opsMonth), '"><a class="btn btn-outline" href="/api/export/payroll?month=', encodeURIComponent(state.opsMonth), '">Tải bảng lương</a><button class="btn btn-primary" data-action="choose-attendance">Nạp file chấm công</button></div></div>',
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Thêm/cập nhật nhân sự</h3><p>Mã nhân sự là khóa không trùng</p></div></div><div class="card-body">',
      '<form id="staffForm" class="payment-grid"><div class="form-field"><label>Mã</label><input name="employee_code" required></div>',
      '<div class="form-field"><label>Họ tên</label><input name="full_name" required></div><div class="form-field"><label>Chức vụ</label><input name="role_name"></div>',
      '<div class="form-field"><label>Bếp</label><input name="kitchen"></div><div class="form-field"><label>Lương cơ bản</label><input name="base_salary" type="number" min="0"></div>',
      '<div class="form-field"><label>Ngày chuẩn/tháng</label><input name="standard_days" type="number" min="1" value="26"></div><div class="form-field"><label>Giờ chuẩn/ngày</label><input name="standard_hours" type="number" min="1" value="8"></div>',
      '<div class="form-field"><label>Tỷ lệ BHXH NLĐ</label><input name="bhxh_employee_rate" type="number" min="0" step="0.001" value="0"></div><div class="form-field"><label>Tỷ lệ BHXH công ty</label><input name="bhxh_company_rate" type="number" min="0" step="0.001" value="0"></div>',
      '<button class="btn btn-outline" type="submit">Lưu nhân sự</button></form></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Chi phí lao động theo bếp</h3><p>Đọc từ sheet chấm công chợ</p></div></div><div class="table-wrap"><table><thead><tr><th>Ngày</th><th>Bếp</th><th>Chi phí</th></tr></thead><tbody>',
      laborRows || '<tr><td colspan="3"><div class="empty">Chưa nạp file chấm công tháng này.</div></td></tr>',
      '</tbody></table></div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Chấm/sửa công một ngày</h3><p>Dùng khi cần bổ sung phát sinh sau khi nạp Excel</p></div></div><div class="card-body"><form id="attendanceForm" class="payment-grid">',
      '<div class="form-field"><label>Mã nhân sự</label><input name="employee_code" required></div><div class="form-field"><label>Ngày</label><input name="work_date" type="date" value="', esc(state.opsDate), '" required></div>',
      '<div class="form-field"><label>Giờ thường</label><input name="normal_hours" type="number" min="0" step="0.5"></div><div class="form-field"><label>Tăng ca</label><input name="overtime_hours" type="number" min="0" step="0.5"></div>',
      '<div class="form-field"><label>Chủ nhật</label><input name="sunday_hours" type="number" min="0" step="0.5"></div><div class="form-field"><label>Ca đêm</label><input name="night_hours" type="number" min="0" step="0.5"></div>',
      '<div class="form-field"><label>Ngày lễ</label><input name="holiday_hours" type="number" min="0" step="0.5"></div><div class="form-field span-2"><label>Ghi chú</label><input name="note"></div>',
      '<button class="btn btn-outline" type="submit">Lưu chấm công</button></form></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Khoản lương theo tháng</h3><p>Phụ cấp, trách nhiệm, BHXH, tạm ứng, thử việc hoặc chốt thực lĩnh theo file hiện tại</p></div></div><div class="card-body"><form id="payrollAdjustmentForm" class="payment-grid">',
      '<div class="form-field"><label>Mã nhân sự</label><input name="employee_code" required></div><div class="form-field"><label>Tháng</label><input name="month" type="month" value="', esc(state.opsMonth), '" required></div>',
      '<div class="form-field"><label>Phụ cấp</label><input name="allowance" type="number" value="0"></div><div class="form-field"><label>Trách nhiệm</label><input name="responsibility" type="number" value="0"></div>',
      '<div class="form-field"><label>Tạm ứng</label><input name="advance" type="number" value="0"></div><div class="form-field"><label>Khấu trừ thử việc</label><input name="probation_deduction" type="number" value="0"></div>',
      '<div class="form-field"><label>BHXH người lao động</label><input name="bhxh_employee_amount" type="number" value="0"></div><div class="form-field"><label>BHXH công ty</label><input name="bhxh_company_amount" type="number" value="0"></div>',
      '<div class="form-field"><label>Tổng lương chốt</label><input name="gross_override" type="number" value="0"></div><div class="form-field"><label>Thực lĩnh chốt</label><input name="net_override" type="number" value="0"></div>',
      '<div class="form-field"><label><input name="use_override" type="checkbox"> Dùng số chốt thay công thức</label></div><div class="form-field span-2"><label>Ghi chú</label><input name="note"></div>',
      '<button class="btn btn-primary" type="submit">Lưu khoản lương</button></form></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Bảng lương ', esc(state.opsMonth),
      '</h3><p>Tính từ dữ liệu chấm công chuẩn hóa; các khoản điều chỉnh lưu riêng theo tháng</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Nhân sự</th><th>Chức vụ</th><th>HC</th><th>TC</th><th>CN</th><th>Đêm</th><th>Lễ</th><th>PC+TN</th><th>Tổng lương</th><th>BHXH NLĐ</th><th>Tạm ứng+TV</th><th>Thực lĩnh</th></tr></thead><tbody>',
      rows || '<tr><td colspan="13"><div class="empty">Chưa có nhân sự/chấm công.</div></td></tr>',
      '</tbody></table></div></div>'
    ]);
  }

  function renderPrinting() {
    var o = state.operations;
    if (!o) { loadOperations(); return; }
    var jobs = o.print_jobs.filter(function (item) { return !state.batchId || item.batch_id === state.batchId; });
    var rows = jobs.map(function (item) {
      return '<tr><td>' + esc(item.document_type) + '</td><td><span class="tag ' +
        (item.status === "printed" ? "tag-ok" : item.status === "error" ? "tag-red" : "tag-warn") + '">' +
        esc(item.status) + '</span></td><td>' + esc(item.approved_at || "") + '</td><td>' +
        esc(item.printed_at || "") + '</td><td>' + esc(item.error_message || "") + '</td></tr>';
    }).join("");
    content.innerHTML = html([
      '<div class="code-note fade-in"><strong>Luồng bắt buộc:</strong> duyệt phiên đơn → chuẩn bị file → người dùng duyệt bộ in → bấm in. Không tự in theo lịch và không tự phát hành hóa đơn.</div>',
      '<div class="toolbar"><div class="status-bar">Một PC Windows · một máy in mặc định đã cấu hình</div><div class="compact-controls">',
      '<button class="btn btn-outline" data-action="prepare-print" ', state.batchId ? '' : 'disabled', '>1. Chuẩn bị</button>',
      '<button class="btn btn-outline" data-action="approve-print" ', state.batchId ? '' : 'disabled', '>2. Duyệt bộ in</button>',
      '<button class="btn btn-primary" data-action="run-print" ', state.batchId ? '' : 'disabled', '>3. In một nút</button></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Cấu hình máy in</h3><p>Để trống tên sẽ dùng máy in mặc định Windows</p></div></div><div class="card-body">',
      '<form id="printSettingsForm" class="payment-grid"><div class="form-field span-2"><label>Tên máy in</label><input name="printer_name" value="', esc(o.printer.name), '"></div>',
      '<div class="form-field"><label>Số bản</label><input name="copies" type="number" min="1" max="10" value="', esc(o.printer.copies), '"></div>',
      '<div class="form-field"><label>Khổ giấy</label><select name="paper"><option>A4</option><option>A5</option></select></div>',
      '<button class="btn btn-outline" type="submit">Lưu cấu hình</button></form></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Hàng đợi in</h3><p>Phiên đơn đang chọn</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Chứng từ</th><th>Trạng thái</th><th>Duyệt lúc</th><th>In lúc</th><th>Lỗi</th></tr></thead><tbody>',
      rows || '<tr><td colspan="5"><div class="empty">Chưa chuẩn bị bộ in.</div></td></tr>',
      '</tbody></table></div></div>'
    ]);
  }

  function renderSettings() {
    var d = state.data;
    var synced = d.master.settings.master_synced_at || "Chưa đồng bộ";
    var m = state.minvoiceStatus;
    var minvoiceTitle = m && m.connected ? "Đã kết nối M-Invoice" : "Kiểm tra kết nối M-Invoice";
    var minvoiceText = m && m.connected
      ? "API M-Invoice chỉ đọc hoạt động · " + num(m.outgoing.series_count) + " ký hiệu hóa đơn. Hóa đơn đầu vào đồng bộ riêng qua mSMI."
      : "Kiểm tra tài khoản theo chế độ chỉ đọc; không tạo, ký hoặc phát hành hóa đơn.";
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
      '<div class="form-actions"><button class="btn btn-primary" data-action="sync-master">Đồng bộ lại từ Excel</button></div></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Sao lưu dữ liệu</h3><p>Tải toàn bộ đơn, công nợ và thanh toán về máy</p></div></div>',
      '<div class="card-body"><div class="code-note"><strong>Dữ liệu lưu tại máy chạy hệ thống.</strong> Máy thứ hai cùng Wi-Fi/LAN có thể dùng chung khi máy chủ đang mở.</div>',
      '<div class="form-actions"><a class="btn btn-primary" href="/api/backup">Tải bản sao lưu SQLite</a></div></div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Thông tin đề nghị thanh toán</h3><p>Đã lấy từ mẫu TĐP khách cung cấp; có thể sửa khi tài khoản hoặc người đại diện thay đổi</p></div></div><div class="card-body">',
      '<form id="documentSettingsForm" class="payment-grid"><div class="form-field span-2"><label>Người đại diện / đề nghị</label><input name="payment_requester" required value="', esc(d.master.settings.payment_requester || ""), '"></div>',
      '<div class="form-field"><label>Số tài khoản nhận tiền</label><input name="payment_bank_account" inputmode="numeric" required value="', esc(d.master.settings.payment_bank_account || ""), '"></div>',
      '<div class="form-field span-2"><label>Ngân hàng</label><input name="payment_bank_name" required value="', esc(d.master.settings.payment_bank_name || ""), '"></div>',
      '<button class="btn btn-primary" type="submit">Lưu thông tin</button></form>',
      '<div class="code-note" style="margin-top:14px"><strong>Kiểm soát:</strong> hệ thống sẽ không xuất đề nghị thanh toán nếu thiếu một trong ba thông tin trên.</div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Tên xuất hóa đơn</h3><p>Ghi nhớ tên đầu ra chuẩn theo mã hàng; nếu chưa khai báo sẽ dùng tên danh mục TĐP</p></div></div><div class="card-body">',
      '<form id="outgoingNameForm" class="payment-grid"><div class="form-field"><label>Mã hàng</label><input name="product_code" required></div>',
      '<div class="form-field span-2"><label>Tên xuất hóa đơn</label><input name="invoice_name" required></div><button class="btn btn-outline" type="submit">Lưu tên đầu ra</button>',
      '<button class="btn btn-primary" type="button" data-action="choose-mapping-file" data-mapping-type="invoice_names">Nạp danh sách từ Excel</button></form>',
      '<div class="status-bar" style="margin-top:16px">Đã lưu ', num(d.master.outgoing_name_count || 0), ' tên đầu ra</div>',
      '<div class="group-list" style="margin-top:12px">', outgoingRows || '<div class="muted">Chưa có tên đầu ra riêng; hệ thống đang dùng tên danh mục TĐP.</div>', '</div></div></div>',
      mappingPreviewHtml("invoice_names"),
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Ranh giới tích hợp</h3><p>Trạng thái kỹ thuật minh bạch</p></div></div>',
      '<div class="card-body"><div class="flow">',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>Excel & dữ liệu vận hành</strong><span>Đã chạy thật: nhập, sửa, lưu, tính và xuất động</span></div></div>',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>mSMI và M-Invoice an toàn</strong><span>Đầu vào đồng bộ tăng dần; đầu ra tạo dự thảo, người dùng kiểm tra và phát hành</span></div></div>',
      '<div class="flow-step"><div class="num">API</div><div><strong>Không tự gửi Zalo, ký hoặc phát hành</strong><span>Các thao tác đối ngoại luôn chờ người dùng duyệt</span></div></div>',
      "</div></div></div>"
    ]);
  }

  function render() {
    if (state.busy || !state.data) return;
    var views = {
      home: renderHome,
      orders: renderOrders,
      purchases: renderPurchases,
      deliveries: renderDeliveries,
      quotes: renderQuotes,
      reports: renderReports,
      documents: renderDocuments,
      inventory: renderInventory,
      msmi: renderMsmi,
      kitchen: renderKitchen,
      payroll: renderPayroll,
      printing: renderPrinting,
      settings: renderSettings
    };
    (views[state.view] || renderHome)();
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

  function openOrderModal(id) {
    var d = state.data;
    var item = id ? d.orders.find(function (row) { return row.id === Number(id); }) : null;
    item = item || {
      work_date: d.batch ? d.batch.work_date : new Date().toISOString().slice(0, 10),
      contractor: "", kitchen: "", product_code: "", product_name: "", qty: 0,
      actual_received: 0, actual_delivered: 0, unit: "", supplier: "",
      damaged_qty: 0, supplier_return_qty: 0, customer_return_qty: 0,
      buy_price: 0, sell_price: 0, tax: "KKKNT", purchase_list: 0,
      seller: "", cccd: "", note: ""
    };
    state.editingId = id ? Number(id) : null;
    state.modalMode = "order";
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
      field("ĐVT", "unit", item.unit, "text", "required"),
      field("Số lượng đặt", "qty", item.qty, "number", 'step="0.01" min="0" required'),
      field("Số thực nhận", "actual_received", item.actual_received, "number", 'step="0.01" min="0" required'),
      field("Số thực giao", "actual_delivered", item.actual_delivered, "number", 'step="0.01" min="0" required'),
      field("Hàng hỏng", "damaged_qty", item.damaged_qty, "number", 'step="0.01" min="0"'),
      field("Trả NCC", "supplier_return_qty", item.supplier_return_qty, "number", 'step="0.01" min="0"'),
      field("Khách trả", "customer_return_qty", item.customer_return_qty, "number", 'step="0.01" min="0"'),
      field("Giá mua", "buy_price", item.buy_price, "number", 'step="1" min="0" required'),
      field("Giá bán", "sell_price", item.sell_price, "number", 'step="1" min="0" required'),
      '<div class="form-field"><label>Thuế</label><select name="tax"><option value="KKKNT"',
      String(item.tax).toUpperCase() === "KKKNT" ? " selected" : "",
      '>KKKNT</option><option value="0.08"', n(item.tax) === 0.08 ? " selected" : "",
      ">8%</option></select></div>",
      field("Người bán bảng kê", "seller", item.seller),
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

  function openPasteModal() {
    state.editingId = null;
    state.modalMode = "paste";
    document.getElementById("modalTitle").textContent = "Dán nhiều dòng từ Excel";
    orderForm.innerHTML = html([
      '<div class="form-grid"><div class="form-field span-4"><div class="code-note"><strong>Cách nhanh nhất:</strong> sao chép vùng Excel có hàng tiêu đề rồi dán vào đây. Hệ thống nhận các cột Mã bếp, Mã hàng/Tên hàng, Số lượng, NCC, Giá mua, Giá bán, Thuế, Ghi chú.<br><br>Nếu không có tiêu đề, dùng thứ tự: Mã bếp → Tên hàng → Số lượng → NCC → Giá mua → Giá bán → Thuế → Ghi chú.</div></div>',
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

  function openImportModal(payload) {
    state.editingId = null;
    state.modalMode = "import";
    state.pendingImport = payload;
    document.getElementById("modalTitle").textContent = "Chọn sheet đơn hàng";
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
      var checked = useDateMatched
        ? dateToken(sheet.name) === fileDate
        : (usePreferred ? sheet.name.toLowerCase().indexOf("đơn hàng") >= 0 : true);
      return '<label class="sheet-choice"><input type="checkbox" name="sheets" value="' + esc(sheet.name) + '" ' +
        (checked ? "checked" : "") + '><span><strong>' + esc(sheet.name) + "</strong><small>" +
        sheet.rows + " dòng nhận diện · hàng tiêu đề " + sheet.headerRow + "</small></span></label>";
    }).join("");
    var fallback = state.data && state.data.batch
      ? state.data.batch.work_date : new Date().toISOString().slice(0, 10);
    if (fileDate) {
      var parts = fileDate.split(".");
      fallback = new Date().getFullYear() + "-" + String(parts[1]).padStart(2, "0") + "-" + String(parts[0]).padStart(2, "0");
    }
    orderForm.innerHTML = html([
      '<div class="form-grid"><div class="form-field span-4"><div class="code-note"><strong>File: ',
      esc(payload.filename), "</strong><br>Chỉ các sheet được chọn mới đi vào phiên đơn. Việc này tránh cộng trùng sheet gộp, sheet đặt hàng hoặc dữ liệu lưu cũ.</div></div>",
      '<div class="form-field span-4"><label>Sheet cần nhập</label><div class="sheet-list">', sheetCards, "</div></div>",
      field("Ngày làm việc dự phòng", "work_date", fallback, "date", "required", "span-2"),
      '<div class="form-actions"><button type="button" class="btn btn-outline" data-action="close-modal">Hủy</button>',
      '<button type="submit" class="btn btn-primary">Nhập các sheet đã chọn</button></div></div>'
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
  }

  async function importExcel(file) {
    if (!file) return;
    setBusy(true, "Đang nhận diện các sheet trong " + file.name + "…");
    try {
      var form = new FormData();
      form.append("file", file);
      var payload = await api("/api/import/analyze", { method: "POST", body: form });
      state.busy = false;
      render();
      openImportModal(payload);
    } catch (error) {
      state.busy = false;
      render();
      showToast(error.message, true);
    }
  }

  async function newBatch() {
    var workDate = window.prompt("Ngày làm việc (YYYY-MM-DD):", new Date().toISOString().slice(0, 10));
    if (!workDate) return;
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
        showToast("Cần chọn ít nhất một sheet", true);
        return;
      }
      try {
        setBusy(true, "Đang nhập, đối chiếu danh mục và kiểm tra giá…");
        var imported = await api("/api/import/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            token: state.pendingImport.token,
            work_date: form.get("work_date"),
            sheets: sheets
          })
        });
        state.pendingImport = null;
        closeModal();
        state.batchId = imported.batch.id;
        state.view = "orders";
        await loadData(state.batchId, true);
        showToast("Đã nhập " + imported.orders.length + " dòng · " + imported.summary.totals.errors + " lỗi · " + (imported.summary.totals.warnings || 0) + " cảnh báo");
      } catch (error) {
        state.busy = false;
        render();
        backdrop.hidden = false;
        showToast(error.message, true);
      }
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

  async function approveBatch() {
    if (!state.batchId || !window.confirm("Duyệt phiên đơn này để chốt số liệu đầu ra?")) return;
    try {
      await api("/api/batches/" + state.batchId + "/approve", { method: "POST" });
      await loadData(state.batchId, true);
      showToast("Đã duyệt phiên đơn · Các đầu ra sẵn sàng");
    } catch (error) { showToast(error.message, true); }
  }

  function copySupplierNeed(groupIndex) {
    var group = state.supplierNeeds && state.supplierNeeds.groups[Number(groupIndex)];
    if (!group) { showToast("Không tìm thấy nhóm đơn NCC", true); return; }
    var text = ["ĐƠN ĐẶT HÀNG " + group.supplier.toUpperCase() + " – " + dateVN(state.data.batch.work_date),
      "Bếp: " + group.kitchen]
      .concat(group.items.map(function (item, index) {
        return (index + 1) + ". " + item.product_name + ": " + num(item.required_qty) + " " + item.unit;
      })).join("\n");
    function fallback() {
      var area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).catch(fallback);
    else fallback();
    showToast("Đã sao chép lượng cần mua sau trừ tồn · Dán vào Zalo để gửi");
  }

  async function savePayment(formElement) {
    var body = Object.fromEntries(new FormData(formElement).entries());
    body.amount = n(body.amount);
    body.party_type = body.kind === "receipt" ? "contractor" : "supplier";
    try {
      await api("/api/payments", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
      state.debtPeriod = null;
      await loadData(state.batchId, true);
      showToast("Đã ghi nhận thanh toán");
    } catch (error) { showToast(error.message, true); }
  }

  async function saveBalance(formElement) {
    var body = Object.fromEntries(new FormData(formElement).entries());
    body.opening = n(body.opening);
    try {
      await api("/api/balances", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
      state.debtPeriod = null;
      await loadData(state.batchId, true);
      showToast("Đã cập nhật số dư đầu kỳ");
    } catch (error) { showToast(error.message, true); }
  }

  async function fetchDebtPeriod() {
    if (!state.debtFrom || !state.debtTo || state.debtLoading) return;
    state.debtLoading = true;
    try {
      state.debtPeriod = await api("/api/debts?from=" + encodeURIComponent(state.debtFrom) +
        "&to=" + encodeURIComponent(state.debtTo));
      if (state.view === "reports") renderReports();
    } catch (error) { showToast(error.message, true); }
    finally { state.debtLoading = false; }
  }

  async function fetchOutgoingInvoices() {
    try {
      var payload = await api("/api/outgoing-invoices");
      state.outgoingInvoices = payload.items || [];
      if (state.view === "documents") renderDocuments();
    } catch (error) { showToast(error.message, true); }
  }

  async function checkMinvoice(button) {
    try {
      button.disabled = true;
      button.textContent = "Đang kiểm tra…";
      state.minvoiceStatus = await api("/api/minvoice/status");
      renderSettings();
      showToast("API M-Invoice chính thức đã kết nối · chỉ đọc · " + num(state.minvoiceStatus.outgoing.series_count) + " ký hiệu");
    } catch (error) {
      button.disabled = false;
      button.textContent = "Kiểm tra lại";
      showToast(error.message, true);
    }
  }

  async function deletePayment(id) {
    if (!window.confirm("Xóa giao dịch thanh toán này?")) return;
    try {
      await api("/api/payments/" + id, { method: "DELETE" });
      await loadData(state.batchId, true);
      showToast("Đã xóa giao dịch");
    } catch (error) { showToast(error.message, true); }
  }

  async function refreshOperations(message) {
    state.operations = null;
    await loadOperations(true);
    if (message) showToast(message);
  }

  async function importAttendance(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("file", file);
      var result = await api("/api/attendance/import", { method: "POST", body: form });
      if (result.month) state.opsMonth = result.month;
      await refreshOperations("Đã nạp " + result.attendance_entries + " ngày công và " + result.labor_cost_entries + " dòng chi phí bếp");
    } catch (error) { showToast(error.message, true); }
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

  async function previewKitchenWorkbook(file) {
    if (!file) return;
    try {
      var form = new FormData();
      form.append("work_date", state.opsDate);
      form.append("file", file);
      state.kitchenImportPreview = await api("/api/kitchen/import/preview", { method: "POST", body: form });
      renderKitchen();
      showToast("Đã kiểm tra file xưởng cơm · xem kỹ rồi xác nhận nhập");
    } catch (error) {
      state.kitchenImportPreview = null;
      showToast(error.message, true);
    }
  }

  async function confirmKitchenImport(button) {
    var preview = state.kitchenImportPreview;
    if (!preview || !preview.can_confirm) return;
    try {
      button.disabled = true;
      button.textContent = "Đang ghi dữ liệu…";
      var result = await api("/api/kitchen/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: preview.token, confirmed: true })
      });
      state.kitchenImportPreview = null;
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

  async function jsonWrite(url, method, body, success) {
    try {
      await api(url, { method: method || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      await refreshOperations(success);
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
    state.operations = null;
    state.debtPeriod = null;
    state.debtLoading = false;
    state.debtFrom = "";
    state.debtTo = "";
    state.outgoingInvoices = null;
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
  orderForm.addEventListener("submit", saveOrder);
  backdrop.addEventListener("click", function (event) {
    if (event.target === backdrop) closeModal();
  });

  content.addEventListener("submit", async function (event) {
    if (event.target.id === "debtPeriodForm") {
      event.preventDefault();
      var debtRange = Object.fromEntries(new FormData(event.target).entries());
      state.debtFrom = debtRange.from;
      state.debtTo = debtRange.to;
      state.debtPeriod = null;
      await fetchDebtPeriod();
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
        state.debtPeriod = null;
        await loadData(state.batchId, true);
        showToast("Đã lưu điều chỉnh công nợ");
      } catch (error) { showToast(error.message, true); }
    }
    if (event.target.id === "paymentForm") {
      event.preventDefault();
      savePayment(event.target);
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
    if (event.target.id === "mealPlanForm") {
      event.preventDefault();
      var plan = Object.fromEntries(new FormData(event.target).entries());
      plan.meal_count = n(plan.meal_count);
      plan.menu_count = n(plan.menu_count) || 1;
      plan.servings_per_menu = n(plan.servings_per_menu);
      plan.meal_price = n(plan.meal_price);
      plan.other_cost = n(plan.other_cost);
      plan.items = String(plan.items || "").split(/\r?\n/).filter(Boolean).map(function (line) {
        var cells = line.split("\t");
        return { product_code: cells[0] || "", norm_qty: n(cells[1]), dish_name: cells[2] || "",
          unit: cells[3] || "", supplier: cells[4] || "", buy_price: n(cells[5]) };
      });
      state.opsDate = plan.work_date;
      jsonWrite("/api/kitchen/plans", "POST", plan, "Đã lưu kế hoạch và tính cost");
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
      window.location.href = "/api/export/payment-request/" + encodeURIComponent(paymentRequest.contractor) +
        "?from=" + encodeURIComponent(from) + "&to=" + encodeURIComponent(state.data.batch.work_date);
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
    if (event.target.id === "orderSearch") {
      state.orderFilter = event.target.value;
      var term = state.orderFilter.toLowerCase();
      content.querySelectorAll("tbody tr").forEach(function (row) {
        row.hidden = term && row.textContent.toLowerCase().indexOf(term) < 0;
      });
    }
  });

  content.addEventListener("change", function (event) {
    if (event.target.id === "quoteContractor") {
      state.quoteContractor = event.target.value;
      state.quoteItems = null;
      renderQuotes();
    }
    if (event.target.id === "inventoryDate" || event.target.id === "kitchenDate") {
      state.opsDate = event.target.value;
      state.opsMonth = state.opsDate.slice(0, 7);
      if (event.target.id === "kitchenDate") {
        state.kitchenImportPreview = null;
        state.mealAttendancePreview = null;
      }
      if (event.target.id === "inventoryDate") state.openingImportPreview = null;
      state.operations = null;
      loadOperations();
    }
    if (event.target.id === "payrollMonth") {
      state.opsMonth = event.target.value;
      state.operations = null;
      loadOperations();
    }
  });

  content.addEventListener("click", async function (event) {
    var viewButton = event.target.closest("[data-view]");
    if (viewButton) { navigate(viewButton.dataset.view); return; }
    var button = event.target.closest("[data-action]");
    if (!button) return;
    var action = button.dataset.action;
    if (action === "reload") loadData();
    if (action === "reload-operations") { state.operations = null; loadOperations(); }
    if (action === "choose-excel") excelInput.click();
    if (action === "choose-attendance") attendanceInput.click();
    if (action === "choose-mapping-file") {
      state.mappingImportType = button.dataset.mappingType || "";
      state.mappingPreview = null;
      mappingFileInput.click();
    }
    if (action === "choose-kitchen-workbook") {
      state.kitchenImportPreview = null;
      kitchenWorkbookInput.click();
    }
    if (action === "choose-meal-attendance") {
      state.mealAttendancePreview = null;
      mealAttendanceInput.click();
    }
    if (action === "choose-opening-workbook") {
      var openingPeriod = document.querySelector('#openingForm [name="period"]');
      if (openingPeriod && openingPeriod.value) state.opsMonth = openingPeriod.value;
      state.openingImportPreview = null;
      openingWorkbookInput.click();
    }
    if (action === "cancel-opening-import") {
      state.openingImportPreview = null;
      renderInventory();
    }
    if (action === "confirm-opening-import") await confirmOpeningImport(button);
    if (action === "cancel-kitchen-import") {
      state.kitchenImportPreview = null;
      renderKitchen();
    }
    if (action === "confirm-kitchen-import") await confirmKitchenImport(button);
    if (action === "cancel-meal-attendance-import") {
      state.mealAttendancePreview = null;
      renderKitchen();
    }
    if (action === "confirm-meal-attendance-import") await confirmMealAttendance(button);
    if (action === "cancel-mapping-import") {
      var cancelledType = state.mappingPreview && state.mappingPreview.mapping_type;
      state.mappingPreview = null;
      state.mappingImportType = "";
      if (cancelledType === "kitchen_units") renderKitchen(); else renderSettings();
    }
    if (action === "confirm-mapping-import") await confirmMappingImport(button);
    if (action === "new-batch") newBatch();
    if (action === "paste-orders") openPasteModal();
    if (action === "add-order") openOrderModal(null);
    if (action === "edit-order") openOrderModal(button.dataset.id);
    if (action === "delete-order") deleteOrder(button.dataset.id);
    if (action === "approve-batch") approveBatch();
    if (action === "copy-supplier-need") copySupplierNeed(button.dataset.groupIndex);
    if (action === "toggle-supplier-rule") {
      try {
        await api("/api/supplier-rules/" + encodeURIComponent(button.dataset.supplier), {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ combine_kitchens: button.dataset.combine === "1" })
        });
        state.supplierNeeds = null;
        await fetchSupplierNeeds();
        showToast(button.dataset.combine === "1" ? "Đã gộp đơn NCC qua nhiều bếp" : "Đã tách đơn NCC theo từng bếp");
      } catch (error) { showToast(error.message, true); }
    }
    if (action === "delete-payment") deletePayment(button.dataset.id);
    if (action === "check-minvoice") checkMinvoice(button);
    if (action === "sync-msmi") {
      try {
        button.disabled = true;
        button.textContent = "Đang đồng bộ…";
        var synced = await api("/api/msmi/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        await refreshOperations("mSMI: " + synced.new_invoices + " hóa đơn mới, " + synced.known_invoices + " hóa đơn đã có");
      } catch (error) { showToast(error.message, true); button.disabled = false; button.textContent = "Đồng bộ hóa đơn mới"; }
    }
    if (action === "save-msmi-mapping") {
      var mappingInput = document.getElementById("map_" + button.dataset.id);
      if (!mappingInput || !mappingInput.value.trim()) { showToast("Cần nhập mã hàng TĐP", true); return; }
      jsonWrite("/api/msmi/items/" + button.dataset.id + "/mapping", "PUT", { product_code: mappingInput.value.trim() }, "Đã ghép và ghi nhớ mã hàng");
    }
    if (action === "create-msmi-receipt") {
      if (!window.confirm("Tạo phiếu nhập kho từ hóa đơn này? Thao tác có chống trùng theo _id.")) return;
      jsonWrite("/api/msmi/invoices/" + button.dataset.id + "/receipt", "POST", {}, "Đã tạo phiếu nhập kho");
    }
    if (action === "create-outgoing-drafts") {
      try {
        var drafts = await api("/api/outgoing-invoices/draft/" + state.batchId, { method: "POST" });
        state.outgoingInvoices = null;
        await fetchOutgoingInvoices();
        showToast("Đã tạo " + drafts.drafts.length + " dự thảo · chưa ký/phát hành");
      } catch (error) { showToast(error.message, true); }
    }
    if (action === "confirm-outgoing-issued") {
      if (!window.confirm("Chỉ xác nhận khi hóa đơn đã được kiểm tra, ký và phát hành trên phần mềm hóa đơn. Tiếp tục?")) return;
      try {
        await api("/api/outgoing-invoices/" + button.dataset.id + "/confirm-issued", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true })
        });
        state.outgoingInvoices = null;
        state.operations = null;
        await fetchOutgoingInvoices();
        showToast("Đã ghi nhận hóa đơn phát hành và ghi xuất kho");
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
        state.operations = null;
        await fetchOutgoingInvoices();
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
      if (!window.confirm("Duyệt toàn bộ chứng từ của phiên đang chọn để sẵn sàng in?")) return;
      jsonWrite("/api/print/approve/" + state.batchId, "POST", {}, "Đã duyệt bộ chứng từ in");
    }
    if (action === "run-print") {
      if (!window.confirm("Gửi toàn bộ chứng từ đã duyệt sang máy in mặc định Windows?")) return;
      jsonWrite("/api/print/run/" + state.batchId, "POST", { dry_run: false }, "Đã gửi bộ chứng từ sang máy in");
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

  loadData(null);
})();
