"use strict";

const assert = require("node:assert/strict");
const baseUrl = process.argv[2] || "http://127.0.0.1:8767";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:9224";

function delay(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function connect() {
  const pages = await fetch(devtoolsUrl + "/json/list").then((response) => response.json());
  const page = pages.find((item) => item.type === "page");
  if (!page || !page.webSocketDebuggerUrl) throw new Error("Không tìm thấy tab Edge CDP");
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  let id = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const item = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) item.reject(new Error(message.error.message));
    else item.resolve(message.result || {});
  });
  return {
    socket,
    call(method, params) {
      const requestId = id++;
      return new Promise((resolve, reject) => {
        pending.set(requestId, { resolve, reject });
        socket.send(JSON.stringify({ id: requestId, method, params: params || {} }));
      });
    }
  };
}

async function evaluate(client, expression) {
  const response = await client.call("Runtime.evaluate", {
    expression, awaitPromise: true, returnByValue: true
  });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text || "Lỗi JavaScript");
  return response.result && response.result.value;
}

async function waitFor(client, expression, label) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return;
    await delay(150);
  }
  throw new Error("Quá thời gian chờ: " + label);
}

async function setField(client, id, value) {
  await evaluate(client, `(() => { const field=document.getElementById(${JSON.stringify(id)});` +
    `if(!field)return false;field.value=${JSON.stringify(value)};` +
    `field.dispatchEvent(new Event("change",{bubbles:true}));return true;})()`);
  await waitFor(client,
    `document.getElementById(${JSON.stringify(id)}) && document.getElementById(${JSON.stringify(id)}).value===${JSON.stringify(value)}`,
    id);
}

async function main() {
  const client = await connect();
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client, 'document.readyState==="complete" && document.querySelector(\'[data-view="msmi"]\')', "app");
    await evaluate(client, 'document.querySelector(\'[data-view="msmi"]\').click()');
    await waitFor(client, 'document.getElementById("invoiceFrom")', "workbench");
    await setField(client, "invoiceFrom", "2026-08-01");
    await setField(client, "invoiceTo", "2026-08-31");
    await evaluate(client, 'document.querySelector(\'[data-action="prepare-invoice-sync"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("NCC kiểm thử") && document.body.innerText.includes("#1")',
      "synced input invoices");
    await evaluate(client, `(() => {
      const input=document.querySelector('.invoice-mapping-input[data-direction="input"]');
      if(!input)return false;input.value='P-BROWSER-BOX';
      input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return true;
    })()`);
    await waitFor(client,
      'document.body.innerText.includes("P-BROWSER-BOX") && document.body.innerText.includes("Khác đơn vị")',
      "keyboard input mapping");
    await evaluate(client, `(() => {
      const input=document.querySelector('[id^="conversion_input_"]');
      if(!input)return false;input.value='30';
      input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return true;
    })()`);
    await waitFor(client,
      'document.body.innerText.includes("P-BROWSER-BOX") && document.body.innerText.includes("SL kho 30")',
      "input unit conversion");
    await evaluate(client, `(() => {
      window.confirm=()=>true;
      const button=document.querySelector('[data-action="create-msmi-receipt"]');
      if(!button)return false;button.click();return true;
    })()`);
    await waitFor(client,
      'document.body.innerText.includes("Đã ghi nhập kho") && !document.querySelector(\'[data-action="create-msmi-receipt"]\')',
      "converted receipt posting");
    const result = await evaluate(client, `({
      inputSelected: document.querySelector('[data-direction="input"]').getAttribute('aria-selected'),
      dateFrom: document.getElementById('invoiceFrom').value,
      dateTo: document.getElementById('invoiceTo').value,
      hasBatch: document.body.innerText.includes('#1'),
      hasSeller: document.body.innerText.includes('NCC kiểm thử'),
      excludesUnlinkedInvoice: !document.body.innerText.includes('NCC NGOÀI PHẠM VI'),
      hasKeyboardMapping: document.body.innerText.includes('P-BROWSER-BOX') && document.body.innerText.includes('SL kho 30'),
      hasPostedReceipt: document.body.innerText.includes('Đã ghi nhập kho'),
      hasReadOnly: document.body.innerText.includes('Chỉ đọc nguồn'),
      hasMappingGate: document.body.innerText.includes('Chưa ghép mã')
    })`);
    assert.deepEqual(result, {
      inputSelected: "true",
      dateFrom: "2026-08-01",
      dateTo: "2026-08-31",
      hasBatch: true,
      hasSeller: true,
      excludesUnlinkedInvoice: true,
      hasKeyboardMapping: true,
      hasPostedReceipt: true,
      hasReadOnly: true,
      hasMappingGate: true
    });
    process.stdout.write("invoice_input_sync_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("invoice_input_sync_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
