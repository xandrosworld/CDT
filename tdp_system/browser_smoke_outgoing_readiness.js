"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");

async function main() {
  const pages = await fetch("http://127.0.0.1:19309/json/list").then(r => r.json());
  const ws = new WebSocket(pages.find(p => p.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let seq = 0;
  const pending = new Map();
  ws.onmessage = event => {
    const msg = JSON.parse(event.data);
    if (pending.has(msg.id)) {
      const [resolve, reject] = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(Error(msg.error.message)) : resolve(msg.result);
    }
  };
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq; pending.set(id, [resolve, reject]); ws.send(JSON.stringify({id, method, params}));
  });
  const evaluate = async expression => {
    const result = await call("Runtime.evaluate", {expression, awaitPromise: true, returnByValue: true});
    if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const wait = async expression => {
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      if (await evaluate(expression)) return;
      await new Promise(r => setTimeout(r, 100));
    }
    throw Error("Timeout: " + expression);
  };
  try {
    await call("Page.enable");
    await call("Page.navigate", {url: "http://127.0.0.1:18799"});
    await wait(`document.querySelector('[data-view="documents"]') && document.querySelector('#batchSelect option')`);
    await evaluate(`document.querySelector('[data-view="documents"]').click()`);
    await wait(`document.querySelector('.invoice-readiness .readiness-totals')`);
    let values = await evaluate(`Array.from(document.querySelectorAll('.invoice-readiness .readiness-totals strong')).map(e => e.textContent)`);
    assert.deepEqual(values, ["10", "0", "0", "7", "3"]);
    let text = await evaluate(`document.querySelector('.invoice-readiness').textContent`);
    assert.ok(text.includes("140") && text.includes("60") && text.includes("Thiếu 3 kg"));
    const created = await evaluate(`(async () => {
      const response = await fetch('/api/outgoing-invoices/draft/' + document.querySelector('#batchSelect').value, {method:'POST'});
      return await response.json();
    })()`);
    assert.equal(created.pending_qty, 3);
    await evaluate(`document.querySelector('[data-action="refresh-outgoing-readiness"]').click()`);
    await wait(`Array.from(document.querySelectorAll('.invoice-readiness .readiness-totals strong')).map(e => e.textContent).join(',') === '10,7,0,0,3'`);
    await evaluate(`fetch('/fixture/add-three', {method:'POST'}).then(r => r.json())`);
    await evaluate(`document.querySelector('[data-action="refresh-outgoing-readiness"]').click()`);
    await wait(`Array.from(document.querySelectorAll('.invoice-readiness .readiness-totals strong')).map(e => e.textContent).join(',') === '10,7,0,3,0'`);
    const image = await call("Page.captureScreenshot", {format:"png", captureBeyondViewport:false});
    fs.writeFileSync("D:/TDP_TEMP_OUTGOING/readiness-browser.png", Buffer.from(image.data, "base64"));
    console.log("PASS: UI 10/7/3, money, shortage reason, reservation and replenishment; synthetic DB only.");
  } finally { ws.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
