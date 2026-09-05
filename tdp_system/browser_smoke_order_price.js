"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:8771";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:9231";

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

async function setInput(client, id, value) {
  await evaluate(client, `(() => {
    const input=document.getElementById(${JSON.stringify(id)});
    if(!input)return false;input.value=${JSON.stringify(value)};
    input.dispatchEvent(new Event('input',{bubbles:true}));return true;
  })()`);
}

async function main() {
  const client = await connectDebugger();
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client, 'document.readyState==="complete" && document.querySelector(\'[data-view="orders"]\')', "app shell");
    await evaluate(client, 'document.querySelector(\'[data-view="orders"]\').click()');
    await waitFor(client, 'document.querySelector(".quick-sell-price") && document.getElementById("priceOverrideReason")', "inline price grid");
    await setInput(client, "priceOverrideActor", "Browser Operator");
    await setInput(client, "priceOverrideReason", "Keyboard confirmation");
    await evaluate(client, `(() => {
      const input=document.querySelector('.quick-sell-price');
      input.value='15000';input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));return true;
    })()`);
    await waitFor(client,
      'document.querySelector(".quick-sell-price") && document.querySelector(".quick-sell-price").value==="15000" && document.body.innerText.includes("Giá override · v2")',
      "Enter saves one override");

    await setInput(client, "priceOverrideReason", "Bulk button confirmation");
    await evaluate(client, `(() => {
      const input=document.querySelector('.quick-sell-price');
      input.value='16000';input.dispatchEvent(new Event('input',{bubbles:true}));
      document.querySelector('[data-action="save-price-overrides"]').click();return true;
    })()`);
    await waitFor(client,
      'document.querySelector(".quick-sell-price") && document.querySelector(".quick-sell-price").value==="16000" && document.body.innerText.includes("Giá override · v3")',
      "bulk button saves changed prices");
    const result = await evaluate(client, `Promise.all([
      fetch('/api/bootstrap').then(r=>r.json()),
      fetch('/api/orders/sell-price-overrides?batch_id=1').then(r=>r.json())
    ]).then(([state,history])=>({
      price:state.orders[0].sell_price,
      revision:state.orders[0].sell_price_revision,
      revenue:state.summary.totals.revenue,
      history:history.items.map(x=>({actor:x.actor,reason:x.reason,newPrice:x.new_price,newRevision:x.new_revision}))
    }))`);
    assert.deepEqual(result, {
      price: 16000,
      revision: 3,
      revenue: 32000,
      history: [
        { actor: "Browser Operator", reason: "Bulk button confirmation", newPrice: 16000, newRevision: 3 },
        { actor: "Browser Operator", reason: "Keyboard confirmation", newPrice: 15000, newRevision: 2 }
      ]
    });
    process.stdout.write("order_price_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("order_price_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
