const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE);
const base=process.env.TDP_BK_BASE||'http://127.0.0.1:18807';
const out=process.env.TDP_BK_PROOF||'D:/TDP_RAILWAY_PRIVATE/simple-day-proof';
(async()=>{
 fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  for(const type of ['summary','receipts']){
   const page=await browser.newPage({viewport:{width:1440,height:1050}});page.setDefaultTimeout(90000);
   if(process.env.TDP_BK_LOCAL_ASSETS)for(const f of ['app.js','bk-draft.js','bk-history.js'])await page.route('**/static/'+f+'*',r=>r.fulfill({contentType:'application/javascript',body:fs.readFileSync('tdp_system/static/'+f,'utf8')}));
   const writes=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
   page.on('request',r=>{if(r.method()==='POST'&&/\/(confirm|approve|reversal)(\?|$)/.test(r.url()))writes.push(r.url());});
   await page.goto(base);
   if(process.env.TDP_BK_LIVE){const a=JSON.parse(fs.readFileSync('D:/TDP_RAILWAY_PRIVATE/access.json'));await page.locator('[name=username]').fill(a.username);await page.locator('[name=password]').fill(a.password);await page.locator('button[type=submit]').click();}
   await page.waitForFunction(()=>window.TdpBkDayPrint);await page.locator('.loading-panel').waitFor({state:'detached'});
   await page.locator('[data-action=open-print-workspace][data-document=purchases]').click();
   await page.locator('#bkPrintDay').locator('..').locator('.localized-date-display').fill(process.env.TDP_DAY||'01/08/2026');
   await page.locator('#bkPrintDay').locator('..').locator('.localized-date-display').press('Tab');
   await page.locator('[data-action=open-saved-bk]').click();
   const preview=page.locator('#bkSavedHistory');await preview.locator('[data-simple-print]').waitFor();
   assert.equal(await page.locator('[data-day-print]').count(),0);

   assert.equal(await preview.locator('.document-paper').isVisible(),false);
   await page.screenshot({path:out+'/01-'+type+'-simple.png'});
   const result=page.waitForResponse(r=>r.url().includes('/api/documents/')&&r.url().includes('/pdf?'),{timeout:240000});
   await preview.locator('[data-doc="print-'+type+'"]').click();
   const response=await result;assert(response.ok());
   const url=new URL(response.url());assert.equal(url.searchParams.get('paper'),type==='summary'?'A4':'A5');
   const file=await page.request.get(response.url(),{timeout:240000});assert(file.ok());
   const bytes=await file.body();assert(bytes.length>100&&bytes.subarray(0,4).toString()==='%PDF');
   fs.writeFileSync(out+'/'+type+'.pdf',bytes);
   await preview.locator('iframe').waitFor();
   assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS chosen day opens saved documents without intermediate status; direct summary A4 and receipts A5 generate PDFs and print frames; no stock writes.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
