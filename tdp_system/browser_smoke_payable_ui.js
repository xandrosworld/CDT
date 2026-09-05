"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:18788";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19238";

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
      if (document.querySelector('.payable-workspace')) throw new Error('Debt details must stay hidden on overview');
      document.querySelector('[data-section="payable"]').click();
      return true;
    })()`);
    await waitFor(client,
      'document.querySelectorAll(".payable-line-select:not(:disabled)").length===3 && document.getElementById("payableStatus")',
      "three payable lines");

    await evaluate(client, `(() => {
      document.getElementById('payableSupplier').value='S1';
      document.getElementById('payableStatus').value='outstanding';
      document.getElementById('debtPeriodForm').requestSubmit();
      return true;
    })()`);
    await waitFor(client,
      'document.querySelectorAll(".payable-line-select:not(:disabled)").length===2 && document.getElementById("payableSupplier").value==="S1"',
      "supplier filter");

    await evaluate(client, 'document.querySelectorAll(".payable-line-select:not(:disabled)")[0].click()');
    await evaluate(client, 'document.querySelectorAll(".payable-line-select:not(:disabled)")[1].click()');
    const keyboardResult = await evaluate(client, `(() => {
      const inputs=[...document.querySelectorAll('.payable-allocation-input:not(:disabled)')];
      inputs[0].value='100000';inputs[0].dispatchEvent(new Event('input',{bubbles:true}));
      inputs[1].value='50000';inputs[1].dispatchEvent(new Event('input',{bubbles:true}));
      inputs[0].focus();inputs[0].dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
      return {
        focusedNext:document.activeElement===inputs[1],
        total:document.getElementById('payablePaymentTotal').value,
        supplier:document.getElementById('payableSelectedSupplier').value,
        enabled:!document.getElementById('payablePaymentSubmit').disabled
      };
    })()`);
    assert.deepEqual(keyboardResult, { focusedNext: true, total: "150000", supplier: "S1", enabled: true });

    await evaluate(client, `(() => {
      window.confirm=()=>true;
      document.getElementById('payablePaymentForm').requestSubmit();
      return true;
    })()`);
    await waitFor(client,
      'document.querySelectorAll(".payable-line-select:not(:disabled)").length===1 && document.querySelector(".payable-history-card").innerText.includes("150.000 đ")',
      "payment refresh");
    const posted = await evaluate(client, `Promise.all([
      fetch('/api/debts/payables/ledger?from=2026-09-01&to=2026-09-01&supplier=S1&status=all').then(r=>r.json()),
      fetch('/api/debts/payables/payments?from=2026-09-01&to=2026-09-30&supplier=S1&status=all').then(r=>r.json())
    ]).then(([ledger,payments])=>({
      states:ledger.rows.map(x=>[x.amount,x.paid_amount,x.remaining_amount,x.status]),
      payments:payments.payments.map(x=>({amount:x.amount,status:x.status,allocations:x.allocations.length}))
    }))`);
    assert.deepEqual(posted, {
      states: [[100000, 100000, 0, "paid"], [200000, 50000, 150000, "partially_paid"]],
      payments: [{ amount: 150000, status: "posted", allocations: 2 }]
    });

    await client.call("Page.reload", { ignoreCache: true });
    await waitFor(client, 'document.readyState==="complete" && document.querySelector(\'[data-view="debts"]\')', "reload shell");
    await evaluate(client, `(() => {
      document.querySelector('[data-view="debts"]').click();
      document.querySelector('[data-section="payable"]').click();
      return true;
    })()`);
    await waitFor(client,
      'document.getElementById("payableSupplier") && document.getElementById("payableSupplier").value==="S1" && document.querySelectorAll(".payable-line-select:not(:disabled)").length===1 && document.querySelector(".payable-history-card").innerText.includes("150.000 đ")',
      "persisted filters and server refresh");
    const exportHref = await evaluate(client, 'document.querySelector(\'a[href*="/api/debts/payables/export"]\').getAttribute("href")');
    assert.match(exportHref, /supplier=S1/);

    await evaluate(client, `(() => {
      window.prompt=()=> 'Sai giao dịch ngân hàng';window.confirm=()=>true;
      document.querySelector('[data-action="reverse-payable-payment"]').click();return true;
    })()`);
    await waitFor(client,
      'document.querySelectorAll(".payable-line-select:not(:disabled)").length===2 && document.querySelector(".payable-history-card").innerText.includes("Đã đảo")',
      "reversal refresh");

    const staleSetup = await evaluate(client, `(() => {
      const first=document.querySelectorAll('.payable-line-select:not(:disabled)')[0];first.click();
      const input=document.querySelector('.payable-allocation-input:not(:disabled)');
      input.value='50000';input.dispatchEvent(new Event('input',{bubbles:true}));
      return {id:Number(first.dataset.id),revision:Number(first.dataset.revision)};
    })()`);
    const external = await evaluate(client, `fetch('/api/debts/payables/payments',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        request_id:'BROWSER-EXTERNAL-0001',payment_date:'2026-09-06',party_code:'S1',amount:10000,
        method:'Chuyển khoản',reference_code:'EXT-001',note:'writer khác',
        allocations:[{ledger_line_id:${staleSetup.id},amount:10000,expected_revision:${staleSetup.revision}}]
      })
    }).then(async r=>({status:r.status,payload:await r.json()}))`);
    assert.equal(external.status, 201);
    await evaluate(client, `(() => {
      window.confirm=()=>true;document.getElementById('payablePaymentForm').requestSubmit();return true;
    })()`);
    await waitFor(client,
      'document.querySelector(".toast.toast-error.show") && document.querySelector(".toast.toast-error.show").innerText.includes("thay đổi") && document.querySelectorAll(".payable-line-select:checked").length===0',
      "stale revision error and refresh");
    const finalState = await evaluate(client, `Promise.all([
      fetch('/api/debts/payables/ledger?from=2026-09-01&to=2026-09-01&supplier=S1&status=all').then(r=>r.json()),
      fetch('/api/debts/payables/payments?from=2026-09-01&to=2026-09-30&supplier=S1&status=all').then(r=>r.json())
    ]).then(([ledger,payments])=>({
      paid:ledger.rows.reduce((s,x)=>s+x.paid_amount,0),
      transactions:payments.payments.map(x=>[x.amount,x.status]),
      selected:document.querySelectorAll('.payable-line-select:checked').length
    }))`);
    assert.deepEqual(finalState, {
      paid: 10000,
      transactions: [[150000, "reversed"], [10000, "posted"]],
      selected: 0
    });
    process.stdout.write("payable_ui_browser_smoke=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("payable_ui_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
