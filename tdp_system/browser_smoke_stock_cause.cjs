const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE);
const base=process.env.TDP_ISSUANCE_TEST_URL,out=process.env.TDP_FIXTURE_OUTPUT;
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.setDefaultTimeout(20000);const result={ok:false,errors:[],writes:[]};
 page.on('pageerror',e=>result.errors.push(e.message));
 const before=await (await page.request.get(base+'/fixture/state')).json();
 let allowOpeningSave=false;
 await page.route('**/api/**',route=>{
  if(route.request().method()!=='GET'){
   result.writes.push(route.request().url());
   if(allowOpeningSave && route.request().url().endsWith('/api/inventory/opening'))return route.continue();
   return route.abort();
  }
  return route.continue();
 });
 try{
  await page.goto(base);await page.locator('#batchSelect option').first().waitFor({state:'attached'});
  await page.locator('#nav [data-view=documents]').click();
  const first=page.locator('[data-action=show-stock-cause][data-code="HH-01"]');
  await first.waitFor();assert.equal(await page.locator('[data-action=show-stock-cause]').count(),2);
  assert((await first.locator('..').innerText()).includes('Quả me tươi'));
  let failOnce=true;
  await page.route('**/readiness/*/stock/HH-01',route=>{
   if(failOnce){failOnce=false;return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Tạm thời chưa tải được.'})});}
   return route.continue();
  });
  await first.click();const dialog=page.locator('.stock-cause-dialog');
  await dialog.getByText('Tạm thời chưa tải được.').waitFor();
  await dialog.getByRole('button',{name:'Thử lại'}).click();
  await dialog.getByRole('heading',{name:'Quả me tươi · HH-01'}).waitFor();
  assert((await dialog.innerText()).includes('Âm ngay từ tồn đầu kỳ'));
  assert((await dialog.innerText()).includes('Tồn kiểm thử.xlsx; sheet Tồn đầu; dòng 168'));
  assert.equal(await dialog.locator('tbody tr').count(),1);
  assert((await dialog.locator('tbody tr').innerText()).includes('-1,5'));
  assert.equal(await page.locator('#nav [data-view=documents]').getAttribute('class'),'nav-item active');
  await dialog.screenshot({path:path.join(out,'stock-cause-desktop.png'),animations:'disabled'});
  await page.setViewportSize({width:390,height:844});
  const bounds=await dialog.boundingBox(),back=await dialog.getByRole('button',{name:'Quay lại'}).boundingBox();
  assert(bounds.width<=390);assert(back.y>=0 && back.y+back.height<=844);
  await dialog.screenshot({path:path.join(out,'stock-cause-mobile.png'),animations:'disabled'});
  await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('[data-action=show-stock-cause][data-code="HH-02"]').click();
  await dialog.getByRole('heading',{name:'Rau <kiểm tra> · HH-02'}).waitFor();
  assert.equal(await dialog.locator('h3 *').count(),0);
  assert(!(await dialog.innerText()).includes('dòng 168'));
  await dialog.getByRole('button',{name:'Quay lại'}).click();
  await dialog.waitFor({state:'detached'});
  const after=await (await page.request.get(base+'/fixture/state')).json();
  assert.deepEqual(after,before);assert.deepEqual(result.errors,[]);assert.deepEqual(result.writes,[]);
  await first.click();await dialog.getByRole('button',{name:'Sửa tồn đầu',exact:true}).click();
  const form=dialog.locator('.stock-opening-form');await form.waitFor();
  assert((await form.innerText()).includes('08/2026'));
  assert.equal(await form.locator('[name=qty]').inputValue(),'-1.5');
  await form.locator('[name=qty]').fill('2.5');
  await form.getByRole('button',{name:'Hủy sửa',exact:true}).click();
  assert.deepEqual(await (await page.request.get(base+'/fixture/state')).json(),before);
  await dialog.getByRole('button',{name:'Sửa tồn đầu',exact:true}).click();
  await form.locator('[name=qty]').fill('2.5');
  await dialog.screenshot({path:path.join(out,'opening-edit.png'),animations:'disabled'});
  allowOpeningSave=true;
  await form.getByRole('button',{name:'Lưu tồn đầu',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Đã lưu tồn đầu kỳ.'}).waitFor();
  await dialog.getByText('Còn có thể lập 2,5 kg',{exact:true}).waitFor();
  const edited=await (await page.request.get(base+'/fixture/state')).json();
  assert.equal(edited.opening[0].qty_in,2.5);assert.equal(edited.opening[0].qty_out,0);
  assert.equal(edited.opening[0].unit_cost,before.opening[0].unit_cost);
  assert(edited.opening[0].note.includes(before.opening[0].note));
  assert.deepEqual(edited.opening[1],before.opening[1]);assert.deepEqual(edited.orders,before.orders);
  assert.equal(edited.ledger_count,before.ledger_count);assert.equal(result.writes.length,1);
  await dialog.getByRole('button',{name:'Quay lại',exact:true}).click();
  assert.equal(await first.count(),0);assert.equal(await page.locator('[data-action=show-stock-cause]').count(),1);
  assert.deepEqual(result.errors,[]);
  result.ok=true;result.correctProduct=true;result.sourceUnchangedBeforeSave=true;result.explicitOpeningEdit=true;
 }catch(e){result.error=e.stack;process.exitCode=1;await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}
 finally{fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();}
})();
