const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, 'static/app.js'), 'utf8');
const code = script.slice(script.indexOf('  function friendlyErrorMessage('), script.indexOf('  function setBusy('));
const context = vm.createContext({Error});
vm.runInContext(code, context);
const message = 'Không có hóa đơn VAT đã phát hành trong kỳ của nhà thầu.';
const generic = 'Không tìm thấy chức năng này. Hãy tải lại trang; nếu vẫn còn lỗi, liên hệ người hỗ trợ.';
(async () => {
  // Both the preview API and download button must keep domain-specific 404s.
  context.fetch = async () => ({ok:false,status:404,headers:{get:()=> 'application/json'},
    json:async()=>({ok:false,error:message,code:'issued_invoice_scope_empty'})});
  await assert.rejects(context.api('/payment-scope/ATV'), e=>e.message===message && e.payload.code==='issued_invoice_scope_empty');
  await assert.rejects(context.downloadFile('/statement/ATV'), e=>e.message===message);
  // A genuinely missing HTML route still has a readable generic error.
  context.fetch = async () => ({ok:false,status:404,headers:{get:()=> 'text/html'}});
  await assert.rejects(context.api('/missing-route'), e=>e.message===generic);
  await assert.rejects(context.downloadFile('/missing-route'), e=>e.message===generic);
  assert.equal(context.friendlyErrorMessage('The requested URL was not found on the server.',404),generic);
  assert.equal(context.friendlyErrorMessage('Không đủ tồn kho',409),'Không đủ tồn kho');
  console.log('6 API/download error checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
