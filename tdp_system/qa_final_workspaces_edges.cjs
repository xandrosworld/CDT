// Acceptance checks for the September 2026 customer snapshot. See FINAL_SIX_ITEMS.md.
const fs=require('fs'),assert=require('assert/strict');
const privateRoot=process.env.TDP_QA_PRIVATE_ROOT || 'D:/TDP_RAILWAY_PRIVATE';
process.env.TEMP=process.env.TMP='D:/CodexTemp/final-items-edges';fs.mkdirSync(process.env.TEMP,{recursive:true});
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1500,height:1050},acceptDownloads:true});page.setDefaultTimeout(60000);
 const base='http://127.0.0.1:5094',out=privateRoot+'/final_items_edges';fs.mkdirSync(out,{recursive:true});
 const errors=[],report={base,source:'isolated production snapshot',checks:[]};page.on('pageerror',e=>errors.push(e.message));
 const nav=async view=>{await page.locator('#nav [data-view='+view+']').click();await page.waitForLoadState('networkidle');};
 const settle=async()=>{await page.waitForLoadState('networkidle');await page.locator('.receivable-account-table[aria-busy=false]').waitFor();await page.waitForFunction(()=>!document.querySelector('#content').innerText.includes('Đang nạp'));};
 try{
  await page.goto(base);await page.locator('#batchSelect option[value="2"]').waitFor({state:'attached'});await page.locator('#batchSelect').selectOption('2');
  await nav('debts');await settle();
  const range=page.locator('#debtPeriodForm');await range.locator('[name=from]').fill('2026-09-01');await range.locator('[name=to]').fill('2026-09-13');await range.locator('[type=submit]').click();await settle();
  const payload=await (await page.request.get(base+'/api/debts?from=2026-09-01&to=2026-09-13')).json();
  const closing=await page.locator('.receivable-account-table tfoot td').last().textContent();
  assert.equal(Number(closing.replace(/[^0-9-]/g,'')),Object.values(payload.contractors).reduce((s,r)=>s+r.closing,0));report.checks.push('all-contractor total equals server accounts');
  await page.locator('#receivableContractor').selectOption('ATV');await page.locator('#receivableFilterForm [type=submit]').click();await settle();
  const values=await page.locator('.receivable-kitchen-table tbody tr td:last-child').allTextContents();
  assert.equal(values.reduce((s,t)=>s+Number(t.replace(/[^0-9-]/g,'')),0),payload.contractors.ATV.period_charge);report.checks.push('all kitchens reconcile with contractor charge');
  await page.locator('[data-action=toggle-receivable-details]').click();await page.locator('[data-action=toggle-receivable-history]').first().click();await page.locator('.receivable-revision-panel').waitFor();report.checks.push('line history remains accessible');
  await page.locator('[data-action=toggle-receivable-details]').click();await page.locator('[data-action=open-payment-request]').click();await page.waitForLoadState('networkidle');
  const buyer=page.locator('#buyerProfileForm');await buyer.waitFor({state:'attached'});assert((await buyer.locator('[name=legal_name]').inputValue()).length>0);assert((await buyer.locator('[name=tax_code]').inputValue()).length>0);report.checks.push('buyer profile loaded when entered directly from debts');
  async function delayedScope(work){
    let arrived,release;const ready=new Promise(r=>arrived=r),gate=new Promise(r=>release=r);
    await page.route('**/api/outgoing-invoices/payment-scope/**',async route=>{const response=await route.fetch();arrived();await gate;await route.fulfill({response});},{times:1});
    await page.locator('#paymentRequestForm [type=submit]').click();await ready;await work();release();await page.waitForLoadState('networkidle');
  }
  await delayedScope(async()=>{await page.locator('#paymentRequestForm [name=contractor]').selectOption('');});
  assert.equal(await page.locator('[data-action=download-invoice-payment-control]').count(),0);assert.equal(await page.locator('#paymentRequestForm [name=contractor]').inputValue(),'');report.checks.push('late scope ignored after contractor changes');
  await page.locator('#paymentRequestForm [name=contractor]').selectOption('ATV');
  await delayedScope(async()=>{await page.locator('#nav [data-view=home]').click();});
  assert.equal(await page.locator('body').getAttribute('data-workspace-view'),'home');assert.equal(await page.locator('#paymentDocumentPreview').count(),0);report.checks.push('late scope cannot replace another workspace');
  await nav('documents');await page.waitForLoadState('networkidle');
  const zip=page.locator('#invoiceZipCard [data-action=download-document]').first();
  if(await zip.count()){
    const response=await page.request.get(base+await zip.getAttribute('data-url'));
    report.invoice_zip_status=response.status();
    if(response.status()===200){fs.writeFileSync(out+'/13_EXISTING_INVOICE_DRAFTS.zip',await response.body());report.checks.push('existing real drafts export ZIP');}
    else{
      report.invoice_zip_business_error=await response.json();await zip.click();await page.locator('#invoiceZipCard .error-summary').waitFor();
      assert(await page.locator('#unissuedForm button[value=template]').isEnabled());report.checks.push('blocked draft export explains cause without disabling other exports');
    }
  }
  const form=page.locator('#orderInvoiceExportForm');await form.locator('[name=contractor]').selectOption('ATV');await form.locator('[name=to]').fill('2026-09-13');
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/export/order-invoices')&&r.request().method()==='POST');await form.locator('button[value=export]').click();
  const result=await pending;report.order_export_status=result.status();
  if(result.status()===200){fs.writeFileSync(out+'/13_ELIGIBLE_SOURCE_EXPORT.zip',await result.body());report.checks.push('eligible M-Invoice export executes on isolated real data');}
  else {assert.equal(result.status(),409);report.order_export_block=await result.json();report.checks.push('no eligible remainder cannot create a duplicate invoice');}
  await page.waitForLoadState('networkidle');
  const after=await (await page.request.get(base+'/api/debts?from=2026-09-01&to=2026-09-13')).json();assert.deepEqual(after.contractors,payload.contractors);report.checks.push('invoice draft export adds no revenue or receivables');
  assert.deepEqual(errors,[]);report.ok=true;fs.writeFileSync(out+'/EDGE_VERIFIED.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }catch(e){await page.screenshot({path:out+'/ERROR.png',animations:'disabled'});fs.writeFileSync(out+'/PARTIAL.json',JSON.stringify(report,null,2));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
