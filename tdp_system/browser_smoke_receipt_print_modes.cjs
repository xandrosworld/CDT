const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const requests=[];let prefixed=false;
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost');
 if(url.pathname==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');return res.end('<script src="/document-preview.js"></script><h1>KIỂM THỬ CHỌN CÁCH IN</h1><div id="preview"></div><script>TDPDocuments.open({kind:"purchases"},"preview")</script>');}
 if(url.pathname==='/document-preview.js'){res.setHeader('Content-Type','text/javascript');return res.end(fs.readFileSync(path.join(__dirname,'static/document-preview.js')));}
 if(url.pathname==='/api/documents/preview'){
  res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({token:'fixture',sheet_count:6,sheets:['bảng kê tổng','biên nhận','biên nhận 02','biên nhận 03','biên nhận 04','biên nhận 05'].map(name=>({name:(prefixed?'purchases 2026-09-02 5 · ':'')+name,width:800,html:'<table><tr><td>'+name+'</td></tr></table>'}))}));
 }
 if(url.pathname.endsWith('/pdf')){requests.push(req.url);res.setHeader('Content-Type','text/html');return res.end('<script>window.print=()=>{}</script>Bản kiểm thử, không gửi lệnh in');}
 res.statusCode=404;res.end();
});
(async()=>{
 const out=process.argv[2]||'tdp_system/exports/receipt_sheets_verified';fs.mkdirSync(out,{recursive:true});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:'+server.address().port);
  const mode=page.getByLabel('Cách in',{exact:true});await mode.waitFor();assert.equal(await mode.inputValue(),'duplex');
  const paper=page.getByLabel('Khổ giấy',{exact:true});assert.equal(await paper.inputValue(),'A4');
  assert.equal(await paper.locator('[value=A5]').evaluate(e=>e.disabled),true);
  assert.match(await page.locator('.document-print-help').innerText(),/kể cả trang trắng/);
  await page.locator('[data-doc=none]').click();assert.equal(await page.locator('[data-doc=print]').isDisabled(),true);
  await page.locator('[data-sheet="2"]').check();assert.equal(await mode.inputValue(),'simplex');
  await page.locator('[data-doc=print]').click();await page.locator('.document-pdf iframe').waitFor();
  assert.match(requests.at(-1),/sheets=2&paper=A4&sides=simplex/);
  await paper.selectOption('A5');await page.locator('[data-doc=print]').click();await page.waitForFunction(()=>!document.querySelector('[data-doc=print]').disabled);
  assert.match(requests.at(-1),/sheets=2&paper=A5&sides=simplex/);
  await mode.selectOption('duplex');await page.locator('[data-doc=all]').click();
  assert.equal(await paper.inputValue(),'A4');assert.equal(await paper.locator('[value=A5]').evaluate(e=>e.disabled),true);
  await page.locator('[data-doc=print]').click();await page.waitForFunction(()=>!document.querySelector('[data-doc=print]').disabled);
  assert.match(requests.at(-1),/sheets=0,1,2,3,4,5&paper=A4&sides=duplex/);
  await mode.selectOption('simplex');await page.locator('[data-doc=print]').click();await page.waitForFunction(()=>!document.querySelector('[data-doc=print]').disabled);
  assert.match(requests.at(-1),/sheets=0,1,2,3,4,5&paper=A4&sides=simplex/);
  prefixed=true;await page.reload();await mode.waitFor();assert.equal(await mode.inputValue(),'duplex');
  assert.deepEqual(errors,[]);const result={ok:true,checks:['Mixed selection defaults to duplex, including multiple workbooks','Receipt alone defaults to simplex','Empty selection cannot print','PDF requests carry exact sheet scope and chosen sides'],requests,errors};fs.writeFileSync(path.join(out,'KIEM_THU_GIAO_DIEN.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
