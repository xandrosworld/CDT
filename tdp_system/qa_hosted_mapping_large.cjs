// Login and exercise unsaved edits only. Never submit mapping or inventory writes.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const [credentialsFile,output]=process.argv.slice(2),base='https://tdp.up.railway.app';
(async()=>{
 fs.mkdirSync(output,{recursive:true});const credentials=JSON.parse(fs.readFileSync(credentialsFile,'utf8'));
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1920,height:900}});
 const report={started:new Date().toISOString(),errors:[],blocked:[],serverErrors:[],checks:[],times:{}};
 page.on('pageerror',e=>report.errors.push(e.message));page.on('response',r=>{if(r.status()>=500)report.serverErrors.push({path:new URL(r.url()).pathname,status:r.status()});});
 try{
  await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all',pending:true,scope_version:2})));
  await page.goto(base+'/login');await page.locator('[name=username]').fill(credentials.username);await page.locator('[name=password]').fill(credentials.password);await page.locator('button[type=submit]').click();await page.waitForURL(u=>u.pathname!='/login');
  await page.route('**/api/**',async route=>{const r=route.request();if(!['GET','HEAD','OPTIONS'].includes(r.method())){report.blocked.push({method:r.method(),path:new URL(r.url()).pathname});await route.abort();}else await route.continue();});
  const listing=page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?'),{timeout:90000});let t=Date.now();
  await page.locator('#nav [data-view=msmi]').click();assert.equal((await listing).status(),200);await page.locator('#invoice-list-count').waitFor({timeout:90000});report.times.openMs=Date.now()-t;
  report.visibleCounts=await page.locator('#invoice-list-count').innerText();assert.match(report.visibleCounts,/23\.\d{3} dòng hàng/);
  const scroll=page.locator('.invoice-lines-card .invoice-lines-scroll');assert((await scroll.locator('tbody tr').count())<=82);
  await page.locator('.invoice-lines-card .tdp-open-sheet').click();
  const fields=scroll.locator('.invoice-mapping-input'),firstId=await fields.first().getAttribute('id'),secondId=await fields.nth(1).getAttribute('id');
  const first=page.locator('#'+firstId),second=page.locator('#'+secondId);
  t=Date.now();await first.pressSequentially('dam',{delay:50});await first.fill('dấm');assert.equal(await first.inputValue(),'dấm');report.times.typeMs=Date.now()-t;assert(report.times.typeMs<2500);
  await page.locator('#msmiProductOptions [data-product-code]').first().waitFor({timeout:20000});
  const chosen=await page.locator('#msmiProductOptions [data-product-code]').first().getAttribute('data-product-code');await page.locator('#msmiProductOptions [data-product-code]').first().click();assert.equal(await first.inputValue(),chosen);
  await second.fill('miến dong');assert.equal(await second.inputValue(),'miến dong');
  const firstRow=first.locator('xpath=ancestor::tr'),firstRowId=await firstRow.getAttribute('id');await firstRow.locator('.invoice-group-select').check();
  report.checks.push('Type Vietnamese, actual server suggestions, choose code without saving, edit next row, tick row');
  const top=await scroll.evaluate(e=>e.scrollTop);
  for(const ratio of [.5,1]){await scroll.evaluate((e,r)=>e.scrollTop=(e.scrollHeight-e.clientHeight)*r,ratio);await page.waitForTimeout(200);assert((await scroll.locator('tbody tr').count())<=82);}
  await scroll.evaluate((e,y)=>e.scrollTop=y,top);await page.waitForTimeout(200);assert.equal(await first.inputValue(),chosen);assert.equal(await second.inputValue(),'miến dong');assert(await page.locator('#'+firstRowId+' .invoice-group-select').isChecked());
  await page.screenshot({path:path.join(output,'pending-1920.png')});
  const target='Bánh đa nem';
  await page.keyboard.press('Control+f');await page.locator('.tdp-table-search input').fill(target);await page.locator('.tdp-table-search input').press('Enter');await page.waitForTimeout(300);assert.match(await page.locator('.tdp-search-result').innerText(),/\d+ \/ \d+/);
  report.checks.push('Scroll middle/end; restore both drafts and tick; Ctrl+F searches beyond mounted rows');
  await page.setViewportSize({width:1024,height:700});await page.screenshot({path:path.join(output,'pending-1024.png')});
  await page.getByRole('button',{name:'Đóng toàn màn hình',exact:true}).click();await page.locator('.invoice-lines-card .tdp-open-sheet').click();
  assert(await page.locator('.invoice-scope-label').isVisible());
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.blocked,[]);assert.deepEqual(report.serverErrors,[]);report.ok=true;
 }catch(e){report.ok=false;report.failure=e.message.split('Call log:')[0];await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});process.exitCode=1;}
 finally{report.finished=new Date().toISOString();fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify(report));}
})().catch(e=>{console.error(e.message.split('Call log:')[0]);process.exitCode=1;});
