"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:8765";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:9223";

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function connectDebugger() {
  const pages = await fetch(devtoolsUrl + "/json/list").then((response) => response.json());
  const page = pages.find((item) => item.type === "page");
  if (!page || !page.webSocketDebuggerUrl) throw new Error("Không tìm thấy tab Edge CDP");
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
    throw new Error("Lỗi JavaScript trong trang: " + (exception.description || result.exceptionDetails.text || "unknown"));
  }
  return result.result && result.result.value;
}

async function waitFor(client, expression, label, timeoutMilliseconds) {
  const deadline = Date.now() + (timeoutMilliseconds || 10000);
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return;
    await delay(150);
  }
  throw new Error("Quá thời gian chờ: " + label);
}

async function changeField(client, id, value) {
  await evaluate(
    client,
    `(() => { const field = document.getElementById(${JSON.stringify(id)});` +
      ` if (!field) return false; field.value = ${JSON.stringify(value)};` +
      ` field.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`
  );
  await waitFor(
    client,
    `document.getElementById(${JSON.stringify(id)}) && document.getElementById(${JSON.stringify(id)}).value === ${JSON.stringify(value)}`,
    id
  );
}

async function main() {
  const client = await connectDebugger();
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client, 'document.readyState === "complete" && document.querySelector(\'[data-view="msmi"]\')', "app shell");
    await evaluate(client, 'document.querySelector(\'[data-view="msmi"]\').click()');
    await waitFor(client, 'document.getElementById("invoiceFrom") && document.body.innerText.includes("Hóa đơn đầu ra")', "invoice workbench");

    await evaluate(client, 'document.querySelector(\'[data-action="set-invoice-direction"][data-direction="output"]\').click()');
    await waitFor(client, 'document.querySelector(\'[data-direction="output"]\') && document.querySelector(\'[data-direction="output"]\').getAttribute("aria-selected") === "true"', "output tab");
    await changeField(client, "invoiceFrom", "2026-08-01");
    await changeField(client, "invoiceTo", "2026-08-31");

    await evaluate(client, 'document.querySelector(\'[data-action="prepare-invoice-sync"]\').click()');
    await waitFor(client, 'document.body.innerText.includes("#1") && document.body.innerText.includes("01/08/2026") && document.body.innerText.includes("31/08/2026") && document.body.innerText.includes("Khách đầu ra kiểm thử")', "synced output batch");
    await evaluate(client, `(() => {
      const input=document.querySelector('.invoice-mapping-input[data-direction="output"]');
      if(!input)return false;input.value='P-BROWSER-BOX';
      input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return true;
    })()`);
    await waitFor(client,
      'document.body.innerText.includes("P-BROWSER-BOX") && document.body.innerText.includes("Khác đơn vị")',
      "keyboard output mapping");
    await evaluate(client, `(() => {
      const input=document.querySelector('[id^="conversion_output_"]');
      if(!input)return false;input.value='30';
      input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return true;
    })()`);
    await waitFor(client,
      'document.body.innerText.includes("P-BROWSER-BOX · đã ghép") && document.body.innerText.includes("SL kho 30")',
      "output unit conversion");
    await evaluate(client, `(() => {
      window.confirm=()=>true;
      const button=document.querySelector('[data-action="post-invoice-output"]');
      if(!button)return false;button.click();return true;
    })()`);
    await waitFor(client,
      'document.body.innerText.includes("Đã ghi xuất kho") && !document.querySelector(\'[data-action="post-invoice-output"]\')',
      "confirmed output posting");
    const canonicalStock = await evaluate(client,
      `fetch('/api/invoice-inventory?as_of=2026-08-31').then(r=>r.json()).then(x=>({
        ok:x.ok, readOnly:x.read_only,
        qty:(x.items.find(i=>i.product_code==='P-BROWSER-BOX')||{}).closing_qty
      }))`);
    assert.deepEqual(canonicalStock, { ok: true, readOnly: true, qty: 970 });

    await client.call("Page.reload", { ignoreCache: true });
    await waitFor(client, 'document.readyState === "complete" && document.querySelector(\'[data-view="msmi"]\')', "reloaded app");
    await evaluate(client, 'document.querySelector(\'[data-view="msmi"]\').click()');
    await waitFor(client, 'document.getElementById("invoiceFrom") && document.querySelector(\'[data-direction="output"]\') && document.querySelector(\'[data-direction="output"]\').getAttribute("aria-selected") === "true"', "persisted filters");

    const result = await evaluate(client, `({
      direction: document.querySelector('[data-direction="output"]').getAttribute('aria-selected'),
      dateFrom: document.getElementById('invoiceFrom').value,
      dateTo: document.getElementById('invoiceTo').value,
      hasPreparedBatch: document.body.innerText.includes('#1'),
      hasBatchSourceStatus: document.body.innerText.includes('Lần cập nhật') && document.body.innerText.includes('Đã ghi kho'),
      hasOutputQueue: document.body.innerText.includes('Khách đầu ra kiểm thử') && document.body.innerText.includes('Đã phát hành (đã ánh xạ)') && document.body.innerText.includes('P-BROWSER-BOX · đã ghép') && document.body.innerText.includes('SL kho 30') && document.body.innerText.includes('Đã ghi xuất kho'),
      hasSafetyText: document.body.innerText.includes('không cộng hoặc trừ kho')
    })`);
    assert.deepEqual(result, {
      direction: "true",
      dateFrom: "2026-08-01",
      dateTo: "2026-08-31",
      hasPreparedBatch: true,
      hasBatchSourceStatus: true,
      hasOutputQueue: true,
      hasSafetyText: true
    });
    process.stdout.write("invoice_workbench_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("invoice_workbench_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
