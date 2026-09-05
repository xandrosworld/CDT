"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:18796";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19246";

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function connectDebugger() {
  const pages = await fetch(devtoolsUrl + "/json/list").then((response) => response.json());
  const page = pages.find((item) => item.type === "page");
  if (!page || !page.webSocketDebuggerUrl) throw new Error("No Edge CDP page");
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const handler = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) handler.reject(new Error(message.error.message));
    else handler.resolve(message.result || {});
  });
  return {
    socket,
    call(method, params) {
      const id = nextId++;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        socket.send(JSON.stringify({ id, method, params: params || {} }));
      });
    }
  };
}

async function evaluate(client, expression) {
  const result = await client.call("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true
  });
  if (result.exceptionDetails) {
    const exception = result.exceptionDetails.exception || {};
    throw new Error(exception.description || result.exceptionDetails.text || "page JavaScript error");
  }
  return result.result && result.result.value;
}

async function waitFor(client, expression, label, timeoutMilliseconds) {
  const deadline = Date.now() + (timeoutMilliseconds || 12000);
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return;
    await delay(150);
  }
  throw new Error("Timeout: " + label);
}

async function main() {
  const client = await connectDebugger();
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(
      client,
      'document.readyState==="complete" && document.querySelector(\'[data-view="payroll"]\')',
      "app shell"
    );
    const visibleModules = await evaluate(client, `(() => ({
      kitchen:document.querySelector('[data-view="kitchen"]').innerText,
      payroll:document.querySelector('[data-view="payroll"]').innerText
    }))()`);
    assert.match(visibleModules.kitchen, /Xưởng cơm \/ PO/);
    assert.match(visibleModules.payroll, /Chấm công & lương/);

    await evaluate(client, 'document.querySelector(\'[data-view="payroll"]\').click()');
    await waitFor(
      client,
      'document.getElementById("staffForm") && document.body.innerText.includes("Nguyễn An")',
      "payroll workspace"
    );
    const importContract = await evaluate(client, `(() => ({
      button:[...document.querySelectorAll('button')].some(x=>x.innerText.includes('Nạp file chấm công')),
      accept:document.getElementById('attendanceInput').getAttribute('accept'),
      exportHref:document.querySelector('a[href*="/api/export/payroll"]').getAttribute('href')
    }))()`);
    assert.equal(importContract.button, true);
    assert.equal(importContract.accept, ".xlsx,.xlsm");
    assert.match(importContract.exportHref, /month=2026-09/);

    await evaluate(client, `(() => {
      const form=document.getElementById('staffForm');
      const values={employee_code:'NV02',full_name:'Trần Bình',role_name:'Nhân viên',kitchen:'MAZDA',
        base_salary:'5200000',standard_days:'26',standard_hours:'8',
        bhxh_employee_rate:'0',bhxh_company_rate:'0'};
      for(const [key,value] of Object.entries(values)) form.elements[key].value=value;
      form.requestSubmit();
      return true;
    })()`);
    await waitFor(
      client,
      'document.body.innerText.includes("Trần Bình") && document.querySelector(".toast.show")',
      "staff refresh"
    );

    await evaluate(client, `(() => {
      const form=document.getElementById('attendanceForm');
      const values={employee_code:'NV02',work_date:'2026-09-03',normal_hours:'8',
        overtime_hours:'2',sunday_hours:'1',night_hours:'1',holiday_hours:'1',note:'Browser smoke'};
      for(const [key,value] of Object.entries(values)) form.elements[key].value=value;
      form.requestSubmit();
      return true;
    })()`);
    await waitFor(
      client,
      'document.querySelector("#content").innerText.includes("432.500 đ")',
      "attendance payroll calculation"
    );

    await evaluate(client, `(() => {
      const form=document.getElementById('payrollAdjustmentForm');
      const values={employee_code:'NV02',month:'2026-09',allowance:'100000',responsibility:'50000',
        advance:'25000',probation_deduction:'10000',bhxh_employee_amount:'20000',
        bhxh_company_amount:'30000',gross_override:'0',net_override:'0',note:'Điều chỉnh smoke'};
      for(const [key,value] of Object.entries(values)) form.elements[key].value=value;
      form.elements.use_override.checked=false;
      form.requestSubmit();
      return true;
    })()`);
    await waitFor(
      client,
      'document.querySelector("#content").innerText.includes("582.500 đ") && document.querySelector("#content").innerText.includes("527.500 đ")',
      "payroll adjustment refresh"
    );

    const apiState = await evaluate(client, `fetch('/api/payroll?month=2026-09').then(r=>r.json()).then(x=>{
      const row=x.items.find(item=>item.employee_code==='NV02');
      return {normal:row.normal_hours,overtime:row.overtime_hours,sunday:row.sunday_hours,
        night:row.night_hours,holiday:row.holiday_hours,allowance:row.allowance,
        responsibility:row.responsibility,advance:row.advance,probation:row.probation_deduction,
        employeeBhxh:row.bhxh_employee,companyBhxh:row.bhxh_company,
        gross:row.gross_salary,net:row.net_salary};
    })`);
    assert.deepEqual(apiState, {
      normal: 8, overtime: 2, sunday: 1, night: 1, holiday: 1,
      allowance: 100000, responsibility: 50000, advance: 25000, probation: 10000,
      employeeBhxh: 20000, companyBhxh: 30000, gross: 582500, net: 527500
    });

    const exportState = await evaluate(client, `fetch('/api/export/payroll?month=2026-09').then(async r=>({
      status:r.status,type:r.headers.get('content-type'),disposition:r.headers.get('content-disposition'),
      size:(await r.arrayBuffer()).byteLength
    }))`);
    assert.equal(exportState.status, 200);
    assert.match(exportState.type, /spreadsheetml/);
    assert.match(exportState.disposition, /Bang_luong_2026-09\.xlsx/);
    assert.ok(exportState.size > 1000);

    await client.call("Page.reload", { ignoreCache: true });
    await waitFor(
      client,
      'document.readyState==="complete" && document.querySelector(\'[data-view="payroll"]\')',
      "reloaded app shell"
    );
    await evaluate(client, 'document.querySelector(\'[data-view="payroll"]\').click()');
    await waitFor(
      client,
      'document.body.innerText.includes("Trần Bình") && document.body.innerText.includes("527.500 đ")',
      "persisted payroll after reload"
    );
    process.stdout.write("payroll_ui_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("payroll_ui_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
