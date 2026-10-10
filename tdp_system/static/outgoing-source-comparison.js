(function () {
  'use strict';
  window.TdpSourceComparison = async function (options) {
    var dialog=document.createElement('dialog'),esc=options.esc;
    var money=function(n){return Number(n).toLocaleString('vi-VN',{maximumFractionDigits:2})+' đ';};
    dialog.className='purchase-selection-dialog';
    dialog.innerHTML='<header><h2>Đối chiếu hóa đơn với bảng kê đã tải</h2><button type="button" class="btn btn-outline" data-close>Đóng</button></header><p role="status">Đang lấy hóa đơn và bảng kê…</p><div data-comparison></div>';
    document.body.appendChild(dialog);dialog.showModal();
    dialog.querySelector('[data-close]').onclick=function(){dialog.close();};
    dialog.addEventListener('close',function(){dialog.remove();});
    try {
      var data=await options.api('/api/outgoing-invoices/source-scopes/'+options.invoiceId+'/comparison');
      if(!dialog.isConnected)return;
      dialog.querySelector('[role=status]').textContent='Hóa đơn '+data.number+' · '+data.buyer+' · '+money(data.invoice_total);
      dialog.querySelector('[data-comparison]').innerHTML=
        '<p>Hóa đơn đã ký không cần xuất lại. Bảng dưới chỉ giúp kiểm tra nguồn; chọn khoảng ngày chưa làm thay đổi đơn hay kho.</p>'+
        ((data.other_buyers||[]).length?'<div class="error-summary"><strong>Có bảng kê của nhà thầu khác khớp toàn bộ mã, lượng, giá, thuế và tổng tiền.</strong><ul>'+data.other_buyers.map(function(c){return '<li>'+esc(c.contractor+' · Ngày đơn '+c.from+' → '+c.to)+' · <a href="/api/outgoing-invoices/export-receipts/'+esc(c.token)+'/file">Tải lại bảng kê để kiểm tra</a></li>';}).join('')+'</ul><p>Phần mềm chưa chuyển hóa đơn sang nhà thầu khác. Nếu giữ hóa đơn cho người mua hiện tại và đã xuất thay mặt hàng, mở Kiểm tra / sửa nguồn đơn rồi đối chiếu theo tiền của đúng nhà thầu.</p></div>':'')+
        '<h3>Bảng kê đã tải của '+esc(data.contractor||'nhà thầu chưa xác định')+'</h3>'+
        '<p>Chỉ liệt kê file cùng nhà thầu trong tháng hóa đơn. Một vài mặt hàng giống nhau chưa đủ để kết luận đã chọn nhầm file.</p>'+
        (data.candidates.length?'<div class="selection-table"><table><thead><tr><th>Bảng kê / ngày đơn</th><th>Tổng tiền</th><th>So với hóa đơn</th><th>Xử lý</th></tr></thead><tbody>'+data.candidates.map(function(c,i){return '<tr><td><a href="/api/outgoing-invoices/export-receipts/'+esc(c.token)+'/file">'+esc(c.filename)+'</a><br>Ngày đơn '+esc(c.from)+' → '+esc(c.to)+'</td><td>'+money(c.total)+'</td><td>'+c.matched_items+'/'+c.invoice_items+' mặt hàng hóa đơn khớp đủ mã, lượng, giá và thuế; bảng kê có '+c.file_items+' mặt hàng.<br>Tiền hóa đơn − bảng kê: '+money(c.difference)+'</td><td><button type="button" class="btn btn-outline" data-period="'+i+'">Chọn khoảng ngày đơn này</button></td></tr>';}).join('')+'</tbody></table></div>':'<p>Chưa tìm được file đã tải có thể đối chiếu trong tháng này. Mở Kiểm tra / sửa nguồn đơn, nhập đúng Từ ngày đơn và Đến ngày đơn. Nếu đã đổi mặt hàng, dùng Đối chiếu theo tiền trong phần đó.</p>')+
        '<button type="button" class="btn btn-primary" data-source-form>Kiểm tra / sửa nguồn đơn</button>'+
        '<details><summary>Mặt hàng trên hóa đơn đã ký · '+data.items.length+' dòng</summary><div class="selection-table"><table><thead><tr><th>Mã / tên hàng</th><th>Số lượng</th><th>ĐVT</th><th>Tiền trước thuế</th></tr></thead><tbody>'+data.items.map(function(r){return '<tr><td>'+esc(r.code+' · '+r.name)+'</td><td>'+esc(r.qty)+'</td><td>'+esc(r.unit)+'</td><td>'+money(r.amount)+'</td></tr>';}).join('')+'</tbody></table></div></details>';
      dialog.querySelector('[data-source-form]').onclick=function(){dialog.close();options.openForm(null,data.token);};
      dialog.querySelectorAll('[data-period]').forEach(function(button){button.onclick=function(){var c=data.candidates[Number(button.dataset.period)];dialog.close();options.openForm(c,data.token);};});
    } catch(error) {if(dialog.isConnected)dialog.querySelector('[role=status]').textContent=error.message+' Đóng và mở lại để thử; phần đã nhập được giữ nguyên.';}
  };
})();
