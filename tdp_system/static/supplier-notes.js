(function(root) {
  'use strict';
  root.TdpSupplierNotes = async function(options) {
    var esc=options.esc, dialog=document.createElement('dialog'), rows=[], planHash='', busy=false;
    dialog.className='supplier-notes-dialog';
    dialog.setAttribute('aria-label','Ghi chú đơn NCC');
    dialog.innerHTML='<div class="supplier-notes-head"><h2>Ghi chú đơn NCC</h2><button type="button" class="btn btn-outline" data-notes-close>Đóng</button></div>'+
      '<p>Ghi lời dặn theo từng bếp, từng mặt hàng. Ghi chú được lưu để hiện trên ảnh và file đơn đặt NCC.</p>'+
      '<form><div class="supplier-notes-table"></div><p role="status" class="supplier-notes-status">Đang tải ghi chú…</p>'+
      '<button class="btn btn-primary" type="submit" disabled>Lưu ghi chú</button></form>';
    document.body.appendChild(dialog);dialog.showModal();
    var status=dialog.querySelector('[role=status]'), save=dialog.querySelector('[type=submit]');
    function edits(){return rows.map(function(r,i){return {note_key:r.note_key,note:dialog.querySelector('[data-note-index="'+i+'"]').value};});}
    function dirty(){return rows.length&&edits().some(function(r,i){return r.note!==rows[i].note;});}
    function close(){if(busy)return;if(dirty()&&!root.confirm('Ghi chú chưa lưu. Đóng và bỏ phần vừa sửa?'))return;dialog.close();}
    dialog.querySelector('[data-notes-close]').addEventListener('click',close);
    dialog.addEventListener('cancel',function(e){e.preventDefault();close();});
    dialog.addEventListener('close',function(){dialog.remove();});
    dialog.querySelector('form').addEventListener('submit',async function(e){
      e.preventDefault();if(busy||!rows.length)return;busy=true;save.disabled=true;
      dialog.querySelectorAll('textarea').forEach(function(el){el.disabled=true;});
      try {
        var result=await options.api('/api/supplier-needs/'+options.batchId+'/notes',{
          method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_hash:planHash,rows:edits()})});
        planHash=result.plan_hash;rows.forEach(function(r,i){r.note=dialog.querySelector('[data-note-index="'+i+'"]').value;});
        status.textContent='Đã lưu ghi chú. Ảnh và file đơn NCC lấy nội dung vừa lưu.';
        await options.onSaved();
      }catch(error){status.textContent=error.message;}
      finally{busy=false;save.disabled=false;dialog.querySelectorAll('textarea').forEach(function(el){el.disabled=false;});}
    });
    try {
      var data=await options.api('/api/supplier-needs/'+options.batchId);
      if(!dialog.isConnected)return;
      if(!data.send_available)throw new Error(data.source_message);
      var supplierRows=data.groups.filter(function(g){return g.supplier_key===options.supplierKey;});
      var keys=new Set(supplierRows.reduce(function(list,g){return list.concat(g.items.reduce(function(a,r){return a.concat(r.source_refs);},[]));},[]).map(function(r){return r.row_key||'order:'+r.order_id;}));
      rows=data.rows.filter(function(r){return keys.has(r.row_key||'order:'+r.order_id);});
      if(!rows.length)throw new Error('NCC không còn dòng đặt hàng. Hãy tải lại danh sách.');
      planHash=data.plan_hash;
      dialog.querySelector('h2').textContent='Ghi chú NCC '+supplierRows[0].supplier+' · '+options.dateText(data.work_date);
      dialog.querySelector('.supplier-notes-table').innerHTML='<table><thead><tr><th>Bếp</th><th>Mặt hàng</th><th>SL</th><th>ĐVT</th><th>Ghi chú khách dặn</th></tr></thead><tbody>'+rows.map(function(r,i){return '<tr><td>'+esc(r.kitchen)+'</td><td>'+esc(r.product_name)+'</td><td>'+esc(options.quantity(r.order_qty))+'</td><td>'+esc(r.unit)+'</td><td><textarea maxlength="1000" rows="3" data-note-index="'+i+'" aria-label="Ghi chú '+esc(r.kitchen+' '+r.product_name)+'" placeholder="Nhập lời dặn của khách">'+esc(r.note||'')+'</textarea></td></tr>';}).join('')+'</tbody></table>';
      status.textContent='Sửa ghi chú rồi bấm Lưu ghi chú. Đơn đã gửi mà đổi lời dặn sẽ chuyển sang Cần đặt lại.';save.disabled=false;
    }catch(error){status.textContent=error.message;}
  };
})(window);
