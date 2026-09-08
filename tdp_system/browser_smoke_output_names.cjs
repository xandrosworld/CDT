const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}});
 const base=process.env.TDP_INVOICE_TEST_URL,errors=[],writes=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
 const get=async p=>(await page.request.get(base+p)).json();
 const api='/api/invoice-workbench/invoices?invoice_type=output&from=2026-08-01&to=2026-08-31';
 try{
  await page.addInitScript(()=>localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'output',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all',scope_version:2})));
  await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});
  await page.locator('[data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor();
  const ids=(await get('/fixture/ids')).output_name_lines,before=await get(api);
  const cell=key=>page.locator('#invoice-line-output-'+ids[key]+' td').nth(2);
  assert.equal(await cell('blank').innerText(),'Chưa ghép');assert.equal(await cell('coded').innerText(),'R1-KG');
  assert.match(await cell('blank').getAttribute('title'),/Không có/);
  const blocked=page.locator('#invoice-line-output-'+ids.blocked);
  assert.equal(await cell('blocked').innerText(),'Chờ kiểm tra HĐ');
  assert.match(await blocked.innerText(),/Hóa đơn cần kiểm tra/);
  assert.match(await blocked.innerText(),/1.938.000 đ.*2.058.000 đ/);
  assert.match(await blocked.innerText(),/Mã trên hóa đơn gốc: R1-KG/);
  assert.equal(await blocked.locator('.invoice-mapping-input').count(),0);
  const button=page.locator('[data-action=match-output-catalog-codes]');
  await page.route('**/api/invoice-workbench/output-match-codes',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'Thử lỗi mạng'})}));
  await button.click();await page.waitForFunction(()=>!document.querySelector('[data-action=match-output-catalog-codes]').disabled);
  assert.equal(await cell('blank').innerText(),'Chưa ghép');await page.unroute('**/api/invoice-workbench/output-match-codes');
  const matched=page.waitForResponse(r=>r.url().endsWith('/output-match-codes'));await button.click();assert.equal((await matched).status(),200);
  await page.waitForFunction(id=>document.querySelector('#invoice-line-output-'+id+' td:nth-child(3)')?.textContent==='R1-KG',ids.blank);
  assert.equal(await cell('coded').innerText(),'R1-KG');assert.equal(await cell('alias').innerText(),'ALIAS');assert.equal(await cell('ambiguous').innerText(),'Chưa ghép');
  const after=await get(api);
  for(const old of before.lines){const current=after.lines.find(r=>r.id===old.id);for(const key of ['source_item_code','source_item_name','source_unit','qty','unit_price','amount'])assert.equal(current[key],old[key]);}
  assert.equal(after.totals.line_amount,before.totals.line_amount);assert(after.items.every(i=>i.stock_status!=='posted'));
  await page.reload();await page.locator('[data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor();
  assert.equal(await cell('blank').innerText(),'R1-KG');
  assert.match(await blocked.innerText(),/Hóa đơn cần kiểm tra/);
  await page.screenshot({path:path.join(process.env.TDP_FIXTURE_OUTPUT,'output-names.png')});
  assert.deepEqual(errors,[]);assert(writes.every(p=>p==='/api/invoice-workbench/output-match-codes'));
  console.log('PASS: same name with/without source code; alias; ambiguous name blocked; network retry; mapped-code display; reload; source amounts unchanged; no stock request');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
