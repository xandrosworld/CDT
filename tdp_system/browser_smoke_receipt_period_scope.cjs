const assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.env.TDP_INVOICE_TEST_URL||'http://127.0.0.1:18805';assert.equal(new URL(base).hostname,'127.0.0.1');
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],listRequests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/invoice-workbench/invoices?'))listRequests.push(r.url());});
 const get=async p=>(await page.request.get(base+p)).json();
 try{
   await page.addInitScript(()=>{if(!localStorage.getItem('tdp.invoiceWorkbenchFilters'))localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all',pending:true}));});
   await page.goto(base);await page.locator('#nav [data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor();
   assert.equal(await page.locator('[data-action=toggle-pending-invoices]').getAttribute('aria-pressed'),'false','Old automatically persisted all-period mode is reset to the selected dates');
   const ids=await get('/fixture/ids'),row=page.locator('#invoice-line-input-'+ids.line_b),box=page.locator('#invoice-line-input-'+ids.line_box);
   await row.locator('.invoice-mapping-input').fill('R1-KG');await page.locator('#msmiProductOptions [data-product-code="R1-KG"]').click();
   let refresh=page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?'));await row.getByRole('button',{name:'Lưu',exact:true}).click();await refresh;
   await box.locator('.invoice-draft-factor').fill('12');refresh=page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?'));await box.getByRole('button',{name:'Lưu',exact:true}).click();await refresh;
   await page.getByRole('button',{name:'Nhập kho 1 hóa đơn',exact:true}).click();const dialog=page.locator('.receipt-review-dialog');await dialog.locator('.receipt-confirm').waitFor();
   assert.equal(await dialog.locator('.receipt-choice').count(),1);refresh=page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?'));
   await dialog.locator('.receipt-confirm').click();await refresh;
   await page.locator('.invoice-post-result').waitFor();
   assert.equal(await page.locator('[data-action=toggle-pending-invoices]').getAttribute('aria-pressed'),'false');
   assert.equal(await page.locator('#invoiceFrom').inputValue(),'2026-08-01');assert.equal(await page.locator('#invoiceTo').inputValue(),'2026-08-31');
   assert.match(await page.locator('.invoice-scope-label').innerText(),/01\/08\/2026.*31\/08\/2026/);
   assert(!listRequests.some(u=>u.includes('scope=pending')),'Posting must not fetch invoices from older periods automatically');
   let data=await get('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31');assert.equal(data.counts.posted,2);assert.equal(data.totals.issue_count,0);
   await page.locator('.invoice-lines-card .tdp-open-sheet').click();assert(await page.locator('.invoice-scope-label').isVisible());await page.keyboard.press('Escape');
   await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'period-after-receipt.png')});
   await page.getByRole('button',{name:'Còn chưa nhập · mọi kỳ',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.invoice-scope-label')?.textContent.includes('Mọi kỳ'));
   assert.match(await page.locator('.invoice-lines-scroll').first().innerText(),/31\/07\/2022/);
   assert.equal(await page.locator('[data-action=toggle-pending-invoices]').getAttribute('aria-pressed'),'true');
   await page.locator('#invoiceTo').evaluate(e=>{e.value='2026-08-30';e.dispatchEvent(new Event('change',{bubbles:true}));});
   await page.waitForFunction(()=>document.querySelector('[data-action=toggle-pending-invoices]')?.getAttribute('aria-pressed')==='false');
   await page.reload();await page.locator('#nav [data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor();
   assert.equal(await page.locator('[data-action=toggle-pending-invoices]').getAttribute('aria-pressed'),'false');assert.deepEqual(errors,[]);
   console.log('PASS: input posting retains August, zero old-period requests, counts correct, scope visible fullscreen, explicit all-period toggle exposes 2022 invoice, return/reload retains chosen period');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
