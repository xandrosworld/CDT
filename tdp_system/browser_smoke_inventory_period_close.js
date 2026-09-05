"use strict";

const assert = require("node:assert/strict");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const baseUrl = process.argv[2] || "http://127.0.0.1:18826";
const screenshotPath = process.argv[3] || "";
const chromePath = process.env.TDP_BROWSER_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const debugPort = 19343;
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
    throw new Error(result.exceptionDetails.exception && result.exceptionDetails.exception.description ||
      result.exceptionDetails.text || "Evaluation failed");
  }
  return result.result && result.result.value;
}

async function waitFor(client, expression, label, timeoutMilliseconds = 20000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    if (await evaluate(client, "Boolean(" + expression + ")")) return;
    await delay(150);
  }
  throw new Error("Timeout: " + label);
}

async function main() {
  if (!fs.existsSync(chromePath)) throw new Error("Chrome not found: " + chromePath);
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "tdp-month-close-ui-"));
  const browser = childProcess.spawn(chromePath, [
    "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-background-networking",
    "--remote-debugging-port=" + debugPort, "--user-data-dir=" + profile,
    "--window-size=1440,1000", "about:blank"
  ], { stdio: "ignore", windowsHide: true });
  let client;
  const runtimeErrors = [];
  try {
    await waitHttp(devtoolsUrl + "/json/version", 20000);
    client = await connectDebugger();
    client.onEvent((message) => {
      if (message.method === "Runtime.exceptionThrown") {
        const details = message.params && message.params.exceptionDetails;
        runtimeErrors.push((details && (details.exception && details.exception.description || details.text)) ||
          "Unknown runtime error");
      }
      if (message.method === "Page.javascriptDialogOpening") {
        client.call("Page.handleJavaScriptDialog", { accept: true }).catch((error) => {
          runtimeErrors.push(error.message);
        });
      }
    });
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("Emulation.setDeviceMetricsOverride", {
      width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false
    });
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client, 'document.readyState==="complete" && document.querySelector("[data-view=inventory]")', "home");
    await evaluate(client, 'document.querySelector("[data-view=inventory]").click()');
    await waitFor(client, 'document.querySelector(".inventory-month-close")', "inventory month close");
    await evaluate(client, `(()=>{
      const from=document.getElementById('inventoryFrom');
      from.value='2026-08-01';
      from.dispatchEvent(new Event('change',{bubbles:true}));
      return true;
    })()`);
    await delay(300);
    await evaluate(client, `(()=>{
      const to=document.getElementById('inventoryTo');
      to.value='2026-08-31';
      to.dispatchEvent(new Event('change',{bubbles:true}));
      return true;
    })()`);
    await waitFor(client, 'document.querySelector("[data-action=close-inventory-month]")', "August close action");
    const before = await evaluate(client, `(()=>( {
      text:document.querySelector('.inventory-month-close').innerText,
      overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth,
      buttons:document.querySelectorAll('[data-action=close-inventory-month]').length
    }))()`);
    assert(before.text.includes("Tháng 08/2026"));
    assert(before.text.includes("tồn đầu tháng 09/2026"));
    assert(before.text.includes("Tổng lượng tồn cuối"));
    assert(before.text.includes("Tổng giá trị tồn cuối"));
    assert.equal(before.buttons, 1);
    assert.equal(before.overflow, false);

    await evaluate(client, `(()=>{
      window.__monthCloseClickSeen=0;
      document.getElementById('content').addEventListener('click',()=>window.__monthCloseClickSeen++,{once:true});
      window.confirm=()=>true;
      document.getElementById('inventoryCloseActor').value='Người kiểm thử chốt tháng';
      document.querySelector('[data-action=close-inventory-month]').click();
      return true;
    })()`);
    await delay(1500);
    const afterClick = await evaluate(client, `(()=>( {
      closeText:document.querySelector('.inventory-month-close').innerText,
      toast:document.getElementById('toast').innerText,
      toastClass:document.getElementById('toast').className,
      clickSeen:window.__monthCloseClickSeen,
      disabled:document.querySelector('[data-action=close-inventory-month]') &&
        document.querySelector('[data-action=close-inventory-month]').disabled,
      button:document.querySelector('[data-action=close-inventory-month]') &&
        document.querySelector('[data-action=close-inventory-month]').innerText
    }))()`);
    if (!afterClick.closeText.includes("Đã chốt")) {
      throw new Error("Close click did not complete: " + JSON.stringify(afterClick) +
        " runtime=" + JSON.stringify(runtimeErrors));
    }
    await waitFor(client, 'document.querySelector(".inventory-month-close").innerText.includes("Đã chốt")', "closed state");
    assert.equal(await evaluate(client,
      'document.querySelectorAll("[data-action=reopen-inventory-month]").length'), 1);

    await client.call("Emulation.setDeviceMetricsOverride", {
      width: 1024, height: 900, deviceScaleFactor: 1, mobile: false
    });
    await delay(300);
    assert.equal(await evaluate(client,
      'document.documentElement.scrollWidth>document.documentElement.clientWidth'), false);

    if (screenshotPath) {
      const screenshot = await client.call("Page.captureScreenshot", {
        format: "png", captureBeyondViewport: false
      });
      fs.mkdirSync(path.dirname(path.resolve(screenshotPath)), { recursive: true });
      fs.writeFileSync(screenshotPath, Buffer.from(screenshot.data, "base64"));
    }
    assert.deepEqual(runtimeErrors, [], "browser runtime errors: " + runtimeErrors.join(" | "));
    process.stdout.write("inventory_period_close_browser_smoke=passed\n");
    process.stdout.write("states=preview,closed,reopen_available\n");
    process.stdout.write("responsive_widths=1440,1024\n");
  } finally {
    if (client) client.socket.close();
    if (!browser.killed) browser.kill();
    await delay(300);
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write("inventory_period_close_browser_smoke=failed: " + error.stack + "\n");
  process.exitCode = 1;
});
