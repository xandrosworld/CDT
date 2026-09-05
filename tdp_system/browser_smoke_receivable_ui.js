"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:18791";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19241";

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
    await waitFor(client,
      'document.readyState==="complete" && document.querySelector(\'[data-view="debts"]\')',
      "app shell");
    await evaluate(client, `(() => {
      localStorage.removeItem('tdp.receivableFilters');
      localStorage.removeItem('tdp.payableFilters');
      location.reload();
      return true;
    })()`);
    await waitFor(client,
      'document.readyState==="complete" && document.querySelector(\'[data-view="debts"]\')',
      "clean app shell");
    await evaluate(client, `(() => {
      document.querySelector('[data-view="debts"]').click();
      if (document.querySelectorAll('.debt-menu-card').length !== 3) throw new Error('Debt overview must have three choices');
      if (document.querySelector('.receivable-workspace')) throw new Error('Debt details must stay hidden on overview');
      document.querySelector('[data-section="receivable-kitchen"]').click();
      return true;
    })()`);
    await waitFor(client,
      'document.querySelectorAll(".receivable-line-active").length===3 && document.getElementById("receivableContractor")',
      "three active receivable rows");
    const boundary = await evaluate(client, `(() => ({
      note:document.querySelector('.operational-receivable-note').innerText,
      title:document.querySelector('.receivable-workspace h3').innerText,
      allExport:document.getElementById('receivableExportSelected').getAttribute('href')
    }))()`);
    assert.match(boundary.note, /không phải đề nghị thanh toán hay hóa đơn đỏ/i);
    assert.equal(boundary.title, "Sổ phải thu vận hành chi tiết");
    assert.doesNotMatch(boundary.allExport, /contractor=/);

    await evaluate(client, `(() => {
      const select=document.getElementById('receivableContractor');
      select.value='C1';select.dispatchEvent(new Event('change',{bubbles:true}));
      return true;
    })()`);
    await waitFor(client,
      'document.getElementById("receivableContractor").value==="C1" && document.querySelectorAll(".receivable-line-active").length===2 && [...document.getElementById("receivableKitchen").options].some(x=>x.value==="K2")',
      "contractor filter and kitchen options");
    await evaluate(client, `(() => {
      document.getElementById('receivableKitchen').value='K2';
      document.getElementById('receivableStatus').value='active';
      document.getElementById('receivableFilterForm').requestSubmit();
      return true;
    })()`);
    await waitFor(client,
      'document.querySelectorAll(".receivable-line-active").length===1 && document.querySelector(".receivable-line-active").innerText.includes("K2")',
      "kitchen filter");
    const filtered = await evaluate(client, `(() => ({
      exportHref:document.getElementById('receivableExportSelected').getAttribute('href'),
      rowText:document.querySelector('.receivable-line-active').innerText,
      reconcile:document.querySelector('.receivable-reconcile').innerText
    }))()`);
    assert.match(filtered.exportHref, /contractor=C1/);
    assert.doesNotMatch(filtered.exportHref, /kitchen=/);
    assert.match(filtered.rowText, /50\.000 đ/);
    for (const value of ["100.000 đ", "116.000 đ", "30.000 đ", "181.000 đ"]) {
      assert.match(filtered.reconcile, new RegExp(value.replace(".", "\\.")));
    }

    await evaluate(client, `(() => {
      document.querySelector('[data-action="toggle-receivable-history"]').click();
      return true;
    })()`);
    await waitFor(client,
      'document.querySelector(".receivable-revision-panel") && document.querySelector(".receivable-revision-panel").innerText.includes("Lần thay đổi 1")',
      "line revision history");

    await evaluate(client, `(() => {
      document.getElementById('receivableKitchen').value='';
      document.getElementById('receivableStatus').value='all';
      document.getElementById('receivableFilterForm').requestSubmit();
      return true;
    })()`);
    await waitFor(client,
      'document.querySelectorAll(".receivable-line-active").length===2 && document.querySelectorAll(".receivable-line-reversed").length===1',
      "active and reversed rows");

    await client.call("Page.reload", { ignoreCache: true });
    await waitFor(client,
      'document.readyState==="complete" && document.querySelector(\'[data-view="debts"]\')',
      "reload shell");
    await evaluate(client, `(() => {
      document.querySelector('[data-view="debts"]').click();
      document.querySelector('[data-section="receivable-kitchen"]').click();
      return true;
    })()`);
    await waitFor(client,
      'document.getElementById("receivableContractor") && document.getElementById("receivableContractor").value==="C1" && document.getElementById("receivableStatus").value==="all" && document.querySelectorAll(".receivable-line-active").length===2 && document.querySelectorAll(".receivable-line-reversed").length===1',
      "persisted receivable filters");
    process.stdout.write("receivable_ui_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("receivable_ui_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
