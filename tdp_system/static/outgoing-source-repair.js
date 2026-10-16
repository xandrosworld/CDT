(function () {
  'use strict';
  window.TdpSourceRepair = async function (options) {
    var dialog=document.createElement('dialog'),esc=options.esc,busy=false;
    dialog.className='purchase-selection-dialog';
    dialog.setAttribute('aria-label','Kiểm tra và xử lý hóa đơn đã ký');
    dialog.innerHTML='<header><h2>Kiểm tra và xử lý hóa đơn đã ký</h2><button class="btn btn-outline" data-close>Đóng</button></header><p>Hóa đơn '+esc(options.number)+' đã ký trên M-Invoice. Không xuất lại hóa đơn này.</p><p role="status">Đang kiểm tra mã hàng, kg thực tế và ghi xuất kho…</p><div data-result></div>';
    document.body.appendChild(dialog);dialog.showModal();
    dialog.querySelector('[data-close]').onclick=function(){if(!busy)dialog.close();};
    dialog.addEventListener('cancel',function(event){if(busy)event.preventDefault();});
    dialog.addEventListener('close',function(){dialog.remove();});
    async function check() {
      var status=dialog.querySelector('[role=status]'),box=dialog.querySelector('[data-result]');
      status.textContent='Đang kiểm tra…';box.innerHTML='';
      try {
        var data=await options.api('/api/invoice-workbench/output-postings?invoice_id='+options.invoiceId);
        if(!dialog.isConnected)return;
        var row=data.items[0],problem=data.blocked[0];
        if(!row){
          status.textContent=problem?problem.reason:'Hóa đơn đã được cập nhật; kiểm tra lại bảng kê.';
          box.innerHTML='<p>'+(problem&&problem.code==='actual_weight_source_unlinked'?'Chưa nối được số kg với file đã tải. Bấm So với file Excel để kiểm tra đúng người mua, mặt hàng và khoảng ngày đơn. Không nhập số kg thành số gói.':'Mở đúng hóa đơn để kiểm tra các dòng có cảnh báo. Sửa xong, quay lại bảng kê và bấm Kiểm tra và xử lý.')+'</p><button class="btn btn-primary" data-open>Mở đúng hóa đơn để xử lý</button> <button class="btn btn-outline" data-compare>So với file Excel đã tải</button> <button class="btn btn-outline" data-refresh>Cập nhật bảng kê</button>';
          box.querySelector('[data-open]').onclick=async function(){dialog.close();await options.openInvoice();};
          box.querySelector('[data-compare]').onclick=function(){dialog.close();options.compare();};
          box.querySelector('[data-refresh]').onclick=async function(){dialog.close();await options.onSaved();};
          return;
        }
        status.textContent='Đã kiểm tra đủ điều kiện ghi xuất kho. Xem số lượng dưới đây trước khi xác nhận.';
        box.innerHTML='<div class="selection-table"><table><thead><tr><th>Mặt hàng</th><th>Trên hóa đơn</th><th>Trừ kho</th></tr></thead><tbody>'+row.stock_lines.map(function(r){return '<tr><td>'+esc(r.code+' · '+r.name)+'</td><td>'+esc(r.invoice_qty+' '+r.invoice_unit)+'</td><td>'+esc(r.stock_qty+' '+r.unit)+'</td></tr>';}).join('')+'</tbody></table></div><p>Chỉ ghi nhận xuất kho cho hóa đơn đã ký; không gửi hay ký thêm hóa đơn. Sau đó phần mềm tính lại lượng đơn còn chưa xuất.</p><label><input type="checkbox" data-confirm> Tôi đã kiểm tra số lượng và đồng ý ghi xuất kho.</label><p><button class="btn btn-primary" data-post disabled>Xác nhận ghi kho và cập nhật bảng kê</button></p>';
        var confirm=box.querySelector('[data-confirm]'),post=box.querySelector('[data-post]');
        confirm.onchange=function(){post.disabled=!confirm.checked;};
        post.onclick=async function(){
          if(busy||!confirm.checked)return;busy=true;post.disabled=true;confirm.disabled=true;
          try {
            await options.api('/api/invoice-workbench/output-postings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:[{id:row.id,token:row.token}],confirmed:true})});
            status.textContent='Đã ghi xuất kho. Đang cập nhật bảng kê…';
            await options.onSaved();
            status.textContent='Đã ghi xuất kho và cập nhật bảng kê. Tiếp tục bước 4 để kiểm tra tồn và tạo file cho phần chưa xuất.';
            box.innerHTML='<button class="btn btn-primary" data-done>Quay lại bảng kê</button>';
            box.querySelector('[data-done]').onclick=function(){dialog.close();};
          }catch(error){status.textContent=error.message;box.innerHTML='<p>Số liệu hoặc kết nối vừa thay đổi. Kiểm tra lại trước khi xác nhận; phần lựa chọn mặt hàng được giữ nguyên.</p><button class="btn btn-primary" data-retry>Kiểm tra lại</button>';box.querySelector('[data-retry]').onclick=check;}
          finally{busy=false;}
        };
      }catch(error){status.textContent=error.message;box.innerHTML='<button class="btn btn-primary" data-retry>Thử kiểm tra lại</button>';box.querySelector('[data-retry]').onclick=check;}
    }
    await check();
  };
})();
