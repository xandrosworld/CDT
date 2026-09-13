// Acceptance checks for the September 2026 customer snapshot. See FINAL_SIX_ITEMS.md.
const fs=require('fs'),assert=require('assert/strict');
const privateRoot=process.env.TDP_QA_PRIVATE_ROOT || 'D:/TDP_RAILWAY_PRIVATE';
process.env.TEMP=process.env.TMP='D:/CodexTemp/final-print-browser';fs.mkdirSync(process.env.TEMP,{recursive:true});
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:5094',live=base==='https://tdp.up.railway.app';assert(live||base==='http://127.0.0.1:5094');
 const out=privateRoot+'/final_items_'+(live?'railway':'browser_local');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true}),page=await browser.newPage({viewport:{width:1500,height:1050},acceptDownloads:true});page.setDefaultTimeout(90000);
 const errors=[],report={base,live,checked_at:new Date().toISOString()};page.on('pageerror',e=>errors.push(e.message));
 const capture=async(name,locator)=>{await page.locator('#toast.show').waitFor({state:'hidden'});await locator.evaluate(el=>el.scrollIntoView({block:'start'}));await page.evaluate(()=>window.scrollBy(0,-95));await page.screenshot({path:out+'/'+name+'.png',animations:'disabled'});};
 const download=async(button,name)=>{const pending=page.waitForEvent('download',{timeout:240000});await button.click();const dl=await pending;await dl.saveAs(out+'/'+name);return dl.suggestedFilename();};
 try{
  if(live){const c=JSON.parse(fs.readFileSync(privateRoot+'/access.json','utf8').replace(/^\uFEFF/,''));const login=await page.request.get(base+'/login'),csrf=(await login.text()).match(/name="csrf" value="([^"]+)"/)[1];assert.equal((await page.request.post(base+'/login',{form:{username:c.username,password:c.password,csrf},headers:{Origin:base}})).status(),200);}
  await page.goto(base);await page.locator('#batchSelect option[value="2"]').waitFor({state:'attached'});await page.locator('#batchSelect').selectOption('2');
  await page.locator('#nav [data-view=purchases]').click();await page.locator('#supplierFrom').fill('2026-09-13');await page.waitForLoadState('networkidle');await page.locator('#supplierTo').fill('2026-09-13');
  const supplier=page.locator('.supplier-day[data-batch-id="9"]');await supplier.waitFor();
  const supplierPreview=page.waitForResponse(r=>r.url().endsWith('/api/documents/preview')&&r.request().postDataJSON().kind==='suppliers');await supplier.locator('[data-action=preview-supplier-documents]').click();const sp=await supplierPreview;assert.equal(sp.status(),200,await sp.text());report.supplier=await sp.json();
  const supplierHost=page.locator('#supplierPrintPreview-9');await supplierHost.locator('.document-scroll table').waitFor();
  report.supplier_excel=await download(supplierHost.locator('[data-doc=excel]'),'15_IN_DON_NCC_13_09.xlsx');await capture('15_WEB_IN_NCC_DUNG_NGAY',supplierHost);
  await page.locator('#nav [data-view=reports]').click();await page.locator('#reportFrom').fill('2026-09-04');await page.waitForLoadState('networkidle');
  const range=page.waitForResponse(r=>r.url().includes('/api/reports/summary?from=2026-09-04&to=2026-09-07'));await page.locator('#reportTo').fill('2026-09-07');report.report_data=await (await range).json();
  const reportPreview=page.waitForResponse(r=>r.url().endsWith('/api/documents/preview')&&r.request().postDataJSON().kind==='report');await page.locator('[data-action=preview-report-documents]').click();const rp=await reportPreview;assert.equal(rp.status(),200,await rp.text());report.report=await rp.json();
  assert(report.report.sheets[0].html.includes('04/09/2026')&&report.report.sheets[0].html.includes('07/09/2026'));
  const reportHost=page.locator('#reportDocumentPreview');await reportHost.locator('.document-scroll table').waitFor();
  report.report_excel=await download(reportHost.locator('[data-doc=excel]'),'15_IN_BAO_CAO_04_07.xlsx');
  if(live)report.report_pdf=await download(reportHost.locator('[data-doc=pdf]'),'15_IN_BAO_CAO_04_07.pdf');
  await capture('15_WEB_IN_BAO_CAO_DUNG_KHOANG_NGAY',reportHost);assert.deepEqual(errors,[]);report.ok=true;fs.writeFileSync(out+'/PRINT_VERIFIED.json',JSON.stringify(report,null,2));console.log(JSON.stringify({ok:true,base,supplier_sheets:report.supplier.sheet_count,report_sheets:report.report.sheet_count}));
 }catch(e){await page.screenshot({path:out+'/PRINT_ERROR.png',animations:'disabled'});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
