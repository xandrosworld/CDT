"use strict";

const assert = require("node:assert/strict");

const baseUrl = process.argv[2] || "http://127.0.0.1:18794";
const devtoolsUrl = process.argv[3] || "http://127.0.0.1:19244";
const conflictFile = process.argv[4];
const cleanFile = process.argv[5];

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
    nodeId: document.root.nodeId, selector: "#quoteWorkbookInput"
  });
  if (!input.nodeId) throw new Error("Quote file input is missing");
  await client.call("DOM.setFileInputFiles", { nodeId: input.nodeId, files: [filePath] });
  await evaluate(client,
    'document.getElementById("quoteWorkbookInput").dispatchEvent(new Event("change",{bubbles:true}))');
}

async function openQuoteView(client) {
  await evaluate(client, `(()=>{
    const button=document.querySelector('[data-view="quotes"]');
    if(!button) throw new Error('Quote navigation is missing');
    button.click();
  })()`);
  await waitFor(client, 'document.getElementById("quotePeriod")', "quote view");
  await evaluate(client, `(()=>{
    const period=document.getElementById('quotePeriod');
    period.value='2026-09';
    period.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await waitFor(client,
    'document.getElementById("quotePeriod") && document.getElementById("quotePeriod").value==="2026-09"',
    "quote period");
  await evaluate(client, `(()=>{
    const contractor=document.getElementById('quoteContractor');
    contractor.value='TOYOTA';
    contractor.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await waitFor(client,
    'document.getElementById("quoteContractor") && document.getElementById("quoteContractor").value==="TOYOTA"',
    "Toyota selection");
}

async function main() {
  if (!conflictFile || !cleanFile) throw new Error("Conflict and clean workbook paths are required");
  const client = await connectDebugger();
  try {
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("DOM.enable");
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client, 'document.readyState==="complete" && document.querySelector("[data-view=quotes]")', "app shell");
    await openQuoteView(client);
    await waitFor(client,
      'document.body.innerText.includes("Chưa thể xuất · cần bảng giá kỳ này")',
      "unconfirmed period export gate");
    assert.equal(await evaluate(client,
      'document.querySelectorAll(\'a[href^="/api/export/quote/TOYOTA"]\').length'), 0);

    await upload(client, conflictFile);
    await waitFor(client, 'document.querySelector(".quote-import-preview")', "conflict preview");
    const conflictText = await evaluate(client, 'document.querySelector(".quote-import-preview").innerText');
    assert(conflictText.includes("TOYOTA · cột Q → TOYOTA"));
    assert(conflictText.includes("P1"));
    assert(conflictText.includes("Đang bị chặn"));
    assert.equal(await evaluate(client,
      'document.querySelectorAll(\'[data-action="confirm-quote-import"]\').length'), 0);

    await evaluate(client, 'document.querySelector(\'[data-action="cancel-quote-import"]\').click()');
    await waitFor(client, '!document.querySelector(".quote-import-preview")', "cancel conflict preview");
    await upload(client, cleanFile);
    await waitFor(client,
      'document.querySelector(\'[data-action="confirm-quote-import"]\')', "clean preview");
    const cleanPreview = await evaluate(client, 'document.querySelector(".quote-import-preview").innerText');
    assert(cleanPreview.includes("Đủ điều kiện xác nhận"));
    assert(cleanPreview.includes("TOYOTA · cột Q → TOYOTA"));
    await evaluate(client, 'document.querySelector(\'[data-action="confirm-quote-import"]\').click()');
    await waitFor(client, 'document.body.innerText.includes("Phiên bản 1 · nhóm TOYOTA")', "confirmed version");

    const quoteText = await evaluate(client, 'document.getElementById("content").innerText');
    assert(quoteText.includes("2 dòng xuất"));
    assert(quoteText.includes("2 dòng X/rỗng đã loại"));
    assert(quoteText.includes("P1"));
    assert(quoteText.includes("0 · giữ để xác nhận"));
    assert(quoteText.includes("P2"));
    assert(!quoteText.includes("P3"));
    assert(!quoteText.includes("P4"));
    assert(quoteText.includes("Các lần báo giá đã lưu"));
    assert(quoteText.includes("Mỗi nhà thầu là một file Excel riêng, không lẫn giá."));
    const exportHref = await evaluate(client,
      'document.querySelector(\'a[href^="/api/export/quote/TOYOTA"]\').getAttribute("href")');
    assert(exportHref.includes("period=2026-09"));
    const download = await evaluate(client, `fetch(${JSON.stringify(exportHref)}).then(async response=>({
      status:response.status,
      type:response.headers.get('content-type'),
      disposition:response.headers.get('content-disposition'),
      size:(await response.arrayBuffer()).byteLength
    }))`);
    assert.equal(download.status, 200);
    assert(download.type.includes("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"));
    assert(download.disposition.includes("BAO_GIA_TOYOTA_T09-2026_V1.xlsx"));
    assert(download.size > 6000);
    const bundleHref = await evaluate(client,
      'document.querySelector(\'a[href^="/api/export/quotes/all"]\').getAttribute("href")');
    assert(bundleHref.includes("period=2026-09"));
    assert(bundleHref.includes("version_id="));
    const bundleDownload = await evaluate(client, `fetch(${JSON.stringify(bundleHref)}).then(async response=>({
      status:response.status,
      type:response.headers.get('content-type'),
      disposition:response.headers.get('content-disposition'),
      size:(await response.arrayBuffer()).byteLength
    }))`);
    assert.equal(bundleDownload.status, 200);
    assert(bundleDownload.type.includes("application/zip"));
    assert(bundleDownload.disposition.includes("BAO_GIA_TAT_CA_T09-2026_V1.zip"));
    assert(bundleDownload.size > 6000);

    await evaluate(client, `(()=>{
      const contractor=document.getElementById('quoteContractor');
      contractor.value='ATV';
      contractor.dispatchEvent(new Event('change',{bubbles:true}));
    })()`);
    await waitFor(client,
      'document.body.innerText.includes("Phiên bản 1 · nhóm ATV") && document.body.innerText.includes("Kính gửi: CÔNG TY CỔ PHẦN SUẤT ĂN CÔNG NGHIỆP ATV")',
      "ATV isolated quotation");
    const atvText = await evaluate(client, 'document.getElementById("content").innerText');
    assert(atvText.includes("10.000"));
    assert(!atvText.includes("0 · giữ để xác nhận"));
    const atvExportHref = await evaluate(client,
      'document.querySelector(\'a[href^="/api/export/quote/ATV"]\').getAttribute("href")');
    const atvDownload = await evaluate(client, `fetch(${JSON.stringify(atvExportHref)}).then(async response=>({
      status:response.status,
      disposition:response.headers.get('content-disposition'),
      size:(await response.arrayBuffer()).byteLength
    }))`);
    assert.equal(atvDownload.status, 200);
    assert(atvDownload.disposition.includes("BAO_GIA_ATV_T09-2026_V1.xlsx"));
    assert(atvDownload.size > 6000);

    await client.call("Page.reload", { ignoreCache: true });
    await waitFor(client, 'document.readyState==="complete" && document.querySelector("[data-view=quotes]")', "reloaded shell");
    await openQuoteView(client);
    await waitFor(client, 'document.body.innerText.includes("Phiên bản 1 · nhóm TOYOTA")', "persisted version");
    process.stdout.write("quote_ui_browser_smoke=passed\n");
    process.stdout.write("header_mapping=TOYOTA_Q\n");
    process.stdout.write("conflict_block_zero_keep_blank_x_omit=persisted\n");
    process.stdout.write("toyota_golden_download=period_version_named_xlsx\n");
    process.stdout.write("all_contractors_zip_and_version_history=passed\n");
    process.stdout.write("atv_same_engine_recipient_and_price_isolated=passed\n");
  } finally {
    client.socket.close();
  }
}

main().catch((error) => {
  process.stderr.write("quote_ui_browser_smoke=failed: " + error.stack + "\n");
  process.exitCode = 1;
});
