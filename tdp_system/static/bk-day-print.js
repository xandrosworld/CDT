(function(root){
  'use strict';
  root.TdpBkDayPrint=async function(options){
    var host=document.getElementById(options.hostId),esc=options.esc;if(!host)return;
    var serial=String(Date.now())+Math.random();host.dataset.historySerial=serial;
    function current(){return host.isConnected&&host.dataset.historySerial===serial;}
    host.innerHTML='<p role="status">Đang kiểm tra bảng đã ghi kho của ngày đã chọn…</p>';
    try{
      var data=await options.api('/api/bk-import/history?from='+encodeURIComponent(options.day)+'&to='+encodeURIComponent(options.day));
      if(!current())return;
      var items=(data.items||[]).concat(data.legacy_items||[]),previewId=options.hostId+'-day-preview';
      var seen=new Set();items=items.filter(function(r){if(seen.has(r.id))return false;seen.add(r.id);return true;});
      host.innerHTML='<section class="card"><div class="card-body"><strong>Ngày '+esc(options.day.split('-').reverse().join('/'))+'</strong><p role="status">'+
        (items.length?'Đã có bảng đã ghi kho để in lại. Không cần lập hoặc nhập kho lại các dòng này.':'Chưa có bảng đã ghi kho của ngày này để in lại. Kiểm tra hàng thực mua còn thiếu trước khi lập mới.')+'</p>'+
        (items.length?'<button class="btn btn-primary" data-day-print>Xem / in bảng đã ghi kho</button><details><summary>Chi tiết '+items.length+' bảng đã ghi kho</summary><ul>'+items.map(function(r){return '<li>#'+r.id+' · '+esc(r.filename)+' · '+esc(r.origin_label||'')+' · '+r.row_count+' dòng · '+Number(r.amount_total).toLocaleString('vi-VN')+' đ</li>';}).join('')+'</ul></details>':'')+
        '<p>Cần bổ sung hàng thực mua chưa ghi kho? Kiểm tra hàng còn thiếu rồi lập bổ sung. Có bảng để in lại không có nghĩa đã hết hàng âm; không có hàng âm cũng chưa xác nhận đủ chứng từ mua.</p><button class="btn btn-outline" data-day-create>Kiểm tra hàng còn thiếu / lập bổ sung</button>'+
        '</div></section><div class="bk-history-preview" id="'+previewId+'"></div>';
      host.querySelector('[data-day-create]').onclick=options.onSupplement;
      if(items.length)host.querySelector('[data-day-print]').onclick=async function(){
        var button=this;button.disabled=true;
        try{await root.TDPDocuments.open({kind:'saved-purchases',from:options.day,to:options.day,document_ids:items.map(function(r){return r.id;}),receipts:true,simple_print:true},previewId);
          if(current())document.getElementById(previewId).scrollIntoView({block:'start'});
        }finally{if(current())button.disabled=false;}
      };
    }catch(error){
      if(!current())return;
      host.innerHTML='<p role="alert">'+esc(error.message)+'</p><button class="btn btn-outline" data-day-retry>Thử lại ngày đã chọn</button>';
      host.querySelector('[data-day-retry]').onclick=function(){root.TdpBkDayPrint(options);};
    }
  };
}(window));
