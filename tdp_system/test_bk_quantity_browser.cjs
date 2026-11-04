const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
const page=await browser.newPage({viewport:{width:1440,height:1000}});await page.route('http://localhost:18899/',r=>r.fulfill({contentType:'text/html',body:'<html><body></body></html>'}));await page.goto('http://localhost:18899/');
await page.addScriptTag({path:require('node:path').join(__dirname,'static','bk-draft.js')});
await page.evaluate(()=>{window.sent=[];window.TdpBkDraft({from:'2026-10-16',to:'2026-10-16',esc:v=>String(v).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),quantity:v=>Number(v).toLocaleString('vi-VN',{maximumFractionDigits:6}),api:async(url,opts)=>{
 if(url.includes('/sellers'))return {names:['Người bán thử'],items:[]};
 if(url.includes('/shortages')&&url.includes('to=2026-10-28'))return {from:'2026-10-28',to:'2026-10-28',month_end:'2026-10-31',items:[],daily_reconciliations:[{product_code:'TEST-DAILY',product_name:'Hàng đã ghi nhập sau',unit:'Kg',closing_qty:-3,month_closing_qty:0,suggested_qty:0,later_inputs:[{date:'2026-10-29',qty:3}]}]};
 if(url.includes('/shortages'))return {from:'2026-10-16',to:'2026-10-16',month_end:'2026-10-31',items:[{product_code:'I000137',product_name:'Rau kinh giới',unit:'Kg',closing_qty:-1.8,month_closing_qty:-15,suggested_qty:1.8,unit_cost:42750,purchase_sources:[{source_key:'a',purchase_qty:.4,source_party:'Người bán thử',document_date:'2026-10-16'},{source_key:'b',purchase_qty:.1,source_party:'Người bán thử',document_date:'2026-10-16'}]}]};
 if(url.includes('/preview')){window.sent.push(JSON.parse(opts.body));throw new Error('Kiểm tra thử: giữ nguyên dữ liệu');}throw new Error(url);
 }});});
await page.waitForFunction(()=>document.querySelectorAll('[data-field=qty]').length===3);
assert.deepEqual(await page.locator('[data-field=qty]').evaluateAll(xs=>xs.map(x=>x.value)),['0.4','0.1','1.3']);
assert((await page.locator('.bk-quantity-explanation').last().innerText()).includes('Tổng lượng gợi ý cho mã này: 1,8 Kg'));
await page.locator('[data-bk=all]').click();
await page.locator('[data-field=source_party]').last().fill('Người bán thử');
await page.locator('[data-field=qty]').last().fill('1.234567');
await page.locator('[data-bk=all]').click();assert.equal(await page.locator('[data-field=qty]').last().inputValue(),'1.234567');
await page.locator('[data-bk=load]').click();await page.waitForFunction(()=>!document.querySelector('[data-bk=load]').disabled);assert.equal(await page.locator('[data-field=qty]').last().inputValue(),'1.234567');
await page.locator('[data-field=qty]').last().fill('1.3');await page.locator('[data-bk=preview]').click();await page.waitForFunction(()=>window.sent.length===1);
assert.equal(await page.locator('[data-field=qty]').last().inputValue(),'1.3');
await page.locator('[name=from]').fill('2026-10-28');await page.locator('[name=to]').fill('2026-10-28');await page.locator('[data-bk=load]').click();
await page.waitForFunction(()=>document.querySelectorAll('[data-field=qty]').length===0);
await page.getByText('Xem mã hàng và các ngày nhập đã ghi kho',{exact:true}).click();
assert((await page.locator('.bk-daily-reconciliation').innerText()).includes('29/10/2026: 3 Kg'));
assert((await page.locator('.bk-daily-reconciliation').innerText()).includes('Không lập thêm bảng kê'));
assert.equal(await page.locator('.bk-daily-reconciliation table').isVisible(),true);
console.log('PASS browser: 0.4+0.1+1.3, Vietnamese explanation, edits retained across render/reload/preview error; no posting.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
