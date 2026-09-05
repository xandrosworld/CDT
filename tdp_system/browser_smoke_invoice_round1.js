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
    const scroll=await evaluate(`(()=>{const e=document.querySelector('.invoice-lines-card .invoice-lines-scroll');e.scrollTop=420;e.scrollLeft=250;const h=e.querySelector('th');return {top:h.getBoundingClientRect().top,wrap:e.getBoundingClientRect().top,scroll:e.scrollTop,x:e.scrollLeft,position:getComputedStyle(h).position,color:getComputedStyle(h).color,bg:getComputedStyle(h).backgroundColor};})()`);
    assert.equal(scroll.position,'sticky');assert.ok(scroll.scroll>0 && scroll.x>0);assert.ok(Math.abs(scroll.top-scroll.wrap)<4);assert.notEqual(scroll.color,scroll.bg);
    await change('invoiceFrom','2026-08-02'); await change('invoiceTo','2026-08-02');
    assert.ok(await evaluate(`document.querySelector('#invoice-list-count').textContent.includes('1 / 1')`));
    await change('invoiceFrom','2026-08-01');await change('invoiceTo','2026-08-31');
    await change('invoiceLineFilter','unit_review');
    assert.equal(await evaluate(`document.querySelectorAll('.invoice-lines-card tbody tr[data-issue]').length`),1);
    await change('invoiceLineFilter','all');
    // Invalid mapping stays visible and MUST NOT create any stock movement.
    const mappingId=`map_input_${fixture.line_b}`;
    await evaluate(`document.getElementById('${mappingId}').value='NO-SUCH-CODE'`);
    await click(`[data-action="save-invoice-mapping"][data-id="${fixture.line_b}"]`);
    await wait(`document.querySelector('#toast').textContent.length > 0 && !document.querySelector('[data-action="save-invoice-mapping"][data-id="${fixture.line_b}"]').disabled`);
    assert.equal((await request(`/api/invoice-inventory/source/input/${fixture.input_ids['2']}`)).body.events.length,0);
    // Enter saves mapping; a differing unit still needs an explicit positive factor.
    await evaluate(`document.getElementById('${mappingId}').value='R1-KG';document.getElementById('${mappingId}').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);
    await wait(`!document.getElementById('${mappingId}')`);
    const conv=`conversion_input_${fixture.line_box}`;
    await evaluate(`document.getElementById('${conv}').value='0'`);
    await click(`[data-action="save-invoice-conversion"][data-id="${fixture.line_box}"]`);
    assert.ok(await evaluate(`document.getElementById('${conv}') !== null`));
    await evaluate(`document.getElementById('${conv}').value='12';document.getElementById('${conv}').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);
    await wait(`!document.getElementById('${conv}')`);
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
    await call('Emulation.clearDeviceMetricsOverride');
    assert.deepEqual(errors,[]);
    console.log('PASS: complete range (266 synthetic invoices / 285 rows), filters, global error order, sticky scroll, invalid code, Enter mapping/conversion, confirmation cancel/accept, exact stock trace, duplicate safety, outgoing post, monthly close/reopen/reclose and carryforward quantities/values. Synthetic isolated DB only.');
  } finally {ws.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
