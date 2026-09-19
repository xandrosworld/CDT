(function (root) {
  'use strict';
  root.TdpBkDraft = function (options) {
    var esc = options.esc, dialog = document.createElement('dialog'), rows = [], loadedPeriod = null, review = null;
    dialog.className = 'bk-draft-dialog';
    dialog.setAttribute('aria-label', 'Lập bảng kê bổ sung');
    dialog.innerHTML = '<div class="bk-draft-head"><h2>Lập bảng kê bổ sung</h2><button class="btn btn-outline" data-bk="close" aria-label="Đóng">Đóng</button></div>' +
      '<p>1. Chọn hàng và điền thông tin mua → 2. Xem bảng kê tổng, biên nhận → 3. Xác nhận nhập kho. Tải và in chưa cộng kho.</p>' +
      '<div class="bk-draft-controls"><label>Từ ngày<input name="from" type="date" value="' + esc(options.from) + '"></label>' +
      '<label>Đến ngày<input name="to" type="date" value="' + esc(options.to) + '"></label>' +
      '<label>Nhóm hàng<select name="tax"><option value="KKKNT">KKKNT</option><option value="all">Tất cả hàng tồn âm</option></select></label>' +
      '<button class="btn btn-outline" data-bk="load">Xem hàng tồn âm</button></div>' +
      '<p class="muted">Có thể chọn lại tháng 8 hoặc kỳ trước. Lượng tồn âm chỉ để đối chiếu; sửa số lượng theo hàng thực mua. Đơn giá gợi ý bằng 95% giá bán gần nhất của đơn đã duyệt đến ngày đối chiếu, cùng ĐVT. Nếu chưa có đơn, dùng giá hóa đơn bán đã ký và ghi kho cùng ĐVT. Nguồn giá hiện dưới mỗi ô; có thể sửa trước khi tải.</p>' +
      '<div class="bk-draft-controls"><label>Ngày mua thực tế<input name="document_date" type="date"></label>' +
      '<label>Số bảng kê<input name="reference" maxlength="100" placeholder="Nhập số của bảng kê đang lập" aria-describedby="bk-reference-help"><small id="bk-reference-help">Số để nhận biết bảng kê này; nhập theo cách đánh số chị đang dùng.</small></label>' +
      '<label>Người bán chung<input name="source_party" list="bk-supplement-sellers" maxlength="150" placeholder="Chọn tên trong danh mục"></label><datalist id="bk-supplement-sellers"></datalist></div>' +
      '<details><summary>Đã sửa file Excel: mở lại tại đây</summary><input name="import_file" type="file" accept=".xlsx" aria-label="File bảng kê bổ sung đã sửa"><button class="btn btn-outline" data-bk="file">Đọc file đã sửa</button><p>Đọc file chưa ghi kho. Xem bộ bảng kê rồi xác nhận bên dưới.</p></details>' +
      '<div class="bk-draft-controls"><label>Thêm hàng ngoài danh sách tồn âm<input name="search" placeholder="Tìm theo mã hoặc tên hàng"></label>' +
      '<button class="btn btn-outline" data-bk="search">Tìm hàng</button><select name="product" aria-label="Kết quả tìm hàng"></select>' +
      '<button class="btn btn-outline" data-bk="add">Thêm dòng</button></div>' +
      '<p class="bk-draft-status" role="status"></p><div class="bk-draft-issues" role="alert" hidden></div><div class="bk-draft-table"></div>' +
      '<div class="bk-draft-controls"><button class="btn btn-outline" data-bk="all">Chọn tất cả</button>' +
      '<button class="btn btn-outline" data-bk="none">Bỏ chọn</button>' +
      '<button class="btn btn-primary" data-bk="excel">Tải Excel để nhập lại</button>' +
      '<button class="btn btn-primary" data-bk="preview">Xem bảng kê tổng & biên nhận</button></div>' +
      '<p class="muted">Thiếu thông tin vẫn tải Excel để điền tiếp. Để in bộ bảng kê, cần đủ ngày mua thực tế, số bảng kê, người bán trong danh mục, lượng và giá. Hạn mức cộng chung 5.000.000đ/người/ngày với các bảng kê đã ghi kho.</p>' +
      '<div class="bk-draft-preview"></div>';
    document.body.appendChild(dialog); dialog.showModal();
    var products = [], busy = false, issues = [], focusAfterAction = null;
    function field(name) { return dialog.querySelector('[name="' + name + '"]'); }
    function status(text, error) { var el=dialog.querySelector('.bk-draft-status');el.textContent=text;el.style.color=error?'#ad2424':''; }
    function focusIssue(target) {
      if (!target || !target.isConnected) return;
      var details=target.closest('details');if(details)details.open=true;
      target.scrollIntoView({block:'center',inline:'center'});target.focus({preventScroll:true});
    }
    function clearIssues() {
      issues=[];
      dialog.querySelectorAll('[aria-invalid="true"]').forEach(function(el){el.removeAttribute('aria-invalid');});
      var box=dialog.querySelector('.bk-draft-issues');box.hidden=true;box.innerHTML='';
    }
    function showIssues(items) {
      clearIssues();issues=items;
      var box=dialog.querySelector('.bk-draft-issues');box.hidden=false;
      box.innerHTML='<strong>Cần bổ sung hoặc sửa '+items.length+' mục:</strong><ul>'+items.map(function(item,i){
        if(item.target)item.target.setAttribute('aria-invalid','true');
        return '<li><span>'+esc(item.message)+'</span><button type="button" class="btn btn-outline" data-bk-fix="'+i+'">'+esc(item.label)+'</button></li>';
      }).join('')+'</ul>';
      focusAfterAction=items[0].target;
    }
    function rowField(i,key) {return dialog.querySelector('tr[data-row="'+i+'"] [data-field="'+key+'"]');}
    function validatePreview() {
      var missing=[];
      function add(message,target,label){missing.push({message:message,target:target,label:label});}
      if(!field('document_date').value)add('Chưa điền Ngày mua thực tế.',field('document_date'),'Điền ngày mua');
      else if(loadedPeriod && (field('document_date').value<loadedPeriod.from || field('document_date').value>loadedPeriod.to))add('Ngày mua thực tế phải nằm trong khoảng Từ ngày – Đến ngày đang chọn.',field('document_date'),'Sửa ngày mua');
      if(!field('reference').value.trim())add('Chưa điền Số bảng kê. Đây là số của bảng kê đang lập, không phải tìm ở bảng khác.',field('reference'),'Điền số bảng kê');
      var noSeller=rows.filter(function(r){return r.selected&&!String(r.source_party||'').trim()&&!field('source_party').value.trim();});
      if(noSeller.length)add(noSeller.length+' mặt hàng chưa có Người bán / NCC. Điền Người bán chung hoặc điền riêng từng dòng.',field('source_party'),'Điền người bán chung');
      rows.forEach(function(r,i){
        if(!r.selected)return;
        var title=r.product_name+' ('+r.product_code+')';
        if(!String(r.qty==null?'':r.qty).trim() || !Number.isFinite(Number(r.qty)) || Number(r.qty)<=0)add(title+': Lượng mua bổ sung phải lớn hơn 0.',rowField(i,'qty'),'Sửa lượng mua');
        if(!String(r.unit_cost==null?'':r.unit_cost).trim() || !Number.isFinite(Number(r.unit_cost)) || Number(r.unit_cost)<=0)add(title+': Đơn giá phải lớn hơn 0.',rowField(i,'unit_cost'),'Sửa đơn giá');
      });
      if(missing.length){var error=new Error('Chưa thể xem bảng kê. Bấm nút bên dưới để đến đúng ô cần sửa.');error.issues=missing;throw error;}
    }
    function errorIssues(message) {
      var target=null,label='Đến chỗ cần sửa';
      if(/Số tham chiếu|Số bảng kê/.test(message)){target=field('reference');label=/đã được ghi/.test(message)?'Kiểm tra số bảng kê':'Điền số bảng kê';}
      else if(/Ngày mua thực tế/.test(message)){target=field('document_date');label='Sửa ngày mua';}
      else if(/Từ ngày|Đến ngày/.test(message)){target=field('from');label='Sửa khoảng ngày';}
      else if(/Xem hàng tồn âm|xem hàng tồn âm/.test(message)){target=dialog.querySelector('[data-bk="load"]');label='Đến nút xem hàng tồn âm';}
      else if(/Chọn ít nhất một dòng/.test(message)){target=rowField(0,'selected');label='Đến danh sách chọn hàng';}
      else if(/Chọn file Excel/.test(message)){target=field('import_file');label='Chọn file Excel';}
      else if(/Nhập mã hoặc tên hàng|Tìm và chọn hàng/.test(message)){target=field('search');label='Tìm hàng';}
      else if(/Người bán|hạn mức/.test(message)){
        var i=rows.findIndex(function(r){var seller=String(r.source_party||field('source_party').value).trim();return r.selected&&seller&&message.indexOf(seller)>=0;});
        if(i>=0){target=rowField(i,/hạn mức/.test(message)?'qty':'source_party');label=/hạn mức/.test(message)?'Sửa lượng hàng của người bán':'Sửa người bán';}
      }
      return target?[{message:message,target:target,label:label}]:[];
    }
    function collect() {
      dialog.querySelectorAll('tr[data-row]').forEach(function(tr) {
        var row=rows[Number(tr.dataset.row)]; row.selected=tr.querySelector('[data-field="selected"]').checked;
        ['qty','unit_cost','source_party','note'].forEach(function(key){row[key]=tr.querySelector('[data-field="'+key+'"]').value;});
      });
    }
    function render() {
      dialog.querySelector('.bk-draft-table').innerHTML='<table><thead><tr><th>Chọn</th><th>Mã / tên hàng</th><th>ĐVT</th><th>Tồn cuối kỳ</th><th>Lượng mua bổ sung</th><th>Đơn giá</th><th>Người bán / NCC</th><th>Ghi chú</th></tr></thead><tbody>'+rows.map(function(r,i){
        return '<tr data-row="'+i+'"><td><input data-field="selected" type="checkbox" '+(r.selected?'checked':'')+' aria-label="Chọn '+esc(r.product_code)+'"></td><td>'+esc(r.product_code)+'<br>'+esc(r.product_name)+'</td><td>'+esc(r.unit)+'</td><td>'+esc(r.closing_qty == null?'—':options.quantity(r.closing_qty))+'</td>'+['qty','unit_cost','source_party','note'].map(function(key){
          var numeric=key==='qty'||key==='unit_cost';
          return '<td><input data-field="'+key+'" '+(numeric?'type="number" min="0" step="any"':'type="text" maxlength="'+(key==='note'?500:150)+'"')+(key==='source_party'?' list="bk-supplement-sellers"':'')+' value="'+esc(r[key] == null?'':r[key])+'" aria-label="'+esc(key+' '+r.product_code)+'">'+(key==='unit_cost'?'<div class="muted bk-price-source">'+esc(r.price_source || '')+'</div>':'')+'</td>';
        }).join('')+'</tr>';
      }).join('')+'</tbody></table>';
    }
    function payload() {
      collect();
      if (!loadedPeriod || loadedPeriod.from!==field('from').value || loadedPeriod.to!==field('to').value) throw new Error('Bấm “Xem hàng tồn âm” để cập nhật khoảng ngày trước khi tải.');
      var selected=rows.filter(function(r){return r.selected;});
      if (!selected.length) throw new Error('Chọn ít nhất một dòng để lập bảng kê.');
      return {from:loadedPeriod.from,to:loadedPeriod.to,document_date:field('document_date').value,reference:field('reference').value,
        rows:selected.map(function(r){return {product_code:r.product_code,qty:r.qty,unit_cost:r.unit_cost,source_party:r.source_party||field('source_party').value,note:r.note,source_line:r.source_line};})};
    }
    function post(body) { return {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}; }
    async function action(name) {
      if (name==='close') {dialog.close();return;}
      if (busy) return;
      clearIssues();focusAfterAction=null;
      busy=true; dialog.querySelectorAll('button').forEach(function(b){if(b.dataset.bk!=='close')b.disabled=true;});
      dialog.querySelectorAll('input,select').forEach(function(el){el.disabled=true;});
      try {
        collect();
        if(['load','file','add','all','none','preview'].indexOf(name)>=0){review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';}
        if (name==='load') {
          if(rows.some(function(r){return r.selected;}) && !root.confirm('Nạp lại danh sách sẽ thay các dòng đang chọn. Tiếp tục?')) return;
          status('Đang đối chiếu sổ kho…');
          var result=await options.api('/api/bk-import/shortages?'+new URLSearchParams({from:field('from').value,to:field('to').value,tax:field('tax').value}));
          if(!dialog.isConnected)return;
          loadedPeriod={from:result.from,to:result.to};
          rows=result.items.map(function(r){return Object.assign({},r,{qty:r.suggested_qty,selected:false,unit_cost:r.unit_cost == null?'':r.unit_cost,source_party:'',note:''});});
          render(); status(rows.length+' mã đang âm cuối kỳ. Chọn những hàng đã mua cần bổ sung chứng từ.');
          dialog.querySelector('.bk-draft-preview').innerHTML='';
          if(options.productCode){
            var index=rows.findIndex(function(r){return r.product_code===options.productCode;});
            if(index>=0){var target=dialog.querySelector('[data-row="'+index+'"]');target.scrollIntoView({block:'center'});focusAfterAction=rowField(index,'selected');}
            options.productCode=null;
          }
        } else if(name==='file') {
          if(!field('import_file').files.length)throw new Error('Chọn file Excel đã sửa trước.');
          var form=new FormData();form.append('file',field('import_file').files[0]);
          var imported=await options.api('/api/bk-import/draft/file',{method:'POST',body:form});
          if(!loadedPeriod)throw new Error('Chọn kỳ và xem hàng tồn âm trước khi đọc file.');
          rows=imported.rows;field('document_date').value=imported.document_date;field('reference').value=imported.reference;
          render();status('Đã đọc '+rows.length+' dòng. Bấm Xem bảng kê tổng & biên nhận để kiểm tra. Kho chưa thay đổi.');
        } else if(name==='search') {
          if(!field('search').value.trim())throw new Error('Nhập mã hoặc tên hàng cần tìm.');
          var catalog=await options.api('/api/catalog/products?q='+encodeURIComponent(field('search').value)+'&all=1');
          if(!dialog.isConnected)return;
          products=catalog.items;
          field('product').innerHTML=products.map(function(p,i){return '<option value="'+i+'">'+esc(p.code+' · '+p.name+' · '+p.unit)+'</option>';}).join('');
          status(products.length+' kết quả.');
        } else if(name==='add') {
          var p=products[Number(field('product').value)]; if(!p)throw new Error('Tìm và chọn hàng trước khi thêm.');
          if(!loadedPeriod)throw new Error('Chọn khoảng ngày rồi bấm “Xem hàng tồn âm” trước.');
          var price=await options.api('/api/bk-import/suggested-price?'+new URLSearchParams({product_code:p.code,to:loadedPeriod.to}));
          if(!dialog.isConnected)return;
          rows.push(Object.assign({},price,{product_code:p.code,product_name:p.name,unit:p.unit,qty:'',source_party:'',note:'',selected:true}));render();
        } else if(name==='all'||name==='none') {
          rows.forEach(function(r){r.selected=name==='all';});render();
        } else if(name==='excel') {
          await options.downloadFile('/api/bk-import/draft/excel',post(payload()));status('Đã tải bảng kê. Kho chưa thay đổi.');
        } else if(name==='next') {
          review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';field('reference').value='';
          status('Lập bộ mới: điền Số bảng kê mới rồi chọn hàng còn thiếu. Bộ vừa nhập đã lưu trong lịch sử.');focusAfterAction=field('reference');
        } else if(name==='preview') {
          var draft=payload();validatePreview();
          status('Đang tạo bản in…');
          var preview=await options.api('/api/bk-import/draft/preview',post(draft));
          if(!dialog.isConnected)return;
          review=preview;
          var base='/api/documents/'+encodeURIComponent(preview.token);
          dialog.querySelector('.bk-draft-preview').innerHTML='<div class="bk-draft-controls"><a class="btn btn-primary" target="_blank" rel="noopener" href="'+base+'/pdf?paper=A4&sides=simplex">In bộ bảng kê & biên nhận</a><a class="btn btn-outline" href="'+base+'/excel">Tải Excel bản in</a></div>'+preview.sheets.map(function(s){return '<details class="bk-supplement-paper" open><summary>'+esc(s.name)+'</summary><div class="bk-draft-paper">'+s.html+'</div></details>';}).join('')+
            (preview.already_posted?'<p>Bộ này đã ghi kho. In hoặc tải lại không cộng thêm kho.</p>':'<div class="bk-supplement-confirm"><p>Tổng tiền mua bổ sung: <strong>'+Number(preview.totals.amount).toLocaleString('vi-VN')+'đ</strong>.</p>'+(preview.rebuild_periods.length?'<p>Tháng '+esc(preview.rebuild_periods.join(', '))+' đã chốt. Khi xác nhận, hệ thống sẽ tính lại tồn chuyển sang tháng sau; nếu không đạt kiểm tra thì không ghi thay đổi nào.</p>':'')+'<label>Người xác nhận<input name="confirm_actor" maxlength="100" placeholder="Họ tên người kiểm tra"></label><label><input name="confirm_actual" type="checkbox"> Tôi đã kiểm tra hàng mua thực tế, ngày mua, người bán và đồng ý nhập kho'+(preview.rebuild_periods.length?', cập nhật tồn chuyển kỳ':'')+'.</label><button class="btn btn-primary" data-bk="confirm" disabled>Xác nhận nhập kho một lần</button></div>');
          status(preview.already_posted?'Bộ bảng kê này đã ghi kho.':'Đã tạo bảng kê tổng và biên nhận. Kiểm tra bản in, rồi xác nhận nhập kho ở dưới.');
          dialog.querySelector('.bk-draft-preview').scrollIntoView({block:'start'});
        } else if(name==='confirm') {
          if(!review || !field('confirm_actual').checked || !field('confirm_actor').value.trim())throw new Error('Điền tên và xác nhận đã kiểm tra hàng mua thực tế.');
          var saved=await options.api('/api/bk-import/draft/confirm',post({token:review.import_token,confirmed:true,actor:field('confirm_actor').value}));
          rows.forEach(function(r){var current=saved.stock.find(function(s){return s.product_code===r.product_code;});if(current){r.closing_qty=current.closing_qty;r.selected=false;r.qty=Math.max(0,-Number(current.closing_qty));}});
          var cleared=saved.stock.filter(function(s){return Number(s.closing_qty)>=-0.000001;}).map(function(s){return s.product_code;});
          rows=rows.filter(function(r){return cleared.indexOf(r.product_code)<0;});render();
          dialog.querySelector('.bk-supplement-confirm').innerHTML='<p><strong>'+ (saved.idempotent?'Bộ này đã nhập trước đó; không cộng thêm kho.':'Đã nhập kho thành công.')+'</strong></p><p>Tồn cuối ngày '+esc(saved.stock_date)+': '+saved.stock.map(function(r){return esc(r.product_code)+': '+options.quantity(r.closing_qty);}).join(' · ')+'</p><p>Đã ẩn '+cleared.length+' mã hết âm khỏi danh sách. Mã vẫn còn thiếu được giữ lại với lượng còn thiếu mới. Có thể in lại bộ vừa nhập ở phía trên.</p><button class="btn btn-primary" data-bk="next">Lập bảng kê tiếp theo</button>';
          status('Đã ghi nhận bộ bảng kê #'+saved.documentId+'. Đã ẩn '+cleared.length+' mã hết âm. Muốn lập bộ mới, bấm “Lập bảng kê tiếp theo” ở dưới.');
          if(options.onSaved)options.onSaved();
        }
      } catch(error) {
        var message=error.message.replace(/Số tham chiếu/gi,'Số bảng kê');
        if(message.indexOf('đã thuộc một bộ BK khác')>=0)message='Số bảng kê này có dòng đã được ghi trong bộ khác. Kiểm tra lại bộ đã nhập; chỉ dùng số mới khi lập bộ khác cho hàng chưa nhập.';
        status(message,true);var items=error.issues||errorIssues(message);if(items.length)showIssues(items);
        if(error.payload&&error.payload.stock_review){
          var stockReview=error.payload.stock_review,box=dialog.querySelector('.bk-draft-issues');
          box.hidden=false;box.innerHTML='<strong>Chưa nhập kho. Kiểm tra tồn chuyển kỳ:</strong><ul>'+stockReview.items.map(function(r){return '<li>'+esc(r.product_code+' · '+r.product_name)+': tồn '+options.quantity(r.closing_qty)+' '+esc(r.unit)+', giá trị '+Number(r.closing_value).toLocaleString('vi-VN')+'đ.</li>';}).join('')+'</ul><button type="button" class="btn btn-outline" data-bk-stock-review>Mở đối chiếu tháng '+esc(stockReview.period)+'</button><p>Các ô đang nhập được giữ lại. Đối chiếu xong, quay lại xem bộ bảng kê rồi xác nhận.</p>';
          box.querySelector('[data-bk-stock-review]').onclick=function(){if(options.onStockReview)options.onStockReview(stockReview.period);};
        }
      }
      finally {busy=false;dialog.querySelectorAll('button,input,select').forEach(function(b){b.disabled=false;});var confirm=dialog.querySelector('[data-bk="confirm"]');if(confirm)confirm.disabled=!field('confirm_actual').checked;if(focusAfterAction){focusIssue(focusAfterAction);focusAfterAction=null;}}
    }
    dialog.addEventListener('click',function(e){var fix=e.target.closest('[data-bk-fix]');if(fix){focusIssue(issues[Number(fix.dataset.bkFix)].target);return;}var button=e.target.closest('[data-bk]');if(button)action(button.dataset.bk);});
    dialog.addEventListener('input',function(e){
      if(e.target.name==='confirm_actor'||e.target.name==='confirm_actual'){var button=dialog.querySelector('[data-bk="confirm"]');if(button)button.disabled=!field('confirm_actual').checked;return;}
      if(issues.length){clearIssues();status('Đã thay đổi thông tin. Bấm Xem bảng kê tổng & biên nhận để kiểm tra lại.');}
      review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';
    });
    dialog.addEventListener('close',function(){dialog.remove();});
    options.api('/api/bk-import/draft/sellers').then(function(p){if(dialog.isConnected)dialog.querySelector('#bk-supplement-sellers').innerHTML=p.names.map(function(n){return '<option value="'+esc(n)+'"></option>';}).join('');}).catch(function(){});
    render(); action('load');
  };
})(window);
