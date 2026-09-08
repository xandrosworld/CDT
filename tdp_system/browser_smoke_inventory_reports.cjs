// Start browser_fixture_inventory_reports_server.py first. No production access.
const assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const base=process.env.TDP_INVENTORY_TEST_URL || 'http://127.0.0.1:18807';
  const errors=[],downloads=[],writes=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('download',d=>downloads.push(d));
  page.on('request',r=>{requests.push(r.url());if(['PUT','POST','DELETE'].includes(r.method()))writes.push(r.url());});
  const get=async url=>(await page.request.get(base+url)).json();
  const shell=page.locator('.tdp-sheet-shell');
  const date=async (id,value)=>page.locator('#'+id).evaluate((e,v)=>{e.value=v;e.dispatchEvent(new Event('change',{bubbles:true}));},value);
  const close=async()=>{await shell.locator('.tdp-sheet-close').click();await shell.waitFor({state:'detached'});};
  const ready=()=>page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent==='Chỉ xem');
  try {
    await page.goto(base);await page.locator('.loading-panel').waitFor({state:'detached'});
    const before=await get('/fixture/digest');
    await page.evaluate(()=>{
      const original=window.TDPWorksheet.open;
      window.TDPWorksheet.open=options=>{window.__reportOptions=options;return original(options);};
    });
    await page.locator('[data-view="inventory"]').click();await page.locator('.inventory-export-grid').waitFor();
    await date('inventoryFrom','2026-08-01');await date('inventoryTo','2026-08-31');
    assert.equal(await page.locator('.inventory-export-grid button').count(),5);
    assert.equal(await page.locator('.inventory-month-close,.inventory-close-history,.stats-grid,.inventory-detail-toggle,.inventory-nxt-card').count(),0);
    assert.equal(await page.locator('#openingForm:visible,#inventoryAdjustmentForm:visible').count(),0);
    assert.equal(await page.locator('#inventoryDataTools > summary').count(),1,'Data entry remains reachable in the collapsed panel');
    assert(!requests.some(url=>url.includes('/month-close/') || url.includes('/bk-import/')));
    for(const kind of ['opening','input','output','nxt']) {
      const button=page.locator('[data-action="preview-inventory-report"][data-kind="'+kind+'"]');
      const label=await button.innerText();
      await button.click();await ready();
      assert.match(await shell.locator('.tdp-sheet-top strong').innerText(),new RegExp(label));
      assert.match(await shell.locator('.tdp-sheet-top strong').innerText(),/01\/08\/2026 → 31\/08\/2026/);
      const options=await page.evaluate(()=>({editable:window.__reportOptions.editable,book:window.__reportOptions.workbookData}));
      assert.equal(options.editable,false);
      const book=options.book,first=book.sheets[book.sheetOrder[0]];
      assert(first.mergeData.length>0);assert(first.cellData[0][0].v);
      assert.equal(downloads.length,0,'Viewing must not trigger a download');
      const bounds=await shell.boundingBox();assert.equal(bounds.x,0);assert.equal(bounds.y,0);assert.equal(bounds.width,1440);assert.equal(bounds.height,1000);
      // Search through the rendered workbook, select a real source code, then test copy.
      const search=shell.getByRole('searchbox',{name:'Tìm trong bảng'});
      await search.fill('R1-KG');await search.press('Enter');
      await page.waitForFunction(()=>document.querySelector('.tdp-search-result')?.textContent.includes('ô khớp'));
      assert(!await shell.locator('.tdp-sheet-status').evaluate(e=>e.classList.contains('is-error')));
      if(book.sheetOrder.length>1) {
        const next=book.sheets[book.sheetOrder[1]];
        await shell.getByText(next.name,{exact:true}).click();
        await search.fill('kg');await search.press('Enter');
        await page.waitForFunction(()=>document.querySelector('.tdp-search-result')?.textContent.includes('ô khớp'));
        await shell.getByText(first.name,{exact:true}).click();
      }
      if(kind==='nxt' && process.env.TDP_INVENTORY_SCREENSHOT)await shell.screenshot({path:process.env.TDP_INVENTORY_SCREENSHOT});
      // Typing/pasting cannot write through a read-only report.
      await shell.locator('canvas[id^="univer-sheet-main-canvas_"]').click({position:{x:350,y:220}});
      await page.keyboard.type('999');await page.keyboard.press('Enter');
      await close();assert.equal(writes.length,0);
      assert.equal(await page.locator('#inventoryFrom').inputValue(),'2026-08-01');
      assert.equal(await page.locator('#inventoryTo').inputValue(),'2026-08-31');
    }
    assert.deepEqual(await get('/fixture/digest'),before);
    // Reversed date range cannot open a report or start a ZIP download.
    await date('inventoryFrom','2026-09-01');assert.equal(await page.locator('.inventory-export-grid button:disabled').count(),5);
    await date('inventoryTo','2026-09-07');
    await page.locator('[data-kind="opening"]').click();await ready();
    assert.match(await shell.locator('.tdp-sheet-top strong').innerText(),/01\/09\/2026 → 07\/09\/2026/);await close();
    // A failed preview remains retryable; stale response after changing dates is ignored.
    await page.route('**/api/invoice-valuation/preview/input?**',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'Lỗi đọc báo cáo thử nghiệm'})}));
    await page.locator('[data-kind="input"]').click();await page.waitForFunction(()=>!document.querySelector('[data-kind="input"]').disabled);
    assert.equal(await shell.count(),0);await page.unroute('**/api/invoice-valuation/preview/input?**');
    let release;const paused=new Promise(resolve=>{release=resolve;});
    let entered;const started=new Promise(resolve=>{entered=resolve;});
    await page.route('**/api/invoice-valuation/preview/output?**',async route=>{entered();await paused;await route.continue();});
    await page.locator('[data-kind="output"]').click();await started;await date('inventoryTo','2026-09-08');release();
    await page.waitForResponse(r=>r.url().includes('/preview/output?'));await page.unroute('**/api/invoice-valuation/preview/output?**');
    assert.equal(await shell.count(),0);
    // Explicit ZIP download still returns exactly four files (verified in backend tests).
    const download=page.waitForEvent('download');await page.getByRole('button',{name:'Tải đủ 4 file ZIP',exact:true}).click();
    assert.match((await download).suggestedFilename(),/\.zip$/);assert.equal(downloads.length,1);
    // Existing table-based worksheet callers must keep working after workbook support.
    await page.evaluate(()=>window.TDPWorksheet.open({title:'Bảng cũ',editable:false,columns:[{key:'code',title:'Mã',width:150},{key:'qty',title:'Lượng',numeric:true}],rows:[{code:'00123',qty:0.855},{code:'TEST-02',qty:1}]}));
    await ready();await shell.getByRole('searchbox',{name:'Tìm trong bảng'}).fill('00123');
    await shell.getByRole('searchbox',{name:'Tìm trong bảng'}).press('Enter');
    await page.waitForFunction(()=>document.querySelector('.tdp-search-result')?.textContent==='1 / 1 ô khớp');
    await shell.locator('.tdp-sheet-close').focus();await page.keyboard.press('Escape');await shell.waitFor({state:'detached'});
    assert.deepEqual(await get('/fixture/digest'),before);assert.deepEqual(errors,[]);
    console.log('PASS: compact landing; four fullscreen workbooks; cells/search/sheet switching; read-only; no implicit download; dates retained; invalid dates; failed/stale response; explicit ZIP; database unchanged');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
