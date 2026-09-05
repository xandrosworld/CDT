"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const baseUrl = process.argv[2] || "http://127.0.0.1:18805";
const outputDir = path.resolve(process.argv[3] || "tmp/user-guide-screens");
const chromePath = process.env.TDP_BROWSER_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const debugPort = 19344;
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
      // Chrome is still starting.
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
  const deadline = Date.now() + (timeoutMilliseconds || 25000);
  while (Date.now() < deadline) {
    if (await evaluate(client, expression)) return;
    await delay(180);
  }
  throw new Error("Timeout: " + label);
}

async function capture(client, filename) {
  await delay(900);
  const screenshot = await client.call("Page.captureScreenshot", {
    format: "png", captureBeyondViewport: false
  });
  fs.writeFileSync(path.join(outputDir, filename), Buffer.from(screenshot.data, "base64"));
}

async function captureElement(client, selector, filename) {
  await delay(900);
  const bounds = await evaluate(client, `(()=>{
    const element=document.querySelector(${JSON.stringify(selector)});
    if(!element) throw new Error('Missing screenshot element: ${selector}');
    const rect=element.getBoundingClientRect();
    return {x:rect.left, y:rect.top, width:rect.width, height:rect.height};
  })()`);
  const screenshot = await client.call("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    clip: {
      x: Math.max(0, bounds.x),
      y: Math.max(0, bounds.y),
      width: bounds.width,
      height: bounds.height,
      scale: 1
    }
  });
  fs.writeFileSync(path.join(outputDir, filename), Buffer.from(screenshot.data, "base64"));
}

async function openView(client, view, readyExpression, filename) {
  await evaluate(client, `(()=>{
    const button=document.querySelector('#nav [data-view="${view}"]');
    if(!button) throw new Error('Missing navigation: ${view}');
    button.click();
  })()`);
  await waitFor(client, readyExpression, view);
  await evaluate(client, "window.scrollTo(0,0)");
  await capture(client, filename);
}

async function main() {
  if (!fs.existsSync(chromePath)) throw new Error("Chrome not found: " + chromePath);
  fs.mkdirSync(outputDir, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "tdp-guide-chrome-"));
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
  try {
    await waitHttp(devtoolsUrl + "/json/version", 20000);
    client = await connectDebugger();
    await client.call("Page.enable");
    await client.call("Runtime.enable");
    await client.call("Emulation.setDeviceMetricsOverride", {
      width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false
    });
    await client.call("Page.navigate", { url: baseUrl });
    await waitFor(client,
      'document.readyState==="complete" && document.querySelectorAll(".daily-action-card").length===4',
      "home");
    await capture(client, "01_cong_viec_hang_ngay.png");

    await openView(client, "orders", 'document.getElementById("orderSearch")', "02_nhap_va_sua_don.png");
    const quickAddOpened = await evaluate(client, `(()=>{
      const button=document.querySelector('[data-action="quick-add-order"]');
      if(!button) return false;
      button.click();
      return true;
    })()`);
    if (quickAddOpened) {
      await waitFor(client, '!document.getElementById("modalBackdrop").hidden', "quick add modal");
      await capture(client, "03_them_nhanh_mat_hang.png");
      await evaluate(client, 'document.querySelector("[data-action=close-modal]").click()');
    }

    await openView(client, "purchases", 'document.querySelector(".supplier-order-overview")', "04_dat_hang_nha_cung_cap.png");
    await openView(client, "deliveries", 'document.querySelector(".delivery-overview-card")', "05_phieu_giao_tong_quan.png");
    await evaluate(client, 'document.querySelector("[data-action=toggle-delivery-details]").click()');
    await waitFor(client, 'document.querySelector(".delivery-details-panel")', "delivery details");
    await evaluate(client, 'document.querySelector(".delivery-details-panel").scrollIntoView({block:"start"})');
    await capture(client, "06_phieu_giao_chi_tiet.png");

    await openView(client, "quotes", 'document.querySelectorAll(".quote-choice-card").length===2', "07_bao_gia.png");
    await openView(client, "reports", 'document.querySelector(".report-primary-card")', "08_bao_cao_tong_hop.png");
    await openView(client, "debts", 'document.querySelectorAll(".debt-menu-card").length===3', "09_cong_no_ba_lua_chon.png");

    await evaluate(client, 'document.querySelector("[data-section=receivable-kitchen]").click()');
    await waitFor(client, 'document.querySelector(".receivable-workspace")', "receivable kitchen");
    await capture(client, "10_cong_no_phai_thu_theo_bep.png");
    await evaluate(client, 'document.querySelector("[data-action=back-debt-overview]").click()');
    await waitFor(client, 'document.querySelectorAll(".debt-menu-card").length===3', "debt menu return");

    await evaluate(client, 'document.querySelector("[data-section=receivable-total]").click()');
    await waitFor(client, 'document.getElementById("receiptForm")', "receivable total");
    await capture(client, "11_cong_no_phai_thu_tong.png");
    await evaluate(client, 'document.querySelector("[data-action=back-debt-overview]").click()');
    await waitFor(client, 'document.querySelectorAll(".debt-menu-card").length===3', "debt menu return 2");

    await evaluate(client, 'document.querySelector("[data-section=payable]").click()');
    await waitFor(client, 'document.querySelector(".payable-workspace")', "payable");
    await capture(client, "12_cong_no_phai_tra.png");

    await openView(client, "documents", 'document.querySelectorAll(".document-primary-card").length===2', "13_bang_ke_va_hoa_don.png");
    await evaluate(client, 'document.querySelector("[data-action=toggle-document-details]").click()');
    await waitFor(client, 'document.querySelector(".document-detail-panel")', "document detail");
    await evaluate(client, 'document.querySelector(".document-detail-panel").scrollIntoView({block:"start"})');
    await capture(client, "14_xu_ly_chi_tiet_hoa_don.png");

    await openView(client, "inventory", 'document.querySelector(".inventory-primary-card")', "15_bao_cao_vat_tu.png");
    await waitFor(client, 'document.querySelector(".inventory-month-close")', "inventory month close");
    await evaluate(client, 'document.querySelector(".inventory-month-close").scrollIntoView({block:"start"})');
    await captureElement(client, ".inventory-month-close", "15b_chot_kho_theo_thang.png");
    await evaluate(client, 'document.querySelector("[data-action=toggle-inventory-details]").click()');
    await waitFor(client, 'document.querySelector(".inventory-detail-panel")', "inventory detail");
    await evaluate(client, 'document.querySelector(".inventory-detail-panel").scrollIntoView({block:"start"})');
    await capture(client, "16_vat_tu_chi_tiet.png");

    await openView(client, "msmi", 'document.querySelector(".invoice-direction-tabs")', "17_hoa_don_dau_vao.png");
    await evaluate(client, 'document.querySelector("[data-action=set-invoice-direction][data-direction=output]").click()');
    await waitFor(client,
      '(()=>{const tab=document.querySelector("[data-action=set-invoice-direction][data-direction=output]");return tab&&tab.getAttribute("aria-selected")==="true";})()',
      "outgoing invoice tab");
    await capture(client, "18_hoa_don_dau_ra.png");

    await openView(client, "kitchen", 'document.getElementById("kitchenDate")', "19_xuong_com_va_po.png");
    await openView(client, "payroll", 'document.getElementById("payrollMonth")', "20_cham_cong_va_luong.png");
    await openView(client, "printing", 'document.querySelector(".print-selection-card")', "21_in_giay_to.png");
    await openView(client, "settings", 'document.getElementById("documentSettingsForm")', "22_danh_muc_va_sao_luu.png");
    await evaluate(client, `(()=>{
      const link=document.querySelector('a[href="/api/backup"]');
      if(link) link.scrollIntoView({block:'center'});
    })()`);
    await capture(client, "23_sao_luu_du_lieu.png");

    process.stdout.write("guide_screens=passed\n");
    process.stdout.write("screen_count=" + fs.readdirSync(outputDir).filter((name) => name.endsWith(".png")).length + "\n");
  } finally {
    if (client) client.socket.close();
    if (!browser.killed) browser.kill();
    await delay(300);
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write("guide_screens=failed: " + error.stack + "\n");
  process.exitCode = 1;
});
