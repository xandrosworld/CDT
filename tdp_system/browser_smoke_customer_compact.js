"use strict";

const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const baseUrl = process.argv[2] || "http://127.0.0.1:8877";
const screenshotPath = process.argv[3] || "";
const chromePath = process.env.TDP_BROWSER_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const debugPort = 19342;
const devtoolsUrl = "http://127.0.0.1:" + debugPort;

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function waitHttp(url, timeoutMilliseconds) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (_error) {
      // Browser startup is still in progress.
    }
    await delay(150);
  }
  throw new Error("Timeout waiting for " + url);
}

async function connectDebugger() {
  const pages = await fetch(devtoolsUrl + "/json/list").then((response) => response.json());
  const page = pages.find((item) => item.type === "page");
  if (!page || !page.webSocketDebuggerUrl) throw new Error("No Chrome CDP page");
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  let nextId = 1;
  const pending = new Map();
  const listeners = [];
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const handler = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) handler.reject(new Error(message.error.message));
      else handler.resolve(message.result || {});
      return;
    }
    listeners.forEach((listener) => listener(message));
  });
  return {
    socket,
    onEvent(listener) { listeners.push(listener); },
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
  const deadline = Date.now() + (timeoutMilliseconds || 20000);
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return;
    await delay(150);
  }
  throw new Error("Timeout: " + label);
}

async function openView(client, view, readyExpression) {
  await evaluate(client, `(()=>{
    const button=document.querySelector('[data-view="${view}"]');
    if(!button) throw new Error('Missing navigation: ${view}');
    button.click();
  })()`);
  await waitFor(client, readyExpression, view + " view");
  await delay(250);
}

async function assertNoPageOverflow(client, label) {
  const result = await evaluate(client, `(()=>{
    const root=document.documentElement;
    const body=document.body;
    const badButtons=Array.from(document.querySelectorAll('button,a.btn')).filter((element)=>{
      const style=getComputedStyle(element);
      const rect=element.getBoundingClientRect();
      if(style.display==='none'||style.visibility==='hidden'||rect.width===0||rect.height===0) return false;
      const intersects=rect.bottom>0&&rect.top<innerHeight;
      return intersects&&(rect.left < -1 || rect.right > innerWidth + 1);
    }).map((element)=>({text:(element.innerText||'').trim(),left:element.getBoundingClientRect().left,right:element.getBoundingClientRect().right}));
    return {
      viewport:innerWidth,
      rootWidth:root.scrollWidth,
      bodyWidth:body.scrollWidth,
      badButtons
    };
  })()`);
  assert(result.rootWidth <= result.viewport + 1, label + " overflows the browser width: " + JSON.stringify(result));
  assert(result.bodyWidth <= result.viewport + 1, label + " body overflows: " + JSON.stringify(result));
  assert.deepEqual(result.badButtons, [], label + " has clipped actions");
}

async function main() {
  if (!fs.existsSync(chromePath)) throw new Error("Chrome not found: " + chromePath);
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "tdp-customer-ui-"));
  const browser = childProcess.spawn(chromePath, [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-background-networking",
    "--remote-debugging-port=" + debugPort,
    "--user-data-dir=" + profile,
    "--window-size=1440,1000",
    "about:blank"
  ], { stdio: "ignore", windowsHide: true });
  let client;
  const runtimeErrors = [];
  try {
    await waitHttp(devtoolsUrl + "/json/version", 20000);
    client = await connectDebugger();
    client.onEvent((message) => {
      if (message.method === "Runtime.exceptionThrown") {
        const details = message.params && message.params.exceptionDetails;
        runtimeErrors.push((details && (details.exception && details.exception.description || details.text)) || "Unknown runtime error");
      }
    });
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("DOM.enable");
    await client.call("Emulation.setDeviceMetricsOverride", {
      width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false
    });
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client,
      'document.readyState==="complete" && document.querySelectorAll(".daily-action-card").length===4',
      "four-item daily home");
    assert.equal(await evaluate(client, 'document.querySelectorAll(".daily-action-card").length'), 4);
    assert.equal(await evaluate(client, 'document.querySelectorAll("#content .stats-grid").length'), 0);
    assert.equal(await evaluate(client, 'document.querySelectorAll("[data-view]").length >= 14'), true);
    await assertNoPageOverflow(client, "home");

    await openView(client, "purchases", 'document.querySelector(".supplier-order-overview")');
    const purchaseLayout = await evaluate(client, `(()=>({
      cards:document.querySelectorAll('.supplier-order-card').length,
      productLists:document.querySelectorAll('.supplier-order-card .group-list').length,
      display:getComputedStyle(document.querySelector('.supplier-order-list')).display,
      direction:getComputedStyle(document.querySelector('.supplier-order-list')).flexDirection,
      copyButtons:document.querySelectorAll('[data-action="copy-supplier-image"]').length
    }))()`);
    assert(purchaseLayout.cards > 0, "supplier cards are missing");
    assert.equal(purchaseLayout.productLists, 0, "supplier product details must stay inside the generated image");
    assert(purchaseLayout.copyButtons > 0, "copy-image action is missing");
    assert.equal(purchaseLayout.display, "flex", "supplier list must use a single vertical flow");
    assert.equal(purchaseLayout.direction, "column", "supplier list must run from top to bottom");
    await assertNoPageOverflow(client, "supplier orders");

    const copyTarget = await evaluate(client, `(()=>{
      const card=Array.from(document.querySelectorAll('.supplier-order-card')).find((item)=>item.dataset.orderStatus!=='ordered');
      if(!card) return null;
      const button=card.querySelector('[data-action="copy-supplier-image"]');
      if(!button) return null;
      const key=card.dataset.supplierKey;
      button.click();
      return key;
    })()`);
    if (copyTarget) {
      await waitFor(client,
        `(()=>{const key=${JSON.stringify(copyTarget)};const card=Array.from(document.querySelectorAll('.supplier-order-card')).find((item)=>item.dataset.supplierKey===key);return card&&card.dataset.orderStatus==='ordered';})()`,
        "copy image automatically marks supplier ordered", 25000);
    }

    await openView(client, "deliveries", 'document.querySelector(".delivery-overview-card")');
    assert.equal(await evaluate(client, 'document.querySelectorAll(".delivery-details-panel").length'), 0);
    assert.equal(await evaluate(client, 'Boolean(document.querySelector("[data-action=toggle-delivery-details]"))'), true);
    await assertNoPageOverflow(client, "deliveries");

    await openView(client, "quotes", 'document.querySelectorAll(".quote-choice-card").length===2');
    assert.equal(await evaluate(client, 'document.querySelectorAll(".quote-choice-card").length'), 2);
    assert.equal(await evaluate(client, 'document.querySelectorAll(".quote-detail-panel").length'), 0);
    await assertNoPageOverflow(client, "quotes");

    await openView(client, "reports", 'document.querySelectorAll(".report-primary-card").length===1');
    assert.equal(await evaluate(client, 'document.querySelectorAll(".report-primary-card").length'), 1);
    await assertNoPageOverflow(client, "reports");

    await openView(client, "debts", 'document.querySelectorAll(".debt-menu-card").length===3');
    assert.equal(await evaluate(client, 'document.querySelectorAll(".debt-menu-card").length'), 3);
    assert.equal(await evaluate(client, 'document.querySelectorAll(".payable-workspace,.receivable-workspace").length'), 0);
    await assertNoPageOverflow(client, "debts");

    await openView(client, "inventory", 'document.querySelectorAll(".inventory-export-grid .btn").length===5');
    assert.equal(await evaluate(client, 'document.querySelectorAll(".inventory-export-grid .btn").length'), 5);
    assert.equal(await evaluate(client, 'document.querySelectorAll(".inventory-detail-panel").length'), 0);
    await assertNoPageOverflow(client, "inventory");

    await openView(client, "documents", 'document.querySelectorAll(".document-primary-card").length===2');
    assert.equal(await evaluate(client, 'document.querySelectorAll(".document-primary-card").length'), 2);
    assert.equal(await evaluate(client, 'document.querySelectorAll(".document-detail-panel").length'), 0);
    await assertNoPageOverflow(client, "documents");

    await openView(client, "printing", 'document.querySelector(".print-selection-card")');
    assert.equal(await evaluate(client, 'document.querySelector("input[name=printDocument]:checked").value'), "deliveries");
    const printBefore = await evaluate(client, `(()=>({
      rows:document.querySelectorAll('.print-batch-select').length,
      checked:document.querySelectorAll('.print-batch-select:checked').length,
      title:document.querySelector('.print-selection-card h3').innerText
    }))()`);
    assert(printBefore.rows > 0, "per-kitchen delivery selections are missing");
    assert.equal(printBefore.rows, printBefore.checked, "all delivery notes should be selected initially");
    assert(printBefore.title.includes("bếp"), "printing must identify kitchens explicitly");
    await evaluate(client, 'document.querySelector(".print-batch-select").click()');
    await waitFor(client,
      `document.querySelectorAll('.print-batch-select:checked').length===${printBefore.checked - 1}`,
      "individual delivery-note selection");
    await assertNoPageOverflow(client, "printing");

    await client.call("Emulation.setDeviceMetricsOverride", {
      width: 1024, height: 900, deviceScaleFactor: 1, mobile: false
    });
    await delay(400);
    await assertNoPageOverflow(client, "printing at 1024px");

    if (screenshotPath) {
      await client.call("Emulation.setDeviceMetricsOverride", {
        width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false
      });
      await evaluate(client, 'document.querySelector("[data-view=home]").click()');
      await waitFor(client, 'document.querySelectorAll(".daily-action-card").length===4', "home screenshot");
      await delay(1000);
      const screenshot = await client.call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
      fs.mkdirSync(path.dirname(path.resolve(screenshotPath)), { recursive: true });
      fs.writeFileSync(screenshotPath, Buffer.from(screenshot.data, "base64"));
    }

    assert.deepEqual(runtimeErrors, [], "browser runtime errors: " + runtimeErrors.join(" | "));
    process.stdout.write("customer_compact_browser_smoke=passed\n");
    process.stdout.write("home=four_actions\n");
    process.stdout.write("supplier_orders=vertical_summary_and_copy_marks_ordered\n");
    process.stdout.write("printing=select_all_or_individual_kitchens\n");
    process.stdout.write("responsive_widths=1440,1024\n");
  } finally {
    if (client) client.socket.close();
    if (!browser.killed) browser.kill();
    await delay(300);
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write("customer_compact_browser_smoke=failed: " + error.stack + "\n");
  process.exitCode = 1;
});
