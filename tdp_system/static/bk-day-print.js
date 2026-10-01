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
      var items=data.items||[],previewId=options.hostId+'-day-preview';
      host.innerHTML='<section class="card"><div class="card-body"><strong>Ngày '+esc(options.day.split('-').reverse().join('/'))+'</strong><p>'+
        (items.length?'Bảng kê A4 · Biên nhận A5. In lại không ghi thêm kho.':'Ngày này chưa có bảng đã xác nhận ghi kho để in lại. Nếu chưa lập, bấm Lập bảng kê bổ sung từ tồn âm và kiểm tra hàng thực mua.')+'</p>'+
        (items.length?'<details><summary>Chi tiết các bảng đã lưu của ngày này ('+items.length+')</summary><ul>'+items.map(function(r){return '<li>#'+r.id+' · '+esc(r.filename)+' · '+r.row_count+' dòng · '+Number(r.amount_total).toLocaleString('vi-VN')+' đ</li>';}).join('')+'</ul></details>':'<button class="btn btn-primary" data-day-create>Lập bảng kê bổ sung từ tồn âm</button>')+
        '</div></section><div class="bk-history-preview" id="'+previewId+'"></div>';
      if(!items.length){host.querySelector('[data-day-create]').onclick=options.onSupplement;return;}
      await root.TDPDocuments.open({kind:'saved-purchases',from:options.day,to:options.day,document_ids:items.map(function(r){return r.id;}),receipts:true,simple_print:true},previewId);
      if(current())document.getElementById(previewId).scrollIntoView({block:'start'});
    }catch(error){
      if(!current())return;
      host.innerHTML='<p role="alert">'+esc(error.message)+'</p><button class="btn btn-outline" data-day-retry>Thử lại ngày đã chọn</button>';
      host.querySelector('[data-day-retry]').onclick=function(){root.TdpBkDayPrint(options);};
    }
  };
}(window));
