const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.env.TDP_INVOICE_TEST_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}});
 const errors=[],report={};let engineRequests=0,release,appReleased=false;
 page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.route('**/static/app.js?**',async route=>{await new Promise(r=>setTimeout(r,1800));appReleased=true;await route.continue();});
  await page.route('**/worksheet-bundle/worksheet.js?**',async route=>{
   engineRequests++;
   if(engineRequests===1)return route.fulfill({status:503,body:'Simulated download failure'});
   await new Promise(r=>{release=r;});await route.continue();
  });
  await page.goto(base,{waitUntil:'commit'});await page.locator('#sidebar').waitFor();
  report.earlySidebarHeight=await page.locator('#sidebar').evaluate(e=>e.getBoundingClientRect().height);
  assert.equal(report.earlySidebarHeight,42);assert.equal(engineRequests,0);
  assert.equal(appReleased,false,'The compact layout is already applied before app.js can run');
  assert.equal(await page.locator('head link[href*="workspace-layout.css"]').count(),1);
  await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'before-app-ready.png')});
  await page.locator('#content .home-work-date').waitFor({timeout:10000}).catch(()=>page.waitForFunction(()=>document.querySelector('#content')?.textContent.length>300));
  assert.equal(engineRequests,0,'Opening home must not fetch the Excel engine');
  await page.locator('#nav [data-view=settings]').click();await page.locator('#catalogProducts .tdp-open-sheet').waitFor();
  await page.locator('#catalogProducts .tdp-open-sheet').click();await page.locator('.worksheet-load-retry').waitFor();assert.equal(engineRequests,1);
  await page.locator('.worksheet-load-retry').click();await page.waitForFunction(()=>document.querySelector('.worksheet-loading-dialog p')?.textContent.includes('Đang mở'));
  while(!release)await page.waitForTimeout(20);
  await page.keyboard.press('Escape');release();await page.waitForTimeout(1000);
  assert.equal(await page.locator('.tdp-sheet-shell').count(),0,'Canceled loading must not open Excel later');
  await page.locator('#catalogProducts .tdp-open-sheet').click();await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.includes('Đã tải'));
  assert.equal(engineRequests,2);assert.equal(await page.locator('.tdp-sheet-shell').count(),1);
  await page.locator('.tdp-sheet-close').click();await page.locator('#catalogProducts .tdp-open-sheet').click();await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.includes('Đã tải'));assert.equal(engineRequests,2);
  await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'excel-ready.png')});assert.deepEqual(errors,[]);
  report.ok=true;report.engineRequests=engineRequests;report.checks=['Compact layout before slow app.js completes','No engine request on home','Download failure/retry','Cancel before delayed download completes','Native Excel opens once and reuses loaded engine'];
  fs.writeFileSync(path.join(process.env.TDP_FIXTURE_OUTPUT,'details.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message.split('Call log:')[0]);process.exitCode=1;});
