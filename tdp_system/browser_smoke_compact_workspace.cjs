const assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 const base=process.env.TDP_COMPACT_TEST_URL || 'http://127.0.0.1:18809';
 const errors=[],writes=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(['POST','PUT','DELETE'].includes(r.method()))writes.push({url:r.url(),body:r.postDataJSON()});});
 const get=async p=>(await page.request.get(base+p)).json();
 const output=()=>get('/api/invoice-workbench/invoices?invoice_type=output&from=2026-08-01&to=2026-08-31');
 const line=id=>page.locator('#invoice-line-output-'+id);
 async function choose(id,code){await line(id).locator('.invoice-mapping-input').fill(code);await page.locator('#msmiProductOptions [data-product-code="'+code+'"]').click();}
 async function save(id){const res=page.waitForResponse(r=>r.url().endsWith('/output/'+id+'/mapping')&&r.request().method()==='PUT');await line(id).getByRole('button',{name:'Lưu',exact:true}).click();assert.equal((await res).status(),200);await page.waitForFunction(id=>{const row=document.getElementById('invoice-line-output-'+id);return row && !row.querySelector('button').disabled && !row.querySelector('.invoice-mapping-cell').dataset.editingId;},id);}
 try{
  await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'output',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'})));
  await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});
  const ids=await get('/fixture/ids'),before=await get('/fixture/snapshot');
  await page.locator('[data-view="msmi"]').click();await page.locator('.invoice-output-table').waitFor();
  assert.equal(await page.locator('.invoice-output-table thead th').count(),9);
  assert.equal(await page.locator('.invoice-output-table .invoice-draft-factor,.invoice-output-table .invoice-row-actions,.invoice-output-table .invoice-issue-text').count(),0);
  assert.equal(await line(ids.unsafe.id).locator('td').nth(3).innerText(),(await output()).lines.find(r=>r.id===ids.unsafe.id).source_item_name);
  assert.equal(await line(ids.unsafe.id).locator('input,button').count(),0);
  assert.equal(await line(ids.posted.id).locator('input,button').count(),0);
  assert.match(await line(ids.unsafe.id).getAttribute('class'),/invoice-row-issue/);
  await choose(ids.output_line,'R1-KG');await save(ids.output_line);
  let saved=(await output()).lines.find(r=>r.id===ids.output_line);assert.equal(saved.mapping_status,'mapped');assert.equal(saved.conversion_factor,1);
  await choose(ids.output_line,'R1-CAI');await save(ids.output_line);
  saved=(await output()).lines.find(r=>r.id===ids.output_line);assert.equal(saved.mapping_status,'unit_review');assert.equal(saved.conversion_factor,null);
  assert.match(await line(ids.output_line).getAttribute('class'),/invoice-row-issue/);
  // Re-saving an existing conversion keeps the confirmed factor even without an input.
  await save(ids.converted.id);assert.equal((await output()).lines.find(r=>r.id===ids.converted.id).conversion_factor,2.5);
  assert(writes.every(r=>r.url.endsWith('/mapping')&&!Object.hasOwn(r.body,'conversion_factor')));
  // Cancel a changed code, then handle a failed save without losing the draft.
  await choose(ids.output_line,'R1-KG');await line(ids.output_line).locator('input').press('Escape');assert.equal(await line(ids.output_line).locator('input').inputValue(),'R1-CAI');
  await choose(ids.output_line,'R1-KG');
  await page.route('**/items/output/'+ids.output_line+'/mapping',r=>r.fulfill({status:503,json:{error:'Lỗi kiểm thử'}}));
  await line(ids.output_line).getByRole('button',{name:'Lưu',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.toast')?.textContent.includes('Lỗi kiểm thử'));
  assert.equal(await line(ids.output_line).locator('input').inputValue(),'R1-KG');assert(await line(ids.output_line).getByRole('button',{name:'Lưu',exact:true}).isEnabled());
  await page.unroute('**/items/output/'+ids.output_line+'/mapping');await line(ids.output_line).locator('input').press('Escape');
  // Compact table fills the width; no source-code wrapping or overlapping sticky cells.
  for(const width of [1920,1440,1024]){
   await page.setViewportSize({width,height:900});await page.waitForTimeout(120);
   assert.equal(await page.locator('.sidebar').evaluate(e=>Math.round(e.getBoundingClientRect().height)),42);
   assert(await page.locator('.invoice-output-table').evaluate(e=>e.getBoundingClientRect().top<400));
   const wrap=page.locator('.invoice-lines-card .invoice-lines-scroll');
   await wrap.evaluate(e=>{e.scrollTop=300;e.scrollLeft=e.scrollWidth;});
   const box=await wrap.boundingBox(),heading=await page.locator('.invoice-output-table thead th').last().boundingBox();
   assert(Math.abs(heading.y-box.y)<3,'Header stays at top while scrolling');
   assert(Math.abs(heading.x+heading.width-(box.x+box.width))<20,'Mapping column stays at right edge');
  }
  await page.setViewportSize({width:1440,height:900});
  await page.locator('.invoice-lines-card .tdp-open-sheet').click();await page.locator('.invoice-mapping-fullscreen-bar').waitFor();
  assert(await page.locator('.invoice-lines-card').evaluate(e=>e.getBoundingClientRect().top===0 && Math.abs(e.getBoundingClientRect().height-innerHeight)<2));
  await page.screenshot({path:'tmp/compact-output-fullscreen.png'});
  await page.getByRole('button',{name:'Đóng toàn màn hình',exact:true}).click();
  await page.locator('[data-action="set-invoice-direction"][data-direction="input"]').click();await page.locator('.invoice-select-first').waitFor();
  assert(await page.locator('.invoice-select-first .invoice-draft-factor').count()>0);
  assert(await page.locator('.invoice-select-first [data-action="view-invoice-receipt-summary"]').count()>0);
  const mutationCount=writes.length;
  const tabs=await page.locator('#nav .nav-item').evaluateAll(es=>es.map(e=>e.dataset.view));
  for(const view of tabs){
   console.log('Checking tab',view);
   await page.locator('#nav [data-view="'+view+'"]').click();
   await page.waitForTimeout(250);await page.locator('#content .loading-panel').waitFor({state:'detached'});
   assert(await page.locator('#pageTitle').innerText());
   assert(await page.locator('#content').evaluate(e=>e.getBoundingClientRect().width>=innerWidth-20),view+' uses full width');
   assert(await page.locator('#nav [data-view="'+view+'"]').evaluate(e=>{const b=e.getBoundingClientRect(),n=e.parentElement.getBoundingClientRect();return b.left>=n.left-2&&b.right<=n.right+2;}),view+' remains accessible in the top bar');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),view+' has no page-wide overflow');
   await page.setViewportSize({width:1024,height:768});await page.waitForTimeout(80);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),view+' fits a smaller laptop');
   await page.setViewportSize({width:1440,height:900});
   if(['orders','settings','quotes','reports'].includes(view)) await page.screenshot({path:'tmp/compact-'+view+'.png'});
  }
  assert.equal(writes.length,mutationCount,'Navigating tabs performs no writes');
  await page.setViewportSize({width:390,height:844});await page.locator('#menuButton').click();await page.locator('#nav [data-view="msmi"]').click();await page.locator('.invoice-lines-card').waitFor();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile tables scroll within their panel');
  await page.setViewportSize({width:1440,height:900});await page.locator('[data-action="set-invoice-direction"][data-direction="output"]').click();await page.locator('.invoice-output-table').waitFor();
  await page.screenshot({path:'tmp/compact-output-desktop.png'});
  // Calendar icon remains clickable across its full, now smaller width.
  await page.evaluate(()=>{
   const original=HTMLInputElement.prototype.showPicker;window.pickerCalls=0;
   HTMLInputElement.prototype.showPicker=function(){original.call(this);window.pickerCalls++;};
  });
  for(const id of ['invoiceFrom','invoiceTo']){
   const icon=page.locator('#'+id).locator('..').locator('.localized-date-icon');
   const box=await icon.boundingBox();
   for(const x of [3,box.width/2,box.width-3]){
    const before=await page.evaluate(()=>window.pickerCalls);
    await page.mouse.click(box.x+x,box.y+box.height/2);
    assert.equal(await page.evaluate(()=>window.pickerCalls),before+1);
    await page.keyboard.press('Escape');
   }
  }
  assert.deepEqual(await get('/fixture/snapshot'),before,'Source quantities, amounts and stock never change');assert.deepEqual(errors,[]);
  console.log('PASS: 12 tabs, desktop/mobile layout, sticky headings, output mapping save/cancel/failure/unit mismatch/preserved conversion, fullscreen, input controls retained, source and stock unchanged.');
 }catch(error){console.log('Browser errors',errors);await page.screenshot({path:'tmp/compact-workspace-failure.png'});throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
