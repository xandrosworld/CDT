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
  await page.locator('[data-action=open-print-workspace][data-document=purchases]').click();
  await page.locator('#bkPrintMonth').fill('2026-08');
  await page.screenshot({path:out+'/01-chon-thang-8.png'});
  await page.locator('[data-action=open-saved-bk]').click();
  await page.locator('[data-history-id]').first().waitFor();
  const count=await page.locator('[data-history-id]').count();assert(count>0);
  await page.screenshot({path:out+'/02-bang-ke-thang-8-da-luu.png'});
  if(!process.env.TDP_BK_LIVE){
   await page.locator('[data-history-id]').first().uncheck();await page.locator('[data-history=summary]').click();
   assert((await page.locator('.bk-history-error').innerText()).includes('Chọn ít nhất'));
   assert.equal(await page.evaluate(()=>document.activeElement.hasAttribute('data-history-id')),true);
   await page.locator('[data-history-id]').first().check();
  }
  await page.locator('[data-history=summary]').click();
  const preview=page.locator('#bkSavedHistory-preview');
  await preview.locator('[data-open-sheet]').first().waitFor();
  assert.equal(await preview.locator('.document-error').innerText(),'');
  assert((await preview.innerText()).includes('2026'));
  await preview.scrollIntoViewIfNeeded();await page.screenshot({path:out+'/03-xem-bang-ke-thang-8.png'});
  const excel=page.waitForEvent('download');await preview.locator('[data-doc=excel]').click();await (await excel).saveAs(out+'/Bang-ke-thang-8.xlsx');
  const pdf=page.waitForEvent('download',{timeout:240000});await preview.locator('[data-doc=pdf]').click();await (await pdf).saveAs(out+'/Bang-ke-thang-8.pdf');
  await preview.locator('[data-doc=print]').click();await preview.locator('iframe').waitFor();
  await page.screenshot({path:out+'/04-mo-ban-in-A4.png'});
  if(!process.env.TDP_BK_LIVE){
   await page.locator('[data-action=open-monthly-bk]').click();
   await page.locator('[data-bk=history]').click();
   await page.locator('.bk-history-host [data-history=summary]').waitFor();
   await page.locator('[data-bk=close]').click();
  }
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  console.log('PASS: August saved history, '+count+' documents, Excel + PDF downloaded and print frame opened; no inventory confirmation requests.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
