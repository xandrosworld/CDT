const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE);
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/bootstrap*',async route=>{const response=await route.fetch();const data=await response.json();data.master.contractors.push({code:'NT-A',name:'Test'});await route.fulfill({response,json:data});});
  await page.goto('http://127.0.0.1:18806');await page.locator('.loading-panel').waitFor({state:'detached'});
  await page.locator('[data-view="debts"]').click();await page.locator('[data-action="open-payment-request"]').click();
  await page.locator('#paymentRequestForm [name=contractor]').selectOption('NT-A');
  await page.locator('#paymentRequestForm [name=from]').fill('2026-09-01');
  await page.locator('#paymentRequestForm [name=to]').fill('2026-09-30');
  await page.locator('#paymentRequestForm button[type=submit]').click();
  await page.locator('[data-action=fix-payment-buyer]').click();
  assert.equal(await page.evaluate(()=>document.activeElement.name),'legal_name');
  await page.locator('#buyerProfileForm [name=legal_name]').fill('Cong ty thu');
  await page.locator('#buyerProfileForm [name=tax_code]').fill('0202225782');
  await page.locator('#buyerProfileForm [name=address]').fill('Dia chi thu');
  await page.route('**/api/outgoing-buyers/NT-A',r=>r.fulfill({status:503,json:{ok:false,error:'Thu mat ket noi'}}));
  await page.locator('#buyerProfileForm button').click();await page.waitForTimeout(300);
  assert.equal(await page.locator('#buyerProfileForm [name=tax_code]').inputValue(),'0202225782');
  await page.unroute('**/api/outgoing-buyers/NT-A');
  const checked=page.waitForResponse(r=>r.url().includes('/payment-scope/NT-A'));
  await page.locator('#buyerProfileForm button').click();const response=await checked;
  assert.equal((await response.json()).code,'issued_invoice_scope_empty');
  assert.equal(await page.locator('#paymentRequestForm [name=from]').inputValue(),'2026-09-01');
  await page.locator('[data-action=payment-open-output]').click();
  await page.locator('#invoiceFrom').waitFor();assert.equal(await page.locator('#invoiceFrom').inputValue(),'2026-09-01');
  assert.equal(await page.locator('#invoiceTo').inputValue(),'2026-09-30');assert.deepEqual(errors,[]);
  console.log('PASS missing profile, focus, failed save preserves inputs, save retries scope, period preserved, output navigation');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
