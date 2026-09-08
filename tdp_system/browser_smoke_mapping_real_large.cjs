// Render an explicitly supplied private, read-only listing. Never write customer records.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.env.TDP_INVOICE_TEST_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
 const data=JSON.parse(fs.readFileSync(process.env.TDP_REAL_PENDING_JSON,'utf8'));assert(data.lines.length>20000);
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1920,height:900}}),errors=[],writes=[],times={};
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.route('**/api/**',async route=>{const r=route.request();if(!['GET','HEAD','OPTIONS'].includes(r.method())){writes.push(new URL(r.url()).pathname);await route.abort();}
   else if(r.url().includes('/api/invoice-workbench/invoices?'))await route.fulfill({json:data});else await route.continue();});
  await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all',pending:true,scope_version:2})));
  let t=Date.now();await page.goto(base);await page.locator('#nav [data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor();times.openMs=Date.now()-t;
  await page.locator('.invoice-lines-card .tdp-open-sheet').click();
  const wrap=page.locator('.invoice-lines-card .invoice-lines-scroll');assert((await wrap.locator('tbody tr').count())<=82);
  const first=wrap.locator('.invoice-mapping-input').first();t=Date.now();await first.pressSequentially('dam',{delay:50});await first.fill('dấm Bình Dương');assert.equal(await first.inputValue(),'dấm Bình Dương');times.typeMs=Date.now()-t;assert(times.typeMs<2000);
  const next=wrap.locator('.invoice-mapping-input').nth(1);await next.fill('miến dong');assert.equal(await next.inputValue(),'miến dong');
  for(const ratio of [.5,1,0]){t=Date.now();await wrap.evaluate((e,r)=>e.scrollTop=(e.scrollHeight-e.clientHeight)*r,ratio);await page.waitForTimeout(150);times['scroll'+ratio]=Date.now()-t;assert((await wrap.locator('tbody tr').count())<=82);}
  assert.equal(await first.inputValue(),'dấm Bình Dương');assert.equal(await next.inputValue(),'miến dong');
  await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'real-pending-1920.png')});
  await page.setViewportSize({width:1024,height:700});await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'real-pending-1024.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  fs.writeFileSync(path.join(process.env.TDP_FIXTURE_OUTPUT,'result-detail.json'),JSON.stringify({ok:true,invoices:data.items.length,lines:data.lines.length,times,errors,writes},null,2));console.log(JSON.stringify({ok:true,lines:data.lines.length,times}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message.split('Call log:')[0]);process.exitCode=1;});
