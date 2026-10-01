const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE);
const base=process.env.TDP_BK_BASE||'http://127.0.0.1:18807';
const out=process.env.TDP_BK_PROOF||'D:/TDP_RAILWAY_PRIVATE/bk-history-proof';
(async()=>{
 fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(90000);
  const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()!=='GET'&&/\/(confirm|reversal|approve|post-stock)(?:\?|$)/.test(r.url()))writes.push(r.url());});
  await page.goto(base);
  if(process.env.TDP_BK_LIVE){
   const a=JSON.parse(fs.readFileSync('D:/TDP_RAILWAY_PRIVATE/access.json','utf8'));
   await page.locator('[name=username]').fill(a.username);await page.locator('[name=password]').fill(a.password);await page.locator('button[type=submit]').click();
  }
  await page.waitForFunction(()=>window.TdpBkHistory);await page.locator('.loading-panel').waitFor({state:'detached'});
  await page.screenshot({path:out+'/00-vao-muc-in-bang-ke.png'});
  await page.locator('[data-action=open-print-workspace][data-document=purchases]').click();
  assert.equal(await page.locator('#bkPrintScope').inputValue(),'day');
  await page.locator('#bkPrintDay').locator('..').locator('.localized-date-display').fill('01/08/2026');
  await page.locator('#bkPrintDay').locator('..').locator('.localized-date-display').press('Tab');
  const dayRequest=page.waitForRequest(r=>r.url().includes('/api/bk-import/history?'));
  await page.locator('[data-action=open-saved-bk]').click();
  assert((await dayRequest).url().includes('from=2026-08-01&to=2026-08-01'));
  await page.locator('[data-history-id]').first().waitFor();
  assert.equal(await page.locator('[data-history-id]:checked').count(),0);
  await page.locator('#bkPrintScope').selectOption('month');
  assert.equal(await page.locator('[data-history-id]').count(),0);
  await page.locator('#bkPrintMonth').locator('..').locator('.localized-date-display').fill('08/2026');
  await page.locator('#bkPrintMonth').locator('..').locator('.localized-date-display').press('Tab');
  await page.screenshot({path:out+'/01-chon-thang-8.png'});
  await page.locator('[data-action=open-saved-bk]').click();
  await page.locator('[data-history-id]').first().waitFor();
  const count=await page.locator('[data-history-id]').count();assert(count>0);
  assert.equal(await page.locator('[data-history-id]:checked').count(),0);
  await page.locator('[data-history=all]').click();
  await page.locator('[data-history-supplement]').click();
  assert.equal(await page.locator('.bk-draft-dialog [name=from]').inputValue(),'2026-08-01');
  assert.equal(await page.locator('.bk-draft-dialog [name=to]').inputValue(),'2026-08-31');
  await page.locator('[data-bk=close]').click();
  assert.equal(await page.locator('[data-history-id]:checked').count(),count);
  await page.screenshot({path:out+'/02-bang-ke-thang-8-da-luu.png'});
  if(!process.env.TDP_BK_LIVE){
   await page.locator('[data-history=none]').click();await page.locator('[data-history=summary]').click();
   assert((await page.locator('.bk-history-error').innerText()).includes('Chọn ít nhất'));
   assert.equal(await page.evaluate(()=>document.activeElement.hasAttribute('data-history-id')),true);
   await page.locator('[data-history=all]').click();
  }
  await page.locator('[data-history=summary]').click();
  const preview=page.locator('#bkSavedHistory-preview');
  await preview.locator('[data-open-sheet]').first().waitFor();
  assert.equal(await preview.locator('.document-error').innerText(),'');
  assert((await preview.innerText()).includes('2026'));
  if(!process.env.TDP_BK_LIVE){
   assert((await preview.innerText()).includes('Từ ngày 01/08/2026 đến ngày 01/08/2026'));
   await preview.locator('[data-saved-receipts]').click();
   await preview.locator('[data-doc=receipts]').waitFor();
   assert.equal(await page.locator('[data-history-id]:checked').count(),count);
   await preview.locator('[data-doc=summary]').click();
  }
  await preview.scrollIntoViewIfNeeded();await page.screenshot({path:out+'/03-xem-bang-ke-thang-8.png'});
  const excel=page.waitForEvent('download');await preview.locator('[data-doc=excel]').click();await (await excel).saveAs(out+'/Bang-ke-thang-8.xlsx');
  const pdf=page.waitForEvent('download',{timeout:240000});await preview.locator('[data-doc=pdf]').click();await (await pdf).saveAs(out+'/Bang-ke-thang-8.pdf');
  if(!process.env.TDP_BK_LIVE){
   await page.route('**/api/documents/preview',route=>{
    const body=route.request().postDataJSON();
    if(body.kind==='saved-purchases'&&body.receipts)return route.fulfill({status:422,json:{ok:false,code:'receipt_daily_limit_exceeded',error:'Seller Test, ngày 01/08/2026: 6.000.000đ. Bảng kê tổng vẫn in được.'}});
    return route.continue();
   });
   await page.locator('[data-history=receipts]').click();
   await preview.locator('[data-saved-back]').waitFor();
   assert((await preview.locator('.document-error').innerText()).includes('Seller Test'));
   await preview.getByRole('button',{name:'Xem bảng kê tổng',exact:true}).click();
   await preview.locator('[data-open-sheet]').first().waitFor();
   assert.equal(await page.locator('[data-history-id]:checked').count(),count);
   await page.unroute('**/api/documents/preview');
   await page.locator('[data-action=open-monthly-bk]').click();
   await page.locator('[data-bk=history]').click();
   await page.locator('.bk-history-host [data-history=summary]').waitFor();
   await page.locator('[data-bk=close]').click();
  }
  await preview.locator('[data-doc=print]').click();await preview.locator('iframe').waitFor();
  await page.screenshot({path:out+'/04-mo-ban-in-A4.png'});
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  console.log('PASS: August saved history, '+count+' documents, Excel + PDF downloaded and print frame opened; no inventory confirmation requests.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
