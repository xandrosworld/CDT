// Browser proof uses the customer's actual data. Production requests are read-only.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
process.env.TEMP=process.env.TMP='D:/CodexTemp/four-items-browser';
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:5094',live=base==='https://tdp.up.railway.app';assert(live||base==='http://127.0.0.1:5094');
 const out=path.resolve('tdp_system/exports/invoice_pending_'+(live?'railway':'local')+'_20260913');fs.mkdirSync(out,{recursive:true});
 const report={base,live,checked_at:new Date().toISOString(),checks:[]},errors=[],writes=[];
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1600,height:1100},acceptDownloads:true});
 const page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().includes('/api/')&&!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+new URL(r.url()).pathname);});
 const scope=()=>page.locator('#orderInvoiceExportForm');
 const ready=async()=>{await page.waitForLoadState('networkidle');await page.locator('#unissuedForm [value=view]').waitFor();await page.waitForFunction(()=>document.querySelector('#unissuedForm [value=view]')?.disabled===false && document.querySelector('#pendingInvoiceSection')?.dataset.loaded==='true');};
 const json=async url=>{const r=await page.request.get(base+url);assert.equal(r.status(),200,await r.text());return r.json();};
 const setScope=async(party,date)=>{await scope().locator('[name=contractor]').selectOption(party);await ready();await scope().locator('[name=to]').fill(date);await ready();};
 const shot=async name=>{await page.locator('#toast.show').waitFor({state:'hidden',timeout:20000});await page.screenshot({path:path.join(out,name+'.png'),animations:'disabled'});};
 const captureDownload=async(selector,name)=>{const wait=page.waitForEvent('download');await page.locator(selector).click();const d=await wait;await d.saveAs(path.join(out,name));await ready();return d.suggestedFilename();};
 const verifyTable=async(party,date)=>{
   const data=await json('/api/outgoing-invoices/unissued?'+new URLSearchParams({contractor:party==='*'?'':party,to:date}));
   const rows=await page.locator('#pendingInvoiceTable tbody tr').allTextContents();assert.equal(rows.length,data.pending_rows.length);
   for(let i=0;i<rows.length;i++){assert(rows[i].includes(data.pending_rows[i].product_code));assert(rows[i].includes(data.pending_rows[i].pending_reason));assert(data.pending_rows[i].waiting_qty>0);}
   assert(data.pending_rows.every(r=>(party==='*'||r.contractor===party)&&r.last_date<=date));
   const waiting=data.details.reduce((s,r)=>s+r.waiting_qty,0),grouped=data.pending_rows.reduce((s,r)=>s+r.waiting_qty,0);assert(Math.abs(waiting-grouped)<1e-6);
   return data;
 };
 try{
  if(live){const c=JSON.parse(fs.readFileSync('D:/TDP_RAILWAY_PRIVATE/access.json','utf8').replace(/^\uFEFF/,''));const login=await page.request.get(base+'/login');const csrf=(await login.text()).match(/name="csrf" value="([^"]+)"/)[1];assert.equal((await page.request.post(base+'/login',{form:{username:c.username,password:c.password,csrf},headers:{Origin:base}})).status(),200);}
  await page.goto(base);await page.locator('#nav [data-view=documents]').click();await ready();
  await setScope('ATV','2026-09-13');
  assert.equal(await page.getByRole('button',{name:'Tải bảng kê để up M-Invoice',exact:true}).count(),1);
  assert.equal(await page.locator('[value=catch-up]').count(),0);
  assert.equal(await page.locator('#unissuedForm input,#unissuedForm select').count(),0);
  const data=await verifyTable('ATV','2026-09-13');assert(data.pending_rows.length>0);fs.writeFileSync(path.join(out,'ATV_PENDING.json'),JSON.stringify(data,null,2));
  await page.evaluate(()=>window.scrollTo(0,0));await shot('01_MOT_NUT_XUAT_CHUNG');
  await page.locator('#pendingInvoiceSection').scrollIntoViewIfNeeded();await shot('02_HANG_CON_CHO_CO_LY_DO');
  report.waiting_template=await captureDownload('#unissuedForm [value=template]','03_PHAN_CON_CHO_THEO_MAU.zip');
  report.waiting_excel=await captureDownload('#unissuedForm [value=excel]','04_HANG_CON_CHO_VA_LY_DO.xlsx');
  await page.locator('#unissuedReconciliation > summary').click();await page.locator('#unissuedReconciliation').scrollIntoViewIfNeeded();await shot('05_DOI_CHIEU_TACH_DU_DIEU_KIEN_VA_CON_CHO');
  report.all_template=await captureDownload('[form=unissuedForm][value=all-template]','06_TOAN_BO_CHUA_XUAT_DOI_CHIEU.zip');
  report.checks.push('One M-Invoice export button; shared contractor/date filter; pending table matches actual API and shows only positive waiting quantities with reasons; both downloads work');
  await setScope('TOYOTA','2026-09-04');const toyota=await verifyTable('TOYOTA','2026-09-04');
  await page.evaluate(()=>window.scrollTo(0,0));await shot('07_LOC_TOYOTA_CUNG_PHAM_VI');
  report.scopes={ATV:{pending_rows:data.pending_rows.length,source_rows:data.pending_order_rows},TOYOTA:{pending_rows:toyota.pending_rows.length,source_rows:toyota.pending_order_rows}};
  // Delay a genuine API response; switching the filter must discard its stale result.
  await page.route('**/api/outgoing-invoices/unissued?**',async route=>{const u=new URL(route.request().url());if(u.searchParams.get('contractor')==='ATV'){const response=await route.fetch();await new Promise(r=>setTimeout(r,1500));await route.fulfill({response});}else await route.continue();});
  await scope().locator('[name=contractor]').selectOption('ATV');await scope().locator('[name=contractor]').selectOption('TOYOTA');await ready();await page.unrouteAll({behavior:'wait'});await ready();await verifyTable('TOYOTA','2026-09-04');
  await setScope('TOYOTA','2000-01-01');const empty=await verifyTable('TOYOTA','2000-01-01');assert.equal(empty.pending_rows.length,0);assert(await page.locator('#unissuedForm [value=template]').isDisabled());
  assert((await page.locator('#pendingInvoiceSection').textContent()).includes('Không còn phần chưa đủ điều kiện'));
  report.checks.push('TOYOTA and cutoff filter both sections; stale responses cannot replace a new selection; empty period has no false waiting rows');
  await setScope('ATV','2026-09-13');
  if(!live){
    const resWait=page.waitForResponse(r=>r.url().endsWith('/api/export/order-invoices')&&r.request().method()==='POST');
    await scope().locator('[value=export]').click();const res=await resWait;report.local_export_status=res.status();
    if(res.status()===200)fs.writeFileSync(path.join(out,'LOCAL_ELIGIBLE_M_INVOICE.zip'),await res.body());
    else{assert.equal(res.status(),409);report.local_export_error=await res.json();}
    await ready();await page.waitForFunction(()=>document.querySelector('#orderInvoiceExportForm [value=export]')?.disabled===false);
    assert(await page.locator('#unissuedForm [value=excel]').isEnabled());
    await verifyTable('ATV','2026-09-13');
    report.checks.push('Local actual-data copy: the single export button calls the existing stock-checked export; afterwards pending downloads remain usable');
  }else assert.deepEqual(writes,[],'No production business writes');
  await setScope('GIANHAPTAY','2026-09-13');const mixed=await verifyTable('GIANHAPTAY','2026-09-13');
  assert(mixed.rows.some(r=>r.ready_qty>0));assert(mixed.pending_rows.length>0);
  fs.writeFileSync(path.join(out,'GIANHAPTAY_PENDING.json'),JSON.stringify(mixed,null,2));
  await page.evaluate(()=>window.scrollTo(0,0));await shot('08_GIANHAPTAY_CHI_HIEN_PHAN_CON_CHO');
  report.mixed_waiting_template=await captureDownload('#unissuedForm [value=template]','09_GIANHAPTAY_PHAN_CON_CHO.zip');
  report.checks.push('GIANHAPTAY has both ready and pending goods: main pending table and download exclude the ready quantity');
  if(!live){
    const resWait=page.waitForResponse(r=>r.url().endsWith('/api/export/order-invoices')&&r.request().method()==='POST');
    await scope().locator('[value=export]').click();const res=await resWait;assert.equal(res.status(),200,await res.text());
    fs.writeFileSync(path.join(out,'LOCAL_GIANHAPTAY_ELIGIBLE_M_INVOICE.zip'),await res.body());await ready();
    report.checks.push('Local GIANHAPTAY actual-data copy: the single primary button successfully downloads eligible M-Invoice files');
  }
  assert.deepEqual(errors,[]);report.ok=true;report.api_writes=writes;
  fs.writeFileSync(path.join(out,'VERIFIED.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }catch(e){await shot('ERROR');throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
