// Read-only surface inventory. Credentials, DOM inventories and screenshots stay private.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE || 'playwright');
const [base,credentialFile,output]=process.argv.slice(2);
if(!base?.startsWith('https://')||!output||!credentialFile)throw Error('HTTPS_URL PRIVATE_CREDENTIAL_JSON OUTPUT required');
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const credentials=JSON.parse(fs.readFileSync(credentialFile,'utf8'));
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 const report={base,started:new Date().toISOString(),screens:[],errors:[],failures:[],requests:[],blocked:[]};
 const active=new Set();
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('request',r=>{if(r.url().includes('/api/'))active.add(r);});
 page.on('requestfinished',r=>active.delete(r));page.on('requestfailed',r=>active.delete(r));
 page.on('response',r=>{if(r.url().includes('/api/'))report.requests.push({method:r.request().method(),path:new URL(r.url()).pathname,status:r.status()});});
 const settle=async()=>{const until=Date.now()+45000;while(active.size&&Date.now()<until)await page.waitForTimeout(100);await page.waitForTimeout(250);};
 const capture=async name=>{
   await settle();
   const controls=await page.locator('#content').evaluate(root=>[...root.querySelectorAll('button,a,input,select,textarea,summary')].map(el=>({
     tag:el.tagName,id:el.id,name:el.name||'',type:el.type||'',action:el.dataset.action||'',view:el.dataset.view||'',
     label:(el.getAttribute('aria-label')||el.innerText||el.getAttribute('title')||el.placeholder||'').trim().slice(0,150),
     disabled:!!el.disabled,visible:!!el.getClientRects().length,href:el.getAttribute('href')||'',
     options:el.tagName==='SELECT'?[...el.options].map(o=>({value:o.value,label:o.textContent})):undefined
   })));
   const text=await page.locator('#content').innerText();
   const record={name,controls,text,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)};
   report.screens.push(record);await page.screenshot({path:path.join(output,name+'.png')});
   fs.writeFileSync(path.join(output,'surface.json'),JSON.stringify(report,null,2));
 };
 const attempt=async(name,fn)=>{try{await fn();await capture(name);}catch(e){report.failures.push({name,error:e.message});await page.screenshot({path:path.join(output,name+'-failure.png')});}};
 try{
   await page.goto(base+'/login');assert.equal((await page.request.get(base+'/api/bootstrap')).status(),401);
   await page.locator('[name=username]').fill(credentials.username);await page.locator('[name=password]').fill(credentials.password);
   await page.locator('button[type=submit]').click();await page.waitForURL(u=>u.pathname!='/login');
   await page.route('**/api/**',async route=>{
     const r=route.request(),url=new URL(r.url());
     const allowed=['GET','HEAD','OPTIONS'].includes(r.method())||(r.method()==='POST'&&url.pathname==='/api/documents/preview');
     if(!allowed){report.blocked.push({method:r.method(),path:url.pathname});await route.abort();}else await route.continue();
   });
   await settle();
   const nav=await page.locator('#nav [data-view]').evaluateAll(list=>list.map(e=>e.dataset.view));
   for(const view of nav){
     await attempt(view,async()=>{await page.locator('#nav [data-view="'+view+'"]').click();await settle();});
     if(view==='debts')for(const section of ['receivable-kitchen','receivable-total','payable']){
       await attempt('debts-'+section,async()=>{
         await page.locator('#nav [data-view=home]').click();await page.locator('#nav [data-view=debts]').click();await settle();
         await page.locator('[data-section="'+section+'"]').click();
       });
     }
     if(view==='settings')await attempt('settings-expanded',async()=>{
       for(const summary of await page.locator('#content details > summary').all())await summary.click();
     });
     if(view==='inventory')await attempt('inventory-period-dialog',async()=>{await page.locator('[data-action=open-inventory-close]').click();await settle();await page.locator('.close-period-dialog').click();});
   }
   for(const width of [1920,1366,1024]){
     await page.setViewportSize({width,height:900});
     for(const view of ['home','orders','msmi','inventory','settings'])await attempt(view+'-'+width,async()=>{await page.locator('#nav [data-view="'+view+'"]').click();});
   }
   report.finished=new Date().toISOString();report.serverErrors=report.requests.filter(r=>r.status>=500);
   report.ok=!report.errors.length&&!report.blocked.length&&!report.failures.length&&!report.serverErrors.length;
   fs.writeFileSync(path.join(output,'surface.json'),JSON.stringify(report,null,2));
   console.log(JSON.stringify({ok:report.ok,screens:report.screens.length,controls:report.screens.reduce((n,s)=>n+s.controls.length,0),failures:report.failures,errors:report.errors,blocked:report.blocked}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
