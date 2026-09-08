const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE);
const base=process.env.TDP_ISSUANCE_TEST_URL,out=process.env.TDP_FIXTURE_OUTPUT;
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.setDefaultTimeout(20000);const result={ok:false,errors:[],nativeDialogs:0};
 page.on('pageerror',e=>result.errors.push(e.message));page.on('dialog',async d=>{result.nativeDialogs++;await d.dismiss();});
 const snapshot=async()=> (await page.request.get(base+'/fixture/state')).json();
 try {
  const before=await snapshot();
  await page.clock.setFixedTime(new Date('2026-09-08T17:30:00Z'));
  await page.goto(base);await page.locator('#batchSelect option').first().waitFor({state:'attached'});
  await page.locator('#nav [data-view=documents]').click();
  const create=page.locator('[data-action=create-outgoing-drafts]');await create.waitFor();await create.click();
  const issueButtons=page.locator('[data-action=confirm-outgoing-issued]');await issueButtons.nth(1).waitFor({state:'visible'});
  assert.equal(await issueButtons.count(),2);assert.equal(await page.locator('.document-detail-panel').count(),0);
  const created=await snapshot();assert.equal(created.drafts.length,2);
  await page.screenshot({path:path.join(out,'visible-invoice-actions.png')});
  const zipButton=page.getByRole('button',{name:'Tải ZIP hóa đơn',exact:true});
  let failDownload=true;
  await page.route('**/api/export/invoices/*',async route=>{
   if(failDownload){failDownload=false;return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:'Tồn vừa thay đổi, hãy tính lại.'})});}
   return route.continue();
  });
  await zipButton.click();await page.getByRole('status').filter({hasText:'Tồn vừa thay đổi'}).waitFor();
  assert.equal(page.url(),base+'/');
  let downloadPromise=page.waitForEvent('download');await zipButton.click();let download=await downloadPromise;
  await download.saveAs(path.join(out,'tax-files.zip'));
  await create.click();await page.getByRole('status').filter({hasText:'Đã tạo'}).waitFor();
  assert.deepEqual((await snapshot()).drafts.map(d=>d.id),created.drafts.map(d=>d.id));
  await issueButtons.first().click();let dialog=page.locator('.invoice-issue-dialog');await dialog.waitFor();
  assert.equal(await dialog.locator('[name=invoice_date]').inputValue(),'2026-09-09');
  await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
  assert((await snapshot()).drafts.every(d=>d.status==='draft'));
  await issueButtons.first().click();dialog=page.locator('.invoice-issue-dialog');
  await dialog.locator('[name=invoice_series]').fill('1C26QA');await dialog.locator('[name=invoice_number]').fill('901');
  await dialog.getByRole('button',{name:'Lưu số hóa đơn'}).click();
  await dialog.locator('[role=alert]').filter({hasText:'người mua'}).waitFor();
  assert.equal(await dialog.locator('[name=invoice_number]').inputValue(),'901');
  await dialog.getByRole('button',{name:'Quay lại'}).click();
  await page.locator('[data-action=edit-invoice-buyer]').first().click();
  const form=page.locator('#buyerProfileForm');await form.waitFor({state:'visible'});
  await form.locator('[name=legal_name]').fill('Công ty khách thử');await form.locator('[name=tax_code]').fill('0200000001');
  await form.locator('[name=address]').fill('Địa chỉ kiểm thử');await form.getByRole('button',{name:'Lưu hồ sơ người mua'}).click();
  await page.getByRole('status').filter({hasText:'Đã lưu hồ sơ người mua'}).waitFor();
  for(const number of ['901','902']){
   await issueButtons.first().click();dialog=page.locator('.invoice-issue-dialog');
   await dialog.locator('[name=invoice_series]').fill('1C26QA');await dialog.locator('[name=invoice_number]').fill(number);
   if(number==='901')await page.screenshot({path:path.join(out,'one-issue-form.png')});
   await dialog.getByRole('button',{name:'Lưu số hóa đơn'}).click();await dialog.waitFor({state:'detached'});
   await page.getByRole('status').filter({hasText:'Đã ghi nhận hóa đơn'}).waitFor();
   if(number==='901'){
    await issueButtons.first().waitFor();downloadPromise=page.waitForEvent('download');await zipButton.click();download=await downloadPromise;
    await download.saveAs(path.join(out,'remaining-tax-file.zip'));
   }
  }
  await page.reload();await page.locator('#nav [data-view=documents]').click();
  await page.getByText('1C26QA 902',{exact:false}).waitFor();
  assert.equal(await issueButtons.count(),0);
  const after=await snapshot();assert.deepEqual(after.orders,before.orders);assert.equal(after.ledger_count,before.ledger_count);
  assert(after.drafts.every(d=>d.status==='issued'));assert.equal(after.holds.reduce((n,h)=>n+h.qty,0),10);
  assert.deepEqual(result.errors,[]);assert.equal(result.nativeDialogs,0);
  result.ok=true;result.separateInvoices=2;result.sourceAndLedgerUnchanged=true;
 }catch(e){result.error=e.stack;process.exitCode=1;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}
 finally{fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();}
})();
