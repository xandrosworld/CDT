/* Load the Excel engine on demand; the main workspace must not wait for it. */
(function () {
  'use strict';
  var loading=null, active=null, engine=null, loadSequence=0;
  function load() {
    if(engine)return Promise.resolve(engine);
    if(loading)return loading.promise;
    var request={};loading=request;
    request.promise=new Promise(function(resolve,reject){
      var script=document.createElement('script');script.src='/static/worksheet-bundle/worksheet.js?v=20260909-2200';
      // Do not let the browser reuse the same in-flight request after a timeout.
      if(++loadSequence>1)script.src+='&retry='+Date.now()+'-'+loadSequence;
      var settled=false;
      function finish(error){
        if(settled)return;
        settled=true;clearTimeout(timer);
        if(loading===request)loading=null;
        if(error){script.remove();reject(error);}else resolve(engine);
      }
      var timer=setTimeout(function(){
        finish(new Error('Tải bảng Excel quá 30 giây. Bấm Thử lại để tải lại, hoặc Hủy để quay về.'));
      },30000);
      request.cancel=function(){finish(new Error('Đã hủy mở bảng Excel.'));};
      script.onload=function(){
        // A removed script may finish late. Restore the facade even then, but
        // never reopen a cancelled dialog or settle a newer load request.
        var candidate=window.TDPWorksheet;window.TDPWorksheet=facade;
        if(candidate!==facade && typeof candidate?.open==='function' && typeof candidate?.isOpen==='function')engine=engine||candidate;
        finish(engine ? null : new Error('Chưa mở được bảng Excel. Bấm Thử lại để tải lại.'));
      };
      script.onerror=function(){finish(new Error('Chưa tải được bảng Excel. Kiểm tra kết nối rồi bấm Thử lại.'));};
      document.head.append(script);
    });
    return request.promise;
  }
  var facade={
    isOpen:function(){return !!active || !!engine?.isOpen();},
    open:function(options){
      if(active)return active.promise;
      var dialog=document.createElement('dialog');dialog.className='worksheet-loading-dialog inventory-totals-dialog';
      dialog.setAttribute('aria-label','Mở bảng Excel');
      dialog.innerHTML='<p role="status">Đang mở bảng Excel…</p><div class="compact-controls"><button type="button" class="btn btn-outline worksheet-load-cancel">Hủy</button><button type="button" class="btn btn-primary worksheet-load-retry" hidden>Thử lại</button></div>';
      var resolve, job={cancelled:false,busy:false,promise:new Promise(function(done){resolve=done;})};active=job;
      function dismiss(){dialog.close();dialog.remove();if(active===job)active=null;}
      function cancel(){job.cancelled=true;if(loading)loading.cancel();dismiss();resolve(null);}
      function showError(error){
        if(job.cancelled)return;
        job.busy=false;dialog.querySelector('p').textContent=error.message||'Chưa mở được bảng Excel.';
        dialog.querySelector('.worksheet-load-retry').hidden=false;
      }
      function attempt(){
        if(job.busy || job.cancelled)return;
        job.busy=true;
        dialog.querySelector('p').textContent='Đang mở bảng Excel…';dialog.querySelector('.worksheet-load-retry').hidden=true;
        load().then(async function(engine){
          if(job.cancelled)return;
          dismiss();
          try{await engine.open(options);resolve(true);}catch(error){
            // Keep errors visible even at callers which do not await open().
            if(job.cancelled)return;
            showError(error);
            document.body.append(dialog);dialog.showModal();active=job;
          }
        },showError);
      }
      dialog.querySelector('.worksheet-load-cancel').onclick=cancel;
      dialog.querySelector('.worksheet-load-retry').onclick=attempt;
      dialog.addEventListener('cancel',function(event){event.preventDefault();cancel();});
      document.body.append(dialog);dialog.showModal();attempt();return job.promise;
    }
  };
  window.TDPWorksheet=facade;
})();
