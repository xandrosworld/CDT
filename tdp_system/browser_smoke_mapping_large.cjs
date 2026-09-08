const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.env.TDP_INVOICE_TEST_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}});
 const errors=[],writes=[],timings={},output=process.env.TDP_FIXTURE_OUTPUT;let delayListing=false;
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='PUT')writes.push(r.url());});
 try{
  const ids=await (await page.request.get(base+'/fixture/ids')).json();
  await page.route('**/api/invoice-workbench/invoices?**',async route=>{
   const response=await route.fetch(),data=await response.json();
   if(delayListing)await new Promise(r=>setTimeout(r,700));
   const original=data.lines.find(r=>r.id===ids.line_b);
   if(original){const extras=Array.from({length:23901-data.lines.length},(_,i)=>({...original,id:1000000+i,source_item_name:'Large fixture '+i,line_index:i+100}));data.lines.splice(0,0,...extras.slice(0,30));data.lines.push(...extras.slice(30));data.totals.line_count=data.lines.length;}
   await route.fulfill({response,json:data});
  });
  await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'})));
  let t=Date.now();await page.goto(base);await page.locator('#nav [data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor();timings.openMs=Date.now()-t;
  const wrap=page.locator('.invoice-lines-card .invoice-lines-scroll');
  assert((await wrap.locator('tbody tr').count())<=82);assert.match(await page.locator('#invoice-list-count').innerText(),/23\.901/);
  await page.locator('.invoice-lines-card .tdp-open-sheet').click();
  const row=page.locator('#invoice-line-input-'+ids.line_b),next=page.locator('#invoice-line-input-'+ids.line_box);
  await row.locator('.invoice-mapping-input').scrollIntoViewIfNeeded();
  t=Date.now();await row.locator('.invoice-mapping-input').fill('R1-KG');await page.locator('#msmiProductOptions [data-product-code="R1-KG"]').click();timings.typeAndChooseMs=Date.now()-t;assert(timings.typeAndChooseMs<3000);
  await next.locator('.invoice-draft-factor').fill('12');assert.equal(await next.locator('.invoice-draft-factor').inputValue(),'12','Can edit the next row while the first has a draft');
  await row.locator('.invoice-mapping-input').click();assert.equal(await row.locator('.invoice-mapping-input').inputValue(),'R1-KG');
  await page.keyboard.press('Escape'); // closes suggestions; stay in fullscreen
  const position=await wrap.evaluate(e=>({top:e.scrollTop,left:e.scrollLeft}));
  delayListing=true;
  const saved=page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?'));
  await row.getByRole('button',{name:'Lưu',exact:true}).click();
  await next.locator('.invoice-draft-factor').fill('24');
  const workingPosition=await wrap.evaluate(e=>({top:e.scrollTop,left:e.scrollLeft}));
  const workingRowTop=await next.evaluate(e=>e.getBoundingClientRect().top);
  await saved;await page.waitForTimeout(300);delayListing=false;
  assert.equal(await next.locator('.invoice-draft-factor').inputValue(),'24','Typing in another row during a slow save survives refresh');
  assert(await next.locator('.invoice-draft-factor').evaluate(e=>e===document.activeElement),'Save does not steal keyboard focus');
  await next.locator('.invoice-draft-factor').fill('12');
  const after=await wrap.evaluate(e=>({top:e.scrollTop,left:e.scrollLeft}));
  const afterRowTop=await next.evaluate(e=>e.getBoundingClientRect().top);
  assert(Math.abs(afterRowTop-workingRowTop)<8,JSON.stringify({position,workingPosition,after,workingRowTop,afterRowTop}));assert.equal(after.left,workingPosition.left);
  await row.locator('.invoice-mapping-input').fill('dang go');await row.locator('.invoice-mapping-input').dispatchEvent('keydown',{key:'Enter',isComposing:true});assert.equal(writes.length,1,'IME Enter must not save');
  // A dirty row and selection remain available after visiting the end of all 23,901 rows.
  const check=row.locator('.invoice-group-select');await check.check();
  await wrap.evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForTimeout(250);
  assert((await wrap.locator('tbody tr').count())<=82);assert.match(await wrap.innerText(),/Large fixture 238/);
  await page.keyboard.press('Control+f');const search=page.locator('.tdp-table-search input');await search.fill('Large fixture 17000');await search.press('Enter');await page.waitForTimeout(200);
  assert.match(await wrap.innerText(),/Large fixture 17000/);assert.match(await page.locator('.tdp-search-result').innerText(),/1 \/ 1/);
  await wrap.evaluate((e,top)=>e.scrollTop=top,position.top);await page.waitForTimeout(200);
  assert.equal(await row.locator('.invoice-mapping-input').inputValue(),'dang go');assert(await row.locator('.invoice-group-select').isChecked());
  const saveNext=page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?'));await next.getByRole('button',{name:'Lưu',exact:true}).click();await saveNext;
  const actual=await (await page.request.get(base+'/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).json();assert.equal(actual.lines.find(r=>r.id===ids.line_box).conversion_factor,12);
  assert.equal(await row.locator('.invoice-mapping-input').inputValue(),'dang go','Can save the second row before the first draft');
  await row.locator('.invoice-mapping-input').press('Escape');
  await next.locator('.invoice-group-select').check();
  await page.locator('[data-action=preview-invoice-group]').click();await page.locator('.invoice-group-dialog').waitFor();
  assert.match(await page.locator('.invoice-group-dialog h3').innerText(),/Gộp 2 dòng/);await page.locator('.group-cancel').click();
  // Failed save keeps the draft and allows retry; a later concurrent mapping is not overwritten.
  const conversionUrl=base+'/api/invoice-workbench/items/input/'+ids.line_b+'/conversion';
  const failedRoute=route=>route.fulfill({status:503,json:{error:'Simulated offline save'}});
  await page.route(conversionUrl,failedRoute);await row.locator('.invoice-draft-factor').fill('1.5');
  let response=page.waitForResponse(r=>r.url()===conversionUrl);await row.getByRole('button',{name:'Lưu',exact:true}).click();assert.equal((await response).status(),503);
  await page.waitForTimeout(100);assert.equal(await row.locator('.invoice-draft-factor').inputValue(),'1.5');assert(await row.locator('.invoice-draft-factor').isEnabled());
  await page.unroute(conversionUrl,failedRoute);
  const old=actual.lines.find(r=>r.id===ids.line_b),expected=Object.fromEntries(['product_code','mapping_status','conversion_factor','source_unit','qty','amount'].map(k=>[k,old[k]]));
  const concurrent=await page.request.put(conversionUrl,{data:{conversion_factor:2,expected}});assert.equal(concurrent.status(),200);
  response=page.waitForResponse(r=>r.url()===conversionUrl);await row.getByRole('button',{name:'Lưu',exact:true}).click();assert.equal((await response).status(),409);
  const fresh=await (await page.request.get(base+'/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31')).json();assert.equal(fresh.lines.find(r=>r.id===ids.line_b).conversion_factor,2);
  assert.equal(await row.locator('.invoice-draft-factor').inputValue(),'1.5');await row.locator('.invoice-draft-factor').press('Escape');
  await page.locator('.receipt-other-actions > summary').click();await page.locator('[data-action=jump-invoice-issue]').click();assert(await page.locator('tr[data-issue="1"]').first().isVisible());
  await page.setViewportSize({width:1024,height:700});await page.screenshot({path:path.join(output,'large-1024.png')});
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(output,'timings.json'),JSON.stringify(timings,null,2));console.log(JSON.stringify({ok:true,lines:23901,timings,writes:writes.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message.split('Call log:')[0]);process.exitCode=1;});
