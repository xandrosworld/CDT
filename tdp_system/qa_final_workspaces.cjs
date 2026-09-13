// Acceptance checks for the September 2026 customer snapshot. See FINAL_SIX_ITEMS.md.
const fs=require('fs'),assert=require('assert/strict');
const privateRoot=process.env.TDP_QA_PRIVATE_ROOT || 'D:/TDP_RAILWAY_PRIVATE';
process.env.TEMP=process.env.TMP='D:/CodexTemp/four-items-browser';fs.mkdirSync(process.env.TEMP,{recursive:true});
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:5094',live=base==='https://tdp.up.railway.app';
 assert(live||base==='http://127.0.0.1:5094');
 const out=privateRoot+'/final_items_'+(live?'railway':'browser_local');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1500,height:1050},acceptDownloads:true});page.setDefaultTimeout(60000);
 const errors=[],report={base,live,checked_at:new Date().toISOString()};page.on('pageerror',e=>errors.push(e.message));
 const json=async url=>{const r=await page.request.get(base+url);assert.equal(r.status(),200);return r.json();};
 const capture=async name=>{await page.locator('#toast.show').waitFor({state:'hidden',timeout:15000});if(!await page.locator('.tdp-sheet-shell').count())await page.evaluate(()=>window.scrollBy(0,-95));await page.screenshot({path:out+'/'+name+'.png',animations:'disabled'});};
 const download=async(button,name)=>{const pending=page.waitForEvent('download',{timeout:240000});await button.click();const d=await pending;await d.saveAs(out+'/'+name);return d.suggestedFilename();};
 async function nav(view){await page.locator('#nav [data-view='+view+']').click();await page.waitForLoadState('networkidle');}
 async function settledDebt(){await page.waitForFunction(()=>!document.querySelector('#content')?.innerText.includes('Đang nạp'));await page.waitForLoadState('networkidle');}
 async function section(code){
   await page.locator('[data-action=open-debt-section][data-section='+ (code.startsWith('receivable')?'receivable':code)+']').click();
   await settledDebt();
 }
 const tableNumbers=async selector=>page.locator(selector+' tbody tr').evaluateAll(rows=>rows.map(row=>Array.from(row.cells).map((c,i)=>i<1?c.textContent.trim():Number(c.textContent.replace(/[^0-9-]/g,'')))));

 try{
  if(live){const c=JSON.parse(fs.readFileSync(privateRoot+'/access.json','utf8').replace(/^\uFEFF/,''));
   const login=await page.request.get(base+'/login'),csrf=(await login.text()).match(/name="csrf" value="([^"]+)"/)[1];
   const auth=await page.request.post(base+'/login',{form:{username:c.username,password:c.password,csrf},headers:{Origin:base}});assert.equal(auth.status(),200);}
  await page.goto(base);await page.locator('#batchSelect option[value="2"]').waitFor({state:'attached'});
  await page.locator('#batchSelect').selectOption('2');await nav('debts');await settledDebt();
  assert.equal(await page.locator('#nav [data-view=printing]').count(),0);assert.equal(await page.locator('.debt-section-tabs [data-section]').count(),2);
  assert.equal(await page.locator('[data-action=back-debt-overview],.debt-detail-head,.receivable-stats,.receivable-ledger-table').count(),0);
  assert(!(await page.locator('#batchSelect').isVisible()));assert(!(await page.locator('#pageTitle').isVisible()));
  const range=page.locator('#debtPeriodForm');await range.locator('[name=from]').fill('2026-09-01');await range.locator('[name=to]').fill('2026-09-13');
  const rangeResponse=page.waitForResponse(r=>r.url().includes('/api/debts?from=2026-09-01&to=2026-09-13'));
  await range.locator('button[type=submit]').click();await rangeResponse;await settledDebt();
  await page.locator('#receivableContractor').selectOption('ATV');
  await page.locator('#receivableKitchen').selectOption('LSVINA');
  const filterResponse=page.waitForResponse(r=>r.url().includes('/api/debts/receivables/ledger?')&&r.url().includes('kitchen=LSVINA'));
  await page.locator('#receivableFilterForm button[type=submit]').click();await filterResponse;
  await page.waitForFunction(()=>document.querySelector('#receivableFilteredExport')?.href.includes('kitchen=LSVINA'));
  const link=await page.locator('#receivableFilteredExport').getAttribute('href');
  assert(link.includes('contractor=ATV')&&link.includes('kitchen=LSVINA'));
  report.filtered_url=link;report.ledger=await json('/api/debts/receivables/ledger?from=2026-09-01&to=2026-09-13&contractor=ATV&kitchen=LSVINA&status=active&limit=5000');
  await settledDebt();
  report.debt_accounts=await json('/api/debts?from=2026-09-01&to=2026-09-13');
  const accounts=await tableNumbers('.receivable-account-table');
  assert.equal(accounts.length,1);assert.equal(accounts[0][0],'ATV');assert.equal(accounts[0][5],report.debt_accounts.contractors.ATV.closing);
  const kitchenRows=await page.locator('.receivable-kitchen-table tbody tr').allTextContents();assert.equal(kitchenRows.length,1);assert(kitchenRows[0].includes('LSVINA'));
  assert.equal(Number((await page.locator('.receivable-kitchen-table tbody tr td').last().textContent()).replace(/[^0-9-]/g,'')),report.ledger.summary.charge_amount);
  await page.evaluate(()=>window.scrollTo(0,0));await capture('07_WEB_GOP_CONG_NO_TONG_VA_BEP');
  await capture('12_WEB_BO_KHOI_THUA_GIU_TONG_VA_BO_LOC');
  await page.locator('[data-action=toggle-receivable-details]').click();
  await page.locator('.card').filter({has:page.locator('.receivable-ledger-table')}).locator('.tdp-open-sheet').click();
  await page.locator('.tdp-sheet-shell').waitFor();
  const exportButton=page.locator('.tdp-sheet-download').filter({hasText:'Excel theo bộ lọc'});
  if(!live){
   await page.route('**/api/debts/receivables/lines/export?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Kiểm tra thử tải lại'})}),{times:1});
   await exportButton.click();await page.locator('.tdp-sheet-status.is-error').waitFor();assert(await exportButton.isEnabled());
   report.download_retry=true;
  }
  report.filtered_filename=await download(exportButton,'08_CONG_NO_THEO_BO_LOC.xlsx');
  await page.locator('.tdp-sheet-status').filter({hasText:'Đã tải file'}).waitFor();await capture('08_WEB_TAI_TRONG_TOAN_MAN_HINH');
  await page.locator('.tdp-sheet-close').click();assert.equal(await page.locator('#receivableKitchen').inputValue(),'LSVINA');
  await page.locator('[data-action=toggle-receivable-details]').click();assert.equal(await page.locator('.receivable-ledger-table').count(),0);
  const debtUrl='/api/debts?from=2026-09-01&to=2026-09-13';report.debt_before=await json(debtUrl);
  const form=page.locator('#receiptForm');await form.locator('[name=party_code]').selectOption('ATV');
  await form.evaluate(el=>el.closest('.card').scrollIntoView({block:'center'}));await capture('10_WEB_GHI_NHAN_THANH_TOAN');
  if(!live){
   await form.locator('[name=actor]').fill('Kiểm thử trên bản sao');await form.locator('[name=payment_date]').fill('2026-09-13');
   await form.locator('[name=amount]').fill('1000000');await form.locator('[name=note]').fill('Chỉ kiểm thử bản sao dữ liệu, không phải tiền khách trả thật');
   await page.locator('[data-action=toggle-receivable-details]').click();assert.equal(await form.locator('[name=amount]').inputValue(),'1000000');await page.locator('[data-action=toggle-receivable-details]').click();
   const posted=page.waitForResponse(r=>r.url().endsWith('/api/payments')&&r.request().method()==='POST');
   await form.locator('[type=submit]').click();const response=await posted;assert.equal(response.status(),201);const payment=await response.json();
   await page.waitForLoadState('networkidle');report.debt_after_receipt=await json(debtUrl);
   assert.equal(report.debt_after_receipt.contractors.ATV.closing,report.debt_before.contractors.ATV.closing-1000000);
   const reverse=page.locator('[data-action=reverse-receipt][data-id="'+payment.id+'"]');await reverse.evaluate(el=>el.scrollIntoView({block:'center'}));await capture('10_LOCAL_KHOAN_THU_VA_LICH_SU');
   const answers=['Hoàn tác kiểm thử bản sao','Kiểm thử trên bản sao',null];const dialogs=async d=>{const a=answers.shift();await d.accept(a===null?undefined:a);};page.on('dialog',dialogs);
   const undone=page.waitForResponse(r=>r.url().endsWith('/api/debts/receipts/'+payment.id+'/reverse'));
   await reverse.click();assert.equal((await undone).status(),200);page.off('dialog',dialogs);await page.waitForLoadState('networkidle');
   report.debt_after_reverse=await json(debtUrl);assert.deepEqual(report.debt_after_reverse.contractors,report.debt_before.contractors);
   report.receipt_lifecycle={id:payment.id,amount:1000000,scope:'isolated production snapshot',reversed:true};
  }
  await settledDebt();
  await page.locator('h3').filter({hasText:'Tổng công nợ phải thu'}).evaluate(el=>el.scrollIntoView({block:'start'}));await capture('11_WEB_DOI_CHIEU_SO_THUC_TE');
  await page.locator('.card').filter({has:page.locator('h3').filter({hasText:'Tổng công nợ phải thu'})}).locator('.tdp-open-sheet').click();
  report.debt_filename=await download(page.locator('.tdp-sheet-download').filter({hasText:'Tải đối chiếu tổng công nợ'}),'10_CONG_NO.xlsx');
  await page.locator('.tdp-sheet-close').click();
  await section('payable');await page.evaluate(()=>window.scrollTo(0,0));await capture('09_WEB_CHUYEN_PHAI_THU_PHAI_TRA');
  await page.locator('.payable-workspace .tdp-open-sheet').first().click();
  report.payable_filename=await download(page.locator('.tdp-sheet-download').filter({hasText:'Excel phải trả nhà cung cấp'}),'08_CONG_NO_PHAI_TRA.xlsx');
  await page.locator('.tdp-sheet-close').click();
  await section('receivable');await page.locator('[data-action=open-payment-request]').click();
  assert.equal(await page.locator('#nav .nav-item.active').getAttribute('data-view'),'debts');
  const paymentForm=page.locator('#paymentRequestForm');assert(await paymentForm.isVisible());
  await paymentForm.locator('[name=contractor]').selectOption('ATV');await paymentForm.locator('[name=from]').fill('2026-09-01');await paymentForm.locator('[name=to]').fill('2026-09-13');
  const scopeResponse=page.waitForResponse(r=>r.url().includes('/payment-scope/ATV?'));
  const previewResponse=page.waitForResponse(r=>r.url().endsWith('/api/documents/preview')&&r.request().postDataJSON().kind==='payment');
  await paymentForm.locator('[type=submit]').click();const sr=await scopeResponse;report.payment_scope=await sr.json();assert.equal(sr.status(),200,JSON.stringify(report.payment_scope));
  const pr=await previewResponse;assert.equal(pr.status(),200,await pr.text());report.payment_preview=await pr.json();
  await page.locator('#paymentDocumentPreview .document-scroll table').waitFor();
  report.payment_filename=await download(page.locator('[data-action=download-invoice-payment-control]'),'14_DE_NGHI_THANH_TOAN.zip');
  await page.locator('[data-action=download-invoice-payment-control]').evaluate(el=>el.closest('.card').scrollIntoView({block:'start'}));await capture('14_WEB_DOI_CHIEU_HOA_DON_DA_PHAT_HANH');
  const requestSheet=page.locator('#paymentDocumentPreview [data-open-sheet]').filter({hasText:/đề nghị|thanh toán/i}).last();if(await requestSheet.count())await requestSheet.click();
  await page.locator('#paymentDocumentPreview').evaluate(el=>el.scrollIntoView({block:'start'}));await capture('14_WEB_MAU_DE_NGHI_THANH_TOAN');
  await nav('documents');await page.waitForLoadState('networkidle');
  assert.equal(await page.locator('#content > section.card').count(),3);
  assert.equal(await page.locator('#paymentRequestForm,#purchaseDocumentPreview,.outgoing-readiness').count(),0);
  assert(await page.locator('#orderInvoiceExportForm').isVisible());assert(await page.locator('#unissuedForm').isVisible());assert(await page.locator('#invoiceZipCard').isVisible());
  await page.evaluate(()=>window.scrollTo(0,0));await capture('13_WEB_BANG_KE_CHUA_XUAT_VA_ZIP');
  const zipButtons=page.locator('#invoiceZipCard [data-action=download-document]');report.invoice_zips=[];
  for(let i=0;i<await zipButtons.count();i++){
    const button=zipButtons.nth(i),url=await button.getAttribute('data-url');
    assert(!url.endsWith('/2'),'A consolidated draft must export from its owning batch, not the selected source order');
    const batchId=url.split('/').pop();report.invoice_zips.push({url,label:await button.textContent(),filename:await download(button,'13_ZIP_DU_THAO_NGAY_'+batchId+'.zip')});
  }
  assert(report.invoice_zips.length>0);
  const uf=page.locator('#unissuedForm');await uf.locator('[name=contractor]').selectOption('ATV');await uf.locator('[name=to]').fill('2026-09-13');
  report.unissued_template=await download(uf.locator('button[value=template]'),'13_CHUA_XUAT_DUNG_MAU.zip');
  await page.locator('#invoiceZipCard [data-view=invoice-tools]').click();await page.waitForLoadState('networkidle');
  assert.equal(await page.locator('#nav .nav-item.active').getAttribute('data-view'),'msmi');
  assert(await page.locator('[data-action=toggle-document-details]').isVisible());
  await page.locator('[data-action=toggle-document-details]').click();await page.waitForLoadState('networkidle');
  await page.evaluate(()=>window.scrollTo(0,0));await capture('13_WEB_GIU_CHUC_NANG_XU_LY_HOA_DON');
  await nav('home');await page.locator('[data-action=open-print-workspace][data-document=purchases]').click();await page.waitForLoadState('networkidle');
  assert.equal(await page.locator('#nav .nav-item.active').getAttribute('data-view'),'home');
  assert.equal(await page.locator('.print-type-grid').count(),0);
  await page.locator('#printingFrom').fill('2026-09-04');await page.locator('#printingFrom').press('Tab');await page.waitForLoadState('networkidle');
  await page.locator('#printingTo').fill('2026-09-04');await page.locator('#printingTo').press('Tab');await page.waitForLoadState('networkidle');
  await page.evaluate(()=>window.scrollTo(0,0));await capture('15_WEB_IN_TU_DON_HANG_BANG_KE');
  const receiptResponse=page.waitForResponse(r=>r.url().endsWith('/api/documents/preview')&&r.request().postDataJSON().kind==='purchases');
  await page.locator('[data-action=preview-print-row]').first().click();const rr=await receiptResponse;assert.equal(rr.status(),200,await rr.text());report.receipt_preview=await rr.json();
  const receiptHost=page.locator('#printingPreview');await receiptHost.locator('.document-scroll table').waitFor();
  const sheets=report.receipt_preview.sheets;const receipts=sheets.map((s,i)=>({s,i})).filter(({s})=>/biên nhận/i.test(s.name));assert(receipts.length>=2);
  const selected=[sheets.findIndex(s=>/bảng kê tổng/i.test(s.name)),...receipts.slice(0,2).map(r=>r.i)].filter(i=>i>=0);
  await receiptHost.locator('[data-doc=none]').click();for(const i of selected)await receiptHost.locator('[data-sheet="'+i+'"]').check();
  await receiptHost.locator('.document-sides').selectOption('duplex');report.receipt_selection=selected;
  report.receipt_excel=await download(receiptHost.locator('[data-doc=excel]'),'16_BIEN_NHAN.xlsx');
  if(live){report.receipt_pdf=await download(receiptHost.locator('[data-doc=pdf]'),'16_BIEN_NHAN_HAI_MAT.pdf');}
  await receiptHost.locator('[data-open-sheet="'+receipts[0].i+'"]').click();await receiptHost.evaluate(el=>el.scrollIntoView({block:'start'}));await capture('15_WEB_BAN_IN_BIEN_NHAN_THAT');
  await nav('home');await page.locator('[data-action=open-print-workspace][data-document=deliveries]').click();await page.waitForLoadState('networkidle');
  await page.locator('#printingCustomer').waitFor({state:'visible'});await page.evaluate(()=>window.scrollTo(0,0));await capture('15_WEB_IN_PHIEU_GIAO_TU_DON_HANG');
  await page.locator('.print-workspace-heading [data-view=home]').click();assert.equal(await page.locator('body').getAttribute('data-workspace-view'),'home');
  if(live)assert.deepEqual((await json(debtUrl)).contractors,report.debt_before.contractors);
  assert.equal(errors.length,0,errors.join('\n'));report.browser_errors=errors;report.ok=true;
  fs.writeFileSync(out+'/BROWSER_VERIFIED.json',JSON.stringify(report,null,2));console.log(JSON.stringify({ok:true,base,output:out,receipt_sheets:selected.length,invoice_count:report.payment_scope.invoices.length}));
 }catch(e){await capture('ERROR').catch(()=>{});fs.writeFileSync(out+'/PARTIAL.json',JSON.stringify(report,null,2));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
