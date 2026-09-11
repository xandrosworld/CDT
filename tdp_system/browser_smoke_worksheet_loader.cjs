// Exercise the actual loader with failed/stalled downloads; never saves data.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'static');
const server=http.createServer((req,res)=>{
 const pathname=req.url.split('?')[0];
 if(pathname==='/'){
  res.setHeader('Content-Type','text/html; charset=utf-8');
  return res.end('<link rel="stylesheet" href="/shared/styles.css"><link rel="stylesheet" href="/static/real.css"><script src="/static/worksheet-loader.js"></script><p>KIỂM THỬ MÔ PHỎNG MẠNG CHẬM · KHÔNG GHI DỮ LIỆU KHÁCH</p>');
 }
 const file=pathname==='/shared/styles.css'?path.resolve(__dirname,'../demo_tdp/styles.css'):path.resolve(root,'.'+pathname.replace(/^\/static/,''));
 if(!(file.startsWith(root+path.sep)||pathname==='/shared/styles.css')||!fs.existsSync(file)){res.statusCode=404;return res.end();}
 res.setHeader('Content-Type',file.endsWith('.css')?'text/css':'text/javascript');fs.createReadStream(file).pipe(res);
});
const bundle='window.TDPWorksheet={isOpen:()=>!!document.querySelector("#opened"),open:async(options)=>{window.openCount=(window.openCount||0)+1;const el=document.createElement("div");el.id="opened";el.textContent=options.title;document.body.append(el);}};';
(async()=>{
 const out=process.argv[2]||'tdp_system/exports/worksheet_loading_verified';fs.mkdirSync(out,{recursive:true});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({channel:'chrome',headless:true});const checks=[],errors=[];
 const pageFor=async handler=>{
  const p=await browser.newPage({viewport:{width:1400,height:850}});p.on('pageerror',e=>errors.push(e.message));
  await p.route('**/worksheet-bundle/worksheet.js*',handler);await p.goto(base);return p;
 };
 const open=async p=>p.evaluate(()=>{window.openJob=window.TDPWorksheet.open({title:'Bảng kiểm thử'});});
 const hidden=async p=>assert.equal(await p.locator('.worksheet-load-retry').isVisible(),false);
 try{
  let attempts=0,held;
  const p=await pageFor(r=>{attempts++;if(attempts===1)held=r;else r.fulfill({contentType:'text/javascript',body:bundle});});
  await p.clock.install();await open(p);await hidden(p);
  const deadline=Date.now()+10000;while(!held&&Date.now()<deadline)await new Promise(r=>setTimeout(r,20));assert(held,'First download reached the network');
  await p.waitForFunction(()=>document.querySelector('script[src*="worksheet-bundle"]'));
  await p.clock.fastForward(31000);
  await p.getByText('Tải bảng Excel quá 30 giây.',{exact:false}).waitFor();
  assert.equal(await p.locator('.worksheet-load-retry').isVisible(),true);
  await p.screenshot({path:path.join(out,'02_MO_PHONG_QUA_THOI_GIAN_CHO.png')});
  await p.locator('.worksheet-load-retry').dblclick();
  try{await p.locator('#opened').waitFor({timeout:10000});}catch(e){console.log(JSON.stringify({attempts,body:await p.locator('body').innerText(),errors}));throw e;}
  assert.equal(attempts,2);assert.equal(await p.evaluate(()=>window.openCount),1);
  if(held)await held.fulfill({contentType:'text/javascript',body:bundle}).catch(()=>{});
  assert.equal(await p.evaluate(()=>window.TDPWorksheet.isOpen()),true);
  assert.equal(await p.locator('.worksheet-loading-dialog').count(),0);
  checks.push('Stalled request times out; retry downloads again and opens once, including repeated clicks');await p.close();

  attempts=0;
  const q=await pageFor(r=>{attempts++;return attempts===1?r.abort('failed'):r.fulfill({contentType:'text/javascript',body:bundle});});
  await open(q);await q.locator('.worksheet-load-retry').waitFor();
  assert.match(await q.locator('.worksheet-loading-dialog p').innerText(),/Chưa tải được/);
  await q.locator('.worksheet-load-retry').click();await q.locator('#opened').waitFor();
  assert.equal(attempts,2);checks.push('Network failure gives an actionable retry');await q.close();

  attempts=0;let cancelled;
  const r=await pageFor(route=>{attempts++;if(attempts===1)cancelled=route;else route.fulfill({contentType:'text/javascript',body:bundle});});
  await open(r);await hidden(r);await r.locator('.worksheet-load-cancel').click();
  assert.equal(await r.evaluate(()=>window.openJob),null);assert.equal(await r.evaluate(()=>window.TDPWorksheet.isOpen()),false);
  await open(r);await r.locator('#opened').waitFor();
  if(cancelled)await cancelled.fulfill({contentType:'text/javascript',body:bundle}).catch(()=>{});
  assert.equal(await r.evaluate(()=>window.openCount),1);checks.push('Cancel ends the pending load; reopening works without a late duplicate');await r.close();

  attempts=0;
  const s=await pageFor(route=>{attempts++;return route.fulfill({contentType:'text/javascript',body:attempts===1?'/* missing engine */':bundle});});
  await open(s);await s.locator('.worksheet-load-retry').waitFor();
  await s.locator('.worksheet-load-retry').click();await s.locator('#opened').waitFor();
  checks.push('Invalid engine response can be retried');await s.close();

  const t=await pageFor(route=>route.fulfill({contentType:'text/javascript',body:bundle.replace('window.openCount=(window.openCount||0)+1;', 'window.openCount=(window.openCount||0)+1;if(window.openCount===1)throw Error("Lỗi mở bảng mô phỏng");')}));
  await open(t);await t.locator('.worksheet-load-retry').waitFor();
  assert.match(await t.locator('.worksheet-loading-dialog p').innerText(),/Lỗi mở bảng/);
  await t.locator('.worksheet-load-retry').click();await t.locator('#opened').waitFor();
  checks.push('Engine open failure restores a usable retry dialog');await t.close();
  assert.deepEqual(errors,[]);const result={ok:true,checks,errors};
  fs.writeFileSync(path.join(out,'KIEM_THU_LOADER.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
