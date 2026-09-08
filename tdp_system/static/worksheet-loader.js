/* Load the Excel engine on demand; the main workspace must not wait for it. */
(function () {
  'use strict';
  var loading=null, active=null, engine=null;
  function load() {
    if(engine)return Promise.resolve(engine);
    if(loading)return loading;
    loading=new Promise(function(resolve,reject){
      var script=document.createElement('script');script.src='/static/worksheet-bundle/worksheet.js?v=20260908-2';
      script.onload=function(){
        if(window.TDPWorksheet!==facade){engine=window.TDPWorksheet;window.TDPWorksheet=facade;resolve(engine);}
        else {loading=null;script.remove();reject(new Error('Chưa mở được bảng Excel. Chị thử lại giúp em.'));}
      };
      script.onerror=function(){loading=null;script.remove();reject(new Error('Chưa tải được bảng Excel. Kiểm tra kết nối rồi bấm Thử lại.'));};
      document.head.append(script);
    });
    return loading;
  }
  var facade={
    isOpen:function(){return !!active || !!engine?.isOpen();},
    open:function(options){
      if(active)return active.promise;
      var dialog=document.createElement('dialog');dialog.className='worksheet-loading-dialog inventory-totals-dialog';
      dialog.setAttribute('aria-label','Mở bảng Excel');
      dialog.innerHTML='<p role="status">Đang mở bảng Excel…</p><div class="compact-controls"><button type="button" class="btn btn-outline worksheet-load-cancel">Hủy</button><button type="button" class="btn btn-primary worksheet-load-retry" hidden>Thử lại</button></div>';
      var resolve, job={cancelled:false,promise:new Promise(function(done){resolve=done;})};active=job;
      function dismiss(){dialog.close();dialog.remove();if(active===job)active=null;}
      function cancel(){job.cancelled=true;dismiss();resolve(null);}
      function attempt(){
        dialog.querySelector('p').textContent='Đang mở bảng Excel…';dialog.querySelector('.worksheet-load-retry').hidden=true;
        load().then(async function(engine){
          if(job.cancelled)return;
          dismiss();
          try{await engine.open(options);resolve(true);}catch(error){
            // Keep errors visible even at callers which do not await open().
            dialog.querySelector('p').textContent=error.message||'Chưa mở được bảng Excel.';
            document.body.append(dialog);dialog.showModal();active=job;
          }
        },function(error){
          if(job.cancelled)return;
          dialog.querySelector('p').textContent=error.message;dialog.querySelector('.worksheet-load-retry').hidden=false;
        });
      }
      dialog.querySelector('.worksheet-load-cancel').onclick=cancel;
      dialog.querySelector('.worksheet-load-retry').onclick=attempt;
      dialog.addEventListener('cancel',function(event){event.preventDefault();cancel();});
      document.body.append(dialog);dialog.showModal();attempt();return job.promise;
    }
  };
  window.TDPWorksheet=facade;
})();
