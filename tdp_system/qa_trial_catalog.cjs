// Native worksheet edit on the isolated Railway copy; restores the product name through the UI.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const [privateFolder,output]=process.argv.slice(2),base='https://tdp-audit-20260908-audit-20260908.up.railway.app';
(async()=>{
 fs.mkdirSync(output,{recursive:true});const c=JSON.parse(fs.readFileSync(path.join(privateFolder,'access.json'),'utf8'));
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
 const result={ok:false,checks:[]};page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(60000);
 const data=async()=>{const r=await page.request.get(base+'/api/catalog/worksheet',{timeout:90000});assert.equal(r.status(),200);return r.json();};
 try{
   const login=await page.request.get(base+'/login');const csrf=(await login.text()).match(/name="csrf" value="([^"]+)"/)[1];
   const auth=await page.request.post(base+'/login',{form:{...c,csrf},headers:{Origin:base},timeout:90000});assert.equal(auth.status(),200);
   const guard=await page.request.get(base+'/api/audit/routes');assert.equal((await guard.json()).external_connections_blocked,true);
   await page.goto(base,{waitUntil:'domcontentloaded'});await page.locator('#nav [data-view=settings]').click();
   const before=await data(),items=before.items,target=items.at(-1);assert(items.length>=1255);
   await page.waitForFunction(n=>document.querySelectorAll('#catalogProducts tbody tr').length===n,items.length);
   const frame=page.locator('.catalog-products-scroll');assert(await frame.evaluate(e=>e.clientHeight<=640&&e.scrollHeight>e.clientHeight*10));
   await page.locator('#catalogProducts .tdp-open-sheet').click();await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.includes('Đã tải'));
   assert.match(await page.locator('.tdp-sheet-notice').innerText(),new RegExp(String(items.length)));
   result.checks.push('All real catalog rows loaded in bounded outer frame and editable workbook');
   const search=page.locator('.tdp-sheet-shell input[type=search]');await search.fill(target.code);await search.press('Enter');
   await page.waitForFunction(address=>document.querySelector('.tdp-sheet-shell input:not([type=search])').value===address,'A'+(items.length+1));
   await page.waitForTimeout(180);
   const position=await page.locator('canvas[id^="univer-sheet-main"]').evaluate(canvas=>{
     const box=canvas.getBoundingClientRect(),pixels=canvas.getContext('2d').getImageData(194,48,5,canvas.height-55).data,ys=[];
     for(let y=0;y<canvas.height-55;y++)for(let x=0;x<5;x++){const i=(y*5+x)*4;if(pixels[i]<110&&pixels[i+1]<180&&pixels[i+2]>200)ys.push(y+48);}
     if(!ys.length)throw Error('Selected row border not rendered');return {y:box.top+(Math.min(...ys)+Math.max(...ys))/2};
   });
   const testName='QA kiểm tra bản sao · '+target.name;
   await page.mouse.click(300,position.y);await page.keyboard.press('F2');await page.keyboard.press('Control+a');await page.keyboard.insertText(testName);await page.keyboard.press('Enter');
   await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.startsWith('Đã lưu'));
   assert.equal((await data()).items.find(r=>r.code===target.code).name,testName);
   await page.screenshot({path:path.join(output,'last-row-saved.png')});result.checks.push('Native edit of final real row saved and independently read back');
   await page.locator('.tdp-sheet-close').click();await page.locator('.tdp-sheet-shell').waitFor({state:'detached'});
   await page.locator('#catalogProducts tbody tr').filter({hasText:target.code}).locator('[data-action=edit-catalog-product]').click();
   const dialog=page.locator('.catalog-product-dialog');await dialog.locator('[name=name]').fill(target.name);await dialog.locator('[type=submit]').click();await dialog.waitFor({state:'detached'});
   const after=await data();assert.equal(after.items.find(r=>r.code===target.code).name,target.name);
   for(const original of items){const restored=after.items.find(r=>r.code===original.code);for(const key of ['code','name','unit','tax','invoice_name'])assert.equal(restored[key],original[key],original.code+' '+key);}
   await page.reload({waitUntil:'domcontentloaded'});assert.equal((await data()).items.length,items.length);result.checks.push('Restored through edit form; every catalog code/name/unit/tax/invoice name matches original');
   assert.deepEqual(errors,[]);result.ok=true;
 }catch(e){result.error=String(e.message).split(/\nCall log:/)[0];await page.screenshot({path:path.join(output,'failure.png')});process.exitCode=1;}
 finally{result.errors=errors;fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();}
})().catch(e=>{console.error(String(e.message).split(/\nCall log:/)[0]);process.exitCode=1;});
