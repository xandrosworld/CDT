// Fresh browser_fixture_invoice_review_server.py; all writes stay in its temporary DB.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const base = process.env.TDP_REVIEW_TEST_URL || 'http://127.0.0.1:18806';
  const errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(['PUT','POST'].includes(r.method()) && !r.url().endsWith('selection-preview'))writes.push(r.url());});
  const get=async p=>(await page.request.get(base+p)).json();
  const listing=()=>get('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31');
  const modal=page.locator('.invoice-review-dialog');
  const row=id=>modal.locator('[data-review-line="'+id+'"]');
  const waitIdle=()=>page.waitForFunction(()=>{const b=document.querySelector('.invoice-review-dialog .review-close');return b && !b.disabled;});
  async function open(id){await page.locator('[data-action="view-invoice-receipt-summary"][data-id="'+id+'"]').first().click();await modal.locator('.review-lines').waitFor();await waitIdle();}
  async function close(){await modal.locator('.review-close').click();await modal.waitFor({state:'detached'});}
  async function choose(id,code){await row(id).locator('.review-code').fill(code);await row(id).locator('.review-results button').filter({hasText:code+' · '}).click();}
  async function save(id){const response=page.waitForResponse(r=>/\/(mapping|conversion)$/.test(r.url()) && r.request().method()==='PUT');await row(id).locator('.review-save').click();const result=await response;await waitIdle();return result;}
  try {
    await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'})));
    await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});await page.locator('[data-view="msmi"]').click();await page.locator('#invoice-list-count').waitFor();
    const ids=await get('/fixture/ids'),before=await get('/fixture/snapshot');
    assert(!before.error,'Fixture snapshot available');
    assert.equal(await page.locator('.invoice-row-actions .invoice-expense-menu').count(),0);
    assert.equal(await page.locator('#invoice-line-input-'+ids.line_b+' [data-action="invoice-expense-all"]').count(),1);
    // Main-table draft must not get discarded by opening and saving in review.
    const mainRow=page.locator('#invoice-line-input-'+ids.line_b);
    await mainRow.locator('.invoice-draft-factor').fill('9');
    await mainRow.locator('[data-action="view-invoice-receipt-summary"]').click();
    assert.equal(await modal.count(),0);assert.equal(await mainRow.locator('.invoice-draft-factor').inputValue(),'9');
    await mainRow.locator('.invoice-draft-factor').press('Escape');
    // Opening from a filtered single visible row still fetches both source rows.
    await page.locator('#invoiceLineFilter').selectOption('unit_review');
    await page.locator('#invoice-line-input-'+ids.line_b).waitFor({state:'detached'});
    await page.route('**/api/invoice-workbench/invoices?**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[],lines:[]})}));
    await page.locator('[data-action="view-invoice-receipt-summary"][data-id="'+ids.input_ids['2']+'"]').click();
    await page.waitForFunction(()=>document.querySelector('.review-error')?.textContent.includes('Không còn tìm thấy'));
    await waitIdle();await close();await page.unroute('**/api/invoice-workbench/invoices?**');
    await open(ids.input_ids['2']);assert.equal(await modal.locator('.review-lines tbody tr').count(),2);
    assert.equal(await modal.locator('.review-reset:visible').count(),0);
    assert.equal(await modal.locator('th').first().evaluate(e=>getComputedStyle(e).color),'rgb(23, 43, 58)');
    assert.equal(writes.length,0);assert.deepEqual(await get('/fixture/snapshot'),before);
    assert(await row(ids.line_b).locator('.review-factor').isEnabled());
    await row(ids.line_b).locator('.review-factor').fill('0,5');
    await row(ids.line_b).locator('.review-save').click();await waitIdle();assert.equal(writes.length,0);
    assert.match(await modal.locator('.review-error').innerText(),/Chọn mã hàng/);
    await choose(ids.line_b,'R1-CAI');assert.equal(await row(ids.line_b).locator('.review-factor').inputValue(),'0,5');
    await choose(ids.line_b,'R1-CAI');assert.equal(await row(ids.line_b).locator('.review-factor').inputValue(),'0,5');
    await choose(ids.line_b,'R1-KG');assert.equal(await row(ids.line_b).locator('.review-factor').inputValue(),'1');
    await row(ids.line_b).locator('.review-factor').fill('0');await row(ids.line_b).locator('.review-save').click();await waitIdle();assert.equal(writes.length,0);
    await row(ids.line_b).locator('.review-factor').fill('0,5');
    await row(ids.line_box).locator('.review-factor').fill('12');
    assert.equal((await save(ids.line_b)).status(),200);
    assert.equal(await row(ids.line_box).locator('.review-factor').inputValue(),'12','Other row draft survives save/refresh');
    assert.match(await modal.locator('.review-summary').innerText(),/0,5/);
    // Close cancellation retains drafts; accepting discards drafts only.
    page.once('dialog',d=>d.dismiss());await modal.locator('.review-close').click();assert(await modal.isVisible());
    page.once('dialog',d=>d.accept());await close();await open(ids.input_ids['2']);
    assert.equal(await row(ids.line_box).locator('.review-factor').inputValue(),'');
    assert.equal(await row(ids.line_b).locator('.review-factor').inputValue(),'0.5');
    // A failed request keeps the user's draft and shows an actionable error.
    await row(ids.line_box).locator('.review-factor').fill('12');
    await page.route('**/items/input/'+ids.line_box+'/conversion',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'Mất kết nối thử nghiệm'})}));
    assert.equal((await save(ids.line_box)).status(),503);
    assert.equal(await row(ids.line_box).locator('.review-factor').inputValue(),'12');
    assert.match(await modal.locator('.review-error').innerText(),/Mất kết nối/);
    await page.unroute('**/items/input/'+ids.line_box+'/conversion');
    assert.equal((await save(ids.line_box)).status(),200);
    assert.match(await modal.locator('.review-summary').innerText(),/24/);
    // Concurrent edit must be rejected rather than silently overwritten.
    await row(ids.line_b).locator('.review-factor').fill('2');
    const live=(await listing()).items.find(i=>i.id===ids.input_ids['2']).items.find(r=>r.id===ids.line_b);
    const expected=Object.fromEntries(['product_code','mapping_status','conversion_factor','source_unit','qty','amount'].map(k=>[k,live[k]]));
    assert.equal((await page.request.put(base+'/api/invoice-workbench/items/input/'+ids.line_b+'/conversion',{data:{conversion_factor:3,expected}})).status(),200);
    assert.equal((await save(ids.line_b)).status(),409);
    assert.equal(await row(ids.line_b).locator('.review-factor').inputValue(),'2');
    page.once('dialog',d=>d.accept());await close();
    await page.locator('#invoiceLineFilter').selectOption('all');
    await page.locator('#invoice-line-input-'+ids.line_b).waitFor();
    await open(ids.input_ids['2']);assert.equal(await row(ids.line_b).locator('.review-factor').inputValue(),'3');
    // Grouping guard prevents losing unfinished edits; reset and cancel group are read-only.
    await row(ids.line_b).locator('.review-select').check();await row(ids.line_box).locator('.review-select').check();
    await row(ids.line_box).locator('.review-factor').fill('2');await modal.locator('.review-group').click();
    assert.match(await modal.locator('.review-error').innerText(),/Lưu hoặc Bỏ sửa/);
    await row(ids.line_box).locator('.review-reset').click();
    const count=writes.length;await modal.locator('.review-group').click();
    const group=page.locator('.invoice-group-dialog');await group.waitFor();await group.locator('.group-cancel').click();
    assert.equal(writes.length,count);assert(await modal.isVisible());
    await modal.locator('.review-group').click();await group.waitFor();
    await group.locator('#group-product-search').fill('R1-KG');await group.locator('.group-product-results button').filter({hasText:'R1-KG'}).click();
    await group.locator('.group-factor[data-id="'+ids.line_box+'"]').fill('2');
    await page.waitForFunction(()=>!document.querySelector('.group-confirm').disabled);
    await group.locator('.group-confirm').click();await group.waitFor({state:'detached'});await waitIdle();
    await row(ids.line_b).locator('.review-split').waitFor();
    assert.equal(await modal.locator('.review-lines tbody tr').count(),2,'Grouping retains every original row inside review');
    assert.equal(await modal.locator('.review-code').count(),0);
    assert.match(await modal.locator('.review-summary').innerText(),/7/);
    await row(ids.line_b).locator('.review-split').click();await waitIdle();
    assert.equal(await modal.locator('.review-code').count(),2);
    await choose(ids.line_b,'R1-CAI');await row(ids.line_b).locator('.review-factor').fill('0,25');
    const entered=page.waitForResponse(r=>r.url().endsWith('/mapping') && r.request().method()==='PUT');await row(ids.line_b).locator('.review-factor').press('Enter');assert.equal((await entered).status(),200);await waitIdle();
    await close();
    // Posted and unsafe source invoices are read-only even when the modal is open.
    for(const id of [ids.input_ids['1'],ids.input_ids['3']]) {
      await open(id);assert.equal(await modal.locator('.review-code,.review-select,.review-split').count(),0);assert(await modal.locator('.review-group').isDisabled());await close();
    }
    // Paid + free goods keep their full quantity and original amount when grouped.
    await open(ids.promotion_invoice);
    const oil=ids.promotion_lines['QA-OIL-PAID'],free=ids.promotion_lines['QA-OIL-FREE'];
    const summary=await modal.locator('.review-summary').innerText();
    await row(oil).locator('.review-select').check();await row(free).locator('.review-select').check();
    await modal.locator('.review-group').click();await group.waitFor();await page.waitForFunction(()=>!document.querySelector('.group-confirm').disabled);
    await group.locator('.group-confirm').click();await group.waitFor({state:'detached'});await row(oil).locator('.review-split').waitFor();await waitIdle();
    assert.equal(await modal.locator('.review-summary').innerText(),summary);
    assert.equal(await modal.locator('.review-lines tbody tr').count(),4);
    if(process.env.TDP_REVIEW_SCREENSHOT)await modal.screenshot({path:process.env.TDP_REVIEW_SCREENSHOT});
    // Narrow viewport keeps close/action controls reachable, scrolling stays inside dialog.
    await page.setViewportSize({width:800,height:650});
    const box=await modal.boundingBox();assert(box.x>=0 && box.x+box.width<=801);assert(box.height<=650);
    assert(await modal.locator('.review-close').isVisible());await close();
    await page.setViewportSize({width:1440,height:1000});
    await page.reload();await page.locator('.loading-panel').waitFor({state:'detached'});await page.locator('[data-view="msmi"]').click();await page.locator('#invoice-list-count').waitFor();
    await open(ids.promotion_invoice);assert.equal(await modal.locator('.review-summary').innerText(),summary);assert.equal(await modal.locator('.review-split').count(),2);await close();
    // A concurrent change invalidating an old group must expose its removal action.
    const groupedLine=(await listing()).items.find(i=>i.id===ids.promotion_invoice).items.find(r=>r.id===oil);
    const groupExpected=Object.fromEntries(['product_code','mapping_status','conversion_factor','source_unit','qty','amount'].map(k=>[k,groupedLine[k]]));
    assert.equal((await page.request.put(base+'/api/invoice-workbench/items/input/'+oil+'/conversion',{data:{conversion_factor:2,expected:groupExpected}})).status(),200);
    await open(ids.promotion_invoice);await modal.getByRole('button',{name:'Bỏ nhóm cũ',exact:true}).waitFor();
    await modal.getByRole('button',{name:'Bỏ nhóm cũ',exact:true}).click();await waitIdle();
    assert.equal(await modal.locator('.review-split').count(),0);assert.equal(await modal.locator('.review-code').count(),4);await close();
    assert.deepEqual(await get('/fixture/snapshot'),before,'Source quantities, prices, amounts, header JSON and stock ledger remain exactly unchanged');
    assert.deepEqual(errors,[]);
    console.log('PASS: full invoice from filtered row; editable factors/mappings; cross-row drafts; cancel/discard; API failure; stale edit rejection; group/cancel/split/remap; paid/free totals; posted/source-error locks; responsive modal; reload persistence; source and stock hashes unchanged');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
