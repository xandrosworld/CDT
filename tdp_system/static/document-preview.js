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
      function receiptAt(i) { return /(?:^| · )biên nhận(?:\s+\d+)?$/.test(data.sheets[i].name.trim().toLowerCase()); }
      function summaryAt(i) { return /(?:^| · )bảng kê tổng$/.test(data.sheets[i].name.trim().toLowerCase()); }
      var purchases = body.kind === 'purchases' && data.sheets.some(function(_,i){return receiptAt(i);});
      var selected = new Set(data.sheets.map(function (_, i) { return i; }).filter(function(i){return !purchases || receiptAt(i);}));
      var deliveries = body.kind === 'deliveries', resolvedSides = '';
      var current = selected.values().next().value || 0;
      host.innerHTML = '<section class="document-preview"><div class="document-toolbar">' +
        '<strong>Xem chứng từ</strong><span class="document-count"></span>' +
        (purchases?'<button type="button" class="btn btn-small btn-primary" data-doc="receipts">Chọn biên nhận A5</button><button type="button" class="btn btn-small btn-outline" data-doc="summary">Chọn bảng kê A4</button>':'') +
        '<button type="button" class="btn btn-small btn-outline" data-doc="all">Chọn tất cả'+(purchases?' (A4)':'')+'</button>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="none">Bỏ chọn</button>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="excel">Tải Excel đã chọn</button>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="pdf">Tải PDF đã chọn</button>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="view-pdf">Xem bản in</button>' +
        '<label>Khổ giấy <select class="document-paper" aria-label="Khổ giấy"><option value="A4">A4</option><option value="A5">A5 · biên nhận</option></select></label>' +
        '<label>Cách in <select class="document-sides" aria-label="Cách in">'+(deliveries||purchases?'<option value="auto">Tự động · theo số trang</option>':'')+'<option value="simplex">Một mặt</option><option value="duplex">Hai mặt · '+(deliveries?'mỗi đơn tờ riêng':'biên nhận tờ riêng')+'</option></select></label>' +
        '<button type="button" class="btn btn-small btn-primary" data-doc="print">In phiếu đã chọn</button>' +
        '<label>Phóng to bản xem <select class="document-zoom" aria-label="Phóng to chứng từ"><option value="0.8">80%</option><option value="1" selected>100%</option><option value="1.25">125%</option><option value="1.5">150%</option></select></label>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="refresh">Đọc lại dữ liệu mới</button></div>' +
        '<p class="document-note">Bản xem, Excel và PDF dùng cùng số liệu tại lúc mở. Có thay đổi đơn thì bấm Đọc lại dữ liệu mới. '+(deliveries?'Phiếu giao căn khổ A4; chữ trên bản in đã tăng một cỡ.':purchases?'Biên nhận mặc định A5 dọc. Bảng kê tổng in riêng A4 ngang; chọn tất cả sẽ dùng A4. Bấm Xem bản in để kiểm tra đúng khổ giấy.':'Chọn khổ giấy và bấm Xem bản in để kiểm tra trước khi in.')+'</p>' +
        '<p class="document-note document-print-help" role="status"></p>' +
        (data.warnings || []).map(function (warning) { return '<p class="document-note tag-warn" role="alert">' + esc(warning) + '</p>'; }).join('') +
        '<div class="document-sheet-list" role="group" aria-label="Chọn từng chứng từ">' +
        data.sheets.map(function (sheet, i) { return '<div><input type="checkbox" checked data-sheet="' + i + '" aria-label="Chọn ' + esc(sheet.name) + '"><button type="button" class="btn btn-small btn-outline" data-open-sheet="' + i + '">' + esc(sheet.name) + '</button></div>'; }).join('') +
        '</div><div class="document-error" role="alert"></div><div class="document-scroll" tabindex="0" aria-label="Nội dung chứng từ"></div><div class="document-pdf"></div></section>';
      var busy = false, modeTouched = false, paperTouched = false;
      function invalidatePrint() {
        resolvedSides = '';
        host.querySelector('.document-pdf').innerHTML = '';
        host.querySelector('.document-error').textContent = '';
      }
      function printHelp() {
        if(deliveries){
          var sides=host.querySelector('.document-sides').value;
          if(sides==='auto'&&!resolvedSides)return 'Tự động: mỗi đơn một trang thì in một mặt; có đơn nhiều trang thì chuẩn bị hai mặt, mỗi đơn bắt đầu trên tờ riêng. Khi in, kiểm tra khổ A4 và chế độ hai mặt của máy in.';
          if(sides==='auto')sides=resolvedSides;
          return 'Khổ A4, tỷ lệ 100%. '+(sides==='duplex'?'Bản in hai mặt · lật cạnh dài. Trong hộp thoại máy in, chọn Hai mặt / Flip on long edge và in tất cả trang, kể cả trang trắng để không ghép hai đơn vào cùng một tờ.':'Bản in một mặt. Trong hộp thoại máy in, chọn Một mặt.');
        }
        var selectedPaper = host.querySelector('.document-paper').value;
        var paper = 'Khổ '+selectedPaper+(selectedPaper==='A5'?' dọc · 148 × 210 mm':'')+'. Khi in chọn đúng khổ '+selectedPaper+' và tỷ lệ 100% / Kích thước thực. ';
        var selectedSides=host.querySelector('.document-sides').value;
        if(selectedSides==='auto'&&!resolvedSides) return paper+'Tự động: phiếu một trang in một mặt; có phiếu hai trang thì chuẩn bị in hai mặt, mỗi người một tờ riêng.';
        if(selectedSides==='auto')selectedSides=resolvedSides;
        var summary = Array.from(selected).some(function(i){return /(?:^| · )bảng kê tổng$/.test(data.sheets[i].name.trim().toLowerCase());});
        var edge = summary ? 'Bảng kê nằm ngang: chọn LẬT CẠNH NGẮN (Flip on short edge) để mặt sau không ngược đầu. ' : 'Trang dọc: chọn LẬT CẠNH DÀI (Flip on long edge). ';
        return paper + (selectedSides === 'duplex' ?
          edge + 'Chọn in hai mặt và in tất cả trang, kể cả trang trắng. Mỗi người một tờ riêng: biên nhận một trang có mặt sau trắng; biên nhận hai trang in trước và sau cùng tờ. Nếu máy in đang chọn cạnh khác, đổi lại trong hộp thoại máy in.' :
          'Trong hộp thoại máy in, chọn in một mặt. Mỗi biên nhận in trên một tờ riêng.');
      }
      function update() {
        var mode = host.querySelector('.document-sides');
        var paper = host.querySelector('.document-paper');
        var receiptsOnly = selected.size > 0 && Array.from(selected).every(function(i){return /(?:^| · )biên nhận(?:\s+\d+)?$/.test(data.sheets[i].name.trim().toLowerCase());});
        paper.querySelector('[value=A5]').disabled = !receiptsOnly;
        if(!receiptsOnly) paper.value='A4';
        else if(!paperTouched) paper.value='A5';
        paper.disabled=busy;
        if (!modeTouched) mode.value = deliveries || purchases ? 'auto' : Array.from(selected).some(function(i){return /(?:^| · )bảng kê tổng$/.test(data.sheets[i].name.trim().toLowerCase());}) ? 'duplex' : 'simplex';
        mode.disabled = busy;
        host.querySelector('.document-print-help').textContent = printHelp();
        host.querySelector('.document-count').textContent = data.sheet_count + ' phiếu · Đã chọn ' + selected.size;
        host.querySelectorAll('[data-doc="excel"],[data-doc="pdf"],[data-doc="print"],[data-doc="view-pdf"]').forEach(function (b) { b.disabled = busy || !selected.size; });
        host.querySelectorAll('[data-sheet]').forEach(function (c) { c.checked = selected.has(Number(c.dataset.sheet)); });
        host.querySelectorAll('[data-sheet],[data-doc="all"],[data-doc="none"],[data-doc="refresh"],[data-doc="receipts"],[data-doc="summary"]').forEach(function(c) { c.disabled=busy; });
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
        resolvedSides='';
        busy = true; update();
        var errorBox = host.querySelector('.document-error');
        var isPdf = type === 'print' || type === 'pdf' || type === 'view-pdf';
        errorBox.textContent = isPdf ? 'Đang tạo PDF đúng mẫu, vui lòng chờ…' : '';
        var url = '/api/documents/' + data.token + '/' + (isPdf ? 'pdf' : 'excel') + '?sheets=' + Array.from(selected).sort(function(a,b){return a-b;}).join(',');
        url += '&paper=' + host.querySelector('.document-paper').value;
        if(isPdf) url += '&sides=' + host.querySelector('.document-sides').value;
        try {
          var response = await checked(await fetch(url));
          if(isPdf)resolvedSides=response.headers.get('X-Print-Sides')||'';
          var blob = await response.blob();
          if (!isCurrent()) return;
          var blobUrl = URL.createObjectURL(blob);
          errorBox.textContent = '';
          if (type === 'print' || type === 'view-pdf') {
            var panel = host.querySelector('.document-pdf');
            panel.innerHTML = '<p>Đã mở bản in của phần đã chọn. Nếu hộp thoại chưa bật, bấm nút máy in trong khung PDF.</p><iframe title="Bản in các phiếu đã chọn"></iframe>';
            panel.querySelector('p').textContent = (type === 'print' ? 'Đã mở bản in. Nếu hộp thoại chưa bật, bấm nút máy in trong khung PDF. ' : 'Bản in đúng khổ giấy của phần đã chọn. ') + printHelp();
            var frame = panel.querySelector('iframe');
            if(type === 'print') frame.onload = function () { setTimeout(function () { if (!isCurrent() || !frame.isConnected) return; try { frame.contentWindow.focus(); frame.contentWindow.print(); } catch (_) {} }, 700); };
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
        if (action.dataset.doc === 'all') { invalidatePrint();paperTouched=false;data.sheets.forEach(function (_,i) { selected.add(i); }); update(); }
        if (action.dataset.doc === 'none') { invalidatePrint();selected.clear(); update(); }
        if (action.dataset.doc === 'receipts' || action.dataset.doc === 'summary') {
          invalidatePrint();selected.clear();paperTouched=false;modeTouched=false;
          data.sheets.forEach(function(_,i){if(action.dataset.doc === 'receipts' ? receiptAt(i) : summaryAt(i)) selected.add(i);});
          update();if(selected.size)show(selected.values().next().value);
        }
        if (['excel', 'pdf', 'print', 'view-pdf'].includes(action.dataset.doc)) output(action.dataset.doc);
      };
      host.onchange = function(event) {
        if(busy && event.target.matches('[data-sheet]')) { update(); return; }
        if (event.target.matches('[data-sheet]')) {
          invalidatePrint();
          var index = Number(event.target.dataset.sheet);
          if (event.target.checked) selected.add(index); else selected.delete(index);
          update();
        }
        if (event.target.matches('.document-zoom')) show(current);
        if (event.target.matches('.document-sides')) { invalidatePrint();modeTouched = true; update(); }
        if (event.target.matches('.document-paper')) {invalidatePrint();paperTouched=true;update();}
      };
      update(); show(current);
      if (printNow) await output('print');
    } catch (error) {
      if (isCurrent()) {
        host.innerHTML = '<div class="document-error" role="alert">' + esc(error.message) + '</div>';
      }
    }
  }
  window.TDPDocuments = {open:open};
}());
