// Run against browser_fixture_documents_resolution only; refuses other hosts.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_PATH || 'C:/Users/DELL/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const base='http://127.0.0.1:18801',out=path.join(__dirname,'exports','documents_resolution_test');
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1500,height:1000}});page.setDefaultTimeout(15000);
 const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.route('**/*',r=>{
  const u=new URL(r.request().url());
  if(u.hostname!=='127.0.0.1'){return r.abort();}
  if(r.request().method()==='POST')requests.push(u.pathname);
  return r.continue();
 });
 try{
  await page.goto(base);await page.locator('#batchSelect option').waitFor({state:'attached'});
  const batch=await page.locator('#batchSelect').inputValue();
  await page.locator('#nav [data-view=documents]').click();
  await page.locator('#outgoing-stock-blocks').waitFor();
  assert.equal(await page.locator('[data-action=show-stock-cause]').count(),7);
  assert.equal(await page.getByRole('button',{name:'Cần duyệt đơn trước',exact:true}).isDisabled(),true);
  assert.equal(await page.getByText('Có thể lập bây giờ',{exact:true}).count(),0);
  const totals=await page.locator('.readiness-totals').innerText();
  assert(totals.includes('kg')&&totals.includes('chai'));
  await page.screenshot({path:path.join(out,'01_seven_blockers.png'),fullPage:true});
  await page.locator('[data-action=show-stock-cause][data-code="TEST-1"]').click();
  await page.locator('[data-stock-source]').first().click();
  await page.locator('[data-action=return-stock-resolution]').waitFor();
  await page.locator('.invoice-just-saved').waitFor();
  assert((await page.locator('.invoice-just-saved').innerText()).includes('TEST-1'));
  await page.locator('[data-action=return-stock-resolution]').click();
  await page.locator('#outgoing-stock-blocks').waitFor();
  for(let i=1;i<=7;i++){
   await page.locator('[data-action=show-stock-cause][data-code="TEST-'+i+'"]').click();
   const dialog=page.locator('.stock-cause-dialog');
   await dialog.getByRole('button',{name:'Sửa tồn đầu',exact:true}).click();
   await dialog.locator('input[name=qty]').fill('3');
   const saved=page.waitForResponse(r=>r.url().endsWith('/api/inventory/opening')&&r.request().method()==='POST');
   await dialog.getByRole('button',{name:'Lưu tồn đầu',exact:true}).click();
   assert.equal((await saved).status(),200);
   await dialog.locator('.ok-summary').waitFor();
   await dialog.getByRole('button',{name:'Quay lại',exact:true}).click();
   assert.equal(await page.locator('[data-action=show-stock-cause]').count(),7-i);
  }
  assert.equal((await (await page.request.get(base+'/api/outgoing-invoices/readiness/'+batch)).json()).blocking_issues.length,0);
  await page.locator('.invoice-readiness [data-view=orders]').click();
  const approve=page.locator('[data-action=approve-batch]');
  assert.equal(await approve.isEnabled(),true);
  const approved=page.waitForResponse(r=>r.url().endsWith('/approve')&&r.request().method()==='POST');
  await approve.click();assert.equal((await approved).status(),200);
  await page.locator('#nav [data-view=documents]').click();
  const create=page.locator('[data-action=create-outgoing-drafts]');
  await create.waitFor();assert.equal(await create.isEnabled(),true);
  const created=page.waitForResponse(r=>r.url().includes('/outgoing-invoices/draft/')&&r.request().method()==='POST');
  await create.click();assert.equal((await created).status(),200);
  await page.getByRole('button',{name:'Tải ZIP hóa đơn',exact:true}).waitFor();
  await page.route('**/api/export/invoices/*',r=>r.fulfill({status:409,contentType:'application/json',body:JSON.stringify({ok:false,error:'Dữ liệu vừa thay đổi. Kiểm tra lại trước khi tải.'})}),{times:1});
  await page.getByRole('button',{name:'Tải ZIP hóa đơn',exact:true}).click();
  await page.locator('[role=alert]').filter({hasText:'Dữ liệu vừa thay đổi'}).waitFor();
  await page.locator('[role=alert] [data-action=refresh-outgoing-readiness]').click();
  await page.getByRole('button',{name:'Tải ZIP hóa đơn',exact:true}).waitFor();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'Tải ZIP hóa đơn',exact:true}).click();
  await (await download).saveAs(path.join(out,'synthetic_invoice_files.zip'));
  const initial=await (await page.request.get(base+'/api/outgoing-invoices/readiness/'+batch)).json();
  assert.equal(initial.pending_qty,0);assert.equal(initial.drafted_qty,14);
  const recalculated=page.waitForResponse(r=>r.url().includes('/outgoing-invoices/draft/')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Tính lại dự thảo',exact:true}).click();assert.equal((await recalculated).status(),200);
  const after=await (await page.request.get(base+'/api/outgoing-invoices/readiness/'+batch)).json();
  assert.equal(after.drafted_qty,14);assert.equal(after.drafted_value,280);
  const cancelled=page.waitForResponse(r=>r.url().endsWith('/cancel')&&r.request().method()==='POST');
  await page.locator('[data-action=cancel-outgoing-draft]').click();assert.equal((await cancelled).status(),200);
  await page.getByRole('button',{name:'Tạo file tải hóa đơn',exact:true}).waitFor();
  const released=await (await page.request.get(base+'/api/outgoing-invoices/readiness/'+batch)).json();
  assert.equal(released.drafted_qty,0);assert.equal(released.invoiceable_qty,14);
  const recreated=page.waitForResponse(r=>r.url().includes('/outgoing-invoices/draft/')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Tạo file tải hóa đơn',exact:true}).click();assert.equal((await recreated).status(),200);
  await page.screenshot({path:path.join(out,'02_export_ready.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  assert(!requests.some(p=>p.includes('minvoice')||p.includes('confirm-issued')));
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({ok:true,seven_openings_corrected:true,source_navigation:true,movement_opening_edit:true,approved:true,downloaded:true,recalculate_stable:true,cancel_releases_stock:true,errors,requests},null,2));
  console.log('PASS: seven errors corrected via UI, approval, draft, ZIP download, recalculate; synthetic DB only.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
