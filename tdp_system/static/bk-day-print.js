(function(root){
  'use strict';
  root.TdpBkDayPrint=async function(options){
    var host=document.getElementById(options.hostId),esc=options.esc;if(!host)return;
    var serial=String(Date.now())+Math.random();host.dataset.historySerial=serial;
    function current(){return host.isConnected&&host.dataset.historySerial===serial;}
    host.innerHTML='<p role="status">Đang mở bảng kê và biên nhận của ngày đã chọn…</p>';
    try{
      var data=await options.api('/api/bk-import/history?from='+encodeURIComponent(options.day)+'&to='+encodeURIComponent(options.day));
      if(!current())return;
      var items=data.items||[],legacy=data.legacy_items||[],previewId=options.hostId+'-day-preview';
      host.innerHTML='<section class="card"><div class="card-body"><strong>Ngày '+esc(options.day.split('-').reverse().join('/'))+'</strong><p>'+
        (items.length?'Đã xác nhận bảng bổ sung / nhập Excel. Bảng kê A4 · Biên nhận A5. In lại không ghi thêm kho.':'Ngày này chưa có bảng bổ sung / nhập Excel đã xác nhận. Bấm Lập bảng kê bổ sung từ tồn âm để kiểm tra phần hàng thực mua còn thiếu.')+'</p>'+
        (items.length?'<details><summary>Chi tiết các bảng đã lưu của ngày này ('+items.length+')</summary><ul>'+items.map(function(r){return '<li>#'+r.id+' · '+esc(r.filename)+' · '+r.row_count+' dòng · '+Number(r.amount_total).toLocaleString('vi-VN')+' đ</li>';}).join('')+'</ul></details>':'<button class="btn btn-primary" data-day-create>Lập bảng kê bổ sung từ tồn âm</button>')+
        (items.length?'<button class="btn btn-outline" data-day-create>Lập bảng kê bổ sung từ tồn âm</button>':'')+
        (legacy.length?'<details data-day-legacy><summary>Dữ liệu cũ từ duyệt đơn ('+legacy.length+' bảng) — không phải bảng bổ sung vừa lập</summary><p>Các bảng này đã ghi kho theo quy trình duyệt đơn trước đây. Không có nghĩa chị đã lập bảng bổ sung cho ngày này. Không nhập lại các dòng đã ghi kho; khi lập bổ sung, kiểm tra phần còn thiếu theo tồn kho hiện tại.</p><button class="btn btn-outline" data-day-legacy-print>Xem lại bảng cũ từ duyệt đơn</button></details>':'')+
        '</div></section><div class="bk-history-preview" id="'+previewId+'"></div>';
      host.querySelector('[data-day-create]').onclick=options.onSupplement;
      if(legacy.length)host.querySelector('[data-day-legacy-print]').onclick=async function(){
        await root.TDPDocuments.open({kind:'saved-purchases',from:options.day,to:options.day,document_ids:legacy.map(function(r){return r.id;}),receipts:true,simple_print:true},previewId);
      };
      if(!items.length)return;
      await root.TDPDocuments.open({kind:'saved-purchases',from:options.day,to:options.day,document_ids:items.map(function(r){return r.id;}),receipts:true,simple_print:true},previewId);
      if(current())document.getElementById(previewId).scrollIntoView({block:'start'});
    }catch(error){
      if(!current())return;
      host.innerHTML='<p role="alert">'+esc(error.message)+'</p><button class="btn btn-outline" data-day-retry>Thử lại ngày đã chọn</button>';
      host.querySelector('[data-day-retry]').onclick=function(){root.TdpBkDayPrint(options);};
    }
  };
}(window));
