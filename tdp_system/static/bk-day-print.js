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
        ((data.legacy_items||[]).length?'Có '+data.legacy_items.length+' bảng từ duyệt đơn cũ đã ghi kho. Đây không phải bảng bổ sung chị vừa lập. ':'')+
        ((data.items||[]).length?'Có '+data.items.length+' bảng bổ sung / nhập Excel đã xác nhận ghi kho.':'Chưa có bảng bổ sung / nhập Excel đã xác nhận cho ngày này.')+'</p>'+
        (items.length?'<button class="btn btn-primary" data-day-print>Xem / in bảng đã ghi kho</button><details><summary>Chi tiết '+items.length+' bảng đã ghi kho</summary><ul>'+items.map(function(r){return '<li>#'+r.id+' · '+esc(r.filename)+' · '+esc(r.origin_label||'')+' · '+r.row_count+' dòng · '+Number(r.amount_total).toLocaleString('vi-VN')+' đ</li>';}).join('')+'</ul></details>':'')+
        '<div data-day-stock role="status">Đang kiểm tra hàng còn thiếu đến hết ngày đã chọn…</div><p>Không nhập lại các dòng đã ghi kho. Chỉ lập bổ sung khi đối chiếu có hàng thực mua chưa ghi nhận; không lấy số âm làm chứng từ mua.</p><button class="btn btn-outline" data-day-create>Kiểm tra hàng còn thiếu / lập bổ sung</button>'+
        '</div></section><div class="bk-history-preview" id="'+previewId+'"></div>';
      host.querySelector('[data-day-create]').onclick=options.onSupplement;
      async function checkStock(){
        var box=host.querySelector('[data-day-stock]');
        box.textContent='Đang kiểm tra hàng còn thiếu đến hết ngày đã chọn…';
        try{
          var stock=await options.api('/api/bk-import/shortages?'+new URLSearchParams({from:options.day,to:options.day,tax:'KKKNT'}));
          if(!current())return;
          var count=(stock.items||[]).length;
          box.textContent=count?'Còn '+count+' mã hàng nhóm KKKNT thiếu đến hết ngày '+options.day.split('-').reverse().join('/')+'. Các bảng đã ghi kho chưa giải quyết hết số thiếu này. Bấm Kiểm tra hàng còn thiếu / lập bổ sung để đối chiếu.':'Không còn mã hàng nhóm KKKNT thiếu đến hết ngày '+options.day.split('-').reverse().join('/')+'. Chưa có gợi ý bổ sung từ tồn âm; vẫn cần đối chiếu chứng từ mua thực tế.';
        }catch(error){if(current()){box.innerHTML='<p>Chưa kiểm tra được hàng còn thiếu: '+esc(error.message)+'. Chưa thể kết luận đã hết âm.</p><button class="btn btn-outline" data-day-stock-retry>Kiểm tra lại hàng còn thiếu</button>';box.querySelector('button').onclick=checkStock;}}
      }
      checkStock();
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
