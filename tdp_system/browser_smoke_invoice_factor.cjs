// Use a fresh browser_fixture_date_picker_server.py, or the compatible local invoice fixture.
const assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],writes=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.method()==='PUT' && /\/(mapping|conversion)$/.test(r.url()))writes.push(r.postDataJSON());});
 const base=process.env.TDP_INVOICE_TEST_URL || 'http://127.0.0.1:18805';
 const get=async p=>(await page.request.get(base+p)).json();
 try{
 await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all'})));
 await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});
 await page.locator('[data-view="msmi"]').click();await page.locator('#invoice-list-count').waitFor();
 const ids=await get('/fixture/ids'),row=page.locator('#invoice-line-input-'+ids.line_b);
 const factor=row.locator('.invoice-draft-factor'),code=row.locator('.invoice-mapping-input');
 assert(await factor.isEnabled());await factor.click();await factor.fill('0,5');
 await row.getByRole('button',{name:'Lưu',exact:true}).click();assert.equal(writes.length,0);
 async function choose(r,value){await r.locator('.invoice-mapping-input').fill(value);await page.locator('#msmiProductOptions [data-product-code="'+value+'"]').click();}
 await code.fill('R1-CAI');assert.equal(await factor.inputValue(),'0,5');
 await row.getByRole('button',{name:'Lưu',exact:true}).click();assert.equal(writes.length,0);
 await page.locator('#msmiProductOptions [data-product-code="R1-CAI"]').click();assert.equal(await factor.inputValue(),'0,5');
 await choose(row,'R1-CAI');assert.equal(await factor.inputValue(),'0,5','Reselecting same code retains typed factor');
 await choose(row,'R1-KG');assert.equal(await factor.inputValue(),'1','Changing product resets factor to its own default');
 await factor.press('Escape');assert(await factor.isEnabled());assert.equal(await factor.inputValue(),'');
 await choose(row,'R1-CAI');assert(await factor.isEnabled());assert.equal(await factor.inputValue(),'');
 await factor.fill('0');await row.getByRole('button',{name:'Lưu',exact:true}).click();assert.equal(writes.length,0);
 await factor.fill('0,5');let saved=page.waitForResponse(r=>r.url().endsWith('/mapping')&&r.request().method()==='PUT');
 await factor.press('Enter');assert.equal((await saved).status(),200);await page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?'));
 let data=await get('/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31');assert.equal(data.lines.find(r=>r.id===ids.line_b).conversion_factor,0.5);
 const posted=data.lines.find(r=>r.invoice_id===ids.input_ids['1']);assert.equal(await page.locator('#invoice-line-input-'+posted.id+' .invoice-draft-factor').count(),0);
 await page.getByRole('tab',{name:'Hóa đơn đầu ra'}).click();await page.locator('#invoice-line-output-'+ids.output_line).waitFor();
 const out=page.locator('#invoice-line-output-'+ids.output_line),outFactor=out.locator('.invoice-draft-factor');
 assert.equal(await outFactor.count(),0);await choose(out,'R1-CAI');
 saved=page.waitForResponse(r=>r.url().endsWith('/mapping')&&r.request().method()==='PUT');await out.getByRole('button',{name:'Lưu',exact:true}).click();assert.equal((await saved).status(),200);
 data=await get('/api/invoice-workbench/invoices?invoice_type=output&from=2026-08-01&to=2026-08-31');assert.equal(data.lines.find(r=>r.id===ids.output_line).conversion_factor,null);assert.equal(data.lines.find(r=>r.id===ids.output_line).mapping_status,'unit_review');
 assert.deepEqual(errors,[]);console.log('PASS: factor-first/code-first, preserve draft, product-change defaults, no-code/invalid blocked, Escape, input/output save, posted locked');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
