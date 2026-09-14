const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const requests=[];const root=process.argv[2];
const server=http.createServer((req,res)=>{
 const u=new URL(req.url,'http://localhost');
 if(u.pathname==='/'){res.setHeader('Content-Type','text/html;charset=utf-8');return res.end('<script src="/document-preview.js"></script><div id="preview"></div><script>TDPDocuments.open({kind:"deliveries"},"preview")</script>');}
 if(u.pathname==='/document-preview.js'){res.setHeader('Content-Type','text/javascript');return res.end(fs.readFileSync(path.join(__dirname,'static/document-preview.js')));}
 if(u.pathname==='/api/documents/preview'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({token:'fixture',sheet_count:3,sheets:['SHORT','LSVINA','SHORT2'].map(name=>({name,width:800,html:'<table><tr><td>'+name+'</td></tr></table>'}))}));}
 if(u.pathname.endsWith('/pdf')){
  requests.push(req.url);const long=u.searchParams.get('sheets').split(',').includes('1');const mode=u.searchParams.get('sides');
  res.setHeader('Content-Type','application/pdf');res.setHeader('Content-Disposition','inline; filename="Don_da_chon.pdf"');
  res.setHeader('X-Print-Sides',mode==='auto'?(long?'duplex':'simplex'):mode);
  return res.end(fs.readFileSync(path.join(root,long?'mixed.pdf':'short.pdf')));
 }
 res.statusCode=404;res.end();
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({acceptDownloads:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port);const mode=page.getByLabel('Cách in',{exact:true});await mode.waitFor();
  assert.equal(await mode.inputValue(),'auto');assert.equal(await page.getByLabel('Khổ giấy',{exact:true}).inputValue(),'A4');
  const download=async()=>{const wait=page.waitForEvent('download');await page.locator('[data-doc=pdf]').click();await(await wait).saveAs(path.join(root,'browser-result.pdf'));await page.waitForFunction(()=>!document.querySelector('[data-doc=pdf]').disabled);};
  await download();assert.match(requests.at(-1),/sides=auto/);assert.match(await page.locator('.document-print-help').innerText(),/Bản in hai mặt/);
  await page.locator('[data-doc=none]').click();assert(await page.locator('[data-doc=print]').isDisabled());
  await page.locator('[data-sheet="0"]').check();assert.equal(await mode.inputValue(),'auto');await download();assert.match(await page.locator('.document-print-help').innerText(),/Bản in một mặt/);
  await page.locator('[data-doc=all]').click();await mode.selectOption('simplex');await download();assert.match(requests.at(-1),/sides=simplex/);assert.match(await page.locator('.document-print-help').innerText(),/Bản in một mặt/);
  await mode.selectOption('duplex');await download();assert.match(requests.at(-1),/sides=duplex/);
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(root,'browser-checks.json'),JSON.stringify({ok:true,requests,errors,auto_default:true,short_simplex:true,long_duplex:true,explicit_override:true,empty_disabled:true},null,2));
  console.log('DELIVERY_PRINT_BROWSER_PASS');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
