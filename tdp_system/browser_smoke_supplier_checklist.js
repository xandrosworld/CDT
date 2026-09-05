"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const baseUrl = process.argv[2] || "http://127.0.0.1:18775";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19235";
const downloadDir = process.argv[4] || "";

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

async function openPurchases(client) {
  await waitFor(client,
    'document.readyState==="complete" && document.querySelector(\'[data-view="purchases"]\')',
    "app shell");
  await evaluate(client, 'document.querySelector(\'[data-view="purchases"]\').click()');
  await waitFor(client,
    'document.body.innerText.includes("Checklist chống sót:") && document.querySelectorAll(".supplier-order-card").length===6',
    "supplier checklist");
}

const protectedStateExpression = `Promise.all([
  fetch('/api/bootstrap?batch_id=1').then(r=>r.json()),
  fetch('/api/debts?from=2026-09-01&to=2026-09-01').then(r=>r.json()),
  fetch('/api/invoice-inventory?as_of=2026-09-01').then(r=>r.json())
]).then(([bootstrap,debts,invoiceStock])=>({
  orders:bootstrap.orders.map(item=>({
    id:item.id,qty:item.qty,actual_received:item.actual_received,
    actual_delivered:item.actual_delivered,buy_price:item.buy_price,
    sell_price:item.sell_price,revenue:item.revenue,total:item.total
  })),
  revenue:bootstrap.summary.totals.revenue,
  total:bootstrap.summary.totals.total,
  contractors:bootstrap.summary.contractors,
  receivables:debts.contractors,
  invoiceStock:invoiceStock.items
}))`;

async function main() {
  const client = await connectDebugger();
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("DOM.enable");
    if (downloadDir) {
      try {
        await client.call("Browser.setDownloadBehavior", {
          behavior: "allow", downloadPath: downloadDir, eventsEnabled: true
        });
      } catch (error) {
        await client.call("Page.setDownloadBehavior", {
          behavior: "allow", downloadPath: downloadDir
        });
      }
    }
    await client.call("Page.navigate", { url: baseUrl });
    await openPurchases(client);
    await waitFor(client,
      'document.body.innerText.includes("3 NCC cần xử lý · 0 NCC đã đặt")',
      "initial pending summary");
    const protectedBefore = await evaluate(client, protectedStateExpression);
    assert.equal(protectedBefore.revenue, 300000);
    assert.equal(protectedBefore.receivables["BROWSER-CUSTOMER"].period_charge, 300000);
    assert.equal(protectedBefore.invoiceStock[0].closing_qty, 52);

    await evaluate(client, `(()=>{
      window.__supplierImageTexts=[];
      if(!window.__supplierImageFillTextHook){
        const original=CanvasRenderingContext2D.prototype.fillText;
        CanvasRenderingContext2D.prototype.fillText=function(value,...args){
          window.__supplierImageTexts.push(String(value));
          return original.call(this,value,...args);
        };
        window.__supplierImageFillTextHook=true;
      }
    })()`);
    await evaluate(client,
      'document.querySelector(\'.supplier-order-card[data-supplier-key="dung"] [data-action="download-supplier-image"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("Đã tải ảnh đơn đặt hàng")',
      "image download remains read only");
    const drawnTexts = await evaluate(client, 'window.__supplierImageTexts.slice()');
    ["Mã bếp", "Ngày", "Tên hàng", "Số lượng", "ĐVT", "NCC", "Ghi chú"].forEach((header) => {
      assert(drawnTexts.includes(header), "Missing supplier-image header: " + header);
    });
    ["Cà rốt", "5", "kg", "Nhà Dũng", "Giao trước 06:00"].forEach((value) => {
      assert(drawnTexts.includes(value), "Missing supplier-image value: " + value);
    });
    const normalizedDrawn = drawnTexts.join("\n").normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "").toLowerCase();
    [
      "ton tu", "gia mua", "thanh tien", "tong can mua", "sau tru ton",
      "ma dong he thong", "so luong thuc te", "hong", "them", "giam", "thieu"
    ].forEach((forbidden) => {
      assert(!normalizedDrawn.includes(forbidden), "Forbidden supplier-image text: " + forbidden);
    });
    let downloadedImage = "";
    if (downloadDir) {
      const deadline = Date.now() + 10000;
      while (Date.now() < deadline) {
        const files = fs.readdirSync(downloadDir).filter((name) => name.endsWith(".png"));
        if (files.length) {
          downloadedImage = path.join(downloadDir, files[0]);
          break;
        }
        await delay(100);
      }
      assert(downloadedImage && fs.statSync(downloadedImage).size > 1000, "Supplier image was not downloaded");
    }
    const afterImage = await evaluate(client, `fetch('/api/supplier-needs/1').then(r=>r.json()).then(p=>{
      const item=p.checklist.find(x=>x.supplier_key==='dung');
      return {status:item.status,revision:item.revision,groups:p.groups.length,raw:p.raw_line_count};
    })`);
    assert.deepEqual(afterImage, { status: "pending", revision: 0, groups: 6, raw: 8 });
    assert.deepEqual(await evaluate(client, protectedStateExpression), protectedBefore);

    await evaluate(client,
      'document.querySelector(\'.supplier-order-card[data-supplier-key="dung"] [data-action="set-supplier-order-status"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("Đã đánh dấu NCC đã đặt") && document.body.innerText.includes("2 NCC cần xử lý · 1 NCC đã đặt") && document.querySelector(\'.supplier-order-card[data-supplier-key="dung"]\').dataset.orderStatus==="ordered"',
      "mark supplier ordered");
    const orderedLast = await evaluate(client, `(()=>{
      const cards=[...document.querySelectorAll('.supplier-order-card')];
      return cards[cards.length-1].dataset.supplierKey;
    })()`);
    assert.equal(orderedLast, "dung");

    await client.call("Page.reload", { ignoreCache: true });
    await openPurchases(client);
    await waitFor(client,
      'document.querySelector(\'.supplier-order-card[data-supplier-key="dung"]\').dataset.orderStatus==="ordered" && document.querySelector(\'.supplier-order-card[data-supplier-key="dung"] [data-action="set-supplier-order-status"]\').dataset.revision==="1"',
      "ordered survives refresh");

    await evaluate(client,
      'document.querySelector(\'.supplier-order-card[data-supplier-key="dung"] [data-action="set-supplier-order-status"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("Đã mở lại NCC · cần đặt lại") && document.querySelector(\'.supplier-order-card[data-supplier-key="dung"]\').dataset.orderStatus==="reopened"',
      "undo to reopened");
    const reopenedFirst = await evaluate(client,
      'document.querySelector(".supplier-order-card").dataset.supplierKey');
    assert.equal(reopenedFirst, "dung");

    await evaluate(client,
      'document.querySelector(\'.supplier-order-card[data-supplier-key="dung"] [data-action="set-supplier-order-status"]\').click()');
    await waitFor(client,
      'document.body.innerText.includes("Đã đánh dấu NCC đã đặt") && document.querySelector(\'.supplier-order-card[data-supplier-key="dung"]\').dataset.orderStatus==="ordered"',
      "ordered again");
    const finalState = await evaluate(client, `fetch('/api/supplier-needs/1').then(r=>r.json()).then(p=>{
      const item=p.checklist.find(x=>x.supplier_key==='dung');
      return {status:item.status,revision:item.revision,pending:p.checklist_counts.pending,reopened:p.checklist_counts.reopened,ordered:p.checklist_counts.ordered,groups:p.groups.length,raw:p.raw_line_count};
    })`);
    assert.deepEqual(finalState, {
      status: "ordered", revision: 3, pending: 2, reopened: 0,
      ordered: 1, groups: 6, raw: 8
    });
    assert.deepEqual(await evaluate(client, protectedStateExpression), protectedBefore);
    process.stdout.write("supplier_checklist_browser_smoke=passed\n");
    process.stdout.write("supplier_boundary_unchanged=orders,revenue,receivables,invoice_stock\n");
    process.stdout.write("supplier_image_texts=" + JSON.stringify(drawnTexts) + "\n");
    if (downloadedImage) process.stdout.write("supplier_image_path=" + downloadedImage + "\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("supplier_checklist_browser_smoke=failed: " + error.message + "\n");
  process.exitCode = 1;
});
