// Browser regression: use PLAYWRIGHT_MODULE for an existing Playwright installation.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const page=await browser.newPage({locale:'vi-VN'});
  await page.setContent('<main>Weight editor regression</main>');
  // The old numeric spinner also increments ArrowUp by one millionth kg.
  await page.setContent('<input type="number" step="0.000001" value="0.000003">');
  await page.locator('input').press('ArrowUp');
  assert.equal(await page.locator('input').inputValue(),'0.000004');
  await page.setContent('<main>Weight editor regression</main>');
  await page.addScriptTag({path:path.join(__dirname,'static/invoice-unit-editor.js')});
  await page.evaluate(()=>{
   window.saved=[];
   const weight={order_id:13661,remaining_qty:8,invoice_unit:'Kg',stock_unit:'Gói',review_kind:'actual_kg',editable:true,actual_kg:null,note:'',amount:64000,token:'test-only'};
   window.TDPInvoiceUnitEditor.open({scope:{contractor:'ATV',from:'2026-10-01',to:'2026-10-31'},orderId:13661,
    api:async (url,options)=>{if(options){window.saved.push(JSON.parse(options.body));throw Error('Thử lỗi kết nối');}return url.includes('actual-weights')?{rows:[weight]}:{line_choices:[{order_id:13661,enabled:true,product_code:'I000100',invoice_name:'Nấm kim châm',unit:'Gói',contractor:'ATV',date:'2026-10-24',kitchen:'YLK'}]};},onSaved:async()=>{}});
  });
  const kg=page.locator('[name=actual_kg]'),note=page.locator('[name=note]');
  await kg.waitFor();await note.fill('Đã cân thực tế');await page.locator('[name=confirmed]').check();
  for(const value of ['0,4','0.4','8','35,25','0,000004']){
   await kg.fill('');await kg.pressSequentially(value);
   assert.equal(await kg.inputValue(),value);
   assert.equal(await kg.evaluate(e=>e.validity.valid),true);
   await page.getByRole('button',{name:'Lưu kg thực tế',exact:true}).click();
   await page.getByText(/Chưa lưu kg/).waitFor();
   assert.equal(await page.evaluate(()=>window.saved.at(-1).actual_kg),value.replace(',','.'));
   assert.equal(await kg.inputValue(),value);assert.equal(await note.inputValue(),'Đã cân thực tế');
   assert.equal(await page.locator('[name=confirmed]').isChecked(),true);
  }
  await kg.fill('0,4');await kg.press('ArrowUp');assert.equal(await kg.inputValue(),'0,4');
  assert.equal(await page.locator('[data-price]').innerText(),'160.000 đ/kg');
  const before=await page.evaluate(()=>window.saved.length);
  for(const value of ['','0','-1','abc','1,2.3','1e3','0,1234567','1000000']){
   await kg.fill(value);await page.getByRole('button',{name:'Lưu kg thực tế',exact:true}).click();
   assert.equal(await page.evaluate(()=>window.saved.length),before);
   assert.equal(await kg.inputValue(),value);
  }
  await kg.fill('0,4');assert.equal(await kg.evaluate(e=>e.validity.valid),true);
  console.log('PASS: decimal comma/dot, clearing/retyping, spinner regression, price, invalid values, failed save preserves kg/note/confirmation');
 } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1});
