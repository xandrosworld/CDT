// Read-only browser acceptance on the customer's September data, local copy or Railway.
const fs=require('fs'), path=require('path'), assert=require('assert/strict');
process.env.TEMP=process.env.TMP='D:/CodexTemp/four-items-browser';
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:5094', live=base==='https://tdp.up.railway.app';
 assert(live||base==='http://127.0.0.1:5094');
 const out=path.resolve('tdp_system/exports/debt_preview_'+(live?'railway':'local')+'_20260913');fs.mkdirSync(out,{recursive:true});
 const report={base,live,checked_at:new Date().toISOString(),checks:[]}, errors=[], writes=[];
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1920,height:1080},acceptDownloads:true});
 const page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('pageerror',e=>errors.push(e.message));let downloads=0;page.on('download',()=>downloads++);
 page.on('request',r=>{if(r.url().includes('/api/')&&!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+r.url());});
 const json=async url=>{const r=await page.request.get(base+url);assert.equal(r.status(),200,await r.text());return r.json();};
 const settle=async()=>{await page.waitForLoadState('networkidle');await page.waitForFunction(()=>!document.querySelector('#content')?.innerText.includes('Đang nạp'));};
 const shot=async name=>{await page.locator('#toast.show').waitFor({state:'hidden',timeout:15000});await page.screenshot({path:path.join(out,name+'.png'),animations:'disabled'});};
 const close=async()=>{await page.locator('.tdp-sheet-close').click();await page.locator('.tdp-sheet-shell').waitFor({state:'detached'});};
 const main=()=>page.locator('[data-action=preview-debt-ledger]');
 const open=async(name,pattern)=>{
   const count=downloads;
   const response=page.waitForResponse(r=>r.url().includes('/preview?')&&r.url().includes('/api/debts/'));
   await main().click();const res=await response;assert.equal(res.status(),200);const data=await res.json();
   await page.locator('.tdp-sheet-status').filter({hasText:/^Chỉ xem$/}).waitFor();
   assert.match(await page.locator('.tdp-sheet-top strong').textContent(),pattern);
   assert.equal(downloads,count,'Viewing must not download a file');
   const rendered=await page.evaluate(()=>window.__openedDebtWorkbook);
   assert.deepEqual(rendered,data.workbook,'The real API workbook must be passed unchanged to the viewer');
   if(name){await shot(name);fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(data));}
   return data;
 };
 const saveExcel=async name=>{const wait=page.waitForEvent('download');await page.getByRole('button',{name:'Tải Excel sổ đang xem',exact:true}).click();const d=await wait;await d.saveAs(path.join(out,name+'.xlsx'));};
 try{
  if(live){const c=JSON.parse(fs.readFileSync('D:/TDP_RAILWAY_PRIVATE/access.json','utf8').replace(/^\uFEFF/,''));const login=await page.request.get(base+'/login');const csrf=(await login.text()).match(/name="csrf" value="([^"]+)"/)[1];assert.equal((await page.request.post(base+'/login',{form:{username:c.username,password:c.password,csrf},headers:{Origin:base}})).status(),200);}
  await page.goto(base);await page.locator('#nav [data-view=debts]').click();await settle();
  // Observe the actual workbook sent to the actual renderer; never substitute data.
  await page.evaluate(()=>{const open=window.TDPWorksheet.open;window.TDPWorksheet.open=function(options){window.__openedDebtWorkbook=options.workbookData?JSON.parse(JSON.stringify(options.workbookData)):null;return open.call(this,options);};});
  const before=await json('/api/debts?from=2026-09-01&to=2026-09-04');
  const period=page.locator('#debtPeriodForm');await period.locator('[name=from]').fill('2026-09-01');await period.locator('[name=to]').fill('2026-09-04');await period.locator('[type=submit]').click();await settle();
  await page.locator('#receivableContractor').selectOption('TOYOTA');await settle();await page.locator('#receivableKitchen').selectOption('TOYOTA');await settle();
  await page.getByRole('button',{name:'Phóng to bảng tổng',exact:true}).waitFor();
  await page.getByRole('button',{name:'Phóng to tổng theo bếp',exact:true}).waitFor();
  await page.evaluate(()=>window.scrollTo(0,0));await shot('01_NUT_XEM_CHI_TIET_PHAI_THU');
  let data=await open('02_SO_PHAI_THU_TOYOTA_48_DONG',/TOYOTA \/ TOYOTA.*48 dòng/);
  assert.equal(data.line_count,48);assert.equal(data.summary.filtered_amount,9329320);
  const search=page.getByRole('searchbox',{name:'Tìm trong bảng'});await search.fill('TỔNG THEO BỘ LỌC');await search.press('Enter');
  await page.locator('.tdp-sheet-shell .tdp-search-result').filter({hasText:'1 / 1 ô khớp'}).waitFor();
  await shot('02B_PHAI_THU_CUOI_SO_VA_TONG_TIEN');
  await saveExcel('03_PHAI_THU_TOYOTA_CUNG_BAN_XEM');await close();
  report.checks.push('TOYOTA 01–04/09: 48 item rows, total 9,329,320 VND; main button opens full Excel-format ledger without download');
  for(const [contractor,kitchen,count,amount] of [['NHUAHAIPHONG','NHUAHP',28,6915520],['ATV','LSVINA',101,29398589]]){
    await page.locator('#receivableContractor').selectOption(contractor);await settle();await page.locator('#receivableKitchen').selectOption(kitchen);await settle();
    data=await open(contractor==='ATV'?'04_DOI_BO_LOC_ATV_LSVINA':null,new RegExp(contractor+' / '+kitchen));
    assert.equal(data.line_count,count);assert.equal(data.summary.filtered_amount,amount);
    await close();
  }
  report.checks.push('Changing TOYOTA → NHUAHAIPHONG → ATV/LSVINA loads only the newly selected kitchen and reconciles exact totals');
  if(!live){
    await page.route('**/api/debts/receivables/lines/preview?**',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'Lỗi kết nối kiểm thử'})}),{times:1});
    await main().click();await page.getByText('Lỗi kết nối kiểm thử',{exact:true}).waitFor();assert.equal(await page.locator('.tdp-sheet-shell').count(),0);await main().isEnabled();
    await open(null,/ATV \/ LSVINA/);await close();
    let arrive,release;const arrived=new Promise(r=>arrive=r),gate=new Promise(r=>release=r);
    await page.route('**/api/debts/receivables/lines/preview?**',async route=>{const res=await route.fetch();arrive();await gate;await route.fulfill({response:res});},{times:1});
    await main().click();await arrived;await page.locator('#receivableContractor').selectOption('TOYOTA');release();await settle();
    assert.equal(await page.locator('.tdp-sheet-shell').count(),0,'A late response must not open the previous contractor');
    report.checks.push('Local only: failed request stays visible and retries; a delayed previous-filter response cannot open an obsolete ledger');
  }
  await page.locator('[data-action=open-debt-section][data-section=payable]').click();await settle();
  await page.locator('#payableSupplier').selectOption('sim');await settle();await page.evaluate(()=>window.scrollTo(0,0));await shot('05_NUT_XEM_CHI_TIET_PHAI_TRA');
  data=await open('06_SO_PHAI_TRA_NCC_SIM_82_DONG',/phải trả · sim.*82 dòng/);assert.equal(data.line_count,82);
  const first=data.workbook.sheets[data.workbook.sheetOrder[0]];assert.equal(first.cellData[String(first.rowCount-1)]['13'].v,1541280);
  await saveExcel('07_PHAI_TRA_SIM_CUNG_BAN_XEM');await close();
  report.checks.push('NCC sim 01–04/09: 82 item rows, total 1,541,280 VND; direct read-only worksheet matches supplier Excel format');
  await page.locator('#payableSupplier').selectOption('');await settle();data=await open('08_PHAI_TRA_TAT_CA_NCC_CO_CAC_SHEET',/Tất cả NCC/);
  assert(data.workbook.sheetOrder.length>2);assert(Object.values(data.workbook.sheets).some(s=>s.name==='Tổng NCC'));
  await page.getByText('Tổng NCC',{exact:true}).click();await shot('09_CHUYEN_SHEET_TONG_NCC');await close();
  report.checks.push('All suppliers opens the full detail sheet first and allows switching to supplier total and individual supplier sheets');
  // Empty real range and an unsubmitted date edit: use what is actually visible in the date fields.
  await page.locator('#payableFrom').fill('2020-01-01');await page.locator('#payableTo').fill('2020-01-02');
  data=await open(null,/01\/01\/2020 → 02\/01\/2020 · 0 dòng/);assert.equal(data.line_count,0);await close();
  report.checks.push('Date values currently visible in the form are respected even before Apply; an empty period opens a 0-row ledger, never stale totals');
  const after=await json('/api/debts?from=2026-09-01&to=2026-09-04');assert.deepEqual(after.contractors,before.contractors);assert.deepEqual(after.suppliers,before.suppliers);
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);report.checks.push('No business write requests and no JavaScript errors; all receivable/payable accounts remain unchanged');
  report.ok=true;fs.writeFileSync(path.join(out,'VERIFIED.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }catch(e){await shot('ERROR');throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
