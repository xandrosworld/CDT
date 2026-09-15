const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const requests=[];let fail=false;
const server=http.createServer((req,res)=>{
 const u=new URL(req.url,'http://localhost');
 if(u.pathname==='/'){res.setHeader('Content-Type','text/html;charset=utf-8');return res.end('<script src="/document-preview.js"></script><div id="preview"></div>');}
 if(u.pathname==='/document-preview.js'){res.setHeader('Content-Type','text/javascript');return res.end(fs.readFileSync(path.join(__dirname,'static/document-preview.js')));}
 if(u.pathname==='/api/documents/preview'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({token:'fixture',sheet_count:1,sheets:[{name:'Đề nghị thanh toán',width:800,html:'<table><tr><td>Preview</td></tr></table>'}]}));}
 if(u.pathname.startsWith('/api/export/invoice-pdfs/')){
  requests.push(req.url);
  if(fail){res.statusCode=409;res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({error:'Phạm vi đã thay đổi'}));}
  res.setHeader('Content-Type','application/zip');res.setHeader('Content-Disposition','attachment; filename="Hoa_don_SUPPY.zip"');return res.end('fixture-original-invoices');
 }
 res.statusCode=404;res.end();
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const p=await browser.newPage({acceptDownloads:true});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto('http://127.0.0.1:'+server.address().port);
  const body={kind:'payment',contractor:'SUPPY',from:'2026-09-01',to:'2026-09-13',scope_id:'REVIEWED-SCOPE'};
  await p.evaluate(body=>TDPDocuments.open(body,'preview'),body);
  const button=p.locator('.document-sheet-list [data-doc=invoice-pdfs]');assert.equal(await button.count(),1);
  await p.locator('[data-doc=none]').click();assert(await p.locator('[data-doc=pdf]').isDisabled());assert(await button.isEnabled());
  const downloaded=p.waitForEvent('download');await button.click();const download=await downloaded;
  assert.equal(download.suggestedFilename(),'Hoa_don_SUPPY.zip');assert.equal(await download.failure(),null);
  await p.waitForFunction(()=>!document.querySelector('[data-doc=invoice-pdfs]').disabled);
  const requested=new URL(requests[0],'http://localhost');assert.equal(requested.pathname,'/api/export/invoice-pdfs/SUPPY');
  assert.deepEqual(Object.fromEntries(requested.searchParams),{from:body.from,to:body.to,scope_id:body.scope_id});
  fail=true;await button.click();await p.waitForFunction(()=>document.querySelector('.document-error').textContent.includes('Phạm vi đã thay đổi'));
  assert(await button.isEnabled());assert.equal(await p.locator('[data-sheet]:checked').count(),0);
  await p.evaluate(()=>TDPDocuments.open({kind:'deliveries'},'preview'));assert.equal(await button.count(),0);
  assert.deepEqual(errors,[]);console.log('INVOICE_PDF_BROWSER_PASS: scope, placement, independent selection, download, errors, payment only');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
