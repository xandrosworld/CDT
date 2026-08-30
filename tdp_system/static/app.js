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
    minvoiceStatus: null,
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
    settings: "Danh mục và sao lưu"
  };

  var content = document.getElementById("content");
  var pageTitle = document.getElementById("pageTitle");
  var sidebar = document.getElementById("sidebar");
  var toast = document.getElementById("toast");
  var batchSelect = document.getElementById("batchSelect");
  var excelInput = document.getElementById("excelInput");
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
      state.busy = false;
      renderBatchSelect();
      render();
    } catch (error) {
      state.busy = false;
      content.innerHTML = '<div class="card"><div class="empty"><h3>Không nạp được dữ liệu</h3><p>' +
        esc(error.message) + '</p><button class="btn btn-primary" data-action="reload">Thử lại</button></div></div>';
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
    render();
  }

  function statCard(label, value, sub, icon) {
    return '<div class="stat-card"><div class="stat-head"><span class="label">' + esc(label) +
      '</span><div class="stat-icon">' + icon + '</div></div><span class="value">' + esc(value) +
      '</span><div class="sub">' + esc(sub) + "</div></div>";
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
        '</td><td class="num-cell">', num(item.actual_received), '</td><td class="num-cell">', num(item.actual_delivered),
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

  function renderPurchases() {
    var d = state.data;
    if (!d.batch) {
      content.innerHTML = emptyBatch("Chưa có dữ liệu đặt hàng", "Nạp đơn để hệ thống tự gộp số lượng theo nhà cung cấp.");
      return;
    }
    var groups = groupBy(d.orders, "supplier");
    var cards = Object.entries(groups).map(function (entry) {
      var supplier = entry[0], items = entry[1];
      var lines = items.map(function (item) {
        return '<div class="group-line"><div><strong>' + esc(item.product_name) + "</strong><span>" +
          esc(item.product_code) + " · " + esc(item.kitchen) + (item.note ? " · " + esc(item.note) : "") +
          "</span></div><strong>" + num(item.qty) + " " + esc(item.unit) + "</strong></div>";
      }).join("");
      return '<div class="group-card"><div class="group-title"><div><strong>NCC ' + esc(supplier.toUpperCase()) +
        "</strong><span>" + items.length + ' dòng hàng</span></div><button class="btn btn-small btn-outline" data-action="copy-supplier" data-supplier="' +
        esc(supplier) + '">Sao chép gửi Zalo</button></div><div class="group-list">' + lines +
        '</div><div class="group-total"><span>Tổng số lượng cộng gộp</span><strong>' +
        num(items.reduce(function (sum, item) { return sum + n(item.qty); }, 0)) + "</strong></div></div>";
    }).join("");
    content.innerHTML = '<div class="toolbar fade-in"><div class="status-bar">✓ Đã tách ' + d.orders.length +
      " dòng thành " + Object.keys(groups).length + ' nhà cung cấp theo số lượng đặt</div><a class="btn btn-primary" href="' +
      exportUrl("suppliers") + '">Tải Excel đặt hàng</a></div><div class="group-grid fade-in">' + cards + "</div>";
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
    var s = d.summary;
    var contractorRows = Object.entries(s.contractors).map(function (entry) {
      var name = entry[0], item = entry[1];
      return "<tr><td><strong>" + esc(name) + '</strong></td><td class="num-cell">' + money(item.opening) +
        '</td><td class="num-cell">' + money(item.total) + '</td><td class="num-cell">' + money(item.paid) +
        '</td><td class="num-cell"><strong>' + money(item.balance) + "</strong></td></tr>";
    }).join("");
    var supplierRows = Object.entries(s.suppliers).map(function (entry) {
      var name = entry[0], item = entry[1];
      return "<tr><td><strong>" + esc(name) + '</strong></td><td class="num-cell">' + money(item.opening) +
        '</td><td class="num-cell">' + money(item.cost) + '</td><td class="num-cell">' + money(item.paid) +
        '</td><td class="num-cell"><strong>' + money(item.balance) + "</strong></td></tr>";
    }).join("");
    var paymentRows = (d.payments || []).map(function (item) {
      return "<tr><td>" + dateVN(item.payment_date) + "</td><td>" +
        (item.kind === "receipt" ? "Thu khách hàng" : "Trả nhà cung cấp") + "</td><td><strong>" +
        esc(item.party_code) + '</strong></td><td class="num-cell">' + money(item.amount) + "</td><td>" +
        esc(item.note) + '</td><td><button class="icon-button danger" data-action="delete-payment" data-id="' +
        item.id + '">×</button></td></tr>';
    }).join("");
    content.innerHTML = html([
      '<div class="toolbar fade-in"><div class="status-bar">✓ Doanh thu theo thực giao · Giá vốn theo thực nhận · Có số dư đầu kỳ và thanh toán</div>',
      '<a class="btn btn-primary" href="', exportUrl("report"), '">Tải báo cáo Excel</a></div>',
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
      '<div class="section-grid" style="margin-top:18px"><div class="card"><div class="card-head"><div><h3>Công nợ phải thu</h3><p>Đầu kỳ + phát sinh có thuế − đã thu</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>Nhà thầu</th><th>Đầu kỳ</th><th>Phát sinh</th><th>Đã thu</th><th>Còn thu</th></tr></thead><tbody>',
      contractorRows, "</tbody></table></div></div>",
      '<div class="card"><div class="card-head"><div><h3>Công nợ phải trả</h3><p>Đầu kỳ + giá vốn thực nhận − đã trả</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>NCC</th><th>Đầu kỳ</th><th>Phát sinh</th><th>Đã trả</th><th>Còn trả</th></tr></thead><tbody>',
      supplierRows, "</tbody></table></div></div></div>",
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Nhập số dư đầu kỳ</h3><p>Có thể cập nhật lại khi bắt đầu sử dụng</p></div></div>',
      '<div class="card-body"><form id="balanceForm" class="payment-grid">',
      '<div class="form-field"><label>Nhóm</label><select name="party_type"><option value="contractor">Nhà thầu phải thu</option><option value="supplier">NCC phải trả</option></select></div>',
      '<div class="form-field span-2"><label>Mã nhà thầu / NCC</label><input name="party_code" required></div>',
      '<div class="form-field"><label>Số dư đầu kỳ</label><input name="opening" type="number" required></div>',
      '<button class="btn btn-outline" type="submit">Lưu số dư</button></form></div></div>',
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
    content.innerHTML = html([
      '<div class="code-note fade-in"><strong>Luồng hóa đơn đúng:</strong> hệ thống sinh file 11 cột theo mẫu khách gửi → tải lên phần mềm trung gian kiểm tra tồn → phần mềm trung gian mới đẩy sang M-Invoice.</div>',
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
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Điểm kiểm soát trước khi tải hóa đơn</h3>',
      '<p>Hệ thống không tự nhận là đã phát hành hóa đơn</p></div></div><div class="card-body"><div class="flow">',
      '<div class="flow-step ', d.summary.totals.errors ? "" : "done", '"><div class="num">1</div><div><strong>Đơn đủ dữ liệu</strong><span>',
      d.summary.totals.errors ? d.summary.totals.errors + " dòng còn lỗi" : "Mã, bếp, giá và thuế đã đủ", "</span></div></div>",
      '<div class="flow-step done"><div class="num">2</div><div><strong>Tách đúng nhóm thuế</strong><span>8% và KKKNT không trộn file</span></div></div>',
      '<div class="flow-step"><div class="num">3</div><div><strong>Kiểm tra tồn ở phần mềm trung gian</strong><span>Thao tác ngoài hệ thống này</span></div></div>',
      "</div></div></div>"
    ]);
  }

  function renderSettings() {
    var d = state.data;
    var synced = d.master.settings.master_synced_at || "Chưa đồng bộ";
    var m = state.minvoiceStatus;
    var minvoiceTitle = m && m.connected ? "Đã kết nối M-Invoice" : "Kiểm tra kết nối M-Invoice";
    var minvoiceText = m && m.connected
      ? "API chính thức hoạt động · " + num(m.outgoing.series_count) + " ký hiệu hóa đơn. Hóa đơn đầu vào cần tài khoản mSMI OpenAPI riêng."
      : "Kiểm tra tài khoản theo chế độ chỉ đọc; không tạo, ký hoặc phát hành hóa đơn.";
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
      '<div class="section-grid"><div class="card"><div class="card-head"><div><h3>Đồng bộ danh mục</h3>',
      '<p>Nguồn: Em Thành.xlsx · Lần cuối ', esc(synced), '</p></div></div><div class="card-body">',
      '<div class="code-note"><strong>Đang áp dụng:</strong> HATRAN, ATV, SUPPY… dùng đúng nhóm giá. GIANHAPTAY và YLKHAN là giá theo ngày, không ăn theo nhà thầu nào.</div>',
      '<div class="form-actions"><button class="btn btn-primary" data-action="sync-master">Đồng bộ lại từ Excel</button></div></div></div>',
      '<div class="card"><div class="card-head"><div><h3>Sao lưu dữ liệu</h3><p>Tải toàn bộ đơn, công nợ và thanh toán về máy</p></div></div>',
      '<div class="card-body"><div class="code-note"><strong>Dữ liệu lưu tại máy chạy hệ thống.</strong> Máy thứ hai cùng Wi-Fi/LAN có thể dùng chung khi máy chủ đang mở.</div>',
      '<div class="form-actions"><a class="btn btn-primary" href="/api/backup">Tải bản sao lưu SQLite</a></div></div></div></div>',
      '<div class="card" style="margin-top:18px"><div class="card-head"><div><h3>Ranh giới tích hợp</h3><p>Trạng thái kỹ thuật minh bạch</p></div></div>',
      '<div class="card-body"><div class="flow">',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>Excel & dữ liệu vận hành</strong><span>Đã chạy thật: nhập, sửa, lưu, tính và xuất động</span></div></div>',
      '<div class="flow-step done"><div class="num">✓</div><div><strong>Zalo thủ công có hỗ trợ</strong><span>Sao chép đơn NCC để dán và gửi</span></div></div>',
      '<div class="flow-step"><div class="num">API</div><div><strong>Zalo tự gửi / phần mềm trung gian / M-Invoice</strong><span>Cần tài khoản và tài liệu API của bên thứ ba mới kết nối thật</span></div></div>',
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
        closeModal();
        state.pendingImport = null;
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
    ["qty", "actual_received", "actual_delivered", "buy_price", "sell_price"].forEach(function (key) {
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

  function copySupplier(supplier) {
    var rows = state.data.orders.filter(function (item) { return item.supplier === supplier; });
    var text = ["ĐƠN ĐẶT HÀNG " + supplier.toUpperCase() + " – " + dateVN(state.data.batch.work_date)]
      .concat(rows.map(function (item, index) {
        return (index + 1) + ". " + item.product_name + ": " + num(item.qty) + " " + item.unit +
          (item.note ? " – " + item.note : "");
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
    showToast("Đã sao chép đơn NCC " + supplier + " · Dán vào Zalo để gửi");
  }

  async function savePayment(formElement) {
    var body = Object.fromEntries(new FormData(formElement).entries());
    body.amount = n(body.amount);
    body.party_type = body.kind === "receipt" ? "contractor" : "supplier";
    try {
      await api("/api/payments", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
      });
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
      await loadData(state.batchId, true);
      showToast("Đã cập nhật số dư đầu kỳ");
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
    loadData(state.batchId);
  });
  excelInput.addEventListener("change", function () {
    var file = excelInput.files[0];
    excelInput.value = "";
    importExcel(file);
  });
  orderForm.addEventListener("submit", saveOrder);
  backdrop.addEventListener("click", function (event) {
    if (event.target === backdrop) closeModal();
  });

  content.addEventListener("submit", function (event) {
    if (event.target.id === "paymentForm") {
      event.preventDefault();
      savePayment(event.target);
    }
    if (event.target.id === "balanceForm") {
      event.preventDefault();
      saveBalance(event.target);
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
  });

  content.addEventListener("click", async function (event) {
    var viewButton = event.target.closest("[data-view]");
    if (viewButton) { navigate(viewButton.dataset.view); return; }
    var button = event.target.closest("[data-action]");
    if (!button) return;
    var action = button.dataset.action;
    if (action === "reload") loadData();
    if (action === "choose-excel") excelInput.click();
    if (action === "new-batch") newBatch();
    if (action === "paste-orders") openPasteModal();
    if (action === "add-order") openOrderModal(null);
    if (action === "edit-order") openOrderModal(button.dataset.id);
    if (action === "delete-order") deleteOrder(button.dataset.id);
    if (action === "approve-batch") approveBatch();
    if (action === "copy-supplier") copySupplier(button.dataset.supplier);
    if (action === "delete-payment") deletePayment(button.dataset.id);
    if (action === "check-minvoice") checkMinvoice(button);
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
