// Real worksheet engine, synthetic catalog. Checks cache reuse across a reload.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'static');let codeRequests=0,dataRequests=0;
const manifest=JSON.parse(fs.readFileSync(path.join(root,'worksheet-bundle/manifest.json'),'utf8'));
const server=http.createServer((req,res)=>{
 const pathname=req.url.split('?')[0];
 if(pathname==='/'){
  res.setHeader('Content-Type','text/html; charset=utf-8');res.setHeader('Cache-Control','no-store');
  return res.end(`<link rel="stylesheet" href="/static/worksheet-bundle/worksheet.css"><link rel="stylesheet" href="/static/real.css"><script src="/static/table-search.js"></script><script src="/static/worksheet-loader.js"></script><button id="open">Mở bảng kiểm thử</button><p>DỮ LIỆU GIẢ LẬP · KIỂM TRA BỘ NHỚ ĐỆM</p><script>
  document.querySelector('#open').onclick=async()=>{const d=await fetch('/api/catalog/worksheet',{cache:'no-store'}).then(r=>r.json());window.lastData=d;
  window.TDPWorksheet.open({kind:'catalog',title:'Danh mục kiểm thử',editable:true,rows:d.items,columns:[{key:'code',title:'Mã hàng',width:150},{key:'name',title:'Tên hàng',width:350,editable:true},{key:'unit',title:'ĐVT',width:80,editable:true}]});};</script>`);
 }
 if(pathname==='/api/catalog/worksheet'){
  assert.equal(req.method,'GET');dataRequests++;
  res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
  return res.end(JSON.stringify({items:Array.from({length:1265},(_,i)=>({id:i+1,code:'TEST'+i,name:'Hàng thử phiên '+dataRequests,unit:'Kg',worksheet_revision:'r'+dataRequests})),total:1265}));
 }
 let file=path.resolve(root,'.'+pathname.replace(/^\/static/,''));
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.statusCode=404;return res.end();}
 const versioned=pathname.endsWith('/'+manifest.script);
 if(versioned){codeRequests++;file+='.gz';res.setHeader('Content-Encoding','gzip');res.setHeader('Cache-Control','private, max-age=31536000, immutable');}
 else res.setHeader('Cache-Control','no-store');
 res.setHeader('Content-Type',pathname.endsWith('.css')?'text/css':pathname.endsWith('.json')?'application/json':'text/javascript');
 res.setHeader('Content-Length',fs.statSync(file).size);fs.createReadStream(file).pipe(res);
});
(async()=>{
 const out=process.argv[2]||'tdp_system/exports/worksheet_cache_verified';fs.mkdirSync(out,{recursive:true});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({channel:process.env.TDP_BROWSER_CHANNEL||'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1500,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const open=async()=>{const started=Date.now();await page.locator('#open').click();await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.includes('Đã tải'));return Date.now()-started;};
 try{
  await page.goto(base);const firstMs=await open();assert.equal(codeRequests,1);const firstData=await page.evaluate(()=>window.lastData.items[0].name);
  await page.waitForFunction(async key=>!!(await (await caches.open('tdp-worksheet-code-v1')).match(key)),'/static/worksheet-bundle/'+manifest.script);
  // Disable the network path to the code entirely: reopening must use stored code.
  await page.route('**/worksheet-bundle/worksheet-*.js*',r=>r.abort('failed'));
  await page.reload();const cachedMs=await open();assert.equal(codeRequests,1);
  assert.notEqual(await page.evaluate(()=>window.lastData.items[0].name),firstData);
  assert.equal(await page.evaluate(()=>window.lastData.items.length),1265);
  await page.screenshot({path:path.join(out,'BAN_SAO_EDGE_MO_TU_BO_NHO_DEM.png')});
  assert.deepEqual(errors,[]);const result={ok:true,browser:process.env.TDP_BROWSER_CHANNEL||'msedge',first_open_ms:firstMs,cached_open_ms:cachedMs,code_downloads:codeRequests,rows:1265,fresh_data_after_reload:true,code_network_blocked_on_reload:true,errors};
  fs.writeFileSync(path.join(out,'KIEM_THU_CACHE.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;server.close();});
