(function () {
  'use strict';
  var serials = new Map();
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  async function checked(response) {
    if (!response.ok) {
      var error = await response.json().catch(function () { return {}; });
      var failure = new Error(error.error || 'Không lấy được chứng từ; hãy thử lại.');
      failure.code = error.code || '';
      throw failure;
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
      var purchases = ['purchases','saved-purchases'].includes(body.kind) && data.sheets.some(function(_,i){return receiptAt(i);});
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
        '<label>Cách in <select class="document-sides" aria-label="Cách in">'+(deliveries||purchases?'<option value="auto">Xếp trang tự động</option>':'')+'<option value="simplex">Một mặt</option><option value="duplex">Hai mặt'+(body.kind==='payment'?'':' · '+(deliveries?'mỗi đơn tờ riêng':'biên nhận tờ riêng'))+'</option></select></label>' +
        '<button type="button" class="btn btn-small btn-primary" data-doc="print">In phiếu đã chọn</button>' +
        '<label>Phóng to bản xem <select class="document-zoom" aria-label="Phóng to chứng từ"><option value="0.8">80%</option><option value="1" selected>100%</option><option value="1.25">125%</option><option value="1.5">150%</option></select></label>' +
        '<button type="button" class="btn btn-small btn-outline" data-doc="refresh">Đọc lại dữ liệu mới</button></div>' +
        '<p class="document-note">Bản xem, Excel và PDF dùng cùng số liệu tại lúc mở. Có thay đổi đơn thì bấm Đọc lại dữ liệu mới. '+(deliveries?'Phiếu giao căn khổ A4; chữ trên bản in đã tăng một cỡ.':purchases?'Biên nhận mặc định A5 dọc. Bảng kê tổng in riêng A4 ngang; chọn tất cả sẽ dùng A4. Bấm Xem bản in để kiểm tra đúng khổ giấy.':'Chọn khổ giấy và bấm Xem bản in để kiểm tra trước khi in.')+'</p>' +
        '<p class="document-note document-print-help" role="status"></p>' +
        '<details class="document-note document-printer-help" hidden><summary>Máy Canon LBP243dw: cách in A5</summary><p>Chọn giấy A5 dọc trên máy in và trong hộp thoại in; tỷ lệ 100% / Kích thước thực. Khay nạp A5 dọc của Canon dùng thiết lập A5R. Máy hỗ trợ in A5, nhưng không tự đảo hai mặt với khổ A5.</p><p>Biên nhận hai trang: chọn riêng biên nhận đó, tải PDF, in trang 1 rồi đặt giấy lại để in trang 2 trên mặt còn lại. Nếu cần tự đảo mặt bằng máy này, chọn A4 trên web và trong hộp thoại máy in.</p><a href="https://oip.manual.canon/USRMA-8782-zz-SSS-240-enGB/contents/devu-mcn-papers.html" target="_blank" rel="noopener">Khổ giấy hỗ trợ theo hướng dẫn Canon</a></details>' +
        (data.warnings || []).map(function (warning) { return '<p class="document-note tag-warn" role="alert">' + esc(warning) + '</p>'; }).join('') +
        '<div class="document-sheet-list" role="group" aria-label="Chọn từng chứng từ">' +
        data.sheets.map(function (sheet, i) { return '<div><input type="checkbox" checked data-sheet="' + i + '" aria-label="Chọn ' + esc(sheet.name) + '"><button type="button" class="btn btn-small btn-outline" data-open-sheet="' + i + '">' + esc(sheet.name) + '</button></div>'; }).join('') +
        (body.kind === 'payment' ? '<button type="button" class="btn btn-small btn-primary" data-doc="invoice-pdfs" title="Tải PDF gốc của các hóa đơn đã phát hành trong kỳ của nhà thầu đang xem. Nhiều hóa đơn được đóng chung file ZIP.">Tải PDF hóa đơn</button><button type="button" class="btn btn-small btn-primary" data-doc="invoice-print" title="In A4 hai mặt, mỗi hóa đơn bắt đầu trên tờ riêng; giữ đủ các trang gốc.">In tất cả hóa đơn</button>' : '') +
        '</div>' + (body.kind === 'payment' ? '<p class="document-note">In hóa đơn: A4 hai mặt · mỗi hóa đơn bắt đầu trên tờ riêng. Giữ đủ các trang như bản gốc; chèn mặt trắng khi cần để hai số hóa đơn không chung một tờ. Chọn Hai mặt, Lật cạnh dài và in tất cả trang, kể cả trang trắng. Cách in phía trên chỉ áp dụng cho In phiếu đã chọn.</p>' : '') +
        '<div class="document-progress" role="status" aria-live="polite"></div><div class="document-error" role="alert"></div><div class="document-scroll" tabindex="0" aria-label="Nội dung chứng từ"></div><div class="document-pdf"></div></section>';
      var busy = false, modeTouched = false, paperTouched = false, cancelDownload = null;
      if(data.purchase_source){
        host.classList.add('bk-history-preview');
        var provenance=data.purchase_source,sourcePanel=document.createElement('section');
        sourcePanel.className='document-note tag-warn';sourcePanel.dataset.purchaseSource=provenance.source;
        sourcePanel.innerHTML='<strong>'+esc(provenance.title)+'</strong><p>'+esc(provenance.message)+'</p>'+
          provenance.items.map(function(item){return '<p>'+esc(item.message)+'</p>';}).join('');
        if(provenance.source==='orders'){
          var savedButton=document.createElement('button');savedButton.className='btn btn-primary';
          savedButton.textContent='Kiểm tra bảng đã ghi kho';savedButton.dataset.checkSavedPurchases='';
          var savedHost=document.createElement('div');savedHost.id=hostId+'-source-history';
          savedButton.onclick=function(){window.TdpBkHistory({hostId:savedHost.id,esc:esc,
            api:async function(url){return (await checked(await fetch(url))).json();},
            from:provenance.from_date,to:provenance.to_date});};
          sourcePanel.appendChild(savedButton);
          sourcePanel.appendChild(savedHost);
        }
        host.querySelector('.document-preview').prepend(sourcePanel);
      }
      if(body.kind==='saved-purchases'&&!body.receipts){
        var receiptLink=document.createElement('button');
        receiptLink.className='btn btn-primary';receiptLink.dataset.savedReceipts='';
        receiptLink.textContent='Xem biên nhận của các bảng kê đã chọn';
        receiptLink.onclick=function(){open(Object.assign({},body,{receipts:true}),hostId,false);};
        var receiptNote=document.createElement('p');receiptNote.className='document-note';
        receiptNote.textContent='Đang xem riêng bảng kê tổng. Muốn in biên nhận, bấm nút bên dưới; giữ nguyên các bảng kê đã chọn.';
        receiptNote.appendChild(document.createElement('br'));receiptNote.appendChild(receiptLink);
        host.querySelector('.document-toolbar').after(receiptNote);
      }
      if(body.simple_print){
        var advanced=document.createElement('details');advanced.className='document-note';advanced.innerHTML='<summary>Chi tiết từng phiếu / tải file</summary>';
        var toolbar=host.querySelector('.document-toolbar');toolbar.before(advanced);advanced.appendChild(toolbar);
        host.querySelectorAll('.document-note,.document-sheet-list').forEach(function(el){
          if(el!==advanced&&!el.dataset.purchaseSource&&el.getAttribute('role')!=='alert'&&!advanced.contains(el))advanced.appendChild(el);
        });
        var simple=document.createElement('div');simple.className='document-toolbar';simple.dataset.simplePrint='';
        simple.innerHTML='<button class="btn btn-outline" data-doc="summary">Xem bảng kê A4</button><button class="btn btn-outline" data-doc="receipts">Xem biên nhận A5</button><button class="btn btn-primary" data-doc="print-summary">In bảng kê A4</button><button class="btn btn-primary" data-doc="print-receipts">In biên nhận A5</button>';
        advanced.before(simple);
      }
      function invalidatePrint() {
        resolvedSides = '';
        host.querySelector('.document-pdf').innerHTML = '';
        host.querySelector('.document-error').textContent = '';
      }
      function printHelp() {
        if(body.kind === 'payment') return 'In phiếu đã chọn: bảng tổng hợp giao nhận và đề nghị thanh toán đều A4 dọc. Chọn tỷ lệ 100% / Kích thước thực, 1 trang trên mỗi mặt giấy. Bảng dài tự sang trang để giữ chữ dễ đọc. '+(host.querySelector('.document-sides').value === 'duplex' ? 'Khi in hai mặt, chọn lật cạnh dài. ' : 'Chọn Một mặt trong hộp thoại máy in. ')+'Phóng to bản xem chỉ đổi hiển thị trên web. Nút In tất cả hóa đơn dùng bản hóa đơn gốc riêng.';
        if(deliveries){
          var sides=host.querySelector('.document-sides').value;
          if(sides==='auto'&&!resolvedSides)return 'Tự động: mỗi đơn một trang thì in một mặt; có đơn nhiều trang thì chuẩn bị hai mặt, mỗi đơn bắt đầu trên tờ riêng. Khi in, kiểm tra khổ A4 và chế độ hai mặt của máy in.';
          if(sides==='auto')sides=resolvedSides;
          return 'Khổ A4, tỷ lệ 100%. '+(sides==='duplex'?'Bản in hai mặt · lật cạnh dài. Trong hộp thoại máy in, chọn Hai mặt / Flip on long edge và in tất cả trang, kể cả trang trắng để không ghép hai đơn vào cùng một tờ.':'Bản in một mặt. Trong hộp thoại máy in, chọn Một mặt.');
        }
        var selectedPaper = host.querySelector('.document-paper').value;
        var paper = 'Khổ '+selectedPaper+(selectedPaper==='A5'?' dọc · 148 × 210 mm':'')+'. Khi in chọn đúng khổ '+selectedPaper+' và tỷ lệ 100% / Kích thước thực. ';
        var a5Duplex = selectedPaper==='A5' ? 'In hai mặt A5 cần máy hỗ trợ đúng khổ giấy; Canon LBP243dw phải lật giấy thủ công. ' : '';
        var selectedSides=host.querySelector('.document-sides').value;
        if(selectedSides==='auto'&&!resolvedSides) return paper+'Xếp trang: phiếu một trang in một mặt; có phiếu hai trang thì chuẩn bị hai mặt, mỗi người một tờ riêng. '+a5Duplex;
        if(selectedSides==='auto')selectedSides=resolvedSides;
        var summary = Array.from(selected).some(function(i){return /(?:^| · )bảng kê tổng$/.test(data.sheets[i].name.trim().toLowerCase());});
        var edge = summary ? 'Bảng kê nằm ngang: chọn LẬT CẠNH NGẮN (Flip on short edge) để mặt sau không ngược đầu. ' : 'Trang dọc: chọn LẬT CẠNH DÀI (Flip on long edge). ';
        return paper + (selectedSides === 'duplex' ?
          a5Duplex + edge + 'Với máy hỗ trợ tự đảo mặt ở khổ giấy đã chọn, chọn in hai mặt và in tất cả trang, kể cả trang trắng. Mỗi người một tờ riêng: biên nhận một trang có mặt sau trắng; biên nhận hai trang in trước và sau cùng tờ.' :
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
        host.querySelector('.document-printer-help').hidden = paper.value !== 'A5';
        host.querySelector('.document-print-help').textContent = printHelp();
        host.querySelector('.document-count').textContent = data.sheet_count + ' phiếu · Đã chọn ' + selected.size;
        host.querySelectorAll('[data-doc="excel"],[data-doc="pdf"],[data-doc="print"],[data-doc="view-pdf"]').forEach(function (b) { b.disabled = busy || !selected.size; });
        host.querySelectorAll('[data-doc="invoice-pdfs"],[data-doc="invoice-print"]').forEach(function (b) { b.disabled = busy; });
        host.querySelectorAll('[data-sheet]').forEach(function (c) { c.checked = selected.has(Number(c.dataset.sheet)); });
        host.querySelectorAll('[data-sheet],[data-doc="all"],[data-doc="none"],[data-doc="refresh"],[data-doc="receipts"],[data-doc="summary"]').forEach(function(c) { c.disabled=busy; });
        host.querySelectorAll('[data-doc="print-summary"],[data-doc="print-receipts"]').forEach(function(c){c.disabled=busy||!data.sheets.some(function(_,i){return c.dataset.doc==='print-summary'?summaryAt(i):receiptAt(i);});});
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
        var originalInvoices = type === 'invoice-pdfs' || type === 'invoice-print';
        var invoicePrint = type === 'invoice-print';
        if (busy || (!originalInvoices && !selected.size)) return;
        resolvedSides='';
        busy = true; update();
        var errorBox = host.querySelector('.document-error');
        var progressBox = host.querySelector('.document-progress');
        var isPdf = invoicePrint || type === 'print' || type === 'pdf' || type === 'view-pdf';
        errorBox.textContent = '';
        var started = Date.now();
        function progress() {
          if (!isCurrent()) return;
          var seconds = Math.floor((Date.now()-started)/1000);
          progressBox.textContent = (originalInvoices ? (invoicePrint?'Đang lấy hóa đơn gốc và ghép thành một bản in cho kỳ ĐNTT đang xem':'Đang tải PDF hóa đơn gốc từ M-Invoice · Nhiều hóa đơn sẽ nằm trong một file ZIP') : 'Đang tạo '+(isPdf?'PDF':'Excel')+' cho '+selected.size+' phiếu')+(seconds?' · Đã chờ '+seconds+' giây':'')+'. Các nút sẽ mở lại khi hoàn tất.';
        }
        progress();
        var cancelButton = document.createElement('button');
        cancelButton.type='button';cancelButton.className='btn btn-outline';cancelButton.textContent='Dừng chờ tải';
        cancelButton.onclick=function(){if(cancelDownload)cancelDownload();};
        progressBox.after(cancelButton);
        var progressTimer = setInterval(progress, 1000);
        var url = '/api/documents/' + data.token + '/' + (isPdf ? 'pdf' : 'excel') + '?sheets=' + Array.from(selected).sort(function(a,b){return a-b;}).join(',');
        url += '&paper=' + host.querySelector('.document-paper').value;
        if(isPdf) url += '&sides=' + host.querySelector('.document-sides').value;
        if(originalInvoices) url = '/api/export/invoice-pdfs/' + encodeURIComponent(body.contractor) + '?from=' + encodeURIComponent(body.from) + '&to=' + encodeURIComponent(body.to) + '&scope_id=' + encodeURIComponent(body.scope_id || '');
        if(invoicePrint)url += '&format=pdf&layout=invoice-per-sheet';
        var controller=new AbortController(),requestTimer=setTimeout(function(){controller.abort();},180000);
        var cancelledByUser=false;
        cancelDownload=function(){cancelledByUser=true;controller.abort();};
        try {
          var response = await checked(await fetch(url,{signal:controller.signal}));
          if(isPdf)resolvedSides=response.headers.get('X-Print-Sides')||'';
          var blob = await response.blob();
          if (!isCurrent()) return;
          var blobUrl = URL.createObjectURL(blob);
          errorBox.textContent = '';
          if (invoicePrint || type === 'print' || type === 'view-pdf') {
            var panel = host.querySelector('.document-pdf');
            panel.innerHTML = '<p>Đã mở bản in của phần đã chọn. Nếu hộp thoại chưa bật, bấm nút máy in trong khung PDF.</p><iframe title="Bản in các phiếu đã chọn"></iframe>';
            panel.querySelector('p').textContent = (type === 'print' ? 'Đã mở bản in. Nếu hộp thoại chưa bật, bấm nút máy in trong khung PDF. ' : 'Bản in đúng khổ giấy của phần đã chọn. ') + printHelp();
            if(invoicePrint){
              panel.querySelector('p').textContent='Bản in gồm '+(response.headers.get('X-Invoice-Count')||'')+' hóa đơn của '+body.contractor+' trong kỳ ĐNTT đang xem. Giữ đủ các trang gốc; mỗi hóa đơn bắt đầu trên tờ mới. Hóa đơn có số trang lẻ được chèn mặt trắng trước hóa đơn tiếp theo. Trong hộp thoại máy in, chọn A4, Hai mặt, Lật cạnh dài, 1 trang trên mỗi mặt và in tất cả trang, kể cả trang trắng. Không chọn bỏ qua trang trắng. Bấm nút máy in trong khung PDF sau khi kiểm tra bản xem.';
              var openPdf=document.createElement('a');openPdf.href=blobUrl;openPdf.target='_blank';openPdf.rel='noopener';openPdf.className='btn btn-outline';openPdf.textContent='Mở bản in hóa đơn ở tab mới';panel.insertBefore(openPdf,panel.querySelector('iframe'));
              panel.querySelector('iframe').title='Bản in tất cả hóa đơn';
            }
            var frame = panel.querySelector('iframe');
            if(invoicePrint || type === 'print') frame.onload = function () { setTimeout(function () { if (!isCurrent() || !frame.isConnected) return; try { frame.contentWindow.focus(); frame.contentWindow.print(); } catch (_) {} }, 700); };
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
        } catch (error) { if (isCurrent()) {
          errorBox.textContent = error.name==='AbortError'?(cancelledByUser?'Đã dừng chờ tải. Lựa chọn và dữ liệu vẫn được giữ.':originalInvoices?'M-Invoice chưa trả đủ PDF trong 3 phút. Bấm Thử lại tải PDF hóa đơn hoặc chọn kỳ ngắn hơn; không cần xuất lại hóa đơn.':'Tạo chứng từ quá lâu. Hãy bấm tải hoặc in để thử lại; lựa chọn vẫn được giữ.'):error.message;
          if(originalInvoices){var retry=document.createElement('button');retry.type='button';retry.className='btn btn-outline';retry.dataset.doc=error.code==='stale_invoice_payment_scope'?'payment-refresh':type;retry.textContent=error.code==='stale_invoice_payment_scope'?'Đọc lại dữ liệu mới':invoicePrint?'Thử lại in hóa đơn':'Thử lại tải PDF hóa đơn';errorBox.appendChild(retry);}
        } }
        finally { clearTimeout(requestTimer);clearInterval(progressTimer); cancelDownload=null;cancelButton.remove();progressBox.textContent=''; busy = false; if (isCurrent()) update(); }
      }
      host.onclick = function (event) {
        var sheet = event.target.closest('[data-open-sheet]');
        if (sheet) { show(Number(sheet.dataset.openSheet)); return; }
        var action = event.target.closest('[data-doc]');
        if (!action) return;
        if (busy) return;
        if(['print-summary','print-receipts'].includes(action.dataset.doc)){
          var receiptPrint=action.dataset.doc==='print-receipts';invalidatePrint();selected.clear();
          data.sheets.forEach(function(_,i){if(receiptPrint?receiptAt(i):summaryAt(i))selected.add(i);});
          paperTouched=true;modeTouched=false;host.querySelector('.document-paper').value=receiptPrint?'A5':'A4';
          update();if(selected.size){show(selected.values().next().value);output('print');}return;
        }
        if(action.dataset.doc==='payment-refresh'){var form=document.getElementById('paymentRequestForm');if(form)form.requestSubmit();return;}
        if (action.dataset.doc === 'refresh') { if (!busy) open(body, hostId, false); }
        if (action.dataset.doc === 'all') { invalidatePrint();paperTouched=false;data.sheets.forEach(function (_,i) { selected.add(i); }); update(); }
        if (action.dataset.doc === 'none') { invalidatePrint();selected.clear(); update(); }
        if (action.dataset.doc === 'receipts' || action.dataset.doc === 'summary') {
          invalidatePrint();selected.clear();paperTouched=false;modeTouched=false;
          data.sheets.forEach(function(_,i){if(action.dataset.doc === 'receipts' ? receiptAt(i) : summaryAt(i)) selected.add(i);});
          update();if(selected.size)show(selected.values().next().value);
        }
        if (['excel', 'pdf', 'print', 'view-pdf', 'invoice-pdfs', 'invoice-print'].includes(action.dataset.doc)) output(action.dataset.doc);
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
        if(body.kind==='saved-purchases'){
          host.innerHTML+='<button type="button" class="btn btn-outline" data-saved-back>Quay lại danh sách bảng kê</button> <button type="button" class="btn btn-primary" data-saved-retry>Kiểm tra lại bản in</button>';
          host.querySelector('[data-saved-retry]').onclick=function(){open(body,hostId,false);};
          if(body.simple_print)host.querySelector('[data-saved-back]').textContent='Chọn lại ngày cần in';
          host.querySelector('[data-saved-back]').onclick=function(){var field=body.simple_print?document.getElementById('bkPrintDay'):host.parentElement.querySelector('[data-history-id]');if(field){field=field.parentElement.querySelector('.localized-date-display')||field;field.scrollIntoView({block:'center'});field.focus();}};
          if(body.receipts){var summary=document.createElement('button');summary.className='btn btn-primary';summary.textContent='Xem bảng kê tổng';summary.onclick=function(){open(Object.assign({},body,{receipts:false}),hostId,false);};host.appendChild(summary);}
        }
        if (body.kind === 'payment' && error.code === 'payment_statement_line_totals_mismatch') {
          host.innerHTML += '<button type="button" class="btn btn-primary" data-action="payment-open-output">Mở hóa đơn đầu ra đúng kỳ</button> <button type="button" class="btn btn-outline" data-payment-retry>Kiểm tra lại bảng kê</button>';
          host.querySelector('[data-payment-retry]').onclick = () => open(body, hostId, false);
        }
        if (body.kind === 'purchases' && ['purchase_document_selection_required','receipt_daily_limit_exceeded'].includes(error.code)) {
          var batchIds = (body.selections || []).map(function (s) { return Number(s.batch_id); }).filter(Number.isFinite);
          host.innerHTML += '<p>Mở tại đây để kiểm tra người bán và lượng hàng được chọn. Nếu đã sửa người bán trong Excel, cập nhật file ở mục “Cập nhật người bán từ Excel” rồi lưu để bản in dùng thông tin mới.</p>' +
            '<button type="button" class="btn btn-primary" data-action="open-purchase-selection" data-purchase-batches="' + esc(batchIds.join(',')) + '" data-purchase-retry-host="' + esc(hostId) + '">Xử lý người bán / chọn hàng để in</button>';
        }
      }
    }
  }
  window.TDPDocuments = {open:open};
}());
