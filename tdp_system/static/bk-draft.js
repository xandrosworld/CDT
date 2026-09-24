(function (root) {
  'use strict';
  root.TdpBkDraft = function (options) {
    var esc = options.esc, dialog = document.createElement('dialog'), rows = [], loadedPeriod = null, review = null, periodDrafts = {};
    dialog.className = 'bk-draft-dialog';
    dialog.setAttribute('aria-label', 'Lập bảng kê bổ sung');
    dialog.innerHTML = '<div class="bk-draft-head"><h2>Lập bảng kê bổ sung</h2><button class="btn btn-outline" data-bk="close" aria-label="Đóng">Đóng</button></div>' +
      '<p>Chốt phần cần xuất ở Bảng kê &amp; hóa đơn trước. KKKNT vẫn được xuất đủ lượng đã chọn khi thiếu tồn. Sau khi hóa đơn đã ký được cập nhật và trừ kho, mở phần này để đối chiếu lượng còn thiếu thực tế; hàng bỏ không xuất không tự tạo nhu cầu nhập.</p>' +
      '<p>1. Đối chiếu phần còn thiếu và thông tin mua thực tế → 2. Xem bảng kê tổng, biên nhận → 3. Xác nhận nhập kho. Tải và in chưa cộng kho; duyệt đơn hàng cũng không cộng kho hóa đơn.</p>' +
      '<div class="bk-draft-controls"><label>Từ ngày<input name="from" type="date" value="' + esc(options.from) + '"></label>' +
      '<label>Đến ngày<input name="to" type="date" value="' + esc(options.to) + '"></label>' +
      '<label>Nhóm hàng<select name="tax"><option value="KKKNT">KKKNT</option><option value="all">Tất cả hàng tồn âm</option></select></label>' +
      '<button class="btn btn-outline" data-bk="load">Xem hàng tồn âm</button></div>' +
      '<p>Chọn Từ ngày – Đến ngày để xem chung và chọn hàng một lần. Các dòng mua của hàng còn âm được đưa sang theo ngày và người bán. Kiểm tra đúng người bán thực tế trước khi chọn. Lượng gợi ý là lượng còn thiếu đến hết Đến ngày, gồm cả thiếu từ trước chưa bổ sung; không cộng lặp lượng âm của từng ngày. Ngày mua thực tế vẫn điền theo hàng đã mua.</p>' +
      '<p class="muted">Có thể chọn lại tháng 8 hoặc kỳ trước. Lượng tồn âm chỉ để đối chiếu; sửa số lượng theo hàng thực mua. Có nguồn mua thì dùng giá mua của dòng nguồn. Khi chưa ghép được nguồn, đơn giá gợi ý bằng 95% giá bán gần nhất của đơn đã duyệt đến hết Đến ngày, cùng ĐVT. Nếu chưa có đơn, dùng giá hóa đơn bán đã ký và ghi kho cùng ĐVT. Nguồn giá hiện dưới mỗi ô; có thể sửa trước khi tải.</p>' +
      '<div class="bk-draft-controls"><label>Ngày mua thực tế<input name="document_date" type="date"></label>' +
      '<label>Số bảng kê<input name="reference" maxlength="100" placeholder="Nhập số của bảng kê đang lập" aria-describedby="bk-reference-help"><small id="bk-reference-help">Số để nhận biết bảng kê này; nhập theo cách đánh số chị đang dùng.</small></label>' +
      '<label>Người bán chung<input name="source_party" list="bk-supplement-sellers" maxlength="150" placeholder="Chọn tên trong danh mục"></label><datalist id="bk-supplement-sellers"></datalist></div>' +
      '<details><summary>Đã sửa file Excel: mở lại tại đây</summary><input name="import_file" type="file" accept=".xlsx" aria-label="File bảng kê bổ sung đã sửa"><button class="btn btn-outline" data-bk="file">Đọc file đã sửa</button><p>Đọc file chưa ghi kho. Xem bộ bảng kê rồi xác nhận bên dưới.</p></details>' +
      '<div class="bk-draft-controls"><label>Thêm hàng ngoài danh sách tồn âm<input name="search" placeholder="Tìm theo mã hoặc tên hàng"></label>' +
      '<button class="btn btn-outline" data-bk="search">Tìm hàng</button><select name="product" aria-label="Kết quả tìm hàng"></select>' +
      '<button class="btn btn-outline" data-bk="add">Thêm dòng</button></div>' +
      '<p class="bk-draft-status" role="status"></p><div class="bk-draft-issues" role="alert" hidden></div><div class="bk-daily-warning" role="status"></div><div class="bk-draft-table"></div>' +
      '<div class="bk-draft-controls"><button class="btn btn-outline" data-bk="all">Chọn tất cả</button>' +
      '<button class="btn btn-outline" data-bk="none">Bỏ chọn</button>' +
      '<button class="btn btn-primary" data-bk="excel">Tải Excel để nhập lại</button>' +
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
    function dailyWarnings() {
      var groups={};
      rows.forEach(function(r,i){if(!r.selected)return;var seller=String(r.source_party||field('source_party').value).trim(),day=r.document_date||field('document_date').value,key=day+'|'+seller.toLocaleLowerCase();if(!seller||!day)return;if(!groups[key])groups[key]={seller:seller,day:day,amount:0,index:i};groups[key].amount+=(Number(r.qty)||0)*(Number(r.unit_cost)||0);});
      var over=Object.values(groups).filter(function(g){return g.amount>5000000;});
      dialog.querySelector('.bk-daily-warning').innerHTML=over.map(function(g){return '<p class="error-summary">'+esc(g.seller+' · '+g.day)+': '+g.amount.toLocaleString('vi-VN')+'đ, vượt 5.000.000đ/người/ngày. Kiểm tra lượng mua và người bán thực tế. Không đổi ngày mua để chia hạn mức. <button type="button" class="btn btn-outline" data-bk-split="'+g.index+'">Thêm người bán thực tế cùng ngày</button></p>';}).join('');
      return over;
    }
    function validatePreview() {
      var missing=[];
      function add(message,target,label){missing.push({message:message,target:target,label:label});}
      if(rows.some(function(r){return r.selected&&!r.document_date;})&&!field('document_date').value)add('Chưa điền Ngày mua thực tế.',field('document_date'),'Điền ngày mua');
      else if(field('document_date').value && loadedPeriod && (field('document_date').value<loadedPeriod.from || field('document_date').value>loadedPeriod.to))add('Ngày mua thực tế phải nằm trong khoảng Từ ngày – Đến ngày đang chọn.',field('document_date'),'Sửa ngày mua');
      if(!field('reference').value.trim())add('Chưa điền Số bảng kê. Đây là số của bảng kê đang lập, không phải tìm ở bảng khác.',field('reference'),'Điền số bảng kê');
      var noSeller=rows.filter(function(r){return r.selected&&!String(r.source_party||'').trim()&&!field('source_party').value.trim();});
      if(noSeller.length)add(noSeller.length+' mặt hàng chưa có Người bán / NCC. Điền Người bán chung hoặc điền riêng từng dòng.',field('source_party'),'Điền người bán chung');
      rows.forEach(function(r,i){
        if(!r.selected)return;
        var title=r.product_name+' ('+r.product_code+')';
        if(!String(r.qty==null?'':r.qty).trim() || !Number.isFinite(Number(r.qty)) || Number(r.qty)<=0)add(title+': Lượng mua bổ sung phải lớn hơn 0.',rowField(i,'qty'),'Sửa lượng mua');
        if(!String(r.unit_cost==null?'':r.unit_cost).trim() || !Number.isFinite(Number(r.unit_cost)) || Number(r.unit_cost)<=0)add(title+': Đơn giá phải lớn hơn 0.',rowField(i,'unit_cost'),'Sửa đơn giá');
        var day=r.document_date||field('document_date').value;
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
        var i=rows.findIndex(function(r){var seller=String(r.source_party||field('source_party').value).trim();return r.selected&&seller&&message.indexOf(seller)>=0;});
        if(i>=0){target=rowField(i,'source_party');label='Kiểm tra người bán thực tế';}
      }
      return target?[{message:message,target:target,label:label}]:[];
    }
    function collect() {
      dialog.querySelectorAll('tr[data-row]').forEach(function(tr) {
        var row=rows[Number(tr.dataset.row)]; row.selected=tr.querySelector('[data-field="selected"]').checked;
        ['document_date','qty','unit_cost','source_party','note'].forEach(function(key){row[key]=tr.querySelector('[data-field="'+key+'"]').value;});
      });
    }
    function purchaseHistoryHtml(r) {
      var history=(r.purchase_sources||[]).filter(function(s){return s.already_posted;});
      if(!history.length)return '';
      return '<details><summary>Nguồn mua đã ghi bảng kê ('+history.length+')</summary><p>Chỉ tra cứu; không gợi ý nhập lại nguồn đã ghi kho. Lượng âm hiện tại cần đối chiếu nguồn nhập, xuất và mã hàng.</p>'+history.map(function(s){return '<p>'+esc(s.document_date+' · '+s.source_party+' · '+s.cccd+' · '+s.address+' · Ngày cấp: '+(s.issue_date||'chưa có')+' · Nơi cấp: '+(s.issue_place||'chưa có')+' · Đã ghi: '+s.posted_qty+' '+s.unit+' · '+s.source_description)+'</p>';}).join('')+'</details>';
    }
    function render() {
      dialog.querySelector('.bk-draft-table').innerHTML='<table><thead><tr><th>Chọn</th><th>Mã / tên hàng</th><th>ĐVT</th><th>Ngày mua thực tế</th><th>Tồn cuối ngày '+esc(loadedPeriod ? loadedPeriod.to.split('-').reverse().join('/') : '')+'</th><th>Lượng mua bổ sung</th><th>Đơn giá</th><th>Người bán / NCC</th><th>Ghi chú</th></tr></thead><tbody>'+rows.map(function(r,i){
        return '<tr data-row="'+i+'"><td><input data-field="selected" type="checkbox" '+(r.selected?'checked':'')+' aria-label="Chọn '+esc(r.product_code)+'"></td><td>'+esc(r.product_code)+'<br>'+esc(r.product_name)+purchaseHistoryHtml(r)+'</td><td>'+esc(r.unit)+'</td><td><input type="date" data-field="document_date" value="'+esc(r.document_date||'')+'" aria-label="Ngày mua thực tế '+esc(r.product_code)+'"><small>'+esc(r.source_description||'')+'</small></td><td>'+esc(r.closing_qty == null?'—':options.quantity(r.closing_qty))+'</td>'+['qty','unit_cost','source_party','note'].map(function(key){
          var numeric=key==='qty'||key==='unit_cost';
          return '<td><input data-field="'+key+'" '+(numeric?'type="number" min="0" step="any"':'type="text" maxlength="'+(key==='note'?500:150)+'"')+(key==='source_party'?' list="bk-supplement-sellers"':'')+' value="'+esc(r[key] == null?'':r[key])+'" aria-label="'+esc(key+' '+r.product_code)+'">'+(key==='source_party'?'<small>'+esc(r.source_party_original ? 'Người bán nguồn: '+r.source_party_original+' · '+(r.cccd||'')+' · '+(r.address||'')+' · Ngày cấp: '+(r.issue_date||'chưa có')+' · Nơi cấp: '+(r.issue_place||'chưa có') : '')+'</small><button type="button" data-bk-split="'+i+'" class="btn btn-outline">Thêm người bán cùng ngày</button>':'')+(key==='unit_cost'?'<div class="muted bk-price-source">'+esc(r.price_source || '')+'</div>':'')+'</td>';
        }).join('')+'</tr>';
      }).join('')+'</tbody></table>';
      dailyWarnings();
    }
    function payload() {
      collect();
      if (!loadedPeriod || loadedPeriod.from!==field('from').value || loadedPeriod.to!==field('to').value) throw new Error('Bấm “Xem hàng tồn âm” để cập nhật khoảng ngày trước khi tải.');
      if (loadedPeriod.tax!==field('tax').value) throw new Error('Bấm “Xem hàng tồn âm” để cập nhật Nhóm hàng trước khi tải.');
      var selected=rows.filter(function(r){return r.selected;});
      if (!selected.length) throw new Error('Chọn ít nhất một dòng để lập bảng kê.');
      var nextLine=selected.reduce(function(max,r){return Math.max(max,Number(r.source_line)||0);},0);
      return {from:loadedPeriod.from,to:loadedPeriod.to,document_date:field('document_date').value,reference:field('reference').value,
        rows:selected.map(function(r){return {document_date:r.document_date||field('document_date').value,product_code:r.product_code,qty:r.qty,unit_cost:r.unit_cost,source_party:r.source_party||field('source_party').value,note:(r.note||'')+(r.source_key?' [TDP-SOURCE:'+r.source_key+']':''),source_line:r.source_line||++nextLine};})};
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
          if(loadedPeriod)periodDrafts[loadedPeriod.from+'|'+loadedPeriod.to+'|'+loadedPeriod.tax]={rows:rows,date:field('document_date').value,reference:field('reference').value,seller:field('source_party').value};
          status('Đang đối chiếu sổ kho…');
          var result=await options.api('/api/bk-import/shortages?'+new URLSearchParams({from:field('from').value,to:field('to').value,tax:field('tax').value}));
          if(!dialog.isConnected)return;
          loadedPeriod={from:result.from,to:result.to,tax:field('tax').value};
          var kept=periodDrafts[result.from+'|'+result.to+'|'+loadedPeriod.tax], fresh=[];
          result.items.forEach(function(item){
            var left=Number(item.suggested_qty),sources=(item.purchase_sources||[]).filter(function(s){return !s.already_posted;});
            sources.forEach(function(source){var qty=Math.min(left,Number(source.purchase_qty));left=Math.max(0,left-qty);fresh.push(Object.assign({},item,source,{row_key:source.source_key,source_party_original:source.source_party,suggested_qty:qty,price_source:'Giá mua từ '+source.source_description}));});
            if(!sources.length||left>0.000001)fresh.push(Object.assign({},item,{row_key:item.product_code+':unmatched',suggested_qty:left,source_description:'Chưa ghép được nguồn mua; điền theo chứng từ thực tế.'}));
          });
          rows=fresh.map(function(r){var old=kept&&kept.rows.find(function(k){return (k.row_key||k.product_code)===(r.row_key||r.product_code);}),merged=Object.assign({},r,{qty:r.suggested_qty,selected:false,unit_cost:r.unit_cost == null?'':r.unit_cost,source_party:r.source_party||'',note:''},old||{},{closing_qty:r.closing_qty,suggested_qty:r.suggested_qty});if(old&&Number(old.qty)===Number(old.suggested_qty))merged.qty=r.suggested_qty;return merged;});
          if(kept){kept.rows.forEach(function(r){if(!fresh.some(function(f){return (f.row_key||f.product_code)===(r.row_key||r.product_code);}))rows.push(Object.assign({},r,{closing_qty:null,selected:false}));});}
          field('document_date').value=kept?kept.date:'';field('reference').value=kept?kept.reference:'';field('source_party').value=kept?kept.seller:'';
          render(); status(result.items.length+' mã hàng còn thiếu đến hết '+result.to.split('-').reverse().join('/')+'. Lượng thiếu được phân gợi ý theo nguồn mua, không cộng lặp giữa các ngày. Dòng lượng 0 chưa cần bổ sung. Bấm Chọn tất cả hoặc chọn từng dòng đã mua cần bổ sung chứng từ.'+(kept?' Đã giữ thông tin đang nhập; kiểm tra lại lượng mua với tồn mới.':''));
          dialog.querySelector('.bk-draft-preview').innerHTML='';
          if(result.source_warnings&&result.source_warnings.length){var warning=document.createElement('p');warning.className='error-summary';warning.textContent=result.source_warnings.join(' | ');dialog.querySelector('.bk-draft-table').prepend(warning);}
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
          dialog.querySelector('.bk-draft-preview').innerHTML='<div class="bk-draft-controls"><a class="btn btn-primary" target="_blank" rel="noopener" href="'+base+'/pdf?paper=A4&sides=simplex">In bộ bảng kê & biên nhận</a><a class="btn btn-outline" href="'+base+'/excel">Tải Excel bản in</a></div>'+preview.sheets.map(function(s){return '<details class="bk-supplement-paper" open><summary>'+esc(s.name)+'</summary><div class="bk-draft-paper">'+s.html+'</div></details>';}).join('')+
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
      finally {busy=false;dialog.querySelectorAll('button,input,select').forEach(function(b){b.disabled=false;});var confirm=dialog.querySelector('[data-bk="confirm"]');if(confirm)confirm.disabled=!field('confirm_actual').checked;if(focusAfterAction){focusIssue(focusAfterAction);focusAfterAction=null;}}
    }
    dialog.addEventListener('click',function(e){var split=e.target.closest('[data-bk-split]');if(split){collect();var source=rows[Number(split.dataset.bkSplit)];rows.push(Object.assign({},source,{row_key:(source.row_key||source.product_code)+':split:'+rows.length,qty:'',source_party:'',source_line:undefined,selected:true}));review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';render();focusIssue(rowField(rows.length-1,'source_party'));return;}var fix=e.target.closest('[data-bk-fix]');if(fix){focusIssue(issues[Number(fix.dataset.bkFix)].target);return;}var button=e.target.closest('[data-bk]');if(button)action(button.dataset.bk);});
    dialog.addEventListener('input',function(e){
      if(e.target.name==='confirm_actor'||e.target.name==='confirm_actual'){var button=dialog.querySelector('[data-bk="confirm"]');if(button)button.disabled=!field('confirm_actual').checked;return;}
      if(issues.length){clearIssues();status('Đã thay đổi thông tin. Bấm Xem bảng kê tổng & biên nhận để kiểm tra lại.');}
      review=null;dialog.querySelector('.bk-draft-preview').innerHTML='';
      collect();dailyWarnings();
    });
    dialog.addEventListener('close',function(){paperObserver.disconnect();dialog.remove();});
    options.api('/api/bk-import/draft/sellers').then(function(p){if(dialog.isConnected)dialog.querySelector('#bk-supplement-sellers').innerHTML=p.names.map(function(n){return '<option value="'+esc(n)+'"></option>';}).join('');}).catch(function(){});
    render(); action('load');
  };
})(window);
