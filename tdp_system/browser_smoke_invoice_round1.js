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
    const checkPrices=async (direction,payload)=>{
      assert.equal(await evaluate(`document.querySelector('.invoice-lines-card thead th:nth-child(7)').textContent`),'Đơn giá');
      for(const line of payload.lines) {
        const cell=await evaluate(`(()=>{const cell=document.querySelector('#invoice-line-${direction}-${line.id} .invoice-unit-price');return {text:cell.textContent,editable:!!cell.querySelector('input,select,textarea,[contenteditable=true]'),align:getComputedStyle(cell).textAlign};})()`);
        assert.equal(Number(cell.text.replace(/[^0-9-]/g,'')),Math.sign(line.unit_price)*Math.floor(Math.abs(line.unit_price)+0.5));
        assert.equal(cell.editable,false);assert.equal(cell.align,'right');
      }
    };
    await checkPrices('input',initial);
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
    await checkPrices('input',(await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body);
    assert.equal(await evaluate(`!!document.querySelector('.tdp-sheet-shell')`),false);
    const ambiguous = initial.lines.find(line=>line.id===fixture.line_b);
    assert.deepEqual(ambiguous.candidate_products.map(p=>p.code).sort(),['R1-ALT-A','R1-ALT-B']);
    assert.equal(await evaluate(`document.getElementById('${mappingId}').tagName`),'INPUT');
    assert.equal(await evaluate(`document.getElementById('${mappingId}').value`),'');
    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar .tdp-table-search')`);
    await evaluate(`document.getElementById('${mappingId}').value='MA-CHUA-LUU';document.getElementById('${mappingId}').focus()`);
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'f',code:'KeyF',windowsVirtualKeyCode:70,modifiers:2});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'f',code:'KeyF',windowsVirtualKeyCode:70,modifiers:2});
    await wait(`document.activeElement===document.querySelector('.tdp-table-search input')`);
    await call('Input.insertText',{text:'ma-chua-luu'});
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',windowsVirtualKeyCode:13});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',windowsVirtualKeyCode:13});
    await wait(`document.querySelector('.tdp-search-result').textContent==='1 / 1 ô khớp'`);
    assert.ok(await evaluate(`document.querySelector('.tdp-search-hit').contains(document.getElementById('${mappingId}'))`));
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',windowsVirtualKeyCode:27});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',windowsVirtualKeyCode:27});
    assert.ok(await evaluate(`!!document.querySelector('.invoice-mapping-fullscreen-bar')`));
    assert.equal(await evaluate(`document.getElementById('${mappingId}').value`),'MA-CHUA-LUU');
    assert.deepEqual((await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body.lines,initial.lines,'Finding unsaved mapping must not save it');
    await evaluate(`document.getElementById('${mappingId}').focus();document.getElementById('${mappingId}').select()`);
    await call('Input.insertText',{text:'Hàng kiểm thử kg'});
    await wait(`!!document.querySelector('#msmiProductOptions [data-product-code="R1-KG"]')`);
    // Choose the visible suggestions using real keyboard events.
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
    assert.equal(await evaluate(`document.getElementById('${mappingId}').value`),'R1-KG');
    for(const width of [1440,1024]) {
      await call('Emulation.setDeviceMetricsOverride',{width,height:800,deviceScaleFactor:1,mobile:false});
      await evaluate(`(()=>{const e=document.getElementById('${mappingId}');e.scrollIntoView({block:'center',inline:'center'});e.focus();e.select();})()`);
      await call('Input.insertText',{text:'Hàng kiểm thử kg'});
      await wait(`!!document.querySelector('#msmiProductOptions [data-product-code="R1-KG"]')`);
      assert.ok(await evaluate(`(()=>{const e=document.getElementById('msmiProductOptions');const r=e.getBoundingClientRect();return !e.hidden && r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;})()`));
      const searchPicture=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
      fs.writeFileSync('D:/TDP_ROUND1/catalog-search-'+width+'.png',Buffer.from(searchPicture.data,'base64'));
      const point=await evaluate(`(()=>{const r=document.querySelector('#msmiProductOptions [data-product-code="R1-KG"]').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);
      await call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});
      await call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});
      assert.equal(await evaluate(`document.getElementById('${mappingId}').value`),'R1-KG');
      assert.equal(await evaluate(`document.getElementById('msmiProductOptions').hidden`),true);
    }
    await evaluate(`document.getElementById('${mappingId}').select()`);
    await call('Input.insertText',{text:'NO-SUCH-PRODUCT-XYZ-987654321'});
    await wait(`!document.getElementById('msmiProductOptions').hidden && document.getElementById('msmiProductOptions').textContent.includes('Không tìm thấy')`);
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    assert.equal(await evaluate(`document.getElementById('msmiProductOptions').hidden`),true);
    assert.ok(await evaluate(`!!document.querySelector('.invoice-mapping-fullscreen-bar')`));
    assert.equal((await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body.lines.find(line=>line.id===fixture.line_b).product_code,'');
    await evaluate(`document.getElementById('${mappingId}').focus();document.getElementById('${mappingId}').select()`);
    await call('Input.insertText',{text:'NO-SUCH-CODE'});
    await click('.invoice-mapping-fullscreen-bar > button');
    assert.equal(await evaluate(`document.getElementById('${mappingId}').value`),'NO-SUCH-CODE');
    await click('.invoice-lines-card .tdp-open-sheet');
    await click(`[data-action="save-invoice-mapping"][data-id="${fixture.line_b}"]`);
    await wait(`document.querySelector('#toast').textContent.length > 0 && !document.querySelector('[data-action="save-invoice-mapping"][data-id="${fixture.line_b}"]').disabled`);
    assert.equal((await request(`/api/invoice-inventory/source/input/${fixture.input_ids['2']}`)).body.events.length,0);
    // Search by code outside the exact-name candidates, then Enter saves it.
    await evaluate(`document.getElementById('${mappingId}').focus();document.getElementById('${mappingId}').select()`);
    await call('Input.insertText',{text:'R1-KG'});
    await wait(`!!document.querySelector('#msmiProductOptions [data-product-code="R1-KG"]')`);
    // A differing unit still needs an explicit positive factor.
    await change('invoiceLineFilter','unmapped');
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
    // Saved rows remain reachable even when the previous filter excluded them.
    assert.ok(await evaluate(`!!document.querySelector('#invoice-line-input-${fixture.line_b} [data-action="edit-invoice-mapping"]')`));
    assert.ok(await evaluate(`!document.querySelector('#invoice-line-input-${fixture.line_b} .invoice-mapping-cell .invoice-group-select').disabled`));
    await change('invoiceLineFilter','unit_review');
    assert.ok(await evaluate(`document.querySelector('#invoice-line-input-${fixture.line_box} .invoice-mapping-cell .invoice-group-select').disabled`));
    assert.ok(await evaluate(`document.querySelector('#invoice-line-input-${fixture.line_box} .invoice-group-hint').textContent.includes('Lưu quy đổi')`));
    await click(`[data-action="edit-invoice-mapping"][data-id="${fixture.line_box}"]`);
    await evaluate(`document.getElementById('map_input_${fixture.line_box}').value='R1-KG'`);
    await click(`[data-action="cancel-invoice-mapping-edit"][data-id="${fixture.line_box}"]`);
    assert.equal((await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body.lines.find(r=>r.id===fixture.line_box).product_code,'R1-CAI');
    // Correct a wrong code, with the next conversion field focused in-place.
    await click(`[data-action="edit-invoice-mapping"][data-id="${fixture.line_box}"]`);
    await evaluate(`document.getElementById('map_input_${fixture.line_box}').value='R1-KG'`);
    await click(`[data-action="save-invoice-mapping"][data-id="${fixture.line_box}"]`);
    await wait(`document.activeElement?.id === 'conversion_input_${fixture.line_box}'`);
    await click(`[data-action="edit-invoice-mapping"][data-id="${fixture.line_box}"]`);
    await evaluate(`document.getElementById('map_input_${fixture.line_box}').value='R1-CAI'`);
    await click(`[data-action="save-invoice-mapping"][data-id="${fixture.line_box}"]`);
    await wait(`document.activeElement?.id === 'conversion_input_${fixture.line_box}'`);
    fs.writeFileSync('D:/TDP_ROUND1/correct-mapping-conversion.png',Buffer.from((await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})).data,'base64'));
    const conv=`conversion_input_${fixture.line_box}`;
    await evaluate(`document.getElementById('${conv}').value='0'`);
    await click(`[data-action="save-invoice-conversion"][data-id="${fixture.line_box}"]`);
    assert.ok(await evaluate(`document.getElementById('${conv}') !== null`));
    await evaluate(`document.getElementById('${conv}').value='12';document.getElementById('${conv}').dispatchEvent(new Event('input',{bubbles:true}))`);
    assert.ok(await evaluate(`document.getElementById('${conv}').closest('td').querySelector('.invoice-conversion-preview').textContent.includes('24 cái')`));
    await evaluate(`document.getElementById('${conv}').value='12';document.getElementById('${conv}').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))`);
    await wait(`!document.getElementById('${conv}')`);
    await wait(`document.activeElement?.dataset.action === 'edit-invoice-mapping'`);
    await click(`[data-action="edit-invoice-conversion"][data-id="${fixture.line_box}"]`);
    assert.equal(await evaluate(`document.getElementById('${conv}').value`),'12');
    await click(`[data-action="create-msmi-receipt"][data-id="${fixture.input_ids['2']}"]`);
    assert.equal(await evaluate(`!!document.querySelector('.receipt-review-dialog[open]')`),false);
    assert.ok(await evaluate(`document.querySelector('#toast').textContent.includes('Lưu hoặc Bỏ sửa')`));

    await evaluate(`document.getElementById('${conv}').value='30'`);
    await click(`[data-action="cancel-invoice-mapping-edit"][data-id="${fixture.line_box}"]`);
    assert.equal((await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body.lines.find(r=>r.id===fixture.line_box).conversion_factor,12);
    await click(`[data-action="edit-invoice-conversion"][data-id="${fixture.line_box}"]`);
    await evaluate(`document.getElementById('${conv}').value='30'`);
    await click(`[data-action="save-invoice-conversion"][data-id="${fixture.line_box}"]`);
    await wait(`!document.getElementById('${conv}')`);
    assert.equal((await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).body.lines.find(r=>r.id===fixture.line_box).stock_qty,60);
    await click(`[data-action="edit-invoice-conversion"][data-id="${fixture.line_box}"]`);
    await evaluate(`document.getElementById('${conv}').value='12'`);
    await click(`[data-action="save-invoice-conversion"][data-id="${fixture.line_box}"]`);
    await wait(`!document.getElementById('${conv}')`);

    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar')`);
    await click('.invoice-mapping-fullscreen-bar > button');
    assert.equal(await evaluate(`document.body.style.overflow`),'');
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await change('invoiceStatus','ready');
    await wait(`document.querySelector('[data-action="create-msmi-receipt"][data-id="${fixture.input_ids['2']}"]')`);
    // Cancelling confirmation must leave zero stock entries.
    await click(`[data-action="create-msmi-receipt"][data-id="${fixture.input_ids['2']}"]`);
    await wait(`document.querySelector('.receipt-cancel')`);
    await click('.receipt-cancel');
    assert.equal((await request(`/api/invoice-inventory/source/input/${fixture.input_ids['2']}`)).body.events.length,0);
    await evaluate('window.confirm=()=>true');
    await click(`[data-action="create-msmi-receipt"][data-id="${fixture.input_ids['2']}"]`);
    await wait(`document.querySelector('.receipt-confirm:not([disabled])')`);
    await click('.receipt-confirm');
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
    await checkPrices('output',(await request('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31&invoice_type=output')).body);
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
    await click('.invoice-mapping-fullscreen-bar > button');
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
    // Paid and free source rows stay separate; saved mappings produce one receipt total.
    await evaluate(`window.confirm=()=>true`);
    await click('[data-view="inventory"]');
    await wait(`document.querySelector('[data-action="reopen-inventory-month"]')`);
    await evaluate(`document.getElementById('inventoryCloseActor').value='Người kiểm thử lượt 1'`);
    await click('[data-action="reopen-inventory-month"]');
    await wait(`document.querySelector('[data-action="close-inventory-month"]')`);
    const promoResponse=await request('/fixture/promotion','POST',{});
    assert.equal(promoResponse.status,200);
    const promo=promoResponse.body;
    await click('[data-view="msmi"]');
    await change('invoiceFrom','2026-08-28');await change('invoiceTo','2026-08-28');
    await wait(`document.getElementById('map_input_${promo.promotion_lines['QA-OIL-PAID']}')`);
    await click('.invoice-lines-card .tdp-open-sheet');
    for(const [code,id] of Object.entries(promo.promotion_lines)) {
      const product=code.includes('OIL')?'QA-OIL':'QA-CHILI';
      await evaluate(`document.getElementById('map_input_${id}').value=${JSON.stringify(product)}`);
      await click(`[data-action="save-invoice-mapping"][data-id="${id}"]`);
      await wait(`!document.getElementById('map_input_${id}')`);
    }
    const promoPayload=(await request('/api/invoice-workbench/invoices?from=2026-08-28&to=2026-08-28')).body;
    assert.ok(await evaluate(`document.querySelector('#invoice-line-input-${promo.promotion_lines['QA-OIL-FREE']} .invoice-grouped-quantity').textContent.includes('30 Can')`));

    for(const line of promoPayload.lines.filter(r=>r.invoice_id===promo.promotion_invoice)) {
      const cells=await evaluate(`(()=>{const row=document.getElementById('invoice-line-input-${line.id}');return [row.querySelector('.invoice-source-qty').textContent,row.querySelector('.invoice-source-unit').textContent];})()`);
      assert.deepEqual(cells,[String(line.qty),'Can']);
    }
    await evaluate(`window.__groupOriginalFetch=window.fetch;window.fetch=async (...args)=>{const response=await window.__groupOriginalFetch(...args);if(String(args[0]).startsWith('/api/invoice-workbench/invoices?'))await new Promise(r=>setTimeout(r,450));return response;}`);
    await change('invoiceLineFilter','mapped');
    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar') && document.querySelectorAll('.invoice-group-select:not(:disabled)').length===4`);
    await change('invoiceLineFilter','all');
    await wait(`document.querySelector('.invoice-mapping-fullscreen-bar') && document.querySelectorAll('.invoice-group-select:not(:disabled)').length===4`);
    await evaluate(`window.fetch=window.__groupOriginalFetch`);
    const oilPair=[promo.promotion_lines['QA-OIL-PAID'],promo.promotion_lines['QA-OIL-FREE']];
    for(const id of oilPair)await click(`.invoice-group-select[data-id="${id}"]`);
    await click('[data-action="preview-invoice-group"]');
    await wait(`document.querySelector('.invoice-group-dialog[open]')`);
    const groupText=await evaluate(`document.querySelector('.invoice-group-dialog').textContent`);
    assert.ok(groupText.includes('30 Can')&&groupText.includes('1,288,889')&&groupText.includes('42,963'));
    await click('.group-cancel');
    assert.equal((await request('/api/invoice-workbench/invoices?from=2026-08-28&to=2026-08-28')).body.lines.filter(r=>r.group_id).length,0);
    await click('[data-action="preview-invoice-group"]');
    await wait(`document.querySelector('.group-confirm')`);
    await click('.group-confirm');
    await wait(`document.querySelector('[data-action="split-invoice-group"]')`);
    let groupedPayload=(await request('/api/invoice-workbench/invoices?from=2026-08-28&to=2026-08-28')).body;
    let oilGroup=groupedPayload.lines.find(r=>r.group_id);
    assert.equal(oilGroup.qty,30);assert.equal(oilGroup.amount,1288889);assert.equal(oilGroup.group_members.length,2);
    assert.equal(groupedPayload.lines.filter(r=>r.product_code==='QA-OIL').length,1);
    assert.equal(await evaluate(`document.querySelector('#invoice-line-input-${oilGroup.id} .invoice-source-qty').textContent`),'30');
    await click(`[data-action="split-invoice-group"][data-id="${oilGroup.group_id}"]`);
    await wait(`document.querySelectorAll('.invoice-group-select:not(:disabled)').length===4`);
    for(const id of oilPair)await click(`.invoice-group-select[data-id="${id}"]`);
    await click('[data-action="preview-invoice-group"]');
    await wait(`document.querySelector('.group-confirm')`);await click('.group-confirm');
    await wait(`document.querySelector('[data-action="split-invoice-group"]')`);
    for(const [width,height] of [[1920,900],[1440,800],[1280,640],[1024,560]]) {
      await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
      fs.writeFileSync('D:/TDP_ROUND1/selected-group-'+width+'.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    }
    await click(`[data-action="view-invoice-receipt-summary"][data-id="${promo.promotion_invoice}"]`);
    await wait(`document.querySelector('.invoice-receipt-summary-dialog[open]')`);
    const oilCells=await evaluate(`Array.from(document.querySelectorAll('.invoice-receipt-summary-dialog tbody tr')).find(r=>r.cells[0].textContent.includes('QA-OIL')).textContent`);
    assert.ok(oilCells.includes('1,288,889'));assert.ok(oilCells.includes('42,963'));
    assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('.invoice-receipt-summary-dialog tbody tr')).find(r=>r.cells[0].textContent.includes('QA-OIL')).cells[2].textContent`),'30');
    for(const width of [1440,1024]) {
      await call('Emulation.setDeviceMetricsOverride',{width,height:800,deviceScaleFactor:1,mobile:false});
      assert.ok(await evaluate(`document.querySelector('.invoice-receipt-summary-dialog').getBoundingClientRect().right<=innerWidth+1`));
      fs.writeFileSync('D:/TDP_ROUND1/promotion-summary-'+width+'.png',Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    }
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    await wait(`!document.querySelector('.invoice-receipt-summary-dialog')`);
    assert.ok(await evaluate(`!!document.querySelector('.invoice-mapping-fullscreen-bar')`));
    await click(`[data-action="create-msmi-receipt"][data-id="${promo.promotion_invoice}"]`);
    await wait(`document.querySelector('.receipt-confirm:not([disabled])')`);
    await click('.receipt-confirm');
    await wait(`document.querySelector('[data-action="view-invoice-stock"][data-id="${promo.promotion_invoice}"]')`);
    assert.equal((await request(`/api/msmi/invoices/${promo.promotion_invoice}/receipt`,'POST',{})).status,200);
    const oilStock=(await request('/api/invoice-valuation?from=2026-08-01&to=2026-08-31')).body.items.find(r=>r.product_code==='QA-OIL');
    assert.equal(oilStock.closing_qty,30);assert.equal(oilStock.closing_value,1288889);
    assert.ok(Math.abs(oilStock.average_unit_cost-1288889/30)<0.000001);
    await click('.invoice-mapping-fullscreen-bar > button');
    const bulk=(await request('/fixture/bulk-receipts','POST',{})).body;
    assert.equal(bulk.ok,true);
    await change('invoiceTo','2026-08-30');
    await change('invoiceFrom','2026-08-30');
    await change('invoiceStatus','ready');
    await wait(`document.querySelector('[data-action="review-input-receipts"]:not([disabled])')`);
    await click('[data-action="review-input-receipts"]');
    await wait(`document.querySelectorAll('.receipt-choice').length>=2`);
    assert.equal(await evaluate(`document.querySelector('.receipt-selection-details').open`),false);
    await evaluate(`document.querySelector('.receipt-selection-details').open=true`);
    await click('.receipt-select-all input');
    assert.equal(await evaluate(`document.querySelector('.receipt-confirm').disabled`),true);
    await click('.receipt-select-all input');
    await evaluate(`document.querySelectorAll('.receipt-choice')[1].click()`);
    const chosen=await evaluate(`Array.from(document.querySelectorAll('.receipt-choice')).filter(c=>c.checked).length`);
    assert.ok(chosen>=1);
    fs.writeFileSync('D:/TDP_ROUND1/bulk-receipt-review.png',Buffer.from((await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})).data,'base64'));
    await click('.receipt-confirm');
    await wait(`!document.querySelector('.receipt-review-dialog')`);
    await wait(`document.querySelector('.receipt-posted-group')`);
    const traces=await Promise.all(bulk.ids.map(id=>request('/api/invoice-inventory/source/input/'+id)));
    assert.equal(traces.filter(r=>r.body.events.length>0).length,1);
    await click('[data-action="review-input-receipts"]');
    await wait(`document.querySelector('.receipt-confirm:not([disabled])')`);
    await click('.receipt-confirm');
    await wait(`!document.querySelector('.receipt-review-dialog')`);
    for(const id of bulk.ids) assert.equal((await request('/api/invoice-inventory/source/input/'+id)).body.events.length,1);
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
  } catch(error) {
    fs.writeFileSync('D:/TDP_ROUND1/failure.json',JSON.stringify({error:String(error),errors,dom:await evaluate(`({active:document.activeElement?.outerHTML,list:document.getElementById('msmiProductOptions')?.outerHTML,toast:document.getElementById('toast')?.textContent})`)},null,2));
    throw error;
  } finally {ws.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
