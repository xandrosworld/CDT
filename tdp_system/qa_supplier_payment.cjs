const fs=require('fs'),path=require('path'),assert=require('assert/strict');
process.env.TEMP=process.env.TMP='D:/CodexTemp/four-items-browser';
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const base=process.argv[2]||'http://127.0.0.1:5094',live=base==='https://tdp.up.railway.app';assert(live||base==='http://127.0.0.1:5094');
 const out=path.resolve('tdp_system/exports/supplier_payment_'+(live?'railway':'local')+'_20260913');fs.mkdirSync(out,{recursive:true});
 const report={base,live,checked_at:new Date().toISOString(),checks:[]},errors=[],writes=[],created=[];
 const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1600,height:1100}});page.setDefaultTimeout(45000);
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.url().includes('/api/')&&!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+new URL(r.url()).pathname);});
 const json=async url=>{const r=await page.request.get(base+url);assert.equal(r.status(),200,await r.text());return r.json();};
 const settle=async()=>{await page.waitForLoadState('networkidle');await page.waitForFunction(()=>!document.querySelector('#content')?.innerText.includes('Đang nạp'));};
 const ready=async()=>{await page.waitForFunction(()=>document.querySelector('#supplierPaymentForm fieldset')?.disabled===false);await settle();};
 const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png'),animations:'disabled'});};
 const number=async selector=>Number((await page.locator(selector).textContent()).replace(/\D/g,''));
 const snapshot=()=>json('/api/debts/payables/settlement?from=2026-09-01&to=2026-09-04&supplier=sim');
 const accounts=()=>json('/api/debts?from=2026-09-01&to=2026-09-04');
 const history=()=>json('/api/debts/payables/payments?from=2026-09-01&to=2026-09-04&supplier=sim&status=all&limit=5000');
 const form=()=>page.locator('#supplierPaymentForm');
 const dialog=()=>page.locator('.supplier-payment-confirm');
 const fill=async amount=>{await form().locator('[name=amount]').fill(String(amount));await form().locator('[name=actor]').fill('Kiểm tra giao diện');await form().locator('[name=note]').fill(live?'Xem trước, chưa ghi nhận':'Kiểm thử trên bản sao dữ liệu khách');};
 const preview=async()=>{const wait=page.waitForResponse(r=>r.url().endsWith('/api/debts/payables/payments/preview'));await form().locator('[type=submit]').click();const r=await wait;assert.equal(r.status(),200,await r.text());const d=await r.json();await dialog().waitFor();return d;};
 try{
  if(live){const c=JSON.parse(fs.readFileSync('D:/TDP_RAILWAY_PRIVATE/access.json','utf8').replace(/^\uFEFF/,''));const login=await page.request.get(base+'/login');const csrf=(await login.text()).match(/name="csrf" value="([^"]+)"/)[1];assert.equal((await page.request.post(base+'/login',{form:{username:c.username,password:c.password,csrf},headers:{Origin:base}})).status(),200);}
  await page.goto(base);await page.locator('#nav [data-view=debts]').click();await settle();await page.locator('[data-action=open-debt-section][data-section=payable]').click();await settle();
  await page.locator('#payableFrom').fill('2026-09-01');await page.locator('#payableTo').fill('2026-09-04');await page.locator('#debtPeriodForm [type=submit]').click();await settle();await page.locator('#payableSupplier').selectOption('sim');await ready();
  const before=await accounts(), initial=await snapshot(), previous=await history();assert.equal(initial.remaining_amount,1541280);assert.equal(initial.line_count,82);
  const accountKey=Object.keys(before.suppliers).find(k=>k.toLowerCase()==='sim');assert(accountKey);
  assert.equal(await number('#supplierPaymentDue'),initial.remaining_amount);await page.evaluate(()=>window.scrollTo(0,0));await shot('01_CHON_NCC_HIEN_SO_CON_NO');
  await fill(500000);assert.equal(await number('#supplierPaymentRemaining'),1041280);await shot('02_NHAP_SO_TIEN_TRA_LAN_NAY');
  // A rerender caused by selecting a manual line must preserve the quick-payment draft.
  const check=page.locator('.payable-line-select:not(:disabled)').first();await check.check();await check.uncheck();
  assert.equal(await form().locator('[name=amount]').inputValue(),'500000');assert.equal(await form().locator('[name=actor]').inputValue(),'Kiểm tra giao diện');
  await page.evaluate(()=>window.scrollTo(0,0));const plan=await preview();assert.equal(plan.before_amount,1541280);assert.equal(plan.after_amount,1041280);
  assert.equal(plan.payment.allocations.reduce((sum,r)=>sum+r.amount,0),500000);await shot('03_XAC_NHAN_KHOAN_TRA_CHUA_GHI_SO');
  report.preview={supplier:'sim',before:plan.before_amount,amount:plan.amount,after:plan.after_amount,lines:plan.line_count};
  report.checks.push('Real NCC sim: 82 outstanding lines, 1,541,280 VND; entering 500,000 shows 1,041,280 remaining; preview gives exact allocations');
  if(live){
    await dialog().locator('[data-cancel]').click();assert.deepEqual(await snapshot(),initial);assert.deepEqual(await history(),previous);
    await page.locator('[data-quick-all]').click();assert.equal(await form().locator('[name=amount]').inputValue(),'1541280');assert.equal(await number('#supplierPaymentRemaining'),0);await shot('04_NUT_TRA_HET_SO_CON_NO');
    assert(writes.every(r=>r==='POST /api/debts/payables/payments/preview'),JSON.stringify(writes));
    report.checks.push('Railway: preview/cancel and Pay All input only; no payment saved, original history and balances unchanged');
  }else{
    // The real local server commits, then its response is lost. Retry after browser reload must not duplicate it.
    await page.route('**/api/debts/payables/payments',async route=>{const response=await route.fetch();assert.equal(response.status(),201);const d=await response.json();created.push(d);await route.abort('failed');},{times:1});
    await dialog().locator('[data-confirm]').click();await dialog().getByText(/Chưa xác định được kết quả/).waitFor();assert.equal((await snapshot()).remaining_amount,1041280);
    await dialog().locator('[data-cancel]').click();await page.reload();await page.locator('#nav [data-view=debts]').click();await settle();
    await page.locator('[data-action=open-debt-section][data-section=payable]').click();await settle();
    await page.locator('[data-quick-retry]').waitFor();await page.locator('[data-quick-retry]').click();
    const replayWait=page.waitForResponse(r=>r.url().endsWith('/api/debts/payables/payments')&&r.request().method()==='POST');await dialog().locator('[data-confirm]').click();const replay=await replayWait;assert.equal(replay.status(),200);assert.equal((await replay.json()).idempotent,true);await ready();
    assert.equal((await history()).pagination.total,previous.pagination.total+1);assert.equal(await number('#supplierPaymentDue'),1041280);
    assert.equal((await accounts()).suppliers[accountKey].closing,before.suppliers[accountKey].closing-500000);await page.evaluate(()=>window.scrollTo(0,0));await shot('LOCAL_04_DA_TRA_MOT_PHAN_CONG_NO_TU_TRU');
    await fill(1041280);const full=await preview();assert.equal(full.after_amount,0);
    const paidWait=page.waitForResponse(r=>r.url().endsWith('/api/debts/payables/payments')&&r.request().method()==='POST');await dialog().locator('[data-confirm]').click();const paid=await paidWait;assert.equal(paid.status(),201);created.push(await paid.json());await ready();
    assert.equal(await number('#supplierPaymentDue'),0);assert.equal((await snapshot()).line_count,0);assert.equal((await accounts()).suppliers[accountKey].closing,before.suppliers[accountKey].closing-1541280);await shot('LOCAL_05_TRA_HET_NO_TRONG_KY');
    report.checks.push('Local copy: lost successful response + reload + identical retry creates one payment; partial payment deducts exactly 500,000, final payment clears all 82 lines');
  }
  await page.locator('#payableSupplier').selectOption('');await settle();assert.equal(await page.locator('#supplierPaymentAmount').count(),0);await page.locator('#payableSupplier').selectOption('sim');await ready();assert.equal(await form().locator('[name=amount]').inputValue(),'');
  report.checks.push('Changing supplier clears the old amount; selecting manual debt rows preserves the quick-payment draft');
  assert.deepEqual(errors,[]);report.ok=true;fs.writeFileSync(path.join(out,'VERIFIED.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }catch(e){await shot('ERROR');throw e;}
 finally{
  if(!live){for(const p of created.reverse()){const r=await page.request.post(base+'/api/debts/payables/payments/'+p.id+'/reverse',{data:{actor:'Kiểm thử',reason:'Hoàn tác sau kiểm thử trên bản sao',expected_revision:p.revision}});assert.equal(r.status(),200,await r.text());}}
  await browser.close();
 }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
