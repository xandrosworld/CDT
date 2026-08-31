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
let printBatchId = null;
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
  async function waitForText(text, loops = 100) {
    for (let i = 0; i < loops; i++) {
      if (await evaluate("document.body.innerText.includes(" + JSON.stringify(text) + ")")) return true;
      await wait(100);
    }
    return false;
  }

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
  const requiredViews = [
    "home", "orders", "purchases", "deliveries", "quotes", "reports", "documents",
    "inventory", "msmi", "kitchen", "payroll", "printing", "settings",
  ];
  assert(await evaluate("JSON.stringify(Array.from(document.querySelectorAll('.nav-item')).map(x=>x.dataset.view))") === JSON.stringify(requiredViews), "Thiếu hoặc sai thứ tự menu hợp đồng");
  assert(await evaluate("document.body.innerText.includes('408 dòng')"), "Trang chủ không hiện đúng số dòng");

  const checks = [
    ["orders", "27 cảnh báo cần xác nhận"],
    ["purchases", "max(lượng khách đặt − tồn khả dụng, 0)"],
    ["deliveries", "Dùng số thực giao"],
    ["reports", "Ghi nhận thu / chi"],
    ["documents", "đúng 11 cột"],
    ["inventory", "Nạp Excel tồn đầu kỳ"],
    ["msmi", "mSMI chỉ đọc"],
    ["kitchen", "Nạp định mức/PO"],
    ["payroll", "Nạp file chấm công"],
    ["printing", "3. In một nút"],
    ["settings", "Ranh giới tích hợp"],
  ];
  for (const [view, text] of checks) {
    await evaluate("document.querySelector('[data-view=\"" + view + "\"]').click()");
    assert(await waitForText(text), "Sai màn hình " + view + ": thiếu " + text);
  }
  assert(await evaluate("document.querySelector('#documentSettingsForm [name=\"payment_requester\"]').value === 'VŨ THỊ THỤY'"), "Sai người đại diện trên đề nghị thanh toán");
  assert(await evaluate("document.querySelector('#documentSettingsForm [name=\"payment_bank_account\"]').value === '1052787580'"), "Sai tài khoản đề nghị thanh toán");
  assert(await evaluate("document.querySelector('#documentSettingsForm [name=\"payment_bank_name\"]').value.includes('Ngoại Thương Việt Nam')"), "Sai ngân hàng đề nghị thanh toán");
  await evaluate("document.querySelector('#documentSettingsForm button[type=\"submit\"]').click()");
  assert(await waitForText("Đã lưu thông tin đề nghị thanh toán"), "Không lưu được cấu hình đề nghị thanh toán qua giao diện");

  // Supplier grouping rule and multi-period debt controls are exercised through the rendered forms.
  await evaluate("document.querySelector('[data-view=\"purchases\"]').click()");
  assert(await waitForText("max(lượng khách đặt − tồn khả dụng, 0)", 120), "Không nạp được nhu cầu NCC");
  assert(await evaluate("Boolean(document.querySelector('[data-action=\"toggle-supplier-rule\"]'))"), "Thiếu nút gộp/tách NCC trên giao diện");
  await evaluate("document.querySelector('[data-action=\"toggle-supplier-rule\"]').click()");
  assert(await waitForText("Đã gộp đơn NCC", 120) || await waitForText("Đã tách đơn NCC", 10), "Không lưu được quy tắc gộp/tách NCC");

  await evaluate("document.querySelector('[data-view=\"reports\"]').click()");
  assert(await waitForText("Kỳ công nợ", 120), "Thiếu bộ lọc công nợ nhiều kỳ");
  await evaluate("(()=>{const f=document.querySelector('#debtPeriodForm');f.from.value='2026-08-01';f.to.value='2026-08-31';f.requestSubmit()})()");
  assert(await waitForText("Điều chỉnh công nợ", 120), "Không xem được công nợ theo khoảng ngày");
  await evaluate("(()=>{const f=document.querySelector('#debtAdjustmentForm');f.adjustment_date.value='2026-08-28';f.party_type.value='contractor';f.party_code.value='HATRAN';f.amount.value='123';f.note.value='Chrome QC';f.requestSubmit()})()");
  assert(await waitForText("Đã lưu điều chỉnh công nợ", 120), "Không lưu được điều chỉnh công nợ qua giao diện");
  const debtFromUi = await evaluate("fetch('/api/debts?from=2026-08-01&to=2026-08-31').then(r=>r.json())");
  assert(debtFromUi.ok && debtFromUi.contractors.HATRAN.period_adjustment === 123, "Điều chỉnh công nợ không vào đúng kỳ");
  const debtExportFromUi = await evaluate("fetch('/api/export/debts?from=2026-08-01&to=2026-08-31').then(async r=>({ok:r.ok,size:(await r.arrayBuffer()).byteLength}))");
  assert(debtExportFromUi.ok && debtExportFromUi.size > 1000, "Không tải được Excel công nợ kỳ");

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

  // Save an edit and a pasted row through the real forms on this disposable 323-row batch.
  await evaluate("document.querySelector('[data-action=\"edit-order\"]').click()");
  assert(await evaluate("!document.querySelector('#modalBackdrop').hidden"), "Không mở lại được form sửa sau import");
  await evaluate("(()=>{const n=document.querySelector('#orderForm [name=\"note\"]');n.value='Đã sửa qua Chrome QC';document.querySelector('#orderForm').requestSubmit()})()");
  assert(await waitForText("Đã lưu dòng đơn và kiểm tra lại", 120), "Không lưu được dòng đã sửa qua giao diện");
  assert(await waitForText("Đã sửa qua Chrome QC", 120), "Giao diện không hiện lại ghi chú vừa lưu");
  await evaluate("document.querySelector('[data-action=\"paste-orders\"]').click()");
  await evaluate("(()=>{const p=document.querySelector('#pasteText');p.value='POT\\tHành tây\\t1\\tkho\\t14000\\t16000\\tKKKNT';document.querySelector('#orderForm').requestSubmit()})()");
  assert(await waitForText("Đã thêm 1 dòng và tự kiểm tra", 120), "Không dán thêm được dòng phát sinh qua giao diện");
  assert(await evaluate("document.querySelectorAll('tbody tr').length === 324"), "Dòng dán phát sinh không xuất hiện trong lưới");

  // A dated file must select only the matching dated sheet, not aggregate/history sheets.
  const datedDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const datedInputNode = await send("DOM.querySelector", {
    nodeId: datedDocumentNode.root.nodeId,
    selector: "#excelInput"
  });
  await send("DOM.setFileInputFiles", {
    files: [join(root, "_HANDOFF", "EXTERNAL_INPUTS", "Đơn hàng 29.08.xlsx")],
    nodeId: datedInputNode.nodeId
  });
  for (let i = 0; i < 100; i++) {
    await wait(100);
    if (await evaluate("!document.querySelector('#modalBackdrop').hidden && document.querySelector('#orderForm').innerText.includes('Đơn hàng 29.08.xlsx')")) break;
  }
  assert(await evaluate("!document.querySelector('#modalBackdrop').hidden && document.querySelector('#orderForm').innerText.includes('Đơn hàng 29.08.xlsx')"), "Không mở được file ngày 29.08 qua bộ chọn file");
  assert(await evaluate("document.querySelectorAll('.sheet-choice input:checked').length === 1"), "File ngày đang chọn trùng nhiều sheet");
  assert(await evaluate("document.querySelector('.sheet-choice input:checked').value === '29.08'"), "Không tự chọn đúng sheet 29.08");
  assert(await evaluate("document.querySelector('input[name=\"work_date\"]').value === '2026-08-29'"), "Ngày làm việc dự phòng không khớp tên file");
  await evaluate("document.querySelector('[data-action=\"close-modal\"]').click()");

  // Real opening-inventory picker flow: preview, explicit confirmation, then idempotent re-import.
  await evaluate("document.querySelector('[data-view=\"inventory\"]').click()");
  assert(await waitForText("Nạp Excel tồn đầu kỳ"), "Không mở được màn hình tồn đầu kỳ");
  await evaluate("const p=document.querySelector('#openingForm [name=\"period\"]');p.value='2026-08';p.dispatchEvent(new Event('change',{bubbles:true}))");
  const openingDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const openingInputNode = await send("DOM.querySelector", {
    nodeId: openingDocumentNode.root.nodeId,
    selector: "#openingWorkbookInput"
  });
  const openingPath = join(root, "_HANDOFF", "EXTERNAL_INPUTS", "TĐK T8-2026.xlsx thụy.xlsx");
  await send("DOM.setFileInputFiles", { files: [openingPath], nodeId: openingInputNode.nodeId });
  assert(await waitForText("395 dòng nguồn → 334 mã TĐP", 150), "Không xem trước đúng file tồn đầu kỳ thật");
  assert(await evaluate("document.body.innerText.includes('113 mã mới') && document.body.innerText.includes('4 mã tồn âm') && document.body.innerText.includes('0 lỗi')"), "Sai số liệu xem trước tồn đầu kỳ");
  assert(await evaluate("!document.querySelector('[data-action=\"confirm-opening-import\"]').disabled"), "Nút xác nhận tồn đầu kỳ bị khóa sai");
  await evaluate("document.querySelector('[data-action=\"confirm-opening-import\"]').click()");
  assert(await waitForText("Đã nạp 334 mã tồn đầu kỳ · thêm 113 mã hàng mới", 150), "Không xác nhận được tồn đầu kỳ");

  const openingRepeatDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const openingRepeatInput = await send("DOM.querySelector", { nodeId: openingRepeatDocument.root.nodeId, selector: "#openingWorkbookInput" });
  await send("DOM.setFileInputFiles", { files: [openingPath], nodeId: openingRepeatInput.nodeId });
  assert(await waitForText("395 dòng nguồn → 334 mã TĐP", 150), "Không xem trước được lần nạp lại tồn đầu kỳ");
  assert(await evaluate("document.body.innerText.includes('0 mã mới')"), "Nạp lại tồn đầu kỳ vẫn nhận nhầm mã mới");
  await evaluate("document.querySelector('[data-action=\"confirm-opening-import\"]').click()");
  assert(await waitForText("Đã nạp 334 mã tồn đầu kỳ · thêm 0 mã hàng mới", 150), "Nạp lại tồn đầu kỳ không cập nhật an toàn");

  // Real kitchen workbook picker flow: 5 plans / 54 items / XCOM and repeat update.
  await evaluate("document.querySelector('[data-view=\"kitchen\"]').click()");
  assert(await waitForText("Nạp định mức/PO"), "Không mở được màn hình xưởng cơm");
  await evaluate("const d=document.querySelector('#kitchenDate');d.value='2026-08-30';d.dispatchEvent(new Event('change',{bubbles:true}))");
  assert(await waitForText("Nạp định mức/PO"), "Không đổi được ngày xưởng cơm");
  const kitchenDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const kitchenInputNode = await send("DOM.querySelector", { nodeId: kitchenDocumentNode.root.nodeId, selector: "#kitchenWorkbookInput" });
  const kitchenPath = join(root, "_HANDOFF", "EXTERNAL_INPUTS", "xưởng cơm.xlsx");
  await send("DOM.setFileInputFiles", { files: [kitchenPath], nodeId: kitchenInputNode.nodeId });
  assert(await waitForText("5 nhóm bếp/ca · 54 nguyên liệu", 150), "Không xem trước đúng file xưởng cơm thật");
  assert(await evaluate("document.body.innerText.includes('0 nhóm lỗi') && document.body.innerText.includes('MAZDA') && document.body.innerText.includes('46 suất tổng')"), "Sai số liệu xem trước xưởng cơm");
  await evaluate("document.querySelector('[data-action=\"confirm-kitchen-import\"]').click()");
  assert(await waitForText("Đã nạp 5 nhóm xưởng cơm và 54 nguyên liệu", 150), "Không xác nhận được file xưởng cơm");

  const kitchenRepeatDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const kitchenRepeatInput = await send("DOM.querySelector", { nodeId: kitchenRepeatDocument.root.nodeId, selector: "#kitchenWorkbookInput" });
  await send("DOM.setFileInputFiles", { files: [kitchenPath], nodeId: kitchenRepeatInput.nodeId });
  assert(await waitForText("5 cập nhật", 150), "Nạp lại xưởng cơm không chuyển sang cập nhật");
  await evaluate("document.querySelector('[data-action=\"confirm-kitchen-import\"]').click()");
  assert(await waitForText("Đã nạp 5 nhóm xưởng cơm và 54 nguyên liệu", 150), "Không xác nhận được lần nạp lại xưởng cơm");

  // Monthly meal attendance from the customer's real workbook; actual meals stay separate from PO plans.
  const mealAttendanceDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const mealAttendanceInput = await send("DOM.querySelector", { nodeId: mealAttendanceDocument.root.nodeId, selector: "#mealAttendanceInput" });
  const mealAttendancePath = join(root, "bosung.30.8.26", "CHẤM CÔNG+ SUẤT ĂN  2026", "SUẤT ĂN XƯỞNG CƠM 2026", "SUẤT ĂN T8.2026.xlsx");
  await send("DOM.setFileInputFiles", { files: [mealAttendancePath], nodeId: mealAttendanceInput.nodeId });
  assert(await waitForText("205 dòng ngày/bếp/ca", 180), "Không xem trước đúng file chấm suất ăn tháng 8");
  assert(await evaluate("document.body.innerText.includes('28 ngày') && document.body.innerText.includes('6 bếp') && document.body.innerText.includes('Tổng thực ăn 6.020 suất') && document.body.innerText.includes('0 lỗi')"), "Sai số liệu xem trước chấm suất ăn");
  await evaluate("document.querySelector('[data-action=\"confirm-meal-attendance-import\"]').click()");
  assert(await waitForText("Đã nạp 205 dòng chấm suất · thêm 205", 180), "Không xác nhận được chấm suất ăn");
  assert(await waitForText("tổng 6.020 suất thực ăn", 120), "Màn hình không hiển thị tổng suất thực tế sau nhập");

  const repeatMealDocument = await send("DOM.getDocument", { depth: 2, pierce: true });
  const repeatMealInput = await send("DOM.querySelector", { nodeId: repeatMealDocument.root.nodeId, selector: "#mealAttendanceInput" });
  await send("DOM.setFileInputFiles", { files: [mealAttendancePath], nodeId: repeatMealInput.nodeId });
  assert(await waitForText("205 không đổi", 180), "Nạp lại chấm suất không nhận diện dữ liệu không đổi");
  await evaluate("document.querySelector('[data-action=\"confirm-meal-attendance-import\"]').click()");
  assert(await waitForText("không đổi 205", 180), "Nạp lại chấm suất không chống cộng trùng");

  // Real attendance picker flow and payroll result from the customer's August workbook.
  await evaluate("document.querySelector('[data-view=\"payroll\"]').click()");
  assert(await waitForText("Nạp file chấm công"), "Không mở được màn hình chấm công/lương");
  await evaluate("const m=document.querySelector('#payrollMonth');m.value='2026-08';m.dispatchEvent(new Event('change',{bubbles:true}))");
  assert(await waitForText("Nạp file chấm công"), "Không đổi được kỳ bảng lương");
  const attendanceDocumentNode = await send("DOM.getDocument", { depth: 2, pierce: true });
  const attendanceInputNode = await send("DOM.querySelector", { nodeId: attendanceDocumentNode.root.nodeId, selector: "#attendanceInput" });
  const attendancePath = join(root, "bosung.30.8.26", "CHẤM CÔNG+ SUẤT ĂN  2026", "CHẤM CÔNG T8.2026.xlsx");
  await send("DOM.setFileInputFiles", { files: [attendancePath], nodeId: attendanceInputNode.nodeId });
  assert(await waitForText("TRIEN", 180), "Không nạp được nhân sự từ file chấm công tháng 8");
  assert(await evaluate("document.body.innerText.includes('8.000.000 đ')"), "Thực lĩnh của TRIEN không khớp file khách");
  assert(await evaluate("Boolean(document.querySelector('#attendanceForm')) && Boolean(document.querySelector('#payrollAdjustmentForm'))"), "Thiếu form chấm/sửa công hoặc khoản lương tháng");
  const payrollExportFromUi = await evaluate("fetch('/api/export/payroll?month=2026-08').then(async r=>({ok:r.ok,size:(await r.arrayBuffer()).byteLength}))");
  assert(payrollExportFromUi.ok && payrollExportFromUi.size > 1000, "Không tải được bảng lương tháng");

  // User approval and print preparation through the UI; final print is a safe dry-run.
  await evaluate("(()=>{const selectedBatch=document.querySelector('#batchSelect');selectedBatch.value='" + imported.batch.id + "';selectedBatch.dispatchEvent(new Event('change',{bubbles:true}))})()");
  await wait(300);
  await evaluate("document.querySelector('[data-view=\"orders\"]').click()");
  assert(await waitForText("Nguồn: Tách212223.xlsx", 120), "Không chuyển được sang phiên 408 dòng sạch để duyệt");
  assert(await evaluate("document.querySelectorAll('tbody tr').length === 408"), "Phiên Tách212223 không hiển thị đủ 408 dòng");
  assert(await waitForText("Duyệt phiên đơn"), "Không quay lại được phiên đơn để duyệt");
  await evaluate("window.confirm=()=>true;document.querySelector('[data-action=\"approve-batch\"]').click()");
  assert(await waitForText("Đã duyệt phiên đơn · Các đầu ra sẵn sàng", 120), "Không duyệt được phiên đơn qua giao diện");
  const activeBatchId = Number(await evaluate("document.querySelector('#batchSelect').value"));
  printBatchId = activeBatchId;
  await evaluate("document.querySelector('[data-view=\"printing\"]').click()");
  assert(await waitForText("1. Chuẩn bị"), "Không mở được màn hình duyệt/in");
  await evaluate("document.querySelector('[data-action=\"prepare-print\"]').click()");
  assert(await waitForText("Đã chuẩn bị bộ chứng từ; cần duyệt trước khi in", 150), "Không chuẩn bị được bộ in qua giao diện");
  await evaluate("document.querySelector('[data-action=\"approve-print\"]').click()");
  assert(await waitForText("Đã duyệt bộ chứng từ in", 120), "Không duyệt được bộ in qua giao diện");
  assert(await evaluate("document.querySelectorAll('tbody tr').length === 4 && Array.from(document.querySelectorAll('tbody tr')).every(r=>r.innerText.includes('approved'))"), "Hàng đợi in không có đúng 4 chứng từ đã duyệt");
  const printDryRun = await evaluate("fetch('/api/print/run/" + activeBatchId + "',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dry_run:true})}).then(r=>r.json())");
  assert(printDryRun.ok && printDryRun.dry_run && printDryRun.jobs === 4, "Dry-run in không đạt 4 chứng từ");

  // A disposable one-line batch drives the full outgoing-draft UI: create, cancel/release, recreate and confirm issued.
  const outgoingSeed = await evaluate(`(async()=>{
    const json=(url,body)=>fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
    const batch=await json('/api/batches',{work_date:'2026-08-31'});
    const order=await json('/api/orders',{batch_id:batch.batch.id,contractor:'HATRAN',kitchen:'POT',product_code:'I000060',qty:2,actual_received:2,actual_delivered:2,unit:'kg',supplier:'kho',buy_price:14000,sell_price:16000,tax:'KKKNT'});
    const opening=await json('/api/inventory/opening',{period:'2026-08',items:[{product_code:'I000060',qty:50,unit_cost:14000}]});
    const approved=await json('/api/batches/'+batch.batch.id+'/approve',{});
    return {batchId:batch.batch.id,orderOk:order.ok,openingOk:opening.ok,approvedOk:approved.ok};
  })()`);
  assert(outgoingSeed.orderOk && outgoingSeed.openingOk && outgoingSeed.approvedOk, "Không tạo được phiên QC đầu ra một dòng");
  await send("Page.navigate", { url: "http://127.0.0.1:" + appPort });
  assert(await waitForText("1 dòng", 120), "Không nạp lại được phiên QC đầu ra");
  await evaluate("document.querySelector('[data-view=\"documents\"]').click()");
  assert(await waitForText("Dự thảo hóa đơn đầu ra", 120), "Thiếu khu vực trạng thái hóa đơn đầu ra");
  await evaluate("document.querySelector('[data-action=\"create-outgoing-drafts\"]').click()");
  assert(await waitForText("Xác nhận đã ký/phát hành", 120), "Không tạo/hiển thị được dự thảo đầu ra qua giao diện");
  await evaluate("window.confirm=()=>true;document.querySelector('[data-action=\"cancel-outgoing-draft\"]').click()");
  assert(await waitForText("Đã hủy dự thảo và nhả tồn khả dụng", 120), "Không hủy/nhả tồn dự thảo qua giao diện");
  assert(await waitForText("Đã hủy", 120), "Trạng thái hủy không hiển thị lại");
  await evaluate("document.querySelector('[data-action=\"create-outgoing-drafts\"]').click()");
  assert(await waitForText("Xác nhận đã ký/phát hành", 120), "Không tạo lại được dự thảo đã hủy");
  await evaluate("document.querySelector('[data-action=\"confirm-outgoing-issued\"]').click()");
  assert(await waitForText("Đã ghi nhận hóa đơn phát hành và ghi xuất kho", 120), "Không xác nhận được hóa đơn đã phát hành");
  assert(await waitForText("Đã phát hành", 120), "Trạng thái phát hành không hiển thị lại");

  const shot = await send("Page.captureScreenshot", { format: "png", fromSurface: true });
  writeFileSync(join(appDir, "qc_browser.png"), Buffer.from(shot.data, "base64"));
  assert(errors.length === 0, "Lỗi trình duyệt: " + errors.join(" | "));
  console.log(JSON.stringify({
    ok: true,
    importedOrders: imported.orders.length,
    selectedSheetOrders: 323,
    editAndPasteFlow: "saved edit / added one row in real forms",
    datedSheetAutoSelected: "29.08",
    errorRows: imported.summary.totals.errors,
    warningRows: imported.summary.totals.warnings,
    screens: requiredViews.length,
    openingWorkbook: "395 rows / 334 codes / repeat update",
    kitchenWorkbook: "5 plans / 54 items / repeat update",
    mealAttendanceWorkbook: "205 daily kitchen/shift rows / 6,020 meals / repeat safe",
    attendanceWorkbook: "August legacy payroll / TRIEN 8,000,000 VND",
    paymentRequestSettings: "TDP representative / Vietcombank 1052787580",
    printApproval: "4 approved documents / dry-run",
    supplierRuleUi: "toggle and persist",
    debtPeriodUi: "range / adjustment / Excel export",
    payrollUi: "manual forms / Excel export",
    outgoingUi: "draft / cancel and release / recreate / confirm issued",
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
  if (printBatchId) {
    try { rmSync(join(appDir, "data", "print_jobs", String(printBatchId)), { recursive: true, force: true }); } catch {}
  }
}
