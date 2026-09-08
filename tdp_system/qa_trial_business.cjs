// Destructive business QA is restricted to the isolated audit service and its copied DB.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const [privateFolder,output]=process.argv.slice(2);
const base='https://tdp-audit-20260908-audit-20260908.up.railway.app';
const safeError=e=>String(e.message||e).includes('apiRequestContext')?String(e.message||e).split(/\nCall log:/)[0]:String(e.message||e);
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const credentials=JSON.parse(fs.readFileSync(path.join(privateFolder,'access.json'),'utf8'));
 const cases=JSON.parse(fs.readFileSync(path.join(privateFolder,'business-cases.json'),'utf8'));
 const report={base,started:new Date().toISOString(),checks:[],errors:[],requests:[]};
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 await page.context().tracing.start({screenshots:true,snapshots:true});
 page.setDefaultTimeout(45000);
 let caseName='setup';
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('response',r=>{if(r.url().startsWith(base+'/api/'))report.requests.push({case:caseName,method:r.request().method(),path:new URL(r.url()).pathname,status:r.status()});});
 const get=async url=>{for(let attempt=1;attempt<=3;attempt++){try{const r=await page.request.get(base+url,{timeout:90000});assert.equal(r.status(),200,url);return await r.json();}catch(e){if(e.name==='AssertionError'||attempt===3)throw e;(report.readRetries||=[]).push({case:caseName,path:url,attempt,error:safeError(e)});await page.waitForTimeout(400);}}};
 const listing=()=>get('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31');
 const source=d=>d.items.map(i=>({id:i.id,date:i.invoice_date,subtotal:i.subtotal,tax:i.tax_amount,total:i.total_amount,
   rows:i.items.map(r=>({id:r.id,code:r.source_item_code,name:r.source_item_name,unit:r.source_unit,qty:r.qty,price:r.unit_price,amount:r.amount}))})).sort((a,b)=>a.id-b.id);
 const row=id=>page.locator('#invoice-line-input-'+id);
 const saved=async(action)=>{const response=page.waitForResponse(r=>r.request().method()==='PUT'&&/\/(mapping|conversion)$/.test(r.url()));await action();assert.equal((await response).status(),200);await page.waitForFunction(()=>!document.querySelector('.invoice-mapping-cell[data-editing-id]'));};
 const record=async(name,fn)=>{if(process.env.TDP_TRIAL_CASES&&!process.env.TDP_TRIAL_CASES.split(',').includes(name))return;caseName=name;console.log('START '+name);await page.setExtraHTTPHeaders({'X-QA-Case':'real-copy-'+name});try{await fn();report.checks.push({name,ok:true});}catch(e){report.checks.push({name,ok:false,error:safeError(e)});throw e;}finally{try{await page.screenshot({path:path.join(output,name+'.png'),timeout:10000});}catch(e){(report.screenshotErrors||=[]).push({name,error:safeError(e)});}fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2));}};
 async function openReview(id){await row(id).locator('[data-action=view-invoice-receipt-summary]').click();await page.locator('.invoice-review-dialog .review-lines').waitFor();}
 async function group(ids){for(const id of ids)await row(id).locator('.invoice-group-select').check();await page.locator('[data-action=preview-invoice-group]').click();const dialog=page.locator('.invoice-group-dialog');await dialog.locator('.group-confirm:enabled').waitFor();return dialog;}
 try{
   await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'})));
   const loginPage=await page.request.get(base+'/login');
   const csrf=(await loginPage.text()).match(/name="csrf" value="([^"]+)"/)[1];
   const logged=await page.request.post(base+'/login',{form:{username:credentials.username,password:credentials.password,csrf},headers:{Origin:base},timeout:90000});
   assert.equal(logged.status(),200);assert(!new URL(logged.url()).pathname.startsWith('/login'));
   await page.goto(base,{waitUntil:'domcontentloaded'});
   assert.equal((await get('/api/audit/routes')).external_connections_blocked,true);
   if(!process.env.TDP_TRIAL_SKIP_SNAPSHOT){const backup=await page.request.get(base+'/api/backup',{timeout:180000});assert.equal(backup.status(),200);fs.writeFileSync(path.join(output,'before.sqlite3'),await backup.body());}
   else report.snapshot_note='Snapshots captured separately; no per-case HTTP backup';
   const before=await listing();fs.writeFileSync(path.join(output,'before-listing.json'),JSON.stringify(before));
   await page.locator('#nav [data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor();
   await record('fullscreen-reopen-focus',async()=>{
     for(let n=0;n<3;n++){
       await page.locator('.invoice-lines-card .tdp-open-sheet').click();await page.locator('.invoice-mapping-fullscreen-bar').waitFor();
       await page.keyboard.press('Escape');await page.locator('.invoice-mapping-fullscreen-bar').waitFor({state:'detached'});
       assert.equal(await page.locator('.invoice-lines-card .tdp-open-sheet').count(),1);
     }
     await page.locator('.receipt-other-actions > summary').click();await page.locator('[data-action=jump-invoice-issue]').click();
     assert(await page.evaluate(()=>document.activeElement.matches('.invoice-mapping-input,.invoice-draft-factor,input[id^="conversion_"]')));
   });
   await record('real-factor-edit-cancel-save-reload',async()=>{
     const r=row(cases.factor.id);await r.locator('.invoice-draft-factor').fill('0');
     await r.locator('[data-action=save-invoice-mapping],[data-action=save-invoice-conversion]').click();
     assert.equal((await listing()).lines.find(l=>l.id===cases.factor.id).conversion_factor,before.lines.find(l=>l.id===cases.factor.id).conversion_factor);
     await r.locator('.invoice-draft-factor').fill(String(cases.factor.factor));
     await saved(()=>r.locator('[data-action=save-invoice-mapping],[data-action=save-invoice-conversion]').click());
     let line=(await listing()).lines.find(l=>l.id===cases.factor.id);assert.equal(line.stock_qty,cases.factor.qty);
     await r.locator('.invoice-draft-factor').fill('999');await r.locator('.invoice-draft-factor').press('Escape');
     assert.equal((await listing()).lines.find(l=>l.id===cases.factor.id).stock_qty,cases.factor.qty);
     await page.reload();await page.locator('#nav [data-view=msmi]').click();await r.waitFor();assert.equal((await listing()).lines.find(l=>l.id===cases.factor.id).stock_qty,cases.factor.qty);
   });
   for(const c of cases.groups)await record('real-group-'+c.name,async()=>{
     const dialog=await group(c.ids);assert.match(await dialog.locator('.group-result').innerText(),new RegExp(String(c.qty)));
     await dialog.locator('.group-cancel').click();assert(!((await listing()).lines.find(l=>l.id===c.ids[0]).group_id));
     const reopened=await group(c.ids);await reopened.locator('.group-confirm').click();await reopened.waitFor({state:'detached'});
     await row(c.ids[0]).locator('[data-action=split-invoice-group]').waitFor();assert.equal(await row(c.ids[1]).count(),0,'Merged source row is hidden in the workbench');
     let line=(await listing()).lines.find(l=>l.id===c.ids[0]);assert.equal(line.stock_qty,c.qty);assert.equal(line.amount,c.amount);assert(Math.abs(line.stock_unit_price-c.amount/c.qty)<0.00001);
     await row(c.ids[0]).locator('[data-action=split-invoice-group]').click();await row(c.ids[1]).waitFor();
     assert(!(await listing()).lines.find(l=>l.id===c.ids[0]).group_id);
     assert.deepEqual(source(await listing()),source(before));
   });
   await record('real-receipt-cancel-post-retry-trace',async()=>{
     const receipt=page.locator('.receipt-review-dialog'),button=page.locator('[data-action=review-input-receipts]');
     const oldValuation=await get('/api/invoice-valuation?from=2026-08-01&to=2026-08-31');
     await button.click();await receipt.locator('.receipt-confirm').waitFor();await receipt.locator('.receipt-cancel').click();
     assert.equal((await listing()).items.find(i=>i.id===cases.receipt.invoice).receipt_status,'ready');
     await button.click();await receipt.locator('.receipt-confirm').waitFor();await receipt.locator('.receipt-selection-details > summary').click();
     await receipt.locator('.receipt-select-all input').uncheck();assert(await receipt.locator('.receipt-confirm').isDisabled());
     await receipt.locator('tr').filter({hasText:cases.receipt.number}).locator('.receipt-choice').check();
     const request=page.waitForRequest(r=>r.url().endsWith('/input-receipts')&&r.method()==='POST');
     await receipt.locator('.receipt-confirm').click();const posted=await request;const body=posted.postDataJSON();assert.deepEqual(body.items.map(i=>i.id),[cases.receipt.invoice]);
     await receipt.waitFor({state:'detached'});assert.equal((await listing()).items.find(i=>i.id===cases.receipt.invoice).receipt_status,'posted');
     const repeat=await page.request.post(base+'/api/invoice-workbench/input-receipts',{data:body,headers:{Origin:base}});assert.equal(repeat.status(),200);assert.equal((await repeat.json()).already_posted_count,1);
     await page.locator('.invoice-post-result [data-action=view-invoice-stock]').click();await page.locator('#inventoryFrom').waitFor();
     const valuation=await get('/api/invoice-valuation?from=2026-08-01&to=2026-08-31');fs.writeFileSync(path.join(output,'after-receipt-valuation.json'),JSON.stringify(valuation));
     const expected={};for(const line of before.items.find(i=>i.id===cases.receipt.invoice).items){if(line.inventory_eligible)expected[line.product_code]=(expected[line.product_code]||0)+line.stock_qty;}
     for(const [code,qty] of Object.entries(expected)){const old=oldValuation.items.find(i=>i.product_code===code),now=valuation.items.find(i=>i.product_code===code);assert(Math.abs(now.input_qty-(old?.input_qty||0)-qty)<0.000001,code+' received once');}
   });
   await record('inventory-entry-reachable-and-month-blocked',async()=>{
     await page.locator('#nav [data-view=inventory]').click();const panel=page.locator('#inventoryDataTools');await panel.locator(':scope > summary').click();await page.locator('#openingForm').waitFor();
     assert(await page.locator('[data-action=choose-opening-workbook]').isVisible());assert(await page.locator('[data-action=choose-bk-workbook]').isVisible());
     const count=report.requests.filter(r=>['POST','PUT','DELETE'].includes(r.method)).length;
     await page.locator('[data-action=reload-bk-documents]').click();await page.locator('[data-action=open-inventory-close]').click();
     const dialog=page.locator('.inventory-close-dialog');await dialog.locator('#inventoryClosePeriod').waitFor();
     const preview=await get('/api/inventory/month-close/preview?period=2026-08');assert.equal(preview.can_close,false);
     assert(await dialog.locator('[data-action=close-inventory-month]').isDisabled());assert.match(await dialog.innerText(),/4 mã/);
     await dialog.locator('.close-period-dialog').click();assert.equal(report.requests.filter(r=>['POST','PUT','DELETE'].includes(r.method)).length,count);
   });
   assert.deepEqual(source(await listing()),source(before),'Original source invoice quantities/prices/amounts remain unchanged');assert.deepEqual(report.errors,[]);
 }catch(e){report.failure=safeError(e);process.exitCode=1;}finally{
   try{if(!process.env.TDP_TRIAL_SKIP_SNAPSHOT){const after=await page.request.get(base+'/api/backup',{timeout:180000});if(after.status()===200)fs.writeFileSync(path.join(output,'after.sqlite3'),await after.body());}}catch(e){report.backupError=safeError(e);}
   report.finished=new Date().toISOString();report.ok=!report.failure&&!report.errors.length;fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2));
   await page.context().tracing.stop({path:path.join(output,'trace.zip')});
   console.log(JSON.stringify({ok:report.ok,checks:report.checks,failure:report.failure,errors:report.errors}));await browser.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
