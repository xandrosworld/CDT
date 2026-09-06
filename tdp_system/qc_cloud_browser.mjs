// Real browser evidence against an authenticated hosted deployment.
// Credentials and screenshots stay in the supplied private directory, outside Git.
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';

const [base, output, credentialFile] = process.argv.slice(2);
if (!base?.startsWith('https://') || !output || !credentialFile) throw Error('Usage: node qc_cloud_browser.mjs HTTPS_URL OUTPUT PRIVATE_CREDENTIAL_JSON');
fs.mkdirSync(output, {recursive:true});
const credentials = JSON.parse(fs.readFileSync(credentialFile,'utf8'));
const profile = fs.mkdtempSync(path.join(os.tmpdir(),'tdp-cloud-browser-'));
const port = 19476;
const chrome = spawn(process.env.TDP_BROWSER_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  ['--headless=new','--disable-gpu','--no-first-run',`--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,'about:blank'],
  {windowsHide:true,stdio:'ignore'});
let ws;
const report={url:base,started_at:new Date().toISOString(),screens:[],checks:[],errors:[],blocked_writes:[],server_errors:[],layouts:[],controls:{}};
const sleep = ms=>new Promise(r=>setTimeout(r,ms));
try {
  let pages;
  for(let i=0;i<100;i++) {try{pages=await fetch(`http://127.0.0.1:${port}/json/list`).then(r=>r.json());break;}catch{await sleep(100);}}
  ws=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
  let seq=0;const pending=new Map();
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown') report.errors.push(m.params.exceptionDetails.text);
    if(m.method==='Network.responseReceived' && m.params.response.status>=500) report.server_errors.push({url:m.params.response.url,status:m.params.response.status});
    if(m.method==='Fetch.requestPaused') {
      const {requestId,request}=m.params;
      const route=new URL(request.url).pathname;
      const allowed=['GET','HEAD','OPTIONS'].includes(request.method) ||
        (request.method==='POST' && ['/api/documents/preview','/logout'].includes(route));
      if(!allowed) report.blocked_writes.push({method:request.method,route});
      call(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId}:{requestId,errorReason:'BlockedByClient'}).catch(error=>report.errors.push(error.message));
    }
    if(pending.has(m.id)){const [r,j]=pending.get(m.id);pending.delete(m.id);m.error?j(Error(m.error.message)):r(m.result);}};
  const call=(method,params={})=>new Promise((r,j)=>{const id=++seq;pending.set(id,[r,j]);ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value;};
  const wait=async expression=>{for(let i=0;i<200;i++){if(await evaluate(expression))return;await sleep(150);}throw Error('Browser wait failed: '+expression);};
  const click=async selector=>{await wait(`document.querySelector(${JSON.stringify(selector)})`);await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});e.click();})()`);};
  const shot=async name=>{await evaluate('window.scrollTo(0,0)');await sleep(350);const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join(output,name+'.png'),Buffer.from(r.data,'base64'));report.screens.push(name+'.png');};
  const api=async(route,body)=>evaluate(`fetch(${JSON.stringify(route)},${JSON.stringify(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})}).then(async r=>({status:r.status,data:await r.json()}))`);
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1680,height:1050,deviceScaleFactor:1,mobile:false});
  await call('Page.addScriptToEvaluateOnNewDocument',{source:`localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'}));`});
  await call('Page.navigate',{url:base});await wait('document.getElementById("username")');
  assert.equal((await api('/api/bootstrap')).status,401);report.checks.push('anonymous_data_blocked');
  await shot('01-login');
  await evaluate(`document.getElementById('username').value=${JSON.stringify(credentials.username)};document.getElementById('password').value=${JSON.stringify(credentials.password)};document.querySelector('button[type="submit"]').click()`);
  await wait('document.querySelector("#nav") && !document.querySelector(".loading-panel")');
  report.checks.push('browser_login_success');
  const boot=await api('/api/bootstrap');assert.equal(boot.status,200);
  // Protocol interception also protects forms, XHR and Request objects, not just fetch options.
  await call('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});
  // This hosted smoke is read-only. Block any accidental edit before it reaches production.
  await evaluate(`window.__qaWrites=[];window.__qaFetch=fetch;window.fetch=(...args)=>{if(['PUT','PATCH','DELETE'].includes(args[1]?.method)){window.__qaWrites.push(String(args[0]));return Promise.resolve(new Response(JSON.stringify({ok:false,error:'Hosted read-only check blocked an edit'}),{status:409,headers:{'Content-Type':'application/json'}}));}return window.__qaFetch(...args);}`);
  for(const [index,view] of ['home','orders','purchases','physical','quotes','reports','debts','documents','inventory','msmi','printing','settings'].entries()){
    await click(`[data-view="${view}"]`);await sleep(1100);await wait('!document.querySelector(".loading-panel")');
    if(view==='msmi')await wait('document.querySelector("#invoice-list-count")');
    await shot(String(index+2).padStart(2,'0')+'-'+view);
    report.controls[view]=await evaluate(`Array.from(document.querySelectorAll('#content button,#content input,#content select,#content a')).filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,id:e.id,action:e.dataset.action||'',label:(e.textContent||e.getAttribute('aria-label')||e.getAttribute('placeholder')||e.name||'').trim().slice(0,120),disabled:e.disabled||false}))`);
    for(const width of [1680,1366,1024]) {
      await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
      await sleep(180);
      const layout=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,offenders:Array.from(document.querySelectorAll('#content *')).filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>innerWidth+2&&!e.closest('.table-scroll,.table-wrap,.inventory-nxt-scroll,.invoice-table-scroll,.document-preview-scroll');}).slice(0,8).map(e=>({tag:e.tagName,class:e.className,id:e.id}))})`);
      report.layouts.push({view,...layout,ok:layout.scrollWidth<=width+2});
      if(width!==1680) await shot(view+'-'+width);
    }
    await call('Emulation.setDeviceMetricsOverride',{width:1680,height:1050,deviceScaleFactor:1,mobile:false});
    report.checks.push('navigation_'+view);
    if(view==='printing') {
      assert.equal(await evaluate(`!!document.querySelector('[data-action="run-print"],#printSettingsForm')`),false,'Hosted printing must use browser PDF, not server Windows printers');
      assert.ok(await evaluate(`!!document.querySelector('[data-action="print-selected-documents"]')`));
      report.checks.push('hosted_print_controls');
    }
    if(view==='settings') {
      assert.ok(await evaluate(`document.querySelector('#content').textContent.includes('kể cả khi đã đóng trình duyệt')`));
      report.checks.push('hosted_backup_instructions');
    }
    if(view==='debts') {
      for(const section of ['receivable-kitchen','receivable-total','payable']) {
        await click('[data-section="'+section+'"]');
        await sleep(1200);await wait(`!document.querySelector('.loading-panel,.loading-inline')`);
        await shot('debts-'+section);
        assert.equal(await evaluate(`!!document.querySelector('.error-summary')`),false,'Debt workspace '+section);
        report.checks.push('debt_workspace_'+section);
        await click('[data-action="back-debt-overview"]');
      }
    }
    if(view==='orders') {
      await click('[data-action="bulk-edit-orders"]');
      await wait(`document.querySelector('.tdp-sheet-status')?.textContent.match(/Đã tải|Chỉ xem/)`);
      await wait(`document.querySelector('canvas[id^="univer-sheet-main"]')?.width>1000`);
      await shot('worksheet-orders');
      await click('.tdp-sheet-close'); await wait(`!document.querySelector('.tdp-sheet-shell')`);
      report.checks.push('hosted_order_worksheet_read_only_smoke');
    }
    if(view==='inventory') {
      await wait(`document.querySelector('[data-action="view-inventory-worksheet"]')`);
      for(const width of [1680,1366,1024]) {
        await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
        const layout=await evaluate(`(()=>{const box=document.querySelector('.inventory-nxt-scroll');box.scrollIntoView({block:'center'});box.scrollTop=box.scrollHeight/2;box.scrollLeft=0;const footer=box.querySelector('tfoot');return {height:footer.getBoundingClientRect().height,viewport:box.clientHeight,sticky:getComputedStyle(footer.querySelector('td')).position,money:Array.from(footer.querySelectorAll('.num-cell')).every(cell=>getComputedStyle(cell).whiteSpace==='nowrap')};})()`);
        assert.ok(layout.height<=64 && layout.viewport-layout.height>200,JSON.stringify(layout));
        assert.equal(layout.sticky,'sticky');assert.equal(layout.money,true);
        const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
        const filename='inventory-fixed-total-'+width+'.png';fs.writeFileSync(path.join(output,filename),Buffer.from(r.data,'base64'));report.screens.push(filename);
      }
      await click('[data-action="view-inventory-unit-totals"]');
      await wait(`document.querySelector('.inventory-totals-dialog[open] tbody tr')`);
      report.inventory_unit_rows=await evaluate(`document.querySelectorAll('.inventory-totals-dialog tbody tr').length`);
      await shot('inventory-unit-totals');
      await click('.inventory-totals-dialog button');
      await call('Emulation.setDeviceMetricsOverride',{width:1680,height:1050,deviceScaleFactor:1,mobile:false});
      await click('[data-action="view-inventory-worksheet"]');
      await wait(`document.querySelector('.tdp-sheet-status')?.textContent==='Chỉ xem'`);
      await shot('worksheet-inventory');
      await click('.tdp-sheet-close'); await wait(`!document.querySelector('.tdp-sheet-shell')`);
      report.checks.push('hosted_inventory_worksheet');
      report.checks.push('inventory_compact_sticky_total','inventory_quantities_by_unit');
    }
  }
  const invoices=await api('/api/invoice-workbench/invoices?invoice_type=input&from=2026-08-01&to=2026-08-31&status=all&line_filter=all');
  assert.equal(invoices.status,200);assert.equal(invoices.data.totals.invoice_count,266);
  report.input_totals=invoices.data.totals;report.input_counts=invoices.data.counts;
  report.checks.push('august_266_input_invoices');
  for(const [name,route] of Object.entries({output:'/api/invoice-workbench/invoices?invoice_type=output&from=2026-08-01&to=2026-08-31',backup:'/api/backup/status',inventory:'/api/invoice-valuation?from=2026-08-01&to=2026-08-31',msmi:'/api/msmi/status',minvoice:'/api/minvoice/status'})){
    const r=await api(route);report[name]={status:r.status,ok:r.data.ok,error:r.data.error,totals:r.data.totals,counts:r.data.counts,item_count:r.data.items?.length};
    if(name==='backup')report.backup={status:r.status,...r.data};
    assert.equal(r.status,200,route);
  }
  const chosen=boot.data.batches.flatMap(b=>(b.delivery_notes||[]).map(n=>({batch_id:b.id,kitchen:n.code})))[0];
  if(chosen){
    const preview=await api('/api/documents/preview',{kind:'deliveries',selections:[chosen]});
    report.delivery_preview={status:preview.status,sheet_count:preview.data.sheet_count,error:preview.data.error};
    assert.equal(preview.status,200);assert.ok(preview.data.sheet_count>0);
    for(const ext of ['excel','pdf']){
      const route='/api/documents/'+preview.data.token+'/'+ext+'?sheets=0';
      const file=await evaluate(`fetch(${JSON.stringify(route)}).then(async r=>{const b=new Uint8Array(await r.arrayBuffer());let s='';for(const v of b)s+=String.fromCharCode(v);return {status:r.status,body:btoa(s),type:r.headers.get('content-type')};})`);
      report['delivery_'+ext]={status:file.status,type:file.type,bytes:Buffer.from(file.body,'base64').length};
      fs.writeFileSync(path.join(output,'delivery.'+(ext==='excel'?'xlsx':'pdf')),Buffer.from(file.body,'base64'));
      assert.equal(file.status,200,ext+' download');
    }
  }
  for(const width of [1024,1366]) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    await sleep(300);
    assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+2'), 'Page overflows at '+width);
    if(width===1024) assert.ok(await evaluate('document.querySelector(".sidebar").getBoundingClientRect().width>=document.documentElement.clientWidth-2'), 'Desktop menu must span the page');
    await shot('responsive-'+width);
  }
  await call('Emulation.setDeviceMetricsOverride',{width:1680,height:1050,deviceScaleFactor:1,mobile:false});
  await click('[data-view="documents"]');
  assert.ok(await evaluate('document.querySelector("#paymentRequestForm input[name=from]") && document.querySelector("#paymentRequestForm input[name=to]")'));
  await evaluate(`(()=>{const select=document.querySelector('#paymentRequestForm select[name=contractor]');select.selectedIndex=1;select.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await wait('document.querySelector("#buyerProfileForm input[name=tax_code]")');
  report.checks.push('buyer_profile_editor_without_creating_invoice');
  report.checks.push('independent_payment_period','desktop_horizontal_menu','desktop_1024_1366_1680');
  assert.deepEqual(await evaluate('window.__qaWrites'),[],'Opening/closing views must not request edits');
  assert.deepEqual(report.blocked_writes,[],'Read-only navigation must not request business writes');
  assert.deepEqual(report.server_errors,[],'No server errors during hosted navigation');
  assert.ok(report.layouts.every(item=>item.ok),'One or more screens overflow; inspect layouts in report');
  report.checks.push('no_edit_requests_from_read_only_views');
  const logout=await evaluate('fetch("/logout",{method:"POST"}).then(r=>({status:r.status,url:r.url}))');
  assert.equal(logout.status,200); assert.ok(logout.url.endsWith('/login'));
  assert.equal((await api('/api/bootstrap')).status,401);
  report.checks.push('logout_blocks_data_again');
  assert.deepEqual(report.errors,[]);
  report.ok=true;
}catch(error){report.ok=false;report.failure=error.message;process.exitCode=1;}
finally{
  fs.writeFileSync(path.join(output,'browser-result.json'),JSON.stringify(report,null,2));
  ws?.close();chrome.kill();
  console.log(JSON.stringify({ok:report.ok,screens:report.screens.length,checks:report.checks.length,failure:report.failure,report:path.join(output,'browser-result.json')}));
}
