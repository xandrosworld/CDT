const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
async function main() {
  const out=process.argv[2], expected=JSON.parse(fs.readFileSync(path.join(out,'summary.json'),'utf8'));
  const page=await fetch('http://127.0.0.1:19430/json/new?about:blank',{method:'PUT'}).then(r=>r.json());
  const ws=new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((yes,no)=>{ws.onopen=yes;ws.onerror=no;});
  let seq=0;const pending=new Map(),errors=[],writes=[];
  const call=(method,params={})=>new Promise((yes,no)=>{const id=++seq;pending.set(id,[yes,no]);ws.send(JSON.stringify({id,method,params}));});
  ws.onmessage=event=>{const m=JSON.parse(event.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);
    if(m.method==='Fetch.requestPaused'){const p=m.params;if(p.request.method!=='GET'){writes.push(p.request.url);call('Fetch.failRequest',{requestId:p.requestId,errorReason:'BlockedByClient'});}else call('Fetch.continueRequest',{requestId:p.requestId});}
    if(pending.has(m.id)){const[y,n]=pending.get(m.id);pending.delete(m.id);m.error?n(Error(m.error.message)):y(m.result);}};
  const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  const wait=async expression=>{const end=Date.now()+40000;while(Date.now()<end){if(await ev(expression))return;await new Promise(r=>setTimeout(r,150));}throw Error(expression);};
  const click=async selector=>{await wait(`document.querySelector(${JSON.stringify(selector)})`);await ev(`document.querySelector(${JSON.stringify(selector)}).click()`);};
  const screenshot=async name=>fs.writeFileSync(path.join(out,name),Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  try {
    await call('Runtime.enable');await call('Page.enable');await call('Fetch.enable',{patterns:[{urlPattern:'*'}]});
    await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:'http://127.0.0.1:18830'});
    await wait(`document.querySelector('#batchSelect option[value="${expected.batch_id}"]')`);
    await ev(`(()=>{const e=document.querySelector('#batchSelect');e.value='${expected.batch_id}';e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    await click('[data-view="purchases"]');
    await wait(`document.querySelectorAll('.purchase-money-adjustments tbody tr').length===2`);
    const rows=await ev(`Array.from(document.querySelectorAll('.purchase-money-adjustments tbody tr'),r=>r.textContent)`);
    assert.ok(rows.every(r=>r.includes('phong')));assert.match(rows.join(' '),/117,000/);assert.match(rows.join(' '),/90,000/);
    assert.match(await ev(`document.querySelector('.purchase-money-adjustments tfoot').textContent`),/207,000/);
    await ev(`document.querySelector('.purchase-money-adjustments').scrollIntoView()`);await screenshot('phong-purchases.png');
    for(const width of [1440,1024]){await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});assert.ok(await ev('document.documentElement.scrollWidth<=innerWidth+1'));}
    await click('[data-view="debts"]');await click('[data-action="open-debt-section"][data-section="payable"]');
    await wait(`document.querySelector('#payableSupplier option[value="phong"]')`);
    await ev(`(()=>{document.querySelector('#payableFrom').value='2026-09-03';document.querySelector('#payableTo').value='2026-09-03';document.querySelector('#payableSupplier').value='phong';document.querySelector('#debtPeriodForm').requestSubmit();})()`);
    await wait(`document.querySelector('.payable-stats')?.textContent.includes('790,040')`);
    const deductions=await ev(`Array.from(document.querySelectorAll('.payable-ledger-table tbody tr')).filter(r=>r.textContent.includes('Trừ tiền mua hộ do hàng hỏng')).map(r=>({text:r.textContent,disabled:r.querySelector('input[type="checkbox"]').disabled}))`);
    assert.equal(deductions.length,2);assert.ok(deductions.every(r=>r.disabled));
    const api=await ev(`fetch('/api/debts/payables/ledger?from=2026-09-03&to=2026-09-03&supplier=phong&status=open,partially_paid&limit=5000').then(r=>r.json())`);
    assert.equal(api.summary.filtered_amount,expected.phong_net);
    const accounts=await ev(`fetch('/api/debts?from=2026-09-03&to=2026-09-03').then(r=>r.json())`);
    assert.equal(accounts.suppliers.phong.period_charge,expected.phong_net);
    await wait(`!document.querySelector('.debt-period-toolbar')?.parentElement.textContent.includes('Đang nạp tổng công nợ đúng kỳ')`);
    assert.equal(await ev(`document.querySelectorAll('.error-summary').length`),0);
    await ev(`document.querySelector('.payable-workspace').scrollIntoView()`);
    await screenshot('phong-payable.png');
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
    fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify({ok:true,deduction_rows:2,net:api.summary.filtered_amount,account_period_charge:accounts.suppliers.phong.period_charge,errors,writes},null,2));
    console.log('PHONG_BROWSER_OK');
  } finally {ws.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
