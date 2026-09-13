(function (root) {
  'use strict';
  root.TdpBkDraft = function (options) {
    var esc = options.esc, dialog = document.createElement('dialog'), rows = [], loadedPeriod = null;
    dialog.className = 'bk-draft-dialog';
    dialog.setAttribute('aria-label', 'Lập bảng kê bổ sung');
    dialog.innerHTML = '<div class="bk-draft-head"><h2>Lập bảng kê bổ sung</h2><button class="btn btn-outline" data-bk="close" aria-label="Đóng">Đóng</button></div>' +
      '<p>Chọn hàng thực mua chưa có hóa đơn để lập bảng kê. Tải và in chưa ghi nhập kho.</p>' +
      '<div class="bk-draft-controls"><label>Từ ngày<input name="from" type="date" value="' + esc(options.from) + '"></label>' +
      '<label>Đến ngày<input name="to" type="date" value="' + esc(options.to) + '"></label>' +
      '<label>Nhóm hàng<select name="tax"><option value="KKKNT">KKKNT</option><option value="all">Tất cả hàng tồn âm</option></select></label>' +
      '<button class="btn btn-outline" data-bk="load">Xem hàng tồn âm</button></div>' +
      '<p class="muted">Có thể chọn lại tháng 8 hoặc kỳ trước. Lượng tồn âm chỉ để đối chiếu; sửa số lượng theo hàng thực mua. Đơn giá gợi ý bằng 95% giá bán gần nhất của đơn đã duyệt đến ngày đối chiếu, cùng ĐVT. Nếu chưa có đơn, dùng giá hóa đơn bán đã ký và ghi kho cùng ĐVT. Nguồn giá hiện dưới mỗi ô; có thể sửa trước khi tải.</p>' +
      '<div class="bk-draft-controls"><label>Ngày mua thực tế<input name="document_date" type="date"></label>' +
      '<label>Số bảng kê<input name="reference" maxlength="100" placeholder="Điền theo chứng từ"></label>' +
      '<label>Người bán / NCC chung<input name="source_party" maxlength="150" placeholder="Có thể điền riêng từng dòng"></label></div>' +
      '<div class="bk-draft-controls"><label>Thêm hàng ngoài danh sách tồn âm<input name="search" placeholder="Tìm theo mã hoặc tên hàng"></label>' +
      '<button class="btn btn-outline" data-bk="search">Tìm hàng</button><select name="product" aria-label="Kết quả tìm hàng"></select>' +
      '<button class="btn btn-outline" data-bk="add">Thêm dòng</button></div>' +
      '<p class="bk-draft-status" role="status"></p><div class="bk-draft-table"></div>' +
      '<div class="bk-draft-controls"><button class="btn btn-outline" data-bk="all">Chọn tất cả</button>' +
      '<button class="btn btn-outline" data-bk="none">Bỏ chọn</button>' +
      '<button class="btn btn-primary" data-bk="excel">Tải Excel để nhập lại</button>' +
      '<button class="btn btn-primary" data-bk="preview">Xem và in bảng kê</button></div>' +
      '<p class="muted">Chưa đủ thông tin vẫn tải được để điền tiếp. Sau khi điền đủ, dùng “Nhập bảng kê bổ sung” trên web để kiểm tra rồi xác nhận nhập kho.</p>' +
      '<div class="bk-draft-preview"></div>';
    document.body.appendChild(dialog); dialog.showModal();
    var products = [], busy = false;
    function field(name) { return dialog.querySelector('[name="' + name + '"]'); }
    function status(text, error) { var el=dialog.querySelector('.bk-draft-status');el.textContent=text;el.style.color=error?'#ad2424':''; }
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
          return '<td><input data-field="'+key+'" '+(numeric?'type="number" min="0" step="any"':'type="text" maxlength="'+(key==='note'?1000:150)+'"')+' value="'+esc(r[key] == null?'':r[key])+'" aria-label="'+esc(key+' '+r.product_code)+'">'+(key==='unit_cost'?'<div class="muted bk-price-source">'+esc(r.price_source || '')+'</div>':'')+'</td>';
        }).join('')+'</tr>';
      }).join('')+'</tbody></table>';
    }
    function payload() {
      collect();
      if (!loadedPeriod || loadedPeriod.from!==field('from').value || loadedPeriod.to!==field('to').value) throw new Error('Bấm “Xem hàng tồn âm” để cập nhật khoảng ngày trước khi tải.');
      var selected=rows.filter(function(r){return r.selected;});
      if (!selected.length) throw new Error('Chọn ít nhất một dòng để lập bảng kê.');
      return {from:loadedPeriod.from,to:loadedPeriod.to,document_date:field('document_date').value,reference:field('reference').value,
        rows:selected.map(function(r){return {product_code:r.product_code,qty:r.qty,unit_cost:r.unit_cost,source_party:r.source_party||field('source_party').value,note:r.note};})};
    }
    function post(body) { return {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}; }
    async function action(name) {
      if (name==='close') {dialog.close();return;}
      if (busy) return;
      busy=true; dialog.querySelectorAll('button').forEach(function(b){if(b.dataset.bk!=='close')b.disabled=true;});
      dialog.querySelectorAll('input,select').forEach(function(el){el.disabled=true;});
      try {
        collect();
        if (name==='load') {
          if(rows.some(function(r){return r.selected;}) && !root.confirm('Nạp lại danh sách sẽ thay các dòng đang chọn. Tiếp tục?')) return;
          status('Đang đối chiếu sổ kho…');
          var result=await options.api('/api/bk-import/shortages?'+new URLSearchParams({from:field('from').value,to:field('to').value,tax:field('tax').value}));
          if(!dialog.isConnected)return;
          loadedPeriod={from:result.from,to:result.to};
          rows=result.items.map(function(r){return Object.assign({},r,{qty:r.suggested_qty,selected:false,unit_cost:r.unit_cost == null?'':r.unit_cost,source_party:'',note:''});});
          render(); status(rows.length+' mã đang âm cuối kỳ. Chọn những hàng đã mua cần bổ sung chứng từ.');
          dialog.querySelector('.bk-draft-preview').innerHTML='';
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
        } else if(name==='preview') {
          status('Đang tạo bản in…');
          var preview=await options.api('/api/bk-import/draft/preview',post(payload()));
          if(!dialog.isConnected)return;
          var base='/api/documents/'+encodeURIComponent(preview.token);
          dialog.querySelector('.bk-draft-preview').innerHTML='<div class="bk-draft-controls"><a class="btn btn-primary" target="_blank" rel="noopener" href="'+base+'/pdf?paper=A4&sides=simplex">Mở PDF để in</a><a class="btn btn-outline" href="'+base+'/excel">Tải Excel bản in</a></div>'+preview.sheets.map(function(s){return '<div class="bk-draft-paper">'+s.html+'</div>';}).join('');
          status('Bản in đã sẵn sàng. Kho chưa thay đổi.');
        }
      } catch(error) {status(error.message,true);}
      finally {busy=false;dialog.querySelectorAll('button,input,select').forEach(function(b){b.disabled=false;});}
    }
    dialog.addEventListener('click',function(e){var button=e.target.closest('[data-bk]');if(button)action(button.dataset.bk);});
    dialog.addEventListener('input',function(){dialog.querySelector('.bk-draft-preview').innerHTML='';});
    dialog.addEventListener('close',function(){dialog.remove();});
    render(); action('load');
  };
})(window);
