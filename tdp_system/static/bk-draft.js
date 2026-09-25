(function (root) {
  'use strict';
  root.TdpBkDraft = function (options) {
    var esc = options.esc, dialog = document.createElement('dialog'), rows = [], loadedPeriod = null, review = null, periodDrafts = {};
    dialog.className = 'bk-draft-dialog';
    dialog.setAttribute('aria-label', 'Lập bảng kê bổ sung');
    dialog.innerHTML = '<div class="bk-draft-head"><h2>Lập bảng kê bổ sung</h2><button class="btn btn-outline" data-bk="close" aria-label="Đóng">Đóng</button></div>' +
      '<p><strong>1. Chọn tháng → 2. Kiểm tra hàng mua → 3. Xem, in và xác nhận nhập kho</strong></p>' +
      '<p class="muted">Cập nhật đủ hóa đơn đã ký trước khi đối chiếu. Lượng âm là gợi ý cần kiểm tra với hàng thực mua; xem và in chưa ghi kho.</p>' +
      '<div class="bk-draft-controls"><label>Từ ngày<input name="from" type="date" value="' + esc(options.from) + '"></label>' +
      '<label>Đến ngày<input name="to" type="date" value="' + esc(options.to) + '"></label>' +
      '<label>Nhóm hàng<select name="tax"><option value="KKKNT">KKKNT</option><option value="all">Tất cả hàng tồn âm</option></select></label>' +
      '<button class="btn btn-outline" data-bk="load">Xem hàng tồn âm</button></div>' +
      '<div class="bk-draft-controls"><label>Số bảng kê<input name="reference" maxlength="100" aria-describedby="bk-reference-help"><small id="bk-reference-help">Đã gợi ý sẵn; có thể sửa theo cách đánh số đang dùng.</small></label></div>' +
      '<div class="bk-quick-fill"><div class="bk-draft-controls"><label>Ngày mua thực tế<input name="document_date" type="date"></label></div><p>Chọn cùng một ngày ở Từ ngày và Đến ngày: dùng sẵn ngày đó cho các dòng đã tích còn trống ngày. Chọn nhiều ngày: chọn Ngày mua thực tế một lần tại đây. Kiểm tra đúng ngày thực mua; có thể sửa tại ô này. Ngày đã có từ nguồn mua được giữ nguyên.</p></div>' +
      '<details class="bk-quick-seller"><summary>Điền nhanh người bán (không bắt buộc)</summary><p>Chỉ điền Người bán / NCC còn trống của những dòng đã tích chọn.</p><div class="bk-draft-controls"><label>Người bán / NCC<input name="source_party" list="bk-supplement-sellers" maxlength="150"></label><button class="btn btn-outline" data-bk="apply-common">Điền người bán cho dòng đã chọn</button></div></details><datalist id="bk-supplement-sellers"></datalist>' +
      '<details><summary>Nguồn số liệu và cách tính lượng gợi ý</summary><p>Đối chiếu tồn đến cuối kỳ, gồm thiếu từ trước chưa bổ sung; không cộng lặp lượng âm từng ngày. Nguồn mua chưa ghi kho được đưa sang theo ngày, người bán và giá mua. Nguồn đã ghi kho chỉ để tra cứu, không nhập lại. Khi chưa có nguồn, giá gợi ý bằng 95% giá bán gần nhất; cần kiểm tra theo giá mua thực tế.</p></details>' +
      '<details><summary>Đã sửa file Excel: mở lại tại đây</summary><input name="import_file" type="file" accept=".xlsx" aria-label="File bảng kê bổ sung đã sửa"><button class="btn btn-outline" data-bk="file">Đọc file đã sửa</button><p>Đọc file chưa ghi kho. Xem bộ bảng kê rồi xác nhận bên dưới.</p></details>' +
      '<details><summary>Thêm hàng ngoài danh sách tồn âm</summary><div class="bk-draft-controls"><label>Thêm hàng ngoài danh sách tồn âm<input name="search" placeholder="Tìm theo mã hoặc tên hàng"></label>' +
      '<button class="btn btn-outline" data-bk="search">Tìm hàng</button><select name="product" aria-label="Kết quả tìm hàng"></select>' +
      '<button class="btn btn-outline" data-bk="add">Thêm dòng</button></div></details>' +
      '<div class="bk-row-summary" role="status"></div><div class="bk-source-panel" hidden></div>' +
      '<p class="bk-draft-status" role="status"></p><div class="bk-draft-issues" role="alert" hidden></div><div class="bk-daily-warning" role="status"></div><div class="bk-draft-table"></div>' +
      '<div class="bk-draft-controls"><button class="btn btn-outline" data-bk="all">Chọn tất cả</button>' +
      '<button class="btn btn-outline" data-bk="none">Bỏ chọn</button>' +
      '<button class="btn btn-outline" data-bk="excel">Tải Excel để nhập lại</button>' +
      '<button class="btn btn-primary" data-bk="preview">Xem bảng kê tổng & biên nhận</button></div>' +
      '<p class="muted">Thiếu thông tin vẫn tải Excel để điền tiếp. Để in bộ bảng kê, cần đủ ngày mua thực tế, số bảng kê, người bán trong danh mục, lượng và giá. Hạn mức cộng chung 5.000.000đ/người/ngày với các bảng kê đã ghi kho.</p>' +
      '<div class="bk-draft-preview"></div>';
    document.body.appendChild(dialog); dialog.showModal();
    function fitPapers() {
      dialog.querySelectorAll('.bk-draft-paper .document-sheet').forEach(function(table){
        var width=Array.from(table.querySelectorAll('col')).reduce(function(total,col){return total+(parseFloat(col.style.width)||0);},0);
        var available=table.parentElement.clientWidth-24;
        if(width&&available>0){table.style.width=width+'px';table.style.margin='0 auto';table.style.zoom=Math.min(1,available/width);}
      });
    }
    var paperWidth=0,paperObserver=new ResizeObserver(function(entries){var width=entries[0].contentRect.width;if(width!==paperWidth){paperWidth=width;fitPapers();}});
    paperObserver.observe(dialog);dialog.addEventListener('toggle',fitPapers,true);
    var products = [], busy = false, issues = [], focusAfterAction = null, sellerCatalog = null;
    function sellerKey(value){return String(value||'').replace(/[đĐ]/g,'d').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');}
    function updateSellerDetails(){
      dialog.querySelectorAll('[data-seller-details]').forEach(function(el){
        var r=rows[Number(el.dataset.sellerDetails)],name=String(r.source_party||'').trim();
        if(!name){el.textContent='Chọn người bán thực tế đã lưu; CCCD và địa chỉ sẽ tự lấy sang bản in. Không cần nhập lại hồ sơ người bán.';return;}
        if(sellerCatalog===null){el.textContent='Chưa tải được hồ sơ người bán. Khi xem bản in, hệ thống kiểm tra lại danh mục.';return;}
        var matches=sellerCatalog.filter(function(p){return sellerKey(p.name)===sellerKey(name);});
        if(matches.length!==1){el.textContent=matches.length?'Tên trùng nhiều hồ sơ. Cần đối chiếu danh mục trước khi in.':'Chưa tìm thấy hồ sơ này. Chọn đúng tên trong danh sách Người bán / NCC.';return;}
        var p=matches[0];el.textContent='Thông tin dùng để in: '+p.name+' · CCCD: '+(p.cccd||'chưa có')+' · Địa chỉ: '+(p.address||'chưa có')+' · Ngày cấp: '+(p.issue_date||'chưa có')+' · Nơi cấp: '+(p.issue_place||'chưa có');
      });
    }
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
    function dailyWarnings() {
      var groups={};
      rows.forEach(function(r,i){if(!r.selected)return;var seller=String(r.source_party||'').trim(),day=r.document_date||'',key=day+'|'+seller.toLocaleLowerCase();if(!seller||!day)return;if(!groups[key])groups[key]={seller:seller,day:day,amount:0,index:i};groups[key].amount+=(Number(r.qty)||0)*(Number(r.unit_cost)||0);});
      var over=Object.values(groups).filter(function(g){return g.amount>5000000;});
      dialog.querySelector('.bk-daily-warning').innerHTML=over.map(function(g){return '<p class="error-summary">'+esc(g.seller+' · '+g.day)+': '+g.amount.toLocaleString('vi-VN')+'đ, vượt 5.000.000đ/người/ngày. Kiểm tra lượng mua và người bán thực tế. Không đổi ngày mua để chia hạn mức. <button type="button" class="btn btn-outline" data-bk-split="'+g.index+'">Thêm người bán thực tế cùng ngày</button></p>';}).join('');
      return over;
    }
    function validatePreview() {
      var missing=[];
      function add(message,target,label){missing.push({message:message,target:target,label:label});}
      var noDate=rows.findIndex(function(r){return r.selected&&!r.document_date;});
      if(noDate>=0)add('Dòng đã chọn còn thiếu Ngày mua thực tế. Chọn Ngày mua thực tế phía trên; các dòng chưa có ngày riêng sẽ tự dùng ngày đó.',field('document_date'),'Điền ngày mua còn thiếu');
      if(!field('reference').value.trim())add('Chưa điền Số bảng kê.',field('reference'),'Điền số bảng kê');
      var noSeller=rows.findIndex(function(r){return r.selected&&!String(r.source_party||'').trim();});
      if(noSeller>=0)add('Dòng đã chọn còn thiếu Người bán / NCC. Chọn đúng người bán thực tế trong danh mục.',rowField(noSeller,'source_party'),'Điền người bán còn thiếu');
      rows.forEach(function(r,i){
        if(!r.selected)return;
        var title=r.product_name+' ('+r.product_code+')';
        if(!String(r.qty==null?'':r.qty).trim() || !Number.isFinite(Number(r.qty)) || Number(r.qty)<=0)add(title+': Lượng mua bổ sung phải lớn hơn 0.',rowField(i,'qty'),'Sửa lượng mua');
        if(!String(r.unit_cost==null?'':r.unit_cost).trim() || !Number.isFinite(Number(r.unit_cost)) || Number(r.unit_cost)<=0)add(title+': Đơn giá phải lớn hơn 0.',rowField(i,'unit_cost'),'Sửa đơn giá');
        var day=r.document_date||'';
        if(day&&loadedPeriod&&(day<loadedPeriod.from||day>loadedPeriod.to))add(title+': Ngày mua thực tế phải nằm trong kỳ đang chọn.',rowField(i,'document_date'),'Sửa ngày mua');
      });
      dailyWarnings().forEach(function(g){add(g.seller+' · '+g.day+': vượt 5.000.000đ/người/ngày. Kiểm tra đúng người bán và lượng thực mua.',rowField(g.index,'source_party'),'Kiểm tra người bán thực tế');});
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
        var i=rows.findIndex(function(r){var seller=String(r.source_party||'').trim();return r.selected&&seller&&message.indexOf(seller)>=0;});
        if(i>=0){target=rowField(i,'source_party');label='Kiểm tra người bán thực tế';}
      }
      return target?[{message:message,target:target,label:label}]:[];
    }
    function syncCommonDate() {
      var day=field('document_date').value;
      // Localized date controls have a visible text input beside the native
      // value. Synchronize both after programmatic changes, without bubbling
      // into this dialog's edit/collect handlers.
      field('document_date').dispatchEvent(new Event('change'));
      rows.forEach(function(r,i){
        if(r.common_date || (r.selected&&!r.document_date&&day)){
          r.common_date=true;r.document_date=day;
          var input=rowField(i,'document_date');if(input){input.value=day;input.readOnly=true;input.dispatchEvent(new Event('change'));var wrapper=input.closest('.localized-date-control');if(wrapper){wrapper.querySelector('.localized-date-display').readOnly=true;wrapper.querySelector('.localized-date-icon').disabled=true;}}
        }
        var hint=dialog.querySelector('[data-date-hint="'+i+'"]');
        if(hint)hint.textContent=r.common_date?(day?'Dùng Ngày mua thực tế đã chọn phía trên.':'Chọn Ngày mua thực tế phía trên.') : (!r.document_date?'Chọn Ngày mua thực tế phía trên một lần cho các dòng đã tích.':'Ngày riêng của dòng; giữ theo nguồn mua.');
      });
    }
    function collect() {
      dialog.querySelectorAll('tr[data-row]').forEach(function(tr) {
        var row=rows[Number(tr.dataset.row)]; row.selected=tr.querySelector('[data-field="selected"]').checked;
        ['document_date','qty','unit_cost','source_party','note'].forEach(function(key){row[key]=tr.querySelector('[data-field="'+key+'"]').value;});
      });
      syncCommonDate();
    }
    function purchaseHistoryHtml(r) {
      var history=(r.purchase_sources||[]).filter(function(s){return s.already_posted;});
      if(!history.length)return '';
      return '<details><summary>Nguồn mua đã ghi bảng kê ('+history.length+')</summary><p>Chỉ tra cứu; không gợi ý nhập lại nguồn đã ghi kho. Lượng âm hiện tại cần đối chiếu nguồn nhập, xuất và mã hàng.</p>'+history.map(function(s){return '<p>'+esc(s.document_date+' · '+s.source_party+' · '+s.cccd+' · '+s.address+' · Ngày cấp: '+(s.issue_date||'chưa có')+' · Nơi cấp: '+(s.issue_place||'chưa có')+' · Đã ghi: '+s.posted_qty+' '+s.unit+' · '+s.source_description)+'</p>';}).join('')+'</details>';
    }
    function render() {
      syncCommonDate();
      dialog.querySelector('.bk-draft-table').innerHTML='<table><thead><tr><th>Chọn</th><th>Mã / tên hàng</th><th>ĐVT</th><th>Ngày mua thực tế</th><th>Tồn cuối ngày '+esc(loadedPeriod ? loadedPeriod.to.split('-').reverse().join('/') : '')+'</th><th>Lượng mua bổ sung</th><th>Đơn giá</th><th>Người bán / NCC</th><th>Ghi chú</th></tr></thead><tbody>'+rows.map(function(r,i){
        return '<tr data-row="'+i+'"><td><input data-field="selected" type="checkbox" '+(r.selected?'checked':'')+' aria-label="Chọn '+esc(r.product_code)+'"></td><td>'+esc(r.product_code)+'<br>'+esc(r.product_name)+'<br><button type="button" class="btn btn-outline" data-bk-source="'+i+'">Xem / chọn nguồn mua</button>'+purchaseHistoryHtml(r)+'</td><td>'+esc(r.unit)+'</td><td><input type="date" data-field="document_date" value="'+esc(r.document_date||'')+'" '+(r.common_date?'readonly ':'')+'aria-label="Ngày mua thực tế '+esc(r.product_code)+'"><small data-date-hint="'+i+'"></small><small>'+esc(r.source_description||'')+'</small></td><td>'+esc(r.closing_qty == null?'—':options.quantity(r.closing_qty))+'</td>'+['qty','unit_cost','source_party','note'].map(function(key){
          var numeric=key==='qty'||key==='unit_cost';
          return '<td><input data-field="'+key+'" '+(numeric?'type="number" min="0" step="any"':'type="text" maxlength="'+(key==='note'?500:150)+'"')+(key==='source_party'?' list="bk-supplement-sellers"':'')+' value="'+esc(r[key] == null?'':r[key])+'" aria-label="'+esc(key+' '+r.product_code)+'">'+(key==='source_party'?'<small>'+esc(r.source_party_original ? 'Người bán nguồn: '+r.source_party_original : '')+'</small><div class="bk-seller-details" data-seller-details="'+i+'"></div><button type="button" data-bk-split="'+i+'" class="btn btn-outline">Thêm người bán cùng ngày</button>':'')+(key==='unit_cost'?'<div class="muted bk-price-source">'+esc(r.price_source || '')+'</div>':'')+'</td>';
        }).join('')+'</tr>';
      }).join('')+'</tbody></table>';
      syncCommonDate();
      dailyWarnings();
      updateSellerDetails();
      updateSummary();
    }
    function updateSummary() {
      var selected=rows.filter(function(r){return r.selected;}),missing=selected.filter(function(r){return !r.document_date||!r.source_party||!(Number(r.qty)>0)||!(Number(r.unit_cost)>0);});
      dialog.querySelector('.bk-row-summary').innerHTML='<strong>Đã chọn '+selected.length+' dòng · '+missing.length+' dòng cần bổ sung thông tin</strong><p>Kiểm tra ngày mua, người bán, lượng và giá ngay trên từng dòng. Nguồn mua có sẵn đã điền tự động; dòng trống có nút Xem / chọn nguồn mua.</p>';
      if(loadedPeriod&&loadedPeriod.from===loadedPeriod.to&&field('from').value===loadedPeriod.from&&field('to').value===loadedPeriod.to&&selected.some(function(r){return !r.document_date;})){
        dialog.querySelector('.bk-row-summary').innerHTML+='<button type="button" class="btn btn-primary" data-bk="apply-period-date">Điền ngày '+esc(loadedPeriod.from.split('-').reverse().join('/'))+' cho dòng đã chọn</button><p class="muted">Bấm khi đây đúng là ngày mua thực tế. Chỉ điền Ngày mua thực tế còn trống; giữ nguyên các thông tin khác.</p>';
      }
    }
    function payload() {
      collect();
      if (!loadedPeriod || loadedPeriod.from!==field('from').value || loadedPeriod.to!==field('to').value) throw new Error('Bấm “Xem hàng tồn âm” để cập nhật khoảng ngày trước khi tải.');
      if (loadedPeriod.tax!==field('tax').value) throw new Error('Bấm “Xem hàng tồn âm” để cập nhật Nhóm hàng trước khi tải.');
      var selected=rows.filter(function(r){return r.selected;});
      if (!selected.length) throw new Error('Chọn ít nhất một dòng để lập bảng kê.');
      var nextLine=selected.reduce(function(max,r){return Math.max(max,Number(r.source_line)||0);},0);
      return {from:loadedPeriod.from,to:loadedPeriod.to,document_date:'',reference:field('reference').value,
        rows:selected.map(function(r){return {document_date:r.document_date||'',product_code:r.product_code,qty:r.qty,unit_cost:r.unit_cost,source_party:r.source_party||'',note:(r.note||'')+(r.source_key?' [TDP-SOURCE:'+r.source_key+']':''),source_line:r.source_line||++nextLine};})};
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
        if(['load','file','add','next','confirm'].indexOf(name)>=0){var sourcePanel=dialog.querySelector('.bk-source-panel');sourcePanel.hidden=true;sourcePanel.innerHTML='';}
        if(['load','file','add','all','none','preview'].indexOf(name)>=0){review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';}
        if (name==='load') {
          if(loadedPeriod)periodDrafts[loadedPeriod.from+'|'+loadedPeriod.to+'|'+loadedPeriod.tax]={rows:rows,date:field('document_date').value,reference:field('reference').value,seller:field('source_party').value};
          status('Đang đối chiếu sổ kho…');
          var result=await options.api('/api/bk-import/shortages?'+new URLSearchParams({from:field('from').value,to:field('to').value,tax:field('tax').value}));
          if(!dialog.isConnected)return;
          loadedPeriod={from:result.from,to:result.to,tax:field('tax').value};
          var kept=periodDrafts[result.from+'|'+result.to+'|'+loadedPeriod.tax], fresh=[];
          result.items.forEach(function(item){
            var left=Number(item.suggested_qty),sources=(item.purchase_sources||[]).filter(function(s){return !s.already_posted;});
            sources.forEach(function(source){var qty=Math.min(left,Number(source.purchase_qty));left=Math.max(0,left-qty);fresh.push(Object.assign({},item,source,{row_key:source.source_key,source_party_original:source.source_party,suggested_qty:qty,price_source:'Giá mua từ '+source.source_description}));});
            if(!sources.length||left>0.000001)fresh.push(Object.assign({},item,{row_key:item.product_code+':unmatched',suggested_qty:left,source_description:'Chưa có nguồn mua chưa ghi kho phù hợp. Kiểm tra nguồn và ngày mua thực tế; chọn người bán từ danh mục đã lưu.'}));
          });
          rows=fresh.map(function(r){var old=kept&&kept.rows.find(function(k){return (k.row_key||k.product_code)===(r.row_key||r.product_code);}),merged=Object.assign({},r,{qty:r.suggested_qty,selected:false,unit_cost:r.unit_cost == null?'':r.unit_cost,source_party:r.source_party||'',note:''},old||{},{closing_qty:r.closing_qty,suggested_qty:r.suggested_qty});if(old&&Number(old.qty)===Number(old.suggested_qty))merged.qty=r.suggested_qty;return merged;});
          if(kept){kept.rows.forEach(function(r){if(!fresh.some(function(f){return (f.row_key||f.product_code)===(r.row_key||r.product_code);}))rows.push(Object.assign({},r,{closing_qty:null,selected:false}));});}
          field('document_date').value=kept?kept.date:(result.from===result.to?result.from:'');field('reference').value=kept?kept.reference:('BKBS-'+result.to.slice(0,7).replace('-','')+'-'+crypto.randomUUID().slice(0,8).toUpperCase());field('source_party').value=kept?kept.seller:'';
          render(); status(result.items.length+' mã hàng còn thiếu đến hết '+result.to.split('-').reverse().join('/')+'. Lượng thiếu được phân gợi ý theo nguồn mua, không cộng lặp giữa các ngày. Dòng lượng 0 chưa cần bổ sung. Bấm Chọn tất cả hoặc chọn từng dòng đã mua cần bổ sung chứng từ.'+(kept?' Đã giữ thông tin đang nhập; kiểm tra lại lượng mua với tồn mới.':''));
          dialog.querySelector('.bk-draft-preview').innerHTML='';
          if(result.source_warnings&&result.source_warnings.length){var warning=document.createElement('p');warning.className='error-summary';warning.textContent=result.source_warnings.join(' | ');dialog.querySelector('.bk-draft-table').prepend(warning);}
          if(options.productCode){
            var index=rows.findIndex(function(r){return r.product_code===options.productCode;});
            if(index>=0){var target=dialog.querySelector('[data-row="'+index+'"]');target.scrollIntoView({block:'center'});focusAfterAction=rowField(index,'selected');}
            options.productCode=null;
          }
        } else if(name==='apply-period-date') {
          if(!loadedPeriod||loadedPeriod.from!==loadedPeriod.to||field('from').value!==loadedPeriod.from||field('to').value!==loadedPeriod.to)throw new Error('Chọn cùng một ngày ở Từ ngày và Đến ngày, rồi bấm Xem hàng tồn âm.');
          field('document_date').value=loadedPeriod.from;var changed=0;rows.forEach(function(r){if(r.selected&&!r.document_date){r.common_date=true;r.document_date=loadedPeriod.from;changed++;}});
          review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';render();status('Đã điền Ngày mua thực tế '+loadedPeriod.from.split('-').reverse().join('/')+' cho '+changed+' dòng còn trống. Người bán, lượng mua và đơn giá được giữ nguyên.');
        } else if(name==='apply-common'||name==='apply-date') {
          var chosen=rows.filter(function(r){return r.selected;});
          if(!chosen.length)throw new Error('Chọn ít nhất một dòng để điền nhanh.');
          var day=name==='apply-date'?field('document_date').value:'',seller=name==='apply-common'?field('source_party').value.trim():'';
          if(!day&&!seller)throw new Error('Điền Ngày mua thực tế hoặc Người bán / NCC tương ứng với nút vừa bấm.');
          if(day&&loadedPeriod&&(day<loadedPeriod.from||day>loadedPeriod.to))throw new Error('Ngày mua thực tế phải nằm trong khoảng Từ ngày – Đến ngày đang chọn.');
          chosen.forEach(function(r){if(!r.document_date&&day)r.document_date=day;if(!r.source_party&&seller)r.source_party=seller;});
          review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';render();status('Đã áp dụng '+(name==='apply-date'?'Ngày mua thực tế':'Người bán / NCC')+' vào ô trống của các dòng đã chọn. Các ô đã có thông tin được giữ nguyên.');
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
          rows.forEach(function(r){r.selected=name==='all'&&Number(r.qty)>0;});render();
        } else if(name==='excel') {
          await options.downloadFile('/api/bk-import/draft/excel',post(payload()));status('Đã tải bảng kê. Kho chưa thay đổi.');
        } else if(name==='next') {
          review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';field('reference').value='';
          periodDrafts={};loadedPeriod=null;setTimeout(function(){action('load');},0);status('Đang tính lại phần còn thiếu và nguồn mua chưa bổ sung…');
        } else if(name==='preview') {
          var draft=payload();validatePreview();
          status('Đang tạo bản in…');
          var preview=await options.api('/api/bk-import/draft/preview',post(draft));
          if(!dialog.isConnected)return;
          review=preview;
          var base='/api/documents/'+encodeURIComponent(preview.token);
          var receiptSheets=preview.sheets.map(function(s,i){return /^biên nhận(?:\s+\d+)?$/i.test(s.name.trim())?i:null;}).filter(function(i){return i!==null;});
          var receiptPrint=receiptSheets.length?'<a class="btn btn-primary" data-bk-receipt-a5 target="_blank" rel="noopener" href="'+base+'/pdf?paper=A5&sides=simplex&amp;sheets='+receiptSheets.join(',')+'">In biên nhận A5</a>':'';
          dialog.querySelector('.bk-draft-preview').innerHTML='<div class="bk-draft-controls"><a class="btn btn-primary" target="_blank" rel="noopener" href="'+base+'/pdf?paper=A4&sides=simplex">In cả bộ A4</a>'+receiptPrint+'<a class="btn btn-outline" href="'+base+'/excel">Tải Excel bản in</a></div>'+preview.sheets.map(function(s){return '<details class="bk-supplement-paper" open><summary>'+esc(s.name)+'</summary><div class="bk-draft-paper">'+s.html+'</div></details>';}).join('')+
            (preview.already_posted?'<p>Bộ này đã ghi kho. In hoặc tải lại không cộng thêm kho.</p>':'<div class="bk-supplement-confirm"><p>Tổng tiền mua bổ sung: <strong>'+Number(preview.totals.amount).toLocaleString('vi-VN')+'đ</strong>.</p>'+(preview.rebuild_periods.length?'<p>Tháng '+esc(preview.rebuild_periods.join(', '))+' đã chốt. Khi xác nhận, hệ thống sẽ tính lại tồn chuyển sang tháng sau; nếu không đạt kiểm tra thì không ghi thay đổi nào.</p>':'')+'<label>Người xác nhận<input name="confirm_actor" maxlength="100" placeholder="Họ tên người kiểm tra"></label><label><input name="confirm_actual" type="checkbox"> Tôi đã kiểm tra hàng mua thực tế, ngày mua, người bán và đồng ý nhập kho'+(preview.rebuild_periods.length?', cập nhật tồn chuyển kỳ':'')+'.</label><button class="btn btn-primary" data-bk="confirm" disabled>Xác nhận nhập kho một lần</button></div>');
          fitPapers();status(preview.already_posted?'Bộ bảng kê này đã ghi kho.':'Đã tạo bảng kê tổng và biên nhận. Kiểm tra bản in, rồi xác nhận nhập kho ở dưới.');
          dialog.querySelector('.bk-draft-preview').scrollIntoView({block:'start'});
        } else if(name==='confirm') {
          if(!review || !field('confirm_actual').checked || !field('confirm_actor').value.trim())throw new Error('Điền tên và xác nhận đã kiểm tra hàng mua thực tế.');
          var saved=await options.api('/api/bk-import/draft/confirm',post({token:review.import_token,confirmed:true,actor:field('confirm_actor').value}));
          delete periodDrafts[loadedPeriod.from+'|'+loadedPeriod.to+'|'+loadedPeriod.tax];
          rows.forEach(function(r){var current=saved.stock.find(function(s){return s.product_code===r.product_code;});if(current){r.closing_qty=current.closing_qty;r.selected=false;r.qty=0;}});
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
      finally {busy=false;dialog.querySelectorAll('button,input,select').forEach(function(b){b.disabled=false;});var confirm=dialog.querySelector('[data-bk="confirm"]');if(confirm)confirm.disabled=!field('confirm_actual').checked||!field('confirm_actor').value.trim();if(focusAfterAction){focusIssue(focusAfterAction);focusAfterAction=null;}}
    }
    dialog.addEventListener('click',function(e){
      if(busy&&!e.target.closest('[data-bk="close"]'))return;
      var sourceButton=e.target.closest('[data-bk-source]');
      if(sourceButton){collect();var index=Number(sourceButton.dataset.bkSource),r=rows[index],panel=dialog.querySelector('.bk-source-panel'),sources=r.purchase_sources||[];panel.hidden=false;
        panel.innerHTML='<strong>'+esc(r.product_code+' · '+r.product_name)+'</strong><p>'+(!sources.length?'Không tìm thấy nguồn mua phù hợp trong kỳ đã chọn. Kiểm tra kỳ, mã hàng và chứng từ mua; chỉ điền ngày và người bán khi có thông tin thực tế.':'Nguồn đã ghi kho chỉ để đối chiếu. Nguồn chưa ghi kho đã có dòng riêng bên dưới; bấm Chọn dòng nguồn để đến đúng dòng, không tạo thêm lượng mua.')+'</p>'+sources.map(function(source){var target=rows.findIndex(function(x){return x.source_key===source.source_key;});return '<p>'+esc(source.document_date+' · '+source.source_party+' · '+source.purchase_qty+' '+source.unit+' · '+source.source_description)+' '+(source.already_posted?'<strong>Đã ghi kho — không nhập lại</strong>':target>=0?'<button type="button" class="btn btn-outline" data-bk-source-row="'+target+'">Chọn dòng nguồn</button>':'')+'</p>';}).join('')+'<button type="button" class="btn btn-outline" data-bk-manual="'+index+'">Điền theo chứng từ thực tế</button> <button type="button" class="btn btn-outline" data-bk-source-close>Đóng nguồn mua</button>';panel.scrollIntoView({block:'center'});return;}
      var sourceRow=e.target.closest('[data-bk-source-row]');if(sourceRow){collect();var i=Number(sourceRow.dataset.bkSourceRow);rows[i].selected=true;review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';render();focusIssue(rowField(i,'qty'));return;}
      var manual=e.target.closest('[data-bk-manual]');if(manual){focusIssue(rowField(Number(manual.dataset.bkManual),'document_date'));return;}
      if(e.target.closest('[data-bk-source-close]')){dialog.querySelector('.bk-source-panel').hidden=true;return;}
      var split=e.target.closest('[data-bk-split]');if(split){if(busy)return;collect();var source=rows[Number(split.dataset.bkSplit)];rows.push(Object.assign({},source,{row_key:(source.row_key||source.product_code)+':split:'+rows.length,qty:'',source_party:'',source_line:undefined,selected:true}));review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';render();focusIssue(rowField(rows.length-1,'source_party'));return;}var fix=e.target.closest('[data-bk-fix]');if(fix){focusIssue(issues[Number(fix.dataset.bkFix)].target);return;}var button=e.target.closest('[data-bk]');if(button)action(button.dataset.bk);});
    dialog.addEventListener('input',function(e){
      if(e.target.name==='confirm_actor'||e.target.name==='confirm_actual'){var button=dialog.querySelector('[data-bk="confirm"]');if(button)button.disabled=!field('confirm_actual').checked||!field('confirm_actor').value.trim();return;}
      if(issues.length){clearIssues();status('Đã thay đổi thông tin. Bấm Xem bảng kê tổng & biên nhận để kiểm tra lại.');}
      review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';
      collect();dailyWarnings();updateSellerDetails();updateSummary();
    });
    dialog.addEventListener('close',function(){paperObserver.disconnect();dialog.remove();});
    options.api('/api/bk-import/draft/sellers').then(function(p){if(dialog.isConnected){sellerCatalog=p.items||[];dialog.querySelector('#bk-supplement-sellers').innerHTML=p.names.map(function(n){return '<option value="'+esc(n)+'"></option>';}).join('');updateSellerDetails();}}).catch(function(){updateSellerDetails();});
    render(); action('load');
  };
})(window);
