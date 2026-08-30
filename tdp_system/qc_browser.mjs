import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const appDir = resolve(import.meta.dirname);
const root = resolve(appDir, "..");
const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const chromePort = 9341;
const appPort = 8765;
const profile = mkdtempSync(join(tmpdir(), "tdp-real-qc-"));
const qcDb = join(appDir, "data", "qc_browser.sqlite3");
for (const suffix of ["", "-wal", "-shm"]) {
  try { rmSync(qcDb + suffix, { force: true }); } catch {}
}

const server = spawn("python", ["server.py", "--no-browser"], {
  cwd: appDir,
  env: { ...process.env, TDP_DB_PATH: qcDb, PYTHONUTF8: "1" },
  windowsHide: true,
  stdio: "ignore",
});

const wait = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
async function waitApp() {
  for (let i = 0; i < 100; i++) {
    try {
      const result = await fetch("http://127.0.0.1:" + appPort + "/health");
      if (result.ok) return;
    } catch {}
    await wait(100);
  }
  throw new Error("Máy chủ không khởi động");
}

let browser;
try {
  await waitApp();
  const source = readFileSync(join(root, "Tách212223.xlsx"));
  const form = new FormData();
  form.append("work_date", "2026-08-28");
  form.append("file", new Blob([source]), "Tách212223.xlsx");
  const importedResponse = await fetch("http://127.0.0.1:" + appPort + "/api/import", { method: "POST", body: form });
  const imported = await importedResponse.json();
  if (!imported.ok || imported.orders.length !== 408) throw new Error("Nhập file trình duyệt không đúng");

  browser = spawn(chromePath, [
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=" + chromePort, "--user-data-dir=" + profile,
    "--window-size=1440,1000", "about:blank",
  ], { windowsHide: true, stdio: "ignore" });

  async function chromeJson(path) {
    for (let i = 0; i < 80; i++) {
      try { return await (await fetch("http://127.0.0.1:" + chromePort + path)).json(); }
      catch { await wait(100); }
    }
    throw new Error("Không kết nối được Chrome");
  }
  const targets = await chromeJson("/json/list");
  const target = targets.find((item) => item.type === "page") || targets[0];
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolvePromise, reject) => {
    ws.addEventListener("open", resolvePromise, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  let seq = 0;
  const pending = new Map();
  const errors = [];
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const pendingItem = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) pendingItem.reject(new Error(message.error.message)); else pendingItem.resolve(message.result);
    }
    if (message.method === "Runtime.exceptionThrown") {
      const details = message.params.exceptionDetails;
      errors.push(details.exception?.description || details.text || "Runtime exception");
    }
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error") errors.push(message.params.entry.text);
  });
  function send(method, params = {}) {
    const id = ++seq;
    ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolvePromise, reject) => pending.set(id, { resolve: resolvePromise, reject }));
  }
  async function evaluate(expression) {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  }
  function assert(value, message) { if (!value) throw new Error(message); }

  await send("Runtime.enable");
  await send("Log.enable");
  await send("Page.enable");
  await send("DOM.enable");
  await send("Page.navigate", { url: "http://127.0.0.1:" + appPort });
  for (let i = 0; i < 80; i++) {
    await wait(100);
    if (await evaluate("document.readyState === 'complete' && document.body.innerText.includes('408 dòng')")) break;
  }
  assert((await evaluate("document.title")).includes("Thành Đạt Phát"), "Sai tiêu đề");
  assert(await evaluate("document.querySelectorAll('.nav-item').length === 8"), "Thiếu menu");
  assert(await evaluate("document.body.innerText.includes('408 dòng')"), "Trang chủ không hiện đúng số dòng");

  const checks = [
    ["orders", "27 cảnh báo cần xác nhận"],
    ["purchases", "nhà cung cấp theo số lượng đặt"],
    ["deliveries", "Dùng số thực giao"],
    ["reports", "Ghi nhận thu / chi"],
    ["documents", "đúng 11 cột"],
    ["settings", "Ranh giới tích hợp"],
  ];
  for (const [view, text] of checks) {
    await evaluate("document.querySelector('[data-view=\"" + view + "\"]').click()");
    await wait(160);
    assert(await evaluate("document.body.innerText.includes(" + JSON.stringify(text) + ")"), "Sai màn hình " + view + ": thiếu " + text);
  }
  await evaluate("document.querySelector('[data-view=\"orders\"]').click()");
  await wait(100);
  await evaluate("document.querySelector('[data-action=\"edit-order\"]').click()");
  assert(await evaluate("!document.querySelector('#modalBackdrop').hidden"), "Không mở được form sửa");
  assert(await evaluate("document.querySelector('#orderForm input[name=\"product_code\"]').value.length > 0"), "Form sửa thiếu dữ liệu");
  await evaluate("document.querySelector('[data-action=\"close-modal\"]').click()");
  await evaluate("document.querySelector('[data-action=\"paste-orders\"]').click()");
  assert(await evaluate("document.querySelector('#pasteText').placeholder.includes('POT')"), "Không mở được form dán Excel");
  await evaluate("document.querySelector('[data-action=\"close-modal\"]').click()");

  await evaluate("document.querySelector('[data-view=\"quotes\"]').click()");
  for (let i = 0; i < 50; i++) {
    await wait(100);
    if (await evaluate("Boolean(document.querySelector('#quoteContractor'))")) break;
  }
  assert(await evaluate("document.body.innerText.includes('Bảng giá HATRAN')"), "Không nạp được bảng giá");
  await evaluate("const s=document.querySelector('#quoteContractor');s.value='GIANHAPTAY';s.dispatchEvent(new Event('change',{bubbles:true}))");
  for (let i = 0; i < 50; i++) {
    await wait(100);
    if (await evaluate("document.body.innerText.includes('không ăn theo bảng giá')")) break;
  }
  assert(await evaluate("document.body.innerText.includes('không ăn theo bảng giá')"), "Sai quy tắc giá theo ngày");

  // Real file-picker flow: analyze workbook, default to the completed-order sheet, then import it.
  await evaluate("document.querySelector('[data-view=\"orders\"]').click()");
  const documentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const inputNode = await send("DOM.querySelector", {
    nodeId: documentNode.root.nodeId,
    selector: "#excelInput"
  });
  await send("DOM.setFileInputFiles", {
    files: [join(root, "Em Thành.xlsx")],
    nodeId: inputNode.nodeId
  });
  for (let i = 0; i < 100; i++) {
    await wait(100);
    if (await evaluate("document.querySelector('#modalTitle')?.textContent.includes('Chọn sheet')")) break;
  }
  assert(await evaluate("document.querySelectorAll('.sheet-choice').length === 3"), "Không nhận diện đúng 3 sheet đơn trong file tổng");
  assert(await evaluate("document.querySelectorAll('.sheet-choice input:checked').length === 1"), "Không tự chọn đúng sheet đơn hoàn thiện");
  assert(await evaluate("document.querySelector('.sheet-choice input:checked').value.includes('đơn hàng')"), "Chọn nhầm sheet mặc định");
  await evaluate("document.querySelector('#orderForm button[type=\"submit\"]').click()");
  for (let i = 0; i < 150; i++) {
    await wait(100);
    if (await evaluate("document.body.innerText.includes('323 dòng đã') || document.body.innerText.includes('323 dòng lỗi')")) break;
  }
  assert(await evaluate("document.body.innerText.includes('323 dòng')"), "Không nhập đúng sheet đã chọn");

  // A dated file must select only the matching dated sheet, not aggregate/history sheets.
  const datedDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const datedInputNode = await send("DOM.querySelector", {
    nodeId: datedDocumentNode.root.nodeId,
    selector: "#excelInput"
  });
  await send("DOM.setFileInputFiles", {
    files: [join(root, "..", "Đơn hàng 29.08.xlsx")],
    nodeId: datedInputNode.nodeId
  });
  for (let i = 0; i < 100; i++) {
    await wait(100);
    if (await evaluate("!document.querySelector('#modalBackdrop').hidden && document.querySelector('#orderForm').innerText.includes('Đơn hàng 29.08.xlsx')")) break;
  }
  assert(await evaluate("document.querySelectorAll('.sheet-choice input:checked').length === 1"), "File ngày đang chọn trùng nhiều sheet");
  assert(await evaluate("document.querySelector('.sheet-choice input:checked').value === '29.08'"), "Không tự chọn đúng sheet 29.08");
  assert(await evaluate("document.querySelector('input[name=\"work_date\"]').value === '2026-08-29'"), "Ngày làm việc dự phòng không khớp tên file");
  await evaluate("document.querySelector('[data-action=\"close-modal\"]').click()");

  const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  writeFileSync(join(appDir, "qc_browser.png"), Buffer.from(shot.data, "base64"));
  assert(errors.length === 0, "Lỗi trình duyệt: " + errors.join(" | "));
  console.log(JSON.stringify({
    ok: true,
    importedOrders: imported.orders.length,
    selectedSheetOrders: 323,
    datedSheetAutoSelected: "29.08",
    errorRows: imported.summary.totals.errors,
    warningRows: imported.summary.totals.warnings,
    screens: 8,
    browserErrors: errors.length
  }, null, 2));
  ws.close();
} finally {
  if (browser) browser.kill();
  server.kill();
  await wait(300);
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
  for (const suffix of ["", "-wal", "-shm"]) {
    try { rmSync(qcDb + suffix, { force: true }); } catch {}
  }
}
