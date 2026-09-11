(function () {
  'use strict';
  var serials = new Map();
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  async function checked(response) {
    if (!response.ok) {
      var error = await response.json().catch(function () { return {}; });
      throw new Error(error.error || 'Không lấy được chứng từ; hãy thử lại.');
    }
    return response;
  }
  async function open(body, hostId, printNow) {
    var host = document.getElementById(hostId);
    if (!host) return;
    var serial = (serials.get(hostId) || 0) + 1;
    serials.set(hostId, serial);
    function isCurrent() { return serial === serials.get(hostId) && host.isConnected && document.getElementById(hostId) === host; }
    host.innerHTML = '<div class="document-status" role="status">Đang đọc chứng từ…</div>';
    try {
      var response = await checked(await fetch('/api/documents/preview', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
      }));
      var data = await response.json();
      if (!isCurrent()) return;
      var selected = new Set(data.sheets.map(function (_, i) { return i; }));
      var current = 0;
      host.innerHTML = '<section class="document-preview"><div class="document-toolbar">' +
        '<strong>Xem chứng từ</strong><span class="document-count"></span>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="all">Chọn tất cả</button>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="none">Bỏ chọn</button>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="excel">Tải Excel đã chọn</button>' +
        '<label>Cách in <select class="document-sides" aria-label="Cách in"><option value="simplex">Một mặt</option><option value="duplex">Hai mặt · biên nhận tờ riêng</option></select></label>' +
        '<button type="button" class="btn btn-small btn-primary" data-doc="print">In phiếu đã chọn</button>' +
        '<label>Cỡ chữ <select class="document-zoom" aria-label="Phóng to chứng từ"><option value="0.8">80%</option><option value="1" selected>100%</option><option value="1.25">125%</option><option value="1.5">150%</option></select></label>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="refresh">Đọc lại dữ liệu mới</button></div>' +
        '<p class="document-note">Bản xem, Excel và PDF dùng cùng số liệu tại lúc mở. Có thay đổi đơn thì bấm Đọc lại dữ liệu mới. Bản in A4 nền trắng.</p>' +
        '<p class="document-note document-print-help" role="status"></p>' +
        (data.warnings || []).map(function (warning) { return '<p class="document-note tag-warn" role="alert">' + esc(warning) + '</p>'; }).join('') +
        '<div class="document-sheet-list" role="group" aria-label="Chọn từng chứng từ">' +
        data.sheets.map(function (sheet, i) { return '<div><input type="checkbox" checked data-sheet="' + i + '" aria-label="Chọn ' + esc(sheet.name) + '"><button type="button" class="btn btn-small btn-outline" data-open-sheet="' + i + '">' + esc(sheet.name) + '</button></div>'; }).join('') +
        '</div><div class="document-error" role="alert"></div><div class="document-scroll" tabindex="0" aria-label="Nội dung chứng từ"></div><div class="document-pdf"></div></section>';
      var busy = false, modeTouched = false;
      function printHelp() {
        return host.querySelector('.document-sides').value === 'duplex' ?
          'Trong hộp thoại máy in, chọn in hai mặt và in tất cả trang, kể cả trang trắng. Bảng kê tổng được in hai mặt; mỗi biên nhận có mặt sau trắng để mỗi người một tờ riêng.' :
          'Trong hộp thoại máy in, chọn in một mặt. Mỗi biên nhận in trên một tờ riêng.';
      }
      function update() {
        var mode = host.querySelector('.document-sides');
        if (!modeTouched) mode.value = Array.from(selected).some(function(i){return /(?:^| · )bảng kê tổng$/.test(data.sheets[i].name.trim().toLowerCase());}) ? 'duplex' : 'simplex';
        mode.disabled = busy;
        host.querySelector('.document-print-help').textContent = printHelp();
        host.querySelector('.document-count').textContent = data.sheet_count + ' phiếu · Đã chọn ' + selected.size;
        host.querySelectorAll('[data-doc="excel"],[data-doc="print"]').forEach(function (b) { b.disabled = busy || !selected.size; });
        host.querySelectorAll('[data-sheet]').forEach(function (c) { c.checked = selected.has(Number(c.dataset.sheet)); });
        host.querySelectorAll('[data-sheet],[data-doc="all"],[data-doc="none"],[data-doc="refresh"]').forEach(function(c) { c.disabled=busy; });
      }
      function show(index) {
        current = index;
        var sheet = data.sheets[index], viewport = host.querySelector('.document-scroll');
        viewport.innerHTML = sheet.html;
        viewport.firstElementChild.style.width = Math.max(650, sheet.width) + 'px';
        host.querySelectorAll('[data-open-sheet]').forEach(function (b) { b.setAttribute('aria-pressed', Number(b.dataset.openSheet) === index ? 'true' : 'false'); });
        viewport.style.zoom = host.querySelector('.document-zoom').value;
        viewport.querySelectorAll('[data-shrink]').forEach(function(cell) {
          var available=cell.clientWidth, needed=cell.scrollWidth;
          if(available && needed>available) cell.style.fontSize=(parseFloat(getComputedStyle(cell).fontSize)*available/needed)+'px';
        });
      }
      async function output(type) {
        if (busy || !selected.size) return;
        busy = true; update();
        var errorBox = host.querySelector('.document-error');
        errorBox.textContent = type === 'print' ? 'Đang tạo PDF đúng mẫu, vui lòng chờ…' : '';
        var url = '/api/documents/' + data.token + '/' + (type === 'print' ? 'pdf' : 'excel') + '?sheets=' + Array.from(selected).sort(function(a,b){return a-b;}).join(',');
        if(type === 'print') url += '&sides=' + host.querySelector('.document-sides').value;
        try {
          var response = await checked(await fetch(url));
          var blob = await response.blob();
          if (!isCurrent()) return;
          var blobUrl = URL.createObjectURL(blob);
          errorBox.textContent = '';
          if (type === 'print') {
            var panel = host.querySelector('.document-pdf');
            panel.innerHTML = '<p>Đã mở bản in của phần đã chọn. Nếu hộp thoại chưa bật, bấm nút máy in trong khung PDF.</p><iframe title="Bản in các phiếu đã chọn"></iframe>';
            panel.querySelector('p').textContent += ' ' + printHelp();
            var frame = panel.querySelector('iframe');
            frame.onload = function () { setTimeout(function () { if (!isCurrent() || !frame.isConnected) return; try { frame.contentWindow.focus(); frame.contentWindow.print(); } catch (_) {} }, 700); };
            frame.src = blobUrl;
            panel.scrollIntoView({block:'nearest'});
            setTimeout(function () { URL.revokeObjectURL(blobUrl); }, 600000);
          } else {
            var disposition = response.headers.get('Content-Disposition') || '';
            var name = /filename\*=UTF-8''([^;]+)/i.exec(disposition) || /filename="?([^";]+)/i.exec(disposition);
            var anchor = document.createElement('a'); anchor.href = blobUrl;
            anchor.download = name ? decodeURIComponent(name[1]) : (blob.type.indexOf('zip') >= 0 ? 'Chung_tu.zip' : 'Chung_tu.xlsx');
            anchor.click(); setTimeout(function () { URL.revokeObjectURL(blobUrl); }, 30000);
          }
        } catch (error) { if (isCurrent()) errorBox.textContent = error.message; }
        finally { busy = false; if (isCurrent()) update(); }
      }
      host.onclick = function (event) {
        var sheet = event.target.closest('[data-open-sheet]');
        if (sheet) { show(Number(sheet.dataset.openSheet)); return; }
        var action = event.target.closest('[data-doc]');
        if (!action) return;
        if (busy) return;
        if (action.dataset.doc === 'refresh') { if (!busy) open(body, hostId, false); }
        if (action.dataset.doc === 'all') { data.sheets.forEach(function (_,i) { selected.add(i); }); update(); }
        if (action.dataset.doc === 'none') { selected.clear(); update(); }
        if (action.dataset.doc === 'excel' || action.dataset.doc === 'print') output(action.dataset.doc);
      };
      host.onchange = function(event) {
        if(busy && event.target.matches('[data-sheet]')) { update(); return; }
        if (event.target.matches('[data-sheet]')) {
          var index = Number(event.target.dataset.sheet);
          if (event.target.checked) selected.add(index); else selected.delete(index);
          update();
        }
        if (event.target.matches('.document-zoom')) show(current);
        if (event.target.matches('.document-sides')) { modeTouched = true; update(); }
      };
      update(); show(0);
      if (printNow) await output('print');
    } catch (error) {
      if (isCurrent()) {
        host.innerHTML = '<div class="document-error" role="alert">' + esc(error.message) + '</div>';
      }
    }
  }
  window.TDPDocuments = {open:open};
}());
