/* Load the Excel engine on demand; the main workspace must not wait for it. */
(function () {
  'use strict';
  var loading=null, active=null, engine=null, loadSequence=0;
  function load(progress) {
    if(engine)return Promise.resolve(engine);
    if(loading)return loading.promise;
    var request={};loading=request;
    request.promise=new Promise(function(resolve,reject){
      var script=document.createElement('script'), controller=new AbortController();
      var settled=false, blobUrl=null, timer=null, sequence=++loadSequence;
      var assetCache=null,assetKey=null,downloadedBlob=null;
      function finish(error){
        if(settled)return;
        settled=true;clearTimeout(timer);
        if(loading===request)loading=null;
        if(blobUrl)URL.revokeObjectURL(blobUrl);
        if(error){controller.abort();script.remove();reject(error);}else resolve(engine);
      }
      function heartbeat(){
        clearTimeout(timer);
        timer=setTimeout(function(){finish(new Error('Tải bảng Excel bị gián đoạn. Bấm Thử lại để tải lại, hoặc Hủy để quay về.'));},45000);
      }
      heartbeat();
      request.cancel=function(){finish(new Error('Đã hủy mở bảng Excel.'));};
      script.onload=function(){
        // Network bytes cannot execute after cancellation. Restore the facade
        // if cancellation happened just as the local script was evaluated.
        var candidate=window.TDPWorksheet;window.TDPWorksheet=facade;
        if(candidate!==facade && typeof candidate?.open==='function' && typeof candidate?.isOpen==='function')engine=engine||candidate;
        // Cache code only, after successful evaluation. Never cache API data or
        // depend on session-cookie changes for reuse of identical code bytes.
        if(engine && !settled && assetCache && downloadedBlob){
          assetCache.put(assetKey,new Response(downloadedBlob,{headers:{'Content-Type':'text/javascript'}})).catch(function(){});
        }
        finish(engine ? null : new Error('Chưa mở được bảng Excel. Bấm Thử lại để tải lại.'));
      };
      script.onerror=function(){finish(new Error('Chưa tải được bảng Excel. Kiểm tra kết nối rồi bấm Thử lại.'));};
      (async function(){
        try{
          var manifest=await fetch('/static/worksheet-bundle/manifest.json',{signal:controller.signal,cache:'no-store'});
          if(!manifest.ok)throw new Error('Chưa tải được bảng Excel. Bấm Thử lại.');
          var meta=await manifest.json();
          if(!/^worksheet-[a-f0-9]{16}\.js$/.test(meta.script) || !Number.isFinite(meta.bytes) || meta.bytes<=0)throw new Error('Chưa tải được bảng Excel. Tải lại trang rồi thử lại.');
          heartbeat();
          var url='/static/worksheet-bundle/'+meta.script;assetKey=url;
          var response=null;
          try{assetCache=await caches.open('tdp-worksheet-code-v1');if(sequence===1)response=await assetCache.match(assetKey);}catch(ignore){}
          if(sequence>1)url+='?retry='+Date.now()+'-'+sequence;
          if(!response)response=await fetch(url,{signal:controller.signal});
          if(!response.ok || !/javascript/.test(response.headers.get('Content-Type')||''))throw new Error('Chưa tải được bảng Excel. Tải lại trang rồi thử lại.');
          var chunks=[],received=0,reader=response.body.getReader();
          while(true){
            var part=await reader.read();if(part.done)break;
            if(settled)return;
            chunks.push(part.value);received+=part.value.length;heartbeat();
            progress('Đang tải bảng Excel… '+Math.min(99,Math.floor(received/Number(meta.bytes)*100))+'%');
          }
          if(settled)return;
          if(!received)throw new Error('Chưa tải được bảng Excel. Bấm Thử lại.');
          progress('Đang mở bảng Excel…');heartbeat();
          downloadedBlob=new Blob(chunks,{type:'text/javascript'});
          blobUrl=URL.createObjectURL(downloadedBlob);
          script.src=blobUrl;document.head.append(script);
        }catch(error){finish(new Error(error instanceof TypeError ? 'Chưa tải được bảng Excel. Kiểm tra kết nối rồi bấm Thử lại.' : error.message));}
      })();
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
        load(function(message){if(!job.cancelled)dialog.querySelector('p').textContent=message;}).then(async function(engine){
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
