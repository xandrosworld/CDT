// Production verification is read-only after login. Artifacts and credentials stay private.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.TDP_PLAYWRIGHT_MODULE||'playwright');
const [credentialFile,output]=process.argv.slice(2),base='https://tdp.up.railway.app';
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const credentials=JSON.parse(fs.readFileSync(credentialFile,'utf8'));
 const browser=await chromium.launch({channel:'chrome',headless:true}),page=await browser.newPage({viewport:{width:1440,height:900}});
 const report={started:new Date().toISOString(),errors:[],blocked:[],serverErrors:[],listRequests:[],checks:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('response',r=>{if(r.status()>=500)report.serverErrors.push({path:new URL(r.url()).pathname,status:r.status()});});
 page.on('request',r=>{if(r.url().includes('/api/invoice-workbench/invoices?'))report.listRequests.push(new URL(r.url()).search);});
 try{
  await page.addInitScript(()=>{if(!localStorage.getItem('tdp.invoiceWorkbenchFilters'))localStorage.setItem('tdp.invoiceWorkbenchFilters',JSON.stringify({direction:'input',date_from:'2026-08-01',date_to:'2026-08-31',status:'all',line_filter:'all',pending:true}));});
  await page.goto(base+'/login');await page.locator('[name=username]').fill(credentials.username);await page.locator('[name=password]').fill(credentials.password);
  await page.locator('button[type=submit]').click();await page.waitForURL(u=>u.pathname!='/login');
  await page.route('**/api/**',async route=>{const r=route.request();if(!['GET','HEAD','OPTIONS'].includes(r.method())){report.blocked.push({method:r.method(),path:new URL(r.url()).pathname});await route.abort();}else await route.continue();});
  await page.locator('#nav [data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor({timeout:60000});
  assert.equal(await page.locator('[data-action=toggle-pending-invoices]').getAttribute('aria-pressed'),'false');
  assert.match(await page.locator('.invoice-scope-label').innerText(),/01\/08\/2026.*31\/08\/2026/);
  const body=await page.locator('#content').innerText();assert(!body.includes('liên quan kỳ này'));
  assert(!(await page.locator('#invoice-list-count').innerText()).includes('4.776'));
  const response=await page.request.get(base+'/api/invoice-workbench/invoices?from=2026-08-01&to=2026-08-31');assert.equal(response.status(),200);
  const data=await response.json();report.counts=data.counts;report.totals=data.totals;
  assert.equal(data.counts.all,266);assert.equal(data.totals.issue_count,0);
  report.checks.push('Legacy all-period preference resets to August; API and visible scope match; misleading historical normalization count removed');
  await page.screenshot({path:path.join(output,'august-normal.png')});
  for(const width of [1440,1024]){
   await page.setViewportSize({width,height:900});await page.locator('.invoice-lines-card .tdp-open-sheet').click();
   assert(await page.locator('.invoice-scope-label').isVisible());await page.screenshot({path:path.join(output,'august-fullscreen-'+width+'.png')});
   await page.keyboard.press('Escape');assert(await page.locator('.invoice-lines-card .tdp-open-sheet').isVisible());
  }
  report.checks.push('Date scope visible in fullscreen at 1440/1024; reopening works');
  await page.reload();await page.locator('#nav [data-view=msmi]').click();await page.locator('#invoice-list-count').waitFor({timeout:60000});
  assert.equal(await page.locator('[data-action=toggle-pending-invoices]').getAttribute('aria-pressed'),'false');
  assert(!report.listRequests.some(q=>q.includes('scope=pending')));assert.deepEqual(report.errors,[]);assert.deepEqual(report.blocked,[]);assert.deepEqual(report.serverErrors,[]);
  report.checks.push('Reload retains August; no historical scope request or business write');report.ok=true;
 }catch(e){report.ok=false;report.failure=e.message.split('Call log:')[0];await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});process.exitCode=1;}
 finally{report.finished=new Date().toISOString();fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify({ok:report.ok,counts:report.counts,checks:report.checks,failure:report.failure}));}
})().catch(e=>{console.error(e.message.split('Call log:')[0]);process.exitCode=1;});
