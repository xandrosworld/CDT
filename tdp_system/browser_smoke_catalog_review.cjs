const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const [base, devtools, output, cookiePath] = process.argv.slice(2);
const pause = ms => new Promise(r => setTimeout(r,ms));

async function main() {
  const pages = await fetch(devtools+'/json/list').then(r=>r.json());
  const ws = new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  let id=0; const pending=new Map(); const faults=[]; const mutations=[];
  let uploads=0;
  ws.onmessage=e=>{
    const m=JSON.parse(e.data);
    if(m.method==='Runtime.exceptionThrown')faults.push(m.params.exceptionDetails.text);
    if(m.method==='Network.requestWillBeSent'){
      const r=m.params.request;
      if(r.url.endsWith('/api/catalog/import/preview'))uploads++;
      if(r.url.includes('/api/')&&!['GET','HEAD','OPTIONS'].includes(r.method))mutations.push(new URL(r.url).pathname);
    }
    if(!pending.has(m.id))return;
    const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(new Error(m.error.message)):p.resolve(m.result);
  };
  const call=(method,params={})=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
  const run=async expression=>{
    const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
    if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);
    return r.result.value;
  };
  const wait=async (expression,label)=>{
    for(let i=0;i<200;i++){if(await run(expression))return;await pause(150);}
    throw new Error('Timeout '+label);
  };
  try {
    await call('Page.enable');await call('DOM.enable');await call('Runtime.enable');await call('Network.enable');
    if(cookiePath)await call('Network.setCookies',{cookies:JSON.parse(fs.readFileSync(cookiePath,'utf8'))});
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:base});
    await wait('document.querySelector("[data-view=settings]")','shell');await pause(3000);
    await run('document.querySelector("[data-view=settings]").click()');
    await wait('document.getElementById("catalogImportMode")','settings');
    const doc=await call('DOM.getDocument');
    const node=await call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#catalogWorkbookInput'});
    await call('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[path.join(output,'catalog-review.xlsx')]});
    await wait('document.getElementById("catalogReviewMode")','initial preview');
    assert.equal(uploads,1);
    assert(await run('document.getElementById("catalogImportCounts").textContent.includes("Mã trong sheet")'));
    await run(`document.getElementById('catalogReviewMode').value='names_and_new';document.getElementById('catalogReviewMode').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[data-action="review-catalog-import"]').click()`);
    await wait('document.querySelectorAll("#catalogImportReview .row-error").length===4','four identity errors');
    assert(await run('document.querySelector("[data-action=confirm-catalog-import]").disabled'));
    const expected=['Cau, trầu','Chè cúng','Hoa cúng','Xôi cúng'];
    await run(`Array.from(document.querySelectorAll('.catalog-preview-editor')).forEach((editor,i)=>{
      editor.parentElement.querySelector('[data-action="edit-catalog-preview-row"]').click();
      const name=editor.querySelector('[data-catalog-field="invoice_name"]');name.value=${JSON.stringify(expected)}[i];name.dispatchEvent(new Event('input',{bubbles:true}));
      const unit=editor.querySelector('[data-catalog-field="invoice_unit"]');unit.value=['Lễ','Cốc','Bộ','Đĩa'][i];unit.dispatchEvent(new Event('input',{bubbles:true}));
    })`);
    await call('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
    await run('document.querySelector("[data-action=review-catalog-import]").click()');
    await wait('document.getElementById("catalogReviewStatus").textContent.includes("giữ nguyên")','failed retry message');
    assert.deepEqual(await run(`Array.from(document.querySelectorAll('[data-catalog-field="invoice_name"]')).map(e=>e.value)`),expected);
    await call('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
    await run('document.querySelector("[data-action=review-catalog-import]").click()');
    await wait('!document.querySelector("[data-action=confirm-catalog-import]").disabled','corrected preview');
    assert.equal(uploads,1);
    // Inspect an edited row at two customer desktop sizes.
    for(const width of [1440,1024]){
      await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
      await run('document.querySelector("[data-action=edit-catalog-preview-row]").click()');await pause(400);
      assert(await run('document.activeElement.matches("[data-catalog-field=invoice_name]")'));
      const shot=await call('Page.captureScreenshot',{format:'png'});
      fs.writeFileSync(path.join(output,`catalog-review-${width}.png`),Buffer.from(shot.data,'base64'));
    }
    if(!cookiePath){
      await run('document.querySelector("[data-action=confirm-catalog-import]").click()');
      await wait('!document.getElementById("catalogImportReview")','confirmed');
      const rows=await run('fetch("/api/catalog/worksheet").then(r=>r.json()).then(r=>r.items)');
      assert.deepEqual(rows.map(r=>r.invoice_name),expected);
      assert.deepEqual(rows.map(r=>r.unit),['Lễ','Cốc','Bộ','Đĩa']);
      assert.deepEqual(rows.map(r=>r.invoice_unit),['Lễ','Cốc','Bộ','Đĩa']);
      await wait('document.getElementById("catalogImportResult")','saved summary');
      assert(await run('document.getElementById("catalogImportResult").textContent.includes("Đã thêm 0 mã mới")'));
      const nextDoc=await call('DOM.getDocument');
      const nextInput=await call('DOM.querySelector',{nodeId:nextDoc.root.nodeId,selector:'#catalogWorkbookInput'});
      await call('DOM.setFileInputFiles',{nodeId:nextInput.nodeId,files:[path.join(output,'catalog-counts.xlsx')]});
      await wait('document.getElementById("catalogImportCounts")','counts preview');
      const counts=await run('document.getElementById("catalogImportCounts").textContent');
      assert(counts.includes('thêm 1 mã mới'),counts);
      assert(counts.includes('sẽ là 5'),counts);
      for(const width of [1440,1024]){
        await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
        await run('document.getElementById("catalogImportCounts").scrollIntoView({block:"center"})');await pause(200);
        const shot=await call('Page.captureScreenshot',{format:'png'});
        fs.writeFileSync(path.join(output,`catalog-counts-${width}.png`),Buffer.from(shot.data,'base64'));
      }
      await run('document.querySelector("[data-action=confirm-catalog-import]").click()');
      await wait('!document.getElementById("catalogImportReview") && document.getElementById("catalogImportResult")?.textContent.includes("Đã thêm 1 mã mới")','actual addition');
      await call('Page.reload');
      await wait('document.querySelector("[data-view=settings]")','reloaded shell');await pause(3000);
      await run('document.querySelector("[data-view=settings]").click()');
      await wait('document.getElementById("catalogImportResult")','persisted summary');
      assert(await run('document.getElementById("catalogImportResult").textContent.includes("Đã thêm 1 mã mới")'));
    } else {
      assert(!mutations.includes('/api/catalog/import/confirm'));
      await run('document.querySelector("[data-action=cancel-catalog-import]").click()');
    }
    assert.deepEqual(faults,[]);
    assert(mutations.every(p=>['/api/catalog/import/preview','/api/catalog/import/review','/api/catalog/import/confirm'].includes(p)),JSON.stringify(mutations));
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({ok:true,uploads,mutations,confirmed:!cookiePath}));
    console.log('catalog_review_browser=passed; single_upload; retry_preserves_edits; 1440_and_1024; confirmed='+!cookiePath);
  } catch(error){
    const shot=await call('Page.captureScreenshot',{format:'png'});
    fs.writeFileSync(path.join(output,'failure.png'),Buffer.from(shot.data,'base64'));throw error;
  } finally {ws.close();}
}
main().catch(error=>{console.error(error.stack);process.exitCode=1;});
