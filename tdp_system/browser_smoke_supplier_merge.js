"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:18774";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19234";

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
    await waitFor(client,
      'document.readyState==="complete" && document.querySelector(\'[data-view="purchases"]\')',
      "app shell");
    await evaluate(client, 'document.querySelector(\'[data-view="purchases"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("Quy tắc dồn cố định:") && document.body.innerText.includes("Tự dồn tên hàng giống nhau") && document.body.innerText.includes("Tự dồn Cà rốt") && document.body.innerText.includes("Giữ riêng theo rule Hoài") && document.body.innerText.includes("2 dòng gốc · 1 dòng gửi")',
      "exact merge policy UI");

    const initial = await evaluate(client, `Promise.all([
      fetch('/api/supplier-needs/1').then(r=>r.json()),
      fetch('/api/supplier-rules/DUNG',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({combine_kitchens:false})}).then(r=>({status:r.status}))
    ]).then(([purchase,locked])=>({
      raw:purchase.raw_line_count,
      presented:purchase.presented_line_count,
      groups:purchase.groups.length,
      autoGroups:purchase.groups.filter(g=>g.automatic_merge).map(g=>({label:g.policy_label,raw:g.raw_line_count,shown:g.presented_line_count,qty:g.items[0].order_qty,refs:g.items[0].source_refs.length})),
      hoaiSeparate:purchase.groups.filter(g=>g.policy_label==='Giữ riêng theo rule Hoài').length,
      huongGroups:purchase.groups.filter(g=>String(g.supplier).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes('huong')).length,
      toggleButtons:document.querySelectorAll('[data-action="toggle-supplier-rule"]').length,
      lockedStatus:locked.status
    }))`);
    assert.deepEqual(initial, {
      raw: 8,
      presented: 6,
      groups: 6,
      autoGroups: [
        { label: "Tự dồn tên hàng giống nhau", raw: 2, shown: 1, qty: 5, refs: 2 },
        { label: "Tự dồn Cà rốt", raw: 2, shown: 1, qty: 9, refs: 2 }
      ],
      hoaiSeparate: 2,
      huongGroups: 2,
      toggleButtons: 2,
      lockedStatus: 409
    });

    await evaluate(client,
      'document.querySelector(\'[data-action="toggle-supplier-rule"][data-supplier*="HƯƠNG"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("Đã gộp đơn NCC qua nhiều bếp")',
      "manual non-policy grouping");
    const manual = await evaluate(client, `fetch('/api/supplier-needs/1').then(r=>r.json()).then(p=>{
      const groups=p.groups.filter(g=>String(g.supplier).normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().includes('huong'));
      return {groups:groups.length,raw:groups[0].raw_line_count,shown:groups[0].presented_line_count,manual:groups[0].manual_combine};
    })`);
    assert.deepEqual(manual, { groups: 1, raw: 2, shown: 2, manual: true });
    process.stdout.write("supplier_merge_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("supplier_merge_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
