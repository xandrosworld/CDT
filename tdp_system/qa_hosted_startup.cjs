// Read-only verification of startup paint and on-demand Excel on production.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const [credentialFile,output]=process.argv.slice(2),base='https://tdp.up.railway.app';
(async()=>{
 fs.mkdirSync(output,{recursive:true});const credentials=JSON.parse(fs.readFileSync(credentialFile,'utf8'));
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}});
 const report={started:new Date().toISOString(),errors:[],blocked:[],serverErrors:[],frames:[]};let engineRequests=0,appReleased=true;
 page.on('pageerror',e=>report.errors.push(e.message));page.on('response',r=>{if(r.status()>=500)report.serverErrors.push({path:new URL(r.url()).pathname,status:r.status()});});
 page.on('request',r=>{if(r.url().includes('/worksheet-bundle/worksheet.js'))engineRequests++;});
 try{
  await page.goto(base+'/login');await page.locator('[name=username]').fill(credentials.username);await page.locator('[name=password]').fill(credentials.password);await page.locator('button[type=submit]').click();await page.waitForURL(u=>u.pathname!='/login');
  await page.route('**/api/**',async route=>{const r=route.request();if(!['GET','HEAD','OPTIONS'].includes(r.method())){report.blocked.push({path:new URL(r.url()).pathname,method:r.method()});await route.abort();}else await route.continue();});
  await page.route('**/static/app.js?**',async route=>{await new Promise(r=>setTimeout(r,2500));appReleased=true;await route.continue();});
  for(const width of [1440,1024]){
   await page.setViewportSize({width,height:900});appReleased=false;await page.reload({waitUntil:'commit'});await page.locator('#sidebar').waitFor();
   // DOM geometry can be queried before blocking stylesheets permit any paint.
   await page.waitForFunction(()=>performance.getEntriesByType('paint').length>0);
   const height=await page.locator('#sidebar').evaluate(e=>e.getBoundingClientRect().height);assert.equal(height,42);assert.equal(appReleased,false);assert.equal(engineRequests,0);
   report.frames.push({width,sidebarHeight:height,appStillDelayed:true});await page.screenshot({path:path.join(output,'early-'+width+'.png')});
   await page.waitForFunction(()=>document.querySelector('#content')?.textContent.length>300);assert.equal(engineRequests,0);
  }
  report.startupAssets=await page.evaluate(()=>performance.getEntriesByType('resource').filter(r=>r.name.includes('/static/')).map(r=>({path:new URL(r.name).pathname,bytes:r.encodedBodySize})));
  await page.locator('#nav [data-view=settings]').click();await page.locator('#catalogProducts .tdp-open-sheet').click();await page.waitForFunction(()=>document.querySelector('.tdp-sheet-status')?.textContent.includes('Đã tải'),{},{timeout:60000});
  assert.equal(engineRequests,1);await page.screenshot({path:path.join(output,'excel-open.png')});await page.locator('.tdp-sheet-close').click();
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.blocked,[]);assert.deepEqual(report.serverErrors,[]);report.ok=true;report.engineRequests=engineRequests;
 }catch(e){report.ok=false;report.failure=e.message.split('Call log:')[0];await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});process.exitCode=1;}
 finally{report.finished=new Date().toISOString();fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify({ok:report.ok,frames:report.frames,engineRequests:report.engineRequests,failure:report.failure}));}
})().catch(e=>{console.error(e.message.split('Call log:')[0]);process.exitCode=1;});
