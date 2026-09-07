const assert=require('node:assert/strict');
// Run against browser_fixture_date_picker_server.py on a fresh synthetic database.
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posts=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/expense')&&r.method()==='POST')posts.push(r.postDataJSON())});
 const base=process.env.TDP_EXPENSE_TEST_URL || 'http://127.0.0.1:18805',get=async p=>(await page.request.get(base+p)).json(),data=()=>get('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31');
 try{
 await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'})));
 await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});await page.locator('[data-view="msmi"]').click();await page.locator('#invoice-list-count').waitFor();
 const ids=await get('/fixture/ids'),before=await data(),row=page.locator('#invoice-line-input-'+ids.line_b),trigger=row.locator('[data-action="invoice-expense-all"]'),dialog=page.locator('dialog.invoice-expense-confirm');
 assert.equal(await trigger.innerText(),'Phân loại…');
 for(const cancellation of ['Escape','Enter','button']){
  await trigger.click();await dialog.waitFor();assert.equal(await dialog.locator('tbody tr').count(),2);assert.match(await dialog.innerText(),/Cả hóa đơn · 2 dòng/);assert.match(await dialog.innerText(),/C26TST \/ 2/);
  assert(await dialog.locator('[data-expense-cancel]').evaluate(e=>document.activeElement===e));
  assert.equal(posts.length,0);assert.deepEqual((await data()).lines,before.lines);
  if(cancellation==='button')await dialog.locator('[data-expense-cancel]').click();else await page.keyboard.press(cancellation);
  await dialog.waitFor({state:'detached'});assert.equal(posts.length,0);assert.deepEqual((await data()).lines,before.lines);assert(await trigger.isEnabled());
 }
 await trigger.click();await dialog.waitFor();if(process.env.TDP_EXPENSE_SCREENSHOT)await dialog.screenshot({path:process.env.TDP_EXPENSE_SCREENSHOT});
 let saved=page.waitForResponse(r=>r.url().endsWith('/expense'));await dialog.locator('[data-expense-confirm]').click();assert.equal((await saved).status(),200);await row.locator('.invoice-expense-label').waitFor();
 assert.equal(posts.length,1);assert.equal(posts[0].confirmed,true);assert.equal(posts[0].item_ids,null);
 await row.locator('[data-action="view-invoice-receipt-summary"]').click();
 const review=page.locator('.invoice-review-dialog');await review.locator('.review-lines').waitFor();
 assert.equal(await review.locator('.review-lines tbody tr').count(),2);assert.equal(await review.locator('.review-code,.review-factor,.review-select').count(),0);
 await review.locator('.review-close').click();await review.waitFor({state:'detached'});
 await row.locator('[data-action="invoice-expense-undo"]').click();await dialog.waitFor();assert.match(await dialog.innerText(),/Chuyển lại thành hàng hóa/);
 saved=page.waitForResponse(r=>r.url().endsWith('/expense'));await dialog.locator('[data-expense-confirm]').click();assert.equal((await saved).status(),200);await trigger.waitFor();
 await row.locator('[data-action="invoice-expense-all"]').click();await dialog.waitFor();assert.match(await dialog.innerText(),/Cả hóa đơn · 2 dòng/);assert.equal(await dialog.locator('tbody tr').count(),2);
 await dialog.locator('[data-expense-cancel]').click();assert.equal(posts.length,2);
 const current=await data(),inv=current.items.find(i=>i.id===ids.input_ids['2']);
 const rejected=await page.request.post(base+'/api/invoice-workbench/input-invoices/'+inv.id+'/expense',{data:{expense:true,expected:inv.expense_token}});assert.equal(rejected.status(),400);
 assert.deepEqual((await data()).lines,before.lines);assert.deepEqual(errors,[]);
 console.log('PASS: open/cancel/Esc/Enter do not write; whole invoice scope shown from under-name classification; explicit confirm only; restore confirmed; old requests rejected');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
