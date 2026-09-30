const assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE);
const base='http://127.0.0.1:18804',out='D:/TDP_RAILWAY_PRIVATE/payment-customer';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const p=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});p.setDefaultTimeout(60000);
  await p.goto(base);await p.waitForFunction(()=>window.TDPDocuments);
  await p.evaluate(()=>{const host=document.createElement('div');host.id='customer-test';document.body.replaceChildren(host);return TDPDocuments.open({kind:'payment',contractor:'NT-A',from:'2026-09-01',to:'2026-09-30'},host.id);});
  await p.locator('[data-open-sheet="0"]').click();
  const content=await p.locator('.document-scroll').innerText();
  for(const text of ['BẢNG TỔNG HỢP GIAO NHẬN','STT','Tên hàng','ĐVT','Số lượng','Đơn giá','Thành tiền','Thuế suất','Tiền thuế','Thanh toán','ĐẠI DIỆN BÊN MUA','ĐẠI DIỆN BÊN BÁN'])assert(content.includes(text),text);
  assert(!content.includes('Ghi chú'));assert(!content.includes('Ký hiệu / số'));
  assert.equal(await p.locator('[data-open-sheet]').count(),2);
  await p.locator('[data-doc=none]').click();await p.locator('[data-sheet="0"]').check();
  const download=p.waitForEvent('download');await p.locator('[data-doc=excel]').click();await (await download).saveAs(out+'/statement.xlsx');
  await p.screenshot({path:out+'/preview.png',fullPage:true});
  const pdf=p.waitForEvent('download',{timeout:180000});await p.locator('[data-doc=pdf]').click();await (await pdf).saveAs(out+'/statement.pdf');
  assert.equal(await p.locator('.document-error').innerText(),'');
  let failOnce=true;
  await p.route('**/api/documents/preview',route=>{
   if(failOnce){failOnce=false;return route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({ok:false,code:'payment_statement_line_totals_mismatch',error:'Tiền thuế chưa khớp hóa đơn 853'})});}
   return route.continue();
  });
  await p.evaluate(()=>TDPDocuments.open({kind:'payment',contractor:'NT-A',from:'2026-09-01',to:'2026-09-30'},'customer-test'));
  assert.equal(await p.locator('[data-action=payment-open-output]').count(),1);
  await p.locator('[data-payment-retry]').click();await p.locator('[data-open-sheet="0"]').waitFor();
  console.log('PASS: actual preview, exactly 2 customer forms, Excel and PDF downloads using selected 9-column statement.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
