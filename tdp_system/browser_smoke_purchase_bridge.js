"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:18773";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19233";
const fixturePath = process.argv[4];
if (!fixturePath) throw new Error("Canonical purchase fixture path is required");

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
  const deadline = Date.now() + (timeoutMilliseconds || 10000);
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
    await client.call("DOM.enable");
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client, 'document.readyState==="complete" && document.querySelector(\'[data-view="purchases"]\')', "app shell");
    await evaluate(client, 'document.querySelector(\'[data-view="purchases"]\').click()');
    await waitFor(client, 'document.getElementById("purchaseOrderInput") && document.body.innerText.includes("sheet đặt hàng")', "canonical purchase screen");
    const documentNode = await client.call("DOM.getDocument", { depth: -1, pierce: true });
    const inputNode = await client.call("DOM.querySelector", {
      nodeId: documentNode.root.nodeId,
      selector: "#purchaseOrderInput"
    });
    await client.call("DOM.setFileInputFiles", {
      nodeId: inputNode.nodeId,
      files: [fixturePath]
    });
    await evaluate(client, 'document.getElementById("purchaseOrderInput").dispatchEvent(new Event("change",{bubbles:true}))');
    await waitFor(client,
      'document.querySelector(\'[data-action="confirm-purchase-order-import"]\') && !document.querySelector(\'[data-action="confirm-purchase-order-import"]\').disabled && document.body.innerText.includes("Hỏng / thêm / giảm / thiếu") && document.body.innerText.includes("SL thực tế = Số lượng + Thêm − Hỏng − Giảm − Thiếu") && document.body.innerText.includes("Kho được phép giá 0")',
      "canonical preview");
    await evaluate(client, 'document.querySelector(\'[data-action="confirm-purchase-order-import"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("Số lượng trên sheet 7") && document.body.innerText.includes("Đặt NCC 8") && document.body.innerText.includes("Giá mua 50.000")',
      "confirmed canonical purchase");
    const result = await evaluate(client, `Promise.all([
      fetch('/api/bootstrap').then(r=>r.json()),
      fetch('/api/supplier-needs/1').then(r=>r.json()),
      fetch('/api/debts?from=2026-09-01&to=2026-09-01').then(r=>r.json())
    ]).then(([state,purchase,debt])=>({
      order:{qty:state.orders[0].qty,buyPrice:state.orders[0].buy_price,sellPrice:state.orders[0].sell_price},
      purchase:{
        format:purchase.format,
        count:purchase.rows.length,
        qty:purchase.rows[0].order_qty,
        buyPrice:purchase.rows[0].buy_price,
        damaged:purchase.rows[0].damaged_qty,
        added:purchase.rows[0].added_qty,
        reduced:purchase.rows[0].reduced_qty,
        missing:purchase.rows[0].missing_qty,
        amount:purchase.rows[0].amount
      },
      receivable:debt.contractors['C-BRIDGE'].period_charge,
      payable:debt.suppliers['S-BRIDGE'].period_charge
    }))`);
    assert.deepEqual(result, {
      order: { qty: 10, buyPrice: 0, sellPrice: 30000 },
      purchase: {
        format: "customer_canonical", count: 1, qty: 8, buyPrice: 50000,
        damaged: 1, added: 3, reduced: 1, missing: 0, amount: 400000
      },
      receivable: 300000,
      payable: 400000
    });
    process.stdout.write("purchase_bridge_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("purchase_bridge_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
