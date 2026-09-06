"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");

async function main() {
  const pages = await fetch("http://127.0.0.1:19311/json/list").then(r => r.json());
  const ws = new WebSocket(pages.find(p => p.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  let seq=0; const pending=new Map(), errors=[];
  ws.onmessage = event => {
    const message=JSON.parse(event.data);
    if(message.method==='Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
    if(pending.has(message.id)){const [resolve,reject]=pending.get(message.id);pending.delete(message.id);message.error?reject(Error(message.error.message)):resolve(message.result);}
  };
  const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,[resolve,reject]);ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;};
  const wait=async expression=>{const deadline=Date.now()+20000;while(Date.now()<deadline){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timeout: '+expression);};
  const click=async selector=>{await wait(`document.querySelector(${JSON.stringify(selector)})`);await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);};
  const change=async(id,value)=>{await wait(`document.getElementById(${JSON.stringify(id)})`);await evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await wait(`document.querySelector('#invoice-list-count')`);};
  const request=async (path,method='GET',body)=>evaluate(`fetch(${JSON.stringify(path)}, {method:${JSON.stringify(method)},headers:{'Content-Type':'application/json'},${body?`body:JSON.stringify(${JSON.stringify(body)}),`:''}}).then(async r=>({status:r.status,body:await r.json()}))`);
  try {
    await call('Page.enable'); await call('Runtime.enable');
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await call('Page.addScriptToEvaluateOnNewDocument',{source:`localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'}));window.confirm=()=>true;`});
    await call('Page.navigate',{url:'http://127.0.0.1:18801'});
    await wait(`document.querySelector('[data-view="msmi"]') && !document.querySelector('.loading-panel')`);
    await click('[data-view="msmi"]');
    await wait(`document.querySelector('#invoice-list-count')?.textContent.includes('3 / 3')`);
    const fixture=(await request('/fixture/ids')).body;
    const initial=(await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body;
    assert.equal(initial.totals.line_count,22);
    assert.ok(await evaluate('innerWidth === 1440 && document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1'));
    const order=await evaluate(`Array.from(document.querySelectorAll('.invoice-lines-card tbody tr')).map(e=>e.dataset.issue)`);
    assert.equal(order.filter(x=>x==='1').length,21);
    assert.equal(order.at(-1),'0');
    await click('[data-action="jump-invoice-issue"]');
    assert.ok(await evaluate(`document.activeElement.classList.contains('invoice-mapping-input')`));
    // Scroll both axes, then prove header sticks and text/background contrast is readable.
    await call('Emulation.setDeviceMetricsOverride',{width:1024,height:700,deviceScaleFactor:1,mobile:false});
    const scroll=await evaluate(`(()=>{const e=document.querySelector('.invoice-lines-card .invoice-lines-scroll');e.scrollTop=420;e.scrollLeft=250;const h=e.querySelector('th');return {top:h.getBoundingClientRect().top,wrap:e.getBoundingClientRect().top,scroll:e.scrollTop,x:e.scrollLeft,position:getComputedStyle(h).position,color:getComputedStyle(h).color,bg:getComputedStyle(h).backgroundColor};})()`);
    assert.equal(scroll.position,'sticky');assert.ok(scroll.scroll>0 && scroll.x>0);assert.ok(Math.abs(scroll.top-scroll.wrap)<4);assert.notEqual(scroll.color,scroll.bg);
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await change('invoiceFrom','2026-08-02'); await change('invoiceTo','2026-08-02');
    assert.ok(await evaluate(`document.querySelector('#invoice-list-count').textContent.includes('1 / 1')`));
    await change('invoiceFrom','2026-08-01');await change('invoiceTo','2026-08-31');
    await change('invoiceLineFilter','unit_review');
    assert.equal(await evaluate(`document.querySelectorAll('.invoice-lines-card tbody tr[data-issue]').length`),1);
    await change('invoiceLineFilter','all');
    // Invalid mapping stays visible and MUST NOT create any stock movement.
    const mappingId=`map_input_${fixture.line_b}`;
    await click('.invoice-lines-card .tdp-open-sheet');
    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar')`);
    assert.equal(await evaluate(`!!document.querySelector('.tdp-sheet-shell')`),false);
    await evaluate(`document.getElementById('${mappingId}').focus();document.getElementById('${mappingId}').select()`);
    await call('Input.insertText',{text:'NO-SUCH-CODE'});
    await click('.invoice-mapping-fullscreen-bar button');
    assert.equal(await evaluate(`document.getElementById('${mappingId}').value`),'NO-SUCH-CODE');
    await click('.invoice-lines-card .tdp-open-sheet');
    await click(`[data-action="save-invoice-mapping"][data-id="${fixture.line_b}"]`);
    await wait(`document.querySelector('#toast').textContent.length > 0 && !document.querySelector('[data-action="save-invoice-mapping"][data-id="${fixture.line_b}"]').disabled`);
    assert.equal((await request(`/api/invoice-inventory/source/input/${fixture.input_ids['2']}`)).body.events.length,0);
    // Enter saves mapping; a differing unit still needs an explicit positive factor.
    await evaluate(`document.getElementById('${mappingId}').value='R1-KG';document.getElementById('${mappingId}').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);
    await wait(`!document.getElementById('${mappingId}')`);
    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar')`);
    assert.ok(await evaluate(`document.querySelector('#content').classList.contains('invoice-mapping-fullscreen')`));
    for(const width of [1440,1024]) {
      await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
      assert.ok(await evaluate(`(()=>{const r=document.querySelector('.invoice-lines-card').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;})()`));
    }
    const mappingPicture=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    fs.writeFileSync('D:/TDP_ROUND1/mapping-fullscreen-browser.png',Buffer.from(mappingPicture.data,'base64'));
    const conv=`conversion_input_${fixture.line_box}`;
    await evaluate(`document.getElementById('${conv}').value='0'`);
    await click(`[data-action="save-invoice-conversion"][data-id="${fixture.line_box}"]`);
    assert.ok(await evaluate(`document.getElementById('${conv}') !== null`));
    await evaluate(`document.getElementById('${conv}').value='12';document.getElementById('${conv}').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);
    await wait(`!document.getElementById('${conv}')`);
    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar')`);
    await click('.invoice-mapping-fullscreen-bar button');
    assert.equal(await evaluate(`document.body.style.overflow`),'');
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await change('invoiceStatus','ready');
    await wait(`document.querySelector('[data-action="create-msmi-receipt"][data-id="${fixture.input_ids['2']}"]')`);
    // Cancelling confirmation must leave zero stock entries.
    await evaluate('window.confirm=()=>false');
    await click(`[data-action="create-msmi-receipt"][data-id="${fixture.input_ids['2']}"]`);
    assert.equal((await request(`/api/invoice-inventory/source/input/${fixture.input_ids['2']}`)).body.events.length,0);
    await evaluate('window.confirm=()=>true');
    await click(`[data-action="create-msmi-receipt"][data-id="${fixture.input_ids['2']}"]`);
    await wait(`document.querySelector('#invoice-list-count')?.textContent.includes('0 / 3')`);
    await change('invoiceStatus','posted');
    await click(`[data-action="view-invoice-stock"][data-id="${fixture.input_ids['2']}"]`);
    await wait(`document.querySelector('#invoice-stock-trace tbody tr')`);
    assert.equal(await evaluate(`document.querySelectorAll('#invoice-stock-trace tbody tr').length`),2);
    assert.ok(await evaluate(`document.querySelector('#invoice-stock-trace').textContent.includes('24') && document.querySelector('#invoice-stock-trace').textContent.includes('R1-CAI')`));
    assert.equal(await evaluate(`document.getElementById('inventoryFrom').value`),'2026-08-01');
    assert.equal(await evaluate(`document.getElementById('inventoryTo').value`),'2026-08-31');
    const trace=(await request(`/api/invoice-inventory/source/input/${fixture.input_ids['2']}`)).body;
    assert.deepEqual(trace.events.map(x=>x.qty_delta),[1,24]);
    const duplicate=await request(`/api/msmi/invoices/${fixture.input_ids['2']}/receipt`,'POST',{});
    assert.equal(duplicate.status,200);
    assert.equal((await request(`/api/invoice-inventory/source/input/${fixture.input_ids['2']}`)).body.events.length,2);
    await click('[data-action="back-invoice-workbench"]');
    await change('invoiceStatus','all');
    await click('[data-action="set-invoice-direction"][data-direction="output"]');
    await wait(`document.getElementById('map_output_${fixture.output_line}')`);
    await evaluate(`document.getElementById('map_output_${fixture.output_line}').value='R1-KG'`);
    await click(`[data-action="save-invoice-mapping"][data-direction="output"][data-id="${fixture.output_line}"]`);
    await wait(`document.querySelector('[data-action="post-invoice-output"]')`);
    await click('[data-action="post-invoice-output"]');
    await wait(`document.querySelector('[data-action="view-invoice-stock"][data-direction="output"]')`);
    await click('[data-action="view-invoice-stock"][data-direction="output"]');
    await wait(`document.querySelector('#invoice-stock-trace')?.textContent.includes('Xuất kho')`);
    assert.equal((await request(`/api/invoice-inventory/source/output/${fixture.output_id}`)).body.events[0].qty_delta,-1);
    const before=(await request('/api/invoice-valuation?from=2026-08-01&to=2026-08-31')).body.items;
    assert.equal(before.find(x=>x.product_code==='R1-KG').closing_qty,1);
    assert.equal(before.find(x=>x.product_code==='R1-CAI').closing_qty,24);
    assert.ok(await evaluate(`document.querySelector('.inventory-month-close').textContent.includes('chưa ghi kho')`));
    await click('[data-action="close-inventory-month"]');
    assert.ok(await evaluate(`document.querySelector('[data-action="close-inventory-month"]') !== null`));
    await evaluate(`document.getElementById('inventoryCloseActor').value='Người kiểm thử lượt 1'`);
    await click('[data-action="close-inventory-month"]');
    await wait(`document.querySelector('[data-action="reopen-inventory-month"]')`);
    let september=(await request('/api/invoice-valuation?from=2026-09-01&to=2026-09-30')).body.items;
    for(const code of ['R1-KG','R1-CAI']){
      const aug=before.find(x=>x.product_code===code),sep=september.find(x=>x.product_code===code);
      assert.equal(sep.opening_qty,aug.closing_qty);assert.equal(sep.opening_value,aug.closing_value);
    }
    await click('[data-action="reopen-inventory-month"]');
    await wait(`document.querySelector('[data-action="close-inventory-month"]')`);
    await click('[data-action="close-inventory-month"]');
    await wait(`document.querySelector('[data-action="reopen-inventory-month"]')`);
    assert.deepEqual((await request('/api/invoice-valuation?from=2026-09-01&to=2026-09-30')).body.items,september);
    const history=(await request('/api/inventory/month-close/preview?period=2026-08')).body.history;
    assert.deepEqual(history.map(x=>x.action),['close','reopen','close']);
    assert.ok(history.every(x=>x.actor==='Người kiểm thử lượt 1'));
    await evaluate(`window.scrollTo(0,0);Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{})))`);
    const picture=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    fs.writeFileSync('D:/TDP_ROUND1/stock-trace-browser.png',Buffer.from(picture.data,'base64'));
    await click('[data-action="back-invoice-workbench"]');
    await click('[data-action="set-invoice-direction"][data-direction="input"]');
    await wait(`document.querySelector('#invoice-list-count')?.textContent.includes('3 / 3')`);
    assert.equal((await request('/fixture/scale-up','POST',{})).status,200);
    await change('invoiceStatus','all');
    await wait(`document.querySelector('#invoice-list-count')?.textContent.includes('266 / 266')`);
    assert.equal(await evaluate(`document.querySelectorAll('.invoice-lines-card tbody tr[data-issue]').length`),285);
    await evaluate('window.scrollTo(0,0);Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{})))');
    const picture2=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    fs.writeFileSync('D:/TDP_ROUND1/invoice-table-browser.png',Buffer.from(picture2.data,'base64'));
    await call('Emulation.setDeviceMetricsOverride',{width:1024,height:900,deviceScaleFactor:1,mobile:false});
    assert.ok(await evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1'));
    assert.ok(await evaluate("(()=>{const box=document.querySelector('.invoice-lines-card .invoice-lines-scroll');return box.scrollWidth > box.clientWidth;})()"));
    await click('.invoice-lines-card .tdp-open-sheet');
    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar')`);
    const mappingLayouts=[];
    for(const [width,height] of [[1920,900],[1440,800],[1280,640],[1024,560]]) {
      await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
      for(const fraction of [0,0.5,1]) {
        const geometry=await evaluate(`(()=>{const box=document.querySelector('.invoice-lines-card > .invoice-lines-scroll');box.scrollTop=box.scrollHeight*${fraction};box.scrollLeft=box.scrollWidth*${fraction};const r=box.getBoundingClientRect();const head=box.querySelector('thead').getBoundingClientRect();const foot=box.querySelector('tfoot').getBoundingClientRect();const action=box.querySelector('thead th:last-child').getBoundingClientRect();return {width:innerWidth,height:innerHeight,tableHeight:r.height,bodySpace:r.height-head.height-foot.height,footerHeight:foot.height,actionRight:action.right,boxRight:r.right,overflow:document.documentElement.scrollWidth>innerWidth+1};})()`);
        assert.ok(geometry.tableHeight>=height*0.70,JSON.stringify(geometry));
        assert.ok(geometry.bodySpace>=height*0.50,JSON.stringify(geometry));
        assert.ok(geometry.footerHeight<=52,JSON.stringify(geometry));
        assert.ok(geometry.actionRight<=width && geometry.boxRight-geometry.actionRight<22,JSON.stringify(geometry));
        assert.equal(geometry.overflow,false); mappingLayouts.push(geometry);
      }
      await evaluate(`document.querySelector('.invoice-lines-card > .invoice-lines-scroll').scrollTop=0;document.querySelector('.invoice-lines-card > .invoice-lines-scroll').scrollLeft=0;document.getElementById('toast').classList.remove('show')`);
      fs.writeFileSync('D:/TDP_ROUND1/mapping-layout-'+width+'.png',Buffer.from((await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})).data,'base64'));
    }
    const totalGroups=(await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body.totals.qty_by_unit;
    await click('[data-action="view-invoice-unit-totals"]');
    assert.equal(await evaluate(`document.querySelectorAll('.invoice-unit-totals-dialog tbody tr').length`),Object.keys(totalGroups).length);
    assert.equal(await evaluate(`document.querySelector('.invoice-unit-totals-dialog tbody').textContent.includes('kg')`),true);
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await wait(`!document.querySelector('.invoice-unit-totals-dialog')`);
    assert.ok(await evaluate(`document.querySelector('.invoice-mapping-fullscreen-bar') !== null`));
    await click('.invoice-workbench-help > summary');
    assert.ok(await evaluate(`document.querySelector('.invoice-workbench-help').open`));
    await click('.invoice-workbench-help > summary');
    await click('.invoice-mapping-fullscreen-bar button');
    fs.writeFileSync('D:/TDP_ROUND1/mapping-layout.json',JSON.stringify(mappingLayouts,null,2));
    // One click performs exact mapping; no human confirmation for a proven match.
    const autoFixture = (await request('/fixture/automatic-mapping','POST',{})).body;
    await change('invoiceStatus','all');
    await wait(`document.getElementById('map_input_${autoFixture.item_id}')`);
    await evaluate(`window.__autoConfirms=0;window.confirm=()=>{window.__autoConfirms++;return false;}`);
    await click('[data-action="apply-msmi-safe-suggestions"]');
    await wait(`!document.getElementById('map_input_${autoFixture.item_id}') && !document.querySelector('[data-action="apply-msmi-safe-suggestions"]').disabled`);
    assert.equal(await evaluate('window.__autoConfirms'),0);
    const autoListing = (await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body;
    const ranks = autoListing.lines.map(row=>row.action_rank);
    assert.deepEqual(ranks,[...ranks].sort());
    assert.equal(autoListing.lines.find(row=>row.id===autoFixture.item_id).mapping_status,'mapped');
    const displayed = await evaluate(`Array.from(document.querySelectorAll('.invoice-lines-card tbody tr[data-issue]')).map(row=>Number(row.id.replace('invoice-line-input-','')))`);
    assert.deepEqual(displayed,autoListing.lines.map(row=>row.id));
    assert.equal(await evaluate(`document.getElementById('invoice-line-input-${autoFixture.item_id}').dataset.issue`),'0');
    await click('[data-action="apply-msmi-safe-suggestions"]');
    await wait(`!document.querySelector('[data-action="apply-msmi-safe-suggestions"]').disabled`);
    assert.equal(await evaluate('window.__autoConfirms'),0);
    fs.writeFileSync('D:/TDP_ROUND1/automatic-mapping-browser.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    // Many units used to turn the sticky total into a panel covering the rows.
    // Replace only this GET response in the isolated browser, leaving the DB intact.
    await evaluate(`(()=>{const original=window.fetch;window.fetch=async function(input,init){const response=await original(input,init);if(String(input).startsWith('/api/invoice-valuation?')){const data=await response.json();data.items=Array.from({length:240},(_,i)=>({product_code:'LAYOUT-'+i,product_name:'Long inventory item '+i,unit:'unit '+(i%24),opening_qty:1000.855,input_qty:2,output_qty:1,closing_qty:1001.855,opening_value:10000000,input_value:20000,output_value:10000,closing_value:10010000,average_unit_cost:10000,valuation_status:'ok'}));return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});}return response;};})()`);
    await click('[data-view="inventory"]');
    await wait(`document.getElementById('inventoryFrom')`);
    await evaluate(`document.getElementById('inventoryFrom').value='2026-08-02';document.getElementById('inventoryFrom').dispatchEvent(new Event('change',{bubbles:true}))`);
    await wait(`document.querySelector('.inventory-nxt-scroll tbody')?.textContent.includes('LAYOUT-239')`);
    for(const width of [1680,1366,1024]) {
      await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
      for(const fraction of [0.5,1]) {
        const geometry=await evaluate(`(()=>{const box=document.querySelector('.inventory-nxt-scroll');box.scrollIntoView({block:'center'});box.scrollTop=box.scrollHeight*${fraction};box.scrollLeft=${fraction===1?'box.scrollWidth':'0'};const cell=box.querySelector('tfoot td');const rect=cell.getBoundingClientRect();return {height:rect.height,visible:box.clientHeight-rect.height,sticky:getComputedStyle(cell).position,bottom:rect.bottom,boxBottom:box.getBoundingClientRect().top+box.clientHeight,overflow:document.documentElement.scrollWidth>innerWidth+1};})()`);
        assert.ok(geometry.height<=64,JSON.stringify(geometry));assert.ok(geometry.visible>200);assert.equal(geometry.sticky,'sticky');assert.ok(Math.abs(geometry.bottom-geometry.boxBottom)<4);assert.equal(geometry.overflow,false);
      }
      await evaluate(`document.querySelector('.inventory-nxt-scroll').scrollLeft=0`);
      const image=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      fs.writeFileSync('D:/TDP_ROUND1/inventory-fixed-total-'+width+'.png',Buffer.from(image.data,'base64'));
    }
    await click('[data-action="view-inventory-unit-totals"]');
    assert.equal(await evaluate(`document.querySelectorAll('.inventory-totals-dialog tbody tr').length`),24);
    assert.ok(await evaluate(`getComputedStyle(document.querySelector('.inventory-totals-dialog thead th')).color==='rgb(23, 43, 58)' && getComputedStyle(document.querySelector('.inventory-totals-dialog tbody th')).position==='static'`));
    assert.ok(await evaluate(`Array.from(document.querySelectorAll('.inventory-totals-dialog tbody tr')).every(row=>row.cells[1].textContent==='10.008,55' && row.cells[2].textContent==='20' && row.cells[3].textContent==='10' && row.cells[4].textContent==='10.018,55')`));
    await click('.inventory-totals-dialog button');
    await click('[data-action="view-inventory-worksheet"]');
    await wait(`document.querySelector('.tdp-sheet-status')?.textContent==='Ch\u1ec9 xem'`);
    await call('Emulation.clearDeviceMetricsOverride');
    assert.deepEqual(errors,[]);
    console.log('PASS: complete range (266 synthetic invoices / 285 rows), filters, global error order, sticky scroll, invalid code, Enter mapping/conversion, confirmation cancel/accept, exact stock trace, duplicate safety, outgoing post, monthly close/reopen/reclose and carryforward quantities/values. Synthetic isolated DB only.');
  } finally {ws.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
