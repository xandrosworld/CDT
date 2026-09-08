// Synthetic fixture only. Uses real keyboard, clipboard, canvas and server saves.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const output=process.argv[2]; fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:900},permissions:['clipboard-read','clipboard-write']});
 const page=await context.newPage(); const errors=[],writes=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(r.method()==='PUT')writes.push(r.postDataJSON());});
 const rows=()=>page.evaluate(()=>fetch('/api/catalog/worksheet').then(r=>r.json()).then(r=>r.items));
 const ready=()=>page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.includes('Đã tải'));
 const shot=n=>page.screenshot({path:path.join(output,n+'.png')});
 const open=async()=>{await page.locator('#catalogProducts .tdp-open-sheet').click();await ready();};
 const close=async()=>{await page.locator('.tdp-sheet-close').click();await page.locator('.tdp-sheet-shell').waitFor({state:'detached'});};
 const select=async address=>{
   const row=Number(address.slice(1))-2;
   const code=(await rows())[row].code;
   const search=page.locator('.tdp-sheet-shell input[type=search]');
   await search.fill(code);await search.press('Enter');
   await page.waitForFunction(expected=>document.querySelector('.tdp-sheet-shell input:not([type=search])').value===expected,'A'+(row+2));
   await page.waitForTimeout(120);
   const position=await page.locator('canvas[id^="univer-sheet-main"]').evaluate(canvas=>{
     const box=canvas.getBoundingClientRect(),ctx=canvas.getContext('2d'),ys=[];
     const pixels=ctx.getImageData(194,48,5,canvas.height-55).data;
     for(let y=0;y<canvas.height-55;y++)for(let x=0;x<5;x++){
       const i=(y*5+x)*4;
       if(pixels[i]<110&&pixels[i+1]<180&&pixels[i+2]>200)ys.push(y+48);
     }
     if(!ys.length)throw Error('Selected row border not rendered');
     return {top:box.top,y:(Math.min(...ys)+Math.max(...ys))/2};
   });
   await page.mouse.click({B:300,C:600,D:700,E:900}[address[0]],position.top+position.y);
 };
 const edit=async(address,value)=>{
   await select(address);await page.keyboard.press('F2');await page.keyboard.press('Control+a');
   await page.keyboard.insertText(value);await page.keyboard.press('Enter');
 };
 const saved=()=>page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.startsWith('Đã lưu'));
 try {
  await page.goto('http://127.0.0.1:18852');await page.locator('[data-view=settings]').click();
  await page.waitForFunction(()=>document.querySelectorAll('#catalogProducts tbody tr').length===1255);
  for(const width of [1440,1024]){
   await page.setViewportSize({width,height:900});
   const frame=page.locator('.catalog-products-scroll');await frame.scrollIntoViewIfNeeded();
   const metrics=await frame.evaluate(el=>{el.scrollTop=el.scrollHeight;return {height:el.clientHeight,scroll:el.scrollHeight,header:el.querySelector('th').getBoundingClientRect().top,top:el.getBoundingClientRect().top};});
   assert.ok(metrics.height<=640&&metrics.scroll>metrics.height*10);assert.ok(Math.abs(metrics.header-metrics.top)<5);
   await shot('catalog-'+width);
  }
  checks.push('1255 rows, bounded scroll and sticky header at 1440/1024');
  await page.setViewportSize({width:1440,height:900});
  const initial=await rows();await open();assert.ok((await page.locator('.tdp-sheet-notice').innerText()).startsWith('1255'));
  await close();assert.equal(writes.length,0);assert.deepEqual(await rows(),initial);checks.push('Open/close does not save');
  await open();
  await edit('B1256','Tên cuối đã sửa');await saved();assert.equal((await rows()).at(-1).name,'Tên cuối đã sửa');
  await shot('last-row-edited');checks.push('Native edit of last row persists');
  await select('B4');await page.evaluate(()=>navigator.clipboard.writeText('Hàng dán một\tCan\t5%\tTên hóa đơn một\nHàng dán hai\tGói\t10%\tTên hóa đơn hai'));
  await page.keyboard.press('Control+v');await saved();
  await page.waitForFunction(()=>fetch('/api/catalog/worksheet').then(r=>r.json()).then(p=>p.items[2].name==='Hàng dán một'&&p.items[3].name==='Hàng dán hai'));
  assert.equal((await rows())[2].tax,'5%');checks.push('Native paste 2 rows x 4 columns');
  await page.evaluate(()=>{window.originalFetch=window.fetch;window.failSave=true;window.fetch=(...args)=>{if(window.failSave&&args[1]?.method==='PUT')return Promise.reject(Error('Offline fixture'));return window.originalFetch(...args);};});
  await edit('B4','Giữ khi mất mạng');await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status').classList.contains('is-error'));
  await page.locator('.tdp-sheet-close').click();await page.waitForFunction(()=>document.querySelector('.tdp-sheet-notice')?.textContent.includes('Chưa đóng'));assert.equal(await page.locator('.tdp-sheet-shell').count(),1);
  await page.evaluate(()=>window.failSave=false);await page.getByRole('button',{name:'Thử lưu lại',exact:true}).click();await saved();
  assert.equal((await rows())[2].name,'Giữ khi mất mạng');checks.push('Offline edits retained, retry saves');
  await edit('C3','Can');await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status').textContent.includes('Mã đã được sử dụng'));
  assert.equal((await rows())[1].unit,'kg');await shot('used-unit-blocked');
  await edit('C3','kg');await page.getByRole('button',{name:'Thử lưu lại',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status').textContent.startsWith('Đã giữ'));checks.push('Used unit blocked and corrected in same sheet');
  await close();await page.waitForFunction(()=>document.querySelectorAll('#catalogProducts tbody tr').length===1255);
  assert.ok(await page.locator('#catalogProducts').innerText().then(s=>s.includes('Tên cuối đã sửa')));
  await open();await page.keyboard.press('Control+f');await page.locator('.tdp-sheet-shell input[type=search]').fill('Tên cuối đã sửa');await page.keyboard.press('Enter');
  await page.waitForFunction(()=>document.querySelector('.tdp-search-result').textContent.includes('1 / 1'));await shot('find-last-row');await close();
  assert.deepEqual(errors,[]);checks.push('Reopen/outer table/search agree with saved server data');
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({ok:true,checks,writes:writes.length,errors},null,2));
  console.log(JSON.stringify({ok:true,checks}));
 }catch(e){await shot('failure');fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({message:e.message,stack:e.stack,errors,checks,writes},null,2));throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
