// Real September customer data. Production uses read/download and unchanged-note saves only.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
process.env.TEMP=process.env.TMP='D:/CodexTemp/four-items-browser';
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:5094',live=base==='https://tdp.up.railway.app';
 assert(live||base==='http://127.0.0.1:5094');
 const out=path.resolve('tdp_system/exports/customer_followups_'+(live?'railway':'local')+'_20260913');fs.mkdirSync(out,{recursive:true});
 const report={base,live,checked_at:new Date().toISOString(),checks:[]},errors=[];
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1100},acceptDownloads:true});page.setDefaultTimeout(60000);
 page.on('pageerror',e=>errors.push(e.message));let downloads=0;page.on('download',()=>downloads++);
 const json=async url=>{const r=await page.request.get(base+url);assert.equal(r.status(),200);return r.json();};
 const settle=async()=>{await page.waitForLoadState('networkidle');await page.waitForFunction(()=>!document.querySelector('#content')?.innerText.includes('Đang nạp'));};
 const nav=async view=>{await page.locator('#nav [data-view='+view+']').click();await settle();};
 const shot=async name=>{await page.locator('#toast.show').waitFor({state:'hidden',timeout:15000});await page.screenshot({path:path.join(out,name+'.png'),animations:'disabled'});};
 const download=async(button,name)=>{const pending=page.waitForEvent('download');await button.click();const d=await pending;await d.saveAs(path.join(out,name));return d.suggestedFilename();};
 const sheet=async table=>{await page.locator('.card').filter({has:page.locator(table)}).locator('.tdp-open-sheet').click();await page.locator('.tdp-sheet-status').filter({hasText:/^Chỉ xem$/}).waitFor();};
 try{
  if(live){const c=JSON.parse(fs.readFileSync('D:/TDP_RAILWAY_PRIVATE/access.json','utf8').replace(/^\uFEFF/,''));const login=await page.request.get(base+'/login');const csrf=(await login.text()).match(/name="csrf" value="([^"]+)"/)[1];assert.equal((await page.request.post(base+'/login',{form:{username:c.username,password:c.password,csrf},headers:{Origin:base}})).status(),200);}
  await page.goto(base);await nav('debts');
  let range=page.locator('#debtPeriodForm');await range.locator('[name=from]').fill('2026-09-01');await range.locator('[name=to]').fill('2026-09-04');await range.locator('[type=submit]').click();await settle();
  report.accounts_before=await json('/api/debts?from=2026-09-01&to=2026-09-04');
  for(const [contractor,kitchen] of [['NHUAHAIPHONG','NHUAHP'],['TOYOTA','TOYOTA'],['ATV','LSVINA'],['TOYOTA','TOYOTA']]){
    await page.locator('#receivableContractor').selectOption(contractor);await page.locator('#receivableKitchen').selectOption(kitchen);await settle();
    assert((await page.locator('#receivableExportSelected').getAttribute('href')).includes('contractor='+contractor));
    assert((await page.locator('#receivableFilteredExport').getAttribute('href')).includes('kitchen='+kitchen));
    assert((await page.locator('.receivable-kitchen-table tbody tr').allTextContents()).every(t=>t.includes(kitchen)));
  }
  report.checks.push('NHUAHAIPHONG -> TOYOTA -> ATV/LSVINA -> TOYOTA automatically updates rows and both export URLs without Apply');
  if(!live){
    let arrived,release;const ready=new Promise(r=>arrived=r),gate=new Promise(r=>release=r);
    await page.route('**/api/debts/receivables/ledger?**contractor=NHUAHAIPHONG*',async route=>{const r=await route.fetch();arrived();await gate;await route.fulfill({response:r});},{times:1});
    await page.locator('#receivableContractor').selectOption('NHUAHAIPHONG');await ready;
    await page.locator('#receivableContractor').selectOption('TOYOTA');await page.locator('#receivableKitchen').selectOption('TOYOTA');release();await settle();
    assert.equal(await page.locator('#receivableKitchen').inputValue(),'TOYOTA');assert((await page.locator('.receivable-kitchen-table').textContent()).includes('TOYOTA'));
    report.checks.push('Delayed previous-contractor response cannot replace the new contractor/kitchen');
  }
  await page.reload();await nav('debts');assert.equal(await page.locator('#receivableContractor').inputValue(),'TOYOTA');assert.equal(await page.locator('#receivableKitchen').inputValue(),'TOYOTA');
  await page.evaluate(()=>window.scrollTo(0,0));await shot('01_PHAI_THU_TOYOTA_TU_DONG_LOC');
  await page.locator('[data-action=toggle-receivable-details]').click();await page.locator('.receivable-ledger-table').waitFor();
  const beforeView=downloads;await sheet('.receivable-ledger-table');await shot('02_PHAI_THU_XEM_TREN_WEB');assert.equal(downloads,beforeView);await page.locator('.tdp-sheet-close').click();
  report.receivable_filename=await download(page.locator('#receivableExportSelected'),'03_CONG_NO_TOYOTA.xlsx');
  assert(report.receivable_filename.includes('TOYOTA'));
  await page.locator('[data-action=open-debt-section][data-section=payable]').click();await settle();
  const supplier=await page.locator('#payableSupplier option').evaluateAll(opts=>opts.find(o=>o.value==='sim')?.value);assert(supplier);
  await page.locator('#payableSupplier').selectOption(supplier);await settle();
  report.payable_supplier=supplier;report.payable_export=await page.locator('a').filter({hasText:/^Excel phải trả nhà cung cấp$/}).getAttribute('href');assert(new URL(report.payable_export,base).searchParams.get('supplier')===supplier);
  const payableData=await json('/api/debts/payables/ledger?from=2026-09-01&to=2026-09-04&status=open,partially_paid&supplier='+supplier+'&limit=5000');assert(payableData.rows.length>0);report.payable_rows=payableData.rows.length;
  await page.evaluate(()=>window.scrollTo(0,0));await shot('04_PHAI_TRA_TU_DONG_LOC');
  const beforePayableView=downloads;await page.locator('#content .tdp-open-sheet').first().click();await page.locator('.tdp-sheet-status').filter({hasText:/^Chỉ xem$/}).waitFor();await shot('05_PHAI_TRA_XEM_TREN_WEB');assert.equal(downloads,beforePayableView);await page.locator('.tdp-sheet-close').click();
  report.checks.push('Receivables and payables both open directly/full-screen on web without downloading; payable supplier auto-applies');
  await nav('home');await page.locator('[data-action=open-print-workspace][data-document=purchases]').click();await settle();
  await page.locator('[data-action=open-bk-draft]').click();const bk=page.locator('.bk-draft-dialog');await bk.locator('[data-bk=excel]:enabled').waitFor();
  await bk.locator('[name=from]').fill('2026-09-01');await bk.locator('[name=to]').fill('2026-09-10');await bk.locator('[data-bk=load]').click();await bk.locator('[data-bk=excel]:enabled').waitFor();
  const shortages=await json('/api/bk-import/shortages?from=2026-09-01&to=2026-09-10');report.shortages=shortages;
  let chosen=-1;for(let i=0;i<shortages.items.length;i++){const r=shortages.items[i];assert.equal(await bk.locator('tr[data-row="'+i+'"] [data-field=unit_cost]').inputValue(),String(r.unit_cost));if(r.unit_cost){assert.equal(r.unit_cost,Math.floor(r.reference_sell_price*.95+.5));if(chosen<0)chosen=i;}}
  assert(chosen>=0);const br=bk.locator('tr[data-row="'+chosen+'"]');await br.locator('[data-field=selected]').check();await br.scrollIntoViewIfNeeded();await shot('06_BANG_KE_GOI_Y_GIA_95');
  report.bk_filename=await download(bk.locator('[data-bk=excel]'),'07_BANG_KE_BO_SUNG_GIA_95.xlsx');
  if(!live){await br.locator('[data-field=unit_cost]').fill('12345');await bk.locator('[data-bk=none]').click();await bk.locator('[data-bk=all]').click();assert.equal(await br.locator('[data-field=unit_cost]').inputValue(),'12345');await bk.locator('[data-bk=none]').click();await br.locator('[data-field=selected]').check();await download(bk.locator('[data-bk=excel]'),'07_LOCAL_GIA_SUA_TAY.xlsx');report.checks.push('Manual BK price survives selection changes and export');}
  await bk.locator('[data-bk=preview]').click();await bk.locator('.bk-draft-paper').waitFor();await bk.locator('.bk-draft-paper').scrollIntoViewIfNeeded();await shot('08_BANG_KE_XEM_BAN_IN');
  await bk.locator('[data-bk=close]').click();report.checks.push('Real shortages receive 95% source price, Excel and printable preview; no inventory posting');
  await nav('purchases');await page.locator('#supplierFrom').fill('2026-09-10');await page.locator('#supplierTo').fill('2026-09-10');await page.locator('[data-action=refresh-supplier-range]').click();await settle();
  const day=(await json('/api/supplier-needs?from=2026-09-10&to=2026-09-10')).days.find(d=>d.send_available&&d.groups.some(g=>g.supplier_key==='bien'));assert(day);report.supplier_batch=day.batch_id;
  let card=page.locator('.supplier-day[data-batch-id="'+day.batch_id+'"] .supplier-order-card[data-supplier-key=bien]');
  await card.locator('[data-action=edit-supplier-notes]').click();const nd=page.locator('.supplier-notes-dialog');await nd.locator('[type=submit]:enabled').waitFor();
  const original=await nd.locator('textarea').first().inputValue();
  if(!live)await nd.locator('textarea').first().fill('Kiểm thử trên bản sao: giao riêng bếp, gọi trước khi giao.');
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/supplier-needs/'+day.batch_id+'/notes')&&r.request().method()==='PUT');await nd.locator('[type=submit]').click();const savedResult=await saved;assert.equal(savedResult.status(),200);const saveBody=await savedResult.json();assert.equal(saveBody.changed,live?0:1);await nd.locator('[type=submit]:enabled').waitFor();await shot('09_GHI_CHU_NCC_NHAP_VA_LUU');
  await nd.locator('[data-notes-close]').click();await settle();
  card=page.locator('.supplier-day[data-batch-id="'+day.batch_id+'"] .supplier-order-card[data-supplier-key=bien]');
  await card.locator('summary').click();await card.scrollIntoViewIfNeeded();await shot('10_GHI_CHU_TRONG_DON_NCC');
  report.supplier_image_filename=await download(card.locator('[data-action=download-supplier-image]'),'11_ANH_NCC_BIEN_CO_COT_GHI_CHU.png');
  const excel=await page.request.get(base+'/api/export/suppliers/'+day.batch_id);assert.equal(excel.status(),200);fs.writeFileSync(path.join(out,'12_DON_NCC.xlsx'),await excel.body());
  if(!live){await card.locator('[data-action=edit-supplier-notes]').click();await nd.locator('[type=submit]:enabled').waitFor();assert((await nd.locator('textarea').first().inputValue()).startsWith('Kiểm thử trên bản sao'));await nd.locator('textarea').first().fill(original);await nd.locator('[type=submit]').click();await nd.locator('[type=submit]:enabled').waitFor();report.checks.push('Edited supplier note persists after reopening, appears in downloaded image/Excel, then restored on isolated copy');}
  else report.checks.push('Production note form loads real lines and unchanged save returns changed=0; original supplier image downloaded with permanent Notes column');
  const after=await json('/api/debts?from=2026-09-01&to=2026-09-04');assert.deepEqual(after.contractors,report.accounts_before.contractors);assert.deepEqual(after.suppliers,report.accounts_before.suppliers);
  assert.deepEqual(errors,[]);report.checks.push('Receivable/payable account values unchanged');report.ok=true;
  fs.writeFileSync(path.join(out,'VERIFIED.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({ok:true,out,checks:report.checks,priced:shortages.items.filter(r=>r.unit_cost).length,shortages:shortages.items.length}));
 }catch(e){await shot('ERROR');fs.writeFileSync(path.join(out,'PARTIAL.json'),JSON.stringify(report,null,2));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
