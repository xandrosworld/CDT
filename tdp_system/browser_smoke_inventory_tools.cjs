const assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.env.TDP_TOOLS_TEST_URL||'http://127.0.0.1:18853';
 assert(new URL(base).hostname==='127.0.0.1');
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const get=async p=>(await page.request.get(base+p)).json(),state=()=>get('/fixture/state');
 const value=async()=>{const r=await get('/api/invoice-valuation?from=2026-08-01&to=2026-08-31');return r.items.find(i=>i.product_code==='BK-P1');};
 const submit=async(selector,endpoint)=>{const response=page.waitForResponse(r=>r.url().includes(endpoint)&&r.request().method()==='POST');await page.locator(selector).click();return response;};
 const upload=async(kind,file)=>{const chooser=page.waitForEvent('filechooser');await page.locator('[data-action=choose-'+kind+'-workbook]').click();await(await chooser).setFiles(path.join(process.env.TDP_FIXTURE_OUTPUT,file));};
 try{
   await page.goto(base);await page.locator('#nav [data-view=inventory]').click();
   const before=await state();assert(!await page.locator('#openingForm').isVisible());
   const history=page.waitForResponse(r=>r.url().includes('/api/bk-import/documents?'));
   await page.locator('#inventoryDataTools > summary').click();await history;
   assert.deepEqual(await state(),before);
   const form=page.locator('#openingForm');await form.locator('[name=period]').fill('2026-08');await form.locator('[name=product_code]').fill('UNKNOWN');
   await form.locator('[name=qty]').fill('10.5');await form.locator('[name=unit_cost]').fill('100');
   assert.equal((await submit('#openingForm [type=submit]','/api/inventory/opening')).status(),400);assert.deepEqual(await state(),before);
   await form.locator('[name=product_code]').fill('BK-P1');assert.equal((await submit('#openingForm [type=submit]','/api/inventory/opening')).status(),200);
   assert.equal((await value()).opening_qty,10.5);
   await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('Đã lưu tồn đầu kỳ'));
   assert.equal(await form.locator('[name=period]').inputValue(),'2026-08','Saving must retain the chosen period for the next import');
   // Native upload, preview/cancel, explicit confirm and repeat preserve quantity.
   await page.locator('#openingForm [name=period]').fill('2026-08');
   const snapshot=await state();await upload('opening','opening.xlsx');
   await page.locator('[data-action=confirm-opening-import]:enabled').waitFor();assert.deepEqual(await state(),snapshot);
   await page.locator('[data-action=cancel-opening-import]').click();assert.deepEqual(await state(),snapshot);
   await upload('opening','opening.xlsx');
   await page.locator('[data-action=confirm-opening-import]:enabled').waitFor();
   assert.equal((await submit('[data-action=confirm-opening-import]','/opening/import/confirm')).status(),200);
   assert.equal((await value()).opening_qty,10.5);
   const opened=await state();await upload('bk','bk.xlsx');
   await page.locator('[data-action=confirm-bk-import]:enabled').waitFor();assert.deepEqual(await state(),opened);
   page.once('dialog',d=>d.dismiss());await page.locator('[data-action=confirm-bk-import]').click();assert.deepEqual(await state(),opened);
   page.once('dialog',d=>d.accept());assert.equal((await submit('[data-action=confirm-bk-import]','/bk-import/confirm')).status(),200);
   await page.locator('[data-action=reverse-bk-import]').waitFor();assert.equal((await value()).input_qty,2);
   await upload('bk','bk.xlsx');await page.locator('[data-action=confirm-bk-import]:enabled').waitFor();
   page.once('dialog',d=>d.accept());assert.equal((await submit('[data-action=confirm-bk-import]','/bk-import/confirm')).status(),200);assert.equal((await value()).input_qty,2);
   await page.locator('[data-action=reverse-bk-import]').waitFor();
   const answers=['31/08/2026','QA hoàn tác bảng kê',''];const answer=d=>d.accept(answers.shift());page.on('dialog',answer);
   assert.equal((await submit('[data-action=reverse-bk-import]','/reversal')).status(),200);page.off('dialog',answer);
   assert.equal((await value()).input_qty,0);assert.equal((await value()).opening_qty,10.5);
   await page.getByText('Đã hoàn tác',{exact:true}).waitFor();
   await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'inventory-tools.png')});assert.deepEqual(errors,[]);
   console.log('PASS inventory tools: collapsed/read-only opening, invalid product, decimal opening, upload preview/cancel/confirm, no double opening, BK cancel/post/reimport/reverse and totals');
 }catch(e){await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'failure.png')});console.log((await page.locator('#content').innerText()).slice(-5000));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
