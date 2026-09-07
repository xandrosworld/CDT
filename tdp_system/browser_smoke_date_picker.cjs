const assert=require('node:assert/strict');
const fs=require('node:fs');
// Run against browser_fixture_date_picker_server only, never the live customer app.
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
const base='http://127.0.0.1:18805';
fs.mkdirSync('tmp',{recursive:true});
(async()=>{
  const report=[];
  for(const channel of ['chrome','msedge']){
    const browser=await chromium.launch({channel,headless:true});
    const page=await browser.newPage({viewport:{width:1920,height:1080}});
    const errors=[],writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.url());});
    await page.addInitScript(()=>{
      localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-31',date_to:'2026-09-07',status:'all',line_filter:'all'}));
      const show=HTMLInputElement.prototype.showPicker;
      window.pickerChecks=[];
      HTMLInputElement.prototype.showPicker=function(){const result=show.call(this);window.pickerChecks.push({id:this.id,type:this.type});return result;};
    });
    try{
      await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});
      await page.locator('[data-view="msmi"]').click();await page.locator('#invoiceFrom').waitFor({state:'attached'});
      let count=0;
      for(const width of [1920,1440,1024]){
        await page.setViewportSize({width,height:1080});
        for(const id of ['invoiceFrom','invoiceTo']){
          const input=page.locator('#'+id), button=input.locator('..').locator('button.localized-date-icon');
          await button.scrollIntoViewIfNeeded();
          const box=await button.boundingBox();
          assert.equal(box.width,44);
          for(const dx of [4,16,22,28,40]){
            await page.keyboard.press('Escape');
            await page.mouse.click(box.x+dx,box.y+box.height/2);
            count++;
            assert.equal(await page.evaluate(()=>window.pickerChecks.length),count,`${channel} ${width} ${id} x=${dx}`);
          }
        }
      }
      await page.keyboard.press('Escape');
      const from=page.locator('#invoiceFrom'), button=from.locator('..').locator('button.localized-date-icon');
      await button.focus();await page.keyboard.press('Enter');count++;
      assert.equal(await page.evaluate(()=>window.pickerChecks.length),count);
      await page.keyboard.press('Escape');await button.focus();await page.keyboard.press('Space');count++;
      assert.equal(await page.evaluate(()=>window.pickerChecks.length),count);
      await page.screenshot({path:'tmp/calendar-fixed-'+channel+'.png'});
      await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');
      await page.waitForFunction(()=>document.getElementById('invoiceFrom')?.value==='2026-09-01');
      assert.equal(await from.locator('..').locator('.localized-date-display').inputValue(),'01/09/2026');
      await page.keyboard.press('Escape');
      const display=from.locator('..').locator('.localized-date-display');
      const typedReload=page.waitForResponse(r=>r.url().includes('/api/invoice-workbench/invoices?')&&r.url().includes('from=2026-08-31'),{timeout:5000});
      await display.fill('31/08/2026');await display.press('Tab');
      await typedReload;
      assert.equal(await from.inputValue(),'2026-08-31');
      await page.locator('[data-view="reports"]').click();
      const month=page.locator('#reportPeriod');await month.waitFor({state:'attached'});
      const monthButton=month.locator('..').locator('button.localized-date-icon');
      await monthButton.click();count++;
      assert.equal(await page.evaluate(()=>window.pickerChecks.length),count);
      await page.screenshot({path:'tmp/calendar-month-fixed-'+channel+'.png'});
      await page.keyboard.press('Escape');
      await page.locator('[data-view="inventory"]').click();
      const inventory=page.locator('#inventoryFrom');await inventory.waitFor({state:'attached'});
      await inventory.locator('..').locator('button.localized-date-icon').click();count++;
      assert.equal(await page.evaluate(()=>window.pickerChecks.length),count);
      await page.keyboard.press('Escape');
      await page.evaluate(()=>document.body.insertAdjacentHTML('beforeend','<form id="date-check-form"><input id="disabled-date" type="date" disabled><input id="readonly-date" type="date" readonly><input id="reset-date" type="date" value="2026-08-31"><button type="reset">Reset test date</button></form>'));
      await page.locator('#disabled-date.localized-date-native').waitFor({state:'attached'});
      assert(await page.locator('#disabled-date').locator('..').locator('button').isDisabled());
      assert(await page.locator('#disabled-date').locator('..').locator('.localized-date-display').isDisabled());
      assert(await page.locator('#readonly-date').locator('..').locator('button').isDisabled());
      assert.equal(await page.locator('#readonly-date').locator('..').locator('.localized-date-display').getAttribute('readonly'),'');
      const resetInput=page.locator('#reset-date'),resetDisplay=resetInput.locator('..').locator('.localized-date-display');
      await resetDisplay.fill('30/08/2026');await resetDisplay.press('Tab');
      assert.equal(await resetInput.inputValue(),'2026-08-30');
      await page.getByRole('button',{name:'Reset test date',exact:true}).click();
      await page.waitForFunction(()=>document.getElementById('reset-date').parentElement.querySelector('.localized-date-display').value==='31/08/2026');
      assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
      report.push({channel,version:await browser.version(),pickerOpens:count,widths:[1920,1440,1024],keyboard:true,dateSelection:true,manualEntry:true,month:true,inventory:true,errors,writes});
    }finally{await browser.close();}
  }
  // Simulate browsers without showPicker: their native indicator must cover all 44px.
  const legacy=await chromium.launch({channel:'chrome',headless:true});
  try{
    const page=await legacy.newPage({viewport:{width:1440,height:1000}});
    await page.addInitScript(()=>{
      HTMLInputElement.prototype.showPicker=undefined;
      localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-31',date_to:'2026-09-07',status:'all',line_filter:'all'}));
    });
    await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});
    await page.locator('[data-view="msmi"]').click();
    for(const [id,offset,next] of [['invoiceFrom',4,'2026-09-01'],['invoiceTo',40,'2026-09-08']]){
      const input=page.locator('#'+id);await input.waitFor({state:'attached'});
      assert(await input.locator('..').evaluate(e=>e.classList.contains('native-picker-fallback')));
      const box=await input.boundingBox();
      await page.mouse.click(box.x+offset,box.y+box.height/2);
      await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');
      await page.waitForFunction(({id,next})=>document.getElementById(id)?.value===next,{id,next});
    }
    report.push({fallbackWithoutShowPicker:true,leftAndRightEdges:true});
  }finally{await legacy.close();}
  fs.writeFileSync('tmp/calendar-fix-results.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
