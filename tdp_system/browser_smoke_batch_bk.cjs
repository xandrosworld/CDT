const assert = require('node:assert/strict');
const {chromium} = require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const base='http://127.0.0.1:18856';const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const status=async()=>(await page.request.get(base+'/fixture/bk-status')).json();
 try {
  await page.goto(base);await page.locator('[data-view="orders"]').first().click();
  const initial=await status();
  await page.locator('[data-action="approve-batch"]').click();
  const modal=page.getByRole('dialog',{name:'Bảng kê cần kiểm tra'});
  await modal.waitFor();assert.match(await modal.innerText(),/Giá bán phải là số hữu hạn lớn hơn 0/);
  await modal.screenshot({path:'bk-missing-price.png'});
  assert.equal((await status()).lines,0);
  await modal.getByRole('button',{name:'Sửa dòng'}).click();
  await page.locator('#orderForm').waitFor({state:'visible'});
  await page.keyboard.press('Escape');
  // Load the good batch through the normal selector after closing the editor.
  await page.goto(base);await page.locator('select#batchSelect').selectOption(String(initial.good));
  await page.locator('[data-view="orders"]').first().click();
  page.once('dialog',async d=>{assert.match(d.message(),/Duyệt đơn và ghi nhập kho/);await d.dismiss();});
  await page.locator('[data-action="approve-batch"]').click();
  await page.waitForTimeout(250);assert.equal((await status()).lines,0);
  page.once('dialog',async d=>{assert.match(d.message(),/95%/);await d.accept();});
  const posted=page.waitForResponse(r=>r.url().endsWith('/approve')&&r.request().method()==='POST');
  await page.locator('[data-action="approve-batch"]').click();assert.equal((await posted).status(),200);
  await page.waitForFunction(()=>document.querySelector('[data-action="approve-batch"]')?.disabled);
  assert.equal((await status()).qty,2);
  await page.screenshot({path:'bk-approved.png',fullPage:true});
  const preview=await (await page.request.get(base+`/api/batches/${initial.good}/approval-preview`)).json();
  const again=await page.request.post(base+`/api/batches/${initial.good}/approve`,{data:{source_hash:preview.sourceHash,confirm_bk:true}});
  assert.equal(again.status(),200);assert.equal((await status()).lines,1);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ok:true,errors,inventoryLines:1}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
