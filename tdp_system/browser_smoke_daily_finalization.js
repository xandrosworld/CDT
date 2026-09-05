"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:18778";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19238";
const initialFile = process.argv[4];
const finalFile = process.argv[5];

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
    expression, awaitPromise: true, returnByValue: true
  });
  if (result.exceptionDetails) {
    const exception = result.exceptionDetails.exception || {};
    throw new Error(exception.description || result.exceptionDetails.text || "page JavaScript error");
  }
  return result.result && result.result.value;
}

async function waitFor(client, expression, label, timeoutMilliseconds) {
  const deadline = Date.now() + (timeoutMilliseconds || 15000);
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return;
    await delay(150);
  }
  throw new Error("Timeout: " + label);
}

async function upload(client, filePath) {
  const document = await client.call("DOM.getDocument", { depth: 1 });
  const input = await client.call("DOM.querySelector", {
    nodeId: document.root.nodeId, selector: "#excelInput"
  });
  await client.call("DOM.setFileInputFiles", {
    nodeId: input.nodeId, files: [filePath]
  });
  await evaluate(client,
    'document.getElementById("excelInput").dispatchEvent(new Event("change",{bubbles:true}))');
}

async function submitScope(client, sheetName) {
  await evaluate(client, `(()=>{
    const input=[...document.querySelectorAll('input[name="sheets"]')]
      .find(item=>item.value===${JSON.stringify(sheetName)});
    if(!input || input.disabled) throw new Error('Scope is not selectable: '+${JSON.stringify(sheetName)});
    input.checked=true;
    document.getElementById('orderForm').requestSubmit();
  })()`);
  await waitFor(client, 'document.getElementById("modalBackdrop").hidden', "scope confirmation");
}

async function currentState(client) {
  return evaluate(client, `fetch('/api/bootstrap').then(r=>r.json()).then(async bootstrap=>{
    const needs=await fetch('/api/supplier-needs/'+bootstrap.batch.id).then(r=>r.json());
    return {
      batchId:bootstrap.batch.id,
      revenue:bootstrap.summary.totals.revenue,
      delivered:bootstrap.orders[0].actual_delivered,
      sellPrice:bootstrap.orders[0].sell_price,
      purchaseQty:needs.required_qty,
      purchaseAmount:needs.total_amount
    };
  })`);
}

async function main() {
  if (!initialFile || !finalFile) throw new Error("Initial and final workbook paths are required");
  const client = await connectDebugger();
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("DOM.enable");
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client, 'document.readyState==="complete" && document.getElementById("excelInput")', "app shell");

    await upload(client, initialFile);
    await waitFor(client,
      '!document.getElementById("modalBackdrop").hidden && document.getElementById("modalTitle").innerText.includes("Chọn sheet đơn hàng")',
      "first-load preview");
    assert.equal(await evaluate(client,
      'document.querySelectorAll(\'input[name="sheets"]:checked\').length'), 1);
    await submitScope(client, "01.09");
    await waitFor(client, 'document.body.innerText.includes("Đã nhập 1 dòng")', "first load");
    assert.deepEqual(await currentState(client), {
      batchId: 1, revenue: 120000, delivered: 10, sellPrice: 12000,
      purchaseQty: 10, purchaseAmount: 0
    });

    await upload(client, finalFile);
    await waitFor(client,
      '!document.getElementById("modalBackdrop").hidden && document.getElementById("modalTitle").innerText.includes("Chốt dữ liệu ngày")',
      "finalization preview");
    const modalText = await evaluate(client, 'document.getElementById("orderForm").innerText');
    assert(modalText.includes("Bán/giao · đơn khách, doanh thu, phải thu"));
    assert(modalText.includes("Mua/phải trả · không sửa đơn khách"));
    assert(modalText.includes("diff: +1 thêm") || modalText.includes("diff: +0 thêm"));
    assert.equal(await evaluate(client,
      'document.querySelectorAll(\'input[name="sheets"]:checked\').length'), 0);
    await submitScope(client, "đặt hàng");
    await waitFor(client, 'document.body.innerText.includes("Đã chốt Mua/phải trả")', "purchase scope");
    assert.deepEqual(await currentState(client), {
      batchId: 1, revenue: 120000, delivered: 10, sellPrice: 12000,
      purchaseQty: 11, purchaseAmount: 99000
    });

    await upload(client, finalFile);
    await waitFor(client,
      '!document.getElementById("modalBackdrop").hidden && document.getElementById("modalTitle").innerText.includes("Chốt dữ liệu ngày")',
      "sales preview");
    assert.equal(await evaluate(client,
      'document.querySelectorAll(\'input[name="sheets"]:checked\').length'), 0);
    await submitScope(client, "01.09");
    await waitFor(client, 'document.body.innerText.includes("Đã chốt Bán/giao")', "sales scope");
    assert.deepEqual(await currentState(client), {
      batchId: 1, revenue: 128000, delivered: 8, sellPrice: 16000,
      purchaseQty: 11, purchaseAmount: 99000
    });
    process.stdout.write("daily_finalization_browser_smoke=passed\n");
    process.stdout.write("scope_defaults=none\n");
    process.stdout.write("purchase_then_sales=120000/99000->128000/99000\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("daily_finalization_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
