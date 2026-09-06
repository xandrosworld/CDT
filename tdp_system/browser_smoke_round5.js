'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs');
async function main() {
  const page = await fetch('http://127.0.0.1:19318/json/new?about:blank', {method:'PUT'}).then(r => r.json());
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((yes,no) => { socket.onopen=yes; socket.onerror=no; });
  let sequence=0; const pending=new Map(), errors=[];
  socket.onmessage=e=>{const m=JSON.parse(e.data); if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);
    if(pending.has(m.id)){const [yes,no]=pending.get(m.id);pending.delete(m.id);m.error?no(Error(m.error.message)):yes(m.result);}};
  const call=(method,params={})=>new Promise((yes,no)=>{const id=++sequence;pending.set(id,[yes,no]);socket.send(JSON.stringify({id,method,params}));});
  const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  const wait=async expression=>{const end=Date.now()+40000;while(Date.now()<end){if(await ev(expression))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timeout: '+expression);};
  const click=async selector=>{await wait(`document.querySelector(${JSON.stringify(selector)})`);await ev(`document.querySelector(${JSON.stringify(selector)}).click()`);};
  try {
    await call('Runtime.enable'); await call('Page.enable');
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:'http://127.0.0.1:18808'});
    await wait(`document.querySelector('.daily-action-grid')`);
    assert.deepEqual(await ev(`Array.from(document.querySelectorAll('#nav [data-view]')).filter(e=>['deliveries','kitchen','payroll'].includes(e.dataset.view)).map(e=>e.dataset.view)`),[]);
    assert.ok(await ev(`document.querySelector('#nav [data-view="physical"]')!==null`));
    await click('[data-view="deliveries"]');
    await wait(`document.querySelector('#deliveryDocumentPreview .document-sheet')`);
    assert.match(await ev(`document.querySelector('.document-sheet').textContent`),/Chả cá loại ngon/);
    await click('#nav [data-view="printing"]');
    await wait(`document.querySelectorAll('.print-batch-select').length===2`);
    const result=await ev(`fetch('/api/operations/bootstrap?active_only=1&as_of=2026-09-05').then(r=>r.json())`);
    assert.deepEqual(result.meal_plans,[]);assert.deepEqual(result.payroll,[]);
    await click('#nav [data-view="settings"]');
    await wait(`document.querySelector('#automaticBackupStatus')?.textContent.includes('đã được kiểm tra an toàn')`);
    assert.equal(await ev(`document.querySelector('#automaticBackupStatus').getAttribute('role')`),'status');
    assert.equal(await ev(`document.querySelector('a[href="/api/backup"]')!==null`),true);
    fs.writeFileSync('D:/TDP_ROUND5/settings-browser.png', Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    // Inject only a GET response, never damage the DB, to verify an actionable warning.
    await ev(`window.__fetch=window.fetch;window.fetch=(...args)=>String(args[0]).includes('/api/backup/status')?Promise.resolve(new Response(JSON.stringify({ok:true,last_success:'2026-09-05T10:00:00',error:'Chưa sao lưu được. Kiểm tra dung lượng ổ đĩa.'}),{headers:{'Content-Type':'application/json'}})):window.__fetch(...args)`);
    await click('#nav [data-view="home"]');await click('#nav [data-view="settings"]');
    await wait(`document.querySelector('#automaticBackupStatus')?.getAttribute('role')==='alert'`);
    assert.match(await ev(`document.querySelector('#automaticBackupStatus').textContent`),/Kiểm tra dung lượng/);
    await ev(`window.fetch=window.__fetch`);
    await click('#nav [data-view="home"]');
    await ev(`document.querySelector('#content').insertAdjacentHTML('beforeend','<div id="acceptancePreview"></div>'); window.TDPDocuments.open({kind:'purchases',selections:[{batch_id:1}]},'acceptancePreview')`);
    await wait(`document.querySelector('#acceptancePreview .document-sheet')`);
    assert.match(await ev(`document.querySelector('#acceptancePreview [role="alert"]').textContent`),/Không lập bảng kê\/biên nhận cho 10 dòng/);
    assert.doesNotMatch(await ev(`document.querySelector('#acceptancePreview .document-scroll').textContent`),/Đoàn Văn Giang|Nguyễn Văn Toại/);
    assert.match(await ev(`document.querySelector('#acceptancePreview .document-scroll').textContent`),/Thái Bình/);
    assert.equal(await ev(`performance.getEntriesByType('resource').filter(r=>r.name.includes('/excel?')||r.name.includes('/pdf?')).length`),0);
    for(const width of [1440,1024]){
      await call('Emulation.setDeviceMetricsOverride',{width,height:950,deviceScaleFactor:1,mobile:false});
      assert.equal(await ev(`document.documentElement.scrollWidth>innerWidth`),false);
    }
    // Emulate only the hosted capability in a disposable fixture; verify the desktop web flow.
    await call('Page.addScriptToEvaluateOnNewDocument',{source:`const originalFetch=window.fetch;window.fetch=async(...args)=>{const response=await originalFetch(...args);if(new URL(String(args[0]),location.href).pathname==='/api/bootstrap'){const data=await response.json();data.hosted=true;return new Response(JSON.stringify(data),{status:response.status,headers:{'Content-Type':'application/json'}});}return response;};`});
    await call('Page.reload',{ignoreCache:true});
    await wait(`document.querySelector('#nav [data-view="printing"]') && !document.querySelector('.loading-panel')`);
    await click('#nav [data-view="printing"]');
    await wait(`document.querySelector('[data-action="print-selected-documents"]')`);
    assert.equal(await ev(`!!document.querySelector('[data-action="run-print"],#printSettingsForm')`),false);
    assert.match(await ev(`document.querySelector('#content').textContent`),/hộp thoại in của trình duyệt/);
    await click('#nav [data-view="settings"]');
    assert.match(await ev(`document.querySelector('#content').textContent`),/kể cả khi đã đóng trình duyệt/);
    assert.doesNotMatch(await ev(`document.querySelector('#content').textContent`),/Máy thứ hai cùng mạng Wi-Fi/);
    fs.writeFileSync('D:/TDP_ROUND5/hosted-settings-browser.png', Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.deepEqual(errors,[]);
    console.log('Round 5 browser PASS: compact menu, delivery still reachable, legacy calculations absent, backup success/error, mixed receipts warning, no automatic export, 1440/1024.');
  } finally {socket.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
